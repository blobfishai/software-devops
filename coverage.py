#!/usr/bin/env python3
"""Per-repo coverage: what the corpus offers, what this world hosts, what is left.

"The most extensive world for this domain" is a claim, and a claim nobody can
check is worth nothing to the person receiving it. This is the instrument that
checks it. It joins two files that are produced independently:

  research/artifacts/port_manifest.json   what the corpus contains, classified
  world/tasks.json                        what this world actually ships

and reports, per source repository, the only four numbers that matter: how many
tasks exist, how many are in domain, how many this world could host, and how
many it does. The gap is printed by name, because a gap you cannot name is a
gap you will not close.

It also audits the join in the direction that can lie. A task may claim to be
ported from a source path; this checks that the path is really in the manifest.
Provenance that points nowhere is worse than no provenance, because it reads as
evidence. That check exits non-zero, so it can run in CI.

    python3 coverage.py             # the ledger
    python3 coverage.py --gap       # name every hostable task not yet ported
"""
import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "research/artifacts/port_manifest.json"
TASKS = ROOT / "world/tasks.json"

# Ported through import_corpus_tasks.py family-by-family rather than task-by-task,
# so its coverage is counted against families and is reported by that script. Its
# rows here would otherwise read as an unclosed gap that is not one.
FAMILY_PORTED = {"AIOpsLab"}


def load():
    if not MANIFEST.exists():
        sys.exit("no port manifest; run: python3 port.py")
    if not TASKS.exists():
        sys.exit("no built world; run: make build")
    return json.loads(MANIFEST.read_text()), json.loads(TASKS.read_text())


def ported_paths(tasks):
    """source_path -> [task_id], for tasks that declare where they came from."""
    out = collections.defaultdict(list)
    for t in tasks:
        if t.get("source_path"):
            out[t["source_path"]].append(t["task_id"])
    return out


def correctness_assertions(task):
    """Exactly what a task grades, ignoring how it is worded.

    Two tasks can read completely differently - one framed as a CVE triage, one
    as a latency complaint - and assert the identical thing about the identical
    scope. The instruction is not the task; the verifier is. So the fingerprint
    is the set of correctness checks, normalised for whitespace, and nothing
    else.
    """
    return tuple(sorted(
        " ".join(line.split())
        for line in task.get("vcode", "").splitlines()
        if '_c("correctness"' in line))


def duplicate_groups(tasks):
    """Tasks that grade identically, grouped. Redundancy = len(group) - 1."""
    by = collections.defaultdict(list)
    for t in tasks:
        by[correctness_assertions(t)].append(t)
    return sorted([g for g in by.values() if len(g) > 1], key=len, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", action="store_true",
                    help="name every hostable task that is not yet ported")
    ap.add_argument("--duplicates", action="store_true",
                    help="group tasks that grade identical correctness assertions")
    args = ap.parse_args()

    manifest, tasks = load()
    ported = ported_paths(tasks)
    known = {t["source_path"] for t in manifest}

    # The audit that can fail: provenance pointing at nothing.
    dangling = sorted(p for p in ported if p not in known)

    by_repo = collections.defaultdict(list)
    for t in manifest:
        by_repo[t["source_repo"]].append(t)

    print("%-18s %6s %9s %9s %8s %7s" %
          ("source", "tasks", "in-domain", "hostable", "ported", "gap"))
    print("-" * 62)
    tot = collections.Counter()
    for repo in sorted(by_repo):
        rows = by_repo[repo]
        in_domain = [t for t in rows if t["portability"] != "out_of_domain"]
        hostable = [t for t in rows if t["portability"] == "substrate_ok"]
        done = {t["source_path"] for t in hostable if t["source_path"] in ported}
        if repo in FAMILY_PORTED:
            gap = "family"
            n_done = len(hostable)
        else:
            n_done = len(done)
            gap = str(len({t["source_path"] for t in hostable}) - n_done)
        print("%-18s %6d %9d %9d %8s %7s" %
              (repo, len(rows), len(in_domain), len(hostable),
               n_done if repo not in FAMILY_PORTED else "by family", gap))
        tot["tasks"] += len(rows)
        tot["in_domain"] += len(in_domain)
        tot["hostable"] += len(hostable)
    print("-" * 62)
    print("%-18s %6d %9d %9d" %
          ("total", tot["tasks"], tot["in_domain"], tot["hostable"]))

    print("\nworld ships %d tasks; %d carry provenance to a source task."
          % (len(tasks), sum(len(v) for v in ported.values())))

    groups = duplicate_groups(tasks)
    redundant = sum(len(g) - 1 for g in groups)
    print("%d task(s) grade the same thing as another task, in %d group(s). "
          "Distinct graded outcomes: %d."
          % (redundant, len(groups), len(tasks) - redundant))
    if args.duplicates:
        for g in groups:
            print("\n  %d tasks grade identically  [%s]"
                  % (len(g), ", ".join(sorted({t["category"] for t in g}))))
            for t in g:
                print("     %-42s %s" % (t["task_id"], t["difficulty"]))
            print("     asserts: %s" % "; ".join(
                a.split('"')[3] for a in correctness_assertions(g[0])[:3]))

    if args.gap:
        print("\nhostable but not yet ported:")
        for repo in sorted(by_repo):
            if repo in FAMILY_PORTED:
                continue
            miss = sorted({t["source_path"] for t in by_repo[repo]
                           if t["portability"] == "substrate_ok"} - set(ported))
            if not miss:
                continue
            print("  %s (%d)" % (repo, len(miss)))
            for p in miss:
                print("     ", pathlib.Path(p).name)

    if dangling:
        print("\nFAIL: %d task(s) claim a source path that is not in the manifest:"
              % len(dangling), file=sys.stderr)
        for p in dangling:
            print("  %s  <- %s" % (p, ", ".join(ported[p])), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
