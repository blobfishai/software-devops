#!/usr/bin/env python3
"""Run terminal-bench tasks and report them in Harbor format.

These tasks were the largest block this world could not host, and the reason was
correct as far as it went: they need a real machine - package installs, C
compilers, virtualenvs, network services - and a simulated world should not grow
an arbitrary shell to pretend otherwise.

But "this world cannot host them" and "these tasks cannot run" are different
claims, and only the first was ever true. terminal-bench ships its own
containerised harness: every task carries a Dockerfile that builds its
environment, a tests/ directory that grades it, and a solution.sh that solves it.
This adapter drives that harness and emits results in the same Harbor shape as
everything else here, so a lab gets one result format across the whole corpus
rather than two.

The container is the point, not a workaround. Nothing model-written executes on
the host: the image is built from the task's own Dockerfile and every command
runs inside it, which is exactly the isolation the benchmark was designed around.

    python3 terminal_adapter.py --list
    python3 terminal_adapter.py --oracle analyze-access-logs
    python3 terminal_adapter.py --oracle-sweep --limit 5 --out research/runs/tb.json

`--oracle` runs the task's own solution.sh and then its tests. That is the same
gate the rest of this world uses: if the reference solution does not pass, the
adapter is wrong and the number means nothing.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
# Below this, a build is refused. Chosen because a single task's image reached
# 941MB and a sweep of six exhausted a 460GB volume's free space.
MIN_FREE_GB = 12
TASKS = (ROOT / "research" / "repos" / "evals" /
         "laude-institute__terminal-bench" / "original-tasks")


def run(cmd, timeout=900, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def free_gb():
    """Free space on the volume docker builds into."""
    import shutil as _sh
    try:
        return _sh.disk_usage("/").free / (1024 ** 3)
    except Exception:  # noqa: BLE001
        return None


def docker_ok():
    if not shutil.which("docker"):
        return False, "docker is not installed"
    p = run(["docker", "info"], timeout=60)
    return (p.returncode == 0), (p.stderr or "docker is not running").strip()[:120]


def list_tasks():
    if not TASKS.is_dir():
        return []
    return sorted(d.name for d in TASKS.iterdir()
                  if d.is_dir() and (d / "Dockerfile").exists()
                  and (d / "run-tests.sh").exists())


PYTEST_LINE = re.compile(r"(\d+) passed|(\d+) failed|(\d+) error")


def parse_tests(out):
    """terminal-bench grades with pytest by default; count what it reported."""
    passed = failed = 0
    for m in re.finditer(r"(\d+)\s+(passed|failed|error(?:s)?)", out):
        n, kind = int(m.group(1)), m.group(2)
        if kind == "passed":
            passed = max(passed, n)
        else:
            failed = max(failed, n)
    if not passed and not failed:
        # some tasks print their own summary
        if re.search(r"\bALL TESTS PASSED\b|\bOK\b\s*$", out, re.M):
            passed = 1
    return passed, failed


def run_task(name, solve=True, timeout=1800, keep=False):
    """Build the task's image, optionally run its solution, then run its tests."""
    d = TASKS / name
    if not d.is_dir():
        return {"task_id": name, "error": "no such task"}
    tag = "tbench_%s" % re.sub(r"[^a-z0-9]+", "_", name.lower())
    cont = tag + "_run"
    started = time.time()
    rec = {"task_id": name, "source_repo": "terminal-bench",
           "source_path": str(d.relative_to(ROOT)), "solved_with": "solution.sh" if solve else "none"}

    # These images are large - one task in the first sweep produced a 941MB image,
    # and six of them filled this machine's disk, which stopped every tool call
    # including the ones needed to clean up. Refuse to start rather than repeat
    # that, and remove the image afterwards rather than accumulating them.
    free = free_gb()
    if free is not None and free < MIN_FREE_GB:
        rec.update(outcome="environment",
                   error="only %.1fGB free; these images run to ~1GB each and a full "
                         "disk stops everything, so refusing to build" % free)
        return rec

    run(["docker", "rm", "-f", cont], timeout=120)
    b = run(["docker", "build", "-q", "-t", tag, str(d)], timeout=timeout)
    if b.returncode != 0:
        rec.update(outcome="environment", error="image build failed: " + b.stderr[-400:],
                   seconds=round(time.time() - started, 1))
        return rec

    # Networked on purpose. terminal-bench's own run-tests.sh installs curl and uv
    # before it can grade anything, so --network none makes every task fail at the
    # test step with the solution already correct - which is exactly what happened
    # the first time this ran, and what the oracle gate exists to catch. The
    # isolation that matters here is the container boundary: nothing model-written
    # touches the host either way.
    up = run(["docker", "run", "-d", "--name", cont, tag,
              "sh", "-c", "sleep infinity"], timeout=300)
    if up.returncode != 0:
        rec.update(outcome="environment", error="container did not start: " + up.stderr[-300:],
                   seconds=round(time.time() - started, 1))
        return rec

    try:
        run(["docker", "exec", cont, "mkdir", "-p", "/tests"], timeout=120)
        if (d / "tests").is_dir():
            run(["docker", "cp", str(d / "tests") + "/.", cont + ":/tests"], timeout=300)
        run(["docker", "cp", str(d / "run-tests.sh"), cont + ":/run-tests.sh"], timeout=120)

        if solve and (d / "solution.sh").exists():
            run(["docker", "cp", str(d / "solution.sh"), cont + ":/solution.sh"], timeout=120)
            s = run(["docker", "exec", cont, "bash", "/solution.sh"], timeout=timeout)
            rec["solution_exit"] = s.returncode

        t = run(["docker", "exec", "-e", "TEST_DIR=/tests", cont,
                 "bash", "/run-tests.sh"], timeout=timeout)
        out = (t.stdout or "") + "\n" + (t.stderr or "")
        passed, failed = parse_tests(out)
        rec.update(tests_passed=passed, tests_failed=failed,
                   passed=bool(passed and not failed),
                   outcome="resolved" if (passed and not failed) else "agent",
                   tail=out.strip()[-500:])
    except subprocess.TimeoutExpired:
        rec.update(outcome="capped", passed=False, error="timed out")
    finally:
        if not keep:
            run(["docker", "rm", "-f", cont], timeout=120)
            run(["docker", "rmi", "-f", tag], timeout=300)
    rec["seconds"] = round(time.time() - started, 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--oracle", default=None, help="run one task's own solution.sh")
    ap.add_argument("--oracle-sweep", action="store_true")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--sample", type=int, default=None,
                    help="a random sample rather than the first N. --limit takes tasks "
                         "alphabetically, which is not a sample of anything")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    names = list_tasks()
    if args.list:
        print("%d terminal-bench tasks with a Dockerfile and tests" % len(names))
        for n in names[:40]:
            print("  " + n)
        if len(names) > 40:
            print("  ... and %d more" % (len(names) - 40))
        return 0

    ok, why = docker_ok()
    if not ok:
        print("docker is required to run these tasks: %s" % why, file=sys.stderr)
        return 2

    if args.oracle:
        targets = [args.oracle]
    elif args.sample:
        import random
        random.seed(args.seed)
        targets = sorted(random.sample(names, min(args.sample, len(names))))
        print("  random sample of %d from %d, seed %d\n" % (len(targets), len(names), args.seed))
    else:
        targets = names[:args.limit]
    results = []
    for n in targets:
        print("  %-42s " % n, end="", flush=True)
        r = run_task(n, solve=True, timeout=args.timeout)
        results.append(r)
        if r.get("outcome") == "resolved":
            print("PASS  %d test(s)  %.0fs" % (r.get("tests_passed", 0), r.get("seconds", 0)))
        else:
            print("%-12s %s" % (r.get("outcome"), str(r.get("error", ""))[:70]))

    scored = [r for r in results if r.get("outcome") in ("resolved", "agent", "capped")]
    if scored:
        p = sum(1 for r in scored if r.get("passed"))
        print("\n  oracle pass rate %.0f%% (%d/%d attributable, %d environment)"
              % (100.0 * p / len(scored), p, len(scored), len(results) - len(scored)))
        print("  A reference solution that does not pass means the ADAPTER is wrong,")
        print("  not the task - the same gate the rest of this world uses.")
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"policy": "terminal-bench-oracle",
                                   "tasks": results}, indent=2) + "\n")
        print("  report -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
