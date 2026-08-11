"""Multi-vendor tool surfaces and the data chaos between them.

NovaCart, like every real engineering org in the research corpus, does not keep
its facts in one place. Tickets live in Jira *and* Linear *and* GitHub Issues;
metrics live in Prometheus *and* Sentry; the service catalogue lives in
PagerDuty *and* a spreadsheet someone maintains by hand. These systems disagree,
and they disagree for reasons that are documented rather than invented.

Every conflict below carries a CS-## reference into
research/notes/domain/F_chaos_scenarios.md and a tool-surface reference into
research/notes/mcp/_TOOL_INVENTORY.md. Tool names mirror the real MCP servers
(jira_search, list_oncalls, query_prometheus, search_issues, ...) so an agent
that has seen the real servers is not surprised here.

Design rule taken from the research (F5): chaos is legitimate when a competent
human would also have to do extra work AND the resolution is discoverable from
inside the world. Nothing here is hidden - it is contradictory.
"""

SCHEMA_SQL = """
-- Every tool call, read or write. Verifiers that ask "did you actually consult
-- X" must derive that from the trace, never from what the agent says it did.
CREATE TABLE tool_calls (
    call_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL
);

-- answers submitted by the agent for reconciliation questions
CREATE TABLE answers (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    assumptions TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------- trackers
-- CS-11/12: the same defect exists in more than one tracker with conflicting
-- severity. 28.9-50.8% of duplicate bug reports carry inconsistent severity.
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
CREATE TABLE linear_issues (
    identifier TEXT PRIMARY KEY,
    team TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    priority INTEGER NOT NULL,     -- 0=none 1=urgent 2=high 3=normal 4=low
    label TEXT NOT NULL DEFAULT '',
    created_day INTEGER NOT NULL
);
CREATE TABLE github_issues (
    number INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,           -- only open|closed exists
    labels TEXT NOT NULL DEFAULT '',
    created_day INTEGER NOT NULL
);
-- the cross-references that DO exist somewhere, so the join is discoverable
CREATE TABLE issue_links (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,            -- duplicates | relates | implements
    PRIMARY KEY (source, target)
);

-- ------------------------------------------------------------ observability
-- CS-08/09: two correct numbers that disagree. Prometheus counts requests;
-- Sentry counts sampled events grouped into issues.
CREATE TABLE prom_series (
    series_id INTEGER PRIMARY KEY,
    metric TEXT NOT NULL,
    label_service TEXT NOT NULL,   -- Prometheus label spelling
    label_env TEXT NOT NULL,
    day INTEGER NOT NULL,
    value REAL NOT NULL,
    counter_reset INTEGER NOT NULL DEFAULT 0
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

-- --------------------------------------------------------------- pagerduty
CREATE TABLE pd_services (
    pd_service_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,            -- CS-01: a THIRD spelling of the service
    escalation_policy TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
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
CREATE TABLE pd_change_events (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pd_service_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    day INTEGER NOT NULL
);
-- CS-18: "customer-facing" exists ONLY here. No incident object carries it.
CREATE TABLE status_page_posts (
    post_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    impact TEXT NOT NULL,          -- none|minor|major|critical
    state TEXT NOT NULL,
    published_day INTEGER NOT NULL,
    linked_incident INTEGER
);

-- ------------------------------------------------------------ knowledge/ops
CREATE TABLE confluence_pages (
    page_id INTEGER PRIMARY KEY,
    space TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    last_updated_day INTEGER NOT NULL,
    stale INTEGER NOT NULL DEFAULT 0
);
-- CS-05: the hand-maintained catalogue that drifts from reality
CREATE TABLE owner_spreadsheet (
    row_id INTEGER PRIMARY KEY,
    service_label TEXT NOT NULL,   -- CS-01: yet another spelling
    owning_team TEXT NOT NULL,
    slack_channel TEXT NOT NULL DEFAULT '',
    last_reviewed_day INTEGER NOT NULL,
    week_start TEXT NOT NULL DEFAULT 'sunday'  -- CS-24: its own week convention
);
-- a team's ad-hoc deploy log kept in a local sqlite because the real one is slow
CREATE TABLE local_deploy_log (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    environment TEXT NOT NULL,     -- CS-07: includes 'nonprod-*' spellings
    day INTEGER NOT NULL,
    was_rollback INTEGER NOT NULL DEFAULT 0   -- CS-26: do rollbacks count?
);
-- Kubernetes events and pod state. The research is explicit that an OOMKill
-- appears here and in pod metrics but NOT in Sentry - the process dies before
-- the SDK flushes - while a handled exception is rich in Sentry and invisible
-- here. The two are complementary blind spots, not redundant sources.
-- (research/notes/mcp/_TOOL_INVENTORY.md, overlap 3 "What broke?")
CREATE TABLE k8s_events (
    event_id INTEGER PRIMARY KEY,
    namespace TEXT NOT NULL,
    pod TEXT NOT NULL,
    reason TEXT NOT NULL,          -- OOMKilled | CrashLoopBackOff | BackOff | Killing
    message TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    day INTEGER NOT NULL
);
CREATE TABLE k8s_pods (
    pod TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    service TEXT NOT NULL,
    image_tag TEXT NOT NULL,       -- the ONLY ground truth for what is running
    phase TEXT NOT NULL,
    restarts INTEGER NOT NULL DEFAULT 0,
    memory_limit_mb INTEGER NOT NULL,
    memory_usage_mb INTEGER NOT NULL
);
-- the mapping that makes the naming chaos SOLVABLE rather than cruel (F5)
CREATE TABLE service_aliases (
    canonical TEXT NOT NULL,
    alias TEXT NOT NULL,
    system TEXT NOT NULL,
    PRIMARY KEY (alias, system)
);
"""

TODAY = 420          # the world's "now", matching commits.day
WEEK = 7

# --------------------------------------------------------------------------
# CS-01/02 — one service, four spellings, with a discoverable mapping
# --------------------------------------------------------------------------
ALIASES = [
    ("checkout", "checkout", "kubernetes"),
    ("checkout", "checkout-api", "pagerduty"),
    ("checkout", "checkout_service", "prometheus"),
    ("checkout", "checkout-web", "sentry"),
    ("checkout", "Checkout Platform", "confluence"),
    ("checkout", "Checkout (commerce)", "spreadsheet"),
    ("payments", "payments", "kubernetes"),
    ("payments", "payments-api", "pagerduty"),
    ("payments", "payments_service", "prometheus"),
    ("payments", "payments-backend", "sentry"),
    ("search", "search", "kubernetes"),
    ("search", "search-svc", "pagerduty"),
    ("search", "search_service", "prometheus"),
    ("api-gateway", "api-gateway", "kubernetes"),
    ("api-gateway", "edge-gateway", "pagerduty"),
    ("api-gateway", "gateway_service", "prometheus"),
]

# --------------------------------------------------------------------------
# CS-11/12 — the same defect in three trackers with conflicting severity
# --------------------------------------------------------------------------
JIRA_ISSUES = [
    # key, project, summary, type, status, resolution, priority, component, assignee, created, updated
    ("ENG-2101", "ENG", "Payments error rate breaching the 1% SLO", "Bug",
     "In Progress", "", "Highest", "payments", "Diego Ramos", 414, 419),
    ("ENG-2102", "ENG", "Inventory reservations failing under peak traffic", "Bug",
     "In Progress", "", "High", "inventory", "Alex Osei", 415, 419),
    ("ENG-3001", "ENG", "Checkout latency spike during evening peak", "Bug",
     "Backlog", "", "Medium", "checkout", "", 411, 413),
    ("ENG-3002", "ENG", "Duplicate charge on retried payment", "Bug",
     "Done", "Fixed", "High", "payments", "Diego Ramos", 402, 409),
    ("ENG-3003", "ENG", "Search returns stale results after reindex", "Bug",
     "Blocked", "", "Medium", "search", "Mei Tanaka", 408, 417),
    ("ENG-3004", "ENG", "Cart total rounds incorrectly for multi-currency", "Bug",
     "Done", "Won't Do", "Low", "checkout", "", 396, 404),
]
LINEAR_ISSUES = [
    # identifier, team, title, state, priority(1=urgent), label, created
    ("GRW-88", "Growth", "Checkout slow at peak — customers dropping off", "In Progress", 1,
     "bug", 411),
    ("GRW-91", "Growth", "Search shows stale products after reindex", "Todo", 3, "bug", 408),
    ("GRW-95", "Growth", "Autocomplete flickers on slow connections", "Todo", 4, "bug", 417),
    ("GRW-97", "Growth", "Product images load from origin, not CDN", "In Progress", 2,
     "bug,performance", 416),
]
GITHUB_ISSUES = [
    (4412, "novacart/storefront", "Checkout page hangs for ~8s before redirect", "open",
     "bug,customer-report", 412),
    (4415, "novacart/platform", "Gateway 502s under sustained load", "open", "bug", 415),
    (4402, "novacart/storefront", "Stale search results after catalog update", "closed",
     "bug,duplicate", 408),
]
# The links exist — so the reconciliation is discoverable, not guesswork (F5).
ISSUE_LINKS = [
    ("ENG-3001", "GRW-88", "duplicates"),
    ("ENG-3001", "4412", "duplicates"),
    ("ENG-3003", "GRW-91", "duplicates"),
    ("ENG-3003", "4402", "duplicates"),
]

# --------------------------------------------------------------------------
# CS-08/09 — Prometheus and Sentry both correct, both different
# --------------------------------------------------------------------------
SENTRY_PROJECTS = [
    ("checkout-web", "javascript", 0.25),     # 25% sampling
    ("payments-backend", "python", 1.0),
    ("search", "python", 0.5),
]
SENTRY_ISSUES = [
    ("CHECKOUT-1A", "checkout-web", "TypeError: NoneType has no attribute 'amount'",
     "error", 2317, 890, 410, 420, "unresolved"),
    ("CHECKOUT-2B", "checkout-web", "TimeoutError: payments call exceeded 8000ms",
     "error", 1904, 1502, 409, 420, "unresolved"),
    ("PAY-9C", "payments-backend", "ConnectionTimeout: notifications call exceeded 30000ms",
     "error", 18422, 6210, 405, 420, "unresolved"),
    ("SRCH-3D", "search", "IndexRefreshTimeout", "warning", 640, 210, 414, 419, "resolved"),
]
# Prometheus sees ALL requests. Sentry sees sampled events. Neither is lying.
PROM_SERIES = [
    # metric, service label, env label, day, value, counter_reset
    ("http_requests_total:rate5m", "checkout_service", "production", 418, 138.0, 0),
    ("http_requests_total:rate5m", "checkout_service", "production", 419, 141.0, 0),
    ("http_requests_total:rate5m", "checkout_service", "production", 420, 139.0, 0),
    ("http_errors_total:rate5m", "checkout_service", "production", 418, 7.6, 0),
    ("http_errors_total:rate5m", "checkout_service", "production", 419, 7.8, 0),
    # CS-08: a counter reset on pod restart under-reports exactly when worst
    ("http_errors_total:rate5m", "checkout_service", "production", 420, 2.1, 1),
    ("http_errors_total:rate5m", "payments_service", "production", 419, 5.5, 0),
    ("http_errors_total:rate5m", "payments_service", "production", 420, 5.6, 0),
    # CS-07: a 'nonprod' environment whose name contains 'prod'
    ("http_errors_total:rate5m", "checkout_service", "nonprod-staging", 419, 31.0, 0),
    ("http_errors_total:rate5m", "checkout_service", "nonprod-staging", 420, 29.4, 0),
]

# --------------------------------------------------------------------------
# PagerDuty — incidents, on-call, change events, and the status page
# --------------------------------------------------------------------------
PD_SERVICES = [
    ("PSVC001", "checkout-api", "EP-Commerce", "active"),
    ("PSVC002", "payments-api", "EP-Commerce", "active"),
    ("PSVC003", "edge-gateway", "EP-Platform", "active"),
    ("PSVC004", "search-svc", "EP-Growth", "active"),
    ("PSVC005", "inventory-api", "EP-Commerce", "active"),
]
# CS-21: urgency and priority are different vocabularies, both present.
PD_INCIDENTS = [
    (5101, "Elevated checkout latency", "PSVC001", "high", "P2", "resolved", 411, 412),
    (5102, "Payments error rate above SLO", "PSVC002", "high", "P1", "triggered", 414, None),
    (5103, "Gateway latency surge after release", "PSVC003", "high", "P1", "acknowledged",
     416, None),
    (5104, "Search index refresh lag", "PSVC004", "low", "P4", "resolved", 414, 415),
    (5105, "Inventory reservation timeouts", "PSVC005", "high", "P2", "triggered", 415, None),
    (5106, "Checkout latency spike (recurrence)", "PSVC001", "high", "P2", "resolved",
     417, 418),
    (5107, "Elevated 5xx from edge gateway", "PSVC003", "low", "P3", "resolved", 419, 419),
]
# CS-18: impact lives ONLY here, and the status page lags internal state.
STATUS_PAGE_POSTS = [
    (7001, "Degraded checkout performance", "major", "resolved", 412, 5101),
    (7002, "Elevated error rates on payments", "minor", "monitoring", 415, 5102),
    (7003, "API latency affecting some customers", "major", "resolved", 417, 5103),
    # 5106 was customer-visible but nobody posted; 5104/5105/5107 were internal only
]
PD_ONCALL = [
    ("SCHED-COM", "Commerce primary", "EP-Commerce", "Diego Ramos", 418),
    ("SCHED-COM", "Commerce primary", "EP-Commerce", "Diego Ramos", 419),
    ("SCHED-PLT", "Platform primary", "EP-Platform", "Priya Nair", 419),
    ("SCHED-GRW", "Growth primary", "EP-Growth", "Mei Tanaka", 419),
]
PD_CHANGE_EVENTS = [
    ("PSVC003", "Deployed edge-gateway v5.1.0", 416),
    ("PSVC001", "Deployed checkout-api v2.6.3", 413),
    ("PSVC002", "Config change: notifications timeout", 414),
]

# --------------------------------------------------------------------------
# The OOMKill blind spot: analytics-worker is being killed by the kernel. The
# kubelet records it; the error tracker never sees it because the process dies
# before the SDK can flush. An agent that starts from Sentry finds nothing.
# --------------------------------------------------------------------------
K8S_PODS = [
    ("analytics-worker-7d9f-x2k1", "production", "analytics-worker", "v2.1.7",
     "CrashLoopBackOff", 47, 512, 511),
    ("analytics-worker-7d9f-m4p8", "production", "analytics-worker", "v2.1.7",
     "Running", 39, 512, 498),
    ("checkout-5b8c-aa10", "production", "checkout", "v2.6.3", "Running", 0, 2048, 890),
    ("payments-6c1d-bb22", "production", "payments", "v2.7.0", "Running", 0, 2048, 1120),
    # CS: the running image tag disagrees with what the release systems report
    ("api-gateway-9f2e-cc33", "production", "api-gateway", "v5.0.9", "Running", 1, 1024, 610),
    ("search-3a7b-dd44", "production", "search", "v3.0.5", "Running", 0, 1024, 700),
]
K8S_EVENTS = [
    (9001, "production", "analytics-worker-7d9f-x2k1", "OOMKilled",
     "Container analytics exceeded its memory limit of 512Mi and was killed", 47, 419),
    (9002, "production", "analytics-worker-7d9f-x2k1", "CrashLoopBackOff",
     "Back-off restarting failed container analytics", 47, 419),
    (9003, "production", "analytics-worker-7d9f-m4p8", "OOMKilled",
     "Container analytics exceeded its memory limit of 512Mi and was killed", 39, 420),
    (9004, "production", "api-gateway-9f2e-cc33", "Killing",
     "Stopping container gateway for rollout", 1, 417),
]

# --------------------------------------------------------------------------
# CS-05 / CS-24 — the hand-maintained catalogue and its own week convention
# --------------------------------------------------------------------------
OWNER_SPREADSHEET = [
    (1, "Checkout (commerce)", "Commerce Platform", "#commerce", 340, "sunday"),
    (2, "Payments (commerce)", "Commerce Platform", "#commerce", 340, "sunday"),
    (3, "Search (growth)", "Discovery Squad", "#growth", 210, "sunday"),
    # CS-05: this team was dissolved and folded into Platform; the sheet is stale
    (4, "Gateway (platform)", "Edge Team", "#edge", 180, "sunday"),
    (5, "Inventory (commerce)", "Commerce Platform", "#commerce", 355, "sunday"),
]
CONFLUENCE_PAGES = [
    (8001, "ENG", "Checkout Platform — architecture",
     "Checkout Platform is owned by the Commerce Platform team. It calls payments "
     "and inventory synchronously. Escalate via #commerce.", 372, 0),
    (8002, "ENG", "Gateway runbook (legacy)",
     "The Edge Team owns the gateway. Page the Edge Team rota for any 5xx spike. "
     "Restart procedure targets host gw-prod-03.", 181, 1),
    (8003, "ENG", "Weekly reporting conventions",
     "Engineering weekly reports run Monday to Sunday, ISO-8601 week numbering, in "
     "UTC. Note that the service-owner spreadsheet uses a Sunday start and will "
     "disagree by one day at the boundary.", 401, 0),
    (8004, "ENG", "Incident severity ladder",
     "P1 = customer-facing outage, P2 = degraded customer experience, P3 = internal "
     "only, P4 = cosmetic. Customer-facing status is recorded on the public status "
     "page, not on the incident.", 395, 0),
]
LOCAL_DEPLOY_LOG = [
    ("checkout", "v2.6.3", "production", 413, 0),
    ("api-gateway", "v5.1.0", "production", 416, 0),
    ("api-gateway", "v5.0.9", "production", 417, 1),      # CS-26: a rollback
    ("checkout", "v2.6.3", "nonprod-staging", 412, 0),    # CS-07: matches naive 'prod'
    ("search", "v3.0.5", "production", 414, 0),
    ("payments", "v2.7.0", "production", 410, 0),
    ("api-gateway", "v5.1.0", "nonprod-staging", 415, 0),
]
