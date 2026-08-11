"""Deterministic builder for the software-devops world.

Produces a blobfish Format-A world package in ./world and hard-gates quality:
  1. every task's vcode FAILS on the pristine seed (no free reward),
  2. every task's expected_calls oracle replays cleanly through the real tools,
  3. every task's vcode PASSES after its oracle replay.

Run:  python3 build/build_world.py [--out world]
"""

import argparse
import hashlib
import json
import pathlib
import shutil
import sqlite3
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import schema_seed as S          # noqa: E402
import tasks_def                 # noqa: E402
from tools_src import make_tools, ENGINE_SNIPPET  # noqa: E402

CREATED_AT = 1786000000.0        # fixed: builds are byte-stable
SEED = 42


# ---------------------------------------------------------------------------
# database construction
# ---------------------------------------------------------------------------

def build_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(S.SCHEMA_SQL)

    conn.executemany(
        "INSERT INTO services(service_id, name, team, tier, language, description, repo_version) "
        "VALUES (?,?,?,?,?,?,?)", S.SERVICES)
    conn.executemany("INSERT INTO oncall(team, engineer) VALUES (?,?)", S.ONCALL)
    conn.executemany(
        "INSERT INTO tickets(ticket_id, key, type, title, description, status, priority, assignee, service) "
        "VALUES (?,?,?,?,?,?,?,?,?)", S.TICKETS)
    conn.executemany(
        "INSERT INTO pull_requests(number, service, title, body, author, ticket_key, status, merged_version) "
        "VALUES (?,?,?,?,?,?,?,?)", S.PULL_REQUESTS)
    conn.executemany(
        "INSERT INTO ci_runs(service, pr_number, status, detail) VALUES (?,?,?,?)", S.CI_RUNS)
    conn.executemany(
        "INSERT INTO deployments(deployment_id, service, environment, version, status, canary_percent) "
        "VALUES (?,?,?,?,?,?)", S.DEPLOYMENTS)
    conn.executemany(
        "INSERT INTO feature_flags(flag_id, key, service, description, environment, enabled, rollout_percent) "
        "VALUES (?,?,?,?,?,?,?)", S.FEATURE_FLAGS)
    conn.executemany(
        "INSERT INTO metric_rules(rule_id, service, metric, kind, ckey, cvalue, value) "
        "VALUES (?,?,?,?,?,?,?)", S.METRIC_RULES)
    conn.executemany(
        "INSERT INTO slos(slo_id, service, metric, threshold, description) VALUES (?,?,?,?,?)", S.SLOS)
    conn.executemany(
        "INSERT INTO alerts(alert_id, service, metric, severity, status, message) "
        "VALUES (?,?,?,?,?,?)", S.ALERTS)
    conn.executemany(
        "INSERT INTO incidents(incident_id, severity, title, service, status, commander) "
        "VALUES (?,?,?,?,?,?)", S.INCIDENTS)
    conn.executemany(
        "INSERT INTO logs(log_id, service, environment, level, message) VALUES (?,?,?,?,?)", S.LOGS)
    conn.executemany(
        "INSERT INTO runbooks(runbook_id, title, body) VALUES (?,?,?)", S.RUNBOOKS)
    conn.executemany(
        "INSERT INTO tests_catalog(test_id, service, suite, name, status, quarantined) "
        "VALUES (?,?,?,?,?,?)", S.TESTS)
    conn.executemany(
        "INSERT INTO vulnerabilities(vuln_id, cve, package, service, severity, fixed_version, status) "
        "VALUES (?,?,?,?,?,?,?)", S.VULNERABILITIES)
    conn.executemany("INSERT INTO channels(channel, purpose) VALUES (?,?)", S.CHANNELS)
    conn.executemany("INSERT INTO messages(channel, author, body) VALUES (?,?,?)", S.MESSAGES)

    # repo_state + mirrored env_state (baseline: HEAD is what is deployed).
    for svc, rows in S.REPO_STATE.items():
        for kind, key, value in rows:
            conn.execute("INSERT INTO repo_state(service, kind, key, value) VALUES (?,?,?,?)",
                         (svc, kind, key, value))
            for env in S.ENVIRONMENTS:
                conn.execute(
                    "INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)",
                    (svc, env, kind, key, value))
    for (sid, name, team, tier, lang, desc, version) in S.SERVICES:
        for env in S.ENVIRONMENTS:
            conn.execute(
                "INSERT INTO env_state(service, environment, kind, key, value) "
                "VALUES (?,?,'version','current',?)", (name, env, version))
    for svc, rows in S.PRODUCTION_TRAFFIC.items():
        for path, pct in rows:
            conn.execute(
                "INSERT INTO env_state(service, environment, kind, key, value) "
                "VALUES (?,'production','traffic',?,?)", (svc, path, pct))

    # version snapshots (current HEAD per service + curated historical versions)
    def snapshot(svc):
        rows = conn.execute(
            "SELECT kind, key, value FROM repo_state WHERE service=? AND "
            "kind IN ('config','dependency','endpoint','module') ORDER BY kind, key",
            (svc,)).fetchall()
        return json.dumps([[r["kind"], r["key"], r["value"]] for r in rows])

    for (sid, name, team, tier, lang, desc, version) in S.SERVICES:
        conn.execute("INSERT INTO versions(service, version, state_json) VALUES (?,?,?)",
                     (name, version, snapshot(name)))
    for svc, extra in S.EXTRA_VERSIONS.items():
        for v in extra:
            conn.execute("INSERT INTO versions(service, version, state_json) VALUES (?,?,?)",
                         (svc, v, snapshot(svc)))

    # seeded audit history mirroring the seeded deployments (the v5.1.0 prod
    # rollout was canaried and promoted — process was followed; code was bad).
    for (did, svc, env, version, status, canary) in S.DEPLOYMENTS:
        if did == 9266:
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("deploy_service", svc, json.dumps(
                             {"environment": env, "version": version,
                              "canary_percent": 25, "applied": False})))
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("promote_canary", svc, json.dumps(
                             {"environment": env, "version": version, "deployment_id": did})))
        else:
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("deploy_service", svc, json.dumps(
                             {"environment": env, "version": version,
                              "canary_percent": canary, "applied": True})))

    # run the same engine the tools embed, so seeded metrics are consistent
    ns = {}
    exec(ENGINE_SNIPPET, ns)
    ns["_recompute"](conn)
    conn.commit()

    base_seq = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM audit_events").fetchone()[0]

    # consistency gates on the seeded story
    expect = {
        ("payments", "error_rate_pct"): 4.2,
        ("search", "latency_p99_ms"): 850.0,
        ("checkout", "error_rate_pct"): 5.5,
        ("api-gateway", "latency_p99_ms"): 1030.0,
    }
    for (svc, metric), want in expect.items():
        got = conn.execute(
            "SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?",
            (svc, metric)).fetchone()[0]
        assert abs(got - want) < 1e-6, "seed metric mismatch %s %s: %s != %s" % (svc, metric, got, want)
    n_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert n_alerts == len(S.ALERTS), "engine created unexpected alerts (%d)" % n_alerts
    vuln = conn.execute("SELECT status FROM vulnerabilities WHERE vuln_id=9801").fetchone()[0]
    assert vuln == "open", "vulnerability must start open"

    conn.close()
    return base_seq


# ---------------------------------------------------------------------------
# validation harness (same gates blobfish enforces for curated tasks)
# ---------------------------------------------------------------------------

def reference_baselines(db_path):
    """Digests/counts of tables the agent must not fabricate. Must use the
    exact same algorithm as the `_digest` helper compiled into every vcode."""
    conn = sqlite3.connect(db_path)
    frozen = {}
    for t in tasks_def.FROZEN_TABLES:
        rows = [tuple(r) for r in
                conn.execute('SELECT * FROM "%s" ORDER BY rowid' % t).fetchall()]
        frozen[t] = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    fixed = {t: conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
             for t in tasks_def.FIXED_ROW_TABLES}
    prefix = [tuple(r) for r in
              conn.execute("SELECT * FROM audit_events ORDER BY seq").fetchall()]
    audit_prefix = hashlib.sha256(repr(prefix).encode()).hexdigest()[:16]
    conn.close()
    return frozen, fixed, audit_prefix


def load_tools_module(tools):
    src = "\n\n".join(t["source_code"] for t in tools)
    compile(src, "tools_combined.py", "exec")
    ns = {}
    exec(src, ns)
    return src, ns


def is_structured_error(result):
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False or result.get("success") is False:
        return True
    err = result.get("error")
    return bool(err) and result.get("ok") is not True and result.get("success") is not True


def run_vcode(vcode, db_path, final_answer=""):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    conn.row_factory = sqlite3.Row

    def get_db():
        c = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
        c.row_factory = sqlite3.Row
        return c

    ns = {"conn": conn, "sqlite3": sqlite3, "json": json, "get_db": get_db,
          "db_path": db_path, "DB_PATH": db_path,
          "final_answer": final_answer, "answer": final_answer}
    ok, err = True, None
    try:
        exec(compile(vcode, "<vcode>", "exec"), ns)
    except AssertionError as e:
        ok, err = False, "assertion: %s" % e
    except Exception as e:  # noqa: BLE001
        ok, err = False, "%s: %s" % (type(e).__name__, e)
    finally:
        conn.close()
    score = ns.get("score")
    return ok, err, (float(score) if isinstance(score, (int, float)) else None)


def replay_oracle(task, pristine_db, tool_ns, workdir):
    db = workdir / ("oracle_%s.db" % task["task_id"])
    shutil.copyfile(pristine_db, db)
    for i, call in enumerate(task["expected_calls"]):
        fn = tool_ns.get(call["tool"])
        if fn is None:
            return None, "step %d: unknown tool %s" % (i, call["tool"])
        try:
            result = fn(db_path=str(db), **call.get("args", {}))
        except Exception as e:  # noqa: BLE001
            return None, "step %d (%s): raised %s: %s" % (i, call["tool"], type(e).__name__, e)
        if is_structured_error(result):
            return None, "step %d (%s): structured error: %s" % (i, call["tool"], result.get("error"))
    return db, None


def validate(tasks, pristine_db, tool_ns, workdir):
    report = []
    failures = []
    for task in tasks:
        tid = task["task_id"]
        ok_pristine, _, _ = run_vcode(task["vcode"], str(pristine_db))
        if ok_pristine:
            failures.append("%s: vcode PASSES on the pristine seed (free reward)" % tid)
            report.append({"task_id": tid, "accepted": False, "reason": "non-discriminating vcode"})
            continue
        replay_db, err = replay_oracle(task, pristine_db, tool_ns, workdir)
        if err:
            failures.append("%s: oracle replay failed: %s" % (tid, err))
            report.append({"task_id": tid, "accepted": False, "reason": err})
            continue
        ok_after, verr, score_after = run_vcode(task["vcode"], str(replay_db))
        if not ok_after:
            failures.append("%s: vcode fails after oracle replay: %s" % (tid, verr))
            report.append({"task_id": tid, "accepted": False, "reason": "oracle does not satisfy vcode: %s" % verr})
            continue
        if score_after is None or score_after < 1.0:
            failures.append("%s: oracle passes but partial-credit score is %s (dimension bookkeeping bug)"
                            % (tid, score_after))
            report.append({"task_id": tid, "accepted": False,
                           "reason": "oracle score %s != 1.0" % score_after})
            continue
        report.append({"task_id": tid, "accepted": True,
                       "oracle_steps": len(task["expected_calls"]),
                       "oracle_score": score_after,
                       "discriminating_vcode": True, "oracle_replay_passed": True})
    return report, failures


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------

def dump_sql(db_path):
    conn = sqlite3.connect(db_path)
    schema_lines, seed_lines = [], []
    for line in conn.iterdump():
        if line.startswith("INSERT INTO"):
            seed_lines.append(line)
        elif line in ("BEGIN TRANSACTION;", "COMMIT;"):
            continue
        else:
            schema_lines.append(line)
    conn.close()
    return "\n".join(schema_lines) + "\n", "\n".join(seed_lines) + "\n"


def compute_digest(schema_sql, seed_sql, tools, tasks):
    h = hashlib.sha256()
    h.update(schema_sql.encode())
    h.update(seed_sql.encode())
    for t in sorted(tools, key=lambda x: x["name"]):
        h.update(json.dumps({k: t[k] for k in
                             ("name", "description", "parameters", "source_code",
                              "read_tables", "write_tables")},
                            sort_keys=True).encode())
    for t in sorted(tasks, key=lambda x: x["task_id"]):
        h.update(json.dumps(t, sort_keys=True).encode())
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent / "world"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sdw_build_"))
    db_path = tmp / "environment.db"
    base_seq = build_db(str(db_path))
    print("seed DB built; base audit seq =", base_seq)

    tools = make_tools()
    combined_src, tool_ns = load_tools_module(tools)
    frozen, fixed_rows, audit_prefix = reference_baselines(str(db_path))
    tasks = tasks_def.make_tasks(base_seq, frozen, fixed_rows, audit_prefix)

    report, failures = validate(tasks, db_path, tool_ns, tmp)
    for r in report:
        flag = "ok " if r["accepted"] else "FAIL"
        print("  [%s] %s%s" % (flag, r["task_id"],
                               "" if r["accepted"] else " -- " + r["reason"]))
    if failures:
        print("\nBUILD FAILED:")
        for f in failures:
            print("  *", f)
        sys.exit(1)

    schema_sql, seed_sql = dump_sql(str(db_path))
    digest = compute_digest(schema_sql, seed_sql, tools, tasks)
    world_id = "env_software_devops_" + digest[:8]

    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(db_path, out / "environment.db")
    (out / "schema.sql").write_text(schema_sql)
    (out / "seed.sql").write_text(seed_sql)
    (out / "tools_combined.py").write_text(combined_src)
    write_json(out / "tools.json", tools)
    write_json(out / "tasks.json", tasks)
    write_json(out / "personas.json", S.PERSONAS)

    conn = sqlite3.connect(str(db_path))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")]
    row_count = sum(conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables)
    conn.close()

    difficulty = {}
    for t in tasks:
        difficulty[t["difficulty"]] = difficulty.get(t["difficulty"], 0) + 1

    write_json(out / "difficulty_distribution.json", difficulty)
    write_json(out / "tool_graph.json", {
        "nodes": [t["tool_id"] for t in tools],
        "edges": [], "strong_edges": 0, "weak_edges": 0, "independent_edges": 0})
    write_json(out / "task_creation_report.json", {
        "accepted": sum(1 for r in report if r["accepted"]),
        "rejected": sum(1 for r in report if not r["accepted"]),
        "tasks": report})

    write_json(out / "env_spec.json", {
        "kind": "AgentWorldEnvSpec",
        "env_id": world_id,
        "version": 1,
        "parent_digest": None,
        "digest": "",
        "tenant_id": "",
        "conformance": {"status": "FLEET_EXTENSION", "paper_section": ""},
        "domain_spec_ref": "",
        "theme": {
            "source_type": "prd",
            "source_ref": "https://polymathlabs.ai/blog/horizon-swe",
            "taxonomy_l1": "Software Engineering",
            "taxonomy_l2": "DevOps & SRE",
            "taxonomy_l3": "End-to-end engineering workflow",
            "description": "NovaCart, a mid-size e-commerce SaaS: seven services with "
                           "tickets, PRs carrying structured changes, CI, staged "
                           "deployments with canaries, feature flags, metrics/SLOs/alerts, "
                           "logs, runbooks, dependency scanning, incidents, and chat. A "
                           "deterministic engine derives production metrics from deployed "
                           "state; tasks are long-horizon engineering workflows scored by "
                           "executable verifiers over final state and the audit-event "
                           "ordering log.",
        },
        "database": {"snapshot_ref": "environment.db",
                     "schema_hash": hashlib.sha256(schema_sql.encode()).hexdigest(),
                     "seed": SEED, "engine": "sqlite",
                     "table_count": len(tables), "row_count": row_count,
                     "complexification_rounds": 0},
        "tools": {"manifest_ref": "", "tests_ref": "", "tool_count": len(tools),
                  "survival_rate": 1.0,
                  "valid_tool_ids": [t["tool_id"] for t in tools]},
        "tool_graph": {"nodes": [t["tool_id"] for t in tools], "edges": [],
                       "strong_edges": 0, "weak_edges": 0, "independent_edges": 0},
        "task_refs": [t["task_id"] for t in tasks],
        "verifier_refs": [],
        "quality": {"five_run_successes": 0, "mutation_score": 0.0,
                    "task_count": len(tasks), "accepted_task_count": len(tasks),
                    "acceptance_rate": 1.0},
        "stage_history": [],
        "provenance": {"generator": "hand-authored",
                       "blueprint": "horizon-swe-inspired",
                       "repo": "software-devops"},
        "verification_summary": {"total_tasks": len(tasks),
                                 "discriminating_vcode_tasks": len(tasks),
                                 "grounded_answer_tasks": 0,
                                 "weak_vcode_tasks": 0,
                                 "source_weak_vcode_tasks": 0,
                                 "weak_vcode_task_ids": []},
    })

    write_json(out / "world.json", {
        "world_id": world_id,
        "blobfish_version": "external-0.1.0",
        "vertical": "software_devops",
        "tenant": "",
        "brief": "End-to-end engineering-workflow world (Horizon-SWE-inspired): "
                 "investigate -> PR -> CI -> merge -> staged deploy -> observe -> resolve.",
        "topic": "software engineering devops ci cd deployments canary feature flags "
                 "incidents slo alerts api migration flaky tests security response",
        "domain": "engineering",
        "engine": "curated",
        "seed": SEED,
        "created_at": CREATED_AT,
        "world_digest": digest,
        "entities": tables,
        "tables_without_tools": [],
        "counts": {"tables": len(tables), "rows": row_count,
                   "tools": len(tools), "tasks": len(tasks), "tasks_rejected": 0},
        "difficulty": difficulty,
        "splits": tasks_def.SPLITS,
        "task_creation": {"accepted": len(tasks), "rejected": 0},
        "personas": [p["persona_id"] for p in S.PERSONAS],
    })

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nworld written to %s (world_id=%s)" % (out, world_id))
    print("tables=%d rows=%d tools=%d tasks=%d" % (len(tables), row_count, len(tools), len(tasks)))


if __name__ == "__main__":
    main()
