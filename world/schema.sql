CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'firing',
    message TEXT NOT NULL DEFAULT ''
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
CREATE TABLE contract_rules (
    rule_id INTEGER PRIMARY KEY,
    producer_service TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    consumer_service TEXT NOT NULL,
    consumer_key TEXT NOT NULL,
    consumer_required_value TEXT NOT NULL,
    message TEXT NOT NULL
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
CREATE TABLE oncall (
    team TEXT PRIMARY KEY,
    engineer TEXT NOT NULL
);
CREATE TABLE pr_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    payload TEXT NOT NULL
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
DELETE FROM "sqlite_sequence";
