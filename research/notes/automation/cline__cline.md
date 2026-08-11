# cline / cline — agent harness notes

## Source

- Local path: `/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/`
- Git remote: `https://github.com/cline/cline.git`
- HEAD: `7e31fb9e0d5f38f3437d6f12a01711a0142fccca` — `Mon Aug 10 20:03:53 2026 -0700` — *"chore(vscode): prepare 4.1.8 release"*
- Answers sections **B**, **D**, **E**, **H** of `/Users/samuelchien/dev/software-devops/research/00-QUESTIONS.md`.

Monorepo layout: `sdk/packages/{shared,core,agents,llms,sdk}` (the reusable agent runtime),
`apps/{vscode,cli,cline-hub,vscode-rollout,examples}`, `evals/`, `docs/`, `.agents/skills/`.
**This repo contains a complete, readable agent runtime** — unlike the OpenHands clone, nothing is elsewhere.

---

## 1. Agent tool surface

### 1.1 The nine default tools

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/constants.ts`:

```ts
export const DefaultToolNames = {
	READ_FILES: "read_files",
	SEARCH_CODEBASE: "search_codebase",
	RUN_COMMANDS: "run_commands",
	FETCH_WEB_CONTENT: "fetch_web_content",
	APPLY_PATCH: "apply_patch",
	EDITOR: "editor",
	SKILLS: "skills",
	ASK: "ask_question",
	SUBMIT_AND_EXIT: "submit_and_exit",
} as const;
```

Definitions and descriptions live in
`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/definitions.ts`;
input schemas (Zod → JSON Schema) in `.../tools/schemas.ts`.

| Tool | Key params (Zod schema) | Description (verbatim, abbreviated) | Retry policy |
|---|---|---|---|
| `read_files` | array of `{path, start_line?, end_line?}` | *"Read the content of text or image files at the provided absolute paths… When you already know multiple files you need, read them together in one call"* | `retryable: true, maxRetries: 1` |
| `search_codebase` | array of regex queries | *"Perform regex pattern searches across the codebase. Supports multiple parallel searches… narrow patterns beat broad ones."* | `retryable: true, maxRetries: 1` |
| `run_commands` | `string[]` or structured `{command, args[]}` | description generated per-shell by `buildRunCommandsDescription(shellKind, isWindows)` | **`retryable: false, maxRetries: 0`** |
| `fetch_web_content` | `requests: [{url, prompt}]` | *"Fetch content from URLs and analyze them using the provided prompts."* | `retryable: true, maxRetries: 2` |
| `apply_patch` | `input` (patch text) | `APPLY_PATCH_TOOL_DESC` | `retryable: false` |
| `editor` | `path`, `old_text?`, `new_text`, `insert_line?` | *"Use this tool for making small, precise edits to existing files or creating new files **over shell commands**."* | **`retryable: false`** — *"Editing operations are stateful and should not auto-retry"* |
| `skills` | `skill`, `args?` | see §3 | `retryable: false` |
| `ask_question` | `question`, `options: string[2..5]` | see §5 | `retryable: false` |
| `submit_and_exit` | `summary` (min 10 chars), `verified: boolean` | see §4 — carries `lifecycle: { completesRun: true }` | `retryable: false` |

Beyond the nine: `spawn_agent` / agent-teams (`sdk/packages/core/src/extensions/tools/team/`,
`spawn-agent-tool.ts`, `configured-agent-tool.ts`, `multi-agent.ts`), MCP servers (documented as an
auto-approve category), and `switch_to_act_mode` (see §5.2).

Output caps are explicit and named in `.../tools/executors/output-limits.ts`:
`MAX_COMMAND_OUTPUT_CHARS`, `MAX_READ_LINES`, `MAX_READ_OUTPUT_CHARS`, `MAX_SEARCH_OUTPUT_CHARS`.
Descriptions surface them to the model — e.g. read_files: *"Each read returns at most {MAX_READ_LINES} lines /
~Nk characters; longer files report their total line count, page through them with start_line/end_line"*.

### 1.2 Tool presets — the tool surface *is* the permission model

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/presets.ts` defines five presets: `act`, `plan`, `search`, `minimal`, `yolo`.

```ts
	/**
	 * Plan mode (read-only)
	 * Good for analysis and documentation agents. Shell access stays enabled
	 * for read-only investigation; file-editing commands are hard-blocked by
	 * the plan-mode command-guard hook the runtime builder registers.
	 */
	plan: {
		enableReadFiles: true, enableSearch: true, enableBash: true,
		enableWebFetch: true, enableApplyPatch: false, enableEditor: false,
		enableSkills: true, enableAskQuestion: true, enableSubmitAndExit: false,
		enableSpawnAgent: true, enableAgentTeams: true,
	},
```

Notice the asymmetry: `yolo` turns **on** `submit_and_exit` and turns **off** `ask_question` —
i.e. the unattended mode replaces "ask the human" with "prove you're done".

```ts
	/**
	 * YOLO mode (automation-focused tools + no approval required)
	 * Good for trusted local automation workflows.
	 */
	yolo: {
		enableReadFiles: true, enableSearch: false, enableBash: true,
		enableWebFetch: false, enableApplyPatch: false, enableEditor: true,
		enableSkills: false, enableAskQuestion: false, enableSubmitAndExit: true,
		enableSpawnAgent: false, enableAgentTeams: false,
	},
```

and `createToolPoliciesWithPreset("yolo")` sets `{ enabled: true, autoApprove: true }` for `"*"` and every
default tool name.

---

## 2. System prompts / policy text

**Both full system prompts are in one file**:
`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/shared/src/prompt/system.ts`.
This is the single densest workflow-discipline artefact in the corpus.

### 2.1 `DEFAULT_CLINE_SYSTEM_PROMPT` (interactive Plan/Act)

Opening:

> You are Cline, an AI coding agent. Your primary goal is to assist users with various coding tasks by leveraging your knowledge and the tools at your disposal.

Context-gathering + verification discipline:

> Always gather all the necessary context before starting to work on a task. For example, if you are generating a unit test or new code, make sure you understand the requirement, the naming conventions, frameworks and libraries used and aligned in the current codebase, and the environment and commands used to run and test the code etc. **Always validate the new unit test at the end including running the code if possible for live feedback.**

Anti-hallucination / ask-instead-of-assume:

> If you need more information, use one of the available tools or **ask for clarification instead of making assumptions or lies.**

The `Remember:` block, verbatim:

> - Always adhere to existing code conventions and patterns.
> - **Use only libraries and frameworks that are confirmed to be in use in the current codebase.**
> - Provide complete and functional code without omissions or placeholders.
> - Be explicit about any assumptions or limitations in your solution.
> - Always show your planning process before executing any task.
> - Always use absolute paths when referring to files.
> - You can call multiple tools in a single response. Before using tools, identify every independent read, search, command, or edit needed for the next step and emit all of those tool calls now… **Do not wait for one independent result before requesting another. Do not split independent reads, searches, checks, or edits across separate turns.**
> - **Always verify the files you have edited or created at the end of the task to ensure they are completed and working as expected.**

Anti-"I will do X" (claiming without doing) — stated twice:

> REMEMBER, be helpful and proactive! **Don't ask for permission to do something when you can do it!** **Do not indicates you will be using a tool unless you are actually going to use it.**

> When you have completed the task, please provide a summary of what you did… **Do not indicate that you will perform an action without actually doing it. Always provide the final result in your response. Always validate your answer with checking the code and running it if possible.**

Stopping rule (turn-level):

> **IMPORTANT: Always includes tool calls in your response until the task is completed. Response without tool calls will considered as completed with final answer.**

Scope control:

> If user asked a simple question without any coding context, answer it directly without using any tools.

### 2.2 `YOLO_CLINE_SYSTEM_PROMPT` (unattended / background)

The framing changes fundamentally — **no human is reachable**:

> You are Cline, a careful and helpful coding agent that works in the background.
> **You are tasked to solve an issue reported by the user who you cannot communicate with directly.**
> Your goal is to utilize the tools at your disposal to investigate and answer the question according to user's instructions **with the aim to verify that the issue is resolved.**

The IMPORTANT block is the corpus's clearest definition-of-done:

> - When the user describes a bug, unexpected behavior, or provides a bug report, your primary goal is to produce a correct fix in the source code that resolves the issue.
> - **A correct fix means the underlying behavior is fixed — not just the symptoms addressed superficially.**
> - **After applying your fix, you must run the relevant test suite to confirm your changes actually resolve the problem. If tests fail, analyze the failures, revise your fix, and re-run until tests pass.**
> - **Do not consider the task complete until the test suite related to the files you have touched passes.**
> - Always includes tool calls in your response until the task is completed. **You should only end the task when all the requirements are met by calling the 'submit_and_exit' tool.**
> - **Response without the submit_and_exit tool call will considered not completed and the task will continue.**

Also: *"Always match output format exactly as shown in examples or existing files."*

### 2.3 Mode-tag instructions (how a mid-task policy change is communicated)

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/shared/src/prompt/cline.ts`:

```ts
export const MODE_TAG_INSTRUCTIONS = `# Plan / Act Modes

User messages arrive wrapped in a <user_input mode="..."> tag. The mode attribute is the interaction mode the user was in when they sent that message: "plan" means plan-mode constraints applied (explore, analyze, and align on a plan -- no edits or state-changing commands), while "act" (or "yolo") means implementation was allowed. If the mode attribute changes between messages, the user switched modes -- the newest message's mode is what governs right now, regardless of what earlier messages allowed. A <mode_notice> block inside a message marks exactly when such a switch happened.`;
```

The code comment above it explains *why* — a directly reusable design insight:

> Every host that sends through the SDK runtime produces those tags, so every host's system prompt must explain them: without this section the model has no idea what the attribute means, and **a mid-conversation mode switch is an invisible system-prompt swap it cannot diff.**

### 2.4 `PLAN_MODE_INSTRUCTIONS` — read-only contract

Same file:

> You are in Plan mode. Your role is to explore, analyze, and plan -- not to execute.
>
> - Read files, search the codebase, and gather context to understand the problem
> - **Ask clarifying questions when requirements are ambiguous**
> - Present your plan as a structured outline with clear steps
> - Explain tradeoffs between different approaches when they exist
> - **Do NOT edit files, write code, run destructive commands, or make any changes**
> - Do NOT implement anything -- focus on understanding and alignment first
>
> The run_commands tool remains available in plan mode strictly for read-only inspection -- listing files, searching (grep), reading configs, inspecting git history and diffs, checking tool versions, and the like. Never use it to change anything: no creating, modifying, or deleting files, no writing scripts that make changes, and no state-changing commands (installs, migrations, database or schema changes, container commands that mutate state, etc.). **File-editing commands … are hard-blocked in plan mode: they are not executed and return a tool error instead, so do not attempt them.** If the task requires a mutation, put it in the plan; it happens only after the user switches to act mode.

And the approval gate:

> Once the user has reviewed your plan and **explicitly approved it in a follow-up message**, use the switch_to_act_mode tool… **Calling switch_to_act_mode immediately starts execution, so never call it in the same turn you present a plan and never treat the original task request as approval -- end your turn after presenting the plan and wait for the user's response.**

The VS Code variant (`PLAN_MODE_INSTRUCTIONS_MANUAL_SWITCH`) has no such tool:

> You do NOT have the ability to switch to act mode yourself -- the user must do it manually with the Plan/Act toggle once they are satisfied with the plan. If the task requires tools that are only available in act mode, ask the user to "toggle to Act mode" (use those words).

---

## 3. Workflow / skill definitions

### 3.1 Skill format

`.agents/skills/<name>/SKILL.md` with YAML frontmatter. Seven skills ship in-repo
(`ls /Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/.agents/skills`):
`cline-sdk`, `create-pull-request`, `opentui`, `publish-cli`, `publish-desktop`, `publish-extension`, `tuistory`.

Categorised: **git/PR workflow** (1: `create-pull-request`), **release/publish** (3: `publish-cli`,
`publish-desktop`, `publish-extension`), **SDK/framework reference** (2: `cline-sdk`, `opentui`),
**docs/storytelling** (1: `tuistory`).

Real example, `/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/.agents/skills/create-pull-request/SKILL.md` (head, verbatim):

```markdown
---
name: create-pull-request
description: Create a GitHub pull request following project conventions. Use when the user asks to create a PR, submit changes for review, or open a pull request. Handles commit analysis, branch management, PR template usage, and PR creation using the gh CLI tool.
---

# Create Pull Request

## Prerequisites Check

Before proceeding, verify the following:

### 1. Check if `gh` CLI is installed
### 2. Check if authenticated with GitHub
### 3. Verify clean working directory
```

Its human-in-the-loop rules are notable:

> If there are uncommitted changes, ask the user whether to: Commit them as part of this PR / Stash them temporarily / Discard them (with caution)

> Ensure you're not on `main` or `master`. If so, ask the user to create or switch to a feature branch.

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/.agents/skills/cline-sdk/SKILL.md` shows a `metadata: references:` field and a progressive-disclosure `references/` tree
(`references/{agent,clinecore,events,multi-agent,plugins,production,providers,scheduling,tools}/`), each with
`REFERENCE.md` / `api.md` / `patterns.md` / `gotchas.md`.

Its "Critical Rules" encode harness invariants worth quoting:

> 4. Return errors as structured data from tool `execute` functions. **Throwing counts as a "mistake" against the agent's mistake limit.**
> 5. Use `lifecycle: { completesRun: true }` on tools that should end the agent loop (e.g. a "submit answer" tool).

### 3.2 The `skills` tool description — invocation is mandatory, not optional

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/definitions.ts`:

```ts
	const baseDescription =
		"Execute a skill within the main conversation. " +
		"When users ask you to perform tasks, check if any available skills match. " +
		"When users reference a slash command, invoke it with this tool. " +
		'Input: `skill` (required) and optional `args`. Example: `skill: "pdf"`, …' +
		"When a skill matches the user's request, invoking this tool is a blocking requirement before any other response. " +
		"Never mention a skill without invoking this tool.";
```

The description is a live getter that appends `Available skills: <names>` from
`executor.configuredSkills?.filter((s) => !s.disabled)`.

### 3.3 Documented workflow docs (D1 material)

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/docs/core-workflows/`:
`plan-and-act.mdx`, `checkpoints.mdx`, `task-management.mdx`, `using-commands.mdx`, `working-with-files.mdx`.
`docs/features/`: `auto-approve.mdx`, `auto-compact.mdx`, `subagents.mdx`, `jupyter-notebooks.mdx`,
`multiroot-workspace.mdx`. `docs/best-practices/memory-bank.mdx`.

`plan-and-act.mdx` gives a mode-selection table (Plan for: exploring unfamiliar codebases, debugging tricky
issues, architecture decisions, **code review and security analysis**, learning a codebase; Act for:
implementing a planned solution, routine changes, following established patterns, running tests).

---

## 4. Definition of done / stopping criteria (B3)

### 4.1 `AgentFinishReason` — five terminal outcomes

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/shared/src/agents/types.ts:536`:

```ts
export type AgentFinishReason =
	| "completed"       // Normal completion (no more tool calls)
	| "max_iterations"  // Hit the maximum iteration limit
	| "aborted"         // User or system aborted
	| "mistake_limit"   // Stopped after repeated recoverable mistakes
	| "error";          // Unrecoverable error occurred
```

Mapped to session status in
`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/runtime/host/local-runtime-host.ts:1685`:

```ts
		switch (finishReason) {
			case "completed":      return "completed";
			case "error":          return "failed";
			case "aborted":
			case "max_iterations":
			case "mistake_limit":  return "cancelled";
		}
```

**`max_iterations` and `mistake_limit` are "cancelled", not "failed"** — running out of budget is not the same
as failing the task.

### 4.2 `submit_and_exit` — completion requires a *verification claim*

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/definitions.ts:808`:

```ts
	return createTool<SubmitInput, string>({
		name: "submit_and_exit",
		description:
			"Submit the final answer and exit the conversation. " +
			"For example, submit a summary of the investigation and confirm the issue is resolved. " +
			"You should only submit once all necessary steps are completed. " +
			"Make sure to verify your output matches the expected format, data types, and file locations specified. " +
			"Provide a summary of the investigation and confirm the issue is resolved.",
		inputSchema: zodToJsonSchema(SubmitInputSchema),
		lifecycle: {
			completesRun: true,
		},
```

The schema (`.../tools/schemas.ts:277`) is the strongest anti-premature-completion text in the corpus:

```ts
export const SubmitInputSchema = z.object({
	summary: z.string().min(10).describe(
		"Summarization of the investigation, steps taken, and resolution status to submit at the end of the session. Before submitting, read the problem again along with any provided test's assertions carefully and confirm your fix produces the expected output.",
	),
	verified: z.boolean().describe(
		`Have you verified that the issue is resolved to the best of your knowledge, including updating and creating all the requested files and items? 'True' if you have completed the investigation and taken all necessary steps to resolve the issue.\n'False' if you have done all you can but cannot resolve the issue or if you are stuck and cannot proceed further. =\nIMPORTANT: You must run the specific failing test(s) mentioned in the issue or test patch and include the test output in your reasoning. If the test still fails after your fix, you must revise. Do NOT submit with 'true' unless the test output shows the test passing.`,
	),
});
```

`verified: false` is a **first-class "I gave up / I'm stuck" channel** for an agent with no human to ask.

### 4.3 The completion-tool policy enforcement loop

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/agents/src/agent-runtime.ts:609`:

```ts
	private getRequiredCompletionToolNames(): string[] {
		if (this.config.completionPolicy?.requireCompletionTool !== true) {
			return [];
		}
		return [...this.tools.values()]
			.filter((tool) => tool.lifecycle?.completesRun === true)
			.map((tool) => tool.name)
			.sort();
	}

	private getCompletionToolReminderMessage(): string | undefined {
		…
		return `[SYSTEM] This run is not complete until you call one of these terminal completion tools: ${terminalToolNames.join(
			", ",
		)}. Continue working if requirements are not met. If the task is complete, call the appropriate terminal completion tool now.`;
	}
```

There is also a pluggable `this.config.completionPolicy?.completionGuard?.()` that can inject an extra
reminder. And `findCompletingToolMessage` (line 1511) only accepts a completion **whose tool result is not an
error**:

```ts
			if (result && !result.isError) {
				return toolMessage;
			}
```

The failure mode this defends against is named explicitly in the mistake taxonomy:
**`completion_without_submit`** (`sdk/packages/shared/src/agents/types.ts:179`,
`sdk/packages/core/src/runtime/safety/mistake-tracker.ts:172`).

### 4.4 Telemetry distinguishes real vs inferred completion

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/services/telemetry/core-events.ts:417`:

```ts
/**
 * Distinguishes the trigger that produced a `task.completed` telemetry event.
 *
 * - `submit_and_exit`: the assistant explicitly declared completion by
 *   invoking the canonical completion tool. …
 * - `shutdown`: the session lifecycle completed (typically a non-interactive
 *   single-run that finished without an explicit completion tool). Acts as a
 *   safety-net so we still report completed runs that never observed
 *   `submit_and_exit`.
 */
export type TaskCompletedSource = "submit_and_exit" | "shutdown";
```

---

## 5. Human-in-the-loop (B1, B4, B5)

### 5.1 `ask_question` — a constrained question channel

`.../tools/definitions.ts:784`:

```ts
		description:
			"Ask user a question for clarifying or gathering information needed to complete the task. " +
			"For example, ask the user clarifying questions about a key implementation decision. " +
			"You should only ask one question. " +
			"Provide an array of 2-5 options for the user to choose from. " +
			"Never include an option to toggle to Act mode.",
```

Schema enforces it (`schemas.ts:261`): `options: z.array(z.string().min(1)).min(2).max(5)`.
**Asking is not free-form** — the agent must offer the human a bounded choice set. That is a
verifier-checkable interface.

### 5.2 Mode switching as the approval protocol

`switch_to_act_mode` exists only where the host exposes it (`planModeSwitchTool`, `prompt/cline.ts`). The
prompt forbids using it in the same turn as the plan, and forbids treating the original request as approval
(quoted in §2.4). In VS Code the human must physically toggle.

### 5.3 Per-tool-call approval, out-of-process

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/runtime/tools/tool-approval.ts` implements approval as a **file-based IPC handshake**:

```ts
	await writeFile(requestPath, `${JSON.stringify({
				requestId, sessionId, createdAt: nowIso(),
				toolCallId: request.toolCallId,
				toolName: request.toolName,
				input: request.input,
				iteration: request.iteration,
				agentId: request.agentId,
				conversationId: request.conversationId,
			}, null, 2)}\n`, "utf8");

	const timeoutMs = options.timeoutMs ?? 5 * 60_000;
	const pollIntervalMs = options.pollIntervalMs ?? 200;
	…
	return { approved: false, reason: "Tool approval request timed out" };
```

**Default human-response budget = 5 minutes; timeout means denied, not approved.** Unconfigured IPC also
denies: `{ approved: false, reason: "Desktop tool approval IPC is not configured" }`.

### 5.4 Auto-approve categories (B4 — what is allowed without a human)

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/docs/features/auto-approve.mdx`:

| Setting | What It Allows |
|---|---|
| Read project files | Read files, list files, search in your workspace |
| Read all files | Read files **outside** your workspace (requires base toggle) |
| Edit project files | Create and edit files in your workspace |
| Edit all files | Edit files outside your workspace (requires base toggle) |
| Execute safe commands | Run terminal commands marked safe |
| Execute all commands | Run commands requiring approval (requires base toggle) |
| Use the browser | Browser tool for web fetching and searching |
| Use MCP servers | MCP tools and resources |

Crucially, safety is **model-judged, not allowlisted**:

> Cline does not use a fixed allowlist. **The model marks each command with a `requires_approval` flag based on the command and arguments.** These are examples, not guarantees.

(the flag appears in the VS Code prompt scaffolding as `<requires_approval>false</requires_approval>` —
`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/apps/vscode/src/core/prompts/responses.ts:121`.)

Examples the doc gives: *safe* = `npm run build`, `npm test`, `git status`, `ls -la`, `cat package.json`;
*requires approval* = `npm install <pkg>`, `rm -rf <path>`, `mv <a> <b>`, `sed -i ...`.

And the doc's own recommendation is minimal privilege:

> A good default setup: Enable **Read project files**. Leave edits, commands, browser, and MCP off until you have a specific reason.

> **Warning: This is dangerous.** YOLO mode disables all safety checks. Cline executes whatever it decides without asking permission.

---

## 6. Failure modes / guardrails (H3)

Cline has a dedicated `runtime/safety/` directory:
`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/runtime/safety/`
= `loop-detection.ts`, `mistake-tracker.ts`, `rules.ts`.

### 6.1 Loop detection — exact algorithm

`.../runtime/safety/loop-detection.ts`. State is `{lastToolName, lastToolSignature, consecutiveIdenticalCount}`;
signature is a **key-sorted JSON serialisation of the tool input** (`toolCallSignature` → `sortKeys`), so
argument reordering does not defeat it.

```ts
const DEFAULT_CONFIG: LoopDetectionConfig = {
	softThreshold: 3,
	hardThreshold: 5,
};
```

```ts
		if (result.hardEscalation) {
			return {
				kind: "hard",
				message: `Detected ${this.state.consecutiveIdenticalCount} consecutive identical calls to \`${call.name}\`; stopping to avoid a loop.`,
			};
		}
		if (result.softWarning) {
			return {
				kind: "soft",
				message: `Detected ${this.state.consecutiveIdenticalCount} consecutive identical calls to \`${call.name}\`; consider trying a different approach.`,
			};
		}
```

Two-stage: at **3** identical calls the agent gets a nudge and keeps going; at **5** the run is stopped.
Installed as a `beforeTool` hook that can return `{ skip, stop, reason }`.

### 6.2 Consecutive-mistake tracker

`.../runtime/safety/mistake-tracker.ts`:

```ts
export type MistakeReason =
	| "api_error"
	| "invalid_tool_call"
	| "tool_execution_failed";
```

(the stop-message helper additionally accepts `"completion_without_submit"`, and the notice-event union in
`sdk/packages/shared/src/agents/types.ts:176` lists all four plus `"mistake_limit"`, `"auto_compaction"`,
`"manual_compaction"`, `"compaction_budget_emergency"`.)

Behaviour: every mistake increments a counter and emits a **recoverable** error event; on reaching
`maxConsecutiveMistakes` an `onLimitReached` callback may either `stop` or `continue` **with guidance**
(which resets the counter to 0 — an explicit recovery path). The default with no callback is:

```ts
		return {
			action: "stop",
			reason: `maximum consecutive mistakes reached (${input.maxConsecutiveMistakes})`,
		};
```

Stop message (`buildMistakeLimitStopMessage`):

> `Stopped after {n}/{max} consecutive mistakes ({reason}) at iteration {i}.` … `Session state was preserved. Send a new prompt to resume from the latest state.`

Note the design decision quoted from the SDK skill: *"Return errors as structured data from tool `execute`
functions. **Throwing counts as a 'mistake' against the agent's mistake limit.**"* — i.e. a tool that reports
failure cleanly does not burn the agent's error budget; a crashing one does.

### 6.3 Plan-mode command guard — the hard backstop against destructive actions

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/sdk/packages/core/src/extensions/tools/command-guard.ts` (521 lines). Header docstring, verbatim:

> Plan mode keeps run_commands available for read-only investigation, but **models (especially weaker ones) use it to edit files anyway.** When the plan preset sets `blockFileEditingCommands`, createShellTool checks each command against this blacklist before executing and returns a tool error instead of running anything that looks like a file modification.
>
> **This is a simple blacklist, not a shell interpreter.** Commands are lightly preprocessed (quoted text, heredoc bodies, escapes, and comments are masked so they cannot false-positive), split on shell separators, and the leading command word of each part is compared against the lists below; output redirection to files is also rejected. **It will not catch every possible mutation** (e.g. `python -c "open(..., 'w')"` or commands hidden inside a quoted `bash -c` string) — it exists to stop the common ways models edit files from the shell, and entries are easy to add.

Blocked command words (`BLOCKED_COMMANDS`): `rm rmdir unlink mv cp dd touch mkdir ln link chmod chown chgrp
truncate shred install patch rsync mkfifo mknod` plus Windows/PowerShell equivalents
(`del erase move ren rename md rd mklink copy xcopy robocopy new-item ni remove-item move-item copy-item
rename-item set-content add-content clear-content out-file` and aliases `mi ri cpi rni ac clc`).

Blocked **subcommands** (`BLOCKED_SUBCOMMANDS`) cover `git` (add am apply checkout cherry-pick clean clone
commit init merge mv pull push rebase reset restore revert rm stash submodule switch worktree), node PMs
(`npm pnpm yarn bun`), `pip/pip3/pipx/uv`, `cargo`, `apt/apt-get/dnf/yum/apk/brew/snap`, `gem`, `composer`,
`go`, `dotnet`, `winget`, `nuget`.

Sophistication worth stealing:
- `READ_ONLY_GIT_FORMS` carves out `git stash list|show`, `git worktree list`, `git submodule status|summary`.
- `WRAPPERS` (`sudo doas env command builtin nohup time nice stdbuf timeout xargs`) are skipped over to find the real command.
- `RESERVED_WORDS` and `ENV_ASSIGNMENT` are skipped.
- Output redirection is rejected unless the target is `/dev/*` or a temp dir, and `..` segments are rejected *"so a temp prefix cannot smuggle a path back into the workspace (`/tmp/../home/user/project/x`)"*.

Blocked-command error text:

```ts
	return (
		`Command not executed: ${reason} can modify files, and file modifications are blocked in plan mode. ` +
		"You are in PLAN MODE — explore, analyze, and present a plan; do not make changes. " +
		"Use read-only commands to inspect the project (redirecting output to /tmp, or %TEMP% on Windows, is allowed), " +
		"and if this change is part of the task, put it in your plan so it can run after the user approves switching to act mode."
	);
```

### 6.4 Budgets

- `maxIterations` — `z.number().int().positive().optional()` on the session config
  (`sdk/packages/core/src/types/chat-schema.ts:12`), threaded through `runtime-builder.ts`,
  `spawn-tool.ts`, `configured-agent-config.ts` (per-subagent override), and persisted
  (`sqlite-db.ts: max_iterations INTEGER`).
- Per-tool `timeoutMs` with `withTimeout(...)` wrappers; defaults: read 10 s, editor 30 s,
  apply_patch 30 s, web fetch 30 s, skills 15 s, submit 15 s.
- Context overflow → compaction, with its own notice reasons `auto_compaction`, `manual_compaction`,
  **`compaction_budget_emergency`** (`sdk/packages/shared/src/agents/types.ts`).
- `run_commands` timeout is telemetered with `timeout_source: "default_setting" | "configured_setting"`
  (`definitions.ts`, `captureRunCommandsTimeout`).

### 6.5 The eval-side failure classifier (directly relevant to G5)

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/evals/analysis/patterns/cline-failures.yaml` — a regex classifier that sorts failures into **categories** before scoring:

```yaml
patterns:
  - name: "gemini_signature"       category: "provider_bug"   issue: ".../issues/7974"
  - name: "claude_tool_format"     category: "provider_bug"   issue: ".../issues/7998"
  - name: "rate_limit"             category: "transient"      pattern: "429|rate.?limit|too.?many.?requests|quota.?exceeded"
  - name: "network_timeout"        category: "transient"      pattern: "ECONNREFUSED|ETIMEDOUT|ENOTFOUND|timed.?out"
  - name: "model_overloaded"       category: "transient"      pattern: "503|service.?unavailable|overloaded"
  - name: "harness_error"          category: "harness"        pattern: "verifier.*failed|test.*harness.*error|missing.*test.*file"
  - name: "environment_failure"    category: "environment"    pattern: "docker.*failed|container.*exit|OCI.*runtime|pod.*error"
  - name: "safety_refusal"         category: "policy"         pattern: "content.*policy|safety.*filter|inappropriate.*request"
  - name: "auth_error"             category: "auth"           pattern: "401|unauthorized|invalid.?api.?key"
```

Seven categories — `provider_bug`, `transient`, `harness`, `environment`, `policy`, `auth` — none of which is
"model was bad at the task". **This is an explicit machine-readable separation of environment failure from
model failure.**

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/evals/README.md` describes the
three-layer eval stack: contract/unit tests → **smoke tests** (5 scenarios, *"3 trials per test for pass@k
metrics"*) → **e2e against `cline-bench`** (*"12 production bug fixes"*, a git submodule — not populated in
this clone), plus `evals/analysis/src/metrics.ts` computing **pass@k and pass^k** and
`evals/baselines/` *"Performance baselines for regression detection"*. `evals/benchmarks/tool-precision/`
exists as a separate benchmark axis.

`/Users/samuelchien/dev/software-devops/research/repos/automation/cline__cline/AGENTS.md` even pre-labels
known environment artefacts so an agent does not chase them:

> Known cloud-env test artifact: … fails because cloud VMs configure git `insteadOf` rules… **This is an environment artifact, not a code bug.**
> Some `@cline/cli` e2e assertions … may fail on exact tool-listing string formats; **treat as pre-existing test drift, not an environment problem.**

---

## 7. Repo conventions

- `AGENTS.md` at repo root is the operating manual for an agent working *on* cline: toolchain (`Bun 1.3.13`,
  Node ≥22, *"Do not use npm/yarn/pnpm"*), build order (`bun run build:sdk` before CLI/SDK tests because
  packages resolve through compiled `dist/`), test commands per app, and the known-artefact list above.
- Skills: `.agents/skills/<name>/SKILL.md`, frontmatter `name` + `description` (+ optional
  `metadata.references`), progressive-disclosure `references/` subtree.
- Tools: `createTool()` from `@cline/shared`, **`snake_case` names required**, Zod input schema converted via
  `zodToJsonSchema`, `lifecycle.completesRun` marks terminal tools, `retryable`/`maxRetries` per tool.
- Hosts: `apps/vscode` (extension), `apps/cli` (auto-spawns `@cline/cline-hub` daemon),
  `apps/examples/*` (code-review-bot, multi-agent, quickstart, cli-agent, vscode).

---

## Cross-references to `00-QUESTIONS.md`

| Q | Answer from this repo |
|---|---|
| **B1** | Two distinct human roles by mode: an *interactive* user who approves plans, answers `ask_question` (2-5 options), and toggles Plan→Act; and in YOLO mode, **no human at all** — *"the user who you cannot communicate with directly"*. |
| **B3** | Done = `submit_and_exit(summary, verified)` **and** `verified` is only allowed to be `true` if test output shows the test passing. `AgentFinishReason` distinguishes `completed` / `max_iterations` / `aborted` / `mistake_limit` / `error`; only the first is "completed" status. |
| **B4** | Plan mode blocks ~90 command words + 20 tool-subcommand families at the executor; auto-approve categories gate everything else; `requires_approval` is model-predicted per command. |
| **B5** | Blocked = a pending `ToolApprovalRequest` file with a 5-minute timeout that defaults to **denied**; or `verified: false` on submit ("stuck and cannot proceed further"); or a `notice` event with `noticeType: "stop"`. |
| **E1/E2** | `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `apply_patch`, `editor`, `skills`, `ask_question`, `submit_and_exit`, plus `spawn_agent`/agent-teams and MCP. GitHub work happens through `gh` CLI inside `run_commands` (see `create-pull-request` skill). |
| **G1/G2** | `evals/`: unit contract tests → 5 smoke scenarios × 3 trials (pass@k) → cline-bench e2e; `pass@k` and `pass^k` in `evals/analysis/src/metrics.ts`; baselines for regression detection. |
| **G5** | `evals/analysis/patterns/cline-failures.yaml` classifies failures into `provider_bug / transient / harness / environment / policy / auth` before attributing anything to the model. |
| **H3** | Named, coded failure modes: identical-tool-call loops (soft 3 / hard 5), `invalid_tool_call`, `tool_execution_failed`, `api_error`, **`completion_without_submit`**, `mistake_limit`, `compaction_budget_emergency`, plan-mode file mutation attempts. |
