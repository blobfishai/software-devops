#!/usr/bin/env python3
"""Summarise an eval run: where a model sits against the world, and how it fails.

A pass rate says whether a model cleared the bar. It does not say which bar. This
reads an eval_model report and answers the three questions that decide whether a
world is measuring anything:

  * Where is the boundary? PF by category, ordered, so the families a model
    clears and the families it cannot are visible separately.
  * How does it fail? The dimension a failure lands in matters more than the
    count: correctness means it got the engineering wrong; deployment means it
    got the engineering right and the procedure wrong.
  * What is not attributable? Harness and environment episodes are excluded from
    the pass rate, so they are reported rather than silently dropped.

    python3 analyse_run.py research/deepseek_full.json [more_shards.json ...] [run.log]

Reports written before failed_checks existed carry only per-dimension ratios, so
an optional run log is parsed for the named assertions instead.
"""

import collections
import json
import pathlib
import sys


def load(paths):
    """One report, or several shards of one run merged back together.

    Episodes are independent - each gets its own session fork - so a long sweep
    can be split across processes and rejoined. The merge refuses to combine
    shards from different worlds or different models, because a pass rate
    averaged across two worlds is not a measurement of either.
    """
    runs = [json.loads(pathlib.Path(p).read_text()) for p in paths]
    worlds = {r.get("world_id") for r in runs}
    models = {r.get("model") or r.get("policy") for r in runs}
    assert len(worlds) == 1, "shards span different worlds: %s" % worlds
    assert len(models) == 1, "shards span different models: %s" % models
    merged = dict(runs[0])
    seen, tasks = set(), []
    for r in runs:
        for t in r["tasks"]:
            if t["task_id"] in seen:
                continue          # a task evaluated twice would be counted twice
            seen.add(t["task_id"])
            tasks.append(t)
    merged["tasks"] = tasks
    return merged


def main(paths):
    run = load(paths)
    tasks = run["tasks"]
    print("%s on %s" % (run.get("model") or run.get("policy"), run.get("world_id", "?")))
    print("%d episodes, guidance=%s, split=%s\n"
          % (len(tasks), run.get("guidance"), run.get("split")))

    outcomes = collections.Counter(t.get("outcome") for t in tasks)
    scored = [t for t in tasks if t.get("outcome") in ("resolved", "agent", "capped")]
    passed = [t for t in scored if t.get("passed")]
    print("outcomes: %s" % dict(outcomes))
    if len(scored) != len(tasks):
        print("  %d episode(s) excluded as non-attributable (harness/environment)"
              % (len(tasks) - len(scored)))
    print("\nPF %.1f%% (%d/%d attributable)   PC %.1f\n"
          % (100.0 * len(passed) / max(1, len(scored)), len(passed), len(scored),
             100.0 * sum(t.get("score") or 0 for t in scored) / max(1, len(scored))))

    # --- where the boundary sits ------------------------------------------
    by_cat = collections.defaultdict(list)
    for t in scored:
        by_cat[t.get("category")].append(bool(t.get("passed")))
    print("PF by category (the boundary is where this crosses):")
    for cat, res in sorted(by_cat.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        pf = 100.0 * sum(res) / len(res)
        bar = "#" * int(round(pf / 5)) or ""
        print("  %-24s %5.1f%%  %-20s (%d/%d)" % (cat, pf, bar, sum(res), len(res)))

    by_diff = collections.defaultdict(list)
    for t in scored:
        by_diff[t.get("difficulty")].append(bool(t.get("passed")))
    print("\nPF by difficulty:")
    for d in ("easy", "medium", "hard", "expert"):
        if d in by_diff:
            r = by_diff[d]
            print("  %-8s %5.1f%%  (%d/%d)" % (d, 100.0 * sum(r) / len(r), sum(r), len(r)))

    # --- how it fails ------------------------------------------------------
    dims, checks = collections.Counter(), collections.Counter()
    for t in scored:
        if t.get("passed"):
            continue
        for a in t.get("failed_checks") or []:
            dims[a["dimension"]] += 1
            checks["%s/%s" % (a["dimension"], a["name"])] += 1
    logs = [a for a in sys.argv[1:] if not a.endswith(".json")]
    if not checks and logs:
        import re
        log = "".join(pathlib.Path(a).read_text() for a in logs)
        for d, name in re.findall(r"(correctness|deployment|quality)/([a-z0-9_]+)", log):
            dims[d] += 1
            checks["%s/%s" % (d, name)] += 1
    # a failure is only located once its dimension is known
    if not dims:
        short = [(t["task_id"], t.get("dimensions")) for t in scored if not t.get("passed")]
        if short:
            print("\nfailed tasks (per-dimension ratios only - no named checks in this report):")
            for tid, d in short[:20]:
                print("  %-42s %s" % (tid, d))
    if dims:
        print("\nfailed assertions by dimension: %s" % dict(dims))
        print("  correctness = got the engineering wrong")
        print("  deployment  = got the engineering right and the procedure wrong")
        print("\nmost common failed checks:")
        for name, n in checks.most_common(12):
            print("  %-46s %d" % (name, n))

    # --- effort ------------------------------------------------------------
    calls = [t.get("tool_calls", 0) for t in scored]
    if calls:
        won = [t.get("tool_calls", 0) for t in passed]
        lost = [t.get("tool_calls", 0) for t in scored if not t.get("passed")]
        print("\ntool calls: mean %.1f overall" % (sum(calls) / len(calls)))
        if won:
            print("            mean %.1f when it passed" % (sum(won) / len(won)))
        if lost:
            print("            mean %.1f when it failed" % (sum(lost) / len(lost)))
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.endswith(".json")]
    sys.exit(main(args or ["research/deepseek_full.json"]))
