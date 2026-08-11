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


def repair_attribution(tasks):
    """Undo a known misattribution in reports written before it was fixed.

    `classify_outcome` briefly searched the *transcript* for harness symptoms, and
    one of those symptoms was the string "API ". The world ships a status page
    post titled "API latency affecting some customers" and documents called "API
    deprecation" and "API gateway", so any agent that read them had its failure
    relabelled as our outage and DELETED from the pass rate.

    The footprint is exactly recoverable: an episode is only misattributed if it
    is marked `harness` while its recorded error contains no harness or
    environment symptom at all. Those become `agent`, or `capped` when the turn
    budget was exhausted. Nothing else is touched.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from eval_model import HARNESS_MARKERS, ENVIRONMENT_MARKERS, CALLER_DEPENDENT_MARKERS
    fixed = 0
    for t in tasks:
        if t.get("outcome") != "harness":
            continue
        err = str(t.get("error") or "")
        if any(m in err for m in HARNESS_MARKERS):
            continue                                   # genuinely our infrastructure
        if any(m in err for m in ENVIRONMENT_MARKERS + CALLER_DEPENDENT_MARKERS):
            t["outcome"] = "environment"               # still excluded, but correctly
            continue
        t["outcome"] = "capped" if t.get("turns", 0) >= 30 else "agent"
        fixed += 1
    if fixed:
        print("repaired %d episode(s) misattributed to `harness` by the \"API \" marker; "
              "they are the model's failures and now count." % fixed)
    return tasks


def load(paths, expected=None):
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
            # Key on (task, trial): repeated trials of one task are distinct
            # episodes and all of them count, but the same episode appearing in
            # two shards must not be counted twice.
            key = (t["task_id"], t.get("trial", 0))
            if key in seen:
                continue
            seen.add(key)
            tasks.append(t)
    merged["tasks"] = repair_attribution(tasks)

    # No silent caps. A sharded run that quietly evaluated 77 of 83 tasks reports a
    # pass rate that looks complete and is not - and this exact thing happened: a
    # `while read` loop dropped the final line of every shard file, so six tasks
    # were never run and nothing said so.
    try:
        if expected is None:
            # No stated scope means the caller intends a full run; compare against
            # the world. A deliberate subset passes its own id set instead.
            world = json.loads((pathlib.Path(__file__).resolve().parent / "world" /
                                "tasks.json").read_text())
            expected = {t["task_id"] for t in world}
        expected = set(expected)
        got = {t["task_id"] for t in merged["tasks"]}
        missing = sorted(expected - got)
        if missing:
            print("INCOMPLETE: %d of %d tasks were never evaluated: %s%s"
                  % (len(missing), len(expected), ", ".join(missing[:6]),
                     " ..." if len(missing) > 6 else ""))
            merged["incomplete"] = missing
    except Exception:  # noqa: BLE001
        pass                      # a subset run against another world is legitimate
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

    # --- where to probe next -----------------------------------------------
    # A single attempt says pass or fail. It cannot say "sometimes", and
    # "sometimes" is the only direct evidence of where capability runs out. The
    # tasks worth spending repeats on are the near misses in both directions:
    # failures that almost passed, and passes that almost failed.
    # PF is binary over correctness and deployment only, so nearness to the PF
    # boundary is measured in those two dimensions. Ranking by PC instead filled
    # this list with tasks that passed and merely lost a quality check - not near
    # the boundary at all, since quality cannot flip a pass into a fail.
    near = []
    for t in scored:
        fr = t.get("dimension_fractions") or {}
        pf_frac = [fr[d] for d in ("correctness", "deployment") if d in fr]
        if not pf_frac:
            continue
        m = sum(pf_frac) / len(pf_frac)
        if not t.get("passed") and m >= 0.8:
            near.append((m, t["task_id"],
                         "failed with correctness+deployment at %.0f%%" % (100 * m)))
    if near:
        near.sort(reverse=True)
        print("\nboundary candidates - failures that nearly cleared correctness and "
              "deployment.\nRun these with repeats: a task that passes sometimes and "
              "fails others is the\nonly direct evidence of where capability runs out.")
        for pc, tid, why in near[:12]:
            print("  %-42s %s" % (tid, why))
        ids = " ".join("--task %s" % t for _, t, _ in near[:12])
        print("\n  python3 calibrate.py --policy deepseek --model %s \\\n    --attempts 3 %s"
              % (run.get("model") or "deepseek-v4-pro", ids))

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
