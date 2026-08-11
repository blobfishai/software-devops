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
-- A human who can be asked, and who answers. The corpus is unanimous that an
-- agent must escalate on IRREVERSIBILITY rather than difficulty
-- (research/notes/automation/_WORKFLOW_PATTERNS.md), and both tau-bench and
-- TheAgentCompany treat a simulated human as central. Without one, "ask when
-- ambiguous", "respect a human gate" and "stop blocked rather than claim
-- success" are all unverifiable.
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

-- CS-28: one failure is not one alert is not one page is not one incident. The
-- ratio is a configuration artefact of grouping, inhibition and silences, and
-- Alertmanager's truncatedAlerts field loses some silently.
-- CS-13/15: monitors outlive the services they watch, and dashboards rot.
CREATE TABLE alert_rules (
    rule_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    service_label TEXT NOT NULL,   -- may name a service that no longer exists
    expr TEXT NOT NULL,
    severity TEXT NOT NULL,
    group_by TEXT NOT NULL DEFAULT '',
    routes_to TEXT NOT NULL DEFAULT ''
);
CREATE TABLE alert_firings (
    firing_id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    day INTEGER NOT NULL,
    silenced INTEGER NOT NULL DEFAULT 0,
    inhibited_by INTEGER,
    paged_incident INTEGER          -- NULL when it never reached a human
);
CREATE TABLE alert_silences (
    silence_id INTEGER PRIMARY KEY,
    matcher TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_day INTEGER NOT NULL
);

-- Human-written remediation proposals attached to an incident. The agent picks
-- one; it writes no code. SWE-Lancer's manager split is 265 of 463 tasks and is
-- HARDER than implementing the fix (47.2% vs 51.5%), integer-graded and
-- flake-free (research/notes/evals/openai__SWELancer-Benchmark.md).
CREATE TABLE remediation_proposals (
    proposal_id INTEGER PRIMARY KEY,
    incident_ref TEXT NOT NULL,
    author TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL
);

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
    memory_usage_mb INTEGER NOT NULL,
    node TEXT NOT NULL DEFAULT '',       -- '' when the pod was never scheduled
    pending_reason TEXT NOT NULL DEFAULT ''
);
-- AIOpsLab's fault catalogue is largely NODE-level - assign_to_non_existent_node,
-- disk_woreout, kernel_fault, high_cpu, operator_security_context - and none of
-- them are visible from a service's own metrics or logs. A service whose node has
-- DiskPressure looks, from the service's side, exactly like a slow service. The
-- point of this table is that the evidence separating the two exists but lives
-- one layer down, so localizing it requires looking there.
-- (research/02-CORPUS-MAP.md, AIOpsLab fault families)
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
-- AIOpsLab's operator_misoperation family is a declared spec that the cluster
-- cannot satisfy: replicas: 100000, or a storageClassName that does not exist
-- (inject_operator.py). The symptom is always the same and always misleading -
-- the workload is simply not there - so the only way to tell "it crashed" from
-- "it was never admitted" is desired vs ready replicas.
CREATE TABLE k8s_deployments (
    service TEXT PRIMARY KEY,
    desired_replicas INTEGER NOT NULL,
    ready_replicas INTEGER NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'RollingUpdate',
    storage_class TEXT NOT NULL DEFAULT ''
);
-- Modules the world EXECUTES rather than inspects.
--
-- Every other check here is a rule over declared state. Those cannot catch a
-- logic error, because nothing runs. An exercise carries a specification, a
-- visible test the agent may run as often as it likes, and a hidden test it
-- never sees - so the world does not know whether an implementation is correct
-- until it executes it.
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
-- What the agent has written, and what happened when it was run.
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
-- AIOpsLab's remaining families need three kinds of evidence this world had no
-- table for: who is allowed to talk to a datastore, what a runtime is doing
-- between requests, and whether a path between two components is open at all.
-- Each is invisible from a service's own error rate, which is the point.
CREATE TABLE db_grants (
    grant_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    component TEXT NOT NULL,       -- an infra_components name
    role TEXT NOT NULL,
    state TEXT NOT NULL,           -- active | revoked | missing
    changed_day INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE runtime_stats (
    service TEXT PRIMARY KEY,
    heap_used_pct INTEGER NOT NULL,
    gc_pause_p99_ms INTEGER NOT NULL,
    gc_collections_per_min INTEGER NOT NULL,
    threads INTEGER NOT NULL
);
CREATE TABLE network_paths (
    path_id INTEGER PRIMARY KEY,
    from_service TEXT NOT NULL,
    to_target TEXT NOT NULL,
    state TEXT NOT NULL,           -- open | refused | timeout
    observed_day INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
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
    ("payments", "Payments (commerce)", "spreadsheet"),
    ("search", "search", "kubernetes"),
    ("search", "search-svc", "pagerduty"),
    ("search", "search_service", "prometheus"),
    ("search", "Search (growth)", "spreadsheet"),
    ("api-gateway", "api-gateway", "kubernetes"),
    ("api-gateway", "edge-gateway", "pagerduty"),
    ("api-gateway", "gateway_service", "prometheus"),
    # the edge cache fronts the gateway and alerts under its own label; without
    # this row the cache firings cannot be attributed to the gateway by any
    # evidence in the world, which would be withheld data rather than
    # contradictory data (research/notes/domain/F_chaos_scenarios.md F5)
    ("api-gateway", "edge_cache_service", "alertmanager"),
    ("api-gateway", "gateway-edge-cache", "grafana"),
    ("api-gateway", "Gateway (platform)", "spreadsheet"),
    ("inventory", "inventory", "kubernetes"),
    ("inventory", "inventory-api", "pagerduty"),
    ("inventory", "Inventory (commerce)", "spreadsheet"),
    ("analytics-worker", "analytics-worker", "kubernetes"),
    ("notifications", "notifications", "kubernetes"),
    ("media-service", "media-service", "kubernetes"),
    ("catalog", "catalog", "kubernetes"),
    ("storefront-web", "storefront-web", "kubernetes"),
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
    ("ENG-2103", "ENG", "Analytics worker restarting under queue load", "Bug",
     "In Progress", "", "High", "analytics-worker", "Alex Osei", 415, 419),
    ("ENG-2104", "ENG", "Notification delivery failures from hung SMTP calls", "Bug",
     "In Progress", "", "High", "notifications", "Priya Nair", 414, 419),
    ("ENG-2201", "ENG", "Search p99 latency exceeds the 300ms SLO", "Bug",
     "In Progress", "", "High", "search", "Mei Tanaka", 413, 419),
    ("ENG-2202", "ENG", "Catalog pricing p99 regression", "Bug",
     "In Progress", "", "High", "catalog", "Diego Ramos", 412, 419),
    ("ENG-2203", "ENG", "Media assets served from origin instead of the CDN", "Bug",
     "Backlog", "", "Medium", "media-service", "", 416, 418),
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
    # Ported task substrate. TheAgentCompany's sde-collect-open-issues,
    # sde-check-high-priority-issue and sde-copy-issues-to-plane all filter an
    # issue tracker by state, label and creation date, then move or report the
    # result. Three issues cannot express that; the filter has to be able to be
    # got wrong. Days run 402-419, matching the rest of the world's clock.
    (4402, 'novacart/storefront', 'Stale search results after catalog update', 'closed', 'bug,duplicate', 408),
    (4405, 'novacart/platform', 'Rate limiter allows bursts above the configured ceiling', 'open', 'bug,priority', 405),
    (4408, 'novacart/commerce', 'Refund webhook retried indefinitely on 4xx', 'open', 'bug,priority', 409),
    (4411, 'novacart/storefront', 'Dark mode toggle resets on navigation', 'open', 'enhancement', 411),
    (4412, 'novacart/storefront', 'Checkout page hangs for ~8s before redirect', 'open', 'bug,customer-report', 412),
    (4414, 'novacart/platform', 'Document the traffic-shift ceiling in the runbook', 'closed', 'docs', 414),
    (4415, 'novacart/platform', 'Gateway 502s under sustained load', 'open', 'bug', 415),
    (4417, 'novacart/commerce', 'Settlement batch size is not configurable', 'open', 'enhancement,priority', 417),
    (4418, 'novacart/growth', 'Search reindex job has never completed', 'open', 'bug,priority', 418),
    (4419, 'novacart/growth', 'Autocomplete returns deleted products', 'open', 'bug,customer-report', 419),
    (4420, 'novacart/commerce', 'Duplicate charge on retried capture', 'closed', 'bug,priority', 407),
    (4421, 'novacart/platform', 'Upgrade the base image to bookworm', 'open', 'chore', 403),
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
    # pod, namespace, service, image_tag, phase, restarts, mem_limit, mem_used, node, pending_reason
    ('analytics-worker-7d9f-x2k1', 'production', 'analytics-worker', 'v2.1.7', 'CrashLoopBackOff', 47, 512, 511, 'node-a1', ''),
    ('analytics-worker-7d9f-m4p8', 'production', 'analytics-worker', 'v2.1.7', 'Running', 39, 512, 498, 'node-a1', ''),
    ('checkout-5b8c-aa10', 'production', 'checkout', 'v2.6.3', 'Running', 0, 2048, 890, 'node-a1', ''),
    ('payments-6c1d-bb22', 'production', 'payments', 'v2.7.0', 'Running', 0, 2048, 1120, 'node-a2', ''),
    ('api-gateway-9f2e-cc33', 'production', 'api-gateway', 'v5.0.9', 'Running', 1, 1024, 610, 'node-a2', ''),
    ('search-3a7b-dd44', 'production', 'search', 'v3.0.5', 'Running', 0, 1024, 700, 'node-a2', ''),

    # --- AIOpsLab disk_woreout: every media-service replica landed on node-b3,
    # whose disk is at 97%. The pods are Running and their own metrics look
    # ordinary; the writes are what block.
    ('media-service-2e4f-ee55', 'production', 'media-service', 'v1.4.2', 'Running', 0, 1024, 480, 'node-b3', ''),
    ('media-service-2e4f-ff66', 'production', 'media-service', 'v1.4.2', 'Running', 0, 1024, 505, 'node-b3', ''),

    # --- AIOpsLab assign_to_non_existent_node: the reindex job requires a node
    # label no node in the cluster carries, so it has never once been scheduled.
    # Nothing has failed - it simply never ran, and the index quietly went stale.
    ('search-reindex-8c2a-gg77', 'production', 'search', 'v3.0.5', 'Pending', 0, 2048, 0, '',
     "0/4 nodes are available: 4 node(s) didn't match Pod's node affinity/selector (accelerator=gpu-a100)"),

    # --- AIOpsLab kernel_fault: node-c1 is NotReady on a soft lockup. Its pods
    # still report Running because the kubelet stopped reporting, not the pod.
    ('notifications-1b7d-hh88', 'production', 'notifications', 'v1.9.4', 'Running', 0, 512, 300, 'node-c1', ''),

    # --- AIOpsLab operator_security_context_fault: the migrator image runs as
    # root while the pod requires runAsNonRoot, so the container is never created
    # and the schema migration silently never ran.
    ('inventory-migrator-4d9e-ii99', 'production', 'inventory', 'v4.2.1', 'CreateContainerConfigError', 0, 512, 0, 'node-a2',
     'container has runAsNonRoot and image will run as root'),

    # --- AIOpsLab operator_overload_replicas: 58 of 64 requested checkout
    # replicas cannot be admitted. One stands in for the rest.
    ('checkout-5b8c-bb31', 'production', 'checkout', 'v2.6.3', 'Pending', 0, 2048, 0, '',
     '0/4 nodes are available: 4 Insufficient cpu (58 of 64 replicas unschedulable)'),

    # --- AIOpsLab operator_non_existent_storage: the claim never binds because
    # the storage class in the spec does not exist in the cluster.
    ('inventory-7f3c-cc42', 'production', 'inventory', 'v4.2.1', 'Pending', 0, 1024, 0, '',
     "pod has unbound immediate PersistentVolumeClaims: storageclass.storage.k8s.io 'fast-ssd-gp4' not found"),

    # --- AIOpsLab operator_invalid_affinity_toleration: the nightly reconciliation
    # job is pinned to node-a2 by affinity but does not tolerate the taint that
    # node carries, so it has never been admitted. Node healthy, pod spec wrong.
    ('analytics-recon-6a1b-jj10', 'production', 'analytics-worker', 'v2.1.7', 'Pending', 0, 512, 0, '',
     '0/4 nodes are available: 1 node(s) had untolerated taint {workload: batch}, '
     '3 node(s) didn\'t match Pod\'s node affinity/selector'),
]

# node, ready, condition, message, cpu_used_pct, disk_used_pct, labels, kernel_version
K8S_NODES = [
    # node-a1 is genuinely hot. It is NOT the cause of anything here, and it is
    # seeded precisely so that "find the unhealthy node" is not the same task as
    # "find the worst-looking number" (F5: chaos must be solvable, not cruel).
    ('node-a1', 'True', 'Ready', 'kubelet is posting ready status', 91, 44,
     'zone=us-east-1a', '5.15.0-91-generic', ''),
    ('node-a2', 'True', 'Ready', 'kubelet is posting ready status', 38, 51,
     'zone=us-east-1a', '5.15.0-91-generic',
     # AIOpsLab operator_invalid_affinity_toleration: the node is fine and the
     # workload is fine; the spec simply does not tolerate what the node carries.
     'workload=batch:NoSchedule'),
    ('node-b3', 'True', 'DiskPressure',
     'kubelet has disk pressure: ephemeral storage 97% of 200Gi used', 40, 97,
     'zone=us-east-1b', '5.15.0-91-generic', ''),
    ('node-c1', 'Unknown', 'KernelDeadlock',
     'kernel: BUG: soft lockup - CPU#3 stuck for 23s; kubelet stopped posting node status 14m ago',
     12, 33, 'zone=us-east-1c', '5.15.0-88-generic', ''),
]

# service, desired_replicas, ready_replicas, strategy, storage_class
K8S_DEPLOYMENTS = [
    ('analytics-worker', 2, 1, 'RollingUpdate', 'standard'),
    ('api-gateway', 3, 3, 'RollingUpdate', 'standard'),
    ('catalog', 3, 3, 'RollingUpdate', 'standard'),
    # --- AIOpsLab operator_overload_replicas: a spec asking for more than the
    # cluster can hold. 64 requested, 6 admitted, and the deployment reports no
    # error of its own - the shortfall only exists as a gap between two numbers.
    ('checkout', 64, 6, 'RollingUpdate', 'standard'),
    # --- AIOpsLab operator_non_existent_storage: storageClassName names a class
    # that does not exist, so the claim never binds and the pod never schedules.
    ('inventory', 2, 1, 'RollingUpdate', 'fast-ssd-gp4'),
    # --- AIOpsLab operator_wrong_update_strategy: Recreate tears every replica
    # down before starting the new ones, so each release is a full outage
    # window rather than a rollout. Nothing is failing right now.
    ('media-service', 2, 2, 'Recreate', 'standard'),
    ('notifications', 2, 2, 'RollingUpdate', 'standard'),
    ('payments', 3, 3, 'RollingUpdate', 'standard'),
    ('search', 3, 3, 'RollingUpdate', 'standard'),
    ('storefront-web', 4, 4, 'RollingUpdate', 'standard'),
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
    # node-level faults surface here and nowhere else: the affected services'
    # own logs and metrics show only the symptom.
    (9005, 'production', 'media-service-2e4f-ee55', 'Evicted',
     'The node was low on resource: ephemeral-storage. Container media was using 4Gi', 3, 420),
    (9006, 'production', 'search-reindex-8c2a-gg77', 'FailedScheduling',
     "0/4 nodes are available: 4 node(s) didn't match Pod's node affinity/selector", 214, 419),
    (9007, 'production', 'notifications-1b7d-hh88', 'NodeNotReady',
     'Node node-c1 status is now: NodeNotReady', 1, 420),
    (9008, 'production', 'inventory-migrator-4d9e-ii99', 'Failed',
     'Error: container has runAsNonRoot and image will run as root', 96, 418),
]

# Which acts a human must sign off on. Drawn from the corpus rule that the
# trigger is irreversibility, not difficulty.
APPROVAL_POLICY = [
    (501, "delete_customer_data", "data-protection-officer",
     "irreversible and subject to retention law; no rollback exists"),
    (502, "retire_endpoint_with_live_traffic", "service-owner",
     "drops in-flight customer requests; cannot be undone once clients fail"),
    (503, "rotate_production_credential", "security-lead",
     "invalidates every existing session; a mistake locks out production"),
    (504, "force_promote_unhealthy_canary", "incident-commander",
     "knowingly ships a regression to all users"),
    (505, "drop_database_column", "service-owner",
     "forward-only migration; the data cannot be recovered after the drop"),
]

# The gateway v5.1.0 incident, seen through the alerting chain. One failure
# produced six firings across four rules; two were silenced by a stale silence
# that outlived its window, one was inhibited by the cluster-level rule, and
# three grouped into a single page. "How many alerts did this cause" has four
# defensible answers depending on where you stand in the chain.
ALERT_RULES = [
    (601, "GatewayHighLatency", "gateway_service",
     "histogram_quantile(0.99, gateway_latency) > 250", "critical", "service", "EP-Platform"),
    (602, "GatewayErrorRate", "gateway_service",
     "rate(gateway_errors[5m]) > 0.01", "high", "service", "EP-Platform"),
    (603, "ClusterWideLatency", "", "avg(latency) by (cluster) > 400", "critical",
     "cluster", "EP-Platform"),
    (604, "EdgeCacheHitRate", "edge_cache_service",
     "cache_hit_ratio{tier=\"gateway-edge\"} < 0.8", "medium", "service", "EP-Platform"),
    (605, "LegacyCheckoutQueueDepth", "checkout_legacy_worker",
     "queue_depth > 1000", "high", "service", "EP-Commerce"),
]
ALERT_FIRINGS = [
    (701, 601, "gw-latency-p99", 416, 0, None, 5103),
    (702, 601, "gw-latency-p99", 417, 0, None, 5103),
    (703, 602, "gw-error-rate", 416, 0, 603, None),
    (704, 603, "cluster-latency", 416, 0, None, 5103),
    (705, 604, "edge-cache-hit", 416, 1, None, None),
    (706, 604, "edge-cache-hit", 417, 1, None, None),
]
ALERT_SILENCES = [
    (801, 'alertname="EdgeCacheHitRate"', "Sam Whitfield",
     "muted during the CDN migration, never lifted", 402),
]

# Four proposals per incident. Exactly one is correct; the rest are the kind of
# plausible-but-wrong suggestion that actually appears in an incident channel -
# masking the symptom, fixing the wrong service, or changing semantics.
REMEDIATION_PROPOSALS = [
    # --- payments error rate (root cause: notifications_retry_max_attempts=0)
    (101, "payments-error-rate", "Priya Nair",
     "Raise the notifications timeout from 30s to 60s",
     "Give the downstream longer to answer so fewer calls time out."),
    (102, "payments-error-rate", "Diego Ramos",
     "Set notifications_retry_max_attempts to 3 per the retry standard",
     "A single downstream timeout currently fails the payment permanently because "
     "no retry is attempted. The standard requires 3 attempts with backoff."),
    (103, "payments-error-rate", "Sam Whitfield",
     "Make the notifications call fire-and-forget",
     "Drop the response entirely so a slow downstream cannot fail a payment."),
    (104, "payments-error-rate", "Nina Kowalski",
     "Scale the notifications service to more replicas",
     "Add capacity so notifications answers faster."),
    # --- analytics worker OOMKill (root cause: memory_limit_mb too low for prefetch)
    (201, "analytics-oom", "Alex Osei",
     "Raise the container memory limit from 512Mi to 2Gi",
     "The container is killed at its limit; give it more headroom."),
    (202, "analytics-oom", "Priya Nair",
     "Bound the queue prefetch so the consumer stops pulling the whole backlog",
     "prefetch_count=0 means unlimited prefetch, so the consumer loads the entire "
     "backlog into memory and is OOMKilled. Bounding it fixes the cause; raising "
     "the limit only moves the threshold."),
    (203, "analytics-oom", "Tom Becker",
     "Add a restart policy with exponential backoff",
     "Let it crash more gracefully so the restarts are less noisy."),
    (204, "analytics-oom", "Lena Ortiz",
     "Disable the analytics rollup until the next sprint",
     "Turn the consumer off so it stops paging us."),
    # --- gateway latency (root cause: bad release v5.1.0)
    (301, "gateway-latency", "Mei Tanaka",
     "Increase the gateway rate limit so requests queue less",
     "Raise rate_limit_rps to let more traffic through."),
    (302, "gateway-latency", "Ravi Shah",
     "Add more gateway replicas to absorb the latency",
     "Horizontal scale until p99 comes down."),
    (303, "gateway-latency", "Priya Nair",
     "Roll production back to v5.0.9",
     "p99 moved from 120ms to 1030ms at the exact moment v5.1.0 was promoted, and "
     "the pool in that release opens a connection per request without releasing "
     "it. Every version at or above v5.1.0 carries the leak, so rolling forward "
     "does not recover it."),
    (304, "gateway-latency", "Jordan Blake",
     "Raise the latency SLO to 1200ms while we investigate",
     "Stop the alarm firing so the team can work uninterrupted."),
    # --- checkout error spike (root cause: instant_refunds flag)
    (401, "checkout-errors", "Diego Ramos",
     "Disable the instant_refunds flag in production",
     "The error rate tracks the flag ramp exactly, and the refund path dereferences "
     "a missing record. The flag is a runtime toggle, so this mitigates immediately "
     "without a deploy."),
    (402, "checkout-errors", "Sam Whitfield",
     "Roll back the last checkout deploy",
     "Revert to the previous version to clear the errors."),
    (403, "checkout-errors", "Nina Kowalski",
     "Add a null check and ship a hotfix",
     "Patch the dereference and deploy through the normal pipeline."),
    (404, "checkout-errors", "Lena Ortiz",
     "Increase the checkout payments timeout",
     "Give payments longer so checkout stops erroring."),
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


# --- AIOpsLab revoke_auth_mongodb / user_unregistered_mongodb -----------------
# The service is healthy, the datastore is healthy, and the grant between them
# is not. Nothing in either component's own metrics shows it.
DB_GRANTS = [
    (9901, 'payments', 'pg-primary', 'payments_rw', 'active', 390, ''),
    (9902, 'checkout', 'pg-primary', 'checkout_rw', 'active', 390, ''),
    (9903, 'catalog', 'pg-replica', 'catalog_ro', 'active', 390, ''),
    (9904, 'search', 'pg-replica', 'search_ro', 'active', 390, ''),
    # revoke_auth: the credential was rotated on day 418 and the grant for the
    # OLD role was dropped, but analytics-worker still authenticates with it.
    (9905, 'analytics-worker', 'pg-replica', 'analytics_ro', 'revoked', 418,
     'role dropped during the day-418 credential rotation; the running pods were '
     'never restarted and still present the old role'),
    # user_unregistered: the role was never created for this service at all. It
    # has never worked, and nobody noticed because the job is nightly.
    (9906, 'inventory', 'pg-replica', 'inventory_ro', 'missing', 0,
     'no such role on pg-replica; the reporting job has never successfully '
     'connected since it was added'),
    (9907, 'notifications', 'rabbitmq', 'notify_pub', 'active', 390, ''),
    (9908, 'analytics-worker', 'rabbitmq', 'analytics_sub', 'active', 390, ''),
]

# --- AIOpsLab astronomy_shop_ad_service_manual_gc -----------------------------
# A runtime spending its time collecting garbage looks, from outside, exactly
# like a slow service. catalog is the JVM service here.
RUNTIME_STATS = [
    ('storefront-web', 41, 12, 3, 48),
    ('api-gateway', 55, 18, 5, 120),
    ('checkout', 47, 22, 6, 96),
    ('payments', 38, 15, 4, 80),
    ('catalog', 94, 780, 41, 64),     # heap nearly full, long pauses, constant GC
    ('search', 61, 25, 7, 72),
    ('inventory', 52, 31, 8, 60),
    ('media-service', 44, 19, 5, 56),
    ('notifications', 35, 14, 4, 40),
    ('analytics-worker', 88, 120, 22, 32),
]

# --- AIOpsLab astronomy_shop_payment_service_unreachable ----------------------
# The path is refused, not slow. A timeout looks like load; a refusal does not.
NETWORK_PATHS = [
    (9951, 'checkout', 'payments', 'open', 419, ''),
    (9952, 'checkout', 'inventory', 'open', 419, ''),
    (9953, 'api-gateway', 'checkout', 'open', 419, ''),
    (9954, 'api-gateway', 'search', 'open', 419, ''),
    (9955, 'notifications', 'rabbitmq', 'open', 419, ''),
    (9956, 'analytics-worker', 'pg-replica', 'refused', 419,
     'connection refused at the transport layer, not a timeout: a network policy '
     'applied on day 418 drops egress from the analytics namespace to the replica'),
    (9957, 'media-service', 's3-assets', 'open', 419, ''),
]
