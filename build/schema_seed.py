"""Schema DDL and deterministic seed for the software-devops world (v2).

Mirrors the Horizon-SWE environment: an editable monorepo with commit history,
a full application stack (frontend, backend services, workers, database, cache,
queue, object store, CDN), a traffic generator, an issue tracker, a knowledge
base, communication tools, deployment tooling with migrations and canaries,
logs, metrics, alarms, error tracking, and a public status page.

Curated ids use the 9000+ range so verifiers never depend on generated rows.
"""

SCHEMA_SQL = """
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
CREATE TABLE infra_components (
    component_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'healthy',
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE service_dependencies (
    service TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (service, depends_on)
);
CREATE TABLE oncall (
    team TEXT PRIMARY KEY,
    engineer TEXT NOT NULL
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
CREATE TABLE documents (
    doc_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    day INTEGER NOT NULL DEFAULT 0,
    body TEXT NOT NULL
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
CREATE TABLE ci_stages (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
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
CREATE TABLE canary_assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    verdict TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    name TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (service, name, environment)
);
CREATE TABLE versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    state_json TEXT NOT NULL,
    requires_migration TEXT NOT NULL DEFAULT '',
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
CREATE TABLE traffic_profile (
    route_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    route TEXT NOT NULL,
    rps INTEGER NOT NULL,
    share_pct INTEGER NOT NULL DEFAULT 100
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
CREATE TABLE status_page (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT ''
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
CREATE TABLE logs (
    log_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production',
    level TEXT NOT NULL,
    message TEXT NOT NULL
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
CREATE TABLE migration_requirements (
    req_id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    module TEXT NOT NULL,
    migration_name TEXT NOT NULL
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
CREATE TABLE audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '{}'
);
"""

# Modules whose schema change needs a migration in the same PR. Forgetting one
# fails the CI build stage with "missing database migration".
MIGRATION_REQUIREMENTS = [
    (9151, "checkout", "loyalty_redeem", "0088_loyalty_ledger"),
    (9152, "catalog", "loyalty_accrual", "0123_loyalty_points"),
    (9153, "payments", "split_settlement", "0042_settlement_splits"),
    (9154, "inventory", "backorder_queue", "0034_backorders"),
    (9155, "checkout", "saved_carts", "0089_saved_carts"),
]

# Retiring a producer endpoint regresses a consumer still pinned to it.
CONTRACT_RULES = [
    (9161, "api-gateway", "/v1/orders", "storefront-web", "orders_api_version", "v2",
     "regression: storefront-web still calls the orders API via orders_api_version=v1 - "
     "migrate the consumer to v2 and deploy it before retiring /v1/orders"),
    (9162, "api-gateway", "/v1/auth", "storefront-web", "auth_api_version", "v2",
     "regression: storefront-web still calls the auth API via auth_api_version=v1 - "
     "migrate the consumer to v2 and deploy it before retiring /v1/auth"),
    (9163, "api-gateway", "/v1/checkout", "storefront-web", "checkout_api_version", "v2",
     "regression: storefront-web still calls the checkout API via checkout_api_version=v1 - "
     "migrate the consumer to v2 and deploy it before retiring /v1/checkout"),
]

ENVIRONMENTS = ("staging", "production")

# service_id, name, kind, team, tier, language, description, repo_version
SERVICES = [
    (9001, "storefront-web", "frontend", "growth", 1, "typescript",
     "Customer-facing storefront (Next.js): browse, cart, checkout UI.", "v3.2.4"),
    (9002, "api-gateway", "backend", "platform", 1, "go",
     "Public API edge: routing, auth, rate limiting, traffic weighting.", "v5.1.0"),
    (9003, "catalog", "backend", "commerce", 2, "python",
     "Product catalog, pricing, and merchandising.", "v1.9.2"),
    (9004, "checkout", "backend", "commerce", 1, "python",
     "Cart and checkout orchestration.", "v2.6.3"),
    (9005, "payments", "backend", "commerce", 1, "python",
     "Payment capture, refunds, and settlement.", "v2.7.0"),
    (9006, "notifications", "worker", "platform", 2, "python",
     "Email/SMS/push notification delivery.", "v1.4.8"),
    (9007, "search", "backend", "growth", 2, "python",
     "Product search and ranking.", "v3.0.5"),
    (9008, "inventory", "backend", "commerce", 2, "java",
     "Stock levels, reservations, and warehouse sync.", "v4.3.1"),
    (9009, "media-service", "backend", "growth", 3, "python",
     "Product imagery and video delivery from the object store.", "v0.9.4"),
    (9010, "analytics-worker", "worker", "platform", 3, "python",
     "Consumes the event queue and builds analytics rollups.", "v2.1.7"),
]

TIER1_SERVICES = ("storefront-web", "api-gateway", "checkout", "payments")

# component_id, name, kind, status, detail
INFRA = [
    (9101, "pg-primary", "database", "healthy", "PostgreSQL 16 primary, 400 max connections"),
    (9102, "pg-replica", "database", "healthy", "PostgreSQL 16 read replica, ~40ms lag"),
    (9103, "redis-cache", "cache", "healthy", "Redis 7, 12 GB, LRU eviction"),
    (9104, "rabbitmq", "queue", "healthy", "RabbitMQ 3.13, events + notifications exchanges"),
    (9105, "s3-assets", "object_store", "healthy", "Object store bucket novacart-assets"),
    (9106, "cdn-edge", "cdn", "healthy", "Edge CDN in front of s3-assets and storefront-web"),
]

SERVICE_DEPS = [
    ("storefront-web", "api-gateway", "http"), ("storefront-web", "cdn-edge", "cdn"),
    ("api-gateway", "checkout", "http"), ("api-gateway", "catalog", "http"),
    ("api-gateway", "search", "http"), ("api-gateway", "media-service", "http"),
    ("checkout", "payments", "http"), ("checkout", "inventory", "http"),
    ("checkout", "pg-primary", "database"), ("catalog", "pg-primary", "database"),
    ("catalog", "redis-cache", "cache"), ("payments", "notifications", "http"),
    ("payments", "pg-primary", "database"), ("search", "redis-cache", "cache"),
    ("search", "pg-replica", "database"), ("inventory", "pg-primary", "database"),
    ("notifications", "rabbitmq", "queue"), ("analytics-worker", "rabbitmq", "queue"),
    ("media-service", "s3-assets", "object_store"), ("media-service", "cdn-edge", "cdn"),
]

ONCALL = [
    ("platform", "Priya Nair"), ("commerce", "Diego Ramos"),
    ("growth", "Mei Tanaka"), ("sre", "Alex Osei"),
]

# service -> [(kind, key, value)] at repo HEAD. Mirrored into both envs at seed.
REPO_STATE = {
    "storefront-web": [
        ("config", "ab_test_bucket", "b"),
        ("config", "bundle_analyzer", "false"),
        ("config", "orders_api_version", "v1"),
        ("config", "auth_api_version", "v1"),
        ("config", "checkout_api_version", "v1"),
        ("module", "homepage", "present"), ("module", "product_page", "present"),
        ("module", "cart", "present"),
    ],
    "api-gateway": [
        ("config", "rate_limit_rps", "500"),
        ("config", "upstream_pool_reuse", "false"),
        ("endpoint", "/v1/orders", "active"), ("endpoint", "/v2/orders", "active"),
        ("endpoint", "/v1/checkout", "active"), ("endpoint", "/v2/checkout", "active"),
        ("endpoint", "/v1/auth", "active"), ("endpoint", "/v2/auth", "active"),
        ("endpoint", "/v1/search", "active"), ("endpoint", "/v2/search", "active"),
        ("endpoint", "/v1/media", "active"), ("endpoint", "/v2/media", "active"),
        ("endpoint", "/v1/inventory", "active"), ("endpoint", "/v2/inventory", "active"),
        ("endpoint", "/v1/notify", "active"), ("endpoint", "/v2/notify", "active"),
        ("endpoint", "/internal/debug", "active"), ("endpoint", "/internal/metrics", "active"),
    ],
    "catalog": [
        ("config", "batch_pricing_enabled", "false"),
        ("config", "cdn_enabled", "true"),
        ("config", "catalog_cache_ttl_s", "120"),
        ("dependency", "pydantic", "2.9.2"),
        ("module", "product_listing", "present"),
    ],
    "checkout": [
        ("config", "payments_timeout_ms", "8000"),
        ("config", "payments_retry_max_attempts", "3"),
        ("config", "inventory_timeout_ms", "1500"),
        ("config", "use_secret_manager", "false"),
        ("config", "db_pool_size", "40"),
        ("dependency", "stripe-sdk", "11.2.0"),
        ("module", "cart", "present"), ("module", "checkout_flow", "present"),
    ],
    "payments": [
        ("config", "notifications_retry_max_attempts", "0"),
        ("config", "notifications_timeout_ms", "30000"),
        ("config", "db_pool_size", "20"),
        ("dependency", "libpayproc", "2.3.1"),
        ("dependency", "requests", "2.32.3"),
        ("module", "payment_capture", "present"), ("module", "refund_flow", "present"),
    ],
    "notifications": [
        ("config", "smtp_pool", "8"),
        ("config", "smtp_timeout_ms", "0"),
        ("config", "prefetch_count", "50"),
    ],
    "search": [
        ("config", "cache_enabled", "false"),
        ("config", "cache_ttl_s", "300"),
        ("config", "index_shards", "4"),
        ("module", "ranking", "present"),
    ],
    "inventory": [
        ("config", "db_pool_size", "5"),
        ("config", "reservation_timeout_ms", "2000"),
        ("module", "stock_ledger", "present"),
    ],
    "media-service": [
        ("config", "cdn_enabled", "false"),
        ("config", "thumbnail_sizes", "3"),
        ("module", "asset_delivery", "present"),
    ],
    "analytics-worker": [
        ("config", "prefetch_count", "0"),
        ("config", "batch_size", "500"),
        ("module", "rollup_daily", "present"),
    ],
}

PRODUCTION_TRAFFIC = {
    "api-gateway": [("/v1/orders", "100"), ("/v2/orders", "0"),
                    ("/v1/checkout", "100"), ("/v2/checkout", "0"),
                    ("/v1/auth", "100"), ("/v2/auth", "0"),
                    ("/v1/search", "100"), ("/v2/search", "0"),
                    ("/v1/media", "100"), ("/v2/media", "0"),
                    ("/v1/inventory", "100"), ("/v2/inventory", "0"),
                    ("/v1/notify", "100"), ("/v2/notify", "0"),
                    ("/internal/debug", "0"), ("/internal/metrics", "0")],
}

# route_id, service, route, rps, share_pct — what the traffic generator drives
TRAFFIC_PROFILE = [
    (9201, "storefront-web", "GET /", 420, 100),
    (9202, "storefront-web", "GET /product/:id", 310, 100),
    (9203, "api-gateway", "POST /v1/orders", 145, 100),
    (9204, "api-gateway", "POST /v2/orders", 0, 0),
    (9205, "api-gateway", "POST /v1/checkout", 138, 100),
    (9206, "api-gateway", "POST /v1/auth", 96, 100),
    (9207, "catalog", "GET /products", 260, 100),
    (9208, "search", "GET /search", 180, 100),
    (9209, "payments", "POST /capture", 132, 100),
    (9210, "inventory", "POST /reserve", 128, 100),
    (9211, "media-service", "GET /assets/:key", 240, 100),
    (9212, "notifications", "queue:notifications", 130, 100),
    (9213, "analytics-worker", "queue:events", 900, 100),
]

EXTRA_VERSIONS = {"api-gateway": ["v5.0.9"]}

FEATURE_FLAGS = [
    (9301, "instant_refunds", "checkout",
     "Pilot: refund immediately at checkout instead of async batch.", "production", 1, 100),
    (9302, "instant_refunds", "checkout",
     "Pilot: refund immediately at checkout instead of async batch.", "staging", 1, 100),
    (9303, "new_search_ui", "search", "Redesigned search results page.", "production", 0, 0),
    (9304, "new_search_ui", "search", "Redesigned search results page.", "staging", 1, 100),
    (9305, "legacy_price_rounding", "catalog",
     "Fully rolled out 6 months ago; stale flag pending cleanup.", "production", 1, 100),
    (9306, "legacy_price_rounding", "catalog",
     "Fully rolled out 6 months ago; stale flag pending cleanup.", "staging", 1, 100),
    (9307, "checkout_v2_layout", "checkout",
     "Checkout redesign, fully rolled out last quarter; stale flag.", "production", 1, 100),
    (9308, "checkout_v2_layout", "checkout",
     "Checkout redesign, fully rolled out last quarter; stale flag.", "staging", 1, 100),
]

# rule_id, service, metric, kind, ckey, cvalue, value
METRIC_RULES = [
    (9401, "payments", "error_rate_pct", "base", "", "", 0.4),
    (9402, "payments", "error_rate_pct", "config_eq", "notifications_retry_max_attempts", "0", 3.8),
    (9403, "search", "latency_p99_ms", "base", "", "", 210.0),
    (9404, "search", "latency_p99_ms", "config_eq", "cache_enabled", "false", 640.0),
    (9405, "checkout", "error_rate_pct", "base", "", "", 0.3),
    (9406, "checkout", "error_rate_pct", "flag_enabled", "instant_refunds", "", 5.2),
    (9407, "api-gateway", "latency_p99_ms", "base", "", "", 120.0),
    (9408, "api-gateway", "latency_p99_ms", "version_ge", "", "v5.1.0", 910.0),
    (9409, "payments", "latency_p99_ms", "base", "", "", 95.0),
    (9410, "checkout", "latency_p99_ms", "base", "", "", 180.0),
    (9411, "api-gateway", "error_rate_pct", "base", "", "", 0.2),
    (9412, "search", "error_rate_pct", "base", "", "", 0.1),
    (9413, "catalog", "latency_p99_ms", "base", "", "", 140.0),
    (9414, "catalog", "latency_p99_ms", "config_eq", "batch_pricing_enabled", "false", 505.0),
    (9415, "catalog", "error_rate_pct", "base", "", "", 0.2),
    (9416, "inventory", "error_rate_pct", "base", "", "", 0.3),
    (9417, "inventory", "error_rate_pct", "config_lt", "db_pool_size", "20", 4.4),
    (9418, "inventory", "latency_p99_ms", "base", "", "", 160.0),
    (9419, "media-service", "latency_p99_ms", "base", "", "", 180.0),
    (9420, "media-service", "latency_p99_ms", "config_eq", "cdn_enabled", "false", 620.0),
    (9421, "media-service", "error_rate_pct", "base", "", "", 0.2),
    (9422, "notifications", "error_rate_pct", "base", "", "", 0.5),
    (9423, "notifications", "error_rate_pct", "config_eq", "smtp_timeout_ms", "0", 3.1),
    (9424, "notifications", "latency_p99_ms", "base", "", "", 240.0),
    (9425, "analytics-worker", "error_rate_pct", "base", "", "", 0.4),
    (9426, "analytics-worker", "error_rate_pct", "config_eq", "prefetch_count", "0", 5.6),
    (9427, "analytics-worker", "latency_p99_ms", "base", "", "", 300.0),
    (9428, "storefront-web", "latency_p99_ms", "base", "", "", 220.0),
    (9429, "storefront-web", "error_rate_pct", "base", "", "", 0.2),
]

# slo_id, service, metric, threshold, description
SLOS = [
    (9501, "payments", "error_rate_pct", 1.0, "Payments succeed 99% of the time."),
    (9502, "search", "latency_p99_ms", 300.0, "Search p99 under 300ms."),
    (9503, "checkout", "error_rate_pct", 1.0, "Checkout succeeds 99% of the time."),
    (9504, "api-gateway", "latency_p99_ms", 250.0, "Gateway p99 under 250ms."),
    (9505, "payments", "latency_p99_ms", 200.0, "Payments p99 under 200ms."),
    (9506, "checkout", "latency_p99_ms", 400.0, "Checkout p99 under 400ms."),
    (9507, "catalog", "latency_p99_ms", 300.0, "Catalog p99 under 300ms."),
    (9508, "inventory", "error_rate_pct", 1.0, "Inventory reservations succeed 99% of the time."),
    (9509, "media-service", "latency_p99_ms", 400.0, "Media p99 under 400ms."),
    (9510, "notifications", "error_rate_pct", 1.5, "Notification delivery succeeds 98.5% of the time."),
    (9511, "analytics-worker", "error_rate_pct", 2.0, "Event processing succeeds 98% of the time."),
    (9512, "storefront-web", "latency_p99_ms", 500.0, "Storefront p99 under 500ms."),
]

# alert_id, service, metric, severity, status, message
ALERTS = [
    (9601, "payments", "error_rate_pct", "high", "firing",
     "payments error_rate_pct 4.2 exceeds SLO 1.0"),
    (9602, "search", "latency_p99_ms", "medium", "firing",
     "search latency_p99_ms 850.0 exceeds SLO 300.0"),
    (9603, "checkout", "error_rate_pct", "high", "firing",
     "checkout error_rate_pct 5.5 exceeds SLO 1.0"),
    (9604, "api-gateway", "latency_p99_ms", "critical", "firing",
     "api-gateway latency_p99_ms 1030.0 exceeds SLO 250.0"),
    (9605, "catalog", "latency_p99_ms", "medium", "firing",
     "catalog latency_p99_ms 645.0 exceeds SLO 300.0"),
    (9606, "inventory", "error_rate_pct", "high", "firing",
     "inventory error_rate_pct 4.7 exceeds SLO 1.0"),
    (9607, "media-service", "latency_p99_ms", "medium", "firing",
     "media-service latency_p99_ms 800.0 exceeds SLO 400.0"),
    (9608, "notifications", "error_rate_pct", "medium", "firing",
     "notifications error_rate_pct 3.6 exceeds SLO 1.5"),
    (9609, "analytics-worker", "error_rate_pct", "medium", "firing",
     "analytics-worker error_rate_pct 6.0 exceeds SLO 2.0"),
]

INCIDENTS = [
    (9701, "sev1", "API gateway latency surge after v5.1.0 rollout", "api-gateway", "open", ""),
    (9702, "sev2", "Checkout error spike since instant_refunds ramp", "checkout", "open", ""),
    (9703, "sev2", "Inventory reservation failures during peak", "inventory", "open", ""),
]

VULNERABILITIES = [
    (9801, "CVE-2026-31337", "libpayproc", "payments", "critical", "2.4.0", "open"),
    (9802, "CVE-2026-40881", "stripe-sdk", "checkout", "high", "11.4.0", "open"),
    (9803, "CVE-2026-22190", "pydantic", "catalog", "medium", "2.11.0", "open"),
    (9804, "CVE-2026-51002", "requests", "payments", "high", "2.33.0", "open"),
]

# test_id, service, suite, name, status, quarantined
TESTS = [
    (9901, "checkout", "unit", "test_cart_totals", "passing", 0),
    (9902, "checkout", "integration", "test_checkout_idempotency", "flaky", 0),
    (9903, "payments", "unit", "test_capture_retries", "passing", 0),
    (9904, "search", "unit", "test_ranking", "passing", 0),
    (9905, "catalog", "integration", "test_price_rounding", "flaky", 0),
    (9906, "inventory", "integration", "test_reservation_race", "flaky", 0),
    (9907, "api-gateway", "integration", "test_upstream_timeout", "flaky", 0),
    (9908, "notifications", "unit", "test_template_render", "passing", 0),
    (9909, "storefront-web", "unit", "test_cart_selector", "passing", 0),
    (9910, "analytics-worker", "integration", "test_rollup_window", "flaky", 0),
    (9911, "media-service", "unit", "test_thumbnail_sizes", "passing", 0),
    (9912, "search", "integration", "test_index_refresh", "flaky", 0),
]

# fingerprint, service, title, culprit, events, status  (Sentry-style)
ERROR_EVENTS = [
    ("pay-timeout-01", "payments", "ConnectionTimeout: notifications call exceeded 30000ms",
     "src/payments/notify_client.py in send_receipt", 18422, "unresolved"),
    ("chk-nil-refund", "checkout", "TypeError: NoneType has no attribute 'amount'",
     "src/checkout/refunds.py in instant_refund", 9310, "unresolved"),
    ("gw-pool-exhaust", "api-gateway", "dial tcp: connection pool exhausted",
     "internal/proxy/pool.go in Acquire", 24187, "unresolved"),
    ("inv-pool-wait", "inventory", "SQLTimeoutException: connection wait timeout",
     "StockRepository.reserve", 7740, "unresolved"),
    ("ana-oom", "analytics-worker", "MemoryError: consumer restarted after OOM",
     "src/analytics/consumer.py in run", 1180, "unresolved"),
    ("ntf-hang", "notifications", "SMTP call hung with no timeout configured",
     "src/notifications/sender.py in deliver", 5210, "unresolved"),
]

STATUS_PAGE = [
    ("resolved", "Scheduled maintenance completed",
     "Catalog read replica maintenance completed with no customer impact."),
]

LOGS = [
    (9010, "payments", "production", "ERROR",
     "ConnectionTimeout calling notifications after 30000ms - request failed permanently "
     "(notifications_retry_max_attempts=0, no retry attempted); order marked failed"),
    (9011, "payments", "production", "ERROR",
     "ConnectionTimeout calling notifications after 30000ms - request failed permanently "
     "(notifications_retry_max_attempts=0, no retry attempted); order marked failed"),
    (9012, "payments", "production", "INFO",
     "startup config: notifications_retry_max_attempts=0 notifications_timeout_ms=30000 db_pool_size=20"),
    (9013, "search", "production", "WARN",
     "query cache disabled (cache_enabled=false); every request is hitting the primary index"),
    (9014, "api-gateway", "production", "ERROR",
     "p99 latency 1030ms; regression began immediately after deploy v5.1.0 "
     "(upstream_pool_reuse=false: connections created per request and never released)"),
    (9015, "checkout", "production", "ERROR",
     "refund worker panic: nil pointer in instant_refunds path; errors correlate 1:1 with "
     "feature flag instant_refunds=enabled"),
    (9016, "checkout", "production", "WARN",
     "CI: test_checkout_idempotency failed on run #142, passed on rerun #143 - "
     "nondeterministic idempotency-key collision in test fixture"),
    (9017, "notifications", "production", "INFO", "delivery queue healthy; smtp_pool=8"),
    (9018, "catalog", "production", "WARN",
     "pricing loop issued 312 sequential price lookups for 312 products "
     "(batch_pricing_enabled=false); p99 645ms"),
    (9019, "inventory", "production", "ERROR",
     "SQLTimeoutException: connection wait timeout after 2000ms; db_pool_size=5 exhausted "
     "under 128 rps of reservations"),
    (9020, "media-service", "production", "WARN",
     "cdn_enabled=false: all 240 rps of asset requests served from origin object store; p99 800ms"),
    (9021, "analytics-worker", "production", "ERROR",
     "consumer restarted after MemoryError; prefetch_count=0 means unlimited prefetch from rabbitmq"),
    (9022, "notifications", "production", "ERROR",
     "outbound SMTP call hung indefinitely; smtp_timeout_ms=0 (no timeout configured)"),
    (9023, "api-gateway", "production", "INFO",
     "traffic split: /v1/orders 100%, /v2/orders 0%; /internal/debug reachable without auth"),
]

CHANNELS = [
    ("#incidents", "Incident coordination and status updates."),
    ("#security", "Security advisories and audit notes."),
    ("#eng", "General engineering."),
    ("#deploys", "Deployment announcements."),
]

MESSAGES = [
    ("#incidents", "Priya Nair",
     "Declared incident 9701 (sev1): api-gateway p99 through the roof since the v5.1.0 promote."),
    ("#incidents", "Diego Ramos",
     "Incident 9702 (sev2): checkout error rate tracks the instant_refunds ramp exactly."),
    ("#incidents", "Alex Osei",
     "Incident 9703 (sev2): inventory reservations timing out at peak; pool looks undersized."),
    ("#eng", "Mei Tanaka",
     "Reminder: deployment policy = staging first; tier-1 canary at 25% then promote."),
    ("#deploys", "Priya Nair", "api-gateway v5.1.0 promoted to production."),
    ("#security", "Jordan Blake",
     "Scanner run complete: 3 open findings across payments, checkout, catalog."),
]

PULL_REQUESTS = [
    (9201, "api-gateway", "Connection pool rewrite", "Perf: new upstream pool.",
     "Priya Nair", "", "merged", "v5.1.0"),
    (9202, "catalog", "Price rounding cleanup", "Draft, do not merge yet.",
     "Diego Ramos", "", "open", ""),
]

# Seeded CI history. Services whose flaky test is live get an even number of
# prior runs so the *next* run fails deterministically, then passes.
CI_RUNS = [
    ("api-gateway", 9201, "passed", "all checks passed"),
    ("checkout", None, "failed", "intermittent failure: test_checkout_idempotency (rerun may pass)"),
    ("checkout", None, "passed", "all checks passed"),
    ("payments", None, "passed", "all checks passed"),
    ("catalog", None, "failed", "intermittent failure: test_price_rounding (rerun may pass)"),
    ("catalog", None, "passed", "all checks passed"),
    ("inventory", None, "passed", "all checks passed"),
    ("inventory", None, "failed", "intermittent failure: test_reservation_race (rerun may pass)"),
    ("search", None, "passed", "all checks passed"),
    ("search", None, "failed", "intermittent failure: test_index_refresh (rerun may pass)"),
    ("analytics-worker", None, "passed", "all checks passed"),
    ("analytics-worker", None, "failed", "intermittent failure: test_rollup_window (rerun may pass)"),
]

DEPLOYMENTS = [
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
    (9267, "inventory", "staging", "v4.3.1", "succeeded", 100),
    (9268, "inventory", "production", "v4.3.1", "succeeded", 100),
    (9269, "media-service", "staging", "v0.9.4", "succeeded", 100),
    (9270, "media-service", "production", "v0.9.4", "succeeded", 100),
    (9271, "analytics-worker", "staging", "v2.1.7", "succeeded", 100),
    (9272, "analytics-worker", "production", "v2.1.7", "succeeded", 100),
]

# Applied baseline migrations, so the migration ledger looks lived-in.
MIGRATIONS = [
    ("payments", "0041_settlement_batches", "staging", "applied"),
    ("payments", "0041_settlement_batches", "production", "applied"),
    ("checkout", "0087_cart_line_discounts", "staging", "applied"),
    ("checkout", "0087_cart_line_discounts", "production", "applied"),
    ("catalog", "0122_product_media_refs", "staging", "applied"),
    ("catalog", "0122_product_media_refs", "production", "applied"),
    ("inventory", "0033_reservation_index", "staging", "applied"),
    ("inventory", "0033_reservation_index", "production", "applied"),
]

PERSONAS = [
    {"persona_id": "persona_priya", "name": "Priya Nair", "role": "sre",
     "department": "platform", "seniority": "senior", "communication_style": "direct",
     "technical_level": "expert",
     "domain_knowledge": ["deployments", "incident response", "observability"],
     "common_tasks": ["rollback", "alert triage", "canary analysis"]},
    {"persona_id": "persona_diego", "name": "Diego Ramos", "role": "staff_engineer",
     "department": "commerce", "seniority": "staff", "communication_style": "professional",
     "technical_level": "expert",
     "domain_knowledge": ["payments", "checkout", "reliability patterns"],
     "common_tasks": ["code review", "SLO remediation", "dependency upgrades"]},
    {"persona_id": "persona_mei", "name": "Mei Tanaka", "role": "staff_engineer",
     "department": "growth", "seniority": "staff", "communication_style": "concise",
     "technical_level": "expert",
     "domain_knowledge": ["search", "frontend", "feature flags"],
     "common_tasks": ["feature rollout", "A/B experiments", "performance tuning"]},
    {"persona_id": "persona_jordan", "name": "Jordan Blake", "role": "engineering_manager",
     "department": "engineering", "seniority": "senior", "communication_style": "supportive",
     "technical_level": "advanced",
     "domain_knowledge": ["process", "postmortems", "ticket hygiene"],
     "common_tasks": ["incident review", "backlog triage"]},
    {"persona_id": "persona_alex", "name": "Alex Osei", "role": "sre",
     "department": "sre", "seniority": "senior", "communication_style": "direct",
     "technical_level": "expert",
     "domain_knowledge": ["capacity", "queues", "databases"],
     "common_tasks": ["pool tuning", "queue tuning", "capacity planning"]},
]
