# Proving the world pushes a model to its boundary

This is the one claim in the project that is **not yet evidenced**, and this
document exists so that proving it is a single command rather than a project.

## Update: a frontier model now runs against this world

`cloud_backend.py` drives any OpenAI-compatible provider through native tool
calling, which is the harness a frontier model actually runs under and removes
the confound that dominated every earlier measurement:

```bash
export DEEPSEEK_API_KEY=...
python3 eval_model.py --policy deepseek --model deepseek-v4-pro
python3 calibrate.py  --policy deepseek --model deepseek-v4-pro --attempts 3
```

Results are recorded in the section below. Everything before that section was
measured with a local 8B model whose failures were mostly protocol, and is kept
because how those failures were diagnosed is the useful part.

## Earlier: partially proven, with a local model

`ANTHROPIC_API_KEY` is absent, but a locally cached model is not. `mlx_lm` with
`mlx-community/Qwen3-8B-4bit` runs on this machine with no credential, so the
calibration loop has now been driven by a real, uncontaminated model:

```bash
python3 calibrate.py --policy local --attempts 3        # no API key needed
```

The very first episode produced exactly the kind of evidence the oracle cannot.
Asked whether payments was violating an SLO, the model called `get_slo_status`,
read the answer correctly - 4.2% against a 1.0% threshold - and then **declared
itself done in prose instead of calling `submit_diagnosis`**. It solved the
analysis and failed the protocol, scoring 0.63 with `diagnosis_submitted` and
`detection_correct` both failing.

That is `completion_without_submit`, a failure mode the harness corpus names
explicitly (research/notes/automation/_WORKFLOW_PATTERNS.md). No scripted policy
would ever exhibit it, because a script always calls the tool it was written to
call. It took a real model to surface it.

**Caveat, recorded rather than hidden:** an 8B 4-bit model has no native
tool-calling API, so `local_backend.py` asks for tool calls as JSON. Some
failures are therefore attributable to that protocol rather than to the task -
which is precisely why `calibrate.py` types outcomes and separates `TASK_FAULT`
from `TOO_HARD`. A frontier model with native tool calling will fail differently,
and the numbers from this backend are a floor, not an estimate of what a strong
model scores.

### First sweep: 10 tasks x 3 attempts, Qwen3-8B-4bit — RETRACTED

| bucket | count |
|---|---|
| `TOO_HARD` | 8 |
| `BUDGET_CAPPED` | 2 |
| `FLAKY` | **0** |
| `TOO_EASY` | 0 |

**These numbers are void. They measured a defect in our harness, not the model.**

The sweep is kept here rather than deleted, because how it was caught is the
useful part. An empty FLAKY band was read at the time as "this model is below the
boundary everywhere." The failure signature said otherwise: the dominant failures
were `ticket_closed` (24), `closed_after_the_work` (18), `diagnosis_submitted`
(18) and `evidence_recorded` (18), while only 9 of 30 episodes got as far as
being wrong about the *content*. A model that reasons correctly and then never
records the answer is not failing the task; it is failing to reach it.

Following that signature found three stacked defects, each hidden by the one
above it:

1. **The tool menu showed the model 48 of 82 tools.** `_tool_digest` carried an
   arbitrary `limit=48`, which hid `submit_diagnosis`, `submit_answer` and the
   entire vendor layer — Jira, PagerDuty, Sentry, Prometheus, Confluence.
   **40 of 76 tasks required at least one tool the model was never shown.** The
   instruction told it to call `submit_diagnosis`; the menu never listed it.
2. **Argument errors named the mistake but not the remedy.** `bad arguments for
   submit_diagnosis: unexpected keyword 'finding'` gave a model no way to recover
   except guessing. It cycled `finding` → `result` → `diagnosis` until the turn
   budget ran out.
3. **Controlled vocabularies lived only in prose.** `fault_type` has eleven legal
   values, stated in the description and enforced at runtime, but absent from the
   JSON schema — so a native tool-calling API could not constrain against them
   either. This produced the worst behaviour of the three, below.

Fixed respectively by: showing all 82 tools with every argument name (~2.7K
tokens, comfortably inside an 8B context); returning `accepts` and `hint` with
every argument error, in `serve.py` so every backend benefits; and declaring
`enum` on all nine controlled vocabularies. Each is pinned by a test —
`test_the_model_can_see_every_tool_its_task_requires`,
`test_bad_argument_errors_say_what_is_accepted`,
`test_declared_enums_match_what_the_runtime_actually_accepts`.

### The failure worth reading twice

With the argument error made actionable, the model recovered the correct schema
on its very next call. Then it did this:

```
submit_diagnosis(fault_detected=true,  fault_type="SLO Breach", ...)  -> ok:false
submit_diagnosis(fault_detected=true,  fault_type="none", ...)        -> ok:false
submit_diagnosis(fault_detected=false, ...)                           -> ok:TRUE
```

It had diagnosed the breach correctly — payments at 4.2% against a 1.0%
threshold. Unable to satisfy a vocabulary it could not see, it **inverted its own
finding** to obtain an `ok: true`, and the episode recorded "no fault" on a
service that was plainly faulting.

That is a validation surface teaching a model to submit a wrong answer, and it
generalises well past this world: a tool that punishes malformed arguments
without naming the legal ones gives a model a cheaper path to acceptance through
changing the claim than through fixing the call. Declaring the vocabulary makes
the wrong value unrepresentable instead of merely punished.

No scripted policy could have surfaced any of this, because a script calls
exactly the tool it was written to call, with exactly the arguments it was
written with. It took a real model to find three harness bugs — and it took the
*failure signature*, not the pass rate, to know they were bugs at all.

### The loop caught a bug in itself

The first sweep flagged four tasks `TASK_FAULT` - our bug, not difficulty. They
were not. The model had invented a tool named `get_alerts` and passed a
`confidence` argument that does not exist, and the screen counted both as
environment failures.

That is precisely the mistake vivaria's rule exists to prevent: an agent may
never attribute its own mistake to the server. Fault attribution is now
caller-dependent - a malformed call from a *scripted* policy is our bug, because
a script calls exactly what it was written to call; the same call from a *model*
is the agent guessing. World-side faults (`no such table`, `Traceback`, a crashed
verifier) count against the world regardless. Pinned by a test.

Had this gone unnoticed we would have spent a day hunting environment bugs that
did not exist.

## Why the cloud measurement is still unproven

Every number reported so far measures the *environment*, not model difficulty:

| evidence | what it actually shows |
|---|---|
| oracle PF 100% (82/82) | the tasks are solvable and the verifiers accept a correct solution |
| random 0.0 | the verifiers reject noise |
| verify-accuracy 1.000 / 1.000 / 0.000 over 5 corruption families | the verifiers reject *near-misses*, not just noise |
| harbor self-test 82/82, free-reward 0 | the shipped package grades correctly outside this repository |
| policy-blind baseline: 0% on every change category | the deployment dimension is load-bearing |

None of that is a model score. Those begin in the next section: a frontier model
with native tool calling now runs against this world through the `deepseek` and
`openai` policies, which hand it all 84 tools as JSON Schema function definitions
and let it call them through the provider's own API. `ANTHROPIC_API_KEY` remains
unset here, so the Claude path is still untested; that is a missing credential
rather than a pending decision, and the harness for it is the same one.

### What each score is actually sensitive to

A global pass rate for a deviation policy is misleading, because most policies
are a no-op on most tasks — `shortcut` can only take a shortcut where the world
offers one. The load-bearing measurement is PF **restricted to the tasks each
policy actually perturbs**:

| deviation | tasks it perturbs | PF on that subset | reads as |
|---|---|---|---|
| `merged_only` — a merged pull request is the finish line | 45 | **0.0%** | caught every time |
| `shortcut` — quarantine the flaky test, blame the alarmed service | 14 | **0.0%** | caught every time |
| `naive` — no knowledge base, no staging, no canary, no comms | 77 | 13.0% | caught 67 of 77 |
| `no_verify` — ships the right change, never closes the loop | 181 | **84.0%** | caught 29 of 181 |

Re-measured at 181 tasks. `shortcut` doubled its reach, 7 to 14, as the flaky and
localization families grew; `naive` tightened from 16.7% to 13.0%, so the newer
change families are more policy-sensitive than the older ones rather than less.

The last row is the honest weak spot, and its cause is structural rather than a
bug. Under `no_verify` the world raises **174 quality failures against 15
correctness and 11 deployment** — every one of the 82 tasks fails `ticket_closed`
and `closed_after_the_work`. But PF is binary over correctness and deployment
only, exactly as the source spec defines it, so loop-closure discipline is worth
0.1 weight in PC and nothing at all in PF.

So: **PF measures whether the right change reached production. It does not
measure whether anyone was told.** PC measures the latter, weakly and by design.
That is inherited from the metric being reproduced, and it is stated here rather
than quietly repaired, because re-weighting would make these numbers
incomparable to the spec they mirror. A lab wanting closure discipline to be
load-bearing should raise the quality weight and re-run; the checks already exist
and already fire on all 181 tasks.

## The one command

```bash
export ANTHROPIC_API_KEY=...
python3 calibrate.py --model claude-sonnet-5 --attempts 3
```

Start smaller to sanity-check cost and wiring:

```bash
python3 eval_model.py --estimate                    # token projection
python3 calibrate.py --model <id> --limit 8         # ~$10, ~20 minutes
```

## What the loop returns, and why each bucket matters

Each task is run up to three times and attributed:

| bucket | meaning | what it tells you |
|---|---|---|
| `TOO_EASY` | passed first attempt | below the boundary — `deepen_tasks.py` proposes harder variants along span / ambiguity / horizon / reconcile |
| **`FLAKY`** | passed some attempts, failed others | **the boundary.** These traces show the same model succeeding and failing on identical input, which is the only direct evidence of where capability runs out |
| `TOO_HARD` | failed all three | above the boundary; the recorded failure mode says which dimension broke |
| `TASK_FAULT` | failed with world-side symptoms | **our bug, not difficulty** — fix before counting |
| `BUDGET_CAPPED` | exhausted the turn budget | cancelled, not failed |

The last two buckets are the point. The research corpus's collective blind spot
is that seven benchmarks collect a rich failure vocabulary and average it away at
scoring time; only METR/vivaria types `ErrorSource` and derives run status from
it in SQL so the two cannot drift. Environment failure is first-order in this
domain — AlgoTune's own *oracle* passes only ~85%, and three SWE-bench Verified
tasks fail with the oracle agent — so a loop that cannot separate a broken world
from a hard task will report our bugs as difficulty.

`eval_model.py` carries the same attribution: episodes are typed `resolved`,
`agent`, `harness`, `environment`, `capped`, and harness/environment failures are
**excluded** from the pass rate rather than averaged into it.

<!-- results:start -->

## Measured: deepseek-v4-pro, native tool calling

_Generated by `write_results.py` from the run report; do not edit by hand._

| | |
|---|---|
| world | `env_software_devops_75f8f41d` |
| episodes | 83 (83 attributable, 0 excluded as harness/environment) |
| **Horizon-SWE-PF** | **60.2%** (50/83) |
| **Horizon-SWE-PC** | **89.6** |

11 episode(s) exhausted the 30-turn budget and are counted as failures. Excluding them the pass rate is 69.4% (50/72) — the difference is the part of the gap that is our turn limit rather than the model's ceiling.

### Where it breaks

Correctness is perfect in **55 of 83** attributable episodes (66%), while deployment is imperfect in **12**. The model largely works out what to change and then does not follow the procedure for changing it — and that procedure is not in the prompt, it is in the knowledge base.

Every episode was attributable. **No episode failed with a world-side symptom** — no missing table, no traceback, no crashed verifier, no invented tool, no provider outage — so none of the failures below are ours.

| failed check | episodes |
|---|---|
| `quality/closed_after_the_work` | 24 |
| `quality/ticket_closed` | 23 |
| `deployment/ack_before_resolve` | 7 |
| `correctness/ci_all_stages_green` | 7 |
| `quality/pr_linked_to_ticket` | 7 |
| `correctness/offending_key_correct` | 7 |
| `quality/jira_twin_resolved` | 6 |
| `correctness/service_localized` | 6 |
| `correctness/fault_type_correct` | 6 |
| `correctness/config_deployed_to_production` | 5 |
| `deployment/canary_then_promote` | 4 |
| `correctness/legacy_retired` | 3 |

### PF by category

The boundary is where this crosses: the families a model clears and the families it cannot are different questions, and a single average hides both.

| category | PF | |
|---|---|---|
| flaky_test | 100% | 6/6 |
| aiops_detection | 100% | 5/5 |
| feature_flag | 86% | 6/7 |
| security_incident | 86% | 6/7 |
| multi_service_rollout | 86% | 6/7 |
| judgement | 75% | 3/4 |
| aiops_localization | 67% | 4/6 |
| api_migration | 57% | 4/7 |
| latency_optimization | 38% | 3/8 |
| aiops_analysis | 30% | 3/10 |
| reconciliation | 29% | 2/7 |
| error_rate_reduction | 25% | 2/8 |
| human_gated | 0% | 0/1 |

### PF by difficulty

| difficulty | PF | |
|---|---|---|
| easy | 100% | 2/2 |
| medium | 76% | 22/29 |
| hard | 58% | 15/26 |
| expert | 42% | 11/26 |

PF falls monotonically with the difficulty label.

### Effort

Mean 35.9 tool calls per episode: 30.8 when it passed, 43.5 when it failed.


### Reliability: the FLAKY band

Boundary candidates re-run 3 times each against deepseek-v4-pro, with `--all-attempts` so a first-try pass does not end the probe.

| task | bucket | passes | mean PC |
|---|---|---|---|
| `tsk_instant_refunds_killswitch` | **FLAKY** | 2/3 | 0.95 |
| `tsk_search_cache` | **FLAKY** | 2/3 | 0.94 |
| `tsk_rca_inventory_unbound_storage` | **FLAKY** | 1/3 | 0.90 |
| `tsk_localize_checkout_latency` | **TOO_HARD** | 0/3 | 0.85 |
| `tsk_payments_retry` | **TOO_HARD** | 0/3 | 0.87 |
| `tsk_rcn_customer_facing_incidents` | **TOO_HARD** | 0/3 | 0.86 |

| k | pass^k |
|---|---|
| 1 | 0.278 |
| 2 | 0.111 |
| 3 | 0.000 |

A 28% single-attempt rate is **0% when consistency is required**: not one boundary task passed all 3 attempts. That is the whole argument for the metric — a pass rate averages away the difference between a model that can do something and a model that can do it reliably, and on the tasks that sit at the edge those are not the same claim.


**3 of 6 candidates are FLAKY** — the same model, the same task, the same prompt, passing on some attempts and failing on others. That band is the point: a task nobody can pass measures nothing, a task everybody passes measures nothing, and a task that goes both ways is measuring exactly where capability runs out.


### The guidance ladder

Every task carries two prompts: `instruction` states the outcome, `instruction_guided` also states the procedure. Same tasks, same model, measured both ways across aiops_analysis.

| prompt | PF | PC |
|---|---|---|
| outcome only | 30.0% (3/10) | 75.7 |
| procedure stated | 50.0% (5/10) | 82.0 |
| **delta** | **+20.0 points** | |

2 task(s) changed side: `tsk_rca_payments_retry`, `tsk_rca_inventory_unbound_storage`.

On 10 tasks a +20.0-point move is 2 task(s) flipping, which is suggestive rather than conclusive, and `tsk_rca_inventory_unbound_storage` is independently known to be FLAKY, so at least one flip may be variance rather than the prompt.

Read plainly: stating the procedure helps, so procedural knowledge is part of what these tasks demand — but it does not carry the model over the line, so the rest is judgement about evidence rather than recall of steps.

<!-- results:end -->

## The composition wave sits above this model, not at it

The attribution family - three concurrent symptoms, each needing its own cause -
was generated from the world's real faults after a frontier model misattributed
one of them. Measured against the same model:

| | |
|---|---|
| PF | **0%** (0/13) |
| PC | 66.0 |
| mean tool calls | 56 |

Zero is a ceiling marker rather than a boundary. A task nobody passes does not
discriminate between models, and by the calibration loop's own rule this family
is TOO_HARD and should be deepened downward, not upward.

What makes it worth keeping is that the failure is concentrated rather than
diffuse, and reproducible across independently generated tasks:

| failed check | of 13 |
|---|---|
| `attributed_media_upload_stalls` | 11 |
| `key_for_media_upload_stalls` | 11 |
| `causes_are_distinct` | 5 |

Eleven of thirteen times the model fails the same sub-question - the one whose
answer is a disk-pressured node rather than anything in the service's own code -
and five times it explicitly attributes several symptoms to a single cause, which
is the "one incident, one rollback" fallacy the task was built to catch. The
evidence chain for the missed one is two calls long and was verified reachable
before the family shipped: pods, then an Evicted event reading "the node was low
on resource: ephemeral-storage", then a node at DiskPressure 97%.

So the honest reading is narrow and useful: this model does not look one layer
below the service it was asked about, and giving it three services to consider at
once does not change that. PC 66.0 shows it is not failing at random - it gets
most of each task right and misses the same piece every time.

## What would count as proof

1. **A non-empty `FLAKY` band.** If a model passes some attempts and fails
   others on the same task, the world is measuring at the capability edge rather
   than above or below it. That band is the deliverable.
2. **A difficulty ladder.** PF should fall monotonically across the guidance
   axis (`--guidance guided` vs `standard`) and across the deepening axes. If
   removing the procedure from the prompt does not move the score, the world is
   testing instruction-following rather than judgement.
3. **`pass^k` decay.** τ-bench's reliability metric (`--trials k`) should decay
   with k. A model that is 60% at pass^1 and 20% at pass^4 is unreliable in a way
   a single pass rate hides entirely.
4. **`TASK_FAULT` at zero.** Any non-zero count invalidates the difficulty
   numbers until fixed.

## The honest prior

The blog this world is modelled on reports ~25.5% PF for the strongest model on
its own 50 tasks. This world is **not calibrated to reproduce that number**, and
a resemblance would be coincidence rather than validation — a point worth holding
onto when the first results arrive. The `naive` policy — technically correct
fixes with every documented procedure stripped out — scores 16.7% across the 54 tasks it
actually changes, bracketing that figure for
entirely unrelated reasons.

## A fourth thing that would count as proof, learned the hard way

5. **The failure signature has to be read before the pass rate is believed.** The
   first sweep's `FLAKY 0` was reported as a property of the model. It was three
   harness bugs. What gave them away was not the score but the *shape* of the
   failures — a model that reasons correctly and then never records the answer is
   not failing the task, it is failing to reach it. Any bucket distribution whose
   failures cluster on the submission handshake rather than on task content
   should be treated as a harness result until proven otherwise.
