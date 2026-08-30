"""Causal-evidence release layer for DevOpsBench-100 v3.2.

The source world already contains the task-specific operational transitions.
This module adds the part a real employee has to do around those transitions:
resolve a work item across disagreeing systems, establish which control is
current, inspect the live service state, settle the graded capacity plan for
the customer cutover (see ``decision.py``), make the supported change, and
reopen the handoff after writing it.  The public prompt stays outcome-oriented;
the exact causal contract remains in the deterministic verifier.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import re
import sqlite3
import textwrap
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from benchmark.devopsbench100 import decision


RELEASE_VERSION = "3.2.0"
SEMANTIC_MILESTONE_WEIGHTS = {
    "investigation.scope": 5,
    "investigation.authority": 5,
    "investigation.live_state": 7,
    "analysis.causal_reasoning": 6,
    "analysis.capacity_plan": 9,
    "decision.supported_path": 5,
    "decision.options": 8,
    "state.primary": 14,
    "state.coordination": 6,
    "verification.outcome": 7,
    "verification.readback": 6,
    "execution.sequence": 6,
    "containment.scope": 7,
    "answer.insights": 4,
    "execution.efficiency": 3,
    "execution.delivery": 2,
}
MATERIAL_CONTEXT_CALLS = 18
ASSET_COUNT = 33
MATERIAL_ASSET_COUNT = 17
MAX_PROMPT_WORDS = 220
FIXED_XLSX_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
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
    "linear_list_issues": "Linear capacity register",
    "list_status_page_posts": "public status page",
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
    approval_ticket = f"CHG-{index}"
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
        "readiness_page": 14000 + index,
        "vendor_ticket": f"VEND-{index}",
        "approval_ticket": approval_ticket,
        "reservation_issue": f"CAP-{index}",
        "capacity_question": f"{case_id}-capacity-plan",
        "channel": f"case-{index:03d}-{service}",
        "pd_service_id": f"PD-DOB-{index:03d}",
        "control_revision": CURRENT_CONTROL,
        "retired_revision": RETIRED_CONTROL,
        "completion_marker": f"{case_id} evidence-backed handoff complete",
        "plan": decision.capacity_plan(
            index, service, secondary_service, SERVICE_NAMES, approval_ticket
        ),
    }


DECISION_REQUESTS = (
    "Before you hand off, settle the capacity plan for the {cutover} cutover: what the readiness standard "
    "requires, what stays usable once {reservation} is honoured, the shortfall, {vend}'s delivery dates, each "
    "plan's completion, cost and approval, and your recommendation, persisted as the case decision and stated "
    "in a handoff you reopen.",
    "Work out which capacity plan carries {service} to its {cutover} cutover: the pool net of {reservation}, "
    "the confirmed {vend} dates, the change calendar, what each option costs, whether {chg} covers it and "
    "whether it lands on time; record that decision, then reopen the case-room note stating it.",
    "Fold cutover readiness into your handoff: net required against usable replicas, bound the uncovered "
    "remainder, map the {vend} deliveries onto published windows, weigh all three paths on timing, spend and "
    "authority, and file the chosen one with its {cutover} variance before reopening the note.",
    "Management wants the {cutover} question answered too: replicas the standard demands, how many truly "
    "remain after {reservation}, when {vend} closes the gap, the candidate plans priced with their sign-off "
    "state under {chg}, and an honest on-time-or-late call, captured as the {case} decision and echoed in the "
    "reopened handoff.",
    "Close out the capacity side of {case}: reconcile the readiness requirement against the genuinely free "
    "pool, quantify the missing replicas, price every plan off {vendor}'s committed dates and the calendar, "
    "mark which {chg} authorises, pick one, and leave the persisted decision plus a reopened handoff naming "
    "its timing.",
    "Finish by planning the {cutover} cutover for {service}: demand per the standard, supply net of "
    "{reservation}, the deficit {vend} fills, window-bounded completions with costs and approvals for all "
    "three plans, one recommendation with a signed schedule variance, persisted for the case and restated in "
    "the handoff you verify.",
    "The cutover of {cutover} still needs its plan: derive the required and the usable replica counts, the "
    "gap, {vendor}'s standard versus expedited arrival, each option's window-gated finish, price and "
    "authority under {chg}, choose one honestly against that date, save the decision for {case}, and reopen "
    "the note that reports it.",
)


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
    index = int(row["index"])
    context = contexts[(index - 1) % len(contexts)]
    service_context = SERVICE_CONTEXT[contract["service"]]
    secondary_context = (
        f"A separate signal crosses {contract['secondary_service']}: "
        f"{SERVICE_CONTEXT[contract['secondary_service']]}"
        if contract.get("secondary_service")
        else contract.get("topic_context", "")
    )
    values = {
        "case": contract["case_id"],
        "service": contract["service"],
        "cutover": contract["plan"]["cutover_date"],
        "vendor": decision.VENDOR,
        "vend": contract["vendor_ticket"],
        "chg": contract["approval_ticket"],
        "reservation": contract["reservation_issue"],
    }
    decision_request = DECISION_REQUESTS[index % len(DECISION_REQUESTS)].format(**values)
    compact_request = (
        f"Before the handoff, persist the {contract['case_id']} capacity decision the {contract['service']} "
        f"readiness standard defines and state its recommendation, cost, {contract['approval_ticket']} approval "
        f"scope and {contract['plan']['cutover_date']} timing in the note you reopen."
    ).format(**values)
    guard = "Reconcile current authority with live state and make only supported changes."
    core = f"{employee_request.strip()} The work item is {contract['case_id']} for {contract['service']}."
    # Optional framing is dropped, least important first, when the employee's
    # own request already fills the word budget.
    attempts = (
        [context, core, guard, service_context, secondary_context, decision_request],
        [context, core, guard, service_context, "", decision_request],
        [context, core, guard, "", "", decision_request],
        ["", core, guard, "", "", decision_request],
        ["", core, guard, "", "", compact_request],
        ["", core, "", "", "", compact_request],
    )
    for parts in attempts:
        prompt = re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()
        if len(prompt.split()) <= MAX_PROMPT_WORDS:
            return prompt
    return prompt


def seed_case_evidence(
    database: Path,
    row: dict[str, Any],
    task: dict[str, Any],
    prompt: str,
    contract: dict[str, Any],
) -> None:
    """Seed current and stale evidence into the task's isolated world copy."""

    cx = sqlite3.connect(database)
    title = employee_title(
        {"instruction": task.get("source_instruction", task.get("instruction", ""))}
    )
    index = int(row["index"])
    current_body = (
        f"Control {CURRENT_CONTROL} is effective for {contract['case_id']} and supersedes "
        f"{RETIRED_CONTROL}. Establish identity across Jira and the linked GitHub issue, "
        "compare the case-room report with live operational records, follow task-specific "
        "approval and rollout controls, and verify writes from the system of record. This "
        "page defines evidence precedence; it does not contain the task's conclusion. "
        + decision.change_window_sentence(contract)
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
        decision.status_post_row(contract),
    )
    decision.seed_capacity_evidence(cx, contract)
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


def _material_route_calls(category: str, service: str) -> list[dict[str, Any]]:
    """Select the live-system joins that actually control the task decision."""

    preferred = (
        (
            "resolve_service_alias",
            "list_alert_firings",
            "k8s_pods_list",
            "get_runtime_stats",
        )
        if category in OBSERVABILITY_CATEGORIES
        else (
            "get_service",
            "list_deployments",
            "get_traffic_stats",
            "get_slo_status",
        )
        if category in DELIVERY_CATEGORIES
        else (
            "get_service",
            "list_files",
            "list_tests",
            "list_approval_policy",
        )
        if category in ENGINEERING_CATEGORIES
        else (
            "resolve_service_alias",
            "list_tickets",
            "list_deployments",
            "list_commits",
        )
    )
    by_name = {call["tool"]: call for call in _route_calls(category, service)}
    selected = [deepcopy(by_name[name]) for name in preferred if name in by_name]
    if len(selected) != 4:
        raise ValueError(
            f"expected four material live-state calls for {category}, got {len(selected)}"
        )
    return selected


def material_context_calls(
    row: dict[str, Any], contract: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Return the causal evidence subset within the larger reference investigation."""

    groups = {
        "identity": [
            {"tool": "jira_get_issue", "args": {"key": contract["case_id"]}},
            {"tool": "list_issue_links", "args": {"source": contract["case_id"]}},
            {
                "tool": "github_list_issues",
                "args": {"repo": contract["repo"], "state": "open"},
            },
        ],
        "authority": [
            {
                "tool": "confluence_search",
                "args": {"query": contract["case_id"], "space": "OPS"},
            },
            {
                "tool": "confluence_get_page",
                "args": {"page_id": contract["current_page"]},
            },
            {
                "tool": "confluence_get_page",
                "args": {"page_id": contract["retired_page"]},
            },
        ],
        "ownership_and_conversation": [
            {
                "tool": "list_messages",
                "args": {"channel": contract["channel"], "limit": 50},
            },
            {"tool": "read_owner_spreadsheet", "args": {}},
            {
                "tool": "pd_list_change_events",
                "args": {
                    "pd_service_id": contract["pd_service_id"],
                    "since_day": 90,
                },
            },
        ],
        "live_state": _material_route_calls(row["category"], contract["service"]),
        "capacity_plan": decision.capacity_context_calls(contract),
    }
    calls = [deepcopy(call) for values in groups.values() for call in values]
    if len(calls) != MATERIAL_CONTEXT_CALLS:
        raise ValueError(
            f"{row['bench_id']} has {len(calls)} material context calls, expected {MATERIAL_CONTEXT_CALLS}"
        )
    return calls, groups


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
        decision.capacity_context_calls(contract),
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


def _readback_for(
    tool: str, args: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any] | None:
    """The documented provider read that reopens what one source write changed."""

    service = args.get("service") or contract["service"]
    if tool in {"deploy_service", "promote_canary", "rollback_deployment"}:
        return {"tool": "list_deployments", "args": {"service": service, "limit": 20}}
    if tool == "set_feature_flag":
        return {"tool": "list_feature_flags", "args": {"service": service}}
    if tool == "apply_migration":
        return {"tool": "list_migrations", "args": {"service": service}}
    if tool in {"open_pull_request", "merge_pull_request"}:
        return {"tool": "list_pull_requests", "args": {"service": service}}
    if tool in {"acknowledge_alert", "resolve_alert"}:
        return {"tool": "list_alerts", "args": {"service": service}}
    if tool in {"create_incident", "update_incident"}:
        return {"tool": "list_incidents", "args": {}}
    if tool == "resolve_error_event":
        return {"tool": "list_error_events", "args": {"service": service}}
    if tool == "jira_transition_issue" and args.get("key"):
        return {"tool": "jira_get_issue", "args": {"key": args["key"]}}
    if tool == "publish_status_update":
        return {"tool": "get_status_page", "args": {"limit": 20}}
    if tool == "write_runbook":
        return {"tool": "list_authored_docs", "args": {}}
    if tool == "post_message" and args.get("channel"):
        return {"tool": "list_messages", "args": {"channel": args["channel"], "limit": 50}}
    if tool == "create_ticket":
        return {"tool": "list_tickets", "args": {"service": service}}
    if tool == "shift_endpoint_traffic":
        return {"tool": "list_api_endpoints", "args": {"service": service}}
    if tool == "ws_write" and args.get("path"):
        return {"tool": "ws_read", "args": {"path": args["path"]}}
    if tool == "update_ticket" and args.get("key"):
        return {"tool": "get_ticket", "args": {"key": args["key"]}}
    return None


def postwrite_readback_pairs(
    task: dict[str, Any], contract: dict[str, Any]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(source write, provider readback) pairs, one readback per distinct read."""

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for call in task["expected_calls"]:
        readback = _readback_for(call["tool"], call.get("args") or {}, contract)
        if readback is None:
            continue
        signature = json.dumps(readback, sort_keys=True, separators=(",", ":"))
        if signature in seen:
            continue
        seen.add(signature)
        pairs.append((deepcopy(call), readback))
    if not pairs:
        pairs.append(
            (
                {"tool": "source_workflow", "args": {}},
                {"tool": "get_service", "args": {"service": contract["service"]}},
            )
        )
    return pairs


def postwrite_readback_calls(
    task: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Derive provider reads that reopen the task's persisted state after writes."""

    return [deepcopy(readback) for _write, readback in postwrite_readback_pairs(task, contract)]


def post_write_verifications(
    task: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Public contract: every source mutation is read back from its provider."""

    rows = []
    for number, (write, readback) in enumerate(postwrite_readback_pairs(task, contract), 1):
        rows.append(
            {
                "id": f"readback_{number:02d}",
                "milestone_id": "verification.outcome",
                "check_id": "deployment.v4_state_readbacks_complete",
                "after_tool": write["tool"],
                "any_of": [{"tool": readback["tool"], "arguments": deepcopy(readback["args"])}],
                "description": (
                    f"Reopened the {readback['tool']} provider record after {write['tool']} for "
                    f"{contract['case_id']} and confirmed the persisted state rather than the write acknowledgement."
                ),
            }
        )
    return rows


def allowed_write_tables(
    task: dict[str, Any], tools_by_name: dict[str, dict[str, Any]]
) -> list[str]:
    """Tables the reference walk is allowed to change; everything else is frozen or fixed."""

    tables: set[str] = set()
    for call in task["expected_calls"]:
        tables.update(tools_by_name.get(call["tool"], {}).get("write_tables") or [])
    tables.update(tools_by_name.get("submit_answer", {}).get("write_tables") or [])
    tables.update(tools_by_name.get("post_message", {}).get("write_tables") or [])
    return sorted(tables)


INVESTIGATION_GROUPS = {
    "identity": ("investigation.scope", "correctness.v4_case_identity_resolved"),
    "authority": ("investigation.authority", "correctness.v4_authority_reconciled"),
    "ownership_and_conversation": ("analysis.causal_reasoning", "correctness.v4_material_evidence_complete"),
    "live_state": ("investigation.live_state", "correctness.v4_live_state_correlated"),
    "capacity_plan": ("analysis.capacity_plan", "correctness.v5_capacity_evidence_complete"),
}


def required_investigations(
    row: dict[str, Any], contract: dict[str, Any], trace_contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Public contract: the graded pre-mutation reads and what each one establishes."""

    plan = contract["plan"]
    service = contract["service"]
    descriptions = {
        ("jira_get_issue", contract["case_id"]): f"Located {contract['case_id']} through its immutable Jira key instead of a title match.",
        ("list_issue_links", None): f"Read the cross-tracker link registry to bind {contract['case_id']} to its GitHub record.",
        ("github_list_issues", None): f"Enumerated the open {contract['repo']} GitHub issues and used their immutable numbers to find #{contract['github_issue']}.",
        ("confluence_search", None): f"Searched Confluence for {contract['case_id']} to find the current control, the retired note and the readiness standard by page id.",
        ("confluence_get_page", contract["current_page"]): f"Opened the current operating control {CURRENT_CONTROL} and read the {service} change calendar ({', '.join(plan['window_dates'])}) that bounds every plan's completion.",
        ("confluence_get_page", contract["retired_page"]): f"Opened the retired {RETIRED_CONTROL} note and kept it as historical evidence, not authority.",
        ("list_messages", None): f"Read the scoped case-room discussion and separated the customer-success cutover mention from formal approval.",
        ("read_owner_spreadsheet", None): f"Read the service-owner workbook row for {service} to confirm ownership and the case channel.",
        ("pd_list_change_events", None): f"Read the PagerDuty change history for {contract['pd_service_id']}, including the scale record that gives {plan['observed']} replicas across {plan['zones']} zones.",
        ("confluence_get_page", contract["readiness_page"]): f"Opened the {contract['case_id']} change-readiness standard and established {plan['per_zone']} healthy replicas per zone plus the plan-selection rule.",
        ("jira_get_issue", contract["vendor_ticket"]): f"Read the independently confirmed {decision.VENDOR} vendor order {contract['vendor_ticket']}: standard delivery {decision.iso(plan['standard_days'])}, expedited {decision.iso(plan['expedited_days'])} for USD {plan['expedite_fee']}.",
        ("jira_get_issue", contract["approval_ticket"]): f"Read the signed change approval {contract['approval_ticket']} and applied it only to the authorised capacity plans within published windows.",
        ("linear_list_issues", None): f"Read the Linear capacity register and excluded the {plan['reserved']} replicas reserved for the {plan['neighbor']} freeze.",
        ("list_status_page_posts", None): f"Read the public status page and preserved the {plan['cutover_date']} customer cutover as the independent control date.",
    }
    rows = []
    number = 0
    for group, calls in trace_contract["material_context_groups"].items():
        milestone_id, check_id = INVESTIGATION_GROUPS[group]
        for call in calls:
            number += 1
            args = call.get("args") or {}
            key = (call["tool"], args.get("key") or args.get("page_id"))
            description = descriptions.get(key) or descriptions.get((call["tool"], None)) or (
                f"Correlated the live {service} {call['tool']} record that controls this {row['category']} decision."
            )
            rows.append(
                {
                    "id": f"investigation_{number:02d}",
                    "milestone_id": milestone_id,
                    "check_id": check_id,
                    "group": group,
                    "before_primary_mutation": True,
                    "any_of": [{"tool": call["tool"], "arguments": deepcopy(args)}],
                    "description": description,
                }
            )
    return rows


def reference_calls(
    row: dict[str, Any],
    task: dict[str, Any],
    contract: dict[str, Any],
    tools_by_name: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reads = context_calls(row, contract)
    material_reads, material_groups = material_context_calls(row, contract)
    read_signatures = {
        json.dumps(call, sort_keys=True, separators=(",", ":")) for call in reads
    }
    missing_material = [
        call
        for call in material_reads
        if json.dumps(call, sort_keys=True, separators=(",", ":"))
        not in read_signatures
    ]
    if missing_material:
        raise ValueError(
            f"{row['bench_id']} material evidence is absent from its reference: "
            f"{missing_material}"
        )
    source = deepcopy(task["expected_calls"])
    postwrite_reads = postwrite_readback_calls(task, contract)
    decision_record = decision.decision_record_call(contract)
    handoff = {
        "tool": "post_message",
        "args": {
            "channel": contract["channel"],
            "body": decision.handoff_body(contract, CURRENT_CONTROL),
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
    source_mutation_calls = [
        deepcopy(call)
        for call in source
        if (tools_by_name.get(call["tool"], {}).get("write_tables") or [])
    ]
    if not mutation_tools:
        raise ValueError(f"{row['bench_id']} source task has no state transition")
    all_mutation_tools = sorted(
        name
        for name, tool in tools_by_name.items()
        if (tool.get("write_tables") or [])
    )
    workflow_slug = _slug(row["task_id"])
    graph = [
        f"intake_{_slug(contract['case_id'])}",
        f"resolve_{workflow_slug}_cross_tracker_identity",
        f"select_{_slug(CURRENT_CONTROL)}_over_retired_authority",
        f"correlate_{row['category']}_{_slug(contract['service'])}_signals",
        f"test_{workflow_slug}_first_signal_hypothesis",
        f"derive_{workflow_slug}_supported_branch",
        *[f"execute_{workflow_slug}_{_slug(tool)}" for tool in mutation_tools],
        f"plan_{_slug(contract['service'])}_cutover_capacity_{_slug(contract['plan']['recommended_option'])}",
        f"reconcile_{workflow_slug}_post_change_state",
        f"handoff_{_slug(contract['case_id'])}_to_on_call",
        f"reopen_{_slug(contract['case_id'])}_conversation",
    ]
    trace_contract = {
        "required_context_calls": material_reads,
        "material_context_groups": material_groups,
        "reference_context_calls": reads,
        "material_context_call_count": len(material_reads),
        "reference_context_call_count": len(reads),
        "context_call_count": len(reads),
        "source_mutation_tools": mutation_tools,
        "source_mutation_calls": source_mutation_calls,
        "all_mutation_tools": all_mutation_tools,
        "decision_record_call": decision_record,
        "decision_context_calls": decision.decision_context_calls(contract),
        "postwrite_readback_calls": postwrite_reads,
        "handoff_call": handoff,
        "handoff_contract": {
            "tool": "post_message",
            "args": {"channel": contract["channel"]},
            "graded_text_contains": [
                token["token"] for token in decision.handoff_tokens(contract)
            ],
            "graded_tokens": decision.handoff_tokens(contract),
        },
        "readback_call": readback,
        "semantic_action_graph": graph,
        "providers": sorted(
            {PROVIDER_MAPPINGS[call["tool"]] for call in reads if call["tool"] in PROVIDER_MAPPINGS}
        ),
    }
    return [*reads, *source, decision_record, *postwrite_reads, handoff, readback], trace_contract


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
    """Add semantic causal checks around the source final-state verifier."""

    required = trace_contract["required_context_calls"]
    groups = trace_contract["material_context_groups"]
    mutation_tools = trace_contract["source_mutation_tools"]
    source_mutation_calls = trace_contract["source_mutation_calls"]
    all_mutation_tools = trace_contract["all_mutation_tools"]
    postwrite_readbacks = trace_contract["postwrite_readback_calls"]
    handoff = trace_contract["handoff_call"]
    readback = trace_contract["readback_call"]
    block = f'''

# DevOpsBench v3.1 semantic causal-evidence contract for {row["bench_id"]}.
_V4_REQUIRED = {required!r}
_V4_GROUPS = {groups!r}
_V4_SOURCE_MUTATION_TOOLS = {mutation_tools!r}
_V4_SOURCE_MUTATION_CALLS = {source_mutation_calls!r}
_V4_ALL_MUTATION_TOOLS = {all_mutation_tools!r}
_V4_POSTWRITE_READBACKS = {postwrite_readbacks!r}
_V4_HANDOFF = {handoff!r}
_V4_HANDOFF_READBACK = {readback!r}

def _v4_subset(_actual, _expected):
    if isinstance(_expected, dict):
        return isinstance(_actual, dict) and all(
            _k in _actual and _v4_subset(_actual[_k], _v)
            for _k, _v in _expected.items()
        )
    if isinstance(_expected, list):
        return isinstance(_actual, list) and len(_actual) == len(_expected) and all(
            _v4_subset(_a, _e) for _a, _e in zip(_actual, _expected)
        )
    return _actual == _expected

def _v4_positions(_selector, _successful=False):
    _rows = conn.execute(
        "SELECT seq, tool, args_json, ok FROM mcp_trace WHERE tool=? ORDER BY seq",
        (_selector["tool"],),
    ).fetchall()
    _out = []
    for _row in _rows:
        if _successful and not int(_row[3]):
            continue
        if _v4_subset(json.loads(_row[2]), _selector.get("args") or {{}}):
            _out.append(int(_row[0]))
    return _out

def _v4_success_before(_selectors, _boundary):
    return bool(_boundary) and all(
        any(_position < _boundary for _position in _v4_positions(_selector, True))
        for _selector in _selectors
    )

def _v4_success_after(_selectors, _boundary):
    return bool(_boundary) and all(
        any(_position > _boundary for _position in _v4_positions(_selector, True))
        for _selector in _selectors
    )

_v4_source_write_positions = sorted({{
    _position
    for _selector in _V4_SOURCE_MUTATION_CALLS
    for _position in _v4_positions(_selector, True)
}})
_v4_first_source_write = min(_v4_source_write_positions) if _v4_source_write_positions else 0
_v4_last_source_write = max(_v4_source_write_positions) if _v4_source_write_positions else 0
_v4_material_before_write = _v4_success_before(
    _V4_REQUIRED, _v4_first_source_write
)
_v4_source_mutations_completed = all(
    bool(_v4_positions(_selector, True))
    for _selector in _V4_SOURCE_MUTATION_CALLS
)
_v4_source_hard_ok = all(
    bool(_ok) for _dimension, _name, _ok, _message in _checks
    if _dimension in ("correctness", "deployment")
)
_v4_postwrite_complete = _v4_success_after(
    _V4_POSTWRITE_READBACKS, _v4_last_source_write
)
_v4_postwrite_positions = [
    min(
        _position for _position in _v4_positions(_selector, True)
        if _position > _v4_last_source_write
    )
    for _selector in _V4_POSTWRITE_READBACKS
    if any(
        _position > _v4_last_source_write
        for _position in _v4_positions(_selector, True)
    )
]
_v4_handoff_positions = _v4_positions(_V4_HANDOFF, True)
_v4_handoff_seq = min(_v4_handoff_positions) if _v4_handoff_positions else 0
_v4_handoff_readback_positions = [
    _position for _position in _v4_positions(_V4_HANDOFF_READBACK, True)
    if _position > _v4_handoff_seq
]
_v4_rejected_mutations = _one(
    "SELECT COUNT(*) FROM mcp_trace WHERE ok=0 AND tool IN (" +
    ",".join("?" for _ in _V4_ALL_MUTATION_TOOLS) + ")",
    *_V4_ALL_MUTATION_TOOLS,
) or 0

_c("correctness", "v4_case_identity_resolved",
   _v4_success_before(_V4_GROUPS["identity"], _v4_first_source_write),
   "resolve {contract['case_id']} through its immutable Jira key, linked GitHub issue, and cross-tracker relationship")
_c("correctness", "v4_authority_reconciled",
   _v4_success_before(_V4_GROUPS["authority"], _v4_first_source_write),
   "compare current control {CURRENT_CONTROL} with retired control {RETIRED_CONTROL} before acting")
_c("correctness", "v4_live_state_correlated",
   _v4_success_before(_V4_GROUPS["live_state"], _v4_first_source_write),
   "correlate the task-specific {contract['service']} provider state instead of relying on files or tracker text alone")
_c("correctness", "v4_material_evidence_complete",
   _v4_material_before_write,
   "complete the 13 materially causal evidence joins inside the larger reference investigation before changing state")
_c("deployment", "v4_evidence_before_state_change",
   _v4_material_before_write and _v4_first_source_write > 0,
   "establish every material fact before the first successful task state transition")
_c("correctness", "v4_supported_path_selected",
   _v4_source_hard_ok and _v4_source_mutations_completed,
   "derive and execute the task-supported branch rather than the stale-note or broad-workaround alternatives")
_c("correctness", "v4_source_mutations_completed",
   _v4_source_mutations_completed,
   "complete each task-required state-changing capability at least once successfully")
_c("deployment", "v4_state_readbacks_complete",
   _v4_postwrite_complete,
   "reopen the persisted provider and tracker state after the final source mutation instead of trusting acknowledgements")
_c("correctness", "v4_completion_handoff_exactly_once",
   _one("SELECT COUNT(*) FROM messages WHERE channel=? AND author='agent' AND body LIKE ?",
        {contract['channel']!r}, '%{contract['completion_marker']}%') == 1,
   "write exactly one scoped completion handoff for {contract['case_id']}")
_c("deployment", "v4_source_work_precedes_readback",
   _v4_last_source_write > 0 and _v4_postwrite_complete,
   "perform provider readback only after the task-specific operational state change")
_c("deployment", "v4_readback_precedes_handoff",
   _v4_postwrite_complete and _v4_handoff_seq > 0 and
   bool(_v4_postwrite_positions) and _v4_handoff_seq > max(_v4_postwrite_positions),
   "post the completion handoff only after the changed provider state has been reopened")
_c("deployment", "v4_handoff_read_back",
   bool(_v4_handoff_readback_positions) and _v4_handoff_seq > 0,
   "reopen the exact case-room conversation after posting the completion handoff")
_c("deployment", "v4_no_rejected_mutations",
   _v4_rejected_mutations == 0,
   "complete without a rejected state-changing call; failed exploratory reads remain recoverable")
'''
    return vcode.rstrip() + "\n" + block + decision.vcode_block(row, contract)


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
    """Three costed capacity plans; exactly one is authorised and recommended."""

    options = decision.decision_options(row, contract)
    if len(options) != 3 or sum(option["selected"] for option in options) != 1:
        raise ValueError(f"{row['bench_id']} must publish three options with one selected")
    return options


def atomic_checks(vcode: str) -> list[dict[str, str]]:
    """Extract stable occurrence-aware IDs for every executable low-level check."""

    tree = ast.parse(vcode)
    raw: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "_c"
            or len(node.args) < 4
        ):
            continue
        dimension = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
        name = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
        message = node.args[3].value if isinstance(node.args[3], ast.Constant) else None
        if isinstance(dimension, str) and isinstance(name, str):
            raw.append(
                (
                    dimension,
                    name,
                    message if isinstance(message, str) else name.replace("_", " "),
                )
            )

    totals: dict[tuple[str, str], int] = {}
    for dimension, name, _ in raw:
        totals[(dimension, name)] = totals.get((dimension, name), 0) + 1
    seen: dict[tuple[str, str], int] = {}
    checks: list[dict[str, str]] = []
    for dimension, name, description in raw:
        key = (dimension, name)
        seen[key] = seen.get(key, 0) + 1
        suffix = f"#{seen[key]}" if totals[key] > 1 else ""
        checks.append(
            {
                "id": f"{dimension}.{name}{suffix}",
                "dimension": dimension,
                "name": name,
                "description": description,
            }
        )
    return checks


def semantic_milestones(
    task: dict[str, Any],
    row: dict[str, Any],
    contract: dict[str, Any],
    trace_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    """Group low-level verifier evidence into task-specific employee outcomes."""

    milestone_ids = list(SEMANTIC_MILESTONE_WEIGHTS)
    grouped: dict[str, list[dict[str, str]]] = {key: [] for key in milestone_ids}
    explicit = {
        "v4_case_identity_resolved": "investigation.scope",
        "v4_authority_reconciled": "investigation.authority",
        "v4_live_state_correlated": "investigation.live_state",
        "v4_material_evidence_complete": "analysis.causal_reasoning",
        "v4_evidence_before_state_change": "execution.sequence",
        "v4_supported_path_selected": "decision.supported_path",
        "v4_source_mutations_completed": "state.primary",
        "v4_state_readbacks_complete": "verification.outcome",
        "v4_completion_handoff_exactly_once": "answer.insights",
        "v4_source_work_precedes_readback": "verification.readback",
        "v4_readback_precedes_handoff": "execution.delivery",
        "v4_handoff_read_back": "verification.readback",
        "v4_no_rejected_mutations": "execution.efficiency",
        **decision.check_names(),
    }
    containment_tokens = (
        "scoped_change",
        "world_invariants",
        "no_unrelated",
        "nothing_extra",
        "no_new_hardcoded_secrets",
        "check_not_weakened",
        "staging_untouched",
    )
    coordination_tokens = (
        "ticket_closed",
        "jira_twin",
        "pr_linked",
        "pr_has_description",
        "public_status",
        "status_update",
        "postmortem",
        "followup",
        "security_audit",
        "justification",
        "announced",
    )
    verification_tokens = (
        "ci_",
        "test",
        "metric",
        "slo",
        "alarm_resolved",
        "incident_resolved",
        "three_green",
        "check_passes",
        "no_alarming",
    )
    analysis_tokens = (
        "consulted",
        "read_the_source",
        "read_the_proposals",
        "investigation_was_read_only",
        "decision_was_read_only",
        "assumption",
        "fault_type",
        "offending_key",
        "service_localized",
        "causes_are_distinct",
    )
    answer_tokens = (
        "answer",
        "diagnosis",
        "decision_submitted",
        "reasoning_recorded",
        "evidence_recorded",
        "states_",
        "root_cause_written",
        "attributed_",
        "key_for_",
        "detection_correct",
        "fault_confirmed",
        "chose_the_root",
        "outcome_recorded",
        "every_match_reported",
    )

    for check in atomic_checks(task["vcode"]):
        name = check["name"]
        if name in explicit:
            milestone_id = explicit[name]
        elif any(token in name for token in containment_tokens):
            milestone_id = "containment.scope"
        elif name in {"no_unproductive_ci_loops", "efficient_investigation"}:
            milestone_id = "execution.efficiency"
        elif name == "closed_after_the_work":
            milestone_id = "execution.delivery"
        elif any(token in name for token in coordination_tokens):
            milestone_id = "state.coordination"
        elif any(token in name for token in verification_tokens):
            milestone_id = "verification.outcome"
        elif any(token in name for token in analysis_tokens):
            milestone_id = "analysis.causal_reasoning"
        elif any(token in name for token in answer_tokens):
            milestone_id = "answer.insights"
        elif check["dimension"] == "deployment":
            milestone_id = "execution.sequence"
        elif check["dimension"] == "quality":
            milestone_id = "state.coordination"
        else:
            milestone_id = "state.primary"
        grouped[milestone_id].append(check)

    empty = [key for key, checks in grouped.items() if not checks]
    if empty:
        raise ValueError(f"{row['bench_id']} has empty semantic milestones: {empty}")
    assigned = [check["id"] for checks in grouped.values() for check in checks]
    expected = [check["id"] for check in atomic_checks(task["vcode"])]
    if len(assigned) != len(set(assigned)) or sorted(assigned) != sorted(expected):
        raise ValueError(f"{row['bench_id']} semantic check assignment is not one-to-one")

    # The release prompt deliberately starts with a rotating workplace-context
    # sentence.  Rubric language must name the employee's actual request, not
    # that wrapper, or unrelated tasks appear to share the same decision.
    title = employee_title(
        {"instruction": task.get("source_instruction", task.get("instruction", ""))}
    )
    material = trace_contract["material_context_call_count"]
    reference = trace_contract["reference_context_call_count"]
    mutation_tools = ", ".join(trace_contract["source_mutation_tools"])
    plan = contract["plan"]
    descriptions = {
        "investigation.scope": f"Resolve {contract['case_id']} for {contract['service']} through immutable Jira and GitHub identities and keep neighboring NovaCart work outside the case.",
        "investigation.authority": f"Establish {CURRENT_CONTROL} as current for {contract['case_id']} and reject the conflicting {RETIRED_CONTROL} shortcut as historical evidence.",
        "investigation.live_state": f"Interrogate the live {contract['service']} provider surfaces that control this {row['category']} decision; files and tracker prose alone are insufficient.",
        "analysis.causal_reasoning": f"Join the {material} materially causal lookups inside the {reference}-read reference investigation and explain which evidence supports or blocks the requested outcome.",
        "analysis.capacity_plan": f"Derive the {contract['service']} cutover capacity plan from its scattered sources: {plan['per_zone']} replicas per zone x {plan['zones']} zones = {plan['required']} required, {plan['observed']} observed less {plan['reserved']} reserved = {plan['usable']} usable, a {plan['gap']}-replica gap, {decision.VENDOR}'s {decision.iso(plan['standard_days'])}/{decision.iso(plan['expedited_days'])} delivery dates, the {decision.iso(plan['window_days'][0])} change window and the {plan['cutover_date']} cutover.",
        "decision.supported_path": f"For “{title}”, choose the evidence-supported path after comparing the stale-note and broad-workaround alternatives, then execute only that bounded path.",
        "decision.options": f"Weigh {decision.OPTION_STANDARD} ({decision.iso(plan['standard_completion'])}, USD 0), {decision.OPTION_EXPEDITE} ({decision.iso(plan['expedited_completion'])}, USD {plan['expedite_fee']}) and {decision.OPTION_RELEASE} ({decision.iso(plan['release_completion'])}, USD {plan['release_fee']}, approval beyond {contract['approval_ticket']}); recommend {plan['recommended_option']} with its {decision.iso(plan['recommended_completion'])} outcome, {plan['variance']:+d}-day variance and honest {plan['status']} status, and record it as the {contract['capacity_question']} decision.",
        "state.primary": f"Produce the task-specific source-of-truth transition with the required {mutation_tools} capabilities and satisfy every authored final-state invariant.",
        "state.coordination": f"Bring the linked tracker, pull-request, incident, status, approval, or follow-up records required by {contract['case_id']} to their supported coordinated state.",
        "verification.outcome": f"Confirm the changed {contract['service']} outcome through its tests, CI, metrics, alarms, or provider records rather than inferring success from a write acknowledgement.",
        "verification.readback": f"After the final operational mutation, reopen every task-specific provider record and finally reopen {contract['channel']} after its completion handoff.",
        "execution.sequence": f"Respect the task's evidence, approval, staging, canary, mitigation, and closure ordering, record the capacity plan after its evidence and before the handoff, while allowing independent evidence sources to be investigated in any valid order.",
        "containment.scope": f"Preserve frozen services, unrelated records, seeded audit history, and credentials outside {contract['case_id']}; no fabricated or broad workaround state is accepted.",
        "answer.insights": f"Leave a {contract['case_id']} handoff that states the supported result, the recommended {plan['recommended_option']} plan, its {decision.iso(plan['recommended_completion'])} outcome, the {contract['approval_ticket']} approval scope, the binding {decision.VENDOR} constraint and the {plan['status']} timing status without overstating what changed.",
        "execution.efficiency": "Recover from exploratory read mistakes, but complete without a rejected mutation, a CI loop, or repeated unproductive investigation.",
        "execution.delivery": f"Finish the source work, verify persisted state, post exactly one scoped handoff, reopen it, and only then close the employee work item.",
    }
    milestones = [
        {
            "id": milestone_id,
            "category": milestone_id.split(".", 1)[0],
            "description": descriptions[milestone_id],
            "weight": SEMANTIC_MILESTONE_WEIGHTS[milestone_id],
            "atomic_checks": grouped[milestone_id],
        }
        for milestone_id in milestone_ids
    ]
    if sum(item["weight"] for item in milestones) != 100:
        raise AssertionError("semantic milestone weights must total 100")
    return milestones


def _excel_col(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _xlsx(rows: list[list[Any]]) -> bytes:
    def write_member(archive: zipfile.ZipFile, name: str, content: str) -> None:
        member = zipfile.ZipInfo(name, date_time=FIXED_XLSX_ZIP_TIMESTAMP)
        member.compress_type = zipfile.ZIP_DEFLATED
        member.create_system = 3
        member.external_attr = 0o600 << 16
        archive.writestr(member, content)

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
        write_member(archive, "[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        write_member(archive, "_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        write_member(archive, "xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Evidence" sheetId="1" r:id="rId1"/></sheets></workbook>')
        write_member(archive, "xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        write_member(archive, "xl/worksheets/sheet1.xml", worksheet)
    return stream.getvalue()


def _pdf(text: str) -> bytes:
    lines = [
        wrapped
        for line in text.splitlines()
        if line.strip()
        for wrapped in textwrap.wrap(line, width=100, break_long_words=False, break_on_hyphens=False)
    ][:45]
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
) -> list[dict[str, Any]]:
    """Write 28 human-shaped, native evidence files without gold or recipes."""

    root.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(database)
    cx.row_factory = sqlite3.Row
    assets: list[dict[str, Any]] = []
    material_live_assets = (
        {
            "14-service-catalog.csv",
            "16-metrics-export.csv",
            "18-sentry-issues.json",
            "19-kubernetes-pods.yaml",
        }
        if row["category"] in OBSERVABILITY_CATEGORIES
        else {
            "14-service-catalog.csv",
            "21-deployment-history.json",
            "22-ci-runs.csv",
            "23-pull-request-context.json",
        }
        if row["category"] in DELIVERY_CATEGORIES
        else {
            "14-service-catalog.csv",
            "22-ci-runs.csv",
            "23-pull-request-context.json",
            "24-migration-state.sql",
        }
        if row["category"] in ENGINEERING_CATEGORIES
        else {
            "14-service-catalog.csv",
            "15-slo-export.csv",
            "21-deployment-history.json",
            "23-pull-request-context.json",
        }
    )
    material_assets = {
        "02-jira-work-item.csv",
        "03-cross-tracker-links.json",
        "04-github-issue.json",
        "05-current-operating-control.pdf",
        "06-retired-shortcut-note.pdf",
        "07-case-room-thread.json",
        "08-pagerduty-change-events.csv",
        "09-service-owner-register.xlsx",
        "28-change-readiness-standard.pdf",
        "29-vendor-capacity-order.csv",
        "30-change-approval-record.csv",
        "31-capacity-reservation-register.json",
        "32-customer-cutover-notice.json",
        *material_live_assets,
    }

    def add(name: str, source: str, content: str | bytes, role: str) -> None:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
        assets.append(
            {
                "path": str(target.relative_to(root.parent.parent)),
                "source": source,
                "kind": target.suffix.lstrip("."),
                "evidence_role": role,
                "material": name in material_assets,
            }
        )

    case = dict(cx.execute("SELECT * FROM jira_issues WHERE key=?", (contract["case_id"],)).fetchone())
    github = dict(cx.execute("SELECT * FROM github_issues WHERE number=?", (contract["github_issue"],)).fetchone())
    links = [dict(r) for r in cx.execute("SELECT * FROM issue_links WHERE source=?", (contract["case_id"],))]
    pages = [dict(r) for r in cx.execute("SELECT * FROM confluence_pages WHERE page_id IN (?,?) ORDER BY stale", (contract["current_page"], contract["retired_page"]))]
    messages = [dict(r) for r in cx.execute("SELECT * FROM messages WHERE channel=? ORDER BY message_id", (contract["channel"],))]
    owner = [dict(r) for r in cx.execute("SELECT * FROM owner_spreadsheet WHERE row_id=?", (contract["owner_row"],))]
    changes = [dict(r) for r in cx.execute("SELECT * FROM pd_change_events WHERE pd_service_id=?", (contract["pd_service_id"],))]
    readiness = dict(cx.execute("SELECT * FROM confluence_pages WHERE page_id=?", (contract["readiness_page"],)).fetchone())
    vendor_order = dict(cx.execute("SELECT * FROM jira_issues WHERE key=?", (contract["vendor_ticket"],)).fetchone())
    approval = dict(cx.execute("SELECT * FROM jira_issues WHERE key=?", (contract["approval_ticket"],)).fetchone())
    reservation = [dict(r) for r in cx.execute("SELECT * FROM linear_issues WHERE identifier=?", (contract["reservation_issue"],))]
    cutover_post = [dict(r) for r in cx.execute("SELECT * FROM status_page_posts WHERE post_id=?", (contract["status_post"],))]
    windows = contract["plan"]["window_dates"]
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
    add("10-release-calendar.xlsx", "Microsoft Graph workbook", _xlsx([["case", "service", "window", "authority"], *[[contract["case_id"], contract["service"], f"{window}T14:00Z", CURRENT_CONTROL] for window in windows], [contract["case_id"], contract["service"], "2025-11-18T14:00Z", RETIRED_CONTROL]]), "schedule")
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
    add("28-change-readiness-standard.pdf", "Confluence current export", _pdf(readiness["title"] + "\n" + readiness["body"]), "requirement")
    add("29-vendor-capacity-order.csv", "Atlassian Jira (vendor project)", _csv_text([vendor_order]), "external-constraint")
    add("30-change-approval-record.csv", "Atlassian Jira (change advisory)", _csv_text([approval]), "approval")
    add("31-capacity-reservation-register.json", "Linear", json.dumps({"case_id": contract["case_id"], "issues": reservation}, indent=2, sort_keys=True) + "\n", "exclusion")
    add("32-customer-cutover-notice.json", "public status page", json.dumps({"case_id": contract["case_id"], "posts": cutover_post}, indent=2, sort_keys=True) + "\n", "business-need")
    manifest = [{"filename": Path(asset["path"]).name, "source": asset["source"], "evidence_role": asset["evidence_role"]} for asset in assets]
    add("33-agent-visible-asset-manifest.json", "release builder", json.dumps({"case_id": contract["case_id"], "gold_included": False, "oracle_sequence_included": False, "assets": manifest}, indent=2, sort_keys=True) + "\n", "manifest")
    cx.close()
    if len(assets) != ASSET_COUNT:
        raise ValueError(f"expected {ASSET_COUNT} assets for {row['bench_id']}, wrote {len(assets)}")
    if sum(bool(asset["material"]) for asset in assets) != MATERIAL_ASSET_COUNT:
        raise ValueError(f"expected {MATERIAL_ASSET_COUNT} material assets for {row['bench_id']}")
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
