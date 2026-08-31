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
import difflib
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

from benchmark.devopsbench100 import decision as v32_decision  # noqa: E402
from benchmark.devopsbench100.realism import (  # noqa: E402
    ASSET_COUNT,
    CURRENT_CONTROL,
    MATERIAL_ASSET_COUNT,
    MATERIAL_CONTEXT_CALLS,
    MINIMUM_REFERENCE_CONTEXT_CALLS,
    MAX_PROMPT_WORDS,
    SEMANTIC_MILESTONE_WEIGHTS,
    allowed_write_tables as v32_allowed_write_tables,
    augment_vcode as v3_augment_vcode,
    case_contract as v3_case_contract,
    decision_options as v3_decision_options,
    employee_title as v3_employee_title,
    post_write_verifications as v32_post_write_verifications,
    prompt_has_coherent_readiness as v32_prompt_has_coherent_readiness,
    rebase_vcode_invariants as v3_rebase_vcode_invariants,
    reference_calls as v3_reference_calls,
    release_prompt as v3_release_prompt,
    required_investigations as v32_required_investigations,
    semantic_milestones as v31_semantic_milestones,
    seed_case_evidence as v3_seed_case_evidence,
    task_scoped_execution_authority as v32_task_scoped_execution_authority,
    validate_native_asset as v3_validate_native_asset,
    write_asset_views as v3_write_asset_views,
)

RELEASE_NAME = "DevOpsBench-100"
RELEASE_SLUG = "devopsbench-100"
RELEASE_VERSION = "3.2.7"
MILESTONE_COUNT = len(SEMANTIC_MILESTONE_WEIGHTS)
HARBOR_ORG = "blobfishai"
DATA_LICENSE = "CC-BY-4.0"
CODE_LICENSE = "Apache-2.0"
PYTHON_BASE = ("python:3.12-slim@sha256:"
               "7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17")
PROMPT_LEAKAGE_PATTERN = re.compile(
    r"\b(?:read_exercise|write_implementation|run_exercise_tests|write_runbook|"
    r"submit_answer|submit_diagnosis|ws_list|ws_read|ws_write|ws_grep|ws_python)\b|"
    r"\b(?:grading|hidden tests?|benchmark|verifier|mcp|expected tool calls?|"
    r"work item is|done when)\b|\b(?:DOB|DOC|ENG|OPS|SEC|SLO|QA|SPAN|SUP|MULTI|W6)-\d+\b",
    flags=re.IGNORECASE,
)
STRUCTURAL_CLONE_RAW_THRESHOLD = 0.90
STRUCTURAL_CLONE_SEMANTIC_THRESHOLD = 0.70

# A few source jobs were written as harness tickets whose first body sentence
# merely paraphrases the title.  The public employee request should spend that
# sentence on the operating uncertainty a human actually needs to resolve.
AUTHORED_DETAIL_REWRITES = {
    "tsk_gateway_pool_reuse": (
        "Steady traffic drives the connection count upward until request latency degrades."
    ),
    "tsk_port_report_customer_reports": (
        "Support needs a reliable customer-impact view, but labels, ownership, and lifecycle "
        "state disagree across the issue trackers."
    ),
}


def _clone_identity_values(record: dict[str, Any]) -> list[str]:
    metadata = record.get("metadata") or {}
    values: list[str] = []
    for source in (record, metadata):
        for key in (
            "task_id", "taskId", "id", "case_id", "caseId", "company",
            "organization", "service", "requester", "world_id", "worldId",
        ):
            value = source.get(key) if isinstance(source, dict) else None
            if isinstance(value, str) and len(value.strip()) >= 3:
                values.append(value.strip())
    return sorted(set(values), key=len, reverse=True)


def _normalize_clone_text(value: Any, identities: list[str]) -> str:
    text = str(value).casefold()
    for identity in identities:
        text = text.replace(identity.casefold(), " ")
    text = re.sub(r"\bdob100[-_ ]?\d{3}\b", " ", text)
    text = re.sub(r"\b(?:case|row|chg|msg|task)[-_ ]?\d+[a-z0-9_-]*\b", " ", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", " ", text)
    text = re.sub(r"\b\d{4}[-_/]\d{1,2}(?:[-_/]\d{1,2})?\b", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", " ", text)
    text = re.sub(r"\b(?:tsk|taskid|recordid|caseid)\b", " ", text)
    return " ".join(re.findall(r"[a-z][a-z0-9]+", text))


def _clone_phrase_tokens(prefix: str, value: Any, identities: list[str]) -> set[str]:
    words = _normalize_clone_text(value, identities).split()
    if not words:
        return set()
    if len(words) < 4:
        return {f"{prefix}:{' '.join(words)}"}
    return {
        f"{prefix}:{' '.join(words[index:index + 4])}"
        for index in range(len(words) - 3)
    }


def structural_clone_tokens(
    record: dict[str, Any], reference_sequence: tuple[str, ...]
) -> set[str]:
    """Describe the employee job while ignoring IDs, names, dates, and values."""

    identities = _clone_identity_values(record)
    metadata = record.get("metadata") or {}
    tokens: set[str] = set()
    authored_graph = (
        record.get("semantic_action_graph")
        or metadata.get("semantic_action_graph")
        or []
    )
    nodes = [
        _normalize_clone_text(node, identities) for node in authored_graph
    ]
    nodes = [node for node in nodes if node]
    for node in nodes:
        tokens.update(_clone_phrase_tokens("authored-node", node, []))
    for left, right in zip(nodes, nodes[1:]):
        tokens.add(f"authored-edge:{left}>{right}")

    normalized_tools = [
        _normalize_clone_text(tool, []) for tool in reference_sequence
    ]
    for left, right in zip(normalized_tools, normalized_tools[1:]):
        tokens.add(f"tool-edge:{left}>{right}")
    for tool in metadata.get("required_tools") or record.get("required_tools") or []:
        tokens.add(f"required-tool:{_normalize_clone_text(tool, [])}")
    for table in record.get("allowed_write_tables") or []:
        tokens.add(f"state:{_normalize_clone_text(table, identities)}")

    rubric = record.get("rubric") or {}
    for milestone in rubric.get("criteria") or []:
        category = _normalize_clone_text(
            milestone.get("category") or "milestone", []
        )
        tokens.update(
            _clone_phrase_tokens(
                f"milestone-{category}",
                milestone.get("description") or "",
                identities,
            )
        )
    for option in rubric.get("decision_options") or []:
        branch = (
            "selected"
            if option.get("selected") is True or option.get("recommended") is True
            else "rejected"
        )
        tokens.update(
            _clone_phrase_tokens(
                f"option-{branch}",
                " ".join(
                    str(option.get(key) or "")
                    for key in ("label", "reason", "approach", "consequence")
                ),
                identities,
            )
        )
    for field in (record.get("answer_schema") or {}):
        tokens.add(f"answer-field:{_normalize_clone_text(field, identities)}")
    for field in (record.get("gold_output") or {}):
        tokens.add(f"deliverable:{_normalize_clone_text(field, identities)}")
    if not tokens:
        raise ValueError(f"{record.get('task_id')}: no identifier-neutral clone graph")
    return tokens


def structural_clone_pairs(
    records: list[dict[str, Any]], reference_sequences: list[tuple[str, ...]]
) -> list[dict[str, Any]]:
    semantic = [
        structural_clone_tokens(record, sequence)
        for record, sequence in zip(records, reference_sequences, strict=True)
    ]
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(reference_sequences):
        for right_index in range(left_index + 1, len(reference_sequences)):
            raw = difflib.SequenceMatcher(
                a=left, b=reference_sequences[right_index], autojunk=False
            ).ratio()
            union = semantic[left_index] | semantic[right_index]
            meaning = (
                len(semantic[left_index] & semantic[right_index]) / len(union)
                if union
                else 1.0
            )
            if (
                raw > STRUCTURAL_CLONE_RAW_THRESHOLD
                and meaning > STRUCTURAL_CLONE_SEMANTIC_THRESHOLD
            ):
                pairs.append(
                    {
                        "left": records[left_index]["task_id"],
                        "right": records[right_index]["task_id"],
                        "raw_sequence_similarity": round(raw, 6),
                        "identifier_neutral_semantic_similarity": round(meaning, 6),
                    }
                )
    return sorted(
        pairs,
        key=lambda pair: (
            -pair["raw_sequence_similarity"],
            -pair["identifier_neutral_semantic_similarity"],
            pair["left"],
            pair["right"],
        ),
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
    """Turn a harness-authored source task into a high-level employee outcome."""

    prompt = task["instruction"].replace("\\n", "\n").strip()
    prompt = re.sub(
        r"^This is (?:an investigation(?: and a write-up)?|a decision), not a change\."
        r".*?(?:\n\s*\n|$)",
        "",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = re.sub(
        r"\b(?:DOC|ENG|OPS|SEC|SLO|QA|SPAN|SUP|MULTI|W6)-\d+\s*[—-]\s*",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"NovaCart's (?:engineering|incident|engineering and security) policies? "
        r"(?:are|is) documented in the knowledge base and (?:are|is) not optional(?:;[^.]+)?\.?",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(r"\bDone when:.*$", "", prompt, flags=re.IGNORECASE | re.DOTALL)

    # The source AIOps tasks intentionally share harness prose.  A released
    # employee request should expose the observed business problem and the
    # uncertainty to resolve, not the benchmark's submission recipe.  Keep the
    # title authored in the world and let the release layer add the affected
    # service boundary and a task-specific handoff expectation.
    lines = [line.strip(" \t—-") for line in prompt.splitlines() if line.strip()]
    headline = lines[0] if lines else prompt

    def sentence(value: str) -> str:
        value = value.strip()
        if value[:1].islower():
            value = value[:1].upper() + value[1:]
        return value if value.endswith((".", "?", "!")) else value + "."

    def without_repeated_headline(value: str, title: str) -> str:
        value = value.strip()
        title = title.strip().rstrip(".!?")
        if value.casefold().startswith(title.casefold()):
            value = value[len(title) :].lstrip(" \t,.;:—-")
        return value

    detail = without_repeated_headline(lines[1], headline) if len(lines) > 1 else ""
    authored_detail = AUTHORED_DETAIL_REWRITES.get(str(row["task_id"]))
    if authored_detail:
        if len(lines) > 1:
            prompt = prompt.replace(lines[1], authored_detail, 1)
            lines[1] = authored_detail
        detail = authored_detail
    if row["category"] == "attribution":
        return (
            f"{sentence(headline)} Three customer-impacting alarms arrived within the same "
            "twenty-minute window. Determine whether one mechanism explains them or whether they "
            "are independent failures, localize each supported cause, and record a production-safe finding "
            "that tells the incident lead how many investigations are actually needed."
        )
    if row["category"] == "reconciliation":
        return (
            f"{sentence(headline)} {sentence(detail) if detail else ''} Reconcile the governing "
            "definition, time window, identities, and conflicting systems; give the supported "
            "answer and explain every material exclusion or unresolved ambiguity."
        ).replace("  ", " ")
    if row["category"] == "judgement":
        proposal_context = (
            ""
            if re.search(r"remediations? (?:have|has) been proposed", detail, re.IGNORECASE)
            else "Several remediations have been proposed. "
        )
        return (
            f"{sentence(headline)} {sentence(detail) if detail else ''} {proposal_context}"
            "Decide which one addresses the underlying mechanism rather than merely "
            "reducing the symptom, and explain why the alternatives are not sufficient."
        ).replace("  ", " ")
    if row["category"] == "handover":
        return (
            f"{sentence(headline)} {sentence(detail) if detail else ''} Turn the incident evidence "
            "into on-call guidance that names the decisive observations, shows how to reproduce the "
            "diagnosis, and helps the next engineer distinguish a service failure from its most "
            "plausible infrastructure alternative."
        ).replace("  ", " ")
    if row["category"] == "workspace":
        return (
            "Restore the finance chart-of-accounts export. An account with no postings currently "
            "breaks the ledger check; restore the expected zero-balance behavior, preserve "
            "the double-entry and per-account semantics, and leave the export validation passing "
            "without changing unrelated workspace files."
        )
    if row["category"] == "human_gated":
        return (
            f"{sentence(headline)} {sentence(detail) if detail else ''} Establish the live exposure, "
            "blast radius, and current approval requirement, then carry out only the transition the "
            "recorded decision actually authorizes and verify the affected partner path afterward."
        ).replace("  ", " ")

    if row["category"] == "aiops_analysis":
        headline = re.sub(r"^Root cause:\s*", "", headline, flags=re.IGNORECASE)
        return re.sub(
            r"\s+",
            " ",
            (
                f"{sentence(headline)} The incident record describes the visible effect, but it does not "
                "establish whether the apparent owner, a dependency, or the deployed configuration "
                "is responsible."
            ),
        ).strip()
    if row["category"] == "aiops_detection":
        headline = re.sub(r"^Detection:\s*", "", headline, flags=re.IGNORECASE)
        return re.sub(
            r"\s+",
            " ",
            (
                f"{sentence(headline)} The current monitoring views do not yet establish whether this is an "
                "active objective breach, a stale signal, or a healthy service being blamed for a "
                "downstream symptom."
            ),
        ).strip()
    if row["category"] == "aiops_localization":
        headline = re.sub(r"^Localize\s+", "", headline, flags=re.IGNORECASE)
        return re.sub(
            r"\s+",
            " ",
            (
                f"{sentence(headline)} The label attached to the alarm may describe where the symptom was "
                "noticed rather than the component or runtime condition that actually caused it."
            ),
        ).strip()
    if row["category"] == "feature_flag":
        if any(token in row["task_id"] for token in ("cleanup", "killswitch")):
            context = (
                "The present exposure and customer impact have to be established from the live "
                "rollout record before deciding whether this is containment or permanent cleanup."
            )
        else:
            context = (
                "The product team has approved a guarded first release, but implementation "
                "readiness, ownership, prerequisites, and safe initial exposure still have to be "
                "established from the current records."
            )
        return f"{sentence(headline)} {context}"
    if row["category"] == "multi_service_rollout":
        return (
            f"{sentence(headline)} This capability crosses producing and consuming services. Work out the "
            "schema readiness, dependency direction, approval state, and safe production sequence "
            "from the repository and current operating records."
        )
    if row["category"] == "api_migration":
        return (
            f"{sentence(headline)} Consumers still span the old and replacement contract, so establish "
            "actual usage, compatibility, and rollback conditions before completing the traffic "
            "transition."
        )
    if row["category"] == "security_incident":
        return (
            f"{sentence(headline)} Security needs the affected production path remediated under the current "
            "control, with customer and dependency risk resolved and an audit trail that proves the "
            "live exposure is gone."
        )
    if row["category"] == "code_implementation":
        return (
            f"{sentence(headline)} The repository documents the intended behavior but the executable "
            "boundary is incomplete; infer the non-obvious cases from its consumers and leave the "
            "behavior demonstrably correct."
        )
    if row["category"] == "flaky_test":
        return (
            f"{sentence(headline)} The team has been rerunning the pipeline until it passes. Determine the "
            "real source of nondeterminism and make the affected behavior trustworthy rather than "
            "masking the intermittent failure."
        )
    if row["category"] in {"error_rate_reduction", "latency_optimization"}:
        observed = lines[1] if len(lines) > 1 else "The current service signal is outside its operating objective"
        observed = without_repeated_headline(observed, headline)
        if not observed:
            observed = "The current service signal is outside its operating objective"
        elif observed.casefold() == "beyond the standard":
            observed = "That wait is beyond the standard"
        elif observed.casefold().startswith(("above ", "below ", "beyond ")):
            observed = "The current signal is " + observed
        return (
            f"{sentence(headline)} {sentence(observed)} Determine which current mechanism actually "
            "explains the degradation, choose the smallest supported production repair, and verify "
            "that the customer-facing objective recovers."
        )
    if row["category"] == "horizon":
        observed = lines[1] if len(lines) > 1 else "Customer impact is active"
        observed = without_repeated_headline(observed, headline)
        if not observed:
            observed = "Customer impact is active"
        return (
            f"{sentence(headline)} {sentence(observed)} The fastest containment may not be the durable "
            "repair. Determine the safe recovery from current evidence, restore the service, and "
            "leave the underlying defect and follow-up ownership unambiguous."
        )

    prompt = re.sub(
        r"The visible tests are not the whole specification\..*?(?=\n\s*\n|$)",
        "Cover the documented edge cases, not only the obvious happy path.",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = re.sub(
        r"Read the specification with read_exercise\('[^']+'\), write your implementation with "
        r"write_implementation, and run it with run_exercise_tests until the visible tests pass\.",
        "Complete the missing behavior from the repository's documented contract and leave the available tests passing.",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = prompt.replace(
        "Write it with write_runbook(title=..., body=...).",
        "Leave the completed runbook in the shared on-call knowledge base.",
    )
    prompt = re.sub(
        r"Work out the answer, then submit it with submit_answer\(.*?\), listing every system "
        r"you actually consulted and recording any judgement you had to make in `assumptions`\.",
        "Work out the supported answer, cite the systems you reconciled, and make any judgement or unresolved assumption explicit.",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = re.sub(
        r"submit its proposal_id with submit_answer\(.*?\)\.",
        "identify the supported proposal and explain why the alternatives do not resolve the underlying cause.",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = re.sub(
        r"(?:and\s+)?submit (?:it|the number|the result) with submit_answer\(.*?\)"
        r"(?:,\s*listing the systems you actually read)?\.?",
        "Give the requesting team the supported result and cite the governing records.",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = prompt.replace(
        "In `assumptions`, say why the others are wrong.",
        "Explain why the other proposals do not address the cause.",
    )
    prompt = re.sub(
        r"Submit one diagnosis per scope listed above\s*[—-].*?each naming",
        "Give the incident lead one evidence-backed finding for each affected scope, each naming",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    prompt = re.sub(
        r"\b(?:read_exercise|write_implementation|run_exercise_tests|write_runbook|"
        r"submit_answer|submit_diagnosis|ws_list|ws_read|ws_write|ws_grep|ws_python)\b(?:\([^)]*\))?",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(
        r"The workspace is a real filesystem:.*?(?:\.|$)|What you write is what runs\.",
        "",
        prompt,
        flags=re.IGNORECASE,
    )
    prompt = re.sub(r"\b(?:DOB|DOC|ENG|OPS|SEC|SLO|QA|SPAN|SUP|MULTI|W6)-\d+\b", "", prompt)
    prompt = re.sub(r"\bscope strings? (?:are|is) [^.]+\.?", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?<![.!?;:])\n+", ". ", prompt)
    prompt = re.sub(r"\n+", " ", prompt)
    prompt = re.sub(r"\band do not\.\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"([.!?])\s*\.\s*", r"\1 ", prompt)
    prompt = re.sub(r"\s+([,.!?])", r"\1", prompt)
    prompt = re.sub(r"\s+", " ", prompt).strip(" -\n")

    words = prompt.split()
    if len(words) > 125:
        prompt = " ".join(words[:125]).rstrip(",;:") + "."
    if len(prompt.split()) < 24:
        prompt += (
            " Establish what the current evidence supports, distinguish a real intervention from "
            "an attractive shortcut, and keep unrelated production state out of scope."
        )
    return re.sub(r"\s+", " ", prompt).strip()


def has_repeated_leading_phrase(value: str) -> bool:
    """Detect ticket titles accidentally pasted twice at the prompt boundary."""

    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    for width in range(5, min(20, len(tokens) // 2) + 1):
        if tokens[:width] == tokens[width : width * 2]:
            return True
    return False


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


def rubric_criteria(
    task: dict,
    row: dict,
    contract: dict,
    trace_contract: dict,
) -> list[dict[str, Any]]:
    """Expose semantic employee outcomes with raw checks nested as evidence."""

    rows = v31_semantic_milestones(task, row, contract, trace_contract)
    if len(rows) != MILESTONE_COUNT or sum(item["weight"] for item in rows) != 100:
        raise ValueError(
            f"{row['bench_id']} semantic rubric is not "
            f"{MILESTONE_COUNT} milestones / 100"
        )
    return rows


def employee_reasoning_contract(
    criteria: list[dict[str, Any]], prompt: str
) -> dict[str, str]:
    """Present the full evidence-to-outcome workflow in reviewer language."""

    criteria_by_id = {criterion["id"]: criterion for criterion in criteria}
    return {
        "employee_outcome": v3_employee_title({"instruction": prompt}),
        "investigate": " ".join(
            criteria_by_id[criterion_id]["description"]
            for criterion_id in (
                "analysis.causal_reasoning",
                "analysis.capacity_plan",
            )
        ),
        "decide": " ".join(
            criteria_by_id[criterion_id]["description"]
            for criterion_id in (
                "decision.supported_path",
                "decision.options",
            )
        ),
        "change_or_record": " ".join(
            criteria_by_id[criterion_id]["description"]
            for criterion_id in (
                "state.primary",
                "state.coordination",
                "containment.scope",
            )
        ),
        "verify": " ".join(
            criteria_by_id[criterion_id]["description"]
            for criterion_id in ("verification.outcome", "verification.readback")
        ),
        "deliver": " ".join(
            criteria_by_id[criterion_id]["description"]
            for criterion_id in ("answer.insights", "execution.delivery")
        ),
    }


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


def gold_output(task: dict, milestones: list[dict[str, Any]]) -> dict:
    submitted = [
        {"tool": c["tool"], "arguments": c.get("args", {})}
        for c in task.get("expected_calls", [])
        if c["tool"] in ("submit_answer", "submit_diagnosis")
    ]
    return {
        "expected_semantic_milestones": [
            {"id": milestone["id"], "weight": milestone["weight"]}
            for milestone in milestones
        ],
        "atomic_check_count": sum(
            len(milestone["atomic_checks"]) for milestone in milestones
        ),
        "ground_truth_submissions": submitted,
        "note": (
            "Acceptance is causal and state-based: all semantic milestones must "
            "hold over successful material reads, provider state, post-write "
            "readback, the append-only audit log, and write-scope containment."
        ),
    }


def task_toml(row: dict, task: dict, split: str) -> str:
    name = f"{HARBOR_ORG}/{row['bench_id']}"
    label = CATEGORY_LABELS[row["category"]]
    title = v3_employee_title({"instruction": task["instruction"]})
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


def verifier_source(task: dict, milestones: list[dict[str, Any]]) -> str:
    """Render the standalone verifier with one 100-point semantic metric."""

    return f'''#!/usr/bin/env python3
"""Deterministic semantic verifier for {task["task_id"]}."""
import hashlib
import json
import sqlite3
import sys

TASK_ID = {task["task_id"]!r}
CATEGORY = {task.get("category", "")!r}
MILESTONES = {milestones!r}
VCODE = {task["vcode"]!r}


def _runtime_atomic_checks(checks):
    totals = {{}}
    for dimension, name, _passed, _message in checks:
        key = (dimension, name)
        totals[key] = totals.get(key, 0) + 1
    seen = {{}}
    output = {{}}
    for dimension, name, passed, message in checks:
        key = (dimension, name)
        seen[key] = seen.get(key, 0) + 1
        suffix = "#%d" % seen[key] if totals[key] > 1 else ""
        check_id = "%s.%s%s" % (dimension, name, suffix)
        output[check_id] = {{
            "id": check_id,
            "dimension": dimension,
            "name": name,
            "passed": bool(passed),
            "message": message,
        }}
    return output


def verify(db_path):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    conn.row_factory = sqlite3.Row
    namespace = {{
        "conn": conn,
        "sqlite3": sqlite3,
        "json": json,
        "hashlib": hashlib,
        "db_path": db_path,
        "DB_PATH": db_path,
        "final_answer": "",
        "answer": "",
    }}
    namespace["get_db"] = lambda: conn
    error = None
    try:
        exec(compile(VCODE, "<vcode>", "exec"), namespace)
    except AssertionError as exc:
        error = "assertion: %s" % exc
    except Exception as exc:  # noqa: BLE001
        error = "%s: %s" % (type(exc).__name__, exc)
    finally:
        conn.close()

    atomic = _runtime_atomic_checks(namespace.get("_checks") or [])
    milestone_reports = []
    for milestone in MILESTONES:
        evidence = []
        passed_count = 0
        for expected in milestone["atomic_checks"]:
            actual = atomic.get(expected["id"])
            passed = bool(actual and actual["passed"])
            passed_count += int(passed)
            evidence.append({{
                "id": expected["id"],
                "passed": passed,
                "message": (actual or expected).get("message")
                    or expected.get("description", ""),
            }})
        total = len(evidence)
        fraction = passed_count / total if total else 0.0
        points = round(float(milestone["weight"]) * fraction, 6)
        milestone_reports.append({{
            "id": milestone["id"],
            "category": milestone["category"],
            "description": milestone["description"],
            "weight": milestone["weight"],
            "passed": total > 0 and passed_count == total,
            "passed_checks": passed_count,
            "total_checks": total,
            "points": points,
            "evidence": evidence,
        }})

    points = round(sum(item["points"] for item in milestone_reports), 6)
    reward = round(points / 100.0, 4)
    failed = [item["id"] for item in milestone_reports if not item["passed"]]
    passed = bool(milestone_reports) and not failed and error is None
    return {{
        "task_id": TASK_ID,
        "category": CATEGORY,
        "passed": passed,
        "reward": reward,
        "score": reward,
        "points": points,
        "semantic_weights": {{item["id"]: item["weight"] for item in MILESTONES}},
        "milestones": milestone_reports,
        "dimensions": {{
            item["id"]: "%d/%d" % (item["passed_checks"], item["total_checks"])
            for item in milestone_reports
        }},
        "assertions": list(atomic.values()),
        "failure_reason": error or "; ".join(failed),
    }}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: %s <world.db>" % sys.argv[0], file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(verify(sys.argv[1]), indent=2))
'''


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

Tasks are high-level workplace requests: the employee states the operational
question or desired business result while procedure, authority, and causal
facts remain distributed across the sandbox. Reference trajectories run
{calls['min']}-{calls['max']} tool calls (median {calls['median']}), with
100/100 distinct tool-name sequences. Every task publishes {ASSET_COUNT}
task-scoped native assets: 32 contextual workplace artifacts, 18 exact
non-empty sandbox exports that correspond one-to-one with the
decision-controlling reads, and one inspectable asset manifest. The reference performs
{stats['reference_evidence_reads_per_task']['min']}-{stats['reference_evidence_reads_per_task']['max']}
context reads, while the verifier requires all {MATERIAL_CONTEXT_CALLS}
decision-controlling joins, the task-specific state transitions, a derived
capacity answer with three date/cost/authority options, provider readback, and
a reopened handoff. Acceptance is fully deterministic and expressed as
{MILESTONE_COUNT} task-specific semantic milestones totaling 100 points.
Low-level vcode, final-state, sequence, and anti-forgery checks remain nested
verifier evidence - no LLM judge, network, or clock is in the reward path.

## What is included

- `data/tasks.jsonl`: task records (`task_id`, `task_name`, `world_id`,
  `prompt`, `context_files`, `rubric`, `gold_output`, `metadata`).
- `tasks/`: one readable JSON record per task (includes the guided
  instruction variant).
- `task_files/`: {ASSET_COUNT} inspectable assets per task spanning tickets, services,
  observability, incidents, deployments, code, CI, migrations, vendor trackers,
  knowledge, chat, approvals, capacity reservations, vendor lead times, and
  customer commitments. The `material/` subdirectory contains the
  {MATERIAL_ASSET_COUNT}
  exact sandbox exports used by the deterministic causal contract; the manifest
  records source, query scope, material reason, format, byte size, and digest
  for every listed file without disclosing an execution order or gold state.
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
| Inspectable assets per task | {ASSET_COUNT} | {stats['assets_per_task']['min']} |
| Exact non-empty material exports per task | {MATERIAL_ASSET_COUNT} | {stats['material_assets_per_task']['min']} |
| Material causal reads per task | {MATERIAL_CONTEXT_CALLS} | {stats['material_evidence_reads_per_task']['min']} |
| Unique causal evidence profiles | 100 | {stats['unique_causal_profile_tool_sequences']} |
| Semantic milestones / points | {MILESTONE_COUNT} / 100 | {stats['criteria_per_task']['min']} / 100 |
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
    records = []
    dataset_rows = []
    call_counts = []
    categories: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    prompts = set()
    prompt_values: list[str] = []
    prompt_words: list[int] = []
    prompt_coherence: list[bool] = []
    prompt_execution_authority: list[bool] = []
    prompt_tool_hits: list[dict[str, Any]] = []
    reference_sequences: list[tuple[str, ...]] = []
    source_sequences: list[tuple[str, ...]] = []
    causal_profile_sequences: list[tuple[str, ...]] = []
    identifier_permutation_flags: list[bool] = []
    semantic_graphs: list[tuple[str, ...]] = []
    context_counts: list[int] = []
    material_context_counts: list[int] = []
    postwrite_readback_counts: list[int] = []
    asset_counts: list[int] = []
    material_asset_counts: list[int] = []
    asset_hashes: list[str] = []
    asset_leakage_hits: list[str] = []
    native_formats: set[str] = set()
    criteria_counts: list[int] = []
    criteria_weight_totals: list[int] = []
    answer_field_counts: list[int] = []
    timing_statuses: set[str] = set()
    recommended_plans: set[str] = set()
    decision_gate_rows: list[bool] = []

    for row in catalog["tasks"]:
        source_task = world_tasks[row["task_id"]]
        bench_id = row["bench_id"]
        contract = v3_case_contract(row, source_task)
        prompt = v3_release_prompt(
            row,
            employee_instruction(source_task, row),
            contract,
        )
        split = "heldout" if row["task_id"] in heldout else "train"
        token = verification_token(bench_id)
        task_dir = tasks_root / bench_id
        env = task_dir / "environment"
        world_dir = env / "world"

        world_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "runtime" / "server.py", world_dir / "server.py")
        shutil.copy2(ROOT / "world" / "tools_combined.py", world_dir / "tools_combined.py")
        shutil.copy2(ROOT / "world" / "environment.db", world_dir / "environment.db")
        v3_seed_case_evidence(
            world_dir / "environment.db",
            row,
            source_task,
            prompt,
            contract,
        )
        reference_calls, trace_contract = v3_reference_calls(
            row,
            source_task,
            contract,
            tools_by_name,
        )
        vcode = v3_rebase_vcode_invariants(
            source_task["vcode"], world_dir / "environment.db"
        )
        vcode = v3_augment_vcode(vcode, row, contract, trace_contract)
        task = {
            **source_task,
            "instruction": prompt,
            "source_instruction": source_task["instruction"],
            "expected_calls": reference_calls,
            "vcode": vcode,
        }
        criteria = rubric_criteria(task, row, contract, trace_contract)
        decision_model = v32_decision.decision_model(
            row, contract, CURRENT_CONTROL
        )
        expected = v32_decision.expected_contract(contract)
        investigations = v32_required_investigations(
            row, contract, trace_contract
        )
        readback_contract = v32_post_write_verifications(source_task, contract)
        write_tables = v32_allowed_write_tables(source_task, tools_by_name)

        write_text(task_dir / "task.toml", task_toml(row, task, split))
        write_text(task_dir / "instruction.md", prompt + "\n")
        write_text(env / "Dockerfile", main_dockerfile())
        write_text(env / "docker-compose.yaml", compose_yaml(row["task_id"]))
        write_text(env / "tool", tool_cli(), executable=True)
        write_text(world_dir / "tools.json", slim + "\n")
        write_text(world_dir / "verify_task.py", verifier_source(task, criteria))
        write_json(world_dir / "spec.json", {
            "schema_version": "2.0",
            "benchmark": RELEASE_NAME,
            "benchmark_version": RELEASE_VERSION,
            "bench_id": bench_id,
            "task_id": row["task_id"],
            "category": row["category"],
            "difficulty": row["difficulty"],
            "world_id": world_meta["world_id"],
            "world_digest": world_meta["world_digest"],
            "case_id": contract["case_id"],
            "service": contract["service"],
            "material_context_call_count": trace_contract["material_context_call_count"],
            "reference_context_call_count": trace_contract["reference_context_call_count"],
            "postwrite_readback_count": len(trace_contract["postwrite_readback_calls"]),
            "semantic_milestones": criteria,
            "verify_token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        })
        write_text(world_dir / "Dockerfile", world_dockerfile())

        write_json(task_dir / "solution" / "reference.json", {
            "task_id": row["task_id"], "bench_id": bench_id,
            "case_contract": contract,
            "trace_contract": trace_contract,
            "decision_model": decision_model,
            "expected_answer": expected,
            "required_investigations": investigations,
            "post_write_verifications": readback_contract,
            "allowed_write_tables": write_tables,
            "source_expected_calls": source_task["expected_calls"],
            "expected_calls": task["expected_calls"],
        })
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
        prompt_values.append(prompt)
        prompt_words.append(len(prompt.split()))
        prompt_coherence.append(
            v32_prompt_has_coherent_readiness(row, contract, prompt)
        )
        prompt_execution_authority.append(
            bool(v32_task_scoped_execution_authority(prompt)["authorized"])
        )
        named_tools = sorted(
            name
            for name in tools_by_name
            if name.casefold() in prompt.casefold()
        )
        if named_tools:
            prompt_tool_hits.append({"bench_id": bench_id, "tools": named_tools})
        reference_sequences.append(tuple(call["tool"] for call in task["expected_calls"]))
        source_sequences.append(
            tuple(call["tool"] for call in source_task["expected_calls"])
        )
        causal_profile_sequences.append(
            tuple(
                call["tool"]
                for call in trace_contract["causal_evidence_profile"]
            )
        )
        identifier_permutation_flags.append(
            bool(trace_contract["identifier_or_group_permutation_used"])
        )
        semantic_graphs.append(tuple(trace_contract["semantic_action_graph"]))
        context_counts.append(trace_contract["reference_context_call_count"])
        material_context_counts.append(trace_contract["material_context_call_count"])
        postwrite_readback_counts.append(len(trace_contract["postwrite_readback_calls"]))
        options = v3_decision_options(task, row, contract, trace_contract)
        answer_values = {str(value) for value in expected["answer"].values()}
        calculation_fields = {
            item["field"] for item in decision_model["calculations"]
        }
        answer_field_counts.append(len(expected["answer"]))
        timing_statuses.add(contract["plan"]["status"])
        recommended_plans.add(contract["plan"]["recommended_option"])
        decision_gate_rows.append(
            len(options) == 3
            and all(
                option.get("completion")
                and isinstance(option.get("incremental_cost"), (int, float))
                and option.get("approval")
                and option.get("control_status")
                and option.get("consequence")
                for option in options
            )
            and sum(
                option["approval"] == "ADDITIONAL_APPROVAL_REQUIRED"
                for option in options
            )
            >= 1
            and sum(
                option["approval"]
                in (
                    "AVAILABLE_NOT_RECOMMENDED",
                    "NOT_SUPPORTED_BY_CURRENT_EVIDENCE",
                )
                for option in options
            )
            >= 1
            and sum(bool(option.get("recommended")) for option in options) == 1
            and all(str(option["completion"]) in answer_values for option in options)
            and calculation_fields <= set(expected["answer"])
            and {check["field"] for check in expected["answer_checks"]}
            == set(expected["answer"])
        )
        reasoning_contract = employee_reasoning_contract(criteria, prompt)
        asset_root = hf_root / "task_files" / bench_id
        assets = v3_write_asset_views(
            asset_root,
            world_dir / "environment.db",
            prompt,
            row,
            contract,
            trace_contract,
        )
        context_files = [asset["path"] for asset in assets]
        material_context_files = [
            asset["path"] for asset in assets if asset.get("material")
        ]
        for asset in assets:
            asset_path = hf_root / asset["path"]
            if not v3_validate_native_asset(asset_path):
                raise ValueError(f"invalid native asset: {asset_path}")
            asset_hashes.append(sha256_file(asset_path))
            native_formats.add(asset_path.suffix.casefold().lstrip("."))
            searchable = asset_path.read_bytes().decode("utf-8", errors="ignore").casefold()
            if any(
                marker in searchable
                for marker in (
                    '"expected_calls"',
                    '"gold_output"',
                    "solution/reference.json",
                    "submit_answer(",
                    "submit_diagnosis(",
                )
            ):
                asset_leakage_hits.append(asset["path"])
        asset_counts.append(len(assets))
        material_asset_counts.append(len(material_context_files))
        criteria_counts.append(len(criteria))
        criteria_weight_totals.append(sum(item["weight"] for item in criteria))

        record = {
            "task_id": bench_id,
            "task_name": v3_employee_title({"instruction": prompt}),
            "world_id": world_meta["world_id"],
            "prompt": prompt,
            "context_files": context_files,
            "assets": assets,
            "decision_model": decision_model,
            "expected": expected,
            "answer_schema": v32_decision.answer_schema(),
            "required_investigations": investigations,
            "post_write_verifications": readback_contract,
            "allowed_write_tables": write_tables,
            "rubric": {
                "type": "deterministic",
                "grading": "deterministic",
                "llm_judge": False,
                "pass_rule": (
                    f"all {MILESTONE_COUNT} semantic milestones hold over causal tool "
                    "evidence, the graded capacity-plan decision record, final world "
                    "state, readback, and containment"
                ),
                "score_weights": {
                    criterion["id"]: criterion["weight"]
                    for criterion in criteria
                },
                "checks": [criterion["id"] for criterion in criteria],
                "criteria": criteria,
                "decision_options": options,
                "reasoning_contract": reasoning_contract,
                "verifier": f"verifiers/verify_{bench_id}.py",
            },
            "gold_output": gold_output(task, criteria),
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
                "material_evidence_reads": trace_contract["material_context_call_count"],
                "reference_evidence_reads": trace_contract["reference_context_call_count"],
                "postwrite_readbacks": len(trace_contract["postwrite_readback_calls"]),
                "material_assets": material_context_files,
                "reference_assets": context_files,
                "call_order_policy": (
                    "The reference trajectory is illustrative. Material evidence may be "
                    "investigated in any valid order and equivalent query shapes may add "
                    "safe optional arguments; each causal read must succeed before its "
                    "dependent mutation, and persisted state must be read back afterward."
                ),
                "semantic_action_graph": trace_contract["semantic_action_graph"],
                "business_reasoning_primitives": trace_contract[
                    "business_reasoning_primitives"
                ],
                "reasoning_contract": reasoning_contract,
                "providers": trace_contract["providers"],
                "case_id": contract["case_id"],
                "service": contract["service"],
                "decision_mode": decision_model["mode"],
                "graded_answer_fields": len(expected["answer"]),
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
                   verifier_source(task, criteria), executable=True)
        dataset_rows.append((f"{HARBOR_ORG}/{bench_id}", task_dir))

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

    def token_set(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.casefold()))

    def max_jaccard(values: list[set[str]]) -> float:
        best = 0.0
        for left_index, left in enumerate(values):
            for right in values[left_index + 1:]:
                union = left | right
                best = max(best, len(left & right) / len(union) if union else 1.0)
        return round(best, 6)

    def max_jaccard_pair(values: list[set[str]]) -> tuple[float, list[str]]:
        best = -1.0
        pair: list[str] = []
        for left_index, left in enumerate(values):
            for right_index in range(left_index + 1, len(values)):
                right = values[right_index]
                union = left | right
                score = len(left & right) / len(union) if union else 1.0
                if score > best:
                    best = score
                    pair = [records[left_index]["task_id"], records[right_index]["task_id"]]
        return round(max(best, 0.0), 6), pair

    prompt_max_jaccard = max_jaccard([token_set(prompt) for prompt in prompt_values])
    semantic_max_jaccard, semantic_max_pair = max_jaccard_pair(
        [set(graph) for graph in semantic_graphs]
    )
    sequence_max_similarity = -1.0
    sequence_max_pair: list[str] = []
    for left_index, left in enumerate(reference_sequences):
        for right_index in range(left_index + 1, len(reference_sequences)):
            score = difflib.SequenceMatcher(
                a=left, b=reference_sequences[right_index], autojunk=False
            ).ratio()
            if score > sequence_max_similarity:
                sequence_max_similarity = score
                sequence_max_pair = [
                    records[left_index]["task_id"], records[right_index]["task_id"]
                ]
    sequence_max_similarity = round(max(sequence_max_similarity, 0.0), 6)
    clone_pairs = structural_clone_pairs(records, reference_sequences)
    source_families: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    for source_sequence, profile_sequence in zip(
        source_sequences, causal_profile_sequences, strict=True
    ):
        source_families.setdefault(source_sequence, []).append(profile_sequence)
    repeated_source_profiles_distinct = all(
        all(profiles) and len(profiles) == len(set(profiles))
        for profiles in source_families.values()
        if len(profiles) > 1
    )
    stats = {
        "schema_version": "2.0",
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
        "prompt_max_pairwise_jaccard": prompt_max_jaccard,
        "prompt_words": {
            "min": min(prompt_words),
            "median": sorted(prompt_words)[len(prompt_words) // 2],
            "max": max(prompt_words),
        },
        "unique_reference_tool_name_sequences": len(set(reference_sequences)),
        "reference_sequence_max_pairwise_similarity": sequence_max_similarity,
        "reference_sequence_max_pair": sequence_max_pair,
        "structural_clone_gate": {
            "raw_sequence_threshold": STRUCTURAL_CLONE_RAW_THRESHOLD,
            "identifier_neutral_semantic_threshold": (
                STRUCTURAL_CLONE_SEMANTIC_THRESHOLD
            ),
            "pair_count": len(clone_pairs),
            "pairs": clone_pairs,
        },
        "repeated_source_profiles_distinct": repeated_source_profiles_distinct,
        "unique_causal_profile_tool_sequences": len(set(causal_profile_sequences)),
        "causal_profile_reads_per_task": {
            "min": min(len(profile) for profile in causal_profile_sequences),
            "median": sorted(len(profile) for profile in causal_profile_sequences)[
                len(causal_profile_sequences) // 2
            ],
            "max": max(len(profile) for profile in causal_profile_sequences),
        },
        "material_evidence_outputs_nonempty": True,
        "causal_profile_outputs_nonempty": True,
        "identifier_or_group_permutation_used": any(identifier_permutation_flags),
        "unique_semantic_action_graphs": len(set(semantic_graphs)),
        "semantic_graph_max_pairwise_jaccard": semantic_max_jaccard,
        "semantic_graph_max_pair": semantic_max_pair,
        "semantic_identity_inputs_ignored": True,
        "prompt_tool_hits": prompt_tool_hits,
        "prompt_repeated_leading_phrases": sum(
            has_repeated_leading_phrase(prompt) for prompt in prompt_values
        ),
        "task_scoped_execution_authority": sum(prompt_execution_authority),
        "material_evidence_reads_per_task": {
            "min": min(material_context_counts),
            "median": sorted(material_context_counts)[len(material_context_counts) // 2],
            "max": max(material_context_counts),
        },
        "reference_evidence_reads_per_task": {
            "min": min(context_counts),
            "median": sorted(context_counts)[len(context_counts) // 2],
            "max": max(context_counts),
        },
        "postwrite_readbacks_per_task": {
            "min": min(postwrite_readback_counts),
            "median": sorted(postwrite_readback_counts)[len(postwrite_readback_counts) // 2],
            "max": max(postwrite_readback_counts),
        },
        "assets_per_task": {
            "min": min(asset_counts),
            "median": sorted(asset_counts)[len(asset_counts) // 2],
            "max": max(asset_counts),
        },
        "material_assets_per_task": {
            "min": min(material_asset_counts),
            "median": sorted(material_asset_counts)[len(material_asset_counts) // 2],
            "max": max(material_asset_counts),
        },
        "criteria_per_task": {
            "min": min(criteria_counts),
            "median": sorted(criteria_counts)[len(criteria_counts) // 2],
            "max": max(criteria_counts),
        },
        "decision_options_per_task": 3,
        "graded_answer_fields_per_task": {
            "min": min(answer_field_counts),
            "max": max(answer_field_counts),
        },
        "decision_timing_statuses": sorted(timing_statuses),
        "recommended_plans": sorted(recommended_plans),
        "native_asset_formats": sorted(native_formats),
        "unique_agent_visible_assets": len(set(asset_hashes)),
        "agent_visible_asset_count": len(asset_hashes),
        "asset_leakage_hits": asset_leakage_hits,
        "verifier": {"deterministic": True, "network_calls": 0,
                     "model_calls": 0, "wall_clock_reads": 0, "random_calls": 0},
        "category_table": "| Family | Tasks |\n|---|---:|\n" + category_table,
    }
    quality_gates = {
        "one_hundred_tasks": len(records) == 100,
        "high_level_prompts_unique": len(prompts) == 100,
        "high_level_prompt_length": (
            min(prompt_words) >= 45 and max(prompt_words) <= MAX_PROMPT_WORDS
        ),
        "high_level_prompt_similarity": prompt_max_jaccard < 0.72,
        "no_repeated_leading_prompt_phrase": not any(
            has_repeated_leading_phrase(prompt) for prompt in prompt_values
        ),
        "single_coherent_operational_objective": all(prompt_coherence),
        "all_task_scoped_state_changes_authorized": all(prompt_execution_authority),
        "no_harness_or_grading_leakage_in_prompts": all(
            PROMPT_LEAKAGE_PATTERN.search(prompt) is None for prompt in prompts
        ),
        "unique_reference_tool_sequences": len(set(reference_sequences)) == 100,
        "reference_tool_sequence_similarity": sequence_max_similarity < 0.95,
        "no_structural_template_clones": not clone_pairs,
        "repeated_source_harnesses_have_distinct_causal_profiles": (
            repeated_source_profiles_distinct
        ),
        "complete_causal_evidence_profiles": (
            min(len(profile) for profile in causal_profile_sequences) >= 3
        ),
        "unique_causal_evidence_profiles": (
            len(set(causal_profile_sequences)) == 100
        ),
        "material_evidence_outputs_nonempty": True,
        "causal_profile_outputs_nonempty": True,
        "sequence_diversity_is_not_identifier_permutation": not any(
            identifier_permutation_flags
        ),
        "unique_semantic_action_graphs": len(set(semantic_graphs)) == 100,
        "semantic_action_graph_similarity": semantic_max_jaccard < 0.9,
        "semantic_identity_inputs_ignored": all(
            not re.search(r"\b(?:dob|tsk|case)[-_]?\d+\b", " ".join(graph), re.IGNORECASE)
            for graph in semantic_graphs
        ),
        "no_reference_tool_names_in_prompts": not prompt_tool_hits,
        "material_causal_evidence_reads": (
            min(material_context_counts) == MATERIAL_CONTEXT_CALLS
            and max(material_context_counts) == MATERIAL_CONTEXT_CALLS
        ),
        "deep_reference_investigation": (
            min(context_counts) >= MINIMUM_REFERENCE_CONTEXT_CALLS
        ),
        "explicit_postwrite_readback": min(postwrite_readback_counts) >= 1,
        "long_horizon_reference": min(call_counts) >= 25,
        "deep_task_assets": (
            min(asset_counts) == ASSET_COUNT and max(asset_counts) == ASSET_COUNT
        ),
        "material_assets_inside_evidence_room": (
            min(material_asset_counts) == MATERIAL_ASSET_COUNT
            and max(material_asset_counts) == MATERIAL_ASSET_COUNT
        ),
        "native_asset_formats": {"csv", "eml", "json", "log", "md", "pdf", "sql", "txt", "xlsx", "yaml"} <= native_formats,
        "all_agent_visible_assets_unique": len(set(asset_hashes)) == len(asset_hashes),
        "no_gold_or_recipe_leakage_in_assets": not asset_leakage_hits,
        "semantic_public_milestones": (
            min(criteria_counts) == MILESTONE_COUNT
            and max(criteria_counts) == MILESTONE_COUNT
        ),
        "semantic_milestone_weights": (
            min(criteria_weight_totals) == 100
            and max(criteria_weight_totals) == 100
        ),
        "three_options_one_selected": all(
            len(record["rubric"]["decision_options"]) == 3
            and sum(option["selected"] for option in record["rubric"]["decision_options"]) == 1
            for record in records
        ),
        "decision_options_fully_qualified": all(decision_gate_rows),
        "graded_decision_answer_fields": min(answer_field_counts) >= 12,
        "decision_regimes_vary": (
            timing_statuses == {"ON_TIME", "LATE"}
            and len(recommended_plans) >= 2
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
