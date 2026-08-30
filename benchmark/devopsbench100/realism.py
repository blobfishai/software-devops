"""Causal-evidence release layer for DevOpsBench-100 v3.2.3.

The source world already contains the task-specific operational transitions.
This module adds the part a real employee has to do around those transitions:
resolve a work item across disagreeing systems, establish which control is
current, inspect the live service state, settle the graded capacity decision,
make the supported change, and reopen the handoff after writing it.  The public
prompt stays outcome-oriented; the exact causal contract remains in the
deterministic verifier.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sqlite3
import tempfile
import textwrap
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from benchmark.devopsbench100 import decision


RELEASE_VERSION = "3.2.3"
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
MATERIAL_CONTEXT_CALLS = 20
MINIMUM_REFERENCE_CONTEXT_CALLS = 26
ASSET_COUNT = 53
MATERIAL_ASSET_COUNT = 20
MAX_PROMPT_WORDS = 220
FIXED_XLSX_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CURRENT_CONTROL = "OPS-CONTROL-2026.03"
RETIRED_CONTROL = "OPS-CONTROL-2025.11"
SNAPSHOT_DAY = 420
ACTIVE_ONCALL_DAY = 419
EVIDENCE_WINDOW_START = SNAPSHOT_DAY - 90
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
TASK_SERVICE_HINTS = {
    "tsk_auth_v1_to_v2": "api-gateway",
    "tsk_impl_ratelimit": "api-gateway",
    "tsk_retire_debug_endpoint": "api-gateway",
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

# The four code exercises and the filesystem repair deliberately expose their
# behavioral contract through the sandbox rather than the employee prompt.
# Their public rubric still needs to say what "correct" means; a filename or a
# green hidden-test counter is not a business outcome a reviewer can inspect.
AUTHORED_BEHAVIOR_OUTCOMES = {
    "tsk_impl_backoff": (
        "the payments retry delay must start at base_ms on attempt 1, double on each "
        "later attempt, cap at max_ms, and reject attempts below 1"
    ),
    "tsk_impl_cachekey": (
        "the search cache key must be stable across dictionary insertion order, distinguish "
        "different parameters, and distinguish an explicit null from a missing parameter"
    ),
    "tsk_impl_chunk": (
        "settlement inputs must be split into consecutive order-preserving groups no larger "
        "than size, support one-pass iterables, return no groups for empty input, and reject "
        "sizes below 1"
    ),
    "tsk_impl_ratelimit": (
        "the per-client bucket must start full, consume one token only for an allowed request, "
        "refill continuously without exceeding capacity, preserve fractional elapsed time, "
        "and handle a backward clock step without granting tokens or stalling future refill"
    ),
    "tsk_ws_ledger_missing_account": (
        "ledger.py must return a zero balance for an account with no postings while preserving "
        "integer per-account accumulation and the existing double-entry balance semantics"
    ),
}

READ_ONLY_CATEGORIES = {
    "aiops_analysis",
    "aiops_detection",
    "aiops_localization",
    "attribution",
    "judgement",
    "reconciliation",
}
DELIVERY_CATEGORIES = {
    "api_migration",
    "error_rate_reduction",
    "feature_flag",
    "horizon",
    "human_gated",
    "latency_optimization",
    "multi_service_rollout",
    "security_incident",
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


def _diagnosis_causal_pattern(task: dict[str, Any] | None) -> str:
    """Return an identifier-neutral causal shape grounded in the gold state."""

    if not task:
        return ""
    diagnosis = next(
        (
            call.get("args") or {}
            for call in task.get("expected_calls", [])
            if call.get("tool") == "submit_diagnosis"
        ),
        {},
    )
    fault_type = _slug(str(diagnosis.get("fault_type", "")))
    offending_key = _slug(str(diagnosis.get("offending_key", "")))
    if fault_type == "bad_release" or re.fullmatch(r"v?\d+(?:_\d+)+", offending_key):
        return "release_regression"
    if "cdn" in fault_type or "cdn" in offending_key:
        return "origin_delivery_bypass"
    if "timeout" in fault_type or "timeout" in offending_key:
        return "downstream_timeout_chain"
    return ""


def business_reasoning_primitive(
    row: dict[str, Any], contract: dict[str, Any], task: dict[str, Any] | None = None
) -> str:
    """Describe the employee decision without IDs or service-name permutations."""

    tokens = _slug(str(row["task_id"])).split("_")
    identity_tokens = {"tsk"}
    for value in (
        contract.get("service"),
        contract.get("secondary_service"),
        *SERVICE_ALIASES,
    ):
        identity_tokens.update(_slug(str(value or "")).split("_"))
    meaningful = [
        token
        for token in tokens
        if token
        and token not in identity_tokens
        and not re.fullmatch(r"(?:w\d+|\d+)", token)
    ]
    primitive = "_".join(meaningful) or _slug(str(row["category"]))
    causal_pattern = _diagnosis_causal_pattern(task)
    if causal_pattern and causal_pattern not in primitive:
        primitive = f"{primitive}_{causal_pattern}"
    return primitive


def _task_id_services(task_id: str) -> list[str]:
    normalized = f"_{_slug(task_id)}_"
    matches = sorted(
        (
            (normalized.find(f"_{_slug(alias)}_"), alias, service)
            for alias, service in SERVICE_ALIASES.items()
            if f"_{_slug(alias)}_" in normalized
        ),
        key=lambda item: (item[0], -len(item[1])),
    )
    ordered: list[str] = []
    for _, _, service in matches:
        if service not in ordered:
            ordered.append(service)
    return ordered


def _mentioned_services(task: dict[str, Any]) -> list[str]:
    """Resolve service identities from task IDs and structured argument values.

    Tool verbs such as ``search_docs`` are not service mentions.  Treating a
    serialized call graph as prose previously turned those verbs into fake
    multi-service workflows.
    """

    ordered = _task_id_services(str(task.get("task_id", "")))
    hinted = TASK_SERVICE_HINTS.get(str(task.get("task_id", "")))
    if hinted and hinted not in ordered:
        ordered.append(hinted)

    service_fields = {
        "service",
        "from_service",
        "producer_service",
        "consumer_service",
        "depends_on",
    }

    def visit(value: Any, field: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, key)
        elif isinstance(value, list):
            for item in value:
                visit(item, field)
        elif isinstance(value, str):
            candidates: list[str] = []
            if field in service_fields:
                candidates.extend(_task_id_services(value))
            elif field == "path":
                # Repository paths encode ownership in their directory, not
                # in arbitrary filename tokens (``notify_client.py`` is still
                # payments code, not a second notifications service).
                components = value.replace("\\", "/").split("/")[:-1]
                for component in components:
                    candidates.extend(_task_id_services(component))
            for service in candidates:
                if service not in ordered:
                    ordered.append(service)

    visit(task.get("expected_calls", []))
    return ordered


def primary_service(task: dict[str, Any], index: int) -> str:
    services = _mentioned_services(task)
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
    task_id_services = _mentioned_services(task)
    explicit_service = bool(task_id_services)
    business_scope = service
    business_context = SERVICE_CONTEXT[service]
    mentioned_services = task_id_services
    if len(mentioned_services) > 1 and row["category"] == "attribution":
        service_list = (
            f"{mentioned_services[0]} and {mentioned_services[1]}"
            if len(mentioned_services) == 2
            else ", ".join(mentioned_services[:-1]) + f", and {mentioned_services[-1]}"
        )
        business_scope = service_list + " incident set"
        business_context = (
            "Its business boundary is temporal correlation versus shared causation, the distinct "
            "runtime and deployment evidence for each affected service, and whether one or several "
            "incident owners are required."
        )
    elif len(mentioned_services) > 1:
        business_scope = " → ".join(mentioned_services) + " capability chain"
        business_context = (
            "Its business boundary is the upstream-to-downstream dependency direction, the "
            "contract at each service boundary, ownership, recoverability, and end-to-end health."
            if row["category"] != "multi_service_rollout"
            else "Its business boundary is producer-consumer dependency direction, schema readiness, "
            "service ownership, guarded rollout order, rollback safety, and end-to-end health."
        )
    elif not explicit_service:
        if row["category"] == "cross_system":
            business_scope = "engineering work portfolio"
            business_context = (
                "Its business boundary is tracker identity, status, ownership, duplicate control, "
                "and communication to the teams acting on the resulting population."
            )
        elif row["category"] == "reconciliation":
            business_scope = "operational reporting portfolio"
            business_context = (
                "Its business boundary is the governing definition, source precedence, reporting "
                "window, duplicate treatment, and the decision made from the reconciled result."
            )
        elif row["category"] == "workspace":
            business_scope = "finance export workspace"
            business_context = (
                "Its business boundary is the account population, zero-balance behavior, executable "
                "export check, and the integrity of unrelated ledger files."
            )
        elif row["category"] == "handover":
            business_scope = "shared on-call operating model"
            business_context = (
                "Its business boundary is symptom triage, escalation ownership, safe diagnostic "
                "commands, and guidance the next engineer can reproduce during an incident."
            )
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
        "service_is_explicit": explicit_service,
        "business_scope": business_scope,
        "business_context": business_context,
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
        "plan": decision.capacity_plan(
            index, service, secondary_service, SERVICE_NAMES, approval_ticket
        ),
    }


CAPACITY_DECISION_CLOSES = (
    "Before handoff, also settle whether {service} can meet its {cutover} cutover: derive the healthy-replica requirement, subtract reserved capacity from the usable pool, quantify the gap, compare {vendor}'s standard and expedited arrivals against the change windows, cost and approval state of all three options, and persist one recommendation with its signed schedule variance and honest on-time-or-late status.",
    "The release review also needs a defensible {service} capacity plan for {cutover}. Reconcile required versus genuinely free replicas, the uncovered gap, {vendor}'s confirmed delivery dates, window-bounded completion, incremental cost, and approval scope for each alternative; record the supported choice and restate its timing in the handoff you reopen.",
    "Include the {cutover} readiness decision in the final handoff. Work from the replica standard, current capacity net of the reservation, the remaining deficit, {vendor}'s two delivery commitments, and the published change calendar; price and authority-label all three paths, then save one recommendation with the exact variance and timing status.",
    "Management also needs to know whether {service} is realistically ready for {cutover}. Calculate demand, usable supply after reserved capacity, and the shortfall; map standard delivery, paid expedite, and releasing the reservation onto real change windows, costs, and approval limits; persist the chosen plan and verify the handoff that reports it.",
    "Close the capacity side of this request too: establish the replicas the readiness rule demands, what remains usable after the reservation, the gap {vendor} must cover, and every option's windowed finish, spend, authority, and consequence. Choose one against {cutover}, save the decision, and reopen the note containing its schedule variance.",
    "For the {service} cutover on {cutover}, reconcile the readiness requirement with the actually available pool, calculate the missing replicas, compare {vendor}'s standard and expedited dates with the release calendar, and evaluate all three costed plans under the recorded approval. Persist the recommendation and verify its on-time-or-late handoff.",
    "Treat the {cutover} cutover as a real planning decision, not a date copied from a ticket: derive required and usable replicas, the capacity gap, vendor arrival and next eligible window for each path, incremental cost, approval status, and consequence. Record one supported option with exact timing and reopen the handoff that states it.",
    "The incoming owner also needs the {service} capacity answer for {cutover}. Join the readiness rule, live pool, reservation, vendor order, approval record, and change calendar; show the required, usable, and missing replicas, all three costed completion options, the selected path, its schedule variance, and whether it is honestly on time or late.",
    "Before closing, resolve the cutover capacity question for {service}. Net the reserved replicas out of current supply, compare the resulting gap with {vendor}'s delivery commitments, place each option into the next valid change window, and make cost and approval tradeoffs explicit. Persist the recommendation and read back the handoff containing the result.",
    "Add a source-backed capacity plan for the {cutover} milestone: required healthy replicas, usable replicas after the existing reservation, deficit, standard and expedited supply dates, window-constrained completions, costs, approval coverage, and consequences for three alternatives. Save one choice with its variance and timing status, then verify the shared note.",
    "The final record must also answer whether {service} can carry the {cutover} cutover. Derive demand and free supply, identify the vendor-bound gap, compare three calendar-aware options by completion, cost, authority, and operational consequence, and persist the supported recommendation with an exact on-time-or-late calculation that the reopened handoff repeats.",
    "Finish with the practical cutover choice: how many healthy replicas {service} needs, how many remain after reserved capacity, what is missing, when {vendor} can supply it, which change window each of three plans can use, what each costs and who may approve it. Record the chosen plan, variance, and timing status and reopen its handoff.",
)


def release_prompt(
    row: dict[str, Any],
    employee_request: str,
    contract: dict[str, Any],
) -> str:
    """Wrap the authored outcome in a natural workplace request, not a recipe."""

    investigation_closes = (
        "Explain which conclusion survives cross-checking, record it in the existing incident work item, and leave the live evidence that lets the incoming engineer reproduce it; production controls should remain unchanged.",
        "Resolve the disagreement far enough for the incident lead to act, keep production unchanged, and record both the supported conclusion and any uncertainty the evidence cannot settle.",
        "Give the next shift a defensible finding and make clear which current observations rule out the most tempting alternative explanations.",
        "Establish the operative cause instead of restating the alert, keep production unchanged, and record why the present system state supports that conclusion in the existing incident work item.",
        "Separate upstream cause from downstream symptoms and leave a concise, evidence-linked handoff that another engineer can independently challenge.",
        "Determine what the operating evidence supports today and explain why stale records or plausible shortcuts do not change the answer.",
        "Trace the inconsistency to its authoritative source and record the supported finding while leaving every production control untouched.",
        "Reconcile the affected boundary, identify the decisive signal, and record a production-safe conclusion the service owner can use in the existing incident work item.",
        "Work through the conflicting records, preserve genuine uncertainty, and state the supported operational conclusion in ordinary language.",
        "Find the narrowest explanation that fits every material signal and leave the incident record ready for independent verification.",
        "Test the apparent explanation against the live state, distinguish correlation from cause, keep production unchanged, and record the sourced finding in the existing incident work item.",
        "Use the current evidence to settle what can be settled, flag what remains ambiguous, and make the reasoning auditable for the next review.",
    )
    delivery_closes = (
        "Decide the safest supported path, respect the current approval boundary, and verify the customer-visible result before handing it back.",
        "Carry the remediation through only where live conditions permit it, then reopen the affected state to prove the intended outcome actually holds.",
        "Distinguish urgent containment from durable repair, account for rollback safety, and leave an auditable completion record for the next owner.",
        "Reconcile the proposed change with current policy and runtime evidence, make the scoped transition, and confirm that dependent behavior remains healthy.",
        "Protect unrelated production state, handle the material dependency or migration constraint, and verify the result rather than trusting the change record.",
        "Choose the supported rollout path from the evidence available today, stop if its control conditions are not met, and document what you observed afterward.",
        "Resolve the customer-impacting condition with the smallest defensible intervention and prove both the recovery and the retained safety boundary.",
        "Account for affected consumers and current authorization, carry the change through in a recoverable way, and leave enough evidence for independent review.",
        "Treat conflicting records as part of the work: establish precedence, make only the justified change, and verify the authoritative state after writing it.",
        "Complete the production outcome without broadening scope, confirm the relevant health signal, and communicate any exception that still needs ownership.",
        "Use current operating constraints to select the viable option, execute its guarded transition, and demonstrate the post-change state at the service boundary.",
        "Balance restoration speed with dependency and rollback risk, then leave a sourced handoff showing why the final production state is acceptable.",
    )
    engineering_closes = (
        "Use the repository's documented behavior to decide what is actually missing, make the smallest defensible edit, and prove the boundary cases another engineer would challenge.",
        "Reproduce the failure, repair its underlying contract rather than its surface symptom, and leave the available validation trustworthy for the next contributor.",
        "Resolve the implementation gap without coupling unrelated behavior, demonstrate the expected edge cases, and record the reasoning behind the change.",
        "Treat the existing code and tests as evidence rather than a recipe, close the behavioral gap, and show that the repaired result remains stable under repetition.",
        "Find the narrowest code-level cause, correct it within the documented interface, and leave a reproducible proof that the original failure no longer occurs.",
        "Make the implementation match its consumer-facing contract, cover the non-obvious cases, and keep the handoff clear enough for independent review.",
        "Separate a deterministic defect from incidental test noise, repair the real boundary, and demonstrate why rerunning the pipeline is no longer a workaround.",
        "Trace the failing behavior through the repository, change only the responsible component, and leave both validation and operational context intact.",
        "Implement the supported behavior with a minimal diff, verify its failure modes as well as its happy path, and document any remaining assumption.",
        "Reconcile the written contract with the executable behavior, correct the discrepancy, and make the result straightforward for another engineer to reproduce.",
        "Use the current workspace evidence to identify the missing invariant, restore it without masking adjacent failures, and prove the final behavior locally.",
        "Close the engineering request at the behavior level, not merely the visible assertion, and leave a concise explanation of what changed and why.",
    )
    coordination_closes = (
        "Use the current records to decide what genuinely belongs in scope, carry the request through, and leave a result that can be independently audited.",
        "Resolve the cross-system disagreement before acting, protect unrelated work, and confirm the final record from its authoritative source.",
        "Determine the supported answer or transition from the live evidence, then communicate it at the level the requesting team needs.",
        "Treat duplicate, stale, and in-flight records carefully, make only the scoped update, and verify that the intended population changed.",
        "Reconcile identity across the available systems, apply the business rule to the resulting set, and leave a clear account of exclusions.",
        "Establish which source governs the decision, complete the requested coordination, and make any unresolved exception visible to its owner.",
        "Work from the actual current population rather than a convenient snapshot, preserve out-of-scope records, and verify the delivered outcome.",
        "Follow the evidence through its conflicting representations, resolve the employee's underlying question, and make the conclusion reproducible.",
        "Use the governing definition and present state to make the decision, then leave the shared record consistent for the next workflow.",
        "Separate records that only look equivalent from those that really refer to the same work, complete the scoped action, and confirm the result.",
        "Account for precedence, status, and ownership before changing anything, and hand back a sourced outcome with no collateral mutations.",
        "Turn the fragmented operating evidence into one defensible result, carry through any justified write, and reopen it to verify persistence.",
    )
    ordinal = int(row["index"]) - 1
    # Shift the prose cadence between each block of twelve tasks so two jobs
    # on the same service never become wording variants merely because their
    # catalog positions share a remainder.
    position = (ordinal % 12 + ordinal // 12) % 12
    if row["category"] in READ_ONLY_CATEGORIES:
        close = investigation_closes[position]
    elif row["category"] in DELIVERY_CATEGORIES:
        close = delivery_closes[position]
    elif row["category"] == "handover":
        close = coordination_closes[position]
    elif row["category"] in ENGINEERING_CATEGORIES:
        close = engineering_closes[position]
    else:
        close = coordination_closes[position]
    service_context = contract.get(
        "business_context", SERVICE_CONTEXT[contract["service"]]
    ).replace(
        "Its business boundary is",
        f"For {contract.get('business_scope', contract['service'])}, the affected business boundary includes",
    )
    topic_context = contract.get("topic_context", "")
    # Use a second coprime cadence for the planning paragraph.  It prevents
    # two jobs from inheriting both the same operational close and the same
    # capacity language merely because their catalog indices collide modulo
    # twelve.
    capacity_position = (ordinal * 5 + ordinal // 12) % 12
    capacity_close = CAPACITY_DECISION_CLOSES[capacity_position].format(
        service=contract["service"],
        cutover=contract["plan"]["cutover_date"],
        vendor=decision.VENDOR,
    )
    attempts = (
        (employee_request.strip(), service_context, topic_context, close, capacity_close),
        (employee_request.strip(), service_context, "", close, capacity_close),
        (employee_request.strip(), service_context, "", "", capacity_close),
        (employee_request.strip(), "", "", "", capacity_close),
    )
    for parts in attempts:
        prompt = re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()
        if len(prompt.split()) <= MAX_PROMPT_WORDS:
            return prompt
    raise ValueError(f"{row['bench_id']} cannot fit its high-level request in {MAX_PROMPT_WORDS} words")


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
            SNAPSHOT_DAY - 6,
            SNAPSHOT_DAY,
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
            SNAPSHOT_DAY - 5,
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
                SNAPSHOT_DAY,
                0,
            ),
            (
                contract["retired_page"],
                "OPS",
                f"{contract['case_id']} retired shortcut note",
                retired_body,
                SNAPSHOT_DAY - 110,
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
            SNAPSHOT_DAY - 1,
            "monday",
        ),
    )
    cx.execute(
        "INSERT INTO pd_change_events(pd_service_id,summary,day) VALUES (?,?,?)",
        (
            contract["pd_service_id"],
            f"{contract['case_id']} intake evidence for {contract['service']}; outcome not yet established",
            SNAPSHOT_DAY - 1,
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
    if category in READ_ONLY_CATEGORIES:
        return [
            {"tool": "resolve_service_alias", "args": {"name": service}},
            {"tool": "pd_list_services", "args": {}},
            {"tool": "pd_list_oncalls", "args": {"day": ACTIVE_ONCALL_DAY}},
            {"tool": "list_status_page_posts", "args": {"since_day": EVIDENCE_WINDOW_START}},
            {"tool": "list_alert_rules", "args": {}},
            {"tool": "list_alert_firings", "args": {"since_day": EVIDENCE_WINDOW_START}},
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
        {"tool": "pd_list_incidents", "args": {"since_day": EVIDENCE_WINDOW_START}},
        {"tool": "list_status_page_posts", "args": {"since_day": EVIDENCE_WINDOW_START}},
        {"tool": "list_tickets", "args": {"service": service}},
        {"tool": "list_pull_requests", "args": {"service": service}},
        {"tool": "list_deployments", "args": {"service": service}},
        {"tool": "list_commits", "args": {"service": service}},
    ]


def _causal_live_state_calls(
    row: dict[str, Any],
    task: dict[str, Any] | None,
    contract: dict[str, Any],
    tools_by_name: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Use different live systems for materially different causal questions."""

    primitive = business_reasoning_primitive(row, contract, task)
    diagnosis = next(
        (
            call.get("args") or {}
            for call in (task or {}).get("expected_calls", [])
            if call.get("tool") == "submit_diagnosis"
        ),
        {},
    )
    responsible_service = str(diagnosis.get("service") or contract["service"])
    service = contract["service"]
    dependency_source = str(contract.get("secondary_service") or service)
    profiles: dict[str, list[dict[str, Any]]] = {
        "rca_disk_pressure": [
            {"tool": "k8s_nodes_list", "args": {}},
            {"tool": "k8s_events_list", "args": {}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
        ],
        "rca_node_deadlock": [
            {"tool": "check_network_path", "args": {"from_service": service}},
            {"tool": "k8s_pods_list", "args": {"service": service}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
        ],
        "detect_errors": [
            {"tool": "sentry_search_issues", "args": {"status": "unresolved"}},
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "list_feature_flags", "args": {"service": service}},
        ],
        "detect": [
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "list_alert_firings", "args": {"since_day": EVIDENCE_WINDOW_START}},
            {"tool": "k8s_pods_list", "args": {"service": service}},
        ],
        "detect_healthy": [
            {"tool": "get_status_page", "args": {"limit": 20}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
        ],
        "localize_crashloop": [
            {"tool": "k8s_events_list", "args": {}},
            {"tool": "k8s_pods_list", "args": {"service": responsible_service}},
            {"tool": "get_runtime_stats", "args": {"service": responsible_service}},
        ],
        "localize_errors": [
            {"tool": "sentry_search_issues", "args": {"status": "unresolved"}},
            {"tool": "search_logs", "args": {"service": responsible_service}},
            {"tool": "query_metrics", "args": {"service": responsible_service}},
        ],
        "localize_latency_downstream_timeout_chain": [
            {"tool": "check_network_path", "args": {"from_service": dependency_source}},
            {"tool": "search_docs", "args": {"query": "retry timeout"}},
            {"tool": "get_runtime_stats", "args": {"service": responsible_service}},
            {"tool": "query_metrics", "args": {"service": responsible_service}},
            {"tool": "list_deployments", "args": {"service": responsible_service}},
        ],
        "localize_latency_release_regression": [
            {"tool": "list_deployments", "args": {"service": responsible_service}},
            {"tool": "list_commits", "args": {"service": responsible_service}},
            {"tool": "get_traffic_stats", "args": {"service": responsible_service}},
        ],
        "localize_latency_origin_delivery_bypass": [
            {"tool": "get_traffic_stats", "args": {"service": responsible_service}},
            {"tool": "get_runtime_stats", "args": {"service": responsible_service}},
            {"tool": "list_deployments", "args": {"service": responsible_service}},
            {"tool": "search_logs", "args": {"service": responsible_service}},
        ],
        "rca_retry": [
            {"tool": "search_logs", "args": {"service": service}},
            {"tool": "search_docs", "args": {"query": "retry policy"}},
            {"tool": "list_commits", "args": {"service": service}},
        ],
        "rca_n_plus_one": [
            {"tool": "search_logs", "args": {"service": service}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service}},
        ],
        "rca_timeout_downstream_timeout_chain": [
            {"tool": "search_logs", "args": {"service": service}},
            {"tool": "search_docs", "args": {"query": "timeout standard"}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "list_error_events", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service}},
            {"tool": "check_network_path", "args": {"from_service": dependency_source}},
        ],
        "rca_pool": [
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "search_logs", "args": {"service": service}},
        ],
        "impl_backoff": [
            {"tool": "search_docs", "args": {"query": "retry"}},
            {"tool": "list_commits", "args": {"service": service}},
            {"tool": "list_tests", "args": {"service": service}},
        ],
        "impl_cachekey": [
            {"tool": "list_api_endpoints", "args": {"service": service}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "list_files", "args": {"service": service}},
        ],
        "impl_chunk": [
            {"tool": "list_packages", "args": {"service": service}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "list_files", "args": {"service": service}},
        ],
        "impl_ratelimit": [
            {"tool": "list_api_endpoints", "args": {"service": service}},
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "list_approval_policy", "args": {}},
        ],
        "port_count_inflight_work": [
            {"tool": "list_tickets", "args": {}},
            {"tool": "linear_list_issues", "args": {"state": "In Progress"}},
            {"tool": "list_deployments", "args": {}},
        ],
        "port_count_unowned_work": [
            {"tool": "list_tickets", "args": {}},
            {"tool": "read_owner_spreadsheet", "args": {}},
            {"tool": "pd_list_oncalls", "args": {"day": ACTIVE_ONCALL_DAY}},
        ],
        "port_high_priority_since": [
            {"tool": "github_list_issues", "args": {"state": "open"}},
            {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
            {"tool": "linear_list_issues", "args": {}},
        ],
        "port_collect_open_issues": [
            {"tool": "github_list_issues", "args": {"state": "open"}},
            {"tool": "jira_search", "args": {"project": "ENG"}},
            {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
            {"tool": "list_issue_links", "args": {}},
        ],
        "port_report_customer_reports": [
            {"tool": "github_list_issues", "args": {"state": "open"}},
            {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
            {"tool": "get_status_page", "args": {"limit": 20}},
            {"tool": "list_tickets", "args": {}},
        ],
        "batch_size": [
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "k8s_pods_list", "args": {"service": service}},
        ],
        "cache_ttl": [
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "list_feature_flags", "args": {"service": service}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "get_slo_status", "args": {"service": service}},
            {"tool": "search_logs", "args": {"service": service}},
        ],
        "timeout": [
            {"tool": "check_network_path", "args": {"from_service": dependency_source}},
            {"tool": "search_docs", "args": {"query": "timeout standard"}},
            {"tool": "get_runtime_stats", "args": {"service": "payments"}},
        ],
        "pool_reuse": [
            {"tool": "get_traffic_stats", "args": {"service": service}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
            {"tool": "list_infra", "args": {}},
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "list_alerts", "args": {"service": service}},
        ],
        "flaky_rollup": [
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
        ],
        "flaky_rounding": [
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service}},
        ],
        "flaky_idempotency": [
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "query_metrics", "args": {"service": service}},
        ],
        "flaky_timeout": [
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "check_network_path", "args": {"from_service": service}},
            {"tool": "list_tests", "args": {"service": service}},
        ],
        "flaky_index": [
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
            {"tool": "list_ci_runs", "args": {"service": service}},
        ],
        "cve_libpayproc": [
            {"tool": "list_packages", "args": {"service": service}},
            {"tool": "list_vulnerabilities", "args": {"service": service}},
            {"tool": "search_docs", "args": {"query": "security"}},
        ],
        "cve_requests": [
            {"tool": "list_packages", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service, "query": "requests"}},
            {"tool": "list_deployments", "args": {"service": service}},
        ],
    }
    # Families with similar source harnesses receive longer, causally distinct
    # investigations.  These are business-specific evidence paths, not
    # catalog-index permutations: removing task IDs and service names still
    # leaves different systems and hypotheses to test.
    profiles.update(
        {
            "batch_pricing": [
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_packages", "args": {"service": service}},
            ],
            "cdn": [
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "cdn"}},
            ],
            "webp": [
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_approval_policy", "args": {}},
                {"tool": "search_docs", "args": {"query": "media delivery"}},
            ],
            "autocomplete": [
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "express": [
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_approval_policy", "args": {}},
                {"tool": "query_metrics", "args": {"service": service}},
            ],
            "rca_unschedulable_replicas": [
                {"tool": "k8s_deployments_list", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "k8s_nodes_list", "args": {}},
                {"tool": "k8s_events_list", "args": {}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_alerts", "args": {"service": service}},
            ],
            "rca_unscheduled_reindex": [
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "k8s_events_list", "args": {"reason": "FailedScheduling"}},
                {"tool": "k8s_nodes_list", "args": {}},
                {"tool": "k8s_deployments_list", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
            ],
            "rca_untolerated_taint": [
                {"tool": "k8s_nodes_list", "args": {}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "k8s_events_list", "args": {}},
                {"tool": "k8s_deployments_list", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
            ],
            "rca_migrator_security_context": [
                {"tool": "k8s_events_list", "args": {}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "k8s_deployments_list", "args": {"service": service}},
            ],
            "rca_unbound_storage": [
                {"tool": "k8s_deployments_list", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_infra", "args": {}},
                {"tool": "k8s_nodes_list", "args": {}},
                {"tool": "k8s_events_list", "args": {}},
            ],
            "rca_revoked_grant": [
                {"tool": "list_db_grants", "args": {}},
                {"tool": "list_infra", "args": {}},
                {"tool": "check_network_path", "args": {"from_service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
            ],
            "rca_missing_role": [
                {"tool": "list_db_grants", "args": {}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_infra", "args": {}},
            ],
            "judge_flag": [
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_alerts", "args": {"service": service}},
                {"tool": "list_messages", "args": {"channel": contract["channel"], "limit": 50}},
                {"tool": "get_status_page", "args": {"limit": 20}},
            ],
            "judge_retry": [
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "retry"}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_error_events", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
            ],
            "prefetch": [
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "pool": [
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "retry": [
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "retry"}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_error_events", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "backorders": [
                {"tool": "list_migrations", "args": {"service": "inventory"}},
                {"tool": "get_service", "args": {"service": "inventory"}},
                {"tool": "list_deployments", "args": {"service": "inventory"}},
                {"tool": "list_approval_policy", "args": {}},
                {"tool": "query_metrics", "args": {"service": "checkout"}},
                {"tool": "list_deployments", "args": {"service": "storefront-web"}},
            ],
            "loyalty_points": [
                {"tool": "list_migrations", "args": {"service": "catalog"}},
                {"tool": "list_migrations", "args": {"service": "checkout"}},
                {"tool": "get_service", "args": {"service": "catalog"}},
                {"tool": "get_service", "args": {"service": "checkout"}},
                {"tool": "list_deployments", "args": {"service": "checkout"}},
                {"tool": "list_deployments", "args": {"service": "storefront-web"}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "cve_pydantic": [
                {"tool": "list_packages", "args": {"service": service}},
                {"tool": "list_vulnerabilities", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_ci_runs", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "security"}},
            ],
            "cve_stripe_sdk": [
                {"tool": "list_packages", "args": {"service": service}},
                {"tool": "list_vulnerabilities", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "security"}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "v2_layout_cleanup": [
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
            ],
            "legacy_price_rounding_cleanup": [
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "flaky_rollup": [
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_ci_runs", "args": {"service": service}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "flaky_idempotency": [
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "get_service", "args": {"service": service}},
                {"tool": "list_ci_runs", "args": {"service": service}},
            ],
            "flaky_timeout": [
                {"tool": "check_network_path", "args": {"from_service": service}},
                {"tool": "list_ci_runs", "args": {"service": service}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "flaky_index": [
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_ci_runs", "args": {"service": service}},
            ],
            "rca_retry": [
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "retry"}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_error_events", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
            ],
            "rca_n_plus_one": [
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_packages", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
            ],
            "rca_traffic_flood": [
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "get_status_page", "args": {"limit": 20}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "get_service", "args": {"service": service}},
            ],
            "rca_recreate_strategy": [
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "k8s_pods_list", "args": {"service": service}},
                {"tool": "k8s_events_list", "args": {}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
            ],
            "impl_cachekey": [
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_files", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_tests", "args": {"service": service}},
                {"tool": "search_docs", "args": {"query": "cache"}},
            ],
            "impl_ratelimit": [
                {"tool": "list_api_endpoints", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_approval_policy", "args": {}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "check_network_path", "args": {"from_service": service}},
                {"tool": "list_tests", "args": {"service": service}},
            ],
            "rca_egress_blocked": [
                {"tool": "check_network_path", "args": {"from_service": service}},
                {"tool": "list_infra", "args": {}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "list_alerts", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
            ],
            "rca_gc_thrash": [
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "get_traffic_stats", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
            ],
            "port_close_backlog_issues": [
                {"tool": "list_tickets", "args": {}},
                {"tool": "linear_list_issues", "args": {"state": "Todo"}},
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
                {"tool": "read_owner_spreadsheet", "args": {}},
                {"tool": "github_list_issues", "args": {"state": "open"}},
            ],
            "port_count_open_priority": [
                {"tool": "github_list_issues", "args": {"state": "open"}},
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "linear_list_issues", "args": {}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
                {"tool": "read_owner_spreadsheet", "args": {}},
                {"tool": "list_issue_links", "args": {}},
            ],
            "port_escalate_to_oncall": [
                {"tool": "resolve_service_alias", "args": {"name": "api-gateway"}},
                {"tool": "pd_list_services", "args": {}},
                {"tool": "pd_list_oncalls", "args": {"day": ACTIVE_ONCALL_DAY}},
                {"tool": "read_owner_spreadsheet", "args": {}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
                {"tool": "get_status_page", "args": {"limit": 20}},
            ],
            "port_count_surface": [
                {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
                {"tool": "get_service", "args": {"service": "api-gateway"}},
                {"tool": "get_traffic_stats", "args": {"service": "api-gateway"}},
                {"tool": "list_commits", "args": {"service": "api-gateway"}},
                {"tool": "list_deployments", "args": {"service": "api-gateway"}},
                {"tool": "search_docs", "args": {"query": "public"}},
            ],
            "port_dedupe_linked_issues": [
                {"tool": "list_issue_links", "args": {}},
                {"tool": "github_list_issues", "args": {"state": "open"}},
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "list_tickets", "args": {}},
                {"tool": "linear_list_issues", "args": {}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
            ],
            "port_close_blocked_issues": [
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "list_tickets", "args": {}},
                {"tool": "linear_list_issues", "args": {"state": "In Progress"}},
                {"tool": "list_issue_links", "args": {}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
                {"tool": "read_owner_spreadsheet", "args": {}},
            ],
            "port_copy_priority_issues": [
                {"tool": "github_list_issues", "args": {"state": "open", "label": "priority"}},
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "list_tickets", "args": {}},
                {"tool": "list_issue_links", "args": {}},
                {"tool": "read_owner_spreadsheet", "args": {}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
            ],
            "copy": [
                {"tool": "github_list_issues", "args": {"state": "open"}},
                {"tool": "list_messages", "args": {"channel": "#eng", "limit": 50}},
                {"tool": "jira_search", "args": {"project": "ENG"}},
                {"tool": "linear_list_issues", "args": {}},
                {"tool": "get_status_page", "args": {"limit": 20}},
                {"tool": "list_issue_links", "args": {}},
            ],
            "hz_flag_kill": [
                {"tool": "list_feature_flags", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "list_alerts", "args": {"service": service}},
                {"tool": "get_status_page", "args": {"limit": 20}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "hz_leak_rollback": [
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "search_logs", "args": {"service": service}},
                {"tool": "list_error_events", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": service}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "rcn_production_deploys": [
                {"tool": "query_local_deploy_log", "args": {"service": service}},
                {"tool": "resolve_service_alias", "args": {"name": service}},
                {"tool": "list_deployments", "args": {"service": service}},
                {"tool": "pd_list_change_events", "args": {"since_day": EVIDENCE_WINDOW_START}},
                {"tool": "list_commits", "args": {"service": service}},
                {"tool": "get_status_page", "args": {"limit": 20}},
            ],
            "upsell": [
                {"tool": "get_service", "args": {"service": "checkout"}},
                {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
                {"tool": "list_packages", "args": {"service": "catalog"}},
                {"tool": "get_traffic_stats", "args": {"service": "storefront-web"}},
                {"tool": "list_deployments", "args": {"service": "checkout"}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "pipeline": [
                {"tool": "get_traffic_stats", "args": {"service": "media-service"}},
                {"tool": "get_service", "args": {"service": "media-service"}},
                {"tool": "list_packages", "args": {"service": "catalog"}},
                {"tool": "list_deployments", "args": {"service": "storefront-web"}},
                {"tool": "search_docs", "args": {"query": "media delivery"}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "templates": [
                {"tool": "get_service", "args": {"service": "notifications"}},
                {"tool": "list_files", "args": {"service": "notifications"}},
                {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
                {"tool": "list_deployments", "args": {"service": "payments"}},
                {"tool": "search_docs", "args": {"query": "retry"}},
                {"tool": "list_approval_policy", "args": {}},
            ],
            "relevance": [
                {"tool": "get_traffic_stats", "args": {"service": "search"}},
                {"tool": "list_migrations", "args": {"service": "catalog"}},
                {"tool": "list_packages", "args": {"service": "catalog"}},
                {"tool": "get_service", "args": {"service": "search"}},
                {"tool": "query_metrics", "args": {"service": "search"}},
                {"tool": "list_deployments", "args": {"service": "catalog"}},
            ],
            "ws_ledger_missing_account": [
                {"tool": "ws_list", "args": {}},
                {"tool": "ws_read", "args": {"path": "ledger.py"}},
                {"tool": "ws_read", "args": {"path": "check.py"}},
            ],
        }
    )
    if primitive == "timeout":
        if contract.get("secondary_service"):
            upstream = str(contract["secondary_service"])
            return [
                {"tool": "check_network_path", "args": {"from_service": upstream}},
                {"tool": "search_docs", "args": {"query": "timeout"}},
                {"tool": "search_logs", "args": {"service": upstream}},
                {"tool": "get_runtime_stats", "args": {"service": service}},
                {"tool": "query_metrics", "args": {"service": upstream}},
                {"tool": "list_deployments", "args": {"service": upstream}},
            ]
        return [
            {"tool": "search_logs", "args": {"service": service}},
            {"tool": "search_docs", "args": {"query": "timeout"}},
            {"tool": "get_runtime_stats", "args": {"service": service}},
            {"tool": "list_error_events", "args": {"service": service}},
            {"tool": "list_commits", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
        ]

    explicit = profiles.get(primitive)
    if explicit:
        return deepcopy(explicit)

    # The authored task already contains its domain-specific investigative
    # reads.  For families without an explicit profile, prioritize the last
    # four pre-mutation reads: operating policies and ticket intake generally
    # come first, while the facts that settle the decision come immediately
    # before the state transition.  Retain the earlier reads afterward so the
    # full causal profile remains inspectable and distinct.
    if task and tools_by_name:
        authored = [
            deepcopy(call)
            for call in _leading_source_reads(task, tools_by_name)
            if call["tool"] not in {"get_ticket", "jira_get_issue"}
        ]
        if authored:
            pivot = max(0, len(authored) - 4)
            return [*authored[pivot:], *authored[:pivot]]
    return []


def _material_route_calls(
    row: dict[str, Any],
    task: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    tools_by_name: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Select the live-system joins that actually control the task decision."""

    category = row["category"]
    service = str((contract or {}).get("service") or "")
    candidates: list[dict[str, Any]] = []
    if task and contract:
        candidates.extend(
            _causal_live_state_calls(row, task, contract, tools_by_name)
        )
        candidates.extend(_leading_source_reads(task, tools_by_name or {}))

    preferred = (
        (
            "resolve_service_alias",
            "list_alert_firings",
            "k8s_pods_list",
            "get_runtime_stats",
        )
        if category in READ_ONLY_CATEGORIES
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
    candidates.extend(deepcopy(by_name[name]) for name in preferred if name in by_name)
    selected: list[dict[str, Any]] = []
    seen_selectors: set[str] = set()
    for call in candidates:
        selector = json.dumps(call, sort_keys=True, separators=(",", ":"))
        if selector in seen_selectors:
            continue
        selected.append(deepcopy(call))
        seen_selectors.add(selector)
        if len(selected) == 4:
            break
    if len(selected) != 4:
        raise ValueError(
            f"expected four material live-state calls for {category}, got {len(selected)}"
        )
    return selected


def _leading_source_reads(
    task: dict[str, Any], tools_by_name: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the authored causal reads before the task's first state change."""

    reads: list[dict[str, Any]] = []
    for call in task.get("expected_calls", []):
        tool = tools_by_name.get(str(call.get("tool")), {})
        if tool.get("write_tables"):
            break
        reads.append(deepcopy(call))
    return reads


def _coordination_context_calls(
    row: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    conversation = {
        "tool": "list_messages",
        "args": {"channel": contract["channel"], "limit": 50},
    }
    scale_record = {
        "tool": "pd_list_change_events",
        "args": {
            "pd_service_id": contract["pd_service_id"],
            "since_day": EVIDENCE_WINDOW_START,
        },
    }
    if row["category"] in {
        "aiops_analysis",
        "aiops_detection",
        "aiops_localization",
        "attribution",
        "judgement",
    }:
        return [
            conversation,
            scale_record,
            {"tool": "get_status_page", "args": {"limit": 20}},
        ]
    if row["category"] in DELIVERY_CATEGORIES:
        return [
            conversation,
            {"tool": "list_approval_policy", "args": {}},
            scale_record,
        ]
    if row["category"] == "handover":
        return [
            conversation,
            {"tool": "get_status_page", "args": {"limit": 20}},
            scale_record,
        ]
    if row["category"] == "workspace":
        return [
            conversation,
            {"tool": "jira_search", "args": {"project": "ENG"}},
            scale_record,
        ]
    if row["category"] in ENGINEERING_CATEGORIES:
        return [
            conversation,
            {"tool": "list_ci_runs", "args": {"service": contract["service"]}},
            scale_record,
        ]
    return [
        conversation,
        {"tool": "linear_list_issues", "args": {}},
        scale_record,
    ]


def _supplemental_context_calls(
    row: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    service = contract["service"]
    if row["category"] in READ_ONLY_CATEGORIES - {"reconciliation"}:
        return [
            {"tool": "list_alerts", "args": {"service": service}},
            {"tool": "query_metrics", "args": {"service": service}},
            {"tool": "k8s_deployments_list", "args": {"service": service}},
            {"tool": "sentry_search_issues", "args": {"status": "unresolved"}},
            {"tool": "list_deployments", "args": {"service": service}},
        ]
    if row["category"] in DELIVERY_CATEGORIES:
        return [
            {"tool": "list_pull_requests", "args": {"service": service}},
            {"tool": "list_ci_runs", "args": {"service": service}},
            {"tool": "list_deployments", "args": {"service": service}},
            {"tool": "list_migrations", "args": {"service": service}},
            {"tool": "get_slo_status", "args": {"service": service}},
        ]
    if row["category"] in ENGINEERING_CATEGORIES:
        return [
            {"tool": "list_files", "args": {"service": service}},
            {"tool": "list_tests", "args": {"service": service}},
            {"tool": "list_packages", "args": {"service": service}},
            {"tool": "list_api_endpoints", "args": {"service": service}},
            {"tool": "list_approval_policy", "args": {}},
        ]
    return [
        {"tool": "github_list_issues", "args": {"state": "open"}},
        {"tool": "linear_list_issues", "args": {}},
        {"tool": "jira_search", "args": {"project": "ENG"}},
        {"tool": "list_tickets", "args": {}},
        {"tool": "read_owner_spreadsheet", "args": {}},
    ]


def material_context_calls(
    row: dict[str, Any],
    contract: dict[str, Any],
    task: dict[str, Any] | None = None,
    tools_by_name: dict[str, dict[str, Any]] | None = None,
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
        "ownership_and_conversation": _coordination_context_calls(row, contract),
        "live_state": _material_route_calls(
            row, task, contract, tools_by_name
        ),
        "capacity_plan": decision.capacity_context_calls(contract),
    }
    # A source can play two conceptual roles, but one identical query is still
    # one fact.  Preserve all four decision-controlling live reads, remove any
    # duplicate coordination selector, and replace it with another relevant
    # authored/profile read instead of counting the same call twice.
    ownership: dict[str, str] = {}
    for group_name in (
        "identity",
        "authority",
        "capacity_plan",
        "live_state",
        "ownership_and_conversation",
    ):
        for call in groups[group_name]:
            signature = json.dumps(call, sort_keys=True, separators=(",", ":"))
            ownership.setdefault(signature, group_name)
    for group_name, values in list(groups.items()):
        groups[group_name] = [
            deepcopy(call)
            for call in values
            if ownership[
                json.dumps(call, sort_keys=True, separators=(",", ":"))
            ]
            == group_name
        ]

    calls = [deepcopy(call) for values in groups.values() for call in values]
    missing = MATERIAL_CONTEXT_CALLS - len(calls)
    if missing > 0:
        candidates = [
            # These cross-functional registers are populated for every world
            # and resolve ownership, service identity, active escalation, and
            # mutation authority.  They are reliable evidence; an empty alert
            # or deployment query is not promoted merely to increase a count.
            {"tool": "read_owner_spreadsheet", "args": {}},
            {"tool": "pd_list_services", "args": {}},
            {"tool": "pd_list_oncalls", "args": {}},
            {"tool": "list_approval_policy", "args": {}},
            {"tool": "sentry_list_projects", "args": {}},
            {"tool": "list_tickets", "args": {}},
            {"tool": "jira_search", "args": {"project": "DOB"}},
            {"tool": "github_list_issues", "args": {"state": "open"}},
            *_causal_live_state_calls(row, task, contract, tools_by_name),
            *_leading_source_reads(task or {}, tools_by_name or {}),
            *_supplemental_context_calls(row, contract),
            *_route_calls(row["category"], contract["service"]),
        ]
        seen = {
            json.dumps(call, sort_keys=True, separators=(",", ":"))
            for call in calls
        }
        corroborating: list[dict[str, Any]] = []
        for call in candidates:
            tool = (tools_by_name or {}).get(str(call.get("tool")), {})
            if tool.get("write_tables"):
                continue
            signature = json.dumps(call, sort_keys=True, separators=(",", ":"))
            if signature in seen:
                continue
            seen.add(signature)
            corroborating.append(deepcopy(call))
            if len(corroborating) == missing:
                break
        if len(corroborating) != missing:
            raise ValueError(
                f"{row['bench_id']} cannot replace {missing} duplicate material reads"
            )
        groups["corroborating_context"] = corroborating
        calls.extend(corroborating)
    if len(calls) != MATERIAL_CONTEXT_CALLS:
        raise ValueError(
            f"{row['bench_id']} has {len(calls)} material context calls, "
            f"expected {MATERIAL_CONTEXT_CALLS}"
        )
    signatures = {
        json.dumps(call, sort_keys=True, separators=(",", ":")) for call in calls
    }
    if len(signatures) != MATERIAL_CONTEXT_CALLS:
        raise ValueError(f"{row['bench_id']} still has duplicate material reads")
    return calls, groups


def context_calls(
    row: dict[str, Any],
    contract: dict[str, Any],
    task: dict[str, Any] | None = None,
    tools_by_name: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    material, _material_groups = material_context_calls(
        row, contract, task, tools_by_name
    )
    source_reads = _leading_source_reads(task or {}, tools_by_name or {})
    groups = [
        material,
        [{"tool": "jira_search", "args": {"project": "DOB"}}],
        _causal_live_state_calls(row, task, contract, tools_by_name) if task else [],
        source_reads,
    ]
    calls = [call for group in groups for call in group]
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for call in calls:
        key = json.dumps(call, sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            deduped.append(deepcopy(call))
    # The causal subset above is what the deterministic verifier requires.  A
    # real investigation also needs enough independent corroboration to avoid
    # treating one dashboard or ticket as the whole system.  Fill the released
    # reference route from valid, task-scoped provider reads; never pad it with
    # duplicate selectors or mutations.
    if len(deduped) < MINIMUM_REFERENCE_CONTEXT_CALLS:
        candidates = [
            *_route_calls(row["category"], contract["service"]),
            *_supplemental_context_calls(row, contract),
            *_coordination_context_calls(row, contract),
            *decision.capacity_context_calls(contract),
        ]
        for call in candidates:
            tool = (tools_by_name or {}).get(str(call.get("tool")), {})
            if tool.get("write_tables"):
                continue
            key = json.dumps(call, sort_keys=True, separators=(",", ":"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(deepcopy(call))
            if len(deduped) == MINIMUM_REFERENCE_CONTEXT_CALLS:
                break
    if len(deduped) < MINIMUM_REFERENCE_CONTEXT_CALLS:
        raise ValueError(
            f"{row['bench_id']} has only {len(deduped)} contextual reads; "
            f"expected at least {MINIMUM_REFERENCE_CONTEXT_CALLS}"
        )
    return deduped


def _readback_for(
    tool: str, args: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any] | None:
    """The provider read that proves one source write persisted."""

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
        return {
            "tool": "list_messages",
            "args": {"channel": args["channel"], "limit": 50},
        }
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
    """Return each source write with the read that reopens its provider state."""

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

    return [
        deepcopy(readback)
        for _write, readback in postwrite_readback_pairs(task, contract)
    ]


def post_write_verifications(
    task: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Public contract: each source mutation is verified from provider state."""

    return [
        {
            "id": f"readback_{number:02d}",
            "milestone_id": "verification.outcome",
            "check_id": "deployment.v4_state_readbacks_complete",
            "after_tool": write["tool"],
            "any_of": [
                {"tool": readback["tool"], "arguments": deepcopy(readback["args"])}
            ],
            "description": (
                f"Reopened {readback['tool']} after {write['tool']} for "
                f"{contract['case_id']} and confirmed persisted provider state, not "
                "merely the write acknowledgement."
            ),
        }
        for number, (write, readback) in enumerate(
            postwrite_readback_pairs(task, contract), 1
        )
    ]


def allowed_write_tables(
    task: dict[str, Any], tools_by_name: dict[str, dict[str, Any]]
) -> list[str]:
    """Tables the reference may change; all other state remains contained."""

    tables: set[str] = set()
    for call in task["expected_calls"]:
        tables.update(tools_by_name.get(call["tool"], {}).get("write_tables") or [])
    tables.update(tools_by_name.get("submit_answer", {}).get("write_tables") or [])
    tables.update(tools_by_name.get("post_message", {}).get("write_tables") or [])
    return sorted(tables)


INVESTIGATION_GROUPS = {
    "identity": ("investigation.scope", "correctness.v4_case_identity_resolved"),
    "authority": (
        "investigation.authority",
        "correctness.v4_authority_reconciled",
    ),
    "ownership_and_conversation": (
        "analysis.causal_reasoning",
        "correctness.v4_material_evidence_complete",
    ),
    "live_state": (
        "investigation.live_state",
        "correctness.v4_live_state_correlated",
    ),
    "corroborating_context": (
        "analysis.causal_reasoning",
        "correctness.v4_material_evidence_complete",
    ),
    "capacity_plan": (
        "analysis.capacity_plan",
        "correctness.v5_capacity_evidence_complete",
    ),
}


def required_investigations(
    row: dict[str, Any], contract: dict[str, Any], trace_contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Public contract for every graded pre-mutation evidence read."""

    plan = contract["plan"]
    service = contract["service"]
    descriptions = {
        ("jira_get_issue", contract["case_id"]): f"Located {contract['case_id']} by immutable Jira key rather than title similarity.",
        ("list_issue_links", None): f"Bound {contract['case_id']} to its linked GitHub record through the cross-tracker registry.",
        ("github_list_issues", None): f"Located GitHub issue #{contract['github_issue']} in {contract['repo']} by immutable number.",
        ("confluence_search", None): f"Located current, retired, and readiness controls for {contract['case_id']} by page identity.",
        ("confluence_get_page", contract["current_page"]): f"Applied {CURRENT_CONTROL} and its {service} change windows: {', '.join(plan['window_dates'])}.",
        ("confluence_get_page", contract["retired_page"]): f"Recognized {RETIRED_CONTROL} as historical evidence, not current authority.",
        ("confluence_get_page", contract["readiness_page"]): f"Established the requirement of {plan['per_zone']} healthy replicas in each production zone.",
        ("jira_get_issue", contract["vendor_ticket"]): f"Read {decision.VENDOR} order {contract['vendor_ticket']}, including both confirmed delivery dates and expedite cost.",
        ("jira_get_issue", contract["approval_ticket"]): f"Applied approval {contract['approval_ticket']} only to its documented capacity scope.",
        ("linear_list_issues", None): f"Excluded {plan['reserved']} replicas reserved for the {plan['neighbor']} freeze.",
        ("list_status_page_posts", None): f"Preserved {plan['cutover_date']} as the independent customer need date.",
        ("list_messages", None): f"Separated the case-room business request from formal operational authority for {service}.",
        ("read_owner_spreadsheet", None): f"Confirmed the accountable {service} owner and scoped case channel.",
        ("pd_list_change_events", None): f"Read the live pool record: {plan['observed']} replicas across {plan['zones']} zones.",
    }
    investigations: list[dict[str, Any]] = []
    number = 0
    for group, calls in trace_contract["material_context_groups"].items():
        milestone_id, check_id = INVESTIGATION_GROUPS[group]
        for call in calls:
            number += 1
            args = call.get("args") or {}
            key = (call["tool"], args.get("key") or args.get("page_id"))
            description = descriptions.get(key) or descriptions.get(
                (call["tool"], None)
            ) or (
                f"Correlated the live {service} {call['tool']} record that controls "
                f"the {row['category']} decision."
            )
            investigations.append(
                {
                    "id": f"investigation_{number:02d}",
                    "milestone_id": milestone_id,
                    "check_id": check_id,
                    "group": group,
                    "before_primary_mutation": True,
                    "any_of": [
                        {"tool": call["tool"], "arguments": deepcopy(args)}
                    ],
                    "description": description,
                }
            )
    return investigations


def reference_calls(
    row: dict[str, Any],
    task: dict[str, Any],
    contract: dict[str, Any],
    tools_by_name: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reads = context_calls(row, contract, task, tools_by_name)
    material_reads, material_groups = material_context_calls(
        row, contract, task, tools_by_name
    )
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
    authored_source = deepcopy(task["expected_calls"])
    leading_reads = _leading_source_reads(task, tools_by_name)
    source = authored_source[len(leading_reads) :]
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
    reasoning_primitive = business_reasoning_primitive(row, contract, task)
    causal_profile = _causal_live_state_calls(
        row, task, contract, tools_by_name
    )
    business_reasoning = [
        f"employee_outcome:{row['category']}:{reasoning_primitive}",
        "authority:current_control_over_retired_shortcut",
        f"investigation:correlate_{reasoning_primitive}_across_live_sources",
        f"alternatives:{reasoning_primitive}:supported_vs_hold_vs_broad_action",
        (
            "capacity:required_minus_reserved_usable_capacity_then_vendor_"
            "delivery_to_change_window"
        ),
        f"capacity_options:{contract['plan']['recommended_option']}:date_cost_authority",
        *[f"state:{_slug(tool)}" for tool in mutation_tools],
        "verification:reopen_each_persisted_change",
        "handoff:source_backed_operating_result",
    ]
    graph = [
        "intake_employee_outcome",
        "resolve_cross_tracker_identity",
        "select_effective_control_over_retired_authority",
        f"correlate_{row['category']}_{reasoning_primitive}_signals",
        f"test_{reasoning_primitive}_competing_hypotheses",
        f"derive_{reasoning_primitive}_supported_branch",
        *[f"execute_{_slug(tool)}" for tool in mutation_tools],
        (
            f"plan_{_slug(contract['service'])}_cutover_capacity_"
            f"{_slug(contract['plan']['recommended_option'])}"
        ),
        f"reconcile_{reasoning_primitive}_post_change_state",
        "handoff_source_backed_result_to_owner",
        "reopen_persisted_state_and_conversation",
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
        "source_execution_calls": source,
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
        "business_reasoning_primitives": business_reasoning,
        "semantic_action_graph": graph,
        "causal_evidence_profile": causal_profile,
        "identifier_or_group_permutation_used": False,
        "business_scope": contract.get("business_scope", contract["service"]),
        "providers": sorted(
            {PROVIDER_MAPPINGS[call["tool"]] for call in reads if call["tool"] in PROVIDER_MAPPINGS}
        ),
    }
    return [
        *reads,
        *source,
        decision_record,
        *postwrite_reads,
        handoff,
        readback,
    ], trace_contract


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
    reference_handoff = trace_contract["handoff_call"]
    handoff = {
        "tool": reference_handoff["tool"],
        "args": dict(trace_contract["handoff_contract"]["args"]),
    }
    readback = trace_contract["readback_call"]
    block = f'''

# DevOpsBench v3.2 causal-evidence and state-transition contract for {row["bench_id"]}.
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
   "complete all {MATERIAL_CONTEXT_CALLS} materially causal evidence joins inside the larger reference investigation before changing state")
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
   len(_v4_handoff_positions) == 1,
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
    task: dict[str, Any],
    row: dict[str, Any],
    contract: dict[str, Any],
    trace_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    options = decision.decision_options(row, contract)
    if len(options) != 3 or sum(bool(option["selected"]) for option in options) != 1:
        raise ValueError(
            f"{row['bench_id']} must publish three costed options with one recommendation"
        )
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


EVIDENCE_SURFACE_LABELS = {
    "jira_get_issue": "the authoritative Jira work item",
    "jira_search": "the current Jira population",
    "list_issue_links": "the cross-tracker link registry",
    "github_list_issues": "the linked GitHub issue population",
    "confluence_search": "the operating-control index",
    "confluence_get_page": "the exact control revision",
    "list_messages": "the case-room conversation",
    "list_approval_policy": "the operative approval policy",
    "pd_list_change_events": "the PagerDuty change-event history",
    "get_ticket": "the employee work item",
    "ws_list": "the workspace inventory",
    "ws_read": "the current workspace file",
    "resolve_service_alias": "the service-alias registry",
    "pd_list_services": "the PagerDuty service catalog",
    "pd_list_oncalls": "the active on-call schedule",
    "list_status_page_posts": "customer-status history",
    "list_alert_rules": "alert definitions",
    "list_alert_firings": "actual alert firings",
    "k8s_pods_list": "live Kubernetes pod state",
    "k8s_events_list": "cluster event history",
    "get_runtime_stats": "runtime resource and process state",
    "get_service": "the authoritative service registry",
    "list_pull_requests": "current code-review state",
    "list_ci_runs": "continuous-integration history",
    "list_deployments": "the deployment ledger",
    "list_migrations": "production schema state",
    "get_traffic_stats": "live traffic allocation",
    "get_slo_status": "current service-objective measurements",
    "list_feature_flags": "live feature exposure",
    "list_approval_policy": "the operative approval policy",
    "list_files": "the deployed repository surface",
    "list_commits": "change history",
    "list_tests": "the executable test contract",
    "list_packages": "the resolved dependency inventory",
    "list_api_endpoints": "the served API surface",
    "linear_list_issues": "the linked planning tracker",
    "pd_list_incidents": "incident history",
    "list_tickets": "the current work-item population",
    "search_docs": "the current operating standard",
    "check_network_path": "the live dependency path",
    "search_docs": "the current operating standard",
    "search_logs": "current service logs",
    "query_metrics": "current service measurements",
    "get_status_page": "the current customer-status record",
    "list_error_events": "the current error-event population",
    "list_infra": "the infrastructure inventory",
    "read_owner_spreadsheet": "the current owner register",
    "list_authored_docs": "the shared knowledge-base page",
    "get_document": "the exact operating document",
    "k8s_deployments_list": "live Kubernetes deployment state",
    "k8s_nodes_list": "live Kubernetes node health",
    "list_alert_silences": "active alarm suppressions",
    "list_alerts": "the current alarm state",
    "list_db_grants": "the live database grants",
    "list_incidents": "the current incident record",
    "list_remediation_proposals": "the proposed remediation set",
    "list_vulnerabilities": "the current vulnerability inventory",
    "query_local_deploy_log": "the node-local deployment ledger",
    "query_prometheus": "the raw time-series samples",
    "read_exercise": "the repository's behavioral specification",
    "read_file": "the current source file",
    "search_code": "the relevant source-code paths",
    "sentry_list_projects": "the error-tracker project registry",
    "sentry_search_issues": "the current error groups",
}

PUBLIC_SOURCE_LABELS = {
    "alert_firings": "raw alarm firings",
    "alert_silences": "alarm silence and inhibition records",
    "github_issues": "GitHub issues",
    "jira_issues": "Jira issues",
    "linear_issues": "Linear issues",
    "local_deploy_log": "the node-local deployment ledger",
    "owner_spreadsheet": "the owner register",
    "pd_incidents": "PagerDuty incidents",
    "pd_oncall": "the active PagerDuty schedule",
    "pd_services": "the PagerDuty service registry",
    "prom_series": "raw Prometheus time-series samples",
    "remediation_proposals": "the remediation proposals",
    "repo_state": "the current repository state",
    "status_page_posts": "published customer-status posts",
}


def _call_business_label(call: dict[str, Any]) -> str:
    label = EVIDENCE_SURFACE_LABELS.get(
        str(call.get("tool")), str(call.get("tool", "record")).replace("_", " ")
    )
    args = call.get("args") or {}
    qualifiers: list[str] = []
    if args.get("service"):
        qualifiers.append(str(args["service"]))
    if args.get("from_service"):
        qualifiers.append(f"from {args['from_service']}")
    query = str(args.get("query") or "")
    if query and not re.fullmatch(r"[A-Z][A-Z0-9_-]*-\d+", query):
        qualifiers.append(f"for {query}")
    if args.get("environment"):
        qualifiers.append(str(args["environment"]))
    if args.get("path"):
        qualifiers.append(str(args["path"]))
    return f"{label} ({', '.join(qualifiers)})" if qualifiers else label


def _join_labels(labels: list[str]) -> str:
    unique = list(dict.fromkeys(label for label in labels if label))
    if not unique:
        return "the authoritative records"
    if len(unique) == 1:
        return unique[0]
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    return ", ".join(unique[:-1]) + f", and {unique[-1]}"


def _evidence_story(trace_contract: dict[str, Any]) -> str:
    calls = trace_contract["material_context_groups"]["live_state"]
    return _join_labels([_call_business_label(call) for call in calls])


def _causal_join_story(trace_contract: dict[str, Any]) -> str:
    """Describe why each evidence group is needed, not merely its read count."""

    groups = trace_contract["material_context_groups"]
    identity = _join_labels([_call_business_label(call) for call in groups["identity"]])
    authority = _join_labels([_call_business_label(call) for call in groups["authority"]])
    ownership = _join_labels(
        [_call_business_label(call) for call in groups["ownership_and_conversation"]]
    )
    live = _join_labels([_call_business_label(call) for call in groups["live_state"]])
    return (
        f"first resolve the same work across {identity}; then use {authority} to select the "
        f"effective rule over the retired shortcut; reconcile ownership, approval, and reported "
        f"context through {ownership}; finally test the competing explanation against {live}"
    )


def _readback_story(trace_contract: dict[str, Any]) -> str:
    return _join_labels(
        [
            _call_business_label(call)
            for call in trace_contract.get("postwrite_readback_calls", [])
        ]
    )


def _transition_business_label(call: dict[str, Any]) -> str:
    tool = str(call.get("tool"))
    args = call.get("args") or {}
    service = str(args.get("service") or "the affected service")
    if tool == "submit_diagnosis":
        if not args.get("fault_detected", True) or str(args.get("fault_type")) == "none":
            scope = str(args.get("scope") or service)
            return (
                f"record the evidence-backed finding that {scope} is healthy, has no active "
                "objective breach, and has no supported fault owner or offending setting"
            )
        fault_type = str(args.get("fault_type") or "supported cause").replace("_", " ")
        if fault_type == "misconfig":
            fault_type = "configuration error"
        return (
            f"record a {fault_type} diagnosis localizing responsibility "
            f"to {args.get('service', 'the supported component')} and identifying "
            f"{args.get('offending_key', 'the operative cause')} with cited evidence"
        )
    if tool == "submit_answer":
        sources = _join_labels(
            [
                PUBLIC_SOURCE_LABELS.get(str(source), str(source).replace("_", " "))
                for source in (args.get("sources") or [])
            ]
        )
        return f"record the supported answer {args.get('answer')} from {sources}, with assumptions"
    if tool == "update_ticket":
        return f"move the employee work item to {args.get('status', 'its supported final status')}"
    if tool == "open_pull_request":
        return f"propose the scoped {service} change “{args.get('title', 'operational repair')}”"
    if tool == "merge_pull_request":
        return "merge only the validated, linked code change"
    if tool == "run_ci":
        return "complete the required code validation"
    if tool == "deploy_service":
        environment = args.get("environment", "the required environment")
        exposure = (
            f" at {args['canary_percent']}% canary exposure"
            if args.get("canary_percent") is not None
            else ""
        )
        return f"deploy {service} to {environment}{exposure}"
    if tool == "assess_canary":
        return f"assess the {service} canary against live health"
    if tool == "promote_canary":
        return f"promote the healthy {service} canary"
    if tool == "apply_migration":
        migration = args.get("migration_id") or args.get("migration") or "required migration"
        return f"apply {migration} for {service} in {args.get('environment', 'production')}"
    if tool == "set_feature_flag":
        flag = args.get("flag") or args.get("name") or "the scoped flag"
        value = args.get("percentage", args.get("percent", args.get("enabled", "the supported exposure")))
        return f"set {flag} for {service} to {value}"
    if tool == "acknowledge_alert":
        return "acknowledge the scoped firing alert"
    if tool == "resolve_alert":
        return "resolve the recovered alert only after verification"
    if tool == "update_incident":
        return f"move the incident to {args.get('status', 'its supported state')}"
    if tool == "publish_status_update":
        return "publish the verified customer-status update"
    if tool == "rollback_deployment":
        return f"roll back {service} to the supported production version"
    if tool == "shift_endpoint_traffic":
        endpoint = args.get("path") or args.get("endpoint") or "the scoped endpoint"
        return f"move {endpoint} traffic to the supported contract without dropping requests"
    if tool == "create_ticket":
        return "create each business-rule-matched tracker record and no others"
    if tool == "post_message":
        return f"publish the scoped result to {args.get('channel', 'the requesting team')}"
    if tool == "jira_transition_issue":
        return f"transition the matched Jira record to {args.get('status', 'its supported state')}"
    if tool == "write_runbook":
        return f"publish the evidence-backed runbook “{args.get('title', 'on-call guidance')}”"
    if tool == "write_implementation":
        return f"implement the documented behavior in {args.get('path', 'the scoped component')}"
    if tool == "run_exercise_tests":
        return "prove the implementation against its executable contract"
    if tool == "request_approval":
        return "obtain the required human approval before the irreversible transition"
    if tool == "resolve_error_event":
        return "resolve the error event after the production cause is removed"
    if tool in {"ws_write", "ws_python"}:
        return "repair and validate the scoped workspace artifact"
    return str(tool).replace("_", " ")


def _transition_story(trace_contract: dict[str, Any]) -> str:
    labels: list[str] = []
    for call in trace_contract["source_mutation_calls"]:
        label = _transition_business_label(call)
        if label not in labels:
            labels.append(label)
    if len(labels) > 5:
        return "; ".join(labels[:5]) + f"; and {len(labels) - 5} dependent guarded transitions"
    return "; ".join(labels)


def _check_requirement(check: dict[str, str]) -> str:
    replacements = {
        "no_new_hardcoded_secrets": "introduce no hardcoded credentials",
        "no_unproductive_ci_loops": "avoid repeated validation runs that make no progress",
        "scoped_change_no_fabricated_data": "fabricate no records or evidence",
        "world_invariants_intact": "preserve every frozen out-of-scope record",
    }
    description = replacements.get(check["name"], check["description"].rstrip("."))
    public_terms = {
        "run_ci": "complete validation",
        "update_ticket": "update the work item",
        "deploy_service": "deploy the service",
        "open_pull_request": "open the linked code review",
        "merge_pull_request": "merge the validated code review",
        "submit_diagnosis": "record the diagnosis",
        "assess_canary": "assess the canary",
        "promote_canary": "promote the healthy canary",
        "create_ticket": "create the matched work item",
        "submit_answer": "record the supported answer",
        "acknowledge_alert": "acknowledge the alert",
        "post_message": "publish the scoped message",
        "jira_transition_issue": "transition the linked Jira issue",
        "resolve_alert": "resolve the recovered alert",
        "apply_migration": "apply the required schema migration",
        "set_feature_flag": "set the approved feature exposure",
        "write_implementation": "write the scoped implementation",
        "run_exercise_tests": "run the executable contract checks",
        "shift_endpoint_traffic": "shift the scoped endpoint traffic",
        "update_incident": "update the incident",
        "publish_status_update": "publish the customer-status update",
        "rollback_deployment": "roll back the affected deployment",
        "write_runbook": "publish the on-call runbook",
        "ws_python": "run the scoped workspace validation",
        "request_approval": "obtain the required human approval",
        "resolve_error_event": "resolve the recovered error event",
        "ws_write": "write the scoped workspace repair",
    }
    for internal, public in public_terms.items():
        description = re.sub(rf"\b{re.escape(internal)}\b", public, description)
    description = description.replace("(merged AND deployed)", "(merged and deployed)")
    description = re.sub(
        r"submit a detection result for scope '([^']+)'",
        lambda match: (
            f"record whether {match.group(1)} has an active objective breach"
        ),
        description,
    )
    description = re.sub(
        r"submit a localization result for scope '([^']+)'",
        lambda match: (
            f"record the component and mechanism responsible for alarm {match.group(1)}"
        ),
        description,
    )
    description = re.sub(
        r"submit a root-cause result for scope '([^']+)'",
        lambda match: (
            "record the evidence-backed root cause for "
            + match.group(1).replace("-", " ")
        ),
        description,
    )
    description = re.sub(
        r"submit an answer for question_id '[^']+'",
        "record the supported answer to the employee's question",
        description,
    )
    description = re.sub(
        r"submit a proposal_id for '[^']+'",
        "record the supported remediation proposal and its rationale",
        description,
    )
    description = description.replace(
        "fault_detected must be true", "the final finding must record an active fault"
    ).replace(
        "fault_detected must be false", "the final finding must record no active fault"
    ).replace(
        "a firing alarm means the final finding must record an active fault",
        "a currently firing alarm must be treated as an active fault",
    )
    for internal, public in PUBLIC_SOURCE_LABELS.items():
        description = re.sub(rf"\b{re.escape(internal)}\b", public, description)
    return description


def _check_story(
    checks: list[dict[str, str]], *, exclude_v4: bool = True, limit: int = 4
) -> str:
    selected = [
        _check_requirement(check)
        for check in checks
        if not (exclude_v4 and check["name"].startswith("v4_"))
    ]
    if not selected:
        return ""
    if len(selected) > limit:
        return "; ".join(selected[:limit]) + f"; plus {len(selected) - limit} related invariants"
    return "; ".join(selected)


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

    # Public rubric language is reconstructed from the employee-visible
    # outcome, material evidence, exact business-state assertions, and guarded
    # transitions.  Internal case IDs and raw tool names never establish task
    # specificity.
    outcome = employee_title({"instruction": task.get("instruction", "")})
    material = trace_contract["material_context_call_count"]
    reference = trace_contract["reference_context_call_count"]
    evidence_story = _evidence_story(trace_contract)
    transition_story = _transition_story(trace_contract)
    analysis_story = _check_story(grouped["analysis.causal_reasoning"], limit=20)
    primary_story = _check_story(grouped["state.primary"], limit=20)
    coordination_story = _check_story(grouped["state.coordination"], limit=20)
    verification_story = _check_story(grouped["verification.outcome"], limit=20)
    sequence_story = _check_story(grouped["execution.sequence"], limit=20)
    containment_story = _check_story(grouped["containment.scope"], limit=20)
    answer_story = _check_story(grouped["answer.insights"], limit=20)
    efficiency_story = _check_story(grouped["execution.efficiency"], limit=20)
    delivery_story = _check_story(grouped["execution.delivery"], limit=20)
    behavior_story = AUTHORED_BEHAVIOR_OUTCOMES.get(str(row.get("task_id")), "")
    plan = contract["plan"]

    def combine_stories(*stories: str) -> str:
        return "; ".join(dict.fromkeys(story for story in stories if story))

    # A business state is more than the outer record that contains it.  Fold
    # in answer checks only when they literally define the persisted artifact;
    # decision rationale and employee reporting remain in their own milestone.
    state_extension_checks = [
        check
        for check in grouped["answer.insights"]
        if check["name"].startswith("states_")
        or check["name"]
        in {
            "root_cause_written_down",
            "outcome_recorded",
            "every_match_reported",
        }
    ]
    state_extension_story = _check_story(state_extension_checks, limit=20)
    state_story = combine_stories(
        primary_story or transition_story,
        behavior_story,
        state_extension_story,
    )
    causal_story = _causal_join_story(trace_contract)
    readback_story = _readback_story(trace_contract)
    observable_story = combine_stories(
        verification_story,
        f"reopen {readback_story} and confirm the persisted result",
    )
    descriptions = {
        "investigation.scope": (
            f"Treat “{outcome}” as one immutable cross-system work item: correlate its Jira record "
            "to the linked GitHub evidence and exclude neighboring work that merely shares a name."
        ),
        "investigation.authority": (
            f"Use {CURRENT_CONTROL} as the operative control and treat {RETIRED_CONTROL} as a "
            f"conflicting historical shortcut before deciding “{outcome}”."
        ),
        "investigation.live_state": (
            f"For “{outcome}”, interrogate {evidence_story}; tracker prose and seeded files alone "
            "cannot establish the current answer."
        ),
        "analysis.causal_reasoning": (
            f"Build the causal case for “{outcome}”: {causal_story}. "
            f"All {material} exact causal facts must be present inside the {reference}-read "
            f"investigation before they support this outcome: {state_story}."
            + (f" Preserve this additional control: {analysis_story}." if analysis_story else "")
        ),
        "analysis.capacity_plan": (
            f"For “{outcome}”, derive the separate cutover-readiness answer from scattered "
            f"records: {plan['per_zone']} healthy replicas per zone across {plan['zones']} "
            f"zones means {plan['required']} required; {plan['observed']} observed less "
            f"{plan['reserved']} reserved for {plan['neighbor']} leaves {plan['usable']} usable "
            f"and a {plan['gap']}-replica gap. Reconcile that gap with {decision.VENDOR}'s "
            f"{decision.iso(plan['standard_days'])} standard and "
            f"{decision.iso(plan['expedited_days'])} expedited deliveries, the published "
            f"change windows, and the independent {plan['cutover_date']} customer date."
        ),
        "decision.supported_path": (
            f"Choose the branch for “{outcome}” that can legitimately produce this business state: "
            f"{state_story}. Reject a stale-record shortcut, an unsupported hold, and any broader workaround."
        ),
        "decision.options": (
            f"Compare three concrete readiness options for “{outcome}”: standard capacity "
            f"finishes {decision.iso(plan['standard_completion'])} at USD 0; expedited "
            f"capacity finishes {decision.iso(plan['expedited_completion'])} at USD "
            f"{plan['expedite_fee']}; releasing reserved capacity finishes "
            f"{decision.iso(plan['release_completion'])} at USD {plan['release_fee']} but "
            f"requires approval beyond {contract['approval_ticket']}. Recommend "
            f"{plan['recommended_option']}, record its {decision.iso(plan['recommended_completion'])} "
            f"outcome and {plan['variance']:+d}-day variance, and report {plan['status']} honestly."
        ),
        "state.primary": f"Establish the exact business state for “{outcome}”: {state_story}.",
        "state.coordination": (
            f"Coordinate the linked records for “{outcome}”: "
            f"{coordination_story or 'leave the work item and its supporting operational records in one consistent final state'}."
        ),
        "verification.outcome": (
            f"Prove the observable result for “{outcome}” after the transition: "
            f"{observable_story}."
        ),
        "verification.readback": (
            f"After the last guarded transition for “{outcome}”, reopen {readback_story}, then "
            "reopen the completion conversation so persistence and communication are both proven."
        ),
        "execution.sequence": (
            f"Respect the causal order for “{outcome}”: "
            f"{sequence_story or 'establish the material evidence before changing state and verify each persisted result before handoff'}."
        ),
        "containment.scope": (
            f"Keep “{outcome}” contained to its supported records and service boundary: "
            f"{containment_story or 'preserve frozen history, unrelated work, and credentials'}."
        ),
        "answer.insights": (
            f"Leave the employee-facing conclusion for “{outcome}” with the exact supported insight: "
            f"{answer_story or state_story}."
        ),
        "execution.efficiency": (
            f"Complete “{outcome}” without unsafe retries or unproductive loops: "
            f"{efficiency_story or 'recover from exploratory read mistakes, but allow no rejected mutation'}."
        ),
        "execution.delivery": (
            f"Close “{outcome}” only after the business state and readbacks are complete: "
            f"{delivery_story or 'post one scoped handoff, reopen it, and only then close the employee work item'}."
        ),
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
        for wrapped in textwrap.wrap(
            line, width=100, break_long_words=False, break_on_hyphens=False
        )
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


def _has_substantive_evidence(value: Any) -> bool:
    """True when a read returned an inspectable fact rather than an empty ack."""

    if value is None:
        return False
    if isinstance(value, (str, bytes, list, tuple, set)):
        return len(value) > 0
    if isinstance(value, dict):
        if value.get("ok") is False or value.get("error"):
            return False
        substantive = [
            item
            for key, item in value.items()
            if key not in {"ok", "case_id", "service", "status"}
        ]
        return bool(substantive) and any(
            _has_substantive_evidence(item) for item in substantive
        )
    # Explicit scalar values, including zero and false, are inspectable facts.
    return True


def _execute_evidence_calls(
    database: Path,
    calls: list[dict[str, Any]],
    *,
    bench_id: str,
) -> dict[str, Any]:
    """Execute read contracts on a disposable database and reject silent gaps."""

    module_path = database.parent / "tools_combined.py"
    spec = importlib.util.spec_from_file_location(
        f"_devopsbench_evidence_{_slug(bench_id)}", module_path
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load sandbox tools for {bench_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    unique: dict[str, dict[str, Any]] = {}
    for call in calls:
        signature = json.dumps(call, sort_keys=True, separators=(",", ":"))
        unique.setdefault(signature, call)

    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="devopsbench-evidence-") as temp_dir:
        disposable = Path(temp_dir) / "environment.db"
        shutil.copy2(database, disposable)
        for signature, call in unique.items():
            tool_name = str(call["tool"])
            function = getattr(module, tool_name, None)
            if function is None:
                raise ValueError(f"{bench_id} has no sandbox read named {tool_name}")
            arguments = deepcopy(call.get("args") or {})
            arguments["db_path"] = str(disposable)
            try:
                result = function(**arguments)
            except Exception as error:
                raise ValueError(
                    f"{bench_id} evidence read {tool_name} failed: {error}"
                ) from error
            if not _has_substantive_evidence(result):
                raise ValueError(
                    f"{bench_id} evidence read {tool_name} returned no inspectable facts"
                )
            results[signature] = result
    return results


def _material_export(
    call: dict[str, Any], result: Any, contract: dict[str, Any]
) -> str:
    tool_name = str(call["tool"])
    source = EVIDENCE_SURFACE_LABELS.get(
        tool_name,
        PROVIDER_MAPPINGS.get(tool_name, tool_name.replace("_", " ")),
    )
    return json.dumps(
        {
            "as_of_world_day": SNAPSHOT_DAY,
            "case_scope": contract["case_id"],
            "source": source,
            "query_scope": call.get("args") or {},
            "records": result,
            "note": (
                "Raw isolated-sandbox export. It contains evidence, not a "
                "precomputed conclusion or execution recipe."
            ),
        },
        indent=2,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
    ) + "\n"


def write_asset_views(
    root: Path,
    database: Path,
    prompt: str,
    row: dict[str, Any],
    contract: dict[str, Any],
    trace_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    """Write 32 contextual files, 18 executed causal exports, and a manifest."""

    root.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(database)
    cx.row_factory = sqlite3.Row
    assets: list[dict[str, Any]] = []
    required_calls = trace_contract["required_context_calls"]
    profile_calls = trace_contract["causal_evidence_profile"]
    evidence_results = _execute_evidence_calls(
        database,
        [*required_calls, *profile_calls],
        bench_id=row["bench_id"],
    )

    def add(
        name: str,
        source: str,
        content: str | bytes,
        role: str,
        *,
        material: bool = False,
        material_reason: str = "",
        query_scope: dict[str, Any] | None = None,
    ) -> None:
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
                "material": material,
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                **({"material_reason": material_reason} if material_reason else {}),
                **({"query_scope": deepcopy(query_scope)} if query_scope is not None else {}),
            }
        )

    case = dict(cx.execute("SELECT * FROM jira_issues WHERE key=?", (contract["case_id"],)).fetchone())
    github = dict(cx.execute("SELECT * FROM github_issues WHERE number=?", (contract["github_issue"],)).fetchone())
    links = [dict(r) for r in cx.execute("SELECT * FROM issue_links WHERE source=?", (contract["case_id"],))]
    pages = [dict(r) for r in cx.execute("SELECT * FROM confluence_pages WHERE page_id IN (?,?) ORDER BY stale", (contract["current_page"], contract["retired_page"]))]
    messages = [dict(r) for r in cx.execute("SELECT * FROM messages WHERE channel=? ORDER BY message_id", (contract["channel"],))]
    owner = [dict(r) for r in cx.execute("SELECT * FROM owner_spreadsheet WHERE row_id=?", (contract["owner_row"],))]
    changes = [dict(r) for r in cx.execute("SELECT * FROM pd_change_events WHERE pd_service_id=?", (contract["pd_service_id"],))]
    readiness = dict(
        cx.execute(
            "SELECT * FROM confluence_pages WHERE page_id=?",
            (contract["readiness_page"],),
        ).fetchone()
    )
    vendor_order = dict(
        cx.execute(
            "SELECT * FROM jira_issues WHERE key=?", (contract["vendor_ticket"],)
        ).fetchone()
    )
    approval = dict(
        cx.execute(
            "SELECT * FROM jira_issues WHERE key=?", (contract["approval_ticket"],)
        ).fetchone()
    )
    reservation = [
        dict(r)
        for r in cx.execute(
            "SELECT * FROM linear_issues WHERE identifier=?",
            (contract["reservation_issue"],),
        )
    ]
    cutover_post = [
        dict(r)
        for r in cx.execute(
            "SELECT * FROM status_page_posts WHERE post_id=?",
            (contract["status_post"],),
        )
    ]
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
    add("28-change-readiness-standard.pdf", "Confluence current export", _pdf(readiness["title"] + "\n" + readiness["body"]), "capacity requirement")
    add("29-vendor-capacity-order.csv", "Atlassian Jira vendor project", _csv_text([vendor_order]), "vendor lead time and cost")
    add("30-change-approval-record.csv", "Atlassian Jira change advisory", _csv_text([approval]), "approval scope")
    add("31-capacity-reservation-register.json", "Linear", json.dumps({"case_id": contract["case_id"], "issues": reservation}, indent=2, sort_keys=True) + "\n", "capacity exclusion")
    add("32-customer-cutover-notice.json", "public status page", json.dumps({"case_id": contract["case_id"], "posts": cutover_post}, indent=2, sort_keys=True) + "\n", "independent business need")
    if len(profile_calls) < 3:
        raise ValueError(
            f"{row['bench_id']} has only {len(profile_calls)} causal profile reads"
        )
    for ordinal, call in enumerate(required_calls, 1):
        signature = json.dumps(call, sort_keys=True, separators=(",", ":"))
        tool_name = str(call["tool"])
        source = EVIDENCE_SURFACE_LABELS.get(
            tool_name,
            PROVIDER_MAPPINGS.get(tool_name, tool_name.replace("_", " ")),
        )
        safe_source = _slug(source).replace("_", "-") or "source-record"
        add(
            f"material/{ordinal:02d}-{safe_source}.json",
            source,
            _material_export(call, evidence_results[signature], contract),
            "decision-controlling sandbox export",
            material=True,
            material_reason=_call_business_label(call),
            query_scope=call.get("args") or {},
        )
    manifest = [
        {
            **asset,
            "path": str(
                Path("material") / Path(asset["path"]).name
                if asset["material"]
                else Path(asset["path"]).name
            ),
        }
        for asset in assets
    ]
    add(
        "51-agent-visible-asset-manifest.json",
        "release builder",
        json.dumps(
            {
                "case_id": contract["case_id"],
                "gold_included": False,
                "oracle_sequence_included": False,
                "ordering_semantics": False,
                "listed_assets": len(manifest),
                "total_assets_including_this_manifest": len(manifest) + 1,
                "assets": manifest,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "manifest",
    )
    cx.close()
    if len(assets) != ASSET_COUNT:
        raise ValueError(
            f"expected {ASSET_COUNT} assets for {row['bench_id']}, wrote {len(assets)}"
        )
    if sum(bool(asset["material"]) for asset in assets) != MATERIAL_ASSET_COUNT:
        raise ValueError(
            f"expected {MATERIAL_ASSET_COUNT} material assets for {row['bench_id']}"
        )
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
