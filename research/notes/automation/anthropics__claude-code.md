# anthropics / claude-code — agent harness notes

## Source

- Local path: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/`
- Git remote: `https://github.com/anthropics/claude-code.git`
- HEAD: `54cc51a08a5d3900e5abd02ad75a2ce46f3f008c` — `Mon Aug 10 22:56:46 2026 +0000` — *"chore: Update CHANGELOG.md and feed.xml"*
- Answers sections **B**, **D**, **E**, **H** of `/Users/samuelchien/dev/software-devops/research/00-QUESTIONS.md`.

**Scope caveat**: this is the *public* claude-code repo — issue tracker, changelog, docs, examples, and the
bundled **plugin marketplace**. The CLI itself is closed-source; there is no agent loop or tool implementation
to read. What *is* readable, and what makes this repo valuable, is the **configuration and policy surface**:
plugin/skill/agent/command/hook formats, enterprise permission settings, sandbox configuration, and 13 real
first-party plugins whose prose is pure workflow-discipline policy.

Inventory (computed):

| Artifact | Count | Location |
|---|---|---|
| plugins | 13 | `plugins/*/` |
| agents (subagent definitions) | 15 | `plugins/*/agents/*.md` |
| slash commands | 15 | `plugins/*/commands/*.md` |
| skills (`SKILL.md`) | 10 | `plugins/*/skills/*/SKILL.md` |
| hook bundles (`hooks.json`) | 5 | `plugins/*/hooks/hooks.json` |

---

## 1. Agent tool surface

### 1.1 Tool names, as constrained by `allowed-tools`

The tool names are visible through the `allowed-tools` frontmatter of commands and the `tools:` field of
agents. Observed identifiers across `plugins/`:

- Core: `Bash`, `Read`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `AskUserQuestion`, `TodoWrite`
- MCP: `mcp__github_inline_comment__create_inline_comment`

`allowed-tools` supports **command-prefix scoping**, which is the harness's finest-grained permission unit.
`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/code-review/commands/code-review.md`:

```yaml
---
allowed-tools: Bash(gh issue view:*), Bash(gh search:*), Bash(gh issue list:*), Bash(gh pr comment:*), Bash(gh pr diff:*), Bash(gh pr view:*), Bash(gh pr list:*), mcp__github_inline_comment__create_inline_comment
description: Code review a pull request
---
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/commit-commands/commands/commit.md`:

```yaml
---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)
description: Create a git commit
---
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/commit-commands/commands/commit-push-pr.md`:

```yaml
allowed-tools: Bash(git checkout --branch:*), Bash(git add:*), Bash(git status:*), Bash(git push:*), Bash(git commit:*), Bash(gh pr create:*)
```

Note what is *not* in the commit command's allowlist: `git push`. The commit-only command literally cannot push.

Commands can also **inject tool output into the prompt** with `!\`cmd\`` interpolation (commit.md `## Context`
block runs `git status`, `git diff HEAD`, `git branch --show-current`, `git log --oneline -10`) — pre-seeding
state so the agent does not have to spend turns discovering it.

### 1.2 Hook events (the harness's interception points)

From `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/plugin-dev/skills/hook-development/SKILL.md` frontmatter, the full event set is:

> …mentions hook events (**PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification**)

Live examples of each shape are in `plugins/security-guidance/hooks/hooks.json`,
`plugins/ralph-wiggum/hooks/hooks.json`, `plugins/hookify/hooks/*.py`,
and `examples/hooks/bash_command_validator_example.py`.

`security-guidance/hooks/hooks.json` shows advanced fields — conditional matchers and asynchronous re-entry:

```json
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/sg-python.sh\" \"${CLAUDE_PLUGIN_ROOT}/hooks/security_reminder_hook.py\"",
            "if": "Bash(git commit:*)",
            "asyncRewake": true,
            "rewakeMessage": "Background security review of commit — address or acknowledge the findings below, then continue with the user's original request or continue waiting for their reply:",
            "rewakeSummary": "Commit security review found issues"
          },
          { "…same for": "Bash(git push:*)" }
        ],
        "matcher": "Bash"
      }
```

### 1.3 Enterprise/permission surface (B4)

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/examples/settings/settings-strict.json`:

```json
{
  "permissions": {
    "disableBypassPermissionsMode": "disable",
    "ask": ["Bash"],
    "deny": ["WebSearch", "WebFetch"]
  },
  "allowManagedPermissionRulesOnly": true,
  "allowManagedHooksOnly": true,
  "strictKnownMarketplaces": [],
  "sandbox": {
    "autoAllowBashIfSandboxed": false,
    "excludedCommands": [],
    "network": {
      "allowUnixSockets": [], "allowAllUnixSockets": false, "allowLocalBinding": false,
      "allowedDomains": [], "httpProxyPort": null, "socksProxyPort": null
    },
    "enableWeakerNestedSandbox": false
  }
}
```

The three-way permission verb set is **`allow` / `ask` / `deny`**. `examples/settings/README.md` tabulates the
enforcement axes: disable `--dangerously-skip-permissions`, block plugin marketplaces, block user/project
permission rules, block user/project hooks, deny web tools, require Bash approval, force Bash into a sandbox.
There is a full MDM/GPO deployment path (`examples/mdm/` — macOS `.mobileconfig`/`.plist`,
Windows `ClaudeCode.admx` + `Set-ClaudeCodePolicy.ps1`), i.e. **the answer to "who enforces it" is: the
enterprise, via device management, above the user's own settings.**

---

## 2. System prompts / policy text

No monolithic system prompt exists here, but the command/agent bodies *are* prompts. The workflow-discipline
quotes below are the highest-value extractions.

### 2.1 Ask-before-implementing, and treat it as a gate

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/feature-dev/commands/feature-dev.md` — a 7-phase workflow (Discovery → Codebase Exploration → Clarifying Questions → Architecture Design → Implementation → Quality Review → Summary):

> - **Ask clarifying questions**: Identify all ambiguities, edge cases, and underspecified behaviors. **Ask specific, concrete questions rather than making assumptions. Wait for user answers before proceeding with implementation.** Ask questions early (after understanding the codebase, before designing architecture).
> - **Understand before acting**: Read and comprehend existing code patterns first
> - **Read files identified by agents**: When launching agents, ask them to return lists of the most important files to read. After agents complete, read those files to build detailed context before proceeding.

> ## Phase 3: Clarifying Questions
> **CRITICAL**: This is one of the most important phases. **DO NOT SKIP.**
> …
> 3. **Present all questions to the user in a clear, organized list**
> 4. **Wait for answers before proceeding to architecture design**
>
> If the user says "whatever you think is best", provide your recommendation and **get explicit confirmation**.

> ## Phase 5: Implementation
> **DO NOT START WITHOUT USER APPROVAL**
> 1. Wait for explicit user approval

> ## Phase 6: Quality Review
> 3. **Present findings to user and ask what they want to do** (fix now, fix later, or proceed as-is)

### 2.2 Precision / false-positive discipline

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/code-review/commands/code-review.md`:

> **Agent assumptions (applies to all agents and subagents):**
> - All tools are functional and will work without error. **Do not test tools or make exploratory calls.**
> - **Only call a tool if it is required to complete the task. Every tool call should have a clear purpose.**

> **CRITICAL: We only want HIGH SIGNAL issues.** Flag issues where:
> - The code will fail to compile or parse (syntax errors, type errors, missing imports, unresolved references)
> - The code will definitely produce wrong results regardless of inputs (clear logic errors)
> - Clear, unambiguous CLAUDE.md violations **where you can quote the exact rule being broken**
>
> Do NOT flag: Code style or quality concerns / Potential issues that depend on specific inputs or state / Subjective suggestions or improvements
>
> **If you are not certain an issue is real, do not flag it. False positives erode trust and waste reviewer time.**

The known-false-positive list is itself policy:

> - Pre-existing issues
> - Something that appears to be a bug but is actually correct
> - Pedantic nitpicks that a senior engineer would not flag
> - **Issues that a linter will catch (do not run the linter to verify)**
> - General code quality concerns … unless explicitly required in CLAUDE.md
> - Issues mentioned in CLAUDE.md but explicitly silenced in the code (e.g., via a lint ignore comment)

And an explicit **independent-validation stage** — every candidate finding is re-checked by a *separate*
subagent before it is allowed to reach a human:

> 5. For each issue found in the previous step … launch parallel subagents to validate the issue. … The agent's job is to review the issue to validate that the stated issue is truly an issue with high confidence.
> 6. **Filter out any issues that were not validated in step 5.**

### 2.3 Do-not-do-anything-else scoping

`plugins/commit-commands/commands/commit.md`:

> You have the capability to call multiple tools in a single response. Stage and create the commit using a single message. **Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.**

### 2.4 Error-handling policy (a named anti-pattern set)

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/pr-review-toolkit/agents/silent-failure-hunter.md`:

> You are an elite error handling auditor with zero tolerance for silent failures…
>
> 1. **Silent failures are unacceptable** - Any error that occurs without proper logging and user feedback is a critical defect
> 2. **Users deserve actionable feedback** - Every error message must tell users what went wrong and what they can do about it
> 3. **Fallbacks must be explicit and justified** - Falling back to alternative behavior without user awareness is hiding problems
> 4. **Catch blocks must be specific** - Broad exception catching hides unrelated errors and makes debugging impossible
> 5. **Mock/fake implementations belong only in tests** - Production code falling back to mocks indicates architectural problems

with a review checklist including *"Would this log help someone debug the issue 6 months from now?"*.

### 2.5 Test-value discipline

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/pr-review-toolkit/agents/pr-test-analyzer.md` requires each suggested test to be rated 1-10 with an explicit rubric
(9-10 = data loss / security / system failure; 1-2 = optional), and closes:

> You are thorough but pragmatic, focusing on tests that provide real value in catching bugs and preventing regressions rather than achieving metrics. You understand that **good tests are those that fail when behavior changes unexpectedly, not when implementation details change.**

---

## 3. Workflow / skill definitions — categories & counts

### 3.1 Plugins by category (13), from `.claude-plugin/marketplace.json`

| Category (SWE/DevOps view) | Count | Plugins |
|---|---|---|
| Code review & PR quality | 2 | `code-review`, `pr-review-toolkit` |
| Git / release workflow | 1 | `commit-commands` |
| Feature development lifecycle | 1 | `feature-dev` |
| Security | 1 | `security-guidance` |
| Guardrails / policy authoring | 1 | `hookify` |
| Autonomous looping | 1 | `ralph-wiggum` |
| Agent/plugin authoring (meta) | 2 | `plugin-dev`, `agent-sdk-dev` |
| Migration | 1 | `claude-opus-4-5-migration` |
| Frontend/design | 1 | `frontend-design` |
| Output styles | 2 | `explanatory-output-style`, `learning-output-style` |

`marketplace.json` carries the declared `category` field per entry (`development`, `productivity`,
`learning`, …) plus `name`, `description`, `version`, `author{name,email}`, `source`.

### 3.2 The 15 agents, categorised

| Category | Count | Files (all under `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/`) |
|---|---|---|
| Code review | 6 | `pr-review-toolkit/agents/code-reviewer.md`, `pr-review-toolkit/agents/silent-failure-hunter.md`, `pr-review-toolkit/agents/comment-analyzer.md`, `pr-review-toolkit/agents/type-design-analyzer.md`, `pr-review-toolkit/agents/code-simplifier.md`, `feature-dev/agents/code-reviewer.md` |
| Testing | 1 | `pr-review-toolkit/agents/pr-test-analyzer.md` |
| Codebase understanding / architecture | 2 | `feature-dev/agents/code-explorer.md`, `feature-dev/agents/code-architect.md` |
| Verification / config audit | 2 | `agent-sdk-dev/agents/agent-sdk-verifier-ts.md`, `agent-sdk-dev/agents/agent-sdk-verifier-py.md` |
| Agent/plugin authoring (meta) | 3 | `plugin-dev/agents/agent-creator.md`, `plugin-dev/agents/plugin-validator.md`, `plugin-dev/agents/skill-reviewer.md` |
| Transcript analysis | 1 | `hookify/agents/conversation-analyzer.md` |

### 3.3 The 15 commands, categorised

| Category | Count | Files |
|---|---|---|
| Code review | 2 | `code-review/commands/code-review.md`, `pr-review-toolkit/commands/review-pr.md` |
| Git / PR | 3 | `commit-commands/commands/commit.md`, `commit-commands/commands/commit-push-pr.md`, `commit-commands/commands/clean_gone.md` |
| Feature development | 1 | `feature-dev/commands/feature-dev.md` |
| Autonomous loop control | 3 | `ralph-wiggum/commands/ralph-loop.md`, `ralph-wiggum/commands/cancel-ralph.md`, `ralph-wiggum/commands/help.md` |
| Guardrail authoring | 4 | `hookify/commands/hookify.md`, `hookify/commands/configure.md`, `hookify/commands/list.md`, `hookify/commands/help.md` |
| Scaffolding (meta) | 2 | `plugin-dev/commands/create-plugin.md`, `agent-sdk-dev/commands/new-sdk-app.md` |

### 3.4 The 10 skills

| Skill | Path |
|---|---|
| `claude-opus-4-5-migration` | `plugins/claude-opus-4-5-migration/skills/claude-opus-4-5-migration/SKILL.md` |
| `frontend-design` | `plugins/frontend-design/skills/frontend-design/SKILL.md` |
| `Writing Hookify Rules` | `plugins/hookify/skills/writing-rules/SKILL.md` |
| `Agent Development` | `plugins/plugin-dev/skills/agent-development/SKILL.md` |
| `Command Development` | `plugins/plugin-dev/skills/command-development/SKILL.md` |
| `Hook Development` | `plugins/plugin-dev/skills/hook-development/SKILL.md` |
| `MCP Integration` | `plugins/plugin-dev/skills/mcp-integration/SKILL.md` |
| `Plugin Settings` | `plugins/plugin-dev/skills/plugin-settings/SKILL.md` |
| `Plugin Structure` | `plugins/plugin-dev/skills/plugin-structure/SKILL.md` |
| `Skill Development` | `plugins/plugin-dev/skills/skill-development/SKILL.md` |

8 of 10 are **meta-skills about authoring agent tooling** — this repo is a toolkit-for-toolkits far more than
a DevOps skill library. (Contrast: `github__awesome-copilot` and `danielmiessler__fabric`.)

### 3.5 Ten concrete examples with descriptions (quoted from each file's own frontmatter)

1. `plugins/code-review/commands/code-review.md` — *"Code review a pull request"*
2. `plugins/pr-review-toolkit/commands/review-pr.md` — *"Comprehensive PR review using specialized agents"*
3. `plugins/pr-review-toolkit/agents/silent-failure-hunter.md` — *"…identify silent failures, inadequate error handling, and inappropriate fallback behavior."*
4. `plugins/pr-review-toolkit/agents/pr-test-analyzer.md` — test coverage quality/completeness review
5. `plugins/feature-dev/commands/feature-dev.md` — *"Guided feature development with codebase understanding and architecture focus"*
6. `plugins/commit-commands/commands/commit.md` — *"Create a git commit"*
7. `plugins/commit-commands/commands/commit-push-pr.md` — *"Commit, push, and open a PR"*
8. `plugins/agent-sdk-dev/agents/agent-sdk-verifier-ts.md` — *"verify that a TypeScript Agent SDK application is properly configured, follows SDK best practices … and is ready for deployment or testing"*
9. `plugins/plugin-dev/skills/hook-development/SKILL.md` — hook authoring incl. *"block dangerous commands"*
10. `plugins/ralph-wiggum/commands/ralph-loop.md` — start a bounded self-referential completion loop

---

## 4. Definition of done / stopping criteria (B3)

### 4.1 The Ralph loop — a completion **promise token** plus an iteration cap

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/ralph-wiggum/README.md`:

> This plugin implements Ralph using a **Stop hook** that intercepts Claude's exit attempts:
> ```
> # 1. Works on the task
> # 2. Tries to exit
> # 3. Stop hook blocks exit
> # 4. Stop hook feeds the SAME prompt back
> # 5. Repeat until completion
> ```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/ralph-wiggum/hooks/stop-hook.sh` is the mechanism, and it is worth reading in full for verifier design. Its three exit conditions:

```bash
# Check if max iterations reached
if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $ITERATION -ge $MAX_ITERATIONS ]]; then
  echo "🛑 Ralph loop: Max iterations ($MAX_ITERATIONS) reached."
  rm "$RALPH_STATE_FILE"
  exit 0
fi
```

```bash
  if [[ -n "$PROMISE_TEXT" ]] && [[ "$PROMISE_TEXT" = "$COMPLETION_PROMISE" ]]; then
    echo "✅ Ralph loop: Detected <promise>$COMPLETION_PROMISE</promise>"
    rm "$RALPH_STATE_FILE"
    exit 0
  fi
```

…and otherwise it **blocks the stop and replays the identical prompt**:

```bash
jq -n --arg prompt "$PROMPT_TEXT" --arg msg "$SYSTEM_MSG" \
  '{ "decision": "block", "reason": $prompt, "systemMessage": $msg }'
```

The re-injected system message is the corpus's bluntest anti-premature-completion instruction
(`stop-hook.sh:160`):

```bash
SYSTEM_MSG="🔄 Ralph iteration $NEXT_ITERATION | To stop: output <promise>$COMPLETION_PROMISE</promise> (ONLY when statement is TRUE - do not lie to exit!)"
```

and again in `plugins/ralph-wiggum/scripts/setup-ralph-loop.sh:158`:

> `Completion promise: ... (ONLY output when TRUE - do not lie!)`

Design notes worth carrying over: **the prompt never changes between iterations** — persistence is via the
filesystem and git history, not the transcript (*"Each iteration sees modified files and git history"*). The
loop state lives in `.claude/ralph-loop.local.md` with YAML frontmatter (`iteration`, `max_iterations`,
`completion_promise`) and the hook validates the numeric fields before arithmetic, deleting the state file
and stopping if anything is corrupt — **every anomaly fails safe toward stopping, not looping.**

### 4.2 "Done" as an explicit, blockable gate

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/hookify/examples/require-tests-stop.local.md` is a ready-made stop-blocker:

```markdown
---
name: require-tests-run
enabled: false
event: stop
action: block
conditions:
  - field: transcript
    operator: not_contains
    pattern: npm test|pytest|cargo test
---

**Tests not detected in transcript!**

Before stopping, please run tests to verify your changes work correctly.
…
**Note:** This rule blocks stopping if no test commands appear in the transcript.
```

**This is literally a verifier check on the transcript** — "did the agent actually run tests before claiming
done?" — implemented as a harness hook.

### 4.3 Phase-based DoD

`feature-dev.md` Phase 7 defines done as: all todos marked complete + a summary listing *what was built, key
decisions made, files modified, suggested next steps*.
`code-review.md` step 7 defines the terminal output contract, including the exact no-issues string:

> If no issues were found, state: "No issues found. Checked for bugs and CLAUDE.md compliance."

and gates side effects on a flag: *"If `--comment` argument was NOT provided, stop here. Do not post any
GitHub comments."*

---

## 5. Human-in-the-loop (B1, B4, B5)

1. **`AskUserQuestion`** is a first-class tool (referenced in `plugins/plugin-dev/skills/command-development/SKILL.md`,
   `.../references/interactive-commands.md`, `plugins/hookify/commands/configure.md`,
   `plugins/plugin-dev/commands/create-plugin.md`).
2. **Permission modes**: `allow` / `ask` / `deny` per tool or tool-with-prefix
   (`examples/settings/settings-strict.json`), with `"ask": ["Bash"]` making every shell command a human gate.
3. **`PreToolUse` hooks can veto** — `examples/hooks/bash_command_validator_example.py` reads the tool call on
   stdin and returns validation issues; `plugins/hookify/examples/dangerous-rm.local.md`:

   ```markdown
   ---
   name: block-dangerous-rm
   enabled: true
   event: bash
   pattern: rm\s+-rf
   action: block
   ---

   ⚠️ **Dangerous rm command detected!**
   ```

4. **`Stop` hooks can veto stopping** (Ralph, require-tests-run, security-guidance).
5. **Async re-wake** — `security-guidance/hooks/hooks.json` uses `asyncRewake: true` with a `rewakeMessage`
   to interrupt the agent *after* it thought it was finished:
   > "Background security review feedback — address or acknowledge the findings below, then continue with the user's original request or continue waiting for their reply. **This is supplementary, not a replacement for your previous response**"
6. **Enterprise-side lockdown** — `allowManagedPermissionRulesOnly`, `allowManagedHooksOnly`,
   `disableBypassPermissionsMode: "disable"`, `strictKnownMarketplaces: []`
   deployed via MDM (`examples/mdm/`), so *the human enforcing the rules is not the operator.*
7. **Prose-level gates** — `feature-dev.md`: *"DO NOT START WITHOUT USER APPROVAL"*, *"Wait for answers before
   proceeding"*, *"get explicit confirmation"*.

---

## 6. Failure modes / guardrails (H3)

### 6.1 Three-layer security review (`plugins/security-guidance/README.md`)

> 1. **Pattern warnings** — instant regex-based reminders on `Edit`/`Write` for ~25 known-dangerous patterns (`yaml.load`, `torch.load(weights_only=False)`, `pickle.load` on untrusted data, raw `innerHTML`, hardcoded secrets, etc.).
> 2. **LLM diff review** — when Claude finishes a turn, the plugin sends the diff to a fast LLM call … and feeds high-severity findings back to Claude **so it can fix them before you see the response.**
> 3. **Agentic commit review** — on `git commit`, an SDK-driven reviewer reads related files (`Read`/`Grep`/`Glob`) to trace data flow across the codebase, **catching multi-file vulnerabilities pattern matching misses (IDOR, auth bypass, cross-file SSRF).**

Findings cover *"injection, XSS, SSRF, hardcoded secrets, IDOR, auth bypass, unsafe deserialization, and path
traversal"*. `plugins/security-guidance/hooks/patterns.py` is real data — e.g. the GitHub Actions rule
enumerates every attacker-controlled `github.event.*` field and gives SAFE/UNSAFE examples; the
`child_process_exec` rule is language-gated (*"Gate to JS/TS files — bare `exec(` otherwise fires on Python's
exec() and on prose/docstrings mentioning exec"*), a nice false-positive-suppression pattern.

A recall/cost knob exists: `SG_DUAL_OR=on` *"Runs two parallel review calls and unions the findings. Catches
a few percentage points more vulnerabilities in our testing, at roughly 2× the API cost per review."*
And a multi-agent hazard is documented: `ENABLE_STOP_REVIEW=0` is *"Useful for multi-agent / shared-worktree
setups where **another agent can move HEAD between a worker's turns**"* — i.e. concurrent agents corrupting
each other's diff view is a known, named failure mode.

### 6.2 Guardrails as declarative rules (`hookify`)

Rule format is markdown with frontmatter: `name`, `enabled`, `event` (`bash`/`file`/`stop`/…),
`pattern` or `conditions[{field, operator, pattern}]`, `action` (`block`/`warn`), body = message shown.
Shipped examples cover the three canonical hazards:

- **Destructive command** → `dangerous-rm.local.md` (`rm -rf`, action `block`)
- **Secret exposure** → `sensitive-files-warning.local.md`, action `warn`:
  ```yaml
  conditions:
    - field: file_path
      operator: regex_match
      pattern: \.env$|\.env\.|credentials|secrets
  ```
  > 🔐 **Sensitive file detected** … Ensure credentials are not hardcoded / Use environment variables for secrets / Verify this file is in .gitignore
- **Unverified completion** → `require-tests-stop.local.md` (§4.2)
- Plus `console-log-warning.local.md` (debug artefacts left in code).

### 6.3 False-positive / over-flagging as a first-class failure mode

Uniquely in this corpus, claude-code treats **too many findings** as the failure to guard against
(§2.2): a dedicated validation pass, an explicit false-positive blocklist, and
*"False positives erode trust and waste reviewer time."* `code-review.md` also guards duplicate work
(*"Claude has already commented on this PR"* → stop) and duplicate comments
(*"Only post ONE comment per unique issue"*).

### 6.4 Loop bounding

Ralph's `--max-iterations` (default: unlimited, per README) plus the completion-promise check; every parse
error in the state machine terminates the loop rather than continuing.

### 6.5 Sandboxing

`examples/settings/settings-bash-sandbox.json` — `sandbox.enabled: true`,
`allowUnsandboxedCommands: false`, `autoAllowBashIfSandboxed: false`, and a network policy defaulting to
**no allowed domains, no local binding, no unix sockets**. That is the harness's answer to "agent exfiltrates
or reaches out unexpectedly".

---

## 7. Skills / plugins — format and conventions

### 7.1 Plugin layout

```
plugins/<name>/
  .claude-plugin/plugin.json      # manifest
  README.md
  commands/*.md                   # slash commands
  agents/*.md                     # subagents
  skills/<skill-name>/SKILL.md    # skills (+ references/, examples/, scripts/)
  hooks/hooks.json + handlers
```

`plugins/pr-review-toolkit/.claude-plugin/plugin.json`, verbatim:

```json
{
  "name": "pr-review-toolkit",
  "version": "1.0.0",
  "description": "Comprehensive PR review agents specializing in comments, tests, error handling, type design, code quality, and code simplification",
  "author": { "name": "Daisy", "email": "daisy@anthropic.com" }
}
```

Marketplace index at `.claude-plugin/marketplace.json` (`$schema: https://json.schemastore.org/claude-code-marketplace.json`)
with `name`, `version`, `description`, `owner`, and a `plugins[]` array of `{name, description, version, author, source, category}`.

`${CLAUDE_PLUGIN_ROOT}` is the path variable used in every hook command.

### 7.2 `SKILL.md` frontmatter

Fields observed: `name` (required), `description` (required), `version`, `license`.
The `description` convention is **trigger-phrase-stuffed**, e.g.
`plugins/plugin-dev/skills/hook-development/SKILL.md`:

```yaml
---
name: Hook Development
description: This skill should be used when the user asks to "create a hook", "add a PreToolUse/PostToolUse/Stop hook", "validate tool use", "implement prompt-based hooks", "use ${CLAUDE_PLUGIN_ROOT}", "set up event-driven automation", "block dangerous commands", or mentions hook events (PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification). Provides comprehensive guidance for creating and implementing Claude Code plugin hooks with focus on advanced prompt-based hooks API.
version: 0.1.0
---
```

Progressive disclosure is the documented pattern: `references/`, `examples/`, `scripts/` subdirectories
(e.g. `plugins/plugin-dev/skills/command-development/references/{frontmatter,testing-strategies,advanced-workflows,interactive-commands,marketplace-considerations,documentation-patterns,plugin-features}-reference.md`).

### 7.3 Agent (subagent) frontmatter — the canonical schema

From `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__claude-code/plugins/plugin-dev/skills/agent-development/SKILL.md`:

```markdown
---
name: agent-identifier
description: Use this agent when [triggering conditions]. Examples:

<example>
Context: [Situation description]
user: "[User request]"
assistant: "[How assistant should respond and use this agent]"
<commentary>
[Why this agent should be triggered]
</commentary>
</example>

model: inherit
color: blue
tools: ["Read", "Write", "Grep"]
---

You are [agent role description]...
```

Rules stated there: *"Agents are FOR autonomous work, commands are FOR user-initiated actions"*;
`name` must be lowercase/numbers/hyphens, 3-50 chars, start and end alphanumeric (bad: `helper` — "too
generic"; `my_agent` — underscores not allowed); `description` is *"the most critical field"* and must
contain triggering conditions + multiple `<example>` blocks + `<commentary>`.

### 7.4 Command frontmatter

`allowed-tools` (comma-separated, prefix-scoped), `description`, `argument-hint`; body supports `$ARGUMENTS`
substitution and `` !`shell command` `` output interpolation. Real examples in §1.1.

---

## Cross-references to `00-QUESTIONS.md`

| Q | Answer from this repo |
|---|---|
| **B1** | Humans: the developer answering clarifying questions and approving each phase (`feature-dev`), the PR reviewer receiving filtered high-signal findings (`code-review`), and an **enterprise admin** who sets policy the operator cannot override (`examples/mdm/`, `allowManagedPermissionRulesOnly`). |
| **B3** | Done = a declared completion token (`<promise>X</promise>`) that the agent is told not to lie about, an iteration cap, a phase checklist with a summary, and hook-enforced preconditions (e.g. tests appear in the transcript). |
| **B4** | Enforced at four layers: `allowed-tools` prefix allowlists per command, `permissions.{allow,ask,deny}`, `PreToolUse`/`Stop` hooks that can `block`, and an OS-level sandbox with a default-deny network policy. |
| **B5** | Blocked = `AskUserQuestion`, a hook `{"decision":"block","reason":...}` payload, or prose gates ("DO NOT START WITHOUT USER APPROVAL"). |
| **E1** | `Bash`, `Read`/`Write`/`Edit`/`MultiEdit`/`NotebookEdit`, `Glob`, `Grep`, `Task`, `WebFetch`, `WebSearch`, `TodoWrite`, `AskUserQuestion`, plus MCP tools; GitHub work via `gh` CLI *(explicitly: "Use gh CLI to interact with GitHub … Do not use web fetch.")*. |
| **H3** | Guarded failure modes: lying to exit a loop, stopping without running tests, `rm -rf`, editing secret files, ~25 dangerous code patterns, low-signal/false-positive review findings, duplicate comments, redundant exploratory tool calls, and concurrent agents moving HEAD under each other. |
