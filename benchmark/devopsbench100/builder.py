#!/usr/bin/env python3
"""Build the DevOpsBench-100 release: Harbor task packs + Hugging Face files.

Reads the committed catalog (benchmark/devopsbench100/catalog.json) and the
world package (world/), and writes dist/devopsbench-100/:

  harbor/tasks/dob100-NNN-<slug>/     one self-contained Harbor 1.4 pack per task
  harbor/dataset/dataset.toml         blobfishai/devopsbench-100 + content digests
  huggingface/                        tasks.jsonl, per-task JSON, world source,
                                      verifiers, licenses, dataset card
  reports/build.json                  measured build statistics

Every pack bakes the full world from in-pack source onto a digest-pinned
public python:3.12-slim base - no private registry anywhere.  Generation is
deterministic and makes no network calls.

Run:  python3 benchmark/devopsbench100/builder.py
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import pathlib
import re
import shutil
import sqlite3
import stat
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from export_harbor import VERIFIER_TEMPLATE  # noqa: E402  (reused verbatim)

RELEASE_NAME = "DevOpsBench-100"
RELEASE_SLUG = "devopsbench-100"
RELEASE_VERSION = "2.0.0"
HARBOR_ORG = "blobfishai"
DATA_LICENSE = "CC-BY-4.0"
CODE_LICENSE = "Apache-2.0"
PYTHON_BASE = ("python:3.12-slim@sha256:"
               "7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17")
PROMPT_LEAKAGE_PATTERN = re.compile(
    r"\b(?:read_exercise|write_implementation|run_exercise_tests|write_runbook|"
    r"submit_answer|submit_diagnosis)\s*\(|"
    r"\b(?:grading|hidden tests?|benchmark|verifier|expected tool calls?)\b",
    flags=re.IGNORECASE,
)

CATEGORY_LABELS = {
    "error_rate_reduction": "Error-rate SLO recovery",
    "latency_optimization": "Latency optimization",
    "feature_flag": "Feature-flag operation",
    "security_incident": "Security incident response",
    "api_migration": "API migration",
    "multi_service_rollout": "Multi-service rollout",
    "flaky_test": "Flaky-test remediation",
    "reconciliation": "Cross-source reconciliation",
    "aiops_detection": "AIOps detection",
    "aiops_localization": "AIOps localization",
    "aiops_analysis": "AIOps root-cause analysis",
    "code_implementation": "Code implementation",
    "cross_system": "Cross-system source of truth",
    "handover": "Incident handover",
    "horizon": "Long-horizon delivery",
    "workspace": "Workspace scripting",
    "attribution": "Change attribution",
    "judgement": "Operational judgement / restraint",
    "human_gated": "Human-approval gated change",
}


def write_text(path: pathlib.Path, value: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_json(path: pathlib.Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def toml_str(value: str) -> str:
    # json string escaping is valid TOML basic-string escaping
    return json.dumps(value, ensure_ascii=False)


def verification_token(bench_id: str) -> str:
    """Capability token for POST /verify.  The world image stores only the
    SHA-256 of this value; the agent container never sees it."""
    return hashlib.sha256(
        f"DevOpsBench-100 verifier capability::{bench_id}".encode()).hexdigest()


def check_names(vcode: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dim, name in re.findall(
            r"_c\(\s*['\"](\w+)['\"]\s*,\s*['\"]([\w./-]+)['\"]", vcode):
        out.setdefault(dim, []).append(name)
    return out


CONTEXT_TOOL_PALETTE = (
    "jira_search",
    "linear_list_issues",
    "github_list_issues",
    "sentry_search_issues",
    "pd_list_incidents",
    "confluence_search",
    "read_owner_spreadsheet",
    "query_local_deploy_log",
    "list_alerts",
    "get_status_page",
    "list_feature_flags",
    "list_incidents",
)

# These calls encode the operating controls that distinguish an end-to-end
# employee workflow from a lucky final-state write.  They are required as a
# set, never in one exact order; the task-specific vcode still decides whether
# the resulting state and answers are correct.
REQUIRED_PROCEDURE_TOOLS = {
    "search_docs",
    "get_document",
    "acknowledge_alert",
    "post_message",
    "publish_status_update",
    "assess_canary",
    "promote_canary",
    "list_migrations",
    "get_ci_run",
    "get_traffic_stats",
    "run_exercise_tests",
}


def realism_vcode(task: dict) -> str:
    """Add auditable read/control requirements without grading call order."""

    required = sorted(
        {call["tool"] for call in task.get("expected_calls", [])}
        & REQUIRED_PROCEDURE_TOOLS
    )
    if not required:
        return task["vcode"]
    controls = [
        "",
        "# Release-level realism controls: required evidence/control tools may be",
        "# called in any order and may be surrounded by additional investigation.",
    ]
    for tool in required:
        controls.append(
            f'_c("correctness", "required_tool_{tool}", _called("{tool}"), '
            f'"use {tool} as part of the evidence-backed workflow")'
        )
    return task["vcode"].rstrip() + "\n" + "\n".join(controls) + "\n"


def employee_instruction(task: dict, row: dict) -> str:
    """Remove harness syntax while preserving the employee's actual outcome."""

    prompt = task["instruction"].strip()
    prompt = re.sub(
        r"Read the specification with read_exercise\('[^']+'\), write your implementation with "
        r"write_implementation, and run it with run_exercise_tests until the visible tests pass\.",
        "Use the repository's documented behavior to complete it and leave the available test suite passing.",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = prompt.replace(
        "Write it with write_runbook(title=..., body=...).",
        "Leave the completed runbook in the shared on-call knowledge base.",
    )
    prompt = prompt.replace(
        "The visible tests are not the whole specification. Other tests run at grading time and are not "
        "shown to you, so satisfying what you can see is necessary and not sufficient — read the "
        "specification and implement what it actually says.",
        "Cover the documented edge cases, not only the obvious happy path. Keep the change scoped to this "
        "module and leave enough test evidence for an engineer reviewing the patch.",
    )
    prompt = re.sub(
        r"Submit your finding under scope '([^']+)' with ",
        r"Leave an audit-ready diagnosis for '\1' that names ",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"Submit the number with submit_answer\([^\n]*\)\.?",
        "Give the team the number and cite the live records that support it.",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"with submit_(?:answer|diagnosis)\([^\n]*\)\.?",
        "in the task's auditable result.",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = prompt.replace("submit_diagnosis(...)", "the incident record")
    prompt = prompt.replace("submit_answer(...)", "the task result")
    if len(prompt.split()) < 45:
        prompt += (
            " Reconcile the live systems rather than trusting a single tracker, preserve unrelated "
            "production state, and leave enough evidence for the next engineer to reproduce the conclusion."
        )
    return prompt


def distinct_reference_calls(
    source_calls: list[dict],
    seen_sequences: set[tuple[str, ...]],
) -> list[dict]:
    """Disambiguate repeated family walks with a useful cross-system read."""

    calls = [dict(call, args=dict(call.get("args", {}))) for call in source_calls]
    sequence = tuple(call["tool"] for call in calls)
    if sequence not in seen_sequences:
        seen_sequences.add(sequence)
        return calls
    for tool in CONTEXT_TOOL_PALETTE:
        candidate = [{"tool": tool, "args": {}}, *calls]
        candidate_sequence = tuple(call["tool"] for call in candidate)
        if candidate_sequence not in seen_sequences:
            seen_sequences.add(candidate_sequence)
            return candidate
    raise ValueError("could not create a distinct task reference sequence")


def _literal_dict(vcode: str, name: str) -> dict[str, Any]:
    match = re.search(rf"^{re.escape(name)}\s*=\s*(\{{.*?\}})$", vcode, re.MULTILINE)
    if not match:
        return {}
    value = ast.literal_eval(match.group(1))
    return value if isinstance(value, dict) else {}


def rubric_criteria(task: dict, bench_id: str) -> list[dict[str, str]]:
    """Expose the concrete subconditions behind the executable vcode."""

    rows: list[dict[str, str]] = []

    def add(category: str, criterion_id: str, description: str, enforced_by: str) -> None:
        rows.append(
            {
                "id": f"{category}.{criterion_id}",
                "category": category,
                "description": description,
                "enforced_by": enforced_by,
            }
        )

    for dimension, names in check_names(task["vcode"]).items():
        for name in names:
            add(
                dimension,
                name,
                f"For {bench_id}, verify {name.replace('_', ' ')} against the final SQLite state and append-only audit log.",
                f"vcode:{dimension}.{name}",
            )
    observed: set[str] = set()
    for call in task["expected_calls"]:
        tool = call["tool"]
        if tool in observed:
            continue
        observed.add(tool)
        arguments = call.get("args", {})
        add(
            "investigation",
            tool,
            f"Use {tool} to establish the task-scoped evidence represented by {arguments!r}; no fixed call order is graded.",
            "vcode:tool_calls and task-specific evidence checks",
        )
    for table, digest in sorted(_literal_dict(task["vcode"], "_FROZEN").items()):
        add(
            "containment",
            f"{table}.digest",
            f"Leave unrelated {table} rows unchanged; the verifier recomputes frozen digest {digest} as part of world integrity.",
            "vcode:correctness.world_invariants_intact",
        )
    for table, count in sorted(_literal_dict(task["vcode"], "_FIXED_ROWS").items()):
        add(
            "containment",
            f"{table}.row_count",
            f"Preserve exactly {count} seeded rows in {table}; additions or deletions outside scope fail world integrity.",
            "vcode:correctness.world_invariants_intact",
        )
    submission = next(
        (
            call
            for call in task["expected_calls"]
            if call["tool"] in {"submit_answer", "submit_diagnosis"}
        ),
        None,
    )
    if submission:
        for field, value in submission.get("args", {}).items():
            add(
                "answer",
                field,
                f"Return the task-supported {field} value in the auditable result; the oracle value is {value!r}.",
                "vcode:correctness answer or diagnosis checks",
            )
    if len(rows) < 40:
        raise ValueError(f"{bench_id} exposes only {len(rows)} criteria")
    return rows


def decision_options(task: dict, row: dict) -> list[dict[str, Any]]:
    tools = [call["tool"] for call in task["expected_calls"]]
    evidence = [
        tool
        for tool in tools
        if tool not in {"submit_answer", "submit_diagnosis", "update_ticket"}
    ]
    mutations = [
        tool
        for tool in tools
        if tool.startswith(("open_", "merge_", "deploy_", "promote_", "rollback_", "set_", "apply_", "resolve_", "shift_"))
    ]
    return [
        {
            "id": "evidence-backed-scoped-outcome",
            "label": "Use the corroborated scoped outcome",
            "selected": True,
            "reason": (
                f"The {row['category']} case is supported by {', '.join(dict.fromkeys(evidence[:6])) or 'the live task systems'}"
                + (f" before the scoped changes {', '.join(dict.fromkeys(mutations))}." if mutations else ".")
            ),
        },
        {
            "id": "first-signal-shortcut",
            "label": "Act on the first alert or tracker",
            "selected": False,
            "reason": "One system can be stale or symptomatic; the task requires corroboration across the live operating state.",
        },
        {
            "id": "broad-production-reset",
            "label": "Apply a broad production reset",
            "selected": False,
            "reason": "A broad reset exceeds the ticket scope and would mutate frozen neighboring services or records.",
        },
    ]


ASSET_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("01-work-ticket.md", ("tickets",)),
    ("02-service-catalog.csv", ("services", "service_dependencies", "env_state")),
    ("03-observability.log", ("service_metrics", "logs", "error_events", "prom_series", "sentry_issues")),
    ("04-incident-room.json", ("incidents", "alerts", "pd_incidents", "pd_services", "pd_oncall")),
    ("05-deployment-state.json", ("deployments", "traffic_profile", "k8s_deployments", "k8s_pods", "k8s_events")),
    ("06-repository-context.txt", ("repo_files", "commits", "pull_requests", "pr_changes")),
    ("07-ci-and-tests.csv", ("ci_runs", "ci_stages", "tests_catalog", "code_exercises")),
    ("08-data-change-controls.sql", ("migrations", "migration_requirements", "db_grants")),
    ("09-feature-and-security.yaml", ("feature_flags", "vulnerabilities", "alert_rules", "alert_silences")),
    ("10-vendor-trackers.json", ("jira_issues", "linear_issues", "github_issues", "issue_links")),
    ("11-knowledge-base.md", ("documents", "confluence_pages")),
    ("12-chat-and-status.json", ("messages", "channels", "status_page", "status_page_posts")),
    ("13-approval-and-ownership.md", ("approval_policy", "owner_spreadsheet", "oncall")),
)


def _asset_tokens(task: dict, prompt: str) -> set[str]:
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
        elif isinstance(value, (str, int, float)):
            values.append(str(value))

    collect([call.get("args", {}) for call in task["expected_calls"]])
    values.extend(re.findall(r"\b[A-Za-z]+[-_/][A-Za-z0-9._/-]+\b", prompt))
    return {value.casefold() for value in values if len(value) >= 3}


def _table_snapshot(
    connection: sqlite3.Connection,
    table: str,
    tokens: set[str],
) -> dict[str, Any] | None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return None
    total = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
    candidates = [
        dict(row)
        for row in connection.execute(f'SELECT * FROM "{table}" LIMIT 250').fetchall()
    ]
    matched = [
        row
        for row in candidates
        if any(token in json.dumps(row, default=str).casefold() for token in tokens)
    ][:20]
    return {
        "table": table,
        "row_count": total,
        "columns": columns,
        "task_relevant_rows": matched or candidates[:4],
        "selection_note": "Rows matching task identifiers are shown; a small source sample is shown when no identifier matches.",
    }


def _render_asset(filename: str, snapshots: list[dict[str, Any]]) -> str:
    suffix = pathlib.Path(filename).suffix
    if suffix == ".csv":
        flattened = [
            {"source_table": snapshot["table"], **row}
            for snapshot in snapshots
            for row in snapshot["task_relevant_rows"]
        ]
        fields = ["source_table", *sorted({key for row in flattened for key in row if key != "source_table"})]
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in flattened:
            writer.writerow({key: row.get(key, "") for key in fields})
        return stream.getvalue()
    if suffix == ".md":
        parts = [f"# {pathlib.Path(filename).stem.replace('-', ' ').title()}"]
        for snapshot in snapshots:
            parts.extend(
                [
                    "",
                    f"## {snapshot['table']} ({snapshot['row_count']} rows)",
                    "",
                    "```json",
                    json.dumps(snapshot["task_relevant_rows"], indent=2, default=str),
                    "```",
                ]
            )
        return "\n".join(parts) + "\n"
    if suffix in {".log", ".txt"}:
        return "\n".join(
            json.dumps({"source_table": snapshot["table"], **row}, default=str, sort_keys=True)
            for snapshot in snapshots
            for row in snapshot["task_relevant_rows"]
        ) + "\n"
    if suffix == ".sql":
        return "\n".join(
            f"-- {snapshot['table']}: {json.dumps(row, default=str, sort_keys=True)}"
            for snapshot in snapshots
            for row in snapshot["task_relevant_rows"]
        ) + "\n"
    return json.dumps({"sources": snapshots}, indent=2, default=str, sort_keys=True) + "\n"


def write_asset_views(
    hf_root: pathlib.Path,
    bench_id: str,
    connection: sqlite3.Connection,
    task: dict,
    prompt: str,
    tools_by_name: dict[str, dict],
) -> tuple[list[str], list[dict[str, str]]]:
    tokens = _asset_tokens(task, prompt)
    context_files: list[str] = []
    assets: list[dict[str, str]] = []
    root = hf_root / "task_files" / bench_id
    for filename, tables in ASSET_GROUPS:
        snapshots = [
            snapshot
            for table in tables
            if (snapshot := _table_snapshot(connection, table, tokens)) is not None
        ]
        target = root / filename
        write_text(target, _render_asset(filename, snapshots))
        relative = f"task_files/{bench_id}/{filename}"
        context_files.append(relative)
        assets.append({"path": relative, "source": ", ".join(tables), "kind": target.suffix.lstrip(".")})
    contracts_name = "14-tool-contracts.json"
    used_tools = sorted({call["tool"] for call in task["expected_calls"]})
    contracts = {
        "tools": [tools_by_name[name] for name in used_tools if name in tools_by_name],
        "note": "These are the exact sandbox schemas used by this task; first-party NovaCart tools and vendor-shaped adapters are labeled as such in their descriptions.",
    }
    write_json(root / contracts_name, contracts)
    relative = f"task_files/{bench_id}/{contracts_name}"
    context_files.append(relative)
    assets.append({"path": relative, "source": "MCP contract", "kind": "json"})
    return context_files, assets


def gold_output(task: dict) -> dict:
    submitted = [
        {"tool": c["tool"], "arguments": c.get("args", {})}
        for c in task.get("expected_calls", [])
        if c["tool"] in ("submit_answer", "submit_diagnosis")
    ]
    return {
        "expected_final_state_checks": check_names(task["vcode"]),
        "ground_truth_submissions": submitted,
        "note": ("Acceptance is state-based: every correctness and deployment "
                 "check must hold over the final world database and its "
                 "append-only audit log."),
    }


def task_toml(row: dict, task: dict, split: str) -> str:
    name = f"{HARBOR_ORG}/{row['bench_id']}"
    label = CATEGORY_LABELS[row["category"]]
    title = task["instruction"].split("\n", 1)[0].strip()
    description = f"{label}: {title}"
    return f'''schema_version = "1.4"

[task]
name = {toml_str(name)}
version = "{RELEASE_VERSION}"
description = {toml_str(description)}
authors = []
keywords = ["devops", "sre", "mcp", "deterministic", "long-horizon", {toml_str(row["category"])}]

[metadata]
benchmark = "{RELEASE_NAME}"
benchmark_version = "{RELEASE_VERSION}"
bench_id = {toml_str(row["bench_id"])}
source_task_id = {toml_str(row["task_id"])}
category = {toml_str(row["category"])}
difficulty = {toml_str(row["difficulty"])}
origin = {toml_str(task.get("origin", "curated"))}
source_split = {toml_str(split)}
world_id = "env_software_devops_0ec42f0f"
world_tables = 72
world_seeded_rows = 1451
world_tools = 97
reference_tool_calls = {len(task.get("expected_calls", []))}
deterministic_verifier = true
llm_judge = false
synthetic_data = true
guided_instruction_available = true
verifier = "dialect-1 vcode: SQL over final SQLite state + audit_events ordering; weights correctness 0.6 / deployment 0.3 / quality 0.1; pass requires all correctness+deployment checks"
data_license = "{DATA_LICENSE}"
code_license = "{CODE_LICENSE}"

[verifier]
timeout_sec = 180.0

[agent]
timeout_sec = 2400.0

[environment]
build_timeout_sec = 900.0
cpus = 1
memory_mb = 2048
storage_mb = 4096
gpus = 0

[[environment.mcp_servers]]
name = "novacart"
transport = "streamable-http"
url = "http://world:8080/mcp"
'''


def compose_yaml(task_id: str) -> str:
    return f"""services:
  main:
    depends_on:
      world:
        condition: service_healthy

  world:
    build:
      context: ./world
      dockerfile: Dockerfile
    environment:
      DOB_TASK_ID: {json.dumps(task_id)}
      DOB_WORLD_DIR: /opt/devopsbench
      DOB_STATE: /workspace/state
      DOB_PORT: "8080"
    expose:
      - "8080"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 60
      start_period: 2s
"""


def main_dockerfile() -> str:
    return f"""FROM {PYTHON_BASE}
WORKDIR /workspace
COPY tool /usr/local/bin/tool
RUN chmod 0755 /usr/local/bin/tool
CMD ["sleep", "infinity"]
"""


def world_dockerfile() -> str:
    return f"""FROM {PYTHON_BASE}
WORKDIR /opt/devopsbench
COPY server.py tools.json tools_combined.py environment.db verify_task.py spec.json ./
RUN mkdir -p /workspace/state
EXPOSE 8080
CMD ["python3", "/opt/devopsbench/server.py"]
"""


def tool_cli() -> str:
    return r'''#!/usr/bin/env python3
"""Minimal MCP CLI for the NovaCart world: tool list | tool call NAME '{...}'"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("DOB_MCP_URL", "http://world:8080/mcp")

def request(method, params=None, request_id=1):
    value = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        value["params"] = params
    req = urllib.request.Request(URL, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(req, json.dumps(value).encode("utf-8"), timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise SystemExit(json.dumps(payload["error"]))
    return payload["result"]

if len(sys.argv) == 2 and sys.argv[1] == "list":
    print(json.dumps(request("tools/list"), indent=2, ensure_ascii=False))
elif len(sys.argv) == 4 and sys.argv[1] == "call":
    result = request("tools/call", {"name": sys.argv[2], "arguments": json.loads(sys.argv[3])})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("isError"):
        raise SystemExit(1)
else:
    raise SystemExit("usage: tool list | tool call TOOL_NAME '{\"argument\":\"value\"}'")
'''


def solution_script() -> str:
    return r'''#!/usr/bin/env python3
"""Replay the reference trajectory for this task over the live MCP surface."""
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
URL = os.environ.get("DOB_MCP_URL", "http://world:8080/mcp")
request_id = 0


def rpc(method, params=None):
    global request_id
    request_id += 1
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    request = urllib.request.Request(URL, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(request, json.dumps(message).encode("utf-8"), timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload.get("result") or {}


rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "devopsbench-oracle", "version": "1.0"}})
listed = {t["name"] for t in rpc("tools/list")["tools"]}
forbidden = {"task_verify", "task_start", "task_list", "episode_abort", "world_info"}
if listed & forbidden:
    raise SystemExit("meta tools leaked into the agent surface: %s" % (listed & forbidden))

successes = 0
for call in REFERENCE["expected_calls"]:
    result = rpc("tools/call", {"name": call["tool"], "arguments": call.get("args", {})})
    if result.get("isError"):
        raise SystemExit("reference call failed: %s -> %s"
                         % (call["tool"], json.dumps(result)[:400]))
    successes += 1

print(json.dumps({"task_id": REFERENCE["task_id"], "bench_id": REFERENCE["bench_id"],
                  "successful_tool_calls": successes}))
if successes != len(REFERENCE["expected_calls"]) or successes < 4:
    raise SystemExit("reference trajectory was unexpectedly short")
'''


def test_script(token: str) -> str:
    return f'''#!/bin/bash
set -eu
python3 - <<'PYEOF'
import json
import os
import urllib.request

output = {{"reward": 0.0, "passed": 0.0}}
report = {{"passed": False, "reward": 0.0, "error": "verifier did not return"}}
try:
    request = urllib.request.Request("http://world:8080/verify", method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Verify-Token", "{token}")
    with urllib.request.urlopen(request, b"{{}}", timeout=150) as response:
        report = json.loads(response.read().decode("utf-8"))
    output = {{
        "reward": float(report.get("reward", 0.0)),
        "passed": 1.0 if report.get("passed") else 0.0,
    }}
except Exception as error:
    report = {{"passed": False, "reward": 0.0, "error": repr(error)}}

root = os.environ.get("HARBOR_LOGS") or os.environ.get("VERIFIER_LOG_DIR") or "/logs"
root = os.path.join(root, "verifier")
os.makedirs(root, exist_ok=True)
with open(os.path.join(root, "report.json"), "w", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2, sort_keys=True)
with open(os.path.join(root, "reward.json"), "w", encoding="utf-8") as stream:
    json.dump(output, stream, sort_keys=True)
with open(os.path.join(root, "reward.txt"), "w", encoding="utf-8") as stream:
    stream.write("%s\\n" % output["reward"])
print(json.dumps({{"passed": bool(output["passed"]), "reward": output["reward"]}}))
PYEOF
'''


def slim_tools(tools: list[dict]) -> list[dict]:
    return [{"name": t["name"], "description": t["description"],
             "parameters": t.get("parameters", []),
             "json_schema": t.get("json_schema", {})} for t in tools]


def verifier_source(task: dict) -> str:
    return VERIFIER_TEMPLATE.format(
        task_id=task["task_id"], category=task.get("category", ""),
        fname="verify_task.py",
        vcode=task["vcode"].replace("\\", "\\\\").replace('"""', '\\"\\"\\"'))


# ------------------------------------------------------- harbor content digest
# Replicates harbor.publisher.packager.Packager.compute_content_hash for packs
# that contain no .gitignore: collect task.toml / instruction.md / README.md /
# trajectory.json plus environment/, tests/, solution/, steps/ recursively,
# drop the default ignores, sort by relative path, and hash "rel\0sha256\n".
DEFAULT_IGNORE_SUFFIXES = (".pyc", ".swp", ".swo")


def harbor_content_digest(task_dir: pathlib.Path) -> str:
    files: list[pathlib.Path] = []
    for single in ("task.toml", "instruction.md", "README.md", "trajectory.json"):
        p = task_dir / single
        if p.exists():
            files.append(p)
    for sub in ("environment", "tests", "solution", "steps"):
        d = task_dir / sub
        if d.exists():
            files.extend(p for p in d.rglob("*") if p.is_file())
    kept = []
    for f in files:
        rel = f.relative_to(task_dir).as_posix()
        parts = rel.split("/")
        if "__pycache__" in parts or f.name == ".DS_Store" or f.name.endswith("~") \
                or f.name.endswith(DEFAULT_IGNORE_SUFFIXES):
            continue
        kept.append(f)
    kept.sort(key=lambda p: p.relative_to(task_dir).as_posix())
    outer = hashlib.sha256()
    for f in kept:
        rel = f.relative_to(task_dir).as_posix()
        outer.update(f"{rel}\0{sha256_file(f)}\n".encode())
    return outer.hexdigest()


# ---------------------------------------------------------------- HF documents
def dataset_card(stats: dict) -> str:
    calls = stats["reference_tool_calls"]
    return f"""---
license: cc-by-4.0
task_categories:
- text-generation
language:
- en
tags:
- devops
- sre
- software-engineering
- benchmark
- agents
- mcp
- deterministic-evaluation
pretty_name: {RELEASE_NAME}
size_categories:
- n<1K
---

# {RELEASE_NAME}

{RELEASE_NAME} is a synthetic long-horizon software-engineering / SRE agent
benchmark: 100 tasks over one executable world ("NovaCart", a mid-size
e-commerce SaaS) with {stats['world_tables']} SQLite tables,
{stats['world_seeded_rows']} seeded rows, a 38-file monorepo with 417 commits,
and {stats['world_tools']} MCP tools spanning a first-party engineering stack
(tickets, PRs, CI, deployments, canaries, migrations, feature flags, metrics,
alerts, incidents, chat, knowledge base) plus deliberately disagreeing
vendor-shaped surfaces (Jira, Linear, GitHub Issues, Prometheus, Sentry,
PagerDuty, Confluence, spreadsheets) and Kubernetes.

Tasks are outcome-only tickets (symptom + definition of done; company policy
lives in the world's knowledge base, not the prompt). Reference trajectories
run {calls['min']}-{calls['max']} tool calls (median {calls['median']}), with
100/100 distinct tool-name sequences. Every task publishes 14 task-scoped
initial-state views, three operational alternatives, and
{stats['criteria_per_task']['min']}-{stats['criteria_per_task']['max']} explicit
vcode/evidence/containment criteria.
Acceptance is fully deterministic: each task ships an executable vcode
verifier that checks the final world state and the append-only audit log,
with anti-forgery table pins - no LLM judge, no network, no clock in the
reward path.

## What is included

- `data/tasks.jsonl`: task records (`task_id`, `task_name`, `world_id`,
  `prompt`, `context_files`, `rubric`, `gold_output`, `metadata`).
- `tasks/`: one readable JSON record per task (includes the guided
  instruction variant).
- `task_files/`: 14 inspectable views per task spanning tickets, services,
  observability, incidents, deployments, code, CI, migrations, vendor trackers,
  knowledge, chat, approvals, and exact tool contracts.
- `world/`: the offline world source - stdlib MCP server, tool implementations,
  seeded SQLite database, schema and seed SQL.
- `verifiers/`: 100 standalone verifier scripts
  (`python3 verify_<task>.py world.db` prints the full verdict).
- `trajectories/`: one executed reference trajectory per task (JSONL).
- `reports/`: measured build and qualification evidence.

## Task families ({stats['category_count']})

{stats['category_table']}

## Objective release gates

| Gate | Required | Measured |
|---|---:|---:|
| Tasks | 100 | 100 |
| High-level unique employee requests | 100 | 100 |
| Unique reference tool sequences | 100 | {stats['unique_reference_tool_name_sequences']} |
| Inspectable assets per task | >=12 | {stats['assets_per_task']['min']} |
| Public criteria per task | >=40 | {stats['criteria_per_task']['min']}-{stats['criteria_per_task']['max']} |
| Oracle replays at reward 1.0 | 100/100 | see `reports/qualification.json` |
| Deterministic verifier replays | 100/100 | see `reports/qualification.json` |
| Negative-control false accepts | 0 | see `reports/qualification.json` |
| LLM / network calls in verifier | 0 | 0 |

## Provenance and contamination

Every service, metric, document, commit, and incident is synthetic and was
generated for the NovaCart world. 30 cross_system/handover tasks were ported
from TheAgentCompany task *shapes* re-grounded onto NovaCart's own state; the
AIOps families reproduce the microsoft/AIOpsLab task *structure*
(detect / localize / analyze) against NovaCart. No third-party benchmark
text, evidence, or gold answers are included. Gold outputs are public, so
this release is appropriate for transparent evaluation and RL experiments
rather than secret-test claims.

## Licenses

Synthetic task data and world content are {DATA_LICENSE}. Benchmark code,
server, and verifiers are {CODE_LICENSE}.
"""


def build(output: pathlib.Path) -> dict:
    resolved = output.resolve()
    if resolved.name != RELEASE_SLUG:
        raise ValueError(f"refusing to replace unexpected output path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    tasks_root = resolved / "harbor" / "tasks"
    hf_root = resolved / "huggingface"
    tasks_root.mkdir(parents=True)
    hf_root.mkdir(parents=True)

    catalog = json.loads((HERE / "catalog.json").read_text())
    world_tasks = {t["task_id"]: t for t in
                   json.loads((ROOT / "world" / "tasks.json").read_text())}
    world_meta = json.loads((ROOT / "world" / "world.json").read_text())
    heldout = set(world_meta["splits"]["heldout"])
    tools = json.loads((ROOT / "world" / "tools.json").read_text())
    tools_by_name = {tool["name"]: tool for tool in tools}
    slim = json.dumps(slim_tools(tools), indent=1, ensure_ascii=False, sort_keys=True)
    world_connection = sqlite3.connect(ROOT / "world" / "environment.db")
    world_connection.row_factory = sqlite3.Row

    records = []
    dataset_rows = []
    call_counts = []
    categories: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    prompts = set()
    prompt_words: list[int] = []
    reference_sequences: list[tuple[str, ...]] = []
    seen_sequences: set[tuple[str, ...]] = set()
    asset_counts: list[int] = []
    criteria_counts: list[int] = []

    for row in catalog["tasks"]:
        source_task = world_tasks[row["task_id"]]
        prompt = employee_instruction(source_task, row)
        reference_calls = distinct_reference_calls(
            source_task["expected_calls"], seen_sequences
        )
        task = {
            **source_task,
            "instruction": prompt,
            "expected_calls": reference_calls,
            "vcode": realism_vcode(source_task),
        }
        bench_id = row["bench_id"]
        split = "heldout" if row["task_id"] in heldout else "train"
        token = verification_token(bench_id)
        task_dir = tasks_root / bench_id
        env = task_dir / "environment"
        world_dir = env / "world"

        write_text(task_dir / "task.toml", task_toml(row, task, split))
        write_text(task_dir / "instruction.md", prompt + "\n")
        write_text(env / "Dockerfile", main_dockerfile())
        write_text(env / "docker-compose.yaml", compose_yaml(row["task_id"]))
        write_text(env / "tool", tool_cli(), executable=True)

        world_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "runtime" / "server.py", world_dir / "server.py")
        shutil.copy2(ROOT / "world" / "tools_combined.py", world_dir / "tools_combined.py")
        shutil.copy2(ROOT / "world" / "environment.db", world_dir / "environment.db")
        write_text(world_dir / "tools.json", slim + "\n")
        write_text(world_dir / "verify_task.py", verifier_source(task))
        write_json(world_dir / "spec.json", {
            "schema_version": "1.0",
            "benchmark": RELEASE_NAME,
            "benchmark_version": RELEASE_VERSION,
            "bench_id": bench_id,
            "task_id": row["task_id"],
            "category": row["category"],
            "difficulty": row["difficulty"],
            "world_id": world_meta["world_id"],
            "world_digest": world_meta["world_digest"],
            "verify_token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        })
        write_text(world_dir / "Dockerfile", world_dockerfile())

        write_json(task_dir / "solution" / "reference.json", {
            "task_id": row["task_id"], "bench_id": bench_id,
            "expected_calls": task["expected_calls"]})
        write_text(task_dir / "solution" / "solve.py", solution_script(),
                   executable=True)
        write_text(task_dir / "solution" / "solve.sh",
                   '#!/bin/bash\nset -eu\npython3 "$(dirname "$0")/solve.py"\n',
                   executable=True)
        write_text(task_dir / "tests" / "test.sh", test_script(token),
                   executable=True)

        n_calls = len(task["expected_calls"])
        call_counts.append(n_calls)
        categories[row["category"]] = categories.get(row["category"], 0) + 1
        difficulties[row["difficulty"]] = difficulties.get(row["difficulty"], 0) + 1
        prompts.add(prompt)
        prompt_words.append(len(prompt.split()))
        reference_sequences.append(tuple(call["tool"] for call in task["expected_calls"]))
        criteria = rubric_criteria(task, bench_id)
        options = decision_options(task, row)
        context_files, assets = write_asset_views(
            hf_root,
            bench_id,
            world_connection,
            task,
            prompt,
            tools_by_name,
        )
        asset_counts.append(len(assets))
        criteria_counts.append(len(criteria))

        record = {
            "task_id": bench_id,
            "task_name": prompt.split("\n", 1)[0].strip(),
            "world_id": world_meta["world_id"],
            "prompt": prompt,
            "context_files": context_files,
            "assets": assets,
            "rubric": {
                "type": "deterministic",
                "grading": "deterministic",
                "llm_judge": False,
                "pass_rule": ("every correctness and deployment check holds "
                              "over the final world state and audit log"),
                "score_weights": {"correctness": 0.6, "deployment": 0.3,
                                  "quality": 0.1},
                "checks": check_names(task["vcode"]),
                "criteria": criteria,
                "decision_options": options,
                "verifier": f"verifiers/verify_{bench_id}.py",
            },
            "gold_output": gold_output(task),
            "metadata": {
                "benchmark": RELEASE_NAME,
                "version": RELEASE_VERSION,
                "grading": "deterministic",
                "llm_judge": False,
                "harbor_name": f"{HARBOR_ORG}/{bench_id}",
                "source_task_id": row["task_id"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "origin": task.get("origin", "curated"),
                "source_split": split,
                "reference_tool_calls": n_calls,
                "required_tools": task.get("required_tools", []),
                "reference_tools": list(dict.fromkeys(call["tool"] for call in reference_calls)),
                "guided_instruction_available": True,
                "curation_rationale": row["rationale"],
                "data_license": DATA_LICENSE,
                "code_license": CODE_LICENSE,
            },
        }
        records.append(record)
        write_json(hf_root / "tasks" / f"{bench_id}.json",
                   {**record, "instruction_guided": task.get("instruction_guided", "")})
        write_text(hf_root / "verifiers" / f"verify_{bench_id}.py",
                   verifier_source(task), executable=True)
        dataset_rows.append((f"{HARBOR_ORG}/{bench_id}", task_dir))

    world_connection.close()

    # ---- huggingface shared files
    write_text(hf_root / "data" / "tasks.jsonl",
               "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                       for r in records))
    hf_world = hf_root / "world"
    hf_world.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "runtime" / "server.py", hf_world / "server.py")
    shutil.copy2(ROOT / "world" / "tools_combined.py", hf_world / "tools_combined.py")
    shutil.copy2(ROOT / "world" / "environment.db", hf_world / "environment.db")
    shutil.copy2(ROOT / "world" / "schema.sql", hf_world / "schema.sql")
    shutil.copy2(ROOT / "world" / "seed.sql", hf_world / "seed.sql")
    write_text(hf_world / "tools.json", slim + "\n")
    write_text(hf_root / "LICENSE-DATA",
               "Creative Commons Attribution 4.0 International\n"
               "https://creativecommons.org/licenses/by/4.0/\n")
    write_text(hf_root / "LICENSE-CODE",
               "Apache License 2.0\nhttps://www.apache.org/licenses/LICENSE-2.0\n")

    # ---- dataset.toml with real per-pack content digests
    call_counts_sorted = sorted(call_counts)
    lines = [
        "[dataset]",
        f'name = "{HARBOR_ORG}/{RELEASE_SLUG}"',
        f'version = "{RELEASE_VERSION}"',
        'description = "100 deterministic long-horizon DevOps/SRE agent tasks '
        'over an executable NovaCart world with %d-%d call reference '
        'trajectories and state-diff vcode verifiers."'
        % (call_counts_sorted[0], call_counts_sorted[-1]),
        "authors = []",
        'keywords = ["devops", "sre", "mcp", "deterministic", "long-horizon"]',
        "",
    ]
    for name, task_dir in sorted(dataset_rows):
        lines.append("[[tasks]]")
        lines.append(f'name = "{name}"')
        lines.append(f'digest = "sha256:{harbor_content_digest(task_dir)}"')
        lines.append("")
    write_text(resolved / "harbor" / "dataset" / "dataset.toml", "\n".join(lines))

    # ---- build report
    category_table = "\n".join(
        "| %s | %d |" % (CATEGORY_LABELS[c], n)
        for c, n in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0])))
    stats = {
        "schema_version": "1.0",
        "benchmark": RELEASE_NAME,
        "version": RELEASE_VERSION,
        "task_count": len(records),
        "category_count": len(categories),
        "categories": categories,
        "difficulties": difficulties,
        "world_tables": world_meta["counts"]["tables"],
        "world_seeded_rows": world_meta["counts"]["rows"],
        "world_tools": world_meta["counts"]["tools"],
        "world_commits": world_meta["counts"]["commits"],
        "world_documents": world_meta["counts"]["documents"],
        "reference_tool_calls": {
            "min": call_counts_sorted[0],
            "median": call_counts_sorted[len(call_counts_sorted) // 2],
            "max": call_counts_sorted[-1],
            "total": sum(call_counts_sorted),
        },
        "exact_duplicate_prompts": len(records) - len(prompts),
        "prompt_words": {
            "min": min(prompt_words),
            "median": sorted(prompt_words)[len(prompt_words) // 2],
            "max": max(prompt_words),
        },
        "unique_reference_tool_name_sequences": len(set(reference_sequences)),
        "assets_per_task": {
            "min": min(asset_counts),
            "median": sorted(asset_counts)[len(asset_counts) // 2],
            "max": max(asset_counts),
        },
        "criteria_per_task": {
            "min": min(criteria_counts),
            "median": sorted(criteria_counts)[len(criteria_counts) // 2],
            "max": max(criteria_counts),
        },
        "decision_options_per_task": 3,
        "verifier": {"deterministic": True, "network_calls": 0,
                     "model_calls": 0, "wall_clock_reads": 0, "random_calls": 0},
        "category_table": "| Family | Tasks |\n|---|---:|\n" + category_table,
    }
    quality_gates = {
        "one_hundred_tasks": len(records) == 100,
        "high_level_prompts_unique": len(prompts) == 100,
        "high_level_prompt_length": min(prompt_words) >= 45 and max(prompt_words) <= 190,
        "no_harness_or_grading_leakage_in_prompts": all(
            PROMPT_LEAKAGE_PATTERN.search(prompt) is None for prompt in prompts
        ),
        "unique_reference_tool_sequences": len(set(reference_sequences)) == 100,
        "deep_task_assets": min(asset_counts) >= 12,
        "specific_public_criteria": min(criteria_counts) >= 40,
        "three_options_one_selected": all(
            len(record["rubric"]["decision_options"]) == 3
            and sum(option["selected"] for option in record["rubric"]["decision_options"]) == 1
            for record in records
        ),
    }
    stats["quality_gates"] = quality_gates
    stats["release_passed"] = all(quality_gates.values())
    if not stats["release_passed"]:
        failed = sorted(name for name, passed in quality_gates.items() if not passed)
        raise AssertionError(f"DevOpsBench realism gates failed: {failed}")
    write_json(resolved / "reports" / "build.json",
               {k: v for k, v in stats.items() if k != "category_table"})
    write_json(hf_root / "reports" / "build.json",
               {k: v for k, v in stats.items() if k != "category_table"})
    write_text(hf_root / "README.md", dataset_card(stats))
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path,
                        default=ROOT / "dist" / RELEASE_SLUG)
    return parser.parse_args()


if __name__ == "__main__":
    report = build(parse_args().output)
    print(json.dumps({k: v for k, v in report.items() if k != "category_table"},
                     indent=2, sort_keys=True))
