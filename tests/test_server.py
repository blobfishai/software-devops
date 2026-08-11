"""End-to-end smoke test of the standalone server: REST + MCP surfaces, session
isolation, and a full kill-switch episode driven exactly the way an agent
harness would drive it."""

import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _req(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = _free_port()
    runtime = tmp_path_factory.mktemp("serve_runtime")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "serve.py"), "--world", str(ROOT / "world"),
         "--host", "127.0.0.1", "--port", str(port),
         "--runtime-dir", str(runtime)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(100):
        try:
            _req(base + "/healthz")
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("server did not come up")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


def test_rest_surface(server):
    health = _req(server + "/healthz")
    assert health["status"] == "ok" and health["tools"] == 82 and health["tasks"] == 76

    tasks = _req(server + "/tasks")
    assert {t["task_id"] for t in tasks} >= {"tsk_payments_retry",
                                             "tsk_gateway_v510_rollback"}
    assert all("vcode" not in t for t in tasks)

    tools = _req(server + "/tools")
    names = {t["name"] for t in tools}
    assert {"list_services", "deploy_service", "resolve_alert"} <= names


def test_rest_session_isolation(server):
    a = _req(server + "/sessions", {})["session_id"]
    b = _req(server + "/sessions", {})["session_id"]
    _req(server + "/sessions/%s/tools/set_feature_flag" % a,
         {"arguments": {"key": "instant_refunds", "environment": "production",
                        "enabled": False}})
    flags_b = _req(server + "/sessions/%s/tools/list_feature_flags" % b,
                   {"arguments": {"environment": "production"}})
    by_key = {f["key"]: f for f in flags_b["rows"]}
    assert by_key["instant_refunds"]["enabled"] == 1  # b unaffected


def test_rest_verify_fails_on_untouched_session(server):
    sid = _req(server + "/sessions", {})["session_id"]
    out = _req(server + "/sessions/%s/verify" % sid,
               {"task_id": "tsk_instant_refunds_killswitch"})
    assert out["passed"] is False and out["reward"] == 0.0
    # graded partial credit is reported alongside the binary reward
    assert 0.0 <= out["score"] < 1.0
    dims = {a["dimension"] for a in out["assertions"]}
    assert {"correctness", "quality"} <= dims


def test_mcp_full_killswitch_episode(server):
    sid = "mcp_episode_1"
    hdr = {"Mcp-Session-Id": sid}

    def rpc(method, params=None, mid=1):
        return _req(server + "/mcp", {"jsonrpc": "2.0", "id": mid,
                                      "method": method, "params": params or {}},
                    hdr)

    init = rpc("initialize")["result"]
    assert init["protocolVersion"]

    listing = rpc("tools/list")["result"]["tools"]
    names = {t["name"] for t in listing}
    assert {"task_start", "task_verify", "set_feature_flag"} <= names

    def tool(name, arguments=None):
        out = rpc("tools/call", {"name": name, "arguments": arguments or {}})
        return json.loads(out["result"]["content"][0]["text"])

    start = tool("task_start", {"task_id": "tsk_instant_refunds_killswitch"})
    assert "instant_refunds" in start["instruction"]

    tool("acknowledge_alert", {"alert_id": 9603})
    tool("set_feature_flag", {"key": "instant_refunds",
                              "environment": "production", "enabled": False})
    tool("resolve_alert", {"alert_id": 9603})
    tool("update_incident", {"incident_id": 9702, "status": "resolved"})
    tool("post_message", {"channel": "#incidents",
                          "body": "Kill-switched instant_refunds; metrics recovered; incident 9702 resolved."})
    tool("publish_status_update", {"state": "resolved", "title": "Checkout errors resolved",
                                   "body": "A recent feature caused elevated checkout errors; "
                                           "it has been disabled."})
    tool("update_ticket", {"key": "ENG-2311", "status": "done"})

    verdict = tool("task_verify", {})
    assert verdict["passed"] is True and verdict["reward"] == 1.0, verdict
    assert verdict["score"] == 1.0
    assert all(a["passed"] for a in verdict["assertions"])


def test_mcp_tool_error_rolls_back(server):
    sid = "mcp_episode_2"
    hdr = {"Mcp-Session-Id": sid}

    def tool(name, arguments=None, mid=2):
        out = _req(server + "/mcp", {"jsonrpc": "2.0", "id": mid,
                                     "method": "tools/call",
                                     "params": {"name": name,
                                                "arguments": arguments or {}}}, hdr)
        return json.loads(out["result"]["content"][0]["text"]), out["result"]["isError"]

    _req(server + "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {}}, hdr)
    result, is_error = tool("resolve_alert", {"alert_id": 9603})
    assert is_error and "SLO" in result["error"]
    alerts, _ = tool("list_alerts", {"status": "firing"})
    ids = {a["alert_id"] for a in alerts["rows"]}
    assert 9603 in ids  # still firing, nothing half-committed
