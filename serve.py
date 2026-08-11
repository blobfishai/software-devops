#!/usr/bin/env python3
"""Standalone world server for the software-devops world (stdlib only, Python 3.12+).

Serves a blobfish Format-A world package over HTTP:

  REST
    GET  /healthz                          liveness
    GET  /world                            world summary (never verifier code)
    GET  /tasks                            [{task_id, instruction, difficulty}]
    GET  /tools                            [{name, description, parameters}]
    POST /sessions                         -> {"session_id"}  (isolated DB fork)
    POST /sessions/<id>/reset              re-fork from the pristine seed
    POST /sessions/<id>/tools/<name>       {"arguments": {...}} -> tool result
    POST /sessions/<id>/verify             {"task_id", "final_answer"?} -> {passed, reward}

  MCP (JSON-RPC 2.0)
    POST /mcp    methods: initialize, ping, tools/list, tools/call
                 session via Mcp-Session-Id or X-Blobfish-Session header
                 meta tools: world_info, task_list, task_start, task_verify, episode_abort

Sessions are independent copies of environment.db, so concurrent rollouts never
collide. Every tool call snapshots the session DB and rolls back on exceptions
or structured errors ({"ok": false} / non-empty "error"). Verifiers run in an
isolated subprocess against a read-only connection.
"""

import argparse
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VCODE_CHILD = r"""
import sys, json, sqlite3
payload = json.loads(sys.stdin.read())
db = payload["db_path"]
fa = payload.get("final_answer", "")
conn = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
def get_db():
    c = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
ns = {"conn": conn, "sqlite3": sqlite3, "json": json, "get_db": get_db,
      "db_path": db, "DB_PATH": db, "final_answer": fa, "answer": fa}
try:
    exec(compile(payload["vcode"], "<vcode>", "exec"), ns)
    out = {"passed": True, "error": None}
except AssertionError as e:
    out = {"passed": False, "error": "assertion: " + str(e)}
except Exception as e:
    out = {"passed": False, "error": type(e).__name__ + ": " + str(e)}
sc = ns.get("score")
if isinstance(sc, (int, float)):
    out["score"] = float(sc)
checks = ns.get("_checks")
if isinstance(checks, list):
    try:
        out["assertions"] = [{"dimension": c[0], "name": c[1],
                              "passed": bool(c[2]), "message": c[3]}
                             for c in checks]
    except Exception:
        pass
print(json.dumps(out))
"""


class World:
    def __init__(self, world_dir, runtime_dir):
        self.dir = pathlib.Path(world_dir)
        self.db_path = self.dir / "environment.db"
        self.tools = json.loads((self.dir / "tools.json").read_text())
        self.tasks = json.loads((self.dir / "tasks.json").read_text())
        self.meta = {}
        wj = self.dir / "world.json"
        if wj.exists():
            self.meta = json.loads(wj.read_text())
        src = (self.dir / "tools_combined.py").read_text()
        self.tool_ns = {}
        exec(compile(src, "tools_combined.py", "exec"), self.tool_ns)
        self.by_name = {t["name"]: t for t in self.tools}
        self.task_by_id = {t["task_id"]: t for t in self.tasks}
        self.runtime = pathlib.Path(runtime_dir)
        self.runtime.mkdir(parents=True, exist_ok=True)
        # Sessions fork from a private copy taken at load, not from world/ itself.
        # tools.json and tasks.json are read once into memory, so a rebuild while
        # a long run is in flight would otherwise leave the run executing the old
        # task set against the new database - a silently mixed world whose results
        # look plausible and mean nothing. A multi-hour calibration sweep was lost
        # to exactly that before this existed.
        self.fork_src = self.runtime / "pristine.db"
        shutil.copyfile(self.db_path, self.fork_src)
        self.sessions = {}
        self.lock = threading.Lock()

    # ---------------------------------------------------------------- sessions
    def create_session(self, session_id=None):
        sid = session_id or ("sess_" + uuid.uuid4().hex[:12])
        db = self.runtime / (sid + ".db")
        shutil.copyfile(self.fork_src, db)
        with self.lock:
            self.sessions[sid] = {"db": db, "task_id": None,
                                  "lock": threading.Lock()}
        return sid

    def session(self, sid):
        with self.lock:
            if sid not in self.sessions and sid == "default":
                pass  # lazily created below
            sess = self.sessions.get(sid)
        if sess is None and sid == "default":
            self.create_session("default")
            sess = self.sessions["default"]
        return sess

    def reset_session(self, sid):
        sess = self.session(sid)
        if sess is None:
            return None
        with sess["lock"]:
            shutil.copyfile(self.fork_src, sess["db"])
            sess["task_id"] = None
        return sid

    # ------------------------------------------------------------------ tools
    def call_tool(self, sid, name, arguments):
        sess = self.session(sid)
        if sess is None:
            return {"ok": False, "error": "unknown session: %s" % sid}
        if name not in self.by_name:
            return {"ok": False, "error": "unknown tool: %s" % name}
        fn = self.tool_ns.get(name)
        arguments = dict(arguments or {})
        arguments.pop("db_path", None)
        with sess["lock"]:
            snapshot = sess["db"].with_suffix(".snap")
            shutil.copyfile(sess["db"], snapshot)
            try:
                result = fn(db_path=str(sess["db"]), **arguments)
            except TypeError as e:
                shutil.copyfile(snapshot, sess["db"])
                spec = self.by_name.get(name, {})
                params = spec.get("parameters", [])
                req = [p["name"] for p in params if p.get("required")]
                opt = [p["name"] for p in params if not p.get("required")]
                return {"ok": False,
                        "error": "bad arguments for %s: %s" % (name, e),
                        "accepts": {"required": req, "optional": opt},
                        "hint": "%s(%s)" % (name, ", ".join(
                            req + ["%s?" % o for o in opt]))}
            except Exception as e:  # noqa: BLE001
                shutil.copyfile(snapshot, sess["db"])
                return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
            finally:
                snap_exists = snapshot.exists()
            if self._is_structured_error(result) and snap_exists:
                shutil.copyfile(snapshot, sess["db"])
            snapshot.unlink(missing_ok=True)
        if isinstance(result, list):
            return {"rows": result, "count": len(result)}
        if isinstance(result, dict):
            return result
        return {"result": result}

    @staticmethod
    def _is_structured_error(result):
        if not isinstance(result, dict):
            return False
        if result.get("ok") is False or result.get("success") is False:
            return True
        err = result.get("error")
        return bool(err) and result.get("ok") is not True and result.get("success") is not True

    # ----------------------------------------------------------------- verify
    def verify(self, sid, task_id, final_answer=""):
        sess = self.session(sid)
        if sess is None:
            return {"passed": False, "reward": 0.0, "error": "unknown session: %s" % sid}
        task_id = task_id or sess.get("task_id")
        task = self.task_by_id.get(task_id)
        if task is None:
            return {"passed": False, "reward": 0.0, "error": "unknown task: %s" % task_id}
        payload = json.dumps({"db_path": str(sess["db"]), "vcode": task.get("vcode", ""),
                              "final_answer": final_answer or ""})
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", VCODE_CHILD],
                                  input=payload, capture_output=True, text=True,
                                  timeout=30)
            out = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as e:  # noqa: BLE001
            return {"passed": False, "reward": 0.0,
                    "error": "verifier execution failed: %s" % e, "task_id": task_id}
        out["reward"] = 1.0 if out.get("passed") else 0.0
        out.setdefault("score", out["reward"])  # graded partial credit
        out["task_id"] = task_id
        return out

    # ------------------------------------------------------------------- meta
    def public_task(self, t):
        return {"task_id": t["task_id"], "instruction": t["instruction"],
                "difficulty": t.get("difficulty", "medium")}

    def public_tools(self):
        return [{"name": t["name"], "description": t["description"],
                 "parameters": t.get("json_schema", {}).get("parameters", {})}
                for t in self.tools]

    def summary(self):
        return {"world_id": self.meta.get("world_id", self.dir.name),
                "vertical": self.meta.get("vertical", ""),
                "brief": self.meta.get("brief", ""),
                "counts": self.meta.get("counts", {"tools": len(self.tools),
                                                   "tasks": len(self.tasks)}),
                "splits": self.meta.get("splits", {}),
                "difficulty": self.meta.get("difficulty", {})}


META_TOOLS = [
    {"name": "world_info", "description": "Summary of this world (services domain, counts, splits).",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "task_list", "description": "List the available tasks (id, instruction, difficulty).",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "task_start",
     "description": "Start a task: resets this session to the pristine seed and returns the instruction.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}},
                     "required": ["task_id"]}},
    {"name": "task_verify",
     "description": "Verify the current (or given) task against this session's state. Returns passed/reward.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"},
                                                      "final_answer": {"type": "string"}},
                     "required": []}},
    {"name": "episode_abort", "description": "Abort the episode: reset this session to the pristine seed.",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
]


class Handler(BaseHTTPRequestHandler):
    world = None  # injected

    # --------------------------------------------------------------- plumbing
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:  # noqa: BLE001
            return None

    def log_message(self, fmt, *args):  # quiet default logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------- GET
    def do_GET(self):  # noqa: N802
        w = self.world
        if self.path == "/healthz":
            return self._send(200, {"status": "ok", "tools": len(w.tools),
                                    "tasks": len(w.tasks)})
        if self.path == "/world":
            return self._send(200, w.summary())
        if self.path == "/tasks":
            return self._send(200, [w.public_task(t) for t in w.tasks])
        if self.path == "/tools":
            return self._send(200, w.public_tools())
        return self._send(404, {"error": "not found"})

    # ------------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        w = self.world
        body = self._body()
        if body is None:
            return self._send(400, {"error": "invalid JSON body"})
        parts = [p for p in self.path.split("/") if p]

        if self.path == "/mcp":
            return self._mcp(body)
        if self.path == "/sessions":
            sid = w.create_session(body.get("session_id"))
            return self._send(200, {"session_id": sid})
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "reset":
            if w.reset_session(parts[1]) is None:
                return self._send(404, {"error": "unknown session: %s" % parts[1]})
            return self._send(200, {"session_id": parts[1], "reset": True})
        if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "verify":
            return self._send(200, w.verify(parts[1], body.get("task_id"),
                                            body.get("final_answer", "")))
        if len(parts) == 4 and parts[0] == "sessions" and parts[2] == "tools":
            result = w.call_tool(parts[1], parts[3], body.get("arguments", body))
            return self._send(200, result)
        return self._send(404, {"error": "not found"})

    # -------------------------------------------------------------------- MCP
    def _mcp(self, msg):
        w = self.world
        sid = (self.headers.get("Mcp-Session-Id")
               or self.headers.get("X-Blobfish-Session") or "default")
        w.session(sid) or w.create_session(sid)
        mid = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        def reply(result):
            resp = {"jsonrpc": "2.0", "id": mid, "result": result}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", sid)
            body = json.dumps(resp).encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        if method == "initialize":
            return reply({"protocolVersion": "2024-11-05",
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": w.summary()["world_id"],
                                         "version": "1.0"}})
        if method in ("notifications/initialized", "notifications/cancelled"):
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if method == "ping":
            return reply({})
        if method == "tools/list":
            listing = list(META_TOOLS)
            for t in w.public_tools():
                listing.append({"name": t["name"], "description": t["description"],
                                "inputSchema": t["parameters"]})
            return reply({"tools": listing})
        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            result, is_error = self._mcp_call(sid, name, args)
            return reply({"content": [{"type": "text",
                                       "text": json.dumps(result)}],
                          "isError": is_error})
        return self._send(200, {"jsonrpc": "2.0", "id": mid,
                                "error": {"code": -32601,
                                          "message": "method not found: %s" % method}})

    def _mcp_call(self, sid, name, args):
        w = self.world
        sess = w.session(sid)
        if name == "world_info":
            return w.summary(), False
        if name == "task_list":
            return [w.public_task(t) for t in w.tasks], False
        if name == "task_start":
            task = w.task_by_id.get(args.get("task_id", ""))
            if task is None:
                return {"error": "unknown task: %s" % args.get("task_id")}, True
            w.reset_session(sid)
            sess = w.session(sid)
            sess["task_id"] = task["task_id"]
            return {"task_id": task["task_id"],
                    "instruction": task["instruction"],
                    "difficulty": task.get("difficulty", "medium"),
                    "session_id": sid}, False
        if name == "task_verify":
            out = w.verify(sid, args.get("task_id"), args.get("final_answer", ""))
            return out, False
        if name == "episode_abort":
            w.reset_session(sid)
            return {"aborted": True, "session_id": sid}, False
        result = w.call_tool(sid, name, args)
        return result, World._is_structured_error(result)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="world")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--runtime-dir", default=None,
                    help="where session DB forks live (default <world>/runs/serve)")
    args = ap.parse_args()

    world_dir = pathlib.Path(args.world)
    runtime = args.runtime_dir or (world_dir / "runs" / "serve")
    Handler.world = World(world_dir, runtime)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("software-devops world serving on http://%s:%d  (world=%s, %d tools, %d tasks)"
          % (args.host, args.port, world_dir, len(Handler.world.tools),
             len(Handler.world.tasks)), file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
