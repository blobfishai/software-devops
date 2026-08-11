#!/usr/bin/env python3
"""Parity against the downloaded corpus, counted rather than asserted.

57 repositories were cloned and read, and notes were written for each. But only
three had their task inventories mechanically enumerated and mapped
(`import_corpus_tasks.py`: AIOpsLab, TheAgentCompany, tau-bench). The other
eighteen eval repos informed the design qualitatively and were never turned into
a checklist, so "coverage" has been a judgement rather than a count.

This walks every downloaded eval repo, finds its task inventory by a per-repo
rule, and reports the size. It separates two questions that were being run
together:

  in scope    a benchmark about operating and changing software systems. Parity
              here is a goal, and the shortfall is a to-do list.
  out of scope
              a benchmark about something else - desktop GUIs, Kaggle notebooks,
              web browsing, language-model accuracy. Parity here is NOT a goal,
              and counting it as a gap would inflate the denominator with work
              nobody should do.

Counting is honest only if the second category is named out loud, because it is
where most of the corpus's raw task count lives.

    python3 parity.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPOS = ROOT / "research" / "repos" / "evals"


def count_dirs(p, pred=None):
    p = pathlib.Path(p)
    if not p.is_dir():
        return None
    out = [d for d in p.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
    if pred:
        out = [d for d in out if pred(d)]
    return len(out)


def count_glob(p, pattern):
    p = pathlib.Path(p)
    return len(list(p.glob(pattern))) if p.is_dir() else None


# repo -> (in_scope, what its unit of work is, how to count it)
INVENTORY = {
    "microsoft__AIOpsLab": (
        True, "fault families in PROBLEM_REGISTRY",
        lambda r: 33),                                   # counted by import_corpus_tasks
    "TheAgentCompany__TheAgentCompany": (
        True, "workspace tasks (112 in this domain)",
        lambda r: count_dirs(r / "workspaces" / "tasks")),
    "sierra-research__tau-bench": (
        True, "tool-use domains",
        lambda r: count_dirs(r / "tau_bench" / "envs")),
    "laude-institute__terminal-bench": (
        True, "terminal tasks",
        lambda r: count_dirs(r / "original-tasks")),
    "princeton-nlp__SWE-bench": (
        True, "repository-fix instances (dataset, not vendored)", lambda r: None),
    "SWE-bench__SWE-smith": (
        True, "synthesised repository-fix instances (dataset)", lambda r: None),
    "microsoft__SWE-bench-Live": (
        True, "live repository-fix instances (dataset)", lambda r: None),
    "multi-swe-bench__multi-swe-bench": (
        True, "multi-language repository fixes (dataset)", lambda r: None),
    "commit-0__commit0": (
        True, "libraries rebuilt from spec", lambda r: None),
    "openai__SWELancer-Benchmark": (
        True, "freelance software tasks", lambda r: None),
    "METR__vivaria": (
        True, "run infrastructure, not a task set", lambda r: 0),
    "SWE-agent__SWE-agent": (
        True, "agent scaffold, not a task set", lambda r: 0),
    "THUDM__AgentBench": (
        True, "environments (OS, DB, KG, card, house, web, lateral, ALFWorld)",
        lambda r: count_dirs(r / "data")),
    "xlang-ai__OSWorld": (
        False, "desktop GUI tasks", lambda r: count_dirs(r / "evaluation_examples" / "examples")),
    "web-arena-x__webarena": (
        False, "web browsing tasks", lambda r: count_glob(r / "config_files", "*.json")),
    "openai__mle-bench": (
        False, "Kaggle ML competitions", lambda r: count_dirs(r / "mlebench" / "competitions")),
    "EleutherAI__lm-evaluation-harness": (
        False, "language-model accuracy tasks", lambda r: count_dirs(r / "lm_eval" / "tasks")),
    "bigcode-project__bigcode-evaluation-harness": (
        False, "code-generation accuracy tasks", lambda r: count_glob(r / "bigcode_eval" / "tasks", "*.py")),
    "stanford-crfm__helm": (
        False, "holistic LM scenarios", lambda r: None),
    "google-deepmind__mctx": (
        False, "search library, not an eval", lambda r: 0),
    "salesforce__CodeRL": (
        False, "code-generation RL, not an eval", lambda r: 0),
}

# What this world reproduces from each in-scope repo, and what it does not.
# Deliberately conservative: "reproduced" means a task in this world exercises the
# same capability against the same kind of evidence, not that it looks similar.
REPRODUCED = {
    "microsoft__AIOpsLab": (21, "fault families covered, 10 partial, 0 not "
                                "(research/02-CORPUS-MAP.md, generated)"),
    "sierra-research__tau-bench": (2, "both patterns adopted rather than the domains: "
                                      "pass^k reliability, and policy that lives in a "
                                      "knowledge base rather than the prompt"),
    "TheAgentCompany__TheAgentCompany": (26, "sde tasks ported with systems substituted "
                                            "(gitlab -> issue tracker, rocketchat -> "
                                            "channels, plane -> tickets); each records the "
                                            "source directory. 38 more sde tasks have "
                                            "substrate and are queued in port.py"),
    "laude-institute__terminal-bench": (236, "not hosted IN the world and not "
                                             "simulated: terminal_adapter.py builds each "
                                             "task's own Dockerfile, runs it, grades with "
                                             "its own tests and reports in Harbor shape. "
                                             "236 of 241 carry a Dockerfile and tests"),
    "princeton-nlp__SWE-bench": (4, "code_implementation tasks are genuinely executed "
                                    "against hidden tests, which is the shape; they are "
                                    "single functions rather than repositories"),
    "METR__vivaria": (1, "typed error attribution adopted: an agent may never blame the "
                         "server for its own mistake"),
    "SWE-agent__SWE-agent": (0, "scaffold, nothing to reproduce"),
    "THUDM__AgentBench": (0, "no environment overlaps this domain"),
}


def main():
    if not REPOS.is_dir():
        print("research/repos/evals is not present; run research/clone_corpus.sh",
              file=sys.stderr)
        return 2
    on_disk = sorted(d.name for d in REPOS.iterdir() if d.is_dir())
    world = json.loads((ROOT / "world" / "world.json").read_text())

    print("PARITY AGAINST THE DOWNLOADED EVAL CORPUS")
    print("this world: %d tasks, %d tools\n" % (world["counts"]["tasks"],
                                                world["counts"]["tools"]))

    for scope, label in ((True, "IN SCOPE — parity is a goal"),
                         (False, "OUT OF SCOPE — parity is not a goal")):
        print("=" * 78)
        print(label)
        print("=" * 78)
        for name in on_disk:
            spec = INVENTORY.get(name)
            if spec is None:
                if scope:
                    print("  %-44s NOT CLASSIFIED" % name)
                continue
            in_scope, unit, counter = spec
            if in_scope != scope:
                continue
            try:
                n = counter(REPOS / name)
            except Exception:  # noqa: BLE001
                n = None
            size = "%4d" % n if isinstance(n, int) else "   ?"
            line = "  %-44s %s  %s" % (name, size, unit)
            if scope and name in REPRODUCED:
                got, note = REPRODUCED[name]
                line += "\n      reproduced: %s — %s" % (got, note)
            elif scope:
                line += "\n      reproduced: NOT ASSESSED"
            print(line)
        print()

    missing = [n for n in on_disk if n not in INVENTORY]
    if missing:
        print("repos on disk with no inventory rule (%d): %s" % (len(missing), ", ".join(missing)))
    print("\nThe honest summary: this world was built to the shape of one blog post and "
          "then\nmapped onto the corpus afterwards. Parity was never the organising "
          "principle, and\nthe one repo with a mechanically enumerable in-domain registry "
          "— AIOpsLab — sits at\n14 of 33 families. Everything else in scope is either a "
          "dataset this world cannot\nhost, a scaffold with nothing to reproduce, or "
          "genuinely untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
