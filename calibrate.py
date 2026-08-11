#!/usr/bin/env python3
"""Difficulty calibration loop.

Run each task up to three times and sort it into one of three buckets:

    TOO_EASY   passed on the first attempt          -> deepen it
    FLAKY      passed some attempts, failed others  -> KEEP, this is the boundary
    TOO_HARD   failed all three attempts            -> record the failure mode

The flaky band is the point of the exercise: those tasks sit on the model's
capability boundary, so their traces show *why* it sometimes fails.

The loop is only trustworthy if it can tell a model failure from an environment
failure. Every trial is therefore screened for world-side faults - a tool that
does not exist, an internal error, a verifier that crashed rather than returned
false - and any task whose failures look environmental is reported separately as
SUSPECT rather than counted as difficulty.

    python3 calibrate.py --policy oracle              # dry-run the loop, no API
    python3 calibrate.py --model claude-sonnet-5 --category flaky_test
"""

import argparse
import collections
import json
import os
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import eval_model as EM              # noqa: E402
from serve import World              # noqa: E402

# Attribution follows METR/vivaria, which is the only benchmark in the research
# corpus that models this properly: ErrorSource = agent | server | task |
# serverOrTask | user | usageLimits, derived in SQL so it cannot drift, and an
# agent is never permitted to claim 'server'
# (research/notes/evals/METR__vivaria.md, shared/src/types.ts:430-441).
#
# The corpus's collective blind spot is that everyone else *collects* a rich
# failure vocabulary and then discards it at scoring time
# (research/notes/evals/_CROSS_CUTTING.md). We keep it.
#
# 'task' here means our world is broken; 'agent' means the model was wrong.
# A policy refusal is emphatically an agent outcome, not a task fault.
# Faults that are ALWAYS the world's fault, whoever made the call.
TASK_FAULT_MARKERS = (
    "Traceback", "InternalError", "no such table", "database is locked",
    "verifier execution failed",
    # A provider outage, rate limit or timeout is neither the model's fault nor a
    # property of the task. It belongs with the other non-attributable outcomes so
    # that a bad afternoon on someone else's API never reads as task difficulty.
    "HARNESS: provider error",
)
# Faults that are the world's fault only when a SCRIPTED policy hits them, because
# a script calls exactly what it was written to call - so an unknown tool means we
# wrote the reference solution wrong. A model generates tool names freely, so the
# same error is the agent guessing, and vivaria's rule applies: an agent is never
# permitted to attribute its own mistake to the server.
CALLER_DEPENDENT_MARKERS = (
    "unknown tool", "missing required parameter", "bad arguments for",
)
SYSTEM_FAULT_MARKERS = TASK_FAULT_MARKERS + CALLER_DEPENDENT_MARKERS   # legacy alias


def looks_environmental(transcript, verdict, caller="model"):
    """Screen a failed trial for world-side faults.

    `caller` decides whether a malformed call counts against the world or the
    agent. Getting this wrong is not cosmetic: a first calibration sweep flagged
    four tasks TASK_FAULT purely because an 8B model invented `get_alerts` and
    passed a `confidence` argument that does not exist. Those are agent errors,
    and counting them as environment failures would have sent us hunting bugs
    that were not there."""
    hits = [m for m in TASK_FAULT_MARKERS if m in transcript]
    if caller == "scripted":
        hits += [m for m in CALLER_DEPENDENT_MARKERS if m in transcript]
    err = str(verdict.get("error") or "")
    if "verifier execution failed" in err or err.startswith(("TypeError", "OperationalError")):
        hits.append("verifier crashed: %s" % err[:120])
    return hits


def failure_signature(verdict):
    """What, specifically, did the agent fail to do?"""
    failed = [a for a in verdict.get("assertions") or [] if not a["passed"]]
    return [(a["dimension"], a["name"]) for a in failed]


def run_trial(world, task, policy, api_key, model, max_turns, verbose, guidance="standard"):
    sid = world.create_session()
    if policy == "local":
        import local_backend
        stats = local_backend.run_episode(world, task, sid, model, max_turns, verbose,
                                          guidance=guidance)
    elif policy in ("deepseek", "openai"):
        import cloud_backend
        stats = cloud_backend.run_episode(world, task, sid, model, max_turns, verbose,
                                          provider=policy, guidance=guidance)
    elif policy == "model":
        stats = EM.run_model_episode(world, task, sid, api_key, model, max_turns, verbose)
    else:
        stats = EM.run_scripted_episode(world, task, sid, verbose, policy)
    verdict = world.verify(sid, task["task_id"])
    return stats, verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="world")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--policy", default="model",
                    help="model (Anthropic), deepseek/openai (native tool calling), "
                         "local (mlx_lm, no credential needed), or a scripted policy to "
                         "dry-run the loop for free")
    ap.add_argument("--category", action="append", default=None)
    ap.add_argument("--task", action="append", default=None)
    ap.add_argument("--guidance", choices=["standard", "guided"], default="standard",
                    help="standard states the outcome; guided also states the procedure. "
                         "PF should fall from guided to standard - if it does not, the world "
                         "is testing instruction-following rather than judgement")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--all-attempts", action="store_true",
                    help="run every attempt even after a first-try pass. Costs more and "
                         "is the only way to see a FLAKY band, since a task that passes "
                         "once and fails twice exits early as TOO_EASY otherwise")
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="research/calibration.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    world = World(pathlib.Path(args.world), tempfile.mkdtemp(prefix="calib_"))
    tasks = world.tasks
    if args.category:
        tasks = [t for t in tasks if t.get("category") in set(args.category)]
    if args.task:
        tasks = [t for t in tasks if t["task_id"] in set(args.task)]
    if args.limit:
        tasks = tasks[:args.limit]

    if args.policy == "local" and args.model.startswith("claude"):
        args.model = "mlx-community/Qwen3-8B-4bit"
    if args.policy in ("deepseek", "openai") and args.model.startswith("claude"):
        import cloud_backend
        args.model = cloud_backend.PROVIDERS[args.policy]["default_model"]
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if args.policy == "model" and not api_key:
        print("ANTHROPIC_API_KEY is not set. Dry-run the loop for free with:\n"
              "  python3 calibrate.py --policy naive", file=sys.stderr)
        return 2

    label = (args.model if args.policy in ("model", "local", "deepseek", "openai")
             else "policy=" + args.policy)
    print("calibrating %d task(s) against %s, %d attempts each, guidance=%s\n"
          % (len(tasks), label, args.attempts, args.guidance))

    records, buckets = [], collections.Counter()
    spend = collections.Counter()          # what the sweep actually cost, in tokens
    for task in tasks:
        tid = task["task_id"]
        print("  %-34s " % tid, end="", flush=True)
        trials, envs = [], []
        started = time.time()
        for _ in range(args.attempts):
            stats, verdict = run_trial(world, task, args.policy, api_key, args.model,
                                       args.max_turns, args.verbose, args.guidance)
            passed = bool(verdict.get("passed"))
            spend["prompt_tokens"] += stats.get("prompt_tokens", 0)
            spend["completion_tokens"] += stats.get("completion_tokens", 0)
            spend["episodes"] += 1
            trials.append({"passed": passed, "score": verdict.get("score"),
                           "tool_calls": stats["tool_calls"],
                           "failed_checks": failure_signature(verdict)})
            if not passed:
                caller = ("model" if args.policy in ("model", "local", "deepseek", "openai")
                          else "scripted")
                envs += looks_environmental(stats.get("transcript", ""), verdict, caller)
            if passed and len(trials) == 1 and not args.all_attempts:
                # A first-try pass is conclusive for "not too hard" and says nothing
                # at all about flakiness. When probing the boundary that is exactly
                # backwards: a task that passes once and fails twice is the result
                # you are hunting, and stopping at the first pass hides it.
                break
        n_pass = sum(t["passed"] for t in trials)
        # vivaria treats a budget exhaustion as 'usageLimits' - a distinct outcome,
        # never a failure. cline and OpenHands agree: capped maps to cancelled.
        capped = all(t["tool_calls"] >= args.max_turns for t in trials if not t["passed"])
        if n_pass == len(trials) and trials[0]["passed"]:
            bucket = "TOO_EASY"
        elif n_pass == 0:
            bucket = "TASK_FAULT" if envs else ("BUDGET_CAPPED" if capped else "TOO_HARD")
        else:
            bucket = "FLAKY"
        buckets[bucket] += 1

        # what the failures have in common - the failure mode
        common = collections.Counter()
        for t in trials:
            for dim, name in t["failed_checks"]:
                common["%s/%s" % (dim, name)] += 1
        records.append({"task_id": tid, "category": task.get("category"),
                        "difficulty": task.get("difficulty"), "bucket": bucket,
                        "attempts": len(trials), "passes": n_pass,
                        "mean_score": round(sum(t["score"] or 0 for t in trials) / len(trials), 3),
                        "failure_mode": common.most_common(6),
                        "environmental_signals": sorted(set(envs)),
                        "seconds": round(time.time() - started, 1)})
        print("%-11s %d/%d  %s" % (bucket, n_pass, len(trials),
                                   ", ".join(k for k, _ in common.most_common(2))))

    print("\n  %s" % "  ".join("%s=%d" % (k, v) for k, v in buckets.most_common()))
    if spend["prompt_tokens"] or spend["completion_tokens"]:
        print("  %d episodes, %.2fM prompt + %.0fK completion tokens"
              % (spend["episodes"], spend["prompt_tokens"] / 1e6,
                 spend["completion_tokens"] / 1e3))
    if buckets["TASK_FAULT"]:
        print("  !! %d task(s) failed with world-side symptoms - our bug, not difficulty; "
              "fix the environment before calling them hard" % buckets["TASK_FAULT"])
    if buckets["BUDGET_CAPPED"]:
        print("  ~~ %d task(s) hit the turn budget - cancelled, not failed"
              % buckets["BUDGET_CAPPED"])
    if buckets["FLAKY"]:
        print("  ** %d flaky task(s): the capability boundary, keep and study these"
              % buckets["FLAKY"])
    if buckets["TOO_EASY"]:
        print("  -> %d task(s) to deepen: python3 deepen_tasks.py --from %s"
              % (buckets["TOO_EASY"], args.out))

    # Provenance, because a bucket distribution is only interpretable against the
    # world that produced it. A sweep was already invalidated once by the world
    # being rebuilt underneath it, and nothing in the report would have said so.
    out = {"model": args.model if args.policy in ("model", "local", "deepseek", "openai") else None,
           "policy": args.policy, "attempts": args.attempts, "max_turns": args.max_turns,
           "guidance": args.guidance,
           "world_id": world.meta.get("world_id"),
           "world_counts": world.meta.get("counts"),
           "tasks_evaluated": len(tasks),
           "buckets": dict(buckets), "spend": dict(spend), "tasks": records}
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print("  report: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
