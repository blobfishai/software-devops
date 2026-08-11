# sooperset/mcp-atlassian — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/sooperset__mcp-atlassian` @ git commit `12fb6fa` (`git -C /Users/samuelchien/dev/software-devops/research/repos/mcp/sooperset__mcp-atlassian rev-parse --short HEAD`), read 2026-08-11

**Language / framework:** Python ≥ 3.10, FastMCP (`from fastmcp import FastMCP` — `src/mcp_atlassian/servers/main.py:12`), Pydantic v2 models (`ApiModel` base, `src/mcp_atlassian/models/base.py`), `atlassian-python-api` + `requests` under the hood. Server subclasses `ErrorPreservingFastMCP` (`src/mcp_atlassian/servers/error_handling.py:23`).

**Registration entrypoint:** `src/mcp_atlassian/servers/main.py:886` (`main_mcp = AtlassianMCP(...)`), which mounts two sub-servers:
- `src/mcp_atlassian/servers/main.py:891` — `main_mcp.mount(jira_mcp, namespace="jira")`
- `src/mcp_atlassian/servers/main.py:892` — `main_mcp.mount(confluence_mcp, namespace="confluence")`

The sub-servers themselves are created at `src/mcp_atlassian/servers/jira.py:50` (`jira_mcp = ErrorPreservingFastMCP(name="Jira MCP Service", ...)`) and `src/mcp_atlassian/servers/confluence.py:182` (`confluence_mcp = ErrorPreservingFastMCP(name="Confluence MCP Service", ...)`).

**Served tool names.** The Python function name is NOT the served name. FastMCP's `mount(..., namespace="jira")` prefixes every mounted tool with `jira_` / `confluence_`. Independently confirmed by the repo's own doc generator, which reconstructs the identical names: `prefixed = f"jira_{tool.name}"` at `scripts/generate_tool_docs.py:370` and `prefixed = f"confluence_{tool.name}"` at `scripts/generate_tool_docs.py:380`. So `async def get_issue` (`src/mcp_atlassian/servers/jira.py:571`) is served as `jira_get_issue`, and `async def search` (`src/mcp_atlassian/servers/confluence.py:192`) is served as `confluence_search`. Only one tool sets an explicit `name=` override, and it matches its function name anyway: `name="batch_create_versions"` at `src/mcp_atlassian/servers/jira.py:3886`.

**Tool gating.** Three independent filters, enforced at BOTH `tools/list` and `tools/call` time:

1. **Read-only mode** — `READ_ONLY_MODE` env var, parsed by `is_read_only_mode()` at `src/mcp_atlassian/utils/io.py:9-20`; also settable via the `--read-only` CLI flag (`src/mcp_atlassian/__init__.py:198-200`, which writes `os.environ["READ_ONLY_MODE"]` at `src/mcp_atlassian/__init__.py:406-407`). Enforcement: `if ctx["read_only"] and "write" in tool_tags: return False` — `src/mcp_atlassian/servers/main.py:293-294`. A second, defence-in-depth check lives in the `@check_write_access` decorator applied to every write tool (`src/mcp_atlassian/utils/decorators.py:115-146`), raising `ValueError(f"Cannot {action_description} in read-only mode.")` at `src/mcp_atlassian/utils/decorators.py:141-142`.
2. **`ENABLED_TOOLS` allowlist** — parsed by `get_enabled_tools()` at `src/mcp_atlassian/utils/tools.py:9-41` (comma-separated, whitespace-stripped, empty → `None` = all enabled). Matching is exact against the *served* (prefixed) name: `should_include_tool()` at `src/mcp_atlassian/utils/tools.py:44-63` does `tool_name in enabled_tools`; the caller passes `registered_name = tool_obj.name` (`src/mcp_atlassian/servers/main.py:348`). CLI flag `--enabled-tools` at `src/mcp_atlassian/__init__.py:203`.
3. **Tool tags / toolsets** — every tool carries a tag set such as `{"jira", "read", "toolset:jira_issues"}` (e.g. `src/mcp_atlassian/servers/jira.py:568`). The `TOOLSETS` env var selects toolsets: `get_enabled_toolsets()` at `src/mcp_atlassian/utils/toolsets.py:172-240`, filter at `should_include_tool_by_toolset()` `src/mcp_atlassian/utils/toolsets.py:243-266`. 25 toolsets are defined — 16 Jira (`src/mcp_atlassian/utils/toolsets.py:27-108`), 8 Confluence (`src/mcp_atlassian/utils/toolsets.py:112-153`), plus `legacy` (`src/mcp_atlassian/utils/toolsets.py:160-164`). `TOOLSETS` supports `all`, `default` (6 toolsets flagged `default=True`), or explicit names; unset currently means *all* with a deprecation warning that v0.22.0 will change the default to the 6 core toolsets (`src/mcp_atlassian/utils/toolsets.py:196-203`). Unknown-only input → empty set → **fail-closed, all tools blocked** (`src/mcp_atlassian/utils/toolsets.py:236-238`). CLI flag `--toolsets` at `src/mcp_atlassian/__init__.py:207`.

Authorization boundary vs. listing filter is deliberately split: `_is_tool_authorized()` (`src/mcp_atlassian/servers/main.py:276-295`) applies the three filters above and is enforced at call time in `_call_tool_mcp()` (`src/mcp_atlassian/servers/main.py:361-373`), raising `NotFoundError(f"Unknown tool: {key}")` (`src/mcp_atlassian/servers/main.py:372`) so a disabled tool is indistinguishable from a nonexistent one. `_is_tool_enabled()` (`src/mcp_atlassian/servers/main.py:297-329`) adds a listing-only hide when the backing service (Jira / Confluence) has no configuration.

A fourth, non-security transform: `_sanitize_schema_for_compatibility()` (`src/mcp_atlassian/servers/main.py:64-131`) collapses Pydantic `T | None` `anyOf` unions into a plain `{"type": T}` in the emitted `inputSchema`, for Vertex AI / Google ADK compatibility.

---

## Full tool list (98 tools)

63 Jira + 35 Confluence. Counts verified by AST parse of the two server modules; the repo's own generated reference also states "**98 tools**" (`docs/tools-reference.mdx:6`) and `src/mcp_atlassian/utils/toolsets.py:3` says "Groups 98 tools into 25 named toolsets". R = has the `read` tag, W = has the `write` tag (and therefore blocked in read-only mode). Line numbers point at the `@…_mcp.tool(` decorator.

### Jira (63 tools)

- `jira_get_user_profile` — R — Retrieve profile information for a specific Jira user. — `src/mcp_atlassian/servers/jira.py:259`
- `jira_search_assignable_users` — R — Search Jira users assignable in a given project or issue. — `src/mcp_atlassian/servers/jira.py:320`
- `jira_get_issue_watchers` — R — Get the list of watchers for a Jira issue. — `src/mcp_atlassian/servers/jira.py:440`
- `jira_add_watcher` — W — Add a user as a watcher to a Jira issue. — `src/mcp_atlassian/servers/jira.py:471`
- `jira_remove_watcher` — W — Remove a user from watching a Jira issue. — `src/mcp_atlassian/servers/jira.py:516`
- `jira_get_issue` — R — Get details of a specific Jira issue. — `src/mcp_atlassian/servers/jira.py:567`
- `jira_search` — R — Search Jira issues using JQL (Jira Query Language). — `src/mcp_atlassian/servers/jira.py:747`
- `jira_search_fields` — R — Search Jira fields by keyword with fuzzy match. — `src/mcp_atlassian/servers/jira.py:869`
- `jira_get_field_options` — R — Get allowed option values for a custom field. — `src/mcp_atlassian/servers/jira.py:984`
- `jira_get_project_issues` — R — Get all issues for a specific Jira project. — `src/mcp_atlassian/servers/jira.py:1087`
- `jira_get_transitions` — R — Get available status transitions for a Jira issue. — `src/mcp_atlassian/servers/jira.py:1128`
- `jira_get_worklog` — R — Get worklog entries for a Jira issue. — `src/mcp_atlassian/servers/jira.py:1157`
- `jira_download_attachments` — R — Download attachments from a Jira issue. — `src/mcp_atlassian/servers/jira.py:1186`
- `jira_get_issue_images` — R — Get all images attached to a Jira issue as inline image content. — `src/mcp_atlassian/servers/jira.py:1320`
- `jira_get_agile_boards` — R — Get jira agile boards by name, project key, or type. — `src/mcp_atlassian/servers/jira.py:1452`
- `jira_get_board_issues` — R — Get all issues linked to a specific board filtered by JQL. — `src/mcp_atlassian/servers/jira.py:1509`
- `jira_get_sprints_from_board` — R — Get jira sprints from board by state. — `src/mcp_atlassian/servers/jira.py:1589`
- `jira_get_sprint_issues` — R — Get jira issues from sprint. — `src/mcp_atlassian/servers/jira.py:1629`
- `jira_get_link_types` — R — Get all available issue link types. — `src/mcp_atlassian/servers/jira.py:1680`
- `jira_create_issue` — W — Create a new Jira issue with optional Epic link or parent for subtasks. — `src/mcp_atlassian/servers/jira.py:1715`
- `jira_batch_create_issues` — W — Create multiple Jira issues in a batch. — `src/mcp_atlassian/servers/jira.py:1829`
- `jira_batch_get_changelogs` — R — Get changelogs for multiple Jira issues (Cloud only). — `src/mcp_atlassian/servers/jira.py:1901`
- `jira_update_issue` — W — Update an issue and optionally transition, comment, and log work. — `src/mcp_atlassian/servers/jira.py:1982`
- `jira_assign_issue` — W — Assign a Jira issue to a user using the dedicated assignment endpoint. — `src/mcp_atlassian/servers/jira.py:2272`
- `jira_delete_issue` — W — Delete an existing Jira issue. — `src/mcp_atlassian/servers/jira.py:2344`
- `jira_move_issue` — W — Move a Jira issue to a different project (Jira Cloud only). — `src/mcp_atlassian/servers/jira.py:2378`
- `jira_add_comment` — W — Add a comment to a Jira issue. — `src/mcp_atlassian/servers/jira.py:2450`
- `jira_edit_comment` — W — Edit an existing comment on a Jira issue. — `src/mcp_atlassian/servers/jira.py:2536`
- `jira_add_worklog` — W — Add a worklog entry to a Jira issue. — `src/mcp_atlassian/servers/jira.py:2583`
- `jira_link_to_epic` — W — Link an existing issue to an epic. — `src/mcp_atlassian/servers/jira.py:2659`
- `jira_create_issue_link` — W — Create a link between two Jira issues. — `src/mcp_atlassian/servers/jira.py:2703`
- `jira_create_remote_issue_link` — W — Create a remote issue link (web link or Confluence link) for a Jira issue. — `src/mcp_atlassian/servers/jira.py:2799`
- `jira_remove_issue_link` — W — Remove a link between two Jira issues. — `src/mcp_atlassian/servers/jira.py:2887`
- `jira_transition_issue` — W — Transition a Jira issue to a new status. — `src/mcp_atlassian/servers/jira.py:2916`
- `jira_create_sprint` — W — Create Jira sprint for a board. — `src/mcp_atlassian/servers/jira.py:3002`
- `jira_update_sprint` — W — Update jira sprint. — `src/mcp_atlassian/servers/jira.py:3048`
- `jira_add_issues_to_sprint` — W — Add issues to a Jira sprint. — `src/mcp_atlassian/servers/jira.py:3109`
- `jira_move_issues_to_backlog` — W — Move issues to the backlog, removing them from any sprint. — `src/mcp_atlassian/servers/jira.py:3146`
- `jira_get_project_issue_types` — R — Get available issue types for a Jira project. — `src/mcp_atlassian/servers/jira.py:3180`
- `jira_get_create_fields` — R — Get fields available for creating an issue of a specific type. — `src/mcp_atlassian/servers/jira.py:3224`
- `jira_get_project_versions` — R — Get all fix versions for a specific Jira project. — `src/mcp_atlassian/servers/jira.py:3277`
- `jira_get_project_components` — R — Get all components for a specific Jira project. — `src/mcp_atlassian/servers/jira.py:3297`
- `jira_get_all_projects` — R — Get all Jira projects accessible to the current user. — `src/mcp_atlassian/servers/jira.py:3317`
- `jira_search_projects` — R — Search for Jira projects by name or key prefix. — `src/mcp_atlassian/servers/jira.py:3385`
- `jira_get_project_fields` — R — Get the fields available on issues of a project (the create schema). — `src/mcp_atlassian/servers/jira.py:3470`
- `jira_get_service_desk_for_project` — R — Get the Jira Service Desk associated with a project key. — `src/mcp_atlassian/servers/jira.py:3519`
- `jira_get_service_desk_queues` — R — Get queues for a Jira Service Desk. — `src/mcp_atlassian/servers/jira.py:3560`
- `jira_get_queue_issues` — R — Get issues from a Jira Service Desk queue. — `src/mcp_atlassian/servers/jira.py:3606`
- `jira_get_request_types` — R — Get request types for a Jira Service Management service desk. — `src/mcp_atlassian/servers/jira.py:3657`
- `jira_get_request_type_fields` — R — Get field definitions for a Jira Service Management request type. — `src/mcp_atlassian/servers/jira.py:3696`
- `jira_create_customer_request` — W — Create a Jira Service Management customer request. — `src/mcp_atlassian/servers/jira.py:3729`
- `jira_create_version` — W — Create a new fix version in a Jira project. — `src/mcp_atlassian/servers/jira.py:3828`
- `jira_batch_create_versions` — W — Batch create multiple versions in a Jira project. — `src/mcp_atlassian/servers/jira.py:3885`
- `jira_update_version` — W — Update an existing fix version in a Jira project. — `src/mcp_atlassian/servers/jira.py:3969`
- `jira_get_issue_proforma_forms` — R — Get all ProForma forms associated with a Jira issue. — `src/mcp_atlassian/servers/jira.py:4042`
- `jira_get_proforma_form_details` — R — Get detailed information about a specific ProForma form. — `src/mcp_atlassian/servers/jira.py:4097`
- `jira_update_proforma_form_answers` — W — Update form field answers using the Jira Forms REST API. — `src/mcp_atlassian/servers/jira.py:4167`
- `jira_get_issue_dates` — R — Get date information and status transition history for a Jira issue. — `src/mcp_atlassian/servers/jira.py:4297`
- `jira_get_issue_sla` — R — Calculate SLA metrics for a Jira issue. — `src/mcp_atlassian/servers/jira.py:4354`
- `jira_get_issue_development_info` — R — Get development information (PRs, commits, branches) linked to a Jira issue. — `src/mcp_atlassian/servers/jira.py:4435`
- `jira_get_issues_development_info` — R — Get development information for multiple Jira issues. — `src/mcp_atlassian/servers/jira.py:4497`
- `jira_get_project_epic_hierarchy` — R — Group a project's epics under their cross-project parent issues. — `src/mcp_atlassian/servers/jira.py:4561`
- `jira_get_cross_project_dependencies` — R — Find all cross-project issue links for a project. — `src/mcp_atlassian/servers/jira.py:4610`

### Confluence (35 tools)

- `confluence_search` — R — Search Confluence content using simple terms or CQL. — `src/mcp_atlassian/servers/confluence.py:188`
- `confluence_get_page` — R — Get content of a specific Confluence page by its ID, or by its title and space key. — `src/mcp_atlassian/servers/confluence.py:280`
- `confluence_get_page_children` — R — Get child pages and folders of a specific Confluence page. — `src/mcp_atlassian/servers/confluence.py:409`
- `confluence_get_space_page_tree` — R — Get page hierarchy for a Confluence space as a flat list. — `src/mcp_atlassian/servers/confluence.py:509`
- `confluence_get_comments` — R — Get comments for a specific Confluence page. — `src/mcp_atlassian/servers/confluence.py:561`
- `confluence_get_labels` — R — Get labels for Confluence content (pages, blog posts, or attachments). — `src/mcp_atlassian/servers/confluence.py:593`
- `confluence_add_label` — W — Add label to Confluence content (pages, blog posts, or attachments). — `src/mcp_atlassian/servers/confluence.py:626`
- `confluence_create_page` — W — Create a new Confluence page. — `src/mcp_atlassian/servers/confluence.py:679`
- `confluence_update_page` — W — Update an existing Confluence page. — `src/mcp_atlassian/servers/confluence.py:866`
- `confluence_update_page_section` — W — Update a single section of a Confluence page without affecting the rest. — `src/mcp_atlassian/servers/confluence.py:1044`
- `confluence_delete_page` — W — Delete an existing Confluence page. — `src/mcp_atlassian/servers/confluence.py:1146`
- `confluence_move_page` — W — Move a Confluence page to a new parent or space. — `src/mcp_atlassian/servers/confluence.py:1191`
- `confluence_add_comment` — W — Add a comment to a Confluence page. — `src/mcp_atlassian/servers/confluence.py:1270`
- `confluence_reply_to_comment` — W — Reply to an existing comment thread on a Confluence page. — `src/mcp_atlassian/servers/confluence.py:1321`
- `confluence_get_inline_comments` — R — Get all inline comments for a Confluence page. — `src/mcp_atlassian/servers/confluence.py:1374`
- `confluence_add_inline_comment` — W — Add an inline comment anchored to a text selection on a page. — `src/mcp_atlassian/servers/confluence.py:1418`
- `confluence_search_user` — R — Search Confluence users using CQL (Cloud) or group member API (Server/DC). — `src/mcp_atlassian/servers/confluence.py:1513`
- `confluence_get_page_history` — R — Get a historical version of a specific Confluence page. — `src/mcp_atlassian/servers/confluence.py:1600`
- `confluence_get_page_diff` — R — Get a unified diff between two versions of a Confluence page. — `src/mcp_atlassian/servers/confluence.py:1680`
- `confluence_get_page_views` — R — Get view statistics for a Confluence page. — `src/mcp_atlassian/servers/confluence.py:1757`
- `confluence_upload_attachment` — W — Upload an attachment to Confluence content (page or blog post). — `src/mcp_atlassian/servers/confluence.py:1827`
- `confluence_upload_attachments` — W — Upload multiple attachments to Confluence content in a single operation. — `src/mcp_atlassian/servers/confluence.py:1969`
- `confluence_get_attachments` — R — List all attachments for a Confluence content item (page or blog post). — `src/mcp_atlassian/servers/confluence.py:2058`
- `confluence_download_attachment` — R — Download an attachment from Confluence as an embedded resource. — `src/mcp_atlassian/servers/confluence.py:2163`
- `confluence_download_content_attachments` — R — Download all attachments for a Confluence content item as embedded resources. — `src/mcp_atlassian/servers/confluence.py:2315`
- `confluence_delete_attachment` — W — Permanently delete an attachment from Confluence. — `src/mcp_atlassian/servers/confluence.py:2468`
- `confluence_get_page_images` — R — Get all images attached to a Confluence page as inline image content. — `src/mcp_atlassian/servers/confluence.py:2522`
- `confluence_list_page_templates` — R — List Confluence page content templates. — `src/mcp_atlassian/servers/confluence.py:2686`
- `confluence_get_page_template` — R — Get a Cloud page template by ID, including its storage-format body. — `src/mcp_atlassian/servers/confluence.py:2747`
- `confluence_create_page_from_template` — W — Create a new Cloud page pre-populated with a template's body. — `src/mcp_atlassian/servers/confluence.py:2782`
- `confluence_get_page_restrictions` — R — Get view and edit restrictions for a Confluence page. — `src/mcp_atlassian/servers/confluence.py:2834`
- `confluence_set_page_restrictions` — W — Set view and edit restrictions on a Confluence page. — `src/mcp_atlassian/servers/confluence.py:2863`
- `confluence_copy_page` — W — Copy a Confluence page to a new location. — `src/mcp_atlassian/servers/confluence.py:2944`
- `confluence_check_content_permissions` — R — Check whether a user or group can perform an operation on specific content. — `src/mcp_atlassian/servers/confluence.py:3014`
- `confluence_get_space_permissions` — R — List all permission assignments for a Confluence space. — `src/mcp_atlassian/servers/confluence.py:3078`

---

## Key tools

Every tool in this server returns a **`str`** — a `json.dumps(..., indent=2, ensure_ascii=False)` of the dict described below. There is no structured MCP output schema; the model receives pretty-printed JSON text. (Exceptions: the image/attachment tools return `list[ImageContent]` / `list[EmbeddedResource]`.)

| Tool | Params (`name`: type — required/default) | Returns (concrete shape) | Source |
|---|---|---|---|
| `jira_search` | `jql`: str — **required** (Field description lists JQL examples: `"issuetype = Epic AND project = PROJ"`, `"parent = PROJ-123"`, `"assignee = currentUser()"`, `"updated >= -7d AND project = PROJ"`); `fields`: str — default `",".join(DEFAULT_READ_JIRA_FIELDS)`, `'*all'` for everything; `limit`: int — default `10`, `ge=1` (description says "Maximum number of results (1-50)" but **no `le=` is set**, so 1–50 is advisory only); `start_at`: int — default `0`, `ge=0`; `projects_filter`: str\|None — default `None` (overrides `JIRA_PROJECTS_FILTER`); `expand`: str\|None — default `None`; `page_token`: str\|None — default `None` (Cloud only; Server/DC uses `start_at`); `use_display_names`: bool — default `False` (adds `names` expansion, custom-field keys become e.g. `"Story Points"` instead of `customfield_10243`) | `JiraSearchResult.to_simplified_dict()` (`src/mcp_atlassian/models/jira/search.py:114-124`): `{"total": int, "start_at": int, "max_results": int, "issues": [<JiraIssue simplified>, ...]}`, plus `"next_page_token": str` only when non-`None`. With `use_display_names=True` it calls `to_display_name_dict()` instead (`src/mcp_atlassian/models/jira/search.py:126-136`), same keys, display-name issue keys. | `src/mcp_atlassian/servers/jira.py:747` (params 751-826, return path 852-866) |
| `jira_get_issue` | `issue_key`: str — **required**, `pattern=ISSUE_KEY_PATTERN` (default regex `^[A-Z][A-Z0-9_]+-\d+(?:-\d+)*$`, `src/mcp_atlassian/servers/jira.py:45-47`); `fields`: str — default `",".join(DEFAULT_READ_JIRA_FIELDS)`; `expand`: str\|None — default `None`; `comment_limit`: int — default `10`, `ge=0`, **`le=100`**; `properties`: str\|None — default `None`; `update_history`: bool — default `True`; `include`: str\|None — default `None`, comma-separated from `{all, remote_links, transitions, watchers, changelog, comments, worklogs}` (`src/mcp_atlassian/servers/jira.py:55-64`); `use_display_names`: bool — default `False` | `JiraIssue.to_simplified_dict()` (`src/mcp_atlassian/models/jira/issue.py:522-…`). Always `{"id", "key"}`; then conditionally, gated by `should_include_field()` against `requested_fields`: `summary`, `url`, `browse_url` (always if set), `description`, `environment`, `status` (nested simplified dict), `issue_type`, `priority`, `project`, `resolution`, `duedate`, `resolutiondate`, `parent`, `subtasks`, `security`, `worklog`, `assignee` (**always emitted when requested — falls back to `{"display_name": "Unassigned"}`**, lines 598-602), `reporter`, `labels`, `components`, `fix_versions`, `versions`, `epic_key`, `epic_name`, `timetracking`, `created`/`updated` (via `format_timestamp`), `comments` (list of simplified comments), `attachments`, `changelogs` (emitted whenever present, **not** gated by requested fields — lines 652-657), `issuelinks`, and custom fields as `{internal_id: {"value": ..., "name": ...}}` (lines 665-691). The tool then merges enrichments in-place: `remote_links`, `transitions`, `watchers`, `worklogs` keys, each wrapped in try/except that falls back to `[]` / `{}` (`src/mcp_atlassian/servers/jira.py:720-742`). | `src/mcp_atlassian/servers/jira.py:567` (params 571-649, return path 704-744) |
| `jira_create_issue` | `project_key`: str — **required**, `pattern=PROJECT_KEY_PATTERN` (default `^[A-Z][A-Z0-9_]+$`, `src/mcp_atlassian/servers/jira.py:48`); `summary`: str — **required**; `issue_type`: str — **required** (e.g. `'Task'`, `'Bug'`, `'Story'`, `'Epic'`, `'Subtask'` — note "use 'Subtask' (not 'Sub-task')"); `assignee`: str\|None — default `None` (email, display name, or `accountid:...`); `description`: str\|None — default `None`, **Markdown**; `components`: str\|None — default `None`, comma-separated names; `additional_fields`: str\|None — default `None`, a **JSON string** (examples in the Field description: `{"priority": {"name": "High"}}`, `{"labels": [...]}`, `{"parent": "PROJ-123"}`, `{"epicKey": "EPIC-123"}` / `{"epic_link": ...}`, `{"fixVersions": [{"id": "10020"}]}`, `{"customfield_10010": "value"}`) | `{"message": "Issue created successfully", "issue": <JiraIssue.to_simplified_dict()>}` — literal at `src/mcp_atlassian/servers/jira.py:1823`. Issue shape per `src/mcp_atlassian/models/jira/issue.py:522`. | `src/mcp_atlassian/servers/jira.py:1715` (`@check_write_access` at 1719, params 1720-1782, return 1821-1826) |
| `jira_update_issue` | `issue_key`: str — **required**, `pattern=ISSUE_KEY_PATTERN`; `fields`: str\|None — default `None`, JSON string; `additional_fields`: str\|None — default `None`, JSON string; `components`: str\|None — default `None`; `attachments`: str\|None — default `None` (JSON array string **or** comma-separated file paths); `transition`: str\|None — default `None` (transition name or ID, names resolved case-insensitively); `comment`: str\|None — default `None`, Markdown; `comment_visibility`: str\|None — default `None`, JSON e.g. `'{"type":"group","value":"jira-users"}'`; `worklog`: str\|None — default `None`, e.g. `'1h 30m'`; `worklog_started`: str\|None — default `None`, ISO datetime; `return_fields`: str — **default `"*all"`** (comma-separated subset to shrink the response; "The issue 'key' is always returned regardless") | JSON string of the updated issue object plus attachment results; the issue portion is `JiraIssue.to_simplified_dict()` filtered by `return_fields`. Docstring: "JSON string representing the updated issue object and attachment results" (`src/mcp_atlassian/servers/jira.py:2118`). | `src/mcp_atlassian/servers/jira.py:1982` (`@check_write_access` at 1986, params 1987-2098) |
| `jira_transition_issue` | `issue_key`: str — **required**, `pattern=ISSUE_KEY_PATTERN`; `transition_id`: str — **required** ("Use the jira_get_transitions tool first"; example values `'11'`, `'21'`, `'31'`); `fields`: str\|None — default `None`, JSON string e.g. `'{"resolution": {"name": "Fixed"}}'`; `comment`: str\|None — default `None`, Markdown — **rejected for projects in `JIRA_INTERNAL_ONLY_PROJECTS`** | `{"message": f"Issue {issue_key} transitioned successfully", "issue": <JiraIssue.to_simplified_dict()> or None}` — literal at `src/mcp_atlassian/servers/jira.py:2995-2998`. | `src/mcp_atlassian/servers/jira.py:2916` (`@check_write_access` at 2920, params 2921-2962, return 2995-2999) |
| `jira_get_transitions` | `issue_key`: str — **required**, `pattern=ISSUE_KEY_PATTERN`. That is the **only** parameter. | A JSON **list** (not an object) produced directly by `jira.get_available_transitions(issue_key)` — "Underlying method returns list[dict] in the desired format" (`src/mcp_atlassian/servers/jira.py:1152-1154`). The corresponding model shape is `JiraTransition.to_simplified_dict()` (`src/mcp_atlassian/models/jira/workflow.py:83-93`): `{"id": str, "name": str}` plus `"to_status": {...}` when a target status is present. Note `id` is coerced to `str` (`src/mcp_atlassian/models/jira/workflow.py:63-65`). | `src/mcp_atlassian/servers/jira.py:1128` (params 1132-1140, return 1151-1154) |
| `jira_add_comment` | `issue_key`: str — **required**, `pattern=ISSUE_KEY_PATTERN`; `body`: str — **required**, Markdown, with `validation_alias=AliasChoices("body", "comment")` so clients may send either key (`src/mcp_atlassian/servers/jira.py:2468`); `visibility`: str\|None — default `None`, JSON e.g. `'{"type":"group","value":"jira-users"}'`; `public`: bool\|None — default `None`, JSM/Service Desk only — `true` = customer-visible, `false` = internal agent-only; cannot be combined with `visibility`; if the project is in `JIRA_INTERNAL_ONLY_PROJECTS` only `public=false` is accepted | JSON of `jira.add_comment(...)` result. Model shape `JiraComment.to_simplified_dict()` (`src/mcp_atlassian/models/jira/comment.py:81-97`): `{"id": str, "body": str}` plus optional `"author"` (nested `JiraUser` simplified dict), `"created"`, `"updated"`. | `src/mcp_atlassian/servers/jira.py:2450` (`@check_write_access` at 2454, params 2455-2499, return 2532-2533) |
| `jira_get_all_projects` | (see source — read-only project listing) | JSON list of `JiraProject.to_simplified_dict()` (`src/mcp_atlassian/models/jira/project.py:92`). | `src/mcp_atlassian/servers/jira.py:3317` |
| `confluence_search` | `query`: str — **required**. Dual-mode: if the string contains **none** of `=`, `~`, `>`, `<`, `" AND "`, `" OR "`, `"currentUser()"` it is treated as plain text and wrapped as `siteSearch ~ "<query>"`; on exception it falls back to `text ~ "<query>"` (`src/mcp_atlassian/servers/confluence.py:253-271`). Otherwise it is passed through as raw CQL. `limit`: int — default `10`, `ge=1`, **`le=50`**; `spaces_filter`: str\|None — default `None` (overrides `CONFLUENCE_SPACES_FILTER`; empty string disables filtering) | A JSON **array** of `ConfluencePage.to_simplified_dict()` (`src/mcp_atlassian/servers/confluence.py:276-277`). Each element (`src/mcp_atlassian/models/confluence/page.py:263-…`): always `{"id", "title", "type", "created", "updated", "url"}` (created/updated via `format_timestamp`), plus optional `"subtype"`, `"space": {"key", "name"}`, `"author": <display_name string>`, `"version": <int>`, `"version_author": <display_name>`, `"version_date": <raw ISO 8601 with offset>`, always `"attachments": [...]`, `"content": {"value": str, "format": str}` when content is non-empty, `"ancestors": [{"id", "title"}, ...]`, `"emoji"`. | `src/mcp_atlassian/servers/confluence.py:188` (params 192-238, return 276-277) |
| `confluence_get_page` | `page_id`: str\|None — default `None`; accepts a numeric ID, a **full page URL**, or a **tiny link** (`https://…/wiki/x/N4CIO`), coerced by `BeforeValidator(lambda x: str(x) if x is not None else None)` and resolved by `_resolve_page_id()` (`src/mcp_atlassian/servers/confluence.py:104`, tiny-id codec at 59-101); `title`: str\|None — default `None`; `space_key`: str\|None — default `None`; `include_metadata`: bool — default `True`; `convert_to_markdown`: bool — default `True` (false = raw HTML, "significantly increases token usage"). **Either `page_id` OR both `title`+`space_key`**; when `page_id` is set the other two are ignored with a warning (357-359). | When `include_metadata=True`: `{"metadata": <ConfluencePage.to_simplified_dict()>}`; when `False`: `{"content": {"value": <page.content>}}` (`src/mcp_atlassian/servers/confluence.py:401-406`). Error paths return a JSON object `{"error": "..."}` rather than raising — see Error shapes. Page shape per `src/mcp_atlassian/models/confluence/page.py:263`. | `src/mcp_atlassian/servers/confluence.py:280` (params 284-337, return 401-406) |
| `confluence_create_page` | `space_key`: str — **required**; `title`: str — **required**; `content`: str\|None — default `None`; `parent_id`: str\|None — default `None` (`BeforeValidator` str-coerces); `content_format`: str — default `"markdown"`, validated against `["markdown", "wiki", "storage", "xhtml"]` (`src/mcp_atlassian/servers/confluence.py:822-826`), `"xhtml"` maps to `"storage"` (837-839); `enable_heading_anchors`: bool — default `False` (markdown only); `include_content`: bool — **default `False`** (response omits the body); `emoji`: str\|None — default `None`; `content_file`: str\|None — default `None`, **mutually exclusive with `content`**, path confined to the workspace by `validate_safe_path` (`src/mcp_atlassian/servers/confluence.py:175`); `page_width`: str\|None — default `None` (`'full-width'` / `'default'`); `table_layout`: str\|None — default `None` (`'full-width'` 1800px / `'wide'` 960px / `'default'` 760px, markdown only); `subtype`: str\|None — default `None` (`'live'` = Confluence Live Doc, Cloud only) | `{"message": "Page created successfully", "page": <ConfluencePage.to_simplified_dict()>}` — literal at `src/mcp_atlassian/servers/confluence.py:860`. When `include_content=False` (the default) the `"content"` key is `pop`ped from the page dict first (`src/mcp_atlassian/servers/confluence.py:857-858`). | `src/mcp_atlassian/servers/confluence.py:679` (`@check_write_access` at 683, params 684-790, return 856-863) |
| `confluence_update_page` | (see source — same content/content_file/content_format family as create, plus version handling) | `JSON` with a message and the updated `ConfluencePage.to_simplified_dict()`. | `src/mcp_atlassian/servers/confluence.py:866` |

---

## Resources

**None.** `grep -rn "\.resource(\|@mcp.resource"` across `src/` returns no matches — there are no `@mcp.resource` / `@…_mcp.resource` handlers anywhere in the codebase. The only non-tool HTTP surface is a plain Starlette custom route: `@main_mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)` at `src/mcp_atlassian/servers/main.py:895-897`, returning `{"status": "ok"}` (`src/mcp_atlassian/servers/main.py:134-135`).

Note that several tools *return* MCP resource content inline without registering resources: `confluence_download_attachment` and `confluence_download_content_attachments` return `EmbeddedResource` / `BlobResourceContents` values, and `jira_get_issue_images` / `confluence_get_page_images` return `ImageContent` (imports at `src/mcp_atlassian/servers/jira.py:10`).

## Prompts

**None.** `grep -rn "\.prompt(\|@mcp.prompt"` across `src/` returns no matches. No `@mcp.prompt` handlers are registered.

## Auth model

Auth is resolved per product (Jira and Confluence configure independently) by `JiraConfig.from_env()` (`src/mcp_atlassian/jira/config.py:234`) and `ConfluenceConfig.from_env()` (`src/mcp_atlassian/confluence/config.py:102`). Cloud vs. Server/DC is decided by `is_atlassian_cloud_url(url)` (`src/mcp_atlassian/jira/config.py:267`, `src/mcp_atlassian/confluence/config.py:137`). `auth_type` is a `Literal` field (`src/mcp_atlassian/jira/config.py:164`, `src/mcp_atlassian/confluence/config.py:33`) taking values `oauth`, `basic`, `pat`, `cert`, `external`.

**Detection precedence — Cloud** (`src/mcp_atlassian/jira/config.py:278-300`): OAuth config → `basic` (needs `JIRA_USERNAME` + `JIRA_API_TOKEN`) → else `ValueError`. **Server/DC** (`src/mcp_atlassian/jira/config.py:301-325`): PAT wins over OAuth ("Server/DC: PAT takes priority over OAuth (fixes #824)", line 302) → OAuth → basic → `cert` (mTLS) → else `ValueError`. `external` short-circuits everything when `ATLASSIAN_EXTERNAL_AUTH_ENABLE` is truthy and no other credential is set (`src/mcp_atlassian/jira/config.py:270-277`).

**Exact env var names:**

| Purpose | Jira | Confluence | Global |
|---|---|---|---|
| Instance URL | `JIRA_URL` (`jira/config.py:243`) | `CONFLUENCE_URL` (`confluence/config.py:111`) | — |
| Cloud basic auth | `JIRA_USERNAME`, `JIRA_API_TOKEN` (`jira/config.py:257-258`) | `CONFLUENCE_USERNAME`, `CONFLUENCE_API_TOKEN` (`confluence/config.py:125-126`) | — |
| Server/DC PAT | `JIRA_PERSONAL_TOKEN` (`jira/config.py:259`) | `CONFLUENCE_PERSONAL_TOKEN` (`confluence/config.py:127`) | — |
| mTLS | `JIRA_CLIENT_CERT`, `JIRA_CLIENT_KEY`, `JIRA_CLIENT_KEY_PASSWORD` (`jira/config.py:353-355`) | `CONFLUENCE_CLIENT_CERT`, `CONFLUENCE_CLIENT_KEY`, `CONFLUENCE_CLIENT_KEY_PASSWORD` (`confluence/config.py:212-214`) | — |
| OAuth 2.0 | `JIRA_OAUTH_CLIENT_ID`, `JIRA_OAUTH_CLIENT_SECRET`, `JIRA_OAUTH_ACCESS_TOKEN` (`servers/main.py:813,818`; `.env.example:80-81,95`) | `CONFLUENCE_OAUTH_CLIENT_ID`, `CONFLUENCE_OAUTH_CLIENT_SECRET`, `CONFLUENCE_OAUTH_ACCESS_TOKEN` (`servers/main.py:814,819`; `.env.example:82-83,96`) | `ATLASSIAN_OAUTH_CLIENT_ID`, `ATLASSIAN_OAUTH_CLIENT_SECRET`, `ATLASSIAN_OAUTH_REDIRECT_URI`, `ATLASSIAN_OAUTH_SCOPE`, `ATLASSIAN_OAUTH_CLOUD_ID`, `ATLASSIAN_OAUTH_ACCESS_TOKEN`, `ATLASSIAN_OAUTH_ENABLE`, `ATLASSIAN_OAUTH_INSTANCE_URL` (`servers/main.py:806-822`) |
| OAuth proxy / DCR | — | — | `ATLASSIAN_OAUTH_PROXY_ENABLE` (`servers/main.py:61`, default false at 799), `ATLASSIAN_OAUTH_ALLOWED_CLIENT_REDIRECT_URIS` (758), `ATLASSIAN_OAUTH_ALLOWED_GRANT_TYPES` (766), `ATLASSIAN_OAUTH_REQUIRE_CONSENT` (862, default `true`), `PUBLIC_BASE_URL` (838) |
| Filtering / behavior | `JIRA_PROJECTS_FILTER` (`jira/config.py:331`), `JIRA_INTERNAL_ONLY_PROJECTS` (337), `JIRA_TIMEOUT` (359, default 75), `JIRA_SSL_VERIFY` (328), `DISABLE_JIRA_MARKUP_TRANSLATION` (349), `JIRA_ISSUE_KEY_PATTERN` / `JIRA_PROJECT_KEY_PATTERN` (`servers/jira.py:45-48`, read once at import time) | `CONFLUENCE_SPACES_FILTER` (`confluence/config.py:202`), `CONFLUENCE_TIMEOUT` (219-222, default 75), `CONFLUENCE_ATTACHMENT_DOWNLOAD_USE_V1` (225) | `READ_ONLY_MODE`, `ENABLED_TOOLS`, `TOOLSETS`, `ALLOW_GLOBAL_CRED_FALLBACK`, `IGNORE_HEADER_AUTH`, `MCP_ALLOWED_URL_DOMAINS`, `ATLASSIAN_EXTERNAL_AUTH_ENABLE` |

**Multi-user / per-request auth headers.** `UserTokenMiddleware` (`src/mcp_atlassian/servers/main.py:413`) is installed as ASGI middleware on the HTTP app (`src/mcp_atlassian/servers/main.py:394-395`). It only processes POSTs to the MCP endpoint path (`_should_process_auth`, `src/mcp_atlassian/servers/main.py:539-550`). Recognised headers:

- `Authorization: Bearer <token>` → `auth_type = "oauth"` (`src/mcp_atlassian/servers/main.py:672-684`)
- `Authorization: Token <PAT>` → `auth_type = "pat"` (`src/mcp_atlassian/servers/main.py:686-698`)
- `Authorization: Basic <base64(email:api_token)>` → `auth_type = "basic"`; splits on the first `:` (`src/mcp_atlassian/servers/main.py:700-733`)
- `X-Atlassian-Cloud-Id` → per-request cloud ID (`src/mcp_atlassian/servers/main.py:558`, 643-647)
- `X-Atlassian-Jira-Personal-Token`, `X-Atlassian-Jira-Url`, `X-Atlassian-Confluence-Personal-Token`, `X-Atlassian-Confluence-Url` (`src/mcp_atlassian/servers/main.py:567-572`, assembled at 610-620). Supplying a token+URL pair without an `Authorization` header sets `auth_type = "pat"` (`src/mcp_atlassian/servers/main.py:655-663`). Both URL headers are SSRF-validated via `validate_url_for_ssrf` (`src/mcp_atlassian/servers/main.py:593-607`).
- `IGNORE_HEADER_AUTH` truthy skips all of the above ("useful for GCP Cloud Run / AWS ALB that inject Authorization headers", `src/mcp_atlassian/servers/main.py:456-458`).

**Global-credential fallback is refused by default over HTTP.** Two independent guards: the middleware rejects unauthenticated MCP POSTs with 401 when no OAuth provider is attached and `ALLOW_GLOBAL_CRED_FALLBACK` is off (`src/mcp_atlassian/servers/main.py:494-511`), and the fetcher dependency raises `ValueError` with "refusing to serve an unauthenticated request with the operator's global credentials" (`src/mcp_atlassian/servers/dependencies.py:990-1000`). stdio / non-HTTP is unaffected.

**OAuth scopes.** The documented default scope string is `read:jira-work write:jira-work read:jira-user read:confluence-space.summary read:confluence-content.summary read:confluence-content.all write:confluence-content search:confluence read:page:confluence offline_access` (`.env.example:67`), with the note "IMPORTANT: 'offline_access' is crucial for refresh tokens" (same line; echoed at `docs/authentication.mdx:158`). The setup wizard reads/prompts for `ATLASSIAN_OAUTH_SCOPE` (`src/mcp_atlassian/utils/oauth_setup.py:426-432`).

**Required Jira/Confluence product permissions** (project roles, space permissions, JSM agent seats, admin rights) are **NOT DETERMINED FROM SOURCE** — the code declares only OAuth scopes; product-level permission requirements are enforced server-side by Atlassian and surface as 401/403 → `MCPAtlassianAuthenticationError`. `docs/authentication.mdx:123-124` only says "Configure Permissions / Add scopes for Jira/Confluence as needed".

## Pagination

There is no single global pagination scheme; each tool declares its own `Field` constraints.

- **`jira_search`**: `limit` default `10`, `ge=1`, **no `le`** (`src/mcp_atlassian/servers/jira.py:780` — description claims "(1-50)" but nothing enforces it); `start_at` default `0`, `ge=0` (`src/mcp_atlassian/servers/jira.py:784`); `page_token` (Cloud-only cursor) default `None` (`src/mcp_atlassian/servers/jira.py:805-814`).
- **`jira_get_project_issues`**: `limit` default `10`, `ge=1`, **`le=50`** (`src/mcp_atlassian/servers/jira.py:1102`); `start_at` default `0`, `ge=0` (1106).
- **Agile tools** (`jira_get_agile_boards` 1481, `jira_get_board_issues` 1548, `jira_get_sprints_from_board` 1606, `jira_get_sprint_issues` 1653): all `limit` default `10`, `ge=1`, **`le=50`**; `start_at` default `0`, `ge=0`.
- **`jira_get_service_desk_queues`**: `limit` default **`50`**, `ge=1`, `le=50` (`src/mcp_atlassian/servers/jira.py:3576`). **`jira_get_queue_issues`**: `limit` default `50`, `ge=1`, **no `le`** (`src/mcp_atlassian/servers/jira.py:3626`). **`jira_get_request_types`**: default `50`, `ge=1`, `le=50` (3673).
- **`jira_search_assignable_users`**: default 20, **`le=1000`** (`src/mcp_atlassian/servers/jira.py:360-363`).
- **`jira_search_projects`**: `le=50` (`src/mcp_atlassian/servers/jira.py:3403`).
- **`jira_get_issue` `comment_limit`**: default `10`, `ge=0`, **`le=100`** (`src/mcp_atlassian/servers/jira.py:604-608`).
- **`jira_get_project_epic_hierarchy` / `jira_get_cross_project_dependencies`**: `le=500` (`src/mcp_atlassian/servers/jira.py:4582`, `4631`).
- **`confluence_search`**: `limit` default `10`, `ge=1`, **`le=50`** (`src/mcp_atlassian/servers/confluence.py:225`). **`confluence_search_user`**: `le=50` (1537). **`confluence_get_page_children`**: `le=50` (434) with a `start` param (451). **`confluence_get_space_page_tree`**: `limit` default `100`, `ge=1`, **`le=1000`** (`src/mcp_atlassian/servers/confluence.py:519-527`). **`confluence_get_attachments`**: `start` (2073) and `le=100` (2092). **`confluence_list_page_templates`**: `le=200` (2707).

**Global optional ceiling.** `ATLASSIAN_MAX_PAGINATION_LIMIT` clamps any `limit` at the mixin entry point via `clamp_limit()` (`src/mcp_atlassian/utils/pagination.py:20-40`). **Disabled by default** — "Disabled by default — opt in via ATLASSIAN_MAX_PAGINATION_LIMIT" (`src/mcp_atlassian/utils/pagination.py:10`); a cap of `<= 0` is a no-op (`src/mcp_atlassian/utils/pagination.py:29-31`), and `requested <= 0` passes through unchanged (26-27).

Cursor pagination: `jira_search` accepts `page_token` and `JiraSearchResult` echoes `next_page_token` only when non-`None` (`src/mcp_atlassian/models/jira/search.py:122-123`). Confluence tree truncation is signalled with an advisory string rather than a cursor: `f"Results truncated at {limit} pages. Increase limit to see more."` (`src/mcp_atlassian/servers/confluence.py:554-556`), set only when the fetcher saw `_links.next`.

## Rate limits

The server imposes **no rate limit by default**, but ships an opt-in outbound throttling layer in `src/mcp_atlassian/utils/http.py` — "The optional retry policy, concurrency cap, rate limiter, and circuit breaker are disabled by default and gated behind env vars" (`src/mcp_atlassian/utils/http.py:9-11`).

- Retries: `ATLASSIAN_RETRY_TOTAL` (default `DEFAULT_RETRY_TOTAL = 0`, i.e. off — `src/mcp_atlassian/utils/http.py:32`, read at 193), `ATLASSIAN_RETRY_BACKOFF` (default `1.0` — line 33, read at 198), retry statuses `DEFAULT_RETRY_STATUSES = (429, 502, 503, 504)` (`src/mcp_atlassian/utils/http.py:34`). The `Retry-After` header is respected unless `ATLASSIAN_RETRY_IGNORE_RETRY_AFTER` is truthy (`src/mcp_atlassian/utils/http.py:184-190`, 210-211).
- Concurrency cap: `ATLASSIAN_MAX_CONCURRENT_REQUESTS`, default `0` = disabled (`src/mcp_atlassian/utils/http.py:283`).
- Outbound rate limit: `ATLASSIAN_REQUESTS_PER_SECOND`, default `0.0` = disabled, token-bucket (`src/mcp_atlassian/utils/http.py:349`, bucket at 301-304).
- Circuit breaker: `ATLASSIAN_CIRCUIT_BREAKER_THRESHOLD` default `0` = disabled, `ATLASSIAN_CIRCUIT_BREAKER_COOLDOWN` default `30.0`s (`src/mcp_atlassian/utils/http.py:408-417`); trips "after N consecutive 429/503 responses" (`src/mcp_atlassian/utils/http.py:84`) and raises `CircuitBreakerOpenError` (`src/mcp_atlassian/utils/http.py:42-43`).

No inbound (per-client) rate limiting on the MCP endpoint was found in source.

## Error shapes

**Exception → ToolError conversion.** Every tool is wrapped by `handle_tool_errors` at registration time — `super().tool(handle_tool_errors(fn), **registration_kwargs)` (`src/mcp_atlassian/servers/error_handling.py:109`). The wrapper re-raises `ToolError` untouched, and converts every other exception (`src/mcp_atlassian/utils/decorators.py:100-110`):

```python
detail = str(e).strip() or type(e).__name__
message = f"Error calling tool '{tool_name}': {detail}"
raise ToolError(message) from e
```

FastMCP renders a `ToolError` to the model as a tool result with `isError: true` and this message string as text, so the underlying Atlassian detail survives FastMCP's usual masking of non-`ToolError` exceptions ("Raising ToolError from inside the tool preserves actionable Atlassian API errors for MCP clients even when the FastMCP server masks non-ToolError exceptions", `src/mcp_atlassian/utils/decorators.py:93-96`). Note `tool_name` here is the **unprefixed function name** (`func.__name__`, `src/mcp_atlassian/utils/decorators.py:98`), so the message reads `Error calling tool 'get_issue': …`, not `'jira_get_issue'`.

**Auth failures.** `MCPAtlassianAuthenticationError` — a bare `Exception` subclass, "Raised when Atlassian API authentication fails (401/403)" (`src/mcp_atlassian/exceptions.py:1-4`). Raised by `handle_auth_errors` / `handle_atlassian_api_errors` on HTTP 401/403 with the literal message (`src/mcp_atlassian/utils/decorators.py:172-178`):

```
Authentication failed for {service_name} ({status_code}). Token may be expired or invalid. Please verify credentials.
```

`handle_atlassian_api_errors` also maps `KeyError` → `ValueError(f"{operation_name} returned an unexpected response from {service_name}: missing key {e}")` (`src/mcp_atlassian/utils/decorators.py:220-227`), `requests.RequestException` → `ValueError(f"Network error during {operation_name}: {e}")` (228-232), `(ValueError, TypeError)` → `ValueError(f"Error processing {operation_name} results: {e}")` (233-237), and everything else → `RuntimeError(f"Unexpected error during {operation_name}: {e}")` (238-245).

**Read-only rejection.** `ValueError(f"Cannot {action_description} in read-only mode.")` where `action_description = tool_name.replace("_", " ")` — so `create_issue` yields the literal `"Cannot create issue in read-only mode."` (`src/mcp_atlassian/utils/decorators.py:137-142`). This surfaces to the model as `Error calling tool 'create_issue': Cannot create issue in read-only mode.`

**Disabled / unknown tool.** `NotFoundError(f"Unknown tool: {key}")` (`src/mcp_atlassian/servers/main.py:372`) — deliberately byte-identical for a genuinely unknown tool and a filtered-out one, "no exists-but-disabled leak" (`src/mcp_atlassian/servers/main.py:366-367`).

**Transport-level 401s** are JSON, not MCP errors — `{"error": "<message>"}` with `content-type: application/json` (`src/mcp_atlassian/servers/main.py:516-537`). Literal messages include `"Unauthorized: Empty Bearer token"` (676), `"Unauthorized: Empty Token (PAT)"` (690), `"Unauthorized: Invalid Basic auth encoding"` (712), `"Unauthorized: Invalid Basic auth format. Expected 'email:api_token'"` (717-719), `"Unauthorized: Email or API token is empty"` (724), `"Unauthorized: Only 'Bearer <OAuthToken>', 'Token <PAT>', or 'Basic <base64(email:api_token)>' types are supported."` (746-749), `"Authentication required: no Atlassian credentials were provided."` (509), and `f"Forbidden: Invalid Jira URL - {ssrf_error}"` (597).

**Soft errors returned as data (not raised).** `confluence_get_page` catches fetch failures and returns a JSON body instead: `{"error": f"Failed to retrieve page by ID '{page_id}': {e}"}` (`src/mcp_atlassian/servers/confluence.py:372-376`), `{"error": f"Page with title '{title}' not found in space '{space_key}'."}` (383-385), and `{"error": "Page not found with the provided identifiers."}` (396). A caller cannot distinguish these from a successful result by protocol-level `isError`. Similarly `jira_get_issue` swallows enrichment failures into empty values (`src/mcp_atlassian/servers/jira.py:720-742`).

**Truncation of long bodies.** There is **no character/token cap on page or issue body text** — no `MAX_CHARS`/content-length truncation constant exists anywhere in `src/`. The only hard size limit is on binary attachments: `ATTACHMENT_MAX_BYTES: int = 50 * 1024 * 1024` — "Maximum attachment size for inline download (50 MB). Used by both Jira and Confluence server tools to gate in-memory transfers" (`src/mcp_atlassian/utils/media.py:10-12`). Enforced at `src/mcp_atlassian/servers/jira.py:1241` and `1393`, and `src/mcp_atlassian/servers/confluence.py:2238`, `2271`, `2403`, `2614`; also `src/mcp_atlassian/jira/attachments.py:217` and `src/mcp_atlassian/jira/customer_requests.py:479-482` (message references "MiB inline limit"). One error-string shortener exists at 400 chars: `_shorten_error_text(error_text, max_length=400)` (`src/mcp_atlassian/jira/customer_requests.py:71-76`).

Body-size control is instead **advisory / opt-in**, achieved by field selection rather than truncation: `jira_update_issue`'s `return_fields` ("TOKEN-SAVING TIP: after an update you usually do NOT need the whole issue back… this can cut the response by thousands of tokens", `src/mcp_atlassian/servers/jira.py:2087-2091`), `confluence_create_page`'s `include_content=False` default which `pop`s `"content"` (`src/mcp_atlassian/servers/confluence.py:857-858`), and `confluence_get_page`'s `convert_to_markdown=True` default whose Field description warns that raw HTML "significantly increases token usage in AI responses" (`src/mcp_atlassian/servers/confluence.py:330-334`). Confluence storage/ADF → Markdown conversion is done in `src/mcp_atlassian/preprocessing/` (confluence.py / jira.py); no length limit is applied there.

## Not exposed (E3)

Verified by `grep -c "async def <name>("` across both server modules — each of the following returns **0**, i.e. no such tool is registered:

**Jira — project & instance administration.** No `create_project`, `update_project`, `delete_project`. Projects are read-only through this server: only `jira_get_all_projects` (`src/mcp_atlassian/servers/jira.py:3317`), `jira_search_projects` (3385), `jira_get_project_fields` (3470), `jira_get_project_issue_types` (3180), `jira_get_project_components` (3297), `jira_get_project_versions` (3277). Versions are the sole writable project sub-resource (`jira_create_version` 3828, `jira_batch_create_versions` 3885, `jira_update_version` 3969) — and there is **no `delete_version`**.

**Jira — workflow & scheme administration.** No `create_workflow`, no `update_permission_scheme`. Workflow interaction is limited to *executing* an existing transition (`jira_transition_issue`, 2916) and reading available ones (`jira_get_transitions`, 1128); the `JiraTransition` model (`src/mcp_atlassian/models/jira/workflow.py`) is read-only. No screen scheme, notification scheme, issue-type scheme, field-configuration, or custom-field-creation tools exist. Custom fields are discoverable only (`jira_search_fields` 869, `jira_get_field_options` 984, `jira_get_create_fields` 3224).

**Jira — comment/worklog deletion.** `jira_add_comment` (2450) and `jira_edit_comment` (2536) exist but there is **no `delete_comment`**. `jira_add_worklog` (2583) exists but there is **no `update_worklog` and no `delete_worklog`**.

**Jira — agile.** `jira_create_sprint` (3002) / `jira_update_sprint` (3048) exist but **no `delete_sprint`**; no board create/update/delete; no backlog rank/reorder beyond `jira_move_issues_to_backlog` (3146).

**Jira — attachments are read-only-ish.** `jira_download_attachments` (1186) and `jira_get_issue_images` (1320) read; uploads only happen as a side-effect of `jira_update_issue`'s `attachments` parameter (`src/mcp_atlassian/servers/jira.py:2029-2038`). There is no standalone `jira_upload_attachment` and no `jira_delete_attachment`.

**Jira — user administration.** Read-only: `jira_get_user_profile` (259), `jira_search_assignable_users` (320). No user/group create, no group membership mutation.

**Confluence — space administration.** No `create_space`, `update_space`, `delete_space`. Spaces are only reachable indirectly (`confluence_get_space_page_tree` 509, `confluence_get_space_permissions` 3078 — read-only). No `set_space_permissions` counterpart to `confluence_set_page_restrictions` (2863).

**Confluence — attachments ARE fully exposed** (contrary to a common assumption): upload (`confluence_upload_attachment` 1827, `confluence_upload_attachments` 1969), list (`confluence_get_attachments` 2058), download (`confluence_download_attachment` 2163, `confluence_download_content_attachments` 2315), delete (`confluence_delete_attachment` 2468), and inline images (`confluence_get_page_images` 2522) — an entire `confluence_attachments` toolset (`src/mcp_atlassian/utils/toolsets.py:138-142`, `default=False`).

**Confluence — other gaps.** No `archive_page`, no page-restore-from-trash, no blog-post-specific create tool (blogposts are reachable only as "content" in label/attachment tools), no `delete_comment` / `resolve_inline_comment`, no watchers/notifications tools, no macro or content-property manipulation.

**Cloud-only tools that silently do not exist on Server/DC** (README/docs caveats): `jira_move_issue` is "(Jira Cloud only)" (`src/mcp_atlassian/servers/jira.py` docstring, tool at 2378); `jira_batch_get_changelogs` is "(Cloud only)" (1901); `jira_get_issue_proforma_forms` is Cloud-only "requires cloud_id for Forms API" (`docs/compatibility.mdx:200`); `confluence_get_page_views` is "Cloud-only analytics API" (`docs/compatibility.mdx:202`); `confluence_get_page_template` and `confluence_create_page_from_template` are documented as Cloud-only in their own docstrings (`src/mcp_atlassian/servers/confluence.py:2751`, `2787`). Custom field IDs differ between Cloud and Server/DC — "Use `jira_search_fields` to discover the correct field IDs for your instance" (`docs/compatibility.mdx:231`).

## Notes for mocking

- **Every tool returns a JSON string, not a JSON object.** The return annotation is `-> str` and the body is `json.dumps(result, indent=2, ensure_ascii=False)` (e.g. `src/mcp_atlassian/servers/jira.py:744`, `866`; `src/mcp_atlassian/servers/confluence.py:277`, `406`). A mock must serialise, with 2-space indent and non-ASCII left unescaped, or it will not byte-match. Image/attachment tools are the exception (`ImageContent` / `EmbeddedResource` lists).
- **Jira issue field shape is *conditional*, driven by the `fields` request parameter.** `JiraIssue.to_simplified_dict()` guards nearly every key behind `should_include_field(name)`, which returns true only when `requested_fields == "*all"`, is not a list, or contains the name (`src/mcp_atlassian/models/jira/issue.py:530-535`). So a mock for `fields="summary,status"` must emit **only** `{id, key, summary, status, browse_url?}` — not a full issue. The API field name and the output key differ in several places: request `issuetype` → output `issue_type`; request `fixVersions` → output `fix_versions`; request `comment` → output `comments`; request `attachment` → output `attachments` (lines 561, 615, 641, 647).
- **Two keys ignore the field filter.** `browse_url` is emitted whenever set (`src/mcp_atlassian/models/jira/issue.py:545-546`) and `changelogs` is emitted whenever present, with the explicit comment "Not use should_include_field since you won't get changelogs if you don't ask for them" (652-657).
- **`assignee` is never absent when requested.** Unassigned issues get the sentinel `{"display_name": "Unassigned"}` rather than `null` or a missing key (`src/mcp_atlassian/models/jira/issue.py:598-602`). Mocks that emit `"assignee": null` will diverge.
- **Custom fields are nested objects, not scalars.** Output is `{"customfield_10243": {"value": <processed>, "name": <field label, only if known>}}` (`src/mcp_atlassian/models/jira/issue.py:665-691`). With `use_display_names=True` the tool instead calls `to_display_name_dict()` and the *key* becomes the human label (`src/mcp_atlassian/servers/jira.py:704-712`).
- **JQL is passed through verbatim — the server does not parse or validate it.** `jira_search` hands `jql` straight to `jira.search_issues` (`src/mcp_atlassian/servers/jira.py:852-861`). A mock can key on the exact string. The 205-word `RESERVED_JQL_WORDS` set (`src/mcp_atlassian/jira/constants.py:9-205`) is used only for *quoting* identifiers elsewhere, not for validating the user's JQL.
- **CQL is NOT passed through verbatim.** `confluence_search` rewrites a query with no `=`, `~`, `>`, `<`, `" AND "`, `" OR "`, or `"currentUser()"` into `siteSearch ~ "<query>"`, and on any exception retries as `text ~ "<query>"` (`src/mcp_atlassian/servers/confluence.py:253-271`). A mock backend will see two different CQL strings for one plain-text query if the first call throws.
- **Jira search returns an object; Confluence search returns a bare array.** `jira_search` → `{"total", "start_at", "max_results", "issues": [...]}` (`src/mcp_atlassian/models/jira/search.py:116-121`); `confluence_search` → `[page, page, ...]` with no envelope (`src/mcp_atlassian/servers/confluence.py:276-277`). Easy to get backwards.
- **`next_page_token` / `version_date` are conditionally present.** `next_page_token` appears only when non-`None` (`src/mcp_atlassian/models/jira/search.py:122-123`); Confluence `version`, `version_author`, `version_date` appear only when a version object exists, and `version_date` is deliberately **raw ISO 8601 with offset** while `created`/`updated` are run through `format_timestamp` (`src/mcp_atlassian/models/confluence/page.py:286-293`).
- **Issue keys are regex-validated client-side before any HTTP call.** `pattern=ISSUE_KEY_PATTERN` (default `^[A-Z][A-Z0-9_]+-\d+(?:-\d+)*$`) and `PROJECT_KEY_PATTERN` (`^[A-Z][A-Z0-9_]+$`) are compiled at import time from `JIRA_ISSUE_KEY_PATTERN` / `JIRA_PROJECT_KEY_PATTERN` (`src/mcp_atlassian/servers/jira.py:45-48`). A lowercase key or single-letter project prefix is rejected by Pydantic before the mock is ever reached — a fixture using `proj-1` will fail schema validation, not return a 404.
- **Complex arguments arrive as JSON *strings*, not objects.** `additional_fields`, `fields` (on update), `visibility`, and `comment_visibility` are all typed `str | None` and parsed inside the tool (`_parse_additional_fields` at `src/mcp_atlassian/servers/jira.py:161`, `_parse_visibility` at 126). `attachments` accepts either a JSON array string or a comma-separated list (`src/mcp_atlassian/servers/jira.py:2141-2157`).
- **`jira_add_comment` accepts two argument names for the same field** via `validation_alias=AliasChoices("body", "comment")` (`src/mcp_atlassian/servers/jira.py:2468`) — a mock keyed on `body` alone will miss callers sending `comment`.
