#!/usr/bin/env python3
"""Curate the 100 DevOpsBench-100 tasks out of the 187 in world/tasks.json.

Every candidate is MEASURED, not assumed: its oracle must replay to reward 1.0
through the real world server, a pristine world must be rejected, and every
applicable scripted adversary (naive / shortcut / wrong_source, from
eval_model.py) must be rejected too.  A control is "applicable" exactly the way
tests/test_eval_harness.py defines it: only when it actually perturbs the
procedure-relevant part of the reference solution (dropping an instrumental
read is not an adversary), and wrong_source only when the policy applies at
all.  Selection then fills fixed per-category quotas, preferring curated over
wave-generated, harder difficulties, and longer reference trajectories.

Writes:
  benchmark/devopsbench100/catalog.json                the committed selection
  benchmark/devopsbench100/reports/curation-measurements.json   raw evidence

Run:  python3 benchmark/devopsbench100/curate.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from serve import World  # noqa: E402
import eval_model as EM  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

# Read-only lookups whose omission is "working from memory", not a policy
# violation.  Mirrors tests/test_eval_harness.py exactly.
INSTRUMENTAL = {"search_docs", "get_document", "get_ci_run", "list_migrations",
                "get_traffic_stats"}

DIFF_RANK = {"expert": 3, "hard": 2, "medium": 1, "easy": 0}

# Category quotas.  Small flagship families ship whole; the change-shipping
# families ship whole (they are the deepest, 14-19 call trajectories); the
# diagnostic families are sampled hard-first with aiops_detection capped well
# under the ~15 ceiling so breadth-wave permutations do not crowd out depth.
FULL_CATEGORIES = [
    "judgement", "human_gated", "horizon", "handover", "workspace",
    "code_implementation",
    "error_rate_reduction", "latency_optimization", "feature_flag",
    "security_incident", "api_migration", "multi_service_rollout",
    "flaky_test", "reconciliation",
]
# Two reconciliation tasks are excluded by measurement (they accept the
# wrong_source adversary), so the diagnostic quotas absorb the two freed slots.
QUOTAS = {
    "cross_system": 8,
    "attribution": 7,
    "aiops_analysis": 6,
    "aiops_localization": 5,
    "aiops_detection": 5,
}


def is_wave(task_id: str) -> bool:
    return task_id.startswith(("tsk_w1_", "tsk_w2_", "tsk_w3_", "tsk_w4_",
                               "tsk_w5_", "tsk_w6_"))


def procedure_relevant(calls):
    return json.dumps([c for c in calls if c["tool"] not in INSTRUMENTAL],
                      sort_keys=True)


def episode(world: World, calls):
    """Replay a scripted call list in a fresh session; return (verdict, db)."""
    sid = world.create_session()
    for c in calls:
        world.call_tool(sid, c["tool"], c.get("args", {}))
    verdict = None
    return sid, verdict


def run_and_verify(world: World, task, calls):
    sid = world.create_session()
    for c in calls:
        world.call_tool(sid, c["tool"], c.get("args", {}))
    verdict = world.verify(sid, task["task_id"])
    # free the 827KB session fork immediately; 187 tasks x 5 episodes adds up
    sess = world.sessions.pop(sid)
    sess["db"].unlink(missing_ok=True)
    return verdict


def measure(world: World, task) -> dict:
    tid = task["task_id"]
    ref = task.get("expected_calls", [])
    out = {"task_id": tid, "category": task["category"],
           "difficulty": task["difficulty"], "origin": task.get("origin", ""),
           "wave": is_wave(tid), "expected_calls": len(ref)}

    pristine = run_and_verify(world, task, [])
    out["pristine_rejected"] = not pristine.get("passed")

    oracle = run_and_verify(world, task, ref)
    out["oracle_passed"] = bool(oracle.get("passed")) and oracle.get("reward") == 1.0

    controls = {}
    ref_proc = procedure_relevant(ref)

    naive = EM.naive_calls(task)
    if procedure_relevant(naive) != ref_proc:
        v = run_and_verify(world, task, naive)
        controls["naive"] = {"applicable": True, "passed": bool(v.get("passed"))}
    else:
        controls["naive"] = {"applicable": False}

    shortcut = EM.shortcut_calls(task)
    if json.dumps(shortcut, sort_keys=True) != json.dumps(ref, sort_keys=True):
        v = run_and_verify(world, task, shortcut)
        controls["shortcut"] = {"applicable": True, "passed": bool(v.get("passed"))}
    else:
        controls["shortcut"] = {"applicable": False}

    wrong = EM.wrong_source_calls(task)
    if wrong is not None:
        v = run_and_verify(world, task, wrong)
        controls["wrong_source"] = {"applicable": True, "passed": bool(v.get("passed"))}
    else:
        controls["wrong_source"] = {"applicable": False}

    out["controls"] = controls
    out["control_clean"] = (out["pristine_rejected"] and not any(
        c.get("passed") for c in controls.values() if c["applicable"]))
    return out


def select(rows: list[dict]) -> list[dict]:
    eligible = [r for r in rows if r["oracle_passed"] and r["control_clean"]]
    by_cat: dict[str, list[dict]] = {}
    for r in eligible:
        by_cat.setdefault(r["category"], []).append(r)

    def rank(r):
        return (r["wave"],                     # curated before wave-generated
                -DIFF_RANK.get(r["difficulty"], 0),
                -r["expected_calls"],
                r["task_id"])

    chosen: list[dict] = []
    for cat in FULL_CATEGORIES:
        pool = sorted(by_cat.get(cat, []), key=rank)
        chosen.extend(pool)
    for cat, quota in QUOTAS.items():
        pool = sorted(by_cat.get(cat, []), key=rank)
        chosen.extend(pool[:quota])
    if len(chosen) != 100:
        raise SystemExit("selection produced %d tasks, wanted 100 - adjust "
                         "quotas (eligible per category: %s)"
                         % (len(chosen), {c: len(v) for c, v in sorted(by_cat.items())}))
    ids = [r["task_id"] for r in chosen]
    if len(set(ids)) != 100:
        raise SystemExit("duplicate selection")
    return chosen


def rationale(r: dict) -> list[str]:
    tags = [r["category"], r["difficulty"], "%d-call-oracle" % r["expected_calls"]]
    tags.append("wave-generated" if r["wave"] else
                ("ported" if r["origin"] == "ported" else "curated"))
    if r["category"] in FULL_CATEGORIES:
        tags.append("category-shipped-whole")
    else:
        tags.append("hardest-of-category-quota")
    applicable = [k for k, v in r["controls"].items() if v["applicable"]]
    tags.append("controls-rejected:" + (",".join(sorted(applicable)) + ",pristine"
                                        if applicable else "pristine"))
    return tags


def slug(task_id: str) -> str:
    return task_id.removeprefix("tsk_").replace("_", "-")


def main() -> int:
    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    runtime = tempfile.mkdtemp(prefix="dob_curate_")
    world = World(ROOT / "world", runtime)

    rows = []
    for i, task in enumerate(tasks, 1):
        row = measure(world, task)
        rows.append(row)
        flag = "" if row["oracle_passed"] and row["control_clean"] else "  <-- NOT CLEAN"
        print("[%3d/187] %-46s oracle=%s clean=%s%s"
              % (i, row["task_id"], row["oracle_passed"], row["control_clean"], flag),
              flush=True)

    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "curation-measurements.json").write_text(
        json.dumps({"schema_version": "1.0", "measured_tasks": len(rows),
                    "oracle_passes": sum(r["oracle_passed"] for r in rows),
                    "control_clean": sum(r["control_clean"] for r in rows),
                    "rows": rows}, indent=2, sort_keys=True) + "\n")

    chosen = select(rows)
    chosen.sort(key=lambda r: (r["category"], r["task_id"]))
    catalog = []
    for index, r in enumerate(chosen, 1):
        catalog.append({
            "index": index,
            "bench_id": "dob100-%03d-%s" % (index, slug(r["task_id"])),
            "task_id": r["task_id"],
            "category": r["category"],
            "difficulty": r["difficulty"],
            "expected_calls": r["expected_calls"],
            "rationale": rationale(r),
        })
    (HERE / "catalog.json").write_text(json.dumps({
        "schema_version": "1.0",
        "benchmark": "DevOpsBench-100",
        "source_world": "world/",
        "selection_criteria": {
            "every_category_represented": True,
            "aiops_detection_cap": QUOTAS["aiops_detection"],
            "full_categories": FULL_CATEGORIES,
            "quotas": QUOTAS,
            "eligibility": "oracle reward 1.0 AND pristine rejected AND all "
                           "applicable scripted adversaries rejected",
        },
        "tasks": catalog}, indent=2, sort_keys=True) + "\n")

    cats = {}
    for c in catalog:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    print(json.dumps({"selected": len(catalog), "categories": cats,
                      "eligible": sum(r["oracle_passed"] and r["control_clean"] for r in rows)},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
