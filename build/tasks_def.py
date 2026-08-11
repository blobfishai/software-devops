"""Task definitions for the software-devops world.

Each task carries:
  * instruction        — the agent-visible assignment,
  * vcode              — module-assertion verifier (dialect 1). Pure SQL over
                         final DB state + the audit_events ordering log.
                         Every vcode MUST fail on the pristine seed.
  * expected_calls     — the oracle trace; the build replays it through the
                         real tools and requires the vcode to pass afterward.

The literal token __BASE_SEQ__ inside vcode is replaced at build time with the
number of seeded audit_events rows, scoping ordering assertions to agent-era
activity.

Deterministic ids the oracles rely on (fresh session forks the pristine DB):
  * next PR number is 9203 (seeded PRs: 9201, 9202), then 9204, 9205, ...
  * seeded alert/incident/ticket ids are fixed (9601..9604, 9701/9702, ENG-*/SEC-*).
"""

# Shared vcode prelude: single-underscore helpers only (double underscores are
# rejected by the vcode AST guard).
PRELUDE = """\
import hashlib
_FROZEN = __FROZEN__
_FIXED_ROWS = __FIXED_ROWS__
_AUDIT_PREFIX = '__AUDIT_PREFIX__'
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
def _prod_apply_seq(_svc):
    return _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND service=? AND ((tool='deploy_service' AND json_extract(detail,'$.environment')='production' AND json_extract(detail,'$.applied')=1) OR (tool='promote_canary' AND json_extract(detail,'$.environment')='production'))", _svc)
_checks = []
def _c(_dim, _name, _ok, _msg):
    _checks.append((_dim, _name, bool(_ok), _msg))
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
        ('deployments', "SELECT COUNT(*) FROM deployments d WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=d.service)"),
        ('versions', "SELECT COUNT(*) FROM versions x WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=x.service)"),
        ('env_state', "SELECT COUNT(*) FROM env_state e WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=e.service)"),
        ('feature_flags', "SELECT COUNT(*) FROM feature_flags f WHERE NOT EXISTS (SELECT 1 FROM services v WHERE v.name=f.service)"),
        ('audit_events', "SELECT COUNT(*) FROM audit_events a WHERE a.service != '' AND NOT EXISTS (SELECT 1 FROM services v WHERE v.name=a.service)"),
        ('deployment_envs', "SELECT COUNT(*) FROM deployments WHERE environment NOT IN ('staging','production')"),
        ('flag_envs', "SELECT COUNT(*) FROM feature_flags WHERE environment NOT IN ('staging','production')"),
        ('pr_changes', "SELECT COUNT(*) FROM pr_changes c WHERE NOT EXISTS (SELECT 1 FROM pull_requests p WHERE p.number=c.pr_number)"),
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
"""

# Tables no tool can write: any change is fabricated data. Byte-compared.
FROZEN_TABLES = ("oncall", "slos", "metric_rules", "runbooks", "channels", "logs")
# Inventories tools may UPDATE (merge bumps versions / fixes tests, the engine
# flips vuln status) but must never grow or shrink. Row-count compared.
FIXED_ROW_TABLES = ("services", "tests_catalog", "vulnerabilities")

# Horizon-SWE-PC composite: feature correctness 0.6, deployment & devops 0.3,
# engineering quality 0.1 (weights renormalized over the dimensions a task
# actually uses). `score` is advisory partial credit; `passed` stays binary —
# ALL checks must hold.
EPILOGUE = """\
_scope = _blast_radius()
_c('quality', 'scoped_change_no_fabricated_data', not _scope, 'the change must stay in scope; world reference data must not be fabricated or altered: ' + '; '.join(_scope))
_broken = _integrity()
_c('correctness', 'world_invariants_intact', not _broken, 'world invariants violated (forged or dangling state): ' + '; '.join(_broken))
_W = {'correctness': 0.6, 'deployment': 0.3, 'quality': 0.1}
_dims = {}
for _d, _n, _ok, _m in _checks:
    _dims.setdefault(_d, []).append(_ok)
_tw = sum(_W[_d] for _d in _dims)
score = 0.0
for _d, _oks in _dims.items():
    score = score + (_W[_d] / _tw) * (sum(1 for _o in _oks if _o) / len(_oks))
score = round(score, 4)
_failed = [_d + '/' + _n + ' - ' + _m for _d, _n, _ok, _m in _checks if not _ok]
assert not _failed, str(len(_failed)) + ' check(s) failed (score=' + str(score) + '): ' + '; '.join(_failed)
"""


def _task(task_id, instruction, difficulty, vcode_body, expected_calls,
          required_tools):
    return {
        "task_id": task_id,
        "instruction": instruction,
        "origin": "curated",
        "difficulty": difficulty,
        "ground_truth": "",
        "reward_kind": "vcode",
        "reward_basis": "vcode",
        "required_tools": required_tools,
        "expected_calls": expected_calls,
        "vcode": PRELUDE + vcode_body + EPILOGUE,
    }


def make_tasks(base_seq, frozen=None, fixed_rows=None, audit_prefix=""):
    frozen = dict(frozen or {})
    fixed_rows = dict(fixed_rows or {})
    tasks = []

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_payments_error_rate",
        "You are the on-call engineer for the commerce team at NovaCart. Work ticket "
        "ENG-2101: the payments service is breaching its error-rate SLO (alert 9601). "
        "Investigate production logs and runbooks to find the root cause, fix it via the "
        "standard workflow (PR with structured changes -> CI -> merge -> deploy), follow "
        "the deployment policy runbook, confirm recovery, resolve the alert, and close "
        "the ticket.",
        "hard",
        """\
_c('correctness', 'retry_config_deployed', _es('payments', 'config', 'notifications_retry_max_attempts') == '3', 'production payments must run with notifications_retry_max_attempts=3 (merged AND deployed)')
_v = _metric('payments', 'error_rate_pct')
_c('correctness', 'error_rate_within_slo', _v is not None and _v <= 1.0, 'payments error_rate_pct must be within its 1.0 SLO (got ' + str(_v) + ')')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='payments' AND p.status='merged' AND p.ticket_key='ENG-2101' AND c.change_type='config' AND json_extract(c.payload,'$.key')='notifications_retry_max_attempts'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, 'a merged PR linked to ENG-2101 must carry the retry config change')
_c('correctness', 'alert_resolved', _one("SELECT status FROM alerts WHERE alert_id=9601") == 'resolved', 'alert 9601 must be resolved')
_c('deployment', 'staging_first', _staging_first('payments'), 'deployment hygiene: production deploys must be staging-first')
_c('deployment', 'canary_then_promote', _canaried('payments'), 'deployment hygiene: payments is tier 1 - canary at <=25% then promote_canary')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2101'") == 'done', 'ticket ENG-2101 must be closed (status done)')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9602") != 'resolved', 'unrelated alert 9602 must not be resolved')
_c('correctness', 'no_unrelated_config_mutation', _es('search', 'config', 'cache_enabled') == 'false', 'unrelated search production config must not change')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2101"}},
            {"tool": "search_logs", "args": {"service": "payments", "query": "retry"}},
            {"tool": "search_runbooks", "args": {"query": "retry"}},
            {"tool": "open_pull_request", "args": {
                "service": "payments",
                "title": "Enable retries for notifications calls",
                "body": "Set notifications_retry_max_attempts=3 per the retry policy standard. Fixes ENG-2101.",
                "ticket_key": "ENG-2101",
                "changes": [{"change_type": "config",
                             "payload": {"key": "notifications_retry_max_attempts", "value": "3"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "payments", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "payments", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "payments"}},
            {"tool": "acknowledge_alert", "args": {"alert_id": 9601}},
            {"tool": "resolve_alert", "args": {"alert_id": 9601}},
            {"tool": "update_ticket", "args": {"key": "ENG-2101", "status": "done"}},
        ],
        ["get_ticket", "search_logs", "open_pull_request", "run_ci",
         "merge_pull_request", "deploy_service", "promote_canary",
         "resolve_alert", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_search_latency_slo",
        "Work ticket ENG-2102 at NovaCart: search p99 latency is 850ms against a 300ms "
        "SLO (alert 9602). Diagnose the root cause from logs and runbooks, ship the fix "
        "through PR -> CI -> merge -> staged deployment (staging first), confirm the "
        "metric recovered, resolve the alert, and close the ticket.",
        "medium",
        """\
_c('correctness', 'cache_config_deployed', _es('search', 'config', 'cache_enabled') == 'true', 'production search must run with cache_enabled=true (merged AND deployed)')
_v = _metric('search', 'latency_p99_ms')
_c('correctness', 'latency_within_slo', _v is not None and _v <= 300.0, 'search latency_p99_ms must be within its 300 SLO (got ' + str(_v) + ')')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='search' AND p.status='merged' AND p.ticket_key='ENG-2102' AND c.change_type='config' AND json_extract(c.payload,'$.key')='cache_enabled'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, 'a merged PR linked to ENG-2102 must carry the cache_enabled config change')
_c('correctness', 'alert_resolved', _one("SELECT status FROM alerts WHERE alert_id=9602") == 'resolved', 'alert 9602 must be resolved')
_c('deployment', 'staging_first', _staging_first('search'), 'deployment hygiene: production deploys must be staging-first')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2102'") == 'done', 'ticket ENG-2102 must be closed (status done)')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9601") != 'resolved', 'unrelated alert 9601 must not be resolved')
_c('correctness', 'no_unrelated_config_mutation', _es('payments', 'config', 'notifications_retry_max_attempts') == '0', 'unrelated payments production config must not change')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2102"}},
            {"tool": "search_logs", "args": {"service": "search", "query": "cache"}},
            {"tool": "search_runbooks", "args": {"query": "caching"}},
            {"tool": "open_pull_request", "args": {
                "service": "search",
                "title": "Enable the query cache in production",
                "body": "cache_enabled=true per the search caching runbook. Fixes ENG-2102.",
                "ticket_key": "ENG-2102",
                "changes": [{"change_type": "config",
                             "payload": {"key": "cache_enabled", "value": "true"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "search", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "search", "environment": "production"}},
            {"tool": "acknowledge_alert", "args": {"alert_id": 9602}},
            {"tool": "resolve_alert", "args": {"alert_id": 9602}},
            {"tool": "update_ticket", "args": {"key": "ENG-2102", "status": "done"}},
        ],
        ["get_ticket", "search_logs", "open_pull_request", "run_ci",
         "merge_pull_request", "deploy_service", "resolve_alert",
         "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_express_checkout_flag",
        "Work ticket ENG-2201 at NovaCart: ship the express_checkout module in the "
        "checkout service behind a NEW feature flag named 'express_checkout', then roll "
        "it out to 10% of production. Consult the feature-flags and deployment-policy "
        "runbooks: the guarded code must be live in production before the flag is "
        "enabled there, and checkout is a tier-1 service. Note: checkout CI has a known "
        "intermittent test - a failed run may pass on retry. Close the ticket when done.",
        "hard",
        """\
_c('correctness', 'module_live_in_production', _es('checkout', 'module', 'express_checkout') == 'present', 'the express_checkout module must be live in production')
_fl = conn.execute("SELECT enabled, rollout_percent FROM feature_flags WHERE key='express_checkout' AND environment='production'").fetchone()
_c('correctness', 'flag_defined_in_production', _fl is not None, 'flag express_checkout must be defined in production')
_c('correctness', 'flag_enabled_at_10pct', _fl is not None and int(_fl[0]) == 1 and int(_fl[1]) == 10, 'express_checkout must be enabled at a 10% production rollout (got ' + str(tuple(_fl) if _fl else None) + ')')
_c('correctness', 'flag_defined_in_staging', conn.execute("SELECT 1 FROM feature_flags WHERE key='express_checkout' AND environment='staging'").fetchone() is not None, 'flag change must define the flag in staging too')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='checkout' AND p.status='merged' AND p.ticket_key='ENG-2201' AND c.change_type='flag' AND json_extract(c.payload,'$.key')='express_checkout'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, 'a merged PR linked to ENG-2201 must define the express_checkout flag')
_apply_seq = _prod_apply_seq('checkout')
_enable_seq = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='set_feature_flag' AND json_extract(detail,'$.key')='express_checkout' AND json_extract(detail,'$.environment')='production' AND json_extract(detail,'$.enabled')=1")
_c('deployment', 'code_before_flag_enable', _apply_seq is not None and _enable_seq is not None and _apply_seq < _enable_seq, 'the guarded code must reach production BEFORE the flag is enabled there')
_c('deployment', 'staging_first', _staging_first('checkout'), 'deployment hygiene: production deploys must be staging-first')
_c('deployment', 'canary_then_promote', _canaried('checkout'), 'deployment hygiene: checkout is tier 1 - canary at <=25% then promote_canary')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2201'") == 'done', 'ticket ENG-2201 must be closed (status done)')
_c('correctness', 'no_unrelated_flag_mutation', _one("SELECT enabled FROM feature_flags WHERE key='instant_refunds' AND environment='production'") == 1, 'unrelated flag instant_refunds must not be touched in this task')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2201"}},
            {"tool": "search_runbooks", "args": {"query": "flag"}},
            {"tool": "open_pull_request", "args": {
                "service": "checkout",
                "title": "Express checkout module behind express_checkout flag",
                "body": "Adds the express_checkout module dark, guarded by the new express_checkout flag. ENG-2201.",
                "ticket_key": "ENG-2201",
                "changes": [
                    {"change_type": "module", "payload": {"name": "express_checkout"}},
                    {"change_type": "flag", "payload": {"key": "express_checkout",
                                                        "description": "Express checkout rollout"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "checkout", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "checkout", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "checkout"}},
            {"tool": "set_feature_flag", "args": {"key": "express_checkout", "environment": "production",
                                                  "enabled": True, "rollout_percent": 10}},
            {"tool": "update_ticket", "args": {"key": "ENG-2201", "status": "done"}},
        ],
        ["get_ticket", "open_pull_request", "run_ci", "merge_pull_request",
         "deploy_service", "promote_canary", "set_feature_flag", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_instant_refunds_killswitch",
        "Incident duty at NovaCart. Work ticket ENG-2202 / incident 9702 (sev2): the "
        "checkout error rate spiked right after the instant_refunds feature flag ramped "
        "in production. Follow the incident-response runbook: acknowledge the alert, "
        "kill-switch the flag in production only (leave staging as-is), verify the "
        "metric recovered, resolve the alert and the incident, post an update in "
        "#incidents mentioning instant_refunds, and close the ticket.",
        "medium",
        """\
_c('correctness', 'flag_disabled_in_production', _one("SELECT enabled FROM feature_flags WHERE key='instant_refunds' AND environment='production'") == 0, 'instant_refunds must be disabled in production')
_c('correctness', 'staging_flag_untouched', _one("SELECT enabled FROM feature_flags WHERE key='instant_refunds' AND environment='staging'") == 1, 'staging instant_refunds must be left as-is')
_v = _metric('checkout', 'error_rate_pct')
_c('correctness', 'error_rate_within_slo', _v is not None and _v <= 1.0, 'checkout error_rate_pct must be within its 1.0 SLO (got ' + str(_v) + ')')
_c('correctness', 'alert_resolved', _one("SELECT status FROM alerts WHERE alert_id=9603") == 'resolved', 'alert 9603 must be resolved')
_ack = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='acknowledge_alert' AND json_extract(detail,'$.alert_id')=9603")
_res = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='resolve_alert' AND json_extract(detail,'$.alert_id')=9603")
_c('deployment', 'ack_before_resolve', _ack is not None and _res is not None and _ack < _res, 'runbook order: acknowledge the alert before resolving it')
_c('correctness', 'incident_resolved', _one("SELECT status FROM incidents WHERE incident_id=9702") == 'resolved', 'incident 9702 must be resolved')
_c('quality', 'status_update_posted', _one("SELECT COUNT(*) FROM messages WHERE channel='#incidents' AND author='agent' AND body LIKE '%instant_refunds%'") >= 1, 'post an update in #incidents mentioning instant_refunds')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2202'") == 'done', 'ticket ENG-2202 must be closed (status done)')
_c('correctness', 'no_unrelated_incident_mutation', _one("SELECT status FROM incidents WHERE incident_id=9701") != 'resolved', 'unrelated incident 9701 must not be resolved')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9604") != 'resolved', 'unrelated alert 9604 must not be resolved')
_c('correctness', 'no_unrelated_flag_mutation', _one("SELECT enabled FROM feature_flags WHERE key='new_search_ui' AND environment='production'") == 0, 'unrelated flag new_search_ui must not be touched')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2202"}},
            {"tool": "search_logs", "args": {"service": "checkout", "query": "instant_refunds"}},
            {"tool": "acknowledge_alert", "args": {"alert_id": 9603}},
            {"tool": "set_feature_flag", "args": {"key": "instant_refunds", "environment": "production",
                                                  "enabled": False}},
            {"tool": "query_metrics", "args": {"service": "checkout", "metric": "error_rate_pct"}},
            {"tool": "resolve_alert", "args": {"alert_id": 9603}},
            {"tool": "update_incident", "args": {"incident_id": 9702, "status": "resolved"}},
            {"tool": "post_message", "args": {"channel": "#incidents",
                                              "body": "Kill-switched instant_refunds in production; checkout error rate recovered. Incident 9702 resolved."}},
            {"tool": "update_ticket", "args": {"key": "ENG-2202", "status": "done"}},
        ],
        ["get_ticket", "acknowledge_alert", "set_feature_flag", "resolve_alert",
         "update_incident", "post_message", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_libpayproc_cve",
        "Security duty at NovaCart. Work ticket SEC-901: the scanner flags libpayproc "
        "2.3.1 in the payments service as vulnerable to CVE-2026-31337 (critical). "
        "Follow the security-response runbook: upgrade the dependency to the fixed "
        "version via PR -> CI -> merge, deploy staging-first (payments is tier 1: "
        "canary then promote), verify the finding shows remediated, post an audit "
        "summary to #security referencing the CVE, and close the ticket.",
        "hard",
        """\
_c('correctness', 'dependency_deployed', _es('payments', 'dependency', 'libpayproc') == '2.4.0', 'production payments must run libpayproc 2.4.0')
_c('correctness', 'vulnerability_remediated', _one("SELECT status FROM vulnerabilities WHERE vuln_id=9801") == 'remediated', 'CVE-2026-31337 must show remediated (fixed version deployed to production)')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='payments' AND p.status='merged' AND p.ticket_key='SEC-901' AND c.change_type='dependency' AND json_extract(c.payload,'$.package')='libpayproc'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, 'a merged PR linked to SEC-901 must carry the libpayproc upgrade')
_c('quality', 'audit_note_posted', _one("SELECT COUNT(*) FROM messages WHERE channel='#security' AND author='agent' AND body LIKE '%CVE-2026-31337%'") >= 1, 'post an audit summary to #security referencing CVE-2026-31337')
_c('deployment', 'staging_first', _staging_first('payments'), 'deployment hygiene: production deploys must be staging-first')
_c('deployment', 'canary_then_promote', _canaried('payments'), 'deployment hygiene: payments is tier 1 - canary at <=25% then promote_canary')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='SEC-901'") == 'done', 'ticket SEC-901 must be closed (status done)')
_c('correctness', 'no_unrelated_dependency_mutation', _es('payments', 'dependency', 'requests') == '2.32.3', 'unrelated dependency requests must not change')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9601") != 'resolved', 'the payments error-rate alert belongs to ENG-2101 and must not be resolved here')
""",
        [
            {"tool": "get_ticket", "args": {"key": "SEC-901"}},
            {"tool": "list_vulnerabilities", "args": {"status": "open"}},
            {"tool": "search_runbooks", "args": {"query": "security"}},
            {"tool": "open_pull_request", "args": {
                "service": "payments",
                "title": "Upgrade libpayproc to 2.4.0 (CVE-2026-31337)",
                "body": "Patches CVE-2026-31337. SEC-901.",
                "ticket_key": "SEC-901",
                "changes": [{"change_type": "dependency",
                             "payload": {"package": "libpayproc", "version": "2.4.0"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "payments", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "payments", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "payments"}},
            {"tool": "list_vulnerabilities", "args": {}},
            {"tool": "post_message", "args": {"channel": "#security",
                                              "body": "CVE-2026-31337 remediated: libpayproc upgraded 2.3.1 -> 2.4.0 in payments and deployed to production (staging-first, 25% canary then promote)."}},
            {"tool": "update_ticket", "args": {"key": "SEC-901", "status": "done"}},
        ],
        ["get_ticket", "list_vulnerabilities", "open_pull_request", "run_ci",
         "merge_pull_request", "deploy_service", "promote_canary", "post_message",
         "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_retire_debug_endpoint",
        "Security duty at NovaCart. Work ticket SEC-902: a review found the "
        "unauthenticated /internal/debug endpoint still active in production on "
        "api-gateway. Retire it via an endpoint PR change and deploy it staging-first "
        "(api-gateway is tier 1: canary then promote). Close the ticket when the "
        "endpoint is retired in production.",
        "medium",
        """\
_c('correctness', 'endpoint_retired', _es('api-gateway', 'endpoint', '/internal/debug') == 'retired', '/internal/debug must be retired in production')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='api-gateway' AND p.status='merged' AND p.ticket_key='SEC-902' AND c.change_type='endpoint' AND json_extract(c.payload,'$.path')='/internal/debug' AND json_extract(c.payload,'$.status')='retired'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, 'a merged PR linked to SEC-902 must retire /internal/debug')
_c('deployment', 'staging_first', _staging_first('api-gateway'), 'deployment hygiene: production deploys must be staging-first')
_c('deployment', 'canary_then_promote', _canaried('api-gateway'), 'deployment hygiene: api-gateway is tier 1 - canary at <=25% then promote_canary')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='SEC-902'") == 'done', 'ticket SEC-902 must be closed (status done)')
_c('correctness', 'no_unrelated_endpoint_mutation', _es('api-gateway', 'endpoint', '/v1/orders') == 'active', 'unrelated endpoint /v1/orders must stay active')
_c('correctness', 'no_unrelated_traffic_mutation', _es('api-gateway', 'traffic', '/v1/orders') == '100', 'unrelated traffic weights must not change')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9604") != 'resolved', 'the latency alert belongs to ENG-2402 and must not be resolved here')
""",
        [
            {"tool": "get_ticket", "args": {"key": "SEC-902"}},
            {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
            {"tool": "open_pull_request", "args": {
                "service": "api-gateway",
                "title": "Retire /internal/debug",
                "body": "Removes the unauthenticated debug endpoint. SEC-902.",
                "ticket_key": "SEC-902",
                "changes": [{"change_type": "endpoint",
                             "payload": {"path": "/internal/debug", "status": "retired"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "api-gateway"}},
            {"tool": "update_ticket", "args": {"key": "SEC-902", "status": "done"}},
        ],
        ["get_ticket", "list_api_endpoints", "open_pull_request", "run_ci",
         "merge_pull_request", "deploy_service", "promote_canary", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_loyalty_multi_service",
        "Work ticket ENG-2301 at NovaCart: ship loyalty points across three services - "
        "module loyalty_accrual in catalog, module loyalty_redeem in checkout, module "
        "loyalty_widget in storefront-web (one PR per service). Deployment order "
        "matters: catalog must be live in production before checkout, and checkout "
        "before storefront-web. Follow the deployment policy (staging-first everywhere; "
        "checkout and storefront-web are tier 1: canary then promote). Note: checkout "
        "CI has a known intermittent test - retry a failed run. Close the ticket.",
        "expert",
        """\
_c('correctness', 'catalog_module_live', _es('catalog', 'module', 'loyalty_accrual') == 'present', 'loyalty_accrual must be live in production catalog')
_c('correctness', 'checkout_module_live', _es('checkout', 'module', 'loyalty_redeem') == 'present', 'loyalty_redeem must be live in production checkout')
_c('correctness', 'storefront_module_live', _es('storefront-web', 'module', 'loyalty_widget') == 'present', 'loyalty_widget must be live in production storefront-web')
for _svc, _mod in (('catalog', 'loyalty_accrual'), ('checkout', 'loyalty_redeem'), ('storefront-web', 'loyalty_widget')):
    _pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service=? AND p.status='merged' AND p.ticket_key='ENG-2301' AND c.change_type='module' AND json_extract(c.payload,'$.name')=?", _svc, _mod)
    _c('quality', 'pr_linked_' + _svc, _pr is not None, 'a merged PR linked to ENG-2301 must add ' + _mod + ' to ' + _svc)
_a = _prod_apply_seq('catalog')
_b = _prod_apply_seq('checkout')
_s = _prod_apply_seq('storefront-web')
_c('deployment', 'rollout_order', _a is not None and _b is not None and _s is not None and _a < _b < _s, 'rollout order must be catalog -> checkout -> storefront-web in production (got seqs ' + str((_a, _b, _s)) + ')')
for _svc in ('catalog', 'checkout', 'storefront-web'):
    _c('deployment', 'staging_first_' + _svc, _staging_first(_svc), 'deployment hygiene: production deploys must be staging-first (' + _svc + ')')
_c('deployment', 'canary_checkout', _canaried('checkout'), 'deployment hygiene: checkout is tier 1 - canary then promote')
_c('deployment', 'canary_storefront', _canaried('storefront-web'), 'deployment hygiene: storefront-web is tier 1 - canary then promote')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2301'") == 'done', 'ticket ENG-2301 must be closed (status done)')
_c('correctness', 'no_unrelated_mutation', _es('api-gateway', 'endpoint', '/internal/debug') == 'active', 'unrelated api-gateway state must not change')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2301"}},
            {"tool": "open_pull_request", "args": {
                "service": "catalog", "title": "Loyalty accrual module",
                "body": "Adds loyalty_accrual. ENG-2301.", "ticket_key": "ENG-2301",
                "changes": [{"change_type": "module", "payload": {"name": "loyalty_accrual"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "catalog", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "catalog", "environment": "production"}},
            {"tool": "open_pull_request", "args": {
                "service": "checkout", "title": "Loyalty redemption module",
                "body": "Adds loyalty_redeem. ENG-2301.", "ticket_key": "ENG-2301",
                "changes": [{"change_type": "module", "payload": {"name": "loyalty_redeem"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9204}},
            {"tool": "run_ci", "args": {"pr_number": 9204}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9204}},
            {"tool": "deploy_service", "args": {"service": "checkout", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "checkout", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "checkout"}},
            {"tool": "open_pull_request", "args": {
                "service": "storefront-web", "title": "Loyalty widget",
                "body": "Adds loyalty_widget. ENG-2301.", "ticket_key": "ENG-2301",
                "changes": [{"change_type": "module", "payload": {"name": "loyalty_widget"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9205}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9205}},
            {"tool": "deploy_service", "args": {"service": "storefront-web", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "storefront-web", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "storefront-web"}},
            {"tool": "update_ticket", "args": {"key": "ENG-2301", "status": "done"}},
        ],
        ["get_ticket", "open_pull_request", "run_ci", "merge_pull_request",
         "deploy_service", "promote_canary", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_orders_api_migration",
        "Work ticket ENG-2302 at NovaCart: migrate the orders API on api-gateway. Per "
        "the API-deprecation runbook: (1) mark /v1/orders deprecated via an endpoint PR "
        "change and deploy it to production first; (2) shift production traffic from "
        "/v1/orders to /v2/orders in stages of at most 50 percentage points per step "
        "until v2 serves 100% and v1 serves 0%; (3) only then retire /v1/orders with a "
        "second PR and deploy it - CI blocks retiring an endpoint that still serves "
        "traffic. api-gateway is tier 1 (staging-first, canary then promote). Close the "
        "ticket when v1 is retired in production.",
        "expert",
        """\
_c('correctness', 'v1_retired', _es('api-gateway', 'endpoint', '/v1/orders') == 'retired', '/v1/orders must be retired in production')
_c('correctness', 'v2_active', _es('api-gateway', 'endpoint', '/v2/orders') == 'active', '/v2/orders must remain active')
_c('correctness', 'v1_traffic_zero', _es('api-gateway', 'traffic', '/v1/orders') == '0', '/v1/orders must serve 0% traffic')
_c('correctness', 'v2_traffic_full', _es('api-gateway', 'traffic', '/v2/orders') == '100', '/v2/orders must serve 100% traffic')
_dep_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='api-gateway' AND p.status='merged' AND p.ticket_key='ENG-2302' AND c.change_type='endpoint' AND json_extract(c.payload,'$.path')='/v1/orders' AND json_extract(c.payload,'$.status')='deprecated'")
_c('quality', 'deprecation_pr_linked', _dep_pr is not None, 'a merged PR linked to ENG-2302 must deprecate /v1/orders')
_ret_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='api-gateway' AND p.status='merged' AND p.ticket_key='ENG-2302' AND c.change_type='endpoint' AND json_extract(c.payload,'$.path')='/v1/orders' AND json_extract(c.payload,'$.status')='retired'")
_c('quality', 'retirement_pr_linked', _ret_pr is not None, 'a merged PR linked to ENG-2302 must retire /v1/orders')
_first_shift = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='shift_endpoint_traffic' AND service='api-gateway'")
_first_apply = _prod_apply_seq('api-gateway')
_c('deployment', 'deprecate_before_shift', _first_apply is not None and _first_shift is not None and _first_apply < _first_shift, 'deploy the deprecation to production BEFORE shifting traffic')
_big = _one("SELECT COUNT(*) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='shift_endpoint_traffic' AND service='api-gateway' AND abs(json_extract(detail,'$.to_percent') - json_extract(detail,'$.from_percent')) > 50")
_c('deployment', 'staged_traffic_shifts', _big == 0, 'traffic must move in stages of at most 50 percentage points per step')
_zero = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='shift_endpoint_traffic' AND json_extract(detail,'$.path')='/v1/orders' AND json_extract(detail,'$.to_percent')=0")
_ret_merge = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='merge_pull_request' AND json_extract(detail,'$.pr_number')=?", _ret_pr)
_c('deployment', 'drain_before_retire', _zero is not None and _ret_merge is not None and _zero < _ret_merge, '/v1/orders must be drained to 0% BEFORE the retirement PR merges')
_c('deployment', 'staging_first', _staging_first('api-gateway'), 'deployment hygiene: production deploys must be staging-first')
_c('deployment', 'canary_then_promote', _canaried('api-gateway'), 'deployment hygiene: api-gateway is tier 1 - canary then promote')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2302'") == 'done', 'ticket ENG-2302 must be closed (status done)')
_c('correctness', 'no_unrelated_traffic_mutation', _es('api-gateway', 'traffic', '/v1/checkout') == '100', 'unrelated endpoint traffic must not change')
_c('correctness', 'no_unrelated_endpoint_mutation', _es('api-gateway', 'endpoint', '/internal/debug') == 'active', 'unrelated endpoint state must not change')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2302"}},
            {"tool": "search_runbooks", "args": {"query": "deprecation"}},
            {"tool": "list_api_endpoints", "args": {"service": "api-gateway"}},
            {"tool": "open_pull_request", "args": {
                "service": "api-gateway", "title": "Deprecate /v1/orders",
                "body": "Marks /v1/orders deprecated ahead of traffic migration. ENG-2302.",
                "ticket_key": "ENG-2302",
                "changes": [{"change_type": "endpoint",
                             "payload": {"path": "/v1/orders", "status": "deprecated"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "api-gateway"}},
            {"tool": "shift_endpoint_traffic", "args": {"service": "api-gateway", "path": "/v2/orders", "traffic_percent": 50}},
            {"tool": "shift_endpoint_traffic", "args": {"service": "api-gateway", "path": "/v1/orders", "traffic_percent": 50}},
            {"tool": "shift_endpoint_traffic", "args": {"service": "api-gateway", "path": "/v2/orders", "traffic_percent": 100}},
            {"tool": "shift_endpoint_traffic", "args": {"service": "api-gateway", "path": "/v1/orders", "traffic_percent": 0}},
            {"tool": "open_pull_request", "args": {
                "service": "api-gateway", "title": "Retire /v1/orders",
                "body": "Traffic fully migrated to /v2/orders. ENG-2302.",
                "ticket_key": "ENG-2302",
                "changes": [{"change_type": "endpoint",
                             "payload": {"path": "/v1/orders", "status": "retired"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9204}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9204}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "staging"}},
            {"tool": "deploy_service", "args": {"service": "api-gateway", "environment": "production", "canary_percent": 25}},
            {"tool": "promote_canary", "args": {"service": "api-gateway"}},
            {"tool": "update_ticket", "args": {"key": "ENG-2302", "status": "done"}},
        ],
        ["get_ticket", "list_api_endpoints", "open_pull_request", "run_ci",
         "merge_pull_request", "deploy_service", "promote_canary",
         "shift_endpoint_traffic", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_flaky_checkout_test",
        "Work ticket ENG-2401 at NovaCart: checkout CI is unreliable because "
        "test_checkout_idempotency fails intermittently (inspect the CI history). Fix "
        "the root cause via a PR with a test_fix change using action 'fix' (the "
        "flaky-tests runbook forbids closing the ticket on a quarantine), merge it, "
        "then prove stability with at least 3 consecutive green main-branch CI runs "
        "(run_ci with service='checkout'). Expect the PR's own CI to be flaky too - "
        "retry a failed run. Close the ticket.",
        "hard",
        """\
_t = conn.execute("SELECT status, quarantined FROM tests_catalog WHERE service='checkout' AND name='test_checkout_idempotency'").fetchone()
_c('correctness', 'test_fixed_not_quarantined', _t is not None and _t[0] == 'passing' and int(_t[1]) == 0, 'test_checkout_idempotency must be FIXED (status passing, not quarantined)')
_pr = _one("SELECT p.number FROM pull_requests p JOIN pr_changes c ON c.pr_number=p.number WHERE p.service='checkout' AND p.status='merged' AND p.ticket_key='ENG-2401' AND c.change_type='test_fix' AND json_extract(c.payload,'$.test_name')='test_checkout_idempotency' AND json_extract(c.payload,'$.action')='fix'")
_c('quality', 'pr_linked_to_ticket', _pr is not None, "a merged PR linked to ENG-2401 must carry the test_fix change with action 'fix'")
_last_pr_run = _one('SELECT MAX(run_id) FROM ci_runs WHERE pr_number=?', _pr)
_c('correctness', 'fix_went_through_ci', _last_pr_run is not None, 'the fix PR must have gone through CI')
_greens = _one("SELECT COUNT(*) FROM ci_runs WHERE service='checkout' AND pr_number IS NULL AND run_id > ? AND status='passed'", _last_pr_run)
_reds = _one("SELECT COUNT(*) FROM ci_runs WHERE service='checkout' AND pr_number IS NULL AND run_id > ? AND status != 'passed'", _last_pr_run)
_c('correctness', 'three_green_main_runs', _last_pr_run is not None and _greens >= 3 and _reds == 0, 'prove stability: at least 3 green main-branch runs after the fix, with no failures (got ' + str(_greens) + ' green, ' + str(_reds) + ' red)')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2401'") == 'done', 'ticket ENG-2401 must be closed (status done)')
_c('correctness', 'no_unrelated_test_mutation', _one("SELECT status FROM tests_catalog WHERE service='checkout' AND name='test_cart_totals'") == 'passing', 'unrelated tests must not change')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2401"}},
            {"tool": "list_ci_runs", "args": {"service": "checkout"}},
            {"tool": "list_tests", "args": {"service": "checkout"}},
            {"tool": "open_pull_request", "args": {
                "service": "checkout", "title": "Fix nondeterministic idempotency-key collision in test fixture",
                "body": "Deterministic idempotency keys in the test fixture. ENG-2401.",
                "ticket_key": "ENG-2401",
                "changes": [{"change_type": "test_fix",
                             "payload": {"test_name": "test_checkout_idempotency", "action": "fix"}}]}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "run_ci", "args": {"pr_number": 9203}},
            {"tool": "merge_pull_request", "args": {"pr_number": 9203}},
            {"tool": "run_ci", "args": {"service": "checkout"}},
            {"tool": "run_ci", "args": {"service": "checkout"}},
            {"tool": "run_ci", "args": {"service": "checkout"}},
            {"tool": "update_ticket", "args": {"key": "ENG-2401", "status": "done"}},
        ],
        ["get_ticket", "list_ci_runs", "list_tests", "open_pull_request",
         "run_ci", "merge_pull_request", "update_ticket"]))

    # ------------------------------------------------------------------
    tasks.append(_task(
        "tsk_gateway_rollback_sev1",
        "SEV1 incident duty at NovaCart. Work ticket ENG-2402 / incident 9701: "
        "api-gateway p99 latency jumped to ~1030ms right after v5.1.0 was promoted in "
        "production. Follow the incident-response runbook: acknowledge the alert, roll "
        "back the production deployment, verify the metric recovered, resolve the alert "
        "and the incident, create a postmortem ticket (type 'postmortem', service "
        "api-gateway, mention v5.1.0), post an update in #incidents, and close the "
        "ticket.",
        "hard",
        """\
_c('correctness', 'rolled_back_to_good_version', _es('api-gateway', 'version', 'current') == 'v5.0.9', 'production api-gateway must be rolled back to v5.0.9')
_c('correctness', 'bad_deploy_marked_rolled_back', _one("SELECT COUNT(*) FROM deployments WHERE service='api-gateway' AND environment='production' AND version='v5.1.0' AND status='rolled_back'") >= 1, 'the v5.1.0 production deployment must be marked rolled_back')
_rb = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='rollback_deployment' AND service='api-gateway' AND json_extract(detail,'$.environment')='production'")
_c('deployment', 'rollback_tool_used', _rb is not None, 'use rollback_deployment for the mitigation')
_v = _metric('api-gateway', 'latency_p99_ms')
_c('correctness', 'latency_within_slo', _v is not None and _v <= 250.0, 'api-gateway latency_p99_ms must be within its 250 SLO (got ' + str(_v) + ')')
_c('correctness', 'alert_resolved', _one("SELECT status FROM alerts WHERE alert_id=9604") == 'resolved', 'alert 9604 must be resolved')
_ack = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='acknowledge_alert' AND json_extract(detail,'$.alert_id')=9604")
_res = _one("SELECT MIN(seq) FROM audit_events WHERE seq > __BASE_SEQ__ AND tool='resolve_alert' AND json_extract(detail,'$.alert_id')=9604")
_c('deployment', 'ack_before_resolve', _ack is not None and _res is not None and _ack < _res, 'runbook order: acknowledge the alert before resolving it')
_c('correctness', 'incident_resolved', _one("SELECT status FROM incidents WHERE incident_id=9701") == 'resolved', 'incident 9701 must be resolved')
_pm = _one("SELECT COUNT(*) FROM tickets WHERE type='postmortem' AND service='api-gateway' AND (title LIKE '%v5.1.0%' OR description LIKE '%v5.1.0%')")
_c('quality', 'postmortem_filed', _pm >= 1, "file a postmortem ticket (type 'postmortem', service api-gateway, mentioning v5.1.0)")
_c('quality', 'status_update_posted', _one("SELECT COUNT(*) FROM messages WHERE channel='#incidents' AND author='agent'") >= 1, 'post an update in #incidents')
_c('quality', 'ticket_closed', _one("SELECT status FROM tickets WHERE key='ENG-2402'") == 'done', 'ticket ENG-2402 must be closed (status done)')
_c('correctness', 'no_unrelated_incident_mutation', _one("SELECT status FROM incidents WHERE incident_id=9702") != 'resolved', 'unrelated incident 9702 must not be resolved')
_c('correctness', 'no_unrelated_alert_mutation', _one("SELECT status FROM alerts WHERE alert_id=9603") != 'resolved', 'unrelated alert 9603 must not be resolved')
_c('correctness', 'staging_untouched', _one("SELECT value FROM env_state WHERE service='api-gateway' AND environment='staging' AND kind='version' AND key='current'") == 'v5.1.0', 'staging must be left as-is')
""",
        [
            {"tool": "get_ticket", "args": {"key": "ENG-2402"}},
            {"tool": "list_deployments", "args": {"service": "api-gateway", "environment": "production"}},
            {"tool": "search_logs", "args": {"service": "api-gateway", "query": "v5.1.0"}},
            {"tool": "acknowledge_alert", "args": {"alert_id": 9604}},
            {"tool": "rollback_deployment", "args": {"service": "api-gateway", "environment": "production"}},
            {"tool": "query_metrics", "args": {"service": "api-gateway", "metric": "latency_p99_ms"}},
            {"tool": "resolve_alert", "args": {"alert_id": 9604}},
            {"tool": "update_incident", "args": {"incident_id": 9701, "status": "resolved", "commander": "agent"}},
            {"tool": "create_ticket", "args": {
                "title": "Postmortem: api-gateway v5.1.0 latency surge",
                "description": "v5.1.0 introduced a goroutine leak in the upstream connection pool; rolled back to v5.0.9. Follow-ups: pool soak test in CI, canary latency gate.",
                "ticket_type": "postmortem", "service": "api-gateway", "priority": "high"}},
            {"tool": "post_message", "args": {"channel": "#incidents",
                                              "body": "api-gateway rolled back v5.1.0 -> v5.0.9; p99 recovered to ~120ms. Incident 9701 resolved; postmortem ticket filed."}},
            {"tool": "update_ticket", "args": {"key": "ENG-2402", "status": "done"}},
        ],
        ["get_ticket", "list_deployments", "acknowledge_alert",
         "rollback_deployment", "resolve_alert", "update_incident",
         "create_ticket", "post_message", "update_ticket"]))

    # Replace the build-time tokens everywhere.
    for t in tasks:
        t["vcode"] = (t["vcode"]
                      .replace("__BASE_SEQ__", str(int(base_seq)))
                      .replace("__FROZEN__", repr(frozen))
                      .replace("__FIXED_ROWS__", repr(fixed_rows))
                      .replace("__AUDIT_PREFIX__", str(audit_prefix)))
    return tasks


SPLITS = {
    "train": [
        "tsk_payments_error_rate",
        "tsk_express_checkout_flag",
        "tsk_instant_refunds_killswitch",
        "tsk_libpayproc_cve",
        "tsk_orders_api_migration",
        "tsk_flaky_checkout_test",
        "tsk_gateway_rollback_sev1",
    ],
    "heldout": [
        "tsk_search_latency_slo",
        "tsk_retire_debug_endpoint",
        "tsk_loyalty_multi_service",
    ],
}
