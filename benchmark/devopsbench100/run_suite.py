#!/usr/bin/env python3
"""Execute the DevOpsBench-100 v3.2 semantic release qualification.

Every task is evaluated from pristine state fourteen times: an oracle run, an
exact deterministic replay, and twelve task-applicable adversarial controls. A
release passes only when all 100 oracles and replays pass and all 1,200
negative executions are rejected by the executable verifier.

Run:  python3 benchmark/devopsbench100/run_suite.py
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
import pathlib
import re
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmark.devopsbench100 import decision  # noqa: E402
from benchmark.devopsbench100.builder import RELEASE_VERSION, verification_token  # noqa: E402
from benchmark.devopsbench100.realism import CURRENT_CONTROL, SEMANTIC_MILESTONE_WEIGHTS  # noqa: E402

CONTROL_NAMES = (
    "noop",
    "shortcut",
    "state_only",
    "incomplete_read",
    "write_before_read",
    "missing_readback",
    "unauthorized_write",
    "wrong_value",
    "wrong_decision",
    "wrong_evidence",
    "wrong_answer",
    "unapproved_option",
)
TRUNCATE_RESULT_AT = 4000
EPHEMERAL_TOOL_DIRECTORY = re.compile(
    r"(?:/[^\s\"'\\]+)*/(?:ws|exercise|dob_suite)_[A-Za-z0-9_-]+"
)


def stable_trace_value(value):
    """Remove host-specific temporary directory names from public traces."""

    if isinstance(value, str):
        return EPHEMERAL_TOOL_DIRECTORY.sub("<task-workspace>", value)
    if isinstance(value, list):
        return [stable_trace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: stable_trace_value(item) for key, item in value.items()}
    return value


def load_pack_world_class(pack_dir: pathlib.Path):
    server = pack_dir / "environment" / "world" / "server.py"
    spec = importlib.util.spec_from_file_location("dob_pack_server", server)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DevOpsWorld


def _subset(actual, expected) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _subset(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_subset(left, right) for left, right in zip(actual, expected))
        )
    return actual == expected


def _matches(call: dict, selector: dict) -> bool:
    return call.get("tool") == selector.get("tool") and _subset(
        call.get("args") or {}, selector.get("args") or {}
    )


def negative_plans(reference: dict) -> dict[str, dict]:
    """Create twelve distinct attacks against one task's causal contract."""

    full = deepcopy(reference["expected_calls"])
    contract = reference["trace_contract"]
    source = deepcopy(
        contract.get("source_execution_calls", reference["source_expected_calls"])
    )
    case = reference["case_contract"]
    context_count = int(contract["reference_context_call_count"])
    reference_context = contract["reference_context_calls"]
    required = contract["required_context_calls"]
    mutation_tools = set(contract["source_mutation_tools"])
    decision_record = deepcopy(contract["decision_record_call"])
    postwrite_readbacks = deepcopy(contract["postwrite_readback_calls"])
    handoff = deepcopy(contract["handoff_call"])
    readback = deepcopy(contract["readback_call"])

    if full[:context_count] != reference_context:
        raise ValueError("reference context prefix does not match trace contract")
    if full[context_count:context_count + len(source)] != source:
        raise ValueError("reference source workflow does not match trace contract")
    decision_index = context_count + len(source)
    if full[decision_index] != decision_record:
        raise ValueError("reference decision record does not match trace contract")
    postwrite_start = decision_index + 1
    postwrite_end = postwrite_start + len(postwrite_readbacks)
    if full[postwrite_start:postwrite_end] != postwrite_readbacks:
        raise ValueError("reference post-write readbacks do not match trace contract")
    handoff_index = postwrite_end
    if not _matches(full[handoff_index], handoff):
        raise ValueError("reference handoff position drifted")

    state_only_source = [
        deepcopy(call) for call in source if call["tool"] in mutation_tools
    ]
    if not state_only_source:
        raise ValueError("state_only control needs at least one source mutation")

    incomplete = deepcopy(full)
    removable = min(
        required,
        key=lambda selector: sum(
            _matches(call, selector) for call in full[:context_count]
        ),
    )
    incomplete = [
        call
        for index, call in enumerate(incomplete)
        if index >= context_count or not _matches(call, removable)
    ]

    reordered = deepcopy(full)
    first_mutation = next(
        i
        for i in range(context_count, context_count + len(source))
        if reordered[i]["tool"] in mutation_tools
    )
    reordered.insert(0, reordered.pop(first_mutation))

    if not _matches(full[-1], readback):
        raise ValueError("reference does not end with the contracted handoff readback")
    no_readback = [
        call
        for index, call in enumerate(deepcopy(full))
        if not (postwrite_start <= index < postwrite_end)
        and index != len(full) - 1
    ]
    if not postwrite_readbacks:
        raise ValueError("reference must contain provider post-write readbacks")

    wrong_value = deepcopy(full)
    if not _matches(wrong_value[handoff_index], handoff):
        raise ValueError("reference handoff position drifted")
    wrong_value[handoff_index]["args"]["body"] = (
        "Unsupported completion claim: the case evidence was not reopened or verified."
    )

    wrong_decision_source = [
        deepcopy(call) for call in source if call["tool"] not in mutation_tools
    ]
    wrong_decision = [
        *deepcopy(reference_context),
        *wrong_decision_source,
        decision_record,
        handoff,
        readback,
    ]

    wrong_evidence = deepcopy(full)
    wrong_evidence = [
        call
        for index, call in enumerate(wrong_evidence)
        if index >= context_count or not _matches(call, removable)
    ]
    wrong_evidence.insert(
        0,
        {"tool": "jira_search", "args": {"project": "ENG"}},
    )

    # Every operational step is right, but the decision record ignores the
    # reservation: usable capacity and the gap are wrong intermediate values.
    wrong_answer = deepcopy(full)
    wrong_answer[decision_index]["args"]["answer"] = json.dumps(
        decision.tampered_answer(case), sort_keys=True, separators=(",", ":")
    )

    # Every operational step is right, but the record and the handoff select
    # the plan that needs approval beyond the change approval.
    unapproved_option = deepcopy(full)
    unapproved_option[decision_index]["args"]["answer"] = json.dumps(
        decision.unapproved_answer(case), sort_keys=True, separators=(",", ":")
    )
    unapproved_option[handoff_index]["args"]["body"] = decision.unapproved_handoff_body(
        case, CURRENT_CONTROL
    )

    controls = {
        "noop": {"calls": []},
        "shortcut": {"calls": source},
        "state_only": {"calls": [*state_only_source, handoff, readback]},
        "incomplete_read": {"calls": incomplete},
        "write_before_read": {"calls": reordered},
        "missing_readback": {"calls": no_readback},
        "unauthorized_write": {"calls": full, "tamper_frozen_state": True},
        "wrong_value": {"calls": wrong_value},
        "wrong_decision": {"calls": wrong_decision},
        "wrong_evidence": {"calls": wrong_evidence},
        "wrong_answer": {"calls": wrong_answer},
        "unapproved_option": {"calls": unapproved_option},
    }
    if tuple(controls) != CONTROL_NAMES:
        raise AssertionError("negative-control registry drifted")
    reference_json = json.dumps(full, sort_keys=True)
    for name, control in controls.items():
        if (
            not control.get("tamper_frozen_state")
            and json.dumps(control["calls"], sort_keys=True) == reference_json
        ):
            raise ValueError(f"{name} control is identical to the oracle")
    return controls


def execute(
    pack_dir: pathlib.Path,
    calls: list[dict],
    task_id: str,
    trace_destination: pathlib.Path | None = None,
    *,
    tamper_frozen_state: bool = False,
):
    """Run one episode against a fresh copy of the pack's world."""

    DevOpsWorld = load_pack_world_class(pack_dir)
    world_dir = pack_dir / "environment" / "world"
    with tempfile.TemporaryDirectory(prefix="dob_suite_") as temporary:
        world = DevOpsWorld(
            world_dir, pathlib.Path(temporary) / "state", task_id=task_id
        )
        trace = []
        for call in calls:
            result = world.call_tool(call["tool"], call.get("args", {}))
            if trace_destination is not None:
                text = json.dumps(
                    stable_trace_value(result), ensure_ascii=False, sort_keys=True
                )
                if len(text) > TRUNCATE_RESULT_AT:
                    text = text[:TRUNCATE_RESULT_AT] + "...[truncated]"
                trace.append(
                    {
                        "tool": call["tool"],
                        "args": call.get("args", {}),
                        "ok": not DevOpsWorld._is_structured_error(result),
                        "result": text,
                    }
                )
        if tamper_frozen_state:
            with sqlite3.connect(world.db) as connection:
                channel = connection.execute(
                    "SELECT channel FROM channels ORDER BY channel LIMIT 1"
                ).fetchone()
                if channel is None:
                    raise ValueError("channels table is unexpectedly empty")
                connection.execute(
                    "UPDATE channels SET purpose=purpose || ? WHERE channel=?",
                    (" [unauthorized negative-control mutation]", channel[0]),
                )
        token = verification_token(pack_dir.name)
        wrong_token_rejected = False
        try:
            world.verify("not-the-token")
        except PermissionError:
            wrong_token_rejected = True
        report = world.verify(token)
        if trace_destination is not None:
            trace_destination.parent.mkdir(parents=True, exist_ok=True)
            with trace_destination.open("w", encoding="utf-8") as stream:
                for step in trace:
                    stream.write(
                        json.dumps(step, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                stream.write(
                    json.dumps(
                        {
                            "verdict": {
                                "passed": report.get("passed"),
                                "reward": report.get("reward"),
                                "score": report.get("score"),
                            }
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
    return report, wrong_token_rejected


def run(release: pathlib.Path) -> dict:
    tasks_root = release / "harbor" / "tasks"
    hf_root = release / "huggingface"
    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir())
    if len(task_dirs) != 100:
        raise ValueError(f"expected 100 packs, found {len(task_dirs)}")

    oracle_passes = 0
    determinism_matches = 0
    token_gate_passes = 0
    false_accepts = {name: 0 for name in CONTROL_NAMES}
    applicable = {name: 0 for name in CONTROL_NAMES}
    task_results = []
    executions = 0

    for pack_dir in task_dirs:
        bench_id = pack_dir.name
        reference = json.loads(
            (pack_dir / "solution" / "reference.json").read_text()
        )
        task_id = reference["task_id"]
        ref_calls = reference["expected_calls"]

        first, wrong_rejected = execute(
            pack_dir,
            ref_calls,
            task_id,
            trace_destination=hf_root / "trajectories" / f"{bench_id}.jsonl",
        )
        second, _ = execute(pack_dir, ref_calls, task_id)
        executions += 2
        oracle_ok = bool(first.get("passed")) and first.get("reward") == 1.0
        oracle_passes += int(oracle_ok)
        deterministic = first == second
        determinism_matches += int(deterministic)
        token_gate_passes += int(wrong_rejected)

        negatives = {}
        for name, control in negative_plans(reference).items():
            report, _ = execute(
                pack_dir,
                control["calls"],
                task_id,
                tamper_frozen_state=control.get("tamper_frozen_state", False),
            )
            executions += 1
            applicable[name] += 1
            accepted = bool(report.get("passed"))
            false_accepts[name] += int(accepted)
            negatives[name] = {
                "passed": accepted,
                "failed_checks": sorted(
                    assertion["name"]
                    for assertion in report.get("assertions", [])
                    if not assertion["passed"]
                ),
            }

        task_results.append(
            {
                "bench_id": bench_id,
                "source_task_id": task_id,
                "oracle_passed": oracle_ok,
                "oracle_reward": first.get("reward"),
                "oracle_score": first.get("score"),
                "oracle_points": first.get("points"),
                "semantic_weights": first.get("semantic_weights"),
                "semantic_milestones": {
                    milestone["id"]: {
                        "passed": milestone["passed"],
                        "points": milestone["points"],
                        "weight": milestone["weight"],
                    }
                    for milestone in first.get("milestones", [])
                },
                "oracle_successful_tool_calls": first.get("successful_tool_calls"),
                "oracle_report_sha256": first.get("report_sha256"),
                "second_oracle_report_sha256": second.get("report_sha256"),
                "deterministic_replay_match": deterministic,
                "wrong_token_rejected": wrong_rejected,
                "negative_executions": negatives,
            }
        )
        print(
            "[%3d/100] %-44s oracle=%s det=%s gate=%s negatives=%s"
            % (
                len(task_results),
                bench_id,
                oracle_ok,
                deterministic,
                wrong_rejected,
                {key: value["passed"] for key, value in negatives.items()},
            ),
            flush=True,
        )

    expected_executions = len(task_dirs) * (2 + len(CONTROL_NAMES))
    report = {
        "schema_version": "3.0",
        "benchmark": "DevOpsBench-100",
        "version": RELEASE_VERSION,
        "task_count": len(task_dirs),
        "metric": {
            "name": "DevOpsBench semantic causal completion",
            "milestones_per_task": len(SEMANTIC_MILESTONE_WEIGHTS),
            "points_per_task": 100,
            "pass_rule": "all semantic milestones pass",
        },
        "executions": executions,
        "expected_executions": expected_executions,
        "oracle": {
            "executions": len(task_dirs),
            "passes": oracle_passes,
            "failures": len(task_dirs) - oracle_passes,
        },
        "determinism": {
            "replays": len(task_dirs),
            "exact_report_matches": determinism_matches,
            "mismatches": len(task_dirs) - determinism_matches,
        },
        "verify_token_gate": {
            "wrong_token_rejections": token_gate_passes,
            "failures": len(task_dirs) - token_gate_passes,
        },
        "negative_controls": {
            name: {
                "applicable_executions": applicable[name],
                "false_accepts": count,
                "correct_rejections": applicable[name] - count,
            }
            for name, count in false_accepts.items()
        },
        "release_passed": (
            executions == expected_executions
            and oracle_passes == len(task_dirs)
            and determinism_matches == len(task_dirs)
            and token_gate_passes == len(task_dirs)
            and all(applicable[name] == len(task_dirs) for name in CONTROL_NAMES)
            and not any(false_accepts.values())
        ),
        "task_results": task_results,
    }
    for target in (
        release / "reports" / "qualification.json",
        hf_root / "reports" / "qualification.json",
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if report["release_passed"]:
        from benchmark.devopsbench100.finalize import seal

        seal(release)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "release_passed",
                    "executions",
                    "expected_executions",
                    "oracle",
                    "determinism",
                    "verify_token_gate",
                    "negative_controls",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        type=pathlib.Path,
        default=ROOT / "dist" / "devopsbench-100",
    )
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args().release)
    raise SystemExit(0 if result["release_passed"] else 1)
