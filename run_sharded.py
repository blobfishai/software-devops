#!/usr/bin/env python3
"""Run an eval across several processes and merge the reports.

83 episodes against a cloud model takes hours sequentially, and episodes are
independent - each gets its own session fork - so the run shards cleanly. This
exists because doing it ad hoc with a shell script produced two silent failures
in one afternoon, both of the kind that leave a plausible-looking result:

  * the task list was read with `while read`, which returns false on a final line
    with no trailing newline, so the LAST task of every shard was skipped. Six of
    83 vanished with no error and no gap in the output.
  * the script was edited while it was running. A shell reads a script
    incrementally by byte offset, so the running shards resumed mid-token in the
    new text and started executing garbage.

Both are impossible here: the task list is passed as arguments, and the runner is
a single process that holds its children.

    python3 run_sharded.py --policy deepseek --model deepseek-v4-pro --shards 6
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import analyse_run

ROOT = pathlib.Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="deepseek")
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--shards", type=int, default=6)
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--guidance", default="standard", choices=["standard", "guided"])
    ap.add_argument("--task", action="append", default=None)
    ap.add_argument("--category", action="append", default=None)
    ap.add_argument("--out", default="research/sharded_run.json")
    args = ap.parse_args()

    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    ids = [t["task_id"] for t in tasks]
    if args.category:
        want = set(args.category)
        ids = [t["task_id"] for t in tasks if t.get("category") in want]
    if args.task:
        ids = [i for i in ids if i in set(args.task)]
    if not ids:
        print("no tasks selected", file=sys.stderr)
        return 2

    n = max(1, min(args.shards, len(ids)))
    # round-robin, so every shard gets a mix of categories and they finish together
    shards = [ids[i::n] for i in range(n)]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sharded_"))
    print("%d task(s) across %d shard(s) -> %s\n" % (len(ids), n, tmp))

    procs = []
    for i, sh in enumerate(shards):
        out = tmp / ("shard_%d.json" % i)
        log = tmp / ("shard_%d.log" % i)
        cmd = [sys.executable, str(ROOT / "eval_model.py"),
               "--policy", args.policy, "--model", args.model,
               "--max-turns", str(args.max_turns), "--guidance", args.guidance,
               "--out", str(out)]
        for t in sh:                       # arguments, never a file a reader can truncate
            cmd += ["--task", t]
        procs.append((i, subprocess.Popen(cmd, stdout=log.open("w"),
                                          stderr=subprocess.STDOUT), out, sh))

    failed = []
    for i, p, out, sh in procs:
        rc = p.wait()
        got = 0
        if out.exists():
            got = len(json.loads(out.read_text())["tasks"])
        print("  shard %d: exit %d, %d/%d episodes" % (i, rc, got, len(sh)))
        if rc != 0 or got != len(sh):
            failed.append(i)

    reports = [str(tmp / ("shard_%d.json" % i)) for i in range(n)
               if (tmp / ("shard_%d.json" % i)).exists()]
    if not reports:
        print("no shard produced a report; logs are in %s" % tmp, file=sys.stderr)
        return 1

    merged = analyse_run.load(reports, expected=ids)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(merged, indent=2) + "\n")
    print("\nmerged %d episode(s) -> %s" % (len(merged["tasks"]), args.out))
    if failed:
        # Loud, and non-zero: a partial run that reports a tidy pass rate is the
        # failure mode this whole file exists to prevent.
        print("shard(s) %s did not complete their assignment; logs in %s"
              % (failed, tmp), file=sys.stderr)
        return 1
    print("logs: %s" % tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
