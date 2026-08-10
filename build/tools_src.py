"""Tool definitions for the software-devops world.

Every tool is a self-contained module-level function:
  * signature starts with db_path=None (gym runtimes always inject db_path;
    blobfish runtimes inject it because the signature declares it; the
    get_db() fallback covers runtimes that inject globals instead),
  * write tools embed the deterministic engine (_recompute) and the
    deployment state applier (_apply) as nested functions, so each tool's
    source_code runs standalone in per-source runtimes,
  * write tools append to audit_events — verifiers use it for workflow
    ordering (staging-before-prod, canary-before-promote, ...),
  * failures return {"ok": False, "error": ...} (the structured-failure
    protocol: runtimes roll the DB back on these).
"""

import textwrap

# ---------------------------------------------------------------------------
# shared snippets (stamped into tools that need them)
# ---------------------------------------------------------------------------

CONN_PREAMBLE = """\
import sqlite3 as _sq
import json as _json
if db_path:
    conn = _sq.connect(db_path)
else:
    conn = get_db()
conn.row_factory = _sq.Row
"""

ENGINE_SNIPPET = """\
def _recompute(conn):
    _totals = {}
    for _r in conn.execute('SELECT service, metric, kind, ckey, cvalue, value FROM metric_rules ORDER BY rule_id').fetchall():
        _s, _m, _k, _ck, _cv, _v = _r['service'], _r['metric'], _r['kind'], _r['ckey'], _r['cvalue'], _r['value']
        _hit = False
        if _k == 'base':
            _hit = True
        elif _k == 'config_eq':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='config' AND key=?", (_s, _ck)).fetchone()
            _hit = _row is not None and _row[0] == _cv
        elif _k == 'flag_enabled':
            _row = conn.execute("SELECT enabled FROM feature_flags WHERE key=? AND environment='production'", (_ck,)).fetchone()
            _hit = _row is not None and int(_row[0]) == 1
        elif _k == 'dep_lt':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='dependency' AND key=?", (_s, _ck)).fetchone()
            _hit = _row is not None and _row[0] < _cv
        elif _k == 'endpoint_status':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='endpoint' AND key=?", (_s, _ck)).fetchone()
            _hit = _row is not None and _row[0] == _cv
        elif _k == 'version_eq':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='version' AND key='current'", (_s,)).fetchone()
            _hit = _row is not None and _row[0] == _cv
        elif _k == 'version_ge':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='version' AND key='current'", (_s,)).fetchone()
            _hit = _row is not None and _row[0] >= _cv
        if _hit:
            _totals[(_s, _m)] = _totals.get((_s, _m), 0.0) + _v
    for (_s, _m), _v in _totals.items():
        conn.execute("INSERT INTO service_metrics(service, environment, metric, value) VALUES (?, 'production', ?, ?) ON CONFLICT(service, environment, metric) DO UPDATE SET value=excluded.value", (_s, _m, round(_v, 3)))
    for _r in conn.execute('SELECT service, metric, threshold FROM slos').fetchall():
        _row = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (_r['service'], _r['metric'])).fetchone()
        if _row is None or _row[0] <= _r['threshold']:
            continue
        _a = conn.execute("SELECT alert_id FROM alerts WHERE service=? AND metric=? AND status != 'resolved'", (_r['service'], _r['metric'])).fetchone()
        if _a is None:
            conn.execute('INSERT INTO alerts(service, metric, severity, status, message) VALUES (?,?,?,?,?)', (_r['service'], _r['metric'], 'high', 'firing', _r['service'] + ' ' + _r['metric'] + ' ' + str(_row[0]) + ' exceeds SLO ' + str(_r['threshold'])))
    for _vl in conn.execute("SELECT vuln_id, service, package, fixed_version FROM vulnerabilities WHERE status='open'").fetchall():
        _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='dependency' AND key=?", (_vl['service'], _vl['package'])).fetchone()
        if _row is not None and _row[0] >= _vl['fixed_version']:
            conn.execute("UPDATE vulnerabilities SET status='remediated' WHERE vuln_id=?", (_vl['vuln_id'],))
"""

APPLY_SNIPPET = """\
def _apply(conn, _svc, _env, _version):
    _row = conn.execute('SELECT state_json FROM versions WHERE service=? AND version=?', (_svc, _version)).fetchone()
    if _row is None:
        return False
    conn.execute("DELETE FROM env_state WHERE service=? AND environment=? AND kind IN ('config','dependency','endpoint','module')", (_svc, _env))
    for _k, _key, _val in _json.loads(_row[0]):
        conn.execute('INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)', (_svc, _env, _k, _key, _val))
    conn.execute("INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,'version','current',?) ON CONFLICT(service, environment, kind, key) DO UPDATE SET value=excluded.value", (_svc, _env, _version))
    return True
"""

AUDIT_SNIPPET = """\
def _audit(conn, _tool, _svc, _detail):
    conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
"""


def _mk(name, description, params, body, *, reads, writes, returns="dict",
        snippets=(), extra_schema=None):
    """Assemble one tool dict in the packaged tools.json shape."""
    sig_parts = ["db_path=None"]
    for p in params:
        if p.get("required"):
            sig_parts.append("%s=None" % p["name"])
        else:
            sig_parts.append("%s=%r" % (p["name"], p.get("default")))
    src_lines = ["def %s(%s):" % (name, ", ".join(sig_parts))]
    src_lines.append('    """%s"""' % description)
    src_lines.append(textwrap.indent(CONN_PREAMBLE.rstrip(), "    "))
    src_lines.append("    try:")
    inner = []
    for p in params:
        if p.get("required"):
            inner.append("if %s is None:\n    return {'ok': False, 'error': 'missing required parameter: %s'}"
                         % (p["name"], p["name"]))
    for snip in snippets:
        inner.append(snip.rstrip())
    inner.append(body.rstrip())
    src_lines.append(textwrap.indent("\n".join(inner), "        "))
    src_lines.append("    finally:")
    src_lines.append("        conn.close()")
    source = "\n".join(src_lines) + "\n"
    compile(source, "<tool:%s>" % name, "exec")  # authoring-time sanity

    type_map = {"str": "string", "int": "integer", "float": "number",
                "bool": "boolean", "list": "array", "dict": "object"}
    props, required = {}, []
    for p in params:
        schema = {"type": type_map.get(p["type"], "string"),
                  "description": p.get("description", p["name"])}
        if extra_schema and p["name"] in extra_schema:
            schema.update(extra_schema[p["name"]])
        props[p["name"]] = schema
        if p.get("required"):
            required.append(p["name"])
    return {
        "tool_id": "tool_" + name,
        "name": name,
        "description": description,
        "source_code": source,
        "parameters": [
            {"name": p["name"], "type": p["type"],
             "required": bool(p.get("required")),
             "default": None if p.get("required") else str(p.get("default")),
             "description": p.get("description", p["name"])}
            for p in params
        ],
        "return_type": returns,
        "read_tables": sorted(reads),
        "write_tables": sorted(writes),
        "json_schema": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props,
                           "required": required},
        },
    }


def make_tools():
    tools = []
    T = tools.append

    # ------------------------------------------------------------------ reads
    T(_mk(
        "list_services",
        "List all services with team, tier, on-call engineer, repo HEAD version and deployed versions per environment.",
        [],
        """\
out = []
for s in conn.execute('SELECT * FROM services ORDER BY service_id').fetchall():
    d = dict(s)
    oc = conn.execute('SELECT engineer FROM oncall WHERE team=?', (s['team'],)).fetchone()
    d['oncall_engineer'] = oc[0] if oc else ''
    for _env in ('staging', 'production'):
        v = conn.execute("SELECT value FROM env_state WHERE service=? AND environment=? AND kind='version' AND key='current'", (s['name'], _env)).fetchone()
        d[_env + '_version'] = v[0] if v else ''
    out.append(d)
return out""",
        reads=["services", "oncall", "env_state"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_tickets",
        "List tickets, optionally filtered by status, service, or ticket type.",
        [{"name": "status", "type": "str", "default": None, "description": "open|in_progress|in_review|done"},
         {"name": "service", "type": "str", "default": None},
         {"name": "ticket_type", "type": "str", "default": None, "description": "task|bug|feature|security|incident|postmortem"}],
        """\
sql = 'SELECT * FROM tickets'
conds, args = [], []
if status:
    conds.append('status=?'); args.append(status)
if service:
    conds.append('service=?'); args.append(service)
if ticket_type:
    conds.append('type=?'); args.append(ticket_type)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY ticket_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["tickets"], writes=[], returns="list[dict]"))

    T(_mk(
        "get_ticket",
        "Fetch a single ticket by its key (e.g. ENG-2101).",
        [{"name": "key", "type": "str", "required": True, "description": "ticket key, e.g. ENG-2101"}],
        """\
row = conn.execute('SELECT * FROM tickets WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such ticket: ' + str(key)}
return dict(row)""",
        reads=["tickets"], writes=[]))

    T(_mk(
        "list_pull_requests",
        "List pull requests, optionally filtered by service or status (open|merged|closed).",
        [{"name": "service", "type": "str", "default": None},
         {"name": "status", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM pull_requests'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if status:
    conds.append('status=?'); args.append(status)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY number'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["pull_requests"], writes=[], returns="list[dict]"))

    T(_mk(
        "get_pull_request",
        "Fetch a pull request with its structured changes and CI run history.",
        [{"name": "pr_number", "type": "int", "required": True}],
        """\
row = conn.execute('SELECT * FROM pull_requests WHERE number=?', (int(pr_number),)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such pull request: ' + str(pr_number)}
d = dict(row)
d['changes'] = [{'change_type': c['change_type'], 'payload': _json.loads(c['payload'])}
                for c in conn.execute('SELECT change_type, payload FROM pr_changes WHERE pr_number=? ORDER BY change_id', (int(pr_number),)).fetchall()]
d['ci_runs'] = [dict(c) for c in conn.execute('SELECT * FROM ci_runs WHERE pr_number=? ORDER BY run_id', (int(pr_number),)).fetchall()]
return d""",
        reads=["pull_requests", "pr_changes", "ci_runs"], writes=[]))

    T(_mk(
        "list_ci_runs",
        "List CI runs (most recent first), optionally filtered by service or PR number.",
        [{"name": "service", "type": "str", "default": None},
         {"name": "pr_number", "type": "int", "default": None},
         {"name": "limit", "type": "int", "default": 20}],
        """\
sql = 'SELECT * FROM ci_runs'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if pr_number is not None:
    conds.append('pr_number=?'); args.append(int(pr_number))
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY run_id DESC LIMIT ?'
args.append(int(limit))
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["ci_runs"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_deployments",
        "List deployments (most recent first), optionally filtered by service or environment.",
        [{"name": "service", "type": "str", "default": None},
         {"name": "environment", "type": "str", "default": None, "description": "staging|production"},
         {"name": "limit", "type": "int", "default": 20}],
        """\
sql = 'SELECT * FROM deployments'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if environment:
    conds.append('environment=?'); args.append(environment)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY deployment_id DESC LIMIT ?'
args.append(int(limit))
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["deployments"], writes=[], returns="list[dict]"))

    T(_mk(
        "query_metrics",
        "Read current production service metrics (recomputed after every deploy/flag change).",
        [{"name": "service", "type": "str", "default": None},
         {"name": "metric", "type": "str", "default": None, "description": "e.g. error_rate_pct, latency_p99_ms"}],
        """\
sql = "SELECT * FROM service_metrics WHERE environment='production'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
if metric:
    sql += ' AND metric=?'; args.append(metric)
sql += ' ORDER BY service, metric'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["service_metrics"], writes=[], returns="list[dict]"))

    T(_mk(
        "get_slo_status",
        "List SLOs with current metric values and whether each is breaching.",
        [{"name": "service", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM slos'
args = []
if service:
    sql += ' WHERE service=?'; args.append(service)
sql += ' ORDER BY slo_id'
out = []
for r in conn.execute(sql, args).fetchall():
    v = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (r['service'], r['metric'])).fetchone()
    d = dict(r)
    d['current_value'] = v[0] if v else None
    d['breaching'] = (v is not None and v[0] > r['threshold'])
    out.append(d)
return out""",
        reads=["slos", "service_metrics"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_alerts",
        "List alerts, optionally filtered by status (firing|acknowledged|resolved) or service.",
        [{"name": "status", "type": "str", "default": None},
         {"name": "service", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM alerts'
conds, args = [], []
if status:
    conds.append('status=?'); args.append(status)
if service:
    conds.append('service=?'); args.append(service)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY alert_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["alerts"], writes=[], returns="list[dict]"))

    T(_mk(
        "search_logs",
        "Search production/staging log lines by substring, optionally filtered by service or level.",
        [{"name": "service", "type": "str", "default": None},
         {"name": "query", "type": "str", "default": ""},
         {"name": "level", "type": "str", "default": None, "description": "INFO|WARN|ERROR"},
         {"name": "limit", "type": "int", "default": 20}],
        """\
sql = 'SELECT * FROM logs'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if level:
    conds.append('level=?'); args.append(level)
if query:
    conds.append('message LIKE ?'); args.append('%' + str(query) + '%')
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY log_id LIMIT ?'
args.append(int(limit))
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["logs"], writes=[], returns="list[dict]"))

    T(_mk(
        "search_runbooks",
        "Search the knowledge base of runbooks by substring in title or body.",
        [{"name": "query", "type": "str", "default": ""}],
        """\
sql = 'SELECT * FROM runbooks'
args = []
if query:
    sql += ' WHERE title LIKE ? OR body LIKE ?'
    args = ['%' + str(query) + '%', '%' + str(query) + '%']
sql += ' ORDER BY runbook_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["runbooks"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_feature_flags",
        "List feature flags with per-environment enabled state and rollout percent.",
        [{"name": "service", "type": "str", "default": None},
         {"name": "environment", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM feature_flags'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if environment:
    conds.append('environment=?'); args.append(environment)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY key, environment'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["feature_flags"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_dependencies",
        "List package dependencies per service: version at repo HEAD and version deployed in production.",
        [{"name": "service", "type": "str", "default": None}],
        """\
sql = "SELECT service, key, value FROM repo_state WHERE kind='dependency'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
sql += ' ORDER BY service, key'
out = []
for r in conn.execute(sql, args).fetchall():
    p = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='dependency' AND key=?", (r['service'], r['key'])).fetchone()
    out.append({'service': r['service'], 'package': r['key'],
                'repo_version': r['value'],
                'production_version': p[0] if p else None})
return out""",
        reads=["repo_state", "env_state"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_vulnerabilities",
        "List security scanner findings, optionally filtered by status (open|remediated).",
        [{"name": "status", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM vulnerabilities'
args = []
if status:
    sql += ' WHERE status=?'; args.append(status)
sql += ' ORDER BY vuln_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["vulnerabilities"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_api_endpoints",
        "List API endpoints per service with repo HEAD status, production status, and production traffic percent.",
        [{"name": "service", "type": "str", "default": None}],
        """\
sql = "SELECT service, key, value FROM repo_state WHERE kind='endpoint'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
sql += ' ORDER BY service, key'
out = []
for r in conn.execute(sql, args).fetchall():
    p = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='endpoint' AND key=?", (r['service'], r['key'])).fetchone()
    t = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (r['service'], r['key'])).fetchone()
    out.append({'service': r['service'], 'path': r['key'],
                'repo_status': r['value'],
                'production_status': p[0] if p else None,
                'production_traffic_percent': int(t[0]) if t else None})
return out""",
        reads=["repo_state", "env_state"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_tests",
        "List the test catalog, optionally filtered by service or status (passing|flaky|failing).",
        [{"name": "service", "type": "str", "default": None},
         {"name": "status", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM tests_catalog'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if status:
    conds.append('status=?'); args.append(status)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
sql += ' ORDER BY test_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["tests_catalog"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_incidents",
        "List incidents, optionally filtered by status (open|mitigated|resolved).",
        [{"name": "status", "type": "str", "default": None}],
        """\
sql = 'SELECT * FROM incidents'
args = []
if status:
    sql += ' WHERE status=?'; args.append(status)
sql += ' ORDER BY incident_id'
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["incidents"], writes=[], returns="list[dict]"))

    T(_mk(
        "list_messages",
        "Read chat messages (most recent first), optionally scoped to one channel.",
        [{"name": "channel", "type": "str", "default": None, "description": "#incidents|#security|#eng"},
         {"name": "limit", "type": "int", "default": 20}],
        """\
sql = 'SELECT * FROM messages'
args = []
if channel:
    sql += ' WHERE channel=?'; args.append(channel)
sql += ' ORDER BY message_id DESC LIMIT ?'
args.append(int(limit))
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
        reads=["messages"], writes=[], returns="list[dict]"))

    # ----------------------------------------------------------------- writes
    T(_mk(
        "create_ticket",
        "Create a new ticket. Returns the generated ticket key.",
        [{"name": "title", "type": "str", "required": True},
         {"name": "description", "type": "str", "default": ""},
         {"name": "ticket_type", "type": "str", "default": "task", "description": "task|bug|feature|security|incident|postmortem"},
         {"name": "service", "type": "str", "default": ""},
         {"name": "priority", "type": "str", "default": "medium"}],
        """\
if not title:
    return {'ok': False, 'error': 'title is required'}
if ticket_type not in ('task', 'bug', 'feature', 'security', 'incident', 'postmortem'):
    return {'ok': False, 'error': 'invalid ticket_type: ' + str(ticket_type)}
if service:
    if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
        return {'ok': False, 'error': 'unknown service: ' + str(service)}
cur = conn.execute('INSERT INTO tickets(key, type, title, description, status, priority, service) VALUES (?,?,?,?,?,?,?)',
                   ('', ticket_type, title, description, 'open', priority, service))
tid = cur.lastrowid
key = 'TKT-' + str(tid)
conn.execute('UPDATE tickets SET key=? WHERE ticket_id=?', (key, tid))
_audit(conn, 'create_ticket', service, {'key': key, 'type': ticket_type, 'title': title})
conn.commit()
return {'ok': True, 'key': key, 'ticket_id': tid, 'status': 'open'}""",
        reads=["services"], writes=["tickets", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "update_ticket",
        "Update a ticket's status and/or assignee.",
        [{"name": "key", "type": "str", "required": True},
         {"name": "status", "type": "str", "default": None, "description": "open|in_progress|in_review|done"},
         {"name": "assignee", "type": "str", "default": None}],
        """\
row = conn.execute('SELECT * FROM tickets WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such ticket: ' + str(key)}
if status is None and assignee is None:
    return {'ok': False, 'error': 'provide status and/or assignee'}
if status is not None and status not in ('open', 'in_progress', 'in_review', 'done'):
    return {'ok': False, 'error': 'invalid status: ' + str(status)}
new_status = row['status'] if status is None else status
new_assignee = row['assignee'] if assignee is None else assignee
conn.execute('UPDATE tickets SET status=?, assignee=? WHERE key=?', (new_status, new_assignee, key))
_audit(conn, 'update_ticket', row['service'], {'key': key, 'status': new_status, 'assignee': new_assignee})
conn.commit()
return {'ok': True, 'key': key, 'status': new_status, 'assignee': new_assignee}""",
        reads=["tickets"], writes=["tickets", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "open_pull_request",
        "Open a pull request carrying structured changes. Change types: "
        "config {key,value}, dependency {package,version}, endpoint {path,status: active|deprecated|retired}, "
        "module {name}, flag {key,description}, test_fix {test_name, action: fix|quarantine}. "
        "Changes take effect at merge; deploys copy them to an environment.",
        [{"name": "service", "type": "str", "required": True},
         {"name": "title", "type": "str", "required": True},
         {"name": "body", "type": "str", "default": ""},
         {"name": "ticket_key", "type": "str", "default": "", "description": "ticket this PR addresses, e.g. ENG-2101"},
         {"name": "changes", "type": "list", "required": True,
          "description": "list of {change_type, payload} objects"}],
        """\
if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
if not title:
    return {'ok': False, 'error': 'title is required'}
if isinstance(changes, str):
    try:
        changes = _json.loads(changes)
    except Exception:
        return {'ok': False, 'error': 'changes must be a JSON list of {change_type, payload}'}
if not isinstance(changes, list) or not changes:
    return {'ok': False, 'error': 'changes must be a non-empty list of {change_type, payload}'}
norm = []
for ch in changes:
    if not isinstance(ch, dict):
        return {'ok': False, 'error': 'each change must be an object with change_type and payload'}
    ct = ch.get('change_type')
    pl = ch.get('payload')
    if isinstance(pl, str):
        try:
            pl = _json.loads(pl)
        except Exception:
            return {'ok': False, 'error': 'change payload must be an object'}
    if not isinstance(pl, dict):
        return {'ok': False, 'error': 'change payload must be an object'}
    if ct == 'config':
        if not pl.get('key') or 'value' not in pl:
            return {'ok': False, 'error': "config change needs payload {key, value}"}
        pl = {'key': str(pl['key']), 'value': str(pl['value'])}
    elif ct == 'dependency':
        if not pl.get('package') or not pl.get('version'):
            return {'ok': False, 'error': "dependency change needs payload {package, version}"}
        if conn.execute("SELECT 1 FROM repo_state WHERE service=? AND kind='dependency' AND key=?", (service, pl['package'])).fetchone() is None:
            return {'ok': False, 'error': 'service ' + service + ' has no dependency ' + str(pl['package'])}
        pl = {'package': str(pl['package']), 'version': str(pl['version'])}
    elif ct == 'endpoint':
        if not pl.get('path') or pl.get('status') not in ('active', 'deprecated', 'retired'):
            return {'ok': False, 'error': "endpoint change needs payload {path, status: active|deprecated|retired}"}
        if conn.execute("SELECT 1 FROM repo_state WHERE service=? AND kind='endpoint' AND key=?", (service, pl['path'])).fetchone() is None:
            return {'ok': False, 'error': 'service ' + service + ' has no endpoint ' + str(pl['path'])}
        pl = {'path': str(pl['path']), 'status': str(pl['status'])}
    elif ct == 'module':
        if not pl.get('name'):
            return {'ok': False, 'error': "module change needs payload {name}"}
        pl = {'name': str(pl['name'])}
    elif ct == 'flag':
        if not pl.get('key'):
            return {'ok': False, 'error': "flag change needs payload {key, description}"}
        if conn.execute('SELECT 1 FROM feature_flags WHERE key=?', (pl['key'],)).fetchone() is not None:
            return {'ok': False, 'error': 'flag already exists: ' + str(pl['key'])}
        pl = {'key': str(pl['key']), 'description': str(pl.get('description', ''))}
    elif ct == 'test_fix':
        if not pl.get('test_name') or pl.get('action') not in ('fix', 'quarantine'):
            return {'ok': False, 'error': "test_fix change needs payload {test_name, action: fix|quarantine}"}
        if conn.execute('SELECT 1 FROM tests_catalog WHERE service=? AND name=?', (service, pl['test_name'])).fetchone() is None:
            return {'ok': False, 'error': 'service ' + service + ' has no test ' + str(pl['test_name'])}
        pl = {'test_name': str(pl['test_name']), 'action': str(pl['action'])}
    else:
        return {'ok': False, 'error': 'invalid change_type: ' + str(ct)}
    norm.append((ct, pl))
number = conn.execute('SELECT COALESCE(MAX(number), 9200) + 1 FROM pull_requests').fetchone()[0]
conn.execute('INSERT INTO pull_requests(number, service, title, body, author, ticket_key, status) VALUES (?,?,?,?,?,?,?)',
             (number, service, title, body, 'agent', ticket_key, 'open'))
for ct, pl in norm:
    conn.execute('INSERT INTO pr_changes(pr_number, change_type, payload) VALUES (?,?,?)', (number, ct, _json.dumps(pl)))
_audit(conn, 'open_pull_request', service, {'pr_number': number, 'ticket_key': ticket_key, 'change_count': len(norm)})
conn.commit()
return {'ok': True, 'pr_number': number, 'service': service, 'status': 'open',
        'next': 'run_ci(pr_number=' + str(number) + ') then merge_pull_request(pr_number=' + str(number) + ')'}""",
        reads=["services", "repo_state", "feature_flags", "tests_catalog", "pull_requests"],
        writes=["pull_requests", "pr_changes", "audit_events"],
        snippets=(AUDIT_SNIPPET,),
        extra_schema={"changes": {
            "items": {"type": "object",
                      "properties": {"change_type": {"type": "string"},
                                     "payload": {"type": "object"}},
                      "required": ["change_type", "payload"]}}}))

    T(_mk(
        "run_ci",
        "Run the CI pipeline for an open PR (pr_number) or for a service's main branch (service). "
        "The tool succeeds even when the pipeline fails; check the returned status.",
        [{"name": "pr_number", "type": "int", "default": None},
         {"name": "service", "type": "str", "default": None}],
        """\
if pr_number is None and not service:
    return {'ok': False, 'error': 'provide pr_number (PR pipeline) or service (main-branch pipeline)'}
if pr_number is not None:
    pr_number = int(pr_number)
    pr = conn.execute('SELECT * FROM pull_requests WHERE number=?', (pr_number,)).fetchone()
    if pr is None:
        return {'ok': False, 'error': 'no such pull request: ' + str(pr_number)}
    if pr['status'] != 'open':
        return {'ok': False, 'error': 'PR ' + str(pr_number) + ' is not open; for main-branch runs use run_ci(service=...)'}
    service = pr['service']
else:
    if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
        return {'ok': False, 'error': 'unknown service: ' + str(service)}
n_prior = conn.execute('SELECT COUNT(*) FROM ci_runs WHERE service=?', (service,)).fetchone()[0]
status, detail = 'passed', 'all checks passed'
if pr_number is not None:
    for c in conn.execute("SELECT payload FROM pr_changes WHERE pr_number=? AND change_type='endpoint'", (pr_number,)).fetchall():
        pl = _json.loads(c['payload'])
        if pl.get('status') == 'retired':
            t = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (service, pl['path'])).fetchone()
            if t is not None and int(t[0]) > 0:
                status = 'failed'
                detail = 'cannot retire ' + pl['path'] + ': still serving ' + str(t[0]) + '% of production traffic - drain it first'
                break
if status == 'passed':
    failing = [r['name'] for r in conn.execute("SELECT name FROM tests_catalog WHERE service=? AND status='failing' AND quarantined=0", (service,)).fetchall()]
    if failing:
        status, detail = 'failed', 'failing tests: ' + ', '.join(failing)
if status == 'passed':
    flaky = [r['name'] for r in conn.execute("SELECT name FROM tests_catalog WHERE service=? AND status='flaky' AND quarantined=0", (service,)).fetchall()]
    if flaky and n_prior % 2 == 0:
        status, detail = 'failed', 'intermittent failure: ' + ', '.join(flaky) + ' (rerun may pass)'
cur = conn.execute('INSERT INTO ci_runs(service, pr_number, status, detail) VALUES (?,?,?,?)', (service, pr_number, status, detail))
_audit(conn, 'run_ci', service, {'pr_number': pr_number, 'status': status})
conn.commit()
return {'ok': True, 'run_id': cur.lastrowid, 'service': service, 'pr_number': pr_number,
        'status': status, 'detail': detail}""",
        reads=["pull_requests", "pr_changes", "tests_catalog", "env_state", "services"],
        writes=["ci_runs", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "merge_pull_request",
        "Merge an open PR. Blocked unless the PR's latest CI run passed. Applies the PR's "
        "changes to the service's repo HEAD and cuts a new deployable version.",
        [{"name": "pr_number", "type": "int", "required": True}],
        """\
pr_number = int(pr_number)
pr = conn.execute('SELECT * FROM pull_requests WHERE number=?', (pr_number,)).fetchone()
if pr is None:
    return {'ok': False, 'error': 'no such pull request: ' + str(pr_number)}
if pr['status'] != 'open':
    return {'ok': False, 'error': 'PR ' + str(pr_number) + ' is not open'}
last = conn.execute('SELECT status FROM ci_runs WHERE pr_number=? ORDER BY run_id DESC LIMIT 1', (pr_number,)).fetchone()
if last is None:
    return {'ok': False, 'error': 'no CI run recorded for PR ' + str(pr_number) + '; call run_ci(pr_number=...) first'}
if last[0] != 'passed':
    return {'ok': False, 'error': 'latest CI run for PR ' + str(pr_number) + ' is ' + last[0] + '; merge blocked'}
service = pr['service']
for c in conn.execute('SELECT change_type, payload FROM pr_changes WHERE pr_number=? ORDER BY change_id', (pr_number,)).fetchall():
    ct, pl = c['change_type'], _json.loads(c['payload'])
    if ct == 'config':
        conn.execute("INSERT INTO repo_state(service, kind, key, value) VALUES (?,'config',?,?) ON CONFLICT(service, kind, key) DO UPDATE SET value=excluded.value", (service, pl['key'], pl['value']))
    elif ct == 'dependency':
        conn.execute("UPDATE repo_state SET value=? WHERE service=? AND kind='dependency' AND key=?", (pl['version'], service, pl['package']))
    elif ct == 'endpoint':
        conn.execute("UPDATE repo_state SET value=? WHERE service=? AND kind='endpoint' AND key=?", (pl['status'], service, pl['path']))
    elif ct == 'module':
        conn.execute("INSERT INTO repo_state(service, kind, key, value) VALUES (?,'module',?,'present') ON CONFLICT(service, kind, key) DO UPDATE SET value=excluded.value", (service, pl['name']))
    elif ct == 'flag':
        for _env in ('staging', 'production'):
            conn.execute('INSERT OR IGNORE INTO feature_flags(key, service, description, environment, enabled, rollout_percent) VALUES (?,?,?,?,0,0)', (pl['key'], service, pl.get('description', ''), _env))
    elif ct == 'test_fix':
        if pl['action'] == 'fix':
            conn.execute("UPDATE tests_catalog SET status='passing', quarantined=0 WHERE service=? AND name=?", (service, pl['test_name']))
        else:
            conn.execute('UPDATE tests_catalog SET quarantined=1 WHERE service=? AND name=?', (service, pl['test_name']))
old = conn.execute('SELECT repo_version FROM services WHERE name=?', (service,)).fetchone()[0]
parts = old.lstrip('v').split('.')
new_version = 'v' + parts[0] + '.' + parts[1] + '.' + str(int(parts[2]) + 1)
conn.execute('UPDATE services SET repo_version=? WHERE name=?', (new_version, service))
state = [[r['kind'], r['key'], r['value']] for r in conn.execute("SELECT kind, key, value FROM repo_state WHERE service=? AND kind IN ('config','dependency','endpoint','module') ORDER BY kind, key", (service,)).fetchall()]
conn.execute('INSERT INTO versions(service, version, state_json) VALUES (?,?,?)', (service, new_version, _json.dumps(state)))
conn.execute("UPDATE pull_requests SET status='merged', merged_version=? WHERE number=?", (new_version, pr_number))
_audit(conn, 'merge_pull_request', service, {'pr_number': pr_number, 'version': new_version})
conn.commit()
return {'ok': True, 'pr_number': pr_number, 'service': service, 'merged_version': new_version,
        'next': 'deploy_service(service=..., environment=...)'}""",
        reads=["pull_requests", "ci_runs", "pr_changes", "services"],
        writes=["repo_state", "feature_flags", "tests_catalog", "services",
                "versions", "pull_requests", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "deploy_service",
        "Deploy a merged version to staging or production. canary_percent<100 stages a canary "
        "(state applies only after promote_canary). Policy: production deploys are staging-first; "
        "tier-1 services canary at <=25% then promote.",
        [{"name": "service", "type": "str", "required": True},
         {"name": "environment", "type": "str", "required": True, "description": "staging|production"},
         {"name": "version", "type": "str", "default": None, "description": "defaults to the service's repo HEAD version"},
         {"name": "canary_percent", "type": "int", "default": 100}],
        """\
if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
if environment not in ('staging', 'production'):
    return {'ok': False, 'error': "environment must be 'staging' or 'production'"}
canary_percent = int(canary_percent)
if canary_percent < 1 or canary_percent > 100:
    return {'ok': False, 'error': 'canary_percent must be between 1 and 100'}
if environment == 'staging':
    canary_percent = 100
if not version:
    version = conn.execute('SELECT repo_version FROM services WHERE name=?', (service,)).fetchone()[0]
if conn.execute('SELECT 1 FROM versions WHERE service=? AND version=?', (service, version)).fetchone() is None:
    return {'ok': False, 'error': 'unknown version ' + str(version) + ' for ' + service + ' (only merged versions can be deployed)'}
applied = canary_percent >= 100
status = 'succeeded' if applied else 'canary'
cur = conn.execute('INSERT INTO deployments(service, environment, version, status, canary_percent) VALUES (?,?,?,?,?)',
                   (service, environment, version, status, canary_percent))
if applied:
    _apply(conn, service, environment, version)
    _recompute(conn)
_audit(conn, 'deploy_service', service, {'environment': environment, 'version': version,
                                         'canary_percent': canary_percent, 'applied': applied})
conn.commit()
out = {'ok': True, 'deployment_id': cur.lastrowid, 'service': service, 'environment': environment,
       'version': version, 'status': status, 'canary_percent': canary_percent, 'applied': applied}
if not applied:
    out['next'] = 'verify metrics, then promote_canary(service=..., environment=...)'
return out""",
        reads=["services", "versions"],
        writes=["deployments", "env_state", "service_metrics", "alerts",
                "vulnerabilities", "audit_events"],
        snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk(
        "promote_canary",
        "Promote the latest canary deployment of a service to 100%; its state takes effect.",
        [{"name": "service", "type": "str", "required": True},
         {"name": "environment", "type": "str", "default": "production"}],
        """\
d = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='canary' ORDER BY deployment_id DESC LIMIT 1", (service, environment)).fetchone()
if d is None:
    return {'ok': False, 'error': 'no canary deployment to promote for ' + str(service) + ' in ' + str(environment)}
conn.execute("UPDATE deployments SET status='succeeded', canary_percent=100 WHERE deployment_id=?", (d['deployment_id'],))
_apply(conn, service, environment, d['version'])
_recompute(conn)
_audit(conn, 'promote_canary', service, {'environment': environment, 'version': d['version'],
                                         'deployment_id': d['deployment_id']})
conn.commit()
return {'ok': True, 'deployment_id': d['deployment_id'], 'service': service,
        'environment': environment, 'version': d['version'], 'status': 'succeeded'}""",
        reads=["deployments"],
        writes=["deployments", "env_state", "service_metrics", "alerts",
                "vulnerabilities", "audit_events"],
        snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk(
        "rollback_deployment",
        "Emergency rollback: revert a service in an environment to its previous successful "
        "deployment. Exempt from the staging-first rule.",
        [{"name": "service", "type": "str", "required": True},
         {"name": "environment", "type": "str", "default": "production"}],
        """\
cur_d = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='succeeded' ORDER BY deployment_id DESC LIMIT 1", (service, environment)).fetchone()
if cur_d is None:
    return {'ok': False, 'error': 'no successful deployment to roll back for ' + str(service) + ' in ' + str(environment)}
prev = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='succeeded' AND deployment_id<? ORDER BY deployment_id DESC LIMIT 1", (service, environment, cur_d['deployment_id'])).fetchone()
if prev is None:
    return {'ok': False, 'error': 'no previous successful deployment to roll back to'}
conn.execute("UPDATE deployments SET status='rolled_back' WHERE deployment_id=?", (cur_d['deployment_id'],))
_apply(conn, service, environment, prev['version'])
_recompute(conn)
_audit(conn, 'rollback_deployment', service, {'environment': environment,
                                              'from_version': cur_d['version'],
                                              'to_version': prev['version']})
conn.commit()
return {'ok': True, 'service': service, 'environment': environment,
        'from_version': cur_d['version'], 'to_version': prev['version']}""",
        reads=["deployments"],
        writes=["deployments", "env_state", "service_metrics", "alerts",
                "vulnerabilities", "audit_events"],
        snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk(
        "set_feature_flag",
        "Toggle a feature flag or change its rollout percent in one environment. Runtime "
        "operation: takes effect immediately, no deploy needed. The flag must already be "
        "defined (flags are defined via a 'flag' PR change).",
        [{"name": "key", "type": "str", "required": True},
         {"name": "environment", "type": "str", "required": True, "description": "staging|production"},
         {"name": "enabled", "type": "bool", "default": None},
         {"name": "rollout_percent", "type": "int", "default": None}],
        """\
if environment not in ('staging', 'production'):
    return {'ok': False, 'error': "environment must be 'staging' or 'production'"}
row = conn.execute('SELECT * FROM feature_flags WHERE key=? AND environment=?', (key, environment)).fetchone()
if row is None:
    return {'ok': False, 'error': 'unknown flag ' + str(key) + ' in ' + str(environment) + " (define flags via a 'flag' PR change)"}
if enabled is None and rollout_percent is None:
    return {'ok': False, 'error': 'provide enabled and/or rollout_percent'}
new_enabled = row['enabled']
if enabled is not None:
    new_enabled = 1 if str(enabled).lower() in ('1', 'true', 'yes', 'on') else 0
new_rollout = row['rollout_percent']
if rollout_percent is not None:
    new_rollout = int(rollout_percent)
    if new_rollout < 0 or new_rollout > 100:
        return {'ok': False, 'error': 'rollout_percent must be between 0 and 100'}
conn.execute('UPDATE feature_flags SET enabled=?, rollout_percent=? WHERE key=? AND environment=?',
             (new_enabled, new_rollout, key, environment))
_recompute(conn)
_audit(conn, 'set_feature_flag', row['service'], {'key': key, 'environment': environment,
                                                  'enabled': new_enabled, 'rollout_percent': new_rollout})
conn.commit()
return {'ok': True, 'key': key, 'environment': environment,
        'enabled': new_enabled, 'rollout_percent': new_rollout}""",
        reads=["feature_flags"],
        writes=["feature_flags", "service_metrics", "alerts", "vulnerabilities",
                "audit_events"],
        snippets=(ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk(
        "shift_endpoint_traffic",
        "Set the production traffic percent served by an endpoint (gateway runtime weight; "
        "no deploy needed). Policy: shift in stages of at most 50 points per step.",
        [{"name": "service", "type": "str", "required": True},
         {"name": "path", "type": "str", "required": True},
         {"name": "traffic_percent", "type": "int", "required": True}],
        """\
tp = int(traffic_percent)
if tp < 0 or tp > 100:
    return {'ok': False, 'error': 'traffic_percent must be between 0 and 100'}
row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (service, path)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no production traffic record for ' + str(path) + ' on ' + str(service)}
old = int(row[0])
conn.execute("UPDATE env_state SET value=? WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (str(tp), service, path))
_audit(conn, 'shift_endpoint_traffic', service, {'path': path, 'from_percent': old, 'to_percent': tp})
conn.commit()
return {'ok': True, 'service': service, 'path': path, 'from_percent': old, 'to_percent': tp}""",
        reads=["env_state"],
        writes=["env_state", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "acknowledge_alert",
        "Acknowledge a firing alert (marks it acknowledged; it stays active until resolved).",
        [{"name": "alert_id", "type": "int", "required": True}],
        """\
alert_id = int(alert_id)
row = conn.execute('SELECT * FROM alerts WHERE alert_id=?', (alert_id,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such alert: ' + str(alert_id)}
if row['status'] == 'resolved':
    return {'ok': False, 'error': 'alert ' + str(alert_id) + ' is already resolved'}
conn.execute("UPDATE alerts SET status='acknowledged' WHERE alert_id=?", (alert_id,))
_audit(conn, 'acknowledge_alert', row['service'], {'alert_id': alert_id})
conn.commit()
return {'ok': True, 'alert_id': alert_id, 'status': 'acknowledged'}""",
        reads=["alerts"], writes=["alerts", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "resolve_alert",
        "Resolve an alert. Refused while the underlying metric still breaches its SLO — "
        "fix and deploy first.",
        [{"name": "alert_id", "type": "int", "required": True}],
        """\
alert_id = int(alert_id)
row = conn.execute('SELECT * FROM alerts WHERE alert_id=?', (alert_id,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such alert: ' + str(alert_id)}
if row['status'] == 'resolved':
    return {'ok': False, 'error': 'alert ' + str(alert_id) + ' is already resolved'}
slo = conn.execute('SELECT threshold FROM slos WHERE service=? AND metric=?', (row['service'], row['metric'])).fetchone()
if slo is not None:
    mv = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (row['service'], row['metric'])).fetchone()
    if mv is not None and mv[0] > slo[0]:
        return {'ok': False, 'error': row['service'] + ' ' + row['metric'] + ' is still ' + str(mv[0]) + ' (SLO ' + str(slo[0]) + ') - fix and deploy before resolving'}
conn.execute("UPDATE alerts SET status='resolved' WHERE alert_id=?", (alert_id,))
_audit(conn, 'resolve_alert', row['service'], {'alert_id': alert_id})
conn.commit()
return {'ok': True, 'alert_id': alert_id, 'status': 'resolved'}""",
        reads=["alerts", "slos", "service_metrics"],
        writes=["alerts", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "create_incident",
        "Declare a new incident.",
        [{"name": "title", "type": "str", "required": True},
         {"name": "service", "type": "str", "required": True},
         {"name": "severity", "type": "str", "required": True, "description": "sev1|sev2|sev3"}],
        """\
if severity not in ('sev1', 'sev2', 'sev3'):
    return {'ok': False, 'error': 'severity must be sev1|sev2|sev3'}
if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
cur = conn.execute('INSERT INTO incidents(severity, title, service, status) VALUES (?,?,?,?)',
                   (severity, title, service, 'open'))
_audit(conn, 'create_incident', service, {'incident_id': cur.lastrowid, 'severity': severity})
conn.commit()
return {'ok': True, 'incident_id': cur.lastrowid, 'status': 'open'}""",
        reads=["services"], writes=["incidents", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "update_incident",
        "Update an incident's status (open|mitigated|resolved) and/or commander.",
        [{"name": "incident_id", "type": "int", "required": True},
         {"name": "status", "type": "str", "default": None},
         {"name": "commander", "type": "str", "default": None}],
        """\
incident_id = int(incident_id)
row = conn.execute('SELECT * FROM incidents WHERE incident_id=?', (incident_id,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such incident: ' + str(incident_id)}
if status is None and commander is None:
    return {'ok': False, 'error': 'provide status and/or commander'}
if status is not None and status not in ('open', 'mitigated', 'resolved'):
    return {'ok': False, 'error': 'invalid status: ' + str(status)}
new_status = row['status'] if status is None else status
new_commander = row['commander'] if commander is None else commander
conn.execute('UPDATE incidents SET status=?, commander=? WHERE incident_id=?',
             (new_status, new_commander, incident_id))
_audit(conn, 'update_incident', row['service'], {'incident_id': incident_id, 'status': new_status})
conn.commit()
return {'ok': True, 'incident_id': incident_id, 'status': new_status, 'commander': new_commander}""",
        reads=["incidents"], writes=["incidents", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    T(_mk(
        "post_message",
        "Post a message to a chat channel (#incidents, #security, or #eng).",
        [{"name": "channel", "type": "str", "required": True},
         {"name": "body", "type": "str", "required": True}],
        """\
if conn.execute('SELECT 1 FROM channels WHERE channel=?', (channel,)).fetchone() is None:
    rows = [r[0] for r in conn.execute('SELECT channel FROM channels ORDER BY channel').fetchall()]
    return {'ok': False, 'error': 'unknown channel ' + str(channel) + '; valid: ' + ', '.join(rows)}
if not str(body).strip():
    return {'ok': False, 'error': 'body must not be empty'}
cur = conn.execute('INSERT INTO messages(channel, author, body) VALUES (?,?,?)', (channel, 'agent', str(body)))
_audit(conn, 'post_message', '', {'channel': channel, 'message_id': cur.lastrowid})
conn.commit()
return {'ok': True, 'message_id': cur.lastrowid, 'channel': channel}""",
        reads=["channels"], writes=["messages", "audit_events"],
        snippets=(AUDIT_SNIPPET,)))

    return tools


if __name__ == "__main__":
    ts = make_tools()
    print(len(ts), "tools")
    for t in ts:
        compile(t["source_code"], t["name"], "exec")
    print("all sources compile")
