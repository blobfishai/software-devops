# elastic/mcp-server-elasticsearch — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/elastic__mcp-server-elasticsearch` @ git commit `9e64b84` (2026-06-23), read 2026-08-11
**Language / framework:** **Rust**, using the `rmcp` crate (`#[tool_router]` / `#[tool]` / `#[tool_handler]` proc macros) + the official `elasticsearch` Rust client. `Cargo.toml`; `src/servers/elasticsearch/base_tools.rs:29` imports `rmcp_macros::{tool, tool_handler, tool_router}`.
**Registration entrypoint:** `src/servers/elasticsearch/base_tools.rs:86` (`#[tool_router] impl EsBaseTools`). Server handler and capabilities: `src/servers/elasticsearch/base_tools.rs:292-302` (`ServerCapabilities::builder().enable_tools().build()` — **tools only**, no resources, no prompts capability advertised).
**Protocol version pinned:** `ProtocolVersion::V_2025_03_26` — `src/servers/elasticsearch/base_tools.rs:296`.

> **IMPORTANT — this server is deprecated.** `README.md:3-6`: "This MCP server is deprecated and will only receive critical security updates going forward. It has been superseded by the Elastic Agent Builder MCP endpoint, which is available in Elastic 9.2.0+ and Elasticsearch Serverless projects." Historically this repo was TypeScript; the current tree is a Rust rewrite (no TS sources remain under `src/`).

---

## Full tool list (5 tools)

All five are annotated `read_only_hint = true`. There are **zero write tools**.

| # | Tool | R/W | Purpose | Source |
|---|------|-----|---------|--------|
| 1 | `list_indices` | R | "List all available Elasticsearch indices" (via `_cat/indices`) | `src/servers/elasticsearch/base_tools.rs:90-94` |
| 2 | `get_mappings` | R | "Get field mappings for a specific Elasticsearch index" | `src/servers/elasticsearch/base_tools.rs:118-122` |
| 3 | `search` | R | "Perform an Elasticsearch search with the provided query DSL." | `src/servers/elasticsearch/base_tools.rs:150-154` |
| 4 | `esql` | R | "Perform an Elasticsearch ES\|QL query." | `src/servers/elasticsearch/base_tools.rs:222-226` |
| 5 | `get_shards` | R | "Get shard information for all or specific indices." (via `_cat/shards`) | `src/servers/elasticsearch/base_tools.rs:256-260` |

Tool names are derived by the `#[tool]` macro from the Rust `async fn` names (`list_indices`, `get_mappings`, `search`, `esql`, `get_shards`). Cross-checked against the documented list in `README.md:261-265`, which matches exactly.

### Config-declared *custom* tools (WIP, not enabled)
The config format supports user-declared extra tools of two kinds — `esql` (a parameterised ES|QL query) and `search_template` (a stored or inline search template) — defined in `src/servers/elasticsearch/mod.rs:110-172` (`Tools`, `CustomTool`, `EsqlTool`, `SearchTemplateTool`). An `include`/`exclude` allowlist for built-in tools also exists in the type (`Tools.incl_excl`, `src/servers/elasticsearch/mod.rs:112`). **However** the sample config marks this whole block `/* WIP */` (`elastic-mcp.json5:10`) and the built-in default config (`src/lib.rs:96-105`) declares no `tools` block, so out of the box only the 5 base tools are served. `ElasticsearchMcpConfig.prompts: Vec<String>` also exists (`src/servers/elasticsearch/mod.rs:66-67`) but is unused by `new_with_config` (`src/servers/elasticsearch/mod.rs:178-214`).

---

## Key tools (all 5)

| Tool | Params (`name`: type — required?) | Returns (concrete shape) | Source |
|---|---|---|---|
| `list_indices` | `index_pattern`: string — **required** ("Index pattern of Elasticsearch indices to list") | `CallToolResult` with **two** content blocks: `Content::text("Found {n} indices:")` then `Content::json(Vec<CatIndexResponse>)` where `CatIndexResponse { index: String, status: String, "docs.count": u64 }`. Underlying call is `_cat/indices` with `h=index,status,docs.count&format=json`. | params `base_tools.rs:50-54`; handler `:94-114`; type `:335-341` |
| `get_mappings` | `index`: string — **required** | Two blocks: `Content::text("Mappings for index {index}:")` then `Content::json(Mappings)` = `{ mappings: { _meta?, properties: { <field>: { type: String, ...settings } } } }`. **Gotcha:** on a wildcard index it silently returns only the *first* mapping (`response.values().next().unwrap()`, `:137`) — and `.unwrap()` will **panic** if the map is empty. | params `:56-60`; handler `:122-143`; types `:358-378` |
| `search` | `index`: string — **required**; `fields`: `Vec<String>` — optional; `query_body`: JSON object — **required** ("Complete Elasticsearch query DSL object that can include query, size, from, sort, etc.") | 1–3 blocks: `Content::text("Total results: {total}, showing {n}.")`, then `Content::json([...])` of **only the `_source`** of each hit (`Hit { _source }` — `_id`, `_score`, `_index` are dropped), then optionally `Content::text("Aggregations results:")` + `Content::json(aggregations)`. | params `:62-72`; handler `:154-218`; types `:309-331` |
| `esql` | `query`: string — **required** (full ES\|QL text) | Two blocks: `Content::text("Results")` then `Content::json(objects)` where the columnar ES\|QL response (`columns[]`, `values[][]`) is **pivoted into an array of row objects** keyed by column name (`:239-246`). Column *types* are discarded. `is_partial` is parsed but never surfaced (`:396`). | params `:74-78`; handler `:226-252`; types `:382-399` |
| `get_shards` | `index`: string — **optional** (omit for all indices) | Two blocks: `Content::text("Found {n} shards:")` then `Content::json(Vec<CatShardsResponse>)` = `{ index, shard, prirep, state, docs?, store?, node? }`. | params `:80-84`; handler `:260-289`; types `:343-354` |

Note the consistent response idiom: **a short human-readable text preamble followed by a JSON content block.** A code comment at `base_tools.rs:203-206` records a deliberate design change — "Original prototype sent a separate content for each document, it seems to confuse some LLMs" — so documents are now batched into one JSON array. The `fields` param on `search` exists purely as an LLM affordance: `base_tools.rs:147-149` — "The additional 'fields' parameter helps some LLMs that don't know about the `_source` request property to narrow down the data returned and reduce their context size". It is merged into `query_body._source` at `:167-176`.

---

## Resources
None. `ServerCapabilities::builder().enable_tools().build()` (`src/servers/elasticsearch/base_tools.rs:297`) enables tools only. A `// TODO: search as resources?` comment sits at `src/servers/elasticsearch/mod.rs:68`.

## Prompts
None served. A `prompts: Vec<String>` config field exists (`src/servers/elasticsearch/mod.rs:66-67`) but is never read by the constructor (`:178-214`).

## Auth model
- **Config-file / env driven.** Default built-in config (`src/lib.rs:96-105`):
  `ES_URL` (required), `ES_API_KEY`, `ES_USERNAME`, `ES_PASSWORD`, `ES_SSL_SKIP_VERIFY` (default `false`).
- Credential precedence in `src/servers/elasticsearch/mod.rs:179-186`: **API key wins**; else username **+** password (missing password → `anyhow` error `"missing password"`); else **no credentials at all** (anonymous).
- Empty `ES_URL` → error `"Elasticsearch URL is empty"` (`mod.rs:189-191`).
- `ssl_skip_verify` → `CertificateValidation::None` (`mod.rs:203-205`).
- **Per-request auth pass-through (HTTP transport):** `EsClientProvider::get()` (`mod.rs:83-106`) reads the incoming HTTP `Authorization` header and rebuilds the ES client with `Credentials::AuthorizationHeader`, so a multi-tenant HTTP deployment forwards the caller's own ES credentials. It strips a spurious `Bearer ` prefix from `Bearer ApiKey …` / `Bearer Basic …` (`mod.rs:96-99`) because "MCP inspector insists on sending a bearer token".
- User-Agent is pinned to `elastic-mcp/{version}` (`mod.rs:206-209`).
- HTTP mode runs **stateless** (`stateful_mode: false`, `NeverSessionManager`, `src/lib.rs:80-84`) and binds `127.0.0.1:8080` by default (`src/lib.rs:63-69`).
- **Required ES privileges:** NOT DETERMINED FROM SOURCE — no privilege list is enforced or documented in code. README only advises "Use API keys with minimal required permissions (read-only access to specific indices when possible)" (`README.md:242`). Implied by the API calls: `monitor`/`view_index_metadata` for `_cat/indices` + `_cat/shards`, `view_index_metadata` for `_mapping`, `read` for `_search` and `_query`.

## Pagination
**There is no pagination layer.** The server delegates entirely to Elasticsearch:
- `search`: paging is whatever the model puts in `query_body` (`size`, `from`, `search_after`, `sort`). The param description explicitly says so (`base_tools.rs:70`). No default `size` is injected, so ES's own default of 10 hits applies. No scroll / PIT support.
- `esql`: paging is whatever `LIMIT` the model writes into the query string. No injected limit.
- `list_indices` / `get_shards`: return **every** matching row from `_cat` with no cap.
- No `size`/`from`/`limit`/`max_results` parameter exists on any tool. There is **no truncation and no byte cap anywhere in the handler code** — a broad `search` or `list_indices` on a big cluster dumps the full response into the model's context. The only mitigations are advisory: the `fields` param and ES's own default page size.

## Rate limits
None found. No retry, backoff, 429 handling, or concurrency limiting anywhere in `src/servers/` or `src/protocol/`.

## Error shapes
Single funnel, in `src/servers/elasticsearch/mod.rs:244-275`:
```rust
pub fn internal_error(e: impl std::error::Error) -> rmcp::Error {
    rmcp::Error::internal_error(e.to_string(), None)
}
pub fn handle_error(result: Result<Response, elasticsearch::Error>) -> Result<Response, rmcp::Error> {
    match result { Ok(resp) => resp.error_for_status_code(), Err(e) => { tracing::error!(...); Err(e) } }.map_err(internal_error)
}
```
Consequences worth mocking faithfully:
- **Every** upstream failure — 404 `index_not_found_exception`, 400 `parsing_exception`, 401/403, connection refused — becomes a **JSON-RPC protocol error** (`rmcp::Error::internal_error`), *not* a `CallToolResult` with `isError: true`. The model gets the Rust client's `Display` string, not the ES error body: `error_for_status_code()` discards the response body, so the structured `{"error":{"type":"index_not_found_exception","reason":...}}` is **lost**.
- The source itself flags this as a deficiency — `mod.rs:249-252`: "This should be refined to handle common error types such as index not found, which could be caused by the client hallucinating an index name." plus a `TODO (in rmcp)` at `:253-254` about wanting an error variant that carries a `CallToolResult`.
- `get_mappings` can **panic** on an index pattern that matches nothing (`.unwrap()` on `values().next()`, `base_tools.rs:137`).
- "Too many results" is **not represented at all** — there is no such concept in this server.

## Not exposed (E3) — Elasticsearch API surface deliberately omitted
The MCP surface is a *tiny* read-only slice of the Elasticsearch API. Absent, with no code path anywhere in `src/`:
- **All writes:** no `index`, `bulk`, `update`, `delete_by_query`, `update_by_query`, no index create/delete, no alias management, no reindex. The read-only intent is encoded as `read_only_hint = true` on all five tools (`base_tools.rs:92,120,152,224,258`) but there is **no enforcement flag** — read-only is achieved simply by not implementing writes (and, operationally, by the advice to use a read-only API key, `README.md:242`).
- **Cluster/ops APIs:** no `_cluster/health`, `_cluster/stats`, `_nodes`, `_tasks`, `_cat/nodes`, `_cat/allocation`, `_cat/thread_pool`. Only `_cat/indices` and `_cat/shards` are wrapped.
- **Index lifecycle / management:** no ILM, no snapshot/restore, no settings read or write, no rollover, no `_analyze`.
- **Search features:** no scroll, no point-in-time, no async search, no `_msearch`, no `_count`, no `terms_enum`, no `_field_caps`, no `_sql`, no vector/semantic-specific helper.
- **Security/Watcher/Transform/ML/Ingest pipelines:** entirely absent.
- **Kibana / alerting:** out of scope; this server talks only to Elasticsearch.
- **Declared but unimplemented in this build:** custom `esql` and `search_template` tools and the built-in-tool `include`/`exclude` allowlist are typed but marked `/* WIP */` (`elastic-mcp.json5:10-11`, types at `src/servers/elasticsearch/mod.rs:110-172`); the sample config's stated intent is to "Exclude the 'search' builtin tool as it's too broad" (`elastic-mcp.json5:12`).

## Notes for mocking
1. Only **5 tools**, all read. If a simulated world needs to write to Elasticsearch, no real MCP surface exists for that — do not invent one.
2. Reproduce the **two-block response idiom**: a text preamble (`"Found 12 indices:"`, `"Total results: 4213, showing 10."`, `"Mappings for index X:"`, `"Results"`) followed by a JSON block. Agents parse the preamble for counts.
3. `search` returns **only `_source`** — no `_id`, no `_score`, no `_index`. An agent cannot correlate a hit back to a document id through this tool. That is a real, exploitable limitation for task design.
4. `esql` returns **row objects, not the columnar ES|QL envelope**, and drops column types.
5. `list_indices` returns exactly three fields: `index`, `status`, `docs.count`. Nothing about size, health colour, or replica count.
6. `get_shards` returns `index, shard, prirep, state, docs, store, node` — enough to reason about unassigned shards, which is a plausible incident scenario.
7. **Total results vs. returned results diverge silently.** `"Total results: 40231, showing 10."` with no `size` given is the default failure mode; a faithful mock should exhibit it so agents learn to set `size`/`from`.
8. Upstream errors arrive as **protocol-level errors with a stringified message and no ES error body**. Do not mock a rich `{"error":{"type":...}}` payload — the real server throws it away.
9. `get_mappings` on a wildcard returns only one index's mapping; on a non-matching pattern the real binary panics.
10. Auth is `ES_URL` + (`ES_API_KEY` | `ES_USERNAME`+`ES_PASSWORD`); over HTTP the caller's own `Authorization` header overrides server credentials per request.
11. Mark this server **deprecated** in any tool catalogue — Elastic has moved to Agent Builder's MCP endpoint (`README.md:3-6`), so an agent world modelling "current Elastic" should expect a different, richer surface.
