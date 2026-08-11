# software-devops — an end-to-end engineering-workflow world

An executable RL/eval environment where a model is tested as an **autonomous
software engineer**, not a coding assistant — inspired by Polymath's
[Horizon-SWE](https://polymathlabs.ai/blog/horizon-swe) benchmark and packaged
in the [Blobfish](https://blobfish.ai/api-docs) world format (Format A), so it
runs under the `blobfish` CLI/MCP tooling *and* fully standalone with zero
dependencies.

The world simulates **NovaCart**, a mid-size e-commerce SaaS, and implements the
environment the blog describes: an editable **monorepo** (38 files, 417 commits)
the agent reads and patches; a full **application stack** (10 services over a
database, replica, cache, queue, object store and CDN); a **traffic generator**
that turns deployed state into live metrics; and the tools engineers actually
use — issue tracker, knowledge base (30 runbooks/ADRs/postmortems/API specs),
chat, deployment tooling with **database migrations** and **canary assessment**,
logs, metrics, alarms, **error tracking**, and a public **status page**.
Agents solve long-horizon workflows: **investigate → PR → CI (build · unit ·
integration · regression) → merge → migrate → staging → canary → promote →
observe → resolve → close the ticket.**

**83 tasks**, graded on both
Horizon-SWE-PF (binary) and Horizon-SWE-PC (composite).

The same world also hosts a second suite that reproduces the use case of
[microsoft/AIOpsLab](https://github.com/microsoft/AIOpsLab) — **12 diagnostic
tasks** covering its taxonomy (detection → localization → analysis) where the
agent investigates read-only and *submits a finding* instead of executing a fix.
See [docs/AIOPSLAB.md](docs/AIOPSLAB.md).

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
- **No free rewards, and no forged ones.** Every verifier provably fails on the
  pristine seed; the blobfish random-policy eval scores 0.0; every task ships an
  `expected_calls` oracle that replays through the real tools to reward 1.0.
  Verifiers also enforce world invariants — reference data no tool can write
  must be byte-identical, every row must reference entities that exist, and
  `audit_events` must remain a contiguous append-only log with its seeded
  prefix intact — so fabricating state or tampering with the audit trail loses.
  The platform's adversarial audit (`blobfish verify-accuracy`) scores the
  verifiers **precision 1.000 · recall 1.000 · FPR 0.000**, rejecting all five
  corruption families (no-op, wrong-target, partial-completion, over-repair,
  zero-tool-call) at 1.000 recall.

## Delivering it

The package a consumer receives is `dist/harbor`. `harbor_selftest.py` copies
that package and the world to a temporary directory and runs every shipped
verifier as a subprocess with no repo on `sys.path`, no repo in `cwd` and a
stripped environment, checking both halves of what a verifier is for:

```
$ python3 harbor_selftest.py
harbor standalone self-test: 83/83 verifiers accept the reference solution
and reject an untouched world
  failures 0, missing 0, free-reward 0
```

An untouched world must be **rejected** — a verifier that passes before anyone
does anything is a free reward, not a grader. The reference solution must be
**accepted**. All 82 do both, outside the repository that built them.

## The 83 tasks

| Category | Tasks | Examples |
|---|---|---|
| error-rate reduction | 8 | missing retries, undersized pool, unbounded queue prefetch, no SMTP timeout |
| latency optimization | 8 | disabled query cache, N+1 pricing loop, CDN bypass, SEV1 rollback |
| root-cause analysis | 10 | mechanism *and* offending key, including four node-level faults |
| feature flag | 7 | dark ship at 10%, ship behind a migration, kill switch, stale-flag cleanup |
| security incident | 7 | four CVE patches, two exposed endpoints, hardcoded credential in source |
| API migration | 7 | deprecate -> drain <=50pp/step -> retire, incl. consumer contract migration |
| multi-service rollout | 7 | ordered rollouts across 2-3 services with migrations |
| reconciliation | 7 | questions no single system answers, over systems that disagree |
| flaky test | 6 | diagnose from CI history, fix (not quarantine), prove 3 green runs |
| localization | 6 | name the responsible service when the alarm names a different one |
| detection | 5 | is this service violating an SLO? one is healthy, and saying so is the pass |
| judgement | 4 | choose between four plausible remediations, three of which treat the symptom |
| human-gated | 1 | the change needs an approval that is not granted on request |

68 train / 15 heldout, split per category. Difficulty: 2 easy, 29 medium, 26 hard, 26 expert.

## Instruction design: outcomes, not procedure

Each task's prompt is written as a realistic ticket. It states the **symptom**
and the **definition of done**, and nothing about *how*. Company policy —
staging-first, tier-1 canaries, migration ordering, the ≤50pp traffic-shift
rule, "fix don't quarantine", the audit-note and status-page requirements — is
never in the prompt. It lives in the knowledge base, and the agent has to go
find it. Deviating from a policy it never read still fails the verifier.

Measured across all 83 tasks, the default prompt contains the exact config key
**0** times, the target value **0** times, a runbook title **0** times, and any
workflow instruction **0** times. Every policy removed from the prompts is
verifiably present in the knowledge base, so the tasks stay solvable by
discovery — just harder.

Each task also ships an `instruction_guided` variant that appends the procedure
back. Running the same tasks both ways measures how much of a model's score is
engineering judgment versus instruction-following:

```bash
python3 eval_model.py --model claude-sonnet-5 --guidance standard   # default
python3 eval_model.py --model claude-sonnet-5 --guidance guided     # procedure spelled out
```

## How hard is it? Scripted baselines

No model has been run against this world yet, so difficulty is uncalibrated.
What *is* measured is a family of scripted baselines, each modelling a specific
way of being wrong. They cost nothing to run and map which dimension each
failure mode damages.

| policy | what it does |
|---|---|
| `oracle` | the reference solution, following every policy |
| `naive` | correct technical fix, ignores every documented policy |
| `merged_only` | treats merging the pull request as the finish line |
| `no_verify` | ships the fix but never checks, resolves or closes anything |
| `shortcut` | quarantines flaky tests; blames whichever service the alarm names |

PF pass rate by category (83 tasks):

```
                          oracle    naive  merged_only  no_verify  shortcut
aiops_analysis              100%     100%       100%       100%      100%
aiops_detection             100%     100%       100%       100%      100%
aiops_localization          100%     100%       100%       100%       80%
api_migration               100%       0%         0%       100%      100%
error_rate_reduction        100%       0%         0%        38%      100%
feature_flag                100%       0%        14%        86%      100%
flaky_test                  100%     100%       100%       100%        0%
latency_optimization        100%       0%         0%        38%      100%
multi_service_rollout       100%       0%         0%       100%      100%
security_incident           100%       0%         0%       100%      100%
ALL PF                      100%      30%        32%        83%       89%
ALL PC                     100.0     87.3       77.5        92.8      97.9
```

What this says, honestly:

- **The deployment dimension is load-bearing.** `naive` scores PF 0% on every
  category that ships a change. Getting the right answer buys nothing if you
  ignore the process.
- **PC is generous by construction.** `naive` still scores 87.3 because feature
  correctness is 60% of the composite and it does get the fix right.
- **PF tolerates poor follow-through.** `no_verify` reaches 83% because ticket
  hygiene and comms are graded under quality, which PF excludes by design. That
  is faithful to the benchmark's definition, not a bug — but it means PF alone
  does not measure closing the loop.
- **`shortcut` is the only baseline that touches flaky tests and localization**,
  and it exposes a genuine limitation: 4 of the 5 localization tasks can be
  solved by naming whichever service the alarm names. Only
  `tsk_localize_checkout_latency` — where checkout's p99 breaches because
  *payments* blocks on a 30s downstream timeout — requires real localization.
  More cross-service faults would strengthen that category.

`tests/test_eval_harness.py` pins the `naive` result as a **difficulty guard**:
if a future change lets the policy-blind agent start passing change tasks, the
tests fail.

> None of these numbers calibrate against the blog's reported ~25.5% for a real
> model. Scripted baselines and language models fail in completely different
> ways.

### Estimating the real calibration run

```bash
python3 eval_model.py --estimate                       # ~26M input tokens for all 62
python3 eval_model.py --model <id> --limit 2 --category aiops_detection   # cheap smoke test
```

## Browsing tasks and traces

Every task's assignment, its executable verifier checks, and the complete oracle
trace are captured in `docs/traces.json` and rendered by
`python3 build/gen_traces.py` into a filterable explorer (filter by category,
difficulty and split; search across ids, instructions and tool names).

```bash
python3 build/gen_traces.py     # -> /tmp/demo/traces.html
```

## Quickstart

```bash
# rebuild the package from source (deterministic; validates every task)
make build

# run the quality gates + adversarial tests + server smoke test
make test

# serve the world standalone (stdlib only, no installs)
make serve            # or: make docker-run
```

### Test a model on it

```bash
# sanity-check the harness — no API key, no tokens spent
python3 eval_model.py --policy oracle

# evaluate a model end to end (needs ANTHROPIC_API_KEY)
python3 eval_model.py --model claude-sonnet-5 --split heldout
python3 eval_model.py --model claude-fable-5 --category security_incident -v
```

Each task runs in its own session fork and is graded by the world's executable
verifier, reporting both Horizon-style numbers:

```
  tsk_payments_retry     hard   PASS  score=1.00  corr 7/7 depl 4/4 qual 5/5  calls=14
  ...
  Horizon-SWE-PF  (pass rate, correctness+deployment must be perfect) : 100.0%  (83/83)
  Horizon-SWE-PC  (0.6 correctness / 0.3 deployment / 0.1 quality)     : 100.0

  by category:
    api_migration            PF 100%  PC 100.0   (7 tasks)
    ...
```

`--quality-judge llm` swaps the deterministic 10% quality dimension for an LLM
judge (as the blog does); correctness and deployment always stay executable.

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
session pinned via the `Mcp-Session-Id` header. Alongside the 84 world tools,
the server exposes the blobfish meta-tools: `world_info`, `task_list`,
`task_start`, `task_verify`, `episode_abort`. Episode lifecycle:
`task_start` → world tool calls → `task_verify` (binary reward, no judge).

### Other runtimes it converts into

Because it is a standard Format-A package, the world converts mechanically into
the platform's other deployment shapes — both verified working end to end:

```bash
# FastAPI gym (reset/step/verify on :8080; PORT env var overrides the port)
python -c "from fleet_harness import GymBuilder; GymBuilder().build_gym_directory('world','gym')"

# zero-dependency HTTP-MCP Docker context (stdlib only, :8000)
blobfish mirror package world --out dist --name software-devops
```

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
- **CI is staged.** `run_ci` runs build → unit → integration → regression.
  A module that persists new state fails the *build* stage without its
  migration ("missing database migration"); retiring an endpoint that still
  serves traffic fails *integration*; retiring one a dependent service still
  calls fails *regression*.
- **Deploys are gated.** A version whose migration is not applied in that
  environment is rejected; `assess_canary` compares the canary against the
  live baseline and reports only *newly* introduced SLO breaches, so deploying
  to an already-unhealthy service is not unfairly penalized.
- **Verification** is dialect-1 vcode: pure SQL checks over the final SQLite
  state plus the audit-event ordering log, executed read-only in an isolated
  subprocess. Every check is tagged with a Horizon-SWE-PC dimension —
  **feature correctness (0.6), deployment & DevOps (0.3), engineering quality
  (0.1)** — and the verifier emits a weighted `score` ∈ [0, 1] alongside the
  binary verdict. `passed` (⇒ blobfish reward 1.0) requires ALL checks; the
  graded `score` and the per-check breakdown are reported by this repo's
  server (`/verify`, `task_verify`) and by gym-entrypoint runtimes, e.g. an
  agent that ships the correct fix but skips the canary fails with
  `score = 0.85`. Note the score has a nonzero floor (negative-control checks
  pass on an untouched world), so compare scores, don't threshold them; the
  binary `passed` is the authoritative gate.

## Repository layout

```
build/            deterministic world builder (single source of truth)
  schema_seed.py    DDL + seeded company state (ids 9000+ are curated)
  tools_src.py      34 tool sources (engine/audit snippets stamped in)
  tasks_def.py      task generators: instruction + vcode + expected_calls oracle
  build_world.py    assembles + hard-gates + emits world/
world/            the packaged world (blobfish Format A) — committed artifact
serve.py          standalone stdlib server (REST + MCP, session forks)
eval_model.py     model-eval harness (PF/PC scoring, oracle self-test)
tests/            gates, guardrails, adversarial rollouts, server + harness e2e
docs/DESIGN.md    design rationale
```

Edit `build/`, then `make build && make test` — a test fails if `world/` is
stale relative to its sources.
