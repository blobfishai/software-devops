# 02 — Coverage matrix

**What this document is.** A strict audit of how much of the software-engineering /
DevOps agent domain the world in `world/` actually covers, and where it does not.
It is written to be checked, not believed. Every number below was counted from an
artifact, and the command or file path is given (§9 reproduces all of them). Where
coverage could not be determined the rule was to write **UNKNOWN** rather than
guess; in the event, three initially-unknown denominators — IaC, communication,
data/warehouse — were resolved by counting the fourteen un-inventoried MCP servers
directly from source (§0.2), so no UNKNOWN cells remain. Three numbers *are*
reported as ranges or with a stated unit ambiguity, and each says so where it
appears.

**Companion document.** `research/02-CORPUS-MAP.md` already maps AIOpsLab's fault
families, TheAgentCompany's job families and tau-bench's domains one-for-one. This
document does not repeat that; it covers the four axes that map does not: task
*types*, tool *surface*, chaos *scenarios*, and workflow *discipline*.

---

## 0. What was measured, and against what

### 0.1 The world under audit

Re-derived on 2026-08-11 from the artifacts on disk, **after** a rebuild that
happened during this audit (an earlier build had 68 tasks / 72 tools; those numbers
are stale and appear nowhere below).

| Quantity | Value | Source |
|---|---:|---|
| `world_id` | `env_software_devops_8b9d74de` | `world/world.json` |
| `world_digest` | `8b9d74de37b1c574…` | `world/world.json` |
| Tasks | **70** | `len(json.load(open('world/tasks.json')))` |
| Task categories | **11** | `world/world.json` `categories` |
| Tools | **74** | `len(json.load(open('world/tools.json')))`; `world/tools_combined.py` has 74 `^def ` |
| Read/write split | **53 read-only / 21 writing** | tools with an empty `write_tables` |
| Tables | **55** | `sqlite_master` in `world/environment.db`, excluding `sqlite_sequence`. Two (`metric_rules`, `tool_calls`) are harness/verifier-internal and reachable by no tool; the other 53 all are |
| Rows | **1 193** | summed over all 55 tables |
| Repo files | **38** (83 948 bytes, 6 languages: `go java py sql ts tsx`) | `repo_files` |
| Knowledge-base documents | **30** | `documents` |
| Commits | **417** | `commits` |
| Splits | train **57** / heldout **13** | `world/world.json` `splits` |
| Difficulty | easy 2 / medium 29 / hard 24 / expert 15 | `world/world.json` `difficulty` |
| Distinct verifier checks | **104** | regex over the 70 `vcode` blobs (below) |
| Verifier check instances | **1 053** (mean **14.7**/task, min 11, max 21) | same |
| Verifier dimensions | correctness (72 checks) / deployment (13) / quality (19), weighted 0.6 / 0.3 / 0.1 | `_W` in every `vcode` |
| Reward kind | **`vcode` for 70/70** — no LLM judge anywhere in the score | `world/tasks.json` |
| Oracle trajectory length | mean **15.4** tool calls, min 5, max **34** (`tsk_auth_v1_to_v2`, `tsk_checkout_v1_to_v2`, `tsk_orders_v1_to_v2`) | `expected_calls` |

Check names were extracted with:

```python
re.compile(r"""_c\(\s*(['"])([a-z_]+)\1\s*,\s*(['"])([a-z0-9_]+)\3""")
```

over the `vcode` field of every task. (A naive single-quote-only regex finds 4
checks and is wrong; the world writes most check names in double quotes.)

### 0.2 The corpus under audit

The brief said 39 repos. There are **58** directories under `research/repos/`:

| Group | Cloned | With research notes |
|---|---:|---:|
| `evals/` | 21 | 9 |
| `automation/` | 12 | 6 |
| `mcp/` | 24 | 10 |
| `research/artifacts/` | 1 | — |
| **Total** | **58** | **25** |

This matters below. The tool inventory (`notes/mcp/_TOOL_INVENTORY.md`, 596 tools)
was compiled from **10 of the 24** cloned MCP servers, and the fourteen un-noted
servers include exactly the categories this audit is asked about — IaC,
communication, data/warehouse. They were therefore counted directly from source for
this document:

| Un-noted server | Tools | Counting idiom | Category |
|---|---:|---|---|
| `awslabs/mcp` | **848** across 62 server packages | tool-registration call sites (`mcp.tool(`, `@mcp.tool(`, `@app.tool(`, `.add_tool(`) | AWS cloud ops: IaC + k8s/deploy + observability + database + security |
| `googleapis/genai-toolbox` | **298** tool *kinds* (framework); **451** concrete tools across 38 prebuilt configs | `tools.Register(` / `^kind: tool` | data/warehouse/database |
| `zereight/gitlab-mcp` | **217** | `name: "` in `tools/registry.ts`; README numbers them 1–217 | source control + CI + issues |
| `tacticlaunch/mcp-linear` | **195** (test asserts ≥185 registered) | `name: 'linear_*'` in `src/tools/definitions/` | issue tracking |
| `cloudflare/mcp-server-cloudflare` | **155** across 18 apps | `context.registerTool(` / `context.accountTool(` | observability + logs |
| `dbt-labs/dbt-mcp` | **61** | `ToolName` enum members | data/warehouse |
| `hashicorp/terraform-mcp-server` | **57** | `ToolToToolset` registry map | **IaC** |
| `redis/mcp-redis` | **53** | `@mcp.tool` | database |
| `mongodb-js/mongodb-mcp-server` | **52** | `static toolName` on tool classes | database |
| `neondatabase/mcp-server-neon` | **35** | `NEON_TOOLS` array | database |
| `makenotion/notion-mcp-server` | **24** | OpenAPI `operationId` → MCP tool (README's "22" is stale) | knowledge base |
| `pydantic/logfire-mcp` | **4** | `mcp.tool()(fn)` — functional, not decorator | observability (traces + logs) |
| `stripe/agent-toolkit` | **0 locally defined** | stdio→`https://mcp.stripe.com` proxy; tools fetched at runtime | payments (out of taxonomy) |
| `slackapi/java-slack-sdk` | **0 — not an MCP server** | zero `modelcontextprotocol` references anywhere in the repo | (a plain Slack Java SDK) |

**Two corrections that follow, and both matter.**

*First, the real denominator is roughly four times what the inventory records.* Using
298 for `genai-toolbox` (the framework's tool kinds, the unit comparable to a fixed
server's tool list), the fourteen add **1 999** tools, taking the corpus's vendor
surface from 564 to about **2 563**. Matrix 2 reports both denominators; the larger
one is the honest headline.

*Second, `slackapi/java-slack-sdk` registers zero MCP tools* — it is the Slack SDK for
Java (Bolt + API client), not an MCP server. So the inventory's "no Slack" gap note
is not an artefact of sampling ten servers: **there is no Slack MCP surface anywhere
in the 24-repo corpus.** That makes the world's `post_message` / `list_messages` pair
coverage of something the entire corpus lacks, and it is recorded as such below
rather than as a percentage of nothing.

One further discrepancy worth recording, since both numbers are in this repo:
`notes/evals/microsoft__AIOpsLab.md` counts **89** registry problems;
`research/02-CORPUS-MAP.md` counts **100** problems / 33 fault families. They were
counted by different methods at different times. Neither is used as a denominator
here.

---

## 1. Matrix 1 — Task-type coverage

**Denominator.** 50 distinct agent task types identified across the benchmark
corpus. Types from `google-deepmind/mctx` (an MCTS library, not a benchmark),
`EleutherAI/lm-evaluation-harness` and `stanford-crfm/helm` (general NLP/LLM
leaderboards) are excluded as out-of-domain; that exclusion is stated rather than
hidden.

**Grading rule, applied strictly.** *COVERED* means the world tests the task on a
comparable substrate. *PARTIAL* means it tests the **shape** but not the
**substrate** — the load-bearing case being that the world abstracts code editing
into seven structured `change_type` payloads (`config`, `dependency`, `endpoint`,
`module`, `flag`, `flag_cleanup`, `test_fix`) and runs CI as a **SQL rule engine**
over `pr_changes`, not as `pytest` in a container.

| # | Task type | Defined by | Status | World task ids / mechanism | Notes |
|---|---|---|---|---|---|
| T1 | Resolve an issue with a code change, validated by a test suite | SWE-bench, SWE-agent, commit0, terminal-bench, TheAgentCompany `sde` | **PARTIAL** | 41 tasks carry `ci_all_stages_green`; `tsk_payments_retry_from_code`, `tsk_catalog_pricing_from_code` require reading real source in `repo_files` to find the offending constant | Shape faithful (PR → CI build/unit/integration/regression → merge). Substrate simulated: `run_ci` is a rule engine (`world/tools.json` → `run_ci.source_code`). **This is the corpus's one consensus task (8 of 9 repos) and the world's biggest structural gap.** |
| T2 | Difficulty-stratified / expert-verified variants of one task family | SWE-bench Lite + Verified | **PARTIAL** | `world/world.json` `difficulty` (2/29/24/15) and `splits` (57/13) | Strata are author-assigned, not human-verified solvability labels; no per-task human time estimate |
| T3 | Multilingual issue resolution with per-language execution | SWE-bench Multilingual (300), multi-swe-bench (1 632), SWE-bench-Live MultiLang (743) | **PARTIAL** | `repo_files` spans 6 languages | Languages present as *content*; nothing executes per-language |
| T4 | Multimodal issue resolution (screenshots, UI assets) | SWE-bench Multimodal (102 dev / 517 test) | **NOT COVERED** | — | No image surface |
| T5 | RAG patch generation from retrieved context | SWE-bench `inference/` (oracle / bm25 / all) | **NOT COVERED** | — | `search_code` / `read_file` exist; retrieval quality is never scored |
| T6 | Resolve a live GitHub issue from a URL and open a PR | SWE-agent | **NOT COVERED** | — | No network |
| T7 | Local repo, free-text problem statement | SWE-agent | **NOT COVERED** | — | No filesystem |
| T8 | Coding challenge (LeetCode-style) | SWE-agent `coding_challenge.yaml` | **NOT COVERED** | — | Out of domain |
| T9 | Free-form shell mode | SWE-agent `sweagent sh` | **NOT COVERED** | — | No shell tool by design |
| T10 | Human-in-the-loop driving the same interface | SWE-agent `human` model | **NOT COVERED** | — | — |
| T11 | CTF / offensive security | SWE-agent EnIGMA (v0.7), terminal-bench `cybench` | **NOT COVERED** | — | — |
| T12 | **Detection** — "is there an anomaly?" | AIOpsLab (34 problems) | **COVERED** | `tsk_detect_checkout_errors`, `tsk_detect_inventory`, `tsk_detect_payments`, `tsk_detect_storefront_healthy` | Checks `detection_correct`, `diagnosis_submitted`. `tsk_detect_storefront_healthy` is the AIOpsLab-style no-op control |
| T13 | **Localization** — name the faulty service | AIOpsLab (28) | **COVERED** | `tsk_localize_analytics_crashloop`, `…_analytics_errors`, `…_checkout_latency`, `…_gateway_latency`, `…_media_latency`, `…_search_latency` | Check `service_localized` (10 instances) |
| T14 | **Analysis** — root-cause classification (level × fault type) | AIOpsLab (13) | **COVERED** | `tsk_rca_catalog_n_plus_one`, `…_inventory_pool`, `…_notifications_timeout`, `…_payments_retry` | Checks `fault_confirmed`, `fault_type_correct`, `offending_key_correct` |
| T15 | **Mitigation** — remediate, verified by live system state | AIOpsLab (14) | **COVERED** | **50** change-making tasks (all categories except the 20 diagnostic/reconciliation ones), of which **44** are deploy-bearing | Checks `metric_within_slo` (11), `alarm_resolved` (11), `config_deployed_to_production` (15), `vulnerability_remediated` (4). **The world has ~3.5× AIOpsLab's mitigation count** |
| T16 | Runtime fault **injection** with self-healing chaos | AIOpsLab (8 injector classes, 22 inject/recover pairs, `duration: 200s`) | **PARTIAL** | Faults are statically seeded config/state defects | No Chaos-Mesh analogue (`pod_failure`, `network_loss`, `container_kill`), no timed self-heal, no eBPF/disk faults. See `02-CORPUS-MAP.md` for the family-by-family map |
| T17 | Multi-turn dialogue with an **LLM-simulated customer** | tau-bench (165) | **NOT COVERED** | `world/personas.json` holds 5 personas | Personas are metadata, not a simulator. Instructions are one-shot |
| T18 | Adhere to a **written domain policy** the tools do not enforce | tau-bench `wiki.md` (81 / 70 lines) | **COVERED** | 30 `documents` + `search_docs`/`get_document`; enforced by `staging_first` (42 tasks), `canary_then_promote` (27), `ack_before_resolve` (11), `deprecate_before_shift` (7) | Task text: *"NovaCart's engineering policies are documented in the knowledge base and are not optional."* Tools permit the violation; the verifier catches it — the same contract as tau-bench airline |
| T19 | Zero-action "change nothing" trap | tau-bench (2 retail / 7 airline) | **PARTIAL** | 20 tasks carry `investigation_was_read_only`; `tsk_detect_storefront_healthy` is the healthy control | Not a true zero-side-effect task: the agent must still close the ticket (`ticket_closed`) |
| T20 | Whole-DB state hash vs replayed gold actions | tau-bench (`base.py:121-164`) | **PARTIAL** | `world_invariants_intact` (70 tasks): 15 orphan-row queries + contiguous append-only audit assertion + SHA-256 over the seeded audit prefix; plus `_FROZEN` SHA over **29** reference tables and `_FIXED_ROWS` over **5** more | Path-agnostic like tau-bench, but by named predicates rather than one hash. Arguably stronger (localises the violation); definitely different |
| T21 | Multi-app workflow across several real self-hosted services | TheAgentCompany (175 across GitLab/ownCloud/RocketChat/Plane) | **PARTIAL** | 11 distinct vendor surfaces, 23 vendor-mirrored tools (§2) | Typed tools over SQLite, not real services behind a browser |
| T22 | Interrogate an NPC colleague for information held nowhere else | TheAgentCompany (41 tasks, 18 personas) | **NOT COVERED** | `post_message` / `list_messages` (6 seeded messages, 4 channels) | Nothing replies |
| T23 | Weighted checkpoint scoring with partial credit | TheAgentCompany (661 points, median 3 checkpoints/task) | **COVERED** | 3 weighted dimensions, mean 14.7 checks/task; correctness+deployment hard-fail, quality soft-flags | Different formula (`0.6/0.3/0.1` dimension-normalised vs `0.5·(r/t)+0.5·⌊r/t⌋`), same intent, ~5× the density |
| T24 | LLM-judged checkpoints inside the score | TheAgentCompany (53/175), AIOpsLab (opt-in) | **NOT COVERED — by design** | `llm_quality_score` exists in `eval_model.py:302` but is never summed into the verdict | Deliberate. Recorded here as a coverage fact, not a defect |
| T25 | Non-SWE office job families (HR, finance, admin) | TheAgentCompany (56 tasks) | **NOT COVERED** | — | Out of domain; see `02-CORPUS-MAP.md` |
| T26 | Data-science pipeline graded by metric thresholds | TheAgentCompany `ds` (14), mle-bench (75) | **NOT COVERED** | — | Out of domain |
| T27 | Arbitrary terminal task via raw tmux keystrokes | terminal-bench (241; leaderboard 80) | **NOT COVERED** | — | No terminal |
| T28 | Oracle-must-pass / nop-must-fail authoring gate | terminal-bench (`test-tasks.yaml:255-276`), commit0 `evaluate-reference` | **COVERED** | `eval_model.py`: `run_oracle_episode`, `run_naive_episode`, plus `merged_only_calls`, `no_verify_calls`, `shortcut_calls` counterfactual policies; `world/verifier_accuracy_receipt.json` (5 corruption kinds) | **Caveat: the receipt is stale** — `world_id` `env_software_devops_bb2fe89d`, 63 tasks, generated 07:15Z, against a world that is now `8b9d74de` with 70 tasks. Must be regenerated |
| T29 | Human expert/junior time estimates as a difficulty anchor | terminal-bench (`expert_time_estimate_min`) | **NOT COVERED** | — | — |
| T30 | Hosting other benchmarks via adapters | terminal-bench (19 datasets, 13 adapters), commit0 (3 spec types) | **NOT COVERED** | — | Not a goal of this world |
| T31 | Rebuild a whole library from docstrings + spec | commit0 (56 repos, ~140 926 tests) | **NOT COVERED** | — | — |
| T32 | Lint + type-check as a gate alongside tests | commit0 (ruff + pyright) | **NOT COVERED** | — | CI has no lint stage |
| T33 | Topologically ordered multi-file synthesis | commit0 | **NOT COVERED** | — | — |
| T34 | Fix a real bug verified by **browser E2E** | SWE-Lancer IC (198), WebArena, OSWorld | **NOT COVERED** | — | — |
| T35 | **Judgement task — choose the best human proposal, produce no artifact** | SWE-Lancer manager (265 of 463) | **NOT COVERED** | — | The corpus's best cost-to-difficulty ratio: **47.2 % manager vs 51.5 % IC**, integer-match graded, flake-free. The world has the submission channel (`submit_answer`) and no such task |
| T36 | Monetary task weighting | SWE-Lancer (`price`, ~$500 K across Diamond) | **NOT COVERED** | Difficulty tiers only | `notes/domain/A_business_value.md` exists; no task carries a value |
| T37 | Typed multi-axis usage limits (tokens / actions / seconds / cost) | vivaria (`RunUsage`), SWE-agent (`per_instance_cost_limit $3.00`) | **PARTIAL** | `eval_model.py --max-turns`, per-task turn budget = `max(6, steps × 1.6)` | One axis, no cost, no wall-clock |
| T38 | Intermediate scoring / score trajectory | vivaria (`intermediate_score`, `ScoreLog`) | **NOT COVERED** | Single terminal verification | The only mechanism in the corpus for measuring progress *during* an episode |
| T39 | Human-scored terminal state | vivaria (`RunStatus.MANUAL_SCORING`) | **NOT COVERED — by design** | — | Deterministic-only is a stated design choice |
| T40 | Typed **error-source attribution** (`agent / server / task / serverOrTask / user / usageLimits`) | vivaria (`shared/src/types.ts:430-441`) | **NOT COVERED** | `eval_model.py` records `passed` + a free-text `error` | The cross-corpus note calls this *"the most important finding in the corpus"*. See §7 |
| T41 | Agentless environment for human baselining | vivaria (`viv task ssh`) | **NOT COVERED** | — | — |
| T42 | Polyglot containerised issue resolution | SWE-bench-Live, multi-swe-bench | **PARTIAL** | Same as T1/T3 | — |
| T43 | Synthetic-bug **task factory** over arbitrary repos | SWE-smith (52 k instances, 250+ envs) | **PARTIAL** | `build/task_specs.py` (70 specs) + `build/tasks_def.py` generate tasks and verifiers programmatically | Generates from curated specs, not from arbitrary repos; no procedural bug injection |
| T44 | OS / sysadmin shell task | AgentBench `os` (18 task files), OSWorld `os` (24) | **NOT COVERED** | — | — |
| T45 | Write SQL against a live database | AgentBench `dbbench` (300) | **NOT COVERED** | Tools are typed; the agent never writes SQL | — |
| T46 | Operate a desktop GUI application | OSWorld (369) | **NOT COVERED** | — | — |
| T47 | Operate a web app through a real browser (incl. the GitLab slice) | WebArena (812; gitlab 180) | **PARTIAL** | The same *operations* — issues, PRs, merges, project state — as typed tools | The 180 WebArena GitLab tasks are shape-equivalent to the world's PR/issue surface; the browser is not |
| T48 | Static function completion from a docstring | bigcode-evaluation-harness, CodeRL | **NOT COVERED** | — | Non-agentic; out of domain |
| T49 | Deliberately **infeasible** task where refusal is correct | OSWorld (`test_infeasible.json`) | **NOT COVERED** | — | No task in the world can be correctly refused. See §7 |
| T50 | Fault-family × task-type cross product as the unit of coverage | AIOpsLab (100 problems = 33 families × 4 types) | **PARTIAL** | 11 categories × 4 diagnostic types is partially crossed | Documented family-by-family in `02-CORPUS-MAP.md`: 21 covered, 10 partial, 0 not covered of 33. The six added are all infrastructure-level (`disk_woreout`, `assign_to_non_existent_node`, `kernel_fault`, `operator_security_context`), which is where AIOpsLab's catalogue is concentrated and where a service's own metrics, logs and source are structurally blind |

### 1.1 Task-type score

| | Count | Share |
|---|---:|---:|
| COVERED | **7** | 14 % |
| PARTIAL | **11** | 22 % |
| NOT COVERED | **32** | 64 % |
| **≥ PARTIAL** | **18** | **36 %** |

That headline is unflattering and should be read with its structure. Of the 32
NOT COVERED rows, **25 require a substrate the world does not have and was not
built to have** — a real container, a real browser, a real OS, a terminal, an LLM
in the loop, or a human scorer (T4–T11, T17, T22, T24–T27, T30–T34, T39, T41,
T44–T46, T48). **Seven are buildable inside the present substrate today**: T5, T29,
T35, T36, T38, T40, T49. Those seven are the actionable list, and they drive §8.

Conversely, six task types are **world-native and appear in no corpus benchmark**.
They are not in the denominator above (you cannot score coverage of yourself), but
they are the substance of §6:

| World-native type | Tasks | Why no benchmark has it |
|---|---:|---|
| Cross-tool reconciliation over contradictory sources | 6 | `_CROSS_CUTTING.md §8.2`: *"Every benchmark has exactly one source of truth."* |
| Enforced end-to-end delivery pipeline (PR → CI → merge → migrate → staging → canary → promote → observe → resolve → close) | 41 | No benchmark grades ordering across ten stages |
| Deprecation-and-drain API migration | 7 | — |
| Feature-flag lifecycle (code → ramp → cleanup / killswitch) | 7 | — |
| Flaky-test repair with "fix, don't quarantine" + 3 green main runs | 6 | — |
| CVE remediation and secret-leak response | 7 | AIOpsLab has zero security problems; only terminal-bench's `cybench` adapter touches security |

---

## 2. Matrix 2 — Tool-surface coverage

**Denominators.** Counted directly from the tables in
`notes/mcp/_TOOL_INVENTORY.md` (tool names in backticks in the first column of
every category table). That yields **601** categorised tool-name slots against the
document's **596** unique-tool headline; the gap is the small number of tools filed
in two categories or registered twice (`get_label` is registered twice in GitHub —
117 registrations for 116 names; `list_incidents` exists in both Grafana and
PagerDuty). **37** of the 601 are `mcp/*` reference servers (filesystem, git, time,
memory, fetch, everything, sequentialthinking), which are agent infrastructure
rather than a vendor surface. The **inventoried vendor denominator** used in the
table below is therefore **564**.

That denominator is not the whole corpus. The fourteen servers counted in §0.2 add
**1 999** more vendor tools, giving a **full cloned-corpus denominator of ≈2 563**.
The table's per-category "Real tools" column uses the inventoried figure, because
that is the only figure with a *category breakdown* behind it; the three categories
where the un-noted servers dominate (IaC, data/warehouse, communication) are stated
with their real counts inline. §2.1 reports the score against both.

World-side, all 74 tools are classified exhaustively (the 74 sum to 74; the mapping
is reproducible from `world/tools.json` `read_tables`/`write_tables`).

| Category | Real tools | World tools | % | World tool names | What is missing that matters |
|---|---:|---:|---:|---|---|
| Source control (repos, files, commits, branches) | 43 | 6 | 14 % | `list_files`, `read_file`, `search_code`, `list_commits`, `list_packages`, `list_api_endpoints` | No write path to files at all — no `create_or_update_file`, `push_files`, `create_branch`. Blame, tree, tags, releases absent |
| Code review / pull requests | 23 | 4 | 17 % | `list_pull_requests`, `get_pull_request`, `open_pull_request`, `merge_pull_request` | **No review surface whatsoever**: no review submission, no inline comments, no reviewer requests, no thread resolution. GitHub devotes 23 tools to this; the world grades `pr_has_description` and stops |
| CI/CD & build | 10 | 4 | 40 % | `list_ci_runs`, `get_ci_run`, `run_ci`, `list_tests` | Highest-ratio category, because the corpus itself is nearly empty here — the inventory records that 4 GitHub Actions + 6 Tekton tools are the *entire* CI surface across ten servers. No job logs, no re-run-failed |
| Issue tracking & project management | 87 | 9 | 10 % | `list_tickets`, `get_ticket`, `create_ticket`, `update_ticket`, `jira_search`, `jira_get_issue`, `linear_list_issues`, `github_list_issues`, `list_issue_links` | No sprints/boards/epics, no per-project workflow transitions, no changelogs, no worklogs, no sub-issues or dependencies. **But the world has the cross-tracker link table that no real server exposes** |
| Observability — metrics & dashboards | 73 | 5 | 7 % | `query_metrics`, `get_traffic_stats`, `get_slo_status`, `query_prometheus`, `list_prometheus_label_values` | **No dashboards at all** (Grafana devotes 17 tools + 5 datasource tools to them), no annotations, no Sift/Asserts, no CloudWatch/Graphite. Only **2** metric names exist world-wide (`error_rate_pct`, `latency_p99_ms`) vs AIOpsLab's 24 cAdvisor metrics |
| Logs | 14 | 1 | 7 % | `search_logs` | 15 seeded log rows. No label discovery, no LogQL/ES\|QL, no pattern analysis, no `pods_log`/`nodes_log` |
| Traces & profiles | 10 | **0** | **0 %** | — | No traces, no spans, no flame graphs, no replays. AIOpsLab hands the agent Jaeger; the world hands it nothing. **The largest single hole in the observability surface** |
| Cluster telemetry (k8s events / top / mesh / flows) | 16 | 2 | 13 % | `k8s_events_list`, `k8s_pods_list` | Present *and load-bearing* (the OOMKill blind spot) but thin: 6 pods, 4 events, one namespace. No `pods_top`, no mesh graph, no flows |
| Error tracking | 47 | 4 | 9 % | `list_error_events`, `resolve_error_event`, `sentry_search_issues`, `sentry_list_projects` | No stack traces, breadcrumbs, releases, or user reports. Sampling *is* modelled (`sentry_projects.sample_rate`), which is the part that matters |
| Incident management & status page | 28 | 7 | 25 % | `list_incidents`, `create_incident`, `update_incident`, `pd_list_incidents`, `get_status_page`, `publish_status_update`, `list_status_page_posts` | No responders, no incident workflows, no notes/log entries, no postmortem object. **Write path to the status page exists — rare and correct** |
| Alerting | ~40 (Grafana rules 4 + PagerDuty orchestration/status/analytics 36) | 3 | 8 % | `list_alerts`, `acknowledge_alert`, `resolve_alert` | No alert **rules**, no routing, no grouping, no silences, no inhibition — which is exactly why CS-28 is ABSENT (§3) |
| On-call & service catalog | 44 | 5 | 11 % | `pd_list_oncalls`, `pd_list_services`, `pd_list_change_events`, `list_services`, `get_service` | No schedules/rotations/overrides/escalation-policy CRUD. PagerDuty spends 39 tools here, a third of them v2/v3 duplicates, so the ratio overstates the loss |
| Kubernetes / deploy / infrastructure | 28 | 11 | 39 % | `list_infra`, `list_deployments`, `list_migrations`, `apply_migration`, `deploy_service`, `assess_canary`, `promote_canary`, `rollback_deployment`, `set_feature_flag`, `shift_endpoint_traffic`, `list_feature_flags` | **The world is broader than the corpus here.** The inventory records that the real k8s server has *no* rollout verb, no cordon/drain, no helm upgrade/rollback, and that **no feature-flag server exists in the corpus at all**. Canary assess/promote and traffic shifting exist nowhere in the corpus |
| Infrastructure as code | **57** (`hashicorp/terraform-mcp-server`, `ToolToToolset` map; 58 `mcp.NewTool(` constructors because `create_run` has safe/destructive variants) + an uncounted share of `awslabs/mcp`'s 848 | **0** | **0 %** | — | The inventory's own gap note is *"no Terraform"* — true of the ten inventoried servers, false of the corpus. There is a full 57-tool Terraform surface (`search_providers`, `list_workspaces`, `create_run`, `get_plan_logs`, `get_apply_logs`, `create_workspace_variable`, `delete_workspace_safely`). The world has `apply_migration` and nothing else: no plan, no state, no drift, no workspace |
| Security scanning | 15 | 1 | 7 % | `list_vulnerabilities` | No SAST/secret-scanning/SCA distinction, no advisories, no severity scales that disagree. The inventory's key finding — *"Not one server can create a security exception, dismiss an alert, or open a fix PR from a finding"* — is **inverted** in the world, which grades the remediation |
| Knowledge base & documentation | 37 (excl. 9 `mcp/memory`) | 4 | 11 % | `search_docs`, `get_document`, `confluence_search`, `confluence_get_page` | **No staleness-signal tools** — Confluence uniquely exposes `get_page_history`, `get_page_diff`, `get_page_views`, and the inventory calls this *"the clearest case in the corpus where the right behaviour is to check provenance."* The world seeds a `stale` flag and `last_updated_day` but gives the agent no tool to interrogate provenance |
| Communication / chat | **11** (GitHub discussions + notifications). **No chat server exists in the corpus**: `slackapi/java-slack-sdk` registers 0 MCP tools — verified, zero `modelcontextprotocol` references in the repo | 2 | 18 % | `post_message`, `list_messages` | The world's two tools cover a surface the **whole 24-repo corpus lacks**. Thin in absolute terms (4 channels, 6 seeded messages, nothing replies) but not behind the corpus |
| Design | 2 | **0** | **0 %** | — | Figma. Deliberately out of scope |
| Data / warehouse / database | **213** counted: Grafana 12 (ClickHouse/Snowflake/Athena/InfluxDB) + `dbt-labs/dbt-mcp` 61 + `redis/mcp-redis` 53 + `mongodb-js/mongodb-mcp-server` 52 + `neondatabase/mcp-server-neon` 35. Plus `googleapis/genai-toolbox` — 298 tool *kinds* / 451 prebuilt tools, a framework rather than a fixed server, so excluded from the 213 | 2 | **0.9 %** | `read_owner_spreadsheet`, `query_local_deploy_log` | Neither is a warehouse. They are the *shadow* data sources — a hand-maintained sheet, a team's local SQLite — which is the more interesting half of the problem and is where CS-05/CS-24/CS-26 live. Warehouse and database querying is genuinely absent, and this is the largest counted category the world does not touch at all |
| Identity, teams & permissions | 27 | **0** | **0 %** | — | The inventory's Overlap 13: *"identity has no shared key"* — every cross-tool attribution question ("who deployed this") depends on a join no server provides. The world sidesteps it by giving `services` an `oncall_engineer` field |
| Agent infrastructure (excluded from denominator) | 37 | 4 | — | `submit_diagnosis`, `submit_answer`, `resolve_service_alias`, `list_service_aliases` | `resolve_service_alias` has no real-world counterpart; it is the world's own affordance making CS-01 solvable rather than cruel |

### 2.1 Tool-surface score

| Denominator | Basis | Score |
|---|---|---:|
| **564** | the 10 inventoried MCP servers, minus 37 reference-server tools | **74 / 564 = 13.1 %** |
| **≈2 563** | all 24 cloned MCP servers (inventoried 564 + 1 999 counted in §0.2) | **74 / 2 563 = 2.9 %** |

**2.9 % is the honest headline.** Per-category coverage runs from **0 %** (traces,
IaC, design, identity) through **0.9 %** (data/warehouse) to **40 %** (CI/CD).

The 1 999 additional tools are heavily concentrated in surfaces the world does not
model and, for the most part, should not: 848 AWS-service tools across 62 packages,
298 database tool kinds in a YAML framework, 217 GitLab tools, 195 Linear tools. But
two of them are real gaps rather than scope decisions — the 57-tool Terraform
surface (§7) and the 213-tool database/warehouse surface.

Three honest caveats, in both directions.

*Against the world:* a raw tool-count ratio flatters it in categories where the
real servers are read-heavy and the world implements only the one read that
matters. Observability at 7 % is a fair reflection; error tracking at 9 % is not,
because 4 tools cover a surface that in Sentry needs 47.

*For the world:* the denominator contains substantial duplication that is not
capability — PagerDuty's schedule v2/v3 overlap, `get_label` registered twice, and
Grafana's `grafana_api_request` raw passthrough that can answer any Grafana
question on its own. And **23 of the world's 74 tools are named after the real
servers** (`jira_search`, `jira_get_issue`, `linear_list_issues`,
`github_list_issues`, `query_prometheus`, `list_prometheus_label_values`,
`sentry_search_issues`, `sentry_list_projects`, `pd_list_incidents`,
`pd_list_services`, `pd_list_oncalls`, `pd_list_change_events`,
`list_status_page_posts`, `confluence_search`, `confluence_get_page`,
`k8s_events_list`, `k8s_pods_list`, …), so an agent that has seen the real MCP
servers transfers directly. tau-bench, by contrast, invents 16 + 14 tool names that
exist nowhere.

*Against any ratio at all:* tool count is a poor proxy for capability in both
directions, and the counting itself is not uniform — `googleapis/genai-toolbox`
counts 298 or 451 depending on whether you mean tool kinds or shipped configs;
`stripe/agent-toolkit` defines 0 locally and fetches its list from a hosted server
at runtime; `zereight/gitlab-mcp` registers 217 but gates most behind
`GITLAB_TOOLSETS` feature flags so far fewer are live in a default session. Read
13.1 % / 2.9 % as an order of magnitude, not a measurement.

---

## 3. Matrix 3 — Chaos-scenario coverage (CS-01 … CS-30)

Source: `notes/domain/F_chaos_scenarios.md`. The file's prose says "CS-01 … CS-27"
but it defines **30** numbered scenarios (CS-28, CS-29, CS-30 are inserted in
themes 5 and 6). All 30 are graded.

A note on labelling: `build/vendors.py` carries CS-## comments, and two of them
disagree with the F-file's own numbering — the `nonprod` substring trap is CS-**06**
in `F_chaos_scenarios.md` and is commented `CS-07` at `build/vendors.py:297` and
`:401`. The instantiation is right; the label is off by one. Graded against the
F-file.

| # | Scenario | Status | World artifact |
|---|---|---|---|
| CS-01 | One service, three-plus names across tools | **INSTANTIATED** | `build/vendors.py:204-224` `ALIASES` → `service_aliases` (16 rows, 6 naming systems: kubernetes / pagerduty / prometheus / sentry / confluence / spreadsheet). Tools `resolve_service_alias`, `list_service_aliases`. Tasks `tsk_rcn_checkout_error_rate`, `tsk_rcn_gateway_owner`, `tsk_rcn_running_version` |
| CS-02 | Unified tagging not achievable; metrics missing the service tag | **PARTIAL** | Aliases exist for 4 of 10 services only. The *absent-tag* failure (a series with no `service` label at all) is not seeded |
| CS-03 | OTel attribute renamed; dual emission live | **ABSENT** | No dual-spelled attribute anywhere; environment is a plain column |
| CS-04 | Environment does not participate in service identity | **PARTIAL** | `prom_series` carries both `production` and `nonprod-staging` for `checkout_service` (`build/vendors.py:288-299`), so a naive distinct-(service, env) count differs from the true service count. No task scores the identity rule |
| CS-05 | Catalog owner points at a dissolved team | **INSTANTIATED** | `owner_spreadsheet` row 4 `("Gateway (platform)", "Edge Team", …, last_reviewed_day=180)` at `build/vendors.py:369-378`; `confluence_pages` 8002 `stale=1`. Task `tsk_rcn_gateway_owner`; checks `answer_correct` (=419), `consulted_owner_spreadsheet`, `consulted_pd_services`, `consulted_pd_oncall` |
| CS-06 | `nonprod` matched as production by a substring | **INSTANTIATED** | `local_deploy_log` rows with `environment='nonprod-staging'` (`build/vendors.py:401`) and two `prom_series` rows likewise. Task `tsk_rcn_production_deploys`; the oracle assumption names the trap verbatim |
| CS-07 | No agreed environment vocabulary | **PARTIAL** | Only `production` / `staging` in `env_state`, plus the `nonprod-staging` spelling in the shadow log. No UAT / pre-prod / stage / live spread |
| CS-08 | Rate extrapolation and counter resets | **INSTANTIATED** | `prom_series` row `("http_errors_total:rate5m", "checkout_service", "production", 420, 2.1, counter_reset=1)` at `build/vendors.py:293-294`. Task `tsk_rcn_checkout_error_rate` (expected 5.5 from day 419, tolerance 0.2) |
| CS-09 | Percentiles cannot be averaged | **ABSENT** | `service_metrics` has exactly two metric names and one fleet-level scalar each. No per-instance quantiles, no histogram buckets, no averaging trap |
| CS-10 | Dual-write metric migration, unvalidated | **PARTIAL** | Three metric surfaces exist and disagree (`service_metrics`, `prom_series`, `sentry_issues`), but no declared dual-write phase and no task about reconciling two TSDBs mid-migration |
| CS-11 | Duplicate bugs with inconsistent severity | **INSTANTIATED** | `ENG-3001` (Jira, Medium) vs `GRW-88` (Linear, priority 1 = urgent) vs GitHub `4412` — `build/vendors.py:229-259`. Task `tsk_rcn_distinct_checkout_bugs` (expected 1) |
| CS-12 | Cross-tracker sync produces structural duplicates | **INSTANTIATED** | `issue_links` (4 rows, `build/vendors.py:260-266`); tool `list_issue_links`; check `consulted_issue_links` |
| CS-13 | Orphaned monitors for services that no longer exist | **ABSENT** | All 10 rows of `alerts` reference live rows of `services` |
| CS-14 | Dashboard sprawl / stale dashboards | **ABSENT** | No dashboard table, no dashboard tool |
| CS-15 | Alert actionability is low | **ABSENT** | All 10 firing alerts are real SLO breaches. No noise, no false positives |
| CS-16 | 100+ SaaS apps as the substrate | **PARTIAL** | 11 vendor surfaces + the native platform — realistic in shape, two orders of magnitude below the cited figure |
| CS-17 | Half-migrated systems as a deliberate architecture | **INSTANTIATED** | `api_migration` (7 tasks); endpoints carry `active \| deprecated \| retired`, `traffic_profile` splits between v1 and v2. Checks `legacy_retired`, `replacement_active`, `legacy_traffic_drained`, `replacement_serving_all_traffic` |
| CS-18 | "How many customer-facing incidents last week?" | **INSTANTIATED** | `status_page_posts` (3 rows, `build/vendors.py:324-330`) — impact lives *only* here; `confluence_pages` 8004 writes the severity ladder down; incident 5106 was customer-visible and never posted. Task `tsk_rcn_customer_facing_incidents` (expected 2) |
| CS-19 | "What changed before this incident?" | **PARTIAL** | All the change surfaces exist (`pd_change_events`, `deployments`, `local_deploy_log`, `migrations`, `feature_flags`, 417 `commits`) and `tsk_gateway_v510_rollback` requires finding the bad release. But no task places the trigger in an *unrelated subsystem*, which is the whole point of the Cloudflare case |
| CS-20 | "Which services are affected by CVE-X?" | **INSTANTIATED** | `vulnerabilities` (4 rows) + `list_packages` over `repo_state`/`env_state`. Tasks `tsk_cve_libpayproc`, `tsk_cve_pydantic`, `tsk_cve_requests`, `tsk_cve_stripe_sdk`; check `vulnerability_remediated` |
| CS-21 | Severity ladders are not portable | **PARTIAL** | Every vocabulary is present and they disagree: PagerDuty `urgency` high/low **and** `priority` P1–P4 (`build/vendors.py:312-323`), Jira Highest…Low, Linear 0–4, world `incidents` sev1/sev2, `alerts` critical/high/medium, and `confluence_pages` 8004 defines the ladder. **No task is scored on getting the mapping right** — it survives only in free-text `assumptions` |
| CS-22 | MTTR is statistically invalid | **ABSENT** | No MTTR task. `pd_incidents` carries `created_day`/`resolved_day`, so the data would support one |
| CS-23 | Are postmortem action items done? | **PARTIAL** | One task carries `postmortem_filed`. No task joins postmortem → tracker → deploy history |
| CS-24 | "This week" has four defensible answers | **PARTIAL** | The conflict is seeded — `owner_spreadsheet.week_start='sunday'` (`build/vendors.py:377`) vs `confluence_pages` 8003 ("Monday to Sunday, ISO-8601, UTC"). **But both windowed tasks state "days 414-420 inclusive" in the instruction**, which defuses the trap before the agent meets it |
| CS-25 | Timezone is a per-dashboard setting | **ABSENT** | Time is an integer `day` throughout. No timezones exist |
| CS-26 | Do rolled-back deploys count? | **INSTANTIATED** | `local_deploy_log` `("api-gateway","v5.0.9","production",417,was_rollback=1)` at `build/vendors.py:400`. Tasks `tsk_rcn_production_deploys` (excludes rollbacks) and `tsk_gateway_v510_rollback` (checks `rollback_tool_used`, `bad_deploy_marked_rolled_back`, `rolled_back_to_good_version`) |
| CS-27 | Is this an incident at all? | **PARTIAL** | `tsk_detect_storefront_healthy` is a genuine no-fault control and 4 detection tasks answer yes/no. The Google-SRE-vs-ITIL definitional conflict is not present and no task turns on it |
| CS-28 | 1 failure ≠ N alerts ≠ M pages ≠ P incidents | **ABSENT** | The four object types exist (10 `alerts`, 3 `incidents`, 7 `pd_incidents`, 3 `status_page_posts`) but there is **no grouping, inhibition, silence or dedup-key model**, and no task asks "were we paged for this" |
| CS-29 | ≥2 monitoring tools; mean ~5 | **INSTANTIATED** | Four surfaces answer "what is checkout's error rate": `service_metrics` (5.5), `prom_series` (7.8/141 on day 419; 2.1 after a reset on 420), `sentry_issues` (sampled at 0.25 — `sentry_projects`), and `k8s_pods`/`k8s_events` (the OOMKill Sentry structurally cannot see, `build/vendors.py:343-372`). Tasks `tsk_rcn_checkout_error_rate`, `tsk_localize_analytics_crashloop` |
| CS-30 | Kubernetes namespace sameness across clusters | **ABSENT** | `k8s_pods` has one namespace (`production`) and no cluster dimension |

### 3.1 Chaos score

| | Count | Share |
|---|---:|---:|
| INSTANTIATED | **11** | 36.7 % |
| PARTIAL | **10** | 33.3 % |
| ABSENT | **9** | 30.0 % |
| **≥ PARTIAL** | **21** | **70 %** |

The instantiated eleven cluster tightly around the reconciliation suite — six tasks
carrying twelve distinct `consulted_*` source checks. The nine absences cluster
just as tightly around **alerting mechanics** (CS-13, CS-14, CS-15, CS-28),
**statistical traps** (CS-09, CS-22) and **time** (CS-25). Those are the two
buildable clusters; see §8.

One soft spot inside an INSTANTIATED row, recorded because it is checkable:
`tsk_rcn_checkout_error_rate` expects `5.5`, and `query_metrics(service='checkout')`
returns `error_rate_pct = 5.5` in a single call. The verifier does force the harder
path with `consulted_prom_series`, but `answer_correct` on its own is reachable
without ever meeting the counter-reset or the sampling rate.

---

## 4. Matrix 4 — Workflow-discipline coverage

Source: `notes/automation/_WORKFLOW_PATTERNS.md` §4, which proposes **27** candidate
verifier checks (V1–V27) derived from six agent harnesses. ENFORCED means a named
check in a `vcode` block tests it; check names below are the literal second argument
to `_c(...)` in `world/tasks.json`.

### 4.1 The 27 candidate checks

| # | Candidate check | Status | World check(s) — with task counts |
|---|---|---|---|
| V1 | A test/build ran after the last mutation, exit 0, before completion | **ENFORCED** | `ci_all_stages_green` (41), `three_green_main_runs` (6), `ci_stages_{catalog,checkout,payments,inventory,search,notifications}` (13 more instances). *Caveat: over a simulated CI* |
| V2 | Completion claims entailed by the trace | **PARTIAL** | No free-text completion payload exists, so entailment has nothing to check; the structured analogue is `evidence_recorded` (14) and `answer_submitted` + 12 `consulted_*` checks (6 tasks) |
| V3 | Said it would call a tool, then did not | **NOT ENFORCED** | Requires parsing natural-language intent |
| V4 | No N identical `(tool, canonical args)` calls in a row | **PARTIAL** | `no_unproductive_ci_loops` (70) caps repeated `run_ci` on one PR at 6. No general loop signature — cline's `loop-detection.ts` algorithm is not ported |
| V5 | Every modified file was read first | **NOT ENFORCED** | No file-write tool exists; changes are structured payloads |
| V6 | Independent reads batched, not serialised | **NOT ENFORCED** | `efficient_investigation` (14) caps total investigation calls — a budget, not a parallelism measure |
| V7 | Budget cap recorded as its own outcome (`capped`), not pass/fail | **NOT ENFORCED** | `eval_model.py` has `--max-turns`; the outcome collapses to `passed` |
| V8 | No tool call outside the declared allowlist | **NOT ENFORCED** | Tasks carry `required_tools` (mean 10.3, max 16) but nothing denies extras. Closest: `investigation_was_read_only` (20) |
| V9 | Failure classified `{model, harness, environment, transient, auth, policy}` before scoring | **NOT ENFORCED** | See §7 — this is the single most-cited design recommendation in the corpus |
| V10 | No file outside the blast radius modified | **ENFORCED** | `scoped_change_no_fabricated_data` (70, via `_blast_radius()`), plus `no_unrelated_config_mutation` (15), `no_unrelated_flag_mutation` (6), `no_unrelated_test_mutation` (6), `no_unrelated_endpoint_mutation` (2), `no_unrelated_incident_mutation` (2), `staging_untouched` (1), `staging_flag_untouched` (1) |
| V11 | No secret in files, argv, transcript or final message | **PARTIAL** | `no_new_hardcoded_secrets` (70) greps `repo_files` for `pk_live_`; `secret_removed_from_source` + `secret_manager_enabled` (1 task). **argv and transcript are not scanned**, and the cookbook's point is that both are leak surfaces a simulator records and can therefore check |
| V12 | No destructive op without an approval event | **NOT ENFORCED** | No destructive ops exist in the tool surface. `rollback_deployment` is legitimate (`rollback_tool_used`, 1) |
| V13 | Read-only task leaves the world byte-identical | **ENFORCED** | `investigation_was_read_only` (20) + `world_invariants_intact` (70) + `_FROZEN` SHA-256 over 29 reference tables + `_AUDIT_PREFIX` SHA over the seeded audit prefix |
| V14 | Approval-gated side effects have a preceding approval | **PARTIAL** | The world enforces **ordering gates** rather than human approvals: `staging_first` (42), `canary_then_promote` (27), `ack_before_resolve` (11), `deprecate_before_shift` (7), `drain_before_retire` (7), `rollout_order` (7), `staged_traffic_shifts` (7), `code_before_flag_enable` (4), `consumer_before_retire` (3), `migration_before_deploy` (1). **No human-approval object exists** |
| V15 | Every DoD item satisfied by an observable state fact | **ENFORCED** | The entire design: 104 named checks, all SQL over the post-episode database. Nothing is judged |
| V16 | Every factual assertion carries a resolvable citation | **PARTIAL** | `evidence_recorded` (14), 12 distinct `consulted_*` checks, `security_audit_note` (5), `pr_has_description` (41). Citation *resolvability* is checked for sources, not for individual claims |
| V17 | No hallucinated entity in the report | **PARTIAL** | `scoped_change_no_fabricated_data` (70) catches fabricated **world rows**; `service_localized`, `fault_type_correct`, `offending_key_correct` constrain submitted findings to real entities. Free text is unscanned |
| V18 | Says "unknown" where data is genuinely unavailable | **NOT ENFORCED** | `assumption_recorded` (6) requires ≥20 characters of assumptions but does not check they name the real ambiguity — the length threshold is trivially satisfiable |
| V19 | Findings precision ≥ threshold; false positives penalised | **NOT ENFORCED** | `service_localized` requires the right service; there is no AIOpsLab-style `100/N` penalty for naming extras |
| V20 | Output conforms to the requested schema | **PARTIAL** | Enforced structurally by 74 typed tool schemas and by `submit_diagnosis` / `submit_answer`. No free-form report contract |
| V21 | Agent asked ≥1 bounded clarifying question before mutating | **NOT ENFORCED** | No ask tool, no simulated user, and every instruction is unambiguous by construction |
| V22 | Genuinely blocked task terminates *blocked*, not falsely successful | **NOT ENFORCED** | No blocked or impossible task exists |
| V23 | No-op task produces no side effects | **PARTIAL** | `tsk_detect_storefront_healthy` + `investigation_was_read_only` (20); but ticket closure is still required, so it is not a zero-side-effect task |
| V24 | Ordering constraints between side effects hold | **ENFORCED — and this is the world's strongest axis** | 13 distinct `deployment`-dimension checks, **207 instances**, **70/70 tasks carry ≥1**, mean **2.96** per task |
| V25 | Agent did not route around a scoped tool with a general-purpose one | **ENFORCED (structurally)** | There is no bash, no shell, no HTTP fetch. All 74 tools are typed and every mutation writes `audit_events`, whose contiguity and seeded prefix are themselves verified |
| V26 | Each work item finalised exactly once | **PARTIAL** | `closed_after_the_work` (70) and `ack_before_resolve` (11) prevent premature and out-of-order finalisation; there is no explicit double-finalisation check |
| V27 | No tool called before its required inputs are known | **NOT ENFORCED** | — |

### 4.2 Workflow-discipline score

| | Count | Share |
|---|---:|---:|
| ENFORCED | **6** (V1, V10, V13, V15, V24, V25) | 22 % |
| PARTIAL | **9** (V2, V4, V11, V14, V16, V17, V20, V23, V26) | 33 % |
| NOT ENFORCED | **12** (V3, V5–V9, V12, V18, V19, V21, V22, V27) | 44 % |
| **≥ PARTIAL** | **15** | **56 %** |

### 4.3 The fifteen discipline rules and twelve guarded failure modes

Rolled up from `_WORKFLOW_PATTERNS.md` §1 and §3, since the V-checks do not cover
all of them:

| Rule / failure mode | Status | Evidence |
|---|---|---|
| §1.1 Verify by execution, put evidence in the record (consensus 5/6) | **ENFORCED** | `ci_all_stages_green`, `three_green_main_runs`, `evidence_recorded` |
| §1.2 Never claim an action you did not take (4/6) | **ENFORCED structurally** | The agent has no narration channel that the score reads; every claim is a state fact |
| §1.3 Gather context before acting (4/6) | **PARTIAL** | `consulted_*` (6 tasks), `efficient_investigation` (14). No general read-before-write rule |
| §1.4 Do not invent (4/6) | **ENFORCED** | `scoped_change_no_fabricated_data` (70) + `world_invariants_intact` (70) — the world's reference data cannot be forged |
| §1.5 Separate read-only investigation from mutation (5/6) | **ENFORCED** | `investigation_was_read_only` (20); the surface is split **53 read-only / 21 writing** tools (by `write_tables`), and every write appends to `audit_events` |
| §1.6 Ask when ambiguous, through a bounded interface (4/6) | **NOT ENFORCED** | No ask tool |
| §1.7 Escalate on enumerated conditions | **NOT ENFORCED** | No escalation channel |
| §1.8 Stay in scope, minimal change (3/6) | **ENFORCED** | The seven `no_unrelated_*` / `*_untouched` checks + blast radius |
| §1.9 Precision beats recall when reporting | **NOT ENFORCED** | No false-positive penalty (V19) |
| §1.10 Cite the evidence for every claim | **PARTIAL** | `consulted_*`, `evidence_recorded`, `security_audit_note` |
| §1.11 Treat injected context as authoritative | **NOT ENFORCED** | No injected runtime context block |
| §1.12 Batch independent work | **NOT ENFORCED** | (V6) |
| §1.13 Prefer structured tools over shell | **ENFORCED structurally** | No shell exists |
| §1.14 Leave the workspace clean and reversible | **PARTIAL** | `rollback_deployment` + `bad_deploy_marked_rolled_back`; no worktree/checkpoint analogue |
| §1.15 Delegation permission lattice | **N/A** | Single-agent world |
| §3.1 Loops / repeated identical actions | **PARTIAL** | `no_unproductive_ci_loops` (70) only |
| §3.2 Premature / dishonest completion | **ENFORCED** | `closed_after_the_work` (70) — closing the ticket before the work is done fails, on every task |
| §3.3 Unverified / hallucinated claims | **PARTIAL** | See §1.4 |
| §3.4 Destructive actions | **N/A** | None exist |
| §3.5 Secret exposure | **PARTIAL** | `no_new_hardcoded_secrets` (70), source only |
| §3.6 Environment failure mistaken for model failure | **NOT ENFORCED** | See §7 |
| §3.7 Over-flagging / false positives | **NOT ENFORCED** | — |
| §3.8 Privilege escalation via delegation | **N/A** | — |
| §3.9 Prompt injection from untrusted event data | **NOT ENFORCED** | No adversarial content in tickets, logs or documents |
| §3.10 Concurrency corrupting shared state | **NOT ENFORCED** | Single-agent |
| §3.11 Context overflow | **NOT ENFORCED** | Not a nameable event in the harness |
| §3.12 Deployment-mode declaration (interactive vs unattended) | **NOT ENFORCED** | Every task is implicitly unattended; §4.5.6 of the note says a verifier that ignores this axis will penalise correct behaviour |

---

## 5. The four coverage percentages, in one place

| Matrix | Denominator | Full | ≥ Partial |
|---|---:|---:|---:|
| 1. Task types | 50 corpus task types | **7 (14 %)** | **18 (36 %)** |
| 2. Tool surface | ≈2 563 vendor tools across all 24 cloned MCP servers | **74 (2.9 %)** | — |
| 2b. Tool surface | 564 tools across the 10 *inventoried* servers | **74 (13.1 %)** | — |
| 3. Chaos scenarios | 30 (CS-01…CS-30) | **11 (36.7 %)** | **21 (70 %)** |
| 4. Workflow discipline | 27 candidate checks (V1…V27) | **6 (22 %)** | **15 (56 %)** |

These are the numbers to quote. They are low, and the reason they are low is worth
stating plainly rather than explaining away: **this world trades substrate for
discipline.** It gives up real code execution, a real browser, a real terminal and
a simulated human, and in exchange it grades the ordered operational process around
a change more densely than anything in the corpus. Whether that is a good trade
depends entirely on what a lab wants to measure. §6 and §7 are the two halves of
that answer.

---

## 6. Where this world is the most extensive

Each claim below is a comparison against a specific number in the corpus, not an
adjective.

**6.1 Deployment-process discipline across a long side-effect chain — no benchmark
is close.** 13 distinct `deployment`-dimension checks, **207 instances**, **70/70
tasks** carrying at least one, mean 2.96 per task. Ten are strict **ordering**
constraints (`staging_first`, `canary_then_promote`, `ack_before_resolve`,
`deprecate_before_shift`, `drain_before_retire`, `rollout_order`,
`staged_traffic_shifts`, `code_before_flag_enable`, `consumer_before_retire`,
`migration_before_deploy`); the other three constrain the manner of the change
(`no_alarming_deploys`, `investigation_was_read_only`, `rollback_tool_used`).
Instance counts: `staging_first` (56), `no_alarming_deploys` (49),
`canary_then_promote` (34), `investigation_was_read_only` (20), `ack_before_resolve`
(11), `deprecate_before_shift` (7), `drain_before_retire` (7), `rollout_order` (7),
`staged_traffic_shifts` (7), `code_before_flag_enable` (4), `consumer_before_retire`
(3), `migration_before_deploy` (1), `rollback_tool_used` (1). The corpus's entire
recorded coverage of this idea (V24) is **two prose rules** in the anthropic
cookbook's SRE notebooks — *"never call `merge_pull_request` unless
`request_approval` returned 'approved'"* and *"always create the post-mortem BEFORE
resolving the PagerDuty incident"* — plus one wall-clock escalation rule in
TheAgentCompany (`qa-escalate-emergency`, ≥600 s). AIOpsLab's 14 mitigation problems
check *state* (pod readiness, `targetPort == 9090`, deployment `command`), never
order.

**6.2 Verifier density.** 104 distinct named checks, 1 053 instances, mean **14.7**
per task, minimum 11. TheAgentCompany — the densest grader in the corpus — budgets
661 points over 175 tasks with a **median of 3** checkpoints and a maximum of 8.
SWE-bench and commit0 grade with two test-ID sets. tau-bench grades with one hash.
Every one of the world's 104 checks carries a human-readable failure message, so a
failed run says *which* discipline broke.

**6.3 Cross-tool reconciliation — the corpus has zero of it, by its own admission.**
`_CROSS_CUTTING.md §8` item 2, verbatim: *"Reconciliation across tools. Every
benchmark has exactly one source of truth. Nothing requires joining Jira + Sentry +
a status page with conflicting severity conventions."* The world has 6 such tasks,
12 distinct `consulted_<table>` checks, and 11 vendor surfaces that genuinely
disagree — including four independent answers to "what is checkout's error rate"
(§3, CS-29). The disagreements are documented rather than invented: every one
carries a CS-## citation in `build/vendors.py`.

**6.4 Stale and contradictory documentation as a graded hazard.** Same note, item 3:
*"Every document handed to an agent here is authoritative."* The world seeds
`confluence_pages` 8002 with `stale=1` and a runbook naming a decommissioned host,
an `owner_spreadsheet` last reviewed on day 180 naming a dissolved team, and a
severity ladder (8004) whose definition of "customer-facing" contradicts where
every incident object stores impact. `tsk_rcn_gateway_owner` is scored on
preferring the live routing system over two written sources.

**6.5 Deploy-side tool surface exceeds the real MCP corpus.** The inventory's own
gap notes record that the real Kubernetes server has **no `rollout` verb of any
kind**, no cordon/drain, no helm upgrade/rollback; that among the ten inventoried
servers there is *"no Slack, no CI beyond GitHub Actions and Tekton, no Terraform,
**no feature flags**, no status-page write outside PagerDuty, no CODEOWNERS/ownership
lookup, no spreadsheet"* (`_TOOL_INVENTORY.md:532`); and that **no security server
can remediate anything**
(*"Ten servers, zero ability to dismiss a security alert, file an exception, or open
a fix PR from a finding"*). The world ships `deploy_service` with canary percent,
`assess_canary`, `promote_canary`, `rollback_deployment`, `set_feature_flag`,
`shift_endpoint_traffic`, `apply_migration` — and grades the remediation of four
CVEs and one leaked credential.

**6.6 Anti-reward-hacking is structural, not procedural.** Three layers, all on all
70 tasks: `_FROZEN` SHA-256 over 29 reference tables and `_FIXED_ROWS` over 5 more;
`world_invariants_intact` (15 orphan-row queries, a contiguous-append-only assertion
on `audit_events`, and a SHA over the 23 seeded audit rows so the pre-episode history
cannot be rewritten); and `scoped_change_no_fabricated_data`. There is no shell, so
the verifier cannot be reached. Compare: SWE-bench's `compute_fail_to_pass` returns
1 when the denominator is 0 and `SKIPPED` satisfies neither predicate;
TheAgentCompany encrypts its rubrics with the published key
`'theagentcompany is all you need'`.

**6.7 Determinism.** 70/70 tasks are `reward_kind: vcode`. No LLM appears in any
score. TheAgentCompany LLM-judges 53/175 tasks and has a stochastic component in
70/175; tau-bench's user simulator has **no temperature parameter at all** and is
the corpus's largest unpinned variance source.

**6.8 Horizon.** Mean oracle trajectory 15.4 tool calls, maximum 34, with 41 tasks
requiring the full ten-stage pipeline. AIOpsLab caps at `max_steps=30` and tau-bench
at `max_num_steps=30` — for a *conversation*.

**6.9 Reliability metric already implemented.** `eval_model.py:259` implements
tau-bench's `pass^k` (sampling without replacement), the corpus's own recommendation
#8, which only tau-bench itself uses.

---

## 7. Where it is thinner than the corpus

Ranked by how much it would matter to a lab deciding whether to adopt the world.

**7.0 Porting is now a pipeline rather than a judgement.** `port.py` reads each
benchmark's native layout into a common form and classifies it: 449 source tasks
enumerated, 102 with substrate in this world, 241 blocked by having no terminal,
59 out of domain because TheAgentCompany simulates a whole business and hr,
finance and admin are not software operations. Three sde tasks are ported with
provenance; 38 more are queued. DeepSeek scores 33% on the three, against 100% on
code implementation — the clerical half of the job is the harder half here.

**7.1 Code execution: now real for one family, simulated everywhere else.**
Eight of nine benchmark repos share exactly one task: fix a real repository and prove
it with its own tests in a container. This was previously absent altogether — CI is a
SQL rule engine over `pr_changes` and a `change_type` payload is never a diff.

**Partially closed.** The `code_implementation` family (3 tasks) is genuinely
executed: `write_implementation` stores source, `run_exercise_tests` runs it in a
fresh interpreter under a timeout, and the verifier reads what happened against
tests the agent never sees. The world cannot grade these without running them,
which is different in kind from every other check here. The visible tests are
deliberately insufficient — each is satisfied by a plausible wrong implementation
that the hidden tests reject, pinned by
`test_the_world_actually_executes_code_it_cannot_otherwise_grade`.

**Measured, and the result is worth stating.** DeepSeek v4-pro passes all four,
including the expert-level token bucket with continuous fractional refill and an
NTP clock that steps backwards. One earlier failure turned out to be our fault:
it wrote a correct `chunk()` and failed only on iterator support, which the spec
had never stated. Once stated, it passed.

So on this evidence **specifying a function precisely enough to test it is
specifying it precisely enough for a frontier model to implement it.** The
difficulty in this world does not live in writing well-specified code; it lives
in the investigation families, where reconciliation sits at 29% and root-cause
analysis at 30%. That is a fact about where a lab should look, and it is the
opposite of what the corpus's emphasis on code benchmarks would predict.

**Still missing.** Four tasks are a family, not a benchmark. The exercises are
single stdlib functions rather than a repository, there is no container, no
dependency resolution and no build; execution is a subprocess with a stripped
environment, which is containment enough for a local eval and not enough for
untrusted code at scale. Test tampering remains impossible because the agent
cannot write the tests — that removes a reward-hacking surface rather than
testing it. A lab evaluating coding ability should still use this world alongside
SWE-bench, never instead of it.

**7.2 No simulated human, and therefore three whole failure modes are untestable.**
No ask-a-question tool, no NPC that replies, no approval object, no blocked state.
That makes V14 (human gates), V21 (ask when ambiguous), V22 (terminate blocked
rather than falsely successful) and rule §1.6/§1.7 structurally uncheckable. tau-bench
and TheAgentCompany both have this and both regard it as central. The five entries
in `world/personas.json` are metadata with no behaviour.

**7.3 No environment-vs-model failure attribution.** `_CROSS_CUTTING.md §3` calls
this *"the most important finding in the corpus"* and recommends vivaria's typed
`ErrorSource = ['agent','server','task','serverOrTask','user','usageLimits']`,
derived into run status in SQL so the taxonomy cannot drift from the metric. The
world's harness records `passed` plus a free-text `error` string. A harness bug and
a model failure are currently the same number.

**7.4 The seeded ambiguity is defused before the agent meets it.** CS-24 (week
boundaries) and CS-21 (severity ladders) are both seeded with genuine, documented
conflicts — and then `tsk_rcn_customer_facing_incidents` and
`tsk_rcn_production_deploys` both state the exact day window in the instruction, and
no task is scored on a severity mapping. `assumption_recorded` checks that the
assumptions field is ≥20 characters, not that it names the real ambiguity. The world
built the trap and then removed the trigger.

**7.5 Nine chaos scenarios absent, clustered in two buildable groups.** Alerting
mechanics: CS-13 (orphaned monitors), CS-14 (dashboards), CS-15 (non-actionable
alerts), CS-28 (the alert → page → incident lossy chain — no grouping, silences,
inhibition or dedup keys). Statistics and time: CS-09 (percentiles cannot be
averaged — the single most-cited real-world metric error), CS-22 (MTTR), CS-25
(timezones). Plus CS-03 (dual-emitted attributes) and CS-30 (namespace sameness).
None of these needs new machinery; they need seed rows and tasks.

**7.6 Observability is two metric names deep, and there are no traces at all.**
`service_metrics` holds only `error_rate_pct` and `latency_p99_ms`, as single
fleet-level scalars. AIOpsLab hands its agent 24 cAdvisor metrics plus Jaeger
traces. Traces, spans, profiles and replays are **0 of 10** real tools. This is the
largest single hole in the tool surface and it directly causes CS-09's absence.

**7.6b Two whole vendor categories are at or near zero, and both were invisible
until the un-noted servers were counted.** *IaC:* `hashicorp/terraform-mcp-server`
ships **57** tools — `list_workspaces`, `create_run`, `get_plan_logs`,
`get_apply_logs`, `create_workspace_variable`, `delete_workspace_safely` — and the
world has `apply_migration` and nothing else. No plan, no apply, no state, no drift
detection, no workspace. For a world whose thesis is *operational* discipline, "the
agent never touches infrastructure code" is a substantive omission, not a scope
decision. *Database/warehouse:* **213** counted tools across dbt, Redis, MongoDB,
Neon and Grafana's warehouse datasources (plus a 298-kind framework in
`googleapis/genai-toolbox`), against the world's two shadow-data readers. The
inventory's "no Terraform" note was true of ten servers and false of the corpus;
this document is the first place that is stated.

**7.7 No judgement-only task type.** SWE-Lancer's manager split is 265 of 463 tasks,
graded by integer equality, completely flake-free, and *harder* than the code tasks
(47.2 % vs 51.5 %). The world already has `submit_answer` and a knowledge base. It
has no such task.

**7.8 Scale, and a thin contamination guard.** 70 tasks, 1 193 rows, 10 services,
38 files. SWE-bench: 2 294. terminal-bench: 241. TheAgentCompany: 175. SWE-smith:
52 000. The heldout split is **13 tasks**, which is a small basis for any
generalisation claim, and the 13 are structurally near-identical to their train
counterparts (`tsk_media_v1_to_v2` alongside six other `*_v1_to_v2`).

**7.9 The verifier-accuracy receipt is stale.** `world/verifier_accuracy_receipt.json`
reports perfect precision/recall over 5 corruption kinds — but for `world_id`
`env_software_devops_bb2fe89d` with **63** tasks, generated at 07:15Z. The world is
now `env_software_devops_8b9d74de` with **70**. Seven tasks have never been through
the corruption panel. Publishing the 1.0 figures as-is would be a real credibility
problem.

**7.10 A shortcut in the flagship reconciliation task.** `query_metrics` returns
checkout's error rate as `5.5` in one call — the exact expected answer of
`tsk_rcn_checkout_error_rate`. `consulted_prom_series` forces the Prometheus read,
but nothing forces the agent to actually *reason* about the counter reset or the
0.25 sample rate to get `answer_correct`.

**7.11 No adversarial input.** Every ticket, log line and document is benign. The
claude-code corpus enumerates every attacker-controlled `github.event.*` field as
the concrete treatment of "the input document is adversarial"; the world has no
prompt-injection surface at all.

**7.12 No cost or wall-clock budget.** `--max-turns` only. SWE-agent budgets in
dollars (`per_instance_cost_limit $3.00`) and the cross-corpus note argues that is
the most realistic axis; vivaria generalises to four.

---

## 8. Highest-value additions

Prioritised. Each is tied to a specific gap found above, with the artifact it would
change.

**1. A judgement task family — "pick the right remediation" (closes T35, and §7.7).**
Seed 3–4 human-written remediation proposals per incident into `documents` or a new
`proposals` table; the agent reads the incident, the telemetry and the proposals and
calls `submit_answer(question_id, answer=<proposal_id>)`. Graded by integer equality
— zero flakiness, no new tools, reuses the existing submission channel. The corpus
evidence is unusually strong: SWE-Lancer's manager split is 57 % of its tasks and is
*harder* than implementing the fix (47.2 % vs 51.5 %). Target: 8–10 tasks. This is
the best difficulty-per-unit-of-build-cost available anywhere in the corpus.

**2. Typed outcome and error-source enum in the harness (closes T40, V7, V9, §7.3).**
Add vivaria's `ErrorSource` to `eval_model.py` and derive the run status from it, so
`agent`, `harness`, `environment`, `serverOrTask`, `capped` and `user` can never be
averaged into a pass rate. Report three numbers — `resolved`, `model_failed`,
`environment_failed` — as the note's design recommendation #1 states. Cheapest item
on this list and it changes what every future number means.

**3. Alert mechanics: the lossy counting chain plus orphaned and noisy monitors
(closes CS-28, CS-13, CS-15, and part of §7.5).** Pure seed data: an
`alert_rules` / `alert_groupings` / `silences` set; 2–3 alerts bound to services
that no longer appear in `services`; a handful of alerts that fire without a real
SLO breach. Then one task: *"were we paged for this incident, and how many distinct
alerts did it produce?"* — a question that currently has one trivially correct
answer and should have four defensible ones. This is the largest cluster of absent
chaos and it needs no new machinery.

**4. Re-arm the ambiguity the world already seeded (closes §7.4, CS-21, CS-24).**
Remove "days 414-420 inclusive" from the two windowed reconciliation instructions
and let `owner_spreadsheet.week_start='sunday'` versus Confluence 8003's ISO-Monday
convention actually bite; add a task scored on mapping PagerDuty `urgency`+`priority`
onto the Confluence 8004 ladder. Strengthen `assumption_recorded` from a 20-character
length test to a keyword test against the ambiguity the task declares. The data
already exists; the tasks currently defuse it.

**5. Percentile aggregation trap and a trace surface (closes CS-09, §7.6).** Add
per-instance latency quantiles and histogram buckets to `prom_series`, so that
`avg(per-host p99)` and `histogram_quantile()` legitimately differ by ~2×, plus a
minimal `traces`/`spans` table with 2–3 tools. One reconciliation task on top. This
is the most-cited real-world metric error in the domain and the world currently
cannot express it.

**6. Infeasible and blocked tasks (closes T49, V22, §7.2).** Three tasks where the
correct terminal behaviour is to report the work impossible — a fix requiring a
service that does not exist, a CVE with no patched version available, an alarm whose
owning team is genuinely unresolvable. OSWorld ships `test_infeasible.json` for
exactly this. Add a `report_blocked(reason)` tool and a check that it was called
*instead of* a fabricated success. The `_WORKFLOW_PATTERNS.md` §4.5.7 recommendation
is explicit: *"a benchmark that only rewards completion selects for exactly the
wrong thing."*

**7. Regenerate the verifier-accuracy receipt against the current world (closes
§7.9)** — and add two corruption kinds the current five miss: `reconciliation_shortcut`
(answer correct, sources never consulted) and `order_violation` (right end state,
wrong sequence), since ordering is the world's headline claim and nothing currently
proves the verifier catches its violation.

**8. Real test execution for one task family (partially closes T1, §7.1).** The
flaky-test family is the cheapest foothold: 6 tasks, 3 seeded test files
(`tests/test_capture_retries.py`, `tests/test_idempotency.py`,
`tests/test_ranking.py`). Running a real `pytest` over those in a sandbox would
convert 6 PARTIAL rows to COVERED and give the world its first genuine claim on the
corpus's consensus task. Highest value of anything here, and by far the highest cost
— which is why it is last rather than first.

**9. A minimal IaC surface (closes §7.6b, the 0/57 Terraform row).** Not a full
Terraform mock — three tools would carry it: `plan_infrastructure_change`,
`apply_infrastructure_change`, `get_infrastructure_drift`, over an
`infra_components` table that already exists (6 rows). Then one task where the
declared state and the running state disagree, which is CS-05's infrastructure twin
and currently has no expression in the world. Lower priority than 1–8 because the
world's change model is config-driven and this is an addition to its thesis rather
than a repair of it — but it is the largest counted category at exactly zero.

**10. Expand the heldout split and vary it structurally (closes §7.8).** 13 of 70,
each a near-twin of a training task, is not a contamination guard. Either raise it
to ~25 % or make the heldout tasks differ in shape rather than only in service name.

---

## 9. Reproducing every number in this document

```bash
cd /Users/samuelchien/dev/software-devops

# world scale
python3 -c "import json;W=json.load(open('world/world.json'));print(W['counts'],W['categories'],W['difficulty'],{k:len(v) for k,v in W['splits'].items()})"

# verifier checks (104 distinct / 1053 instances / 14.7 per task)
python3 - <<'PY'
import json,re,collections
T=json.load(open('world/tasks.json'))
pat=re.compile(r"""_c\(\s*(['"])([a-z_]+)\1\s*,\s*(['"])([a-z0-9_]+)\3""")
p=collections.Counter()
for t in T:
    for _,d,__,n in pat.findall(t['vcode']): p[(d,n)]+=1
print(len(p), sum(p.values()), sum(p.values())/len(T))
PY

# database
python3 -c "import sqlite3;c=sqlite3.connect('world/environment.db');ts=[r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'\")];print(len(ts), sum(c.execute('SELECT COUNT(*) FROM \"%s\"'%t).fetchone()[0] for t in ts))"

# corpus size
for d in evals automation mcp; do echo "$d: $(ls -d research/repos/$d/*/ | wc -l)"; done

# the 14 un-noted MCP servers (§0.2) — one command per repo, all run from research/repos/mcp/
# awslabs/mcp → 848
find awslabs__mcp/src -name "*.py" -not -path "*/tests/*" -not -name "test_*" -exec grep -hoE \
  "@?(mcp|app|server|self\.mcp|self\.server)\.tool\(|@(mcp|app|server)\.tool\b|\.add_tool\(" {} + | wc -l
grep -oE 'name: "[a-z_A-Z0-9]+"' zereight__gitlab-mcp/tools/registry.ts | sort -u | wc -l        # 217
grep -rhoE "name: 'linear_[a-zA-Z0-9_]+'" tacticlaunch__mcp-linear/src/tools/definitions/*.ts | sort -u | wc -l  # 195
grep -ohE '"[a-z_0-9]+":' hashicorp__terraform-mcp-server/pkg/toolsets/mapping.go | tr -d '":' | sort -u | wc -l # 57
grep -cE '^\s{4}[A-Z][A-Z_0-9]* = ' dbt-labs__dbt-mcp/src/dbt_mcp/tools/tool_names.py            # 61
grep -rn "@mcp.tool" redis__mcp-redis/src/tools/*.py | wc -l                                     # 53
grep -rhoE "static toolName" mongodb-js__mongodb-mcp-server/src/tools/{atlas,atlasLocal,mongodb,assistant} --include="*.ts" | wc -l  # 52
grep -cE "^\s+name: '" neondatabase__mcp-server-neon/mcp/tools/definitions.ts                    # 35
grep -c "mcp.tool()" pydantic__logfire-mcp/logfire_mcp/main.py                                   # 4
grep -rl "tools.Register(" googleapis__genai-toolbox/internal/tools --include="*.go" | wc -l     # 298 kinds
# slackapi/java-slack-sdk → 0 (not an MCP server); stripe/agent-toolkit → 0 locally defined
grep -ril "modelcontextprotocol\|mcp server" slackapi__java-slack-sdk --include="*.java" --include="*.md" | wc -l  # 0

# chaos citations in the seed
grep -n "CS-[0-9]" build/vendors.py
```

**Audit date:** 2026-08-11. **World audited:** `env_software_devops_8b9d74de`.
Any rebuild changes the counts; re-run §9 before quoting them.
