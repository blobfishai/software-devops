"""Schema DDL and deterministic seed data for the software-devops world.

Curated row ids use the 9000+ range (blobfish convention) so task verifiers
and oracle traces never depend on generated-row counts.
"""

SCHEMA_SQL = """
CREATE TABLE services (
    service_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    team TEXT NOT NULL,
    tier INTEGER NOT NULL,
    language TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    repo_version TEXT NOT NULL
);
CREATE TABLE oncall (
    team TEXT PRIMARY KEY,
    engineer TEXT NOT NULL
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
CREATE TABLE pr_changes (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    payload TEXT NOT NULL
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
CREATE TABLE versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    state_json TEXT NOT NULL,
    UNIQUE (service, version)
);
CREATE TABLE repo_state (
    service TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (service, kind, key)
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
CREATE TABLE metric_rules (
    rule_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    kind TEXT NOT NULL,
    ckey TEXT NOT NULL DEFAULT '',
    cvalue TEXT NOT NULL DEFAULT '',
    value REAL NOT NULL
);
CREATE TABLE slos (
    slo_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    threshold REAL NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE service_metrics (
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (service, environment, metric)
);
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    metric TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'firing',
    message TEXT NOT NULL DEFAULT ''
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
CREATE TABLE runbooks (
    runbook_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE tests_catalog (
    test_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    suite TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'passing',
    quarantined INTEGER NOT NULL DEFAULT 0
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
CREATE TABLE channels (
    channel TEXT PRIMARY KEY,
    purpose TEXT NOT NULL DEFAULT ''
);
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    author TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '{}'
);
"""

ENVIRONMENTS = ("staging", "production")

SERVICES = [
    # service_id, name, team, tier, language, description, repo_version
    (9001, "storefront-web", "growth", 1, "typescript",
     "Customer-facing web storefront (Next.js).", "v3.2.4"),
    (9002, "api-gateway", "platform", 1, "go",
     "Public API edge: routing, auth, rate limiting, traffic weighting.", "v5.1.0"),
    (9003, "catalog", "commerce", 2, "python",
     "Product catalog and pricing service.", "v1.9.2"),
    (9004, "checkout", "commerce", 1, "python",
     "Cart and checkout orchestration.", "v2.6.3"),
    (9005, "payments", "commerce", 1, "python",
     "Payment capture, refunds, and settlement.", "v2.7.0"),
    (9006, "notifications", "platform", 2, "python",
     "Email/SMS/push notification delivery.", "v1.4.8"),
    (9007, "search", "growth", 2, "python",
     "Product search and ranking.", "v3.0.5"),
]

ONCALL = [
    ("platform", "Priya Nair"),
    ("commerce", "Diego Ramos"),
    ("growth", "Mei Tanaka"),
    ("sre", "Alex Osei"),
]

# repo_state: service -> list[(kind, key, value)]
REPO_STATE = {
    "storefront-web": [
        ("config", "ab_test_bucket", "b"),
        ("module", "homepage", "present"),
        ("module", "product_page", "present"),
    ],
    "api-gateway": [
        ("config", "rate_limit_rps", "500"),
        ("endpoint", "/v1/orders", "active"),
        ("endpoint", "/v2/orders", "active"),
        ("endpoint", "/v1/checkout", "active"),
        ("endpoint", "/internal/debug", "active"),
    ],
    "catalog": [
        ("config", "cdn_enabled", "true"),
        ("module", "product_listing", "present"),
    ],
    "checkout": [
        ("config", "payment_timeout_ms", "8000"),
        ("dependency", "stripe-sdk", "11.2.0"),
        ("module", "cart", "present"),
        ("module", "checkout_flow", "present"),
    ],
    "payments": [
        ("config", "notifications_retry_max_attempts", "0"),
        ("config", "notifications_timeout_ms", "30000"),
        ("config", "db_pool_size", "20"),
        ("dependency", "libpayproc", "2.3.1"),
        ("dependency", "requests", "2.32.3"),
        ("module", "payment_capture", "present"),
        ("module", "refund_flow", "present"),
    ],
    "notifications": [
        ("config", "smtp_pool", "8"),
    ],
    "search": [
        ("config", "cache_enabled", "false"),
        ("config", "cache_ttl_s", "300"),
        ("config", "index_shards", "4"),
    ],
}

# Traffic weights live only in production env_state (runtime gateway config).
PRODUCTION_TRAFFIC = {
    "api-gateway": [
        ("/v1/orders", "100"),
        ("/v2/orders", "0"),
        ("/v1/checkout", "100"),
        ("/internal/debug", "0"),
    ],
}

# Extra historical versions (beyond each service's current repo_version).
# api-gateway v5.0.9 is the known-good release the SEV1 task rolls back to.
EXTRA_VERSIONS = {
    "api-gateway": ["v5.0.9"],
}

FEATURE_FLAGS = [
    # flag_id, key, service, description, environment, enabled, rollout_percent
    (9301, "instant_refunds", "checkout",
     "Pilot: refund immediately at checkout instead of async batch.", "production", 1, 100),
    (9302, "instant_refunds", "checkout",
     "Pilot: refund immediately at checkout instead of async batch.", "staging", 1, 100),
    (9303, "new_search_ui", "search",
     "Redesigned search results page.", "production", 0, 0),
    (9304, "new_search_ui", "search",
     "Redesigned search results page.", "staging", 1, 100),
]

METRIC_RULES = [
    # rule_id, service, metric, kind, ckey, cvalue, value
    (9401, "payments", "error_rate_pct", "base", "", "", 0.4),
    (9402, "payments", "error_rate_pct", "config_eq", "notifications_retry_max_attempts", "0", 3.8),
    (9403, "search", "latency_p99_ms", "base", "", "", 210.0),
    (9404, "search", "latency_p99_ms", "config_eq", "cache_enabled", "false", 640.0),
    (9405, "checkout", "error_rate_pct", "base", "", "", 0.3),
    (9406, "checkout", "error_rate_pct", "flag_enabled", "instant_refunds", "", 5.2),
    (9407, "api-gateway", "latency_p99_ms", "base", "", "", 120.0),
    # version_ge (not eq): the goroutine leak is in v5.1.0 AND any version cut
    # on top of it — only a genuine rollback to v5.0.9 recovers latency.
    (9408, "api-gateway", "latency_p99_ms", "version_ge", "", "v5.1.0", 910.0),
    (9409, "payments", "latency_p99_ms", "base", "", "", 95.0),
    (9410, "checkout", "latency_p99_ms", "base", "", "", 180.0),
    (9411, "api-gateway", "error_rate_pct", "base", "", "", 0.2),
    (9412, "search", "error_rate_pct", "base", "", "", 0.1),
]

SLOS = [
    # slo_id, service, metric, threshold, description
    (9501, "payments", "error_rate_pct", 1.0, "Payments requests must succeed 99% of the time."),
    (9502, "search", "latency_p99_ms", 300.0, "Search p99 latency under 300ms."),
    (9503, "checkout", "error_rate_pct", 1.0, "Checkout requests must succeed 99% of the time."),
    (9504, "api-gateway", "latency_p99_ms", 250.0, "Gateway p99 latency under 250ms."),
    (9505, "payments", "latency_p99_ms", 200.0, "Payments p99 latency under 200ms."),
    (9506, "checkout", "latency_p99_ms", 400.0, "Checkout p99 latency under 400ms."),
]

ALERTS = [
    # alert_id, service, metric, severity, status, message
    (9601, "payments", "error_rate_pct", "high", "firing",
     "payments error_rate_pct 4.2 exceeds SLO 1.0"),
    (9602, "search", "latency_p99_ms", "medium", "firing",
     "search latency_p99_ms 850.0 exceeds SLO 300.0"),
    (9603, "checkout", "error_rate_pct", "high", "firing",
     "checkout error_rate_pct 5.5 exceeds SLO 1.0"),
    (9604, "api-gateway", "latency_p99_ms", "critical", "firing",
     "api-gateway latency_p99_ms 1030.0 exceeds SLO 250.0"),
]

INCIDENTS = [
    # incident_id, severity, title, service, status, commander
    (9701, "sev1", "API gateway latency surge after v5.1.0 rollout", "api-gateway", "open", ""),
    (9702, "sev2", "Checkout error spike since instant_refunds ramp", "checkout", "open", ""),
]

TICKETS = [
    # ticket_id, key, type, title, description, status, priority, assignee, service
    (9101, "ENG-2101", "bug", "Reduce payments error rate breaching SLO",
     "payments error_rate_pct has been breaching its 1.0% SLO for two days (alert 9601). "
     "Investigate production logs to find the root cause, fix it through the standard "
     "PR -> CI -> merge -> staged deployment workflow (see the 'Deployment policy' runbook: "
     "staging first, tier-1 services canary at <=25% then promote), confirm the metric "
     "recovered, resolve the alert, and close this ticket.",
     "open", "high", "", "payments"),
    (9102, "ENG-2102", "bug", "Search p99 latency exceeds SLO",
     "search latency_p99_ms is 850ms against a 300ms SLO (alert 9602). Find the root cause "
     "(see logs and the 'Search caching' runbook), ship the fix staging-first, confirm "
     "recovery, resolve the alert, and close this ticket.",
     "open", "high", "", "search"),
    (9103, "ENG-2201", "feature", "Ship express checkout behind a feature flag at 10% production rollout",
     "Implement the express_checkout module in the checkout service gated behind a NEW "
     "feature flag named 'express_checkout' (define the flag in the same PR with a 'flag' "
     "change). Per the 'Feature flags' runbook the code must be deployed to production "
     "(staging first, canary then promote — checkout is tier 1) BEFORE the flag is enabled. "
     "Then enable the flag in production at a 10% rollout. Close this ticket when done.",
     "open", "medium", "", "checkout"),
    (9104, "ENG-2202", "incident", "Disable instant_refunds and resolve checkout error spike",
     "Incident 9702 (sev2): checkout error_rate_pct jumped to 5.5% right after the "
     "instant_refunds flag ramped to 100% in production. Per the 'Incident response' "
     "runbook: acknowledge the alert, kill-switch the flag in production (leave staging "
     "as-is), verify the metric recovered, resolve the alert and the incident, post an "
     "update in #incidents mentioning instant_refunds, and close this ticket.",
     "open", "critical", "", "checkout"),
    (9105, "SEC-901", "security", "Patch CVE-2026-31337 in libpayproc (payments)",
     "Security scanner reports libpayproc 2.3.1 in payments is vulnerable to "
     "CVE-2026-31337 (critical). Upgrade the dependency to the fixed version 2.4.0 via "
     "the standard workflow, deploy staging-first (payments is tier 1: canary then "
     "promote), confirm the scanner shows the vulnerability remediated, post an audit "
     "summary to #security referencing the CVE, and close this ticket.",
     "open", "critical", "", "payments"),
    (9106, "SEC-902", "security", "Retire exposed /internal/debug endpoint on api-gateway",
     "A security review found the unauthenticated /internal/debug endpoint still active "
     "in production on api-gateway. Retire it via an endpoint PR change and deploy "
     "staging-first (api-gateway is tier 1: canary then promote). Close this ticket.",
     "open", "high", "", "api-gateway"),
    (9107, "ENG-2301", "feature", "Loyalty points across catalog, checkout, and storefront-web",
     "Ship the loyalty-points feature: add module 'loyalty_accrual' to catalog, module "
     "'loyalty_redeem' to checkout, and module 'loyalty_widget' to storefront-web (one PR "
     "per service). Deployment order matters: catalog must reach production before "
     "checkout, and checkout before storefront-web. Every production deploy is "
     "staging-first; checkout and storefront-web are tier 1 (canary <=25% then promote). "
     "Close this ticket when all three are live.",
     "open", "medium", "", ""),
    (9108, "ENG-2302", "feature", "Migrate /v1/orders traffic to /v2/orders and retire v1",
     "Per the 'API deprecation' runbook: mark /v1/orders deprecated (endpoint PR change) "
     "and deploy that to production first; then shift traffic from /v1/orders to "
     "/v2/orders in stages of at most 50 percentage points per step until /v2/orders "
     "serves 100% and /v1/orders serves 0%; only then retire /v1/orders with a second PR "
     "and deploy it. api-gateway is tier 1 (staging first, canary then promote). Close "
     "this ticket when v1 is retired in production.",
     "open", "medium", "", "api-gateway"),
    (9109, "ENG-2401", "bug", "Fix flaky test_checkout_idempotency; prove 3 consecutive green main runs",
     "checkout CI is unreliable: test_checkout_idempotency fails intermittently (see CI "
     "history). Fix the root cause via a PR with a test_fix change (action 'fix' — do NOT "
     "just quarantine it), merge it, then demonstrate stability with at least 3 "
     "consecutive green main-branch CI runs (run_ci with service='checkout'). Close this "
     "ticket.",
     "open", "high", "", "checkout"),
    (9110, "ENG-2402", "incident", "SEV1: roll back api-gateway v5.1.0 and file postmortem",
     "Incident 9701 (sev1): api-gateway p99 latency jumped to ~1030ms right after v5.1.0 "
     "was promoted in production. Per the 'Incident response' runbook: acknowledge the "
     "alert, roll back the production deployment, verify the metric recovered, resolve "
     "the alert and the incident, create a postmortem ticket (type 'postmortem', service "
     "api-gateway, mention v5.1.0), post an update in #incidents, and close this ticket.",
     "open", "critical", "", "api-gateway"),
]

VULNERABILITIES = [
    (9801, "CVE-2026-31337", "libpayproc", "payments", "critical", "2.4.0", "open"),
]

TESTS = [
    # test_id, service, suite, name, status, quarantined
    (9901, "checkout", "unit", "test_cart_totals", "passing", 0),
    (9902, "checkout", "integration", "test_checkout_idempotency", "flaky", 0),
    (9903, "payments", "unit", "test_capture_retries", "passing", 0),
    (9904, "search", "unit", "test_ranking", "passing", 0),
]

LOGS = [
    # log_id, service, environment, level, message
    (9010, "payments", "production", "ERROR",
     "ConnectionTimeout calling notifications after 30000ms - request failed permanently "
     "(retry_max_attempts=0, no retry attempted); order marked failed"),
    (9011, "payments", "production", "ERROR",
     "ConnectionTimeout calling notifications after 30000ms - request failed permanently "
     "(retry_max_attempts=0, no retry attempted); order marked failed"),
    (9012, "payments", "production", "INFO",
     "startup config: notifications_retry_max_attempts=0 notifications_timeout_ms=30000 db_pool_size=20"),
    (9013, "search", "production", "WARN",
     "query cache disabled (cache_enabled=false); every request is hitting the primary index"),
    (9014, "api-gateway", "production", "ERROR",
     "p99 latency 1030ms; regression began immediately after deploy v5.1.0 "
     "(suspected goroutine leak in upstream connection pool)"),
    (9015, "checkout", "production", "ERROR",
     "refund worker panic: nil pointer in instant_refunds path; errors correlate 1:1 with "
     "feature flag instant_refunds=enabled"),
    (9016, "checkout", "production", "WARN",
     "CI: test_checkout_idempotency failed on run #142, passed on rerun #143 - "
     "nondeterministic idempotency-key collision in test fixture"),
    (9017, "notifications", "production", "INFO",
     "delivery queue healthy; smtp_pool=8"),
]

RUNBOOKS = [
    (9951, "Retry policy standard",
     "All cross-service calls MUST configure retries: set config key "
     "'<downstream>_retry_max_attempts' to 3 (exponential backoff is applied "
     "automatically). A value of 0 means a single downstream timeout permanently fails "
     "the request."),
    (9952, "Deployment policy",
     "Every production deploy must first succeed on staging (same version). Tier-1 "
     "services (storefront-web, api-gateway, checkout, payments) must additionally "
     "canary in production at <=25% (deploy_service with canary_percent<=25) and promote "
     "with promote_canary only after verification. Use rollback_deployment for emergency "
     "rollback; rollbacks are exempt from the staging-first rule."),
    (9953, "Search caching",
     "cache_enabled=true is required in production for the search service; the query "
     "cache absorbs ~75% of index load. TTL standard is 300s."),
    (9954, "Incident response",
     "1) acknowledge the firing alert 2) mitigate (rollback or feature-flag kill switch) "
     "3) verify metric recovery 4) resolve the alert 5) resolve the incident 6) post an "
     "update in #incidents 7) for sev1: file a postmortem ticket (type 'postmortem')."),
    (9955, "API deprecation",
     "Deprecate the endpoint first (status 'deprecated') and deploy that change. Then "
     "shift traffic to the replacement in stages of at most 50 percentage points per "
     "step. Only when the legacy endpoint serves 0% traffic may it be retired (status "
     "'retired'); CI blocks retirement of endpoints still serving traffic."),
    (9956, "Security response",
     "Patch the vulnerable dependency, deploy staging then production, verify the "
     "scanner shows the finding remediated, post an audit summary to #security "
     "referencing the CVE id, and close the security ticket."),
    (9957, "Feature flags",
     "New user-facing features ship dark behind a flag (define the flag via a 'flag' PR "
     "change; it is created disabled in both environments at merge). The guarded code "
     "must be deployed to production BEFORE the flag is enabled there. Initial "
     "production rollout must not exceed 10%. Flags are runtime toggles: "
     "set_feature_flag needs no deploy."),
    (9958, "Flaky tests",
     "Diagnose from CI history (list_ci_runs). Fix the root cause via a PR with a "
     "test_fix change (action 'fix'); quarantine (action 'quarantine') is a last resort "
     "and does not close the ticket. After merging, prove stability with 3 consecutive "
     "green main-branch runs: run_ci(service=...)."),
]

CHANNELS = [
    ("#incidents", "Incident coordination and status updates."),
    ("#security", "Security advisories and audit notes."),
    ("#eng", "General engineering."),
]

MESSAGES = [
    ("#incidents", "Priya Nair",
     "Declared incident 9701 (sev1): api-gateway p99 through the roof since the v5.1.0 promote."),
    ("#incidents", "Diego Ramos",
     "Incident 9702 (sev2): checkout error rate tracks the instant_refunds ramp exactly."),
    ("#eng", "Mei Tanaka",
     "Reminder: deployment policy = staging first; tier-1 canary at 25% then promote."),
]

# Seeded PRs: history only. Next PR number is deterministically 9203.
PULL_REQUESTS = [
    # number, service, title, body, author, ticket_key, status, merged_version
    (9201, "api-gateway", "Connection pool rewrite", "Perf: new upstream pool.",
     "Priya Nair", "", "merged", "v5.1.0"),
    (9202, "catalog", "Price rounding cleanup", "Draft, do not merge yet.",
     "Diego Ramos", "", "open", ""),
]

# Seeded CI history. checkout has exactly TWO prior runs, so with the flake rule
# "fails when (count of prior runs for the service) % 2 == 0" the next checkout
# run fails, then passes — deterministic intermittence.
CI_RUNS = [
    # service, pr_number(None for main), status, detail
    ("api-gateway", 9201, "passed", "all checks passed"),
    ("checkout", None, "failed", "intermittent failure: test_checkout_idempotency (rerun may pass)"),
    ("checkout", None, "passed", "all checks passed"),
    ("payments", None, "passed", "all checks passed"),
]

# Seeded deployment history (explicit ids). api-gateway shows the bad v5.1.0
# rollout preceded by the known-good v5.0.9 in production.
DEPLOYMENTS = [
    # deployment_id, service, environment, version, status, canary_percent
    (9251, "storefront-web", "staging", "v3.2.4", "succeeded", 100),
    (9252, "storefront-web", "production", "v3.2.4", "succeeded", 100),
    (9253, "api-gateway", "staging", "v5.0.9", "succeeded", 100),
    (9254, "api-gateway", "production", "v5.0.9", "succeeded", 100),
    (9255, "catalog", "staging", "v1.9.2", "succeeded", 100),
    (9256, "catalog", "production", "v1.9.2", "succeeded", 100),
    (9257, "checkout", "staging", "v2.6.3", "succeeded", 100),
    (9258, "checkout", "production", "v2.6.3", "succeeded", 100),
    (9259, "payments", "staging", "v2.7.0", "succeeded", 100),
    (9260, "payments", "production", "v2.7.0", "succeeded", 100),
    (9261, "notifications", "staging", "v1.4.8", "succeeded", 100),
    (9262, "notifications", "production", "v1.4.8", "succeeded", 100),
    (9263, "search", "staging", "v3.0.5", "succeeded", 100),
    (9264, "search", "production", "v3.0.5", "succeeded", 100),
    (9265, "api-gateway", "staging", "v5.1.0", "succeeded", 100),
    (9266, "api-gateway", "production", "v5.1.0", "succeeded", 100),
]

PERSONAS = [
    {
        "persona_id": "persona_priya", "name": "Priya Nair", "role": "sre",
        "department": "platform", "seniority": "senior",
        "communication_style": "direct", "technical_level": "expert",
        "domain_knowledge": ["deployments", "incident response", "observability"],
        "common_tasks": ["rollback", "alert triage", "canary analysis"],
    },
    {
        "persona_id": "persona_diego", "name": "Diego Ramos", "role": "staff_engineer",
        "department": "commerce", "seniority": "staff",
        "communication_style": "professional", "technical_level": "expert",
        "domain_knowledge": ["payments", "checkout", "reliability patterns"],
        "common_tasks": ["code review", "SLO remediation", "dependency upgrades"],
    },
    {
        "persona_id": "persona_mei", "name": "Mei Tanaka", "role": "staff_engineer",
        "department": "growth", "seniority": "staff",
        "communication_style": "concise", "technical_level": "expert",
        "domain_knowledge": ["search", "frontend", "feature flags"],
        "common_tasks": ["feature rollout", "A/B experiments", "performance tuning"],
    },
    {
        "persona_id": "persona_jordan", "name": "Jordan Blake", "role": "engineering_manager",
        "department": "engineering", "seniority": "senior",
        "communication_style": "supportive", "technical_level": "advanced",
        "domain_knowledge": ["process", "postmortems", "ticket hygiene"],
        "common_tasks": ["incident review", "backlog triage"],
    },
]

TIER1_SERVICES = ("storefront-web", "api-gateway", "checkout", "payments")
