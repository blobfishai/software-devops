"""Graded capacity-plan decision model for DevOpsBench-100 v3.2.

Every DevOpsBench case ends in a customer-facing cutover for the case service.
Before the handoff, the on-call engineer has to settle a change-readiness plan
the way a real employee would: read the readiness standard for the required
healthy-replica count, read the live pool size and the reservation that must
stay untouched, net the two into a capacity gap, read the cloud vendor's
confirmed delivery dates, read the change calendar, and weigh three plans
(standard delivery, paid expedite, releasing the reserved capacity) against
the customer cutover date before recording the recommendation and stating it
in the handoff.

Every value in that chain is seeded into the task's isolated world across
several providers (Confluence, PagerDuty, Linear, Jira, the status page and
Slack), derived by the reference walk, submitted as the case decision record,
and graded field by field by the deterministic verifier.  The decision record,
the option table and the graded answer contract are published with the task
so the reasoning chain is inspectable as data, never as prompt prose.
"""

from __future__ import annotations

import datetime
import json
from copy import deepcopy
from typing import Any

TODAY = datetime.date(2026, 3, 3)
# DevOpsBench's source world uses an abstract monotonically increasing day
# counter.  Keep the capacity evidence on the same frozen snapshot as the
# deeper causal-evidence layer instead of silently mixing day-100 and day-420
# records in one case room.
TODAY_DAY = 420
EVIDENCE_WINDOW_START = TODAY_DAY - 90
VENDOR = "CloudCap"
QUANTITY_UNIT = "replicas"
OPTION_STANDARD = "standard_capacity_plan"
OPTION_EXPEDITE = "expedite_capacity"
OPTION_RELEASE = "release_reserved_capacity"
ANALYSIS_MILESTONE = "analysis.capacity_plan"
DECISION_MILESTONE = "decision.options"
ANSWER_FIELDS: tuple[str, ...] = (
    "business_need_date",
    "replicas_per_zone",
    "production_zones",
    "required_replicas",
    "observed_replicas",
    "reserved_replicas",
    "usable_replicas",
    "replica_gap",
    "quantity_unit",
    "standard_capacity_date",
    "expedited_capacity_date",
    "capacity_request_replicas",
    "next_change_window",
    "standard_plan_completion",
    "expedited_plan_completion",
    "reserved_release_completion",
    "recommended_option",
    "recommended_outcome_date",
    "recommended_incremental_cost_usd",
    "escalation_approval_required",
    "approval_reference",
    "outcome_vs_control_days",
    "decision_timing_status",
)
ANALYSIS_FIELDS = frozenset(
    {
        "business_need_date",
        "replicas_per_zone",
        "production_zones",
        "required_replicas",
        "observed_replicas",
        "reserved_replicas",
        "usable_replicas",
        "replica_gap",
        "quantity_unit",
        "standard_capacity_date",
        "expedited_capacity_date",
        "capacity_request_replicas",
        "next_change_window",
    }
)


def iso(days: int) -> str:
    return (TODAY + datetime.timedelta(days=days)).isoformat()


def capacity_plan(
    index: int,
    service: str,
    secondary_service: str | None,
    service_names: tuple[str, ...],
    approval_ticket: str,
) -> dict[str, Any]:
    """Deterministic, task-specific plan parameters and their derived outcomes."""

    zones = 2 + index % 3
    per_zone = 2 + (index // 3) % 3
    required = zones * per_zone
    gap = 1 + (index // 2) % 3
    reserved = gap + index % 2
    usable = required - gap
    observed = usable + reserved
    standard_days = 2 + index % 3
    expedited_days = 1
    first_window = 1 + index % 2
    window_step = 2 + (index // 4) % 2
    window_days = [first_window + step * window_step for step in range(4)]
    cutover_days = 1 + (index // 5) % 6
    expedite_fee = 600 + 150 * (index % 7)
    release_fee = 1200 + 200 * (index % 5)
    neighbor = secondary_service or service_names[(index + 3) % len(service_names)]
    if neighbor == service:
        neighbor = service_names[(index + 4) % len(service_names)]
    freeze_end_days = cutover_days + 3

    def completion(delivery_days: int) -> int:
        return min(window for window in window_days if window >= delivery_days)

    standard_completion = completion(standard_days)
    expedited_completion = completion(expedited_days)
    release_completion = 0
    candidates = [
        (OPTION_STANDARD, standard_completion, 0, standard_days),
        (OPTION_EXPEDITE, expedited_completion, expedite_fee, expedited_days),
    ]
    meeting = [candidate for candidate in candidates if candidate[1] <= cutover_days]
    if meeting:
        chosen = min(meeting, key=lambda candidate: (candidate[2], candidate[1]))
    else:
        chosen = min(candidates, key=lambda candidate: (candidate[1], candidate[2]))
    recommended, recommended_completion, recommended_cost, recommended_delivery = chosen
    variance = recommended_completion - cutover_days
    status = "ON_TIME" if variance <= 0 else "LATE"
    binding_kind = "standard" if recommended == OPTION_STANDARD else "expedited"

    def authorized_option(option: str, completion_days: int, cost: int, delivery_days: int, label: str) -> dict[str, Any]:
        is_recommended = option == recommended
        landing = completion_days - cutover_days
        if is_recommended:
            timing = (
                f"{-landing} day(s) ahead of the {iso(cutover_days)} cutover"
                if landing < 0
                else f"on the {iso(cutover_days)} cutover date"
                if landing == 0
                else f"{landing} day(s) after the {iso(cutover_days)} cutover, the earliest authorised result"
            )
            consequence = (
                f"{label} {VENDOR} delivery on {iso(delivery_days)} lands in the {iso(completion_days)} change window, "
                f"{timing}, keeps the {reserved} reserved {QUANTITY_UNIT} untouched, and carries the documented "
                f"incremental cost of USD {cost}."
            )
        elif completion_days == recommended_completion:
            consequence = (
                f"{label} delivery reaches the same {iso(completion_days)} window as {recommended} and changes the "
                f"incremental cost by USD {cost - recommended_cost:+d}; it is authorised but not the best tradeoff."
            )
        elif completion_days > recommended_completion:
            consequence = (
                f"{label} delivery only reaches the {iso(completion_days)} window, {completion_days - recommended_completion} "
                f"day(s) after {recommended}, and would land {max(landing, 0)} day(s) after the cutover; it is authorised but inferior."
            )
        else:
            consequence = (
                f"{label} delivery would reach the {iso(completion_days)} window but adds USD {cost - recommended_cost:+d} for time "
                f"the cutover does not need; it is authorised but not recommended."
            )
        return {
            "id": option,
            "label": f"{option}: outcome {iso(completion_days)}, incremental cost USD {cost}, "
            f"{'SUPPORTED_AND_APPROVED' if is_recommended else 'FEASIBLE_WITH_INFERIOR_TRADEOFF'}",
            "completion": iso(completion_days),
            "incremental_cost": cost,
            "approval": "APPROVED" if is_recommended else "AVAILABLE_NOT_RECOMMENDED",
            "control_status": "SUPPORTED_AND_APPROVED" if is_recommended else "FEASIBLE_WITH_INFERIOR_TRADEOFF",
            "consequence": consequence,
            "recommended": is_recommended,
        }

    options = [
        authorized_option(OPTION_STANDARD, standard_completion, 0, standard_days, "Standard"),
        authorized_option(OPTION_EXPEDITE, expedited_completion, expedite_fee, expedited_days, "Expedited"),
        {
            "id": OPTION_RELEASE,
            "label": f"{OPTION_RELEASE}: outcome {iso(release_completion)}, incremental cost USD {release_fee}, "
            "SEPARATE_APPROVAL_OR_POLICY_EXCEPTION_REQUIRED",
            "completion": iso(release_completion),
            "incremental_cost": release_fee,
            "approval": "ADDITIONAL_APPROVAL_REQUIRED",
            "control_status": "SEPARATE_APPROVAL_OR_POLICY_EXCEPTION_REQUIRED",
            "consequence": (
                f"Releasing the {reserved} {QUANTITY_UNIT} reserved for the {neighbor} freeze would cover the {gap}-replica gap "
                f"today, but it breaks a reservation another team depends on, needs incident-commander approval beyond "
                f"{approval_ticket}, and adds the USD {release_fee} re-provisioning charge."
            ),
            "recommended": False,
        },
    ]
    answer = {
        "business_need_date": iso(cutover_days),
        "replicas_per_zone": per_zone,
        "production_zones": zones,
        "required_replicas": required,
        "observed_replicas": observed,
        "reserved_replicas": reserved,
        "usable_replicas": usable,
        "replica_gap": gap,
        "quantity_unit": QUANTITY_UNIT,
        "standard_capacity_date": iso(standard_days),
        "expedited_capacity_date": iso(expedited_days),
        "capacity_request_replicas": gap,
        "next_change_window": iso(window_days[0]),
        "standard_plan_completion": iso(standard_completion),
        "expedited_plan_completion": iso(expedited_completion),
        "reserved_release_completion": iso(release_completion),
        "recommended_option": recommended,
        "recommended_outcome_date": iso(recommended_completion),
        "recommended_incremental_cost_usd": recommended_cost,
        "escalation_approval_required": 1,
        "approval_reference": approval_ticket,
        "outcome_vs_control_days": variance,
        "decision_timing_status": status,
    }
    if tuple(answer) != ANSWER_FIELDS:
        raise AssertionError("answer field order drifted from ANSWER_FIELDS")
    return {
        "zones": zones,
        "per_zone": per_zone,
        "required": required,
        "gap": gap,
        "reserved": reserved,
        "usable": usable,
        "observed": observed,
        "standard_days": standard_days,
        "expedited_days": expedited_days,
        "window_days": window_days,
        "window_dates": [iso(day) for day in window_days],
        "cutover_days": cutover_days,
        "cutover_date": iso(cutover_days),
        "expedite_fee": expedite_fee,
        "release_fee": release_fee,
        "neighbor": neighbor,
        "freeze_end_date": iso(freeze_end_days),
        "standard_completion": standard_completion,
        "expedited_completion": expedited_completion,
        "release_completion": release_completion,
        "recommended_option": recommended,
        "recommended_completion": recommended_completion,
        "recommended_cost": recommended_cost,
        "binding_delivery_date": iso(recommended_delivery),
        "binding_kind": binding_kind,
        "variance": variance,
        "status": status,
        "options": options,
        "answer": answer,
    }


# ------------------------------------------------------------------ evidence
def readiness_standard_body(contract: dict[str, Any]) -> str:
    plan = contract["plan"]
    fields = ", ".join(ANSWER_FIELDS)
    return (
        f"Change-readiness standard for {contract['case_id']} ({contract['service']}), effective under "
        f"{contract['control_revision']}. Before the {contract['service']} customer cutover is declared ready, the "
        f"production pool must hold {plan['per_zone']} healthy serving replicas in every production zone. The zone "
        f"count and the current pool size are the PagerDuty scale record for {contract['pd_service_id']}; replicas "
        f"reserved for another team's freeze in the Linear capacity register ({contract['reservation_issue']}) are not "
        f"usable. Any shortfall is covered only by confirmed {VENDOR} capacity (Jira order {contract['vendor_ticket']}) "
        f"and becomes effective in the next published change window on the current operating control page. Plan "
        f"selection: choose the lowest-cost authorised plan whose completion is on or before the customer cutover "
        f"date published on the status page; if no authorised plan meets it, choose the earliest authorised plan and "
        f"report the shortfall honestly as LATE. Releasing reserved capacity or working outside a change window needs "
        f"incident-commander approval beyond change approval {contract['approval_ticket']}. Record the plan as the "
        f"reconciliation answer to question {contract['capacity_question']}: a JSON object with the keys {fields}. "
        f"Dates are ISO (YYYY-MM-DD); the unit is '{QUANTITY_UNIT}'; escalation_approval_required is 1 when a listed "
        f"plan needs approval beyond the change approval; outcome_vs_control_days is completion minus cutover "
        f"(positive means late); decision_timing_status is ON_TIME or LATE."
    )


def change_window_sentence(contract: dict[str, Any]) -> str:
    plan = contract["plan"]
    return (
        f"Change windows for {contract['service']}: {', '.join(plan['window_dates'])} at 14:00Z; work outside these "
        f"windows requires incident-commander approval. Vendor capacity order {contract['vendor_ticket']} and change "
        f"approval {contract['approval_ticket']} are the authoritative records for the cutover capacity plan."
    )


def seed_capacity_evidence(cx: Any, contract: dict[str, Any]) -> None:
    """Insert the scattered source facts the decision model is derived from."""

    plan = contract["plan"]
    service = contract["service"]
    cx.execute(
        "INSERT INTO confluence_pages(page_id,space,title,body,last_updated_day,stale) VALUES (?,?,?,?,?,?)",
        (
            contract["readiness_page"],
            "OPS",
            f"{contract['case_id']} change-readiness standard for {service}",
            readiness_standard_body(contract),
            TODAY_DAY,
            0,
        ),
    )
    cx.execute(
        "INSERT INTO pd_change_events(pd_service_id,summary,day) VALUES (?,?,?)",
        (
            contract["pd_service_id"],
            f"Scaled {service} production pool to {plan['observed']} replicas across {plan['zones']} zones "
            f"({contract['case_id']} capacity baseline)",
            TODAY_DAY - 2,
        ),
    )
    cx.execute(
        "INSERT INTO linear_issues(identifier,team,title,state,priority,label,created_day) VALUES (?,?,?,?,?,?,?)",
        (
            contract["reservation_issue"],
            f"team-{service}",
            f"{plan['reserved']} {service} replicas reserved for the {plan['neighbor']} freeze until "
            f"{plan['freeze_end_date']}; early release needs incident-commander approval and a USD "
            f"{plan['release_fee']} re-provisioning charge ({contract['case_id']})",
            "In Progress",
            3,
            "capacity",
            TODAY_DAY - 3,
        ),
    )
    cx.executemany(
        "INSERT INTO jira_issues(key,project,summary,issue_type,status,resolution,priority,component,assignee,"
        "created_day,updated_day) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                contract["vendor_ticket"],
                "VEND",
                f"{VENDOR} capacity order for {contract['case_id']}: {plan['gap']} {service} replicas, standard "
                f"delivery {iso(plan['standard_days'])}, expedited delivery {iso(plan['expedited_days'])} for USD "
                f"{plan['expedite_fee']}",
                "Vendor Order",
                "Done",
                "Confirmed",
                "Medium",
                service,
                "procurement",
                TODAY_DAY - 4,
                TODAY_DAY - 1,
            ),
            (
                contract["approval_ticket"],
                "CHG",
                f"Change approval {contract['approval_ticket']} for {contract['case_id']}: the standard and expedited "
                f"{VENDOR} capacity plans for {service} are approved within the published change windows; releasing "
                f"reserved capacity or executing outside a window is not approved",
                "Change",
                "Done",
                "Approved",
                "Medium",
                service,
                "change-advisory",
                TODAY_DAY - 3,
                TODAY_DAY - 1,
            ),
        ],
    )
    cx.execute(
        "INSERT INTO messages(channel,author,body) VALUES (?,?,?)",
        (
            contract["channel"],
            "customer-success",
            f"The {service} cutover is committed to the customer for {plan['cutover_date']}; please state in the "
            f"handoff whether the capacity plan lands on time and what it costs.",
        ),
    )


def status_post_row(contract: dict[str, Any]) -> tuple[Any, ...]:
    plan = contract["plan"]
    return (
        contract["status_post"],
        f"{contract['case_id']}: {contract['service']} customer cutover scheduled for {plan['cutover_date']}",
        "none",
        "scheduled",
        TODAY_DAY - 1,
    )


# --------------------------------------------------------------------- reads
def capacity_context_calls(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """The five extra evidence reads the capacity plan needs, one per source."""

    return [
        {"tool": "confluence_get_page", "args": {"page_id": contract["readiness_page"]}},
        {"tool": "jira_get_issue", "args": {"key": contract["vendor_ticket"]}},
        {"tool": "jira_get_issue", "args": {"key": contract["approval_ticket"]}},
        {"tool": "linear_list_issues", "args": {"team": f"team-{contract['service']}"}},
        {"tool": "list_status_page_posts", "args": {"since_day": EVIDENCE_WINDOW_START}},
    ]


def decision_context_calls(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Every read the decision record depends on (graded before the record)."""

    return [
        *capacity_context_calls(contract),
        {
            "tool": "pd_list_change_events",
            "args": {
                "pd_service_id": contract["pd_service_id"],
                "since_day": EVIDENCE_WINDOW_START,
            },
        },
        {"tool": "list_messages", "args": {"channel": contract["channel"], "limit": 50}},
        {"tool": "confluence_get_page", "args": {"page_id": contract["current_page"]}},
    ]


def decision_record_call(contract: dict[str, Any]) -> dict[str, Any]:
    plan = contract["plan"]
    return {
        "tool": "submit_answer",
        "args": {
            "question_id": contract["capacity_question"],
            "answer": json.dumps(plan["answer"], sort_keys=True, separators=(",", ":")),
            "sources": [
                "confluence_pages",
                "pd_change_events",
                "linear_issues",
                "jira_issues",
                "status_page_posts",
                "messages",
            ],
            "assumptions": (
                f"Required {plan['required']} = {plan['per_zone']} per zone x {plan['zones']} zones from the readiness "
                f"standard and the PagerDuty scale record; usable {plan['usable']} = {plan['observed']} observed - "
                f"{plan['reserved']} reserved in {contract['reservation_issue']}; gap {plan['gap']} covered by "
                f"{contract['vendor_ticket']}; completion is the first published change window on or after delivery; "
                f"{OPTION_RELEASE} needs approval beyond {contract['approval_ticket']} so it is not selected."
            ),
        },
    }


def handoff_tokens(contract: dict[str, Any]) -> list[dict[str, str]]:
    plan = contract["plan"]
    return [
        {"name": "selected_option", "token": plan["recommended_option"]},
        {"name": "outcome_date", "token": iso(plan["recommended_completion"])},
        {"name": "approval_reference", "token": contract["approval_ticket"]},
        {"name": "timing_status", "token": plan["status"]},
        {"name": "binding_constraint", "token": f"{VENDOR} {plan['binding_kind']} capacity on {plan['binding_delivery_date']}"},
    ]


def handoff_body(contract: dict[str, Any], current_control: str) -> str:
    plan = contract["plan"]
    return (
        f"{contract['completion_marker']}. Current authority: {current_control}. Capacity plan "
        f"{plan['recommended_option']}: {contract['service']} reaches {plan['required']} healthy replicas on "
        f"{iso(plan['recommended_completion'])} ({plan['status']}, {plan['variance']:+d} day(s) versus the "
        f"{plan['cutover_date']} cutover) for USD {plan['recommended_cost']} under change approval "
        f"{contract['approval_ticket']}; binding constraint: {VENDOR} {plan['binding_kind']} capacity on "
        f"{plan['binding_delivery_date']} and the {iso(plan['recommended_completion'])} change window; "
        f"{OPTION_RELEASE} stays unexecuted because it needs approval beyond {contract['approval_ticket']}. "
        "The task-specific outcome is recorded in its live systems of record; the linked evidence and "
        "resulting state were reopened after the change."
    )


# ---------------------------------------------------------------- decision model
def _calculation_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    plan = contract["plan"]
    answer = plan["answer"]
    service = contract["service"]
    rows = [
        ("identify_business_date", "business_need_date", 1.0, f"Preserved {answer['business_need_date']} from the published status-page cutover notice as the control date; did not infer urgency from the ticket title."),
        ("read_replicas_per_zone", "replicas_per_zone", 1.0, f"Read {plan['per_zone']} healthy replicas per production zone from the {contract['case_id']} change-readiness standard."),
        ("read_production_zones", "production_zones", 1.0, f"Read {plan['zones']} production zones from the PagerDuty scale record for {contract['pd_service_id']}."),
        ("derive_plan_requirement", "required_replicas", 2.0, f"Derived {plan['per_zone']} per zone x {plan['zones']} zones = {plan['required']} {QUANTITY_UNIT} required before the {service} cutover."),
        ("read_gross_coverage", "observed_replicas", 1.0, f"Read {plan['observed']} {QUANTITY_UNIT} in the {service} production pool from the PagerDuty scale record."),
        ("remove_ineligible_coverage", "reserved_replicas", 1.5, f"Excluded {plan['reserved']} {QUANTITY_UNIT} reserved for the {plan['neighbor']} freeze in Linear {contract['reservation_issue']}."),
        ("calculate_usable_coverage", "usable_replicas", 2.0, f"Calculated {plan['observed']} observed - {plan['reserved']} reserved = {plan['usable']} usable {QUANTITY_UNIT}."),
        ("calculate_plan_gap", "replica_gap", 2.0, f"Calculated {plan['required']} required - {plan['usable']} usable = {plan['gap']} {QUANTITY_UNIT} uncovered."),
        ("preserve_plan_unit", "quantity_unit", 0.5, f"Kept every capacity quantity in {QUANTITY_UNIT}."),
        ("read_standard_external_readiness", "standard_capacity_date", 1.0, f"Read {answer['standard_capacity_date']} as {VENDOR}'s independently confirmed standard delivery date from vendor order {contract['vendor_ticket']}."),
        ("read_expedited_external_readiness", "expedited_capacity_date", 1.0, f"Read {answer['expedited_capacity_date']} as {VENDOR}'s independently confirmed expedited delivery date (USD {plan['expedite_fee']}) from vendor order {contract['vendor_ticket']}."),
        ("bound_external_recovery_quantity", "capacity_request_replicas", 1.0, f"Bound the vendor request to the {plan['gap']} uncovered {QUANTITY_UNIT} rather than the full {plan['required']}-replica requirement."),
        ("identify_safe_window", "next_change_window", 1.0, f"Read the {service} change calendar ({', '.join(plan['window_dates'])}) from the current operating control and identified {answer['next_change_window']} as the next window."),
        ("compare_baseline_plan", "standard_plan_completion", 1.0, f"Calculated {OPTION_STANDARD} outcome as {answer['standard_plan_completion']}: the first change window on or after standard delivery."),
        ("compare_accelerated_plan", "expedited_plan_completion", 1.0, f"Calculated {OPTION_EXPEDITE} outcome as {answer['expedited_plan_completion']}: the first change window on or after expedited delivery."),
        ("compare_escalated_plan", "reserved_release_completion", 1.0, f"Calculated {OPTION_RELEASE} outcome as {answer['reserved_release_completion']} and kept its separate-approval condition."),
        ("choose_task_specific_option", "recommended_option", 2.0, f"Compared the date, cost and authority of {OPTION_STANDARD}, {OPTION_EXPEDITE} and {OPTION_RELEASE}; selected {plan['recommended_option']} as the best currently authorised plan under the readiness standard."),
        ("calculate_recommended_outcome", "recommended_outcome_date", 2.0, f"Calculated {answer['recommended_outcome_date']} as the supported outcome date for {plan['recommended_option']}."),
        ("calculate_selected_cost", "recommended_incremental_cost_usd", 1.0, f"Applied USD {plan['recommended_cost']} as the documented incremental cost of {plan['recommended_option']}."),
        ("apply_escalation_authority", "escalation_approval_required", 1.0, f"Recognised that {OPTION_RELEASE} remains outside current authority and needs incident-commander approval beyond {contract['approval_ticket']}."),
        ("apply_approval_record", "approval_reference", 1.0, f"Applied change approval {contract['approval_ticket']} only to the authorised {plan['recommended_option']} scope."),
        ("calculate_outcome_variance", "outcome_vs_control_days", 1.5, f"Compared {answer['recommended_outcome_date']} with the independent control date {answer['business_need_date']} and calculated a signed variance of {plan['variance']:+d} day(s)."),
        ("state_honest_timing_status", "decision_timing_status", 1.0, f"Reported {plan['status']}; did not relabel a controlled but late result as on time."),
    ]
    return [
        {
            "id": identifier,
            "field": field,
            "description": description,
            "weight": weight,
            "milestone_id": ANALYSIS_MILESTONE if field in ANALYSIS_FIELDS else DECISION_MILESTONE,
            "check_id": f"correctness.v5_answer_{field}",
        }
        for identifier, field, weight, description in rows
    ]


def decision_model(row: dict[str, Any], contract: dict[str, Any], current_control: str) -> dict[str, Any]:
    plan = contract["plan"]
    service = contract["service"]
    facts = [
        {
            "id": "authoritative_identity",
            "sources": ["jira", "github"],
            "statement": f"{contract['case_id']} resolves to Jira {contract['case_id']} and GitHub issue #{contract['github_issue']} for {service}; the effective control is {current_control}.",
            "rubric": f"Located {contract['case_id']} for {service} through immutable Jira and GitHub identities and preserved {current_control} as the effective control.",
        },
        {
            "id": "effective_requirement",
            "sources": ["confluence", "pagerduty"],
            "statement": f"The readiness standard requires {plan['per_zone']} healthy replicas per zone and the PagerDuty scale record shows {plan['zones']} zones: {plan['required']} {QUANTITY_UNIT} are required before the {plan['cutover_date']} cutover.",
            "rubric": f"Derived {plan['required']} {QUANTITY_UNIT} from {plan['per_zone']} per zone x {plan['zones']} zones, with control date {plan['cutover_date']}.",
        },
        {
            "id": "eligible_coverage",
            "sources": ["pagerduty", "linear"],
            "statement": f"The pool holds {plan['observed']} {QUANTITY_UNIT}; {plan['reserved']} are reserved for the {plan['neighbor']} freeze, leaving {plan['usable']} usable and a gap of {plan['gap']}.",
            "rubric": f"Reconciled {plan['observed']} observed less {plan['reserved']} reserved to {plan['usable']} usable {QUANTITY_UNIT} and a {plan['gap']}-replica gap.",
        },
        {
            "id": "conditional_external_recovery",
            "sources": ["jira"],
            "statement": f"{VENDOR} vendor order {contract['vendor_ticket']} confirms {plan['gap']} {QUANTITY_UNIT}: standard delivery {iso(plan['standard_days'])}, expedited delivery {iso(plan['expedited_days'])} for USD {plan['expedite_fee']}.",
            "rubric": f"Used {VENDOR}'s confirmed standard and expedited dates as inputs, not as authorisation or as completion dates.",
        },
        {
            "id": "finite_capacity",
            "sources": ["confluence"],
            "statement": f"Change windows for {service} are {', '.join(plan['window_dates'])}; work outside a window needs incident-commander approval.",
            "rubric": f"Applied the published {service} change calendar to derive every plan's completion without using excluded or unapproved scope.",
        },
        {
            "id": "approval_scope",
            "sources": ["jira"],
            "statement": f"{contract['approval_ticket']} approves the standard and expedited plans within published windows; releasing reserved capacity is outside current authority.",
            "rubric": f"Applied {contract['approval_ticket']} only to {plan['recommended_option']} and kept {OPTION_RELEASE} outside current authority.",
        },
        {
            "id": "business_impact",
            "sources": ["status_page", "slack"],
            "statement": f"The customer cutover is published for {plan['cutover_date']}; the recommended plan lands {plan['variance']:+d} day(s) versus it ({plan['status']}).",
            "rubric": f"Compared the selected outcome with the {plan['cutover_date']} cutover and reported {plan['status']} honestly.",
        },
    ]
    return {
        "mode": "capacity_plan",
        "case_reference": contract["case_id"],
        "record": contract["case_id"],
        "revision": current_control,
        "subject": f"{service} customer cutover readiness for {contract['case_id']}",
        "source_document": f"{contract['case_id']} change-readiness standard, {VENDOR} order {contract['vendor_ticket']}, change approval {contract['approval_ticket']}",
        "question_id": contract["capacity_question"],
        "selected_option": plan["recommended_option"],
        "selected_completion": iso(plan["recommended_completion"]),
        "facts": facts,
        "calculations": _calculation_rows(contract),
        "options": deepcopy(plan["options"]),
    }


def decision_options(row: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Public option table: every alternative carries outcome, cost and authority."""

    plan = contract["plan"]
    reasons = {
        OPTION_STANDARD: f"Standard {VENDOR} delivery {iso(plan['standard_days'])} reaches the {iso(plan['standard_completion'])} window at USD 0.",
        OPTION_EXPEDITE: f"Expedited {VENDOR} delivery {iso(plan['expedited_days'])} reaches the {iso(plan['expedited_completion'])} window for USD {plan['expedite_fee']}.",
        OPTION_RELEASE: f"Releasing the {plan['reserved']} {QUANTITY_UNIT} reserved for the {plan['neighbor']} freeze covers the gap today but needs approval beyond {contract['approval_ticket']}.",
    }
    return [
        {
            **option,
            "selected": bool(option["recommended"]),
            "reason": reasons[option["id"]] + " " + option["consequence"],
        }
        for option in plan["options"]
    ]


def answer_schema() -> dict[str, Any]:
    descriptions = {
        "business_need_date": "Customer cutover date published on the status page that the plan must protect (YYYY-MM-DD).",
        "replicas_per_zone": "Healthy replicas required per production zone by the change-readiness standard.",
        "production_zones": "Production zone count from the PagerDuty scale record.",
        "required_replicas": "replicas_per_zone x production_zones.",
        "observed_replicas": "Replicas in the production pool per the PagerDuty scale record, before exclusions.",
        "reserved_replicas": "Replicas reserved for another team's freeze in the Linear capacity register.",
        "usable_replicas": "observed_replicas - reserved_replicas.",
        "replica_gap": "required_replicas - usable_replicas.",
        "quantity_unit": f"Unit shared by every capacity quantity: {QUANTITY_UNIT}.",
        "standard_capacity_date": f"{VENDOR}'s confirmed standard delivery date from the vendor order.",
        "expedited_capacity_date": f"{VENDOR}'s confirmed expedited delivery date from the vendor order.",
        "capacity_request_replicas": "Uncovered replicas the vendor order must cover.",
        "next_change_window": "Next published change window on the current operating control page.",
        "standard_plan_completion": f"Outcome date for {OPTION_STANDARD}: first change window on or after standard delivery.",
        "expedited_plan_completion": f"Outcome date for {OPTION_EXPEDITE}: first change window on or after expedited delivery.",
        "reserved_release_completion": f"Outcome date for {OPTION_RELEASE}.",
        "recommended_option": f"One of {OPTION_STANDARD}, {OPTION_EXPEDITE}, {OPTION_RELEASE}.",
        "recommended_outcome_date": "Outcome date of the recommended plan.",
        "recommended_incremental_cost_usd": "Documented incremental cost of the recommended plan in USD.",
        "escalation_approval_required": "1 when a listed plan needs approval beyond the change approval; otherwise 0.",
        "approval_reference": "The change approval record applied to the recommended plan.",
        "outcome_vs_control_days": "Recommended outcome date minus the cutover date; positive means late.",
        "decision_timing_status": "ON_TIME when the recommended outcome is on or before the cutover; otherwise LATE.",
    }
    integer_fields = {
        "replicas_per_zone",
        "production_zones",
        "required_replicas",
        "observed_replicas",
        "reserved_replicas",
        "usable_replicas",
        "replica_gap",
        "capacity_request_replicas",
        "recommended_incremental_cost_usd",
        "escalation_approval_required",
        "outcome_vs_control_days",
    }
    properties: dict[str, Any] = {}
    for field in ANSWER_FIELDS:
        entry: dict[str, Any] = {
            "type": "integer" if field in integer_fields else "string",
            "description": descriptions[field],
        }
        if field == "decision_timing_status":
            entry["enum"] = ["ON_TIME", "LATE"]
        if field == "recommended_option":
            entry["enum"] = [OPTION_STANDARD, OPTION_EXPEDITE, OPTION_RELEASE]
        properties[field] = entry
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(ANSWER_FIELDS),
        "properties": properties,
        "submission": (
            "Submitted once as the reconciliation answer whose question_id is the case capacity-plan question; "
            "the answer is the JSON object above."
        ),
    }


def expected_contract(contract: dict[str, Any]) -> dict[str, Any]:
    plan = contract["plan"]
    checks = []
    for calculation in _calculation_rows(contract):
        field = calculation["field"]
        checks.append(
            {
                "id": f"answer_{field}",
                "field": field,
                "milestone_id": calculation["milestone_id"],
                "check_id": calculation["check_id"],
                "weight": calculation["weight"],
                "description": f"Reported {field} as {plan['answer'][field]!r} in the {contract['capacity_question']} decision record.",
            }
        )
    return {"answer": deepcopy(plan["answer"]), "answer_checks": checks}


# --------------------------------------------------------------------- vcode
def vcode_block(row: dict[str, Any], contract: dict[str, Any]) -> str:
    """Grade the decision record, its evidence order and the handoff content.

    Relies on the v4 helpers (_v4_positions, _v4_success_before, _v4_handoff_seq,
    _v4_first_source_write) defined by realism.augment_vcode.
    """

    plan = contract["plan"]
    expected = plan["answer"]
    reads = decision_context_calls(contract)
    capacity_reads = capacity_context_calls(contract)
    lines = [
        "",
        f"# DevOpsBench v3.2 graded capacity-plan decision model for {row['bench_id']}.",
        f"_V5_QUESTION = {contract['capacity_question']!r}",
        f"_V5_DECISION_READS = {reads!r}",
        f"_V5_CAPACITY_READS = {capacity_reads!r}",
        "",
        "def _v5_same(_actual, _expected):",
        "    if isinstance(_expected, bool):",
        "        return str(_actual).strip().casefold() in ({'1', 'true'} if _expected else {'0', 'false'})",
        "    if isinstance(_expected, (int, float)):",
        "        try:",
        "            return abs(float(_actual) - float(_expected)) < 1e-9",
        "        except (TypeError, ValueError):",
        "            return False",
        "    return str(_actual).strip().casefold() == str(_expected).strip().casefold()",
        "",
        "_v5_row = conn.execute(",
        "    'SELECT answer FROM answers WHERE question_id=? ORDER BY answer_id DESC', (_V5_QUESTION,)",
        ").fetchone()",
        "try:",
        "    _v5_answer = json.loads(_v5_row[0]) if _v5_row else {}",
        "except Exception:",
        "    _v5_answer = {}",
        "if not isinstance(_v5_answer, dict):",
        "    _v5_answer = {}",
        "_v5_record_positions = _v4_positions({'tool': 'submit_answer', 'args': {'question_id': _V5_QUESTION}}, True)",
        "_v5_record_seq = max(_v5_record_positions) if _v5_record_positions else 0",
        "_v5_handoff_body = _one(",
        "    \"SELECT body FROM messages WHERE channel=? AND author='agent' AND body LIKE ? ORDER BY message_id DESC\",",
        f"    {contract['channel']!r}, '%{contract['completion_marker']}%'",
        ") or ''",
        "",
        "_c('correctness', 'v5_capacity_plan_recorded',",
        "   bool(_v5_record_positions) and bool(_v5_answer),",
        f"   {f'record the {contract['case_id']} capacity plan once as the JSON reconciliation answer to {contract['capacity_question']}'!r})",
    ]
    for calculation in _calculation_rows(contract):
        field = calculation["field"]
        lines.extend(
            [
                f"_c('correctness', {'v5_answer_' + field!r},",
                f"   _v5_same(_v5_answer.get({field!r}), {expected[field]!r}),",
                f"   {calculation['description']!r})",
            ]
        )
    evidence_message = (
        f"read the readiness standard, {VENDOR} order {contract['vendor_ticket']}, change approval "
        f"{contract['approval_ticket']}, the Linear reservation and the status-page cutover notice before changing state"
    )
    approval_message = (
        f"apply {contract['approval_ticket']} to {plan['recommended_option']} only and keep "
        f"{OPTION_RELEASE} outside current authority"
    )
    lines.extend(
        [
            "_c('correctness', 'v5_capacity_evidence_complete',",
            "   _v4_success_before(_V5_CAPACITY_READS, _v4_first_source_write),",
            f"   {evidence_message!r})",
            "_c('deployment', 'v5_decision_evidence_precedes_record',",
            "   _v5_record_seq > 0 and _v4_success_before(_V5_DECISION_READS, _v5_record_seq),",
            "   'derive the capacity plan only after every source fact it depends on has been read successfully')",
            "_c('deployment', 'v5_record_precedes_handoff',",
            "   _v5_record_seq > 0 and _v4_handoff_seq > _v5_record_seq,",
            "   'record the capacity plan before stating it in the completion handoff')",
            "_c('correctness', 'v5_approval_applied_to_selected_scope',",
            f"   _v5_same(_v5_answer.get('approval_reference'), {contract['approval_ticket']!r})",
            f"   and _v5_same(_v5_answer.get('recommended_option'), {plan['recommended_option']!r})",
            "   and _v5_same(_v5_answer.get('escalation_approval_required'), 1),",
            f"   {approval_message!r})",
        ]
    )
    for token in handoff_tokens(contract):
        message = (
            f"state the {token['name'].replace('_', ' ')} ({token['token']}) in the "
            "scoped completion handoff"
        )
        lines.extend(
            [
                f"_c('correctness', {'v5_handoff_states_' + token['name']!r},",
                f"   {token['token'].casefold()!r} in _v5_handoff_body.casefold(),",
                f"   {message!r})",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def check_names() -> dict[str, str]:
    """Milestone assignment for every v5 atomic check name."""

    names = {
        "v5_capacity_plan_recorded": DECISION_MILESTONE,
        "v5_capacity_evidence_complete": ANALYSIS_MILESTONE,
        "v5_decision_evidence_precedes_record": "execution.sequence",
        "v5_record_precedes_handoff": "execution.sequence",
        "v5_approval_applied_to_selected_scope": DECISION_MILESTONE,
    }
    for field in ANSWER_FIELDS:
        names[f"v5_answer_{field}"] = ANALYSIS_MILESTONE if field in ANALYSIS_FIELDS else DECISION_MILESTONE
    for token in ("selected_option", "outcome_date", "approval_reference", "timing_status", "binding_constraint"):
        names[f"v5_handoff_states_{token}"] = "answer.insights"
    return names


# ---------------------------------------------------------------- controls
def tampered_answer(contract: dict[str, Any]) -> dict[str, Any]:
    """A decision record that ignores the reservation (wrong intermediate values)."""

    plan = contract["plan"]
    answer = deepcopy(plan["answer"])
    answer["usable_replicas"] = plan["observed"]
    answer["replica_gap"] = max(plan["required"] - plan["observed"], 0)
    answer["capacity_request_replicas"] = answer["replica_gap"]
    return answer


def unapproved_answer(contract: dict[str, Any]) -> dict[str, Any]:
    """A decision record that selects the plan outside current authority."""

    plan = contract["plan"]
    answer = deepcopy(plan["answer"])
    answer["recommended_option"] = OPTION_RELEASE
    answer["recommended_outcome_date"] = iso(plan["release_completion"])
    answer["recommended_incremental_cost_usd"] = plan["release_fee"]
    answer["escalation_approval_required"] = 0
    answer["outcome_vs_control_days"] = plan["release_completion"] - plan["cutover_days"]
    answer["decision_timing_status"] = "ON_TIME"
    return answer


def unapproved_handoff_body(contract: dict[str, Any], current_control: str) -> str:
    plan = contract["plan"]
    return (
        f"{contract['completion_marker']}. Current authority: {current_control}. Capacity plan {OPTION_RELEASE}: "
        f"{contract['service']} reaches {plan['required']} healthy replicas on {iso(plan['release_completion'])} "
        f"(ON_TIME) by releasing the reserved capacity under {contract['approval_ticket']}."
    )
