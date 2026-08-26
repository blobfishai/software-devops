#!/usr/bin/env python3
"""Qualify the built DevOpsBench-100 release by executing every pack.

For each of the 100 Harbor packs in dist/devopsbench-100/harbor/tasks this
suite instantiates the PACK's own world server code (environment/world/
server.py, loaded from the pack, not from the repo) and runs:

  1. oracle          replay solution/reference.json; verifier must accept with
                     reward 1.0 (trajectory recorded to huggingface/trajectories/)
  2. determinism     replay the oracle a second time from pristine state; the
                     two verifier reports must be exactly identical
  3. token gate      a wrong capability token must be rejected
  4. negative controls, each of which must score 0:
       pristine      a world nobody touched (applies to every task)
       naive         the policy-blind adversary from eval_model.py, where it
                     perturbs the procedure-relevant reference steps
       shortcut      the forbidden-shortcut adversary, where it differs from
                     the reference
       wrong_source  right answers read from the wrong system of record,
                     where the task pins a source of truth

Writes reports/qualification.json (release root + huggingface/reports/).

Run:  python3 benchmark/devopsbench100/run_suite.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import eval_model as EM  # noqa: E402  (scripted adversaries)
from builder import verification_token  # noqa: E402

sys.path.insert(0, str(HERE))

INSTRUMENTAL = {"search_docs", "get_document", "get_ci_run", "list_migrations",
                "get_traffic_stats"}
TRUNCATE_RESULT_AT = 4000


def procedure_relevant(calls):
    return json.dumps([c for c in calls if c["tool"] not in INSTRUMENTAL],
                      sort_keys=True)


def load_pack_world_class(pack_dir: pathlib.Path):
    server = pack_dir / "environment" / "world" / "server.py"
    spec = importlib.util.spec_from_file_location("dob_pack_server", server)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DevOpsWorld


def execute(pack_dir: pathlib.Path, calls, task_id: str,
            trace_destination: pathlib.Path | None = None):
    """Run one episode against a fresh copy of the pack's world."""
    DevOpsWorld = load_pack_world_class(pack_dir)
    world_dir = pack_dir / "environment" / "world"
    with tempfile.TemporaryDirectory(prefix="dob_suite_") as temporary:
        world = DevOpsWorld(world_dir, pathlib.Path(temporary) / "state",
                            task_id=task_id)
        trace = []
        for call in calls:
            result = world.call_tool(call["tool"], call.get("args", {}))
            if trace_destination is not None:
                text = json.dumps(result, ensure_ascii=False, sort_keys=True)
                if len(text) > TRUNCATE_RESULT_AT:
                    text = text[:TRUNCATE_RESULT_AT] + "...[truncated]"
                trace.append({"tool": call["tool"],
                              "args": call.get("args", {}),
                              "ok": not DevOpsWorld._is_structured_error(result),
                              "result": text})
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
                    stream.write(json.dumps(step, ensure_ascii=False,
                                            sort_keys=True) + "\n")
                stream.write(json.dumps(
                    {"verdict": {"passed": report.get("passed"),
                                 "reward": report.get("reward"),
                                 "score": report.get("score")}},
                    ensure_ascii=False, sort_keys=True) + "\n")
    return report, wrong_token_rejected


def run(release: pathlib.Path) -> dict:
    tasks_root = release / "harbor" / "tasks"
    hf_root = release / "huggingface"
    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir())
    if len(task_dirs) != 100:
        raise ValueError(f"expected 100 packs, found {len(task_dirs)}")

    world_tasks = {t["task_id"]: t for t in
                   json.loads((ROOT / "world" / "tasks.json").read_text())}

    oracle_passes = 0
    determinism_matches = 0
    token_gate_passes = 0
    false_accepts = {"pristine": 0, "naive": 0, "shortcut": 0, "wrong_source": 0}
    applicable = {"pristine": 0, "naive": 0, "shortcut": 0, "wrong_source": 0}
    task_results = []
    executions = 0

    for pack_dir in task_dirs:
        bench_id = pack_dir.name
        reference = json.loads(
            (pack_dir / "solution" / "reference.json").read_text())
        task = world_tasks[reference["task_id"]]
        ref_calls = reference["expected_calls"]

        first, wrong_rejected = execute(
            pack_dir, ref_calls, reference["task_id"],
            trace_destination=hf_root / "trajectories" / f"{bench_id}.jsonl")
        second, _ = execute(pack_dir, ref_calls, reference["task_id"])
        executions += 2
        oracle_ok = bool(first.get("passed")) and first.get("reward") == 1.0
        oracle_passes += int(oracle_ok)
        deterministic = first == second
        determinism_matches += int(deterministic)
        token_gate_passes += int(wrong_rejected)

        negative_plans = {"pristine": []}
        naive = EM.naive_calls(task)
        if procedure_relevant(naive) != procedure_relevant(ref_calls):
            negative_plans["naive"] = naive
        shortcut = EM.shortcut_calls(task)
        if json.dumps(shortcut, sort_keys=True) != json.dumps(ref_calls, sort_keys=True):
            negative_plans["shortcut"] = shortcut
        wrong = EM.wrong_source_calls(task)
        if wrong is not None:
            negative_plans["wrong_source"] = wrong

        negatives = {}
        for name, plan in negative_plans.items():
            report, _ = execute(pack_dir, plan, reference["task_id"])
            executions += 1
            applicable[name] += 1
            accepted = bool(report.get("passed"))
            false_accepts[name] += int(accepted)
            negatives[name] = {
                "passed": accepted,
                "failed_checks": sorted(
                    a["name"] for a in report.get("assertions", [])
                    if not a["passed"]),
            }

        task_results.append({
            "bench_id": bench_id,
            "source_task_id": reference["task_id"],
            "oracle_passed": oracle_ok,
            "oracle_reward": first.get("reward"),
            "oracle_score": first.get("score"),
            "oracle_successful_tool_calls": first.get("successful_tool_calls"),
            "oracle_report_sha256": first.get("report_sha256"),
            "second_oracle_report_sha256": second.get("report_sha256"),
            "deterministic_replay_match": deterministic,
            "wrong_token_rejected": wrong_rejected,
            "negative_executions": negatives,
        })
        print("[%3d/100] %-44s oracle=%s det=%s gate=%s negatives=%s"
              % (len(task_results), bench_id, oracle_ok, deterministic,
                 wrong_rejected,
                 {k: v["passed"] for k, v in sorted(negatives.items())}),
              flush=True)

    report = {
        "schema_version": "1.0",
        "benchmark": "DevOpsBench-100",
        "version": "1.0.0",
        "task_count": len(task_dirs),
        "executions": executions,
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
            oracle_passes == len(task_dirs)
            and determinism_matches == len(task_dirs)
            and token_gate_passes == len(task_dirs)
            and not any(false_accepts.values())
        ),
        "task_results": task_results,
    }
    for target in (release / "reports" / "qualification.json",
                   hf_root / "reports" / "qualification.json"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("release_passed", "executions", "oracle", "determinism",
                       "verify_token_gate", "negative_controls")},
                     indent=2, sort_keys=True))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=pathlib.Path,
                        default=ROOT / "dist" / "devopsbench-100")
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args().release)
    raise SystemExit(0 if result["release_passed"] else 1)
