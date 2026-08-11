"""Deterministic builder for the software-devops world (v2).

Produces a blobfish Format-A package in ./world and hard-gates quality:
  1. every task's vcode FAILS on the pristine seed (no free reward),
  2. every task's expected_calls oracle replays cleanly through the real tools,
  3. every task's vcode PASSES after its oracle replay at PC score 1.0.

Run:  python3 build/build_world.py [--out world]
"""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import schema_seed as S          # noqa: E402
import task_specs                # noqa: E402
import tasks_def                 # noqa: E402
from tools_src import make_tools, ENGINE_SNIPPET  # noqa: E402
from vendor_tools import make_vendor_tools  # noqa: E402
import vendors as V  # noqa: E402

try:
    from content_code import REPO_FILES, COMMITS
except Exception:                # pragma: no cover - content authored separately
    REPO_FILES, COMMITS = [], []
try:
    from content_docs import DOCUMENTS
except Exception:                # pragma: no cover
    DOCUMENTS = []

CREATED_AT = 1786000000.0
SEED = 42
FROZEN_TABLES = ("oncall", "slos", "metric_rules", "runbooks_placeholder")
# Tables no tool can write (byte-compared) and inventories that must not grow.
FROZEN = ("oncall", "slos", "metric_rules", "documents", "channels", "logs",
          "infra_components", "service_dependencies",
          "migration_requirements", "contract_rules", "commits",
          "linear_issues", "github_issues", "issue_links",
          "prom_series", "sentry_issues", "sentry_projects", "pd_services",
          "pd_incidents", "pd_oncall", "pd_change_events", "status_page_posts",
          "confluence_pages", "owner_spreadsheet", "local_deploy_log",
          "service_aliases", "k8s_events", "k8s_pods", "k8s_nodes", "k8s_deployments", "code_exercises", "remediation_proposals", "alert_rules", "alert_firings", "alert_silences", "approval_policy")
# traffic_profile is legitimately updated by shift_endpoint_traffic, so only its
# row count is pinned; the rest may not gain or lose rows either.
FIXED_ROWS = ("services", "tests_catalog", "vulnerabilities", "repo_files",
              "traffic_profile", "jira_issues")


def build_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(S.SCHEMA_SQL)

    conn.executemany("INSERT INTO services(service_id, name, kind, team, tier, language, "
                     "description, repo_version) VALUES (?,?,?,?,?,?,?,?)", S.SERVICES)
    conn.executemany("INSERT INTO infra_components(component_id, name, kind, status, detail) "
                     "VALUES (?,?,?,?,?)", S.INFRA)
    conn.executemany("INSERT INTO service_dependencies(service, depends_on, kind) VALUES (?,?,?)",
                     S.SERVICE_DEPS)
    conn.executemany("INSERT INTO oncall(team, engineer) VALUES (?,?)", S.ONCALL)
    conn.executemany("INSERT INTO tickets(ticket_id, key, type, title, description, status, "
                     "priority, assignee, service) VALUES (?,?,?,?,?,?,?,?,?)",
                     task_specs.tickets())
    conn.executemany("INSERT INTO pull_requests(number, service, title, body, author, ticket_key, "
                     "status, merged_version) VALUES (?,?,?,?,?,?,?,?)", S.PULL_REQUESTS)
    conn.executemany("INSERT INTO deployments(deployment_id, service, environment, version, "
                     "status, canary_percent) VALUES (?,?,?,?,?,?)", S.DEPLOYMENTS)
    conn.executemany("INSERT INTO feature_flags(flag_id, key, service, description, environment, "
                     "enabled, rollout_percent) VALUES (?,?,?,?,?,?,?)", S.FEATURE_FLAGS)
    conn.executemany("INSERT INTO metric_rules(rule_id, service, metric, kind, ckey, cvalue, "
                     "value) VALUES (?,?,?,?,?,?,?)", S.METRIC_RULES)
    conn.executemany("INSERT INTO slos(slo_id, service, metric, threshold, description) "
                     "VALUES (?,?,?,?,?)", S.SLOS)
    conn.executemany("INSERT INTO traffic_profile(route_id, service, route, rps, share_pct) "
                     "VALUES (?,?,?,?,?)", S.TRAFFIC_PROFILE)
    conn.executemany("INSERT INTO alerts(alert_id, service, metric, severity, status, message) "
                     "VALUES (?,?,?,?,?,?)", S.ALERTS)
    conn.executemany("INSERT INTO incidents(incident_id, severity, title, service, status, "
                     "commander) VALUES (?,?,?,?,?,?)", S.INCIDENTS)
    conn.executemany("INSERT INTO status_page(state, title, body) VALUES (?,?,?)", S.STATUS_PAGE)
    conn.executemany("INSERT INTO error_events(fingerprint, service, title, culprit, events, "
                     "status) VALUES (?,?,?,?,?,?)", S.ERROR_EVENTS)
    conn.executemany("INSERT INTO logs(log_id, service, environment, level, message) "
                     "VALUES (?,?,?,?,?)", S.LOGS)
    conn.executemany("INSERT INTO tests_catalog(test_id, service, suite, name, status, "
                     "quarantined) VALUES (?,?,?,?,?,?)", S.TESTS)
    conn.executemany("INSERT INTO vulnerabilities(vuln_id, cve, package, service, severity, "
                     "fixed_version, status) VALUES (?,?,?,?,?,?,?)", S.VULNERABILITIES)
    conn.executemany("INSERT INTO channels(channel, purpose) VALUES (?,?)", S.CHANNELS)
    conn.executemany("INSERT INTO messages(channel, author, body) VALUES (?,?,?)", S.MESSAGES)
    conn.executemany("INSERT INTO migration_requirements(req_id, service, module, migration_name) "
                     "VALUES (?,?,?,?)", S.MIGRATION_REQUIREMENTS)
    conn.executemany("INSERT INTO contract_rules(rule_id, producer_service, endpoint, "
                     "consumer_service, consumer_key, consumer_required_value, message) "
                     "VALUES (?,?,?,?,?,?,?)", S.CONTRACT_RULES)
    conn.executemany("INSERT INTO migrations(service, name, environment, status) VALUES (?,?,?,?)",
                     S.MIGRATIONS)

    # ---- multi-vendor layer: the same facts, split across systems that disagree
    conn.executescript(V.SCHEMA_SQL)
    conn.executemany("INSERT INTO service_aliases(canonical, alias, system) VALUES (?,?,?)",
                     V.ALIASES)
    conn.executemany("INSERT INTO jira_issues(key, project, summary, issue_type, status, "
                     "resolution, priority, component, assignee, created_day, updated_day) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", V.JIRA_ISSUES)
    conn.executemany("INSERT INTO linear_issues(identifier, team, title, state, priority, "
                     "label, created_day) VALUES (?,?,?,?,?,?,?)", V.LINEAR_ISSUES)
    conn.executemany("INSERT INTO github_issues(number, repo, title, state, labels, "
                     "created_day) VALUES (?,?,?,?,?,?)", V.GITHUB_ISSUES)
    conn.executemany("INSERT INTO issue_links(source, target, kind) VALUES (?,?,?)",
                     V.ISSUE_LINKS)
    conn.executemany("INSERT INTO sentry_projects(slug, platform, sample_rate) VALUES (?,?,?)",
                     V.SENTRY_PROJECTS)
    conn.executemany("INSERT INTO sentry_issues(issue_id, project_slug, title, level, events, "
                     "users_affected, first_seen_day, last_seen_day, status) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", V.SENTRY_ISSUES)
    for i, row in enumerate(V.PROM_SERIES, start=1):
        conn.execute("INSERT INTO prom_series(series_id, metric, label_service, label_env, "
                     "day, value, counter_reset) VALUES (?,?,?,?,?,?,?)", (i,) + row)
    conn.executemany("INSERT INTO pd_services(pd_service_id, name, escalation_policy, status) "
                     "VALUES (?,?,?,?)", V.PD_SERVICES)
    conn.executemany("INSERT INTO pd_incidents(incident_number, title, pd_service_id, urgency, "
                     "priority, status, created_day, resolved_day) VALUES (?,?,?,?,?,?,?,?)",
                     V.PD_INCIDENTS)
    conn.executemany("INSERT INTO pd_oncall(schedule_id, schedule_name, escalation_policy, "
                     "user_name, day) VALUES (?,?,?,?,?)", V.PD_ONCALL)
    conn.executemany("INSERT INTO pd_change_events(pd_service_id, summary, day) VALUES (?,?,?)",
                     V.PD_CHANGE_EVENTS)
    conn.executemany("INSERT INTO status_page_posts(post_id, title, impact, state, "
                     "published_day, linked_incident) VALUES (?,?,?,?,?,?)", V.STATUS_PAGE_POSTS)
    conn.executemany("INSERT INTO confluence_pages(page_id, space, title, body, "
                     "last_updated_day, stale) VALUES (?,?,?,?,?,?)", V.CONFLUENCE_PAGES)
    conn.executemany("INSERT INTO owner_spreadsheet(row_id, service_label, owning_team, "
                     "slack_channel, last_reviewed_day, week_start) VALUES (?,?,?,?,?,?)",
                     V.OWNER_SPREADSHEET)
    conn.executemany("INSERT INTO approval_policy(policy_id, action, approver_role, "
                     "rationale) VALUES (?,?,?,?)", V.APPROVAL_POLICY)
    conn.executemany("INSERT INTO alert_rules(rule_id, name, service_label, expr, severity, "
                     "group_by, routes_to) VALUES (?,?,?,?,?,?,?)", V.ALERT_RULES)
    conn.executemany("INSERT INTO alert_firings(firing_id, rule_id, fingerprint, day, "
                     "silenced, inhibited_by, paged_incident) VALUES (?,?,?,?,?,?,?)",
                     V.ALERT_FIRINGS)
    conn.executemany("INSERT INTO alert_silences(silence_id, matcher, created_by, reason, "
                     "expires_day) VALUES (?,?,?,?,?)", V.ALERT_SILENCES)
    conn.executemany("INSERT INTO remediation_proposals(proposal_id, incident_ref, author, "
                     "summary, detail) VALUES (?,?,?,?,?)", V.REMEDIATION_PROPOSALS)
    conn.executemany("INSERT INTO k8s_pods(pod, namespace, service, image_tag, phase, "
                     "restarts, memory_limit_mb, memory_usage_mb, node, pending_reason) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", V.K8S_PODS)
    conn.executemany("INSERT INTO k8s_nodes(node, ready, condition, message, cpu_used_pct, "
                     "disk_used_pct, labels, kernel_version, taints) VALUES (?,?,?,?,?,?,?,?,?)",
                     V.K8S_NODES)
    conn.executemany("INSERT INTO k8s_deployments(service, desired_replicas, ready_replicas, "
                     "strategy, storage_class) VALUES (?,?,?,?,?)", V.K8S_DEPLOYMENTS)
    import code_exercises as CE
    conn.executemany("INSERT INTO code_exercises(exercise_id, service, path, func, spec, "
                     "starter, visible_tests, hidden_tests) VALUES (?,?,?,?,?,?,?,?)",
                     CE.as_rows())
    # the starter also lands in the monorepo, so read_file and list_files see it
    for ex in CE.EXERCISES:
        conn.execute("INSERT INTO repo_files(service, path, language, owner, loc, content) "
                     "VALUES (?,?,?,?,?,?)",
                     (ex["service"], ex["path"], "python", "", 
                      len(ex["starter"].splitlines()), ex["starter"]))
    conn.executemany("INSERT INTO k8s_events(event_id, namespace, pod, reason, message, "
                     "count, day) VALUES (?,?,?,?,?,?,?)", V.K8S_EVENTS)
    conn.executemany("INSERT INTO local_deploy_log(service, version, environment, day, "
                     "was_rollback) VALUES (?,?,?,?,?)", V.LOCAL_DEPLOY_LOG)

    # monorepo
    for f in REPO_FILES:
        conn.execute("INSERT INTO repo_files(service, path, language, owner, loc, content) "
                     "VALUES (?,?,?,?,?,?)",
                     (f["service"], f["path"], f.get("language", "text"), f.get("owner", ""),
                      len(f["content"].splitlines()), f["content"]))
    for c in COMMITS:
        conn.execute("INSERT INTO commits(sha, service, author, day, message, files, additions, "
                     "deletions) VALUES (?,?,?,?,?,?,?,?)",
                     (c["sha"], c["service"], c["author"], int(c["day"]), c["message"],
                      c.get("files", ""), int(c.get("additions", 0)), int(c.get("deletions", 0))))
    # knowledge base (normalise the CDN runbook onto media-service)
    for d in DOCUMENTS:
        svc = d.get("service", "")
        if "CDN" in d["title"] and svc == "catalog":
            svc = "media-service"
        conn.execute("INSERT INTO documents(doc_id, kind, title, service, author, day, body) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (d["doc_id"], d["kind"], d["title"], svc, d.get("author", ""),
                      int(d.get("day", 0)), d["body"]))

    # repo + env state
    for svc, rows in S.REPO_STATE.items():
        for kind, key, value in rows:
            conn.execute("INSERT INTO repo_state(service, kind, key, value) VALUES (?,?,?,?)",
                         (svc, kind, key, value))
            for env in S.ENVIRONMENTS:
                conn.execute("INSERT INTO env_state(service, environment, kind, key, value) "
                             "VALUES (?,?,?,?,?)", (svc, env, kind, key, value))
    for row in S.SERVICES:
        name, version = row[1], row[7]
        for env in S.ENVIRONMENTS:
            conn.execute("INSERT INTO env_state(service, environment, kind, key, value) "
                         "VALUES (?,?,'version','current',?)", (name, env, version))
    for svc, rows in S.PRODUCTION_TRAFFIC.items():
        for path, pct in rows:
            conn.execute("INSERT INTO env_state(service, environment, kind, key, value) "
                         "VALUES (?,'production','traffic',?,?)", (svc, path, pct))

    def snapshot(svc):
        rows = conn.execute("SELECT kind, key, value FROM repo_state WHERE service=? AND "
                            "kind IN ('config','dependency','endpoint','module') ORDER BY kind, key",
                            (svc,)).fetchall()
        return json.dumps([[r["kind"], r["key"], r["value"]] for r in rows])

    for row in S.SERVICES:
        conn.execute("INSERT INTO versions(service, version, state_json) VALUES (?,?,?)",
                     (row[1], row[7], snapshot(row[1])))
    for svc, extra in S.EXTRA_VERSIONS.items():
        for v in extra:
            conn.execute("INSERT INTO versions(service, version, state_json) VALUES (?,?,?)",
                         (svc, v, snapshot(svc)))

    # seeded CI history with per-stage detail
    for (svc, pr, status, detail) in S.CI_RUNS:
        cur = conn.execute("INSERT INTO ci_runs(service, pr_number, status, detail) "
                           "VALUES (?,?,?,?)", (svc, pr, status, detail))
        rid = cur.lastrowid
        for stage in ("build", "unit", "integration", "regression"):
            if status == "passed":
                conn.execute("INSERT INTO ci_stages(run_id, stage, status, detail) "
                             "VALUES (?,?,'passed','ok')", (rid, stage))
            else:
                st = "failed" if stage == "integration" else (
                    "passed" if stage in ("build", "unit") else "skipped")
                conn.execute("INSERT INTO ci_stages(run_id, stage, status, detail) "
                             "VALUES (?,?,?,?)", (rid, stage, st,
                                                  detail if st == "failed" else "ok"))

    # seeded deploy audit trail (v5.1.0 was canaried and promoted: process was
    # followed, the code was bad)
    for (did, svc, env, version, status, canary) in S.DEPLOYMENTS:
        if did == 9266:
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("deploy_service", svc, json.dumps(
                             {"environment": env, "version": version, "canary_percent": 25,
                              "applied": False, "new_alarms": []})))
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("promote_canary", svc, json.dumps(
                             {"environment": env, "version": version, "deployment_id": did,
                              "new_alarms": []})))
        else:
            conn.execute("INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)",
                         ("deploy_service", svc, json.dumps(
                             {"environment": env, "version": version, "canary_percent": canary,
                              "applied": True, "new_alarms": []})))

    ns = {}
    exec(ENGINE_SNIPPET, ns)
    ns["_recompute"](conn)
    conn.commit()
    base_seq = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM audit_events").fetchone()[0]

    expect = {("payments", "error_rate_pct"): 4.2, ("search", "latency_p99_ms"): 850.0,
              ("checkout", "error_rate_pct"): 5.5, ("api-gateway", "latency_p99_ms"): 1030.0,
              ("catalog", "latency_p99_ms"): 645.0, ("inventory", "error_rate_pct"): 4.7,
              ("media-service", "latency_p99_ms"): 800.0,
              ("notifications", "error_rate_pct"): 3.6,
              ("analytics-worker", "error_rate_pct"): 6.0,
              ("checkout", "latency_p99_ms"): 530.0}
    for (svc, metric), want in expect.items():
        got = conn.execute("SELECT value FROM service_metrics WHERE service=? AND "
                           "environment='production' AND metric=?", (svc, metric)).fetchone()[0]
        assert abs(got - want) < 1e-6, "seed metric %s %s: %s != %s" % (svc, metric, got, want)
    n_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert n_alerts == len(S.ALERTS), "engine created unexpected alerts (%d)" % n_alerts
    conn.close()
    return base_seq


def reference_baselines(db_path):
    conn = sqlite3.connect(db_path)
    frozen = {}
    for t in FROZEN:
        try:
            rows = [tuple(r) for r in
                    conn.execute('SELECT * FROM "%s" ORDER BY rowid' % t).fetchall()]
        except sqlite3.OperationalError:
            continue
        frozen[t] = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    fixed = {t: conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in FIXED_ROWS}
    prefix = [tuple(r) for r in conn.execute("SELECT * FROM audit_events ORDER BY seq").fetchall()]
    audit_prefix = hashlib.sha256(repr(prefix).encode()).hexdigest()[:16]
    n_secret = conn.execute("SELECT COUNT(*) FROM repo_files WHERE content LIKE '%pk_live_%'").fetchone()[0]
    lit = ""
    row = conn.execute("SELECT content FROM repo_files WHERE content LIKE '%pk_live_%' LIMIT 1").fetchone()
    if row:
        m = re.search(r'["\']?(pk_live_[A-Za-z0-9_\-]+)["\']?', row[0])
        if m:
            lit = m.group(1)
    conn.close()
    return frozen, fixed, audit_prefix, n_secret, lit


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

    ns = {"conn": conn, "sqlite3": sqlite3, "json": json, "get_db": get_db, "db_path": db_path,
          "DB_PATH": db_path, "final_answer": final_answer, "answer": final_answer}
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
            return None, "step %d (%s): %s" % (i, call["tool"], result.get("error"))
    return db, None


def validate(tasks, pristine_db, tool_ns, workdir):
    report, failures = [], []
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
            report.append({"task_id": tid, "accepted": False, "reason": verr})
            continue
        if score_after is None or score_after < 1.0:
            failures.append("%s: oracle passes but PC score is %s" % (tid, score_after))
            report.append({"task_id": tid, "accepted": False,
                           "reason": "oracle score %s != 1.0" % score_after})
            continue
        report.append({"task_id": tid, "accepted": True, "category": task["category"],
                       "oracle_steps": len(task["expected_calls"]), "oracle_score": score_after,
                       "discriminating_vcode": True, "oracle_replay_passed": True})
    return report, failures


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
        h.update(json.dumps({k: t[k] for k in ("name", "description", "parameters", "source_code",
                                               "read_tables", "write_tables")},
                            sort_keys=True).encode())
    for t in sorted(tasks, key=lambda x: x["task_id"]):
        h.update(json.dumps(t, sort_keys=True).encode())
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent / "world"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    out = pathlib.Path(args.out)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sdw_build_"))
    db_path = tmp / "environment.db"
    base_seq = build_db(str(db_path))
    frozen, fixed_rows, audit_prefix, n_secret, secret_lit = reference_baselines(str(db_path))
    print("seed built: base audit seq=%d, monorepo files=%d, commits=%d, docs=%d, secret='%s'"
          % (base_seq, len(REPO_FILES), len(COMMITS), len(DOCUMENTS), secret_lit or "<none>"))

    tools = make_tools() + make_vendor_tools()
    combined_src, tool_ns = load_tools_module(tools)
    reads_map = {}
    for t in tools:
        for tb in t.get("read_tables", []):
            reads_map.setdefault(tb, []).append(t["name"])
    tasks = tasks_def.make_tasks(base_seq, frozen, fixed_rows, audit_prefix, n_secret,
                                 secret_lit or "pk_live_none", reads_map)

    report, failures = validate(tasks, db_path, tool_ns, tmp)
    by_cat = {}
    for r in report:
        c = r.get("category", "?")
        d = by_cat.setdefault(c, [0, 0])
        d[1] += 1
        if r["accepted"]:
            d[0] += 1
    if not args.quiet:
        for r in report:
            if not r["accepted"]:
                print("  [FAIL] %s -- %s" % (r["task_id"], r["reason"][:200]))
    for c in sorted(by_cat):
        print("  %-24s %d/%d" % (c, by_cat[c][0], by_cat[c][1]))
    if failures:
        print("\nBUILD FAILED (%d):" % len(failures))
        for f in failures[:12]:
            print("  *", f[:240])
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
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                                         "name != 'sqlite_sequence' ORDER BY name")]
    row_count = sum(conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables)
    conn.close()

    difficulty, categories = {}, {}
    for t in tasks:
        difficulty[t["difficulty"]] = difficulty.get(t["difficulty"], 0) + 1
        categories[t["category"]] = categories.get(t["category"], 0) + 1
    splits = tasks_def.splits(tasks)

    write_json(out / "difficulty_distribution.json", difficulty)
    write_json(out / "tool_graph.json", {"nodes": [t["tool_id"] for t in tools], "edges": [],
                                         "strong_edges": 0, "weak_edges": 0,
                                         "independent_edges": 0})
    write_json(out / "task_creation_report.json",
               {"accepted": len(report), "rejected": 0, "by_category": categories,
                "tasks": report})
    write_json(out / "env_spec.json", {
        "kind": "AgentWorldEnvSpec", "env_id": world_id, "version": 2, "parent_digest": None,
        "digest": "", "tenant_id": "",
        "conformance": {"status": "FLEET_EXTENSION", "paper_section": ""},
        "domain_spec_ref": "",
        "theme": {"source_type": "prd", "source_ref": "https://polymathlabs.ai/blog/horizon-swe",
                  "taxonomy_l1": "Software Engineering", "taxonomy_l2": "DevOps & SRE",
                  "taxonomy_l3": "End-to-end engineering workflow",
                  "description": "NovaCart: ten services over a database, cache, queue, object "
                                 "store and CDN, with an editable monorepo and commit history, a "
                                 "traffic generator, issue tracker, knowledge base, chat, "
                                 "deployment tooling with migrations and canaries, logs, metrics, "
                                 "alarms, error tracking and a public status page. 50 long-horizon "
                                 "engineering tasks graded by executable verifiers."},
        "database": {"snapshot_ref": "environment.db",
                     "schema_hash": hashlib.sha256(schema_sql.encode()).hexdigest(),
                     "seed": SEED, "engine": "sqlite", "table_count": len(tables),
                     "row_count": row_count, "complexification_rounds": 0},
        "tools": {"manifest_ref": "", "tests_ref": "", "tool_count": len(tools),
                  "survival_rate": 1.0, "valid_tool_ids": [t["tool_id"] for t in tools]},
        "tool_graph": {"nodes": [t["tool_id"] for t in tools], "edges": [], "strong_edges": 0,
                       "weak_edges": 0, "independent_edges": 0},
        "task_refs": [t["task_id"] for t in tasks], "verifier_refs": [],
        "quality": {"five_run_successes": 0, "mutation_score": 0.0, "task_count": len(tasks),
                    "accepted_task_count": len(tasks), "acceptance_rate": 1.0},
        "stage_history": [],
        "provenance": {"generator": "hand-authored", "blueprint": "horizon-swe",
                       "repo": "software-devops"},
        "verification_summary": {"total_tasks": len(tasks),
                                 "discriminating_vcode_tasks": len(tasks),
                                 "grounded_answer_tasks": 0, "weak_vcode_tasks": 0,
                                 "source_weak_vcode_tasks": 0, "weak_vcode_task_ids": []},
    })
    write_json(out / "world.json", {
        "world_id": world_id, "blobfish_version": "external-0.2.0", "vertical": "software_devops",
        "tenant": "",
        "brief": "Horizon-SWE-style end-to-end engineering world: investigate -> PR -> CI "
                 "(build/unit/integration/regression) -> merge -> migrate -> staging -> canary -> "
                 "promote -> observe -> resolve.",
        "topic": "software engineering devops ci cd deployments canary migrations feature flags "
                 "incidents slo alarms api migration flaky tests security response monorepo",
        "domain": "engineering", "engine": "curated", "seed": SEED, "created_at": CREATED_AT,
        "world_digest": digest, "entities": tables, "tables_without_tools": [],
        "counts": {"tables": len(tables), "rows": row_count, "tools": len(tools),
                   "tasks": len(tasks), "tasks_rejected": 0,
                   "repo_files": len(REPO_FILES), "commits": len(COMMITS),
                   "documents": len(DOCUMENTS)},
        "difficulty": difficulty, "categories": categories, "splits": splits,
        "task_creation": {"accepted": len(tasks), "rejected": 0},
        "personas": [p["persona_id"] for p in S.PERSONAS],
    })

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nworld -> %s (%s)" % (out, world_id))
    print("tables=%d rows=%d tools=%d tasks=%d files=%d commits=%d docs=%d"
          % (len(tables), row_count, len(tools), len(tasks), len(REPO_FILES), len(COMMITS),
             len(DOCUMENTS)))


if __name__ == "__main__":
    main()
