CREATE TABLE alert_firings (
    firing_id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    day INTEGER NOT NULL,
    silenced INTEGER NOT NULL DEFAULT 0,
    inhibited_by INTEGER,
    paged_incident INTEGER          -- NULL when it never reached a human
);
CREATE TABLE alert_rules (
    rule_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    service_label TEXT NOT NULL,   -- may name a service that no longer exists
    expr TEXT NOT NULL,
    severity TEXT NOT NULL,
    group_by TEXT NOT NULL DEFAULT '',
    routes_to TEXT NOT NULL DEFAULT ''
);
CREATE TABLE alert_silences (
    silence_id INTEGER PRIMARY KEY,
    matcher TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_day INTEGER NOT NULL
);
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'firing',
    message TEXT NOT NULL DEFAULT ''
);
CREATE TABLE answers (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    assumptions TEXT NOT NULL DEFAULT ''
);
CREATE TABLE approval_policy (
    policy_id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,          -- the irreversible act requiring sign-off
    approver_role TEXT NOT NULL,
    rationale TEXT NOT NULL
);
CREATE TABLE approval_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL DEFAULT 'pending',   -- pending|approved|denied
    responder TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL DEFAULT ''
);
CREATE TABLE audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE canary_assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    verdict TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE channels (
    channel TEXT PRIMARY KEY,
    purpose TEXT NOT NULL DEFAULT ''
);
CREATE TABLE ci_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    pr_number INTEGER,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE ci_stages (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE code_exercises (
    exercise_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    func TEXT NOT NULL,
    spec TEXT NOT NULL,
    starter TEXT NOT NULL,
    visible_tests TEXT NOT NULL,   -- json [[name, body], ...]
    hidden_tests TEXT NOT NULL     -- json, never returned by any read tool
);
CREATE TABLE code_submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    visible_passed INTEGER NOT NULL DEFAULT 0,
    visible_total INTEGER NOT NULL DEFAULT 0,
    hidden_passed INTEGER NOT NULL DEFAULT 0,
    hidden_total INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE commits (
    commit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha TEXT UNIQUE NOT NULL,
    service TEXT NOT NULL,
    author TEXT NOT NULL,
    day INTEGER NOT NULL,
    message TEXT NOT NULL,
    files TEXT NOT NULL DEFAULT '',
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE confluence_pages (
    page_id INTEGER PRIMARY KEY,
    space TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    last_updated_day INTEGER NOT NULL,
    stale INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE contract_rules (
    rule_id INTEGER PRIMARY KEY,
    producer_service TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    consumer_service TEXT NOT NULL,
    consumer_key TEXT NOT NULL,
    consumer_required_value TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE db_grants (
    grant_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    component TEXT NOT NULL,       -- an infra_components name
    role TEXT NOT NULL,
    state TEXT NOT NULL,           -- active | revoked | missing
    changed_day INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE deployments (
    deployment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    canary_percent INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE diagnoses (
    diagnosis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    fault_detected INTEGER NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    fault_type TEXT NOT NULL DEFAULT '',
    offending_key TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE documents (
    doc_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    day INTEGER NOT NULL DEFAULT 0,
    body TEXT NOT NULL
);
CREATE TABLE env_state (
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (service, environment, kind, key)
);
CREATE TABLE error_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    service TEXT NOT NULL,
    title TEXT NOT NULL,
    culprit TEXT NOT NULL DEFAULT '',
    events INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'unresolved'
);
CREATE TABLE feature_flags (
    flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    service TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    environment TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    rollout_percent INTEGER NOT NULL DEFAULT 0,
    UNIQUE (key, environment)
);
CREATE TABLE github_issues (
    number INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,           -- only open|closed exists
    labels TEXT NOT NULL DEFAULT '',
    created_day INTEGER NOT NULL
);
CREATE TABLE incidents (
    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    service TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    commander TEXT NOT NULL DEFAULT ''
);
CREATE TABLE infra_components (
    component_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'healthy',
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE issue_links (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,            -- duplicates | relates | implements
    PRIMARY KEY (source, target)
);
CREATE TABLE jira_issues (
    key TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    summary TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    status TEXT NOT NULL,          -- per-project workflow, NOT open/closed
    resolution TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL,
    component TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    created_day INTEGER NOT NULL,
    updated_day INTEGER NOT NULL
);
CREATE TABLE k8s_deployments (
    service TEXT PRIMARY KEY,
    desired_replicas INTEGER NOT NULL,
    ready_replicas INTEGER NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'RollingUpdate',
    storage_class TEXT NOT NULL DEFAULT ''
);
CREATE TABLE k8s_events (
    event_id INTEGER PRIMARY KEY,
    namespace TEXT NOT NULL,
    pod TEXT NOT NULL,
    reason TEXT NOT NULL,          -- OOMKilled | CrashLoopBackOff | BackOff | Killing
    message TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    day INTEGER NOT NULL
);
CREATE TABLE k8s_nodes (
    node TEXT PRIMARY KEY,
    ready TEXT NOT NULL,           -- True | False | Unknown
    condition TEXT NOT NULL,       -- Ready | DiskPressure | MemoryPressure | KernelDeadlock
    message TEXT NOT NULL,
    cpu_used_pct INTEGER NOT NULL,
    disk_used_pct INTEGER NOT NULL,
    labels TEXT NOT NULL DEFAULT '',
    kernel_version TEXT NOT NULL DEFAULT '',
    taints TEXT NOT NULL DEFAULT ''
);
CREATE TABLE k8s_pods (
    pod TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    service TEXT NOT NULL,
    image_tag TEXT NOT NULL,       -- the ONLY ground truth for what is running
    phase TEXT NOT NULL,
    restarts INTEGER NOT NULL DEFAULT 0,
    memory_limit_mb INTEGER NOT NULL,
    memory_usage_mb INTEGER NOT NULL,
    node TEXT NOT NULL DEFAULT '',       -- '' when the pod was never scheduled
    pending_reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE linear_issues (
    identifier TEXT PRIMARY KEY,
    team TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    priority INTEGER NOT NULL,     -- 0=none 1=urgent 2=high 3=normal 4=low
    label TEXT NOT NULL DEFAULT '',
    created_day INTEGER NOT NULL
);
CREATE TABLE local_deploy_log (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    environment TEXT NOT NULL,     -- CS-07: includes 'nonprod-*' spellings
    day INTEGER NOT NULL,
    was_rollback INTEGER NOT NULL DEFAULT 0   -- CS-26: do rollbacks count?
);
CREATE TABLE logs (
    log_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production',
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    author TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE metric_rules (
    rule_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    kind TEXT NOT NULL,
    ckey TEXT NOT NULL DEFAULT '',
    cvalue TEXT NOT NULL DEFAULT '',
    value REAL NOT NULL
);
CREATE TABLE migration_requirements (
    req_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    module TEXT NOT NULL,
    migration_name TEXT NOT NULL
);
CREATE TABLE migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    name TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (service, name, environment)
);
CREATE TABLE network_paths (
    path_id INTEGER PRIMARY KEY,
    from_service TEXT NOT NULL,
    to_target TEXT NOT NULL,
    state TEXT NOT NULL,           -- open | refused | timeout
    observed_day INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE oncall (
    team TEXT PRIMARY KEY,
    engineer TEXT NOT NULL
);
CREATE TABLE owner_spreadsheet (
    row_id INTEGER PRIMARY KEY,
    service_label TEXT NOT NULL,   -- CS-01: yet another spelling
    owning_team TEXT NOT NULL,
    slack_channel TEXT NOT NULL DEFAULT '',
    last_reviewed_day INTEGER NOT NULL,
    week_start TEXT NOT NULL DEFAULT 'sunday'  -- CS-24: its own week convention
);
CREATE TABLE pd_change_events (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pd_service_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    day INTEGER NOT NULL
);
CREATE TABLE pd_incidents (
    incident_number INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    pd_service_id TEXT NOT NULL,
    urgency TEXT NOT NULL,         -- high|low  (NOT the same as priority)
    priority TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_day INTEGER NOT NULL,
    resolved_day INTEGER
);
CREATE TABLE pd_oncall (
    schedule_id TEXT NOT NULL,
    schedule_name TEXT NOT NULL,
    escalation_policy TEXT NOT NULL,
    user_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    PRIMARY KEY (schedule_id, day)
);
CREATE TABLE pd_services (
    pd_service_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,            -- CS-01: a THIRD spelling of the service
    escalation_policy TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE pr_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE prom_series (
    series_id INTEGER PRIMARY KEY,
    metric TEXT NOT NULL,
    label_service TEXT NOT NULL,   -- Prometheus label spelling
    label_env TEXT NOT NULL,
    day INTEGER NOT NULL,
    value REAL NOT NULL,
    counter_reset INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE pull_requests (
    number INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    ticket_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    merged_version TEXT NOT NULL DEFAULT ''
);
CREATE TABLE remediation_proposals (
    proposal_id INTEGER PRIMARY KEY,
    incident_ref TEXT NOT NULL,
    author TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE TABLE repo_files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    path TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    loc INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL
);
CREATE TABLE repo_state (
    service TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (service, kind, key)
);
CREATE TABLE runtime_stats (
    service TEXT PRIMARY KEY,
    heap_used_pct INTEGER NOT NULL,
    gc_pause_p99_ms INTEGER NOT NULL,
    gc_collections_per_min INTEGER NOT NULL,
    threads INTEGER NOT NULL
);
CREATE TABLE sentry_issues (
    issue_id TEXT PRIMARY KEY,
    project_slug TEXT NOT NULL,    -- Sentry's own naming
    title TEXT NOT NULL,
    level TEXT NOT NULL,
    events INTEGER NOT NULL,       -- sampled
    users_affected INTEGER NOT NULL DEFAULT 0,
    first_seen_day INTEGER NOT NULL,
    last_seen_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'unresolved'
);
CREATE TABLE sentry_projects (
    slug TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    sample_rate REAL NOT NULL      -- why Sentry counts < Prometheus counts
);
CREATE TABLE service_aliases (
    canonical TEXT NOT NULL,
    alias TEXT NOT NULL,
    system TEXT NOT NULL,
    PRIMARY KEY (alias, system)
);
CREATE TABLE service_dependencies (
    service TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (service, depends_on)
);
CREATE TABLE service_metrics (
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (service, environment, metric)
);
CREATE TABLE services (
    service_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    team TEXT NOT NULL,
    tier INTEGER NOT NULL,
    language TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    repo_version TEXT NOT NULL
);
CREATE TABLE slos (
    slo_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    threshold REAL NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE status_page (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT ''
);
CREATE TABLE status_page_posts (
    post_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    impact TEXT NOT NULL,          -- none|minor|major|critical
    state TEXT NOT NULL,
    published_day INTEGER NOT NULL,
    linked_incident INTEGER
);
CREATE TABLE tests_catalog (
    test_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    suite TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'passing',
    quarantined INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    assignee TEXT NOT NULL DEFAULT '',
    service TEXT NOT NULL DEFAULT ''
);
CREATE TABLE tool_calls (
    call_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL
);
CREATE TABLE traffic_profile (
    route_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    route TEXT NOT NULL,
    rps INTEGER NOT NULL,
    share_pct INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    state_json TEXT NOT NULL,
    requires_migration TEXT NOT NULL DEFAULT '',
    UNIQUE (service, version)
);
CREATE TABLE vulnerabilities (
    vuln_id INTEGER PRIMARY KEY,
    cve TEXT NOT NULL,
    package TEXT NOT NULL,
    service TEXT NOT NULL,
    severity TEXT NOT NULL,
    fixed_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE workspace_files (
    path TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    seeded INTEGER NOT NULL DEFAULT 1   -- 0 once the agent has written it
);
CREATE TABLE workspace_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    stdout TEXT NOT NULL DEFAULT '',
    stderr TEXT NOT NULL DEFAULT '',
    timed_out INTEGER NOT NULL DEFAULT 0
);
DELETE FROM "sqlite_sequence";
