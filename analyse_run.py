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

    python3 analyse_run.py research/deepseek_full.json [run.log]

Reports written before failed_checks existed carry only per-dimension ratios, so
an optional run log is parsed for the named assertions instead.
"""

import collections
import json
import pathlib
import sys


def main(path):
    run = json.loads(pathlib.Path(path).read_text())
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
    if not checks and len(sys.argv) > 2:
        import re
        log = pathlib.Path(sys.argv[2]).read_text()
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
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "research/deepseek_full.json"))
