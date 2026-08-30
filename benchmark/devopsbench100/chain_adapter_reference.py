"""Reference reasoning-chain adapter for the v3.2 export contract.

This file documents, in executable form, exactly which released artifact
fields prove each hop class H1-H13 of the Blobfish reasoning-chain realism
standard.  It is the drop-in replacement for
``blobfish-0/benchmark/chain_adapters/devopsbench_100.py`` (which still
reads the v3.0 export shape); it imports ``.core`` from that package and is
not imported by anything in this repository.

Released artifacts (``blobfishai/software-devops``, export tree
``dist/devopsbench-100`` produced by ``benchmark/devopsbench100/builder.py``):

* ``huggingface/tasks/dob100-NNN-<slug>.json`` — public task record with
  ``decision_model`` (``mode``, ``facts[] {id, sources, statement}``,
  ``calculations[] {id, field, check_id, milestone_id}``, ``options[]
  {id, completion, incremental_cost, approval, control_status, consequence,
  recommended}``, ``selected_option``, ``selected_completion``),
  ``expected.answer`` + ``expected.answer_checks``, ``answer_schema``,
  ``required_investigations[] {milestone_id, check_id,
  before_primary_mutation, any_of[] {tool, arguments}, description}``,
  ``post_write_verifications[] {after_tool, any_of, check_id}``,
  ``allowed_write_tables``, ``rubric.criteria[] {id, weight,
  atomic_checks[] {id, dimension, name}}``, ``rubric.decision_options``,
  ``rubric.llm_judge`` and ``metadata {source_task_id, category, providers}``.
* ``harbor/tasks/<task_id>/solution/reference.json`` — the sealed contract:
  ``case_contract {case_id, service, current_page, retired_page, ...}`` and
  ``trace_contract {required_context_calls[], source_mutation_tools[],
  decision_record_call, postwrite_readback_calls[], handoff_call,
  handoff_contract {tool, graded_text_contains[]}, readback_call,
  providers[]}``.
* ``reports/build.json`` ``version``.

The released ``huggingface/verifiers/verify_<task_id>.py`` embeds the same
16 semantic milestones and grades their nested atomic checks (``v4_*`` causal
evidence/order/readback checks, ``v5_answer_<field>`` per-field decision-record
checks, ``v5_capacity_evidence_complete``, ``v5_decision_evidence_precedes_record``,
``v5_record_precedes_handoff``, ``v5_approval_applied_to_selected_scope`` and
``v5_handoff_states_*`` content checks) over the final SQLite state and the
argument-aware ``mcp_trace``.

Hop evidence (a hop counts only when the graded check backing it exists in the
released rubric):

* H1  — >=2 graded ``investigation.scope`` reads (one a search/list), the
  ``authoritative_identity`` fact and ``correctness.v4_case_identity_resolved``.
* H2  — ``read_replicas_per_zone`` + ``read_production_zones`` +
  ``derive_plan_requirement`` calculations, each with its graded
  ``correctness.v5_answer_<field>`` check.
* H3  — ``read_gross_coverage`` + ``remove_ineligible_coverage`` +
  ``calculate_usable_coverage`` calculations graded the same way.
* H4  — ``calculate_plan_gap`` graded.
* H5  — ``read_standard_external_readiness`` + ``read_expedited_external_readiness``
  graded, the ``conditional_external_recovery`` fact, and a graded
  pre-mutation read whose description names the vendor/external source.
* H6  — ``identify_safe_window`` graded, the ``finite_capacity`` fact, graded
  reads of both the current and retired control pages, and
  ``deployment.v4_evidence_before_state_change``.
* H7  — three options each carrying ``completion``, numeric ``incremental_cost``,
  ``approval`` + ``control_status``; >=1 ``ADDITIONAL_APPROVAL_REQUIRED``, >=1
  ``AVAILABLE_NOT_RECOMMENDED``/``NOT_SUPPORTED_BY_CURRENT_EVIDENCE``, exactly
  one recommended, and every option outcome graded in ``expected.answer``.
* H8  — ``choose_task_specific_option`` + ``calculate_recommended_outcome``
  graded, the answer's ``recommended_option`` equal to the model's
  ``selected_option``, and the ``state.primary`` milestone present.
* H9  — ``identify_business_date`` + ``calculate_outcome_variance`` +
  ``state_honest_timing_status`` graded with their answer fields.
* H10 — ``apply_escalation_authority`` + ``apply_approval_record`` graded,
  ``correctness.v5_approval_applied_to_selected_scope``, >=1 graded
  ``investigation.authority`` read, the ``approval_scope`` fact and the
  ``escalation_approval_required`` / ``approval_reference`` answer fields.
* H11 — non-empty ``source_mutation_tools``, >=1 exported
  ``post_write_verifications`` / ``postwrite_readback_calls`` graded by
  ``deployment.v4_state_readbacks_complete``, the ``containment.scope``
  milestone and non-empty ``allowed_write_tables``.
* H12 — ``handoff_contract.tool == "post_message"`` whose
  ``graded_text_contains`` names the selected option and completion, each
  enforced by a ``correctness.v5_handoff_states_*`` check.
* H13 — >=12 graded answer fields, every calculation field present in the
  answer, and every field's ``v5_answer_<field>`` check in the rubric.

Counts: ``dependentDerivations`` = decision-model calculations (all graded);
``sourceSystemsBeforeDecision`` = ``trace_contract.providers``;
``evidenceReadsBeforeDecision`` = ``required_context_calls``;
``gradedAnswerFields`` = ``expected.answer`` fields.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .core import empty_measure, not_measured, read_json, release_path_label, release_version, summarize

SLUG = "devopsbench-100"
RELEASE = Path("software-devops") / "dist" / "devopsbench-100"
SEARCH_TOOL = re.compile(r"search|list", re.I)
EXTERNAL_WORDS = re.compile(r"external|supplier|vendor|counterpart|third.?party", re.I)
UNAUTHORIZED_STATES = {"ADDITIONAL_APPROVAL_REQUIRED"}
INFERIOR_STATES = {"AVAILABLE_NOT_RECOMMENDED", "NOT_SUPPORTED_BY_CURRENT_EVIDENCE"}


def measure_devopsbench_task(task: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    metadata = task.get("metadata", {})
    model = task.get("decision_model") or {}
    measure = empty_measure(task["task_id"], model.get("mode") or metadata.get("category"))
    hops = measure["hops"]
    rubric = task.get("rubric", {})
    milestones = {criterion["id"] for criterion in rubric.get("criteria", [])}
    checks = {
        check["id"]
        for criterion in rubric.get("criteria", [])
        for check in criterion.get("atomic_checks", [])
    }
    answer = (task.get("expected") or {}).get("answer") or {}
    answer_values = {str(value) for value in answer.values()}
    calculations = model.get("calculations", [])
    calcs = {calculation["id"] for calculation in calculations}
    calc_fields = {calculation["field"] for calculation in calculations}
    calc_checks_graded = {calculation["check_id"] for calculation in calculations} <= checks
    facts = {fact["id"] for fact in model.get("facts", [])}
    case = reference.get("case_contract", {})
    trace = reference.get("trace_contract", {})
    reads = trace.get("required_context_calls", [])
    investigations = [
        investigation
        for investigation in task.get("required_investigations", [])
        if investigation.get("before_primary_mutation") and investigation.get("check_id") in checks
    ]
    by_milestone = Counter(investigation["milestone_id"] for investigation in investigations)
    readbacks = trace.get("postwrite_readback_calls", []) or []
    verifications = task.get("post_write_verifications", [])
    handoff_contract = trace.get("handoff_contract", {}) or {}
    graded_handoff = set(map(str, handoff_contract.get("graded_text_contains", [])))

    def graded(ids: set[str]) -> bool:
        return bool(ids) and ids <= calcs and calc_checks_graded

    def reads_page(page_id: Any) -> bool:
        return page_id is not None and any(
            read.get("tool") == "confluence_get_page" and read.get("args", {}).get("page_id") == page_id
            for read in reads
        )

    hops["H1"] = (
        by_milestone.get("investigation.scope", 0) >= 2
        and "authoritative_identity" in facts
        and "correctness.v4_case_identity_resolved" in checks
        and any(SEARCH_TOOL.search(read.get("tool", "")) for read in reads)
        and bool(case.get("service"))
    )
    hops["H2"] = graded({"read_replicas_per_zone", "read_production_zones", "derive_plan_requirement"})
    hops["H3"] = graded({"read_gross_coverage", "remove_ineligible_coverage", "calculate_usable_coverage"})
    hops["H4"] = graded({"calculate_plan_gap"})
    graded_external_reads = sum(
        1 for investigation in investigations if EXTERNAL_WORDS.search(investigation["description"])
    )
    hops["H5"] = (
        graded({"read_standard_external_readiness", "read_expedited_external_readiness"})
        and "conditional_external_recovery" in facts
        and graded_external_reads >= 1
    )
    hops["H6"] = (
        graded({"identify_safe_window"})
        and "finite_capacity" in facts
        and reads_page(case.get("current_page"))
        and reads_page(case.get("retired_page"))
        and "deployment.v4_evidence_before_state_change" in checks
    )

    options = model.get("options", [])
    alt = measure["alternatives"]
    alt["count"] = len(options)
    alt["withOutcome"] = sum(1 for option in options if option.get("completion"))
    alt["withCost"] = sum(1 for option in options if isinstance(option.get("incremental_cost"), (int, float)))
    alt["withAuthority"] = sum(1 for option in options if option.get("approval") and option.get("control_status"))
    alt["unauthorized"] = sum(1 for option in options if option.get("approval") in UNAUTHORIZED_STATES)
    alt["inferiorOrUnsupported"] = sum(1 for option in options if option.get("approval") in INFERIOR_STATES)
    alt["recommended"] = sum(1 for option in options if option.get("recommended"))
    alt["outcomesGraded"] = sum(1 for option in options if str(option.get("completion")) in answer_values)
    hops["H7"] = (
        alt["count"] >= 3
        and alt["withOutcome"] == alt["count"]
        and alt["withCost"] == alt["count"]
        and alt["withAuthority"] == alt["count"]
        and alt["unauthorized"] >= 1
        and alt["inferiorOrUnsupported"] >= 1
        and alt["recommended"] == 1
        and alt["outcomesGraded"] == alt["count"]
    )
    hops["H8"] = (
        graded({"choose_task_specific_option", "calculate_recommended_outcome"})
        and {"recommended_option", "recommended_outcome_date"} <= answer.keys()
        and answer.get("recommended_option") == model.get("selected_option")
        and "state.primary" in milestones
    )
    hops["H9"] = (
        graded({"identify_business_date", "calculate_outcome_variance", "state_honest_timing_status"})
        and {"business_need_date", "outcome_vs_control_days", "decision_timing_status"} <= answer.keys()
    )
    hops["H10"] = (
        graded({"apply_escalation_authority", "apply_approval_record"})
        and "correctness.v5_approval_applied_to_selected_scope" in checks
        and by_milestone.get("investigation.authority", 0) >= 1
        and {"escalation_approval_required", "approval_reference"} <= answer.keys()
        and "approval_scope" in facts
    )
    hops["H11"] = (
        bool(trace.get("source_mutation_tools"))
        and len(readbacks) >= 1
        and len(verifications) >= 1
        and "deployment.v4_state_readbacks_complete" in checks
        and "containment.scope" in milestones
        and bool(task.get("allowed_write_tables"))
    )
    decision_tokens = {str(model.get("selected_option")), str(model.get("selected_completion"))}
    hops["H12"] = (
        handoff_contract.get("tool") == "post_message"
        and decision_tokens <= graded_handoff
        and {"correctness.v5_handoff_states_selected_option", "correctness.v5_handoff_states_outcome_date"} <= checks
    )
    hops["H13"] = len(answer) >= 12 and bool(calc_fields) and calc_fields <= answer.keys() and calc_checks_graded

    measure["dependentDerivations"] = len(calcs)
    measure["sourceSystemsBeforeDecision"] = len(trace.get("providers", []))
    measure["evidenceReadsBeforeDecision"] = len(reads)
    measure["gradedAnswerFields"] = len(answer)
    measure["intermediateValuesGraded"] = hops["H13"]
    measure["llmJudgeCalls"] = 0 if rubric.get("llm_judge") is False else 1
    measure["handoffReadbackOnly"] = not readbacks
    return measure


def audit(source_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    release = source_root / RELEASE
    tasks_dir = release / "huggingface" / "tasks"
    harbor_dir = release / "harbor" / "tasks"
    if not tasks_dir.is_dir() or not harbor_dir.is_dir():
        return not_measured(entry, f"release export not found under {release_path_label(release, source_root)}")
    measures = []
    for task_path in sorted(tasks_dir.glob("dob100-*.json")):
        task = read_json(task_path)
        reference = read_json(harbor_dir / task["task_id"] / "solution" / "reference.json")
        measures.append(measure_devopsbench_task(task, reference))
    version = release_version(release, "reports/build.json", "huggingface/reports/build.json", "release-manifest.json")
    return summarize(
        entry,
        measures,
        adapter="devopsbench-structural",
        version=version,
        source="dist/devopsbench-100 huggingface/tasks + harbor/tasks/*/solution/reference.json in blobfishai/software-devops",
    )
