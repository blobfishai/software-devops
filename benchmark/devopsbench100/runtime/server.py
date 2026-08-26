#!/usr/bin/env python3
"""DevOpsBench-100 in-pack world server (stdlib only, Python 3.12+).

One Harbor task pack = one pinned NovaCart task.  This server bakes the world
into the pack and exposes exactly two surfaces:

  Agent-facing (MCP, Streamable HTTP JSON-RPC at POST /mcp):
    initialize, ping, tools/list, tools/call - the 97 world tools ONLY.
    The blobfish meta-tools (task_start / task_verify / task_list /
    episode_abort / world_info) are NOT served: the task is fixed by the
    DOB_TASK_ID environment variable baked into docker-compose, the
    instruction ships as instruction.md, and there is no agent-reachable
    verification or reward surface at all.

  Verifier-facing (POST /verify, capability-token gated):
    Runs this task's standalone vcode verifier (verify_task.py, generated the
    same way export_harbor.py generates verify_<id>.py) in an isolated
    subprocess against the CURRENT world state and returns the full report.
    The pack stores only the SHA-256 digest of the token (spec.json); the
    token itself exists only in tests/test.sh, which runs outside the agent
    container.  A wrong or missing token gets a 404, indistinguishable from
    the route not existing.

State model: a single live SQLite database, copied from the pristine
environment.db at startup.  Every tool call snapshots the database first and
rolls back on exceptions or structured errors ({"ok": false} / non-empty
"error"), exactly like the upstream serve.py, so failed calls never corrupt
state.  No wall clock, randomness, network, or LLM is on the reward path.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL_VERSION = "2024-11-05"


class DevOpsWorld:
    def __init__(self, world_dir, state_dir, task_id=None):
        self.dir = pathlib.Path(world_dir)
        self.spec = json.loads((self.dir / "spec.json").read_text())
        want = task_id or os.environ.get("DOB_TASK_ID") or self.spec["task_id"]
        if want != self.spec["task_id"]:
            raise SystemExit("DOB_TASK_ID=%r does not match the packed task %r"
                             % (want, self.spec["task_id"]))
        self.task_id = self.spec["task_id"]
        self.tools = json.loads((self.dir / "tools.json").read_text())
        self.by_name = {t["name"]: t for t in self.tools}
        src = (self.dir / "tools_combined.py").read_text()
        self.tool_ns: dict = {}
        exec(compile(src, "tools_combined.py", "exec"), self.tool_ns)
        state = pathlib.Path(state_dir)
        state.mkdir(parents=True, exist_ok=True)
        self.db = state / "world.db"
        shutil.copyfile(self.dir / "environment.db", self.db)
        self.lock = threading.Lock()
        self.successful_tool_calls = 0
        self.failed_tool_calls = 0

    # ------------------------------------------------------------------ tools
    def list_tools(self):
        out = []
        for t in self.tools:
            schema = (t.get("json_schema") or {}).get("parameters") or {
                "type": "object", "properties": {}, "required": []}
            out.append({"name": t["name"], "description": t["description"],
                        "inputSchema": schema})
        return out

    def call_tool(self, name, arguments):
        if name not in self.by_name:
            self.failed_tool_calls += 1
            return {"ok": False, "error": "unknown tool: %s" % name}
        fn = self.tool_ns.get(name)
        arguments = dict(arguments or {})
        arguments.pop("db_path", None)
        with self.lock:
            snapshot = self.db.with_suffix(".snap")
            shutil.copyfile(self.db, snapshot)
            try:
                result = fn(db_path=str(self.db), **arguments)
            except TypeError as e:
                shutil.copyfile(snapshot, self.db)
                snapshot.unlink(missing_ok=True)
                spec = self.by_name.get(name, {})
                params = spec.get("parameters", [])
                req = [p["name"] for p in params if p.get("required")]
                opt = [p["name"] for p in params if not p.get("required")]
                self.failed_tool_calls += 1
                return {"ok": False,
                        "error": "bad arguments for %s: %s" % (name, e),
                        "accepts": {"required": req, "optional": opt},
                        "hint": "%s(%s)" % (name, ", ".join(
                            req + ["%s?" % o for o in opt]))}
            except Exception as e:  # noqa: BLE001
                shutil.copyfile(snapshot, self.db)
                snapshot.unlink(missing_ok=True)
                self.failed_tool_calls += 1
                return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
            if self._is_structured_error(result):
                shutil.copyfile(snapshot, self.db)
            snapshot.unlink(missing_ok=True)
        if isinstance(result, list):
            result = {"rows": result, "count": len(result)}
        elif not isinstance(result, dict):
            result = {"result": result}
        if self._is_structured_error(result):
            self.failed_tool_calls += 1
        else:
            self.successful_tool_calls += 1
        return result

    @staticmethod
    def _is_structured_error(result):
        if not isinstance(result, dict):
            return False
        if result.get("ok") is False or result.get("success") is False:
            return True
        err = result.get("error")
        return bool(err) and result.get("ok") is not True and result.get("success") is not True

    # ----------------------------------------------------------------- verify
    def verify(self, token):
        digest = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
        if digest != self.spec["verify_token_sha256"]:
            raise PermissionError("bad verification token")
        with self.lock:
            proc = subprocess.run(
                [sys.executable, "-I", str(self.dir / "verify_task.py"), str(self.db)],
                capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return {"task_id": self.task_id, "passed": False, "reward": 0.0,
                    "error": "verifier exited %d: %s"
                             % (proc.returncode, proc.stderr[-400:])}
        report = json.loads(proc.stdout)
        report["successful_tool_calls"] = self.successful_tool_calls
        report["failed_tool_calls"] = self.failed_tool_calls
        report["report_sha256"] = hashlib.sha256(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return report


# ---------------------------------------------------------------------- HTTP
def rpc_response(world: DevOpsWorld, request):
    request_id = request.get("id") if isinstance(request, dict) else None
    method = request.get("method") if isinstance(request, dict) else None
    if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return None
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" \
            or not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32600, "message": "Invalid Request"}}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "devopsbench-novacart", "version": "1.0.0"},
            "instructions": ("NovaCart engineering world. Work the assigned "
                             "ticket end to end with these tools; company "
                             "policy lives in the knowledge base "
                             "(search_docs / get_document)."),
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"tools": world.list_tools()}}
    if method == "tools/call":
        params = request.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        result = world.call_tool(params.get("name", ""), params.get("arguments"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False)}],
            "isError": DevOpsWorld._is_structured_error(result)}}
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32601, "message": "Method not found"}}


class Handler(BaseHTTPRequestHandler):
    world: DevOpsWorld = None  # injected
    server_version = "DevOpsBenchWorld/1.0"

    def log_message(self, fmt, *args):
        return

    def _json(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            return self._json(200, {"status": "ok", "task_id": self.world.task_id,
                                    "tools": len(self.world.tools)})
        return self._json(404, {"error": "not_found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if self.path == "/verify":
            try:
                report = self.world.verify(self.headers.get("X-Verify-Token"))
            except PermissionError:
                return self._json(404, {"error": "not_found"})
            return self._json(200, report)
        if self.path != "/mcp":
            return self._json(404, {"error": "not_found"})
        try:
            request = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return self._json(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700, "message": "Parse error"}})
        if isinstance(request, list):
            responses = [r for item in request
                         if (r := rpc_response(self.world, item)) is not None]
            return self._json(200, responses)
        response = rpc_response(self.world, request)
        if response is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        return self._json(200, response)


def main():
    world_dir = os.environ.get("DOB_WORLD_DIR", "/opt/devopsbench")
    state_dir = os.environ.get("DOB_STATE", "/workspace/state")
    host = os.environ.get("DOB_HOST", "0.0.0.0")
    port = int(os.environ.get("DOB_PORT", "8080"))
    Handler.world = DevOpsWorld(world_dir, state_dir)
    print("devopsbench world serving task %s on %s:%d"
          % (Handler.world.task_id, host, port), file=sys.stderr)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
