"""Vendor-shaped MCP tool surfaces over the chaotic multi-system data.

Tool names and argument shapes mirror the real servers documented in
research/notes/mcp/ (jira_search, list_oncalls, query_prometheus,
search_issues, confluence_search, list_status_page_posts ...), so an agent that
has used the real thing is not surprised here.

The point of these tools is that no single one answers a question that matters.
"How many customer-facing incidents last week" needs PagerDuty incidents joined
to status-page posts across a week boundary whose definition differs per system.
"""

from tools_src import _mk, CONN_PREAMBLE, AUDIT_SNIPPET  # noqa: F401


def make_vendor_tools():
    tools = []
    T = tools.append

    # ------------------------------------------------------------- trackers
    T(_mk("jira_search",
          "Search Jira issues. Jira status is a per-project workflow, not open/closed: "
          "a resolved issue has status='Done' AND a resolution set. Filter by project, "
          "status, issue_type, component or priority.",
          [{"name": "project", "type": "str", "default": None},
           {"name": "status", "type": "str", "default": None},
           {"name": "issue_type", "type": "str", "default": None},
           {"name": "component", "type": "str", "default": None},
           {"name": "limit", "type": "int", "default": 50}],
          """\
sql = 'SELECT * FROM jira_issues'
conds, args = [], []
for col, val in (('project', project), ('status', status), ('issue_type', issue_type),
                 ('component', component)):
    if val:
        conds.append(col + '=?'); args.append(val)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY key LIMIT ?', args + [int(limit)]).fetchall()]""",
          reads=["jira_issues"], writes=[], returns="list[dict]"))

    T(_mk("jira_get_issue",
          "Fetch one Jira issue by key, including any links to issues in other trackers.",
          [{"name": "key", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT * FROM jira_issues WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such issue: ' + str(key)}
d = dict(row)
d['links'] = [dict(r) for r in conn.execute(
    'SELECT target, kind FROM issue_links WHERE source=?', (key,)).fetchall()]
return d""",
          reads=["jira_issues", "issue_links"], writes=[]))

    T(_mk("linear_list_issues",
          "List Linear issues. Linear priority is numeric: 0=none, 1=urgent, 2=high, "
          "3=normal, 4=low - it does not map cleanly onto Jira priority names.",
          [{"name": "team", "type": "str", "default": None},
           {"name": "state", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM linear_issues'
conds, args = [], []
if team:
    conds.append('team=?'); args.append(team)
if state:
    conds.append('state=?'); args.append(state)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY identifier', args).fetchall()]""",
          reads=["linear_issues"], writes=[], returns="list[dict]"))

    T(_mk("github_list_issues",
          "List GitHub issues. GitHub has only state=open|closed; severity lives in "
          "labels if anywhere.",
          [{"name": "repo", "type": "str", "default": None},
           {"name": "state", "type": "str", "default": None},
           {"name": "label", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM github_issues'
conds, args = [], []
if repo:
    conds.append('repo=?'); args.append(repo)
if state:
    conds.append('state=?'); args.append(state)
if label:
    conds.append('labels LIKE ?'); args.append('%' + str(label) + '%')
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY number', args).fetchall()]""",
          reads=["github_issues"], writes=[], returns="list[dict]"))

    T(_mk("list_issue_links",
          "List known cross-tracker links (duplicates/relates/implements). This is the "
          "only place the trackers are reconciled; neither tracker knows about it.",
          [{"name": "source", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM issue_links'
args = []
if source:
    sql += ' WHERE source=? OR target=?'; args = [source, source]
return [dict(r) for r in conn.execute(sql, args).fetchall()]""",
          reads=["issue_links"], writes=[], returns="list[dict]"))

    # -------------------------------------------------------- observability
    T(_mk("query_prometheus",
          "Query a Prometheus series by metric and label selectors. Note the label "
          "spelling is Prometheus's own (e.g. checkout_service), and counter resets are "
          "flagged: a rate() over a reset under-reports.",
          [{"name": "metric", "type": "str", "required": True},
           {"name": "label_service", "type": "str", "default": None},
           {"name": "label_env", "type": "str", "default": None},
           {"name": "day_from", "type": "int", "default": None},
           {"name": "day_to", "type": "int", "default": None}],
          """\
sql = 'SELECT * FROM prom_series WHERE metric=?'
args = [metric]
if label_service:
    sql += ' AND label_service=?'; args.append(label_service)
if label_env:
    sql += ' AND label_env=?'; args.append(label_env)
if day_from is not None:
    sql += ' AND day >= ?'; args.append(int(day_from))
if day_to is not None:
    sql += ' AND day <= ?'; args.append(int(day_to))
return [dict(r) for r in conn.execute(sql + ' ORDER BY day', args).fetchall()]""",
          reads=["prom_series"], writes=[], returns="list[dict]"))

    T(_mk("list_prometheus_label_values",
          "List the values a Prometheus label actually takes. Use this when you are not "
          "sure how a service is spelled in metrics.",
          [{"name": "label", "type": "str", "default": "label_service"}],
          """\
col = 'label_service' if str(label).endswith('service') else 'label_env'
return [r[0] for r in conn.execute(
    'SELECT DISTINCT ' + col + ' FROM prom_series ORDER BY 1').fetchall()]""",
          reads=["prom_series"], writes=[], returns="list[str]"))

    T(_mk("sentry_search_issues",
          "Search Sentry issues (grouped exceptions). Event counts are SAMPLED at the "
          "project's sample_rate - see sentry_list_projects - so they are a fraction of "
          "the true volume and are not comparable to Prometheus counters.",
          [{"name": "project_slug", "type": "str", "default": None},
           {"name": "status", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM sentry_issues'
conds, args = [], []
if project_slug:
    conds.append('project_slug=?'); args.append(project_slug)
if status:
    conds.append('status=?'); args.append(status)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY events DESC', args).fetchall()]""",
          reads=["sentry_issues"], writes=[], returns="list[dict]"))

    T(_mk("sentry_list_projects",
          "List Sentry projects with their event sample rates.",
          [],
          """\
return [dict(r) for r in conn.execute('SELECT * FROM sentry_projects ORDER BY slug').fetchall()]""",
          reads=["sentry_projects"], writes=[], returns="list[dict]"))

    # ------------------------------------------------------------ pagerduty
    T(_mk("pd_list_incidents",
          "List PagerDuty incidents in a day range. urgency (high|low) and priority "
          "(P1..P4) are separate vocabularies; neither records whether customers saw it.",
          [{"name": "since_day", "type": "int", "default": None},
           {"name": "until_day", "type": "int", "default": None},
           {"name": "urgency", "type": "str", "default": None},
           {"name": "status", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM pd_incidents'
conds, args = [], []
if since_day is not None:
    conds.append('created_day >= ?'); args.append(int(since_day))
if until_day is not None:
    conds.append('created_day <= ?'); args.append(int(until_day))
if urgency:
    conds.append('urgency=?'); args.append(urgency)
if status:
    conds.append('status=?'); args.append(status)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY incident_number', args).fetchall()]""",
          reads=["pd_incidents"], writes=[], returns="list[dict]"))

    T(_mk("pd_list_services", "List PagerDuty technical services and escalation policies.",
          [],
          """\
return [dict(r) for r in conn.execute('SELECT * FROM pd_services ORDER BY pd_service_id').fetchall()]""",
          reads=["pd_services"], writes=[], returns="list[dict]"))

    T(_mk("pd_list_oncalls", "Who is on call, by day and escalation policy.",
          [{"name": "day", "type": "int", "default": None},
           {"name": "escalation_policy", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM pd_oncall'
conds, args = [], []
if day is not None:
    conds.append('day=?'); args.append(int(day))
if escalation_policy:
    conds.append('escalation_policy=?'); args.append(escalation_policy)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY schedule_id', args).fetchall()]""",
          reads=["pd_oncall"], writes=[], returns="list[dict]"))

    T(_mk("pd_list_change_events",
          "Change events recorded against a PagerDuty service. These exist only where "
          "someone wired the integration.",
          [{"name": "pd_service_id", "type": "str", "default": None},
           {"name": "since_day", "type": "int", "default": None}],
          """\
sql = 'SELECT * FROM pd_change_events'
conds, args = [], []
if pd_service_id:
    conds.append('pd_service_id=?'); args.append(pd_service_id)
if since_day is not None:
    conds.append('day >= ?'); args.append(int(since_day))
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY day', args).fetchall()]""",
          reads=["pd_change_events"], writes=[], returns="list[dict]"))

    T(_mk("list_status_page_posts",
          "Public status-page posts. This is the ONLY system that records customer "
          "impact; incidents do not carry it. The status page also lags internal state.",
          [{"name": "since_day", "type": "int", "default": None},
           {"name": "impact", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM status_page_posts'
conds, args = [], []
if since_day is not None:
    conds.append('published_day >= ?'); args.append(int(since_day))
if impact:
    conds.append('impact=?'); args.append(impact)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY post_id', args).fetchall()]""",
          reads=["status_page_posts"], writes=[], returns="list[dict]"))

    # ------------------------------------------------------- knowledge / ops
    T(_mk("confluence_search",
          "Search the Confluence wiki. Pages carry a last_updated_day; some are stale.",
          [{"name": "query", "type": "str", "default": ""},
           {"name": "space", "type": "str", "default": None}],
          """\
sql = 'SELECT page_id, space, title, last_updated_day, stale FROM confluence_pages'
conds, args = [], []
if query:
    conds.append('(title LIKE ? OR body LIKE ?)'); args += ['%' + str(query) + '%'] * 2
if space:
    conds.append('space=?'); args.append(space)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY page_id', args).fetchall()]""",
          reads=["confluence_pages"], writes=[], returns="list[dict]"))

    T(_mk("confluence_get_page", "Read one Confluence page in full.",
          [{"name": "page_id", "type": "int", "required": True}],
          """\
row = conn.execute('SELECT * FROM confluence_pages WHERE page_id=?', (int(page_id),)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such page: ' + str(page_id)}
return dict(row)""",
          reads=["confluence_pages"], writes=[]))

    T(_mk("read_owner_spreadsheet",
          "Read the hand-maintained service-owner spreadsheet. Note last_reviewed_day: "
          "rows drift as teams reorganise, and the sheet uses its own week convention.",
          [],
          """\
return [dict(r) for r in conn.execute('SELECT * FROM owner_spreadsheet ORDER BY row_id').fetchall()]""",
          reads=["owner_spreadsheet"], writes=[], returns="list[dict]"))

    T(_mk("query_local_deploy_log",
          "Query a team's local deploy log (a SQLite file kept because the central one "
          "is slow). Environment strings are free text and include 'nonprod-*' spellings; "
          "rollbacks are flagged separately.",
          [{"name": "service", "type": "str", "default": None},
           {"name": "environment", "type": "str", "default": None},
           {"name": "since_day", "type": "int", "default": None},
           {"name": "include_rollbacks", "type": "bool", "default": True}],
          """\
sql = 'SELECT * FROM local_deploy_log'
conds, args = [], []
if service:
    conds.append('service=?'); args.append(service)
if environment:
    conds.append('environment=?'); args.append(environment)
if since_day is not None:
    conds.append('day >= ?'); args.append(int(since_day))
if str(include_rollbacks).lower() in ('0', 'false', 'no'):
    conds.append('was_rollback=0')
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY day', args).fetchall()]""",
          reads=["local_deploy_log"], writes=[], returns="list[dict]"))

    T(_mk("resolve_service_alias",
          "Resolve any spelling of a service to its canonical name, and list every "
          "spelling it has across systems. Use this before comparing data from two tools.",
          [{"name": "name", "type": "str", "required": True}],
          """\
row = conn.execute('SELECT canonical FROM service_aliases WHERE alias=? OR canonical=? LIMIT 1',
                   (name, name)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no service matches ' + str(name) +
            '; try list_service_aliases()'}
canon = row[0]
return {'canonical': canon,
        'aliases': [dict(r) for r in conn.execute(
            'SELECT alias, system FROM service_aliases WHERE canonical=? ORDER BY system',
            (canon,)).fetchall()]}""",
          reads=["service_aliases"], writes=[]))

    T(_mk("list_service_aliases", "Every known service-name spelling, by system.",
          [],
          """\
return [dict(r) for r in conn.execute(
    'SELECT canonical, alias, system FROM service_aliases ORDER BY canonical, system').fetchall()]""",
          reads=["service_aliases"], writes=[], returns="list[dict]"))

    T(_mk("list_remediation_proposals",
          "Read the remediation proposals people have put forward for an incident. "
          "Exactly one is the right call; the others are plausible suggestions that "
          "mask the symptom, target the wrong component, or change behaviour.",
          [{"name": "incident_ref", "type": "str", "required": True}],
          """\
rows = conn.execute('SELECT * FROM remediation_proposals WHERE incident_ref=? ORDER BY proposal_id',
                    (incident_ref,)).fetchall()
if not rows:
    refs = [r[0] for r in conn.execute(
        'SELECT DISTINCT incident_ref FROM remediation_proposals ORDER BY 1').fetchall()]
    return {'ok': False, 'error': 'no proposals for ' + str(incident_ref) +
            '; known: ' + ', '.join(refs)}
return [dict(r) for r in rows]""",
          reads=["remediation_proposals"], writes=[], returns="list[dict]"))

    T(_mk("jira_transition_issue",
          "Transition a Jira issue. Jira status is a per-project workflow, so moving an "
          "issue to 'Done' does NOT by itself mean it was fixed - a completed issue also "
          "carries a resolution (e.g. 'Fixed'). Set both.",
          [{"name": "key", "type": "str", "required": True},
           {"name": "status", "type": "str", "required": True},
           {"name": "resolution", "type": "str", "default": ""}],
          """\
row = conn.execute('SELECT * FROM jira_issues WHERE key=?', (key,)).fetchone()
if row is None:
    return {'ok': False, 'error': 'no such Jira issue: ' + str(key)}
valid = ('Backlog', 'In Progress', 'In Review', 'Blocked', 'Done')
if status not in valid:
    return {'ok': False, 'error': 'status must be one of: ' + ', '.join(valid)}
if status == 'Done' and not (resolution or '').strip():
    return {'ok': False, 'error': 'transitioning to Done requires a resolution '
            '(for example Fixed) - a status alone does not record the outcome'}
conn.execute('UPDATE jira_issues SET status=?, resolution=? WHERE key=?',
             (status, resolution or '', key))
_audit(conn, 'jira_transition_issue', row['component'] or '',
       {'key': key, 'status': status, 'resolution': resolution or ''})
conn.commit()
return {'ok': True, 'key': key, 'status': status, 'resolution': resolution or ''}""",
          reads=["jira_issues"], writes=["jira_issues", "audit_events"],
          snippets=(AUDIT_SNIPPET,)))

    T(_mk("k8s_events_list",
          "List Kubernetes events (OOMKilled, CrashLoopBackOff, ...). The kubelet records "
          "kernel-level kills that an application error tracker never sees, because the "
          "process dies before its SDK can flush.",
          [{"name": "namespace", "type": "str", "default": None},
           {"name": "pod", "type": "str", "default": None},
           {"name": "reason", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM k8s_events'
conds, args = [], []
for col, val in (('namespace', namespace), ('pod', pod), ('reason', reason)):
    if val:
        conds.append(col + '=?'); args.append(val)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY day DESC, event_id', args).fetchall()]""",
          reads=["k8s_events"], writes=[], returns="list[dict]"))

    T(_mk("k8s_pods_list",
          "List pods with phase, restart count, memory limit/usage and the running image "
          "tag. The image tag is the only ground truth for what is actually deployed - "
          "release records in other systems drift from it, especially after a rollback.",
          [{"name": "namespace", "type": "str", "default": None},
           {"name": "service", "type": "str", "default": None}],
          """\
sql = 'SELECT * FROM k8s_pods'
conds, args = [], []
if namespace:
    conds.append('namespace=?'); args.append(namespace)
if service:
    conds.append('service=?'); args.append(service)
if conds:
    sql += ' WHERE ' + ' AND '.join(conds)
return [dict(r) for r in conn.execute(sql + ' ORDER BY pod', args).fetchall()]""",
          reads=["k8s_pods"], writes=[], returns="list[dict]"))

    T(_mk("submit_answer",
          "Submit the answer to a reconciliation question. `sources` must list every "
          "system you actually consulted (e.g. pd_incidents, status_page_posts). "
          "`assumptions` is where you record any judgement you had to make - a week "
          "boundary, whether rollbacks count, which of two disagreeing numbers you "
          "trusted and why. An answer with no stated assumption on an ambiguous "
          "question is not a complete answer.",
          [{"name": "question_id", "type": "str", "required": True},
           {"name": "answer", "type": "str", "required": True},
           {"name": "sources", "type": "list", "default": None,
            "description": "systems consulted"},
           {"name": "assumptions", "type": "str", "default": ""}],
          """\
if isinstance(sources, str):
    try:
        sources = _json.loads(sources)
    except Exception:
        sources = [x.strip() for x in sources.split(',') if x.strip()]
sources = sources or []
if not isinstance(sources, list):
    return {'ok': False, 'error': 'sources must be a list of system names'}
cur = conn.execute('INSERT INTO answers(question_id, answer, sources, assumptions) '
                   'VALUES (?,?,?,?)',
                   (str(question_id), str(answer), _json.dumps(sorted(str(x) for x in sources)),
                    str(assumptions or '')))
_audit(conn, 'submit_answer', '', {'question_id': str(question_id), 'answer': str(answer),
                                   'source_count': len(sources)})
conn.commit()
return {'ok': True, 'answer_id': cur.lastrowid, 'question_id': str(question_id),
        'answer': str(answer), 'sources': sorted(str(x) for x in sources)}""",
          reads=[], writes=["answers", "audit_events"], snippets=(AUDIT_SNIPPET,),
          extra_schema={"sources": {"items": {"type": "string"}}}))

    return tools
