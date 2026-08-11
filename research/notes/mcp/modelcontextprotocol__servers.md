# modelcontextprotocol/servers — reference MCP servers

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/modelcontextprotocol__servers` @ git commit `76d64c8` (2026-07-29), read 2026-08-11

**Scope:** the 7 reference servers, with language each.

| Server | Language | Package | Tools |
|---|---|---|---|
| `git` | Python | `mcp-server-git` | 12 |
| `filesystem` | TypeScript | `@modelcontextprotocol/server-filesystem` | 14 |
| `fetch` | Python | `mcp-server-fetch` | 1 |
| `memory` | TypeScript | `@modelcontextprotocol/server-memory` | 9 |
| `time` | Python | `mcp-server-time` | 2 |
| `sequentialthinking` | TypeScript | `@modelcontextprotocol/server-sequential-thinking` | 1 |
| `everything` | TypeScript | `@modelcontextprotocol/server-everything` | 19 (12 always + 7 capability-gated) |

The 7 servers are enumerated at `README.md:29-35`. Language/package mapping is confirmed at `CLAUDE.md:14-22`. The repo warns these are **reference implementations, not production-ready solutions** — `README.md:8-9`.

**Archived / removed servers:** `README.md:37-39` — "### Archived / The following reference servers are now archived and can be found at [servers-archived](https://github.com/modelcontextprotocol/servers-archived)." The named servers that no longer live in this repo, one per line:

| Server | README.md line | Note in source |
|---|---|---|
| AWS KB Retrieval | `README.md:41` | Bedrock Agent Runtime retrieval |
| Brave Search | `README.md:42` | "Has been replaced by the [official server](https://github.com/brave/brave-search-mcp-server)" |
| EverArt | `README.md:43` | AI image generation |
| GitHub | `README.md:44` | Repository management / GitHub API |
| GitLab | `README.md:45` | GitLab API |
| Google Drive | `README.md:46` | file access & search |
| Google Maps | `README.md:47` | location/directions/places |
| PostgreSQL | `README.md:48` | "Read-only database access with schema inspection" |
| Puppeteer | `README.md:49` | browser automation |
| Redis | `README.md:50` | key-value store |
| Sentry | `README.md:51` | issues from Sentry.io |
| Slack | `README.md:52` | "Now maintained by [Zencoder](https://github.com/zencoderai/slack-mcp-server)" |
| SQLite | `README.md:53` | database interaction / BI |

Notable inconsistency: the "Using an MCP Client" example config still references the archived `@modelcontextprotocol/server-github` (with `GITHUB_PERSONAL_ACCESS_TOKEN`) at `README.md:119-125` and archived `@modelcontextprotocol/server-postgres` at `README.md:126-129`, even though both are listed as archived 70 lines earlier. These npm package names no longer correspond to anything in this repo.

`ADDITIONAL.md` contains **no** archived-server list. It is exclusively "a curated collection of community-built frameworks and resources" (`ADDITIONAL.md:1-3`), split into "For servers" (`ADDITIONAL.md:7-32`), "For clients" (`ADDITIONAL.md:34-43`) and "Resources" (`ADDITIONAL.md:45-95`). No vendor server named above appears there.

Also relevant to contribution/scope: new server implementations are **not accepted** into this repo (`CLAUDE.md:107`), and users are pointed at the MCP Registry instead (`README.md:5-6`).

---

## `git` (Python) — 12 tools

**Entrypoint:** `src/git/src/mcp_server_git/server.py:308` (`async def serve(repository: Path | None)`); server object created at `src/git/src/mcp_server_git/server.py:319` (`Server("mcp-git")`). CLI wrapper: `src/git/src/mcp_server_git/__init__.py:7-21`.

Tool names are defined as a `str, Enum` at `src/git/src/mcp_server_git/server.py:96-109`, listed via `@server.list_tools()` at `src/git/src/mcp_server_git/server.py:321-456`, and dispatched by a `match name:` block at `src/git/src/mcp_server_git/server.py:497-598`.

### Tools

- `git_status` — R — shows the working tree status (`repo.git.status()`) — `src/git/src/mcp_server_git/server.py:97` (enum), `:324-334` (registration), `:111-112` (impl)
- `git_diff_unstaged` — R — changes in the working directory not yet staged — `:98`, `:335-345`, `:114-115`
- `git_diff_staged` — R — changes staged for commit (`--cached`) — `:99`, `:346-356`, `:117-118`
- `git_diff` — R — diff between branches or commits against an arbitrary target ref — `:100`, `:357-367`, `:120-126`
- `git_commit` — W — records changes to the repository via `repo.index.commit(message)` — `:101`, `:368-378`, `:128-130`
- `git_add` — W — stages file contents (`repo.git.add`) — `:102`, `:379-389`, `:132-153`
- `git_reset` — W (destructive) — unstages all staged changes (`repo.index.reset()`) — `:103`, `:390-400`, `:155-157`
- `git_log` — R — commit log, optionally date-filtered — `:104`, `:401-411`, `:159-198`
- `git_create_branch` — W — creates a branch from an optional base branch — `:105`, `:412-422`, `:200-212`
- `git_checkout` — W — switches branches — `:106`, `:423-433`, `:214-221`
- `git_show` — R — contents of a commit incl. patch — `:107`, `:434-444`, `:225-250`
- `git_branch` — R — lists local/remote/all branches with optional contains filters — `:109`, `:445-455`, `:273-305`

Read/write classification above matches the declared `ToolAnnotations`: `readOnlyHint=True` for status/diff_unstaged/diff_staged/diff/log/show/branch, `readOnlyHint=False` for commit/add/reset/create_branch/checkout. Only `git_reset` sets `destructiveHint=True` (`src/git/src/mcp_server_git/server.py:396`). Notably `git_checkout` is **not** marked destructive (`:428-431`) despite discarding nothing — but it does mutate the working tree.

### Key tools table

Every tool takes `repo_path` (string, required) — it is read unconditionally at `src/git/src/mcp_server_git/server.py:489` (`repo_path = Path(arguments["repo_path"])`) before any dispatch, so a call missing it raises `KeyError`.

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `git_status` | `repo_path`: str — required | `[TextContent(type="text", text="Repository status:\n<git status output>")]` | model `:23-24`; handler `:498-503` |
| `git_diff_unstaged` | `repo_path`: str — required; `context_lines`: int — optional, default `3` (`DEFAULT_CONTEXT_LINES`, `:21`) | `[TextContent(type="text", text="Unstaged changes:\n<unified diff>")]` | model `:26-28`; handler `:505-510` |
| `git_diff_staged` | `repo_path`: str — required; `context_lines`: int — optional, default `3` | `[TextContent(type="text", text="Staged changes:\n<unified diff>")]` | model `:30-32`; handler `:512-517` |
| `git_diff` | `repo_path`: str — required; `target`: str — required; `context_lines`: int — optional, default `3` | `[TextContent(type="text", text="Diff with <target>:\n<unified diff>")]` | model `:34-37`; handler `:519-524` |
| `git_commit` | `repo_path`: str — required; `message`: str — required | `[TextContent(type="text", text="Changes committed successfully with hash <hexsha>")]` | model `:39-41`; impl `:128-130`; handler `:526-531` |
| `git_add` | `repo_path`: str — required; `files`: list[str] — required | `[TextContent(type="text", text="Files staged successfully")]` | model `:43-45`; impl `:132-153`; handler `:533-538` |
| `git_reset` | `repo_path`: str — required | `[TextContent(type="text", text="All staged changes reset")]` | model `:47-48`; impl `:155-157`; handler `:540-545` |
| `git_log` | `repo_path`: str — required; `max_count`: int — optional, default `10`; `start_timestamp`: str\|null — optional; `end_timestamp`: str\|null — optional | `[TextContent(type="text", text="Commit history:\n" + "\n".join(entries))]` where each entry is `"Commit: …\nAuthor: …\nDate: …\nMessage: …\n"` | model `:50-60`; impl `:159-198`; handler `:548-558` |
| `git_create_branch` | `repo_path`: str — required; `branch_name`: str — required; `base_branch`: str\|null — optional (defaults to `repo.active_branch`, `:209`) | `[TextContent(type="text", text="Created branch '<branch_name>' from '<base.name>'")]` | model `:62-65`; impl `:200-212`; handler `:560-569` |
| `git_checkout` | `repo_path`: str — required; `branch_name`: str — required | `[TextContent(type="text", text="Switched to branch '<branch_name>'")]` | model `:67-69`; impl `:214-221`; handler `:571-576` |
| `git_show` | `repo_path`: str — required; `revision`: str — required | `[TextContent(type="text", text="Commit: …\nAuthor: …\nDate: …\nMessage: …\n" + per-file "\n--- a_path\n+++ b_path\n" + patch)]` | model `:71-73`; impl `:225-250`; handler `:578-583` |
| `git_branch` | `repo_path`: str — required; `branch_type`: str — **required** (`'local'`/`'remote'`/`'all'`); `contains`: str\|null — optional; `not_contains`: str\|null — optional | `[TextContent(type="text", text=<raw `git branch` output>)]` | model `:77-93`; impl `:273-305`; handler `:585-595` |

Quirk in `git_branch`: the pydantic model marks `branch_type` required (`Field(...)`, `:82-85`) but the handler supplies a default of `'local'` (`src/git/src/mcp_server_git/server.py:588`), so the declared JSON schema and runtime behaviour disagree.

### Auth / config / sandboxing

- **No auth of any kind.** No tokens, no headers, no credentials anywhere in the file. Transport is stdio only (`src/git/src/mcp_server_git/server.py:601`).
- Config surface is exactly two CLI flags: `--repository/-r` (a `Path`) and `-v/--verbose` (count) — `src/git/src/mcp_server_git/__init__.py:8-9`. Verbosity maps WARN → INFO → DEBUG at `src/git/src/mcp_server_git/__init__.py:14-18`.
- **Sandboxing is opt-in and weak.** `validate_repo_path(repo_path, allowed_repository)` returns immediately when no `--repository` was given: `if allowed_repository is None: return  # No restriction configured` (`src/git/src/mcp_server_git/server.py:254-255`). So started bare, the server will operate on **any** git repo path the model names.
- When `--repository` *is* set, both paths are `.resolve()`d (symlink-flattening) and checked with `resolved_repo.relative_to(resolved_allowed)` (`src/git/src/mcp_server_git/server.py:258-270`). Validation runs on every call before `git.Repo(repo_path)` (`:492-495`).
- Startup validates the repo exists, logging `f"{repository} is not a valid Git repository"` and returning without starting a server on `InvalidGitRepositoryError` (`src/git/src/mcp_server_git/server.py:311-317`).
- Argument-injection hardening ("defense in depth") is applied per tool: refs/branches/revisions/timestamps that start with `-` are rejected (`:123-124`, `:162-165`, `:202-205`, `:217-218`, `:228-229`, `:275-278`); `git_add` resolves each path under the working tree and passes `--` before filenames (`:136-152`).

### Notable behaviours for E6 (pagination / truncation / error text)

- **No pagination, no truncation.** `git_status`, `git_diff*`, and `git_show` return whole outputs. The only bound anywhere is `git_log`'s `max_count` (default `10`, `src/git/src/mcp_server_git/server.py:52`), and in the date-filtered branch that bound is applied *after* fetching the full log — `repo.git.log(*args)` with no `-n`, then a Python-side `len(log) < max_count` cut (`:174-186`). A large repo produces a full log in memory.
- `raise_exceptions=True` on `server.run` (`src/git/src/mcp_server_git/server.py:602`): tool exceptions propagate as **protocol errors**, not `isError` results. There is no `try/except` around the dispatch. This server never returns a content payload with `isError: true`.
- Literal error strings raised from source:
  - `f"Invalid target: '{target}' - cannot start with '-'"` (`BadName`) — `src/git/src/mcp_server_git/server.py:124`
  - `f"Invalid start_timestamp: '{start_timestamp}' - cannot start with '-'"` / `f"Invalid end_timestamp: '{end_timestamp}' - cannot start with '-'"` (`ValueError`) — `:163`, `:165`
  - `f"Invalid path: '{f}'"` (`ValueError`) — `:144`
  - `f"Path '{f}' is outside the repository '{repo_root}'"` (`ValueError`) — `:149`
  - `f"Invalid branch name: '{branch_name}' - cannot start with '-'"` — `:203`, `:218`
  - `f"Invalid base branch: '{base_branch}' - cannot start with '-'"` — `:205`
  - `f"Invalid revision: '{revision}' - cannot start with '-'"` — `:229`
  - `f"Invalid path: {repo_path}"` (`ValueError`, from `validate_repo_path`) — `:262`
  - `f"Repository path '{repo_path}' is outside the allowed repository '{allowed_repository}'"` (`ValueError`) — `:269`
  - `f"Unknown tool: {name}"` (`ValueError`) — `:598`
  - `"server.request_context.session must be a ServerSession"` (`TypeError`) — `:461`
- **One error is not an error:** an invalid `branch_type` returns a *successful* text result whose body is `f"Invalid branch type: {branch_type}"` (`src/git/src/mcp_server_git/server.py:300`, returned via `:592-595`). A mock must reproduce this as a normal 200-style result, not an error.
- Roots support: `list_repos()` (`src/git/src/mcp_server_git/server.py:458-485`) checks `ClientCapabilities(roots=RootsCapability())`, calls `session.list_roots()`, and keeps roots that are valid git repos. **It is dead code in this commit** — nothing calls `list_repos`; grep shows only its definition. Roots therefore do *not* widen or narrow the sandbox for git.
- `git_log`'s two branches produce **different text**: the non-filtered path uses `!r` repr formatting (`f"Commit: {commit.hexsha!r}"` → quoted string, `:193-196`), the date-filtered path does not (`f"Commit: {log_output[i]}"`, `:181-184`). Same for `git_show`, which uses `!r` throughout (`:232-235`). Faithful mocks must include the surrounding quotes.

---

## `filesystem` (TypeScript) — 14 tools

**Entrypoint:** `src/filesystem/index.ts:1` (`#!/usr/bin/env node`); server constructed at `src/filesystem/index.ts:163-168` as `{ name: "secure-filesystem-server", version: "0.2.0" }`; stdio connect at `src/filesystem/index.ts:773-780`. Supporting modules: `src/filesystem/lib.ts` (validation + IO), `src/filesystem/path-validation.ts` (containment check), `src/filesystem/roots-utils.ts` (roots → directories).

### Tools

- `read_file` — R — **deprecated** alias of `read_text_file`, shares the same handler — `src/filesystem/index.ts:213-223` (handler `:191-211`)
- `read_text_file` — R — read a file as text, optional `head`/`tail` line windows — `src/filesystem/index.ts:225-246`
- `read_media_file` — R — read a file as base64 image/audio content, or an embedded resource for other types — `src/filesystem/index.ts:248-316`
- `read_multiple_files` — R — read many files; per-file failures are inlined, not fatal — `src/filesystem/index.ts:318-355`
- `write_file` — W (destructive) — create or overwrite a file — `src/filesystem/index.ts:357-381`
- `edit_file` — W (destructive) — line-based edits, returns a git-style diff; `dryRun` previews — `src/filesystem/index.ts:383-410`
- `create_directory` — W (idempotent) — `mkdir -p` semantics — `src/filesystem/index.ts:412-436`
- `list_directory` — R — `[FILE]`/`[DIR]` prefixed listing — `src/filesystem/index.ts:438-464`
- `list_directory_with_sizes` — R — listing plus sizes and a summary — `src/filesystem/index.ts:466-543`
- `directory_tree` — R — recursive JSON tree with exclude globs — `src/filesystem/index.ts:545-613`
- `move_file` — W (destructive) — rename/move; fails if destination exists — `src/filesystem/index.ts:615-642`
- `search_files` — R — recursive glob search — `src/filesystem/index.ts:644-671`
- `get_file_info` — R — stat metadata — `src/filesystem/index.ts:673-699`
- `list_allowed_directories` — R — introspect the sandbox — `src/filesystem/index.ts:701-721`

### Key tools table

Every tool declares `outputSchema: { content: z.string() }` **except** `read_media_file`, which declares a union array (`src/filesystem/index.ts:259-276`). All handlers return both a `content` array and a mirrored `structuredContent`.

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `read_file` | `path`: string — required; `tail`: number — optional; `head`: number — optional | `{ content: [{type:"text", text:<file text>}], structuredContent: { content: <file text> } }` | `src/filesystem/index.ts:213-223`, handler `:191-211` |
| `read_text_file` | same as above | same as above | `src/filesystem/index.ts:225-246` |
| `read_media_file` | `path`: string — required | `{ content: [ {type:"image"\|"audio", data:<base64>, mimeType} \| {type:"resource", resource:{uri:<file:// href>, mimeType, blob}} ], structuredContent: { content: [same] } }` | `src/filesystem/index.ts:248-316`; MIME map `:282-294`; branch `:302-310` |
| `read_multiple_files` | `paths`: string[] — required, `.min(1)` | `{ content:[{type:"text", text: entries.join("\n---\n")}], … }`; per file `"<path>:\n<content>\n"` or `"<path>: Error - <msg>"` | `src/filesystem/index.ts:318-355`; join `:349`; per-file `:342`, `:345` |
| `write_file` | `path`: string — required; `content`: string — required | text `` `Successfully wrote to ${args.path}` `` | `src/filesystem/index.ts:357-381`; text `:375` |
| `edit_file` | `path`: string — required; `edits`: `{oldText: string, newText: string}[]` — required; `dryRun`: boolean — optional, default `false` | text = fenced unified diff, `` `${backticks}diff\n${diff}${backticks}\n\n` `` | `src/filesystem/index.ts:383-410`; diff formatting `src/filesystem/lib.ts:256-263` |
| `create_directory` | `path`: string — required | text `` `Successfully created directory ${args.path}` `` | `src/filesystem/index.ts:412-436`; text `:430` |
| `list_directory` | `path`: string — required | text of lines `"[DIR] name"` / `"[FILE] name"` | `src/filesystem/index.ts:438-464`; format `:456-458` |
| `list_directory_with_sizes` | `path`: string — required; `sortBy`: `"name"\|"size"` — optional, default `"name"` | text lines `"[FILE] <name padEnd(30)> <size padStart(10)>"` then `""`, `"Total: N files, M directories"`, `"Combined size: <X>"` | `src/filesystem/index.ts:466-543`; rows `:519-523`; summary `:530-534` |
| `directory_tree` | `path`: string — required; `excludePatterns`: string[] — optional, default `[]` | text = `JSON.stringify(tree, null, 2)` of `{name, type:"file"\|"directory", children?}` | `src/filesystem/index.ts:545-613`; shape `:562-566`; serialize `:606` |
| `move_file` | `source`: string — required; `destination`: string — required | text `` `Successfully moved ${args.source} to ${args.destination}` `` | `src/filesystem/index.ts:615-642`; text `:635` |
| `search_files` | `path`: string — required; `pattern`: string — required; `excludePatterns`: string[] — optional, default `[]` | text = newline-joined absolute paths, or literal `"No matches found"` | `src/filesystem/index.ts:644-671`; fallback `:665` |
| `get_file_info` | `path`: string — required | text of `"key: value"` lines for `size, created, modified, accessed, isDirectory, isFile, permissions` | `src/filesystem/index.ts:673-699`; field set `src/filesystem/lib.ts:144-155`; render `index.ts:691-693` |
| `list_allowed_directories` | *(none — `inputSchema: {}`)* | text `` `Allowed directories:\n${allowedDirectories.join('\n')}` `` | `src/filesystem/index.ts:701-721`; text `:715` |

### Auth / config / sandboxing

**No auth.** Access control is entirely the allowed-directories sandbox. Two independent ways to populate it, and at least one must supply a directory (`src/filesystem/index.ts:33-38`).

1. **Command-line arguments.** `process.argv.slice(2)` (`src/filesystem/index.ts:32`). Each argument is `~`-expanded, `path.resolve`d, normalized, then `fs.realpath`ed; **both** the pre-symlink and post-symlink forms are kept when they differ, explicitly to handle macOS `/tmp` → `/private/tmp` (`src/filesystem/index.ts:41-67`, comment at `:43-44`). Non-existent paths keep the normalized absolute form so directories can be created later (`:61-65`). Paths that are not directories or are unreadable are skipped with `Warning: ${dir} is not a directory, skipping` / `Warning: Cannot access directory ${dir}, skipping` (`:77`, `:80`). If *all* specified paths are inaccessible the process exits 1 with `"Error: None of the specified directories are accessible"` (`:85-88`).
2. **MCP roots protocol.** On `oninitialized`, if `clientCapabilities?.roots` is present the server calls `server.server.listRoots()` and **replaces** the entire allowed set (`src/filesystem/index.ts:749-762`, replacement at `:727`). A `roots/list_changed` notification triggers the same full replacement (`src/filesystem/index.ts:736-746`). Root URIs are parsed by `parseRootUri` — `file://` via `fileURLToPath`, `~` expansion, `path.resolve`, then `fs.realpath` — returning `null` on failure (`src/filesystem/roots-utils.ts:13-25`); non-directories and unresolvable entries are skipped with `Skipping non-directory root: <dir>` / `Skipping invalid path or inaccessible: <uri>` / `Skipping invalid directory: <dir> due to error: <msg>` (`src/filesystem/roots-utils.ts:34-40`, `:60`, `:69`, `:72`).

Important: roots **override**, they do not merge. `allowedDirectories = [...validatedRootDirs]` (`src/filesystem/index.ts:727`) discards CLI-supplied directories once a client provides any valid root. If the client returns zero valid roots, the server logs `"No valid root directories provided by client"` and keeps the current set (`src/filesystem/index.ts:731-732`).

If the client does **not** support roots and no CLI directories were given, `oninitialized` throws:

```
Server cannot operate: No allowed directories available. Server was started without command-line directories and client either does not support MCP roots protocol or provided empty roots. Please either: 1) Start server with directory arguments, or 2) Use a client that supports MCP roots protocol and provides valid root directories.
```
— `src/filesystem/index.ts:767`

**The containment check** is `isPathWithinAllowedDirectories(absolutePath, allowedDirectories)` (`src/filesystem/path-validation.ts:11-86`). It returns `false` for non-string input, empty path, empty allow-list, or any embedded `\x00` null byte (`:13-25`, `:46-49`); it `path.resolve(path.normalize(...))`s both sides (`:30`, `:54`); it throws `'Path must be absolute after normalization'` (`:37`) or `'Allowed directories must be absolute paths after normalization'` (`:61`) if resolution somehow yields a relative path. Containment is exact-equality (`:66-68`), POSIX root special-case (`:72-74`), Windows drive-root special-case with a same-drive comparison (`:77-82`), otherwise `normalizedPath.startsWith(normalizedDir + path.sep)` (`:84`) — the trailing separator is what stops `/home/userevil` from matching `/home/user`.

**`validatePath` is a three-stage gate** (`src/filesystem/lib.ts:99-140`), called at the top of every tool handler:

1. Expand `~`, resolve. Relative paths are resolved against each allowed directory in turn, falling back to `allowedDirectories[0]` (or `process.cwd()` when the list is empty) — `src/filesystem/lib.ts:76-96`, `:100-103`.
2. Containment check **before any filesystem call** (`src/filesystem/lib.ts:107-111`).
3. `fs.realpath` and re-check, so a symlink inside the sandbox pointing outside it is rejected (`src/filesystem/lib.ts:115-121`). On `ENOENT` (new file) the **parent** directory is realpath'd and re-checked instead, and the un-realpath'd absolute path is returned (`src/filesystem/lib.ts:125-137`).

**Exact error text on a path escape** — three distinct strings, all thrown as `Error` from `src/filesystem/lib.ts`:

```
Access denied - path outside allowed directories: ${absolute} not in ${allowedDirectories.join(', ')}
```
— `src/filesystem/lib.ts:110` (the primary escape; `absolute` is the resolved request, the list is comma-space joined)

```
Access denied - symlink target outside allowed directories: ${realPath} not in ${allowedDirectories.join(', ')}
```
— `src/filesystem/lib.ts:119`

```
Access denied - parent directory outside allowed directories: ${realParentPath} not in ${allowedDirectories.join(', ')}
```
— `src/filesystem/lib.ts:131`

Additional write-path hardening: `writeFileContent` first tries the `'wx'` exclusive-create flag so it never writes *through* a pre-existing symlink, and on `EEXIST` falls back to write-to-temp + atomic `fs.rename` (`src/filesystem/lib.ts:161-185`, comments `:163-164`, `:167-170`). `applyFileEdits` uses the same temp+rename pattern (`src/filesystem/lib.ts:265-279`).

### Notable behaviours for E6 (pagination / truncation / error text)

- **No pagination and no size cap.** `read_text_file` with neither `head` nor `tail` calls `fs.readFile` on the whole file (`src/filesystem/lib.ts:157-159`). `read_media_file` buffers the entire file in memory before base64-encoding (`src/filesystem/index.ts:173-186`). `directory_tree` recurses without a depth limit (`src/filesystem/index.ts:569-603`). The *only* windowing primitives are `head`/`tail` on `read_text_file`, implemented chunk-wise at 1KB (`src/filesystem/lib.ts:285-334` for tail, `:337-372` for head).
- `head` and `tail` are mutually exclusive: `throw new Error("Cannot specify both head and tail parameters simultaneously")` — `src/filesystem/index.ts:196`.
- **Partial-failure pattern** (worth copying for DevOps tools): `read_multiple_files` catches per-file errors and inlines them as `` `${filePath}: Error - ${errorMessage}` `` (`src/filesystem/index.ts:343-346`) rather than failing the call; entries are joined by `"\n---\n"` (`:349`).
- `search_files` silently swallows per-entry validation failures (`catch { continue; }`, `src/filesystem/lib.ts:407-409`) — so files it cannot validate are just absent from results, with no diagnostic. Empty results become the literal string `"No matches found"` (`src/filesystem/index.ts:665`).
- `edit_file` falls back to whitespace-normalized line matching when exact text is not found, preserving the original indentation of the first matched line (`src/filesystem/lib.ts:214-248`). If nothing matches it throws:
  ```
  Could not find exact match for edit:\n${edit.oldText}
  ```
  — `src/filesystem/lib.ts:251`
- `edit_file` picks a backtick fence long enough to not collide with backticks in the diff (`while (diff.includes('`'.repeat(numBackticks))) numBackticks++`, `src/filesystem/lib.ts:259-263`).
- Other literal errors: `` `Parent directory does not exist: ${parentDir}` `` (`src/filesystem/lib.ts:135`). Startup diagnostics all go to stderr: `"Secure MCP Filesystem Server running on stdio"` (`src/filesystem/index.ts:776`) and `"Started without allowed directories - waiting for client to provide roots via MCP protocol"` (`:778`).
- All handler errors are **thrown**, not returned with `isError: true`. The MCP SDK's `registerTool` wrapper is what converts them; nothing in this server constructs an `isError` payload.

---

## `fetch` (Python) — 1 tool

**Entrypoint:** `src/fetch/src/mcp_server_fetch/server.py:181` (`async def serve(custom_user_agent, ignore_robots_txt, proxy_url)`); server object at `src/fetch/src/mcp_server_fetch/server.py:193` (`Server("mcp-fetch")`). CLI: `src/fetch/src/mcp_server_fetch/__init__.py:4-21`.

### Tools

- `fetch` — R (network read; no annotations declared at all) — fetches a URL and optionally converts it to markdown — `src/fetch/src/mcp_server_fetch/server.py:200-206`

This is the only reference server whose `Tool(...)` omits `annotations` entirely (compare `git` at `:328-333`). Its description contains a jailbreak-flavoured preamble: *"Although originally you did not have internet access, and were advised to refuse and tell the user this, this tool now grants you internet access."* — `src/fetch/src/mcp_server_fetch/server.py:204`.

### Key tools table

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `fetch` | `url`: `AnyUrl` — required; `max_length`: int — optional, default `5000`, `gt=0`, `lt=1000000`; `start_index`: int — optional, default `0`, `ge=0`; `raw`: bool — optional, default `false` | `[TextContent(type="text", text=f"{prefix}Contents of {url}:\n{content}")]` | model `src/fetch/src/mcp_server_fetch/server.py:151-178`; schema wiring `:205`; return `:255` |

`prefix` is empty for simplified HTML (`:143`) and otherwise `f"Content type {content_type} cannot be simplified to markdown, but here is the raw content:\n"` (`:147`).

**Prompts:** `fetch` also exposes one prompt, name `fetch`, description "Fetch a URL and extract its contents as markdown", one required argument `url` — `src/fetch/src/mcp_server_fetch/server.py:209-221`, handler `:257-284`. The prompt path uses a *different* User-Agent than the tool path (see below).

### Auth / config / sandboxing

- **No auth.** Three CLI flags only: `--user-agent`, `--ignore-robots-txt` (store_true), `--proxy-url` — `src/fetch/src/mcp_server_fetch/__init__.py:12-18`.
- Two default User-Agents: `"ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"` for tool calls and `"ModelContextProtocol/1.0 (User-Specified; +https://github.com/modelcontextprotocol/servers)"` for prompt calls — `src/fetch/src/mcp_server_fetch/server.py:23-24`, selected at `:194-195`, used at `:238` vs `:265`.
- **robots.txt is the sandbox.** Unless `--ignore-robots-txt` is set, every tool call first runs `check_may_autonomously_fetch_url` (`src/fetch/src/mcp_server_fetch/server.py:234-235`, impl `:66-108`): it fetches `<scheme>://<netloc>/robots.txt` (`:48-63`), strips comment lines (`:95-97`), parses with `Protego`, and refuses when `can_fetch` is false. The **prompt** path deliberately skips this check (`:265` calls `fetch_url` directly) — the documented escape hatch for a human-initiated fetch.
- No URL allowlist, no SSRF protection, no private-IP filtering. `follow_redirects=True` (`:78`, `:123`), 30s timeout on the content fetch (`:125`), no timeout on the robots.txt fetch (`:77-81`).

### Notable behaviours for E6 (pagination / truncation / error text)

- **This is the only reference server with real pagination**, and it is offset/limit style rather than cursor style: `start_index` + `max_length` slice the extracted content (`src/fetch/src/mcp_server_fetch/server.py:244`), and the server appends a self-describing continuation hint only when a full page was returned *and* content remains:
  ```
  \n\n<error>Content truncated. Call the fetch tool with a start_index of {next_start} to get more content.</error>
  ```
  — `src/fetch/src/mcp_server_fetch/server.py:254`, guarded by `if actual_content_length == args.max_length and remaining_content > 0:` (`:252`)
- Reading past the end yields the literal text `<error>No more content available.</error>` — `src/fetch/src/mcp_server_fetch/server.py:242` and `:246`. Note this is returned as **successful** text content, not an error.
- Failed HTML simplification returns `<error>Page failed to be simplified from HTML</error>` as ordinary content — `src/fetch/src/mcp_server_fetch/server.py:40`.
- `McpError` (protocol error) strings, all with `ErrorData`:
  - `INVALID_PARAMS`, `str(e)` on pydantic validation failure — `:228`
  - `INVALID_PARAMS`, `"URL is required"` — `:232` (tool) and `:260` (prompt)
  - `INTERNAL_ERROR`, `f"Failed to fetch robots.txt {robot_txt_url} due to a connection issue"` — `:85`
  - `INTERNAL_ERROR`, `f"When fetching robots.txt ({robot_txt_url}), received status {response.status_code} so assuming that autonomous fetching is not allowed, the user can try manually fetching by using the fetch prompt"` — `:90`
  - `INTERNAL_ERROR`, the multi-line robots.txt refusal carrying `<useragent>`, `<url>` and `<robots>` blocks plus instructions to the assistant — `:102-107`
  - `INTERNAL_ERROR`, `f"Failed to fetch {url}: {e!r}"` — `:128`
  - `INTERNAL_ERROR`, `f"Failed to fetch {url} - status code {response.status_code}"` — `:132`
- `raise_exceptions=False` on `server.run` (`src/fetch/src/mcp_server_fetch/server.py:288`) — the opposite of `git`. Uncaught exceptions are swallowed by the SDK rather than crashing the loop.
- The prompt handler catches `McpError` and returns it as prompt *content* rather than an error, with a `# TODO: after SDK bug is addressed, don't catch the exception` comment — `src/fetch/src/mcp_server_fetch/server.py:266-276`.
- HTML detection heuristic: `"<html" in page_raw[:100] or "text/html" in content_type or not content_type` — `src/fetch/src/mcp_server_fetch/server.py:138-140`. Note `max_length`/`start_index` slice **characters of the converted markdown**, not bytes of the response.

---

## `memory` (TypeScript) — 9 tools

**Entrypoint:** `src/memory/index.ts:1`; server at `src/memory/index.ts:257-260` (`{ name: "memory-server", version: "0.6.3" }`); `main()` at `:588-597`.

### Tools

- `create_entities` — W — create entities, skipping ones whose `name` already exists — `src/memory/index.ts:277-303`; impl `:120-126`
- `create_relations` — W — create relations, skipping exact duplicates — `src/memory/index.ts:306-332`; impl `:128-138`
- `add_observations` — W — append observations to existing entities — `src/memory/index.ts:335-367`; impl `:140-153`
- `delete_entities` — W (destructive) — delete entities and all relations touching them — `src/memory/index.ts:370-397`; impl `:155-160`
- `delete_observations` — W (destructive) — remove specific observations — `src/memory/index.ts:400-430`; impl `:162-171`
- `delete_relations` — W (destructive) — remove matching relations — `src/memory/index.ts:433-460`; impl `:173-181`
- `read_graph` — R — return the whole graph — `src/memory/index.ts:463-487`
- `search_nodes` — R — substring match over name / entityType / observations — `src/memory/index.ts:490-516`; impl `:188-213`
- `open_nodes` — R — fetch entities by exact name — `src/memory/index.ts:519-545`; impl `:215-238`

### Key tools table

`Entity` = `{name: string, entityType: string, observations: string[]}` (`src/memory/index.ts:244-248`); `Relation` = `{from: string, to: string, relationType: string}` (`:250-254`). Every handler returns `content: [{type:"text", text: <JSON or fixed string>}]` plus a typed `structuredContent`.

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `create_entities` | `entities`: Entity[] — required | text = `JSON.stringify(newEntities, null, 2)`; `structuredContent: { entities: Entity[] }` — **only the newly created ones** | `src/memory/index.ts:277-303`; filter `:122` |
| `create_relations` | `relations`: Relation[] — required | text = JSON of new relations; `structuredContent: { relations: Relation[] }` | `src/memory/index.ts:306-332` |
| `add_observations` | `observations`: `{entityName: string, contents: string[]}[]` — required | `structuredContent: { results: [{entityName, addedObservations: string[]}] }` | `src/memory/index.ts:335-367` |
| `delete_entities` | `entityNames`: string[] — required | text `"Entities deleted successfully"`; `structuredContent: {success: true, message: "Entities deleted successfully"}` | `src/memory/index.ts:370-397`; text `:393-394` |
| `delete_observations` | `deletions`: `{entityName: string, observations: string[]}[]` — required | text `"Observations deleted successfully"`; same success/message shape | `src/memory/index.ts:400-430`; text `:426-427` |
| `delete_relations` | `relations`: Relation[] — required | text `"Relations deleted successfully"`; same success/message shape | `src/memory/index.ts:433-460`; text `:456-457` |
| `read_graph` | *(none)* | text = `JSON.stringify(graph, null, 2)`; `structuredContent: {entities, relations}` | `src/memory/index.ts:463-487` |
| `search_nodes` | `query`: string — required | same shape as `read_graph`, filtered | `src/memory/index.ts:490-516` |
| `open_nodes` | `names`: string[] — required | same shape as `read_graph`, filtered | `src/memory/index.ts:519-545` |

**Resource:** one static resource `memory://knowledge-graph` (`src/memory/index.ts:262`), registered as `"knowledge-graph"` with `mimeType: "application/json"` returning `contents: [{uri, mimeType, text: JSON.stringify(graph, null, 2)}]` — `src/memory/index.ts:547-572`.

**Subscriptions:** memory advertises `resources: { subscribe: true }` and installs `SubscribeRequestSchema`/`UnsubscribeRequestSchema` handlers backed by a `Set<string>` of URIs (`src/memory/index.ts:576-586`, set at `:266`). Every mutating tool calls `notifyGraphUpdated()`, which emits `notifications/resources/updated` **only if the client actually subscribed** (`src/memory/index.ts:270-274`).

### Auth / config / sandboxing

- **No auth. No sandbox.** The only config is the `MEMORY_FILE_PATH` env var (`src/memory/index.ts:16`); relative values are resolved against the module directory (`:18-20`), absolute values used as-is. Default is `memory.jsonl` next to the compiled module (`src/memory/index.ts:12`).
- Backward-compat migration: if a legacy `memory.json` exists and `memory.jsonl` does not, the file is `fs.rename`d, logging `'DETECTED: Found legacy memory.json file, migrating to memory.jsonl for JSONL format compatibility'` then `'COMPLETED: Successfully migrated memory.json to memory.jsonl'` — `src/memory/index.ts:23-44`.
- Storage format is JSONL: one `{"type":"entity",…}` or `{"type":"relation",…}` object per line (`src/memory/index.ts:102-118`); load filters blank lines and ignores unknown `type` values (`:72-100`). A missing file yields an empty graph rather than an error (`ENOENT` handling at `:95-97`).

### Notable behaviours for E6 (pagination / truncation / error text)

- **No pagination, no limit, no cursor.** `read_graph` serializes the entire graph; `search_nodes` is a naive lowercase `includes` scan over every entity (`src/memory/index.ts:192-196`) with no result cap.
- Whole-file rewrite on every mutation: `saveGraph` re-serializes and `fs.writeFile`s the complete graph (`src/memory/index.ts:102-118`) — not append-only, and not atomic (no temp+rename, unlike `filesystem`).
- Only one literal error string in the whole server: `` `Entity with name ${o.entityName} not found` `` thrown from `addObservations` (`src/memory/index.ts:145`). Deletes are silently tolerant — `deleteObservations` no-ops on a missing entity (`if (entity)`, `:166`), and `deleteEntities` / `deleteRelations` filter without reporting how many matched.
- Relation filtering in `search_nodes` and `open_nodes` uses `has(r.from) || has(r.to)` — either endpoint, not both. The source comment at `src/memory/index.ts:224-227` records that requiring both previously "silently dropped" a node's outbound connections.
- Errors are thrown, never returned as `isError`. Fatal startup errors log `"Fatal error in main():"` and exit 1 (`src/memory/index.ts:599-601`).

---

## `time` (Python) — 2 tools

**Entrypoint:** `src/time/src/mcp_server_time/server.py:123` (`async def serve(local_timezone)`); server at `src/time/src/mcp_server_time/server.py:124` (`Server("mcp-time")`). CLI: `src/time/src/mcp_server_time/__init__.py:4-15`.

### Tools

- `get_current_time` — R — current time in an IANA timezone — `src/time/src/mcp_server_time/server.py:18` (enum), `:132-151` (registration), `:61-71` (impl)
- `convert_time` — R — convert an `HH:MM` time between two IANA timezones — `src/time/src/mcp_server_time/server.py:19`, `:152-179`, `:73-120`

Both declare `readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False` (`:145-150`, `:173-178`) — note `get_current_time` is marked idempotent although it obviously is not.

### Key tools table

Unlike `git` and `fetch`, `time` hand-writes its JSON Schema rather than deriving it from pydantic (`src/time/src/mcp_server_time/server.py:135-144`, `:155-172`). The pydantic models here are used only for the **response**.

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `get_current_time` | `timezone`: string — required (IANA name) | `[TextContent(type="text", text=json.dumps({"timezone":str,"datetime":str ISO-8601 seconds,"day_of_week":str,"is_dst":bool}, indent=2))]` | schema `:135-144`; model `:22-27`; build `:66-71`; serialize `:211-213` |
| `convert_time` | `source_timezone`: string — required; `time`: string — required (`HH:MM`, 24h); `target_timezone`: string — required | `[TextContent(type="text", text=json.dumps({"source": TimeResult, "target": TimeResult, "time_difference": str}, indent=2))]` | schema `:155-172`; models `:29-33`; build `:106-120` |

`time_difference` formatting: whole-hour offsets render as `f"{hours:+.1f}h"` (e.g. `+9.0h`), fractional offsets strip trailing zeros then append `h` (e.g. Nepal's `+5.75h`) — `src/time/src/mcp_server_time/server.py:100-104`.

### Auth / config / sandboxing

- **No auth, nothing to sandbox.** One CLI flag: `--local-timezone` (`src/time/src/mcp_server_time/__init__.py:12`).
- Local timezone resolution order: explicit override → `tzlocal.get_localzone_name()` → hard fallback to `ZoneInfo("UTC")` — `src/time/src/mcp_server_time/server.py:41-50`.
- The resolved local timezone is **interpolated into the tool descriptions at registration time**, e.g. `f"IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use '{local_tz}' as local timezone if no timezone provided by the user."` — `src/time/src/mcp_server_time/server.py:140`, `:160`, `:168`. A mock must therefore render descriptions per-host, not as a fixed constant.

### Notable behaviours for E6 (pagination / truncation / error text)

- No pagination; responses are fixed-size JSON blobs.
- **All exceptions are re-wrapped.** The whole dispatch is inside `try/except Exception as e: raise ValueError(f"Error processing mcp-server-time query: {str(e)}")` — `src/time/src/mcp_server_time/server.py:215-216`. This means even the carefully constructed `McpError` from `get_zoneinfo` is flattened into a `ValueError` whose message is the stringified original. Nested text a client actually sees looks like:
  `Error processing mcp-server-time query: Invalid timezone: 'No time zone found with key Bad/Zone'`
- Literal strings:
  - `f"Invalid timezone: {str(e)}"` with `code=INVALID_PARAMS` — `src/time/src/mcp_server_time/server.py:57`
  - `"Invalid time format. Expected HH:MM [24-hour format]"` — `:83`
  - `"Missing required argument: timezone"` — `:192`
  - `"Missing required arguments"` — `:201`
  - `f"Unknown tool: {name}"` — `:209`
  - `f"Error processing mcp-server-time query: {str(e)}"` — `:216`
- `server.run` is called **without** a `raise_exceptions` argument (`src/time/src/mcp_server_time/server.py:220`), unlike git (`True`) and fetch (`False`) — so the SDK default applies. NOT DETERMINED FROM SOURCE what that default is (it lives in the Python SDK, not this repo).
- `convert_time` always uses *today's* date in the source timezone (`datetime.now(source_timezone)` at `:85`, fields reused at `:86-93`), so results are not stable across days — relevant if mocking deterministic fixtures.

---

## `sequentialthinking` (TypeScript) — 1 tool

**Entrypoint:** `src/sequentialthinking/index.ts:1`; server at `src/sequentialthinking/index.ts:18-21` (`{ name: "sequential-thinking-server", version: "0.2.0" }`); logic in `src/sequentialthinking/lib.ts`.

### Tools

- `sequentialthinking` — R (declared `readOnlyHint: true`, though it mutates in-process history) — records one reasoning step, supporting revision and branching — `src/sequentialthinking/index.ts:25-123`; impl `src/sequentialthinking/lib.ts:52-98`

### Key tools table

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `sequentialthinking` | `thought`: string — required; `nextThoughtNeeded`: boolean (coerced from `"true"`/`"false"` strings) — required; `thoughtNumber`: int ≥1 (coerced) — required; `totalThoughts`: int ≥1 (coerced) — required; `isRevision`: boolean — optional; `revisesThought`: int ≥1 — optional; `branchFromThought`: int ≥1 — optional; `branchId`: string — optional; `needsMoreThoughts`: boolean — optional | `content: [{type:"text", text: JSON.stringify({thoughtNumber, totalThoughts, nextThoughtNeeded, branches: string[], thoughtHistoryLength: number}, null, 2)}]` plus identical `structuredContent` | inputSchema `src/sequentialthinking/index.ts:83-93`; outputSchema `:100-106`; payload `src/sequentialthinking/lib.ts:74-85` |

The tool's `description` is a ~50-line usage manual (`src/sequentialthinking/index.ts:29-82`) — by far the longest description in the repo, and a useful reference for how much prompt text a single tool can carry.

A bespoke `coercedBoolean` preprocessor accepts the strings `"true"`/`"false"` case-insensitively, explicitly to stop `"false"` being truthy (`src/sequentialthinking/index.ts:9-16`); numeric fields use `z.coerce.number()` (`:86-90`).

### Auth / config / sandboxing

- **No auth, no filesystem, no network.** All state is in-process: `thoughtHistory: ThoughtData[]` and `branches: Record<string, ThoughtData[]>` (`src/sequentialthinking/lib.ts:16-17`). Nothing persists across restarts.
- One env var: `DISABLE_THOUGHT_LOGGING` (compared lowercased against `"true"`) suppresses the stderr rendering — `src/sequentialthinking/lib.ts:21`, used at `:69-72`.
- Side effect worth knowing when mocking: unless disabled, each call prints a chalk-coloured box (`🔄 Revision` / `🌿 Branch` / `💭 Thought`) to **stderr** — `src/sequentialthinking/lib.ts:24-50`.

### Notable behaviours for E6 (pagination / truncation / error text)

- No pagination or truncation; the response is a small fixed JSON object. The thought text itself is never echoed back — only counters and branch IDs.
- Silent input correction: if `thoughtNumber > totalThoughts`, `totalThoughts` is raised to match rather than rejected — `src/sequentialthinking/lib.ts:56-58`.
- **This is the only reference server that returns an `isError: true` content payload** rather than throwing. `processThought` catches and returns:
  ```
  { content: [{ type: "text", text: JSON.stringify({ error: <message>, status: 'failed' }, null, 2) }], isError: true }
  ```
  — `src/sequentialthinking/lib.ts:86-97`. The registration wrapper short-circuits on it (`if (result.isError) return result;`, `src/sequentialthinking/index.ts:111-113`), so an error result carries **no** `structuredContent` — asymmetric with the success path (`:118-121`). In practice the `try` body cannot realistically throw (validation already happened in Zod, per the comment at `src/sequentialthinking/lib.ts:54`), so this path is mostly aspirational.

---

## `everything` (TypeScript) — 19 tools

**Entrypoint:** `src/everything/index.ts:1` — a launcher only; it dispatches on `argv[2]` to `./transports/stdio.js` (default), `./transports/sse.js`, or `./transports/streamableHttp.js` (`src/everything/index.ts:4-35`). The actual server factory is `createServer()` at `src/everything/server/index.ts:35`, constructing `{ name: "mcp-servers/everything", title: "Everything Reference Server", version: "2.0.0" }` (`src/everything/server/index.ts:46-51`).

Declared capabilities (`src/everything/server/index.ts:52-78`): `tools.listChanged`, `prompts.listChanged`, `resources.subscribe` + `resources.listChanged`, `logging`, and experimental `tasks` (`list`, `cancel`, `requests.tools.call`). Server `instructions` are loaded from `src/everything/docs/instructions.md` at startup, falling back to the string `"Server instructions not loaded: " + e` on failure (`src/everything/resources/index.ts:24-35`).

### Tools

**Always registered** — `registerTools`, `src/everything/tools/index.ts:26-39`:

- `echo` — R — echoes the input string — `src/everything/tools/echo.ts:11` (name), `:12-22` (config), `:34-39` (handler)
- `get-annotated-message` — R — demonstrates content-block `annotations` (`priority`, `audience`) — `src/everything/tools/get-annotated-message.ts:18`, `:19-30`, `:45-95`
- `get-env` — R — dumps `process.env` as JSON — `src/everything/tools/get-env.ts:5`, `:6-17`, `:29-38`
- `get-resource-links` — R — returns `resource_link` content blocks — `src/everything/tools/get-resource-links.ts:22`, `:23-34`, `:48-85`
- `get-resource-reference` — R — returns an embedded `resource` content block — `src/everything/tools/get-resource-reference.ts:26`, `:27-37`, `:56-103`
- `get-structured-content` — R — demonstrates `outputSchema` + `structuredContent` — `src/everything/tools/get-structured-content.ts:23`, `:24-36`, `:53-91`
- `get-sum` — R — adds two numbers — `src/everything/tools/get-sum.ts:12`, `:13-23`, `:39-50`
- `get-tiny-image` — R — returns text + an `image` block — `src/everything/tools/get-tiny-image.ts:9`, `:10-20`, `:34-52`
- `gzip-file-as-resource` — W (`openWorldHint: true`, fetches URLs) — gzips remote/data-URI content and registers it as a session resource — `src/everything/tools/gzip-file-as-resource.ts:44`, `:45-56`, `:74-125`
- `toggle-simulated-logging` — W — starts/stops periodic random-level `notifications/message` — `src/everything/tools/toggle-simulated-logging.ts:9`, `:10-20`, `:38-59`
- `toggle-subscriber-updates` — W — starts/stops periodic `notifications/resources/updated` — `src/everything/tools/toggle-subscriber-updates.ts:9`, `:10-20`, `:41-62`
- `trigger-long-running-operation` — R — emits `notifications/progress` over N steps — `src/everything/tools/trigger-long-running-operation.ts:15`, `:16-26`, `:43-82`

**Conditionally registered** in `oninitialized`, after client capabilities are known — `registerConditionalTools`, `src/everything/tools/index.ts:45-55`, invoked at `src/everything/server/index.ts:97`:

- `get-roots-list` — R — requires `clientCapabilities.roots` — `src/everything/tools/get-roots-list.ts:6`, gate `:38-43`, registration `:44-47`
- `trigger-elicitation-request` — W — requires `clientCapabilities.elicitation` — `src/everything/tools/trigger-elicitation-request.ts:8`, gate `:40-46`, registration `:47-50`
- `trigger-url-elicitation` — W (`openWorldHint: true`) — requires `clientCapabilities.elicitation.url` — `src/everything/tools/trigger-url-elicitation.ts:36`, gate `:96-106`, registration `:107-110`
- `trigger-sampling-request` — W (`openWorldHint: true`) — requires `clientCapabilities.sampling` — `src/everything/tools/trigger-sampling-request.ts:19`, gate `:46-52`, registration `:53-56`
- `simulate-research-query` — W — registered via `server.experimental.tasks.registerToolTask` with `execution: { taskSupport: "required" }` — `src/everything/tools/simulate-research-query.ts:236-258` (name literal at `:243`)
- `trigger-sampling-request-async` — W (`openWorldHint: true`) — requires `sampling` **and** `tasks.requests.sampling.createMessage` — `src/everything/tools/trigger-sampling-request-async.ts:18`, gate `:52-65`, registration `:66-68`
- `trigger-elicitation-request-async` — W — requires `elicitation` **and** `tasks.requests.elicitation.create` — `src/everything/tools/trigger-elicitation-request-async.ts:6`, gate `:43-57`, registration `:58-60`

So `tools/list` from a bare client returns 12 entries; a fully capable client sees 19. This staged registration is the whole point of `tools.listChanged: true` (`src/everything/server/index.ts:54-56`).

### Key tools table

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `echo` | `message`: string — required | `{content:[{type:"text", text:"Echo: <message>"}]}` | `src/everything/tools/echo.ts:6-8`, `:36-38` |
| `get-sum` | `a`: number — required; `b`: number — required | `{content:[{type:"text", text:"The sum of <a> and <b> is <sum>."}]}` | `src/everything/tools/get-sum.ts:6-9`, `:42-49` |
| `get-env` | *(none, `inputSchema: {}`)* | `{content:[{type:"text", text: JSON.stringify(process.env, null, 2)}]}` | `src/everything/tools/get-env.ts:10`, `:30-37` |
| `get-tiny-image` | *(none)* | 3 blocks: text `"Here's the image you requested:"`, `{type:"image", data:<base64 PNG>, mimeType:"image/png"}`, text `"The image above is the MCP logo."` | `src/everything/tools/get-tiny-image.ts:35-51` |
| `get-annotated-message` | `messageType`: `"error"\|"success"\|"debug"` — required; `includeImage`: boolean — optional, default `false` | text blocks carrying `annotations: {priority, audience}` (errors: `priority: 1.0`, `audience: ["user","assistant"]`) | `src/everything/tools/get-annotated-message.ts:7-15`, `:48-59` |
| `get-structured-content` | `location`: `"New York"\|"Chicago"\|"Los Angeles"` — required | `{content:[{type:"text", text: JSON.stringify(weather)}], structuredContent: {temperature:number, conditions:string, humidity:number}}` | input `src/everything/tools/get-structured-content.ts:9-13`; output schema `:16-20`; return `:87-90` |
| `get-resource-links` | `count`: number — optional, `.min(1).max(10)`, default `3` | intro text block + N `{type:"resource_link", uri, name, description, mimeType}` blocks | `src/everything/tools/get-resource-links.ts:12-19`, `:52-84` |
| `get-resource-reference` | `resourceType`: `"Text"\|"Blob"` — optional, default `"Text"`; `resourceId`: number — optional, default `1` | content including a `{type:"resource", resource:{uri, mimeType, text\|blob}}` block | `src/everything/tools/get-resource-reference.ts:15-23`, `:56-103` |
| `trigger-long-running-operation` | `duration`: number — optional, default `10` (seconds); `steps`: number — optional, default `5` | interim `notifications/progress` per step, then a completion text block | `src/everything/tools/trigger-long-running-operation.ts:6-12`, `:46-82` |
| `gzip-file-as-resource` | `name`: string — optional, default `"README.md.gz"`; `data`: URL — optional, default the repo README raw URL; `outputType`: `"resourceLink"\|"resource"` — optional, default `"resourceLink"` | `outputType="resource"` → `{content:[{type:"resource", resource:{uri, mimeType:"application/gzip", blob}}]}`; `"resourceLink"` → `{content:[{type:"resource_link", …}]}` | `src/everything/tools/gzip-file-as-resource.ts:27-41`, `:95-124` |
| `toggle-simulated-logging` | *(none)* | text `"Started simulated, random-leveled logging for session <id> at a 5 second pace. …"` or `"Stopped simulated logging for session <id>"` | `src/everything/tools/toggle-simulated-logging.ts:44-57` |
| `toggle-subscriber-updates` | *(none)* | text `"Started simulated resource updated notifications for session <id> at a 5 second pace. …"` or `"Stopped simulated resource updates for session <id>"` | `src/everything/tools/toggle-subscriber-updates.ts:47-60` |
| `get-roots-list` | *(none)* | text listing the roots the server currently knows; if none configured, a 3-bullet explanation block | `src/everything/tools/get-roots-list.ts:11`, `:47-69` |
| `trigger-sampling-request` | `prompt`: string — required; `maxTokens`: number — optional, default `100` | result of a server→client `sampling/createMessage` round trip | `src/everything/tools/trigger-sampling-request.ts:10-16`, `:53-56` |
| `trigger-sampling-request-async` | `prompt`: string — required; `maxTokens`: number — optional, default `100` | client-executed task; server polls `tasks/get` then `tasks/result` (`POLL_INTERVAL = 1000` ms, `MAX_POLL_ATTEMPTS = 60`) | `src/everything/tools/trigger-sampling-request-async.ts:9-15`, `:34-38`, `:66-68` |
| `trigger-elicitation-request` | *(none)* | echoes the elicitation outcome (accept-with-content / decline / cancel) plus raw result for debugging | `src/everything/tools/trigger-elicitation-request.ts:12`, `:47-50` |
| `trigger-elicitation-request-async` | *(none)* | client-executed elicitation task; `POLL_INTERVAL = 1000` ms, `MAX_POLL_ATTEMPTS = 600` (10 minutes for human input) | `src/everything/tools/trigger-elicitation-request-async.ts:13`, `:22-26`, `:58-60` |
| `trigger-url-elicitation` | `url`: string (URL) — required; `message`: string — optional, default `"Please open the link to complete this action."`; `elicitationId`: string — optional (random UUID); `errorPath`: boolean — optional, default `false` | request path → awaited `elicitation/create` result; error path → throws `UrlElicitationRequiredError` (MCP error **-32042**) | `src/everything/tools/trigger-url-elicitation.ts:12-33`, `:107-110` |
| `simulate-research-query` | `topic`: string — required; `ambiguous`: boolean — optional, default `false` | `CreateTaskResult` first; final `tasks/result` is a long markdown report text block | `src/everything/tools/simulate-research-query.ts:13-21`, `:217-224`, `:242-258` |

### Resources

Registered by `registerResources` — `src/everything/resources/index.ts:12-15`.

**1. Static file resources** — one per file in `src/everything/docs/`, enumerated with `readdirSync` at startup (`src/everything/resources/files.ts:16-27`). URI pattern `demo://resource/static/document/<encodeURIComponent(filename)>` (`src/everything/resources/files.ts:41`), description `` `Static document file exposed from /docs: ${name}` `` (`:43`). MIME by extension: `.md`/`.markdown` → `text/markdown`, `.txt` → `text/plain`, `.json` → `application/json`, else `text/plain` (`src/everything/resources/files.ts:70-77`). Read failures return the text `` `Error reading file: ${path}. ${e}` `` as resource content rather than erroring (`:83-88`). Directories are skipped (`:33-38`); a missing `docs/` folder silently skips all registration (`:22-27`). The docs directory in this commit contains 7 files: `architecture.md`, `extension.md`, `features.md`, `how-it-works.md`, `instructions.md`, `startup.md`, `structure.md`.

**2. Resource templates (2)** — `src/everything/resources/templates.ts:171-211`:

| Template name | URI template | mimeType | Behaviour |
|---|---|---|---|
| `Dynamic Text Resource` | `demo://resource/dynamic/text/{resourceId}` | `text/plain` | `{uri, mimeType, text: "Resource <id>: This is a plaintext resource created at <time>"}` — `src/everything/resources/templates.ts:173-190`, generator `:86-93` |
| `Dynamic Blob Resource` | `demo://resource/dynamic/blob/{resourceId}` | `application/octet-stream` | `{uri, mimeType:"text/plain", blob: base64("Resource <id>: This is a base64 blob created at <time>")}` — `:193-210`, generator `:101-111` |

Both pass `list: undefined` (`src/everything/resources/templates.ts:176`, `:196`), so **they never appear in `resources/list`** — they are reachable only by constructing a template URI (documented at `:161-162`). Both attach a `complete: { resourceId: … }` handler (`:177`, `:197`) wired to `resourceIdForResourceTemplateCompleter`, which echoes the value back only if it parses as a positive integer (`:67-72`). Invalid IDs throw `` `Unknown resource: ${uri.toString()}` `` (`src/everything/resources/templates.ts:140`, thrown at `:145` and `:152`).

**3. Session resources** — created at runtime, not at startup. `registerSessionResource` (`src/everything/resources/session.ts:32-80`) registers a resource at `demo://resource/session/<name>` (`:17-19`) and returns a `{ type: "resource_link", ...resource }` (`:79`). It de-duplicates by URI, calling `.remove()` on a prior registration to avoid "Resource already registered" (`src/everything/resources/session.ts:9, 57-62`). Only `gzip-file-as-resource` uses it (`src/everything/tools/gzip-file-as-resource.ts:101-106`).

**4. Subscriptions** — `setSubscriptionHandlers(server)` at `src/everything/server/index.ts:91`, implemented in `src/everything/resources/subscriptions.ts`; driven by the `toggle-subscriber-updates` tool and torn down in `cleanup` (`src/everything/server/index.ts:109-116`).

### Prompts (4)

Registered by `registerPrompts` — `src/everything/prompts/index.ts:12-17`.

| Prompt | Arguments | Demonstrates | Source |
|---|---|---|---|
| `simple-prompt` | none | fixed single user message: `"This is a simple prompt without arguments."` | `src/everything/prompts/simple.ts:11-28` |
| `args-prompt` | `city`: string — required; `state`: string — optional | argument interpolation → `` `What's weather in ${location}?` `` | `src/everything/prompts/args.ts:13-16`, `:19-40` |
| `completable-prompt` | `department`: string — required; `name`: string — required | **completions**, including context-dependent completion (the `name` completer reads `context?.arguments?.["department"]` and returns a different roster per department) | `src/everything/prompts/completions.ts:15-42`, `:45-63` |
| `resource-prompt` | `resourceType`: string — required; `resourceId`: string — required | **embedded resource in a prompt message** — returns a text block plus `{role:"user", content:{type:"resource", resource}}` | `src/everything/prompts/resource.ts:25-28`, `:31-92`, resource block `:82-88` |

Completion values in `completable-prompt`: departments `Engineering, Sales, Marketing, Support` (`src/everything/prompts/completions.ts:19`); names per department `Alice/Bob/Charlie`, `David/Eve/Frank`, `Grace/Henry/Iris`, `John/Kim/Lee` (`:31-37`). All completers filter by `startsWith(value)`.

`resource-prompt` validation errors: `` `Invalid resourceType: ${args?.resourceType}. Must be ${RESOURCE_TYPE_TEXT} or ${RESOURCE_TYPE_BLOB}.` `` (`src/everything/prompts/resource.ts:46-48`) and `` `Invalid resourceId: ${args?.resourceId}. Must be a finite positive integer.` `` (`:58-60`). A source comment records why `resourceId` is a *string* rather than a number: "prompt arguments can only be strings since type is not field of `PromptArgument`" (`src/everything/resources/templates.ts:40-42`).

### Auth / config / sandboxing

- **No auth on any transport.** stdio is the default (`src/everything/index.ts:11-14`). The Streamable HTTP transport mounts Express on `/mcp` with **wide-open CORS** — `origin: "*"` with the source comment "use `*` with caution in production" (`src/everything/transports/streamableHttp.ts:43-51`), sessions keyed by `randomUUID` in an in-memory `Map` (`:53-57`), and an in-memory `EventStore` for SSE resumability that never evicts (`:11-37`). A third transport exists at `src/everything/transports/sse.ts` (dispatched at `src/everything/index.ts:15-18`); repo docs describe transport support as "stdio (default), SSE (deprecated), Streamable HTTP" (`CLAUDE.md:103`).
- The only real guardrails in the whole server are on `gzip-file-as-resource`, all env-configurable: `GZIP_MAX_FETCH_SIZE` (default 10 MB, `src/everything/tools/gzip-file-as-resource.ts:11-13`), `GZIP_MAX_FETCH_TIME_MILLIS` (default 30 s, `:16-18`), and `GZIP_ALLOWED_DOMAINS` (comma-separated; **empty means all domains allowed**, `:20-24`). `validateDataURI` restricts protocols to `http:`, `https:`, `data:` and throws `` `Unsupported URL protocol for ${dataUri}. Only http, https, and data URLs are supported.` `` (`src/everything/tools/gzip-file-as-resource.ts:135-147`).
- `get-env` returns the **entire process environment** verbatim (`src/everything/tools/get-env.ts:34`) — an obvious secret-exfiltration primitive that ships enabled by default. Worth flagging in any threat model that treats this server as representative.

### Notable behaviours for E6 (pagination / truncation / error text)

- **No pagination anywhere.** The closest thing to a limit is `get-resource-links`'s `count` bounded `.min(1).max(10)` (`src/everything/tools/get-resource-links.ts:14-17`).
- **Long-running work is modelled three different ways**, which is the most useful part of this server as a reference:
  1. *Progress notifications* — `trigger-long-running-operation` emits `notifications/progress` per step when the caller supplied `_meta.progressToken` (`src/everything/tools/trigger-long-running-operation.ts:50`, `:57-60`); with no token it just blocks.
  2. *Server-side tasks* — `simulate-research-query` returns a `CreateTaskResult` immediately and the client polls `tasks/get` → `tasks/result`; the status sequence is documented in the returned report as `working` → (optionally `input_required`) → `completed` (`src/everything/tools/simulate-research-query.ts:186-192`). It declares `execution: { taskSupport: "required" }` (`:251`), so it cannot be called synchronously.
  3. *Client-side tasks (bidirectional)* — `trigger-sampling-request-async` / `trigger-elicitation-request-async` invert the relationship: the **server** polls the **client**'s `tasks/get` and `tasks/result` (`src/everything/tools/trigger-sampling-request-async.ts:44-47`, `src/everything/tools/trigger-elicitation-request-async.ts:31-36`) with fixed budgets (60 attempts × 1 s for sampling, 600 × 1 s for elicitation).
- **Error-as-protocol-signal**: `trigger-url-elicitation` with `errorPath: true` throws `UrlElicitationRequiredError` carrying **MCP error code -32042** (`src/everything/tools/trigger-url-elicitation.ts:28`, `:42`, `:87`). The tool keeps a `Set<string>` of already-issued error-path keys so that the client's retry is recognized and proceeds via the request path instead of looping forever (`src/everything/tools/trigger-url-elicitation.ts:53-70`). The comment at `:63-69` explicitly flags this as a demo simplification that leaks entries and would need TTL eviction in production.
- Literal error strings: `` `Unknown outputType: ${outputType}` `` (`src/everything/tools/gzip-file-as-resource.ts:123`), `` `Invalid resourceType: … Must be Text or Blob.` `` (`src/everything/tools/get-resource-reference.ts:60-62`), `` `Unknown resource: ${uri}` `` (`src/everything/resources/templates.ts:140`). Launcher errors: `` `Unknown transport: ${scriptName}` `` (`src/everything/index.ts:29`) and `"Error running script:"` (`:37`).
- Cleanup is explicit and session-scoped: `cleanup(sessionId)` stops simulated logging and resource updates, cleans task-store timers, and clears the roots-sync timeout (`src/everything/server/index.ts:109-116`). The roots sync is deliberately deferred by 350 ms after `oninitialized` "otherwise, the request gets lost" (`src/everything/server/index.ts:99-103`).

---

## Cross-cutting notes for mocking

- **The minimal faithful tool response is a content array of text blocks, nothing more.** Every one of these 7 servers ultimately returns `{"content": [{"type": "text", "text": "..."}]}`. The plainest examples: git's `[TextContent(type="text", text="Files staged successfully")]` (`src/git/src/mcp_server_git/server.py:153` + `:533-538`) and everything's `{content:[{type:"text", text:"Echo: <message>"}]}` (`src/everything/tools/echo.ts:36-38`). A mock that emits only that shape is protocol-valid for all of them.
- **Content blocks beyond text, and where to find one of each:** `image` (`src/everything/tools/get-tiny-image.ts:41-45`, and `filesystem`'s `read_media_file` at `src/filesystem/index.ts:304`), `audio` (`src/filesystem/index.ts:306`), `resource` — embedded, carrying `text` or `blob` (`src/everything/tools/gzip-file-as-resource.ts:111-116`; `src/filesystem/index.ts:307-310`), `resource_link` (`src/everything/tools/get-resource-links.ts:71-81`; `src/everything/resources/session.ts:79`). Note `filesystem`'s comment that `type:"blob"` is **not** a valid content block and non-image/audio binaries must be wrapped as an embedded resource (`src/filesystem/index.ts:298-301`).
- **`structuredContent` is duplicated, not substituted.** Servers that declare an `outputSchema` return the human-readable text *and* the machine-readable object side by side: `src/filesystem/index.ts:207-210`, `src/memory/index.ts:298-301`, `src/everything/tools/get-structured-content.ts:87-90`, `src/sequentialthinking/index.ts:118-121`. A mock returning only `structuredContent` would break older clients, which is exactly what the "backwardCompatibleContentBlock" naming at `src/everything/tools/get-structured-content.ts:82-85` is guarding against.
- **`isError` is almost never used; errors are thrown and become protocol errors.** Only `sequentialthinking` constructs an `isError: true` payload (`src/sequentialthinking/lib.ts:86-97`), and even there the error path drops `structuredContent` (`src/sequentialthinking/index.ts:111-113`). All TypeScript servers throw plain `Error`; the Python servers either throw (`ValueError`/`BadName`) or raise `McpError(ErrorData(code=…, message=…))`. Mocking realistic failure means emitting a JSON-RPC error, not a content payload with a flag.
- **The three Python servers disagree on error propagation, and it matters.** `git` runs with `raise_exceptions=True` (`src/git/src/mcp_server_git/server.py:602`) so exceptions surface; `fetch` runs with `raise_exceptions=False` (`src/fetch/src/mcp_server_fetch/server.py:288`) so they are swallowed; `time` passes neither and additionally re-wraps *every* exception into `ValueError(f"Error processing mcp-server-time query: {str(e)}")` (`src/time/src/mcp_server_time/server.py:215-216`), producing doubly-nested messages. Do not assume a uniform error envelope across Python MCP servers.
- **Python vs TypeScript schema authoring differ structurally.** Python servers build a `Tool(name=…, description=…, inputSchema=<Model>.model_json_schema(), annotations=ToolAnnotations(...))` list inside a `@server.list_tools()` handler and dispatch by name in a `match` block — see `src/git/src/mcp_server_git/server.py:321-456` + `:497-598` and `src/fetch/src/mcp_server_fetch/server.py:197-207` + `:223-255`. This means the wire schema is whatever pydantic emits (`$defs`, `title`, `anyOf` for `Optional`), and defaults live in the model rather than the handler. TypeScript servers instead call `server.registerTool(name, {inputSchema: <zod shape>, outputSchema, annotations}, handler)` — one call per tool, schema and handler co-located (`src/filesystem/index.ts:213`, `src/memory/index.ts:277`, `src/everything/tools/echo.ts:34`). `time` is the outlier that hand-writes raw JSON Schema dicts (`src/time/src/mcp_server_time/server.py:135-144`).
- **Annotations are declared but not always honest.** `time`'s `get_current_time` claims `idempotentHint=True` (`src/time/src/mcp_server_time/server.py:148`); `sequentialthinking` claims `readOnlyHint: true` while mutating in-process history (`src/sequentialthinking/index.ts:95`); `fetch` declares no annotations at all (`src/fetch/src/mcp_server_fetch/server.py:200-206`). Treat annotations as hints for UI, never as an authorization boundary.
- **These reference servers have no auth, no rate limits, and (with one exception) no pagination.** Not one of the 7 reads a token, API key, or `Authorization` header. `fetch`'s `start_index`/`max_length` (`src/fetch/src/mcp_server_fetch/server.py:155-171`, continuation hint at `:254`) is the *only* pagination in the repo, and it is offset-based with the cursor embedded in prose rather than a `nextCursor` field. Vendor servers you mock against will differ on all three axes: expect opaque cursors, 401/403 refresh flows, and 429 backoff — none of which have a template here.
- **Sandboxing, where it exists, is a path-containment check and nothing more.** `filesystem` resolves symlinks then checks `startsWith(dir + path.sep)` (`src/filesystem/path-validation.ts:84`) and fails closed with `Access denied - path outside allowed directories: <abs> not in <list>` (`src/filesystem/lib.ts:110`); `git` does the same with `Path.relative_to` but **skips the check entirely** when no `--repository` was passed (`src/git/src/mcp_server_git/server.py:254-255`). `memory`, `time`, `sequentialthinking` and `everything` have no path sandbox at all — and `everything`'s `get-env` returns the full environment (`src/everything/tools/get-env.ts:34`).
- **Roots are handled inconsistently and are worth pinning down per server.** `filesystem` treats client roots as authoritative and *replaces* the CLI allow-list on both initialization and `roots/list_changed` (`src/filesystem/index.ts:724-746`). `everything` merely reports roots via `get-roots-list` and syncs on a 350 ms delay (`src/everything/server/index.ts:99-103`). `git` has roots-discovery code that is never called (`src/git/src/mcp_server_git/server.py:458-485`). A mock that assumes uniform roots semantics will be wrong for at least one of them.
- **Notifications a faithful mock may need to emit:** `notifications/progress` (`src/everything/tools/trigger-long-running-operation.ts:57-60`), `notifications/resources/updated` gated on an actual subscription (`src/memory/index.ts:270-274`; `src/everything/tools/toggle-subscriber-updates.ts:53`), `notifications/message` for logging (`src/everything/tools/toggle-simulated-logging.ts:50`), and `tools/list_changed` implied by `everything`'s post-initialization conditional registration (`src/everything/server/index.ts:54-56`, `:97`).
