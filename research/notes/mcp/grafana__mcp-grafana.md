# grafana/mcp-grafana — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/grafana__mcp-grafana` @ git commit `460e62e` (`git -C /Users/samuelchien/dev/software-devops/research/repos/mcp/grafana__mcp-grafana rev-parse --short HEAD`), read 2026-08-11

**Language / framework:** Go. MCP server built on `github.com/mark3labs/mcp-go` (`server.MCPServer`, `mcp.Tool`) — see imports at `tools.go:13-14`. Tools are declared with the in-repo generic helper `mcpgrafana.MustTool[T,R](name, description, handler, options...)` (`tools.go:58-68`), which wraps `ConvertTool` (`tools.go:197-429`). `ConvertTool` reflects the handler's second argument (a Go struct with `jsonschema:"..."` tags) into the tool's `RawInputSchema` via `github.com/invopop/jsonschema` (`tools.go:225`, `tools.go:458-493`), sets `additionalProperties: false` (`tools.go:403`), and registers via `(*Tool).Register` → `mcp.AddTool` (`tools.go:52-54`).

**Registration entrypoint:** `cmd/mcp-grafana/main.go:182` (`(*disabledTools).toolEntries()`) is the single source of truth mapping category → registration function; it is executed by `cmd/mcp-grafana/main.go:222` (`processTools`) which is called from `newServer` at `cmd/mcp-grafana/main.go:360`. Per-category registrars live in `tools/*.go` as `Add<Category>Tools(...)` (e.g. `tools/prometheus.go:593`, `tools/loki.go:918`, `tools/dashboard.go:1219`).

**Tool categories / enable-disable flags:**
- Category gating is two-layered: a category must be present in `--enabled-tools` AND its `--disable-<category>` flag must be false (`cmd/mcp-grafana/main.go:27-38`, `cmd/mcp-grafana/main.go:42-44`).
- `--enabled-tools` default value (`cmd/mcp-grafana/main.go:118`): `search,datasource,incident,prometheus,loki,alerting,dashboard,folder,oncall,asserts,sift,pyroscope,navigation,proxied,annotations,rendering,snapshot,plugin,api,config,provisioning`. Categories that exist but are **NOT** enabled by default: `elasticsearch, quickwit, influxdb, admin, cloudwatch, examples, clickhouse, snowflake, runpanelquery, graphite, athena, agento11y, assistant` (compare `cmd/mcp-grafana/main.go:118` with `cmd/mcp-grafana/main.go:184-218`; README states the same at `README.md:456`).
- Per-category boolean flags: `--disable-search`, `--disable-datasource`, `--disable-incident`, `--disable-prometheus`, `--disable-loki`, `--disable-elasticsearch`, `--disable-quickwit`, `--disable-influxdb`, `--disable-alerting`, `--disable-dashboard`, `--disable-folder`, `--disable-oncall`, `--disable-asserts`, `--disable-sift`, `--disable-admin`, `--disable-pyroscope`, `--disable-navigation`, `--disable-proxied`, `--disable-write`, `--disable-annotations`, `--disable-rendering`, `--disable-snapshot`, `--disable-cloudwatch`, `--disable-examples`, `--disable-clickhouse`, `--disable-snowflake`, `--disable-runpanelquery`, `--disable-graphite`, `--disable-athena`, `--disable-plugin`, `--disable-api`, `--disable-config`, `--disable-provisioning`, `--disable-agento11y`, `--disable-assistant` (`cmd/mcp-grafana/main.go:119-153`).
- **Write gating:** `--disable-write` (`cmd/mcp-grafana/main.go:137`) sets `enableWriteTools := !dt.write` (`cmd/mcp-grafana/main.go:183`), which is threaded into the write-aware registrars (`cmd/mcp-grafana/main.go:186,187,193,194,195,198,201,202,204,212,213,216,217`). Each such registrar either skips write tools entirely or swaps in a read-only variant registered under the *same tool name* (see "Read-only variants" below).
- **Proxied tools** are NOT in `toolEntries` — they are registered per-session via MCP hooks (`cmd/mcp-grafana/main.go:293-331`) and gated only by `--disable-proxied`; the `proxied` token in `--enabled-tools` has no effect (`docs/sources/configure/proxied-tools.md:36`).
- Server instructions are generated from the enabled category set (`cmd/mcp-grafana/main.go:231-269`, descriptions at `cmd/mcp-grafana/main.go:47-81`).

## Full tool list (105 tools)

105 distinct tool names from 111 `mcpgrafana.MustTool(` call sites in `tools/` (6 names are registered twice, as read-only / read-write variants — see the "Read-only variants" note below). Verified with `rg -n 'MustTool\(' tools/`.

`R` = advertised `mcp.WithReadOnlyHintAnnotation(true)`; `W` = `mcp.WithReadOnlyHintAnnotation(false)`.

### search (2) — `tools/search.go:146`
- `search_dashboards` — R — Search dashboards by query string; returns title/UID/folder/tags/URL — `tools/search.go:103`
- `search_folders` — R — Search folders by query string — `tools/search.go:135`

### datasource (5) — `tools/datasources.go:825`
- `list_datasources` — R — List configured datasources, filter by type, paginated — `tools/datasources.go:426`
- `get_datasource` — R — Get a full datasource model by UID or name — `tools/datasources.go:509`
- `check_datasources_health` — R — Run datasource health checks, filtered by type or UIDs — `tools/datasources.go:813`
- `create_datasource` — W — Create a datasource (two-phase: schema first, then confirmed field values) — `tools/datasources.go:437` (write-gated, `tools/datasources.go:829-832`)
- `update_datasource` — W — Update non-secret datasource fields by UID — `tools/datasources.go:448` (write-gated)

### dashboard (5) — `tools/dashboard.go:1219`
- `get_dashboard_by_uid` — R — Full dashboard JSON (v1 classic or v2 elements/layout) — `tools/dashboard.go:670`
- `get_dashboard_panel_queries` — R — Extract panel queries + datasource info from a dashboard — `tools/dashboard.go:753`
- `get_dashboard_property` — R — JSONPath-scoped read of a dashboard to save context — `tools/dashboard.go:805`
- `get_dashboard_summary` — R — Compact dashboard summary (panel count/types/variables) — `tools/dashboard.go:920`
- `update_dashboard` — W — Create/update a dashboard by full JSON or JSONPath patch operations — `tools/dashboard.go:681` (write-gated, `tools/dashboard.go:1221-1223`)

### folder (1) — `tools/folder.go:55`
- `create_folder` — W — Create a Grafana folder — `tools/folder.go:44` (only registered when writes enabled, `tools/folder.go:56-58`; the folder category registers **nothing** in read-only mode)

### prometheus (6) — `tools/prometheus.go:593`
- `query_prometheus` — R — Run a PromQL instant or range query — `tools/prometheus.go:180`
- `query_prometheus_histogram` — R — Build + run a `histogram_quantile` PromQL range query — `tools/prometheus.go:578`
- `list_prometheus_metric_names` — R — List/regex-filter metric names, paginated — `tools/prometheus.go:262`
- `list_prometheus_label_names` — R — List label names with selectors + time range — `tools/prometheus.go:367`
- `list_prometheus_label_values` — R — List values of one label with selectors + time range — `tools/prometheus.go:426`
- `list_prometheus_metric_metadata` — R — Metric metadata from scrape targets (experimental endpoint) — `tools/prometheus.go:56`

### loki (6) — `tools/loki.go:918` (includes `AddLokiLabelAnalyzerTools`, `tools/loki_label_analyzer.go:929`)
- `query_loki_logs` — R — LogQL/LogsQL query returning log entries or metric samples — `tools/loki.go:747`
- `query_loki_stats` — R — Index-level stream/chunk/entry/byte stats for a selector — `tools/loki.go:861`
- `query_loki_patterns` — R — Detected log patterns with occurrence counts (Loki only) — `tools/loki.go:904`
- `list_loki_label_names` — R — List label/field names in a time range — `tools/loki.go:218`
- `list_loki_label_values` — R — List all values for a label name — `tools/loki.go:267`
- `analyze_loki_labels` — R — Audit a Loki label strategy / diagnose query performance — `tools/loki_label_analyzer.go:1007`

### alerting (2) — `tools/alerting.go:63`
- `alerting_manage_rules` — R **or** W — Multi-operation alert-rule tool. Read-only variant supports `list|get|versions` (`tools/alerting.go:42`); read-write variant adds `create|update|delete` (`tools/alerting.go:53`). Exactly one is registered depending on `enableWriteTools` (`tools/alerting.go:63-68`).
- `alerting_manage_routing` — R — Read notification policies, contact points, time intervals — `tools/alerting_routing.go:156`

### annotations (4) — `tools/annotations.go:231`
- `get_annotations` — R — Fetch annotations by dashboard UID / time range / tags — `tools/annotations.go:57`
- `get_annotation_tags` — R — List annotation tags — `tools/annotations.go:220`
- `create_annotation` — W — Create an annotation (standard or Graphite format) — `tools/annotations.go:133` (write-gated, `tools/annotations.go:233-236`)
- `update_annotation` — W — Partial update of an annotation by ID — `tools/annotations.go:186` (write-gated)

### incident (4, Grafana Cloud) — `tools/incident.go:167`
- `list_incidents` — R — List incidents, filter by status, optionally include drills — `tools/incident.go:85`
- `get_incident` — R — Get a single incident by ID — `tools/incident.go:194`
- `create_incident` — W — Create an incident — `tools/incident.go:126` (write-gated, `tools/incident.go:169-172`)
- `add_activity_to_incident` — W — Append a `userNote` activity to an incident timeline — `tools/incident.go:157` (write-gated)

### oncall (7, Grafana Cloud / OnCall plugin) — `tools/oncall.go:584` (no write gating)
- `list_oncall_schedules` — R — List OnCall schedules, optionally by team or schedule ID — `tools/oncall.go:188`
- `get_oncall_shift` — R — Get details of one OnCall shift by ID — `tools/oncall.go:240`
- `get_current_oncall_users` — R — Users currently on call for a schedule — `tools/oncall.go:310`
- `list_oncall_teams` — R — List OnCall teams (paginated) — `tools/oncall.go:363`
- `list_oncall_users` — R — List OnCall users (directory / by ID / by username) — `tools/oncall.go:435`
- `list_alert_groups` — R — List OnCall alert groups with filters — `tools/oncall.go:526`
- `get_alert_group` — R — Get one OnCall alert group by ID — `tools/oncall.go:573`

### sift (5, Grafana Cloud) — `tools/sift.go:429`
- `get_sift_investigation` — R — Get an investigation by UUID — `tools/sift.go:173`
- `get_sift_analysis` — R — Get one analysis inside an investigation — `tools/sift.go:217`
- `list_sift_investigations` — R — List investigations (default 10) — `tools/sift.go:254`
- `find_error_pattern_logs` — W — Create + await an `ErrorPatternLogs` investigation over Loki — `tools/sift.go:349` (write-gated, `tools/sift.go:433-436`; it creates server-side state, hence `ReadOnlyHint=false`)
- `find_slow_requests` — W — Create + await a `SlowRequests` investigation over Tempo — `tools/sift.go:418` (write-gated)

### asserts (1, Grafana Cloud) — `tools/asserts.go:155`
- `get_assertions` — R — Assertion summary for an entity over a time range — `tools/asserts.go:144`

### pyroscope (4) — `tools/pyroscope.go:26`
- `list_pyroscope_label_names` — R — Label names matching a selector — `tools/pyroscope.go:40`
- `list_pyroscope_label_values` — R — Label values for a label name — `tools/pyroscope.go:101`
- `list_pyroscope_profile_types` — R — Available profile types — `tools/pyroscope.go:169`
- `query_pyroscope` — R — Profile (flamegraph table / DOT) and/or metrics query — `tools/pyroscope.go:624`

### admin (9, not enabled by default) — `tools/admin.go:262` (all read-only, no write gating)
- `list_teams` — R — Search Grafana teams — `tools/admin.go:34`
- `list_users_by_org` — R — List org users — `tools/admin.go:58`
- `list_all_roles` — R — List roles (optionally delegatable-only) — `tools/admin.go:89`
- `get_role_details` — R — Role details by UID — `tools/admin.go:115`
- `get_role_assignments` — R — Users/teams/service accounts assigned a role — `tools/admin.go:141`
- `list_user_roles` — R — Roles assigned to users — `tools/admin.go:168`
- `list_team_roles` — R — Roles assigned to teams — `tools/admin.go:195`
- `get_resource_permissions` — R — Permissions set on a resource — `tools/admin.go:222`
- `get_resource_description` — R — Available permissions for a resource type — `tools/admin.go:251`

### navigation (1) — `tools/navigation.go:332`
- `generate_deeplink` — W **or** R — Build dashboard/panel/Explore deeplinks. Full variant can also mint a `/goto/<uid>` short URL (a server-side write) — `tools/navigation.go:310`; read-only variant accepts but ignores `shorten` — `tools/navigation.go:321`.

### api (1) — `tools/api.go:199`
- `grafana_api_request` — W **or** R — Arbitrary authenticated Grafana HTTP API call with optional jq filtering. Full variant allows GET/POST/PUT/PATCH/DELETE (`tools/api.go:173`, methods at `tools/api.go:18-24`); read-only variant rejects anything but GET (`tools/api.go:185`, enforcement at `tools/api.go:49-59`).

### rendering (1) — `tools/rendering.go:368`
- `get_panel_image` — R — Render a panel or dashboard to base64 PNG (requires Image Renderer) — `tools/rendering.go:354`

### snapshot (4) — `tools/snapshot.go:271`
- `list_snapshots` — R — List dashboard snapshots — `tools/snapshot.go:227`
- `get_snapshot` — R — Get a snapshot by key — `tools/snapshot.go:238`
- `create_snapshot` — W — Create a snapshot from a dashboard payload — `tools/snapshot.go:249` (write-gated, `tools/snapshot.go:274-277`)
- `delete_snapshot` — W — Delete a snapshot by key — `tools/snapshot.go:260` (write-gated)

### plugin (3) — `tools/plugins.go:408`
- `search_plugin_information` — R — Search the Grafana plugin catalog — `tools/plugins.go:393`
- `get_plugin` — R — Check whether a plugin is installed and get details — `tools/plugins.go:125`
- `install_plugin` — W — Install a plugin by ID — `tools/plugins.go:230` (write-gated, `tools/plugins.go:411-413`)

### config (1) — `tools/config.go:128`
- `suggest_loki_alloy_label_config` — R — Generate an Alloy `loki.process` label-enforcement snippet — `tools/config.go:116`

### provisioning (2) — `tools/provisioning.go:388`
- `list_provisioning_repositories` — R — List provisioning (git-sync) repositories — `tools/provisioning.go:155`
- `validate_provisioning_file` — R — Dry-run validate a file at a branch/commit — `tools/provisioning.go:375`

### examples (1, not enabled by default) — `tools/examples.go:302`
- `get_query_examples` — R — Example queries per datasource type — `tools/examples.go:290`

### runpanelquery (1, not enabled by default) — `tools/run_panel_query.go:851`
- `run_panel_query` — R — Execute dashboard panel queries with time/variable overrides — `tools/run_panel_query.go:839`

### elasticsearch (1, not enabled by default) — `tools/elasticsearch.go:64`
- `query_elasticsearch` — R — Lucene / Query DSL search against Elasticsearch or OpenSearch — `tools/elasticsearch.go:52`

### quickwit (1, not enabled by default) — `tools/quickwit.go:270`
- `query_quickwit` — R — Lucene / Query DSL search against Quickwit — `tools/quickwit.go:258`

### influxdb (1, not enabled by default) — `tools/influxdb.go:229`
- `query_influxdb` — W — InfluxQL or Flux query (annotated `ReadOnlyHint=false` because arbitrary query text can mutate) — `tools/influxdb.go:209`

### cloudwatch (4, not enabled by default) — `tools/cloudwatch.go:559`
- `query_cloudwatch` — R — Query CloudWatch metrics via Grafana — `tools/cloudwatch.go:304`
- `list_cloudwatch_namespaces` — R — List namespaces — `tools/cloudwatch.go:421`
- `list_cloudwatch_metrics` — R — List metrics in a namespace — `tools/cloudwatch.go:483`
- `list_cloudwatch_dimensions` — R — List dimension keys for a metric — `tools/cloudwatch.go:547`

### clickhouse (3, not enabled by default) — `tools/clickhouse.go:398`
- `list_clickhouse_tables` — R — List tables (name/db/engine/rows/size) — `tools/clickhouse.go:307`
- `describe_clickhouse_table` — R — Column schema for a table — `tools/clickhouse.go:386`
- `query_clickhouse` — W — Arbitrary SQL via Grafana (annotated `ReadOnlyHint=false`) — `tools/clickhouse.go:230`

### snowflake (3, not enabled by default) — `tools/snowflake.go:416`
- `list_snowflake_tables` — R — List tables via INFORMATION_SCHEMA — `tools/snowflake.go:320`
- `describe_snowflake_table` — R — Column schema for a table — `tools/snowflake.go:404`
- `query_snowflake` — W — Arbitrary SQL via Grafana (annotated `ReadOnlyHint=false`) — `tools/snowflake.go:229`

### athena (5, not enabled by default) — `tools/athena.go:538`
- `list_athena_catalogs` — R — List Athena data catalogs — `tools/athena.go:237`
- `list_athena_databases` — R — List databases in a catalog — `tools/athena.go:280`
- `list_athena_tables` — R — List tables in a database — `tools/athena.go:327`
- `describe_athena_table` — R — Column names for a table — `tools/athena.go:381`
- `query_athena` — W — Arbitrary SQL via Grafana (annotated `ReadOnlyHint=false`) — `tools/athena.go:515`

### graphite (4, not enabled by default) — `tools/graphite.go:513`
- `query_graphite` — R — Graphite render-API query — `tools/graphite.go:229`
- `list_graphite_metrics` — R — Browse the Graphite metric tree — `tools/graphite.go:306`
- `list_graphite_tags` — R — List tag names for tag-based metrics — `tools/graphite.go:355`
- `query_graphite_density` — R — Analyse data density for series over a window — `tools/graphite.go:496`

### agento11y (6 names / 8 registrations, Grafana Cloud, not enabled by default) — `tools/agento11y.go:721`
- `agento11y_manage_conversations` — R — List/search/fetch LLM conversations — `tools/agento11y.go:445`
- `agento11y_manage_generations` — R — Fetch a generation + its eval scores — `tools/agento11y.go:476`
- `agento11y_manage_agents` — R — Read the agent catalog (prompts, tools, versions, scores) — `tools/agento11y_agents.go:298`
- `agento11y_manage_evaluators` — R **or** W — Evaluators / templates / judge catalog; read-only at `tools/agento11y.go:658`, read-write at `tools/agento11y.go:691` (`tools/agento11y.go:725-733`)
- `agento11y_manage_eval_rules` — R **or** W — Eval rules and guards; `tools/agento11y.go:669` / `tools/agento11y.go:701`
- `agento11y_manage_eval_collections` — R **or** W — Saved conversations and collections; `tools/agento11y.go:680` / `tools/agento11y.go:711`

### assistant (1, Grafana Cloud, not enabled by default) — `tools/assistant.go:190`
- `ask_assistant` — W — Ask Grafana Assistant a question, return the full text reply — `tools/assistant.go:177`. **The whole category is write-gated**: `AddAssistantTools` registers nothing when `--disable-write` is set (`tools/assistant.go:191-193`), and the capability is dropped from the instructions string (`cmd/mcp-grafana/main.go:242-244`).

### proxied (dynamic, not statically declared)
Tools discovered from an MCP server behind a Grafana datasource proxy, currently only Tempo (`proxied_tools.go:34`: `"tempo": {Type: "tempo", EndpointPath: "/api/mcp"}`). Names are prefixed `<datasourceType>_<remoteToolName>`, e.g. `tempo_traceql-search` (`proxied_tools.go:183`, `proxied_tools.go:589`). Registered per session via `AddSessionTools` (`proxied_tools.go:944`), gated only by `--disable-proxied` (`docs/sources/configure/proxied-tools.md:36`).

### Write tools and gating mechanism (summary)
- The gate is `--disable-write` → `enableWriteTools` (`cmd/mcp-grafana/main.go:137`, `cmd/mcp-grafana/main.go:183`).
- Tools **not registered at all** in read-only mode: `create_datasource`, `update_datasource`, `update_dashboard`, `create_folder`, `create_incident`, `add_activity_to_incident`, `create_annotation`, `update_annotation`, `find_error_pattern_logs`, `find_slow_requests`, `create_snapshot`, `delete_snapshot`, `install_plugin`, `ask_assistant`.
- **Read-only variants registered under the same name** (6 names): `alerting_manage_rules` (`tools/alerting.go:63-68`), `grafana_api_request` (`tools/api.go:199-205`), `generate_deeplink` (`tools/navigation.go:332-338`), `agento11y_manage_evaluators` / `agento11y_manage_eval_rules` / `agento11y_manage_eval_collections` (`tools/agento11y.go:725-733`).
- `--debug` is **not** a write gate — it only enables debug mode for the Grafana HTTP transport (`cmd/mcp-grafana/main.go:157`).
- Every tool also advertises MCP annotations (`ReadOnlyHint`, `DestructiveHint`, `IdempotentHint`, `OpenWorldHint`) at its `MustTool` call site, e.g. `tools/prometheus.go:184-188`, `tools/dashboard.go:686-689`.

## Key tools

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `query_prometheus` | `datasourceUid`: string — required; `expr`: string — required (PromQL); `endTime`: string — required (RFC3339 or `now-1h`); `startTime`: string — optional (required when `queryType=range`); `stepSeconds`: int — optional (required when `queryType=range`); `queryType`: string — optional (`range` default, or `instant`); `projectName`: string — optional (Cloud Monitoring only) | `*QueryPrometheusResult{Data model.Value (prometheus/common/model — Vector/Matrix/Scalar/String), Hints *EmptyResultHints (only when empty), Warnings []string}`, JSON-marshalled by `ConvertTool` | params `tools/prometheus.go:67-75`; result type `tools/prometheus.go:78-82`; handler `tools/prometheus.go:154-178`; tool `tools/prometheus.go:180` |
| `query_loki_logs` | `datasourceUid`: string — required; `logql`: string — required; `startRfc3339`: string — optional (default `now-1h`); `endRfc3339`: string — optional (default now); `limit`: int — optional (default 10, capped at 100 / `--max-loki-log-limit`); `direction`: string — optional (`backward` default); `queryType`: string — optional (`range` default, or `instant`); `stepSeconds`: int — optional | `*QueryLokiLogsResult{Data []LogEntry, Hints *EmptyResultHints, Metadata *QueryMetadata}` where `LogEntry{Timestamp string, Line string, Value *float64, Values []MetricValue, Labels map[string]string, StructuredMetadata map[string]string, Parsed map[string]string}` and `QueryMetadata{LinesReturned, MaxLinesAllowed int, ResultsTruncated bool, TotalLinesScanned *int, StartTime, EndTime string}` | params `tools/loki.go:450-459`; results `tools/loki.go:462-490`; handler `tools/loki.go:651-746`; tool `tools/loki.go:747` |
| `list_loki_label_values` | `datasourceUid`: string — required; `labelName`: string — required; `startRfc3339`: string — optional (default 1h ago); `endRfc3339`: string — optional (default now) | `[]string` (empty slice, not nil, when no values — `tools/loki.go:298-301`) | params `tools/loki.go:230-235`; handler `tools/loki.go:238-303`; tool `tools/loki.go:267` |
| `query_loki_stats` | `datasourceUid`: string — required; `logql`: string — required (label selector only, no filters/aggregations); `startRfc3339`/`endRfc3339`: string — optional (default last hour) | `*Stats{Streams int, Chunks int, Entries int, Bytes int}`; on VictoriaLogs only `Entries` is populated | params `tools/loki.go:833-838`; `Stats` `tools/loki.go:38-43`; tool `tools/loki.go:861` |
| `alerting_manage_rules` (read-only variant) | `operation`: string — required (enum `list`\|`get`\|`versions`); `rule_uid`: string — optional (required for `get`/`versions`); `datasource_uid`: *string — optional; `folder_uid`: string — optional; `rule_group`: string — optional; plus embedded `listFilterParams`: `rule_limit` int (default 200, max 200), `label_selectors` []string, `limit_alerts` int, `search_folder` string, `search_rule_name` string, `states` []string, `rule_type` string (enum `alerting`\|`recording`), `matchers` []string — all optional | `any`, switched on operation: `list` → `[]alertRuleSummary{UID,Title,Type,State,Health,FolderUID,RuleGroup,For,LastEvaluation,Labels,Annotations,Query}`; `get` → `*alertRuleDetail{UID,Title,FolderUID,RuleGroup,Condition,NoDataState,ExecErrState,For,Annotations,Labels,IsPaused,NotificationSettings *models.AlertRuleNotificationSettings,Data []*models.AlertQuery,KeepFiringFor,Record,MissingSeriesEvalsToResolve,State,Health,Type,LastEvaluation,LastError,Alerts}`; `versions` → the alerting client's version list | params `tools/alerting_manage_rules_types.go:580-600`; handler `tools/alerting_manage_rules_handlers.go:16-42`; summary `tools/alerting_manage_rules_types.go:44-61`; detail `tools/alerting_manage_rules_types.go:66-88`; tool `tools/alerting.go:42` |
| `alerting_manage_rules` (read-write variant) | Read-only params plus `operation` enum extended with `create`\|`update`\|`delete`, and `title`, `rule_group`, `folder_uid`, `condition`, `data` []map[string]any, `no_data_state`, `exec_err_state`, `for`, `keep_firing_for`, `is_paused`, `notification_settings`, `record`, `missing_series_evals_to_resolve`, `annotations`, `labels`, `org_id`, `disable_provenance` *bool — all optional in schema, validated per operation | `create`/`update` → `*models.ProvisionedAlertRule` (grafana-openapi-client-go); `delete` → string `"Alert rule <uid> deleted successfully"` | params `tools/alerting_manage_rules_types.go:627-650`; handler `tools/alerting_manage_rules_handlers.go:44-86`; create `…:319-389`; delete message `…:477`; tool `tools/alerting.go:53` |
| `alerting_manage_routing` | `operation`: string — required (enum `get_notification_policies`\|`get_contact_points`\|`get_contact_point`\|`get_time_intervals`\|`get_time_interval`); `datasource_uid`: *string — optional; `name`: *string — optional; `contact_point_title`: *string — optional (required for `get_contact_point`); `time_interval_name`: *string — optional; `limit`: int — optional (default 100) | `any` — the Grafana provisioning API payloads for policies / contact points / time intervals | params `tools/alerting_routing.go:28-37`; handler `tools/alerting_routing.go:71`; tool `tools/alerting_routing.go:156` |
| `search_dashboards` | `query`: string — optional; `limit`: int — optional (default 50, capped 100); `page`: int — optional (default 1, 1-indexed) | `*SearchDashboardsResult{Dashboards []dashboardSearchHit{UID,Title,URL,Type,FolderUID,FolderTitle,Tags,Description}, Total int, HasMore bool}`. Note `Total` is the page length, not a global count (`tools/search.go:98`) | params `tools/search.go:18-22`; hit `tools/search.go:24-33`; result `tools/search.go:35-39`; tool `tools/search.go:103` |
| `get_dashboard_by_uid` | `uid`: string — required | `*DashboardResponse{Dashboard interface{} (the raw dashboard spec map), Meta *models.DashboardMeta, APIVersion string, IsV2 bool}` | params `tools/dashboard.go:36-38`; response `tools/dashboard.go:62-67`; handler `tools/dashboard.go:69-80`; tool `tools/dashboard.go:670` |
| `list_datasources` | `type`: string — optional (substring match on datasource type); `limit`: int — optional (default 50, max 100); `offset`: int — optional (default 0) | `*ListDatasourcesResult{Datasources []dataSourceSummary{ID int64, UID, Name, Type string, IsDefault bool}, Total int (count before pagination), HasMore bool}` | params `tools/datasources.go:51-55`; summary `tools/datasources.go:57-63`; result `tools/datasources.go:65-69`; handler `tools/datasources.go:71-118`; tool `tools/datasources.go:426` |
| `list_incidents` | `limit`: int — optional (default 10); `drill`: bool — optional (false ⇒ adds `isdrill:false` to the query); `status`: string — optional (`active`\|`resolved`) | `*ListIncidentsResult{Incidents []incidentPreviewSummary{IncidentID,Title,Status,Severity,CreatedTime,ModifiedTime,IncidentStart,IsDrill}, HasMore bool}` | params `tools/incident.go:13-17`; summary `tools/incident.go:19-28`; result `tools/incident.go:30-33`; handler `tools/incident.go:52-83`; tool `tools/incident.go:85` |
| `get_incident` / `create_incident` / `add_activity_to_incident` | `get_incident`: `id` string — required. `create_incident`: `title`, `severity`, `roomPrefix` — required; `isDrill` bool, `status`, `attachCaption`, `attachUrl` strings, `labels` []incident.IncidentLabel — optional. `add_activity_to_incident`: `incidentId`, `body` — required; `eventTime` — optional | `get_incident`/`create_incident` → `*incident.Incident` (github.com/grafana/incident-go); `add_activity_to_incident` → `*incident.ActivityItem` | `tools/incident.go:176-178`, `tools/incident.go:96-105`, `tools/incident.go:136-140`; handlers `tools/incident.go:180-192`, `:107-124`, `:142-155`; tools `tools/incident.go:194`, `:126`, `:157` |
| `list_sift_investigations` / `get_sift_investigation` / `find_error_pattern_logs` | `list_sift_investigations`: `limit` int — optional (default 10). `get_sift_investigation`: `id` string — required (UUID). `find_error_pattern_logs` (and `find_slow_requests`): `name` string — required; `labels` map[string]string — required; `start`, `end` time.Time — optional (default last 30 min) | `[]Investigation` / `*Investigation{ID uuid.UUID, CreatedAt, UpdatedAt time.Time, TenantID, Name, GrafanaURL string, Status investigationStatus, FailureReason string, Analyses analysisMeta{Items []analysis}, Datasources InvestigationDatasources}`; the `find_*` tools return `*analysis` (with `Result analysisResult{Successful, Interesting bool, Message string, Details map[string]any}`; for error patterns, each pattern gets an injected `examples` key) | `Investigation` `tools/sift.go:82-104`; `analysisResult` `tools/sift.go:45-50`; params `tools/sift.go:147-149`, `:229-231`, `:266-271`; handlers `tools/sift.go:152-171`, `:233-252`, `:273-347`; tools `tools/sift.go:254`, `:173`, `:349` |

## Resources

One MCP resource is registered — an MCP "App" HTML UI, not data:
- URI `ui://mcp-grafana/panel-viewer.html`, name "Panel Viewer", MIME type `text/html;profile=mcp-app`, body served from the embedded `panelViewerAppHTML` (`ui_apps.go:10-16`, `ui_apps.go:47-65`). Registered unconditionally at server construction (`cmd/mcp-grafana/main.go:361`).
- Tools can link themselves to it via `_meta.ui.resourceUri` using `WithUIResource` (`ui_apps.go:20-32`); result content can carry `_meta.ui.kind` (`ui_apps.go:36-44`, kind `deeplink` at `ui_apps.go:15`).
- No `AddResourceTemplate` calls exist (verified by `rg -n 'AddResourceTemplate' `; no matches).

## Prompts

None. `rg -n 'AddPrompt|mcp.NewPrompt|WithPromptCapabilities'` over the repo returns no matches; the server is created with only instructions and hooks (`cmd/mcp-grafana/main.go:343-346`).

## Auth model

Two independent auth layers.

**1. Server → Grafana credentials.** Env vars are read in `mcpgrafana.go`:
- `GRAFANA_URL` (`mcpgrafana.go:38`), default `http://localhost:3000` (`mcpgrafana.go:35-36`), normalized at read time (`mcpgrafana.go:56`).
- `GRAFANA_SERVICE_ACCOUNT_TOKEN` (`mcpgrafana.go:39`) — preferred; checked first (`mcpgrafana.go:59-62`).
- `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` (`mcpgrafana.go:40`) — read fresh on every call so rotated K8s secrets are picked up without restart (`mcpgrafana.go:67-74`).
- `GRAFANA_API_KEY` (`mcpgrafana.go:41`) — **deprecated**, used only as a fallback and logs a warning (`mcpgrafana.go:77-81`).
- `GRAFANA_USERNAME` / `GRAFANA_PASSWORD` — basic auth alternative (`mcpgrafana.go:44-45`, `mcpgrafana.go:85-95`).
- `GRAFANA_ORG_ID` (`mcpgrafana.go:42`, parsed at `mcpgrafana.go:97-108`).
- `GRAFANA_EXTRA_HEADERS` (JSON map) and `GRAFANA_FORWARD_HEADERS` (comma-separated header names copied from the incoming HTTP request) — `mcpgrafana.go:47-48`, `mcpgrafana.go:110-141`.

**2. Per-request / on-behalf-of headers.** For HTTP transports, config can be supplied per request: `X-Grafana-URL`, `X-Grafana-Service-Account-Token`, and deprecated `X-Grafana-API-Key` (`mcpgrafana.go:50-52`), merged with env config at `mcpgrafana.go:816-854`.

**3. Caller authentication (who may call the MCP server).** `caller_auth.go` implements `RequireBearerToken(expected, logger)` middleware (`caller_auth.go:26-59`): callers must send `Authorization: Bearer <token>`; both sides are SHA-256 hashed and compared in constant time (`caller_auth.go:48-51`); CORS preflight passes through (`caller_auth.go:35-38`); an empty expected token fails closed (`caller_auth.go:39-42`); on success the `Authorization` header is **stripped** so the caller token never reaches Grafana or a cache key (`caller_auth.go:53-56`). Configured by `--server-auth-token`, falling back to `MCP_GRAFANA_SERVER_TOKEN` (`cmd/mcp-grafana/main.go:388`, `cmd/mcp-grafana/main.go:399-401`); it has no effect on stdio. `ForwardsAuthorizationHeader()` (`caller_auth.go:119-126`) detects the conflict where `GRAFANA_FORWARD_HEADERS` would forward `Authorization`, and the server refuses to start when both are set (`caller_auth.go:115-118`). Additional HTTP hardening: Host/Origin allowlists via `--allowed-hosts` / `--allowed-origins` (`cmd/mcp-grafana/main.go:382-383`, `http_security.go`).

**Grafana Cloud vs OSS.** The code does not branch on Cloud vs OSS; the difference is which plugins/services exist. Cloud-only (or plugin-only) categories are `incident`, `oncall`, `sift`, `asserts`, `agento11y`, `assistant` — README explicitly says Agent Observability "work[s] only in Grafana Cloud" and is disabled by default (`README.md:156`), and the Assistant category description notes it "requires the Grafana Assistant plugin" (`cmd/mcp-grafana/main.go:80`). `GRAFANA_URL` is just set to the instance URL for Cloud (`README.md:32`, `README.md:540`).

**Permissions / roles.** README documents required RBAC permission + scope per tool in a large table starting at `README.md:313` (e.g. `roles:read` + `roles:*` for `list_all_roles`, `README.md:317`; `annotations:write` + `annotations:*` for `create_annotation`, `README.md:397`; `grafana-oncall-app.schedules:read` for OnCall schedule tools, `README.md:371`; `datasources:query` scoped to the datasource UID for Pyroscope tools, `README.md:383-386`). Incident and Sift use **basic roles** rather than fine-grained RBAC: Viewer for reads, Editor for writes (`README.md:260-262`, and rows at `README.md:340-343`, `README.md:378-382`). Agent Observability writes need `grafana-agento11y-app.eval:write` granted by the Agento11y Admin role (`README.md:163-164`). README suggests assigning the built-in `Editor` role as a coarse shortcut (`README.md:258`, `README.md:545`).

## Pagination

- **Loki logs:** `DefaultLokiLogLimit = 10`, `MaxLokiLogLimit = 100` (`tools/loki.go:21-25`). `enforceLogLimit` clamps: ≤0 → default (further capped by the configured max), >max → max (`tools/loki.go:493-511`). The max is configurable via `--max-loki-log-limit` (default `tools.MaxLokiLogLimit` = 100, `cmd/mcp-grafana/main.go:166`) and carried on `GrafanaConfig.MaxLokiLogLimit` (`mcpgrafana.go:267-269`). The tool internally requests `limit+1` to detect truncation and reports it in `metadata.resultsTruncated` (`tools/loki.go:677-712`). Loki/label/stats/pattern tools default to a 1-hour window when the range is omitted (`tools/loki.go:665-670`).
- **Prometheus:** `query_prometheus` requires `stepSeconds` for range queries and errors if it is 0 (`tools/prometheus.go:140-142`); there is no `maxDataPoints` parameter. `list_prometheus_metric_names` — `limit` default 10, `page` default 1, sliced client-side (`tools/prometheus.go:207-257`). `list_prometheus_label_names` and `list_prometheus_label_values` — `limit` default 100 (`jsonschema:"default=100"` in the param structs), applied at `tools/prometheus.go:337` and `tools/prometheus.go:396`, then truncated client-side. `list_prometheus_metric_metadata` — `limit` default 10 (`tools/prometheus.go:44-47`). `query_prometheus_histogram` defaults: `rateInterval` `5m`, `startTime` `now-1h`, `endTime` `now`, `stepSeconds` 60 (`tools/prometheus.go` handler `queryPrometheusHistogram`).
- **Dashboard search:** `limit` default 50, hard-capped at 100; `page` default 1 (1-indexed) (`tools/search.go:69-85`). `hasMore` is inferred from a full page (`tools/search.go:94`). `search_folders` takes no limit/page at all (`tools/search.go:114-116`).
- **Datasources:** `defaultListDataSourceLimit = 50`, `maxListDataSourceLimit = 100` (`tools/datasources.go:23-24`), applied with an `offset` (`tools/datasources.go:84-112`).
- **Alert rules:** `DefaultListAlertRulesLimit = 200`, `DefaultListContactPointsLimit = 100` (`tools/alerting.go:13-14`); hard cap `maxRulesLimit = 200` enforced both server-side (`tools/alerting_client.go:132-133`) and client-side (`tools/alerting_manage_rules_handlers.go:249-261`). Contact points fall back to 100 (`tools/alerting_contact_points.go:77`, `:126-127`).
- **Sift:** `list_sift_investigations` limit defaults to 10 (`tools/sift.go:239-241`).
- **Incidents:** `list_incidents` limit defaults to 10 (`tools/incident.go:57-60`); `HasMore` comes from the incident API cursor (`tools/incident.go:81`).
- **Pyroscope:** `max_node_depth` (a count of functions/nodes, default 100) trims the profile table (`tools/pyroscope.go:643`, applied at `tools/pyroscope.go:545-546`).

## Rate limits

**No tool-call rate limiting found.** There is no token bucket, semaphore, or concurrency limiter over tool invocations or Grafana API calls anywhere in the Go source (`rg -ni 'rate.?limit|throttl|x/time/rate|semaphore'` over non-test Go files returns only unrelated matches: a Datadog datasource JSON schema field `jsonData.logApiRateLimits` at `tools/datasource_schemas/grafana-datadog-datasource_schema.json:35-38`, and test fixtures).

The only retry/backoff logic is Assistant-specific: `assistantInitialBackoff = 500ms`, `assistantMaxBackoff = 5s`, exponential with cap (`tools/assistant.go:52-56`, `tools/assistant.go:326-336`), retried on `http.StatusTooManyRequests` among other statuses (`tools/assistant.go:311`).

Related, but not rate limits: a global Grafana client timeout via `--grafana-timeout` (default `mcpgrafana.DefaultGrafanaClientTimeout`, `cmd/mcp-grafana/main.go:169`; README says `10s` at `README.md:440`), and session reaping via `--session-idle-timeout-minutes` (default 30, `cmd/mcp-grafana/main.go:741`).

## Error shapes

- **Handler `error` → tool result, not a protocol error.** `ConvertTool`'s wrapper catches the handler's second return value and returns `&mcp.CallToolResult{Content: []mcp.Content{mcp.TextContent{Type:"text", Text: handlerErr.Error()}}, IsError: true}` with a `nil` Go error (`tools.go:322-339`). So a failed Grafana/Prometheus/Loki call arrives at the client as an `isError: true` tool result whose single text block is the **raw wrapped Go error string**.
- **Error strings are `fmt.Errorf` chains.** E.g. `"getting backend: %w"` (`tools/prometheus.go:41`), `"listing Prometheus metric metadata: %w"` (`tools/prometheus.go:51`), `"parsing end time: %w"` (`tools/prometheus.go:134`), `"creating Loki backend: %w"` (`tools/loki.go:653`), `"search dashboards for %+v: %w"` (`tools/search.go:89`), `"alerting_manage_rules: %w"` (`tools/alerting_manage_rules_handlers.go:18`), `"list incidents: %w"` (`tools/incident.go:77`), `"getting investigation: %w"` (`tools/sift.go:167`). The underlying `%w` is typically a `grafana-openapi-client-go` typed error whose `Error()` embeds the HTTP status. A 404 on `get_datasource` is specially rewritten to `"datasource with UID '%s' not found. Please check if the datasource exists and is accessible"` (`tools/datasources.go:471`).
- **`HardError` escalates to a JSON-RPC protocol error.** Wrapping an error in `*mcpgrafana.HardError` makes `ConvertTool` return `nil, hardErr.Err` instead of a tool result (`tools.go:32-45`, `tools.go:326-329`). Intended for non-recoverable failures such as missing auth.
- **Argument validation.** Unknown argument keys are rejected as a tool-result error (not a protocol error) listing the valid arguments: `unknown argument "x"; valid arguments: a, b, c` (`tools.go:265-273`, message builder `tools_param_validation.go:46-67`). The schema also advertises `additionalProperties: false` (`tools.go:398-404`). Marshal/unmarshal failures of the arguments themselves *do* become protocol errors (`tools.go:257`, `tools.go:279`). LLM-friendly coercions are applied first: `"42"` → `42` for int fields and `"v"` → `["v"]` for `[]string` fields (`tools.go:74-128`).
- **Nil results** are returned as the literal text `"null"` rather than nil, to avoid a nil deref in mcp-go (`tools.go:352-357`). Non-string, non-`CallToolResult` returns are JSON-marshalled into a single text block (`tools.go:385-391`).
- **Huge results: a byte guard that errors rather than truncates.** `defaultResponseLimitBytes = 10MB` (`tools/response_utils.go:8`); `readResponseBody` reads `limit+1` and returns `"response body exceeds maximum size of %d bytes; try narrowing your query"` if exceeded (`tools/response_utils.go:12-21`). It is used across essentially every HTTP-backed tool: `tools/loki.go:130`, `tools/api.go:123`, `tools/alerting_client.go:303`, `tools/sift.go:472`, `tools/asserts.go:84`, `tools/cloudwatch.go:412/474/538`, `tools/pyroscope.go:322`, `tools/graphite.go:81`, `tools/es_backend.go:187`, `tools/quickwit.go:156`, `tools/snapshot.go:107`, `tools/plugins.go:79`, `tools/provisioning.go:117/320`, `tools/navigation.go:258`, `tools/oncall_proxy.go:115/155`, `tools/agento11y.go:83`, `tools/ds_query.go:30`, `tools/loki_backend_victorialogs.go:128`, `tools/prom_backend_cloudmonitoring.go:297`. Athena uses its own equal-valued constant `athenaResponseLimitBytes = 10MB` (`tools/athena.go:33-34`, applied `tools/athena.go:106`). Assistant streams under the same cap (`tools/assistant.go:484-488`).
- **Row-level truncation** (as opposed to erroring) exists only in a few places: Loki log lines (`tools/loki.go:703-712`, surfaced via `metadata.resultsTruncated`), Pyroscope profile tables (`tools/pyroscope.go:545-546`, plus a note about Pyroscope's own server-side tree truncation at `tools/pyroscope.go:561-563`), alert-rule lists (`tools/alerting_manage_rules_handlers.go:249-261`), and label/metric-name lists (Prometheus limits above).

## Not exposed (E3)

Confirmed absent from the tool surface (verified by grepping every `MustTool` name and by searching `tools/` for the corresponding Grafana client calls):

- **No dashboard delete.** `update_dashboard` is the only dashboard mutation (`tools/dashboard.go:681`, `tools/dashboard.go:1219-1227`). `DeleteDashboardByUID` appears only in test helpers (`tools/run_panel_query_integration_test.go:142`, `:321`).
- **No folder delete or update.** The folder category registers exactly one tool, `create_folder`, and nothing at all in read-only mode (`tools/folder.go:55-59`).
- **No datasource delete.** Only `list/get/create/update/check health` exist (`tools/datasources.go:825-833`).
- **No user, team, or org management writes.** The admin category is entirely read-only — `c.Teams.SearchTeams` and `c.AccessControl.*` read calls only (`tools/admin.go:27`, `tools/admin.go:82-243`, registrar `tools/admin.go:262-272` takes no `enableWriteTools` argument). There is no create/update/delete user, no team membership change, no role assignment write.
- **No incident resolve/close or severity update.** Incident writes are limited to `create_incident` and `add_activity_to_incident` (`tools/incident.go:167-174`). Status can only be set at creation time (`tools/incident.go:101`).
- **No OnCall writes at all.** `AddOnCallTools` registers seven read tools and takes no write flag (`tools/oncall.go:584-592`) — no schedule creation, no alert-group acknowledge/resolve.
- **No annotation delete.** Only `get`/`create`/`update`/`get tags` (`tools/annotations.go:231-238`).
- **No plugin uninstall.** Only `search_plugin_information`, `get_plugin`, `install_plugin` (`tools/plugins.go:408-414`).
- **No provisioning writes.** Only `list_provisioning_repositories` and a dry-run `validate_provisioning_file` (`tools/provisioning.go:388-391`).
- **Escape hatch:** anything missing can still be reached through `grafana_api_request`, which permits GET/POST/PUT/PATCH/DELETE against any Grafana API path when writes are enabled (`tools/api.go:18-24`, `tools/api.go:173`) — so "not exposed" means "no dedicated tool", not "unreachable". In read-only mode that escape hatch is closed to GET only (`tools/api.go:49-59`).
- **Documented functional gaps (TODO / unsupported):**
  - `query_loki_patterns` is not supported on VictoriaLogs datasources — explicit error (`tools/loki_backend_victorialogs.go:287-291`).
  - `run_panel_query` rejects datasource types it does not support and tells the caller to use the native tool (`tools/run_panel_query.go:228`).
  - `update_dashboard` patch paths support only numeric array indices; JSONPath filter expressions `[?(@.id==2)]` and wildcards `[*]` are explicitly rejected (`tools/dashboard.go:941-946`).
  - Dashboard v2 writes hardcode `v2beta1` instead of negotiating the version — `// TODO: negotiate the version to write instead of hardcoding v2beta1` (`tools/dashboard.go:506`).
  - `generate_deeplink` supports only `dashboard`, `panel`, `explore` resource types (`tools/navigation.go:143`).
  - `query_influxdb` supports only `influxql` and `flux` dialects (`tools/influxdb.go:83`).
  - Proxied tools currently support only Tempo as a proxied MCP source; adding another datasource type requires a code change (`proxied_tools.go:34`, `docs/sources/configure/proxied-tools.md:19`).
  - `list_prometheus_metric_metadata` is flagged experimental in its own description (`tools/prometheus.go:58`).
- README contains no consolidated "limitations"/"known issues" section (`rg -ni 'limitation|known issue|caveat' README.md` matches only an unrelated OTEL note at `README.md:1161`).

## Notes for mocking

- **Category enablement is the first thing to model.** A default-flag server exposes only the 21 default categories (`cmd/mcp-grafana/main.go:118`); a mock that advertises `query_clickhouse` or `list_teams` without an explicit `--enabled-tools` override is unfaithful. `admin`, `agento11y`, `assistant`, `athena`, `clickhouse`, `cloudwatch`, `elasticsearch`, `examples`, `graphite`, `quickwit`, `runpanelquery`, `snowflake` are off by default.
- **Grafana-Cloud-only vs OSS.** `incident` (`tools/incident.go`), `oncall` (`tools/oncall.go`), `sift` (`tools/sift.go`), `asserts` (`tools/asserts.go`), `agento11y` (`tools/agento11y.go`), `assistant` (`tools/assistant.go`) all talk to Cloud services/plugins and will fail against a plain OSS Grafana even though they are *registered* (`incident`, `oncall`, `sift`, `asserts` are in the default enabled list). OSS-safe categories are `search`, `datasource`, `dashboard`, `folder`, `prometheus`, `loki`, `alerting`, `annotations`, `snapshot`, `plugin`, `api`, `navigation`, `admin`, `pyroscope`, `provisioning`, `config`, `rendering` (rendering additionally needs the Image Renderer plugin, `tools/rendering.go:354`).
- **Six tool names have two implementations.** `alerting_manage_rules`, `grafana_api_request`, `generate_deeplink`, `agento11y_manage_evaluators`, `agento11y_manage_eval_rules`, `agento11y_manage_eval_collections` register under one name with different schemas and descriptions depending on `--disable-write`. A mock must pick one variant per configuration; the read-only `alerting_manage_rules` schema has a *smaller* `operation` enum (`tools/alerting_manage_rules_types.go:595` vs `:630`).
- **The clients that matter differ per category.** Grafana-native tools go through the generated OpenAPI client (`mcpgrafana.GrafanaClientFromContext`, e.g. `tools/search.go:62`); Loki/Sift/Asserts/OnCall/Athena/agento11y hand-roll HTTP through the datasource proxy or plugin routes (`tools/loki.go:88-107`, `tools/sift.go`, `tools/oncall_proxy.go`). Loki additionally probes `/proxy` and falls back to `/resources` on 403/500 (`tools/loki.go:79-81`).
- **Error mocking:** return `isError: true` with a single text block containing the raw Go error string, e.g. `"listing Prometheus metric metadata: <underlying>"` — not a structured error object (`tools.go:330-338`).
- **Size mocking:** any body >10MB should produce the literal error `response body exceeds maximum size of 10485760 bytes; try narrowing your query` (`tools/response_utils.go:18`), *not* a truncated payload. Only Loki logs, Pyroscope tables, and alert-rule lists truncate silently and flag it.
- **Loki metadata block is mandatory in realistic mocks.** `query_loki_logs` always returns `metadata` with `linesReturned`, `maxLinesAllowed`, `resultsTruncated`, `totalLinesScanned` (nullable) and, when the default window was used, a `hints` block explaining the 1-hour lookback (`tools/loki.go:713-741`).
- **Prometheus returns Prometheus-native JSON.** `data` is `model.Value` — a `matrix` (range) or `vector` (instant) as serialized by `prometheus/common/model`, wrapped in `{data, hints?, warnings?}` (`tools/prometheus.go:78-82`). Don't invent a flat row shape.
- **Argument strictness.** Unknown keys are rejected with a listing of valid arguments (`tools.go:270-273`), but `"42"`→`42` and `"x"`→`["x"]` coercions are silently accepted (`tools.go:81-128`) — a faithful mock should accept both forms.
- **Proxied tools appear late.** With SSE/streamable-http they are discovered per session on the first `tools/list` or `tools/call` (`cmd/mcp-grafana/main.go:309-330`), so the tool list can grow after initialize; with stdio they are discovered once at startup (`docs/sources/configure/proxied-tools.md:38`).
- **One resource, no prompts.** Advertise `ui://mcp-grafana/panel-viewer.html` (`ui_apps.go:12`) and an empty prompt list.
