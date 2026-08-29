"""Causal-evidence release layer for DevOpsBench-100 v3.

The source world already contains the task-specific operational transitions.
This module adds the part a real employee has to do around those transitions:
resolve a work item across disagreeing systems, establish which control is
current, inspect the live service state, make the supported change, and reopen
the handoff after writing it.  The public prompt stays outcome-oriented; the
exact causal contract remains in the deterministic verifier.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


RELEASE_VERSION = "3.0.0"
CURRENT_CONTROL = "OPS-CONTROL-2026.03"
RETIRED_CONTROL = "OPS-CONTROL-2025.11"
SERVICE_NAMES = (
    "analytics-worker",
    "api-gateway",
    "catalog",
    "checkout",
    "inventory",
    "media-service",
    "notifications",
    "payments",
    "search",
    "storefront-web",
)
SERVICE_ALIASES = {
    "analytics": "analytics-worker",
    "api": "api-gateway",
    "gateway": "api-gateway",
    "catalog": "catalog",
    "checkout": "checkout",
    "inventory": "inventory",
    "media": "media-service",
    "notify": "notifications",
    "notification": "notifications",
    "notifications": "notifications",
    "payments": "payments",
    "search": "search",
    "storefront": "storefront-web",
}
SERVICE_CONTEXT = {
    "analytics-worker": "Its business boundary is reporting freshness, warehouse replica access, scheduled rollups, and downstream decision data.",
    "api-gateway": "Its business boundary is edge routing, partner request compatibility, authentication policy, and public latency exposure.",
    "catalog": "Its business boundary is price publication, product availability, merchandising feeds, and cache-consistent customer display.",
    "checkout": "Its business boundary is cart conversion, order creation, idempotency, and the customer's final purchase step.",
    "inventory": "Its business boundary is stock reservation, warehouse truth, backorder promises, and race-free quantity updates.",
    "media-service": "Its business boundary is customer uploads, image transformation, object storage, and CDN delivery behavior.",
    "notifications": "Its business boundary is receipts, retry policy, delivery templates, and downstream messaging reliability.",
    "payments": "Its business boundary is authorization, settlement, retry safety, and duplicate-charge prevention.",
    "search": "Its business boundary is index freshness, query relevance, cache behavior, and shopper discovery latency.",
    "storefront-web": "Its business boundary is browser delivery, page rendering, customer navigation, and edge-cache behavior.",
}
TOPIC_CONTEXT = {
    "egress": "The disputed mechanism is outbound connectivity, DNS reachability, firewall policy, and dependency access.",
    "grant": "The disputed mechanism is database authorization, revoked roles, credential scope, and least-privilege access.",
    "crashloop": "The disputed mechanism is container lifecycle, restart pressure, image state, and process termination evidence.",
    "errors": "The disputed mechanism is application exceptions, sampled error groups, request failures, and service-level breach.",
    "auth": "The change boundary covers tokens, identity sessions, compatibility headers, and authentication consumers.",
    "orders": "The change boundary covers order contracts, fulfillment consumers, persistence, and backward compatibility.",
    "debug": "The retirement boundary is diagnostic introspection, operator-only access, traces, and accidental public exposure.",
    "metrics": "The retirement boundary is telemetry scraping, counters, collectors, dashboards, and monitoring consumers.",
    "express": "The product boundary is accelerated checkout, cart conversion, rollout cohorts, and purchase completion.",
    "saved": "The product boundary is returning-shopper persistence, cart restoration, ownership, and session continuity.",
    "backoff": "The implementation boundary is retry delay growth, caps, jitter behavior, and transient-failure safety.",
    "chunk": "The implementation boundary is batch partitioning, payload size, terminal fragments, and ordering.",
    "recurrence": "The disputed mechanism is a supposedly resolved incident recurring behind stale customer-status communication.",
    "timeout": "The disputed mechanism is deadline propagation, downstream waiting, retry amplification, and request cancellation.",
    "race": "The disputed mechanism is concurrent state access, ordering, duplicate work, and nondeterministic tests.",
    "secret": "The security boundary is credential material, repository history, rotation evidence, and leak containment.",
}

OBSERVABILITY_CATEGORIES = {
    "aiops_analysis",
    "aiops_detection",
    "aiops_localization",
    "attribution",
    "judgement",
    "security_incident",
}
DELIVERY_CATEGORIES = {
    "api_migration",
    "error_rate_reduction",
    "feature_flag",
    "horizon",
    "human_gated",
    "latency_optimization",
    "multi_service_rollout",
}
ENGINEERING_CATEGORIES = {
    "code_implementation",
    "flaky_test",
    "handover",
    "workspace",
}

PROVIDER_MAPPINGS = {
    "jira_search": "Atlassian Jira issue search",
    "jira_get_issue": "Atlassian Jira issue retrieval",
    "list_issue_links": "cross-tracker link registry",
    "github_list_issues": "GitHub issues",
    "confluence_search": "Atlassian Confluence search",
    "confluence_get_page": "Atlassian Confluence page retrieval",
    "list_messages": "Slack conversation history",
    "post_message": "Slack message creation",
    "read_owner_spreadsheet": "Microsoft Graph workbook",
    "pd_list_change_events": "PagerDuty change events",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _task_id_services(task_id: str) -> list[str]:
    matches = sorted(
        (
            (task_id.find(alias), alias, service)
            for alias, service in SERVICE_ALIASES.items()
            if alias in task_id
        ),
        key=lambda item: (item[0], -len(item[1])),
    )
    ordered: list[str] = []
    for _, _, service in matches:
        if service not in ordered:
            ordered.append(service)
    return ordered


def primary_service(task: dict[str, Any], index: int) -> str:
    task_id = task.get("task_id", "").casefold()
    services = _task_id_services(task_id)
    if services:
        return services[-1]
    blob = json.dumps(
        [task.get("instruction", ""), task.get("expected_calls", [])],
        ensure_ascii=False,
        sort_keys=True,
    ).casefold()
    for service in sorted(SERVICE_NAMES, key=len, reverse=True):
        if service in blob:
            return service
    return SERVICE_NAMES[(index - 1) % len(SERVICE_NAMES)]


def case_contract(row: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    index = int(row["index"])
    case_id = f"DOB-{index:03d}"
    service = primary_service(task, index)
    task_id_services = _task_id_services(task.get("task_id", "").casefold())
    secondary_service = next(
        (candidate for candidate in reversed(task_id_services[:-1]) if candidate != service),
        None,
    )
    task_tokens = set(_slug(task.get("task_id", "")).split("_"))
    topic_context = next(
        (description for token, description in TOPIC_CONTEXT.items() if token in task_tokens),
        "",
    )
    return {
        "case_id": case_id,
        "service": service,
        "secondary_service": secondary_service,
        "topic_context": topic_context,
        "repo": f"novacart/{service}",
        "github_issue": 9000 + index,
        "current_page": 10000 + index,
        "retired_page": 11000 + index,
        "owner_row": 12000 + index,
        "status_post": 13000 + index,
        "channel": f"case-{index:03d}-{service}",
        "pd_service_id": f"PD-DOB-{index:03d}",
        "control_revision": CURRENT_CONTROL,
        "retired_revision": RETIRED_CONTROL,
        "completion_marker": f"{case_id} evidence-backed handoff complete",
    }


def release_prompt(
    row: dict[str, Any],
    employee_request: str,
    contract: dict[str, Any],
) -> str:
    """Wrap the authored outcome in a natural workplace request, not a recipe."""

    contexts = (
        "Customer support escalated a morning reliability review after two dashboards disagreed.",
        "The overnight on-call handover left an unresolved production judgement for the incoming engineer.",
        "A release-train checkpoint is waiting on a defensible service-state conclusion.",
        "The incident commander needs the underlying facts separated from a plausible first hypothesis.",
        "A change-window reviewer found that the ticket and operating records no longer line up.",
        "The weekly reliability council needs a reproducible answer before it closes the action item.",
        "A regional operations lead flagged conflicting ownership, rollout, and telemetry records.",
        "The security-response handoff needs the real scope established before anyone broadens remediation.",
        "A vendor integration review exposed a gap between recorded and actually deployed state.",
        "An after-hours escalation needs a safe answer that the next shift can independently verify.",
        "The service owner is reconciling an audit exception against today's production evidence.",
        "A customer-impact retrospective has one open question whose sources currently disagree.",
    )
    context = contexts[(int(row["index"]) - 1) % len(contexts)]
    service_context = SERVICE_CONTEXT[contract["service"]]
    secondary_context = (
        f"A separate signal crosses {contract['secondary_service']}: "
        f"{SERVICE_CONTEXT[contract['secondary_service']]}"
        if contract.get("secondary_service")
        else contract.get("topic_context", "")
    )
    prompt = (
        f"{context} {employee_request.strip()} The work item is {contract['case_id']} "
        f"for {contract['service']}. {service_context} {secondary_context} "
        "Reconcile current authority with live state, make only "
        "supported changes, and leave a case-room handoff that you have reopened and verified."
    )
    return re.sub(r"\s+", " ", prompt).strip()


def seed_case_evidence(
    database: Path,
    row: dict[str, Any],
    task: dict[str, Any],
    prompt: str,
    contract: dict[str, Any],
) -> None:
    """Seed current and stale evidence into the task's isolated world copy."""

    cx = sqlite3.connect(database)
    title = employee_title(task)
    index = int(row["index"])
    current_body = (
        f"Control {CURRENT_CONTROL} is effective for {contract['case_id']} and supersedes "
        f"{RETIRED_CONTROL}. Establish identity across Jira and the linked GitHub issue, "
        "compare the case-room report with live operational records, follow task-specific "
        "approval and rollout controls, and verify writes from the system of record. This "
        "page defines evidence precedence; it does not contain the task's conclusion."
    )
    retired_body = (
        f"Retired control {RETIRED_CONTROL} for {contract['case_id']}. This draft recommends "
        "trusting the first alert and closing the tracker after a single-system check. It is "
        f"retained for audit history and was superseded by {CURRENT_CONTROL}."
    )
    cx.execute(
        "INSERT INTO jira_issues(key,project,summary,issue_type,status,resolution,priority,"
        "component,assignee,created_day,updated_day) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            contract["case_id"],
            "DOB",
            title,
            "Task",
            "In Progress",
            "",
            "High" if row["difficulty"] in {"hard", "expert"} else "Medium",
            contract["service"],
            "on-call",
            94,
            100,
        ),
    )
    cx.execute(
        "INSERT INTO github_issues(number,repo,title,state,labels,created_day) VALUES (?,?,?,?,?,?)",
        (
            contract["github_issue"],
            contract["repo"],
            f"Operational evidence for {contract['case_id']}",
            "open",
            f"{row['category']},needs-correlation",
            95,
        ),
    )
    cx.execute(
        "INSERT INTO issue_links(source,target,kind) VALUES (?,?,?)",
        (contract["case_id"], f"GH-{contract['github_issue']}", "relates"),
    )
    cx.executemany(
        "INSERT INTO confluence_pages(page_id,space,title,body,last_updated_day,stale) "
        "VALUES (?,?,?,?,?,?)",
        [
            (
                contract["current_page"],
                "OPS",
                f"{contract['case_id']} current operating control",
                current_body,
                100,
                0,
            ),
            (
                contract["retired_page"],
                "OPS",
                f"{contract['case_id']} retired shortcut note",
                retired_body,
                72,
                1,
            ),
        ],
    )
    cx.execute(
        "INSERT INTO channels(channel,purpose) VALUES (?,?)",
        (contract["channel"], f"Scoped operations room for {contract['case_id']}"),
    )
    cx.executemany(
        "INSERT INTO messages(channel,author,body) VALUES (?,?,?)",
        [
            (
                contract["channel"],
                "release-manager",
                f"Please resolve {contract['case_id']}. The Jira state is only intake; confirm the live systems.",
            ),
            (
                contract["channel"],
                "on-call",
                f"For {contract['service']}, the first signal may be symptomatic. Check the linked records before changing production.",
            ),
            (
                contract["channel"],
                "former-owner",
                f"I would follow {RETIRED_CONTROL}, but that note may be stale. No one has verified it against today's state.",
            ),
        ],
    )
    cx.execute(
        "INSERT INTO owner_spreadsheet(row_id,service_label,owning_team,slack_channel,"
        "last_reviewed_day,week_start) VALUES (?,?,?,?,?,?)",
        (
            contract["owner_row"],
            contract["service"],
            f"team-{contract['service']}",
            contract["channel"],
            99,
            "monday",
        ),
    )
    cx.execute(
        "INSERT INTO pd_change_events(pd_service_id,summary,day) VALUES (?,?,?)",
        (
            contract["pd_service_id"],
            f"{contract['case_id']} intake evidence for {contract['service']}; outcome not yet established",
            99,
        ),
    )
    cx.execute(
        "INSERT INTO status_page_posts(post_id,title,impact,state,published_day,linked_incident) "
        "VALUES (?,?,?,?,?,NULL)",
        (
            contract["status_post"],
            f"{contract['case_id']} customer-impact review pending",
            "none",
            "investigating",
            99,
        ),
    )
    cx.commit()
    cx.close()


def employee_title(task: dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", task.get("instruction", "")).strip()
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return sentence[:180] or "Resolve the scoped production question"


def _route_calls(category: str, service: str) -> list[dict[str, Any]]:
    if category in OBSERVABILITY_CATEGORIES:
        return [
            {"tool": "resolve_service_alias", "args": {"name": service}},
            {"tool": "pd_list_services", "args": {}},
            {"tool": "pd_list_oncalls", "args": {"day": 100}},
            {"tool": "list_status_page_posts", "args": {"since_day": 90}},
            {"tool": "list_alert_rules", "args": {}},
            {"tool": "list_alert_firings", "args": {"since_day": 90}},
            {"tool": "k8s_pods_list", "args": {"service": service}},
            {"tool": "k8s_events_list", "args": {}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
        ]
    if category in DELIVERY_CATEGORIES:
        return [
            {"tool": "get_service", "args": {"service": service}},
            {"tool": "list_pull_requests", "args": {"service": service}},
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
            {"tool": "list_migrations", "args": {"service": service}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "get_slo_status", "args": {"service": service}},
            {"tool": "list_feature_flags", "args": {"service": service}},
            {"tool": "list_approval_policy", "args": {}},
        ]
    if category in ENGINEERING_CATEGORIES:
        return [
            {"tool": "get_service", "args": {"service": service}},
            {"tool": "list_files", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service}},
            {"tool": "list_pull_requests", "args": {"service": service}},
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "list_packages", "args": {"service": service}},
            {"tool": "list_api_endpoints", "args": {"service": service}},
            {"tool": "list_approval_policy", "args": {}},
        ]
    return [
        {"tool": "resolve_service_alias", "args": {"name": service}},
        {"tool": "list_service_aliases", "args": {}},
        {"tool": "linear_list_issues", "args": {}},
        {"tool": "pd_list_incidents", "args": {"since_day": 90}},
        {"tool": "list_status_page_posts", "args": {"since_day": 90}},
        {"tool": "list_tickets", "args": {"service": service}},
        {"tool": "list_pull_requests", "args": {"service": service}},
        {"tool": "list_deployments", "args": {"service": service}},
        {"tool": "list_commits", "args": {"service": service}},
    ]


def context_calls(
    row: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    groups = [
        [
            {"tool": "jira_search", "args": {"project": "DOB"}},
            {"tool": "jira_get_issue", "args": {"key": contract["case_id"]}},
            {"tool": "list_issue_links", "args": {"source": contract["case_id"]}},
        ],
        [
            {"tool": "github_list_issues", "args": {"repo": contract["repo"], "state": "open"}},
        ],
        [
            {"tool": "confluence_search", "args": {"query": contract["case_id"], "space": "OPS"}},
            {"tool": "confluence_get_page", "args": {"page_id": contract["current_page"]}},
            {"tool": "confluence_get_page", "args": {"page_id": contract["retired_page"]}},
        ],
        [
            {"tool": "list_messages", "args": {"channel": contract["channel"], "limit": 50}},
            {"tool": "read_owner_spreadsheet", "args": {}},
        ],
        [
            {"tool": "pd_list_change_events", "args": {"pd_service_id": contract["pd_service_id"], "since_day": 90}},
        ],
        _route_calls(row["category"], contract["service"]),
    ]
    # The evidence sources do not have a prescribed internal order.  Use a
    # one-to-one factoradic permutation for indices 1..100 so two tasks never
    # inherit the same raw investigation prefix merely because their source
    # workflows belong to the same family.
    pool = list(groups)
    ordered_groups: list[list[dict[str, Any]]] = []
    permutation = int(row["index"]) - 1
    while pool:
        position = permutation % len(pool)
        permutation //= len(pool)
        ordered_groups.append(pool.pop(position))
    calls = [call for group in ordered_groups for call in group]
    optional = [
        {"tool": "list_infra", "args": {}},
        {"tool": "list_vulnerabilities", "args": {"service": contract["service"]}},
        {"tool": "get_status_page", "args": {"limit": 20}},
        {"tool": "list_approval_policy", "args": {}},
        {"tool": "k8s_nodes_list", "args": {}},
        {"tool": "check_network_path", "args": {"from_service": contract["service"]}},
        {"tool": "sentry_list_projects", "args": {}},
    ]
    number = int(row["index"])
    calls.extend(call for bit, call in enumerate(optional) if number & (1 << bit))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for call in calls:
        key = json.dumps(call, sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            deduped.append(deepcopy(call))
    if len(deduped) < 19:
        raise ValueError(f"{row['bench_id']} has only {len(deduped)} contextual reads")
    return deduped


def reference_calls(
    row: dict[str, Any],
    task: dict[str, Any],
    contract: dict[str, Any],
    tools_by_name: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reads = context_calls(row, contract)
    source = deepcopy(task["expected_calls"])
    handoff = {
        "tool": "post_message",
        "args": {
            "channel": contract["channel"],
            "body": (
                f"{contract['completion_marker']}. Current authority: {CURRENT_CONTROL}. "
                "The task-specific outcome is recorded in its live systems of record; "
                "the linked evidence and resulting state were reopened after the change."
            ),
        },
    }
    readback = {
        "tool": "list_messages",
        "args": {"channel": contract["channel"], "limit": 50},
    }
    mutation_tools = sorted(
        {
            call["tool"]
            for call in source
            if (tools_by_name.get(call["tool"], {}).get("write_tables") or [])
        }
    )
    if not mutation_tools:
        raise ValueError(f"{row['bench_id']} source task has no state transition")
    workflow_slug = _slug(row["task_id"])
    graph = [
        f"intake_{_slug(contract['case_id'])}",
        f"resolve_{workflow_slug}_cross_tracker_identity",
        f"select_{_slug(CURRENT_CONTROL)}_over_retired_authority",
        f"correlate_{row['category']}_{_slug(contract['service'])}_signals",
        f"test_{workflow_slug}_first_signal_hypothesis",
        f"derive_{workflow_slug}_supported_branch",
        *[f"execute_{workflow_slug}_{_slug(tool)}" for tool in mutation_tools],
        f"reconcile_{workflow_slug}_post_change_state",
        f"handoff_{_slug(contract['case_id'])}_to_on_call",
        f"reopen_{_slug(contract['case_id'])}_conversation",
    ]
    trace_contract = {
        "required_context_calls": reads,
        "context_call_count": len(reads),
        "source_mutation_tools": mutation_tools,
        "handoff_call": handoff,
        "readback_call": readback,
        "semantic_action_graph": graph,
        "providers": sorted(
            {PROVIDER_MAPPINGS[call["tool"]] for call in reads if call["tool"] in PROVIDER_MAPPINGS}
        ),
    }
    return [*reads, *source, handoff, readback], trace_contract


def _literal_mapping(vcode: str, name: str) -> dict[str, Any]:
    match = re.search(rf"^{re.escape(name)}\s*=\s*(\{{.*\}})$", vcode, re.MULTILINE)
    if not match:
        return {}
    value = ast.literal_eval(match.group(1))
    return value if isinstance(value, dict) else {}


def rebase_vcode_invariants(vcode: str, database: Path) -> str:
    """Recompute frozen-table invariants after adding task-specific evidence."""

    cx = sqlite3.connect(database)
    frozen = _literal_mapping(vcode, "_FROZEN")
    rebased: dict[str, str] = {}
    for table in frozen:
        rows = [tuple(row) for row in cx.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
        rebased[table] = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    fixed = _literal_mapping(vcode, "_FIXED_ROWS")
    counts = {
        table: cx.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in fixed
    }
    cx.close()
    if frozen:
        vcode = re.sub(r"^_FROZEN\s*=\s*\{.*\}$", f"_FROZEN = {rebased!r}", vcode, count=1, flags=re.MULTILINE)
    if fixed:
        vcode = re.sub(r"^_FIXED_ROWS\s*=\s*\{.*\}$", f"_FIXED_ROWS = {counts!r}", vcode, count=1, flags=re.MULTILINE)
    return vcode


def augment_vcode(
    vcode: str,
    row: dict[str, Any],
    contract: dict[str, Any],
    trace_contract: dict[str, Any],
) -> str:
    """Add exact, argument-aware causal checks to the source state verifier."""

    required = trace_contract["required_context_calls"]
    mutation_tools = trace_contract["source_mutation_tools"]
    handoff = trace_contract["handoff_call"]
    readback = trace_contract["readback_call"]
    block = f'''

# DevOpsBench v3 causal-evidence contract for {row["bench_id"]}.
_V3_REQUIRED = {required!r}
_V3_MUTATION_TOOLS = {mutation_tools!r}
_V3_HANDOFF = {handoff!r}
_V3_READBACK = {readback!r}

def _v3_subset(_actual, _expected):
    if isinstance(_expected, dict):
        return isinstance(_actual, dict) and all(
            _k in _actual and _v3_subset(_actual[_k], _v)
            for _k, _v in _expected.items()
        )
    if isinstance(_expected, list):
        return isinstance(_actual, list) and len(_actual) == len(_expected) and all(
            _v3_subset(_a, _e) for _a, _e in zip(_actual, _expected)
        )
    return _actual == _expected

def _v3_positions(_selector, _successful=False):
    _rows = conn.execute(
        "SELECT seq, tool, args_json, ok FROM mcp_trace WHERE tool=? ORDER BY seq",
        (_selector["tool"],),
    ).fetchall()
    _out = []
    for _row in _rows:
        if _successful and not int(_row[3]):
            continue
        if _v3_subset(json.loads(_row[2]), _selector.get("args") or {{}}):
            _out.append(int(_row[0]))
    return _out

_v3_missing = [_r for _r in _V3_REQUIRED if not _v3_positions(_r)]
_v3_failed = [_r for _r in _V3_REQUIRED if not _v3_positions(_r, True)]
_v3_context_positions = [min(_v3_positions(_r)) for _r in _V3_REQUIRED if _v3_positions(_r)]
_v3_first_write = _one(
    "SELECT MIN(seq) FROM mcp_trace WHERE tool IN (" +
    ",".join("?" for _ in _V3_MUTATION_TOOLS) + ")",
    *_V3_MUTATION_TOOLS,
) or 0
_v3_handoff_positions = _v3_positions(_V3_HANDOFF, True)
_v3_readback_positions = _v3_positions(_V3_READBACK, True)
_v3_handoff_seq = min(_v3_handoff_positions) if _v3_handoff_positions else 0
_v3_prior_source_write = _one(
    "SELECT MAX(seq) FROM mcp_trace WHERE seq < ? AND tool IN (" +
    ",".join("?" for _ in _V3_MUTATION_TOOLS) + ")",
    _v3_handoff_seq,
    *_V3_MUTATION_TOOLS,
) or 0

_c("correctness", "v3_case_identity_resolved", not _v3_missing,
   "resolve {contract['case_id']} across the exact Jira, GitHub, Confluence, Slack, PagerDuty and workbook records")
_c("correctness", "v3_context_reads_succeeded", not _v3_failed,
   "the required evidence lookups must succeed; failed or unrelated requests are not investigation")
_c("deployment", "v3_evidence_before_state_change",
   bool(_v3_context_positions) and _v3_first_write > max(_v3_context_positions),
   "establish current evidence before the first task state transition")
_c("correctness", "v3_completion_handoff_exactly_once",
   _one("SELECT COUNT(*) FROM messages WHERE channel=? AND author='agent' AND body LIKE ?",
        {contract['channel']!r}, '%{contract['completion_marker']}%') == 1,
   "write exactly one scoped completion handoff for {contract['case_id']}")
_c("deployment", "v3_source_work_precedes_handoff",
   _v3_prior_source_write > 0 and _v3_handoff_seq > _v3_prior_source_write,
   "record the handoff only after the task-specific operational state change")
_c("deployment", "v3_handoff_read_back",
   bool(_v3_readback_positions) and _v3_handoff_seq > 0 and
   max(_v3_readback_positions) > _v3_handoff_seq,
   "reopen the exact case-room conversation after posting the completion handoff")
'''
    return vcode.rstrip() + "\n" + block


def check_descriptions(vcode: str) -> dict[tuple[str, str], str]:
    """Extract the verifier's authored human explanation for each assertion."""

    descriptions: dict[tuple[str, str], str] = {}
    try:
        tree = ast.parse(vcode)
    except SyntaxError:
        return descriptions
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "_c":
            continue
        if len(node.args) < 4:
            continue
        dimension = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
        name = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
        message = node.args[3].value if isinstance(node.args[3], ast.Constant) else None
        if all(isinstance(value, str) for value in (dimension, name, message)):
            descriptions[(dimension, name)] = message
    return descriptions


def decision_options(
    row: dict[str, Any], contract: dict[str, Any], mutation_tools: list[str]
) -> list[dict[str, Any]]:
    action = ", ".join(mutation_tools[:4])
    return [
        {
            "id": f"supported-{_slug(row['task_id'])}",
            "label": "Evidence-supported scoped outcome",
            "selected": True,
            "reason": (
                f"For {contract['case_id']}, current authority and live {contract['service']} state "
                f"support the task-specific transition ({action}) and a verified handoff."
            ),
        },
        {
            "id": f"stale-{_slug(row['task_id'])}",
            "label": "Follow the retired note",
            "selected": False,
            "reason": (
                f"{RETIRED_CONTROL} is retained evidence, not operative authority, and its first-signal "
                f"shortcut is not corroborated for {contract['case_id']}."
            ),
        },
        {
            "id": f"broad-{_slug(row['task_id'])}",
            "label": "Apply a broad workaround",
            "selected": False,
            "reason": (
                f"A broad reset or unrelated production mutation exceeds the {contract['service']} "
                "work item and violates deterministic write-scope containment."
            ),
        },
    ]


def reasoning_criteria(
    row: dict[str, Any], contract: dict[str, Any], trace_contract: dict[str, Any]
) -> list[dict[str, str]]:
    slug = _slug(row["task_id"])
    return [
        {"id": f"investigation.{slug}.identity", "category": "investigation", "description": f"Resolve {contract['case_id']} by immutable Jira key and its explicit cross-tracker link; a matching title is insufficient.", "enforced_by": "exact argument-aware MCP trace"},
        {"id": f"investigation.{slug}.authority", "category": "investigation", "description": f"Establish {CURRENT_CONTROL} as operative and treat {RETIRED_CONTROL} only as a competing historical hypothesis.", "enforced_by": "current and retired Confluence page reads"},
        {"id": f"investigation.{slug}.conversation", "category": "investigation", "description": f"Use the {contract['channel']} room to recover the request, the live-system warning, and the unverified prior-owner suggestion.", "enforced_by": "exact Slack history read"},
        {"id": f"investigation.{slug}.ownership", "category": "investigation", "description": f"Confirm current {contract['service']} ownership and escalation context instead of trusting a stale display name.", "enforced_by": "owner workbook and provider identity reads"},
        {"id": f"investigation.{slug}.live-state", "category": "investigation", "description": f"Reconcile the task's source systems with live {contract['service']} operational state before choosing the supported branch.", "enforced_by": "successful category-specific evidence route"},
        {"id": f"decision.{slug}.alternatives", "category": "decision", "description": "Keep the stale-note and broad-workaround alternatives visible, and reject them for evidence and scope reasons rather than by label.", "enforced_by": "task-specific options and negative controls"},
        {"id": f"procedure.{slug}.read-before-write", "category": "procedure", "description": "Complete every causal context read before the first operational mutation; a final state reached before investigation is not accepted.", "enforced_by": "mcp_trace sequence check"},
        {"id": f"state.{slug}.source-transition", "category": "state", "description": f"Produce the exact task-specific source transition using only {', '.join(trace_contract['source_mutation_tools'])} where supported by the live state.", "enforced_by": "source vcode final-state and audit checks"},
        {"id": f"state.{slug}.handoff", "category": "state", "description": f"Write exactly one completion handoff for {contract['case_id']} after the supported work, without claiming a broader result.", "enforced_by": "exact message state assertion"},
        {"id": f"procedure.{slug}.readback", "category": "procedure", "description": f"Reopen {contract['channel']} after the handoff so the persisted post, not the write response, is verified.", "enforced_by": "post-write readback sequence check"},
        {"id": f"containment.{slug}.scope", "category": "containment", "description": "Preserve all frozen neighboring services, policies, trackers, secrets, and seeded audit history outside the task-authorized changes.", "enforced_by": "source blast-radius and unauthorized-write control"},
    ]


def _excel_col(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _xlsx(rows: list[list[Any]]) -> bytes:
    xml_rows: list[str] = []
    for row_index, values in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{_excel_col(column + 1)}{row_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            for column, value in enumerate(values)
        )
        xml_rows.append(f'<row r="{row_index}">{cells}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Evidence" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return stream.getvalue()


def _pdf(text: str) -> bytes:
    lines = [line[:105] for line in text.splitlines() if line.strip()][:45]
    commands = ["BT", "/F1 9 Tf", "54 750 Td", "11 TL"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(("" if index == 0 else "T* ") + f"({safe}) Tj")
    commands.append("ET")
    content = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def _rows(cx: sqlite3.Connection, table: str, service: str, limit: int = 24) -> list[dict[str, Any]]:
    columns = [row[1] for row in cx.execute(f'PRAGMA table_info("{table}")')]
    if not columns:
        return []
    if "service" in columns:
        query = f'SELECT * FROM "{table}" WHERE service=? LIMIT ?'
        values = cx.execute(query, (service, limit)).fetchall()
    else:
        values = cx.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in values]


def _csv_text(rows: list[dict[str, Any]]) -> str:
    fields = sorted({key for row in rows for key in row}) or ["status"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fields})
    return stream.getvalue()


def _eml(subject: str, body: str, case_id: str, index: int) -> str:
    return "\n".join(
        [
            "From: release-manager@novacart.example",
            "To: on-call@novacart.example",
            "Date: Tue, 03 Mar 2026 09:00:00 +0000",
            f"Subject: {subject}",
            f"Message-ID: <dob-{index:03d}-{case_id.casefold()}@novacart.example>",
            f"X-Work-Item: {case_id}",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "",
            body,
            "",
        ]
    )


def write_asset_views(
    root: Path,
    database: Path,
    prompt: str,
    row: dict[str, Any],
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    """Write 28 human-shaped, native evidence files without gold or recipes."""

    root.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(database)
    cx.row_factory = sqlite3.Row
    assets: list[dict[str, str]] = []

    def add(name: str, source: str, content: str | bytes, role: str) -> None:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
        assets.append({"path": str(target.relative_to(root.parent.parent)), "source": source, "kind": target.suffix.lstrip("."), "evidence_role": role})

    case = dict(cx.execute("SELECT * FROM jira_issues WHERE key=?", (contract["case_id"],)).fetchone())
    github = dict(cx.execute("SELECT * FROM github_issues WHERE number=?", (contract["github_issue"],)).fetchone())
    links = [dict(r) for r in cx.execute("SELECT * FROM issue_links WHERE source=?", (contract["case_id"],))]
    pages = [dict(r) for r in cx.execute("SELECT * FROM confluence_pages WHERE page_id IN (?,?) ORDER BY stale", (contract["current_page"], contract["retired_page"]))]
    messages = [dict(r) for r in cx.execute("SELECT * FROM messages WHERE channel=? ORDER BY message_id", (contract["channel"],))]
    owner = [dict(r) for r in cx.execute("SELECT * FROM owner_spreadsheet WHERE row_id=?", (contract["owner_row"],))]
    changes = [dict(r) for r in cx.execute("SELECT * FROM pd_change_events WHERE pd_service_id=?", (contract["pd_service_id"],))]
    index = int(row["index"])

    def scoped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return [{"case_id": contract["case_id"], "status": "no matching rows in this source"}]
        return [{"case_id": contract["case_id"], **item} for item in rows]

    add("01-employee-request.md", "employee request", prompt + "\n", "request")
    add("02-jira-work-item.csv", "Atlassian Jira", _csv_text([case]), "identity")
    add("03-cross-tracker-links.json", "tracker link registry", json.dumps(links, indent=2, sort_keys=True) + "\n", "identity")
    add("04-github-issue.json", "GitHub", json.dumps(github, indent=2, sort_keys=True) + "\n", "engineering-signal")
    add("05-current-operating-control.pdf", "Confluence current export", _pdf(pages[0]["body"]), "authority")
    add("06-retired-shortcut-note.pdf", "Confluence history export", _pdf(pages[1]["body"]), "stale-authority")
    add("07-case-room-thread.json", "Slack", json.dumps(messages, indent=2, sort_keys=True) + "\n", "conversation")
    add("08-pagerduty-change-events.csv", "PagerDuty", _csv_text(changes), "change-history")
    add("09-service-owner-register.xlsx", "Microsoft Graph workbook", _xlsx([["service", "team", "channel", "reviewed_day"], *[[r["service_label"], r["owning_team"], r["slack_channel"], r["last_reviewed_day"]] for r in owner]]), "ownership")
    add("10-release-calendar.xlsx", "Microsoft Graph workbook", _xlsx([["case", "service", "window", "authority"], [contract["case_id"], contract["service"], "2026-03-03T14:00Z", CURRENT_CONTROL], [contract["case_id"], contract["service"], "2025-11-18T14:00Z", RETIRED_CONTROL]]), "schedule")
    add("11-source-inventory.csv", "case intake", _csv_text([{"case_id": contract["case_id"], "source": name, "status": "inspect"} for name in ("Jira", "GitHub", "Confluence", "Slack", "PagerDuty", "live service")]), "inventory")
    add("12-request-email.eml", "Gmail export", _eml(f"Please resolve {contract['case_id']}", "The tracker captures intake only. Reconcile the live systems and leave an auditable handoff; do not follow a copied runbook blindly.", contract["case_id"], index), "request")
    add("13-former-owner-email.eml", "Gmail export", _eml(f"Old suggestion for {contract['case_id']}", f"I previously used {RETIRED_CONTROL}. That may no longer be valid, and I did not verify today's production state.", contract["case_id"], index + 100), "conflict")
    add("14-service-catalog.csv", "service catalog", _csv_text(scoped(_rows(cx, "services", contract["service"]))), "service-state")
    add("15-slo-export.csv", "SLO platform", _csv_text(scoped(_rows(cx, "slos", contract["service"]))), "live-signal")
    add("16-metrics-export.csv", "Prometheus", _csv_text(scoped(_rows(cx, "service_metrics", contract["service"]))), "live-signal")
    add("17-observability-log-slice.log", "log platform", "\n".join(json.dumps(r, sort_keys=True, default=str) for r in scoped(_rows(cx, "logs", contract["service"]))) + "\n", "live-signal")
    add("18-sentry-issues.json", "Sentry", json.dumps({"case_id": contract["case_id"], "issues": _rows(cx, "sentry_issues", contract["service"])}, indent=2, default=str, sort_keys=True) + "\n", "live-signal")
    add("19-kubernetes-pods.yaml", "Kubernetes", f"case_id: {contract['case_id']}\nitems:\n" + "\n".join(f"  - {json.dumps(r, sort_keys=True, default=str)}" for r in _rows(cx, "k8s_pods", contract["service"])), "runtime-state")
    add("20-kubernetes-events.log", "Kubernetes", "\n".join(json.dumps(r, sort_keys=True, default=str) for r in scoped(_rows(cx, "k8s_events", contract["service"]))) + "\n", "runtime-state")
    add("21-deployment-history.json", "deployment platform", json.dumps({"case_id": contract["case_id"], "deployments": _rows(cx, "deployments", contract["service"])}, indent=2, default=str, sort_keys=True) + "\n", "deployment-state")
    add("22-ci-runs.csv", "CI platform", _csv_text(scoped(_rows(cx, "ci_runs", contract["service"]))), "build-state")
    add("23-pull-request-context.json", "GitHub", json.dumps({"case_id": contract["case_id"], "pull_requests": _rows(cx, "pull_requests", contract["service"])}, indent=2, default=str, sort_keys=True) + "\n", "change-state")
    migrations = _rows(cx, "migrations", contract["service"])
    add("24-migration-state.sql", "database change control", f"-- case_id: {contract['case_id']}\n" + "\n".join(f"-- {json.dumps(r, sort_keys=True, default=str)}" for r in migrations) + "\n", "change-control")
    vulnerabilities = _rows(cx, "vulnerabilities", contract["service"])
    add("25-security-scanner-report.pdf", "security scanner", _pdf(f"Case {contract['case_id']} security observations\n" + "\n".join(json.dumps(r, sort_keys=True, default=str) for r in vulnerabilities) + "\nNo task conclusion is precomputed here."), "security")
    add("26-approval-policy.md", "change governance", f"# Approval context for {contract['case_id']}\n\n{CURRENT_CONTROL} is operative. Irreversible actions require the approval recorded in the live policy system. Difficulty is not a reason to seek approval, and approval is not evidence that a proposed outcome is correct.\n", "governance")
    add("27-current-versus-stale-notes.txt", "evidence custodian", f"{contract['case_id']} has a current control ({CURRENT_CONTROL}) and a retained retired note ({RETIRED_CONTROL}). Resolve effective status and corroborate the underlying facts; filenames and display names are not authority.\n", "lineage")
    manifest = [{"filename": Path(asset["path"]).name, "source": asset["source"], "evidence_role": asset["evidence_role"]} for asset in assets]
    add("28-agent-visible-asset-manifest.json", "release builder", json.dumps({"case_id": contract["case_id"], "gold_included": False, "oracle_sequence_included": False, "assets": manifest}, indent=2, sort_keys=True) + "\n", "manifest")
    cx.close()
    if len(assets) != 28:
        raise ValueError(f"expected 28 assets for {row['bench_id']}, wrote {len(assets)}")
    return assets


def validate_native_asset(path: Path) -> bool:
    suffix = path.suffix.casefold()
    data = path.read_bytes()
    if suffix == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                required = {"[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"}
                return required <= set(archive.namelist()) and b"<worksheet" in archive.read("xl/worksheets/sheet1.xml")
        except zipfile.BadZipFile:
            return False
    if suffix == ".pdf":
        return data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF") and b"/Type /Page" in data
    if suffix == ".json":
        json.loads(data.decode("utf-8"))
    elif suffix == ".csv":
        list(csv.reader(io.StringIO(data.decode("utf-8"))))
    elif suffix == ".eml":
        text = data.decode("utf-8")
        return all(header in text for header in ("From:", "To:", "Subject:", "Message-ID:"))
    else:
        data.decode("utf-8")
    return True
