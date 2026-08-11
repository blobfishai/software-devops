#!/usr/bin/env python3
"""Consume benchmark repositories and reproduce their tasks in this world.

Parity was previously a judgement. This makes it a pipeline.

Every benchmark in the corpus ships the same five things under different names,
and a port has to carry all five or it is a paraphrase rather than a
reproduction:

    task        what the agent is asked to do
    tools       the systems it may act through
    seed data   the state those systems start in
    workflow    the ordered steps that count as doing it properly
    verifier    what is checked afterwards

TheAgentCompany puts them in `task.md`, `dependencies.yml`, `populate_data.py`,
`checkpoints.md` and `evaluator.py`. terminal-bench puts them in `task.yaml`, a
Dockerfile and a test suite. tau-bench puts them in `tools/`, `data/`, `tasks.py`,
`wiki.md` and `rules.py`. AIOpsLab puts them in an injector, a registry entry and
a per-problem `eval()`. Different shapes, same five parts.

An adapter reads one repo's native layout into a common `SourceTask`. A classifier
decides whether this world can host it, and says why not when it cannot. Nothing
is marked portable on the strength of resemblance: a port needs a substitution for
every system the source task touches, and where one does not exist that is
recorded as missing substrate rather than quietly dropped.

    python3 port.py                 # enumerate and classify everything
    python3 port.py --repo agentcompany --detail
    python3 port.py --emit          # draft world specs for portable tasks
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPOS = ROOT / "research" / "repos" / "evals"

# ---------------------------------------------------------------------------
# What each external system becomes here. A port is only honest if the
# substitute exposes the same *kind* of evidence: an issue tracker you can query
# and transition, a chat you can post to and read back, a document store you can
# search. Where this world has no counterpart the task is NOT portable, and
# saying so is the point of the table.
# ---------------------------------------------------------------------------
SUBSTITUTES = {
    "gitlab": ("github_issues + pull_requests + repo_files",
               ["github_list_issues", "list_issue_links", "open_pull_request",
                "merge_pull_request", "list_commits", "read_file"]),
    "rocketchat": ("channels + messages",
                   ["post_message", "read_channel", "list_channels"]),
    "owncloud": ("documents + confluence_pages",
                 ["search_docs", "get_document", "confluence_search",
                  "confluence_get_page"]),
    "plane": ("jira_issues + linear_issues",
              ["jira_search", "jira_get_issue", "jira_transition_issue",
               "linear_list_issues"]),
}
# Systems with no counterpart here, and no plan to build one. Naming them keeps
# "not portable" from sounding like "not yet".
NO_SUBSTITUTE = {
    "terminal": "no shell, no filesystem, no processes",
    "browser": "no rendering surface and no DOM",
    "desktop": "no window server",
    "kubernetes-live": "a real cluster to mutate, not a modelled one",
}


class SourceTask(dict):
    """One task from one repo, with provenance and the five parts."""

    @property
    def portable(self):
        return self["portability"] == "substrate_ok"


def _read(p, default=""):
    try:
        return pathlib.Path(p).read_text(errors="ignore")
    except Exception:  # noqa: BLE001
        return default


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------

def adapt_agentcompany(repo):
    """TheAgentCompany: one directory per task, five files, all five parts."""
    root = repo / "workspaces" / "tasks"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        deps = [l.strip("- ").strip() for l in _read(d / "dependencies.yml").splitlines()
                if l.strip().startswith("-")]
        checkpoints = _read(d / "checkpoints.md")
        pts = re.findall(r"\((\d+)\s*pts?\)", checkpoints)
        out.append(SourceTask({
            "source_repo": "TheAgentCompany",
            "source_path": str(d.relative_to(ROOT)),
            "id": d.name,
            "family": d.name.split("-")[0],
            "instruction": _read(d / "task.md").strip(),
            "systems": deps,
            "workflow_steps": len(re.findall(r"^## ", checkpoints, re.M)),
            "points": sum(int(x) for x in pts) if pts else None,
            "has_verifier": (d / "evaluator.py").exists(),
            "has_seed": (d / "populate_data.py").exists(),
        }))
    return out


def adapt_terminalbench(repo):
    """terminal-bench: task.yaml carries the instruction, tests/ the verifier."""
    root = repo / "original-tasks"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        y = _read(d / "task.yaml")
        m = re.search(r"instruction:\s*\|(.*?)(?=\n\w|\Z)", y, re.S)
        out.append(SourceTask({
            "source_repo": "terminal-bench",
            "source_path": str(d.relative_to(ROOT)),
            "id": d.name,
            "family": "terminal",
            "instruction": (m.group(1).strip() if m else "")[:600],
            "systems": ["terminal"],
            "workflow_steps": None,
            "points": None,
            "has_verifier": any((d / n).exists() for n in ("tests", "run-tests.sh")),
            "has_seed": (d / "Dockerfile").exists(),
        }))
    return out


def adapt_taubench(repo):
    """tau-bench: a domain ships tools, seed data, tasks, a wiki and rules."""
    root = repo / "tau_bench" / "envs"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "tools").is_dir()):
        tools = sorted(t.stem for t in (d / "tools").glob("*.py") if t.stem != "__init__")
        out.append(SourceTask({
            "source_repo": "tau-bench",
            "source_path": str(d.relative_to(ROOT)),
            "id": d.name,
            "family": "tool-use-domain",
            "instruction": "domain: %d tools, policy in wiki.md" % len(tools),
            "systems": [d.name],
            "workflow_steps": None,
            "points": None,
            "has_verifier": (d / "env.py").exists(),
            "has_seed": (d / "data").is_dir(),
            "tools": tools,
        }))
    return out


def adapt_aiopslab(repo):
    """AIOpsLab: a registry of fault families, each with an injector and eval()."""
    reg = _read(repo / "aiopslab" / "orchestrator" / "problems" / "registry.py")
    fams = sorted(set(re.findall(r"problems\.([a-z0-9_]+) import", reg)))
    out = []
    for f in fams:
        out.append(SourceTask({
            "source_repo": "AIOpsLab",
            "source_path": "research/repos/evals/microsoft__AIOpsLab/aiopslab/"
                           "orchestrator/problems/%s" % f,
            "id": f,
            "family": "fault-injection",
            "instruction": "inject %s, then detect / localize / analyse / mitigate" % f,
            "systems": ["kubernetes-live"] if "operator" in f or "node" in f else ["modelled-cluster"],
            "workflow_steps": 4,
            "points": None,
            "has_verifier": True,
            "has_seed": True,
        }))
    return out


ADAPTERS = {
    "agentcompany": ("TheAgentCompany__TheAgentCompany", adapt_agentcompany),
    "terminalbench": ("laude-institute__terminal-bench", adapt_terminalbench),
    "taubench": ("sierra-research__tau-bench", adapt_taubench),
    "aiopslab": ("microsoft__AIOpsLab", adapt_aiopslab),
}

# AIOpsLab is ported through import_corpus_tasks.py, which tracks it family by
# family against the world. Recording that here rather than re-deriving it keeps
# one source of truth for that number.
AIOPSLAB_PORTED_ELSEWHERE = True


# A declared dependency list says which SERVICES a task touches. It does not say
# whether the task also needs a shell, and many do: "clone the project to
# /workspace", "run the linter", "pip install". Those are not portable here
# however well the tracker substitutes, so the instruction text is evidence too.
NEEDS_SHELL = re.compile(
    r"\b(clone|/workspace|git clone|pip install|npm |docker |run the (linter|tests?)|"
    r"unit test|compile|build the|make |bash|shell|terminal|virtualenv|conda|"
    r"\.sh\b|localhost:\d+|curl )", re.I)

# TheAgentCompany is a whole simulated company. Its hr, finance, admin and bm
# families are about running a business, not operating software. They are not
# gaps in a software-devops world, and counting them as portable inflates the
# number with work nobody should do here.
IN_DOMAIN_FAMILIES = {"sde", "pm", "qa", "ds", "ml", "example",
                      "fault-injection", "tool-use-domain", "terminal"}


def classify(task):
    """Can this world host it, and if not, exactly what is missing?

    `substrate_ok` means this world has a counterpart for every system the task
    touches. It does NOT mean the task has been ported - that is a separate
    column, because conflating the two is how a parity claim becomes a fiction.
    """
    if task.get("family") not in IN_DOMAIN_FAMILIES:
        return "out_of_domain", ("%s is about running a business rather than "
                                 "operating software" % task.get("family"))

    systems = [s for s in task.get("systems", []) if s]
    if not systems:
        return "needs_design", "no declared systems; the port has to be designed by hand"

    blocked = [s for s in systems if s in NO_SUBSTITUTE]
    if blocked:
        return "not_portable", "; ".join("%s: %s" % (s, NO_SUBSTITUTE[s]) for s in blocked)

    if NEEDS_SHELL.search(task.get("instruction", "")):
        m = NEEDS_SHELL.search(task["instruction"])
        return "not_portable", ("needs a shell or filesystem (%r in the instruction); "
                                "this world has neither" % m.group(0).strip())

    unknown = [s for s in systems if s not in SUBSTITUTES and s != "modelled-cluster"]
    if unknown:
        return "needs_substrate", "no counterpart for: %s" % ", ".join(sorted(unknown))

    if not task.get("has_verifier"):
        return "needs_design", "source ships no verifier, so there is nothing to reproduce"
    return "substrate_ok", "substitutes exist for %s" % ", ".join(systems)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=None, choices=sorted(ADAPTERS))
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--out", default="research/artifacts/port_manifest.json")
    args = ap.parse_args()

    if not REPOS.is_dir():
        print("research/repos/evals is absent; run research/clone_corpus.sh", file=sys.stderr)
        return 2

    wanted = args.repo or sorted(ADAPTERS)
    manifest, totals = [], {}
    for key in wanted:
        dirname, fn = ADAPTERS[key]
        path = REPOS / dirname
        if not path.is_dir():
            print("  %-16s repo not on disk" % key)
            continue
        tasks = fn(path)
        for t in tasks:
            t["portability"], t["portability_reason"] = classify(t)
        manifest.extend(tasks)
        counts = {}
        for t in tasks:
            counts[t["portability"]] = counts.get(t["portability"], 0) + 1
        totals[key] = (len(tasks), counts)

    print("PORTING SURFACE — what the corpus offers and what this world can host\n")
    for key, (n, counts) in totals.items():
        print("  %-16s %4d task(s)   %s" % (key, n,
              "  ".join("%s=%d" % (k, v) for k, v in sorted(counts.items()))))
    print()

    portable = [t for t in manifest if t.portable]
    print("SUBSTRATE EXISTS (not yet ported): %d" % len(portable))
    by_family = {}
    for t in portable:
        by_family.setdefault((t["source_repo"], t["family"]), []).append(t)
    for (repo, fam), ts in sorted(by_family.items()):
        print("  %-18s %-12s %3d   systems: %s"
              % (repo, fam, len(ts),
                 ", ".join(sorted({s for t in ts for s in t["systems"]}))))

    print("\nBLOCKED, and by what:")
    reasons = {}
    for t in manifest:
        if t.portable:
            continue
        reasons.setdefault((t["portability"], t["portability_reason"]), []).append(t["id"])
    for (kind, why), ids in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        print("  %-16s %4d   %s" % (kind, len(ids), why[:88]))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print("\nmanifest -> %s  (%d task(s), each with its source path)" % (out, len(manifest)))

    if args.detail:
        print("\n--- portable tasks in detail ---")
        for t in portable[:40]:
            print("\n  %s  [%s]" % (t["id"], t["source_path"]))
            print("     systems: %s | workflow steps: %s | points: %s"
                  % (", ".join(t["systems"]), t["workflow_steps"], t["points"]))
            print("     %s" % (t["instruction"][:200].replace("\n", " ")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
