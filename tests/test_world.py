"""World quality gates + adversarial rollouts.

The positive gates mirror what `blobfish generate` enforces for curated tasks:
vcode must fail on the pristine seed, the oracle must replay through the real
tools, and the vcode must pass afterward. The adversarial tests prove the
verifiers actually discriminate: cutting workflow corners must lose the reward.
"""

import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import pathlib

import pytest

import build_world as bw
import tasks_def
from tools_src import make_tools
from vendor_tools import make_vendor_tools

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("world_build")
    db = tmp / "environment.db"
    base_seq = bw.build_db(str(db))
    tools = make_tools() + make_vendor_tools()
    _, ns = bw.load_tools_module(tools)
    frozen, fixed_rows, audit_prefix, n_secret, secret_lit = bw.reference_baselines(str(db))
    reads_map = {}
    for t in tools:
        for tb in t.get("read_tables", []):
            reads_map.setdefault(tb, []).append(t["name"])
    tasks = tasks_def.make_tasks(base_seq, frozen, fixed_rows, audit_prefix, n_secret,
                                 secret_lit or "pk_live_none", reads_map)
    return {"tmp": tmp, "db": db, "tools": tools, "ns": ns,
            "tasks": {t["task_id"]: t for t in tasks}}


def fork(env, name):
    db = env["tmp"] / (name + ".db")
    shutil.copyfile(env["db"], db)
    return db


def call(env, db, tool, **args):
    return env["ns"][tool](db_path=str(db), **args)


def run_calls(env, db, calls):
    results = []
    for c in calls:
        r = call(env, db, c["tool"], **c.get("args", {}))
        assert not bw.is_structured_error(r), "%s errored: %s" % (c["tool"], r)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# positive gates
# ---------------------------------------------------------------------------

def test_all_task_gates(env):
    report, failures = bw.validate(list(env["tasks"].values()), env["db"],
                                   env["ns"], env["tmp"])
    assert not failures, failures
    assert all(r["accepted"] for r in report)


def test_committed_world_is_current(tmp_path):
    """Rebuilding must reproduce the committed world/ byte-for-byte (determinism
    + guards against editing build/ without re-running the builder)."""
    out = tmp_path / "world"
    subprocess.run([sys.executable, str(ROOT / "build" / "build_world.py"),
                    "--out", str(out)], check=True, capture_output=True)
    for name in ("tools.json", "tasks.json", "schema.sql", "seed.sql",
                 "world.json", "env_spec.json", "personas.json"):
        assert (out / name).read_bytes() == (ROOT / "world" / name).read_bytes(), \
            "world/%s is stale - run: python3 build/build_world.py" % name


def test_package_has_required_files():
    for name in ("env_spec.json", "environment.db", "tools.json", "tasks.json",
                 "tools_combined.py", "schema.sql", "seed.sql", "world.json"):
        assert (ROOT / "world" / name).exists(), name
    tools = json.loads((ROOT / "world" / "tools.json").read_text())
    assert isinstance(tools, list)
    compile((ROOT / "world" / "tools_combined.py").read_text(),
            "tools_combined.py", "exec")


# ---------------------------------------------------------------------------
# tool guardrails
# ---------------------------------------------------------------------------

def test_merge_requires_passing_ci(env):
    db = fork(env, "merge_guard")
    r = call(env, db, "open_pull_request", service="search", title="x",
             ticket_key="ENG-2201",
             changes=[{"change_type": "config",
                       "payload": {"key": "cache_enabled", "value": "true"}}])
    pr = r["pr_number"]
    blocked = call(env, db, "merge_pull_request", pr_number=pr)
    assert blocked["ok"] is False and "run_ci" in blocked["error"]


def test_resolve_alert_blocked_while_breaching(env):
    db = fork(env, "resolve_guard")
    r = call(env, db, "resolve_alert", alert_id=9603)
    assert r["ok"] is False and "SLO" in r["error"]


def test_ci_blocks_retiring_endpoint_with_traffic(env):
    db = fork(env, "retire_guard")
    r = call(env, db, "open_pull_request", service="api-gateway", title="retire v1",
             ticket_key="ENG-2401",
             changes=[{"change_type": "endpoint",
                       "payload": {"path": "/v1/orders", "status": "retired"}}])
    ci = call(env, db, "run_ci", pr_number=r["pr_number"])
    assert ci["status"] == "failed" and "still serving" in ci["detail"]
    blocked = call(env, db, "merge_pull_request", pr_number=r["pr_number"])
    assert blocked["ok"] is False


def test_deploy_rejects_unmerged_version(env):
    db = fork(env, "deploy_guard")
    r = call(env, db, "deploy_service", service="payments",
             environment="production", version="v9.9.9")
    assert r["ok"] is False and "unknown version" in r["error"]


def test_promote_without_canary_fails(env):
    db = fork(env, "promote_guard")
    r = call(env, db, "promote_canary", service="payments")
    assert r["ok"] is False


def test_flag_killswitch_recomputes_metrics(env):
    db = fork(env, "engine_unit")
    call(env, db, "set_feature_flag", key="instant_refunds",
         environment="production", enabled=False)
    conn = sqlite3.connect(db)
    v = conn.execute("SELECT value FROM service_metrics WHERE service='checkout' "
                     "AND environment='production' AND metric='error_rate_pct'").fetchone()[0]
    conn.close()
    assert abs(v - 0.3) < 1e-6


def test_checkout_ci_is_deterministically_flaky(env):
    """A PR's first CI attempt hits the live flake; the rerun passes."""
    db = fork(env, "flake_unit")
    pr = call(env, db, "open_pull_request", service="checkout", title="x",
              changes=[{"change_type": "config",
                        "payload": {"key": "db_pool_size", "value": "41"}}])["pr_number"]
    r1 = call(env, db, "run_ci", pr_number=pr)
    r2 = call(env, db, "run_ci", pr_number=pr)
    assert r1["status"] == "failed" and "intermittent" in r1["detail"]
    assert r2["status"] == "passed"
    assert [s["stage"] for s in r2["stages"]] == ["build", "unit", "integration", "regression"]


def test_missing_migration_fails_build_stage(env):
    """The blog's canonical failure: a schema change shipped without its migration."""
    db = fork(env, "mig_guard")
    pr = call(env, db, "open_pull_request", service="checkout", title="saved carts",
              changes=[{"change_type": "module", "payload": {"name": "saved_carts"}}])["pr_number"]
    r = call(env, db, "run_ci", pr_number=pr)
    assert r["status"] == "failed"
    build = [s for s in r["stages"] if s["stage"] == "build"][0]
    assert build["status"] == "failed" and "missing database migration" in build["detail"]


def test_deploy_blocked_until_migration_applied(env):
    db = fork(env, "mig_deploy")
    pr = call(env, db, "open_pull_request", service="checkout", title="saved carts",
              changes=[{"change_type": "module", "payload": {"name": "saved_carts"}},
                       {"change_type": "migration",
                        "payload": {"name": "0089_saved_carts"}}])["pr_number"]
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "merge_pull_request", pr_number=pr)
    blocked = call(env, db, "deploy_service", service="checkout", environment="staging")
    assert blocked["ok"] is False and "requires migration" in blocked["error"]
    call(env, db, "apply_migration", service="checkout", name="0089_saved_carts",
         environment="staging")
    ok = call(env, db, "deploy_service", service="checkout", environment="staging")
    assert ok["ok"] is True


def test_regression_stage_catches_consumer_contract(env):
    """Retiring /v1/orders while storefront-web still pins v1 fails regression."""
    db = fork(env, "regress_guard")
    call(env, db, "shift_endpoint_traffic", service="api-gateway", path="/v1/orders",
         traffic_percent=0)
    pr = call(env, db, "open_pull_request", service="api-gateway", title="retire v1",
              changes=[{"change_type": "endpoint",
                        "payload": {"path": "/v1/orders", "status": "retired"}}])["pr_number"]
    call(env, db, "run_ci", pr_number=pr)
    r = call(env, db, "run_ci", pr_number=pr)
    assert r["status"] == "failed"
    reg = [s for s in r["stages"] if s["stage"] == "regression"][0]
    assert reg["status"] == "failed" and "storefront-web" in reg["detail"]


def test_canary_assessment_flags_regression(env):
    """assess_canary compares canary against baseline and reports new breaches."""
    db = fork(env, "canary_probe")
    pr = call(env, db, "open_pull_request", service="search", title="break the cache",
              changes=[{"change_type": "config",
                        "payload": {"key": "cache_enabled", "value": "true"}}])["pr_number"]
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "merge_pull_request", pr_number=pr)
    call(env, db, "deploy_service", service="search", environment="staging")
    call(env, db, "deploy_service", service="search", environment="production",
         canary_percent=25)
    a = call(env, db, "assess_canary", service="search")
    assert a["verdict"] == "healthy" and "clears" in a["detail"]


def test_monorepo_is_readable_and_editable(env):
    db = fork(env, "repo_edit")
    hits = call(env, db, "search_code", query="pk_live_")
    assert hits and hits[0]["matches"]
    path = hits[0]["path"]
    before = call(env, db, "read_file", path=path)["content"]
    assert "pk_live_" in before
    lit = [m["text"] for m in hits[0]["matches"]][0]
    secret = [w.strip("\"'= ") for w in lit.split() if "pk_live_" in w][0].strip("\"'")
    pr = call(env, db, "open_pull_request", service="checkout", title="secret",
              changes=[{"change_type": "code_edit",
                        "payload": {"path": path, "find": secret,
                                    "replace": "secrets.get('partner_api_key')"}}])["pr_number"]
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "merge_pull_request", pr_number=pr)
    after = call(env, db, "read_file", path=path)["content"]
    assert secret not in after and "secrets.get" in after


# ---------------------------------------------------------------------------
# adversarial rollouts — corner-cutting must not be rewarded
# ---------------------------------------------------------------------------

def _replayed_with(env, task_id, mutate):
    """Copy the oracle, apply `mutate(calls)`, replay, return the DB."""
    task = env["tasks"][task_id]
    calls = copy.deepcopy(task["expected_calls"])
    calls = mutate(calls) or calls
    db = fork(env, "adv_" + task_id)
    run_calls(env, db, calls)
    return db, task


def test_direct_prod_deploy_fails_canary_assertion(env):
    def mutate(calls):
        out = []
        for c in calls:
            if c["tool"] in ("promote_canary", "assess_canary"):
                continue
            if c["tool"] == "deploy_service" and c["args"].get("environment") == "production":
                c = {"tool": "deploy_service",
                     "args": {"service": "payments", "environment": "production"}}
            out.append(c)
        return out
    db, task = _replayed_with(env, "tsk_payments_retry", mutate)
    ok, err, score = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "canary" in err
    # Horizon-SWE-PC awards partial credit: correctness and quality still score,
    # but the deployment dimension is docked, so PF fails and PC < 1.
    assert score is not None and 0.7 < score < 1.0, score


def test_skipping_staging_fails_hygiene_assertion(env):
    def mutate(calls):
        return [c for c in calls
                if not (c["tool"] == "deploy_service"
                        and c["args"].get("environment") == "staging")]
    db, task = _replayed_with(env, "tsk_payments_retry", mutate)
    ok, err, score = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "staging-first" in err
    assert score is not None and 0.0 < score < 1.0


def test_quarantining_flaky_test_does_not_pass(env):
    def mutate(calls):
        for c in calls:
            if c["tool"] == "open_pull_request":
                c["args"]["changes"][0]["payload"]["action"] = "quarantine"
        return calls
    db, task = _replayed_with(env, "tsk_flaky_checkout_idempotency", mutate)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "must be fixed" in err


def test_enabling_flag_before_deploy_fails_ordering(env):
    def mutate(calls):
        flag = [c for c in calls if c["tool"] == "set_feature_flag"][0]
        rest = [c for c in calls if c["tool"] != "set_feature_flag"]
        merge_idx = next(i for i, c in enumerate(rest)
                         if c["tool"] == "merge_pull_request")
        return rest[:merge_idx + 1] + [flag] + rest[merge_idx + 1:]
    db, task = _replayed_with(env, "tsk_express_checkout", mutate)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "BEFORE" in err


def test_rollforward_cannot_dodge_the_rollback(env):
    """Merging a trivial PR on top of the bad release does not recover latency
    (the leak is in every version >= v5.1.0), so the alert cannot be resolved."""
    db = fork(env, "adv_rollforward")
    r = call(env, db, "open_pull_request", service="api-gateway", title="bump limit",
             ticket_key="ENG-2402",
             changes=[{"change_type": "config",
                       "payload": {"key": "rate_limit_rps", "value": "600"}}])
    call(env, db, "run_ci", pr_number=r["pr_number"])
    call(env, db, "merge_pull_request", pr_number=r["pr_number"])
    call(env, db, "deploy_service", service="api-gateway", environment="staging")
    call(env, db, "deploy_service", service="api-gateway",
         environment="production", canary_percent=25)
    call(env, db, "promote_canary", service="api-gateway")
    blocked = call(env, db, "resolve_alert", alert_id=9604)
    assert blocked["ok"] is False and "SLO" in blocked["error"]


def test_resolving_without_mitigation_is_blocked(env):
    db = fork(env, "adv_no_mitigation")
    call(env, db, "acknowledge_alert", alert_id=9603)
    blocked = call(env, db, "resolve_alert", alert_id=9603)
    assert blocked["ok"] is False


def test_vcode_rejects_unrelated_blanket_mutation(env):
    """Solving payments while also resolving the search alert must fail the
    negative-control assertion."""
    task = env["tasks"]["tsk_payments_retry"]
    calls = copy.deepcopy(task["expected_calls"])
    db = fork(env, "adv_blanket")
    run_calls(env, db, calls)
    # blanket mutation: also fix+resolve search out of scope
    r = call(env, db, "open_pull_request", service="search", title="cache",
             changes=[{"change_type": "config",
                       "payload": {"key": "cache_enabled", "value": "true"}}])
    call(env, db, "run_ci", pr_number=r["pr_number"])
    call(env, db, "run_ci", pr_number=r["pr_number"])
    call(env, db, "merge_pull_request", pr_number=r["pr_number"])
    call(env, db, "deploy_service", service="search", environment="staging")
    call(env, db, "deploy_service", service="search", environment="production")
    call(env, db, "resolve_alert", alert_id=9602)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "unrelated" in err


def test_fabricated_reference_data_is_rejected(env):
    """Solving the task but also inventing world data (the platform's
    `over_repair` corruption) must lose the reward."""
    task = env["tasks"]["tsk_payments_retry"]
    db = fork(env, "adv_fabricate")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    ok, _, _ = bw.run_vcode(task["vcode"], str(db))
    assert ok, "clean oracle must pass before corrupting"
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO services(name, kind, team, tier, language, description, "
                 "repo_version) VALUES ('ghost-svc','backend','platform',3,'go','','v1.0.0')")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "scope" in err


def test_mutated_runbook_is_rejected(env):
    """Rewriting a runbook to match a shortcut must not be rewarded."""
    task = env["tasks"]["tsk_payments_retry"]
    db = fork(env, "adv_runbook")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    conn = sqlite3.connect(db)
    conn.execute("UPDATE documents SET body='no policy' WHERE doc_id=9601")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "reference data" in err


def test_tampered_audit_log_is_rejected(env):
    """Forging the append-only audit trail (how an agent would fake workflow
    ordering) must lose the reward."""
    task = env["tasks"]["tsk_loyalty_points"]
    db = fork(env, "adv_audit")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    ok, _, _ = bw.run_vcode(task["vcode"], str(db))
    assert ok, "clean oracle must pass before tampering"
    conn = sqlite3.connect(db)
    conn.execute("UPDATE audit_events SET seq = seq + 7919")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "audit log" in err


def test_rewritten_audit_history_is_rejected(env):
    task = env["tasks"]["tsk_payments_retry"]
    db = fork(env, "adv_history")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    conn = sqlite3.connect(db)
    conn.execute("UPDATE audit_events SET detail='{}' WHERE seq=1")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "rewritten" in err


def test_oracle_scores_full_credit(env):
    """Every accepted oracle must reach score 1.0 (checked as a build gate too)."""
    report, failures = bw.validate(list(env["tasks"].values()), env["db"],
                                   env["ns"], env["tmp"])
    assert not failures
    assert all(r.get("oracle_score") == 1.0 for r in report)


# ---------------------------------------------------------------------------
# AIOpsLab-style diagnostics (microsoft/AIOpsLab taxonomy reproduced here)
# ---------------------------------------------------------------------------

def test_wrong_localization_is_rejected(env):
    """Submitting the wrong responsible service must lose the reward."""
    task = env["tasks"]["tsk_localize_gateway_latency"]
    db = fork(env, "aiops_wrong_svc")
    calls = copy.deepcopy(task["expected_calls"])
    for c in calls:
        if c["tool"] == "submit_diagnosis":
            c["args"]["service"] = "search"          # plausible but wrong
    run_calls(env, db, calls)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "responsible service is api-gateway" in err


def test_wrong_fault_type_is_rejected(env):
    """Right service, wrong mechanism: root-cause analysis must still fail."""
    task = env["tasks"]["tsk_rca_payments_retry"]
    db = fork(env, "aiops_wrong_type")
    calls = copy.deepcopy(task["expected_calls"])
    for c in calls:
        if c["tool"] == "submit_diagnosis":
            c["args"]["fault_type"] = "resource_exhaustion"
            c["args"]["offending_key"] = "db_pool_size"
    run_calls(env, db, calls)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "missing_retry" in err


def test_false_positive_detection_is_rejected(env):
    """Calling a healthy service faulty must fail (true-negative case)."""
    task = env["tasks"]["tsk_detect_storefront_healthy"]
    db = fork(env, "aiops_false_pos")
    calls = copy.deepcopy(task["expected_calls"])
    for c in calls:
        if c["tool"] == "submit_diagnosis":
            c["args"].update({"fault_detected": True, "service": "storefront-web",
                              "fault_type": "misconfig"})
    run_calls(env, db, calls)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "fault_detected must be false" in err


def test_investigation_must_stay_read_only(env):
    """Mutating production during a detection task fails the deployment check."""
    task = env["tasks"]["tsk_detect_payments"]
    db = fork(env, "aiops_mutating")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    ok, _, _ = bw.run_vcode(task["vcode"], str(db))
    assert ok, "clean read-only oracle must pass"
    call(env, db, "set_feature_flag", key="instant_refunds", environment="production",
         enabled=False)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "must not change production state" in err


def test_submit_diagnosis_validates_its_taxonomy(env):
    db = fork(env, "aiops_validate")
    bad = call(env, db, "submit_diagnosis", scope="payments", fault_detected=True,
               service="payments", fault_type="gremlins")
    assert bad["ok"] is False and "fault_type must be one of" in bad["error"]
    inconsistent = call(env, db, "submit_diagnosis", scope="payments", fault_detected=True,
                        service="payments", fault_type="none")
    assert inconsistent["ok"] is False


def test_closing_the_ticket_before_the_work_is_rejected(env):
    """Ticket hygiene: marking the ticket done up front, then working, must lose
    the quality check even though the end state is identical."""
    task = env["tasks"]["tsk_payments_retry"]
    calls = copy.deepcopy(task["expected_calls"])
    close = [c for c in calls if c["tool"] == "update_ticket"][0]
    rest = [c for c in calls if c["tool"] != "update_ticket"]
    db = fork(env, "adv_close_first")
    run_calls(env, db, [rest[0], close] + rest[1:])   # close it second, before any work
    ok, err, score = bw.run_vcode(task["vcode"], str(db))
    # end state is correct, so PF still passes; the quality dimension is docked
    assert ok, "correctness and deployment are unaffected by ticket order"
    assert score is not None and score < 1.0, score


def test_instructions_do_not_leak_the_procedure(env):
    """The default prompt must state outcomes, not the workflow: policy has to be
    discovered from the knowledge base."""
    leaks = []
    for t in env["tasks"].values():
        ins = t["instruction"].lower()
        for phrase in ("staging-first", "canary at", "promote_canary", "test_fix",
                       "apply_migration", "use_secret_manager", "50 percentage"):
            if phrase in ins:
                leaks.append((t["task_id"], phrase))
    assert not leaks, leaks
    # ...but the guided variant deliberately does spell it out, for calibration
    guided = [t for t in env["tasks"].values() if "Procedure:" in t["instruction_guided"]]
    assert len(guided) == len(env["tasks"])


def test_cross_service_localization_is_not_trivially_solvable(env):
    """The checkout latency alarm must NOT be solvable by naming the alarmed
    service: the fault lives in payments, one hop downstream."""
    task = env["tasks"]["tsk_localize_checkout_latency"]
    db = fork(env, "aiops_lazy")
    calls = copy.deepcopy(task["expected_calls"])
    for c in calls:
        if c["tool"] == "submit_diagnosis":
            c["args"]["service"] = "checkout"       # the service the alarm names
    run_calls(env, db, calls)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "responsible service is payments" in err


def test_cascade_metric_is_actually_cross_service(env):
    """Fixing payments' downstream timeout must clear checkout's latency breach."""
    db = fork(env, "cascade")
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT value FROM service_metrics WHERE service='checkout' AND "
                          "environment='production' AND metric='latency_p99_ms'").fetchone()[0]
    conn.close()
    assert before == 530.0, before
    pr = call(env, db, "open_pull_request", service="payments", title="timeout",
              changes=[{"change_type": "config",
                        "payload": {"key": "notifications_timeout_ms",
                                    "value": "2000"}}])["pr_number"]
    call(env, db, "run_ci", pr_number=pr)
    call(env, db, "merge_pull_request", pr_number=pr)
    call(env, db, "deploy_service", service="payments", environment="staging")
    call(env, db, "deploy_service", service="payments", environment="production",
         canary_percent=25)
    call(env, db, "promote_canary", service="payments")
    conn = sqlite3.connect(db)
    after = conn.execute("SELECT value FROM service_metrics WHERE service='checkout' AND "
                         "environment='production' AND metric='latency_p99_ms'").fetchone()[0]
    conn.close()
    assert after == 180.0, "a payments config change must move checkout's p99: %s" % after


# ---------------------------------------------------------------------------
# Multi-vendor reconciliation (research/notes/domain/F_chaos_scenarios.md)
# ---------------------------------------------------------------------------

NAIVE_ANSWERS = {
    # task -> (question_id, the answer a single-source agent would give, sources)
    "tsk_rcn_customer_facing_incidents": ("Q-CFI-7D", "5", ["pd_incidents"]),
    "tsk_rcn_checkout_error_rate": ("Q-CER", "2.1%", ["prom_series"]),
    "tsk_rcn_distinct_checkout_bugs": ("Q-DCB", "3",
                                       ["jira_issues", "linear_issues", "github_issues",
                                        "issue_links"]),
    "tsk_rcn_production_deploys": ("Q-PD-7D", "3", ["local_deploy_log"]),
    "tsk_rcn_gateway_owner": ("Q-OWN", "180",
                              ["pd_services", "pd_oncall", "owner_spreadsheet"]),
}


@pytest.mark.parametrize("tid", sorted(NAIVE_ANSWERS))
def test_single_source_answer_is_rejected(env, tid):
    """Each reconciliation task must punish the obvious single-source answer:
    counting every incident, trusting the latest metric sample across a counter
    reset, summing three trackers that hold duplicates, matching 'prod' as a
    substring, or believing a stale spreadsheet."""
    qid, naive, sources = NAIVE_ANSWERS[tid]
    task = env["tasks"][tid]
    db = fork(env, "rcn_" + tid)
    for c in copy.deepcopy(task["expected_calls"]):
        if c["tool"] == "submit_answer":
            c = {"tool": "submit_answer",
                 "args": {"question_id": qid, "answer": naive, "sources": sources,
                          "assumptions": "took the first source at face value"}}
        call(env, db, c["tool"], **c.get("args", {}))
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "answer_correct" in err


def test_service_naming_chaos_is_resolvable_not_cruel(env):
    """F5: chaos is legitimate only when the resolution is discoverable from
    inside the world. Every alias must map back to a canonical service."""
    db = fork(env, "aliases")
    for spelling in ("checkout-api", "checkout_service", "checkout-web",
                     "Checkout Platform", "edge-gateway", "payments_service"):
        r = call(env, db, "resolve_service_alias", name=spelling)
        assert r.get("canonical"), "%s does not resolve: chaos would be cruel" % spelling
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(DISTINCT alias) FROM service_aliases").fetchone()[0]
    conn.close()
    assert n >= 15


def test_nonprod_matches_a_naive_prod_filter(env):
    """CS-06/07: the trap only exists if 'nonprod' really is in the data."""
    db = fork(env, "nonprod")
    rows = call(env, db, "query_local_deploy_log", since_day=414)
    envs = {r["environment"] for r in rows}
    assert any(e.startswith("nonprod") for e in envs), envs
    naive = [r for r in rows if "prod" in r["environment"] and not r["was_rollback"]]
    exact = [r for r in rows if r["environment"] == "production" and not r["was_rollback"]]
    assert len(naive) > len(exact), "the substring trap must actually bite"


def test_sentry_and_prometheus_disagree_for_a_documented_reason(env):
    """CS-08/09: two correct numbers. Sentry samples; Prometheus counts."""
    db = fork(env, "metric_conflict")
    projects = {p["slug"]: p for p in call(env, db, "sentry_list_projects")}
    assert projects["checkout-web"]["sample_rate"] < 1.0
    prom = call(env, db, "query_prometheus", metric="http_errors_total:rate5m",
                label_service="checkout_service", label_env="production")
    assert any(r["counter_reset"] for r in prom), "the reset must be present and flagged"


def test_declared_sources_must_match_the_trace(env):
    """A verifier must never accept a self-report as evidence. An agent that
    submits the right answer while naming a system it never queried fails."""
    task = env["tasks"]["tsk_rcn_customer_facing_incidents"]
    db = fork(env, "liar")
    call(env, db, "get_ticket", key="OPS-201")
    call(env, db, "pd_list_incidents", since_day=414, until_day=420)
    call(env, db, "submit_answer", question_id="Q-CFI-7D", answer="2",
         sources=["pd_incidents", "status_page_posts"],
         assumptions="claimed the status page without ever querying it")
    call(env, db, "update_ticket", key="OPS-201", status="done")
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "consulted_status_page_posts" in err


def test_documentation_counts_match_the_built_world(tmp_path):
    """Stale documentation is a hazard the research documents in four benchmark
    repos. Our own README must not drift from world.json."""
    import re as _re
    world = json.loads((ROOT / "world" / "world.json").read_text())
    readme = (ROOT / "README.md").read_text()
    n = world["counts"]["tasks"]
    wrong = [m for m in _re.findall(r"\b(\d+) tasks\b", readme)
             if m.isdigit() and int(m) not in (n, 8, 7, 6, 5, 4, 3, 2, 1)]
    assert not wrong, "README claims task counts %s but the world has %d" % (wrong, n)
