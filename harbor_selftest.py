#!/usr/bin/env python3
"""Run every Harbor verifier standalone, exactly as an external consumer would.

Copies dist/harbor and the world OUT of the repo, solves each task with its own
reference calls through the packaged tools, then invokes the shipped verifier as
a subprocess with no repo on sys.path. If this passes, the package is a
deliverable rather than a directory that only works next to its builder.
"""
import argparse, json, pathlib, shutil, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, default=None,
                help="check only the first N tasks (the suite uses this; the full "
                     "sweep is the default)")
cli = ap.parse_args()

REPO = pathlib.Path(__file__).resolve().parent
stage = pathlib.Path(tempfile.mkdtemp(prefix="harbor_selftest_"))
shutil.copytree(REPO / "dist" / "harbor", stage / "harbor")
shutil.copytree(REPO / "world", stage / "world")

sys.path.insert(0, str(REPO))
from serve import World                                    # noqa: E402
world = World(stage / "world", str(stage / "runtime"))

tasks = [json.loads(l) for l in
         (stage / "harbor" / "tasks" / "tasks.jsonl").read_text().splitlines() if l.strip()]
if cli.limit:
    # No silent caps: say what was skipped.
    print("checking %d of %d tasks (--limit)" % (cli.limit, len(tasks)))
    tasks = tasks[:cli.limit]
by_id = {t["task_id"]: t for t in world.tasks}

ok = fail = missing = 0
free = 0                      # verifiers that accept a world nobody touched
problems = []
for t in tasks:
    tid = t["task_id"]
    v = stage / "harbor" / "verifiers" / ("verify_%s.py" % tid)
    if not v.exists():
        missing += 1; problems.append((tid, "no verifier shipped")); continue
    # half one: a pristine world must be REJECTED, or the reward is free
    pristine = world.sessions[world.create_session()]["db"]
    p = subprocess.run([sys.executable, str(v), str(pristine)], capture_output=True,
                       text=True, timeout=120, cwd=str(stage),
                       env={"PATH": "/usr/bin:/bin", "HOME": str(stage)})
    try:
        if json.loads(p.stdout).get("passed") is True:
            free += 1
            problems.append((tid, "ACCEPTS AN UNTOUCHED WORLD - the reward is free"))
            continue
    except Exception:
        pass

    # half two: the reference solution must be ACCEPTED
    sid = world.create_session()
    for c in by_id[tid].get("expected_calls", []):
        world.call_tool(sid, c["tool"], c.get("args", {}))
    db = world.sessions[sid]["db"]
    # no repo on the path, no cwd inside the repo: a bare consumer
    proc = subprocess.run([sys.executable, str(v), str(db)], capture_output=True,
                          text=True, timeout=120, cwd=str(stage),
                          env={"PATH": "/usr/bin:/bin", "HOME": str(stage)})
    if proc.returncode != 0:
        fail += 1; problems.append((tid, "exit %d: %s" % (proc.returncode, proc.stderr[-160:]))); continue
    try:
        verdict = json.loads(proc.stdout)
    except Exception as e:
        fail += 1; problems.append((tid, "unparseable stdout: %s" % e)); continue
    if verdict.get("passed") is True and abs(verdict.get("score", 0) - 1.0) < 1e-9:
        ok += 1
    else:
        fail += 1
        bad = [a["name"] for a in verdict.get("assertions", []) if not a.get("passed")]
        problems.append((tid, "passed=%s score=%s failed=%s"
                         % (verdict.get("passed"), verdict.get("score"), bad[:4])))

print("harbor standalone self-test: %d/%d verifiers accept the reference solution "
      "and reject an untouched world" % (ok, len(tasks)))
print("  failures %d, missing %d, free-reward %d" % (fail, missing, free))
for tid, why in problems[:12]:
    print("  ! %-46s %s" % (tid, why))
sys.exit(0 if (fail == 0 and missing == 0 and free == 0) else 1)
