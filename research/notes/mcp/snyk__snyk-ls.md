# snyk/snyk-ls — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/snyk__snyk-ls` @ git commit `1cf40fc` (2026-08-07), read 2026-08-11
**Language / framework:** Go (LSP language server). MCP dependency: `github.com/snyk/studio-mcp v1.6.1` (`go.mod:38`), which itself uses `github.com/mark3labs/mcp-go v0.31.0` (`go.mod:103`, marked `// indirect`).

## ⚠️ Headline finding: the MCP tool definitions are NOT in this repo

`mcp_extension/README.md:1-3` is the entire contents of the MCP extension directory:

```
# Snyk MCP
Implementation has been moved to https://github.com/snyk/studio-mcp.
```

The only MCP code left in `snyk-ls` is `internal/mcp/mcp_config.go` (99 lines) — a **configuration workflow**, not a tool server. It invokes `mcpconfig.WORKFLOWID_MCP_CONFIG` from the external `studio-mcp` module to write MCP server config into the user's IDE (`internal/mcp/mcp_config.go:92`), and notifies the IDE via a `$/snyk.registerMcp` LSP notification carrying `{command, args, env}` (`internal/mcp/mcp_config.go:43-50`; notification documented at `README.md:262-274`).

**Therefore an exact, source-verified tool inventory for the Snyk MCP server cannot be produced from this corpus repo.** It would require cloning `github.com/snyk/studio-mcp`. Everything below is what *this* repo genuinely evidences; nothing is inferred from memory.

---

## Full tool list — PARTIAL, 4 tool names verifiable from this repo

These four names appear as literal strings in this repository's own documentation and agent instructions, i.e. they are the names Snyk's own tooling tells an agent to call:

| Tool | R/W | Purpose | Source |
|------|-----|---------|--------|
| `snyk_auth` | W (side effect: starts an auth flow) | "Invoke the `snyk_auth` tool to authenticate the user to the Snyk platform." | `llms-install.md:43` |
| `snyk_trust` | W (side effect: marks a folder trusted) | "invoke the `snyk_trust` tool with the path to the current project's directory to confirm the user trusts Snyk to perform security scans of its contents." | `llms-install.md:43` |
| `snyk_sca_scan` | R (scan) | Software Composition Analysis / open-source dependency scan. Takes an **absolute project directory path** as a parameter. | `AGENT.md:70-72` |
| `snyk_code_scan` | R (scan) | Static application security testing (Snyk Code) scan. Takes an **absolute project directory path** as a parameter. | `AGENT.md:70`, `:72` |

`AGENT.md:69-72` (the repo's own agent guidance) states the calling contract:
> "determine the absolute path of the project directory. you can do that e.g. by executing `pwd` on the shell within the directory."
> "pass the absolute path of the project directory as a parameter to `snyk_sca_scan` and `snyk_code_scan`."
> "run `snyk_sca_scan` after updating go.mod"
> "run `snyk_sca_scan` and `snyk_code_scan` before committing. if not test data, fix issues before committing."

Container and IaC scan tools are **NOT DETERMINED FROM SOURCE** — no literal tool names for them exist in this repo. Do not assume `snyk_container_scan` / `snyk_iac_scan` exist without checking `snyk/studio-mcp`.

## Key tools table
NOT DETERMINED FROM SOURCE — parameter schemas and return shapes live in `github.com/snyk/studio-mcp`, which is not vendored here (`licenses/github.com/snyk/studio-mcp/` contains only a `LICENSE` file). Only the "absolute directory path" parameter of the two scan tools is evidenced (`AGENT.md:70`).

## Relationship to the Language Server and the CLI

Three distinct Snyk surfaces, easy to conflate:

1. **Snyk CLI** — the binary. The MCP server is shipped *as part of the CLI*: `llms-install.md:14` — "As part of the Snyk CLI, this server allows AI agents to autonomously run Snyk's vulnerability scans…". Launch command is `snyk mcp -t stdio` (`llms-install.md:20-26`; also `README.md:269` shows `"args": [ "mcp", "-t", "stdio" ]`).
2. **snyk-ls (this repo)** — the LSP server for IDE plugins. It *configures* the MCP server for the IDE but does not serve MCP tools.
3. **snyk/studio-mcp** — the actual MCP tool implementations (external module).

So in practice: `MCP client → snyk CLI (mcp subcommand) → Snyk CLI scan commands / Snyk API`. `snyk-ls` runs alongside as the IDE integration and, per `llms-install.md:14`, the MCP server "work[s] alongside existing Snyk IDE plugins".

## Resources
NOT DETERMINED FROM SOURCE (implementation is external).

## Prompts
NOT DETERMINED FROM SOURCE. Note that `internal/mcp/mcp_config.go` also configures **agent rules** ("Secure at Inception"), which is a prompt-adjacent surface: modes `On Code Generation` / `Smart Scan` / `Manual` (`internal/mcp/mcp_config.go:34-38`), mapped to `RuleTypeAlwaysApply` / `RuleTypeSmart` (`:71-75`), written at `RulesGlobalScope` (`:86`). `Manual` mode triggers a **removal** of the rules while explicitly never removing the MCP server config itself (`:77-84`).

## Auth model
- **Interactive**, via the `snyk_auth` tool, not an env var supplied by the MCP client (`llms-install.md:43`). This is unusual and important: the agent must trigger a browser/device auth flow.
- The language server side uses `SNYK_TOKEN` and `SNYK_API` (endpoint, default `https://api.snyk.io`) — evidenced in tests: `application/server/server_smoke_test.go:69-71`, `:1867`, `:2455-2456`.
- **Folder trust is a second, separate gate.** Scans only run on trusted folders. `internal/mcp/mcp_config.go:52-65` reads `types.SettingTrustedFolders`, joins the paths with `;` and passes them as `mcpTypes.TrustedFoldersParam`; the workspace's own `GetFolderTrust()` bounds which folders get configured at all (`:64-65`). `snyk_trust` is the tool that grants it (`llms-install.md:43`).
- Org / scopes: NOT DETERMINED FROM SOURCE for the MCP path.

## Pagination
**None, by design.** These are CLI-invoked scans, not paged list APIs — a scan returns one whole result document for one directory. There is no `limit`, `offset`, `cursor`, or page parameter anywhere in the MCP-related code in this repo. Consequence for a huge monorepo scan: the entire JSON result is produced in one shot; no truncation mechanism is evidenced here.

## Rate limits
None found in this repo for the MCP path.

## Error shapes — exit-code semantics (the important part)

Snyk's CLI **exits non-zero when it finds vulnerabilities**, so "failure" and "found issues" must be distinguished by exit code. `snyk-ls` documents and implements exactly this, and any faithful mock must reproduce it. From `infrastructure/oss/cli_scanner.go:559-586`:

```
// Exit codes
//  Possible exit codes and their meaning:
//
//  0: success, no issues found
//  1: action_needed, issues found
//  2: failure, try to re-run command
//  3: failure, no supported projects detected
```
Handling (`cli_scanner.go:570-581`):
- **1** → `return false, nil` — *not an error*; parse the results.
- **2** → logged as an error and surfaced to the user via `notifier.SendErrorDiagnostic(path, err)`, deliberately **not** sent to Sentry ("we want a user notification, but don't want to send it to sentry", `:575`).
- **3** → debug-level only: "no supported projects/files detected." (`:578`).
- anything else → error reported as an issue (`:580`).

IaC follows the same convention with its own threshold (`infrastructure/iac/iac.go:249-250`): `const iacIssuesExitCode = 1; if errorType.ExitCode() > iacIssuesExitCode { // Exit code > 1 == CLI has errors`. On a real error it builds the message as stdout **plus** stderr: `errorOutput := string(res) + "\n\n\nSTDERR output:\n" + string(exitError.Stderr)` and wraps it as `Error executing %v.\n%s` (`iac.go:266-268`). It also has an *ignorable error codes* allowlist — if every result's `ErrorCode` is ignorable it returns empty scan results instead of an error (`iac.go:251-260`).

CLI errors are otherwise parsed as JSON into a `cliError` struct, falling back to raw stdout as `ErrorMessage` when unmarshalling fails (`cli_scanner.go:549-554`).

Generic CLI execution from the IDE returns a structured `{ ..., "exitCode": <int> }` (`domain/ide/command/execute_cli.go:47`, `:83-89`).

## Not exposed (E3)
Because the tool set is (at least) `snyk_auth`, `snyk_trust`, `snyk_sca_scan`, `snyk_code_scan`, the MCP surface is **scan-and-authenticate only**. Nothing in this repo evidences MCP tools for the Snyk **platform REST API**, i.e. no:
- listing issues/projects/targets across an org (the org-wide vulnerability backlog),
- ignore / policy management (creating or approving an ignore, setting a policy),
- `snyk monitor` (snapshotting a project into the platform for continuous monitoring),
- SBOM / AI-BOM generation, license reports, or Snyk Learn content,
- org/group/user administration, integrations, or webhooks,
- fix-PR creation (Snyk's Fix PR / upgrade PR feature).

This makes the Snyk MCP surface **local and point-in-time**: it answers "what is wrong with this directory right now", not "what is our security posture" or "what did we agree to ignore". Note the caveat that these absences are inferred from the *absence of tool names in this repo* — confirm against `snyk/studio-mcp` before treating as definitive.

## Notes for mocking
1. **Do not model Snyk as a queryable issue database over MCP.** The evidenced surface is "scan this absolute path and return findings". Org-level questions ("how many criticals do we have across all repos?") have no MCP answer here.
2. **Two gates before any scan works:** `snyk_auth` (interactive) then `snyk_trust <abs path>`. An unauthenticated or untrusted-folder call is a realistic, high-frequency failure to simulate (`llms-install.md:43`; trust plumbing at `internal/mcp/mcp_config.go:52-65`).
3. **Absolute paths only.** `AGENT.md:69-70` instructs the agent to run `pwd` first. Relative-path calls are a realistic failure.
4. **Exit code 1 means "issues found", not "failed".** This is the single most important behaviour to reproduce — 0/1/2/3 map to success / issues-found / retryable-failure / no-supported-projects (`infrastructure/oss/cli_scanner.go:561-566`).
5. Underlying CLI invocations, for shaping realistic output: OSS is `snyk test --json …` (`infrastructure/oss/cli_scanner.go:403-404`); IaC is `snyk iac test <path> --json` (`infrastructure/iac/iac.go:330`). Output is CLI JSON.
6. **Severity ladder is 4 levels**: `Critical, High, Medium, Low` (`internal/types/issues.go:33-36`, string map at `:54`). Not CVSS-numeric at the top level.
7. **Products are distinct scan domains**: `ProductCode`, `ProductOpenSource`, `ProductInfrastructureAsCode`, `ProductSecrets` (`internal/types/config_resolver.go:532-538`). SCA and Code are separate tools with separate result shapes — an agent must run both.
8. Real errors carry **stdout + a `STDERR output:` section** concatenated into one message (`infrastructure/iac/iac.go:266`) — verbose, multi-KB error text is realistic.
9. IaC has an **ignorable-error-code allowlist** that converts some failures into an empty (successful) result set (`infrastructure/iac/iac.go:251-260`) — a nice source of "the scan said nothing was wrong but actually it errored" ambiguity.
10. The MCP server is launched as `snyk mcp -t stdio` from the CLI binary (`llms-install.md:20-26`, `README.md:269`) — model it as a locally-executed process, not a hosted HTTP service.
11. **To complete this inventory**, clone `github.com/snyk/studio-mcp` (v1.6.1 per `go.mod:38`) and read its `mcp-go` tool registrations.
