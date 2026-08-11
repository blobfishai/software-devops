# github/github-mcp-server — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/github__github-mcp-server` @ git commit `eff4c3c` ("Minimize Actions workflow list responses (#3047)", 2026-08-10), read 2026-08-11
**Language / framework:** Go (`go.mod`), MCP via the official Go SDK `github.com/modelcontextprotocol/go-sdk/mcp`; GitHub REST via `github.com/google/go-github/v89/github` and GraphQL via `github.com/shurcooL/githubv4` (`pkg/github/tools.go:1`-`pkg/github/tools.go:13`). Schemas are `github.com/google/jsonschema-go/jsonschema` values, not struct reflection.
**Registration entrypoint:**
- Tool inventory (the authoritative list): `pkg/github/tools.go:212` (`func AllTools`).
- Inventory assembly (tools + resources + prompts): `pkg/github/inventory.go:13` (`func NewInventory`).
- Actual MCP registration onto the server: `pkg/github/server.go:124` (`inv.RegisterAll(ctx, ghServer, deps, ...)`), implemented at `pkg/inventory/registry.go:260`.
- Per-tool constructor helpers: `pkg/github/dependencies.go:230` (`NewTool[In, Out]`) and `pkg/github/dependencies.go:253` (`NewToolFromHandler`). There is **no** `mcp.NewTool(...)` in this repo — tools are `mcp.Tool{Name: "...", ...}` struct literals passed to `NewTool`.

**Toolsets** (all declared in `pkg/github/tools.go:22`-`pkg/github/tools.go:155`; `Default: true` means on when the client sends no toolset selection):

| Toolset ID | Default? | Citation |
|---|---|---|
| `all` (meta — enables everything) | n/a | `pkg/github/tools.go:24` |
| `default` (meta — expands to `Default: true` sets) | n/a | `pkg/github/tools.go:29` |
| `context` | **DEFAULT ON** | `pkg/github/tools.go:34`, `:36` |
| `repos` | **DEFAULT ON** | `pkg/github/tools.go:41`, `:43` |
| `issues` | **DEFAULT ON** | `pkg/github/tools.go:52`, `:54` |
| `pull_requests` | **DEFAULT ON** | `pkg/github/tools.go:59`, `:61` |
| `users` | **DEFAULT ON** | `pkg/github/tools.go:66`, `:68` |
| `copilot` | **DEFAULT ON** | `pkg/github/tools.go:140`, `:142` |
| `git` | opt-in | `pkg/github/tools.go:47` |
| `orgs` | opt-in | `pkg/github/tools.go:72` |
| `actions` | opt-in | `pkg/github/tools.go:77` |
| `code_quality` | opt-in | `pkg/github/tools.go:82` |
| `code_security` | opt-in | `pkg/github/tools.go:87` |
| `secret_protection` | opt-in | `pkg/github/tools.go:92` |
| `dependabot` | opt-in | `pkg/github/tools.go:97` |
| `notifications` | opt-in | `pkg/github/tools.go:102` |
| `discussions` | opt-in | `pkg/github/tools.go:107` |
| `gists` | opt-in | `pkg/github/tools.go:113` |
| `security_advisories` | opt-in | `pkg/github/tools.go:118` |
| `projects` | opt-in | `pkg/github/tools.go:123` |
| `stargazers` | opt-in | `pkg/github/tools.go:129` |
| `labels` | opt-in | `pkg/github/tools.go:134` |
| `copilot_issue_intents` | opt-in | `pkg/github/tools.go:151` |
| `copilot_spaces` | **remote-server only, no tools in this repo** | `pkg/github/tools.go:173` |
| `github_support_docs_search` | **remote-server only, no tools in this repo** | `pkg/github/tools.go:178` |

"default" / "all" keyword expansion happens in `pkg/inventory/builder.go:337`-`pkg/inventory/builder.go:360`. Toolset selection comes from `--toolsets` / `GITHUB_TOOLSETS` (`cmd/github-mcp-server/main.go:234`, `:275`) or the `X-MCP-Toolsets` HTTP header (`pkg/http/headers/headers.go:37`).

## Full tool list (116 unique tool names / 117 registrations)

117 `inventory.ServerTool` entries are returned by `AllTools` (`pkg/github/tools.go:212`-`pkg/github/tools.go:377`); `get_label` is registered twice under two different toolsets (`GetLabel` in `issues`, `GetLabelForLabelsToolset` in `labels` — `pkg/github/labels.go:125`-`pkg/github/labels.go:129`), so the MCP client sees **116 distinct tool names**. This count was verified two ways: by enumerating every `Name: "..."` literal under `pkg/github/*.go` (non-test), and by diffing against the 116 published schema snapshots in `pkg/github/__toolsnaps__/` — the sets match exactly.

Legend: **R** = `Annotations.ReadOnlyHint: true`, **W** = write.

### `context` — DEFAULT ON
- `get_me` — R — Get details of the authenticated GitHub user — `pkg/github/context_tools.go:49`
- `get_teams` — R — Get details of the teams the user is a member of — `pkg/github/context_tools.go:130`
- `get_team_members` — R — Get member usernames of a specific team in an organization — `pkg/github/context_tools.go:233`
- `ui_get` — R — Fetch UI data for MCP Apps (labels, assignees, milestones, issue types, branches, issue fields, reviewers) — `pkg/github/ui_tools.go:37` *(flag `remote_mcp_ui_apps` — `pkg/github/ui_tools.go:102`; `_meta.ui.visibility:["app"]` keeps it out of the model's tool list — `pkg/github/ui_tools.go:45`)*

### `repos` — DEFAULT ON
- `search_repositories` — R — Find GitHub repositories by name, description, readme, topics, or other metadata — `pkg/github/search.go:53`
- `search_code` — R — Fast and precise code search across ALL GitHub repositories using GitHub's native search engine — `pkg/github/search.go:224`
- `search_commits` — R — Search for commits across GitHub repositories using GitHub's commit search syntax — `pkg/github/search.go:553`
- `get_file_contents` — R — Get the contents of a file or directory from a GitHub repository — `pkg/github/repositories.go:759`
- `get_file_blame` — R — Get git blame information for a file, showing the commit that last modified each line — `pkg/github/repositories.go:2470` *(flag `file_blame` — `pkg/github/repositories.go:2762`)*
- `get_commit` — R — Get details for a commit from a GitHub repository — `pkg/github/repositories.go:31`
- `list_commits` — R — Get list of commits of a branch in a GitHub repository — `pkg/github/repositories.go:181`
- `list_branches` — R — List branches in a GitHub repository — `pkg/github/repositories.go:317`
- `list_tags` — R — List git tags in a GitHub repository — `pkg/github/repositories.go:1589`
- `get_tag` — R — Get details about a specific git tag in a GitHub repository — `pkg/github/repositories.go:1680`
- `list_releases` — R — List releases in a GitHub repository — `pkg/github/repositories.go:1813`
- `get_latest_release` — R — Get the latest release in a GitHub repository — `pkg/github/repositories.go:1916`
- `get_release_by_tag` — R — Get a specific release by its tag name in a GitHub repository — `pkg/github/repositories.go:1990`
- `list_repository_collaborators` — R — List collaborators of a GitHub repository — `pkg/github/repositories.go:2771`
- `create_or_update_file` — W — Create or update a single file in a GitHub repository — `pkg/github/repositories.go:409`
- `create_repository` — W — Create a new GitHub repository in your account or specified organization — `pkg/github/repositories.go:605`
- `fork_repository` — W — Fork a GitHub repository to your account or specified organization — `pkg/github/repositories.go:957`
- `create_branch` — W — Create a new branch in a GitHub repository — `pkg/github/repositories.go:1241`
- `push_files` — W — Push multiple files to a GitHub repository in a single commit — `pkg/github/repositories.go:1354`
- `delete_file` — W — Delete a file from a GitHub repository — `pkg/github/repositories.go:1056`

### `issues` — DEFAULT ON
- `issue_read` — R — Get information about a specific issue in a GitHub repository — `pkg/github/issues.go:645`
- `list_issues` — R — List issues in a GitHub repository (GraphQL, cursor paginated) — `pkg/github/issues.go:2827`
- `search_issues` — R — Search issues using natural-language semantic matching — `pkg/github/issues.go:1693`
- `list_issue_types` — R — List supported issue types for a repository or its owner organization — `pkg/github/issues.go:1091`
- `list_issue_fields` — R — List issue fields for a repository or organization — `pkg/github/issue_fields.go:111`
- `get_label` — R — Get a specific label from a repository — `pkg/github/labels.go:30`
- `find_duplicate` — R — Find likely duplicate issues for an existing issue — `pkg/github/find_duplicate.go:78` *(flag `duplicate_detection` — `pkg/github/find_duplicate.go:178`)*
- `issue_dependency_read` — R — Read an issue's blocked_by / blocking dependency relationships — `pkg/github/issue_dependencies.go:57` *(flag `issue_dependencies` — `pkg/github/issue_dependencies.go:106`)*
- `issue_write` — W — Create a new or update an existing issue in a GitHub repository — `pkg/github/issues.go:2180` *(suppressed when flag `issues_granular` on — `pkg/github/issues.go:2446`)*
- `add_issue_comment` — W — Add a comment and/or reaction to an issue or issue comment — `pkg/github/issues.go:1193`
- `sub_issue_write` — W — Add a sub-issue to a parent issue — `pkg/github/issues.go:1389` *(suppressed when flag `issues_granular` on — `pkg/github/issues.go:1496`)*
- `issue_dependency_write` — W — Add or remove an issue dependency relationship — `pkg/github/issue_dependencies.go:194` *(flag `issue_dependencies` — `pkg/github/issue_dependencies.go:323`)*
- `create_issue` — W — Create a new issue with a title and optional body — `pkg/github/issues_granular.go:120` *(flag `issues_granular` only)*
- `update_issue_title` — W — Update the title of an existing issue — `pkg/github/issues_granular.go:202` *(flag `issues_granular` only)*
- `update_issue_body` — W — Update the body content of an existing issue — `pkg/github/issues_granular.go:222` *(flag `issues_granular` only)*
- `update_issue_assignees` — W — Replace the assignees of an existing issue — `pkg/github/issues_granular.go:244` *(flag `issues_granular` only)*
- `update_issue_labels` — W — Replace the labels of an existing issue — `pkg/github/issues_granular.go:462` *(flag `issues_granular` only)*
- `update_issue_milestone` — W — Update the milestone of an existing issue — `pkg/github/issues_granular.go:646` *(flag `issues_granular` only)*
- `update_issue_type` — W — Set or remove the type of an existing issue — `pkg/github/issues_granular.go:687` *(flag `issues_granular` only)*
- `update_issue_state` — W — Update the state of an existing issue (open or closed) — `pkg/github/issues_granular.go:853` *(flag `issues_granular` only)*
- `set_issue_fields` — W — Set org-level custom issue field values on an issue — `pkg/github/issues_granular.go:1303` *(flag `issues_granular` only)*
- `add_sub_issue` — W — Add a sub-issue to a parent issue — `pkg/github/issues_granular.go:1034` *(flag `issues_granular` only)*
- `remove_sub_issue` — W — Remove a sub-issue from a parent issue — `pkg/github/issues_granular.go:1108` *(flag `issues_granular` only)*
- `reprioritize_sub_issue` — W — Reorder a sub-issue relative to other sub-issues — `pkg/github/issues_granular.go:1177` *(flag `issues_granular` only)*
- `add_issue_reaction` — W — Add a reaction to an issue or pull request — `pkg/github/issues_granular.go:1550` *(flag `issues_granular` only)*
- `add_issue_comment_reaction` — W — Add a reaction to an issue or PR comment — `pkg/github/issues_granular.go:1632` *(flag `issues_granular` only)*

### `pull_requests` — DEFAULT ON
- `pull_request_read` — R — Get information on a specific pull request (9 sub-methods incl. diff, files, reviews, check runs) — `pkg/github/pullrequests.go:74`
- `list_pull_requests` — R — List pull requests in a GitHub repository — `pkg/github/pullrequests.go:1372`
- `search_pull_requests` — R — Search PRs using issues search syntax, pre-scoped to `is:pr` — `pkg/github/pullrequests.go:1659`
- `create_pull_request` — W — Create a new pull request in a GitHub repository — `pkg/github/pullrequests.go:655`
- `update_pull_request` — W — Update an existing pull request — `pkg/github/pullrequests.go:916` *(suppressed when flag `pull_requests_granular` on — `pkg/github/pullrequests.go:1173`)*
- `merge_pull_request` — W — Merge a pull request — `pkg/github/pullrequests.go:1536`
- `update_pull_request_branch` — W — Update the PR branch with latest changes from base — `pkg/github/pullrequests.go:1708`
- `pull_request_review_write` — W — Create and/or submit, delete review of a pull request; resolve/unresolve threads — `pkg/github/pullrequests.go:1834` *(suppressed when flag `pull_requests_granular` on — `pkg/github/pullrequests.go:1883`)*
- `add_comment_to_pending_review` — W — Add a review comment to the requester's latest pending review — `pkg/github/pullrequests.go:2335` *(suppressed when flag `pull_requests_granular` on — `pkg/github/pullrequests.go:2416`)*
- `add_reply_to_pull_request_comment` — W — Reply and/or react to an existing PR comment — `pkg/github/pullrequests.go:1215`
- `update_pull_request_title` — W — Update the title of an existing PR — `pkg/github/pullrequests_granular.go:113` *(flag `pull_requests_granular` only)*
- `update_pull_request_body` — W — Update the body of an existing PR — `pkg/github/pullrequests_granular.go:133` *(flag `pull_requests_granular` only)*
- `update_pull_request_state` — W — Update the state (open/closed) of an existing PR — `pkg/github/pullrequests_granular.go:153` *(flag `pull_requests_granular` only)*
- `update_pull_request_draft_state` — W — Mark a PR as draft or ready for review — `pkg/github/pullrequests_granular.go:179` *(flag `pull_requests_granular` only)*
- `request_pull_request_reviewers` — W — Request reviewers for a pull request — `pkg/github/pullrequests_granular.go:284` *(flag `pull_requests_granular` only)*
- `create_pull_request_review` — W — Create (and optionally submit) a review on a PR — `pkg/github/pullrequests_granular.go:379` *(flag `pull_requests_granular` only)*
- `submit_pending_pull_request_review` — W — Submit a pending PR review — `pkg/github/pullrequests_granular.go:448` *(flag `pull_requests_granular` only)*
- `delete_pending_pull_request_review` — W — Delete a pending PR review — `pkg/github/pullrequests_granular.go:512` *(flag `pull_requests_granular` only)*
- `add_pull_request_review_comment` — W — Add a review comment to the current user's pending review — `pkg/github/pullrequests_granular.go:567` *(flag `pull_requests_granular` only)*
- `resolve_review_thread` — W — Resolve a review thread on a PR — `pkg/github/pullrequests_granular.go:678` *(flag `pull_requests_granular` only)*
- `unresolve_review_thread` — W — Unresolve a previously resolved review thread — `pkg/github/pullrequests_granular.go:722` *(flag `pull_requests_granular` only)*
- `add_pull_request_review_comment_reaction` — W — Add a reaction to a PR review comment — `pkg/github/pullrequests_granular.go:766` *(flag `pull_requests_granular` only)*

### `users` — DEFAULT ON
- `search_users` — R — Find GitHub users by username, real name, or other profile information — `pkg/github/search.go:469`

### `copilot` — DEFAULT ON
- `assign_copilot_to_issue` — W — Assign Copilot to a specific issue — `pkg/github/copilot.go:168`
- `request_copilot_review` — W — Request a GitHub Copilot code review for a pull request — `pkg/github/copilot.go:860`

### `orgs` — opt-in
- `search_orgs` — R — Find GitHub organizations by name, location, or other organization metadata — `pkg/github/search.go:511`

### `git` — opt-in
- `get_repository_tree` — R — Get the tree structure (files and directories) at a specific ref or SHA — `pkg/github/git.go:47`

### `actions` — opt-in
- `actions_list` — R — List workflows / workflow runs / jobs / run artifacts — `pkg/github/actions.go:205`
- `actions_get` — R — Get a workflow, run, job, artifact download URL, run usage, or run-logs URL by ID — `pkg/github/actions.go:412`
- `get_job_logs` — R — Download logs for a specific job, or all failed job logs for a run — `pkg/github/actions.go:651`
- `actions_run_trigger` — W — Run / re-run / re-run-failed / cancel a workflow run; delete run logs — `pkg/github/actions.go:534`

### `code_security` — opt-in
- `get_code_scanning_alert` — R — Get details of a specific code scanning alert — `pkg/github/code_scanning.go:24`
- `list_code_scanning_alerts` — R — List code scanning alerts in a repository — `pkg/github/code_scanning.go:141`

### `code_quality` — opt-in
- `get_code_quality_finding` — R — Get details of a specific code quality finding — `pkg/github/code_quality.go:24`

### `secret_protection` — opt-in
- `get_secret_scanning_alert` — R — Get details of a specific secret scanning alert — `pkg/github/secret_scanning.go:25`
- `list_secret_scanning_alerts` — R — List secret scanning alerts in a repository — `pkg/github/secret_scanning.go:137`

### `dependabot` — opt-in
- `get_dependabot_alert` — R — Get details of a specific dependabot alert — `pkg/github/dependabot.go:25`
- `list_dependabot_alerts` — R — List dependabot alerts in a repository — `pkg/github/dependabot.go:134`

### `security_advisories` — opt-in
- `list_global_security_advisories` — R — List global security advisories from GitHub — `pkg/github/security_advisories.go:25`
- `get_global_security_advisory` — R — Get a global security advisory — `pkg/github/security_advisories.go:335`
- `list_repository_security_advisories` — R — List repository security advisories for a repository — `pkg/github/security_advisories.go:221`
- `list_org_repository_security_advisories` — R — List repository security advisories for an organization — `pkg/github/security_advisories.go:396`

### `notifications` — opt-in
- `list_notifications` — R — List GitHub notifications for the authenticated user — `pkg/github/notifications.go:33`
- `get_notification_details` — R — Get detailed information for a specific notification — `pkg/github/notifications.go:338`
- `dismiss_notification` — W — Mark a notification as read or done — `pkg/github/notifications.go:170`
- `mark_all_notifications_read` — W — Mark all notifications as read — `pkg/github/notifications.go:246`
- `manage_notification_subscription` — W — Ignore / watch / delete a notification thread subscription — `pkg/github/notifications.go:413`
- `manage_repository_notification_subscription` — W — Ignore / watch / delete a repository notification subscription — `pkg/github/notifications.go:509`

### `discussions` — opt-in
- `list_discussions` — R — List discussions for a repository or organisation — `pkg/github/discussions.go:132`
- `get_discussion` — R — Get a specific discussion by ID — `pkg/github/discussions.go:289`
- `get_discussion_comments` — R — Get comments from a discussion — `pkg/github/discussions.go:397`
- `list_discussion_categories` — R — List discussion categories (id + name) for a repo or org — `pkg/github/discussions.go:1008`
- `discussion_comment_write` — W — Write operations for discussion comments — `pkg/github/discussions.go:605`

### `gists` — opt-in
- `list_gists` — R — List gists for a user — `pkg/github/gists.go:26`
- `get_gist` — R — Get gist content by gist ID — `pkg/github/gists.go:115`
- `create_gist` — W — Create a new gist — `pkg/github/gists.go:175`
- `update_gist` — W — Update an existing gist — `pkg/github/gists.go:277`

### `projects` — opt-in
- `projects_list` — R — List Projects resources (projects, fields, items) — `pkg/github/projects.go:161`
- `projects_get` — R — Get details about specific Projects resources — `pkg/github/projects.go:317`
- `projects_write` — W — Create projects; add/update/delete items; bulk updates — `pkg/github/projects.go:578`

### `labels` — opt-in
- `get_label` — R — Get a specific label from a repository (same tool object as the `issues` copy, re-tagged) — `pkg/github/labels.go:125` (definition at `pkg/github/labels.go:30`)
- `list_label` — R — List labels from a repository, ordered by issue count desc — `pkg/github/labels.go:136`
- `label_write` — W — Create / update / delete repository labels — `pkg/github/labels.go:234`

### `stargazers` — opt-in
- `list_starred_repositories` — R — List starred repositories — `pkg/github/repositories.go:2077`
- `star_repository` — W — Star a GitHub repository — `pkg/github/repositories.go:2221`
- `unstar_repository` — W — Unstar a GitHub repository — `pkg/github/repositories.go:2287`

### `copilot_issue_intents` — opt-in
- `assign_copilot_to_issue_with_intent` — W — Assign Copilot with intent metadata (rationale, confidence, is_suggestion) — `pkg/github/copilot.go:517`

### How read-only mode is enforced

Read-only-ness is a *property of each tool's MCP annotation*, not a separate registry:

```go
// pkg/inventory/server_tool.go:95
func (st *ServerTool) IsReadOnly() bool {
	return st.Tool.Annotations != nil && st.Tool.Annotations.ReadOnlyHint
}
```

The inventory filter drops non-read-only tools before registration:

```go
// pkg/inventory/filters.go:94
// 2. Check read-only filter (applies to all tools)
if r.readOnly && !tool.IsReadOnly() {
    return false
}
```

Set via `--read-only` / `GITHUB_READ_ONLY` (`cmd/github-mcp-server/main.go:238`, `:274`), threaded through `MCPServerConfig.ReadOnly` (`pkg/github/server.go:41`) → `WithReadOnly(cfg.ReadOnly)` (`internal/ghmcp/server.go:175`), or per-request via the `X-MCP-Readonly` HTTP header (`pkg/http/headers/headers.go:35`). Read-only mode also suppresses the write-form MCP App UI resources (`pkg/github/ui_resources.go:49`).

Note: read-only is a *registration-time* filter (tools disappear from `tools/list`), not a runtime handler guard.

## Key tools (12 most important for a DevOps agent)

Params are exact from the published snapshots in `pkg/github/__toolsnaps__/*.snap`, cross-checked against the Go schema literals. `page`/`perPage` come from `WithPagination` (`pkg/github/params.go:347`) unless noted.

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `issue_read` | `method`: string enum `get`\|`get_comments`\|`get_sub_issues`\|`get_parent`\|`get_labels` — required; `owner`: string — required; `repo`: string — required; `issue_number`: number — required; `page`: number (min 1) — optional; `perPage`: number (1–100) — optional | Text content holding JSON. `get` → `MinimalIssue` (`pkg/github/minimal_types.go:537`: `number,title,body,state,state_reason,draft,locked,html_url,user{MinimalUser},author_association,labels[],assignees[],milestone,comments,reactions,created_at,updated_at,closed_at,closed_by,issue_type,field_values[],has_parent,has_children,parent{MinimalIssueRef},sub_issues_summary,closed_by_pull_requests{total_count,references[≤5]}`; `issue_field_values` is explicitly nulled at `pkg/github/issues.go:757`). `get_comments` → `[]MinimalIssueComment` (`:619`). `get_parent` → `MinimalIssueRef` (`:596`). | `pkg/github/issues.go:645` (handler dispatch `:694`; `GetIssue` `:715`; `GetIssueComments` `:833`) |
| `issue_write` | `method`: string enum `create`\|`update` — required; `owner`: string — required; `repo`: string — required; `issue_number`: number — optional; `title`: string — optional; `body`: string — optional; `assignees`: string[] — optional; `labels`: string[] — optional; `milestone`: number — optional; `state`: string enum `open`\|`closed` — optional; `state_reason`: enum `completed`\|`not_planned`\|`duplicate` — optional; `duplicate_of`: number — optional; `type`: string\|null — optional; `issue_fields`: array of `{field_name: string (req), value: string\|number\|bool, field_option_name: string, delete: true}` — optional | `MinimalResponse{"id": string, "url": string}` only — deliberately not the created issue (`pkg/github/minimal_types.go:406`). Create path `pkg/github/issues.go:2490`-`:2500`; update path `pkg/github/issues.go:2716`-`:2724`. Also carries `_meta.ui.resourceUri: "ui://github-mcp-server/issue-write"` when MCP Apps is on. | `pkg/github/issues.go:2180` |
| `list_issues` | `owner`: string — required; `repo`: string — required; `state`: enum `OPEN`\|`CLOSED` — optional; `labels`: string[] — optional; `orderBy`: enum `CREATED_AT`\|`UPDATED_AT`\|`COMMENTS` — optional; `direction`: enum `ASC`\|`DESC` — optional; `since`: string (ISO 8601) — optional; `field_filters`: array of `{field_name, value}` (both req) — optional; `fields`: string[] from `number,title,body,state,user,labels,comments,created_at,updated_at,field_values` — optional; `perPage`: number (1–100) — optional; `after`: string cursor — optional. **No `page`** (cursor-only, `WithCursorPagination` `pkg/github/params.go:388`) | `MinimalIssuesResponse{"issues": []MinimalIssue, "totalCount": int, "pageInfo": {hasNextPage,hasPreviousPage,startCursor,endCursor}}` (`pkg/github/minimal_types.go:612`, `:1788`). With `fields`, `issues` becomes `[]map[string]any` holding only the selected keys while `totalCount`/`pageInfo` are preserved (`pkg/github/issues.go:3021`-`:3030`). GraphQL-backed. | `pkg/github/issues.go:2827` |
| `search_issues` | `query`: string — required; `owner`: string — optional; `repo`: string — optional; `sort`: enum `comments`\|`reactions`\|`reactions-+1`\|`reactions--1`\|`reactions-smile`\|`reactions-thinking_face`\|`reactions-heart`\|`reactions-tada`\|`interactions`\|`created`\|`updated` — optional; `order`: enum `asc`\|`desc` — optional; `fields`: string[] (curated enum, `pkg/github/minimal_types.go:73`) — optional; `page`, `perPage` — optional | `SearchIssuesResponse{"total_count": *int, "incomplete_results": *bool, "items": []SearchIssueResult}` where each item is the **full `github.Issue` JSON** with `issue_field_values` deleted and normalized `field_values` added (`pkg/github/issues.go:1799`-`:1830`). Not a Minimal type. | `pkg/github/issues.go:1693` |
| `pull_request_read` | `method`: string enum `get`\|`get_diff`\|`get_status`\|`get_files`\|`get_commits`\|`get_review_comments`\|`get_reviews`\|`get_comments`\|`get_check_runs` — required; `owner`: string — required; `repo`: string — required; `pullNumber`: number — required; `page`: number — optional; `perPage`: number (1–100) — optional; `after`: string cursor (only used by `get_review_comments`) — optional | Per method: `get` → `MinimalPullRequest` (`pkg/github/minimal_types.go:661`) via `pkg/github/pullrequests.go:204`. `get_diff` → **raw unified diff text**, not JSON (`pkg/github/pullrequests.go:269`). `get_status` → raw `github.CombinedStatus` JSON (`:310`). `get_files` → `[]MinimalPRFile` (`:249`). `get_commits` → `[]MinimalPullRequestCommit` (`:260`). `get_review_comments` → `MinimalReviewThreadsResponse{review_threads:[{id,is_resolved,is_outdated,is_collapsed,comments:[{body,path,line,author,created_at,updated_at,html_url}],total_count}],totalCount,pageInfo}` (`pkg/github/minimal_types.go:1817`; handler `pkg/github/pullrequests.go:554`). `get_reviews` → `[]MinimalPullRequestReview` (`:713`; handler `pkg/github/pullrequests.go:611`). `get_check_runs` → `MinimalCheckRunsResult{total_count, check_runs:[]MinimalCheckRun}` (`pkg/github/minimal_types.go:2068`; handler `pkg/github/pullrequests.go:375`). | `pkg/github/pullrequests.go:74` |
| `list_pull_requests` | `owner`: string — required; `repo`: string — required; `state`: enum `open`\|`closed`\|`all` — optional; `head`: string — optional; `base`: string — optional; `sort`: enum `created`\|`updated`\|`popularity`\|`long-running` — optional; `direction`: enum `asc`\|`desc` — optional; `fields`: string[] from the `MinimalPullRequest` key list (`pkg/github/minimal_types.go:44`) — optional; `page`, `perPage` — optional | Bare JSON array `[]MinimalPullRequest` (`pkg/github/minimal_types.go:661`) — **no envelope, no pageInfo**. With `fields`, `[]map[string]any` of selected keys (`pkg/github/pullrequests.go:1466`-`:1487`). | `pkg/github/pullrequests.go:1372` |
| `pull_request_review_write` | `method`: string enum `create`\|`submit_pending`\|`delete_pending`\|`resolve_thread`\|`unresolve_thread` — required; `owner`: string — required; `repo`: string — required; `pullNumber`: number — required; `body`: string — optional; `event`: enum `APPROVE`\|`REQUEST_CHANGES`\|`COMMENT` — optional; `commitID`: string — optional; `threadId`: string — optional | Plain text strings, not JSON: `"pending pull request created"` when `event` is empty, else `"pull request review submitted successfully"` (`pkg/github/pullrequests.go:1938`-`:1942`). Comment on source: "we're not leaking API implementation details to the LLM". | `pkg/github/pullrequests.go:1834` |
| `actions_list` | `method`: string enum `list_workflows`\|`list_workflow_runs`\|`list_workflow_jobs`\|`list_workflow_run_artifacts` — required; `owner`: string — required; `repo`: string — required; `resource_id`: string — optional (workflow id/filename or run id); `workflow_runs_filter`: object (`actor`,`branch`,`event`,`status`) — optional; `workflow_jobs_filter`: object (`filter`) — optional; `page`: number — optional; `per_page`: number — optional (**note `per_page`, snake case, not `perPage`**) | `list_workflows` → raw `github.Workflows` JSON, full fidelity (`pkg/github/actions.go:837`). `list_workflow_runs` → `MinimalWorkflowRunsResult{total_count, workflow_runs:[]MinimalWorkflowRun}` (`pkg/github/minimal_types.go:359`; handler `pkg/github/actions.go:887`). `list_workflow_jobs` → `{"jobs": MinimalWorkflowJobsResult{total_count, jobs:[]MinimalWorkflowJob{...steps[]...}}}` (`pkg/github/minimal_types.go:398`; handler `pkg/github/actions.go:921`). `list_workflow_run_artifacts` → raw `github.ArtifactList` JSON (`pkg/github/actions.go:946`). | `pkg/github/actions.go:205` |
| `actions_get` | `method`: string enum `get_workflow`\|`get_workflow_run`\|`get_workflow_job`\|`download_workflow_run_artifact`\|`get_workflow_run_usage`\|`get_workflow_run_logs_url` — required; `owner`: string — required; `repo`: string — required; `resource_id`: string — required | Raw go-github structs marshalled directly (no Minimal types): `github.Workflow` (`pkg/github/actions.go:786`), `github.WorkflowRun` (`:799`), `github.WorkflowJob` (`:812`). Artifact/logs methods return a JSON object containing the redirect download URL. | `pkg/github/actions.go:412` |
| `get_job_logs` | `owner`: string — required; `repo`: string — required; `job_id`: number — optional; `run_id`: number — optional; `failed_only`: boolean — optional; `return_content`: boolean — optional; `tail_lines`: number (default `500`) — optional. Validation: `run_id` required when `failed_only`; `job_id` required otherwise (`pkg/github/actions.go:738`-`:743`) | Single job → `{"job_id":int, "logs_content":string, "message":"Job logs content retrieved successfully", "original_length":int}` when `return_content`, else `{"job_id":int,"logs_url":string,"message":"Job logs are available for download","note":"..."}` (`pkg/github/actions.go:155`-`:163`). `failed_only` → `{"message":"Retrieved logs for N failed jobs","run_id":int,"total_jobs":int,"failed_jobs":int,"logs":[<per-job objects, each possibly {"job_id","job_name","error"}>],"return_format":{"content":bool,"urls":bool}}` (`pkg/github/actions.go:96`-`:104`). | `pkg/github/actions.go:651` |
| `list_code_scanning_alerts` | `owner`: string — required; `repo`: string — required; `ref`: string — optional; `state`: enum `open`\|`closed`\|`dismissed`\|`fixed` — optional; `severity`: enum `critical`\|`high`\|`medium`\|`low`\|`warning`\|`note`\|`error` — optional; `tool_name`: string — optional; `page`, `perPage` — optional | Bare JSON array of **full `[]*github.Alert`** from go-github v89 — no minimization, no envelope (`pkg/github/code_scanning.go:212`). Result always carries the static IFC label `LabelSecurityAlert()` (`pkg/github/code_scanning.go:219`). Requires OAuth scope `security_events` (`pkg/github/code_scanning.go:149`). | `pkg/github/code_scanning.go:141` |
| `get_file_contents` | `owner`: string — required; `repo`: string — required; `path`: string — optional (defaults to repo root); `ref`: string — optional; `sha`: string — optional; `fields`: string[] from `type,name,path,size,sha,url,git_url,html_url,download_url` (directory listings only) — optional | Not plain JSON. **File < 1 MB, text** → `NewToolResultResource` = `[TextContent("successfully downloaded text file (SHA: ...)"), EmbeddedResource{ResourceContents{URI,Text,MIMEType}}]` (`pkg/github/repositories.go:905`-`:910`). **Binary** → same but `Blob` base64 (`:917`-`:920`). **Empty file** → text resource with `""` (`:855`-`:866`). **≥ 1 MB** → `NewToolResultResourceLink` with `{URI, Name, Title, Size}` and no content (`:871`-`:881`). **Directory** → text content holding JSON array of `github.RepositoryContent` entries, optionally field-filtered (`:920`-`:938`). Helpers at `pkg/utils/result.go:36` / `:49`. | `pkg/github/repositories.go:759` |

## Resources

Five `mcp.ResourceTemplate` registrations, all in the `repos` toolset, listed by `AllResources` (`pkg/github/resources.go:10`):

- `repository_content` — `repo://{owner}/{repo}/contents{/path*}` — `pkg/github/repository_resource.go:38` (template `:26`)
- `repository_content_branch` — `repo://{owner}/{repo}/refs/heads/{branch}/contents{/path*}` — `pkg/github/repository_resource.go:52` (template `:27`)
- `repository_content_commit` — `repo://{owner}/{repo}/sha/{sha}/contents{/path*}` — `pkg/github/repository_resource.go:66` (template `:28`)
- `repository_content_tag` — `repo://{owner}/{repo}/refs/tags/{tag}/contents{/path*}` — `pkg/github/repository_resource.go:80` (template `:29`)
- `repository_content_pr` — `repo://{owner}/{repo}/refs/pull/{prNumber}/head/contents{/path*}` — `pkg/github/repository_resource.go:94` (template `:30`)

Shared handler: `repositoryResourceContentsHandlerFunc` → `RepositoryResourceContentsHandler` (`pkg/github/repository_resource.go:102`, `:110`). Directories are rejected: `"directories are not supported: %s"` (`pkg/github/repository_resource.go:185`).

Additionally, four **static** (non-template) MCP App UI resources are registered outside the inventory, only when the embedded UI assets are present (`pkg/github/server.go:135`; guard `UIAssetsAvailable()`):
- `get_me_ui` (`ui://github-mcp-server/get-me`) — `pkg/github/ui_resources.go:21`
- `issue_write_ui` — `pkg/github/ui_resources.go:57` (skipped in read-only, `:49`)
- `pr_write_ui` — `pkg/github/ui_resources.go:87`
- `pr_edit_ui` — `pkg/github/ui_resources.go:114`

Resource-URI completions are served by `CompletionsHandler` (`pkg/github/server.go:90`, `pkg/github/repository_resource_completions.go`).

## Prompts

Two, via `AllPrompts` (`pkg/github/prompts.go:10`):
- `AssignCodingAgent` — args: `repo` (required, `owner/repo`) — issues toolset — `pkg/github/copilot.go:923` (name literal `pkg/github/copilot.go:928`)
- `issue_to_fix_workflow` — args: `owner`, `repo`, `title`, `description`, `labels`, `assignees` — `pkg/github/workflow_prompts.go:17`

Prompt capability is advertised explicitly without `listChanged` (`pkg/github/server.go:98`-`:101`).

## Auth model

Three mutually exclusive mechanisms, all resolved in `cmd/github-mcp-server/main.go:42`-`:70`. Env vars use viper prefix `github` with `-`→`_` replacement (`cmd/github-mcp-server/main.go:303`-`:305`), so flag `--foo-bar` ⇒ `GITHUB_FOO_BAR`.

1. **PAT** — `GITHUB_PERSONAL_ACCESS_TOKEN` (`cmd/github-mcp-server/main.go:42`, error message at `:63`). This is the documented path for the local/stdio server (`docs/policies-and-governance.md`, "Local GitHub MCP Server … Requires Personal Access Tokens (PATs)").
2. **GitHub App (installation tokens)** — `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, and `GITHUB_APP_PRIVATE_KEY_PATH` (preferred) or `GITHUB_APP_PRIVATE_KEY` (`cmd/github-mcp-server/main.go:43`-`:46`, `:259`, `:353`). Mutually exclusive with PAT (`:66`) and with OAuth (`:69`).
3. **OAuth interactive login** — `--oauth-client-id` / `--oauth-client-secret` / `--oauth-scopes`, with a build-time baked-in client for github.com (`cmd/github-mcp-server/main.go:48`-`:61`, flags `:252`-`:255`). Requested scopes default to `ghoauth.SupportedScopes`; a narrower `--oauth-scopes` both narrows the grant **and hides tools requiring other scopes** (`cmd/github-mcp-server/main.go:134`-`:140`).

Token transport: `Authorization` bearer via `transport.BearerAuthTransport` (`internal/ghmcp/server.go:66`, `:76`, `:96`). In HTTP mode the token arrives per-request in the `Authorization` header (`pkg/http/headers/headers.go:5`).

**Scopes needed** are declared per tool as `[]scopes.Scope` (third argument of `NewTool`, `pkg/github/dependencies.go:230`-`:236`), then expanded through a hierarchy (`pkg/scopes/scopes.go:64`-`:72`: `repo` ⊃ `public_repo`, `security_events`; `admin:org` ⊃ `write:org` ⊃ `read:org`; `project` ⊃ `read:project`; `user` ⊃ `read:user`, `user:email`). Examples: `repo` for issues/PRs/actions/labels (`pkg/github/issues.go:653`, `pkg/github/actions.go:583`), `security_events` for code scanning (`pkg/github/code_scanning.go:149`). `cmd/github-mcp-server/list_scopes.go` prints the full per-tool scope table. When token scopes are known, `CreateToolScopeFilter` hides tools whose scopes are missing — with an exception that read-only tools needing only `repo`/`public_repo` stay visible because they work on public repos (`pkg/github/scope_filter.go:55`-`:60`).

## Pagination

Three schema mixins, all in `pkg/github/params.go`:

- `WithPagination(schema)` — REST page pagination. Adds `page`: number, `minimum: 1`; `perPage`: number, `minimum: 1`, `maximum: 100` (`pkg/github/params.go:347`-`:361`).
- `WithUnifiedPagination(schema)` — same two plus `after`: string, "Use the endCursor from the previous page's PageInfo for GraphQL APIs" (`pkg/github/params.go:365`-`:386`).
- `WithCursorPagination(schema)` — `perPage` + `after` only, **no `page`** (`pkg/github/params.go:388`-`:403`).

**Defaults are applied server-side, not in the schema**: `page` defaults to `1`, `perPage` defaults to `30` (`pkg/github/params.go:416`-`:433`; cursor variant `:436`-`:449`). Maximum `perPage` is 100, enforced twice — by `maximum: 100` in the JSON schema and by an explicit guard in `ToGraphQLParams`: `"perPage value %d exceeds maximum of 100"` and `"perPage value %d cannot be negative"` (`pkg/github/params.go:476`-`:479`).

REST↔GraphQL bridging: `PaginationParams.ToGraphQLParams()` converts `perPage` → `first` (int32) and `after` → cursor; `page` is **dropped** for GraphQL calls — `after` takes precedence (`pkg/github/params.go:498`-`:511`). GraphQL responses carry `MinimalPageInfo{hasNextPage,hasPreviousPage,startCursor,endCursor}` (`pkg/github/minimal_types.go:1788`); some REST list tools return a `pageInfo{hasNextPage,hasPreviousPage,nextCursor,prevCursor}` built from `resp.After`/`resp.Before` (`pkg/github/params.go:459`-`:471`).

Exception: the Actions tools use **`per_page` (snake case)**, not `perPage` — see `pkg/github/__toolsnaps__/actions_list.snap` and `pkg/github/actions.go:205`.

## Rate limits

There is **no client-side retry or backoff** anywhere in the codebase — no retry loop, no exponential backoff, no `Retry-After` sleeping. Rate limits are surfaced to the model as tool errors only:

```go
// pkg/errors/error.go:165-178
var rateLimitErr *github.RateLimitError
if stderrors.As(err, &rateLimitErr) {
    resetTime := rateLimitErr.Rate.Reset.Time
    if !resetTime.IsZero() {
        retryIn := time.Until(resetTime).Round(time.Second)
        if retryIn > 0 {
            return utils.NewToolResultError(fmt.Sprintf(
                "%s: GitHub API rate limit exceeded. Retry after %v.", message, retryIn))
        }
    }
    return utils.NewToolResultError(fmt.Sprintf(
        "%s: GitHub API rate limit exceeded. Wait before retrying.", message))
}
```

Secondary ("abuse") rate limits get the same treatment with `github.AbuseRateLimitError` and `RetryAfter`: `"%s: GitHub secondary rate limit exceeded. Retry after %v."` / `"… Wait before retrying."` (`pkg/errors/error.go:180`-`:193`). Both paths also stash the error in request context for middleware/observability (`pkg/errors/error.go:159`-`:163`). `docs/policies-and-governance.md` notes only that the server is "Subject to GitHub API rate limits based on authentication method".

## Error shapes

Every failure reaches the model as a `*mcp.CallToolResult` with `IsError: true` and a **single plain-text `TextContent`** — never structured JSON error objects (except the one case noted below). The two constructors:

```go
// pkg/utils/result.go:15
func NewToolResultError(message string) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: message}},
		IsError: true,
	}
}

// pkg/utils/result.go:26
func NewToolResultErrorFromErr(message string, err error) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: message + ": " + err.Error()}},
		IsError: true,
	}
}
```

So the literal wire format for an upstream API failure is `"<handler message>: <go error string>"`, e.g. `"failed to get GitHub client: ..."`, `"failed to update issue: ..."`. Upstream errors go through `ghErrors.NewGitHubAPIErrorResponse(ctx, message, resp, err)` (`pkg/errors/error.go:159`), which records the error in context and then delegates to `NewToolResultErrorFromErr` — except for the rate-limit branches above. GraphQL failures use `NewGitHubGraphQLErrorResponse` (`pkg/errors/error.go:197`) and raw-API failures `NewGitHubRawAPIErrorResponse` (`pkg/errors/error.go:206`). Non-2xx responses with `err == nil` are synthesized: `"unexpected status %d: %s"` with the body (`pkg/errors/error.go:216`-`:221`). Parameter validation errors return the raw validation string with `NewToolResultError` (pattern repeated at e.g. `pkg/github/issues.go:657`).

The one structured exception is Projects name-resolution, which returns a **JSON body as the error text** so an agent can self-correct: `StructuredResolutionError{"error": kind, "name", "field", "candidates", "hint"}` with kinds `field_not_found`, `field_ambiguous`, `option_not_found`, `option_ambiguous`, `item_not_in_project`, `wrong_field_type` (`pkg/errors/error.go:224`-`:257`).

MCP App form deferral is also signalled as an error so agents stop: `IsError: true` plus `StructuredContent: {"status":"awaiting_user_submission","reason":"An interactive form is being shown to the user. The operation has not been performed."}` (`pkg/utils/result.go:63`-`:81`).

**Truncation / "too many results"** is represented several distinct ways:
- **`MinimalResponse{id,url}`** — every write tool returns only an id + URL rather than the created object, by design: "Success is implicit in the HTTP response status, and all other information can be derived from the URL or fetched separately" (`pkg/github/minimal_types.go:403`-`:409`).
- **`Minimal*` projection types** — ~30 trimmed structs replace the go-github models on list/read paths (`pkg/github/minimal_types.go:149` onward).
- **`fields` parameter + `filterFields`/`filterEachField`** — per-tool opt-in field selection with a fixed enum per tool, applied post-marshal (`pkg/github/minimal_types.go:93`-`:143`; enums at `:22`-`:90`). Usage is telemetered via `recordFieldsUsageFor` (`pkg/github/fields_telemetry.go`).
- **Log content window** — `--content-window-size`, default **5000** lines (`cmd/github-mcp-server/main.go:243`). `get_job_logs` reads the tail through a ring buffer sized `min(tail_lines, contentWindowSize)` (`pkg/github/actions.go:182`) and reports the pre-truncation line count as `original_length` (`pkg/github/actions.go:157`).
- **Explicit `truncated` flags** — `TreeResponse.Truncated` for `get_repository_tree` (`pkg/github/git.go:33`); blame ranges capped at 1000 with `truncated` + `total_ranges` (`pkg/github/repositories.go:2419`, `:2476`); `ui_get` caps at `uiGetMaxPages = 10` pages and sets `has_more` (`pkg/github/ui_tools.go:28`-`:31`).
- **Capped embedded lists** — `MinimalClosingPullRequests.References` is capped at 5 while `total_count` stays authoritative (`pkg/github/minimal_types.go:576`-`:583`).
- **Large files** — `get_file_contents` returns a `ResourceLink` with no body for files ≥ 1 MB (`pkg/github/repositories.go:870`-`:881`).

## Not exposed (E3)

Deliberate omissions and gates found in source:

1. **No repository/branch/issue deletion, no repo administration.** There is no `delete_repository`, `delete_branch`, `delete_issue`, branch-protection, webhook, environment, deploy-key, or repo-settings tool anywhere in `AllTools` (`pkg/github/tools.go:212`-`:377`). `delete_file` and `delete_pending_pull_request_review` / `delete_project_item` are the only DELETE-shaped operations exposed.
2. **No Actions secrets / variables / self-hosted runners / OIDC.** `actions_run_trigger` exposes exactly five methods — `run_workflow`, `rerun_workflow_run`, `rerun_failed_jobs`, `cancel_workflow_run`, `delete_workflow_run_logs` (`pkg/github/actions.go:548`-`:554`). Nothing for `repos/{o}/{r}/actions/secrets`, `/variables`, `/runners`, `/permissions`.
3. **Security alerts are read-only.** Code scanning, Dependabot, secret scanning, and code quality expose only `get_*` / `list_*` (`pkg/github/code_scanning.go:24`,`:141`; `pkg/github/dependabot.go:25`,`:134`; `pkg/github/secret_scanning.go:25`,`:137`; `pkg/github/code_quality.go:24`). GitHub's alert-update endpoints (dismiss/reopen an alert, `PATCH .../alerts/{n}`) are not surfaced. Security advisories are likewise list/get only — no advisory create/publish (`pkg/github/security_advisories.go`).
4. **No deployments, releases-write, packages, or Pages.** Releases are read-only (`list_releases`, `get_latest_release`, `get_release_by_tag`); there is no `create_release`/`upload_asset`. `pkg/scopes/scopes.go:56`-`:60` defines `read:packages`/`write:packages` constants but no tool requests them.
5. **Toolsets that exist only on the hosted remote server** are documented in this repo but ship zero tools here: `copilot_spaces` and `github_support_docs_search` — "Remote-only toolsets — these are only available in the remote MCP server but are documented here for consistency" (`pkg/github/tools.go:169`-`:181`).
6. **Feature-flag-gated tools are off by default**: `get_file_blame` (`file_blame`), `issue_dependency_read`/`issue_dependency_write` (`issue_dependencies`), `find_duplicate` (`duplicate_detection`), `ui_get` (`remote_mcp_ui_apps`), and all 26 granular issue/PR tools (`issues_granular`, `pull_requests_granular`). Only flags in `AllowedFeatureFlags` can be enabled by users; unknown flags are silently dropped (`pkg/github/feature_flags.go:41`-`:51`, `:83`-`:92`). `duplicate_detection` is explicitly excluded from insiders mode "so duplicate detection is only ever an explicit opt-in" (`pkg/github/feature_flags.go:29`-`:34`, `InsidersFeatureFlags` at `:56`-`:62`).
7. **Lockdown mode withholds content the model would otherwise see.** With `--lockdown-mode`, issues/PRs/comments authored by users who are not "safe content sources" for the repo are replaced by `"access to issue details is restricted by lockdown mode"` / `"access to pull request is restricted by lockdown mode"`, and it fails closed on a missing cache or lookup error (`pkg/github/lockdown.go:14`-`:37`; comment filtering at `pkg/github/issues.go:868`-`:886`; PR review-thread comment filtering at `pkg/github/pullrequests.go:539`; PR review filtering at `pkg/github/pullrequests.go:595`).
8. **Host-capability gap acknowledged in a source comment, not gated:** `request_copilot_review` "will not work on GHES where this feature is unsupported. In future, we should not expose this tool if the configured host does not support it" (`pkg/github/copilot.go:840`-`:841`).
9. **Directory reads via MCP resources are refused** — `"directories are not supported: %s"` (`pkg/github/repository_resource.go:185`); callers must use `get_file_contents` instead.
10. **Renamed/removed tools are aliases, not real tools.** 26 legacy names (`list_workflows`, `get_workflow_run`, `run_workflow`, `list_projects`, `add_project_item`, …) resolve to the consolidated tools at build time and are not registered separately (`pkg/github/deprecated_tool_aliases.go:12`-`:41`).

## Notes for mocking

- **Tool count and names:** 116 distinct names; `get_label` is the only name registered twice (two toolsets, identical schema). The 116 files in `pkg/github/__toolsnaps__/` are byte-exact published schemas — use them as fixtures. Three carry a `_ff_<flag>` suffix (`find_duplicate_ff_duplicate_detection.snap`, `issue_dependency_read_ff_issue_dependencies.snap`, `issue_dependency_write_ff_issue_dependencies.snap`), meaning the tool only appears with that flag on.
- **Default surface is much smaller than "all".** With no toolset selection, only `context`, `repos`, `issues`, `pull_requests`, `users`, `copilot` are on (`pkg/github/tools.go:36`,`:43`,`:54`,`:61`,`:68`,`:142`). A DevOps mock that needs `actions`, `code_security`, `dependabot`, or `secret_protection` must model those as explicitly enabled.
- **Consolidated "method" dispatch tools.** `issue_read`, `issue_write`, `pull_request_read`, `pull_request_review_write`, `actions_list`, `actions_get`, `actions_run_trigger`, `projects_list/get/write`, `label_write`, `discussion_comment_write`, `sub_issue_write`, `manage_*_subscription` all take a required `method` enum and return a *different shape per method*. Mock per-method, not per-tool. Unknown methods return `NewToolResultError("unknown method: <m>")` (e.g. `pkg/github/actions.go:522`).
- **Writes return almost nothing.** Model `MinimalResponse{"id": "<numeric id as string>", "url": "<html_url>"}` for issue/PR/file writes, and bare strings for `pull_request_review_write` (`"pending pull request created"` / `"pull request review submitted successfully"`). Do not return the created object.
- **Mixed minimization.** Some tools return trimmed `Minimal*` structs (`list_issues`, `list_pull_requests`, `list_workflow_runs`, `list_workflow_jobs`, `pull_request_read`), others return raw go-github v89 JSON verbatim (`list_code_scanning_alerts`, `list_dependabot_alerts`, `get_workflow`, `get_workflow_run`, `get_workflow_job`, `list_workflows`, `search_issues` items). A faithful mock must copy the right one per tool.
- **`pull_request_read` with `method: "get_diff"` returns raw unified diff text**, not JSON (`pkg/github/pullrequests.go:269`). `get_file_contents` returns an *embedded resource* or a *resource link*, not a JSON string. Both break naive "everything is JSON in TextContent" mocks.
- **Pagination is not uniform.** `page`+`perPage` (most REST tools), `perPage`+`after` cursor only (`list_issues`, `get_discussion_comments`), `page`+`perPage`+`after` (unified), and `page`+`per_page` snake case for the Actions tools. Defaults `page=1`, `perPage=30`, max 100.
- **Errors are text, never JSON.** `IsError: true` with one `TextContent` of the form `"<message>: <error>"`. Rate limits have their own literal strings including a computed `Retry after <duration>.` There is no retry/backoff, so a mock returning 403/429 will surface immediately to the model.
- **Envelope inconsistency matters.** `list_issues` wraps in `{issues, totalCount, pageInfo}`; `list_pull_requests` returns a bare array; `list_workflow_jobs` wraps in `{"jobs": {total_count, jobs: []}}`; `list_code_scanning_alerts` returns a bare array. Don't normalize.
- **Optional response transforms exist behind flags.** With `csv_output` on, every default-toolset tool whose name starts with `list_` has its JSON converted to CSV at response time (`pkg/github/csv_output.go:47`-`:66`). With `ifc_labels` on, results gain security labels in `_meta`. With `remote_mcp_ui_apps` on, `issue_write`/`create_pull_request`/`update_pull_request` gain `_meta.ui.resourceUri` and may return the `awaiting_user_submission` error instead of performing the write.
