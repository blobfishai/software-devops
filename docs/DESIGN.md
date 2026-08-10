# software-devops — an end-to-end engineering-workflow world

A Blobfish-format executable world, inspired by Polymath's **Horizon-SWE** benchmark
(https://polymathlabs.ai/blog/horizon-swe): it tests whether a model can act as an
autonomous software engineer across *long-horizon* workflows — investigate → change →
CI → merge → staged deploy → observe → resolve — not just write code.

## Company thesis

**NovaCart** — a mid-size e-commerce SaaS. Seven services owned by four teams:

| Service | Team | Tier |
|---|---|---|
| storefront-web | growth | 1 |
| api-gateway | platform | 1 |
| catalog | commerce | 2 |
| checkout | commerce | 1 |
| payments | commerce | 1 |
| notifications | platform | 2 |
| search | growth | 2 |

The org stack mirrors Horizon-SWE's toolset: issue tracker (tickets), source control
workflow (PRs with structured changes), CI, deploys with staging/canary/production,
feature flags, metrics + SLOs + alerts, logs, incidents, a knowledge base (runbooks),
dependency/vulnerability scanning, and a chat system (channels/messages).

## Core mechanic: deterministic "physics"

"Code" is abstracted into **structured state** so everything is verifiable without an
LLM judge:

- A PR carries `pr_changes` — typed ops: `config`, `flag_guarded_code`, `dependency`,
  `endpoint`, `test_fix`.
- Merging a PR applies changes to the service's *repo state* and cuts a new version.
- Deploying copies repo state into that environment's *effective state*
  (`env_configs`, deployed version, endpoint states, dependency versions).
- A pure **engine** recomputes production metrics from effective state via seeded,
  data-driven `metric_rules` (e.g. `payments.error_rate = 0.4 + 3.8 if
  notifications retry_max_attempts == 0`). Alerts derive from metrics vs `slos`.
- Every write tool appends to an append-only `audit_events` table — verifiers assert
  **ordering** (staging before production, canary before promote, status update
  posted before incident close) that tools do not hard-enforce.

This gives real end-to-end causality: reading logs/runbooks reveals the root cause;
only the correct structured change, merged and deployed to production, moves the
metric; only then can the alert be resolved and the ticket closed.

## Tool surface (~28 tools)

**Read**: list_services, get_service, list_tickets, get_ticket, list_pull_requests,
get_pull_request, list_ci_runs, list_deployments, query_metrics, get_slo_status,
list_alerts, search_logs, search_runbooks, list_feature_flags, list_dependencies,
list_vulnerabilities, list_api_endpoints, list_tests, get_oncall, list_messages.

**Write**: create_ticket, update_ticket, open_pull_request, run_ci,
merge_pull_request (rejects unless latest CI run passed), deploy_service
(version + canary_percent), promote_canary, rollback_deployment, set_feature_flag
(runtime toggle — no deploy needed, as in real life), acknowledge_alert,
resolve_alert (rejects while the metric still breaches), create_incident,
update_incident, post_message.

## Tasks (the seven Horizon-SWE categories)

| Task | Category |
|---|---|
| payments error-rate 4.2% vs 1% SLO (missing retry to notifications) | error-rate reduction |
| search p99 850ms vs 300ms SLO (cache disabled) | latency optimization |
| ship `express_checkout` behind a flag, roll to 10% prod | feature flag |
| kill-switch a flag that is causing checkout errors, resolve incident | feature flag / incident |
| CVE in `libpayproc` — patch dependency, audit note to #security | security response |
| retire an exposed `/internal/debug` endpoint from production | security response |
| loyalty-points feature across catalog → checkout → storefront, deployed in dependency order | multi-service rollout |
| migrate /v1/orders traffic to /v2, then retire v1 (ordering matters) | API migration |
| flaky `test_checkout_idempotency` — diagnose from CI history, fix, 3 green runs | flaky test remediation |
| SEV1: bad checkout deploy — rollback, verify recovery, postmortem ticket | incident response |

## Scoring (mirrors Horizon-SWE-PC)

Each verifier is a set of weighted deterministic assertions over final DB state and
the audit-event log:

- **Feature correctness (0.6)** — the target state change happened and landed in
  production; no unrelated state was broken (regression assertions).
- **Deployment & DevOps (0.3)** — CI passed before merge, staging before production,
  canary before full rollout where required, rollbacks used where required.
- **Engineering quality (0.1)** — PR linked to ticket, ticket closed, status
  update posted to the right channel.

`passed` = all assertions marked `required` hold; `reward` = weighted sum ∈ [0, 1].
No LLM judge anywhere in the reward path.

## Sessions

Per-session state forks: each session copies the baseline SQLite DB; concurrent
rollouts never collide; `reset` restores the baseline copy.
