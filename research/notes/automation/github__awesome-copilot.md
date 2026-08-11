# github/awesome-copilot — source-grounded research notes

## Source

- **Repo path:** `/Users/samuelchien/dev/software-devops/research/repos/automation/github__awesome-copilot/`
- **Git remote:** `https://github.com/github/awesome-copilot.git` (fetch + push)
- **HEAD:** `git -C <path> log -1 --format='%H %ad %s'` →
  `35b7b9b0ece5ef92fd0f4c91944f56be9ab8b675 Tue Aug 11 04:02:14 2026 +0000 Add external plugin apify (#2619)`

### Important structural correction to the task brief

The brief listed `prompts?` and `chatmodes?` as possible top-level dirs. **Neither exists at this HEAD**, and there is no `collections/` dir either. Verified:

```
$ find . -path ./.git -prune -o -type f -name '*.md' -print | sed 's/.*\///' \
    | grep -oE '\.[a-z0-9]+\.md$' | sort | uniq -c | sort -rn
 226 .agent.md
 193 .instructions.md
   1 .workflows.md   1 .template.md   1 .skills.md   1 .plugins.md
   1 .hooks.md       1 .agents.md
```

Zero `.prompt.md` and zero `.chatmode.md` files exist. The repo has consolidated onto five artifact primitives: **agents, instructions, skills, hooks, workflows**, bundled by **plugins**. `README.md:19-27` confirms this ("A community-created collection of custom agents, instructions, skills, hooks, workflows, and plugins"). Legacy chatmode content survives only as prose — e.g. `instructions/ms-sql-dba.instructions.md:6` still says "MS-SQL DBA **Chat Mode** Instructions".

Top-level dirs actually present: `agents/ instructions/ skills/ plugins/ hooks/ workflows/ extensions/ cookbook/ docs/ eng/ website/ .schemas/ .github/`.

---

## 1. Agent tool surface

This repo ships **no runtime**. `package.json` scripts are all build/validate/generate (`eng/update-readme.mjs`, `eng/generate-marketplace.mjs`, `eng/validate-skills.mjs`, `eng/validate-plugins.mjs`). The "tool surface" is entirely **declarative `tools:` frontmatter** consumed by VS Code / Copilot CLI.

### Extraction method

`tools:` appears in **160** of 224 `agents/*.agent.md` (146 inline `[...]` arrays, 17 block YAML lists), **1** instructions file, and **11** `SKILL.md` files (as `allowed-tools:`). Extractor (awk, handles both inline and block YAML, strips quotes/brackets, splits on commas) written to scratchpad; results:

```
TOTAL tool references: 1518
DISTINCT identifiers:   187
namespaced (contain '/'): 539   flat: 979   wildcard-bearing ('*'): 30
DISTINCT after stripping namespace: 145
```

### Distinct tool identifiers with frequency (agents/*.agent.md)

Head of the tally — note the repo is mid-migration between **two naming generations**: flat VS Code tool ids (`codebase`, `editFiles`) and namespaced group ids (`search/codebase`, `edit/editFiles`, `execute/runTests`). Both forms coexist.

| n | identifier | | n | identifier |
|---|---|---|---|---|
| 116 | `search` | | 27 | `runTasks` |
| 87 | `edit/editFiles` | | 27 | `fetch` |
| 68 | `codebase` | | 27 | `execute/getTerminalOutput` |
| 51 | `githubRepo` | | 26 | `search/codebase` |
| 48 | `web/fetch` | | 26 | `read/problems` |
| 42 | `runCommands` | | 25 | `terminalLastCommand` |
| 42 | `problems` | | 25 | `edit` |
| 33 | `usages` | | 24 | `new` |
| 33 | `findTestFiles` | | 24 | `extensions` |
| 31 | `read` | | 22 | `vscodeAPI` |
| 30 | `execute/runInTerminal` | | 21 | `terminalSelection` |
| 29 | `read/terminalLastCommand` | | 20 | `terminalCommand` |
| 29 | `changes` | | 20 | `searchResults` |
| 28 | `runTests` | | 18 | `todo` |
| 28 | `read/terminalSelection` | | 16 | `web`, `search/usages`, `execute`, `agent` |
| 28 | `openSimpleBrowser` | | 15 | `microsoft.docs.mcp` |
| 27 | `testFailure` | | 14 | `read/readFile` |

Mid-tail: `vscode/memory` 12, `execute/testFailure` 12, `search/searchResults` 11, `vscode` 10, `shell` 9, `github/*` 9, `execute/runTests` 9, `execute/createAndRunTask` 9, `runNotebooks` 8, `execute/runTask` 8, `editFiles` 8, `runCommands/terminalSelection` 7, `runCommands/terminalLastCommand` 7, `vscode/vscodeAPI` 6, `vscode/runCommand` 6, `vscode/extensions` 6, `vscode/newWorkspace` 5, `vscode/installExtension` 5, `vscode/getProjectSetupInfo` 5, `read/getTaskOutput` 5, `search/fileSearch` 4, `azure_get_schema_for_Bicep` 4, `azure_get_deployment_best_practices` 4.

Normalized (last path segment) top identifiers — the true capability surface:
`search` 117, `editFiles` 95, `codebase` 94, `fetch` 75, `problems` 68, `terminalLastCommand` 61, `terminalSelection` 56, `githubRepo` 54, `usages` 49, `runCommands` 42, `testFailure` 39, `runTests` 37, `findTestFiles` 33, `searchResults` 31, `read` 31, `runInTerminal` 30, `openSimpleBrowser` 30, `extensions` 30, `changes` 30, `*` 30, `vscodeAPI` 28, `runTasks` 27, `getTerminalOutput` 27.

**MCP tool names referenced in `tools:`** (long tail, count 1–15 each):
`microsoft.docs.mcp` (15), `microsoft.docs.mcp/*` (2), `mslearnmcp/*`, `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft-docs`, `Microsoft Docs` (3);
`github/*` (9) plus explicit GitHub MCP verbs `github/get_file_contents`, `github/create_pull_request`, `github/create_branch`, `github/create_or_update_file`, `github/list_commits`, `github/search_code`, `github/issue_read`, `github/list_branches`, `github/get_pull_request` …;
`azure-mcp/*` (3), `azure-mcp/bicepschema`, `azure-mcp/azureterraformbestpractices`, `azure_query_learn` (3), `azure_design_architecture` (2), `azure_get_swa_best_practices` (2);
`terraform` (3), `terraform/*`, `terraform.mcp/*`, `context7` (3), `context7/*`, `playwright`, `atlassian`, `pagerduty/*`, `outagedeck/*`, `opik/*`, `new-relic-mcp-server/*`, `elastic-mcp/*`, `stackhawk-mcp/*`, `sfdx-mcp/*`, `DiffblueCover/*`, `lingo/*`, `bgpt/*`, `figma-dev-mode-mcp-server` (2), `pulumi-mcp/get-type`;
DB MCP verbs: `pgsql_connect`, `pgsql_query`, `pgsql_modifyDatabase`, `pgsql_bulkLoadCsv`, `pgsql_visualizeSchema` … (10 pgsql_*), `mssql_connect`/`mssql_query`/… (6 mssql_*), `neo4j-local/neo4j-local-write_neo4j_cypher` and 2 siblings;
VS Code extension-scoped: `ms-python.python/configurePythonEnvironment` (+3 siblings), `ms-toolsai.jupyter/configureNotebook` (+2), `ms-azuretools.vscode-containers/containerToolsConfig`, `ms-azuretools.vscode-azure-github-copilot/azure_query_azure_resource_graph` (2), `github.vscode-pull-request-github/*` (7 distinct verbs), `vscode.mermaid-chat-features/renderMermaidDiagram`.

Bare `'*'` (grant everything) appears **twice** as a whole-value; wildcard-bearing entries total 30.

Example, `agents/tdd-green.agent.md:4` — the namespaced style:

```yaml
tools: ['github/*', 'search/fileSearch', 'edit/editFiles', 'execute/runTests', 'execute/runInTerminal', 'execute/getTerminalOutput', 'execute/testFailure', 'read/readFile', 'read/terminalLastCommand', 'read/terminalSelection', 'read/problems', 'search/codebase']
```

And `agents/accessibility-runtime-tester.agent.md:5` — the flat style:

```yaml
tools: ['codebase', 'search', 'fetch', 'findTestFiles', 'problems', 'runCommands', 'runTasks', 'runTests', 'terminalLastCommand', 'terminalSelection', 'testFailure', 'openSimpleBrowser']
```

### `mcp.json` (repo root, 306 bytes)

Only **one** server, and it is for the repo's own maintenance, not for the shipped artifacts:

```json
{
  "mcpServers": {
    "github-agentic-workflows": {
      "type": "local",
      "command": "gh",
      "args": ["aw", "mcp-server"],
      "tools": ["compile", "audit", "logs", "inspect", "status", "audit-diff"]
    }
  }
}
```

Path: `/Users/samuelchien/dev/software-devops/research/repos/automation/github__awesome-copilot/mcp.json`. `AGENTS.md:345` documents it under "## MCP Server".

### `hooks/` — 8 hooks, event-driven shell interception

Each hook = folder with `README.md` (frontmatter: `name`, `description`, `tags`) + `hooks.json` + scripts. Events observed across all 8 `hooks/*/hooks.json`: **`preToolUse`, `postToolUse`, `sessionStart`, `sessionEnd`, `userPromptSubmitted`**. Schema is `{"version":1,"hooks":{<event>:[{"type":"command","bash":…,"powershell":…,"cwd":…,"env":{…},"timeoutSec":N}]}}`.

| hook | events | mode env | timeout |
|---|---|---|---|
| `hooks/tool-guardian/` | preToolUse | `GUARD_MODE=block` | 10s |
| `hooks/attester-import-check/` | preToolUse | `ATTESTER_MODE=block` | 30s |
| `hooks/secrets-scanner/` | sessionEnd | `SCAN_MODE=warn`, `SCAN_SCOPE=diff` | 30s |
| `hooks/dependency-license-checker/` | sessionEnd | `LICENSE_MODE=warn` | 60s |
| `hooks/fix-broken-links/` | postToolUse | — (bash + powershell variants) | 120s |
| `hooks/governance-audit/` | sessionStart, sessionEnd, userPromptSubmitted | `GOVERNANCE_LEVEL=standard`, `BLOCK_ON_THREAT=false` | 5s/5s/10s |
| `hooks/session-logger/` | sessionStart, sessionEnd, userPromptSubmitted | `LOG_LEVEL=INFO` | 5s |
| `hooks/session-auto-commit/` | sessionEnd | — | 30s |

`hooks/tool-guardian/README.md:1-5,13-20` is the clearest statement of what a hook exposes:

```markdown
---
name: 'Tool Guardian'
description: 'Blocks dangerous tool operations (destructive file ops, force pushes, DB drops) before the Copilot coding agent executes them'
tags: ['security', 'safety', 'preToolUse', 'guardrails']
---
...
AI coding agents can autonomously execute shell commands, file operations, and database queries. Without guardrails, a misinterpreted instruction could lead to irreversible damage. This hook intercepts every tool invocation at the `preToolUse` event and scans it against ~20 threat patterns across 6 categories:

- **Destructive file ops**: `rm -rf /`, deleting `.env` or `.git`
- **Destructive git ops**: `git push --force` to main/master, `git reset --hard`
- **Database destruction**: `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, `DELETE FROM` without `WHERE`
- **Permission abuse**: `chmod 777`, recursive world-writable permissions
- **Network exfiltration**: `curl | bash`, `wget | sh`, uploading files via `curl --data @`
- **System danger**: `sudo`, `npm publish`
```

Backing implementation, `hooks/tool-guardian/guard-tool.sh:99`:

```bash
"destructive_git_ops:::critical:::git push --force.*(main|master):::Use 'git push --force-with-lease' or push to a feature branch"
```

### `workflows/` — 8 GitHub Agentic Workflows

Compiled to `.lock.yml` GitHub Actions via `gh aw compile` (`docs/README.workflows.md:11-12`). The exposed surface is **`permissions` + `tools` + `safe-outputs` + `network` + `timeout-minutes`** — a genuinely capability-scoped model, not free-form. Every one of the 8 grants only **read** permissions and routes all writes through `safe-outputs`.

Full frontmatter, `workflows/daily-issues-report.md:1-13`:

```yaml
---
name: "Daily Issues Report"
description: "Generates a daily summary of open issues and recent activity as a GitHub issue"
on:
  schedule: daily on weekdays
permissions:
  contents: read
  issues: read
safe-outputs:
  create-issue:
    title-prefix: "[daily-report] "
    labels: [report]
---
```

Richer example, `workflows/weekly-comment-sync.md:1-30` (note `draft: true`, `if-no-changes: warn`, `fallback-as-issue: false`):

```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
engine: copilot
tools:
  github:
    toolsets: [default]
  bash: true
safe-outputs:
  create-pull-request:
    max: 1
    title-prefix: "[ai] "
    labels: [automation]
    draft: true
    if-no-changes: warn
    fallback-as-issue: false
timeout-minutes: 20
```

`workflows/ospo-org-health.md:34-38` additionally declares an egress allowlist:

```yaml
network:
  allowed:
    - defaults
    - python
```

`workflows/relevance-check.md:4-7` gates a slash command by role:

```yaml
on:
  slash_command:
    name: relevance-check
  roles: [admin, maintainer, write]
```

GitHub toolsets referenced across workflows: `repos`, `issues`, `pull_requests`, `orgs`, `users`, `default`; plus `bash: true`. `safe-outputs` verbs used: `create-issue`, `add-comment`, `create-pull-request`.

---

## 2. System prompts / policy text — workflow discipline

Phrase frequencies across `agents/ instructions/ skills/ workflows/` (`--include='*.md'`, case-insensitive; `files` = files with ≥1 match, `occ` = total occurrences):

| phrase | files | occ | | phrase | files | occ |
|---|---|---|---|---|---|---|
| `do not` | 513 | 1548 | | `hallucinat` | 37 | 108 |
| `never` | 479 | 1489 | | `do not assume` | 32 | 35 |
| `don't` | 378 | 998 | | `human review` | 28 | 48 |
| `secrets` | 175 | 543 | | `do not proceed` | 23 | 42 |
| `ask the user` | 135 | 213 | | `never commit` | 21 | 21 |
| `pause` | 58 | 89 | | `confirm with` | 21 | 30 |
| `success criteria` | 53 | 97 | | `definition of done` | 14 | 21 |
| `stop and` | 49 | 69 | | `human-in-the-loop` | 9 | 15 |
| `destructive` | 49 | 58 | | `scope creep` | 8 | 9 |
| `acceptance criteria` | 45 | 111 | | `ask for confirmation` | 7 | 8 |
| `always verify` | 33 | 36 | | `before completing` | 6 | 6 |
| — | | | | `force push` | 5 | 5 |

### Verbatim quotes (verification / stopping / asking humans)

1. `agents/blueprint-mode.agent.md:18` —
   > `- Libraries/Frameworks: Never assume. Verify usage in project files (package.json, Cargo.toml, requirements.txt, build.gradle, imports, neighbors) before using.`
2. `agents/blueprint-mode.agent.md:22` —
   > `- Fact Based: No speculation. Use only verified content from files.`
3. `agents/blueprint-mode.agent.md:121` —
   > `- Max Iterations: 3. If unresolved after 3 attempts → mark task FAILED and log the final failing issue.`
4. `agents/salesforce-apex-triggers.agent.md:122` —
   > `- **DO NOT claim completion if verification fails** - Fix ALL issues first`
5. `agents/salesforce-apex-triggers.agent.md:26` (identical wording also at `agents/salesforce-visualforce.agent.md:37`, `agents/salesforce-aura-lwc.agent.md:26`, `agents/salesforce-flow.agent.md:42`) —
   > `**If you have ANY questions or uncertainties before or during implementation — STOP and ask the user first.**`
6. `agents/oracle-to-postgres-migration-expert.agent.md:97` —
   > `- If a checklist item is ambiguous or turns out to be more complex than expected, stop and ask the user before proceeding.`
7. `agents/oracle-to-postgres-migration-expert.agent.md:40` —
   > `If DDL artifacts are missing, stop and ask the user to provide them before proceeding — Phase 2 depends on them for schema-aware risk analysis.`
8. `agents/software-engineer-agent-v1.agent.md:99-104` —
   > `Escalate to a human operator ONLY when:` / `- **Hard Blocked**: An external dependency (e.g., a third-party API is down) prevents all progress.` / `- **Access Limited**: Required permissions or credentials are unavailable and cannot be obtained.` / `- **Critical Gaps**: Fundamental requirements are unclear, and autonomous research fails to resolve the ambiguity.` / `- **Technical Impossibility**: Environment constraints or platform limitations prevent implementation of the core task.`
9. `agents/tdd-green.agent.md:47` —
   > `3. **Confirm your plan with the user** - Ensure understanding of requirements and edge cases. NEVER start making changes without user confirmation`
10. `agents/dotnet-self-learning-architect.agent.md:30` —
    > `- Do not fabricate facts, logs, API behavior, or test outcomes.`
11. `agents/spark-performance.agent.md:140` —
    > `- Do not fabricate Spark UI metrics, data sizes, or cluster configs.`
12. `agents/terminal-helper.agent.md:27` —
    > `- Do not invent output. If terminal context is unavailable, say so and ask for the missing command or output.`
13. `agents/repo-architect.agent.md:197` —
    > `**Important:** Only suggest awesome-copilot resources when the MCP tools are detected. Do not hallucinate tool availability.`
14. `agents/kusto-assistant.agent.md:66` —
    > `- ALWAYS discover actual timestamp column names via schema inspection - never assume column names like TimeGenerated, Timestamp, etc.`
15. `agents/hlbpa.agent.md:187` —
    > `- **No Guessing**: Unknown values are marked TBD and surfaced in Information Requested.`
16. `agents/workshop-ta.agent.md:54` —
    > `- **Stop is a valid finish.** Zero output can be the correct answer.`
17. `instructions/clojure.instructions.md:88` —
    > `**Never edit code files when the REPL is unavailable.** When REPL evaluation returns errors indicating that the REPL is unavailable, stop immediately and inform the user. Let the user restore REPL before continuing.`
18. `instructions/dotnet-architecture-good-practices.instructions.md:32` —
    > `**If you cannot clearly explain these points, STOP and ask for clarification.**`
19. `instructions/spec-driven-workflow-v1.instructions.md:97` and `:189` —
    > `- **Do not proceed until all requirements are clear and documented.**` / `- **Do not proceed until all validation steps are complete and all issues are resolved.**`
20. `skills/azure-developer-cli/SKILL.md:134` —
    > `Do not claim deployment success unless the target environment was actually deployed and verified.`
21. `skills/import-infrastructure-as-code/SKILL.md:340` —
    > `- Do not claim successful import without listing discovered files and validation output.`
22. `skills/bug-reproduction-brief/SKILL.md:73` —
    > `- Do not claim a root cause from correlation alone.`
23. `skills/github-actions-efficiency/references/reporting.md:8` —
    > `- Do not claim exact time or cost savings without before/after run data.`
24. `skills/apple-appstore-reviewer/SKILL.md:38` —
    > `- Do not claim something exists unless you can point to evidence in code or config.`
25. `skills/autoresearch/SKILL.md:136` —
    > `Ask the user to confirm. Do not proceed until confirmed.`

**Counter-example worth flagging** — not all artifacts endorse stopping. `instructions/tasksync.instructions.md:54` and `:152`:

> `- **PRIMARY DIRECTIVE #10**: **NO CONVERSATION PAUSING** - Never pause, wait, or stop the conversation flow`
> `- **CRITICAL**: BEGIN immediate task request (do not wait for user input)`

and `agents/Thinking-Beast-Mode.agent.md:34`:

> `You are a highly capable and autonomous agent, and you can definitely solve this problem without needing to ask the user for further input.`

So the corpus contains directly contradictory autonomy policies; there is no repo-level arbitration between them.

---

## 3. Workflow / skill definitions — categories and counts

### 3a. Artifact-type inventory (filesystem, computed)

| directory | count | how counted | docs index claims | match? |
|---|---|---|---|---|
| `agents/` | **224** `*.agent.md` | `ls agents/*.agent.md \| wc -l` | `docs/README.agents.md` 224 table rows | ✅ |
| `instructions/` | **192** `*.instructions.md` | `ls instructions/*.instructions.md` (= all 192 files in dir) | `docs/README.instructions.md` 192 rows | ✅ |
| `skills/` | **406** top-level skill folders / `skills/*/SKILL.md` | `ls -d skills/*/SKILL.md` | `docs/README.skills.md` 406 rows | ✅ |
| `plugins/` | **92** folders with `plugin.json` | `find plugins -maxdepth 1 -type d \| tail -n +2` | `docs/README.plugins.md` 92 rows | ✅ |
| `workflows/` | **8** `*.md` | `ls workflows/*.md` | `docs/README.workflows.md` 8 rows | ✅ |
| `hooks/` | **8** folders | `find hooks -maxdepth 1 -type d \| tail -n +2` | `docs/README.hooks.md` 8 rows | ✅ |
| `extensions/` | 69 folders, 336 files | `find extensions -maxdepth 1 -type d` | not indexed in `docs/` | — |
| `cookbook/` | 90 files (49 `.md`), schema at `.schemas/cookbook.schema.json` | `find cookbook -type f` | `cookbook/README.md` | — |
| `eng/` | 39 files (build/validation scripts) | `find eng -type f` | `eng/README.md` | — |

**`prompts/`, `chatmodes/`, `collections/`: 0 — directories do not exist.**

### README vs filesystem — verified discrepancies

- `README.md` **no longer contains artifact tables at all**. Its only table is the 5-row "What's in this repo" pointer table (`README.md:21-27`); the rest is the all-contributors list (lines 56-561). The per-type index tables moved to `docs/README.{agents,instructions,skills,plugins,hooks,workflows}.md`. Counting `^| \[` rows per README heading yields **zero** artifact rows.
- All six `docs/README.*.md` row counts match the filesystem exactly (table above). No count drift found.
- **Real discrepancy 1:** `find` reports 226 `.agent.md` repo-wide but `agents/` holds 224. The extra two live inside a skill: `skills/quality-playbook/agents/quality-playbook.agent.md` and `skills/quality-playbook/agents/quality-playbook-claude.agent.md`. They are bundled skill assets, not indexed agents.
- **Real discrepancy 2:** `find` reports 193 `.instructions.md` but `instructions/` holds 192. The extra is `docs/README.instructions.md` — the index file itself is named with the artifact suffix, which any glob-based tooling on `**/*.instructions.md` would wrongly ingest.
- **Real discrepancy 3:** 421 `SKILL.md` files exist repo-wide but only **406** are indexed. 15 are nested sub-skills under two skill families, invisible to `docs/README.skills.md`:
  `skills/qdrant-scaling/scaling-data-volume/{tenant,vertical,horizontal}-scaling/SKILL.md`, `skills/qdrant-scaling/scaling-data-volume/sliding-time-window/SKILL.md`, `skills/qdrant-scaling/{minimize-latency,scaling-qps,scaling-query-volume,scaling-data-volume}/SKILL.md`, `skills/qdrant-performance-optimization/{memory-usage,indexing-performance,search-speed}-optimization/SKILL.md`, `skills/qdrant-monitoring/{debugging,setup}/SKILL.md`, `skills/qdrant-search-quality/{search-strategies,diagnosis}/SKILL.md`.
- **Real discrepancy 4 (schema violation):** 5 instructions files have **no YAML frontmatter whatsoever**, despite `CONTRIBUTING.md` requiring `description` + `applyTo`:
  `instructions/dataverse-python-{advanced-features,agentic-workflows,best-practices,file-operations,pandas-integration}.instructions.md` — each begins directly with `# Dataverse SDK for Python - …`. (Frontmatter key census: 185 `applyTo:`, 178 `description:` out of 192 files.)

### 3b. SWE/DevOps categorization

Method: regex classifier over `filename + description` frontmatter, run per artifact type. Categories are **non-exclusive** (an artifact can land in several — e.g. `terraform-iac-reviewer` is code review + IaC + planning), so category sums exceed directory totals. Script + full output in scratchpad; counts below are computed, not estimated.

#### Agents (n=224)

| category | n | filenames (`agents/…`) |
|---|---|---|
| code review | **9** | address-comments, agent-governance-reviewer, electron-angular-native, gem-reviewer, gilfoyle, quality-playbook, se-security-reviewer, se-system-architecture-reviewer, terraform-iac-reviewer |
| testing / TDD | **23** | accessibility, ai-team-qa, amplitude-experiment-implementation, apify-integration-expert, diffblue-cover, gem-browser-tester, gem-implementer, gem-implementer-mobile, gem-mobile-tester, laravel-expert-agent, playwright-tester, qa-subagent, react18-test-guardian, react19-dep-surgeon, react19-test-guardian, sast-sca-security-analyzer, stackhawk-security-onboarding, swe-subagent, **tdd-green, tdd-red, tdd-refactor**, terratest-module-testing, vuejs-expert |
| security & compliance | **21** | aws-cloud-expert, azure-policy-analyzer, centos-linux-expert, dynatrace-expert, elasticsearch-observability, expert-embedded-c-engineer, gem-reviewer, github-actions-expert, jfrog-sec, platform-sre-kubernetes, react18-auditor, react18-batching-fixer, sast-sca-security-analyzer, se-responsible-ai-code, se-security-reviewer, stackhawk-security-onboarding, taxcore-technical-writer, tdd-refactor, terraform, trojan-skill-hunter, wg-code-sentinel |
| incident response / debugging | **20** | aws-incident-triage, azure-verified-modules-owner-triage, blueprint-mode, cloud-saas-outage-triage, debug, devtools-regression-investigator, dynatrace-expert, elasticsearch-observability, frontend-performance-investigator, gem-debugger, mentoring-juniors, monday-bug-fixer, new-relic-incident-response, pagerduty-incident-responder, platform-sre-kubernetes, power-bi-performance-expert, qa-subagent, se-gitops-ci-specialist, spark-performance, swe-subagent |
| CI-CD & release | **23** | ai-team-qa, amplitude-experiment-implementation, apify-integration-expert, arch-linux-expert, arm-migration, azure-iac-generator, devops-expert, doublecheck, droid, dynatrace-expert, gem-devops, github-actions-expert, github-actions-node-upgrade, kubestellar-console, new-relic-incident-response, octopus-deploy-release-notes-mcp, platform-sre-kubernetes, python-win-arm64-gha-wheel-builder, react19-commander, sast-sca-security-analyzer, se-gitops-ci-specialist, stackhawk-security-onboarding, terraform |
| IaC / cloud / kubernetes | **33** | arm-migration, aws-cloud-expert, aws-incident-triage, aws-principal-architect, aws-serverless-architect, azure-iac-exporter, azure-iac-generator, azure-logic-apps-expert, azure-policy-analyzer, azure-principal-architect, azure-saas-architect, azure-smart-city-iot-architect, azure-verified-modules-bicep, azure-verified-modules-owner-triage, azure-verified-modules-terraform, bicep-implement, bicep-plan, devils-advocate, gem-devops, kubestellar-console, kusto-assistant, microsoft-study-mode, neo4j-docker-client-generator, platform-sre-kubernetes, python-notebook-sample-builder, sast-sca-security-analyzer, terraform-aws-implement, terraform-aws-planning, terraform-azure-implement, terraform-azure-planning, terraform-iac-reviewer, terraform, terratest-module-testing |
| observability | **10** | ai-readiness-reporter, comet-opik, devops-expert, dynatrace-expert, elasticsearch-observability, neon-optimization-analyzer, new-relic-incident-response, power-bi-performance-expert, power-bi-visualization-expert, prd |
| documentation & specs | **25** | address-comments, adr-generator, arch, atlassian-requirements-to-jira, azure-smart-city-iot-architect, azure-verified-modules-owner-triage, context7, dotnet-self-learning-architect, gem-documentation-writer, hlbpa, microsoft_learn_contributor, modernization, monday-bug-fixer, openapi-to-application, prd, project-architecture-planner, project-documenter, research-technical-spike, se-technical-writer, simple-app-idea-generator, software-engineer-agent-v1, specification, taxcore-technical-writer, tech-debt-remediation-plan, technical-content-evaluator |
| refactoring / modernization | **31** | arm-migration, azure-iac-exporter, centos-linux-expert, csharp-dotnet-janitor, dotnet-upgrade, gem-code-simplifier, gem-implementer, github-actions-node-upgrade, hlbpa, implementation-plan, janitor, launchdarkly-flag-cleanup, modernization, neon-migration-specialist, oracle-to-postgres-migration-expert, planner, react18-{auditor,class-surgeon,commander,dep-surgeon,test-guardian}, react19-{auditor,commander,dep-surgeon,migrator,test-guardian}, salesforce-expert, swe-subagent, tdd-refactor, tech-debt-remediation-plan, terratest-module-testing |
| architecture | **34** | Thinking-Beast-Mode, adr-generator, aem-frontend-specialist, api-architect, arch, arm-migration, aws-cloud-expert, aws-principal-architect, aws-serverless-architect, azure-principal-architect, azure-saas-architect, azure-smart-city-iot-architect, blueprint-mode, cast-imaging-software-discovery, clojure-interactive-programming, context-architect, declarative-agents-architect, demonstrate-understanding, dotnet-fullstack-mentor, dotnet-self-learning-architect, drupal-expert, expert-dotnet-software-engineer, gem-designer, gem-researcher, hlbpa, interview-prep, modernization, plan, project-architecture-planner, project-documenter, repo-architect, salesforce-visualforce, se-system-architecture-reviewer, technical-content-evaluator |
| planning / task breakdown | **27** | ai-readiness-reporter, ai-team-producer, arch, atlassian-requirements-to-jira, azure-verified-modules-owner-triage, bicep-plan, context-architect, devops-expert, gem-orchestrator, gem-planner, gem-reviewer, implementation-plan, modernization, monday-bug-fixer, one-shot-feature-issue-planner, plan, planner, prd, project-architecture-planner, qa-subagent, refine-issue, task-planner, tdd-green, tech-debt-remediation-plan, terraform-aws-planning, terraform-azure-planning, terraform-iac-reviewer |
| database / data | **13** | aws-cloud-expert, code-tour, elasticsearch-observability, mongodb-performance-advisor, ms-sql-dba, neo4j-docker-client-generator, neon-migration-specialist, neon-optimization-analyzer, oracle-to-postgres-migration-expert, postgresql-dba, power-bi-data-modeling-expert, power-platform-expert, power-platform-mcp-integration-expert |
| performance | **22** | adr-generator, arm-migration, aws-cloud-expert, caveman-mode, defender-scout-kql, dotnet-maui, dynatrace-expert, elasticsearch-observability, expert-react-frontend-engineer, frontend-performance-investigator, linkedin-post-writer, mongodb-performance-advisor, neon-optimization-analyzer, nuxt-expert, power-bi-{data-modeling,dax,performance}-expert, project-architecture-planner, se-system-architecture-reviewer, search-ai-optimization-expert, spark-performance, vuejs-expert |
| *(no SWE/DevOps category matched)* | 52 | language/persona agents (`CSharpExpert`, `expert-cpp-software-engineer`, 12× `*-mcp-expert`, 4× `*-linux-expert`, `mentor`, `prompt-engineer`, …) |

#### Instructions (n=187 with parseable frontmatter; 192 files)

| category | n | filenames (`instructions/…`) |
|---|---|---|
| code review | **2** | code-review-generic, gilfoyle-code-review |
| testing / TDD | **13** | dataverse-python-testing-debugging, github-actions-ci-cd-best-practices, java-junit5-assertions, nodejs-javascript-vitest, playwright-{dotnet,python,typescript}, power-bi-custom-visuals-development, powershell-pester-5, qa-engineering-best-practices, scala-spark, vue, wordpress |
| security & compliance | **10** | containerization-docker-best-practices, dataverse-python-authentication-security, github-actions-ci-cd-best-practices, kubernetes-deployment-best-practices, kubernetes-manifests, pcf-canvas-apps, power-bi-security-rls-best-practices, security-and-owasp, vue, wordpress |
| incident response / debugging | **1** | dataverse-python-testing-debugging |
| CI-CD & release | **9** | arch-linux, azure-devops-pipelines, github-actions-ci-cd-best-practices, java-11-to-java-17-upgrade, java-17-to-java-21-upgrade, java-21-to-java-25-upgrade, kubernetes-deployment-best-practices, power-bi-devops-alm-best-practices, scala-spark |
| IaC / cloud / kubernetes | **22** | ansible, aws-appsync, azure-apim-ai-gateway, azure-devops-pipelines, azure-durable-functions-csharp, azure-functions-csharp, azure-functions-typescript, azure-iot-edge-architecture, azure-logic-apps-power-automate, azure-naming, azure-verified-modules-bicep, azure-verified-modules-terraform, bicep-code-best-practices, containerization-docker-best-practices, convert-cassandra-to-spring-data-cosmos, convert-jpa-to-spring-data-cosmos, generate-modern-terraform-code-for-azure, kubernetes-deployment-best-practices, kubernetes-manifests, terraform-azure, terraform-sap-btp, terraform |
| observability | **4** | azure-apim-ai-gateway, copilot-thought-logging, devops-core-principles, power-bi-report-design-best-practices |
| documentation & specs | **15** | azure-iot-edge-architecture, context7, draw-io, exclude-prompt-data, localization, markdown-accessibility, markdown, memory-bank, playwright-python, power-platform-connector, r, self-explanatory-code-commenting, spec-driven-workflow-v1, update-docs-on-code-change, use-cliche-data-in-docs |
| refactoring / modernization | **8** | convert-cassandra-to-spring-data-cosmos, convert-jpa-to-spring-data-cosmos, dotnet-maui-9-to-dotnet-maui-10-upgrade, dotnet-upgrade, java-11-to-java-17-upgrade, java-17-to-java-21-upgrade, java-21-to-java-25-upgrade, springboot-4-migration |
| architecture | **4** | azure-iot-edge-architecture, dotnet-architecture-good-practices, gilfoyle-code-review, oop-design-patterns |
| planning / task breakdown | **1** | spec-driven-workflow-v1 |
| database / data | **19** | 11× `dataverse-python-*`, convert-cassandra-to-spring-data-cosmos, convert-jpa-to-spring-data-cosmos, declarative-agents-microsoft365, mongo-dba, ms-sql-dba, pcf-manifest-schema, power-apps-canvas-yaml, power-bi-data-modeling-best-practices, power-platform-connector, sql-sp-generation |
| performance | **11** | azure-apim-ai-gateway, caveman-mode, containerization-docker-best-practices, dataverse-python-performance-optimization, github-actions-ci-cd-best-practices, java-junit5-assertions, kubernetes-deployment-best-practices, nextjs, performance-optimization, scala-spark, vue |
| *(none matched)* | 103 | mostly language/framework style guides (`csharp`, `go`, `rust`, `svelte`, 12× `*-mcp-server`, 15× `pcf-*`) |

#### Skills (n=406)

| category | n | representative filenames (`skills/<name>/SKILL.md`) |
|---|---|---|
| code review | **18** | agentic-eval, ai-ready, apple-appstore-reviewer, audit-integrity, autoresearch, brag-sheet, code-tour, copilot-pr-autopilot, email-drafter, **github-actions-hardening**, landing-page-conversion-audit, **postgresql-code-review**, power-bi-model-design-review, quality-playbook, shopify-review-triage, **sql-code-review**, verify-agent-action, web-design-reviewer |
| testing / TDD | **37** | breakdown-test, csharp-{mstest,nunit,tunit,xunit}, java-junit, javascript-typescript-jest, pytest-coverage, pester-migration, pester-should-migration, playwright-{automation-fill-in-form,explore-website,generate-test}, react18-enzyme-to-rtl, spring-boot-testing, unit-test-vue-pinia, webapp-testing, mcp-release-qa, scoutqa-test, salesforce-apex-quality, creating-oracle-to-postgres-migration-integration-tests, … |
| security & compliance | **34** | agent-owasp-compliance, agent-skill-stack, agent-supply-chain, **codeql**, **secret-scanning**, **security-review**, dependabot, gdpr-compliant, **github-actions-hardening**, mcp-security-audit, mcp-implementation-security-review, threat-model-analyst, tm7-threat-model, data-breach-blast-radius, react-audit-grep-patterns, … |
| incident response / debugging | **47** | **incident-postmortem**, **aws-cloudwatch-investigation**, aws-resource-health-diagnose, azure-resource-health-diagnose, **bug-reproduction-brief**, arch-linux-triage, centos-linux-triage, debian-linux-triage, fedora-linux-triage, chrome-devtools, diagnose, power-bi-performance-troubleshooting, flowstudio-power-automate-debug, qdrant-monitoring, phoenix-cli, … |
| CI-CD & release | **55** | **devops-rollout-plan**, **azure-deployment-preflight**, azure-devops-cli, github-actions-efficiency, github-actions-hardening, github-actions-runtime-upgrade-conventions, github-release, conventional-branch, create-github-action-workflow-specification, publish-to-pages, doublecheck, mcp-deploy-manage-agents, python-pypi-package-builder, msstore-cli, foundry-agent-sync, … |
| IaC / cloud / kubernetes | **45** | aws-cdk-python-setup, aws-cost-optimize, aws-well-architected-review, az-cost-optimize, azure-architecture-autopilot, azure-container-registry-cli, azure-developer-cli, azure-well-architected-review, containerize-aspnetcore, containerize-aspnet-framework, **multi-stage-dockerfile**, import-infrastructure-as-code, terraform-azurerm-set-diff-analyzer, update-avm-modules-in-bicep, qdrant-deployment-options, … |
| observability | **33** | appinsights-instrumentation, arize-instrumentation, arize-evaluator, phoenix-tracing, aws-cloudwatch-investigation, copilot-usage-metrics, pr-dashboard, qdrant-monitoring, postgresql-optimization, sql-optimization, acreadiness-assess, … |
| documentation & specs | **80** | architecture-blueprint-generator, create-architectural-decision-record, create-specification, update-specification, create-readme, readme-blueprint-generator, create-technical-spike, csharp-docs, java-docs, documentation-writer, drawio, draw-io-diagram-generator, excalidraw-diagram-generator, plantuml-ascii, efcore-d2-db-diagram, conventional-commit, gen-specs-as-issues, folder-structure-blueprint-generator, technology-stack-blueprint-generator, … |
| refactoring / modernization | **64** | refactor, refactor-plan, refactor-method-complexity-reduce, review-and-refactor, doc-and-modernize, dotnet-upgrade, javax-to-jakarta-migration, java-refactoring-extract-method, java-refactoring-remove-parameter, 8× `migrating|creating|reviewing|planning|scaffolding-oracle-to-postgres-*`, 9× `react18-*`/`react19-*` pattern skills, qdrant-version-upgrade, winui3-migration-guide, … |
| architecture | **37** | acquire-codebase-knowledge, architecture-blueprint-generator, aws-well-architected-review, azure-well-architected-review, cloud-design-patterns, code-exemplars-blueprint-generator, dotnet-design-pattern-review, create-implementation-plan, breakdown-epic-arch, power-platform-architect, system-commandline-cli, threat-model-analyst, … |
| planning / task breakdown | **42** | breakdown-plan, breakdown-epic-arch, breakdown-epic-pm, breakdown-feature-prd, breakdown-feature-implementation, breakdown-test, create-implementation-plan, update-implementation-plan, create-github-issues-feature-from-implementation-plan, create-github-issues-for-unmet-specification-requirements, prd, devops-rollout-plan, structured-autonomy-plan, eval-driven-dev, refactor-plan, … |
| database / data | **47** | ef-core, cosmosdb-datamodeling, fabric-lakehouse, postgresql-code-review, postgresql-optimization, sql-code-review, sql-optimization, sql-server-table-reconciliation, ssma-console, snowflake-semanticview, 7× `qdrant-*`, 4× `dataverse-python-*`, pinecone-rag, … |
| performance | **59** | aws-cost-optimize, az-cost-optimize, postgresql-optimization, sql-optimization, power-bi-dax-optimization, power-bi-performance-troubleshooting, qdrant-{performance-optimization,scaling,monitoring}, multi-stage-dockerfile, chrome-devtools, premium-frontend-ui, cloud-design-patterns, … |
| *(none matched)* | 97 | git-commit, gitmoji, editorconfig, 12× `*-mcp-server-generator`, `gtm-*` go-to-market skills, `desk-*`, `from-the-other-side-*`, … |

### 3c. Ten+ concrete examples with absolute paths and their own `description:` frontmatter

1. `/Users/.../automation/github__awesome-copilot/agents/tdd-red.agent.md`
   > "Guide test-first development by writing failing tests that describe desired behaviour from GitHub issue context before implementation exists."
2. `/Users/.../agents/tdd-green.agent.md`
   > "Implement minimal code to satisfy GitHub issue requirements and make failing tests pass without over-engineering."
3. `/Users/.../agents/tdd-refactor.agent.md`
   > "Improve code quality, apply security best practices, and enhance design whilst maintaining green tests and GitHub issue compliance."
4. `/Users/.../agents/aws-incident-triage.agent.md`
   > "On-call SRE agent that drives structured CloudWatch-based incident investigation from alarms through root-cause hypothesis."
5. `/Users/.../agents/terraform-iac-reviewer.agent.md`
   > "Terraform-focused agent that reviews and creates safer IaC changes with emphasis on state safety, least privilege, module patterns, drift detection, and plan/apply discipline"
6. `/Users/.../agents/se-gitops-ci-specialist.agent.md`
   > "DevOps specialist for CI/CD pipelines, deployment debugging, and GitOps workflows focused on making deployments boring and reliable"
7. `/Users/.../agents/platform-sre-kubernetes.agent.md`
   > "SRE-focused Kubernetes specialist prioritizing reliability, safe rollouts/rollbacks, security defaults, and operational verification for production-grade deployments"
8. `/Users/.../agents/cloud-saas-outage-triage.agent.md`
   > "Distinguish upstream cloud or SaaS incidents from application failures before changing code, using live official-feed status and incident timelines."
9. `/Users/.../agents/pagerduty-incident-responder.agent.md`
   > "Responds to PagerDuty incidents by analyzing incident context, identifying recent code changes, and suggesting fixes via GitHub PRs."
10. `/Users/.../agents/blueprint-mode.agent.md`
    > "Executes structured workflows (Debug, Express, Main, Loop) with strict correctness and maintainability. Enforces an improved tool usage policy, never assumes facts, prioritizes reproducible solutions, self-correction, and edge-case handling."
11. `/Users/.../instructions/devops-core-principles.instructions.md`
    > "Foundational instructions covering core DevOps principles, culture (CALMS), and key metrics (DORA) to guide GitHub Copilot in understanding and promoting effective software delivery."
12. `/Users/.../instructions/kubernetes-deployment-best-practices.instructions.md`
    > "Comprehensive best practices for deploying and managing applications on Kubernetes. Covers Pods, Deployments, Services, Ingress, ConfigMaps, Secrets, health checks, resource limits, scaling, and security contexts."
13. `/Users/.../instructions/security-and-owasp.instructions.md`
    > "Comprehensive secure coding standards based on OWASP Top 10 2025, with 55+ anti-patterns, detection regex, framework-specific fixes for modern web and backend frameworks, and AI/LLM security guidance."
14. `/Users/.../skills/incident-postmortem/SKILL.md`
    > "Use when an outage, production incident, or significant service degradation has occurred and the team needs to write a structured blameless post-mortem. Triggers on phrases like \"write a post-mortem\", \"incident review\", \"what went wrong\", \"outage report\", \"root cause analysis\", or \"RCA\". Covers timeline reconstruction, contributing factor analysis, impact quantification, and action item generation with owners."
15. `/Users/.../skills/github-actions-hardening/SKILL.md`
    > "Security hardening reviewer for GitHub Actions workflow files (.github/workflows/*.yml). Reasons about the Actions threat model that pattern matchers and general code linters miss — untrusted-input script injection, privileged triggers running fork code, mutable action references, and over-scoped tokens. …"
16. `/Users/.../skills/devops-rollout-plan/SKILL.md`
    > "Generate comprehensive rollout plans with preflight checks, step-by-step deployment, verification signals, rollback procedures, and communication plans for infrastructure and application changes"
17. `/Users/.../skills/azure-deployment-preflight/SKILL.md`
    > "Performs comprehensive preflight validation of Bicep deployments to Azure, including template syntax validation, what-if analysis, and permission checks. Use this skill before any deployment to Azure to preview changes, identify potential issues, and ensure the deployment will succeed. …"
18. `/Users/.../skills/bug-reproduction-brief/SKILL.md`
    > "Turn a vague, intermittent, or environment-specific bug report into a minimal evidence-backed reproduction before proposing a fix."
19. `/Users/.../skills/aws-cloudwatch-investigation/SKILL.md`
    > "Reusable investigation patterns for AWS CloudWatch: Logs Insights query templates, alarm-to-deployment correlation, blast-radius narrowing decision tree, and PromQL-style metric query patterns for structured incident triage."
20. `/Users/.../skills/security-review/SKILL.md`
    > "AI-powered codebase security scanner that reasons about code like a security researcher — tracing data flows, understanding component interactions, and catching vulnerabilities that pattern-matching tools miss. …"

---

## 4. Definition of done / stopping criteria

`definition of done` appears in **14 files / 21 occurrences**; `acceptance criteria` in **45 / 111**; `success criteria` in **53 / 97**. Headed sections named `## Definition of Done`, `## Success Criteria`, `## Acceptance Criteria`, `### Completion Checklist`, `## Escalation` are the dominant idiom.

1. `agents/software-engineer-agent-v1.agent.md:127-137` — `### Completion Checklist (Every Task)`
   > `- [ ] All requirements from requirements.md implemented and validated.` … `- [ ] All quality gates are passed.` … `- [ ] Test coverage is adequate with all tests passing.` … `- [ ] The workspace is clean and organized.` … `- [ ] The handoff phase has been completed successfully.`
2. `agents/software-engineer-agent-v1.agent.md:120-125` — `### Pre-Action Checklist (Every Action)`
   > `- [ ] Success criteria for this specific action are defined.` / `- [ ] Validation method is identified.` / `- [ ] Autonomous execution is confirmed (i.e., not waiting for permission).`
3. `agents/tdd-green.agent.md:53-60` — `## Green Phase Checklist`
   > `- [ ] Implementation aligns with GitHub issue requirements` / `- [ ] All tests are passing (green bar)` / `- [ ] No more code written than necessary for issue scope` / `- [ ] Existing tests remain unbroken` / `- [ ] Issue acceptance criteria satisfied` / `- [ ] Ready for refactoring phase`
4. `agents/tdd-refactor.agent.md:22` —
   > `- **Definition of Done adherence** - Ensure all issue checklist items are satisfied`
5. `agents/tdd-red.agent.md:23` —
   > `- **Definition of Done** - Use issue checklist items as test validation points`
6. `agents/clojure-interactive-programming.agent.md:81` — section header
   > `### Definition of Done (ALL Required)`
7. `agents/salesforce-apex-triggers.agent.md:105` + `:122` — `### Definition of Done` gated by
   > `- **DO NOT claim completion if verification fails** - Fix ALL issues first`
8. `agents/blueprint-mode.agent.md:121` — an explicit *failure* terminal state, not just a success one:
   > `- Max Iterations: 3. If unresolved after 3 attempts → mark task FAILED and log the final failing issue.`
9. `agents/prompt-builder.agent.md:34` + `:293` —
   > `- You WILL NEVER complete a prompt improvement without Prompt Tester validation` / `#### Validation Success Criteria (any one met ends cycle):`
10. `agents/one-shot-feature-issue-planner.agent.md:322` + `:338` —
    > `## Definition of done` / `Before finalizing, you MUST verify that the plan:`
11. `skills/breakdown-plan/SKILL.md:27` and four repeated `## Definition of Done` blocks (`:115`, `:165`, `:214`, `:268`), plus `:503`
    > `- **Definition of Done**: Quality gates and completion criteria` / `- **Definition of Done Compliance**: 100% of completed stories meet DoD criteria`
12. `skills/doc-and-modernize/SKILL.md:653` —
    > `#### Verification & Exit Criteria (Definition of Done)`
    and `:730` (a DoD that explicitly refuses deferral):
    > `phase's Definition of Done, not a follow-up — a stale "quarantined module" list`
13. `skills/semantic-kernel/SKILL.md:52` — `## Completion criteria`
14. `skills/azure-architecture-autopilot/references/phase1-advisor.md:766` —
    > `## 🚨 Phase 1 Completion Checklist — Required Verification Before Phase 2 Entry`
15. `instructions/spec-driven-workflow-v1.instructions.md:189` —
    > `- **Do not proceed until all validation steps are complete and all issues are resolved.**`
16. `skills/incident-postmortem/SKILL.md:94` — a stopping rule for root-cause depth:
    > `Stop when you reach a system/process gap you can fix. The last "why" should point to an action item.`
17. `skills/phoenix-evals/references/error-analysis.md:170` — a saturation-based stop:
    > `Stop when new traces reveal no new failure modes. Minimum: 100 traces.`

---

## 5. Human-in-the-loop

`ask the user` 135 files / 213 occ; `human review` 28 / 48; `human-in-the-loop` 9 / 15; `do not proceed` 23 / 42; `requires approval` 4 / 4; `ask for confirmation` 7 / 8; `confirm with` 21 / 30; `pause` 58 / 89.

### Approval-gate quotes

- `agents/atlassian-requirements-to-jira.agent.md:18` and `:404` and `:417` —
  > `- **ALWAYS** require explicit user approval before creating/updating any Jira items`
  > `- **APPROVAL GATES**: Require explicit user confirmation before any create/update operations`
  > `❌ **FORBIDDEN**: Mass deletion or destructive operations without multiple confirmations`
- `agents/ai-team-dev.agent.md:27` —
  > `Follow the repository's Git and contribution policy. Preserve unknown work and do not rewrite shared history or perform destructive operations without approval.`
- `agents/azure-verified-modules-owner-triage.agent.md:11` —
  > `> ❗ **Step 0 - Ask for the owner alias.** Before doing anything else, the agent **MUST** ask the user for their GitHub handle … Do not assume; do not carry over an alias from a previous session.`
- `agents/azure-principal-architect.agent.md:27` —
  > `3. **Ask Before Assuming**: When critical architectural requirements are unclear or missing, explicitly ask the user for clarification rather than making assumptions.`
- `agents/prd.agent.md:65` —
  > `**Confirmation and Issue Creation**: After presenting the PRD, ask for the user's approval. Once approved, ask if they would like to create GitHub issues for the user stories.`
- `agents/task-planner.agent.md:285-286` — parameterized human gates:
  > `**CRITICAL**: If ${input:phaseStop:true} is true, you WILL stop after each Phase for user review.`
  > `**CRITICAL**: If ${input:taskStop:false} is true, you WILL stop after each Task for user review.`
- `agents/gem-devops.agent.md:43` —
  > `- \`devops.approval_required_for\` → check if current env requires approval`
- `agents/gem-orchestrator.agent.md:195` — machine-readable blocked states:
  > `- \`failed\` -> apply the failure enum; \`blocked\`, \`escalate\`, and \`needs_approval\` stop the affected path.`
- `skills/aws-cost-optimize/SKILL.md:135` — `Wait for user confirmation before proceeding.`
- `skills/refactor-plan/SKILL.md:19` —
  > `8. Stop after the plan and ask for confirmation before implementing. If the user already asked you to implement, still produce the plan first and wait for confirmation unless they explicitly said to continue without review after the plan.`
- `skills/onboard-context-matic/SKILL.md:9` — `Stop after each interaction point and wait for the user's reply before continuing.`
- `instructions/agent-safety.instructions.md:20` — the generic policy statement:
  > `- Require human-in-the-loop approval for high-impact tools (send email, deploy, delete records)`
- `instructions/mcp-m365-copilot.instructions.md:223` — `- Requires approval in Microsoft 365 admin center`
- Escalation-section headers: `agents/se-system-architecture-reviewer.agent.md:159` `**Escalate to Human When:**`; `agents/se-product-manager-advisor.agent.md:182` `## Escalate to Human When`; `agents/se-responsible-ai-code.agent.md:193`; `agents/se-ux-ui-designer.agent.md:266` `## When to Escalate to Human`; `agents/se-gitops-ci-specialist.agent.md:190` `**Escalate to human when:**`; `agents/project-architecture-planner.agent.md:502`:
  > `10. **Escalate to humans** when: budget decisions exceed estimates, compliance implications are unclear, tech choices require team retraining, or political/organizational factors are involved`

### Frontmatter fields controlling autonomy (`agents/*.agent.md`)

Census of autonomy-relevant keys across 224 agents:

| key | count | values observed |
|---|---|---|
| `argument-hint` | 26 | free text |
| `user-invocable` | 25 | `false` (24), `true` (1 — `gem-orchestrator`) |
| `mode` | 16 | `subagent` (15), `primary` (1 — `gem-orchestrator`) |
| `hidden` | 16 | `true` (15), `false` (1 — `gem-orchestrator`) |
| `disable-model-invocation` | 16 | `false` (15), `true` (1 — `gem-orchestrator`) |
| `mcp-servers` | 20 | inline MCP server + allowed-tool lists |
| `agents` | 3 | delegation rosters |
| `handoffs` | 1 | `agents/context7.agent.md` |
| `target` | 1 | `agents/defender-scout-kql.agent.md`: `target: 'vscode'` |
| `agent` | 1 | `agents/one-shot-feature-issue-planner.agent.md`: `agent: agent` |
| `excludeAgent` | 1 (instructions) | `instructions/code-review-generic.instructions.md:4`: `excludeAgent: ["coding-agent"]` |

The `gem-*` family is the only coherent multi-agent autonomy model: 15 subagents all carry
```yaml
mode: subagent
hidden: true
user-invocable: false
disable-model-invocation: false
```
and exactly one primary (`agents/gem-orchestrator.agent.md`) carries the inverse — `mode: primary`, `hidden: false`, `user-invocable: true`, `disable-model-invocation: true` (i.e. the human entry point cannot itself be model-invoked). Delegation roster, `agents/react18-commander.agent.md`:

```yaml
agents: ['react18-auditor', 'react18-dep-surgeon', 'react18-class-surgeon', 'react18-batching-fixer', 'react18-test-guardian']
```
with each of those five declaring `user-invocable: false`. `agents/rug-orchestrator.agent.md` declares `agents: ['SWE', 'QA']`.

---

## 6. Failure modes / guardrails

Counts (files / occurrences across `agents/ instructions/ skills/ workflows/`): `hallucinat` 37/108 · `do not assume` 32/35 · `never commit` 21/21 · `destructive` 49/58 · `secrets` 175/543 · `scope creep` 8/9 · `force push` 5/5 · `do not push` 1/1.

### Hallucination / unverified claims

- `agents/context7.agent.md:34` — `**If you skip steps 3-5, you are providing outdated/hallucinated information.**`; `:602` — `❌ **Hallucinate features** - If docs don't mention it, it may not exist`; `:578` — `- **Use verified APIs**: No hallucinated methods or properties`
- `agents/microsoft-study-mode.agent.md:27` — a tool-availability-conditional citation policy:
  > `… ONLY share links that have been verified through these tools. If these tools are not available … DO NOT share specific links or URLs to avoid potential hallucination`
- `agents/hlbpa.agent.md:230` — `- [ ] **No Guessing**: Ensure no speculative content or assumptions; all unknowns are clearly marked.`
- `agents/diffblue-cover.agent.md:49` — `Do not make up the names.`
- `agents/ai-team-dev.agent.md:12` — `Do not invent layers or frameworks that the repository does not use.`
- `agents/ai-team-producer.agent.md:28` — `Do not invent required gates that the repository or user did not request.`
- `skills/resemble-detect/SKILL.md:14` — `**"NEVER DECLARE MEDIA AS REAL OR FAKE WITHOUT A COMPLETED DETECTION RESULT."**`
- `skills/verify-agent-action/SKILL.md:12-26` — the strongest anti-escalation block in the repo (`## Preserve the safety boundary` at line 12, bullets from 14, `Fail closed` at 20, JSON field at 26):
  > `- Never execute, approve, sign, send, purchase, deploy, or mutate anything.`
  > `- Never convert this review into execution authority.`
  > `- Never infer missing evidence, identities, timestamps, or parameters.`
  > `- Treat a valid schema, checksum, or signature as insufficient by itself.`
  > `- Fail closed on a material mismatch. Use \`INCONCLUSIVE\` when required evidence is unavailable.`
  followed by a mandated machine-readable field: `{"execution_authorized": false}`

### Destructive actions / git safety

- `agents/react18-dep-surgeon.agent.md:159` — `- Never \`--force\`` ; `agents/react19-dep-surgeon.agent.md:108` — `- **Never use \`--force\`**`
- `agents/cloud-saas-outage-triage.agent.md:41` — `- Do not make destructive changes or incident-response mutations unless the user explicitly requests them.`
- `agents/sast-sca-security-analyzer.agent.md:346` and `:387` — `- DO NOT modify source files unless explicitly asked.` / `- Do not modify source files, dependency files, or configuration unless explicitly requested.`
- `agents/azure-verified-modules-owner-triage.agent.md:176` — `Do not post comments. Do not assign Copilot. Do not modify any repo. Read-only clones OK in deep mode.`
- `agents/ai-readiness-reporter.agent.md:218` — `9. **Only write \`reports/index.html\`** — do not modify any other files.`
- `agents/ai-team-qa.agent.md:19` — `- Do not edit application source or implementation configuration.`
- `agents/oracle-to-postgres-migration-expert.agent.md:105` — `**Do not modify the original Oracle test project** — it must remain pure so Oracle behavior continues to be provable independently.`
- `agents/terraform-iac-reviewer.agent.md:129` — `2. Never commit state files to version control`
- `agents/trojan-skill-hunter.agent.md:91` — a detection heuristic for *other* artifacts' guardrail failures:
  > `- Destructive operations gated behind vague descriptions ("cleanup", "optimize", "sync") that actually \`rm -rf\`, force-push, or overwrite unrelated paths`
- Enforcement (not prose) lives in `hooks/tool-guardian/guard-tool.sh:89-100`, `MODE="${GUARD_MODE:-block}"` (line 27) — see §1.

### Secrets exposure

- `agents/cloud-saas-outage-triage.agent.md:40` — `- Never expose secrets found in configuration, logs, or environment variables.`
- `agents/comet-opik.agent.md:140` — `Always mask tokens in logs; never echo secrets back to the user.`
- `agents/apify-integration-expert.agent.md:92` — `- **Protect secrets:** Never commit API tokens or credentials to the code. Use environment variables.`
- `agents/swe-subagent.agent.md:53` — `**Security:** Sanitize inputs. Parameterize queries. Never log secrets.`
- `agents/terraform-iac-reviewer.agent.md:64`,`:132`; `agents/azure-iac-generator.agent.md:140`; `agents/dotnet-maui.agent.md:147`; `agents/se-gitops-ci-specialist.agent.md:85`; `agents/laravel-expert-agent.agent.md:140` — `Never commit \`.env\` files to version control`
- `instructions/security-and-owasp.instructions.md:464` — `Use masked secrets in CI. Never echo environment variables containing secrets.`
- `instructions/azure-functions-csharp.instructions.md:87` — `- Never log request bodies containing PII or secrets.`
- `instructions/microsoft-foundry.instructions.md:269` — `… never ship unredacted logs to shared log sinks.`

### Scope creep and loops

- `agents/tdd-green.agent.md:16` — `- **Stay in scope** - Implement only what's required by current issue, avoid scope creep`
- `agents/gem-reviewer.agent.md:65` — `- Flag unauthorized scope creep (tasks that do not map to any PRD requirement).`
- `agents/blueprint-mode.agent.md:121` — `Max Iterations: 3` (see §4).
- `agents/cloud-saas-outage-triage.agent.md:123` — `- Do not repeatedly poll providers without a decision-relevant interval.`
- `skills/agentic-eval/SKILL.md:162` — `| **Iteration limits** | Set max iterations (3-5) to prevent infinite loops |`
- `instructions/agent-safety.instructions.md:21` — `- Enforce rate limits on tool calls per request to prevent infinite loops and resource exhaustion`

### The repo's own general-purpose guardrail doc

`instructions/agent-safety.instructions.md` (95 lines, `applyTo: '**'`) is the single most policy-dense artifact. Lines 9-13:

```markdown
- **Fail closed**: If a governance check errors or is ambiguous, deny the action rather than allowing it
- **Policy as configuration**: Define governance rules in YAML/JSON files, not hardcoded in application logic
- **Least privilege**: Agents should have the minimum tool access needed for their task
- **Append-only audit**: Never modify or delete audit trail entries — immutability enables compliance
```

Lines 17-21 and 33-37:

```markdown
- Always define an explicit allowlist of tools an agent can use — never give unrestricted tool access
- Separate tool registration from tool authorization …
- Use blocklists for known-dangerous operations (shell execution, file deletion, database DDL)
- Require human-in-the-loop approval for high-impact tools (send email, deploy, delete records)
- Enforce rate limits on tool calls per request to prevent infinite loops and resource exhaustion
...
- When agents delegate to other agents, apply the most restrictive policy from either
- Never allow an inner agent to have broader permissions than the outer agent that called it
```

Note the tension with §1: 30 tool references in this repo's own agents are wildcard-bearing (`*`, `github/*`, `azure-mcp/*`), and `'*'` appears twice as an entire `tools:` value — directly contravening line 17.

### Repo-level supply-chain guardrails

`CONTRIBUTING.md:38-49` enumerates rejection categories: "Violate Responsible AI Principles", "Compromise Security", "Enable Malicious Activities", "Exploit Weaknesses", "Circumvent Platform Policies", and:

> `- **Unreviewed remote-source plugins**: Do not open a pull request that directly adds a third-party plugin to \`plugins/external.json\`. Public external plugins must use the review workflow documented below.`

Backing CI: `.github/workflows/{external-plugin-intake,external-plugin-quality-gates,external-plugin-pr-quality-gates,external-plugin-approval-command,external-plugin-rereview,pr-risk-scan,skill-check,validate-plugins,validate-agentic-workflows-pr,check-plugin-structure}.yml` plus `eng/pr-risk-scan.mjs`, `eng/external-plugin-*.mjs`. `README.md:52` carries the standing disclaimer:

> `> The customizations here are sourced from third-party developers. Please inspect any agent and its documentation before installing.`

---

## 7. Repo conventions — exact file formats

Authoritative sources: `CONTRIBUTING.md` §"How to Contribute" (lines 60-424), `AGENTS.md` §"Working with Agents, Instructions, Skills, and Hooks" (lines 57-126), `eng/validate-skills.mjs`, `eng/validate-plugins.mjs`, `eng/agent-plugin-schema.mjs`, `.schemas/*.json`.

### Frontmatter schemas (from `AGENTS.md:61-126`)

**`*.agent.md`** — `AGENTS.md:61-66`:
> `- Must have \`description\` field (wrapped in single quotes)` / `- File names should be lower case with words separated by hyphens` / `- Recommended to include \`tools\` field` / `- Strongly recommended to specify \`model\` field`

Observed key census over 224 agents: `name:` 224, `description:` 223, `tools:` 160, `model:` 83, `argument-hint:` 26, `user-invocable:` 25, `mcp-servers:` 20, `mode:`/`hidden:`/`disable-model-invocation:` 16 each, `agents:` 3, `target:`/`handoffs:`/`agent:` 1 each. **`name` is universally present but undocumented in AGENTS.md; `description` is missing from 1 file; `model` is only on 37%.** `model:` values are unnormalized — 25 distinct strings including `GPT-4.1` (24), `GPT-5` (16), `gpt-4.1` (5), `gpt-5` (2), `Claude Sonnet 4.5` (7), `claude-sonnet-4-5` (1), `claude-sonnet-4-5-20250929` (1), `Claude Sonnet 4.5 (copilot)` (1), plus multi-value forms `GPT-4.1 | gpt-5 | Claude Sonnet 4.5` and a YAML array `[GPT-5.3-Codex, Claude Sonnet 4.6 (copilot), …]`, and one empty value.

**`*.instructions.md`** — `AGENTS.md:68-72`:
> `- Must have \`description\` field (wrapped in single quotes, not empty)` / `- Must have \`applyTo\` field specifying file patterns (e.g., \`'**.js, **.ts'\`)`

Observed: `applyTo:` 185, `description:` 178, `name:` 7, `title:` 1, `excludeAgent:` 1 — out of 192 files, so **7 files lack `applyTo` and 14 lack `description`** (5 of them lack frontmatter entirely; see §3).

**`skills/*/SKILL.md`** — `AGENTS.md:74-83`, enforced by `eng/validate-skills.mjs:16-98`:
- `name` required, regex `/^[a-z0-9-]+$/`, length-bounded, and **must equal the folder name** (`validate-skills.mjs:65-69`: `Folder name "${folderName}" does not match skill name "${metadata.name}"`)
- `description` required, **10–1024 chars** — limits live in `eng/constants.mjs:208-211` (`SKILL_NAME_MIN_LENGTH = 1`, `SKILL_NAME_MAX_LENGTH = 64`, `SKILL_DESCRIPTION_MIN_LENGTH = 10`, `SKILL_DESCRIPTION_MAX_LENGTH = 1024`), consumed by `eng/validate-skills.mjs:10-14`; `CONTRIBUTING.md:136` documents the creation command `npm run skill:create -- --name <skill-name> --description "<skill description>"`
- duplicate `name` across folders is an error (`validate-skills.mjs:141-146`)
- bundled assets capped: `const MAX_ASSET_SIZE = 5 * 1024 * 1024; // 5 MB` (`validate-skills.mjs:79`)
- spec: <https://agentskills.io/specification>

Observed over 421 `SKILL.md`: `name:` 421, `description:` 421 (100% compliant), `license:` 47, `metadata:` 45, `compatibility:` 29, `argument-hint:` 11, `allowed-tools:` 11, plus one-offs `user-invocable`, `context`, `category`, `authors`.

**`hooks/*/README.md`** — `AGENTS.md:94-104`: `name` (human-readable), `description` (single-quoted, non-empty), optional `tags`; sibling `hooks.json` required and hook events are extracted from it.

**`workflows/*.md`** — `AGENTS.md:106-114`: `name` + `description` required, plus `on`/`permissions`/`safe-outputs`; and a hard CI rule — `- Only \`.md\` files are accepted — \`.yml\`, \`.yaml\`, and \`.lock.yml\` files are blocked by CI`.

**`plugins/*/plugin.json`** — `AGENTS.md:116-125` + `eng/agent-plugin-schema.mjs`. Required: `$schema` (const `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) and `name` (`pattern: "^(?!.*(?:--|\\.\\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$"`, maxLength 64); `additionalProperties: false`. Content is declared source-only under `extensions["com.github.awesome-copilot"]` and **materialized into plugins by CI** — plugin dirs in git contain only `plugin.json` + `README.md`.

### Validation / build entry points (`package.json` scripts)

```json
"build":            "node ./eng/update-readme.mjs && node ./eng/generate-marketplace.mjs",
"plugin:validate":  "node ./eng/validate-plugins.mjs",
"plugin:create":    "node ./eng/create-plugin.mjs",
"skill:validate":   "node ./eng/validate-skills.mjs",
"skill:create":     "node ./eng/create-skill.mjs",
"website:data":     "node ./eng/generate-website-data.mjs"
```

44 workflows in `.github/workflows/`, including `validate-plugins.yml`, `validate-readme.yml`, `validate-canvas-extensions.yml`, `validate-agentic-workflows-pr.yml`, `check-plugin-structure.yml`, `check-line-endings.yml`, `codespell.yml`, `skill-check.yml`, `skill-quality-report.yml`, `pr-risk-scan.yml`. Note six of them are themselves agentic workflows shipped as `.md` + compiled `.lock.yml` pairs (`duplicate-resource-detector`, `pr-duplicate-check`, `learning-hub-updater`, `resource-staleness-report`, `codeowner-update`, `cli-for-beginners-sync`, `copilot-workshops-sync`).

### Full verbatim examples

**(a) `.agent.md` — `/Users/.../agents/tdd-green.agent.md` (61 lines, complete):**

```markdown
---
description: 'Implement minimal code to satisfy GitHub issue requirements and make failing tests pass without over-engineering.'
name: 'TDD Green Phase - Make Tests Pass Quickly'
tools: ['github/*', 'search/fileSearch', 'edit/editFiles', 'execute/runTests', 'execute/runInTerminal', 'execute/getTerminalOutput', 'execute/testFailure', 'read/readFile', 'read/terminalLastCommand', 'read/terminalSelection', 'read/problems', 'search/codebase']
---
# TDD Green Phase - Make Tests Pass Quickly

Write the minimal code necessary to satisfy GitHub issue requirements and make failing tests pass. Resist the urge to write more than required.

## GitHub Issue Integration

### Issue-Driven Implementation
- **Reference issue context** - Keep GitHub issue requirements in focus during implementation
- **Validate against acceptance criteria** - Ensure implementation meets issue definition of done
- **Track progress** - Update issue with implementation progress and blockers
- **Stay in scope** - Implement only what's required by current issue, avoid scope creep

### Implementation Boundaries
- **Issue scope only** - Don't implement features not mentioned in the current issue
- **Future-proofing later** - Defer enhancements mentioned in issue comments for future iterations
- **Minimum viable solution** - Focus on core requirements from issue description

## Core Principles

### Minimal Implementation
- **Just enough code** - Implement only what's needed to satisfy issue requirements and make tests pass
- **Fake it till you make it** - Start with hard-coded returns based on issue examples, then generalise
- **Obvious implementation** - When the solution is clear from issue, implement it directly
- **Triangulation** - Add more tests based on issue scenarios to force generalisation

### Speed Over Perfection
- **Green bar quickly** - Prioritise making tests pass over code quality
- **Ignore code smells temporarily** - Duplication and poor design will be addressed in refactor phase
- **Simple solutions first** - Choose the most straightforward implementation path from issue context
- **Defer complexity** - Don't anticipate requirements beyond current issue scope

### Implementation Strategies (Polyglot)
- **Start with constants** - Return hard-coded values from issue examples initially
- **Progress to conditionals** - Add if/else logic as more issue scenarios are tested
- **Extract to methods/functions** - Create simple helpers when duplication emerges
- **Use basic collections** - Simple arrays, lists, or maps over complex data structures

## Execution Guidelines

1. **Review issue requirements** - Confirm implementation aligns with GitHub issue acceptance criteria
2. **Run the failing test** - Confirm exactly what needs to be implemented
3. **Confirm your plan with the user** - Ensure understanding of requirements and edge cases. NEVER start making changes without user confirmation
4. **Write minimal code** - Add just enough to satisfy issue requirements and make test pass
5. **Run all tests** - Ensure new code doesn't break existing functionality
6. **Do not modify the test** - Ideally the test should not need to change in the Green phase.
7. **Update issue progress** - Comment on implementation status if needed

## Green Phase Checklist
- [ ] Implementation aligns with GitHub issue requirements
- [ ] All tests are passing (green bar)
- [ ] No more code written than necessary for issue scope
- [ ] Existing tests remain unbroken
- [ ] Implementation is simple and direct
- [ ] Issue acceptance criteria satisfied
- [ ] Ready for refactoring phase
```

**(b) `.instructions.md` — `/Users/.../instructions/ms-sql-dba.instructions.md` (26 lines, complete):**

```markdown
---
applyTo: "**"
description: 'Instructions for customizing GitHub Copilot behavior for MS-SQL DBA chat mode.'
---

# MS-SQL DBA Chat Mode Instructions

## Purpose
These instructions guide GitHub Copilot to provide expert assistance for Microsoft SQL Server Database Administrator (DBA) tasks when the `ms-sql-dba.agent.md` chat mode is active.

## Guidelines
- Always recommend installing and enabling the `ms-mssql.mssql` VS Code extension for full database management capabilities.
- Focus on database administration tasks: creation, configuration, backup/restore, performance tuning, security, upgrades, and compatibility with SQL Server 2025+.
- Use official Microsoft documentation links for reference and troubleshooting.
- Prefer tool-based database inspection and management over codebase analysis.
- Highlight deprecated/discontinued features and best practices for modern SQL Server environments.
- Encourage secure, auditable, and performance-oriented solutions.

## Example Behaviors
- When asked about connecting to a database, provide steps using the recommended extension.
- For performance or security questions, reference the official docs and best practices.
- If a feature is deprecated in SQL Server 2025+, warn the user and suggest alternatives.

## Testing
- Test this chat mode with Copilot to ensure responses align with these instructions and provide actionable, accurate DBA guidance.
```

**(c) `SKILL.md` — `/Users/.../skills/conventional-commit/SKILL.md` (73 lines, complete):**

```markdown
---
name: conventional-commit
description: 'Prompt and workflow for generating conventional commit messages using a structured XML format. Guides users to create standardized, descriptive commit messages in line with the Conventional Commits specification, including instructions, examples, and validation.'
---

### Instructions

```xml
	<description>This file contains a prompt template for generating conventional commit messages. It provides instructions, examples, and formatting guidelines to help users write standardized, descriptive commit messages in accordance with the Conventional Commits specification.</description>
```

### Workflow

**Follow these steps:**

1. Run `git status` to review changed files.
2. Run `git diff` or `git diff --cached` to inspect changes.
3. Stage your changes with `git add <file>`.
4. Construct your commit message using the following XML structure.
5. After generating your commit message, Copilot will automatically run the following command in your integrated terminal (no confirmation needed):

```bash
git commit -m "type(scope): description"
```

6. Just execute this prompt and Copilot will handle the commit for you in the terminal.

### Commit Message Structure

```xml
<commit-message>
	<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert</type>
	<scope>()</scope>
	<description>A short, imperative summary of the change</description>
	<body>(optional: more detailed explanation)</body>
	<footer>(optional: e.g. BREAKING CHANGE: details, or issue references)</footer>
</commit-message>
```

### Examples

```xml
<examples>
	<example>feat(parser): add ability to parse arrays</example>
	<example>fix(ui): correct button alignment</example>
	<example>docs: update README with usage instructions</example>
	<example>refactor: improve performance of data processing</example>
	<example>chore: update dependencies</example>
	<example>feat!: send email on registration (BREAKING CHANGE: email service required)</example>
</examples>
```

### Validation

```xml
<validation>
	<type>Must be one of the allowed types. See <reference>https://www.conventionalcommits.org/en/v1.0.0/#specification</reference></type>
	<scope>Optional, but recommended for clarity.</scope>
	<description>Required. Use the imperative mood (e.g., "add", not "added").</description>
	<body>Optional. Use for additional context.</body>
	<footer>Use for breaking changes or issue references.</footer>
</validation>
```

### Final Step

```xml
<final-step>
	<cmd>git commit -m "type(scope): description"</cmd>
	<note>Replace with your constructed message. Include body and footer if needed.</note>
</final-step>
```
```

Worth flagging: this skill's step 5 — *"Copilot will automatically run the following command in your integrated terminal (no confirmation needed)"* — is a direct counterexample to the §5 approval-gate norm, in a skill that writes to git.

**(d) Agentic workflow — `/Users/.../workflows/daily-issues-report.md` (24 lines, complete):**

```markdown
---
name: "Daily Issues Report"
description: "Generates a daily summary of open issues and recent activity as a GitHub issue"
on:
  schedule: daily on weekdays
permissions:
  contents: read
  issues: read
safe-outputs:
  create-issue:
    title-prefix: "[daily-report] "
    labels: [report]
---

## Daily Issues Report

Create a daily summary of open issues for the team.

## What to Include

- New issues opened in the last 24 hours
- Issues closed or resolved
- Stale issues that need attention
```

**(e) Plugin manifest — `/Users/.../plugins/devops-oncall/plugin.json` (complete):**

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "devops-oncall",
  "description": "A focused set of prompts, instructions, and a chat mode to help triage incidents and respond quickly with DevOps tools and Azure resources.",
  "version": "1.0.0",
  "author": { "name": "Awesome Copilot Community" },
  "repository": "https://github.com/github/awesome-copilot",
  "license": "MIT",
  "keywords": ["devops", "incident-response", "oncall", "azure"],
  "extensions": {
    "com.github.awesome-copilot": {
      "agents": ["./agents/azure-principal-architect.md"],
      "skills": [
        "./skills/azure-resource-health-diagnose/",
        "./skills/multi-stage-dockerfile/"
      ]
    }
  }
}
```

Note the stale `description` — it still advertises "prompts, instructions, and a chat mode", three primitives this plugin no longer references (and two of which no longer exist in the repo). Same drift is absent in `plugins/testing-automation/plugin.json`, which correctly lists 4 agents (`tdd-red`, `tdd-green`, `tdd-refactor`, `playwright-tester`) and 5 skills.

**(f) Hook — `/Users/.../hooks/tool-guardian/hooks.json` (complete):**

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "bash": "hooks/tool-guardian/guard-tool.sh",
        "cwd": ".",
        "env": { "GUARD_MODE": "block" },
        "timeoutSec": 10
      }
    ]
  }
}
```

---

## Summary of notable findings

1. **No `prompts/`, `chatmodes/`, or `collections/` at this HEAD** — the repo consolidated to agents / instructions / skills / hooks / workflows + plugins. Prose in several artifacts still refers to the removed primitives.
2. **The tool surface is declarative-only and mid-migration**: 187 distinct identifiers, 1518 references, split 979 flat (`codebase`) vs 539 namespaced (`search/codebase`) — 145 distinct after normalization. 30 wildcard grants.
3. **`workflows/` is the only place with real, enforced capability scoping** — read-only `permissions` + `safe-outputs` as the sole write channel + `network.allowed` + `timeout-minutes`. `hooks/tool-guardian` and `hooks/attester-import-check` are the only `preToolUse` blockers.
4. **README no longer indexes artifacts**; `docs/README.*.md` does, and all six index counts match the filesystem exactly. The four genuine discrepancies are 2 stray `.agent.md` inside a skill, `docs/README.instructions.md` colliding with the artifact glob, 15 unindexed nested `SKILL.md` files, and 5 instructions files with zero frontmatter.
5. **Policy text is abundant but uncoordinated.** 513 files say "do not", 479 say "never", yet the corpus contains directly contradictory autonomy stances (`tasksync.instructions.md`'s "NO CONVERSATION PAUSING" vs 135 files' "ask the user"), and `instructions/agent-safety.instructions.md`'s "never give unrestricted tool access" is violated by the repo's own `tools: ['*']` agents.
6. **Skills are 100% frontmatter-compliant** (421/421 have `name` + `description`, enforced by `eng/validate-skills.mjs` with folder-name equality and a 5 MB asset cap); agents and instructions are not (`model` on 37% of agents; 7 instructions missing `applyTo`, 14 missing `description`).
