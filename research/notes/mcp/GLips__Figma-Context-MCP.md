# GLips/Figma-Context-MCP (Framelink) — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/GLips__Figma-Context-MCP` @ git commit `c083d65` (2026-06-24), read 2026-08-11
**Language / framework:** TypeScript, `@modelcontextprotocol/sdk` `McpServer` + `server.registerTool(...)`, zod schemas. `src/mcp/index.ts:1`, `:80`.
**Registration entrypoint:** `src/mcp/index.ts:75-121` (`registerTools`). Server metadata at `src/mcp/index.ts:15-20`.
**Transports:** stdio and stateless StreamableHTTP at `/mcp` (also `/sse` for back-compat) — `src/server.ts`; documented in `CLAUDE.md`.

---

## Full tool list (2 tools)

| # | Tool | R/W | Purpose | Source |
|---|------|-----|---------|--------|
| 1 | `get_figma_data` | **R** (`annotations: { readOnlyHint: true }`) | "Get comprehensive Figma file data including layout, content, visuals, and component information" | name/desc `src/mcp/tools/get-figma-data-tool.ts:109-115`; registration `src/mcp/index.ts:80-98` |
| 2 | `download_figma_images` | **W to local disk** (`annotations: { openWorldHint: true }`, no `readOnlyHint`) | Download SVG/PNG/GIF assets for given nodes and write them into the server's image directory | name `src/mcp/tools/download-figma-images-tool.ts:249-255`; registration `src/mcp/index.ts:100-120` |

`download_figma_images` is **conditionally registered** — suppressed when `--skip-image-downloads` / `SKIP_IMAGE_DOWNLOADS` is set (`src/mcp/index.ts:100`, config at `src/config.ts:152-155`). So the served surface is either 2 tools or 1.

This is deliberate minimalism. `CLAUDE.md` (Philosophy): "**Unix Philosophy** — Tools should have one job and few arguments. Keep tools simple to avoid confusing LLMs" and "**Focused Scope** — The server only handles 'ingesting designs for AI consumption.' Out of scope: image manipulation, CMS syncing, code generation, third-party integrations." Also "**Project-level Config** — Options unlikely to change between requests should be CLI arguments, not tool parameters" — which is why output format, image directory and auth are CLI/env, not tool params.

---

## Key tools (both)

| Tool | Params (`name`: type — required?) | Returns (concrete shape) | Source |
|---|---|---|---|
| `get_figma_data` | `fileKey`: string, regex `/^[a-zA-Z0-9]+$/` — **required**; `nodeId`: string, regex `/^I?\d+[:\|-]\d+(?:;\d+[:\|-]\d+)*$/` — optional; `depth`: number — optional ("Do NOT use unless explicitly requested by the user. Controls how many levels deep to traverse the node tree.") | `{ content: [{ type: "text", text: <serialized simplified design> }] }` — **one text blob**, format decided server-side by `--format`/`OUTPUT_FORMAT` ∈ `tree` (default) \| `yaml` \| `json`. Top-level keys of the serialized object: `metadata` (`{ name, components, componentSets }`), `nodes`, `globalVars` (`{ styles }`), `elements`. | params `src/mcp/tools/get-figma-data-tool.ts:14-37`; return `:95-97`; format enum `src/utils/serialize.ts:5-7`; default `src/mcp/index.ts:33` and `src/config.ts:174`; wrapper shape `src/utils/serializable-design.ts:4-12` |
| `download_figma_images` | `fileKey`: string — **required**; `nodes`: array of `{ nodeId: string (**req**), imageRef?: string, gifRef?: string, fileName: string matching `/^[a-zA-Z0-9_.-]+\.(png\|svg\|gif)$/` (**req**), needsCropping?: boolean, cropTransform?: number[][], requiresImageDimensions?: boolean, filenameSuffix?: string }` — **required**; `pngScale`: positive number — optional, **default 2**; `localPath`: string — **required** (relative to the server's image dir) | Success: `{ content: [{ type: "text", text: "Downloaded {n} images to \`{resolvedPath}\`:\n- {file}: {W}x{H}[ \| {cssVariables}][ (cropped)][ (also requested as: …)]\n…" }] }` — a **human-readable markdown list**, not JSON. Failure: `{ isError: true, content: [{ type: "text", text: "Failed to download images: {message}" }] }` | params `src/mcp/tools/download-figma-images-tool.ts:16-89`; success return `:176-190`; error return `:191-203` |

Both tools emit **MCP progress notifications** during long calls (3-step progress + heartbeats): `sendProgress(extra, 0..2, 3, "…")` at `src/mcp/tools/get-figma-data-tool.ts:69,76,86` and `download-figma-images-tool.ts:133,140,155`, helper in `src/mcp/progress.ts`. Heartbeat text includes a live node count: `` `Simplifying design data (${progress.getNodeCount()} nodes processed)` `` (`get-figma-data-tool.ts:79`).

---

## The simplification layer (the point of this server)

Raw Figma `GET /v1/files/:key` responses are enormous; this server's value is the reduction. Pipeline in `src/services/get-figma-data.ts:73-157`: **fetch → simplify → serialize**, with byte counts measured at each stage (`rawSizeKb` vs `simplifiedSizeKb`, `:104`, `:137`).

1. **Fetch** — `figmaService.getRawNode(fileKey, nodeId, depth)` when `nodeId` is given, else `getRawFile(fileKey, depth)` (`src/services/get-figma-data.ts:92-96`). Endpoints: `/files/{fileKey}[?depth=]` and `/files/{fileKey}/nodes?ids={nodeId}[&depth=]` (`src/services/figma.ts:313`, `:333`).
2. **Extractor walk** — `simplifyRawFigmaObject(rawApiResponse, allExtractors, { maxDepth: depth, afterChildren: collapseSvgContainers, nodeCounter })` (`src/services/get-figma-data.ts:110-114`). `allExtractors = [layoutExtractor, textExtractor, visualsExtractor, componentExtractor]` (`src/extractors/built-in.ts:320`); each is an `ExtractorFn(node, result, context)` applied per node by the recursive walker (`src/extractors/node-walker.ts`, type at `src/extractors/types.ts:99-103`). Alternative presets exist but are unused by the tool: `layoutAndText`, `contentOnly`, `visualsOnly`, `layoutOnly` (`src/extractors/built-in.ts:325-340`).
3. **SVG container collapse** — `collapseSvgContainers` folds all-vector subtrees into a single node (`src/extractors/built-in.ts:352` `SVG_ELIGIBLE_TYPES`, `:400`).
4. **Finalize / dedup pass** — `src/extractors/finalize.ts:34-52`. Two global transforms that a single walk cannot do:
   - **Count-gated style hoisting**: a style stays in `globalVars.styles` only when **2+** nodes reference it or it is a named Figma style; single-use styles are inlined back onto the node "dropping the indirection tax" (`finalize.ts:16-18`, `inlineSingleUseStyles`). The style-bearing fields are exactly `["layout","fills","strokes","effects","textStyle"]` (`finalize.ts:55`).
   - **Element templates**: node bodies (everything except `id`/`name`/`children`) appearing **2+** times are hoisted once into `elements`, content-addressed as `EL-xxxxxxxx` (sha hash of a `stableStringify`), and each occurrence becomes `{ id, name, template, children? }` (`src/extractors/types.ts:111-117`, `:126`; `finalize.ts:19-21`, `deduplicateElements`).
   - A third step `inlineExclusiveStyles` collapses the double indirection when a surviving style is used only by instances of one deduplicated element (`finalize.ts:49`).
5. **Noise-name stripping** — auto-generated names (`Rectangle 12`) and TEXT-layer names are deleted before serialization (`src/utils/serializable-design.ts:14-33`, `src/utils/node-names.ts` `isNoiseName`).
6. **Default-value omission** — `CLAUDE.md` (Token Efficiency): "Omit default values where LLMs can reliably infer the expectation… (e.g. `strokeAlign: INSIDE` matches the default CSS `border` an LLM already produces, so it is dropped; only `OUTSIDE`/`CENTER` are emitted.)"
7. **Serialize** — `serializeResult(wrapForSerialization(design), outputFormat)` (`src/services/get-figma-data.ts:133`; `src/utils/serialize.ts:17-19`). The default `tree` format is a bespoke token-efficient indented format, node line = `[TYPE] "name" #id key=value key=value ...`, with `NAME:`, `GLOBAL_VARS:`, `ELEMENTS:`, `COMPONENTS:`, `COMPONENT_SETS:` sections (`src/utils/serialize-tree.ts:5-40`). Rationale in the doc comment: "Structural keys (id, name, type, children) are encoded positionally on each node line, eliminating the YAML/JSON overhead of repeating those keys for every node."

**Resulting node fields** (`src/extractors/types.ts:128-170`): `id`, `name?`, `type?`, `template?`, `text?`, `textStyle?`, `boldWeight?`, `fills?`, `styles?`, `strokes?`, `strokeWeight?`, `strokeDashes?`, `strokeWeights?`, `strokeAlign?`, `effects?`, `opacity?`, `borderRadius?`, `layout?`, `componentId?`, `componentProperties?`, `componentPropertyReferences?`, `children?`. Style-bearing fields hold **either** a `globalVars` key string **or** the inline value — a union the consumer must handle (`types.ts:149-152`).

---

## Resources
None. `src/mcp/index.ts` registers only tools; no `registerResource`/`ResourceTemplate` call exists in `src/`.

## Prompts
None. No prompt registration in `src/mcp/`.

## Auth model
- Two mutually-acceptable credentials, CLI flag or env: `FIGMA_API_KEY` / `--figma-api-key` (Personal Access Token) and `FIGMA_OAUTH_TOKEN` / `--figma-oauth-token` (OAuth Bearer). `src/config.ts:98-99`, `:148-149`.
- Header selection: OAuth → `Authorization: Bearer <token>`; PAT → `X-Figma-Token: <key>`. `src/services/figma.ts:40-41`, `:51`.
- At least one is required: `"Either FIGMA_API_KEY or FIGMA_OAUTH_TOKEN is required (via CLI argument or .env file)"` (`src/config.ts:135`).
- **Per-request auth over HTTP** is supported: `"Figma API authentication is required. Configure FIGMA_API_KEY or FIGMA_OAUTH_TOKEN on the server, or send X-Figma-Token / Authorization: Bearer on the HTTP request."` (`src/services/figma.ts:46`).
- Tokens are masked in startup logs (`maskApiKey`, `src/config.ts:204`, `:209`).
- **Required Figma scopes:** `File content: Read` and `Dev resources: Read` — stated in the 403 diagnostic text: `"- The access token is missing required scopes (File content: Read, Dev resources: Read)"` (`src/services/errors/forbidden.ts:6`). No README scope table exists.
- Other project-level config (not tool params): `PORT`/`--port` (default 3333), `OUTPUT_FORMAT`/`--format`, `--skip-image-downloads`, `--proxy`/`FIGMA_PROXY` (`src/config.ts`, `src/utils/proxy-env.ts`).

## Pagination
Figma files are trees, so there is no page/cursor concept. The only size controls are:
- **`depth`** (tool param) → passed straight through as the Figma API `?depth=N` query param (`src/services/figma.ts:313`, `:333`) and also used as `maxDepth` in the local walk (`src/services/get-figma-data.ts:111`). The description actively **discourages** the model from using it: "OPTIONAL. Do NOT use unless explicitly requested by the user." (`src/mcp/tools/get-figma-data-tool.ts:35`).
- **`nodeId`** — scoping to a subtree is the real "pagination" mechanism.
- **No result cap, no byte cap, no truncation.** There is no `maxNodes`, no size guard, and no error when a file is huge — a whole-file call returns everything the extractors kept. The mitigation is entirely the simplification/dedup layer plus the `tree` format. Metrics record `rawSizeKb` vs `simplifiedSizeKb`, `rawNodeCount` vs `simplifiedNodeCount`, `maxDepth` (`src/services/get-figma-data.ts:140-156`) but these are telemetry only and are **not** returned to the model.

## Rate limits
No client-side rate limiting, no retry loop, and no backoff. `fetchJSON` classifies but does not act: `RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}` and tags `is_retryable` for telemetry only (`src/utils/fetch-json.ts:53`, `:78-82`). A 429 is converted into a rich human-readable message and thrown (see below) — retrying is left to the calling agent.

## Error shapes
Errors reach the model as an MCP tool result with `isError: true` and a single text block — never a protocol-level exception.
- `get_figma_data`: `` `Error fetching file: ${message}` `` (`src/mcp/tools/get-figma-data-tool.ts:98-105`).
- `download_figma_images`: `` `Failed to download images: ${message}` `` (`:191-203`), plus a pre-flight path-traversal rejection with bespoke guidance (`:116-130`, messages built at `:206-244`, e.g. `Invalid path: "{p}" resolves outside the allowed image directory. The server's image directory is "{baseDir}". Provide a path relative to this directory…`).
- Base HTTP failure message: `` `Fetch failed with status ${response.status}: ${response.statusText}` `` plus, when a body was read, `` `\nResponse body: ${body}` `` capped at **500 chars** (`src/utils/fetch-json.ts:57`, `:74-76`). Response bodies are scrubbed of credentials before attaching (`:12`).
- **429** → `buildRateLimitMessage` (`src/services/figma.ts:89-90`; `src/services/errors/rate-limit.ts:11-37`): starts `"Figma API rate limit hit (429)."`, then appends, from the response headers, `Retry after {retry-after} seconds.` (`retry-after`), a seat-type note when `x-figma-rate-limit-type === "low"`, a plan note for `x-figma-plan-tier` ∈ {starter, student}, an `Upgrade: {x-figma-upgrade-link}`, and always a docs link.
- **403** → `buildForbiddenMessage` (`src/services/figma.ts:92-93`; `src/services/errors/forbidden.ts:39-58`): echoes the endpoint and the verbatim Figma response body, then a fixed 5-item cause list (missing scopes / revoked-or-expired token / no permission on this file / share settings block export / an HTTP intermediary rejected it), a troubleshooting URL, a proxy hint if a proxy is configured, and an explicit **instruction addressed to the LLM**: `"Instructions: explain the specific reason from the response body above to the user in plain language and walk them through resolving it."` (`forbidden.ts:19-20`). The doc comment explains the design: surface the body verbatim rather than string-match, "fragile as Figma's wording drifts" (`forbidden.ts:29-38`).
- **Network errors** (`ECONNREFUSED`, `ETIMEDOUT`, `ENOTFOUND`, `UND_ERR_CONNECT_TIMEOUT`) are wrapped with proxy guidance: `"Could not connect to the Figma API. If your network requires a proxy, set the --proxy flag…"` (`src/utils/fetch-json.ts:92-99`, codes at `:41-49`).
- Errors are also **tagged with a phase** (`fetch` / `simplify` / `serialize`) for telemetry via `tagError` (`src/services/get-figma-data.ts:98`, `:116`, `:135`).
- Zod validation rejections are intercepted and counted separately (`src/mcp/validation-capture.ts`, wired at `src/mcp/index.ts:54-59`).

## Not exposed (E3) — Figma REST API surface deliberately omitted
The server is **read-only against Figma**; the only write it performs is to the local filesystem (image downloads). `FIGMA_API_KEY` is used purely for GETs — the whole client only implements `getRawFile`, `getRawNode`, `downloadImages` (`CLAUDE.md` Architecture; `src/services/figma.ts:309`, `:328`).

Absent from the tool surface, with no code path in `src/`:
- **Comments** — no `GET/POST /v1/files/:key/comments`, no comment reactions. An agent cannot read or leave design feedback.
- **Versions / version history** — no `/v1/files/:key/versions`.
- **Webhooks** — no `/v2/webhooks` (create/list/delete).
- **Variables** — no `/v1/files/:key/variables/local` or `/published`. `detectVariables(rawApiResponse)` only records a boolean *for telemetry* (`src/services/get-figma-data.ts:125`); ROADMAP.md:70 has an open item to "Port `deduceVariablesFromTokens` for non-Enterprise users", confirming variables are not properly supported.
- **Team/project/library APIs** — no `/v1/teams/:id/projects`, `/v1/projects/:id/files`, no published-components/styles library endpoints, no component-usage analytics.
- **Dedicated component extraction** — explicitly a *planned* tool, not a current one: ROADMAP.md:15-16 "Create `get_figma_components` tool for fetching full component/component set design data including variants and properties". Also open: INSTANCE override-only returns, and hiding INSTANCE children (ROADMAP.md:17-20).
- **Prototype / interaction data** — open roadmap item, not implemented: "Extract interactivity data (e.g. actions on hover, click, etc.)", "Return data on animations / transitions" (ROADMAP.md:21-24).
- **Dev resources write**, **activity logs**, **payments**, **users/me** — none.
- **Any mutation of a Figma file** — the server cannot create, rename, or modify anything in Figma. Per `CONTRIBUTING.md` philosophy quoted in `CLAUDE.md`, code generation and third-party integration are explicitly out of scope.

## Notes for mocking
1. **Two tools only** (one if image downloads are disabled). Resist adding plausible-sounding Figma tools — the real server's minimalism is a deliberate, documented design stance.
2. `get_figma_data` returns **a single text blob in a server-configured format**, not structured JSON. Default is the bespoke `tree` format: `NAME:` / `GLOBAL_VARS:` / `ELEMENTS:` / `COMPONENTS:` / `COMPONENT_SETS:` sections and node lines `[TYPE] "name" #id key=value`.
3. Reproduce the **globalVars indirection**: style fields are `string` refs *or* inline objects depending on reuse count (≥2 → hoisted). This union is the single most likely thing to trip an agent.
4. Reproduce **element templates**: repeated subtrees collapse to `{ id, name, template: "EL-xxxxxxxx", children? }` and the body lives in `elements`. Agents must dereference.
5. Node **names are frequently missing** — auto-generated and TEXT names are stripped. An agent cannot rely on `name` to locate a layer; it must use `id`.
6. `nodeId` accepts the deep-instance form `I5666:180910;1:10515;1:10336` and the tool rewrites `-` to `:` before calling Figma (`get-figma-data-tool.ts:56`) — because Figma URLs use `1234-5678` but the API wants `1234:5678`. A faithful mock should accept both.
7. `download_figma_images` writes to disk and returns a **markdown bullet list** with `WxH`, optional CSS variables, and `(cropped)` markers — not JSON. `pngScale` defaults to 2.
8. `localPath` is sandboxed to the server's image directory; absolute paths outside it are rejected with a specific, LLM-directed remediation message. Path-traversal rejection is a realistic recurring agent failure worth modelling.
9. Error text is **verbose and instructional** — the 403 message literally tells the model what to do next. Terse `{"error":"forbidden"}` mocks would be unrealistic.
10. There is **no pagination and no truncation**; the size lever is `nodeId` scoping (and, reluctantly, `depth`). A whole-file call on a large design is a legitimate context-blowup scenario.
11. Long calls emit progress notifications with live node counts — relevant if modelling timeouts or streaming.
