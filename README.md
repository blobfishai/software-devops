# software-devops — an end-to-end engineering-workflow world

An executable RL/eval environment where a model is tested as an **autonomous
software engineer**, not a coding assistant — inspired by Polymath's
[Horizon-SWE](https://polymathlabs.ai/blog/horizon-swe) benchmark and packaged
in the [Blobfish](https://blobfish.ai/api-docs) world format (Format A), so it
runs under the `blobfish` CLI/MCP tooling *and* fully standalone with zero
dependencies.

The world simulates **NovaCart**, a mid-size e-commerce SaaS: seven services,
four teams, and the full org stack — tickets, PRs carrying structured changes,
CI, staged deployments with canaries, feature flags, metrics/SLOs/alerts, logs,
runbooks, dependency/vulnerability scanning, incidents, and chat. Agents solve
long-horizon workflows: **investigate → PR → CI → merge → staging → canary →
promote → observe → resolve → close the ticket.**

## Why it's hard (and honest)

- **Deterministic physics, no LLM judge.** "Code" is abstracted into structured
  state; a pure engine derives production metrics from what is actually
  *deployed* (configs, dependencies, endpoints, flags, version). Reading logs
  reveals the root cause; only the correct change, merged **and** deployed to
  production, moves the metric; only then can the alert be resolved.
- **Workflow ordering is scored.** Every write tool appends to an append-only
  `audit_events` log. Verifiers assert ordering the tools don't hard-enforce:
  staging before production, canary ≤25% before promote (tier-1 services), code
  deployed before its flag is enabled, traffic drained before an endpoint
  retires, alert acknowledged before resolved.
- **Guardrails bite.** Merges are blocked without a passing CI run; alerts
  can't be resolved while the metric breaches; CI blocks retiring endpoints
  that still serve traffic; checkout CI is deterministically flaky until the
  flaky test is fixed; and the SEV1 bad release can only be cured by a genuine
  rollback (the regression is in every version ≥ v5.1.0).
- **Negative controls.** Each verifier asserts that unrelated alerts, flags,
  configs, and incidents were *not* touched — blanket mutation loses.
- **No free rewards.** Every verifier provably fails on the pristine seed, the
  blobfish random-policy eval scores 0.0, and every task ships an
  `expected_calls` oracle that replays through the real tools to reward 1.0
  (`blobfish eval --policy oracle` → pass rate 1.0).

## The 10 tasks (all seven Horizon-SWE categories)

| Task | Category | Difficulty | Split |
|---|---|---|---|
| `tsk_payments_error_rate` | error-rate reduction (missing retries) | hard | train |
| `tsk_search_latency_slo` | latency optimization (cache disabled) | medium | heldout |
| `tsk_express_checkout_flag` | feature-flag rollout (dark ship, 10%) | hard | train |
| `tsk_instant_refunds_killswitch` | feature-flag kill switch + incident | medium | train |
| `tsk_libpayproc_cve` | security response (CVE dependency patch) | hard | train |
| `tsk_retire_debug_endpoint` | security response (exposed endpoint) | medium | heldout |
| `tsk_loyalty_multi_service` | multi-service rollout in dependency order | expert | heldout |
| `tsk_orders_api_migration` | API migration (deprecate → drain → retire) | expert | train |
| `tsk_flaky_checkout_test` | flaky-test remediation (3 green runs) | hard | train |
| `tsk_gateway_rollback_sev1` | incident response (rollback + postmortem) | hard | train |

## Quickstart

```bash
# rebuild the package from source (deterministic; validates every task)
make build

# run the quality gates + adversarial tests + server smoke test
make test

# serve the world standalone (stdlib only, no installs)
make serve            # or: make docker-run
```

### Drive it over REST

```bash
curl -s localhost:8080/tasks | jq '.[0]'
SID=$(curl -s -XPOST localhost:8080/sessions -d '{}' | jq -r .session_id)
curl -s -XPOST localhost:8080/sessions/$SID/tools/list_alerts \
     -d '{"arguments": {"status": "firing"}}' | jq
curl -s -XPOST localhost:8080/sessions/$SID/verify \
     -d '{"task_id": "tsk_instant_refunds_killswitch"}' | jq
```

### Drive it over MCP

`POST /mcp` (JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`), with the
session pinned via the `Mcp-Session-Id` header. Alongside the 34 world tools,
the server exposes the blobfish meta-tools: `world_info`, `task_list`,
`task_start`, `task_verify`, `episode_abort`. Episode lifecycle:
`task_start` → world tool calls → `task_verify` (binary reward, no judge).

### Evaluate a model with the blobfish CLI

The package is a standard Format-A world dir, so from a repo with `blobfish_cli`
installed:

```bash
blobfish info  path/to/software-devops/world
blobfish eval  path/to/software-devops/world --policy oracle   # sanity: 1.0
blobfish eval  path/to/software-devops/world --policy agent \
               --model claude-sonnet-5 --split heldout
blobfish serve path/to/software-devops/world                   # stdio MCP
```

## How the simulation works

- **Two-layer state.** `repo_state` is HEAD (configs, dependencies, endpoints,
  modules); `env_state` is what each environment actually runs. Merging a PR
  applies its typed changes to HEAD and cuts a version snapshot; deploying
  copies that snapshot into the environment; a canary deploy holds the state
  until `promote_canary`.
- **The engine.** After every state-changing operation, seeded `metric_rules`
  recompute production metrics (e.g. payments error rate = 0.4% + 3.8% while
  `notifications_retry_max_attempts=0` is deployed). Breaches auto-open alerts;
  fixed-version deploys flip vulnerability findings to remediated.
- **PR changes** are typed: `config {key,value}`, `dependency
  {package,version}`, `endpoint {path,status}`, `module {name}`, `flag
  {key,description}`, `test_fix {test_name,action}`.
- **Verification** is dialect-1 vcode: pure SQL assertions over the final
  SQLite state plus the audit-event ordering log, executed read-only in an
  isolated subprocess. `passed` ⇒ reward 1.0.

## Repository layout

```
build/            deterministic world builder (single source of truth)
  schema_seed.py    DDL + seeded company state (ids 9000+ are curated)
  tools_src.py      34 tool sources (engine/audit snippets stamped in)
  tasks_def.py      10 tasks: instruction + vcode + expected_calls oracle
  build_world.py    assembles + hard-gates + emits world/
world/            the packaged world (blobfish Format A) — committed artifact
serve.py          standalone stdlib server (REST + MCP, session forks)
tests/            gates, guardrails, adversarial rollouts, server e2e
docs/DESIGN.md    design rationale
```

Edit `build/`, then `make build && make test` — a test fails if `world/` is
stale relative to its sources.
