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

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("world_build")
    db = tmp / "environment.db"
    base_seq = bw.build_db(str(db))
    tools = make_tools()
    _, ns = bw.load_tools_module(tools)
    frozen, fixed_rows, audit_prefix = bw.reference_baselines(str(db))
    tasks = tasks_def.make_tasks(base_seq, frozen, fixed_rows, audit_prefix)
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
             ticket_key="ENG-2102",
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
             ticket_key="ENG-2302",
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
    db = fork(env, "flake_unit")
    r1 = call(env, db, "run_ci", service="checkout")
    r2 = call(env, db, "run_ci", service="checkout")
    assert r1["status"] == "failed" and "intermittent" in r1["detail"]
    assert r2["status"] == "passed"


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
            if c["tool"] == "promote_canary":
                continue
            if c["tool"] == "deploy_service" and c["args"].get("environment") == "production":
                c = {"tool": "deploy_service",
                     "args": {"service": "payments", "environment": "production"}}
            out.append(c)
        return out
    db, task = _replayed_with(env, "tsk_payments_error_rate", mutate)
    ok, err, score = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "canary" in err
    # Horizon-PC partial credit: correctness 5/5, deployment 1/2, quality 2/2
    assert abs(score - 0.85) < 1e-6, score


def test_skipping_staging_fails_hygiene_assertion(env):
    def mutate(calls):
        return [c for c in calls
                if not (c["tool"] == "deploy_service"
                        and c["args"].get("environment") == "staging")]
    db, task = _replayed_with(env, "tsk_payments_error_rate", mutate)
    ok, err, score = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "staging-first" in err
    assert score is not None and 0.0 < score < 1.0


def test_quarantining_flaky_test_does_not_pass(env):
    def mutate(calls):
        for c in calls:
            if c["tool"] == "open_pull_request":
                c["args"]["changes"][0]["payload"]["action"] = "quarantine"
        return calls
    db, task = _replayed_with(env, "tsk_flaky_checkout_test", mutate)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "FIXED" in err


def test_enabling_flag_before_deploy_fails_ordering(env):
    def mutate(calls):
        flag = [c for c in calls if c["tool"] == "set_feature_flag"][0]
        rest = [c for c in calls if c["tool"] != "set_feature_flag"]
        merge_idx = next(i for i, c in enumerate(rest)
                         if c["tool"] == "merge_pull_request")
        return rest[:merge_idx + 1] + [flag] + rest[merge_idx + 1:]
    db, task = _replayed_with(env, "tsk_express_checkout_flag", mutate)
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
    task = env["tasks"]["tsk_payments_error_rate"]
    calls = copy.deepcopy(task["expected_calls"])
    db = fork(env, "adv_blanket")
    run_calls(env, db, calls)
    # blanket mutation: also fix+resolve search out of scope
    r = call(env, db, "open_pull_request", service="search", title="cache",
             changes=[{"change_type": "config",
                       "payload": {"key": "cache_enabled", "value": "true"}}])
    call(env, db, "run_ci", pr_number=r["pr_number"])
    call(env, db, "merge_pull_request", pr_number=r["pr_number"])
    call(env, db, "deploy_service", service="search", environment="staging")
    call(env, db, "deploy_service", service="search", environment="production")
    call(env, db, "resolve_alert", alert_id=9602)
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "9602" in err


def test_fabricated_reference_data_is_rejected(env):
    """Solving the task but also inventing world data (the platform's
    `over_repair` corruption) must lose the reward."""
    task = env["tasks"]["tsk_payments_error_rate"]
    db = fork(env, "adv_fabricate")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    ok, _, _ = bw.run_vcode(task["vcode"], str(db))
    assert ok, "clean oracle must pass before corrupting"
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO services(name, team, tier, language, description, "
                 "repo_version) VALUES ('ghost-svc','platform',3,'go','','v1.0.0')")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "scope" in err


def test_mutated_runbook_is_rejected(env):
    """Rewriting a runbook to match a shortcut must not be rewarded."""
    task = env["tasks"]["tsk_payments_error_rate"]
    db = fork(env, "adv_runbook")
    run_calls(env, db, copy.deepcopy(task["expected_calls"]))
    conn = sqlite3.connect(db)
    conn.execute("UPDATE runbooks SET body='no policy' WHERE runbook_id=9952")
    conn.commit()
    conn.close()
    ok, err, _ = bw.run_vcode(task["vcode"], str(db))
    assert not ok and "reference data" in err


def test_tampered_audit_log_is_rejected(env):
    """Forging the append-only audit trail (how an agent would fake workflow
    ordering) must lose the reward."""
    task = env["tasks"]["tsk_loyalty_multi_service"]
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
    task = env["tasks"]["tsk_payments_error_rate"]
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
