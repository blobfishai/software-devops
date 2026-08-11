"""The 50 Horizon-SWE task specifications.

Each spec names its category (the benchmark's seven), the generator that emits
its instruction/verifier/oracle, and the ticket seeded into the issue tracker.

Ticket tuple = (key, priority, title).
"""

SPECS = []


def _add(category, generator, **kw):
    kw["category"] = category
    kw["generator"] = generator
    SPECS.append(kw)


# ==========================================================================
# 1. error_rate_reduction (8) — reliability: retries, timeouts, pools, queues
# ==========================================================================
_add("error_rate_reduction", "config_fix", id="payments_retry", service="payments",
     config_key="notifications_retry_max_attempts", good="3", metric="error_rate_pct",
     alert_id=9601, difficulty="hard",
     ticket=("ENG-2101", "critical", "Payments error rate breaching the 1% SLO"),
     symptom="payments error_rate_pct is 4.2% against a 1.0% SLO (alarm 9601)",
     hint="production logs show a ConnectionTimeout on the notifications call with no retry attempted",
     doc="Retry and timeout standard")

_add("error_rate_reduction", "config_fix", id="inventory_pool", service="inventory",
     config_key="db_pool_size", good="20", metric="error_rate_pct", alert_id=9606,
     difficulty="hard", incident_id=9703,
     ticket=("ENG-2102", "high", "Inventory reservations failing under peak traffic"),
     symptom="inventory error_rate_pct is 4.7% against a 1.0% SLO (alarm 9606) and incident 9703 is open",
     hint="logs show SQLTimeoutException connection-wait timeouts at 128 rps of reservations",
     doc="Connection pool sizing")

_add("error_rate_reduction", "config_fix", id="analytics_prefetch", service="analytics-worker",
     config_key="prefetch_count", good="50", metric="error_rate_pct", alert_id=9609,
     difficulty="medium",
     ticket=("ENG-2103", "high", "Analytics worker restarting under queue load"),
     symptom="analytics-worker error_rate_pct is 6.0% against a 2.0% SLO (alarm 9609)",
     hint="the consumer runs out of memory because it prefetches the whole queue",
     doc="Queue consumer tuning")

_add("error_rate_reduction", "config_fix", id="notifications_timeout", service="notifications",
     config_key="smtp_timeout_ms", good="2000", metric="error_rate_pct", alert_id=9608,
     difficulty="medium",
     ticket=("ENG-2104", "high", "Notification delivery failures from hung SMTP calls"),
     symptom="notifications error_rate_pct is 3.6% against a 1.5% SLO (alarm 9608)",
     hint="outbound SMTP calls hang forever because no timeout is configured",
     doc="Retry and timeout standard")

_add("error_rate_reduction", "config_fix", id="payments_retry_from_code", service="payments",
     config_key="notifications_retry_max_attempts", good="3", metric="error_rate_pct",
     alert_id=9601, difficulty="expert", require_code_read=True,
     resolve_error_event=True, fingerprint="pay-timeout-01",
     ticket=("ENG-2105", "critical",
             "Payments: eliminate the permanent-failure path on notification timeouts"),
     symptom="payments error_rate_pct is 4.2% (SLO 1.0%) and the error tracker shows 18k events "
             "on 'pay-timeout-01'",
     hint="read src/payments/notify_client.py and the commit that last touched it to find the "
          "setting that governs the retry",
     doc="Retry and timeout standard")

_add("error_rate_reduction", "config_fix", id="payments_notify_timeout", service="payments",
     config_key="notifications_timeout_ms", good="2000", difficulty="medium",
     ticket=("ENG-2106", "medium", "Bring the payments notification timeout into policy"),
     symptom="payments waits 30s on the notifications call, far beyond the standard",
     hint="the retry and timeout standard caps downstream timeouts at 2000ms",
     doc="Retry and timeout standard")

_add("error_rate_reduction", "config_fix", id="checkout_payments_timeout", service="checkout",
     config_key="payments_timeout_ms", good="2000", difficulty="medium",
     ticket=("ENG-2107", "medium", "Bring the checkout->payments timeout into policy"),
     symptom="checkout waits 8s on the payments call, beyond the standard",
     hint="the retry and timeout standard caps downstream timeouts at 2000ms",
     doc="Retry and timeout standard")

_add("error_rate_reduction", "config_fix", id="analytics_batch_size", service="analytics-worker",
     config_key="batch_size", good="200", difficulty="medium",
     ticket=("ENG-2108", "low", "Reduce analytics rollup batch size for backpressure"),
     symptom="large rollup batches amplify memory pressure on the consumer",
     hint="the queue consumer runbook recommends smaller batches alongside bounded prefetch",
     doc="Queue consumer tuning")

# ==========================================================================
# 2. latency_optimization (8)
# ==========================================================================
_add("latency_optimization", "config_fix", id="search_cache", service="search",
     config_key="cache_enabled", good="true", metric="latency_p99_ms", alert_id=9602,
     difficulty="medium",
     ticket=("ENG-2201", "high", "Search p99 latency exceeds the 300ms SLO"),
     symptom="search latency_p99_ms is 850ms against a 300ms SLO (alarm 9602)",
     hint="the query cache was disabled during an old incident and never re-enabled",
     doc="Search caching")

_add("latency_optimization", "config_fix", id="catalog_batch_pricing", service="catalog",
     config_key="batch_pricing_enabled", good="true", metric="latency_p99_ms", alert_id=9605,
     difficulty="hard",
     ticket=("ENG-2202", "high", "Catalog pricing p99 regression"),
     symptom="catalog latency_p99_ms is 645ms against a 300ms SLO (alarm 9605)",
     hint="the pricing path issues one query per product - a classic N+1 loop",
     doc="Catalog pricing performance")

_add("latency_optimization", "config_fix", id="media_cdn", service="media-service",
     config_key="cdn_enabled", good="true", metric="latency_p99_ms", alert_id=9607,
     difficulty="medium",
     ticket=("ENG-2203", "medium", "Media assets served from origin instead of the CDN"),
     symptom="media-service latency_p99_ms is 800ms against a 400ms SLO (alarm 9607)",
     hint="every asset request bypasses the CDN and hits the object store directly",
     doc="CDN and media delivery")

_add("latency_optimization", "config_fix", id="catalog_pricing_from_code", service="catalog",
     config_key="batch_pricing_enabled", good="true", metric="latency_p99_ms", alert_id=9605,
     difficulty="expert", require_code_read=True,
     ticket=("ENG-2204", "high", "Catalog: remove the N+1 pricing query from the hot path"),
     symptom="catalog latency_p99_ms is 645ms (SLO 300ms)",
     hint="read src/catalog/pricing.py to find the per-product lookup loop and the setting that "
          "switches it to a batched query",
     doc="Catalog pricing performance")

_add("latency_optimization", "config_fix", id="gateway_pool_reuse", service="api-gateway",
     config_key="upstream_pool_reuse", good="true", difficulty="hard",
     ticket=("ENG-2205", "high", "Enable upstream connection reuse on the API gateway"),
     symptom="the gateway opens a new upstream connection per request and never releases it",
     hint="the pool rewrite that shipped in v5.1.0 left connection reuse switched off",
     doc="Rollback and recovery")

_add("latency_optimization", "config_fix", id="catalog_cache_ttl", service="catalog",
     config_key="catalog_cache_ttl_s", good="300", difficulty="medium",
     ticket=("ENG-2206", "low", "Align the catalog cache TTL with the caching standard"),
     symptom="catalog caches entries for only 120s, well under the standard",
     hint="the caching standard sets a 300s TTL",
     doc="Search caching")

_add("latency_optimization", "config_fix", id="search_shards", service="search",
     config_key="index_shards", good="8", difficulty="medium",
     ticket=("ENG-2207", "medium", "Increase search index shards for query parallelism"),
     symptom="search queries fan out over only 4 shards at 180 rps",
     hint="more shards spread query load; coordinate with the caching change",
     doc="Search caching")

_add("latency_optimization", "incident", id="gateway_v510_rollback", service="api-gateway",
     bad="v5.1.0", good="v5.0.9", alert_id=9604, incident_id=9701, difficulty="hard",
     ticket=("ENG-2208", "critical", "SEV1: roll back api-gateway v5.1.0 and file the postmortem"))

# ==========================================================================
# 3. feature_flag (7)
# ==========================================================================
_add("feature_flag", "flag_ship", id="express_checkout", service="checkout",
     module="express_checkout", flag="express_checkout", rollout=10, difficulty="hard",
     ticket=("ENG-2301", "medium", "Ship express checkout behind a feature flag at 10%"),
     blurb="Implement the express_checkout module in the checkout service, gated behind a NEW "
           "feature flag named 'express_checkout', and roll it out to 10% of production traffic.")

_add("feature_flag", "flag_ship", id="search_autocomplete", service="search",
     module="autocomplete", flag="search_autocomplete", rollout=10, difficulty="medium",
     ticket=("ENG-2302", "medium", "Ship search autocomplete behind a feature flag"),
     blurb="Implement the autocomplete module in the search service, gated behind a NEW feature "
           "flag named 'search_autocomplete', and roll it out to 10% of production traffic.")

_add("feature_flag", "flag_ship", id="saved_carts", service="checkout", module="saved_carts",
     flag="saved_carts", rollout=10, difficulty="expert", migration="0089_saved_carts",
     ticket=("ENG-2303", "medium", "Ship saved carts (schema change) behind a feature flag"),
     blurb="Implement the saved_carts module in the checkout service, gated behind a NEW feature "
           "flag named 'saved_carts', and roll it out to 10% of production traffic.")

_add("feature_flag", "flag_ship", id="media_webp", service="media-service", module="webp_pipeline",
     flag="webp_delivery", rollout=10, difficulty="medium",
     ticket=("ENG-2304", "low", "Ship WebP delivery behind a feature flag"),
     blurb="Implement the webp_pipeline module in media-service, gated behind a NEW feature flag "
           "named 'webp_delivery', and roll it out to 10% of production traffic.")

_add("feature_flag", "flag_kill", id="instant_refunds_killswitch", flag="instant_refunds",
     service="checkout", alert_id=9603, incident_id=9702, difficulty="medium",
     ticket=("ENG-2311", "critical",
             "Kill-switch instant_refunds and resolve the checkout error spike"))

_add("feature_flag", "flag_cleanup", id="legacy_price_rounding_cleanup",
     flag="legacy_price_rounding", service="catalog", difficulty="medium",
     ticket=("ENG-2321", "low", "Clean up the fully rolled-out legacy_price_rounding flag"))

_add("feature_flag", "flag_cleanup", id="checkout_v2_layout_cleanup", flag="checkout_v2_layout",
     service="checkout", difficulty="medium",
     ticket=("ENG-2322", "low", "Clean up the fully rolled-out checkout_v2_layout flag"))

# ==========================================================================
# 4. security_incident (7)
# ==========================================================================
_add("security_incident", "security_cve", id="cve_libpayproc", service="payments",
     package="libpayproc", fixed="2.4.0", cve="CVE-2026-31337", vuln_id=9801, difficulty="hard",
     ticket=("SEC-901", "critical", "Patch CVE-2026-31337 in libpayproc (payments)"))

_add("security_incident", "security_cve", id="cve_stripe_sdk", service="checkout",
     package="stripe-sdk", fixed="11.4.0", cve="CVE-2026-40881", vuln_id=9802, difficulty="medium",
     ticket=("SEC-902", "high", "Patch CVE-2026-40881 in stripe-sdk (checkout)"))

_add("security_incident", "security_cve", id="cve_pydantic", service="catalog",
     package="pydantic", fixed="2.11.0", cve="CVE-2026-22190", vuln_id=9803, difficulty="medium",
     ticket=("SEC-903", "medium", "Patch CVE-2026-22190 in pydantic (catalog)"))

_add("security_incident", "security_cve", id="cve_requests", service="payments",
     package="requests", fixed="2.33.0", cve="CVE-2026-51002", vuln_id=9804, difficulty="medium",
     ticket=("SEC-904", "high", "Patch CVE-2026-51002 in requests (payments)"))

_add("security_incident", "security_endpoint", id="retire_debug_endpoint", service="api-gateway",
     path="/internal/debug", difficulty="medium",
     ticket=("SEC-905", "high", "Retire the exposed /internal/debug endpoint"))

_add("security_incident", "security_endpoint", id="retire_metrics_endpoint", service="api-gateway",
     path="/internal/metrics", difficulty="medium",
     ticket=("SEC-906", "high", "Retire the unauthenticated /internal/metrics endpoint"))

_add("security_incident", "security_secret", id="checkout_hardcoded_secret", service="checkout",
     path="src/checkout/config.py", difficulty="expert",
     ticket=("SEC-907", "critical", "Remove the hardcoded partner API key from checkout"))

# ==========================================================================
# 5. api_migration (7)
# ==========================================================================
_add("api_migration", "api_migration", id="orders_v1_to_v2", service="api-gateway",
     legacy="/v1/orders", replacement="/v2/orders", consumer="storefront-web",
     consumer_key="orders_api_version", consumer_value="v2", difficulty="expert",
     ticket=("ENG-2401", "medium", "Migrate /v1/orders traffic to /v2/orders and retire v1"))

_add("api_migration", "api_migration", id="auth_v1_to_v2", service="api-gateway",
     legacy="/v1/auth", replacement="/v2/auth", consumer="storefront-web",
     consumer_key="auth_api_version", consumer_value="v2", difficulty="expert",
     ticket=("ENG-2402", "medium", "Migrate /v1/auth traffic to /v2/auth and retire v1"))

_add("api_migration", "api_migration", id="checkout_v1_to_v2", service="api-gateway",
     legacy="/v1/checkout", replacement="/v2/checkout", consumer="storefront-web",
     consumer_key="checkout_api_version", consumer_value="v2", difficulty="expert",
     ticket=("ENG-2403", "medium", "Migrate /v1/checkout traffic to /v2/checkout and retire v1"))

_add("api_migration", "api_migration", id="search_v1_to_v2", service="api-gateway",
     legacy="/v1/search", replacement="/v2/search", difficulty="hard",
     ticket=("ENG-2404", "medium", "Migrate /v1/search traffic to /v2/search and retire v1"))

_add("api_migration", "api_migration", id="media_v1_to_v2", service="api-gateway",
     legacy="/v1/media", replacement="/v2/media", difficulty="hard",
     ticket=("ENG-2405", "low", "Migrate /v1/media traffic to /v2/media and retire v1"))

_add("api_migration", "api_migration", id="inventory_v1_to_v2", service="api-gateway",
     legacy="/v1/inventory", replacement="/v2/inventory", difficulty="hard",
     ticket=("ENG-2406", "medium", "Migrate /v1/inventory traffic to /v2/inventory and retire v1"))

_add("api_migration", "api_migration", id="notify_v1_to_v2", service="api-gateway",
     legacy="/v1/notify", replacement="/v2/notify", difficulty="hard",
     ticket=("ENG-2407", "low", "Migrate /v1/notify traffic to /v2/notify and retire v1"))

# ==========================================================================
# 6. flaky_test (6)
# ==========================================================================
_add("flaky_test", "flaky", id="flaky_checkout_idempotency", service="checkout",
     test="test_checkout_idempotency", difficulty="hard",
     ticket=("ENG-2501", "high", "Fix flaky test_checkout_idempotency"),
     cause="the fixture derives idempotency keys from int(time.time()), so parallel runs collide")

_add("flaky_test", "flaky", id="flaky_catalog_rounding", service="catalog",
     test="test_price_rounding", difficulty="medium",
     ticket=("ENG-2502", "medium", "Fix flaky test_price_rounding"),
     cause="the assertion depends on float rounding that varies with locale")

_add("flaky_test", "flaky", id="flaky_inventory_race", service="inventory",
     test="test_reservation_race", difficulty="hard",
     ticket=("ENG-2503", "high", "Fix flaky test_reservation_race"),
     cause="two threads race on the same stock row without a deterministic barrier")

_add("flaky_test", "flaky", id="flaky_gateway_timeout", service="api-gateway",
     test="test_upstream_timeout", difficulty="medium",
     ticket=("ENG-2504", "medium", "Fix flaky test_upstream_timeout"),
     cause="the test asserts on wall-clock timing with only a 50ms margin")

_add("flaky_test", "flaky", id="flaky_search_index", service="search",
     test="test_index_refresh", difficulty="medium",
     ticket=("ENG-2505", "medium", "Fix flaky test_index_refresh"),
     cause="the test reads the index before the refresh interval has elapsed")

_add("flaky_test", "flaky", id="flaky_analytics_rollup", service="analytics-worker",
     test="test_rollup_window", difficulty="medium",
     ticket=("ENG-2506", "medium", "Fix flaky test_rollup_window"),
     cause="the rollup window boundary is computed from the current clock")

# ==========================================================================
# 7. multi_service_rollout (7)
# ==========================================================================
_add("multi_service_rollout", "multi_service", id="loyalty_points", difficulty="expert",
     ticket=("ENG-2601", "medium",
             "Roll out loyalty points across catalog, checkout and storefront-web"),
     steps=[("catalog", "loyalty_accrual", "0123_loyalty_points"),
            ("checkout", "loyalty_redeem", "0088_loyalty_ledger"),
            ("storefront-web", "loyalty_widget", None)])

_add("multi_service_rollout", "multi_service", id="split_settlement", difficulty="expert",
     ticket=("ENG-2602", "medium", "Roll out split settlement across payments and checkout"),
     steps=[("payments", "split_settlement", "0042_settlement_splits"),
            ("checkout", "split_settlement_ui", None)])

_add("multi_service_rollout", "multi_service", id="backorders", difficulty="expert",
     ticket=("ENG-2603", "medium",
             "Roll out backorders across inventory, checkout and storefront-web"),
     steps=[("inventory", "backorder_queue", "0034_backorders"),
            ("checkout", "backorder_flow", None),
            ("storefront-web", "backorder_banner", None)])

_add("multi_service_rollout", "multi_service", id="media_pipeline", difficulty="hard",
     ticket=("ENG-2604", "medium",
             "Roll out the new media pipeline across media-service, catalog and storefront-web"),
     steps=[("media-service", "asset_pipeline", None),
            ("catalog", "media_refs", None),
            ("storefront-web", "gallery_v2", None)])

_add("multi_service_rollout", "multi_service", id="search_relevance", difficulty="hard",
     ticket=("ENG-2605", "medium", "Roll out relevance signals across catalog and search"),
     steps=[("catalog", "relevance_signals", None),
            ("search", "relevance_v2", None)])

_add("multi_service_rollout", "multi_service", id="notification_templates", difficulty="hard",
     ticket=("ENG-2606", "low", "Roll out templated receipts across notifications and payments"),
     steps=[("notifications", "template_v2", None),
            ("payments", "receipt_v2", None)])

_add("multi_service_rollout", "multi_service", id="checkout_upsell", difficulty="expert",
     ticket=("ENG-2607", "medium",
             "Roll out checkout upsell across catalog, checkout and storefront-web"),
     steps=[("catalog", "upsell_slots", None),
            ("checkout", "upsell_flow", None),
            ("storefront-web", "upsell_widget", None)])


def all_specs():
    return list(SPECS)


def tickets():
    """Every spec's ticket, as issue-tracker seed rows."""
    rows = []
    for i, s in enumerate(SPECS, start=9101):
        key, priority, title = s["ticket"]
        rows.append((i, key, _ticket_type(s), title, _ticket_desc(s), "open", priority, "",
                     _ticket_service(s)))
    return rows


def _ticket_type(s):
    return {"security_cve": "security", "security_endpoint": "security",
            "security_secret": "security", "flag_kill": "incident",
            "incident": "incident", "flaky": "bug", "config_fix": "bug",
            "flag_ship": "feature", "flag_cleanup": "task",
            "api_migration": "task", "multi_service": "feature"}[s["generator"]]


def _ticket_service(s):
    if s["generator"] == "multi_service":
        return ""
    return s.get("service", "")


def _ticket_desc(s):
    g = s["generator"]
    if g == "config_fix":
        return "%s Investigate the root cause, ship the fix through the standard workflow, and " \
               "follow the deployment policy." % s.get("symptom", "")
    if g == "flag_ship":
        return s["blurb"]
    if g == "flag_kill":
        return "Incident %d: the %s error rate spiked right after the %s flag ramped in " \
               "production." % (s["incident_id"], s["service"], s["flag"])
    if g == "flag_cleanup":
        return "The %s flag has been fully rolled out for months and should be removed." % s["flag"]
    if g == "security_cve":
        return "Scanner reports %s in %s vulnerable to %s; fixed in %s." \
               % (s["package"], s["service"], s["cve"], s["fixed"])
    if g == "security_endpoint":
        return "The unauthenticated %s endpoint is still reachable in production." % s["path"]
    if g == "security_secret":
        return "A partner API key is hardcoded in %s and must move to the secret manager." % s["path"]
    if g == "api_migration":
        return "Deprecate %s, migrate traffic to %s, and retire the legacy path." \
               % (s["legacy"], s["replacement"])
    if g == "flaky":
        return "%s fails intermittently in CI: %s." % (s["test"], s["cause"])
    if g == "multi_service":
        return "Ship: " + ", ".join("%s in %s" % (m, sv) for sv, m, _ in s["steps"]) + "."
    if g == "incident":
        return "Incident %d: %s p99 latency surged right after %s was promoted." \
               % (s["incident_id"], s["service"], s["bad"])
    return ""
