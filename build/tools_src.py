"""Tool definitions for the software-devops world (v2).

Every tool is a self-contained module-level function:
  * signature starts with db_path=None (gym runtimes always inject db_path;
    blobfish runtimes inject it because the signature declares it; the
    get_db() fallback covers runtimes that inject globals instead),
  * write tools embed the deterministic engine (_recompute), the deployment
    state applier (_apply) and the audit helper, so each tool's source_code
    runs standalone in per-source runtimes,
  * failures return {"ok": False, "error": ...} (the structured-failure
    protocol: runtimes roll the DB back on these).
"""

import textwrap

CONN_PREAMBLE = """\
import sqlite3 as _sq
import json as _json
if db_path:
    conn = _sq.connect(db_path)
else:
    conn = get_db()
conn.row_factory = _sq.Row
"""

# The traffic generator + application model: production metrics are recomputed
# from what is actually deployed, alarms follow SLOs, scanners follow deployed
# dependency versions.
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
        elif _k == 'xconfig_eq':
            _os, _ok2 = _ck.split(':', 1)
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='config' AND key=?", (_os, _ok2)).fetchone()
            _hit = _row is not None and _row[0] == _cv
        elif _k == 'config_lt':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='config' AND key=?", (_s, _ck)).fetchone()
            try:
                _hit = _row is not None and float(_row[0]) < float(_cv)
            except Exception:
                _hit = False
        elif _k == 'flag_enabled':
            _row = conn.execute("SELECT enabled FROM feature_flags WHERE key=? AND environment='production'", (_ck,)).fetchone()
            _hit = _row is not None and int(_row[0]) == 1
        elif _k == 'endpoint_status':
            _row = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='endpoint' AND key=?", (_s, _ck)).fetchone()
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
def _breaching(conn, _svc):
    _out = []
    for _r in conn.execute('SELECT metric, threshold FROM slos WHERE service=?', (_svc,)).fetchall():
        _v = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (_svc, _r['metric'])).fetchone()
        if _v is not None and _v[0] > _r['threshold']:
            _out.append(_r['metric'] + '=' + str(_v[0]) + ' (SLO ' + str(_r['threshold']) + ')')
    return _out
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
    inner = ["try:\n    conn.execute('INSERT INTO tool_calls(tool) VALUES (?)', (%r,)); conn.commit()\nexcept Exception:\n    pass" % name]
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
    compile(source, "<tool:%s>" % name, "exec")

    type_map = {"str": "string", "int": "integer", "float": "number",
                "bool": "boolean", "list": "array", "dict": "object"}
    props, required = {}, []
    for p in params:
        schema = {"type": type_map.get(p["type"], "string"),
                  "description": p.get("description", p["name"])}
        # A controlled vocabulary that lives only in prose is invisible to a
        # native tool-calling API, which constrains generation against `enum`.
        # Leaving it out let a model emit fault_type="SLO Breach", get rejected,
        # and then flip its own answer to something the tool would accept.
        if p.get("choices"):
            schema["enum"] = list(p["choices"])
        if extra_schema and p["name"] in extra_schema:
            schema.update(extra_schema[p["name"]])
        props[p["name"]] = schema
        if p.get("required"):
            required.append(p["name"])
    return {
        "tool_id": "tool_" + name, "name": name, "description": description,
        "source_code": source,
        "parameters": [
            {"name": p["name"], "type": p["type"], "required": bool(p.get("required")),
             "default": None if p.get("required") else str(p.get("default")),
             "description": p.get("description", p["name"])} for p in params],
        "return_type": returns,
        "read_tables": sorted(reads), "write_tables": sorted(writes),
        "json_schema": {"name": name, "description": description,
                        "parameters": {"type": "object", "properties": props,
                                       "required": required}},
    }


def make_tools():
    tools = []
    T = tools.append

    # ================================================================= READS
    T(_mk("list_services",
          "List all services with team, tier, kind, on-call engineer, repo HEAD version and deployed versions.",
          [{"name": "team", "type": "str", "default": None},
           {"name": "tier", "type": "int", "default": None}],
          """\
sql = 'SELECT * FROM services'
conds, args = [], []
if team:
    conds.append('team=?'); args.append(team)
if tier is not None:
    conds.append('tier=?'); args.append(int(tier))
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
out = []
for s in conn.execute(sql + ' ORDER BY service_id', args).fetchall():
    d = dict(s)
    oc = conn.execute('SELECT engineer FROM oncall WHERE team=?', (s['team'],)).fetchone()
    d['oncall_engineer'] = oc[0] if oc else ''
    for _env in ('staging', 'production'):
        v = conn.execute("SELECT value FROM env_state WHERE service=? AND environment=? AND kind='version' AND key='current'", (s['name'], _env)).fetchone()
        d[_env + '_version'] = v[0] if v else ''
    out.append(d)
return out""",
          reads=["services", "oncall", "env_state"], writes=[], returns="list[dict]"))

    T(_mk("get_service",
          "Full detail for one service: metadata, deployed config, modules, endpoints, dependencies, current metrics.",
          [{"name": "service", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT * FROM services WHERE name=?', (service,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
d = dict(row)
d['production'] = {}
for r in conn.execute("SELECT kind, key, value FROM env_state WHERE service=? AND environment='production' ORDER BY kind, key", (service,)).fetchall():
    d['production'].setdefault(r['kind'], {})[r['key']] = r['value']
d['depends_on'] = [dict(r) for r in conn.execute('SELECT depends_on, kind FROM service_dependencies WHERE service=? ORDER BY depends_on', (service,)).fetchall()]
d['metrics'] = {r['metric']: r['value'] for r in conn.execute("SELECT metric, value FROM service_metrics WHERE service=? AND environment='production'", (service,)).fetchall()}
oc = conn.execute('SELECT engineer FROM oncall WHERE team=?', (row['team'],)).fetchone()
d['oncall_engineer'] = oc[0] if oc else ''
return d""",
          reads=["services", "env_state", "service_dependencies", "service_metrics", "oncall"],
          writes=[]))

    T(_mk("list_infra",
          "List infrastructure components of the application stack (databases, caches, queues, object stores, CDN).",
          [],
          """\
return [dict(r) for r in conn.execute('SELECT * FROM infra_components ORDER BY component_id').fetchall()]""",
          reads=["infra_components"], writes=[], returns="list[dict]"))

    T(_mk("list_files",
          "List monorepo files, optionally filtered by service or path substring.",
          [{"name": "service", "type": "str", "default": None},
           {"name": "path_contains", "type": "str", "default": None}],
          """\
sql = 'SELECT file_id, service, path, language, owner, loc FROM repo_files'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if path_contains:
    conds.append('path LIKE ?'); args.append('%' + str(path_contains) + '%')
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY path', args).fetchall()]""",
          reads=["repo_files"], writes=[], returns="list[dict]"))

    T(_mk("read_file",
          "Read a monorepo source file. Returns its full current content.",
          [{"name": "path", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT * FROM repo_files WHERE path=?', (path,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such file: ' + str(path)}
return dict(row)""",
          reads=["repo_files"], writes=[]))

    T(_mk("search_code",
          "Search monorepo file contents for a substring; returns matching files with matching line numbers.",
          [{"name": "query", "type": "str", "required": True},
           {"name": "service", "type": "str", "default": None},
           {"name": "limit", "type": "int", "default": 20}],
          """\
sql = 'SELECT service, path, content FROM repo_files WHERE content LIKE ?'
args = ['%' + str(query) + '%']
if service:
    sql += ' AND service=?'; args.append(service)
out = []
for r in conn.execute(sql + ' ORDER BY path LIMIT ?', args + [int(limit)]).fetchall():
    hits = []
    for i, line in enumerate(r['content'].split(chr(10)), 1):
        if str(query) in line:
            hits.append({'line': i, 'text': line.strip()[:200]})
    out.append({'service': r['service'], 'path': r['path'], 'matches': hits[:8]})
return out""",
          reads=["repo_files"], writes=[], returns="list[dict]"))

    T(_mk("list_commits",
          "Browse monorepo commit history (most recent first).",
          [{"name": "service", "type": "str", "default": None},
           {"name": "query", "type": "str", "default": None, "description": "substring of the commit message"},
           {"name": "path", "type": "str", "default": None, "description": "only commits touching this file path"},
           {"name": "limit", "type": "int", "default": 20}],
          """\
sql = 'SELECT sha, service, author, day, message, files, additions, deletions FROM commits'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if query:
    conds.append('message LIKE ?'); args.append('%' + str(query) + '%')
if path:
    conds.append('files LIKE ?'); args.append('%' + str(path) + '%')
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY day DESC, commit_id DESC LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["commits"], writes=[], returns="list[dict]"))

    T(_mk("search_docs",
          "Search the engineering knowledge base (runbooks, policies, design docs, ADRs, postmortems, API specs).",
          [{"name": "query", "type": "str", "default": ""},
           {"name": "kind", "type": "str", "default": None,
            "description": "runbook|policy|design_doc|adr|postmortem|api_spec|onboarding"},
           {"name": "service", "type": "str", "default": None},
           {"name": "limit", "type": "int", "default": 10}],
          """\
sql = 'SELECT doc_id, kind, title, service, author, day FROM documents'
conds, args = [], []
if query:
    conds.append('(title LIKE ? OR body LIKE ?)'); args += ['%' + str(query) + '%', '%' + str(query) + '%']
if kind:
    conds.append('kind=?'); args.append(kind)
if service:
    conds.append('service=?'); args.append(service)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY doc_id LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["documents"], writes=[], returns="list[dict]"))

    T(_mk("get_document",
          "Read one knowledge-base document in full by doc_id (or exact title).",
          [{"name": "doc_id", "type": "int", "default": None},
           {"name": "title", "type": "str", "default": None}],
          """\
row = None
if doc_id is not None:
    row = conn.execute('SELECT * FROM documents WHERE doc_id=?', (int(doc_id),)).fetchone()
elif title:
    row = conn.execute('SELECT * FROM documents WHERE title=?', (title,)).fetchone()
    if row is None:
        row = conn.execute('SELECT * FROM documents WHERE title LIKE ?', ('%' + str(title) + '%',)).fetchone()
else:
    return {'ok': False, 'error': 'provide doc_id or title'}
if row is None:
    return {'ok': False, 'error': 'document not found'}
return dict(row)""",
          reads=["documents"], writes=[]))

    T(_mk("list_tickets",
          "List issue-tracker tickets, optionally filtered by status, service, or type.",
          [{"name": "status", "type": "str", "default": None},
           {"name": "service", "type": "str", "default": None},
           {"name": "ticket_type", "type": "str", "default": None}],
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY ticket_id', args).fetchall()]""",
          reads=["tickets"], writes=[], returns="list[dict]"))

    T(_mk("get_ticket", "Fetch one ticket by key (e.g. ENG-2101).",
          [{"name": "key", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT * FROM tickets WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such ticket: ' + str(key)}
return dict(row)""",
          reads=["tickets"], writes=[]))

    T(_mk("list_pull_requests", "List pull requests, optionally filtered by service or status.",
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY number', args).fetchall()]""",
          reads=["pull_requests"], writes=[], returns="list[dict]"))

    T(_mk("get_pull_request", "Fetch a PR with its structured changes and CI history.",
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

    T(_mk("list_ci_runs", "List CI runs (most recent first).",
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY run_id DESC LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["ci_runs"], writes=[], returns="list[dict]"))

    T(_mk("get_ci_run", "Fetch one CI run with its per-stage results (build, unit, integration, regression).",
          [{"name": "run_id", "type": "int", "required": True}],
          """\
row = conn.execute('SELECT * FROM ci_runs WHERE run_id=?', (int(run_id),)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such CI run: ' + str(run_id)}
d = dict(row)
d['stages'] = [dict(s) for s in conn.execute('SELECT stage, status, detail FROM ci_stages WHERE run_id=? ORDER BY stage_id', (int(run_id),)).fetchall()]
return d""",
          reads=["ci_runs", "ci_stages"], writes=[]))

    T(_mk("list_deployments", "List deployments (most recent first).",
          [{"name": "service", "type": "str", "default": None},
           {"name": "environment", "type": "str", "default": None},
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY deployment_id DESC LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["deployments"], writes=[], returns="list[dict]"))

    T(_mk("list_migrations", "List database migrations and whether they are applied per environment.",
          [{"name": "service", "type": "str", "default": None},
           {"name": "environment", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM migrations'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if environment:
    conds.append('environment=?'); args.append(environment)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
rows = [dict(r) for r in conn.execute(sql + ' ORDER BY migration_id', args).fetchall()]
pend = [dict(r) for r in conn.execute('SELECT service, module, migration_name FROM migration_requirements ORDER BY req_id').fetchall()]
return {'applied': rows, 'declared_requirements': pend}""",
          reads=["migrations", "migration_requirements"], writes=[]))

    T(_mk("query_metrics", "Read current production service metrics (recomputed continuously from live traffic).",
          [{"name": "service", "type": "str", "default": None},
           {"name": "metric", "type": "str", "default": None}],
          """\
sql = "SELECT * FROM service_metrics WHERE environment='production'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
if metric:
    sql += ' AND metric=?'; args.append(metric)
return [dict(r) for r in conn.execute(sql + ' ORDER BY service, metric', args).fetchall()]""",
          reads=["service_metrics"], writes=[], returns="list[dict]"))

    T(_mk("get_traffic_stats",
          "Traffic-generator statistics: request rate per route with the current error rate and p99 of the owning service.",
          [{"name": "service", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM traffic_profile'
args = []
if service:
    sql += ' WHERE service=?'; args.append(service)
out = []
for r in conn.execute(sql + ' ORDER BY route_id', args).fetchall():
    d = dict(r)
    for m in ('error_rate_pct', 'latency_p99_ms'):
        v = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (r['service'], m)).fetchone()
        d[m] = v[0] if v else None
    if d.get('error_rate_pct') is not None:
        d['failed_requests_per_min'] = round(r['rps'] * 60.0 * d['error_rate_pct'] / 100.0, 1)
    out.append(d)
return out""",
          reads=["traffic_profile", "service_metrics"], writes=[], returns="list[dict]"))

    T(_mk("get_slo_status", "List SLOs with current values and whether each is breaching.",
          [{"name": "service", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM slos'
args = []
if service:
    sql += ' WHERE service=?'; args.append(service)
out = []
for r in conn.execute(sql + ' ORDER BY slo_id', args).fetchall():
    v = conn.execute("SELECT value FROM service_metrics WHERE service=? AND environment='production' AND metric=?", (r['service'], r['metric'])).fetchone()
    d = dict(r)
    d['current_value'] = v[0] if v else None
    d['breaching'] = (v is not None and v[0] > r['threshold'])
    out.append(d)
return out""",
          reads=["slos", "service_metrics"], writes=[], returns="list[dict]"))

    T(_mk("list_alerts", "List alarms, optionally filtered by status (firing|acknowledged|resolved) or service.",
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY alert_id', args).fetchall()]""",
          reads=["alerts"], writes=[], returns="list[dict]"))

    T(_mk("list_error_events",
          "Error-tracking issues (Sentry-style): grouped exceptions with culprit and event counts.",
          [{"name": "service", "type": "str", "default": None},
           {"name": "status", "type": "str", "default": None, "description": "unresolved|resolved"}],
          """\
sql = 'SELECT * FROM error_events'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if status:
    conds.append('status=?'); args.append(status)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY events DESC', args).fetchall()]""",
          reads=["error_events"], writes=[], returns="list[dict]"))

    T(_mk("search_logs", "Search application logs by substring, service, or level.",
          [{"name": "service", "type": "str", "default": None},
           {"name": "query", "type": "str", "default": ""},
           {"name": "level", "type": "str", "default": None},
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY log_id LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["logs"], writes=[], returns="list[dict]"))

    T(_mk("list_feature_flags", "List feature flags with per-environment state.",
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY key, environment', args).fetchall()]""",
          reads=["feature_flags"], writes=[], returns="list[dict]"))

    T(_mk("list_packages", "List package dependencies: version at repo HEAD and version deployed in production.",
          [{"name": "service", "type": "str", "default": None}],
          """\
sql = "SELECT service, key, value FROM repo_state WHERE kind='dependency'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
out = []
for r in conn.execute(sql + ' ORDER BY service, key', args).fetchall():
    p = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='dependency' AND key=?", (r['service'], r['key'])).fetchone()
    out.append({'service': r['service'], 'package': r['key'], 'repo_version': r['value'],
                'production_version': p[0] if p else None})
return out""",
          reads=["repo_state", "env_state"], writes=[], returns="list[dict]"))

    T(_mk("list_vulnerabilities", "List security-scanner findings.",
          [{"name": "status", "type": "str", "default": None},
           {"name": "service", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM vulnerabilities'
conds, args = [], []
if status:
    conds.append('status=?'); args.append(status)
if service:
    conds.append('service=?'); args.append(service)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY vuln_id', args).fetchall()]""",
          reads=["vulnerabilities"], writes=[], returns="list[dict]"))

    T(_mk("list_api_endpoints", "List API endpoints with repo status, production status, and production traffic share.",
          [{"name": "service", "type": "str", "default": None}],
          """\
sql = "SELECT service, key, value FROM repo_state WHERE kind='endpoint'"
args = []
if service:
    sql += ' AND service=?'; args.append(service)
out = []
for r in conn.execute(sql + ' ORDER BY service, key', args).fetchall():
    p = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='endpoint' AND key=?", (r['service'], r['key'])).fetchone()
    t = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (r['service'], r['key'])).fetchone()
    out.append({'service': r['service'], 'path': r['key'], 'repo_status': r['value'],
                'production_status': p[0] if p else None,
                'production_traffic_percent': int(t[0]) if t else None})
return out""",
          reads=["repo_state", "env_state"], writes=[], returns="list[dict]"))

    T(_mk("list_tests", "List the test catalog.",
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
return [dict(r) for r in conn.execute(sql + ' ORDER BY test_id', args).fetchall()]""",
          reads=["tests_catalog"], writes=[], returns="list[dict]"))

    T(_mk("list_incidents", "List incidents.",
          [{"name": "status", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM incidents'
args = []
if status:
    sql += ' WHERE status=?'; args.append(status)
return [dict(r) for r in conn.execute(sql + ' ORDER BY incident_id', args).fetchall()]""",
          reads=["incidents"], writes=[], returns="list[dict]"))

    T(_mk("get_status_page", "Read the public system-status page.",
          [{"name": "limit", "type": "int", "default": 10}],
          """\
return [dict(r) for r in conn.execute('SELECT * FROM status_page ORDER BY post_id DESC LIMIT ?', (int(limit),)).fetchall()]""",
          reads=["status_page"], writes=[], returns="list[dict]"))

    T(_mk("list_messages", "Read chat messages.",
          [{"name": "channel", "type": "str", "default": None},
           {"name": "limit", "type": "int", "default": 20}],
          """\
sql = 'SELECT * FROM messages'
args = []
if channel:
    sql += ' WHERE channel=?'; args.append(channel)
return [dict(r) for r in conn.execute(sql + ' ORDER BY message_id DESC LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["messages"], writes=[], returns="list[dict]"))

    # ================================================================ WRITES
    T(_mk("create_ticket", "Create a ticket. Returns the generated key.",
          [{"name": "title", "type": "str", "required": True},
           {"name": "description", "type": "str", "default": ""},
           {"name": "ticket_type", "type": "str", "default": "task",
            "choices": ("task", "bug", "feature", "security", "incident", "postmortem"),
            "description": "task|bug|feature|security|incident|postmortem"},
           {"name": "service", "type": "str", "default": ""},
           {"name": "priority", "type": "str", "default": "medium"}],
          """\
if ticket_type not in ('task', 'bug', 'feature', 'security', 'incident', 'postmortem'):
    return {'ok': False, 'error': 'invalid ticket_type: ' + str(ticket_type)}
if service and conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
cur = conn.execute('INSERT INTO tickets(key, type, title, description, status, priority, service) VALUES (?,?,?,?,?,?,?)',
                   ('', ticket_type, title, description, 'open', priority, service))
tid = cur.lastrowid
key = 'TKT-' + str(tid)
conn.execute('UPDATE tickets SET key=? WHERE ticket_id=?', (key, tid))
_audit(conn, 'create_ticket', service, {'key': key, 'type': ticket_type, 'title': title})
conn.commit()
return {'ok': True, 'key': key, 'ticket_id': tid, 'status': 'open'}""",
          reads=["services"], writes=["tickets", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("update_ticket", "Update a ticket's status and/or assignee.",
          [{"name": "key", "type": "str", "required": True},
           {"name": "status", "type": "str", "default": None,
            "choices": ("open", "in_progress", "in_review", "done"),
            "description": "open|in_progress|in_review|done"},
           {"name": "assignee", "type": "str", "default": None}],
          """\
row = conn.execute('SELECT * FROM tickets WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such ticket: ' + str(key)}
if status is None and assignee is None:
    return {'ok': False, 'error': 'provide status and/or assignee'}
if status is not None and status not in ('open', 'in_progress', 'in_review', 'done'):
    return {'ok': False, 'error': 'invalid status: ' + str(status)}
ns = row['status'] if status is None else status
na = row['assignee'] if assignee is None else assignee
conn.execute('UPDATE tickets SET status=?, assignee=? WHERE key=?', (ns, na, key))
_audit(conn, 'update_ticket', row['service'], {'key': key, 'status': ns})
conn.commit()
return {'ok': True, 'key': key, 'status': ns, 'assignee': na}""",
          reads=["tickets"], writes=["tickets", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("open_pull_request",
          "Open a pull request carrying structured changes. change_type is one of: "
          "config {key,value}; dependency {package,version}; endpoint {path,status: active|deprecated|retired}; "
          "module {name}; flag {key,description}; flag_cleanup {key}; test_fix {test_name, action: fix|quarantine}; "
          "migration {name}; code_edit {path, find, replace}. Changes apply at merge; deploys carry them to an environment.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "title", "type": "str", "required": True},
           {"name": "body", "type": "str", "default": ""},
           {"name": "ticket_key", "type": "str", "default": ""},
           {"name": "changes", "type": "list", "required": True,
            "description": "list of {change_type, payload}"}],
          """\
if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
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
    ct, pl = ch.get('change_type'), ch.get('payload')
    if isinstance(pl, str):
        try:
            pl = _json.loads(pl)
        except Exception:
            return {'ok': False, 'error': 'change payload must be an object'}
    if not isinstance(pl, dict):
        return {'ok': False, 'error': 'change payload must be an object'}
    if ct == 'config':
        if not pl.get('key') or 'value' not in pl:
            return {'ok': False, 'error': 'config change needs payload {key, value}'}
        pl = {'key': str(pl['key']), 'value': str(pl['value'])}
    elif ct == 'dependency':
        if not pl.get('package') or not pl.get('version'):
            return {'ok': False, 'error': 'dependency change needs payload {package, version}'}
        if conn.execute("SELECT 1 FROM repo_state WHERE service=? AND kind='dependency' AND key=?", (service, pl['package'])).fetchone() is None:
            return {'ok': False, 'error': service + ' has no dependency ' + str(pl['package'])}
        pl = {'package': str(pl['package']), 'version': str(pl['version'])}
    elif ct == 'endpoint':
        if not pl.get('path') or pl.get('status') not in ('active', 'deprecated', 'retired'):
            return {'ok': False, 'error': 'endpoint change needs payload {path, status: active|deprecated|retired}'}
        if conn.execute("SELECT 1 FROM repo_state WHERE service=? AND kind='endpoint' AND key=?", (service, pl['path'])).fetchone() is None:
            return {'ok': False, 'error': service + ' has no endpoint ' + str(pl['path'])}
        pl = {'path': str(pl['path']), 'status': str(pl['status'])}
    elif ct == 'module':
        if not pl.get('name'):
            return {'ok': False, 'error': 'module change needs payload {name}'}
        pl = {'name': str(pl['name'])}
    elif ct == 'flag':
        if not pl.get('key'):
            return {'ok': False, 'error': 'flag change needs payload {key, description}'}
        if conn.execute('SELECT 1 FROM feature_flags WHERE key=?', (pl['key'],)).fetchone() is not None:
            return {'ok': False, 'error': 'flag already exists: ' + str(pl['key'])}
        pl = {'key': str(pl['key']), 'description': str(pl.get('description', ''))}
    elif ct == 'flag_cleanup':
        if not pl.get('key'):
            return {'ok': False, 'error': 'flag_cleanup change needs payload {key}'}
        if conn.execute('SELECT 1 FROM feature_flags WHERE key=?', (pl['key'],)).fetchone() is None:
            return {'ok': False, 'error': 'no such flag: ' + str(pl['key'])}
        pl = {'key': str(pl['key'])}
    elif ct == 'test_fix':
        if not pl.get('test_name') or pl.get('action') not in ('fix', 'quarantine'):
            return {'ok': False, 'error': "test_fix change needs payload {test_name, action: fix|quarantine}"}
        if conn.execute('SELECT 1 FROM tests_catalog WHERE service=? AND name=?', (service, pl['test_name'])).fetchone() is None:
            return {'ok': False, 'error': service + ' has no test ' + str(pl['test_name'])}
        pl = {'test_name': str(pl['test_name']), 'action': str(pl['action'])}
    elif ct == 'migration':
        if not pl.get('name'):
            return {'ok': False, 'error': 'migration change needs payload {name}'}
        pl = {'name': str(pl['name'])}
    elif ct == 'code_edit':
        if not pl.get('path') or 'find' not in pl or 'replace' not in pl:
            return {'ok': False, 'error': 'code_edit change needs payload {path, find, replace}'}
        f = conn.execute('SELECT content, service FROM repo_files WHERE path=?', (pl['path'],)).fetchone()
        if f is None:
            return {'ok': False, 'error': 'no such file: ' + str(pl['path'])}
        if str(pl['find']) not in f['content']:
            return {'ok': False, 'error': 'find text not present in ' + str(pl['path'])}
        pl = {'path': str(pl['path']), 'find': str(pl['find']), 'replace': str(pl['replace'])}
    else:
        return {'ok': False, 'error': 'invalid change_type: ' + str(ct)}
    norm.append((ct, pl))
number = conn.execute('SELECT COALESCE(MAX(number), 9200) + 1 FROM pull_requests').fetchone()[0]
conn.execute('INSERT INTO pull_requests(number, service, title, body, author, ticket_key, status) VALUES (?,?,?,?,?,?,?)',
             (number, service, title, body, 'agent', ticket_key, 'open'))
for ct, pl in norm:
    conn.execute('INSERT INTO pr_changes(pr_number, change_type, payload) VALUES (?,?,?)', (number, ct, _json.dumps(pl)))
_audit(conn, 'open_pull_request', service, {'pr_number': number, 'ticket_key': ticket_key,
                                            'change_count': len(norm),
                                            'change_types': sorted(set(c[0] for c in norm))})
conn.commit()
return {'ok': True, 'pr_number': number, 'service': service, 'status': 'open',
        'next': 'run_ci(pr_number=' + str(number) + ') then merge_pull_request(pr_number=' + str(number) + ')'}""",
          reads=["services", "repo_state", "feature_flags", "tests_catalog", "pull_requests", "repo_files"],
          writes=["pull_requests", "pr_changes", "audit_events"], snippets=(AUDIT_SNIPPET,),
          extra_schema={"changes": {"items": {"type": "object",
                                              "properties": {"change_type": {"type": "string"},
                                                             "payload": {"type": "object"}},
                                              "required": ["change_type", "payload"]}}}))

    T(_mk("run_ci",
          "Run the CI pipeline for an open PR (pr_number) or a service's main branch (service). "
          "Stages run in order: build, unit, integration, regression. The tool succeeds even when "
          "the pipeline fails - inspect the returned status and stages.",
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
elif conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
changes = []
if pr_number is not None:
    changes = [(c['change_type'], _json.loads(c['payload'])) for c in
               conn.execute('SELECT change_type, payload FROM pr_changes WHERE pr_number=? ORDER BY change_id', (pr_number,)).fetchall()]
stages = []
# --- build: schema changes need their migration in the same PR
bstatus, bdetail = 'passed', 'compiled and packaged'
for ct, pl in changes:
    if ct != 'module':
        continue
    req = conn.execute('SELECT migration_name FROM migration_requirements WHERE service=? AND module=?', (service, pl['name'])).fetchone()
    if req is not None and not any(c[0] == 'migration' and c[1].get('name') == req[0] for c in changes):
        bstatus = 'failed'
        bdetail = 'missing database migration: module ' + pl['name'] + ' requires migration ' + req[0] + " (add a 'migration' change to this PR)"
        break
stages.append(('build', bstatus, bdetail))
# --- unit
if bstatus == 'passed':
    failing = [r['name'] for r in conn.execute("SELECT name FROM tests_catalog WHERE service=? AND suite='unit' AND status='failing' AND quarantined=0", (service,)).fetchall()]
    stages.append(('unit', 'failed' if failing else 'passed',
                   ('failing unit tests: ' + ', '.join(failing)) if failing else 'unit suite green'))
else:
    stages.append(('unit', 'skipped', 'build failed'))
# --- integration: contract checks + flaky suite
istatus, idetail = 'passed', 'integration suite green'
if stages[-1][1] != 'passed':
    istatus, idetail = 'skipped', 'upstream stage failed'
else:
    for ct, pl in changes:
        if ct == 'endpoint' and pl.get('status') == 'retired':
            t = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='traffic' AND key=?", (service, pl['path'])).fetchone()
            if t is not None and int(t[0]) > 0:
                istatus = 'failed'
                idetail = 'cannot retire ' + pl['path'] + ': still serving ' + str(t[0]) + '% of production traffic - drain it first'
                break
    if istatus == 'passed':
        flaky = [r['name'] for r in conn.execute("SELECT name FROM tests_catalog WHERE service=? AND suite='integration' AND status='flaky' AND quarantined=0", (service,)).fetchall()]
        if pr_number is not None:
            seen_red = conn.execute("SELECT COUNT(*) FROM ci_runs WHERE pr_number=? AND status='failed'", (pr_number,)).fetchone()[0]
            trips = bool(flaky) and seen_red == 0
        else:
            n_prior = conn.execute('SELECT COUNT(*) FROM ci_runs WHERE service=? AND pr_number IS NULL', (service,)).fetchone()[0]
            trips = bool(flaky) and n_prior % 2 == 0
        if trips:
            istatus, idetail = 'failed', 'intermittent failure: ' + ', '.join(flaky) + ' (rerun may pass)'
        else:
            failing = [r['name'] for r in conn.execute("SELECT name FROM tests_catalog WHERE service=? AND suite='integration' AND status='failing' AND quarantined=0", (service,)).fetchall()]
            if failing:
                istatus, idetail = 'failed', 'failing integration tests: ' + ', '.join(failing)
stages.append(('integration', istatus, idetail))
# --- regression: cross-service consumer contracts
rstatus, rdetail = 'passed', 'no regressions in dependent services'
if istatus != 'passed':
    rstatus, rdetail = 'skipped', 'upstream stage failed'
else:
    for ct, pl in changes:
        if ct != 'endpoint' or pl.get('status') != 'retired':
            continue
        for cr in conn.execute('SELECT * FROM contract_rules WHERE producer_service=? AND endpoint=?', (service, pl['path'])).fetchall():
            cv = conn.execute("SELECT value FROM env_state WHERE service=? AND environment='production' AND kind='config' AND key=?", (cr['consumer_service'], cr['consumer_key'])).fetchone()
            if cv is None or cv[0] != cr['consumer_required_value']:
                rstatus = 'failed'
                rdetail = cr['message']
                break
        if rstatus == 'failed':
            break
stages.append(('regression', rstatus, rdetail))
status = 'passed' if all(s[1] == 'passed' for s in stages) else 'failed'
detail = 'all stages passed' if status == 'passed' else next(s[2] for s in stages if s[1] == 'failed')
cur = conn.execute('INSERT INTO ci_runs(service, pr_number, status, detail) VALUES (?,?,?,?)', (service, pr_number, status, detail))
rid = cur.lastrowid
for st, sv, sd in stages:
    conn.execute('INSERT INTO ci_stages(run_id, stage, status, detail) VALUES (?,?,?,?)', (rid, st, sv, sd))
_audit(conn, 'run_ci', service, {'pr_number': pr_number, 'status': status,
                                 'stages': {s[0]: s[1] for s in stages}})
conn.commit()
return {'ok': True, 'run_id': rid, 'service': service, 'pr_number': pr_number, 'status': status,
        'detail': detail, 'stages': [{'stage': s[0], 'status': s[1], 'detail': s[2]} for s in stages]}""",
          reads=["pull_requests", "pr_changes", "tests_catalog", "env_state", "services",
                 "migration_requirements", "contract_rules", "ci_runs"],
          writes=["ci_runs", "ci_stages", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("merge_pull_request",
          "Merge an open PR. Blocked unless its latest CI run passed. Applies the PR's changes to "
          "repo HEAD (including code edits) and cuts a new deployable version.",
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
requires_migration = ''
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
    elif ct == 'flag_cleanup':
        conn.execute('DELETE FROM feature_flags WHERE key=?', (pl['key'],))
    elif ct == 'test_fix':
        if pl['action'] == 'fix':
            conn.execute("UPDATE tests_catalog SET status='passing', quarantined=0 WHERE service=? AND name=?", (service, pl['test_name']))
        else:
            conn.execute('UPDATE tests_catalog SET quarantined=1 WHERE service=? AND name=?', (service, pl['test_name']))
    elif ct == 'migration':
        requires_migration = pl['name']
        conn.execute('INSERT OR IGNORE INTO migrations(service, name, environment, status) VALUES (?,?,?,?)', (service, pl['name'], '', 'pending'))
    elif ct == 'code_edit':
        f = conn.execute('SELECT content FROM repo_files WHERE path=?', (pl['path'],)).fetchone()
        if f is not None and pl['find'] in f['content']:
            conn.execute('UPDATE repo_files SET content=? WHERE path=?', (f['content'].replace(pl['find'], pl['replace']), pl['path']))
old = conn.execute('SELECT repo_version FROM services WHERE name=?', (service,)).fetchone()[0]
parts = old.lstrip('v').split('.')
new_version = 'v' + parts[0] + '.' + parts[1] + '.' + str(int(parts[2]) + 1)
conn.execute('UPDATE services SET repo_version=? WHERE name=?', (new_version, service))
state = [[r['kind'], r['key'], r['value']] for r in conn.execute("SELECT kind, key, value FROM repo_state WHERE service=? AND kind IN ('config','dependency','endpoint','module') ORDER BY kind, key", (service,)).fetchall()]
conn.execute('INSERT INTO versions(service, version, state_json, requires_migration) VALUES (?,?,?,?)', (service, new_version, _json.dumps(state), requires_migration))
conn.execute("UPDATE pull_requests SET status='merged', merged_version=? WHERE number=?", (new_version, pr_number))
_audit(conn, 'merge_pull_request', service, {'pr_number': pr_number, 'version': new_version,
                                             'ticket_key': pr['ticket_key']})
conn.commit()
out = {'ok': True, 'pr_number': pr_number, 'service': service, 'merged_version': new_version,
       'next': 'deploy_service(service=..., environment="staging")'}
if requires_migration:
    out['requires_migration'] = requires_migration
    out['next'] = 'apply_migration then deploy_service'
return out""",
          reads=["pull_requests", "ci_runs", "pr_changes", "services", "repo_files"],
          writes=["repo_state", "feature_flags", "tests_catalog", "services", "versions",
                  "pull_requests", "migrations", "repo_files", "audit_events"],
          snippets=(AUDIT_SNIPPET,)))

    T(_mk("apply_migration",
          "Apply a database migration to an environment. Migrations are forward-only and must be "
          "applied before the code version that requires them is deployed there.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "name", "type": "str", "required": True},
           {"name": "environment", "type": "str", "required": True,
            "choices": ("staging", "production"), "description": "staging|production"}],
          """\
if environment not in ('staging', 'production'):
    return {'ok': False, 'error': "environment must be 'staging' or 'production'"}
known = conn.execute('SELECT 1 FROM migrations WHERE service=? AND name=?', (service, name)).fetchone()
declared = conn.execute('SELECT 1 FROM migration_requirements WHERE service=? AND migration_name=?', (service, name)).fetchone()
if known is None and declared is None:
    return {'ok': False, 'error': 'unknown migration ' + str(name) + ' for ' + str(service) + " (merge a PR carrying a 'migration' change first)"}
if conn.execute("SELECT 1 FROM migrations WHERE service=? AND name=? AND environment=? AND status='applied'", (service, name, environment)).fetchone():
    return {'ok': False, 'error': 'migration ' + str(name) + ' is already applied in ' + environment}
conn.execute("INSERT INTO migrations(service, name, environment, status) VALUES (?,?,?,'applied') ON CONFLICT(service, name, environment) DO UPDATE SET status='applied'", (service, name, environment))
_audit(conn, 'apply_migration', service, {'name': name, 'environment': environment})
conn.commit()
return {'ok': True, 'service': service, 'name': name, 'environment': environment, 'status': 'applied'}""",
          reads=["migrations", "migration_requirements"], writes=["migrations", "audit_events"],
          snippets=(AUDIT_SNIPPET,)))

    T(_mk("deploy_service",
          "Deploy a merged version to staging or production. canary_percent<100 stages a canary whose "
          "state only takes effect at promote_canary. Policy: production is staging-first; tier-1 services "
          "canary at <=25% then promote. A version whose migration is not applied is rejected.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "environment", "type": "str", "required": True,
            "choices": ("staging", "production")},
           {"name": "version", "type": "str", "default": None},
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
vrow = conn.execute('SELECT requires_migration FROM versions WHERE service=? AND version=?', (service, version)).fetchone()
if vrow is None:
    return {'ok': False, 'error': 'unknown version ' + str(version) + ' for ' + service + ' (only merged versions can be deployed)'}
if vrow[0]:
    ok_mig = conn.execute("SELECT 1 FROM migrations WHERE service=? AND name=? AND environment=? AND status='applied'", (service, vrow[0], environment)).fetchone()
    if ok_mig is None:
        return {'ok': False, 'error': 'deploy blocked: version ' + version + ' requires migration ' + vrow[0] + ' which is not applied in ' + environment + ' (run apply_migration first)'}
applied = canary_percent >= 100
status = 'succeeded' if applied else 'canary'
before = _breaching(conn, service) if environment == 'production' else []
cur = conn.execute('INSERT INTO deployments(service, environment, version, status, canary_percent) VALUES (?,?,?,?,?)',
                   (service, environment, version, status, canary_percent))
did = cur.lastrowid
new_alarms = []
if applied:
    _apply(conn, service, environment, version)
    _recompute(conn)
    if environment == 'production':
        new_alarms = [b for b in _breaching(conn, service) if b.split('=')[0] not in [x.split('=')[0] for x in before]]
_audit(conn, 'deploy_service', service, {'environment': environment, 'version': version,
                                         'canary_percent': canary_percent, 'applied': applied,
                                         'new_alarms': new_alarms})
conn.commit()
out = {'ok': True, 'deployment_id': did, 'service': service, 'environment': environment,
       'version': version, 'status': status, 'canary_percent': canary_percent, 'applied': applied}
if new_alarms:
    out['alarms_triggered'] = new_alarms
if not applied:
    out['next'] = 'assess_canary(service=...) then promote_canary(service=...)'
return out""",
          reads=["services", "versions", "migrations", "slos", "service_metrics"],
          writes=["deployments", "env_state", "service_metrics", "alerts", "vulnerabilities", "audit_events"],
          snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("assess_canary",
          "Evaluate the pending canary for a service: reports whether the canary version would breach "
          "any SLO or trip an alarm if promoted. Run this before promote_canary.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "environment", "type": "str", "default": "production"}],
          """\
d = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='canary' ORDER BY deployment_id DESC LIMIT 1", (service, environment)).fetchone()
if d is None:
    return {'ok': False, 'error': 'no pending canary for ' + str(service) + ' in ' + str(environment)}
baseline = _breaching(conn, service)
saved = [(r['kind'], r['key'], r['value']) for r in conn.execute("SELECT kind, key, value FROM env_state WHERE service=? AND environment='production'", (service,)).fetchall()]
_apply(conn, service, 'production', d['version'])
_recompute(conn)
canary = _breaching(conn, service)
conn.execute("DELETE FROM env_state WHERE service=? AND environment='production'", (service,))
for k, key, val in saved:
    conn.execute('INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)', (service, 'production', k, key, val))
_recompute(conn)
base_names = [x.split('=')[0] for x in baseline]
breaches = [b for b in canary if b.split('=')[0] not in base_names]
fixed = [b for b in baseline if b.split('=')[0] not in [x.split('=')[0] for x in canary]]
verdict = 'unhealthy' if breaches else 'healthy'
detail = ('canary introduces new SLO breaches: ' + '; '.join(breaches)) if breaches else (
    ('canary is healthy and clears: ' + '; '.join(fixed)) if fixed else
    'no new SLO breach detected in the canary population')
conn.execute('INSERT INTO canary_assessments(deployment_id, service, verdict, detail) VALUES (?,?,?,?)',
             (d['deployment_id'], service, verdict, detail))
_audit(conn, 'assess_canary', service, {'deployment_id': d['deployment_id'], 'version': d['version'],
                                        'verdict': verdict})
conn.commit()
return {'ok': True, 'service': service, 'environment': environment, 'deployment_id': d['deployment_id'],
        'version': d['version'], 'verdict': verdict, 'detail': detail,
        'next': 'promote_canary' if verdict == 'healthy' else 'do NOT promote - fix the regression or roll back'}""",
          reads=["deployments", "env_state", "versions", "slos", "service_metrics"],
          writes=["canary_assessments", "env_state", "service_metrics", "alerts",
                  "vulnerabilities", "audit_events"],
          snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("promote_canary", "Promote the pending canary to 100%; its state takes effect.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "environment", "type": "str", "default": "production"}],
          """\
d = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='canary' ORDER BY deployment_id DESC LIMIT 1", (service, environment)).fetchone()
if d is None:
    return {'ok': False, 'error': 'no canary deployment to promote for ' + str(service) + ' in ' + str(environment)}
before = _breaching(conn, service) if environment == 'production' else []
conn.execute("UPDATE deployments SET status='succeeded', canary_percent=100 WHERE deployment_id=?", (d['deployment_id'],))
_apply(conn, service, environment, d['version'])
_recompute(conn)
new_alarms = []
if environment == 'production':
    new_alarms = [b for b in _breaching(conn, service) if b.split('=')[0] not in [x.split('=')[0] for x in before]]
_audit(conn, 'promote_canary', service, {'environment': environment, 'version': d['version'],
                                         'deployment_id': d['deployment_id'], 'new_alarms': new_alarms})
conn.commit()
out = {'ok': True, 'deployment_id': d['deployment_id'], 'service': service, 'environment': environment,
       'version': d['version'], 'status': 'succeeded'}
if new_alarms:
    out['alarms_triggered'] = new_alarms
return out""",
          reads=["deployments"],
          writes=["deployments", "env_state", "service_metrics", "alerts", "vulnerabilities", "audit_events"],
          snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("rollback_deployment",
          "Emergency rollback to the previous successful deployment. Exempt from staging-first.",
          [{"name": "service", "type": "str", "required": True},
           {"name": "environment", "type": "str", "default": "production"}],
          """\
cur_d = conn.execute("SELECT * FROM deployments WHERE service=? AND environment=? AND status='succeeded' ORDER BY deployment_id DESC LIMIT 1", (service, environment)).fetchone()
if cur_d is None:
    return {'ok': False, 'error': 'no successful deployment to roll back for ' + str(service)}
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
          writes=["deployments", "env_state", "service_metrics", "alerts", "vulnerabilities", "audit_events"],
          snippets=(APPLY_SNIPPET, ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("set_feature_flag",
          "Toggle a feature flag or change its rollout percent in one environment. Runtime operation: "
          "takes effect immediately, no deploy needed.",
          [{"name": "key", "type": "str", "required": True},
           {"name": "environment", "type": "str", "required": True,
            "choices": ("staging", "production")},
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
ne = row['enabled']
if enabled is not None:
    ne = 1 if str(enabled).lower() in ('1', 'true', 'yes', 'on') else 0
nr = row['rollout_percent']
if rollout_percent is not None:
    nr = int(rollout_percent)
    if nr < 0 or nr > 100:
        return {'ok': False, 'error': 'rollout_percent must be between 0 and 100'}
conn.execute('UPDATE feature_flags SET enabled=?, rollout_percent=? WHERE key=? AND environment=?', (ne, nr, key, environment))
_recompute(conn)
_audit(conn, 'set_feature_flag', row['service'], {'key': key, 'environment': environment,
                                                  'enabled': ne, 'rollout_percent': nr})
conn.commit()
return {'ok': True, 'key': key, 'environment': environment, 'enabled': ne, 'rollout_percent': nr}""",
          reads=["feature_flags"],
          writes=["feature_flags", "service_metrics", "alerts", "vulnerabilities", "audit_events"],
          snippets=(ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("shift_endpoint_traffic",
          "Set the production traffic percent served by an endpoint (gateway runtime weight, no deploy "
          "needed). Policy: shift in stages of at most 50 points per step.",
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
conn.execute('UPDATE traffic_profile SET share_pct=? WHERE service=? AND route LIKE ?', (tp, service, '%' + path))
_audit(conn, 'shift_endpoint_traffic', service, {'path': path, 'from_percent': old, 'to_percent': tp})
conn.commit()
return {'ok': True, 'service': service, 'path': path, 'from_percent': old, 'to_percent': tp}""",
          reads=["env_state"], writes=["env_state", "traffic_profile", "audit_events"],
          snippets=(AUDIT_SNIPPET,)))

    T(_mk("acknowledge_alert", "Acknowledge a firing alarm.",
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
          reads=["alerts"], writes=["alerts", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("resolve_alert", "Resolve an alarm. Refused while the underlying metric still breaches its SLO.",
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
          reads=["alerts", "slos", "service_metrics"], writes=["alerts", "audit_events"],
          snippets=(AUDIT_SNIPPET,)))

    T(_mk("resolve_error_event",
          "Mark an error-tracking issue resolved. Refused while the owning service still breaches an SLO.",
          [{"name": "fingerprint", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT * FROM error_events WHERE fingerprint=?', (fingerprint,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such error issue: ' + str(fingerprint)}
if row['status'] == 'resolved':
    return {'ok': False, 'error': 'error issue ' + str(fingerprint) + ' is already resolved'}
bad = _breaching(conn, row['service'])
if bad:
    return {'ok': False, 'error': row['service'] + ' is still breaching: ' + '; '.join(bad)}
conn.execute("UPDATE error_events SET status='resolved' WHERE fingerprint=?", (fingerprint,))
_audit(conn, 'resolve_error_event', row['service'], {'fingerprint': fingerprint})
conn.commit()
return {'ok': True, 'fingerprint': fingerprint, 'status': 'resolved'}""",
          reads=["error_events", "slos", "service_metrics"], writes=["error_events", "audit_events"],
          snippets=(ENGINE_SNIPPET, AUDIT_SNIPPET)))

    T(_mk("create_incident", "Declare an incident.",
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
          reads=["services"], writes=["incidents", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("update_incident", "Update an incident's status (open|mitigated|resolved) and/or commander.",
          [{"name": "incident_id", "type": "int", "required": True},
           {"name": "status", "type": "str", "default": None,
            "choices": ("open", "mitigated", "resolved")},
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
ns = row['status'] if status is None else status
nc = row['commander'] if commander is None else commander
conn.execute('UPDATE incidents SET status=?, commander=? WHERE incident_id=?', (ns, nc, incident_id))
_audit(conn, 'update_incident', row['service'], {'incident_id': incident_id, 'status': ns})
conn.commit()
return {'ok': True, 'incident_id': incident_id, 'status': ns, 'commander': nc}""",
          reads=["incidents"], writes=["incidents", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("publish_status_update",
          "Publish an update to the public system-status page (state: investigating|identified|monitoring|resolved).",
          [{"name": "state", "type": "str", "required": True,
            "choices": ("investigating", "identified", "monitoring", "resolved")},
           {"name": "title", "type": "str", "required": True},
           {"name": "body", "type": "str", "default": ""}],
          """\
if state not in ('investigating', 'identified', 'monitoring', 'resolved'):
    return {'ok': False, 'error': 'state must be investigating|identified|monitoring|resolved'}
cur = conn.execute('INSERT INTO status_page(state, title, body) VALUES (?,?,?)', (state, title, body))
_audit(conn, 'publish_status_update', '', {'post_id': cur.lastrowid, 'state': state, 'title': title})
conn.commit()
return {'ok': True, 'post_id': cur.lastrowid, 'state': state}""",
          reads=[], writes=["status_page", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("submit_diagnosis",
          "Submit a diagnostic finding for an investigation. `scope` is what you were asked to "
          "investigate (a service name or alarm id). Set fault_detected=false with "
          "fault_type='none' when the scope is healthy. fault_type is one of: misconfig, "
          "missing_retry, missing_timeout, resource_exhaustion, unbounded_prefetch, "
          "cache_disabled, n_plus_one_query, cdn_bypass, bad_release, feature_flag_regression, "
          "none. offending_key is the specific config key, flag key or version responsible.",
          [{"name": "scope", "type": "str", "required": True,
            "description": "the service or alarm id you were asked to investigate"},
           {"name": "fault_detected", "type": "bool", "required": True},
           {"name": "service", "type": "str", "default": "",
            "description": "the service responsible (localization)"},
           {"name": "fault_type", "type": "str", "default": "none",
            "choices": ('misconfig', 'missing_retry', 'missing_timeout', 'resource_exhaustion', 'unbounded_prefetch', 'cache_disabled', 'n_plus_one_query', 'cdn_bypass', 'bad_release', 'feature_flag_regression', 'none')},
           {"name": "offending_key", "type": "str", "default": "",
            "description": "config key, flag key or version at fault"},
           {"name": "evidence", "type": "str", "default": "",
            "description": "what you observed that supports this finding"}],
          """\
kinds = ('misconfig', 'missing_retry', 'missing_timeout', 'resource_exhaustion',
         'unbounded_prefetch', 'cache_disabled', 'n_plus_one_query', 'cdn_bypass',
         'bad_release', 'feature_flag_regression', 'none')
if fault_type not in kinds:
    return {'ok': False, 'error': 'fault_type must be one of: ' + ', '.join(kinds)}
_t, _f = ('1', 'true', 'yes', 'on'), ('0', 'false', 'no', 'off')
_v = str(fault_detected).lower()
if _v not in _t + _f:
    return {'ok': False, 'error': 'fault_detected must be true or false, not ' + repr(fault_detected)}
det = 1 if _v in _t else 0
if service and conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
    return {'ok': False, 'error': 'unknown service: ' + str(service)}
if det and fault_type == 'none':
    return {'ok': False, 'error': "fault_detected=true requires a specific fault_type"}
if not det and fault_type != 'none':
    return {'ok': False, 'error': "fault_detected=false requires fault_type='none'"}
cur = conn.execute('INSERT INTO diagnoses(scope, fault_detected, service, fault_type, offending_key, evidence) VALUES (?,?,?,?,?,?)',
                   (str(scope), det, service or '', fault_type, offending_key or '', evidence or ''))
_audit(conn, 'submit_diagnosis', service or '', {'scope': str(scope), 'fault_detected': det,
                                                 'fault_type': fault_type,
                                                 'offending_key': offending_key or ''})
conn.commit()
return {'ok': True, 'diagnosis_id': cur.lastrowid, 'scope': str(scope),
        'fault_detected': bool(det), 'service': service or '', 'fault_type': fault_type,
        'offending_key': offending_key or ''}""",
          reads=["services"], writes=["diagnoses", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    T(_mk("post_message", "Post a message to a chat channel.",
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
          reads=["channels"], writes=["messages", "audit_events"], snippets=(AUDIT_SNIPPET,)))

    return tools


if __name__ == "__main__":
    ts = make_tools()
    print(len(ts), "tools")
    for t in ts:
        compile(t["source_code"], t["name"], "exec")
    print("all sources compile")
