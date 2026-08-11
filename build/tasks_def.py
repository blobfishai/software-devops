"""Task generators: 50 Horizon-SWE tasks emitted from build/task_specs.py.

Each generator returns (instruction, checks, oracle_calls):
  * checks are dimension-tagged vcode lines. Horizon-SWE-PF passes only when
    every `correctness` and `deployment` check holds (quality excluded).
    Horizon-SWE-PC = 0.6*correctness + 0.3*deployment + 0.1*quality.
  * oracle_calls replay through the real tools during the build and must yield
    a full-credit rollout.

Build-time tokens replaced in every vcode: __BASE_SEQ__, __FROZEN__,
__FIXED_ROWS__, __AUDIT_PREFIX__, __SECRET_FILES__.
"""

import json

import task_specs
from schema_seed import SLOS, TIER1_SERVICES

# Services whose integration suite still carries a live flaky test: their first
# CI attempt on a PR fails and the rerun passes.
FLAKY_SERVICES = {"checkout", "catalog", "inventory", "api-gateway", "search",
                  "analytics-worker"}

SLO_BY = {(s[1], s[2]): s[3] for s in SLOS}

PRELUDE = """\
import hashlib
_FROZEN = __FROZEN__
_FIXED_ROWS = __FIXED_ROWS__
_AUDIT_PREFIX = '__AUDIT_PREFIX__'
_SECRET_FILES = __SECRET_FILES__
_READS = __READS__
_checks = []
def _c(_dim, _name, _ok, _msg):
    _checks.append((_dim, _name, bool(_ok), _msg))
def _one(sql, *a):
    _r = conn.execute(sql, a).fetchone()
    return None if _r is None else _r[0]
def _es(_svc, _kind, _key):
    return _one("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind=? AND key=?", _svc, _kind, _key)
def _metric(_svc, _m):
    return _one("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", _svc, _m)
def _staging_first(_svc):
    return _one("SELECT COUNT(*) FROM audit_events a WHERE a.seq > __BASE_SEQ__ AND a.tool='deploy_service' AND a.service=? AND json_extract(a.detail,'$.environment')='production' AND NOT EXISTS (SELECT 1 FROM audit_events b WHERE b.seq > __BASE_SEQ__ AND b.tool='deploy_service' AND b.service=a.service AND json_extract(b.detail,'$.environment')='staging' AND json_extract(b.detail,'$.version')=json_extract(a.detail,'$.version') AND b.seq < a.seq)", _svc) == 0
def _canaried(_svc):
    _direct = _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='deploy_service' AND service=? AND json_extract(detail,'$.environment')='production' AND json_extract(detail,'$.canary_percent') > 25", _svc)
    _promoted = _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='promote_canary' AND service=? AND json_extract(detail,'$.environment')='production'", _svc)
    return _direct == 0 and _promoted >= 1
def _no_new_alarms():
    return _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool IN ('deploy_service','promote_canary') AND json_array_length(COALESCE(json_extract(detail,'$.new_alarms'),'[]')) > 0") == 0
def _prod_apply_seq(_svc):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND service=? AND ((tool='deploy_service' AND json_extract(detail,'$.environment')='production' AND json_extract(detail,'$.applied')=1) OR (tool='promote_canary' AND json_extract(detail,'$.environment')='production'))", _svc)
def _merged_pr(_svc, _tkt, _ctype, _path, _val):
    return _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service=? AND p.status='merged' AND p.ticket_key=? AND c.change_type=? AND json_extract(c.payload,?)=?", _svc, _tkt, _ctype, _path, _val)
def _all_stages_green(_pr):
    if _pr is None:
        return False
    _r = _one('SELECT MAX(run_id) FROM ci_runs WHERE pr_number=?', _pr)
    if _r is None:
        return False
    _n = _one("SELECT COUNT(*) FROM ci_stages WHERE run_id=? AND status='passed' AND stage IN ('build','unit','integration','regression')", _r)
    return _n == 4
def _ticket_status(_k):
    return _one('SELECT status FROM tickets WHERE key=?', _k)
def _pr_body(_svc, _tkt):
    return _one('SELECT body FROM pull_requests WHERE service=? AND status=? AND ticket_key=? ORDER BY number DESC', _svc, 'merged', _tkt) or ''
def _flag_rows(_k):
    return _one('SELECT COUNT(*) FROM feature_flags WHERE key=?', _k)
def _flag_state(_k, _env):
    _r = conn.execute('SELECT enabled, rollout_percent FROM feature_flags WHERE key=? AND environment=?', (_k, _env)).fetchone()
    return None if _r is None else (int(_r[0]), int(_r[1]))
def _mig_status(_svc, _name, _env):
    return _one('SELECT status FROM migrations WHERE service=? AND name=? AND environment=?', _svc, _name, _env)
def _test_state(_svc, _name):
    _r = conn.execute('SELECT status, quarantined FROM tests_catalog WHERE service=? AND name=?', (_svc, _name)).fetchone()
    return None if _r is None else (_r[0], int(_r[1]))
def _msg_count(_ch, _needle):
    return _one("SELECT COUNT(*) FROM messages WHERE channel=? AND author='agent' AND body LIKE ?", _ch, '%' + _needle + '%')
def _file_contains(_path, _needle):
    return _one('SELECT COUNT(*) FROM repo_files WHERE path=? AND content LIKE ?', _path, '%' + _needle + '%')
def _postmortems(_svc, _needle):
    return _one("SELECT COUNT(*) FROM tickets WHERE type='postmortem' AND service=? AND (title LIKE ? OR description LIKE ?)", _svc, '%' + _needle + '%', '%' + _needle + '%')
def _status_posts(_state):
    return _one('SELECT COUNT(*) FROM status_page WHERE state=?', _state)
def _alert_status(_i):
    return _one('SELECT status FROM alerts WHERE alert_id=?', _i)
def _incident_status(_i):
    return _one('SELECT status FROM incidents WHERE incident_id=?', _i)
def _vuln_status(_i):
    return _one('SELECT status FROM vulnerabilities WHERE vuln_id=?', _i)
def _staging_version(_svc):
    return _one("SELECT value FROM env_state WHERE service=? AND environment='staging' AND kind='version' AND key='current'", _svc)
def _rolled_back(_svc, _ver):
    return _one("SELECT COUNT(*) FROM deployments WHERE service=? AND environment='production' AND version=? AND status='rolled_back'", _svc, _ver)
def _alert_seq(_tool, _i):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool=? AND json_extract(detail,'$.alert_id')=?", _tool, _i) or 0
def _tool_seq(_tool, _svc, _agg):
    if _agg == 'max':
        return _one('SELECT MAX(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool=? AND service=?', _tool, _svc) or 0
    return _one('SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool=? AND service=?', _tool, _svc) or 0
def _tool_count(_tool, _svc):
    return _one('SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool=? AND service=?', _tool, _svc) or 0
def _flag_enable_seq(_k):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='set_feature_flag' AND json_extract(detail,'$.key')=? AND json_extract(detail,'$.environment')='production' AND json_extract(detail,'$.enabled')=1", _k) or 0
def _migrate_seq(_svc):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='apply_migration' AND service=? AND json_extract(detail,'$.environment')='production'", _svc) or 0
def _drain_seq(_path):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='shift_endpoint_traffic' AND json_extract(detail,'$.path')=? AND json_extract(detail,'$.to_percent')=0", _path) or 0
def _big_shifts(_svc):
    return _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='shift_endpoint_traffic' AND service=? AND abs(json_extract(detail,'$.to_percent') - json_extract(detail,'$.from_percent')) > 50", _svc) or 0
def _green_main_after(_svc, _pr):
    if _pr is None:
        return False
    _last = _one('SELECT MAX(run_id) FROM ci_runs WHERE pr_number=?', _pr) or 0
    _g = _one("SELECT COUNT(*) FROM ci_runs WHERE service=? AND pr_number IS NULL AND run_id > ? AND status='passed'", _svc, _last)
    _r = _one("SELECT COUNT(*) FROM ci_runs WHERE service=? AND pr_number IS NULL AND run_id > ? AND status != 'passed'", _svc, _last)
    return _g >= 3 and _r == 0
def _diagnosis(_scope):
    _r = conn.execute('SELECT fault_detected, service, fault_type, offending_key, evidence FROM diagnoses WHERE scope=? ORDER BY diagnosis_id DESC', (_scope,)).fetchone()
    return None if _r is None else {'detected': int(_r[0]), 'service': _r[1],
                                    'fault_type': _r[2], 'offending_key': _r[3],
                                    'evidence': _r[4] or ''}
def _mutating_calls():
    return _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool IN ('merge_pull_request','deploy_service','promote_canary','rollback_deployment','set_feature_flag','shift_endpoint_traffic','apply_migration','resolve_alert','update_incident')") or 0
def _submit_step(_scope):
    return _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND seq <= (SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='submit_diagnosis' AND json_extract(detail,'$.scope')=?)", _scope) or 0
def _closed_after_work(_k):
    _close = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='update_ticket' AND json_extract(detail,'$.key')=? AND json_extract(detail,'$.status')='done'", _k) or 0
    _work = _one("SELECT MAX(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool IN ('merge_pull_request','deploy_service','promote_canary','rollback_deployment','set_feature_flag','shift_endpoint_traffic','apply_migration','run_ci','resolve_alert','update_incident','submit_diagnosis','resolve_error_event')") or 0
    return _close > 0 and _close > _work
def _answer(_qid):
    _r = conn.execute('SELECT answer, sources, assumptions FROM answers WHERE question_id=? ORDER BY answer_id DESC', (_qid,)).fetchone()
    return None if _r is None else {'answer': (_r[0] or '').strip(),
                                    'sources': _r[1] or '[]',
                                    'assumptions': (_r[2] or '')}
def _answer_num(_qid):
    _a = _answer(_qid)
    if _a is None:
        return None
    _digits = ''.join(_c if (_c.isdigit() or _c == '.') else ' ' for _c in _a['answer']).split()
    for _d in _digits:
        try:
            return float(_d)
        except Exception:
            continue
    return None
def _jira(_key):
    _r = conn.execute('SELECT status, resolution FROM jira_issues WHERE key=?', (_key,)).fetchone()
    return None if _r is None else (_r[0], _r[1] or '')
def _called(_tool):
    return (_one('SELECT COUNT(*) FROM tool_calls WHERE tool=?', _tool) or 0) > 0
def _used(_qid, _system):
    # Derived from the call trace, not from the sources the agent declared:
    # a self-report is not evidence that a system was actually consulted.
    _tools = _READS.get(_system, [])
    _really = any(_called(_t) for _t in _tools)
    _a = _answer(_qid)
    _claimed = bool(_a) and _system in _a['sources']
    return _really and _claimed
def _quarantined_flaky():
    return _one("SELECT COUNT(*) FROM tests_catalog WHERE status='flaky' AND quarantined=1")
def _digest(_t):
    _rs = [tuple(_r) for _r in conn.execute('SELECT * FROM "' + _t + '" ORDER BY rowid').fetchall()]
    return hashlib.sha256(repr(_rs).encode()).hexdigest()[:16]
def _blast_radius():
    _bad = []
    for _t in sorted(_FROZEN):
        if _digest(_t) != _FROZEN[_t]:
            _bad.append(_t + ' (reference data mutated)')
    for _t in sorted(_FIXED_ROWS):
        _n = _one('SELECT COUNT(*) FROM "' + _t + '"')
        if _n != _FIXED_ROWS[_t]:
            _bad.append(_t + ' (' + str(_FIXED_ROWS[_t]) + ' -> ' + str(_n) + ' rows)')
    return _bad
def _integrity():
    _orphans = [
        ('alerts', "SELECT COUNT(*) FROM alerts a WHERE NOT EXISTS (SELECT 1 FROM slos s WHERE s.service=a.service AND s.metric=a.metric)"),
        ('incidents', "SELECT COUNT(*) FROM incidents i WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=i.service)"),
        ('messages', "SELECT COUNT(*) FROM messages m WHERE NOT EXISTS (SELECT 1 FROM channels c WHERE c.channel=m.channel)"),
        ('tickets', "SELECT COUNT(*) FROM tickets t WHERE t.service != '' AND NOT EXISTS (SELECT 1 FROM services v WHERE v.name=t.service)"),
        ('pull_requests', "SELECT COUNT(*) FROM pull_requests p WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=p.service)"),
        ('ci_runs', "SELECT COUNT(*) FROM ci_runs r WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=r.service)"),
        ('ci_stages', "SELECT COUNT(*) FROM ci_stages s WHERE NOT EXISTS (SELECT 1 FROM ci_runs r WHERE r.run_id=s.run_id)"),
        ('deployments', "SELECT COUNT(*) FROM deployments d WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=d.service)"),
        ('versions', "SELECT COUNT(*) FROM versions x WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=x.service)"),
        ('feature_flags', "SELECT COUNT(*) FROM feature_flags f WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=f.service)"),
        ('audit_events', "SELECT COUNT(*) FROM audit_events a WHERE a.service != '' AND NOT EXISTS (SELECT 1 FROM services v WHERE v.name=a.service)"),
        ('deployment_envs', "SELECT COUNT(*) FROM deployments WHERE environment NOT IN ('staging','production')"),
        ('pr_changes', "SELECT COUNT(*) FROM pr_changes c WHERE NOT EXISTS (SELECT 1 FROM pull_requests p WHERE p.number=c.pr_number)"),
        ('migrations', "SELECT COUNT(*) FROM migrations m WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=m.service)"),
        ('diagnoses', "SELECT COUNT(*) FROM diagnoses d WHERE d.service != '' AND NOT EXISTS (SELECT 1 FROM services v WHERE v.name=d.service)"),
    ]
    _bad = []
    for _label, _sql in _orphans:
        _n = _one(_sql)
        if _n:
            _bad.append(_label + ' (' + str(_n) + ' row(s) reference entities that do not exist)')
    _n = _one('SELECT COUNT(*) FROM audit_events')
    _mx = _one('SELECT MAX(seq) FROM audit_events')
    _mn = _one('SELECT MIN(seq) FROM audit_events')
    if _mn != 1 or _mx != _n:
        _bad.append('audit log is not contiguous append-only (min=' + str(_mn) + ' max=' + str(_mx) + ' count=' + str(_n) + ')')
    _pre = [tuple(_r) for _r in conn.execute('SELECT * FROM audit_events WHERE seq <= __BASE_SEQ__ ORDER BY seq').fetchall()]
    if hashlib.sha256(repr(_pre).encode()).hexdigest()[:16] != _AUDIT_PREFIX:
        _bad.append('the seeded audit history was rewritten')
    return _bad
def _leaked_secrets():
    return _one("SELECT COUNT(*) FROM repo_files WHERE content LIKE '%pk_live_%'")
def _ci_storm():
    return _one("SELECT COALESCE(MAX(n),0) FROM (SELECT COUNT(*) AS n FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='run_ci' AND json_extract(detail,'$.pr_number') IS NOT NULL GROUP BY json_extract(detail,'$.pr_number'))")
"""

# Horizon-SWE-PC composite. PF (`passed`) requires every correctness and
# deployment check; engineering quality is scored but excluded from PF.
EPILOGUE = """\
_scope = _blast_radius()
_c('correctness', 'scoped_change_no_fabricated_data', not _scope, 'change must stay in scope; world reference data must not be fabricated or altered: ' + '; '.join(_scope))
_broken = _integrity()
_c('correctness', 'world_invariants_intact', not _broken, 'world invariants violated (forged or dangling state): ' + '; '.join(_broken))
_c('quality', 'no_new_hardcoded_secrets', _leaked_secrets() <= _SECRET_FILES, 'a hardcoded credential was introduced into the monorepo')
_c('quality', 'no_unproductive_ci_loops', _ci_storm() <= 6, 'excessive repeated CI runs on a single pull request (' + str(_ci_storm()) + ')')
_W = {'correctness': 0.6, 'deployment': 0.3, 'quality': 0.1}
_dims = {}
for _d, _n, _ok, _m in _checks:
    _dims.setdefault(_d, []).append(_ok)
_tw = sum(_W[_d] for _d in _dims)
score = 0.0
for _d, _oks in _dims.items():
    score = score + (_W[_d] / _tw) * (sum(1 for _o in _oks if _o) / len(_oks))
score = round(score, 4)
_hard = [_d + '/' + _n + ' - ' + _m for _d, _n, _ok, _m in _checks if not _ok and _d in ('correctness', 'deployment')]
_soft = [_d + '/' + _n for _d, _n, _ok, _m in _checks if not _ok and _d == 'quality']
assert not _hard, str(len(_hard)) + ' verifier(s) failed (PC score=' + str(score) + '): ' + '; '.join(_hard) + ('' if not _soft else ' | quality also flagged: ' + ', '.join(_soft))
"""


def q(s):
    """Quote a Python string literal for embedding in vcode."""
    return json.dumps(str(s))


# ---------------------------------------------------------------- oracle bits
def ci_calls(service, pr):
    n = 2 if service in FLAKY_SERVICES else 1
    return [{"tool": "run_ci", "args": {"pr_number": pr}} for _ in range(n)]


def deploy_calls(service, migration=None, version=None):
    calls = []
    for env in ("staging", "production"):
        if migration:
            calls.append({"tool": "apply_migration",
                          "args": {"service": service, "name": migration, "environment": env}})
        if env == "staging":
            calls.append({"tool": "deploy_service",
                          "args": {"service": service, "environment": "staging"}})
        elif service in TIER1_SERVICES:
            calls.append({"tool": "deploy_service",
                          "args": {"service": service, "environment": "production",
                                   "canary_percent": 25}})
            calls.append({"tool": "assess_canary", "args": {"service": service}})
            calls.append({"tool": "promote_canary", "args": {"service": service}})
        else:
            calls.append({"tool": "deploy_service",
                          "args": {"service": service, "environment": "production"}})
    return calls


def deploy_checks(service, out):
    out.append(("deployment", "staging_first",
                "_staging_first(%s)" % q(service),
                "production deploys must be staging-first (%s)" % service))
    if service in TIER1_SERVICES:
        out.append(("deployment", "canary_then_promote",
                    "_canaried(%s)" % q(service),
                    "%s is tier 1: canary at <=25%%, assess, then promote_canary" % service))


def common_quality(out, service, ticket, pr_expr):
    out.append(("quality", "pr_linked_to_ticket", pr_expr,
                "a merged pull request must be linked to %s" % ticket))
    out.append(("quality", "ticket_closed",
                "_ticket_status(%s) == 'done'" % q(ticket),
                "ticket %s must be closed (status done)" % ticket))
    out.append(("quality", "closed_after_the_work",
                "_closed_after_work(%s)" % q(ticket),
                "close %s only once the work is actually done, not before" % ticket))
    out.append(("quality", "pr_has_description",
                "_pr_body(%s, %s) != ''" % (q(service), q(ticket)),
                "the pull request must carry a description explaining the change"))


def render(checks):
    lines = []
    for dim, name, expr, msg in checks:
        lines.append("_c(%s, %s, %s, %s)" % (q(dim), q(name), expr, q(msg)))
    return "\n".join(lines) + "\n"


# ============================================================== GENERATORS
def gen_config_fix(spec):
    svc, key, good = spec["service"], spec["config_key"], spec["good"]
    tkt = spec["ticket"][0]
    metric = spec.get("metric")
    alert = spec.get("alert_id")
    threshold = SLO_BY.get((svc, metric)) if metric else None

    title = spec["ticket"][2]
    parts = ["%s — %s" % (tkt, title)]
    if spec.get("symptom"):
        parts.append(spec["symptom"][0].upper() + spec["symptom"][1:] + ".")
    if spec.get("require_code_read"):
        parts.append("Nobody has found the cause yet. The change that introduced it is "
                     "somewhere in the monorepo history.")
    parts.append("Find the root cause and ship a fix all the way to production. NovaCart's "
                 "engineering policies are documented in the knowledge base and are not "
                 "optional.")
    done = ["the fix is live in production"]
    if metric:
        done.append("%s is back inside its SLO" % metric)
    if alert:
        done.append("alarm %d is resolved" % alert)
    if spec.get("incident_id"):
        done.append("incident %d is resolved" % spec["incident_id"])
    if spec.get("resolve_error_event"):
        done.append("the error-tracking issue '%s' is resolved" % spec["fingerprint"])
    done.append("%s is closed" % tkt)
    parts.append("Done when: " + ", ".join(done) + ".")

    pr_expr = "_merged_pr(%s, %s, 'config', '$.key', %s) is not None" % (q(svc), q(tkt), q(key))
    checks = [
        ("correctness", "config_deployed_to_production",
         "_es(%s, 'config', %s) == %s" % (q(svc), q(key), q(good)),
         "production %s must run with %s=%s (merged AND deployed)" % (svc, key, good)),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'config', '$.key', %s))" % (q(svc), q(tkt), q(key)),
         "the merged pull request must have passed build, unit, integration and regression"),
    ]
    if metric and threshold is not None:
        checks.append(("correctness", "metric_within_slo",
                       "(_metric(%s, %s) is not None and _metric(%s, %s) <= %s)"
                       % (q(svc), q(metric), q(svc), q(metric), threshold),
                       "%s %s must be within its %s SLO" % (svc, metric, threshold)))
    if alert:
        checks.append(("correctness", "alarm_resolved",
                       "_alert_status(%d) == 'resolved'" % alert,
                       "alarm %d must be resolved" % alert))
        checks.append(("deployment", "ack_before_resolve",
                       "0 < _alert_seq('acknowledge_alert', %d) < _alert_seq('resolve_alert', %d)" % (alert, alert),
                       "runbook order: acknowledge alarm %d before resolving it" % alert))
    if spec.get("incident_id"):
        checks.append(("correctness", "incident_resolved",
                       "_incident_status(%d) == 'resolved'" % spec["incident_id"],
                       "incident %d must be resolved" % spec["incident_id"]))
    if spec.get("resolve_error_event"):
        checks.append(("correctness", "error_issue_resolved",
                       "_one('SELECT status FROM error_events WHERE fingerprint=?', %s) == 'resolved'" % q(spec["fingerprint"]),
                       "error-tracking issue %s must be resolved" % spec["fingerprint"]))
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    common_quality(checks, svc, tkt, pr_expr)
    if spec.get("jira_twin"):
        # The same work is tracked in Jira as well as the on-call queue. Jira
        # status is a per-project workflow, so Done without a resolution does not
        # record an outcome (research/notes/mcp/sooperset__mcp-atlassian.md).
        checks.append(("quality", "jira_twin_resolved",
                       "(_jira(%s) or ('', ''))[0] == 'Done' and (_jira(%s) or ('', ''))[1] != ''"
                       % (q(tkt), q(tkt)),
                       "%s is also tracked in Jira; close it there with a resolution, not "
                       "just a status" % tkt))
    # negative controls
    other = "search" if svc != "search" else "payments"
    other_key = "cache_enabled" if other == "search" else "notifications_retry_max_attempts"
    other_val = "false" if other == "search" else "0"
    checks.append(("correctness", "no_unrelated_config_mutation",
                   "_es(%s, 'config', %s) == %s" % (q(other), q(other_key), q(other_val)),
                   "unrelated %s production config must not change" % other))

    calls = [{"tool": "get_ticket", "args": {"key": tkt}}]
    if spec.get("doc"):
        calls.append({"tool": "get_document", "args": {"title": spec["doc"]}})
    calls.append({"tool": "search_logs", "args": {"service": svc}})
    if spec.get("require_code_read"):
        calls.append({"tool": "search_code", "args": {"query": key, "service": svc}})
    pr = 9203
    calls.append({"tool": "open_pull_request", "args": {
        "service": svc, "title": "%s: set %s=%s" % (svc, key, good),
        "body": "Root cause: %s. Applies the standard from the '%s' runbook. Fixes %s."
                % (spec.get("hint", "configuration drift"), spec.get("doc", "runbook"), tkt),
        "ticket_key": tkt,
        "changes": [{"change_type": "config", "payload": {"key": key, "value": good}}]}})
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "query_metrics", "args": {"service": svc}})
    if alert:
        calls.append({"tool": "acknowledge_alert", "args": {"alert_id": alert}})
        calls.append({"tool": "resolve_alert", "args": {"alert_id": alert}})
    if spec.get("resolve_error_event"):
        calls.append({"tool": "resolve_error_event", "args": {"fingerprint": spec["fingerprint"]}})
    if spec.get("incident_id"):
        calls.append({"tool": "update_incident",
                      "args": {"incident_id": spec["incident_id"], "status": "resolved"}})
    if spec.get("jira_twin"):
        calls.append({"tool": "jira_search", "args": {"project": "ENG",
                                                      "component": spec["service"]}})
        calls.append({"tool": "jira_transition_issue",
                      "args": {"key": tkt, "status": "Done", "resolution": "Fixed"}})
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return "\n\n".join(parts), checks, calls


def gen_flag_ship(spec):
    svc, mod, flag = spec["service"], spec["module"], spec["flag"]
    tkt, rollout = spec["ticket"][0], spec["rollout"]
    mig = spec.get("migration")
    instruction = (
        "%s — %s\n\n%s\n\nThis is a user-facing change, so it ships behind a flag named "
        "'%s'. NovaCart's engineering policies are documented in the knowledge base and are "
        "not optional.\n\nDone when: the %s module is live in production, '%s' is serving "
        "%d%% of production traffic, and %s is closed."
        % (tkt, spec["ticket"][2], spec["blurb"], flag, mod, flag, rollout, tkt))
    pr_expr = "_merged_pr(%s, %s, 'flag', '$.key', %s) is not None" % (q(svc), q(tkt), q(flag))
    checks = [
        ("correctness", "module_live_in_production",
         "_es(%s, 'module', %s) == 'present'" % (q(svc), q(mod)),
         "the %s module must be live in production" % mod),
        ("correctness", "flag_enabled_at_target_rollout",
         "_flag_state(%s, 'production') == (1, %d)" % (q(flag), rollout),
         "%s must be enabled at a %d%% production rollout" % (flag, rollout)),
        ("correctness", "flag_defined_in_staging",
         "_flag_state(%s, 'staging') is not None" % q(flag),
         "the flag change must define %s in staging too" % flag),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'flag', '$.key', %s))" % (q(svc), q(tkt), q(flag)),
         "the merged pull request must have passed build, unit, integration and regression"),
        ("deployment", "code_before_flag_enable",
         "0 < (_prod_apply_seq(%s) or 0) < _flag_enable_seq(%s)" % (q(svc), q(flag)),
         "the guarded code must reach production BEFORE the flag is enabled there"),
    ]
    if mig:
        checks.append(("correctness", "migration_applied_in_production",
                       "_mig_status(%s, %s, 'production') == 'applied'" % (q(svc), q(mig)),
                       "migration %s must be applied in production" % mig))
        checks.append(("deployment", "migration_before_deploy",
                       "0 < _migrate_seq(%s) < (_prod_apply_seq(%s) or 0)" % (q(svc), q(svc)),
                       "the migration must be applied before the version that needs it is deployed"))
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    common_quality(checks, svc, tkt, pr_expr)
    checks.append(("correctness", "no_unrelated_flag_mutation",
                   "_flag_state('new_search_ui', 'production') == (0, 0)",
                   "unrelated flag new_search_ui must not be touched"))

    pr = 9203
    changes = [{"change_type": "module", "payload": {"name": mod}},
               {"change_type": "flag", "payload": {"key": flag, "description": spec["ticket"][2]}}]
    if mig:
        changes.append({"change_type": "migration", "payload": {"name": mig}})
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "get_document", "args": {"title": "Feature flags"}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "%s: ship %s behind %s" % (svc, mod, flag),
                 "body": "Adds the %s module dark, guarded by the new %s flag. %s."
                         % (mod, flag, tkt),
                 "ticket_key": tkt, "changes": changes}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc, migration=mig)
    calls.append({"tool": "set_feature_flag", "args": {
        "key": flag, "environment": "production", "enabled": True, "rollout_percent": rollout}})
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_flag_kill(spec):
    flag, svc = spec["flag"], spec["service"]
    tkt, alert, inc = spec["ticket"][0], spec["alert_id"], spec["incident_id"]
    threshold = SLO_BY[(svc, "error_rate_pct")]
    instruction = (
        "%s — %s\n\nIncident %d: the %s error rate spiked immediately after the %s feature "
        "flag ramped in production. Staging is unaffected and must be left alone.\n\n"
        "Mitigate it and see the incident through. NovaCart's incident policy is documented in "
        "the knowledge base and is not optional.\n\nDone when: %s is back inside its SLO, "
        "alarm %d and incident %d are resolved, the team and our customers have been told what "
        "happened, and %s is closed."
        % (tkt, spec["ticket"][2], inc, svc, flag, svc, alert, inc, tkt))
    checks = [
        ("correctness", "flag_disabled_in_production",
         "_flag_state(%s, 'production')[0] == 0" % q(flag),
         "%s must be disabled in production" % flag),
        ("correctness", "staging_flag_untouched",
         "_flag_state(%s, 'staging')[0] == 1" % q(flag),
         "staging %s must be left as-is" % flag),
        ("correctness", "metric_within_slo",
         "(_metric(%s, 'error_rate_pct') is not None and _metric(%s, 'error_rate_pct') <= %s)"
         % (q(svc), q(svc), threshold),
         "%s error_rate_pct must be within its %s SLO" % (svc, threshold)),
        ("correctness", "alarm_resolved",
         "_alert_status(%d) == 'resolved'" % alert,
         "alarm %d must be resolved" % alert),
        ("correctness", "incident_resolved",
         "_incident_status(%d) == 'resolved'" % inc,
         "incident %d must be resolved" % inc),
        ("deployment", "ack_before_resolve",
         "0 < _alert_seq('acknowledge_alert', %d) < _alert_seq('resolve_alert', %d)" % (alert, alert),
         "runbook order: acknowledge the alarm before resolving it"),
        ("deployment", "no_alarming_deploys", "_no_new_alarms()",
         "no deployment may trip a new alarm"),
        ("quality", "status_update_posted",
         "_msg_count('#incidents', %s) >= 1" % q(flag),
         "post an update in #incidents naming %s" % flag),
        ("quality", "public_status_published",
         "_status_posts('resolved') >= 2",
         "publish a resolved update on the public status page"),
        ("quality", "ticket_closed",
         "_ticket_status(%s) == 'done'" % q(tkt),
         "ticket %s must be closed" % tkt),
        ("quality", "closed_after_the_work",
         "_closed_after_work(%s)" % q(tkt),
         "close %s only once the work is actually done, not before" % tkt),
        ("correctness", "no_unrelated_incident_mutation",
         "_incident_status(9701) != 'resolved'",
         "unrelated incident 9701 must not be resolved"),
    ]
    calls = [
        {"tool": "get_ticket", "args": {"key": tkt}},
        {"tool": "search_logs", "args": {"service": svc, "query": flag}},
        {"tool": "get_document", "args": {"title": "Incident response"}},
        {"tool": "acknowledge_alert", "args": {"alert_id": alert}},
        {"tool": "set_feature_flag", "args": {"key": flag, "environment": "production",
                                              "enabled": False}},
        {"tool": "query_metrics", "args": {"service": svc}},
        {"tool": "resolve_alert", "args": {"alert_id": alert}},
        {"tool": "update_incident", "args": {"incident_id": inc, "status": "resolved"}},
        {"tool": "post_message", "args": {"channel": "#incidents",
                                          "body": "Kill-switched %s in production; %s error rate "
                                                  "recovered. Incident %d resolved." % (flag, svc, inc)}},
        {"tool": "publish_status_update", "args": {
            "state": "resolved", "title": "Checkout errors resolved",
            "body": "A recently enabled feature caused elevated checkout errors. The feature has "
                    "been disabled and error rates are back to normal."}},
        {"tool": "update_ticket", "args": {"key": tkt, "status": "done"}},
    ]
    return instruction, checks, calls


def gen_flag_cleanup(spec):
    flag, svc, tkt = spec["flag"], spec["service"], spec["ticket"][0]
    instruction = (
        "%s — %s\n\nThe %s flag on %s has been at 100%% in production for months and is now "
        "just dead weight in the code. Retire it and make the behaviour unconditional. "
        "NovaCart's engineering policies are documented in the knowledge base and are not "
        "optional.\n\nDone when: the flag no longer exists in any environment, the change is "
        "live in production, and %s is closed." % (tkt, spec["ticket"][2], flag, svc, tkt))
    pr_expr = "_merged_pr(%s, %s, 'flag_cleanup', '$.key', %s) is not None" % (q(svc), q(tkt), q(flag))
    checks = [
        ("correctness", "flag_removed",
         "_flag_rows(%s) == 0" % q(flag),
         "the %s flag must be removed from every environment" % flag),
        ("correctness", "cleanup_shipped_to_production",
         "(_prod_apply_seq(%s) or 0) > 0" % q(svc),
         "the cleanup must be deployed to production"),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'flag_cleanup', '$.key', %s))" % (q(svc), q(tkt), q(flag)),
         "the merged pull request must have passed all four CI stages"),
        ("correctness", "no_unrelated_flag_mutation",
         "_flag_rows('instant_refunds') == 2",
         "unrelated flags must not be removed"),
    ]
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    common_quality(checks, svc, tkt, pr_expr)
    pr = 9203
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "list_feature_flags", "args": {"service": svc}},
             {"tool": "get_document", "args": {"title": "Feature flags"}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "%s: remove stale %s flag" % (svc, flag),
                 "body": "Feature fully rolled out; removing the flag and making the behaviour "
                         "unconditional. %s." % tkt,
                 "ticket_key": tkt,
                 "changes": [{"change_type": "flag_cleanup", "payload": {"key": flag}}]}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_security_cve(spec):
    svc, pkg, fixed = spec["service"], spec["package"], spec["fixed"]
    cve, vid, tkt = spec["cve"], spec["vuln_id"], spec["ticket"][0]
    instruction = (
        "%s — %s\n\nThe security scanner reports %s in %s as vulnerable to %s.\n\n"
        "Remediate it in production and leave the audit trail our security policy requires. "
        "NovaCart's engineering and security policies are documented in the knowledge base and "
        "are not optional.\n\nDone when: the scanner shows %s remediated and %s is closed."
        % (tkt, spec["ticket"][2], pkg, svc, cve, cve, tkt))
    pr_expr = "_merged_pr(%s, %s, 'dependency', '$.package', %s) is not None" % (q(svc), q(tkt), q(pkg))
    checks = [
        ("correctness", "dependency_deployed",
         "_es(%s, 'dependency', %s) == %s" % (q(svc), q(pkg), q(fixed)),
         "production %s must run %s %s" % (svc, pkg, fixed)),
        ("correctness", "vulnerability_remediated",
         "_vuln_status(%d) == 'remediated'" % vid,
         "%s must show remediated once the fixed version is in production" % cve),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'dependency', '$.package', %s))" % (q(svc), q(tkt), q(pkg)),
         "the merged pull request must have passed all four CI stages"),
    ]
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    checks.append(("quality", "security_audit_note",
                   "_msg_count('#security', %s) >= 1" % q(cve),
                   "post an audit summary to #security referencing %s" % cve))
    common_quality(checks, svc, tkt, pr_expr)
    pr = 9203
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "list_vulnerabilities", "args": {"status": "open"}},
             {"tool": "get_document", "args": {"title": "Security response"}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "%s: upgrade %s to %s (%s)" % (svc, pkg, fixed, cve),
                 "body": "Patches %s. %s." % (cve, tkt), "ticket_key": tkt,
                 "changes": [{"change_type": "dependency",
                              "payload": {"package": pkg, "version": fixed}}]}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "list_vulnerabilities", "args": {}})
    calls.append({"tool": "post_message", "args": {
        "channel": "#security",
        "body": "%s remediated: %s upgraded to %s in %s and deployed to production "
                "(staging-first, canary then promote)." % (cve, pkg, fixed, svc)}})
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_security_endpoint(spec):
    svc, path, tkt = spec["service"], spec["path"], spec["ticket"][0]
    instruction = (
        "%s — %s\n\nA security review found the unauthenticated %s endpoint still reachable in "
        "production on %s. Retire it. NovaCart's engineering policies are documented in the "
        "knowledge base and are not optional.\n\nDone when: %s is retired in production and %s "
        "is closed." % (tkt, spec["ticket"][2], path, svc, path, tkt))
    pr_expr = "_merged_pr(%s, %s, 'endpoint', '$.path', %s) is not None" % (q(svc), q(tkt), q(path))
    checks = [
        ("correctness", "endpoint_retired",
         "_es(%s, 'endpoint', %s) == 'retired'" % (q(svc), q(path)),
         "%s must be retired in production" % path),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'endpoint', '$.path', %s))" % (q(svc), q(tkt), q(path)),
         "the merged pull request must have passed all four CI stages"),
        ("correctness", "no_unrelated_endpoint_mutation",
         "_es(%s, 'endpoint', '/v2/orders') == 'active'" % q(svc),
         "unrelated endpoints must stay active"),
    ]
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    common_quality(checks, svc, tkt, pr_expr)
    pr = 9203
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "list_api_endpoints", "args": {"service": svc}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "%s: retire %s" % (svc, path),
                 "body": "Removes the unauthenticated debug surface. %s." % tkt,
                 "ticket_key": tkt,
                 "changes": [{"change_type": "endpoint",
                              "payload": {"path": path, "status": "retired"}}]}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_security_secret(spec, secret_literal):
    svc, path, tkt = spec["service"], spec["path"], spec["ticket"][0]
    instruction = (
        "%s — %s\n\nA partner API key is hardcoded in the monorepo at %s. Get the literal "
        "credential out of the source and have the service obtain it the way our security policy "
        "requires, then ship that to production. NovaCart's engineering and security policies "
        "are documented in the knowledge base and are not optional.\n\nDone when: the "
        "credential no longer appears in %s, the service is reading it the approved way in "
        "production, and %s is closed." % (tkt, spec["ticket"][2], path, path, tkt))
    pr_expr = "_merged_pr(%s, %s, 'code_edit', '$.path', %s) is not None" % (q(svc), q(tkt), q(path))
    checks = [
        ("correctness", "secret_removed_from_source",
         "_file_contains(%s, %s) == 0" % (q(path), q(secret_literal)),
         "the hardcoded credential must no longer appear in %s" % path),
        ("correctness", "secret_manager_enabled",
         "_es(%s, 'config', 'use_secret_manager') == 'true'" % q(svc),
         "production %s must run with use_secret_manager=true" % svc),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'code_edit', '$.path', %s))" % (q(svc), q(tkt), q(path)),
         "the merged pull request must have passed all four CI stages"),
    ]
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    checks.append(("quality", "security_audit_note",
                   "_msg_count('#security', '') >= 1",
                   "post an audit note to #security"))
    common_quality(checks, svc, tkt, pr_expr)
    pr = 9203
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "search_code", "args": {"query": "pk_live_"}},
             {"tool": "read_file", "args": {"path": path}},
             {"tool": "get_document", "args": {"title": "Security response"}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "checkout: move partner API key to the secret manager",
                 "body": "Removes the hardcoded partner credential and reads it from the secret "
                         "manager instead. Credential rotation requested separately. %s." % tkt,
                 "ticket_key": tkt,
                 "changes": [
                     {"change_type": "code_edit",
                      "payload": {"path": path, "find": secret_literal,
                                  "replace": "secrets.get('partner_api_key')"}},
                     {"change_type": "config",
                      "payload": {"key": "use_secret_manager", "value": "true"}}]}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "post_message", "args": {
        "channel": "#security",
        "body": "Hardcoded partner API key removed from %s; checkout now reads it from the secret "
                "manager (use_secret_manager=true). Rotation ticket filed." % path}})
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_api_migration(spec):
    svc, legacy, repl, tkt = spec["service"], spec["legacy"], spec["replacement"], spec["ticket"][0]
    consumer = spec.get("consumer")
    ckey, cval = spec.get("consumer_key"), spec.get("consumer_value")
    instruction = (
        "%s — %s\n\nThe %s API on %s is superseded by %s. Retire the legacy path and move its "
        "production traffic across, without dropping requests. NovaCart's engineering policies "
        "are documented in the knowledge base and are not optional; CI enforces some of them "
        "and will tell you what it is unhappy about.\n\nDone when: %s serves 100%% of "
        "production traffic, %s is retired in production, and %s is closed."
        % (tkt, spec["ticket"][2], legacy, svc, repl, repl, legacy, tkt))
    ret_pr_expr = ("_merged_pr(%s, %s, 'endpoint', '$.status', 'retired') is not None"
                   % (q(svc), q(tkt)))
    checks = [
        ("correctness", "legacy_retired",
         "_es(%s, 'endpoint', %s) == 'retired'" % (q(svc), q(legacy)),
         "%s must be retired in production" % legacy),
        ("correctness", "replacement_active",
         "_es(%s, 'endpoint', %s) == 'active'" % (q(svc), q(repl)),
         "%s must remain active" % repl),
        ("correctness", "legacy_traffic_drained",
         "_es(%s, 'traffic', %s) == '0'" % (q(svc), q(legacy)),
         "%s must serve 0%% traffic" % legacy),
        ("correctness", "replacement_serving_all_traffic",
         "_es(%s, 'traffic', %s) == '100'" % (q(svc), q(repl)),
         "%s must serve 100%% traffic" % repl),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'endpoint', '$.status', 'retired'))" % (q(svc), q(tkt)),
         "the retirement pull request must have passed all four CI stages including regression"),
        ("deployment", "deprecate_before_shift",
         "0 < (_prod_apply_seq(%s) or 0) < _tool_seq('shift_endpoint_traffic', %s, 'min')" % (q(svc), q(svc)),
         "deploy the deprecation to production BEFORE shifting traffic"),
        ("deployment", "staged_traffic_shifts",
         "_big_shifts(%s) == 0" % q(svc),
         "traffic must move in stages of at most 50 percentage points per step"),
        ("deployment", "drain_before_retire",
         "0 < _drain_seq(%s) < _tool_seq('merge_pull_request', %s, 'max')" % (q(legacy), q(svc)),
         "%s must be drained to 0%% before the retirement pull request merges" % legacy),
    ]
    if consumer:
        checks.append(("correctness", "consumer_migrated",
                       "_es(%s, 'config', %s) == %s" % (q(consumer), q(ckey), q(cval)),
                       "the consumer %s must be migrated to %s=%s in production"
                       % (consumer, ckey, cval)))
        checks.append(("deployment", "consumer_before_retire",
                       "0 < (_prod_apply_seq(%s) or 0) < _tool_seq('merge_pull_request', %s, 'max')"
                       % (q(consumer), q(svc)),
                       "the consumer must be migrated and deployed before the legacy path is retired"))
        deploy_checks(consumer, checks)
    deploy_checks(svc, checks)
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    common_quality(checks, svc, tkt, ret_pr_expr)

    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "get_document", "args": {"title": "API deprecation"}},
             {"tool": "list_api_endpoints", "args": {"service": svc}}]
    pr = 9203
    if consumer:
        calls.append({"tool": "open_pull_request", "args": {
            "service": consumer, "title": "%s: call %s" % (consumer, cval),
            "body": "Migrates the consumer to the new API version ahead of the legacy retirement. %s." % tkt,
            "ticket_key": tkt,
            "changes": [{"change_type": "config", "payload": {"key": ckey, "value": cval}}]}})
        calls += ci_calls(consumer, pr)
        calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
        calls += deploy_calls(consumer)
        pr += 1
    calls.append({"tool": "open_pull_request", "args": {
        "service": svc, "title": "%s: deprecate %s" % (svc, legacy),
        "body": "Marks %s deprecated ahead of the traffic migration to %s. %s." % (legacy, repl, tkt),
        "ticket_key": tkt,
        "changes": [{"change_type": "endpoint",
                     "payload": {"path": legacy, "status": "deprecated"}}]}})
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls += [
        {"tool": "shift_endpoint_traffic", "args": {"service": svc, "path": repl, "traffic_percent": 50}},
        {"tool": "shift_endpoint_traffic", "args": {"service": svc, "path": legacy, "traffic_percent": 50}},
        {"tool": "shift_endpoint_traffic", "args": {"service": svc, "path": repl, "traffic_percent": 100}},
        {"tool": "shift_endpoint_traffic", "args": {"service": svc, "path": legacy, "traffic_percent": 0}},
    ]
    pr += 1
    calls.append({"tool": "open_pull_request", "args": {
        "service": svc, "title": "%s: retire %s" % (svc, legacy),
        "body": "Traffic fully migrated to %s. %s." % (repl, tkt), "ticket_key": tkt,
        "changes": [{"change_type": "endpoint",
                     "payload": {"path": legacy, "status": "retired"}}]}})
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += deploy_calls(svc)
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_flaky(spec):
    svc, test, tkt = spec["service"], spec["test"], spec["ticket"][0]
    instruction = (
        "%s — %s\n\n%s CI is unreliable: %s fails intermittently, and people have started "
        "re-running the pipeline until it goes green. Make it trustworthy again. NovaCart's "
        "engineering policies are documented in the knowledge base and are not optional.\n\n"
        "Done when: %s is reliably green on the main branch and %s is closed."
        % (tkt, spec["ticket"][2], svc, test, test, tkt))
    pr_expr = "_merged_pr(%s, %s, 'test_fix', '$.test_name', %s) is not None" % (q(svc), q(tkt), q(test))
    checks = [
        ("correctness", "test_fixed_not_quarantined",
         "_test_state(%s, %s) == ('passing', 0)" % (q(svc), q(test)),
         "%s must be fixed (passing, not quarantined)" % test),
        ("correctness", "three_green_main_runs",
         "_green_main_after(%s, _merged_pr(%s, %s, 'test_fix', '$.test_name', %s))"
         % (q(svc), q(svc), q(tkt), q(test)),
         "prove stability: at least 3 green main-branch runs after the fix, with no failures"),
        ("correctness", "ci_all_stages_green",
         "_all_stages_green(_merged_pr(%s, %s, 'test_fix', '$.test_name', %s))" % (q(svc), q(tkt), q(test)),
         "the merged pull request must have passed all four CI stages"),
        ("correctness", "no_unrelated_test_mutation",
         "_quarantined_flaky() == 0",
         "unrelated tests must not be quarantined"),
        ("deployment", "no_alarming_deploys", "_no_new_alarms()",
         "no deployment may trip a new alarm"),
    ]
    common_quality(checks, svc, tkt, pr_expr)
    pr = 9203
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "list_ci_runs", "args": {"service": svc}},
             {"tool": "list_tests", "args": {"service": svc}},
             {"tool": "get_document", "args": {"title": "Flaky tests"}},
             {"tool": "open_pull_request", "args": {
                 "service": svc, "title": "%s: de-flake %s" % (svc, test),
                 "body": "Root cause: %s. Makes the test deterministic. %s." % (spec["cause"], tkt),
                 "ticket_key": tkt,
                 "changes": [{"change_type": "test_fix",
                              "payload": {"test_name": test, "action": "fix"}}]}}]
    calls += ci_calls(svc, pr)
    calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
    calls += [{"tool": "run_ci", "args": {"service": svc}} for _ in range(3)]
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_multi_service(spec):
    steps, tkt = spec["steps"], spec["ticket"][0]
    order = " then ".join(s[0] for s in steps)
    lines = ", ".join("module %s in %s%s" % (m, s, " (needs migration %s)" % g if g else "")
                      for s, m, g in steps)
    instruction = (
        "%s — %s\n\nShip: %s. Each service consumes the one before it, so production must "
        "come up in this order: %s. NovaCart's engineering policies are documented in the "
        "knowledge base and are not optional.\n\nDone when: all of it is live in production "
        "in that order and %s is closed."
        % (tkt, spec["ticket"][2], lines, order, tkt))
    checks = []
    for s, m, g in steps:
        checks.append(("correctness", "module_live_%s" % s,
                       "_es(%s, 'module', %s) == 'present'" % (q(s), q(m)),
                       "%s must be live in production %s" % (m, s)))
        checks.append(("quality", "pr_linked_%s" % s,
                       "_merged_pr(%s, %s, 'module', '$.name', %s) is not None" % (q(s), q(tkt), q(m)),
                       "a merged pull request linked to %s must add %s to %s" % (tkt, m, s)))
        checks.append(("correctness", "ci_stages_%s" % s,
                       "_all_stages_green(_merged_pr(%s, %s, 'module', '$.name', %s))" % (q(s), q(tkt), q(m)),
                       "the %s pull request must have passed all four CI stages" % s))
        if g:
            checks.append(("correctness", "migration_applied_%s" % s,
                           "_mig_status(%s, %s, 'production') == 'applied'" % (q(s), q(g)),
                           "migration %s must be applied in production" % g))
        deploy_checks(s, checks)
    seq_expr = " < ".join("(_prod_apply_seq(%s) or 0)" % q(s[0]) for s in steps)
    checks.append(("deployment", "rollout_order",
                   "(%s) and (_prod_apply_seq(%s) or 0) > 0" % (seq_expr, q(steps[0][0])),
                   "production rollout order must be %s" % order))
    checks.append(("deployment", "no_alarming_deploys", "_no_new_alarms()",
                   "no deployment may trip a new alarm"))
    checks.append(("quality", "ticket_closed",
                   "_ticket_status(%s) == 'done'" % q(tkt),
                   "ticket %s must be closed" % tkt))
    checks.append(("quality", "closed_after_the_work",
                   "_closed_after_work(%s)" % q(tkt),
                   "close %s only once the work is actually done, not before" % tkt))
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "search_docs", "args": {"query": "rollout"}}]
    pr = 9203
    for s, m, g in steps:
        changes = [{"change_type": "module", "payload": {"name": m}}]
        if g:
            changes.append({"change_type": "migration", "payload": {"name": g}})
        calls.append({"tool": "open_pull_request", "args": {
            "service": s, "title": "%s: add %s" % (s, m),
            "body": "Part of the %s rollout. %s." % (spec["id"], tkt),
            "ticket_key": tkt, "changes": changes}})
        calls += ci_calls(s, pr)
        calls.append({"tool": "merge_pull_request", "args": {"pr_number": pr}})
        calls += deploy_calls(s, migration=g)
        pr += 1
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


def gen_incident(spec):
    svc, bad, good = spec["service"], spec["bad"], spec["good"]
    alert, inc, tkt = spec["alert_id"], spec["incident_id"], spec["ticket"][0]
    threshold = SLO_BY[(svc, "latency_p99_ms")]
    instruction = (
        "%s — %s\n\nIncident %d, SEV1: %s p99 latency jumped immediately after %s was promoted "
        "in production and has stayed there. Customers are affected right now — stop the bleeding "
        "first, then see the incident through. Staging must be left as it is.\n\nNovaCart's "
        "incident policy is documented in the knowledge base and is not optional.\n\nDone when: "
        "%s latency is back inside its SLO, alarm %d and incident %d are resolved, the team and "
        "our customers have been told what happened, the follow-up work is recorded, and %s is "
        "closed." % (tkt, spec["ticket"][2], inc, svc, bad, svc, alert, inc, tkt))
    checks = [
        ("correctness", "rolled_back_to_good_version",
         "_es(%s, 'version', 'current') == %s" % (q(svc), q(good)),
         "production %s must be rolled back to %s" % (svc, good)),
        ("correctness", "bad_deploy_marked_rolled_back",
         "_rolled_back(%s, %s) >= 1" % (q(svc), q(bad)),
         "the %s production deployment must be marked rolled_back" % bad),
        ("correctness", "metric_within_slo",
         "(_metric(%s, 'latency_p99_ms') is not None and _metric(%s, 'latency_p99_ms') <= %s)"
         % (q(svc), q(svc), threshold),
         "%s latency_p99_ms must be within its %s SLO" % (svc, threshold)),
        ("correctness", "alarm_resolved",
         "_alert_status(%d) == 'resolved'" % alert,
         "alarm %d must be resolved" % alert),
        ("correctness", "incident_resolved",
         "_incident_status(%d) == 'resolved'" % inc,
         "incident %d must be resolved" % inc),
        ("correctness", "staging_untouched",
         "_staging_version(%s) == %s" % (q(svc), q(bad)),
         "staging must be left as-is"),
        ("deployment", "rollback_tool_used",
         "_tool_count('rollback_deployment', %s) >= 1" % q(svc),
         "use rollback_deployment for the mitigation"),
        ("deployment", "ack_before_resolve",
         "0 < _alert_seq('acknowledge_alert', %d) < _alert_seq('resolve_alert', %d)" % (alert, alert),
         "acknowledge the alarm before resolving it"),
        ("quality", "postmortem_filed",
         "_postmortems(%s, %s) >= 1" % (q(svc), q(bad)),
         "file a postmortem ticket mentioning %s" % bad),
        ("quality", "status_update_posted",
         "_msg_count('#incidents', '') >= 1",
         "post an update in #incidents"),
        ("quality", "public_status_published",
         "_status_posts('resolved') >= 2",
         "publish a resolved update on the public status page"),
        ("quality", "ticket_closed",
         "_ticket_status(%s) == 'done'" % q(tkt),
         "ticket %s must be closed" % tkt),
        ("quality", "closed_after_the_work",
         "_closed_after_work(%s)" % q(tkt),
         "close %s only once the work is actually done, not before" % tkt),
        ("correctness", "no_unrelated_incident_mutation",
         "_incident_status(9702) != 'resolved'",
         "unrelated incident 9702 must not be resolved"),
    ]
    calls = [
        {"tool": "get_ticket", "args": {"key": tkt}},
        {"tool": "list_deployments", "args": {"service": svc, "environment": "production"}},
        {"tool": "search_logs", "args": {"service": svc, "query": bad}},
        {"tool": "get_document", "args": {"title": "Incident response"}},
        {"tool": "acknowledge_alert", "args": {"alert_id": alert}},
        {"tool": "rollback_deployment", "args": {"service": svc, "environment": "production"}},
        {"tool": "query_metrics", "args": {"service": svc}},
        {"tool": "resolve_alert", "args": {"alert_id": alert}},
        {"tool": "update_incident", "args": {"incident_id": inc, "status": "resolved",
                                             "commander": "agent"}},
        {"tool": "create_ticket", "args": {
            "title": "Postmortem: %s %s latency surge" % (svc, bad),
            "description": "%s introduced an upstream connection-pool leak; rolled back to %s. "
                           "Action items: pool soak test in CI, canary latency gate." % (bad, good),
            "ticket_type": "postmortem", "service": svc, "priority": "high"}},
        {"tool": "publish_status_update", "args": {
            "state": "resolved", "title": "API latency restored",
            "body": "Elevated API latency has been resolved by rolling back a recent release."}},
        {"tool": "post_message", "args": {
            "channel": "#incidents",
            "body": "%s rolled back %s -> %s; p99 recovered. Incident %d resolved; postmortem filed."
                    % (svc, bad, good, inc)}},
        {"tool": "update_ticket", "args": {"key": tkt, "status": "done"}},
    ]
    return instruction, checks, calls


# ==================================================== AIOpsLab-style diagnostics
# Reproduces microsoft/AIOpsLab's task taxonomy — detection, localization,
# analysis — where the agent investigates and SUBMITS a finding rather than
# executing a fix. Graded on the submitted answer, not on world state.

AIOPS_INTRO = (
    "This is an investigation, not a change. Do NOT modify production state: no pull "
    "requests, deploys, flag toggles, migrations or resolutions. Investigate with the read "
    "tools and report what you find with submit_diagnosis(...).\n\n")


def _aiops_common(checks, scope, steps_budget):
    checks.append(("deployment", "investigation_was_read_only", "_mutating_calls() == 0",
                   "an investigation must not change production state"))
    checks.append(("quality", "evidence_recorded",
                   "(_diagnosis(%s) or {}).get('evidence', '') != ''" % q(scope),
                   "record the evidence that supports the finding"))
    checks.append(("quality", "efficient_investigation",
                   "0 < _submit_step(%s) <= %d" % (q(scope), steps_budget),
                   "reach a conclusion within %d tool calls" % steps_budget))


def gen_detection(spec):
    scope, tkt = spec["scope"], spec["ticket"][0]
    faulty = spec["fault_detected"]
    instruction = (
        AIOPS_INTRO +
        "%s — %s\n\nDetermine whether %s is currently violating any of its service level "
        "objectives, and submit the result under scope '%s' with the evidence you relied on. "
        "Report honestly either way: a clean bill of health is a valid finding."
        % (tkt, spec["ticket"][2], scope, scope))
    checks = [
        ("correctness", "diagnosis_submitted",
         "_diagnosis(%s) is not None" % q(scope),
         "submit a detection result for scope '%s'" % scope),
        ("correctness", "detection_correct",
         "(_diagnosis(%s) or {}).get('detected') == %d" % (q(scope), 1 if faulty else 0),
         "%s is %s: fault_detected must be %s"
         % (scope, "breaching its SLO" if faulty else "healthy", str(bool(faulty)).lower())),
    ]
    _aiops_common(checks, scope, spec.get("budget", 8))
    checks.append(("quality", "ticket_closed",
                   "_ticket_status(%s) == 'done'" % q(tkt),
                   "close ticket %s once reported" % tkt))
    checks.append(("quality", "closed_after_the_work",
                   "_closed_after_work(%s)" % q(tkt),
                   "close %s only once the finding is submitted, not before" % tkt))
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "get_slo_status", "args": {"service": spec["service"]}},
             {"tool": "query_metrics", "args": {"service": spec["service"]}},
             {"tool": "list_alerts", "args": {"service": spec["service"]}},
             {"tool": "submit_diagnosis", "args": {
                 "scope": scope, "fault_detected": bool(faulty),
                 "service": spec["service"] if faulty else "",
                 "fault_type": spec["fault_type"] if faulty else "none",
                 "offending_key": spec.get("offending_key", "") if faulty else "",
                 "evidence": spec["evidence"]}},
             {"tool": "update_ticket", "args": {"key": tkt, "status": "done"}}]
    return instruction, checks, calls


def gen_localization(spec):
    scope, tkt = spec["scope"], spec["ticket"][0]
    instruction = (
        AIOPS_INTRO +
        "%s — %s\n\nAlarm %s is firing. Work out which service is actually responsible — the "
        "service the alarm names is not automatically the culprit — and submit your finding "
        "under scope '%s' with the evidence you relied on."
        % (tkt, spec["ticket"][2], scope, scope))
    checks = [
        ("correctness", "diagnosis_submitted",
         "_diagnosis(%s) is not None" % q(scope),
         "submit a localization result for scope '%s'" % scope),
        ("correctness", "service_localized",
         "(_diagnosis(%s) or {}).get('service') == %s" % (q(scope), q(spec["service"])),
         "the responsible service is %s" % spec["service"]),
        ("correctness", "fault_confirmed",
         "(_diagnosis(%s) or {}).get('detected') == 1" % q(scope),
         "a firing alarm means fault_detected must be true"),
    ]
    _aiops_common(checks, scope, spec.get("budget", 10))
    checks.append(("quality", "ticket_closed",
                   "_ticket_status(%s) == 'done'" % q(tkt),
                   "close ticket %s once reported" % tkt))
    checks.append(("quality", "closed_after_the_work",
                   "_closed_after_work(%s)" % q(tkt),
                   "close %s only once the finding is submitted, not before" % tkt))
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "list_alerts", "args": {"status": "firing"}},
             {"tool": "get_slo_status", "args": {}},
             {"tool": "get_service", "args": {"service": spec["service"]}},
             {"tool": "search_logs", "args": {"service": spec["service"]}},
             {"tool": "submit_diagnosis", "args": {
                 "scope": scope, "fault_detected": True, "service": spec["service"],
                 "fault_type": spec["fault_type"],
                 "offending_key": spec.get("offending_key", ""),
                 "evidence": spec["evidence"]}},
             {"tool": "update_ticket", "args": {"key": tkt, "status": "done"}}]
    return instruction, checks, calls


def gen_analysis(spec):
    scope, tkt = spec["scope"], spec["ticket"][0]
    instruction = (
        AIOPS_INTRO +
        "%s — %s\n\nGet to the bottom of %s: not just which service, but the mechanism and the "
        "exact setting responsible. Confirm it in the source rather than inferring it from the "
        "symptom alone. Submit your finding under scope '%s' with the responsible service, the "
        "fault type, the offending key, and your evidence."
        % (tkt, spec["ticket"][2], scope, scope))
    checks = [
        ("correctness", "diagnosis_submitted",
         "_diagnosis(%s) is not None" % q(scope),
         "submit a root-cause result for scope '%s'" % scope),
        ("correctness", "service_localized",
         "(_diagnosis(%s) or {}).get('service') == %s" % (q(scope), q(spec["service"])),
         "the responsible service is %s" % spec["service"]),
        ("correctness", "fault_type_correct",
         "(_diagnosis(%s) or {}).get('fault_type') == %s" % (q(scope), q(spec["fault_type"])),
         "the root cause is a %s fault" % spec["fault_type"]),
        ("correctness", "offending_key_correct",
         "(_diagnosis(%s) or {}).get('offending_key') == %s"
         % (q(scope), q(spec["offending_key"])),
         "the offending key is %s" % spec["offending_key"]),
    ]
    _aiops_common(checks, scope, spec.get("budget", 12))
    checks.append(("quality", "ticket_closed",
                   "_ticket_status(%s) == 'done'" % q(tkt),
                   "close ticket %s once reported" % tkt))
    checks.append(("quality", "closed_after_the_work",
                   "_closed_after_work(%s)" % q(tkt),
                   "close %s only once the finding is submitted, not before" % tkt))
    calls = [{"tool": "get_ticket", "args": {"key": tkt}},
             {"tool": "query_metrics", "args": {"service": spec["service"]}},
             {"tool": "search_logs", "args": {"service": spec["service"]}},
             {"tool": "list_error_events", "args": {"service": spec["service"]}},
             {"tool": "get_service", "args": {"service": spec["service"]}}]
    if spec.get("code_path"):
        calls.append({"tool": "read_file", "args": {"path": spec["code_path"]}})
        calls.append({"tool": "list_commits", "args": {"service": spec["service"], "limit": 5}})
    calls += [{"tool": "submit_diagnosis", "args": {
                  "scope": scope, "fault_detected": True, "service": spec["service"],
                  "fault_type": spec["fault_type"], "offending_key": spec["offending_key"],
                  "evidence": spec["evidence"]}},
              {"tool": "update_ticket", "args": {"key": tkt, "status": "done"}}]
    return instruction, checks, calls


def gen_reconcile(spec):
    """Answer a question no single system can answer, over data that disagrees."""
    qid, tkt = spec["question_id"], spec["ticket"][0]
    instruction = (
        "This is an investigation, not a change. Do NOT modify production state.\n\n"
        "%s — %s\n\n%s\n\nNovaCart's data does not live in one place, and the systems "
        "do not always agree. Work out the answer, then submit it with submit_answer("
        "question_id='%s', ...), listing every system you actually consulted and recording "
        "any judgement you had to make in `assumptions`."
        % (tkt, spec["ticket"][2], spec["question"], qid))
    checks = [
        ("correctness", "answer_submitted", "_answer(%s) is not None" % q(qid),
         "submit an answer for question_id '%s'" % qid),
        ("correctness", "answer_correct",
         "(_answer_num(%s) is not None and abs(_answer_num(%s) - %s) <= %s)"
         % (q(qid), q(qid), spec["expected"], spec.get("tolerance", 0.001)),
         spec["why"]),
    ]
    for sysname in spec["required_sources"]:
        checks.append(("correctness", "consulted_%s" % sysname,
                       "_used(%s, %s)" % (q(qid), q(sysname)),
                       "the answer requires evidence from %s" % sysname))
    checks.append(("deployment", "investigation_was_read_only", "_mutating_calls() == 0",
                   "an investigation must not change production state"))
    checks.append(("quality", "assumption_recorded",
                   "len((_answer(%s) or {}).get('assumptions','')) >= 20" % q(qid),
                   "record the judgement you made - %s" % spec["ambiguity"]))
    checks.append(("quality", "ticket_closed",
                   "_ticket_status(%s) == 'done'" % q(tkt),
                   "close ticket %s once reported" % tkt))
    checks.append(("quality", "closed_after_the_work",
                   "_closed_after_work(%s)" % q(tkt),
                   "close %s only once the answer is submitted" % tkt))

    calls = [{"tool": "get_ticket", "args": {"key": tkt}}]
    calls += spec["oracle_reads"]
    calls.append({"tool": "submit_answer", "args": {
        "question_id": qid, "answer": spec["oracle_answer"],
        "sources": spec["required_sources"], "assumptions": spec["oracle_assumption"]}})
    calls.append({"tool": "update_ticket", "args": {"key": tkt, "status": "done"}})
    return instruction, checks, calls


GENERATORS = {
    "reconcile": gen_reconcile,
    "detection": gen_detection, "localization": gen_localization, "analysis": gen_analysis,
    "config_fix": gen_config_fix, "flag_ship": gen_flag_ship, "flag_kill": gen_flag_kill,
    "flag_cleanup": gen_flag_cleanup, "security_cve": gen_security_cve,
    "security_endpoint": gen_security_endpoint, "security_secret": gen_security_secret,
    "api_migration": gen_api_migration, "flaky": gen_flaky,
    "multi_service": gen_multi_service, "incident": gen_incident,
}


GUIDANCE = {
    "config_fix": "Procedure: open a pull request carrying the configuration change, get CI "
                  "green, merge it, then deploy staging-first — tier-1 services canary at "
                  "<=25%, assess the canary, then promote. Confirm the metric recovered, then "
                  "acknowledge the alarm before resolving it, and close the ticket last.",
    "flag_ship": "Procedure: define the flag in the same pull request as the guarded module "
                 "(and its database migration if it persists new state); get CI green, merge, "
                 "apply any migration to an environment before deploying there, deploy "
                 "staging-first with a canary for tier-1 services, and only enable the flag in "
                 "production once the code is live there.",
    "flag_kill": "Procedure: acknowledge the alarm, disable the flag in production only, "
                 "verify the metric recovered, resolve the alarm and then the incident, post an "
                 "update in #incidents naming the flag, publish a resolved update on the public "
                 "status page, and close the ticket.",
    "flag_cleanup": "Procedure: open a pull request with a flag_cleanup change, get CI green, "
                    "merge, and deploy it staging-first following the deployment policy.",
    "security_cve": "Procedure: upgrade the dependency via a pull request, get CI green, merge, "
                    "deploy staging-first with a canary for tier-1 services, re-check the "
                    "scanner, post an audit summary to #security quoting the CVE id, and close "
                    "the ticket.",
    "security_endpoint": "Procedure: retire the endpoint with an endpoint change in a pull "
                         "request, get CI green, merge, and deploy staging-first with a canary "
                         "for tier-1 services.",
    "security_secret": "Procedure: remove the literal credential from the source with a "
                       "code_edit change and set use_secret_manager=true in the same pull "
                       "request, get CI green, merge, deploy staging-first, and post an audit "
                       "note to #security.",
    "api_migration": "Procedure: migrate any consumer service to the new version first and "
                     "deploy it; deprecate the legacy endpoint and deploy that; shift traffic "
                     "in steps of at most 50 percentage points until the replacement serves "
                     "100%; only then retire the legacy endpoint in a second pull request and "
                     "deploy it. Every deploy is staging-first, tier-1 canary then promote.",
    "flaky": "Procedure: read the CI history, fix the root cause with a test_fix change using "
             "action 'fix' (quarantining does not count), get CI green — the pull request's own "
             "first run will hit the same flake, so rerun it — merge, then prove stability with "
             "at least 3 consecutive green main-branch runs.",
    "multi_service": "Procedure: one pull request per service, in the stated order. Any module "
                     "that persists new state needs its migration in the same pull request and "
                     "applied to an environment before deploying there. Every production deploy "
                     "is staging-first, tier-1 canary then promote.",
    "incident": "Procedure: acknowledge the alarm, roll back the production deployment, verify "
                "the metric recovered, resolve the alarm and then the incident, file a "
                "postmortem ticket of type 'postmortem', publish a resolved update on the "
                "public status page, post an update in #incidents, and close the ticket.",
    "detection": "Procedure: compare live production metrics against the service's SLOs and "
                 "check the alarm state, then submit. If healthy, submit fault_detected=false "
                 "with fault_type='none'.",
    "localization": "Procedure: trace the symptom through the metrics, the service dependency "
                    "graph and the logs, then submit the responsible service.",
    "reconcile": "Procedure: identify every system that holds part of the answer, resolve "
                 "the service naming across them, check for duplicates and sampling before "
                 "counting, decide the boundary condition explicitly, and record which "
                 "source you trusted and why.",
    "analysis": "Procedure: read the production logs and the error tracker, inspect the "
                "deployed configuration, and read the source and the commit that introduced "
                "the change to confirm the mechanism before submitting.",
}


def make_tasks(base_seq, frozen=None, fixed_rows=None, audit_prefix="", secret_files=0,
               secret_literal="pk_live_placeholder", reads_map=None):
    tasks = []
    for spec in task_specs.all_specs():
        gen = spec["generator"]
        if gen == "security_secret":
            instruction, checks, calls = GENERATORS[gen](spec, secret_literal)
        else:
            instruction, checks, calls = GENERATORS[gen](spec)
        # The oracle must model the discovery the instruction now demands: the
        # policies were removed from the prompt, so the reference solution reads
        # them out of the knowledge base.
        needs_deploy_policy = any(c[1] in ("staging_first", "canary_then_promote")
                                  or c[1].startswith("staging_first_")
                                  or c[1].startswith("canary_") for c in
                                  [(x[0], x[1]) for x in checks])
        needs_migration_policy = any(c["tool"] == "apply_migration" for c in calls)
        is_flaky = any(c["tool"] == "run_ci" and "service" in c.get("args", {}) for c in calls)
        is_latency = any(c[1] == "metric_within_slo" for c in [(x[0], x[1]) for x in checks]) \
            and any("latency" in str(x[3]) for x in checks)
        pre = []
        if needs_deploy_policy:
            pre.append({"tool": "get_document", "args": {"title": "Deployment policy"}})
        if needs_migration_policy:
            pre.append({"tool": "get_document", "args": {"title": "Database migration policy"}})
            pre.append({"tool": "list_migrations", "args": {"service": calls[
                next(i for i, c in enumerate(calls)
                     if c["tool"] == "apply_migration")]["args"]["service"]}})
        if pre:
            at = 1 if calls and calls[0]["tool"] == "get_ticket" else 0
            calls = calls[:at] + pre + calls[at:]
        if is_latency:
            at = 1 if calls and calls[0]["tool"] == "get_ticket" else 0
            calls = calls[:at] + [{"tool": "get_traffic_stats", "args": {}}] + calls[at:]
        discovered = []
        for c in calls:
            if c["tool"] == "get_document" and c.get("args", {}).get("title"):
                discovered.append({"tool": "search_docs",
                                   "args": {"query": c["args"]["title"].split()[0].lower()}})
            discovered.append(c)
            # after a red CI run, a real engineer opens the run to read the stages
            if c["tool"] == "run_ci" and is_flaky and not any(
                    x["tool"] == "get_ci_run" for x in discovered):
                discovered.append({"tool": "get_ci_run", "args": {"run_id": 13}})
        calls = discovered
        tasks.append({
            "task_id": "tsk_" + spec["id"],
            "instruction": instruction,
            "instruction_guided": instruction + "\n\n" + GUIDANCE[gen],
            "origin": "curated",
            "difficulty": spec["difficulty"],
            "category": spec["category"],
            "ground_truth": "",
            "reward_kind": "vcode",
            "reward_basis": "vcode",
            "required_tools": sorted({c["tool"] for c in calls}),
            "expected_calls": calls,
            "vcode": PRELUDE + render(checks) + EPILOGUE,
        })
    for t in tasks:
        t["vcode"] = (t["vcode"]
                      .replace("__BASE_SEQ__", str(int(base_seq)))
                      .replace("__FROZEN__", repr(dict(frozen or {})))
                      .replace("__FIXED_ROWS__", repr(dict(fixed_rows or {})))
                      .replace("__AUDIT_PREFIX__", str(audit_prefix))
                      .replace("__SECRET_FILES__", str(int(secret_files)))
                      .replace("__READS__", repr(dict(reads_map or {}))))
    return tasks


def splits(tasks):
    """Freeze a deterministic train/heldout split: every 4th task is held out,
    keeping each category represented on both sides."""
    train, heldout = [], []
    by_cat = {}
    for t in tasks:
        by_cat.setdefault(t["category"], []).append(t["task_id"])
    for cat, ids in sorted(by_cat.items()):
        for i, tid in enumerate(sorted(ids)):
            (heldout if i % 4 == 3 else train).append(tid)
    return {"train": sorted(train), "heldout": sorted(heldout)}
