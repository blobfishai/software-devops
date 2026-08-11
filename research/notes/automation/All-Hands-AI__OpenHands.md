# All-Hands-AI / OpenHands — agent harness notes

## Source

- Local path: `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/`
- Git remote: `https://github.com/All-Hands-AI/OpenHands.git`
- HEAD: `21f0967c8f7b728f5840730fe36a33d5833640cb` — `Mon Aug 10 22:34:56 2026 -0400` — *"fix: resolve flaky ProgressEvent unhandled rejection in CI (#16504)"*
- Answers sections **B**, **D**, **E**, **H** of `/Users/samuelchien/dev/software-devops/research/00-QUESTIONS.md`.

### ⚠️ Important caveat about what this clone actually contains

The `All-Hands-AI/OpenHands` repository at this commit is **no longer the Python agent runtime**. It has been
re-purposed as **"OpenHands Agent Canvas"** — a React/TypeScript control-plane frontend. There is **no Python
`openhands/` package, no `agenthub/`, no `microagents/` directory, and no `AgentFinishAction` Python class in
this checkout**. Verified: `find . -name "*.py" -not -path "*/node_modules/*"` returns only 7 files, all CI
scripts / mock servers / a canvas UI tool.

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/README.md` line 8:

> Run OpenHands, Claude Code, Codex, Gemini, or any ACP-compatible agent across local, remote, and cloud backends.

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/docs/architecture.md`:

> The primary backend is the [OpenHands Agent Server](https://github.com/OpenHands/software-agent-sdk/tree/main/openhands-agent-server/openhands/agent_server). Agent Canvas can connect to one or more Agent Server instances and switch between them from the UI.
>
> Agent Canvas is not responsible for:
> - Executing agent actions directly.
> - Providing the sandbox or workspace isolation layer.

**What we can still extract with full fidelity**: this repo carries a *hand-mirrored, docstring-preserving
TypeScript port of the agent-server's Pydantic wire contract* under
`src/types/agent-server/`. Those interfaces reproduce the SDK's action/observation classes verbatim including
the parameter descriptions the LLM sees. That is the citable tool surface. The actual Python classes live in
`OpenHands/software-agent-sdk` which is **not cloned** — flagged as a corpus gap.

---

## 1. Agent tool surface

### 1.1 Action classes (the agent's actuators)

Defined in `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/base/action.ts`.
The discriminated union at the end of that file is the complete action surface (26 members):

```ts
export type Action =
  | MCPToolAction | FinishAction | ThinkAction | ExecuteBashAction | TerminalAction
  | FileEditorAction | StrReplaceEditorAction | TaskTrackerAction | PlanningFileEditorAction
  | BrowserNavigateAction | BrowserClickAction | BrowserTypeAction | BrowserGetStateAction
  | BrowserGetContentAction | BrowserScrollAction | BrowserGoBackAction | BrowserListTabsAction
  | BrowserSwitchTabAction | BrowserCloseTabAction
  | GlobAction | GrepAction | InvokeSkillAction | TaskAction | SwitchLLMAction
  | CanvasUIAction | LaunchChildConversationAction;
```

| Action | Params (exact field names) | Notes from the source docstrings |
|---|---|---|
| `ExecuteBashAction` | `command: string`, `is_input: boolean`, `timeout: number\|null`, `reset: boolean` | `reset`: *"Used only when the terminal becomes unresponsive. Note that all previously set environment variables and session state will be lost after reset."* `command` may be `C-c` to interrupt. |
| `TerminalAction` | `command`, `is_input`, `timeout`, `reset` | Newer terminal tool, same shape |
| `FileEditorAction` / `StrReplaceEditorAction` | `command: "view"\|"create"\|"str_replace"\|"insert"\|"undo_edit"`, `path`, `file_text`, `old_str`, `new_str`, `insert_line`, `view_range: [number,number]\|null` | Absolute path required |
| `PlanningFileEditorAction` | same as above, `path` doc = *"File path (typically workspace/project/PLAN.md)."* | A **dedicated tool for the plan artifact** — plan is a first-class file |
| `TaskTrackerAction` | `command: "view"\|"plan"`, `task_list: TaskItem[]` | *"Always `view` the current list before making changes."* |
| `GlobAction` | `pattern`, `path\|null` | |
| `GrepAction` | `pattern`, `path\|null`, `include\|null` | |
| `BrowserNavigateAction` | `url`, `new_tab` | Full browser toolset: navigate/click/type/get_state/get_content/scroll/go_back/list_tabs/switch_tab/close_tab |
| `BrowserClickAction` | `index` *(from browser_get_state)*, `new_tab` | Index-addressed DOM, not coordinates |
| `MCPToolAction` | `data: Record<string, unknown>` — *"Dynamic data fields from the tool call"* | **MCP passthrough is a first-class action kind** |
| `InvokeSkillAction` | `name` — *"Name of the loaded skill to invoke."* | Skills are invoked as tool calls |
| `TaskAction` | `prompt`, `subagent_type`, `description?`, `resume?` | Subagent delegation, resumable by task id |
| `SwitchLLMAction` | `profile_name`, `reason` — *"Brief reason why this profile is a better fit for the next step."* | Agent can escalate/downgrade its own model mid-task |
| `ThinkAction` | `thought` | |
| `FinishAction` | `message` — *"Final message to send to the user"* | See §4 |
| `LaunchChildConversationAction` | `target`, `task`, `title?`, `repository?`, `branch?`, `isolation?` | Client-side tool; spawns a whole new conversation |
| `CanvasUIAction` | `command: "navigate_to_file"\|"open_tab"\|"show_preview"`, `path?`, `tab?` | Agent can drive the human's UI |

### 1.2 Observation classes (what comes back)

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/base/observation.ts`:

```ts
export type Observation =
  | MCPToolObservation | FinishObservation | ThinkObservation | BrowserObservation
  | ExecuteBashObservation | TerminalObservation | FileEditorObservation
  | StrReplaceEditorObservation | TaskTrackerObservation | PlanningFileEditorObservation
  | GlobObservation | GrepObservation | InvokeSkillObservation | TaskObservation
  | CanvasUIObservation | SwitchLLMObservation;
```

Observation fields that matter for verifier design (same file):

- `ExecuteBashObservation.exit_code: number | null` — *"-1 indicates the process hit the soft timeout and is not yet finished."*
- `ExecuteBashObservation.error: boolean`, `.timeout: boolean`, `.metadata: CmdOutputMetadata`
- `FileEditorObservation.prev_exist: boolean`, `.old_content`, `.new_content` — the harness records the **before/after diff for every edit**, i.e. edits are state-verifiable at the observation layer
- `GlobObservation.truncated: boolean` / `GrepObservation.truncated: boolean` — *"Whether results were truncated to 100 files."* (an explicit, agent-visible incompleteness signal)
- `TaskObservation` carries `task_id`, `subagent`, `status` (*"Lifecycle status of the task (e.g. \"completed\")"*)

`CmdOutputMetadata` (`.../src/types/agent-server/core/base/common.ts`) carries `exit_code, pid, username, hostname, working_dir, py_interpreter_path, prefix, suffix`.

### 1.3 Event envelope

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/openhands-event.ts`:

```ts
export type OpenHandsEvent =
  | ActionEvent | MessageEvent | ObservationEvent | UserRejectObservation
  | AgentErrorEvent | SystemPromptEvent | ACPToolCallEvent | HookExecutionEvent
  | CondensationEvent | CondensationRequestEvent | CondensationSummaryEvent
  | ConversationStateUpdateEvent | ConversationErrorEvent
  | PauseEvent | ServerErrorEvent | StreamingDeltaEvent;
```

`ActionEvent` (`.../core/events/action-event.ts`) is the key one — **every action carries an LLM-predicted risk label**:

```ts
  /**
   * The LLM's assessment of the safety risk of this action
   */
  security_risk: SecurityRisk;

  /**
   * Optional critic evaluation of this action and preceding history.
   */
  critic_result?: CriticResult | null;
```

and its docstring for `tool_call` explains why:

> This could be different from `action`: e.g., `tool_call` may contain `security_risk` field predicted by LLM when LLM risk analyzer is enabled, while `action` does not.

`SourceType` (`.../core/base/common.ts`) = `"agent" | "user" | "environment" | "hook"`.

### 1.4 Client tools + MCP + plugin wiring

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/api/agent-server-adapter.ts` builds the conversation-start payload:

```ts
type StartConversationPayload = Record<string, unknown> & {
  agent_settings?: AgentSettingsPayload;
  agent_profile_id?: string;
  workspace: LocalWorkspacePayload;
  confirmation_policy: SettingsRecord;
  security_analyzer?: SettingsRecord;
  initial_message?: InitialMessagePayload;
  max_iterations: number;
  stuck_detection: true;
  autotitle: true;
  worktree: boolean;
  secrets?: Record<string, LookupSecret>;
  client_tools: ClientToolSpec[];
  tool_module_qualnames?: Record<string, string>;
};
```

`client_tools` is `[CANVAS_UI_CLIENT_TOOL, LAUNCH_CHILD_CONVERSATION_CLIENT_TOOL]` for native OpenHands agents.
The same file (comment block ~line 1080) documents a real toolset-composition hazard:

> The exec toolset (terminal/file_editor/task_tracker) and public-skill loading are the server/SDK's responsibility to restore on the profile path — tracked in software-agent-sdk#3967 (profile resolution must attach the default toolset + public skills, else a profile-launched OpenHands agent has only Finish/Think).

A browser toolset can be omitted entirely at deploy time — `AGENTS.md`:

> `VITE_ENABLE_BROWSER_TOOLS=false` to omit `BrowserToolSet` from new conversation payloads.

**E1/E2 relevance**: the tool surface is *bash + str-replace file editor + glob/grep + browser + task-tracker +
plan-file + MCP passthrough + subagent spawn + skill invoke*. Ticketing/observability/CI tools are **not**
native actions — they arrive only through `MCPToolAction` or through bash (`gh` CLI, as used in
`.agents/skills/release.md`).

---

## 2. System prompts / policy text

There is no monolithic system prompt file in this checkout (it lives in the SDK). What this repo *does* own is
the **system-message suffix** it injects, plus repo-scoped skills that are pure workflow-discipline text.

### 2.1 Injected `<RUNTIME_SERVICES>` block — "don't guess, read the authoritative block"

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/AGENTS.md`:

> Agents should treat the `<RUNTIME_SERVICES>` block as authoritative: don't hardcode `localhost:8000` for "the automation server", and don't probe random ports trying to discover services. If the block says automation is not running, skip `/api/automation` calls; otherwise use the listed `url_from_agent` + `api_prefix` (default `/api/automation`) and the `X-Session-API-Key: $OPENHANDS_AUTOMATION_API_KEY` header.

Plumbed via `buildRuntimeServicesSystemSuffix()` → `agent_context.system_message_suffix`
(`.../src/api/agent-server-adapter.ts`, described in `AGENTS.md` § "Runtime Services in Dev Stacks").

### 2.2 The hard human boundary in `AGENTS.md`

> ## PR Description Human Check
>
> The `HUMAN:` section in PR descriptions is reserved for human contributors only.
> AI agents MUST NOT add to, edit, move, or remove it. If the PR description
> CI fails because the section is missing or empty, **stop and ask the
> human user to update it in their own words**. If the section was already updated
> by a human, report the exact validator error rather than editing it yourself.

This is the cleanest *"agent is blocked on a human"* rule in the whole corpus: a CI failure the agent is
explicitly forbidden from fixing itself.

### 2.3 Workflow discipline in the repo's own review skill

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/.agents/skills/custom-codereview-guide.md`:

> **Mandatory:** Always submit exactly one PR review object before finishing. If you found no actionable issues, post a short **APPROVE** review rather than ending silently without posting a review.

> **IMPORTANT:** If you determine a PR is worth merging **and it is not in the eval-risk category above**, you should approve it. Don't just say a PR is "worth merging" or "ready to merge" without actually submitting an approval. **Your words and actions should be consistent.**

(that last line is a direct, quotable guard against *claiming* an action instead of *taking* it — a verifier check)

> ### Review decision policy (eval / benchmark risk)
> Do **NOT** submit an **APPROVE** review when the PR changes agent behavior or anything that could plausibly affect benchmark/evaluation performance. […] If a PR is in this category (**or you are uncertain**), leave a **COMMENT** review and explicitly flag it for a human maintainer to decide after running lightweight evals.

> **Cross-File Data Flow**: When new code calls existing APIs (constructors, factory methods), trace 1–2 levels into those APIs to verify the caller uses them correctly. Bugs often hide at layer boundaries where the caller's assumptions don't match the callee's behavior

> When in doubt, add it — running the tests is cheap, missing a regression is not.

> ## What NOT to Comment On … If a PR is approvable, just approve it. Don't add "one small suggestion" or "consider doing X" comments that delay merging without adding real value.

### 2.4 Release skill — an explicit stop-and-confirm gate

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/.agents/skills/release.md`:

> **Never commit to the release PR's branch by hand** — release-please owns it and force-pushes it on every push to `main`.

> ## Step 3: Cut the Release
>
> **STOP HERE and confirm with the user before proceeding.** Marking the PR ready and merging it publishes to npm and GHCR.

### 2.5 Verification commands as repo policy (D1: the authoritative doc)

`AGENTS.md`:

> Primary verification commands: `npm run lint`, `npm test`, `npm run build`, and `npm run build:lib`.

`docs/architecture.md` § "Quality gates" repeats them as the CI contract (typecheck + ESLint + Prettier + unit
tests + standalone build + library build + `npm pack --dry-run`).

---

## 3. Workflow / skill definitions

### 3.1 Skill format (successor to `microagents/`)

There is no `microagents/` directory at this commit. The successor is **`.agents/skills/*.md`** with YAML
frontmatter. `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/.agents/skills/release.md` header, verbatim:

```markdown
---
name: release
description: Guide the release process for @openhands/agent-canvas — review the release-please draft PR, mark it ready, merge it; the tag push publishes to npm and Docker.
triggers:
- release
- new release
- cut a release
- publish release
- bump version
---
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/.agents/skills/custom-codereview-guide.md`:

```markdown
---
name: custom-codereview-guide
description: Repo-specific code review guidelines for OpenHands/agent-canvas. Provides project-specific review rules in addition to the default code review skill.
triggers:
- /codereview
---
```

The runtime skill record is `SkillInfo` in
`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/settings.ts`:

```ts
export type SkillType = "repo" | "knowledge" | "agentskills";

export type SkillInfo = {
  name: string;
  type: SkillType;
  source: string | null;
  description?: string | null;
  triggers?: string[];
  category?: SkillCategoryId | null;
  version?: string;
  license?: string | null;
  compatibility?: string | null;
  metadata?: Record<string, string> | null;
  allowed_tools?: string[] | null;
  is_agentskills_format?: boolean;
  disable_model_invocation?: boolean;
  content?: string;
};
```

Two fields are directly relevant to policy: `allowed_tools` (per-skill tool restriction) and
`disable_model_invocation` (skill can only be invoked by an explicit human trigger, not chosen by the model).

`type: "repo" | "knowledge" | "agentskills"` preserves the old microagent taxonomy (repo microagents vs
knowledge microagents triggered by keyword) alongside the newer Agent-Skills format.

### 3.2 Skill discovery paths (proves the legacy microagent path still resolves)

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/utils/skill-scope.ts`:

```ts
export type SkillScope = "project" | "personal" | "public";

const USER_SKILL_DIR_MARKERS = [
  "/.agents/skills/",
  "/.openhands/skills/",
  "/.openhands/microagents/",
] as const;
```

### 3.3 Skill categories (the harness's own taxonomy)

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/utils/skill-category.ts` — imported from the published `@openhands/extensions` catalog:

```ts
export const SKILL_CATEGORY_ORDER: readonly SkillCategoryId[] = [
  "automations", "environment", "code-hosting", "agent-authoring",
  "code-quality", "integrations", "writing", "design", "other",
];
```

9 categories; the SWE/DevOps-relevant ones are `automations`, `environment`, `code-hosting`, `code-quality`,
`integrations`. Note the catalog itself ships in the `@openhands/extensions` npm package and is **not vendored
here** (`node_modules/` absent), so per-category counts are not obtainable from this checkout.

### 3.4 Automations — the scheduled/event-driven DevOps workflow object

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/automation.ts`:

```ts
export interface AutomationTrigger {
  type: string;              // "cron" / "schedule" (time-based) or "event" (webhook)
  schedule?: string;         // cron expression
  schedule_human?: string;
  timezone?: string;         // IANA tz
  source?: string;           // e.g. "github"
  on?: string | string[];    // e.g. "pull_request.opened" or ["push", "release.*"]
  filter?: string;           // JMESPath filter over the raw webhook payload
}

export interface Automation {
  id: string; name: string; trigger: AutomationTrigger; enabled: boolean;
  repository?: string; model?: string | null;
  timeout?: number | null;   // "Maximum run time in seconds. null/omitted uses the server default (600s, 10 min)"
  prompt: string | null; branch?: string; plugins?: string[];
  notification?: string; timezone?: string; last_triggered_at?: string | null;
}

export enum AutomationRunStatus {
  PENDING = "PENDING", RUNNING = "RUNNING", COMPLETED = "COMPLETED",
  FAILED = "FAILED", CANCELLED = "CANCELLED", SKIPPED = "SKIPPED",
}
```

**B2 (where work originates)** is answered directly by this type: cron schedule, or a GitHub webhook event
matched by key pattern + JMESPath filter. Demo conversation titles in
`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/fixtures/home-automations-demo.ts`
are `"Fix flaky CI on main"` and `"Summarize open pull requests"`.

---

## 4. Definition of done / stopping criteria (B3)

Three distinct completion mechanisms coexist. This is the richest DoD model in the corpus.

### 4.1 `FinishAction` — the agent declares done

`.../src/types/agent-server/core/base/action.ts`:

```ts
export interface FinishAction extends ActionBase<"FinishAction"> {
  /** Final message to send to the user */
  message: string;
}
```

and its observation (`.../core/base/observation.ts`) can itself be an error:

```ts
export interface FinishObservation extends ObservationBase<"FinishObservation"> {
  content: Array<TextContent | ImageContent>;
  /** Whether the finish action resulted in an error */
  is_error: boolean;
}
```

### 4.2 `ExecutionStatus` — the harness's terminal states

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/base/common.ts`:

```ts
export enum ExecutionStatus {
  IDLE = "idle",
  RUNNING = "running",
  PAUSED = "paused",
  WAITING_FOR_CONFIRMATION = "waiting_for_confirmation",
  FINISHED = "finished",
  ERROR = "error",
  STUCK = "stuck",
}
```

`"stuck"` is a **first-class terminal status, distinct from `error`** — the harness treats "looping / making no
progress" as its own outcome class. `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/utils/status.ts` collapses them for the user:

```ts
export function isExecutionErrored(status: ExecutionStatus | null | undefined): boolean {
  return status === ExecutionStatus.ERROR || status === ExecutionStatus.STUCK;
}
```

### 4.3 The `/goal` loop — an LLM **judge** that must certify completion

This is the most directly transferable "definition of done" mechanism in the corpus.
`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/events/conversation-state-event.ts`:

```ts
/**
 * The judge's verdict on whether a `/goal` objective is complete.
 */
export interface GoalVerdict {
  /** Probability (0-1) that the full objective is provably done. */
  score: number;
  /** Whether the judge considers the objective complete. */
  complete: boolean;
  /** Concise description of what remains, or empty if complete. */
  missing: string;
}

export interface GoalStatus {
  active: boolean;
  status: "running" | "complete" | "capped" | "interrupted";
  /** Audit rounds completed so far (0 at kickoff). */
  iteration: number;
  /** Maximum audit rounds before the loop gives up. */
  max_iterations: number;
  objective: string;
  /** Last judge verdict; null at kickoff and on an interrupted loop. */
  verdict: GoalVerdict | null;
}
```

Note the wording *"provably done"* and the fourth status `"capped"` — **giving up because you ran out of rounds
is a distinct outcome from finishing**.

Client side, `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/hooks/chat/use-goal-interceptor.ts`:

```ts
/**
 * Intercepts "/goal [--max N] <objective>" submissions and starts a goal loop
 * on the agent server: it pursues the objective, judging completion after each
 * run until done or the cap is reached.
 */
```

and `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/utils/constants.ts:44`:

```ts
/** The /goal slash command — drives the agent toward an objective, judging completion each round. */
export const GOAL_COMMAND = "/goal";
```
> "Drive the agent toward an objective until a judge says it's done — /goal <objective> or /goal --max <n> <objective>"

### 4.4 Hard iteration budget

`.../src/api/agent-server-adapter.ts`:

```ts
    max_iterations:
      typeof conversationSettings.max_iterations === "number"
        ? conversationSettings.max_iterations
        : 500,
```

User-facing description (`src/i18n/translation.json`, key `SCHEMA$MAX_ITERATIONS$DESCRIPTION`):

> "Maximum number of iterations the conversation will run before stopping."

**Default budget = 500 steps.** Automations additionally get a wall-clock budget: `Automation.timeout`,
*"Maximum run time in seconds. `null`/omitted uses the server default (600s, 10 min)"*
(`src/types/automation.ts`).

---

## 5. Human-in-the-loop (B1, B4, B5)

### 5.1 Confirmation policy — computed per conversation

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/api/agent-server-adapter.ts:581`:

```ts
function getConversationConfirmationPolicy(conversationSettings: SettingsRecord) {
  if (conversationSettings.confirmation_mode !== true) {
    return { kind: "NeverConfirm" };
  }

  if (conversationSettings.security_analyzer === "llm") {
    return { kind: "ConfirmRisky", threshold: "HIGH", confirm_unknown: true };
  }

  return { kind: "AlwaysConfirm" };
}
```

Three policies: `NeverConfirm`, `AlwaysConfirm`, `ConfirmRisky{threshold: "HIGH", confirm_unknown: true}`.
Note `confirm_unknown: true` — **an action whose risk the analyzer cannot classify is treated as risky**.

### 5.2 Security analyzers

Same file, line 595:

```ts
function getConversationSecurityAnalyzer(conversationSettings: SettingsRecord) {
  switch (conversationSettings.security_analyzer) {
    case "llm":         return { kind: "LLMSecurityAnalyzer" };
    case "pattern":     return { kind: "PatternSecurityAnalyzer" };
    case "policy_rail": return { kind: "PolicyRailSecurityAnalyzer" };
    default:            return undefined;
  }
}
```

Risk ladder (`.../core/base/common.ts`):

```ts
export enum SecurityRisk { UNKNOWN = "UNKNOWN", LOW = "LOW", MEDIUM = "MEDIUM", HIGH = "HIGH" }
```

User-facing copy (`src/i18n/translation.json`):

- `SCHEMA$CONFIRMATION_MODE$DESCRIPTION` → **"Require user confirmation before executing risky actions."**
- `SCHEMA$SECURITY_ANALYZER$DESCRIPTION` → **"Security analyzer that evaluates actions before execution."**
- `SETTINGS$CONFIRMATION_MODE_TOOLTIP` → **"Awaits for user confirmation before executing code."**
- `INVARIANT$ASK_CONFIRMATION_RISK_SEVERITY_LABEL` → **"Ask for user confirmation on risk severity:"**
- `CHAT_INTERFACE$AGENT_AWAITING_USER_CONFIRMATION_MESSAGE` → **"Agent is awaiting user confirmation for the pending action."**
- `CHAT_INTERFACE$USER_ASK_CONFIRMATION` → **"Do you want to continue with this action?"**

### 5.3 "Blocked on human" is a protocol state, not prose

`ExecutionStatus.WAITING_FOR_CONFIRMATION` is a real wire status
(`src/api/conversation-service/agent-server-conversation-service.api.ts:293`, `RUNTIME_STATUSES`), and rejection
is an event type — `/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/events/observation-event.ts`:

```ts
// User rejection observation event
export interface UserRejectObservation extends ObservationBaseEvent {
  /** Reason for rejecting the action */
  rejection_reason: string;
  /** The action id that this observation is responding to */
  action_id: EventID;
}
```

So the loop is: `ActionEvent{security_risk}` → policy → `WAITING_FOR_CONFIRMATION` → either execute, or
`UserRejectObservation{rejection_reason}` fed back to the model. There is also a `PauseEvent`.

**B4 (what the agent may not do, and who enforces it)**: enforced in three layers — (a) the confirmation
policy in the agent-server, (b) prose prohibitions in `AGENTS.md` / skills (the `HUMAN:` section; "never commit
to the release PR's branch"), (c) CI guards. `.agents/skills/custom-codereview-guide.md` names a CI test that
mechanically enforces a policy the agent could otherwise violate:

> These two rules are enforced by the CI test `src/api/no-direct-agent-server-calls.test.ts`. **Flag any PR that introduces a violation** -- these are correctness bugs, not style nits.

### 5.4 External governance layer

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/docs/DefenseClaw.md` documents bolting on a policy runtime:

> [DefenseClaw](https://github.com/cisco-ai-defense/defenseclaw) is a security governance layer for agentic AI runtimes — it scans skills and MCP servers before they run, inspects LLM traffic at runtime, and produces durable audit evidence.

Mapping table in that file: Skills (`.agents/skills/`) → scanned by `cisco-ai-skill-scanner`; MCP servers →
`cisco-ai-mcp-scanner`; LLM `base_url` → guardrail proxy upstream; workspace files → CodeGuard scan surface.

---

## 6. Failure modes / guardrails (H3)

### 6.1 Stuck detection is switched on unconditionally

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/api/agent-server-adapter.ts` — the type is literally `true`, not `boolean`:

```ts
type StartConversationPayload = Record<string, unknown> & {
  …
  max_iterations: number;
  stuck_detection: true;
  autotitle: true;
```

and the payload builder always sends `stuck_detection: true`. Every conversation this frontend starts runs
with loop detection on; it is not a user-facing toggle.

The **algorithm** lives in the agent-server SDK (not in this clone). What is observable here is its output
contract: `ExecutionStatus.STUCK`, surfaced as a red status
(`src/hooks/use-app-title.test.tsx:76` asserts `[ExecutionStatus.STUCK, "🔴"]`) and mapped in
`src/hooks/use-agent-state.ts:30-31`:

```ts
    case ExecutionStatus.STUCK:
      return AgentState.ERROR; // Map STUCK to ERROR for now
```

`src/components/features/chat/custom-chat-input.tsx:53` documents the recovery affordance:

> in an ERROR/STUCK execution state. Users should be able to send a follow-up

### 6.2 The **Critic** — a model that scores agent behaviour, with named failure features

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/types/agent-server/core/base/critic.ts` is the single most useful artefact in this repo for H3:

```ts
/**
 * A single feature detected by the critic (e.g., "Insufficient Testing").
 */
export interface CriticFeature {
  name: string;          // e.g. "insufficient_testing"
  display_name: string;  // e.g. "Insufficient Testing"
  probability: number;   // 0-1
}

export interface CriticCategorizedFeatures {
  /** Agent behavioral issues (e.g., insufficient testing, loop behavior) */
  agent_behavioral_issues?: CriticFeature[];
  /** Likely user follow-up patterns */
  user_followup_patterns?: CriticFeature[];
  /** Infrastructure-related issues */
  infrastructure_issues?: CriticFeature[];
  other?: CriticFeature[];
}

/**
 * Result of a critic evaluation on an agent's actions.
 * The critic predicts the probability that the agent has successfully
 * completed the task.
 */
export interface CriticResult {
  score: number;                  // predicted probability of success (0-1)
  message: string | null;
  metadata: CriticMetadata | null; // includes event_ids for reproducibility
}
```

Named failure taxonomy from the docstrings: **`insufficient_testing`**, **`loop behavior`**, plus three
buckets — *agent behavioural issues*, *likely user follow-up patterns* (i.e. "the human will have to ask again"
= premature completion), and *infrastructure issues* (i.e. **environment failure separated from model failure**,
question G5). `event_ids` are stored *"for reproducibility"*.

`critic_result` hangs off each `ActionEvent`, so critique is per-step, not just per-episode.

### 6.3 Budget / context guardrails

`.../core/events/conversation-state-event.ts`:

```ts
export interface LLMMetrics {
  model_name: string;
  accumulated_cost: number;
  max_budget_per_task: number | null;
  accumulated_token_usage: TokenUsage | null;
  costs: Array<{ model: string; cost: number; timestamp: number }>;
  response_latencies: Array<{ model: string; latency: number; response_id: string }>;
  token_usages: TokenUsage[];
}
```

`max_budget_per_task` is a hard money budget. `TokenUsage` tracks `context_window` and `per_turn_token`.
Context overflow is handled by a **condenser**, which emits its own events (`CondensationEvent`,
`CondensationRequestEvent`, `CondensationSummaryEvent` in `core/openhands-event.ts`) and gets its own metrics
bucket (`usage_to_metrics` keys are *"default", "condenser", "profile:<name>:<uuid>"*).

### 6.4 Truncation as an explicit signal

`GlobObservation.truncated` / `GrepObservation.truncated` — *"Whether results were truncated to 100 files."*
The agent is told when its search view is incomplete rather than silently receiving a partial list. That is a
direct antidote to "trusted a single, partial source" (question F4).

### 6.5 Documented environment-risk posture

`docs/architecture.md` § Security posture:

> Local operation can give agents access to user workspaces. The README and self-hosting guide call out this risk and recommend Docker sandbox mode for laptop usage.

`docs/architecture.md` on `npm run dev`: *"The agent has host filesystem access; use only in trusted environments."*

Automations get a `worktree: boolean` flag on conversation start (`agent-server-adapter.ts`, default `true`) —
isolation by git worktree per conversation.

### 6.6 Failure → new investigation task

`/Users/samuelchien/dev/software-devops/research/repos/automation/All-Hands-AI__OpenHands/src/utils/automation-debug-prompt.ts` turns a failed automation run into a seeded agent task:

```ts
  const lines: string[] = [
    `${intro} Please investigate the error and fix the root cause.`,
  ];
```

with the automation's original prompt, the run id, and the **tail** of stderr (`MAX_ERROR_CHARS = 4000`,
`keepTail` — *"A traceback's most useful part is the tail (the actual error), so when the captured output is
huge we keep the end."*). `intro` = `The scheduled automation "<name>" failed during a run.`

---

## 7. Microagents / repo conventions

- **`microagents/` does not exist at this commit.** The path is still *recognised* for backwards compatibility
  (`/.openhands/microagents/` in `USER_SKILL_DIR_MARKERS`, `src/utils/skill-scope.ts`) but the live convention
  is `.agents/skills/<name>.md` with `name` / `description` / `triggers` frontmatter (§3.1).
- Skills resolve at three scopes — `project`, `personal`, `public` (`SKILL_SCOPE_ORDER`) — from
  `<repo>/.agents/skills/`, `~/.agents/skills/` or `~/.openhands/skills/`, and the bundled
  `@openhands/extensions` catalog respectively.
- `AGENTS.md` at repo root is the repo-convention file the agent is expected to read; it is prose policy, not
  frontmattered.
- Real example: the full `custom-codereview-guide.md` is quoted extensively in §2.3 — it is a 300-line
  review policy with sections `Review Decisions`, `Security`, `Core Principles`, `What to Check`,
  `Agent-Server Event Wire Contracts — Blocking Review Checkpoint`, `E2E Test Label Triage`,
  `What NOT to Comment On`, `Communication Style`. It encodes: an allowed-verdict set
  (*"You have permission to APPROVE or COMMENT… Do not use REQUEST_CHANGES"*), blocking conditions, a
  supply-chain rule (7-day `tool.uv.exclude-newer` freshness window), and an escalation rule to a human.

---

## Cross-references to `00-QUESTIONS.md`

| Q | Answer from this repo |
|---|---|
| **B1** | Humans appear as: PR reviewer/maintainer (escalation target for eval-risk PRs), release approver (`STOP HERE and confirm`), confirmation-mode operator (`Do you want to continue with this action?`), and PR description author (`HUMAN:` section agents must not touch). |
| **B2** | Work originates from: chat message, `/goal <objective>`, a cron `AutomationTrigger`, or a GitHub webhook event filtered by JMESPath (`src/types/automation.ts`). Also from a *failed prior automation run* (`automation-debug-prompt.ts`). |
| **B3** | Four competing "done"s: `FinishAction` (agent says so), `ExecutionStatus.FINISHED` (harness), `GoalVerdict.complete` (judge says *provably* done), and `AutomationRunStatus.COMPLETED` (run wrapper). They can disagree — `GoalStatus.status === "capped"` is the case where the agent stopped but nothing was certified. |
| **B4** | Enforced by `confirmation_policy` + `SecurityRisk` analyzers in the server; by prose rules in `AGENTS.md` / skills; and by CI guards (`no-direct-agent-server-calls.test.ts`). |
| **B5** | `ExecutionStatus.WAITING_FOR_CONFIRMATION` + `UserRejectObservation{rejection_reason}` + `PauseEvent`. |
| **D1/D3** | Authoritative context is injected as `<RUNTIME_SERVICES>` (agent told not to probe ports); failed-run context is stderr tail + run id + original automation prompt. |
| **E1/E2** | Native surface = bash/terminal, str-replace file editor, glob, grep, browser (10 actions), task tracker, PLAN.md editor, MCP passthrough, subagent spawn, skill invoke, LLM-profile switch. Everything else (GitHub, Slack, Linear, Notion) is MCP or `gh` CLI. |
| **G5** | The critic explicitly separates `infrastructure_issues` from `agent_behavioral_issues`. |
| **H3** | `STUCK` status, `stuck_detection: true`, critic features `loop behavior` / `insufficient_testing`, `user_followup_patterns` (premature completion), `max_iterations: 500`, `max_budget_per_task`, automation `timeout` 600s. |
