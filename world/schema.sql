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
CREATE TABLE deployments (
    deployment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    canary_percent INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE env_state (
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (service, environment, kind, key)
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
CREATE TABLE repo_state (
    service TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (service, kind, key)
);
CREATE TABLE runbooks (
    runbook_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL
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
CREATE TABLE versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    state_json TEXT NOT NULL,
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
