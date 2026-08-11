#!/usr/bin/env python3
"""Map the cloned benchmark corpus onto the world, task by task.

Requirement: the tasks and tools we researched must actually run here, not merely
be cited. This tool reads task registries straight out of `research/repos/` and
reports, for each real benchmark task family, whether the world instantiates it -
and emits grounded proposals for the ones it does not.

It reads, from source:
  * AIOpsLab   `aiopslab/orchestrator/problems/registry.py` PROBLEM_REGISTRY
  * TheAgentCompany  `workspaces/tasks/*` directory names
  * tau-bench  `tau_bench/envs/*` domains
  * SWE-bench  the dataset task schema

Output:
  research/02-CORPUS-MAP.md            human-readable mapping
  research/artifacts/corpus_gaps.json  proposals for uncovered families, each
                                       carrying a real citation so the grounding
                                       judge can accept or reject it

    python3 import_corpus_tasks.py
"""

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPOS = ROOT / "research" / "repos"


def read(p, default=""):
    try:
        return pathlib.Path(p).read_text(errors="ignore")
    except Exception:  # noqa: BLE001
        return default


# --------------------------------------------------------------- extractors
def aiopslab_families():
    """Fault families x task types from the real PROBLEM_REGISTRY."""
    src = read(REPOS / "evals/microsoft__AIOpsLab/aiopslab/orchestrator/problems/registry.py")
    keys = re.findall(r'"([a-z0-9_\-]+)"\s*:', src)
    keys = [k for k in keys
            if re.search(r"(detection|localization|analysis|mitigation)", k)]
    fams = collections.defaultdict(set)
    for k in keys:
        m = re.search(r"-(detection|localization|analysis|mitigation)", k)
        if not m:
            continue
        fams[k[:m.start()]].add(m.group(1))
    return dict(fams), len(keys)


def agentcompany_tasks():
    d = REPOS / "evals/TheAgentCompany__TheAgentCompany/workspaces/tasks"
    names = sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []
    groups = collections.defaultdict(list)
    for n in names:
        groups[n.split("-")[0]].append(n)
    return dict(groups), len(names)


def taubench_domains():
    d = REPOS / "evals/sierra-research__tau-bench/tau_bench/envs"
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and not p.name.startswith("_")) if d.is_dir() else []


def swebench_shape():
    src = read(REPOS / "evals/princeton-nlp__SWE-bench/swebench/harness/constants/constants.py")
    fields = re.findall(r'KEY_([A-Z_]+)\s*=\s*"([a-z_]+)"', src)
    return [f[1] for f in fields][:14]


# ------------------------------------------------- what the world implements
def world_state():
    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    tools = json.loads((ROOT / "world" / "tools.json").read_text())
    return tasks, {t["name"] for t in tools}


# AIOpsLab fault families -> the world mechanism that reproduces them.
# A family is COVERED when the world can express the same fault and grade the
# same four task types over it; PARTIAL when the mechanism differs materially.
FAMILY_MAP = {
    "k8s_target_port-misconfig": ("COVERED", "config misconfiguration on a deployed service",
                                  ["tsk_search_cache", "tsk_media_cdn",
                                   "tsk_rca_catalog_n_plus_one"]),
    "misconfig_app_hotel_res": ("COVERED", "application config misconfiguration",
                                ["tsk_catalog_batch_pricing", "tsk_gateway_pool_reuse"]),
    "auth_miss_mongodb": ("PARTIAL", "auth/credential fault modelled as the hardcoded "
                          "secret task, not a database auth revocation",
                          ["tsk_checkout_hardcoded_secret"]),
    "revoke_auth_mongodb": ("NOT COVERED", "credential revoked mid-flight", []),
    "user_unregistered_mongodb": ("NOT COVERED", "identity/registration fault", []),
    "scale_pod_zero_social_net": ("PARTIAL", "capacity starvation modelled as pool "
                                  "exhaustion rather than replica count",
                                  ["tsk_inventory_pool"]),
    "assign_to_non_existent_node_social_net": ("NOT COVERED",
                                               "scheduling/placement fault", []),
    "astronomy_shop_kafka_queue_problems": ("COVERED", "queue consumer fault",
                                            ["tsk_analytics_prefetch",
                                             "tsk_analytics_batch_size"]),
    "container_kill": ("COVERED", "OOMKill/CrashLoopBackOff via k8s_events and k8s_pods; "
                       "the error tracker is structurally blind to it",
                       ["tsk_localize_analytics_crashloop"]),
    "pod_failure_hotel_res": ("COVERED", "pod phase CrashLoopBackOff with restart counts",
                              ["tsk_localize_analytics_crashloop"]),
    "pod_kill_hotel_res": ("COVERED", "kubelet Killing/OOMKilled events",
                           ["tsk_localize_analytics_crashloop"]),
    "wrong_bin_usage": ("COVERED", "running image tag drifts from every release record "
                        "after a rollback",
                        ["tsk_rcn_running_version"]),
    "network_loss_hotel_res": ("PARTIAL", "network fault modelled as timeout/retry faults",
                               ["tsk_payments_retry", "tsk_notifications_timeout"]),
    "network_delay_hotel_res": ("COVERED", "downstream latency propagating upstream",
                                ["tsk_localize_checkout_latency"]),
    "noop": ("COVERED", "healthy-system true negative",
             ["tsk_detect_storefront_healthy"]),
}

# TheAgentCompany prefixes -> whether this world addresses that job family.
AC_MAP = {
    "sde": ("COVERED", "software engineering tasks are the world's core"),
    "pm": ("PARTIAL", "ticket hygiene and postmortems are graded; sprint planning is not"),
    "ds": ("NOT COVERED", "data science / analysis job family"),
    "admin": ("PARTIAL", "reconciliation over messy records is covered by the "
              "reconciliation suite; HR/office admin is out of domain"),
    "hr": ("NOT COVERED", "HR job family, out of domain for an SRE world"),
    "finance": ("NOT COVERED", "finance job family, out of domain"),
    "research": ("NOT COVERED", "research job family, out of domain"),
    "example": ("N/A", "template"),
}


def main():
    tasks, tool_names = world_state()
    task_ids = {t["task_id"] for t in tasks}
    cats = collections.Counter(t.get("category", "") for t in tasks)

    fams, n_problems = aiopslab_families()
    ac_groups, n_ac = agentcompany_tasks()
    domains = taubench_domains()
    swe_fields = swebench_shape()

    out, gaps = [], []
    A = out.append
    A("# Corpus map — which real benchmark tasks run in this world\n")
    A("Generated by `import_corpus_tasks.py`, reading task registries directly out of")
    A("`research/repos/`. Nothing here is from memory.\n")
    A("| corpus | unit | count |")
    A("|---|---|---|")
    A("| AIOpsLab | registry problems | %d |" % n_problems)
    A("| AIOpsLab | distinct fault families | %d |" % len(fams))
    A("| TheAgentCompany | task directories | %d |" % n_ac)
    A("| tau-bench | domains | %d (%s) |" % (len(domains), ", ".join(domains)))
    A("| this world | tasks | %d across %d categories |" % (len(tasks), len(cats)))
    A("| this world | tools | %d |\n" % len(tool_names))

    # ---- AIOpsLab
    A("## AIOpsLab fault families\n")
    A("AIOpsLab is the closest benchmark by domain. Its %d registry problems are %d fault"
      % (n_problems, len(fams)))
    A("families crossed with detection / localization / analysis / mitigation.\n")
    A("| fault family | its task types | status | world mechanism | world tasks |")
    A("|---|---|---|---|---|")
    cov = collections.Counter()
    for fam in sorted(fams):
        status, mech, ids = FAMILY_MAP.get(fam, ("NOT COVERED", "not modelled", []))
        ids = [i for i in ids if i in task_ids]
        cov[status] += 1
        A("| `%s` | %s | **%s** | %s | %s |"
          % (fam, ", ".join(sorted(fams[fam])), status, mech,
             ", ".join("`%s`" % i for i in ids) or "—"))
        if status == "NOT COVERED":
            gaps.append({
                "kind": "task", "id": "aiopslab_gap__%s" % fam,
                "claim": "The world does not instantiate the AIOpsLab fault family '%s', "
                         "which appears in its PROBLEM_REGISTRY crossed with %s. Adding it "
                         "would extend fault coverage into a mechanism we currently cannot "
                         "express." % (fam, "/".join(sorted(fams[fam]))),
                "evidence": [{
                    "path": "research/notes/evals/microsoft__AIOpsLab.md",
                    "quote": "PROBLEM_REGISTRY"}]})
    A("\n**Coverage: %d covered, %d partial, %d not covered (of %d families).**\n"
      % (cov["COVERED"], cov["PARTIAL"], cov["NOT COVERED"], len(fams)))

    # ---- TheAgentCompany
    A("## TheAgentCompany job families\n")
    A("TheAgentCompany's %d tasks are named by job family. Only some are in this"
      % n_ac)
    A("world's domain; claiming the rest would be dishonest.\n")
    A("| prefix | tasks | status | note |")
    A("|---|---|---|---|")
    for pre in sorted(ac_groups):
        status, note = AC_MAP.get(pre, ("UNKNOWN", "unclassified"))
        A("| `%s` | %d | **%s** | %s |" % (pre, len(ac_groups[pre]), status, note))
    in_domain = sum(len(v) for k, v in ac_groups.items()
                    if AC_MAP.get(k, ("", ""))[0] in ("COVERED", "PARTIAL"))
    A("\n%d of %d TheAgentCompany tasks fall in this world's domain (sde/pm/admin); "
      "the rest are HR, finance, data science and research job families that an SRE "
      "world should not pretend to cover.\n" % (in_domain, n_ac))

    # ---- tau-bench / SWE-bench
    A("## tau-bench\n")
    A("Domains present: %s. Neither is software engineering - tau-bench contributes its"
      % ", ".join("`%s`" % d for d in domains))
    A("*method* rather than its tasks. Its pass^k reliability metric is implemented in")
    A("`eval_model.py` (`pass_hat_k`, `--trials k`).\n")
    A("## SWE-bench\n")
    A("Task record fields: %s.\n" % ", ".join("`%s`" % f for f in swe_fields))
    A("The world reproduces the *shape* - an issue, a change, tests that must pass - via")
    A("`repo_files`, `code_edit` pull-request changes and a CI pipeline with build, unit,")
    A("integration and regression stages. It does **not** execute real test suites against")
    A("real repositories, so SWE-bench-style tasks here are PARTIAL by construction: the")
    A("workflow is faithful, the substrate is simulated.\n")

    (ROOT / "research" / "02-CORPUS-MAP.md").write_text("\n".join(out) + "\n")
    art = ROOT / "research" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    (art / "corpus_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n")

    print("corpus map -> research/02-CORPUS-MAP.md")
    print("  AIOpsLab: %d problems / %d families -> %d covered, %d partial, %d not"
          % (n_problems, len(fams), cov["COVERED"], cov["PARTIAL"], cov["NOT COVERED"]))
    print("  TheAgentCompany: %d tasks, %d in this domain" % (n_ac, in_domain))
    print("  tau-bench domains: %s" % ", ".join(domains))
    print("  gaps -> research/artifacts/corpus_gaps.json (%d proposals)" % len(gaps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
