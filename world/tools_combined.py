def list_services(db_path=None):
    """List all services with team, tier, on-call engineer, repo HEAD version and deployed versions per environment."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        out = []
        for s in conn.execute('SELECT * FROM services ORDER BY service_id').fetchall():
            d = dict(s)
            oc = conn.execute('SELECT engineer FROM oncall WHERE team=?', (s['team'],)).fetchone()
            d['oncall_engineer'] = oc[0] if oc else ''
            for _env in ('staging', 'production'):
                v = conn.execute("SELECT value FROM env_state WHERE service=? AND environment=? AND kind='version' AND key='current'", (s['name'], _env)).fetchone()
                d[_env + '_version'] = v[0] if v else ''
            out.append(d)
        return out
    finally:
        conn.close()


def list_tickets(db_path=None, status=None, service=None, ticket_type=None):
    """List tickets, optionally filtered by status, service, or ticket type."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_ticket(db_path=None, key=None):
    """Fetch a single ticket by its key (e.g. ENG-2101)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if key is None:
            return {'ok': False, 'error': 'missing required parameter: key'}
        row = conn.execute('SELECT * FROM tickets WHERE key=?', (key,)).fetchone()
        if row is None:
            return {'ok': False, 'error': 'no such ticket: ' + str(key)}
        return dict(row)
    finally:
        conn.close()


def list_pull_requests(db_path=None, service=None, status=None):
    """List pull requests, optionally filtered by service or status (open|merged|closed)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM pull_requests'
        conds, args = [], []
        if service:
            conds.append('service=?'); args.append(service)
        if status:
            conds.append('status=?'); args.append(status)
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY number'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_pull_request(db_path=None, pr_number=None):
    """Fetch a pull request with its structured changes and CI run history."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if pr_number is None:
            return {'ok': False, 'error': 'missing required parameter: pr_number'}
        row = conn.execute('SELECT * FROM pull_requests WHERE number=?', (int(pr_number),)).fetchone()
        if row is None:
            return {'ok': False, 'error': 'no such pull request: ' + str(pr_number)}
        d = dict(row)
        d['changes'] = [{'change_type': c['change_type'], 'payload': _json.loads(c['payload'])}
                        for c in conn.execute('SELECT change_type, payload FROM pr_changes WHERE pr_number=? ORDER BY change_id', (int(pr_number),)).fetchall()]
        d['ci_runs'] = [dict(c) for c in conn.execute('SELECT * FROM ci_runs WHERE pr_number=? ORDER BY run_id', (int(pr_number),)).fetchall()]
        return d
    finally:
        conn.close()


def list_ci_runs(db_path=None, service=None, pr_number=None, limit=20):
    """List CI runs (most recent first), optionally filtered by service or PR number."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_deployments(db_path=None, service=None, environment=None, limit=20):
    """List deployments (most recent first), optionally filtered by service or environment."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def query_metrics(db_path=None, service=None, metric=None):
    """Read current production service metrics (recomputed after every deploy/flag change)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = "SELECT * FROM service_metrics WHERE environment='production'"
        args = []
        if service:
            sql += ' AND service=?'; args.append(service)
        if metric:
            sql += ' AND metric=?'; args.append(metric)
        sql += ' ORDER BY service, metric'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def get_slo_status(db_path=None, service=None):
    """List SLOs with current metric values and whether each is breaching."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return out
    finally:
        conn.close()


def list_alerts(db_path=None, status=None, service=None):
    """List alerts, optionally filtered by status (firing|acknowledged|resolved) or service."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM alerts'
        conds, args = [], []
        if status:
            conds.append('status=?'); args.append(status)
        if service:
            conds.append('service=?'); args.append(service)
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY alert_id'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def search_logs(db_path=None, service=None, query='', level=None, limit=20):
    """Search production/staging log lines by substring, optionally filtered by service or level."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def search_runbooks(db_path=None, query=''):
    """Search the knowledge base of runbooks by substring in title or body."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM runbooks'
        args = []
        if query:
            sql += ' WHERE title LIKE ? OR body LIKE ?'
            args = ['%' + str(query) + '%', '%' + str(query) + '%']
        sql += ' ORDER BY runbook_id'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_feature_flags(db_path=None, service=None, environment=None):
    """List feature flags with per-environment enabled state and rollout percent."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM feature_flags'
        conds, args = [], []
        if service:
            conds.append('service=?'); args.append(service)
        if environment:
            conds.append('environment=?'); args.append(environment)
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY key, environment'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_dependencies(db_path=None, service=None):
    """List package dependencies per service: version at repo HEAD and version deployed in production."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return out
    finally:
        conn.close()


def list_vulnerabilities(db_path=None, status=None):
    """List security scanner findings, optionally filtered by status (open|remediated)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM vulnerabilities'
        args = []
        if status:
            sql += ' WHERE status=?'; args.append(status)
        sql += ' ORDER BY vuln_id'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_api_endpoints(db_path=None, service=None):
    """List API endpoints per service with repo HEAD status, production status, and production traffic percent."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
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
        return out
    finally:
        conn.close()


def list_tests(db_path=None, service=None, status=None):
    """List the test catalog, optionally filtered by service or status (passing|flaky|failing)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM tests_catalog'
        conds, args = [], []
        if service:
            conds.append('service=?'); args.append(service)
        if status:
            conds.append('status=?'); args.append(status)
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY test_id'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_incidents(db_path=None, status=None):
    """List incidents, optionally filtered by status (open|mitigated|resolved)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM incidents'
        args = []
        if status:
            sql += ' WHERE status=?'; args.append(status)
        sql += ' ORDER BY incident_id'
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_messages(db_path=None, channel=None, limit=20):
    """Read chat messages (most recent first), optionally scoped to one channel."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        sql = 'SELECT * FROM messages'
        args = []
        if channel:
            sql += ' WHERE channel=?'; args.append(channel)
        sql += ' ORDER BY message_id DESC LIMIT ?'
        args.append(int(limit))
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def create_ticket(db_path=None, title=None, description='', ticket_type='task', service='', priority='medium'):
    """Create a new ticket. Returns the generated ticket key."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if title is None:
            return {'ok': False, 'error': 'missing required parameter: title'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return {'ok': True, 'key': key, 'ticket_id': tid, 'status': 'open'}
    finally:
        conn.close()


def update_ticket(db_path=None, key=None, status=None, assignee=None):
    """Update a ticket's status and/or assignee."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if key is None:
            return {'ok': False, 'error': 'missing required parameter: key'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return {'ok': True, 'key': key, 'status': new_status, 'assignee': new_assignee}
    finally:
        conn.close()


def open_pull_request(db_path=None, service=None, title=None, body='', ticket_key='', changes=None):
    """Open a pull request carrying structured changes. Change types: config {key,value}, dependency {package,version}, endpoint {path,status: active|deprecated|retired}, module {name}, flag {key,description}, test_fix {test_name, action: fix|quarantine}. Changes take effect at merge; deploys copy them to an environment."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        if title is None:
            return {'ok': False, 'error': 'missing required parameter: title'}
        if changes is None:
            return {'ok': False, 'error': 'missing required parameter: changes'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'next': 'run_ci(pr_number=' + str(number) + ') then merge_pull_request(pr_number=' + str(number) + ')'}
    finally:
        conn.close()


def run_ci(db_path=None, pr_number=None, service=None):
    """Run the CI pipeline for an open PR (pr_number) or for a service's main branch (service). The tool succeeds even when the pipeline fails; check the returned status."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'status': status, 'detail': detail}
    finally:
        conn.close()


def merge_pull_request(db_path=None, pr_number=None):
    """Merge an open PR. Blocked unless the PR's latest CI run passed. Applies the PR's changes to the service's repo HEAD and cuts a new deployable version."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if pr_number is None:
            return {'ok': False, 'error': 'missing required parameter: pr_number'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'next': 'deploy_service(service=..., environment=...)'}
    finally:
        conn.close()


def deploy_service(db_path=None, service=None, environment=None, version=None, canary_percent=100):
    """Deploy a merged version to staging or production. canary_percent<100 stages a canary (state applies only after promote_canary). Policy: production deploys are staging-first; tier-1 services canary at <=25% then promote."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        if environment is None:
            return {'ok': False, 'error': 'missing required parameter: environment'}
        def _apply(conn, _svc, _env, _version):
            _row = conn.execute('SELECT state_json FROM versions WHERE service=? AND version=?', (_svc, _version)).fetchone()
            if _row is None:
                return False
            conn.execute("DELETE FROM env_state WHERE service=? AND environment=? AND kind IN ('config','dependency','endpoint','module')", (_svc, _env))
            for _k, _key, _val in _json.loads(_row[0]):
                conn.execute('INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)', (_svc, _env, _k, _key, _val))
            conn.execute("INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,'version','current',?) ON CONFLICT(service, environment, kind, key) DO UPDATE SET value=excluded.value", (_svc, _env, _version))
            return True
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
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return out
    finally:
        conn.close()


def promote_canary(db_path=None, service=None, environment='production'):
    """Promote the latest canary deployment of a service to 100%; its state takes effect."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        def _apply(conn, _svc, _env, _version):
            _row = conn.execute('SELECT state_json FROM versions WHERE service=? AND version=?', (_svc, _version)).fetchone()
            if _row is None:
                return False
            conn.execute("DELETE FROM env_state WHERE service=? AND environment=? AND kind IN ('config','dependency','endpoint','module')", (_svc, _env))
            for _k, _key, _val in _json.loads(_row[0]):
                conn.execute('INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)', (_svc, _env, _k, _key, _val))
            conn.execute("INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,'version','current',?) ON CONFLICT(service, environment, kind, key) DO UPDATE SET value=excluded.value", (_svc, _env, _version))
            return True
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
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'environment': environment, 'version': d['version'], 'status': 'succeeded'}
    finally:
        conn.close()


def rollback_deployment(db_path=None, service=None, environment='production'):
    """Emergency rollback: revert a service in an environment to its previous successful deployment. Exempt from the staging-first rule."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        def _apply(conn, _svc, _env, _version):
            _row = conn.execute('SELECT state_json FROM versions WHERE service=? AND version=?', (_svc, _version)).fetchone()
            if _row is None:
                return False
            conn.execute("DELETE FROM env_state WHERE service=? AND environment=? AND kind IN ('config','dependency','endpoint','module')", (_svc, _env))
            for _k, _key, _val in _json.loads(_row[0]):
                conn.execute('INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,?,?,?)', (_svc, _env, _k, _key, _val))
            conn.execute("INSERT INTO env_state(service, environment, kind, key, value) VALUES (?,?,'version','current',?) ON CONFLICT(service, environment, kind, key) DO UPDATE SET value=excluded.value", (_svc, _env, _version))
            return True
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
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'from_version': cur_d['version'], 'to_version': prev['version']}
    finally:
        conn.close()


def set_feature_flag(db_path=None, key=None, environment=None, enabled=None, rollout_percent=None):
    """Toggle a feature flag or change its rollout percent in one environment. Runtime operation: takes effect immediately, no deploy needed. The flag must already be defined (flags are defined via a 'flag' PR change)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if key is None:
            return {'ok': False, 'error': 'missing required parameter: key'}
        if environment is None:
            return {'ok': False, 'error': 'missing required parameter: environment'}
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
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
                'enabled': new_enabled, 'rollout_percent': new_rollout}
    finally:
        conn.close()


def shift_endpoint_traffic(db_path=None, service=None, path=None, traffic_percent=None):
    """Set the production traffic percent served by an endpoint (gateway runtime weight; no deploy needed). Policy: shift in stages of at most 50 points per step."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        if path is None:
            return {'ok': False, 'error': 'missing required parameter: path'}
        if traffic_percent is None:
            return {'ok': False, 'error': 'missing required parameter: traffic_percent'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return {'ok': True, 'service': service, 'path': path, 'from_percent': old, 'to_percent': tp}
    finally:
        conn.close()


def acknowledge_alert(db_path=None, alert_id=None):
    """Acknowledge a firing alert (marks it acknowledged; it stays active until resolved)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if alert_id is None:
            return {'ok': False, 'error': 'missing required parameter: alert_id'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
        alert_id = int(alert_id)
        row = conn.execute('SELECT * FROM alerts WHERE alert_id=?', (alert_id,)).fetchone()
        if row is None:
            return {'ok': False, 'error': 'no such alert: ' + str(alert_id)}
        if row['status'] == 'resolved':
            return {'ok': False, 'error': 'alert ' + str(alert_id) + ' is already resolved'}
        conn.execute("UPDATE alerts SET status='acknowledged' WHERE alert_id=?", (alert_id,))
        _audit(conn, 'acknowledge_alert', row['service'], {'alert_id': alert_id})
        conn.commit()
        return {'ok': True, 'alert_id': alert_id, 'status': 'acknowledged'}
    finally:
        conn.close()


def resolve_alert(db_path=None, alert_id=None):
    """Resolve an alert. Refused while the underlying metric still breaches its SLO — fix and deploy first."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if alert_id is None:
            return {'ok': False, 'error': 'missing required parameter: alert_id'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return {'ok': True, 'alert_id': alert_id, 'status': 'resolved'}
    finally:
        conn.close()


def create_incident(db_path=None, title=None, service=None, severity=None):
    """Declare a new incident."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if title is None:
            return {'ok': False, 'error': 'missing required parameter: title'}
        if service is None:
            return {'ok': False, 'error': 'missing required parameter: service'}
        if severity is None:
            return {'ok': False, 'error': 'missing required parameter: severity'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
        if severity not in ('sev1', 'sev2', 'sev3'):
            return {'ok': False, 'error': 'severity must be sev1|sev2|sev3'}
        if conn.execute('SELECT 1 FROM services WHERE name=?', (service,)).fetchone() is None:
            return {'ok': False, 'error': 'unknown service: ' + str(service)}
        cur = conn.execute('INSERT INTO incidents(severity, title, service, status) VALUES (?,?,?,?)',
                           (severity, title, service, 'open'))
        _audit(conn, 'create_incident', service, {'incident_id': cur.lastrowid, 'severity': severity})
        conn.commit()
        return {'ok': True, 'incident_id': cur.lastrowid, 'status': 'open'}
    finally:
        conn.close()


def update_incident(db_path=None, incident_id=None, status=None, commander=None):
    """Update an incident's status (open|mitigated|resolved) and/or commander."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if incident_id is None:
            return {'ok': False, 'error': 'missing required parameter: incident_id'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
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
        return {'ok': True, 'incident_id': incident_id, 'status': new_status, 'commander': new_commander}
    finally:
        conn.close()


def post_message(db_path=None, channel=None, body=None):
    """Post a message to a chat channel (#incidents, #security, or #eng)."""
    import sqlite3 as _sq
    import json as _json
    if db_path:
        conn = _sq.connect(db_path)
    else:
        conn = get_db()
    conn.row_factory = _sq.Row
    try:
        if channel is None:
            return {'ok': False, 'error': 'missing required parameter: channel'}
        if body is None:
            return {'ok': False, 'error': 'missing required parameter: body'}
        def _audit(conn, _tool, _svc, _detail):
            conn.execute('INSERT INTO audit_events(tool, service, detail) VALUES (?,?,?)', (_tool, _svc, _json.dumps(_detail)))
        if conn.execute('SELECT 1 FROM channels WHERE channel=?', (channel,)).fetchone() is None:
            rows = [r[0] for r in conn.execute('SELECT channel FROM channels ORDER BY channel').fetchall()]
            return {'ok': False, 'error': 'unknown channel ' + str(channel) + '; valid: ' + ', '.join(rows)}
        if not str(body).strip():
            return {'ok': False, 'error': 'body must not be empty'}
        cur = conn.execute('INSERT INTO messages(channel, author, body) VALUES (?,?,?)', (channel, 'agent', str(body)))
        _audit(conn, 'post_message', '', {'channel': channel, 'message_id': cur.lastrowid})
        conn.commit()
        return {'ok': True, 'message_id': cur.lastrowid, 'channel': channel}
    finally:
        conn.close()
