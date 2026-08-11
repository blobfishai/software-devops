"""Knowledge-base documents for the NovaCart world.

Pure data. No imports, no logic. Consumed by build_world.py to populate the
`documents` table that agents read with the document search/read tools.

Each entry:
    doc_id  : int, unique, sequential from 9601
    kind    : one of runbook | design_doc | adr | postmortem | api_spec |
              onboarding | policy
    title   : str, unique, referenced by tickets and by other documents
    service : str, one of the seeded service names, or "" for org-wide docs
    body    : markdown
    author  : str, matches a seeded persona
    day     : int, simulated day the document was last revised
"""

DOCUMENTS = [
    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------
    {
        "doc_id": 9601,
        "kind": "policy",
        "title": "Deployment policy",
        "service": "",
        "author": "Priya Nair",
        "day": 268,
        "body": """# Deployment policy

This policy is binding for every NovaCart service. It is enforced partly by
tooling and partly by review; deviations are treated as incidents.

## Staging first, always

Every production deploy must first succeed on staging with the **same version**.
`deploy_service(service, environment="staging", version=V)` must be in a
`succeeded` state for version `V` before `deploy_service(service,
environment="production", version=V)` is accepted. Deploying a version to
production that has never been deployed to staging is rejected. There is no
"hotfix exception" - a hotfix is still a version, and it still goes to staging
first. In practice this costs about ninety seconds and it has caught eleven bad
releases in the last two quarters.

## Tier-1 services canary

Tier-1 services are the four that are directly in the money path or in front of
customers:

- `storefront-web`
- `api-gateway`
- `checkout`
- `payments`

For these, the production deploy must be a canary: call `deploy_service` with
`canary_percent <= 25`. Twenty-five percent is a ceiling, not a target; 10% is
the usual first step for anything touching payment capture. The canary must then
be assessed with `assess_canary` and may only be promoted with `promote_canary`
once the assessment reports healthy. Promoting a canary that `assess_canary`
reports as unhealthy is the single most common way engineers turn a small
regression into a SEV1 - see "Postmortem: api-gateway v5.1.0 latency surge"
in the incident archive.

Tier-2 services (`catalog`, `notifications`, `search`) deploy at 100% directly,
still staging-first.

## Rollback

`rollback_deployment` is **exempt** from the staging-first rule. During an
incident you roll back immediately; you do not stage a rollback. Rolling back
returns the service to the previously succeeded production version. See the
"Incident response" runbook for where rollback sits in the mitigation ordering,
and "Rollback and recovery" for the mechanics.

## Deployment score

Every deploy that trips an alarm counts against the owning team's deployment
score, which is reviewed monthly. A tripped alarm on a canary that was correctly
assessed and *not* promoted is recorded but weighted at one quarter - the
canary did its job. This is deliberate: we would rather you canary and catch it
than skip the canary and get lucky.

## Related

- "Database migration policy" - migrations precede the code that needs them.
- "ADR-021: Standardize on staged canary deploys" - why we chose this shape.
- "Engineering onboarding: how we ship" - the end-to-end workflow.
""",
    },
    {
        "doc_id": 9602,
        "kind": "policy",
        "title": "Database migration policy",
        "service": "",
        "author": "Diego Ramos",
        "day": 254,
        "body": """# Database migration policy

Schema changes are the most common way a deploy goes sideways, because the code
and the schema move on different clocks. This policy makes the ordering
explicit.

## Migrations ship ahead of code

A schema change ships as a **migration**, applied to an environment with
`apply_migration(service, environment, migration_id)`. The migration must be
applied to an environment **before** the code version that depends on it is
deployed there.

The order for a schema-dependent release is therefore:

1. `apply_migration(service, "staging", M)`
2. `deploy_service(service, "staging", V)`
3. `apply_migration(service, "production", M)`
4. `deploy_service(service, "production", V)` - canary if tier-1
5. `promote_canary(...)` after `assess_canary` reports healthy

Deploying a version whose migration has not been applied in that environment
**fails the deploy**. The deploy tool checks the declared migration dependency of
the version and refuses to start. This is a hard failure, not a warning, and it
counts as a failed deploy for the team's deployment score.

## Forward-only

Migrations are **forward-only**. We do not write `down` steps and we do not
"unapply" a migration. If a migration is wrong, the fix is a *new* migration
that corrects it. The reasoning: a down-migration that drops a column is
indistinguishable from data loss when it runs against production, and the one
time we needed it under pressure it was untested. See "Postmortem: catalog
migration 0043 forced a rollback" for the incident that settled this argument.

Because migrations are forward-only, code rollback and schema rollback are
asymmetric: `rollback_deployment` moves the code back a version, but the schema
stays where it is. That is only safe if migrations are written to be
**backwards compatible with the previous code version** - the N-1 rule.

## The N-1 rule

Every migration must leave the database readable and writable by the currently
deployed code. Concretely:

- Adding a column: always safe, add it nullable or with a default.
- Renaming a column: never do it in one step. Add the new column, dual-write,
  backfill, switch reads, drop the old column in a later migration.
- Dropping a column or table: only after a release in which no deployed code
  references it.
- Adding a NOT NULL constraint: backfill first, constrain in a second migration.

## Review

Any migration that touches a table over ten million rows needs a second reviewer
from the owning team plus one from platform. `orders`, `payments_ledger`, and
`catalog_products` are all above that line.
""",
    },
    {
        "doc_id": 9603,
        "kind": "runbook",
        "title": "Retry and timeout standard",
        "service": "",
        "author": "Priya Nair",
        "day": 241,
        "body": """# Retry and timeout standard

Applies to every cross-service call in the NovaCart fleet. Two config keys per
downstream dependency, named after the downstream service.

## The two keys

For a caller talking to downstream service `X`:

- `<downstream>_retry_max_attempts` - **must be 3**
- `<downstream>_timeout_ms` - **must be at most 2000**

So `payments` calling `notifications` runs with
`notifications_retry_max_attempts=3` and `notifications_timeout_ms=2000` (or
lower). `checkout` calling `payments` runs with `payments_retry_max_attempts=3`
and `payment_timeout_ms` inside the 2000ms ceiling.

Retries use exponential backoff with jitter; the backoff schedule is applied
automatically by the shared HTTP client, so you do not configure delays. Three
attempts means one initial call plus two retries, worst case roughly
`3 * timeout_ms` plus backoff.

## Why 3 and why 2000

**A retry value of 0 means one timeout permanently fails the request.** There is
no second chance. A single blip in a downstream - a pod restart, a brief GC
pause, a rebalanced connection - becomes a user-visible failure and a failed
order. This is not hypothetical: payments ran with
`notifications_retry_max_attempts=0` and `notifications_timeout_ms=30000` for
several weeks and pushed `error_rate_pct` from a baseline of 0.4% to 3.8%,
straight through the 1.0% SLO.

The 2000ms ceiling exists because timeouts multiply up the call stack. A 30000ms
timeout on a leaf call does not "wait patiently" - it holds a request-handling
worker and a database connection for thirty seconds, and under load that is how
you exhaust a pool (see "Connection pool sizing"). If a downstream genuinely
cannot answer in two seconds, the call belongs on a queue, not in the request
path.

## Checklist for a new dependency

1. Add `<downstream>_retry_max_attempts=3` to the caller's config.
2. Add `<downstream>_timeout_ms` at or below 2000.
3. Confirm the call is idempotent, or that the downstream deduplicates by
   idempotency key. Retrying a non-idempotent write is worse than failing.
4. Confirm the caller's own inbound timeout is larger than
   `attempts * timeout_ms` plus backoff, or the retry budget is fiction.
5. Add the dependency to the service's dependency section in its design doc.

## Anti-patterns

- Retrying on 4xx. Only retry timeouts, connection errors, 429, and 5xx.
- Retrying inside a retry. Nested retries multiply: 3 x 3 = 9 calls.
- Raising the timeout to "fix" a slow downstream. Fix the downstream.
""",
    },
    {
        "doc_id": 9604,
        "kind": "runbook",
        "title": "Search caching",
        "service": "search",
        "author": "Mei Tanaka",
        "day": 233,
        "body": """# Search caching

Owner: growth. Service: `search` (tier 2, python). SLO:
`latency_p99_ms < 300`.

## The rule

Production `search` **requires `cache_enabled=true`**. This is not a tuning
knob; it is a capacity assumption baked into how the index cluster is sized.

## Why

The query cache sits in front of the primary index and absorbs roughly **75% of
index load**. Search traffic is extremely head-heavy: the top few thousand
queries ("black jeans", "usb-c cable", "gift card") are a large majority of all
requests, and their result sets change only when the index is rebuilt. Serving
those from cache is close to free.

With `cache_enabled=false` every request goes to the primary index. Observed
effect in production: `latency_p99_ms` moves from a ~210ms baseline to ~640ms and
keeps climbing as concurrency rises, blowing through the 300ms SLO and firing a
`medium` alert. The service does not error - it just gets slow, which is why this
one is easy to miss until the alert fires. The tell in the logs is:

```
WARN query cache disabled (cache_enabled=false); every request is hitting the primary index
```

## Config keys

| Key             | Production value | Notes                                      |
| --------------- | ---------------- | ------------------------------------------ |
| `cache_enabled` | `true`           | Required. Never ship `false` to production. |
| `cache_ttl_s`   | `300`            | Standard TTL. Five minutes.                 |
| `index_shards`  | `4`              | Change only with a capacity review.         |

`cache_ttl_s=300` is the standard. It is a deliberate compromise: long enough
that the hit rate stays above 70%, short enough that a price or availability
change is visible within five minutes. Do not lower it below 60 - at that point
the stampede risk (below) outweighs the freshness gain. Do not raise it above
900 without merchandising sign-off, because stale out-of-stock results generate
support tickets.

## Cache stampede

A cold cache is dangerous, not merely slow. When many identical queries miss at
once they all reach the index simultaneously. We ship single-flight coalescing
plus a +/-10% TTL jitter for exactly this reason. If you flush the cache
manually, do it during low traffic and expect a latency spike. The full story is
in "Postmortem: search cache stampede after index rebuild".

## Changing cache config

`cache_enabled` and `cache_ttl_s` are repo config, not runtime flags. Changing
them means a PR with a `config` change, CI, merge, then a deploy - staging
first, per the "Deployment policy". `search` is tier 2, so production deploys go
straight to 100%.

## Verification

After deploying, confirm `latency_p99_ms` has returned to the ~210ms band before
resolving any related alert.
""",
    },
    {
        "doc_id": 9605,
        "kind": "runbook",
        "title": "Catalog pricing performance",
        "service": "catalog",
        "author": "Diego Ramos",
        "day": 229,
        "body": """# Catalog pricing performance

Owner: commerce. Service: `catalog` (tier 2, python). Consumed by `search`,
`checkout`, and `storefront-web` on every product listing render.

## The rule

`batch_pricing_enabled=true` is **required in production**.

## Why

`catalog` resolves a price per product from the pricing rules table, applying
the active promotion, the customer's currency, and any tier discount. With
`batch_pricing_enabled=false`, the listing endpoint loops over the products in
the response and issues one pricing query per product. This is a textbook
**N+1 pattern**: a 48-item category page produces 1 listing query plus 48
pricing queries.

Measured cost: the per-product loop adds roughly **500ms at p99** on a standard
category page. It also multiplies database connection checkouts by the page
size, which is how a catalog slowdown turns into a `db_pool_size` exhaustion
event in a service that was nowhere near its own limits (see "Connection pool
sizing").

With `batch_pricing_enabled=true` the same page issues one listing query and one
batched pricing query with an `IN` clause over the product ids, then applies
promotions in memory. Same results, two round trips.

## Config keys

| Key                       | Production value | Notes                                  |
| ------------------------- | ---------------- | -------------------------------------- |
| `batch_pricing_enabled`   | `true`           | Required. The N+1 killer.              |
| `cdn_enabled`             | `true`           | See "CDN and media delivery".          |

## How to spot it

- p99 on `catalog` listing endpoints scales with page size rather than staying
  flat. If 24 items is 200ms and 96 items is 900ms, it is the loop.
- Database query counts per request in the hundreds.
- Log lines of the form `pricing lookup for product_id=... (batch disabled)`
  repeating with the same trace id.

## Fixing it

`batch_pricing_enabled` is repo config. Ship it as a PR with a `config` change,
run CI, merge, deploy to staging, then production. `catalog` is tier 2 so the
production deploy is a straight 100% deploy - no canary required, though a
canary is never wrong.

After the deploy, re-measure p99 on a large category page before closing the
ticket.

## Do not

- Do not "fix" this by raising `db_pool_size`. That hides the symptom and moves
  the failure to the database.
- Do not add a per-product cache in front of the loop. The batch query is
  cheaper than the cache lookups it would replace.
""",
    },
    {
        "doc_id": 9606,
        "kind": "runbook",
        "title": "Incident response",
        "service": "",
        "author": "Priya Nair",
        "day": 271,
        "body": """# Incident response

The one runbook everyone is expected to know cold. When an alert fires, follow
these steps **in order**. Do not skip ahead to root cause analysis - mitigate
first, understand later.

## The ordered steps

1. **Acknowledge the firing alert.** This tells everyone else the page has an
   owner. An unacknowledged alert is assumed unowned and will escalate.
2. **Mitigate.** Two levers, in order of preference:
   - `rollback_deployment` if the regression correlates with a deploy. Rollback
     is exempt from staging-first (see "Deployment policy").
   - Feature-flag kill switch: `set_feature_flag(..., enabled=false)` in the
     affected environment only. Flags are runtime toggles and need no deploy.
   Mitigation is not the fix. Do not spend twenty minutes writing a patch while
   customers are failing.
3. **Verify metric recovery.** Read the metric that fired. It must actually be
   back inside its SLO. "It looks better" is not verification.
4. **Resolve the alert.**
5. **Resolve the incident.**
6. **Post an update in `#incidents`.** What broke, what you did, current status.
   One paragraph is fine; silence is not.
7. **Publish a public status-page update** for any customer-visible incident.
   If a customer could have seen an error, a slow page, or a failed order, it is
   customer-visible. When in doubt, publish.
8. **For sev1, file a postmortem ticket** (type `postmortem`) naming the
   service and the version or flag involved. Sev1 postmortems are due within
   five working days.

## Severity

- **sev1** - money path broken or the whole site is down. `checkout`,
  `payments`, `api-gateway`, `storefront-web` hard-failing. Postmortem
  mandatory.
- **sev2** - significant degradation, workaround exists, revenue impact
  bounded. Postmortem optional but encouraged.
- **sev3** - internal or cosmetic, no customer impact.

## Choosing the mitigation

| Signal                                            | Mitigation           |
| ------------------------------------------------- | -------------------- |
| Regression starts exactly at a deploy timestamp    | `rollback_deployment` |
| Regression tracks a feature-flag rollout percent   | Flag kill switch     |
| Config value is obviously wrong in production      | Config PR + deploy   |
| Downstream dependency is the one that is unhealthy | Page that team too   |

If the deploy that caused it was a canary, do not promote it - roll the canary
back and leave production on the previous version.

## Things that go wrong

- Resolving the alert before verifying recovery. It re-fires in four minutes and
  now nobody trusts the alert.
- Kill-switching a flag in *both* environments when only production is broken.
  Leave staging enabled so you can reproduce.
- Forgetting the status-page update. Support finds out from customers.

## Related

- "Deployment policy", "Rollback and recovery", "On-call and alert triage".
""",
    },
    {
        "doc_id": 9607,
        "kind": "runbook",
        "title": "Feature flags",
        "service": "",
        "author": "Mei Tanaka",
        "day": 247,
        "body": """# Feature flags

Every new user-facing feature ships **dark**: merged, deployed, and switched
off, then turned on gradually.

## Defining a flag

A flag is defined by a `flag` change in the PR that introduces the guarded code.
Flag and code land together, in one PR, so there is never a flag referencing
code that does not exist or guarded code with no way to turn it off. At merge
the flag is created **disabled in both environments** with a rollout of 0%.

Naming: lowercase snake_case, describing the feature, not the experiment -
`express_checkout`, `instant_refunds`, `new_search_ui`. Not `mei_test_2` and not
`enable_new_thing_v3_final`.

## Ordering: deploy the code, then enable the flag

**The guarded code must be deployed to production BEFORE the flag is enabled
there.** Enabling a flag whose code is not deployed does one of two things:
nothing at all (best case, and you waste an hour wondering why), or it activates
a half-present code path across a partially deployed fleet (worst case).

So the sequence is:

1. PR with the module change and the `flag` change - CI - merge.
2. Deploy to staging.
3. Deploy to production. Tier-1 services canary at `canary_percent <= 25`,
   `assess_canary`, then `promote_canary` (see "Deployment policy").
4. Only now: `set_feature_flag(flag, environment="production", enabled=true,
   rollout_percent=10)`.

## Initial rollout must not exceed 10%

The first production enablement is capped at **10%**. Sit there long enough to
see real traffic - at minimum one full traffic peak - and watch the owning
service's error rate and p99. Then ramp: 10 - 25 - 50 - 100, checking metrics at
each step.

Flags are **runtime toggles**: `set_feature_flag` takes effect immediately and
needs **no deploy**. That cuts both ways - it is why a flag is the fastest kill
switch we have, and it is why an unreviewed ramp to 100% is the fastest way to
cause a sev2. The `instant_refunds` incident was exactly this: the flag went to
100% in production and `checkout` `error_rate_pct` went from 0.3% to 5.5%.

## Kill switch

During an incident, disable the flag in the affected environment only. Leave the
other environment as it is so you can still reproduce. See "Incident response".

## Cleanup

**Stale flags must be cleaned up after full rollout.** Once a flag has been at
100% in production for two weeks and there is no plan to turn it off, remove the
conditional from the code and delete the flag in a follow-up PR. Every flag left
behind is a branch of untested code and a future outage. The owning team reviews
its flag list at each sprint boundary.
""",
    },
    {
        "doc_id": 9608,
        "kind": "runbook",
        "title": "API deprecation",
        "service": "api-gateway",
        "author": "Priya Nair",
        "day": 259,
        "body": """# API deprecation

How to retire a public endpoint without breaking integrators. Traffic weights
live in `api-gateway` production runtime state; endpoint status lives in the
repo.

## The three phases

### 1. Deprecate and deploy

Mark the endpoint `deprecated` via an `endpoint` PR change, and **deploy that
first**. Deprecation is a real code change: the gateway starts emitting
`Deprecation` and `Sunset` response headers, the endpoint is flagged in the
public API reference, and usage is tagged by client id so we can see who is
still on it. `api-gateway` is tier 1, so this deploy is staging first, then a
production canary at `canary_percent <= 25`, `assess_canary`, `promote_canary`.

Do not shift any traffic yet. Deprecated is a label, not a redirect.

### 2. Shift traffic in stages

Move traffic from the legacy endpoint to its replacement in steps of **at most
50 percentage points per step**. A typical path is 100 - 50 - 0 with a soak in
between, and for a high-volume endpoint 100 - 75 - 50 - 25 - 0 is better.

At each step:

- Watch the replacement's error rate and p99 for at least one traffic peak.
- Compare response shapes on a sample of real requests.
- If anything regresses, shift back. Shifting back is free and instant.

The two endpoints' weights should sum to 100 at every step. A step larger than
50 points is rejected - it is the difference between a bad hour and a bad
quarter.

### 3. Retire

**Only when the legacy endpoint serves 0% traffic may it be retired.** Retire it
with a second `endpoint` PR change (status `retired`) and deploy that change,
staging first, canary, promote.

**CI blocks retiring an endpoint that is still serving traffic.** The check
reads the production traffic weight for the endpoint and fails the run if it is
non-zero. This is not overridable; get the weight to 0 first.

## Communication

- Announce in `#eng` when the deprecation deploy lands.
- Give external integrators a minimum 90-day sunset window from the date the
  `Sunset` header first ships.
- Update the public API spec in the same sprint - see "Public Orders API".

## Worked example

`/v1/orders` to `/v2/orders`: deprecate `/v1/orders` and deploy; shift
`/v1/orders` 100 to 50 while `/v2/orders` goes 0 to 50; soak; shift to 0/100;
soak; retire `/v1/orders` and deploy. Rationale in "ADR-031: Versioned public
API (/v1 to /v2 orders)".
""",
    },
    {
        "doc_id": 9609,
        "kind": "runbook",
        "title": "Security response",
        "service": "",
        "author": "Alex Osei",
        "day": 263,
        "body": """# Security response

Covers dependency vulnerabilities reported by the scanner and secrets found in
source. Security tickets carry the `security` type and are prioritized above
feature work.

## Vulnerable dependency

Ordered steps:

1. **Patch the vulnerable dependency.** Bump to the fixed version named in the
   finding via a PR with a `dependency` change. Do not jump several major
   versions to "get ahead" - patch to the fixed version, then plan the upgrade
   separately.
2. **Deploy staging, then production.** Staging-first per the "Deployment
   policy". Tier-1 services canary at `canary_percent <= 25`, `assess_canary`,
   then `promote_canary`.
3. **Verify the scanner shows the finding remediated.** Re-run the scan against
   the deployed service and confirm the vulnerability status is no longer
   `open`. A merged PR is not remediation; a deployed and re-scanned service is.
4. **Post an audit summary to `#security` referencing the CVE id.** State the
   CVE, the service, the old and new versions, and when production was patched.
   Auditors read this channel; the CVE id must appear literally.
5. **Close the security ticket.**

Timelines by severity, measured from the finding appearing:

| Severity | Production patched within |
| -------- | ------------------------- |
| critical | 48 hours                  |
| high     | 7 days                    |
| medium   | 30 days                   |
| low      | next maintenance window   |

## Secrets in code

If a credential, API key, or token is found in source, config, or CI logs:

1. **Move it to the secret manager.** Set config key
   `use_secret_manager=true` for the service and reference the secret by name;
   the value never appears in the repo again.
2. **Rotate the credential.** Assume it is compromised the moment it was
   committed - git history is forever and the repo is mirrored to CI. Rotation
   is not optional even if the repo is private.
3. Deploy staging then production, verify the service still authenticates, and
   post the summary to `#security`.

Do not "delete the line and force-push". The old blob is still reachable and the
credential is still live.

## Escalation

Anything involving customer data exposure, an actively exploited vulnerability,
or credential misuse in production is a sev1 - open an incident and follow
"Incident response" in parallel with this runbook.

## Related

- "ADR-027: Move partner credentials to the secret manager".
""",
    },
    {
        "doc_id": 9610,
        "kind": "runbook",
        "title": "Flaky tests",
        "service": "",
        "author": "Diego Ramos",
        "day": 244,
        "body": """# Flaky tests

A flaky test is a test that passes and fails without the code changing. It is
worse than a failing test, because it teaches the team to ignore red builds.

## Diagnose from CI history

Start with `list_ci_runs` for the service. You are looking for the same test
name alternating between `passed` and `failed` across runs on the same commit or
adjacent commits. The CI detail line usually names it:

```
intermittent failure: test_checkout_idempotency (rerun may pass)
```

Common root causes, roughly in order of how often we hit them:

1. **Shared mutable fixture state** - two tests write the same row, key, or temp
   file, and ordering decides who wins. The `test_checkout_idempotency` flake was
   a nondeterministic idempotency-key collision in the fixture.
2. **Time and timezone** - `now()` at a boundary, tests that assume ordering by
   second-resolution timestamps.
3. **Unseeded randomness** - random ids that occasionally collide.
4. **Real sleeps and races** - `sleep(0.1)` standing in for a synchronization
   point.
5. **Network or clock dependence** - a test that quietly reaches a real service.

## Fix the root cause

Ship the fix as a PR containing a `test_fix` change with **action `fix`**. The
change should make the test deterministic: seed the randomness, isolate the
fixture per test, inject the clock, replace sleeps with explicit waits.

**Quarantine is a last resort.** A `test_fix` change with action `quarantine`
stops the test from blocking CI, but it **does not close the ticket** - the
ticket stays open until an action `fix` change lands. Quarantine is for
unblocking a release train at 2am, not for closing your backlog. Quarantined
tests are reviewed weekly and anything quarantined for more than two weeks is
escalated to the owning team's lead.

## Prove stability

After merging, demonstrate stability with **3 consecutive green main-branch
runs**: `run_ci(service=...)` three times, all `passed`, with no other change in
between. One green run proves nothing about a test that fails half the time -
three consecutive greens give roughly 87% confidence for a 50% flake and much
more for the typical 10-20% flake.

Only then close the ticket.

## Prevention

- No shared fixtures across test files; build state per test.
- Inject the clock, never call `now()` directly in application code under test.
- Seed every random source in the test harness.
- If a test needs a real dependency, it is an integration test - label it and
  run it in the integration stage.
""",
    },
    {
        "doc_id": 9611,
        "kind": "runbook",
        "title": "Connection pool sizing",
        "service": "",
        "author": "Priya Nair",
        "day": 236,
        "body": """# Connection pool sizing

Applies to every service holding a database connection pool. The relevant config
key is `db_pool_size`.

## The rule

`db_pool_size` must be **at least 20** for tier-1 and tier-2 services. Below
that, requests queue and time out under normal traffic - not peak traffic,
normal traffic.

## Why 20

The pool is the number of database connections a single service instance may
hold concurrently. When every connection is checked out, the next request waits
on the pool's acquire queue. That wait is invisible in database metrics - the
database looks idle and healthy - and shows up only as application latency and
timeouts. It is one of the most consistently misdiagnosed failures we have.

Rough sizing arithmetic: a service handling 200 requests per second per instance
with a 40ms mean query time needs about `200 * 0.04 = 8` connections just to
keep up in steady state. Traffic is bursty, queries are not uniform, and one
slow query holds a connection for its full duration, so we take a 2-3x headroom
factor. Twenty is the resulting floor for anything customer-facing.

## Symptoms of an undersized pool

- Application p99 climbs while the database's own p99 is flat.
- Errors are `TimeoutError` on acquire, not on query execution.
- Latency is highly sensitive to a small change in traffic - a 10% traffic
  increase doubles p99. Queueing systems behave like this near saturation.
- Restarting the service "fixes" it for a few minutes.

## Upper bound

Bigger is not automatically better. Total connections to the primary is
`instances * db_pool_size` and the database has a hard `max_connections`. Past
that ceiling, connection attempts are refused outright, which is a far worse
failure than queueing. Before raising a pool above 50 per instance, check the
instance count and the database limit, and consider a connection proxy instead.

## Interaction with timeouts

Pool sizing and the "Retry and timeout standard" are the same problem seen from
two directions. A downstream call with a 30000ms timeout holds its request
worker - and any connection that worker checked out - for thirty seconds. A
handful of those exhausts a 20-connection pool. Keeping
`<downstream>_timeout_ms` at or below 2000 is part of pool hygiene.

## Changing it

`db_pool_size` is repo config: PR with a `config` change, CI, merge, deploy
staging then production. Measure p99 and the acquire-wait metric before and
after; if p99 did not move, the pool was not the bottleneck and you should look
at query performance instead (see "Catalog pricing performance" for the classic
N+1 case).
""",
    },
    {
        "doc_id": 9612,
        "kind": "runbook",
        "title": "Queue consumer tuning",
        "service": "notifications",
        "author": "Priya Nair",
        "day": 226,
        "body": """# Queue consumer tuning

Owner: platform. Primary consumer service: `notifications` (tier 2), which
drains the email, SMS, and push delivery queues. The same rules apply to any
service that consumes from the message broker.

## The rule

`prefetch_count` must be a **bounded** value. **Recommended: 50.**

`prefetch_count=0` means **unlimited prefetch** and is the single worst setting
in this runbook.

## What prefetch does

Prefetch is the number of unacknowledged messages the broker will push to a
single consumer. With `prefetch_count=50`, a consumer holds at most 50
in-flight messages; the broker will not send a 51st until one is acknowledged.
This is the backpressure mechanism - it is what lets a slow consumer tell the
broker to slow down.

With `prefetch_count=0` there is no backpressure. The broker pushes the entire
backlog to whichever consumer connects first. Consequences, all of which we have
seen in `notifications`:

- **Memory pressure.** A 400k-message backlog lands in one process's heap. RSS
  climbs until the container hits its memory limit.
- **Consumer restarts.** The container is OOM-killed, the unacknowledged
  messages are redelivered, the restarted consumer grabs them all again, and it
  is killed again. A restart loop that looks like a broker problem and is not.
- **Terrible load distribution.** One consumer holds everything while its
  siblings sit idle, so scaling out does nothing.
- **Head-of-line latency.** A high-priority message sits behind 400k others.

## Sizing

| Message profile                | prefetch_count |
| ------------------------------ | -------------- |
| Fast, uniform (a few ms each)  | 100-200        |
| Standard delivery work         | **50**         |
| Slow or variable (seconds)     | 5-10           |
| Long-running jobs (minutes)    | 1              |

Rule of thumb: `prefetch_count` should be roughly the number of messages a
consumer can process in one to two seconds. Start at 50 and adjust with
evidence.

## Related settings

- `smtp_pool` on `notifications` bounds concurrent SMTP connections. Prefetch
  above the SMTP concurrency just buys queueing inside the process.
- Ack **after** the work is done, never on receipt. Acking on receipt turns a
  crash into silent message loss.
- Dead-letter after 5 delivery attempts so a poison message cannot loop forever.

## Changing it

Repo config: PR with a `config` change, CI, merge, staging, production.
`notifications` is tier 2 - straight 100% deploy after staging. Watch consumer
memory and queue depth for one full peak after the change.
""",
    },
    {
        "doc_id": 9613,
        "kind": "runbook",
        "title": "CDN and media delivery",
        "service": "catalog",
        "author": "Mei Tanaka",
        "day": 221,
        "body": """# CDN and media delivery

Covers media-service, the product-image and asset delivery path owned by
commerce and shipped as part of the `catalog` service. Product photography,
generated thumbnails, size charts, and marketing video posters all flow through
it.

## The rule

`cdn_enabled=true` is **required in production** for media-service. Origin-only
serving is not an acceptable production configuration.

## Why

With the CDN enabled, edge nodes serve cached objects close to the user and the
origin sees only cache misses and revalidations - typically under 5% of
requests. With `cdn_enabled=false`, every image request travels to the origin
and out of the object store.

Measured impact of origin-only serving:

- **~600ms added at p99** on image-heavy pages. Category and product-detail
  pages are the worst affected because they fan out to dozens of assets, and
  browsers cap parallel connections per origin, so the latency serializes.
- **Object-store cost rises sharply.** Egress and per-request charges are billed
  on every single request instead of on misses. In the one week we ran
  origin-only during a migration, media egress was roughly 20x the normal line
  item.
- Origin bandwidth saturates first during traffic spikes, and image failures
  make the storefront look broken even when checkout is perfectly healthy.

## Config

| Key             | Production value | Notes                                   |
| --------------- | ---------------- | --------------------------------------- |
| `cdn_enabled`   | `true`           | Required.                               |

Cache-control defaults: immutable, content-hashed asset URLs get a one-year
max-age; mutable paths get 300s with revalidation. Because asset URLs are
content-hashed, a new image is a new URL - you should almost never need to purge.

## Purging

Purge only for a legal or trademark takedown, or for an asset published in
error. A full-prefix purge is effectively a cold cache: expect an origin load
spike and a temporary p99 regression. Purge narrowly, by exact URL, during low
traffic.

## Troubleshooting

- Images slow but HTML fast: check `cdn_enabled` first, before anything else.
- Cache hit ratio below 90%: usually a query string added to asset URLs, which
  fragments the cache key. Strip non-semantic query parameters at the edge.
- 403s from the edge: signed-URL clock skew on the origin.

## Changing it

Repo config: PR with a `config` change, CI, merge, staging, then production per
the "Deployment policy". Verify p99 on a product-detail page and the edge hit
ratio before closing the ticket.
""",
    },
    {
        "doc_id": 9614,
        "kind": "design_doc",
        "title": "Checkout architecture",
        "service": "checkout",
        "author": "Diego Ramos",
        "day": 198,
        "body": """# Checkout architecture

Service: `checkout` (tier 1, python, commerce). Owns the cart and the checkout
orchestration state machine. SLOs: `error_rate_pct < 1.0`,
`latency_p99_ms < 400`.

## Responsibilities

`checkout` owns the transition from "a cart exists" to "an order exists and is
paid". It does not own money movement (that is `payments`), product data (that
is `catalog`), or customer notification (that is `notifications`). It owns the
sequencing and the guarantee that the sequence happens exactly once.

Modules: `cart`, `checkout_flow`, and - once the loyalty program ships -
`loyalty_redeem`.

## The state machine

Every checkout session is a row with an explicit state:

```
cart_open -> pricing_locked -> payment_pending -> paid -> order_created
                   |                   |
                   +-> abandoned       +-> payment_failed
```

Transitions are append-only and each is stamped with the idempotency key of the
request that caused it. Replaying a request that has already produced a
transition returns the existing result rather than performing it again. This is
what makes the checkout endpoint safe to retry, which matters because clients
retry aggressively on mobile networks.

## Dependencies

| Downstream      | Call                     | Timeout budget            |
| --------------- | ------------------------ | ------------------------- |
| `catalog`       | price and availability   | `<= 2000ms`, 3 attempts   |
| `payments`      | authorize and capture    | `payment_timeout_ms`      |
| `notifications` | order confirmation       | async, fire-and-forget    |

All synchronous calls follow the "Retry and timeout standard": three attempts,
timeout at or below 2000ms. The `notifications` call is deliberately
asynchronous - a confirmation email must never be able to fail an order.

## Pricing lock

At `pricing_locked` we snapshot the price, the promotion, and the tax
computation into the session row. From that point the customer pays the price
they were shown even if `catalog` changes underneath. The lock expires after 20
minutes, after which the session re-prices.

## Failure handling

- `payments` timeout: the session stays `payment_pending` and a reconciliation
  job asks `payments` for the authoritative status. We never assume a timeout
  means "did not happen".
- `catalog` unavailable: fail closed. We do not sell at a guessed price.
- Partial capture: not supported; a capture is all-or-nothing per order.

## Feature flags

Checkout-adjacent behavior ships behind flags - `instant_refunds`,
`express_checkout`. Per the "Feature flags" runbook, the code deploys first and
the flag is enabled afterwards at no more than 10%. `instant_refunds` is the
cautionary tale: ramped to 100% in production, it took `error_rate_pct` from
0.3% to 5.5% via a nil-pointer panic in the refund worker.

## Open questions

- Should the pricing lock move into `catalog` so `search` can honor it too?
- Cart merge on login is still last-write-wins; it should be a real merge.
""",
    },
    {
        "doc_id": 9615,
        "kind": "design_doc",
        "title": "Payments settlement pipeline",
        "service": "payments",
        "author": "Diego Ramos",
        "day": 205,
        "body": """# Payments settlement pipeline

Service: `payments` (tier 1, python, commerce). Owns capture, refunds, and daily
settlement against the processor. SLOs: `error_rate_pct < 1.0`,
`latency_p99_ms < 200`.

## Ledger first

Everything in `payments` is derived from an append-only ledger. A capture is not
"a field set to captured" - it is a sequence of ledger entries that must balance.
Nothing is ever updated in place; corrections are compensating entries. This is
what makes settlement reconcilable at all.

Entry kinds: `authorization`, `capture`, `refund`, `chargeback`, `fee`,
`payout`. Each carries the processor reference id, the currency, the minor-unit
amount, and the order id.

## Synchronous path

1. `checkout` calls authorize with an idempotency key.
2. `payments` writes an `authorization` entry and calls the processor through
   `libpayproc`.
3. On success, capture is either immediate or deferred to fulfilment depending
   on the merchant configuration.
4. `payments` emits an event; `notifications` sends the receipt.

The call to `notifications` is where this service has historically hurt itself.
It must run with `notifications_retry_max_attempts=3` and
`notifications_timeout_ms` at or below 2000, per the "Retry and timeout
standard". Running with retries at 0 and a 30000ms timeout produced
`ConnectionTimeout` errors that permanently failed the request and marked orders
failed, pushing `error_rate_pct` from a 0.4% baseline to 3.8%.

## Nightly settlement

At 02:00 UTC the settlement job:

1. Freezes the ledger cursor for the previous day.
2. Fetches the processor's settlement file.
3. Matches each processor line to a ledger entry by reference id.
4. Writes `fee` and `payout` entries for matched lines.
5. Files unmatched lines into an exceptions queue for manual review.

The exceptions queue is expected to be small but never empty - a handful of
cross-midnight captures land there daily and clear the next run.

## Invariants

- Sum of `capture` minus `refund` minus `chargeback` per order is never
  negative.
- No order has a `capture` without a preceding `authorization`.
- Every `payout` reconciles to a processor settlement line.

These are asserted by a checker that runs after settlement; a violation pages
commerce immediately.

## Pool and dependencies

`db_pool_size` is 20 (the floor from "Connection pool sizing"). `libpayproc` is
pinned and patched promptly - it is the highest-value dependency in the fleet
for an attacker, and CVE handling follows "Security response".

## Open questions

- Multi-currency payouts still net in the merchant's home currency only.
- Chargeback ingestion is a daily poll; a webhook would cut the delay to minutes.
""",
    },
    {
        "doc_id": 9616,
        "kind": "design_doc",
        "title": "Search indexing pipeline",
        "service": "search",
        "author": "Mei Tanaka",
        "day": 212,
        "body": """# Search indexing pipeline

Service: `search` (tier 2, python, growth). Owns the product index, the query
path, and ranking. SLO: `latency_p99_ms < 300`.

## Two paths

**Ingest** takes product changes from `catalog` and turns them into index
documents. **Query** turns a user's text into a ranked result set. They share
nothing but the index itself, and they are deliberately allowed to fail
independently: a stalled ingest means stale results, not an outage.

## Ingest

`catalog` emits product-changed events. The indexer consumes them, hydrates the
full product (title, description, attributes, category path, price band,
availability), and writes into the index across `index_shards=4` shards, keyed
by product id so a product always lands on the same shard.

Two modes:

- **Incremental** - the steady state. Event to searchable in under 30 seconds at
  p95.
- **Full rebuild** - triggered by a mapping change or an analyzer change. Builds
  into a new index alias and swaps atomically. A rebuild takes about 40 minutes
  for the current catalog size.

A rebuild swap invalidates the query cache. That is the dangerous moment; see
"Postmortem: search cache stampede after index rebuild" and the warm-up
procedure it produced.

## Query

1. Normalize and analyze the query text.
2. Check the query cache (`cache_enabled`, `cache_ttl_s=300`).
3. On miss, fan out to all four shards, gather, and merge.
4. Rank, apply availability filtering, paginate.
5. Populate the cache, return.

The cache is not optional. It absorbs roughly 75% of index load, and running
with `cache_enabled=false` moves p99 from ~210ms to ~640ms. See the "Search
caching" runbook - that document is the operational contract for this design.

## Ranking

Score is a weighted blend: BM25 text relevance, a popularity signal from 30-day
conversions, availability (out-of-stock items are demoted, not hidden), and a
small merchandising boost that category managers control. Weights are versioned
alongside the index mapping so a ranking change and a mapping change move
together.

## Shard sizing

Four shards is a capacity decision, not a default. Each shard is roughly 6GB and
comfortably fits in page cache on the current instance type. Changing
`index_shards` requires a full rebuild and a capacity review - it is not a
config tweak you ship on a Friday.

## UI

The redesigned results page ships behind the `new_search_ui` flag, enabled in
staging and dark in production, per the "Feature flags" runbook.

## Open questions

- Vector recall for long-tail queries: promising offline, unproven on latency.
- Per-locale analyzers currently force a full rebuild per locale.
""",
    },
    {
        "doc_id": 9617,
        "kind": "design_doc",
        "title": "Loyalty points program",
        "service": "",
        "author": "Diego Ramos",
        "day": 288,
        "body": """# Loyalty points program

Cross-service feature spanning `catalog`, `checkout`, and `storefront-web`.
Customers earn points on purchases and redeem them for order discounts.

## Modules and ownership

| Module            | Service           | Responsibility                        |
| ----------------- | ----------------- | ------------------------------------- |
| `loyalty_accrual` | `catalog`         | Points-earning rules per product      |
| `loyalty_redeem`  | `checkout`        | Applying points as an order discount  |
| `loyalty_widget`  | `storefront-web`  | Balance display and redeem affordance |

Each module ships in **its own PR against its own service**. There is no shared
library; the contract between them is the points-rate field on the product
payload and the redeem call on the checkout API.

## Why this split

Accrual rules are product data - they vary per product and per category, they
change with merchandising campaigns, and they belong next to pricing. Redemption
is an order-level money decision and belongs in the checkout state machine.
Display is display. Putting accrual in `checkout` would have meant `checkout`
reading the product rules table, which is exactly the coupling we spent last
year removing.

## Rollout order

Deployment order matters and is not negotiable:

**`catalog` - then `checkout` - then `storefront-web`.**

The reasoning is a strict data dependency chain:

1. `catalog` must be emitting a points rate on the product payload before
   `checkout` can compute a balance to redeem against. If `checkout` ships
   first, every redeem attempt reads a missing field and either errors or
   silently computes zero.
2. `checkout` must expose the redeem endpoint and be live before
   `storefront-web` renders a redeem button. If the widget ships first,
   customers see a button that 404s - a visible, embarrassing failure on the
   busiest page we have.

`catalog` is tier 2 (straight production deploy after staging). `checkout` and
`storefront-web` are tier 1, so each is staging-first, then a production canary
at `canary_percent <= 25`, `assess_canary`, then `promote_canary` - see
"Deployment policy". Do not begin the next service's production deploy until the
previous one is fully promoted.

## Points model

Balances live in an append-only ledger, mirroring the approach in "Payments
settlement pipeline": `earn`, `redeem`, `expire`, `adjust`. Balance is the sum,
never a stored counter. Redemption is authorized at `pricing_locked` and
committed at `paid`; an abandoned cart releases the hold after 20 minutes.

Default rate is 1 point per whole currency unit, 100 points equals one currency
unit of discount, points expire 12 months after earning. Maximum redemption is
50% of order subtotal.

## Risks

- Double-redeem across concurrent sessions. Mitigated by the hold and by the
  idempotency key on the checkout transition.
- Accrual rule changes retroactively altering historical balances. The ledger
  stamps the rate version at earn time.
""",
    },
    {
        "doc_id": 9618,
        "kind": "adr",
        "title": "ADR-014: Adopt per-service feature flags",
        "service": "",
        "author": "Mei Tanaka",
        "day": 156,
        "body": """# ADR-014: Adopt per-service feature flags

**Status:** Accepted
**Date:** day 156
**Deciders:** growth, platform, commerce leads

## Context

Before this decision, shipping a user-facing change meant shipping a deploy, and
turning it off meant shipping another deploy. For tier-1 services that is a
staging deploy, a canary, an assessment, and a promotion - fifteen to forty
minutes on a good day. During the `checkout` incident in the previous quarter,
those minutes were the entire outage.

We also had three ad-hoc mechanisms doing flag-shaped work: an environment
variable in `storefront-web` (`ab_test_bucket`), a hardcoded allowlist in
`checkout`, and a database table in `catalog` that nobody remembered owning.
None were auditable and none could be changed safely under pressure.

## Decision

Adopt a single **per-service feature flag** system with the following
properties:

1. A flag is scoped to exactly one service and one environment. There is no
   global flag. `new_search_ui` in staging and `new_search_ui` in production are
   independent records with independent enabled state and rollout percent.
2. A flag is **defined by a `flag` change in the PR that introduces the guarded
   code**, so flag and code are reviewed together and land together.
3. At merge, the flag exists **disabled in both environments** at 0% rollout.
4. Toggling is a **runtime operation** (`set_feature_flag`) requiring **no
   deploy**.
5. Guarded code must be **deployed to production before the flag is enabled**
   there.
6. Initial production rollout is capped at **10%**.

## Alternatives considered

**Trunk-based with no flags, relying on fast rollback.** Rejected: rollback is
minutes and coarse - it reverts everything in the release, including unrelated
fixes. A flag reverts one behavior in seconds.

**A third-party flag SaaS.** Rejected for now: an external network dependency in
the request path of tier-1 services, and flag evaluation would have needed a
cache with its own failure modes. Revisit if we outgrow the current model.

**Global (cross-service) flags.** Rejected: they imply synchronized deploys
across services, which is precisely the coupling we are trying to avoid. The
loyalty rollout demonstrates the alternative - ordered per-service deploys.

## Consequences

Positive: mitigation in seconds via kill switch; dark launches; percentage
ramps; a per-service audit trail of who toggled what.

Negative: every flag is a branch in the code, and untested branches rot. This is
why the "Feature flags" runbook mandates cleanup of stale flags after full
rollout, reviewed at each sprint boundary.
""",
    },
    {
        "doc_id": 9619,
        "kind": "adr",
        "title": "ADR-021: Standardize on staged canary deploys",
        "service": "",
        "author": "Priya Nair",
        "day": 174,
        "body": """# ADR-021: Standardize on staged canary deploys

**Status:** Accepted
**Date:** day 174
**Deciders:** platform, SRE, engineering leadership

## Context

Production deploys were all-at-once. A bad release reached 100% of traffic in
the time it took the fleet to roll, which meant every defect that got past CI
and staging became a full-blast customer incident. Over two quarters, four of
our six sev1s and sev2s followed this shape: deploy, metric moves, scramble,
roll back. Mean time to detect was decent - our alerting is good - but by
detection time, everyone was already affected.

Staging catches a lot, but it does not catch what only real traffic produces:
production data shapes, real concurrency, real cache states, real client
diversity. A goroutine leak in a connection pool is invisible on staging's
traffic profile and obvious at 1000 rps.

## Decision

Standardize on **staged canary deploys** for tier-1 services:
`storefront-web`, `api-gateway`, `checkout`, `payments`.

1. Every production deploy still requires the **same version** to have
   succeeded on **staging** first.
2. The production deploy starts as a canary: `deploy_service` with
   `canary_percent <= 25`.
3. The canary is evaluated with **`assess_canary`**, which compares the canary
   population's error rate and latency against the stable population over the
   soak window.
4. Only when `assess_canary` reports **healthy** may the release be advanced
   with **`promote_canary`**.
5. If it reports unhealthy, roll the canary back. Do not promote and watch.
6. `rollback_deployment` is exempt from staging-first.

Tier-2 services (`catalog`, `notifications`, `search`) deploy at 100% after
staging. Their blast radius is degradation, not lost orders, and the operational
overhead of canarying everything was judged not worth it.

## Alternatives considered

**Blue/green.** Rejected: the cutover is still all-at-once, so it improves
rollback speed but not exposure. It also doubles the running fleet.

**Canary everything, all tiers.** Rejected as too slow for the number of deploys
tier-2 services make. Revisit if a tier-2 service ever causes a sev1.

**Time-based auto-promotion without assessment.** Rejected: a timer is not a
signal. It codifies "nothing paged in ten minutes" as health, and slow burns -
the exact class canaries are for - do not page in ten minutes.

## Consequences

Deploys take longer, and engineers must wait for an assessment. The tooling
enforces `canary_percent <= 25` on tier-1 production deploys. Any deploy that
trips an alarm counts against the team's deployment score, weighted at one
quarter if the canary was correctly assessed and not promoted - the incentive
points toward canarying honestly.

Operational detail lives in "Deployment policy".
""",
    },
    {
        "doc_id": 9620,
        "kind": "adr",
        "title": "ADR-027: Move partner credentials to the secret manager",
        "service": "payments",
        "author": "Alex Osei",
        "day": 191,
        "body": """# ADR-027: Move partner credentials to the secret manager

**Status:** Accepted
**Date:** day 191
**Deciders:** security, platform, commerce

## Context

Partner credentials - the payment processor API key, the shipping carrier
tokens, the SMTP credentials used by `notifications`, and the analytics
write key - were stored as plain config values in each service's repo config
and injected as environment variables at deploy time.

Three problems made this untenable:

1. **Git history is permanent.** Every credential ever committed remains in
   history, in every clone, and in every CI cache. Removing the line does not
   remove the secret.
2. **Rotation was a deploy.** Rotating the processor key meant a PR, CI, staging,
   canary, promote - per service. So rotation happened roughly never, and the
   processor key in production had been unchanged for over a year.
3. **No access audit.** We could not answer "who read this value, and when",
   which is a direct finding in the annual audit.

The trigger was a scanner hit: a carrier token visible in a config file in a
repo that four teams could read.

## Decision

All partner credentials move to the managed **secret manager**. Each service
opts in with the config key **`use_secret_manager=true`** and references secrets
by name rather than value. The application resolves secrets at startup and on a
refresh interval; the plaintext never appears in the repo, in a PR diff, or in a
deploy artifact.

Every credential moved is **rotated as part of the move**, on the assumption
that anything previously in the repo is compromised.

Rollout order: `payments` first (highest value), then `notifications`, then the
remaining services.

## Alternatives considered

**Encrypted secrets committed to the repo (sealed values).** Rejected: it solves
plaintext exposure but not rotation-as-a-deploy, and the decryption key becomes
the new committed secret.

**Environment variables set manually on hosts.** Rejected: unauditable,
drift-prone, and impossible to reproduce.

**Do nothing, tighten repo permissions.** Rejected: it does not address history,
rotation, or audit.

## Consequences

Positive: rotation is an operation, not a release; access is logged per read;
secret scanning in CI becomes a hard gate rather than advisory.

Negative: a new startup-time dependency. If the secret manager is unreachable a
service cannot start, so we cache the last successful resolution on disk,
encrypted, with a short TTL, to survive a brief outage.

Operational procedure for a leaked credential is in the "Security response"
runbook: move to the secret manager, **rotate**, deploy, verify, post to
`#security`.
""",
    },
    {
        "doc_id": 9621,
        "kind": "adr",
        "title": "ADR-031: Versioned public API (/v1 to /v2 orders)",
        "service": "api-gateway",
        "author": "Priya Nair",
        "day": 216,
        "body": """# ADR-031: Versioned public API (/v1 to /v2 orders)

**Status:** Accepted
**Date:** day 216
**Deciders:** platform, commerce, partner engineering

## Context

The public orders API at `/v1/orders` was shaped by the original single-currency,
single-shipment order model. Four requirements have since outgrown it:

- Multi-shipment orders. `v1` assumes one shipment per order and exposes
  `tracking_number` as a scalar.
- Minor-unit amounts. `v1` returns `total` as a decimal string, which every
  integrator parses into a float, and floats and money are a bad combination.
- Partial refunds. `v1` has a boolean `refunded`.
- Loyalty points. There is nowhere in the `v1` payload to put them.

Each of these is a breaking change to the response shape. There is no additive
path.

## Decision

Introduce **`/v2/orders`** as a new versioned path alongside `/v1/orders`, and
migrate traffic in stages rather than cutting over.

`v2` changes:

- `amount` fields are integer **minor units** plus an explicit `currency`.
- `shipments` is an **array**; each element carries its own carrier, tracking
  number, and line items.
- `refunds` is an **array** of refund records replacing the `refunded` boolean.
- `loyalty` object with `points_earned` and `points_redeemed`.
- Cursor pagination (`next_cursor`) replacing offset pagination.
- Errors follow a single problem-details shape with a stable `type` field.

Both paths are served by `api-gateway`, which routes by path and holds the
traffic weights in production runtime state. `v1` responses are produced by
adapting the `v2` internal representation, so there is one source of truth and
`v1` cannot drift.

The migration follows the "API deprecation" runbook: deprecate `/v1/orders` and
deploy that change first; then shift traffic in steps of **at most 50 percentage
points**; retire `/v1/orders` only when it serves **0%** traffic, which CI
enforces.

## Alternatives considered

**Header-based versioning (`Accept: application/vnd.novacart.v2+json`).**
Rejected: invisible in logs, dashboards, and traffic weights. Path versioning
lets us shift a percentage of traffic, which is the entire migration strategy.

**Additive-only evolution of v1.** Rejected: `total` and `refunded` cannot be
fixed additively without leaving permanently misleading fields.

**Big-bang cutover with a flag day.** Rejected: we have integrators we cannot
schedule.

## Consequences

Two response shapes to maintain during the migration window, and a 90-day
minimum sunset from the first `Sunset` header. Details of both shapes are in
"Public Orders API".
""",
    },
    {
        "doc_id": 9622,
        "kind": "postmortem",
        "title": "Postmortem: search cache stampede after index rebuild",
        "service": "search",
        "author": "Mei Tanaka",
        "day": 183,
        "body": """# Postmortem: search cache stampede after index rebuild

**Severity:** sev2
**Service:** `search`
**Duration:** 34 minutes of degraded search
**Author:** Mei Tanaka
**Status:** action items complete

## Summary

A planned index rebuild swapped the search index alias at a moderate traffic
hour. The alias swap invalidated the entire query cache. Every in-flight query
missed simultaneously and hit the primary index, driving `latency_p99_ms` from
~210ms to a peak of 2100ms and firing the `search latency_p99_ms` alert against
its 300ms SLO. Search was slow, not down; conversion on search-originated
sessions dropped an estimated 18% for the duration.

## Timeline (UTC)

- **14:02** Engineer starts a full index rebuild for an analyzer change. Routine;
  done a dozen times before.
- **14:41** Rebuild completes. Alias swaps to the new index. Query cache keys are
  namespaced by index generation, so the swap invalidates 100% of the cache.
- **14:42** `latency_p99_ms` crosses 300ms. Alert fires, `medium`.
- **14:44** On-call acknowledges. Initial hypothesis: the new analyzer is slow.
- **14:51** Index CPU is pegged; per-query cost is unchanged from before the
  rebuild. Hypothesis discarded - it is volume, not per-query cost.
- **14:58** Cache hit ratio confirmed at 3%, against a normal 76%. Root cause
  identified.
- **15:06** Traffic to search temporarily shed at the gateway by 30% to let the
  cache refill.
- **15:16** Hit ratio back above 60%; p99 at 340ms and falling.
- **15:22** Shedding removed. p99 at 215ms.
- **15:26** Alert resolved, incident resolved, update posted in `#incidents`.

## Root cause

The query cache is namespaced by index generation. An alias swap therefore
performs a **complete, instantaneous cache flush** with no warm-up. Because the
cache normally absorbs about **75% of index load**, the index was asked to serve
roughly 4x its steady-state query volume within one second. Requests queued,
latency rose, clients retried, and the retries added load - a classic stampede
with a positive feedback loop.

## Contributing factors

- No warm-up step in the rebuild procedure. The runbook ended at "swap alias".
- Rebuild was run at 14:00 local, in the daily traffic ramp, because the job
  takes 40 minutes and nobody wanted to babysit it at night.
- Single-flight coalescing existed for identical concurrent queries but the
  stampede was across *thousands of distinct* queries, so coalescing did nothing.
- No alert on cache hit ratio, so the actual signal was invisible for 14 minutes.

## What went well

- Alerting fired within a minute of the SLO breach.
- Load shedding at the gateway was the correct blunt instrument and worked.

## Action items

1. Add a **warm-up phase** to the rebuild: replay the top 5000 queries against
   the new index before swapping the alias. **Done.**
2. Add **+/-10% TTL jitter** to `cache_ttl_s=300` so natural expiry never
   synchronizes. **Done.**
3. Alert on **cache hit ratio below 50%** for 5 minutes. **Done.**
4. Move scheduled rebuilds to 03:00-05:00 UTC. **Done.**
5. Document the stampede risk in the "Search caching" runbook. **Done.**
""",
    },
    {
        "doc_id": 9623,
        "kind": "postmortem",
        "title": "Postmortem: catalog migration 0043 forced a rollback",
        "service": "catalog",
        "author": "Diego Ramos",
        "day": 202,
        "body": """# Postmortem: catalog migration 0043 forced a rollback

**Severity:** sev1
**Service:** `catalog` (with knock-on impact to `checkout` and `storefront-web`)
**Duration:** 22 minutes of failed product-detail pages
**Author:** Diego Ramos
**Status:** action items complete

## Summary

Migration `0043_rename_price_column` renamed `catalog_products.price_cents` to
`price_minor_units` in a single step, and the matching code version `v1.8.0` was
deployed immediately after. The migration was applied to production before the
deploy, as policy requires - but the migration was **not backwards compatible**
with the code version already running. Between the migration completing and the
new version being fully rolled out, the running `v1.7.6` instances queried a
column that no longer existed. Product-detail and category pages returned 500s;
`checkout` fell back to failing closed on pricing, per its design.

## Timeline (UTC)

- **09:12** `apply_migration(catalog, production, 0043)` starts.
- **09:13** Migration completes. Column renamed.
- **09:13** `v1.7.6` instances begin throwing
  `UndefinedColumn: price_cents` on every pricing query.
- **09:14** `catalog` error rate goes vertical. `checkout` starts failing closed.
  Two alerts fire.
- **09:15** Deploy of `v1.8.0` starts, as planned, but rolls instance by instance.
- **09:17** On-call acknowledges, declares sev1.
- **09:19** Commander recognizes the pattern: schema ahead of code, partial fleet.
- **09:21** Decision: do **not** attempt to reverse the migration. Accelerate the
  `v1.8.0` rollout instead.
- **09:31** Rollout complete on all instances. Errors stop.
- **09:34** Metrics confirmed recovered; alerts resolved; incident resolved.
- **09:40** Update posted in `#incidents`; status page updated and cleared.
- Later that day: `v1.8.0` was rolled back for an unrelated defect found in
  review, which is when the second lesson landed - the rolled-back `v1.7.6` code
  could not read the renamed column either, and a hotfix `v1.8.1` had to be cut
  because **migrations are forward-only** and there was no going back.

## Root cause

A **destructive, non-backwards-compatible schema change shipped in one step**. A
column rename is two incompatible states with no overlap: code that knows the old
name and code that knows the new name cannot both work against the same schema.
Any window in which both code versions run - and a rolling deploy guarantees such
a window - is an outage.

## Contributing factors

- The "migration before code" rule was followed correctly, and following it
  correctly was *insufficient*. The rule says nothing about compatibility with
  the code already running.
- The migration had one reviewer, from the authoring team.
- Rolling deploys were assumed to be fast enough not to matter. They are not.
- `catalog` is tier 2, so there was no canary to catch it at 25%.

## What went well

- Nobody tried to hand-write a reverse migration under pressure. Rolling forward
  was the right call and it was made in six minutes.
- `checkout` failing closed on pricing prevented selling at a wrong price.

## Action items

1. Write the **N-1 rule** into the "Database migration policy": every migration
   must leave the schema usable by the currently deployed code. **Done.**
2. Mandate the **expand/contract** pattern for renames: add column, dual-write,
   backfill, switch reads, drop in a later migration. **Done.**
3. Require a **second reviewer from platform** for migrations on tables above ten
   million rows. **Done.**
4. Add a CI check that flags `DROP COLUMN`, `RENAME COLUMN`, and new `NOT NULL`
   constraints for explicit sign-off. **Done.**
""",
    },
    {
        "doc_id": 9624,
        "kind": "api_spec",
        "title": "Public Orders API",
        "service": "api-gateway",
        "author": "Priya Nair",
        "day": 265,
        "body": """# Public Orders API

Served by `api-gateway`. Two versions are live: **`/v1/orders` (deprecated)** and
**`/v2/orders` (current)**. Authentication is a bearer partner token on both.
Rationale for the split is in "ADR-031: Versioned public API (/v1 to /v2
orders)".

## Status

| Path          | Status     | Notes                                        |
| ------------- | ---------- | -------------------------------------------- |
| `/v1/orders`  | deprecated | Emits `Deprecation` and `Sunset` headers.    |
| `/v2/orders`  | current    | Use for all new integrations.                |

Traffic between the two is weighted at the gateway and shifted in steps of at
most 50 percentage points per the "API deprecation" runbook. `/v1/orders` may
only be retired once it serves 0% of traffic; CI blocks retirement otherwise.

## `GET /v2/orders`

Query parameters: `status`, `created_after` (RFC3339), `limit` (default 50, max
200), `cursor`.

Response `200`:

```json
{
  "data": [
    {
      "id": "ord_01H9Z",
      "status": "paid",
      "created_at": "2026-03-04T11:02:19Z",
      "currency": "USD",
      "amount_total_minor": 12995,
      "amount_tax_minor": 1040,
      "shipments": [
        {"id": "shp_1", "carrier": "ups", "tracking_number": "1Z...",
         "line_item_ids": ["li_1", "li_2"], "status": "in_transit"}
      ],
      "refunds": [
        {"id": "ref_1", "amount_minor": 2500, "reason": "damaged",
         "created_at": "2026-03-07T09:11:00Z"}
      ],
      "loyalty": {"points_earned": 130, "points_redeemed": 0}
    }
  ],
  "next_cursor": "eyJvIjoiMDFIOVoifQ"
}
```

## `POST /v2/orders`

Request:

```json
{
  "idempotency_key": "5f2c...",
  "customer_id": "cus_88",
  "currency": "USD",
  "line_items": [{"sku": "NC-1042", "quantity": 2, "unit_price_minor": 4995}],
  "shipping_address_id": "addr_9",
  "loyalty": {"points_to_redeem": 500}
}
```

`idempotency_key` is required. Replaying the same key returns the original order
with `200` rather than creating a second one.

Responses: `201` created; `409` idempotency key reused with a different body;
`422` validation failure.

## `/v1/orders` (deprecated)

Same resource, older shape. Differences that break naive migration:

- `total` is a **decimal string** (`"129.95"`), not integer minor units.
- `tracking_number` is a **scalar** on the order; multi-shipment orders report
  only the first.
- `refunded` is a **boolean**; partial refunds are indistinguishable from full.
- No `loyalty` object.
- Offset pagination (`page`, `per_page`) instead of `next_cursor`.

## Migration guidance

1. Parse amounts as integers in minor units; drop all float handling. Multiply
   the old decimal by 100 only at the boundary, never in business logic.
2. Iterate `shipments` instead of reading `tracking_number`. Single-shipment
   orders return an array of one.
3. Replace `refunded == true` with `sum(refunds[].amount_minor) > 0`, and
   compare against `amount_total_minor` if you need "fully refunded".
4. Switch pagination to `next_cursor`; do not compute offsets. Cursors are
   opaque - do not parse them.
5. Handle the problem-details error shape: match on `type`, not on the message
   string.
6. Send `idempotency_key` on every write.

## Errors

```json
{"type": "validation_error", "title": "Invalid line item",
 "detail": "line_items[0].quantity must be >= 1", "status": 422}
```

`type` values are stable and safe to branch on: `validation_error`,
`idempotency_conflict`, `rate_limited`, `not_found`, `internal_error`.
""",
    },
    {
        "doc_id": 9625,
        "kind": "onboarding",
        "title": "Engineering onboarding: how we ship",
        "service": "",
        "author": "Priya Nair",
        "day": 290,
        "body": """# Engineering onboarding: how we ship

Read this first. It is the whole workflow end to end; the runbooks it points at
have the detail.

## The path

**ticket - PR with structured changes - CI - merge - staging - canary - promote -
verify - close**

### 1. Ticket

All work starts from a ticket. It carries the type (`bug`, `feature`,
`incident`, `security`, `postmortem`), the priority, and the owning service. If
you are doing work with no ticket, you are doing work nobody can find later.

### 2. PR with structured changes

A pull request is linked to its ticket and carries **structured changes**, not
just prose. Change types:

| Change type  | Use for                                        |
| ------------ | ---------------------------------------------- |
| `config`     | A config key and value in the service repo     |
| `module`     | Adding or removing a code module               |
| `dependency` | Upgrading a library (see "Security response")  |
| `endpoint`   | Adding, deprecating, or retiring an endpoint   |
| `flag`       | Defining a feature flag                        |
| `test_fix`   | Fixing (`fix`) or quarantining a flaky test    |

Structured changes are what make a PR mechanically checkable and what the deploy
tooling reads. One concern per PR.

### 3. CI

CI runs four stages in order: **build - unit - integration - regression**. A
failing stage stops the run. Some checks are hard gates: retiring an endpoint
that still serves traffic fails CI, and so does a secret detected in the diff.

### 4. Merge

Merging cuts a version for the service. The version is the unit that gets
deployed; nothing reaches an environment except as a version.

### 5. Staging

`deploy_service(service, "staging", version)`. **Every production deploy must
first succeed on staging with the same version** - see "Deployment policy". If
the change needs a schema migration, `apply_migration` runs against staging
*before* this deploy - see "Database migration policy".

### 6. Canary

For tier-1 services (`storefront-web`, `api-gateway`, `checkout`, `payments`),
the production deploy starts as a canary: `deploy_service` with
`canary_percent <= 25`. Tier-2 services (`catalog`, `notifications`, `search`)
deploy at 100%.

### 7. Promote

Run `assess_canary`. Only when it reports **healthy** do you `promote_canary`.
An unhealthy canary is rolled back, not promoted.

### 8. Verify

Read the metric you were trying to move. Confirm it is inside its SLO. If an
alert was firing, resolve it only after the metric has actually recovered.

### 9. Close

Close the ticket. If it was an incident, follow "Incident response" for the
alert, incident, `#incidents` update, status page, and - for sev1 - the
postmortem ticket.

## Things new engineers get wrong

- Enabling a feature flag before the guarded code is deployed. Deploy first, then
  enable, at no more than 10%.
- Skipping staging for "a one-line config change". There are no exceptions.
- Promoting a canary because it "looked fine" instead of assessing it.
- Resolving an alert before verifying recovery.
- Quarantining a flaky test and closing the ticket. It does not close the ticket.

## Where to look next

"Deployment policy", "Database migration policy", "Incident response",
"Feature flags", "Retry and timeout standard", "Service catalog and service
tiers".
""",
    },
    {
        "doc_id": 9626,
        "kind": "runbook",
        "title": "On-call and alert triage",
        "service": "",
        "author": "Alex Osei",
        "day": 257,
        "body": """# On-call and alert triage

One rotation per team, weekly, handing over on Monday. Current primaries:
platform - Priya Nair; commerce - Diego Ramos; growth - Mei Tanaka; SRE -
Alex Osei.

## Expectations

- Acknowledge a `critical` page within 5 minutes, `high` within 15, `medium`
  within 60 during working hours.
- You are expected to mitigate, not to fix. Handing a well-mitigated problem to
  the owning team in the morning is a success, not a failure.
- If you are stuck for 15 minutes on a customer-impacting issue, escalate. There
  is no prize for solo debugging during an outage.

## Triage order

1. **Is it customer-visible?** Money path or storefront - sev1 or sev2 and you
   follow "Incident response" immediately. Internal only - triage calmly.
2. **Did something change?** Check recent deploys, canary promotions, feature
   flag toggles, and config changes for the service and its dependencies, in that
   order. The overwhelming majority of incidents follow a change within the last
   hour.
3. **Is it this service or a dependency?** A spike in `checkout` errors with a
   simultaneous spike in `payments` latency is one incident, not two. Follow the
   dependency graph down before paging sideways.
4. **Mitigate** with the cheapest reversible lever: flag kill switch, then
   rollback, then config change.

## Reading an alert

An alert names the service, the metric, the observed value, and the SLO:

```
payments error_rate_pct 4.2 exceeds SLO 1.0
```

Three questions, in order: when did it start; what changed at that time; is the
value still moving. A metric that is still climbing needs mitigation now. A
metric that stepped once and is flat is usually a config or flag state, not a
degradation in progress.

## Severity mapping

| Condition                                       | Severity |
| ----------------------------------------------- | -------- |
| Orders cannot be placed or paid                  | sev1     |
| Storefront down or unusable                      | sev1     |
| Degraded but working, bounded revenue impact     | sev2     |
| Internal tooling, no customer impact             | sev3     |

## Handover

At the end of a shift, post in `#incidents`: what fired, what is still open,
what is deliberately being watched, and any change freeze in effect. An
unrecorded "I'm keeping an eye on it" dies with the shift.

## Alert hygiene

An alert that fires and is resolved with no action taken twice in a month is a
bad alert. Fix the threshold or delete it. Alert fatigue is how a real page gets
ignored. See "Observability, SLOs, and alerting" for how thresholds are set.
""",
    },
    {
        "doc_id": 9627,
        "kind": "policy",
        "title": "Observability, SLOs, and alerting",
        "service": "",
        "author": "Alex Osei",
        "day": 250,
        "body": """# Observability, SLOs, and alerting

Every service in the fleet publishes the same core metrics, has explicit SLOs,
and alerts only on SLO breaches. This document defines what "instrumented" means
before a service may take production traffic.

## Required metrics

Every service emits, at minimum:

- `error_rate_pct` - percentage of requests failing, per minute.
- `latency_p99_ms` - 99th percentile request latency.

Tier-1 services additionally emit saturation signals: connection pool
utilization, queue depth where applicable, and canary-vs-stable splits for both
core metrics so `assess_canary` has something to compare.

## Current SLOs

| Service        | Metric            | Threshold |
| -------------- | ----------------- | --------- |
| `payments`     | `error_rate_pct`  | 1.0       |
| `payments`     | `latency_p99_ms`  | 200       |
| `checkout`     | `error_rate_pct`  | 1.0       |
| `checkout`     | `latency_p99_ms`  | 400       |
| `api-gateway`  | `latency_p99_ms`  | 250       |
| `search`       | `latency_p99_ms`  | 300       |

An SLO is a promise about customer experience, not a description of current
behavior. We do not raise an SLO because we are breaching it; we fix the service
or we explicitly and publicly re-scope the promise with product sign-off.

## Alerting rules

1. **Alert on SLO breach, not on causes.** No alerts on CPU, memory, or pod
   restarts. Those are dashboard signals for a human already investigating.
2. **One alert per user-visible symptom.** Do not alert on a metric and its
   derivative.
3. **Every alert names the service, metric, observed value, and threshold**, so
   the responder can triage from the message alone.
4. Severity follows blast radius: money path breaks are `critical`, degradation
   is `high` or `medium`.

## Instrumentation before traffic

A service does not take production traffic until it emits both core metrics, has
at least one SLO, and has a runbook entry naming its owner. This is checked at
service registration, not left to good intentions.

## Dashboards

Each service has one dashboard with a fixed top row: the two core metrics with
their SLO lines drawn on them, deploy markers, and flag-change markers. Deploy
and flag markers on the same timeline are the fastest correlation tool we have -
most incidents are diagnosed by seeing a metric step exactly at a marker.

## Reviews

SLOs are reviewed quarterly. A service that has not breached its SLO in two
quarters is either genuinely reliable or has a threshold set too loosely;
we check which. Error-budget burn is reviewed monthly alongside the deployment
score described in the "Deployment policy".
""",
    },
    {
        "doc_id": 9628,
        "kind": "runbook",
        "title": "Rollback and recovery",
        "service": "",
        "author": "Priya Nair",
        "day": 273,
        "body": """# Rollback and recovery

How to get a service back to a known-good state. Read "Incident response" first
for where this sits in the ordering.

## When to roll back

Roll back when the regression correlates with a deploy. The signal is a metric
that steps at a deploy marker - not drifts, steps. You do not need root cause to
roll back; you need correlation. Root cause happens after customers are healthy.

Do **not** roll back when:

- The regression tracks a feature-flag rollout percent. Kill the flag instead;
  it is faster and more precise.
- The bad version has already been superseded by versions containing needed
  fixes. Roll forward with a hotfix instead.

## How

`rollback_deployment(service, environment)` returns the service to the
previously succeeded version in that environment.

**Rollback is exempt from staging-first.** You do not stage a rollback. This
exemption exists precisely so mitigation is never gated on a build pipeline. See
"Deployment policy".

If the bad release is still a canary, roll the canary back rather than promoting
it. Never "promote to fix" - promoting an unhealthy canary takes the blast
radius from 25% to 100%.

## The version trap

Rolling back moves to the previous *succeeded* version, and defects introduced in
version N are usually still present in N+1 and N+2 if those were cut on top of
N. A rollback to N+1 will not recover. Check what the last known-good version
actually is before you assume one step back is enough - for `api-gateway`, the
goroutine leak introduced in `v5.1.0` is present in every version cut on top of
it, and only a rollback to `v5.0.9` recovers latency.

## Schema

**Migrations are forward-only.** A code rollback does not roll back the schema.
This is only safe because migrations must satisfy the N-1 rule in the "Database
migration policy" - the schema must remain usable by the previous code version.
If a migration violated that rule, rolling back the code makes things worse; you
must roll forward with a corrective migration and a hotfix. This is exactly what
happened in "Postmortem: catalog migration 0043 forced a rollback".

## After the rollback

1. Verify the metric actually recovered - read it, do not assume.
2. Resolve the alert and the incident, post in `#incidents`, update the status
   page if it was customer-visible.
3. Mark the bad version so nobody redeploys it by reflex.
4. For sev1, file the postmortem ticket (type `postmortem`) naming the service
   and version.
5. Fix forward on a branch, with a regression test that would have caught it.

## Practice

Each team rolls back one service in staging every quarter, timed. If the drill
takes more than five minutes, the tooling or the documentation is the problem.
""",
    },
    {
        "doc_id": 9629,
        "kind": "design_doc",
        "title": "API gateway: routing, traffic weights, and rate limiting",
        "service": "api-gateway",
        "author": "Priya Nair",
        "day": 209,
        "body": """# API gateway: routing, traffic weights, and rate limiting

Service: `api-gateway` (tier 1, go, platform). The single public entry point for
partner and storefront traffic. SLO: `latency_p99_ms < 250`.

## Responsibilities

1. **Routing** - map a public path to an internal service.
2. **Authentication** - validate partner bearer tokens and storefront sessions;
   reject unauthenticated requests before they reach any backend.
3. **Rate limiting** - `rate_limit_rps` per partner token.
4. **Traffic weighting** - split traffic between endpoint versions during a
   migration.

Deliberately *not* responsibilities: business logic, response transformation
beyond version adaptation, and caching. The gateway must stay boring, because
everything is behind it.

## Endpoint registry

Endpoints live in the repo with a status: `active`, `deprecated`, or `retired`.
Status is a code change and ships through the normal PR-CI-deploy path. Current
public surface includes `/v1/orders`, `/v2/orders`, and `/v1/checkout`;
`/internal/debug` exists and should not - it is unauthenticated and is being
retired.

## Traffic weights

Weights are **production runtime state**, not repo config. Each endpoint carries
a weight from 0 to 100, and weights for a path family sum to 100. Changing a
weight takes effect immediately without a deploy - the same property that makes
feature flags useful mitigation tools.

Weight changes move in steps of **at most 50 percentage points**, and an
endpoint may only be retired at 0% - both enforced per the "API deprecation"
runbook, the second one as a hard CI gate.

## Rate limiting

`rate_limit_rps=500` per partner token by default, token-bucket with a 2x burst
allowance. Over-limit requests get `429` with `Retry-After`. Limits are per token
and not per IP; partners behind a NAT would otherwise share a bucket. Storefront
session traffic uses a separate, looser bucket keyed by session.

## Connection pooling

The gateway holds an upstream connection pool per backend service. This is the
most performance-sensitive component in the fleet and the source of our worst
recent incident: a connection-pool rewrite in `v5.1.0` leaked a goroutine per
request, and p99 went from ~120ms to ~1030ms - 4x the 250ms SLO. The defect is
present in `v5.1.0` and in anything cut on top of it; recovery required a
rollback to `v5.0.9`. See "Rollback and recovery".

Upstream calls follow the "Retry and timeout standard": three attempts, timeout
at or below 2000ms.

## Deployment

Tier 1: staging first, production canary at `canary_percent <= 25`,
`assess_canary`, then `promote_canary`. Because every request in the company
passes through this service, canary discipline here is not negotiable.

## Open questions

- Per-endpoint rate limits, not just per-token.
- Move token validation to an edge cache to shave ~8ms off p50.
""",
    },
    {
        "doc_id": 9630,
        "kind": "onboarding",
        "title": "Service catalog and service tiers",
        "service": "",
        "author": "Mei Tanaka",
        "day": 285,
        "body": """# Service catalog and service tiers

The full NovaCart fleet, who owns what, and what tier means operationally.

## The fleet

| Service          | Team      | Tier | Language   | Purpose                                      |
| ---------------- | --------- | ---- | ---------- | -------------------------------------------- |
| `storefront-web` | growth    | 1    | typescript | Customer-facing web storefront (Next.js)     |
| `api-gateway`    | platform  | 1    | go         | Public API edge: routing, auth, rate limits  |
| `checkout`       | commerce  | 1    | python     | Cart and checkout orchestration              |
| `payments`       | commerce  | 1    | python     | Payment capture, refunds, settlement         |
| `catalog`        | commerce  | 2    | python     | Product catalog and pricing                  |
| `notifications`  | platform  | 2    | python     | Email, SMS, and push delivery                |
| `search`         | growth    | 2    | python     | Product search and ranking                   |

On-call primaries: platform - Priya Nair; commerce - Diego Ramos; growth -
Mei Tanaka; SRE - Alex Osei.

## What tier means

**Tier 1** - a failure directly costs money or breaks the storefront.

- Production deploys must be canaries: `canary_percent <= 25`, then
  `assess_canary`, then `promote_canary`.
- Paged 24/7 on SLO breach.
- `db_pool_size >= 20`.
- Changes require a reviewer outside the authoring pair.

**Tier 2** - a failure degrades the experience but orders still complete.

- Production deploys go straight to 100% after a successful staging deploy.
- Paged during working hours; critical alerts page out of hours.
- `db_pool_size >= 20` still applies.

Both tiers are staging-first without exception. Tier is a property of blast
radius, not of team seniority or code quality.

## Dependency shape

```
storefront-web -> api-gateway -> checkout -> payments -> notifications
                              -> search   -> catalog
                                 catalog  <- checkout (pricing)
```

Read it as: a failure in `catalog` shows up as a `checkout` and `search`
problem, and a failure in `notifications` should show up nowhere at all, because
callers treat it as best-effort. When it does show up in `payments`, that is a
retry and timeout misconfiguration, not a `notifications` outage - see "Retry
and timeout standard".

## Environments

Two: `staging` and `production`. Staging carries a sampled copy of production
catalog data and synthetic orders. It is not a traffic-realistic environment,
which is exactly why tier-1 services canary in production - see "ADR-021:
Standardize on staged canary deploys".

## Channels

- `#incidents` - incident coordination and status updates.
- `#security` - advisories and audit notes, CVE ids referenced literally.
- `#eng` - everything else.

## Adding a service

Register it with a team, a tier, an owner, both core metrics, at least one SLO,
and a runbook entry before it takes traffic. See "Observability, SLOs, and
alerting".
""",
    },
]
