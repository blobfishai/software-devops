#!/usr/bin/env python3
"""Deepen tasks that a model solves on the first attempt.

Calibration sorts tasks into TOO_EASY / FLAKY / TOO_HARD. This tool takes the
TOO_EASY set and proposes harder variants, walking the sequence tree rather than
padding: a deeper task should require *more inference*, not more typing.

Four deepening axes, each with a different reason to be harder:

  span       more services in the causal chain, so the fix is not where the
             symptom is (3 tools becomes 10)
  ambiguity  the request no longer names the target; the agent must decide what
             "this week" or "the checkout problem" refers to
  horizon    the task continues past the fix into verification, communication
             and follow-up, so premature completion fails
  reconcile  the answer requires joining sources that disagree

Proposals are emitted as spec stubs plus a grounding artifact for
research/grounding_judge.py - a deepened task still has to justify itself
against the corpus, not merely be longer.

    python3 deepen_tasks.py --from research/calibration.json --out research/artifacts/
"""

import argparse
import json
import pathlib
import sys

AXES = {
    "span": {
        "why": "real faults are frequently one hop from the symptom; a task whose fix "
               "lives in the alarmed service tests reading, not diagnosis",
        "recipe": "move the root cause into a dependency of the alarmed service and "
                  "require the agent to traverse the dependency graph to find it",
        "adds": ["cross-service causal chain", "dependency traversal"],
    },
    "ambiguity": {
        "why": "real tickets under-specify the target; deciding what was meant is part "
               "of the work",
        "recipe": "strip the identifier from the request (no alarm id, no service name) "
                  "and leave only the customer-visible symptom, so the agent must "
                  "select the target itself",
        "adds": ["target selection", "scope judgement"],
    },
    "horizon": {
        "why": "premature completion is a documented agent failure mode; a task that "
               "ends at the fix cannot detect it",
        "recipe": "extend past the change into verification, stakeholder communication, "
                  "follow-up work and cleanup, with ordering constraints between them",
        "adds": ["post-fix verification", "communication", "follow-up record"],
    },
    "reconcile": {
        "why": "the same fact lives in several systems that disagree; trusting one "
               "source is the trap",
        "recipe": "split the evidence across two or more tools whose values differ, so "
                  "the agent must reconcile them and justify which it trusts",
        "adds": ["multi-source join", "conflict resolution"],
    },
}


def propose(rec, axis):
    tid = rec["task_id"]
    a = AXES[axis]
    return {
        "kind": "task",
        "id": "%s__%s" % (tid, axis),
        "parent": tid,
        "axis": axis,
        "category": rec.get("category"),
        "difficulty": {"medium": "hard", "hard": "expert", "expert": "expert",
                       "easy": "medium"}.get(rec.get("difficulty"), "hard"),
        "rationale": "%s solved on the first attempt (mean score %s); %s"
                     % (tid, rec.get("mean_score"), a["why"]),
        "recipe": a["recipe"],
        "adds_capabilities": a["adds"],
        "claim": "Deepen %s along the '%s' axis: %s. Justified because the calibration "
                 "loop scored it TOO_EASY (%d/%d attempts passed on first try)."
                 % (tid, axis, a["recipe"], rec.get("passes", 1), rec.get("attempts", 1)),
        "evidence": [],   # must be filled with a real corpus citation before it ships
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="research/calibration.json")
    ap.add_argument("--out", default="research/artifacts")
    ap.add_argument("--axis", action="append", default=None,
                    choices=sorted(AXES), help="restrict to these axes")
    ap.add_argument("--max-per-task", type=int, default=2)
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.exists():
        print("no calibration report at %s - run calibrate.py first" % src, file=sys.stderr)
        return 2
    report = json.loads(src.read_text())
    easy = [t for t in report["tasks"] if t["bucket"] == "TOO_EASY"]
    if not easy:
        print("nothing scored TOO_EASY in %s - no deepening needed" % src)
        return 0

    axes = args.axis or list(AXES)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    proposals = []
    for rec in easy:
        # pick the axes that fit this task's shape
        picks = [a for a in axes if not (a == "reconcile"
                                         and (rec.get("category") or "").startswith("aiops_"))]
        for axis in picks[:args.max_per_task]:
            proposals.append(propose(rec, axis))

    path = out_dir / "deepened_tasks.json"
    path.write_text(json.dumps(proposals, indent=2) + "\n")
    print("%d task(s) scored TOO_EASY -> %d deepening proposal(s)" % (len(easy), len(proposals)))
    by_axis = {}
    for p in proposals:
        by_axis[p["axis"]] = by_axis.get(p["axis"], 0) + 1
    for a, n in sorted(by_axis.items()):
        print("  %-10s %d" % (a, n))
    print("\nwritten: %s" % path)
    print("every proposal has an EMPTY evidence list on purpose - it cannot ship until")
    print("a real corpus citation is attached and it passes:")
    print("  python3 research/grounding_judge.py --check %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
