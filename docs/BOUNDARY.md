# Proving the world pushes a model to its boundary

This is the one claim in the project that is **not yet evidenced**, and this
document exists so that proving it is a single command rather than a project.

## Update: it is now partially proven, with a local model

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

### First sweep: 10 tasks x 3 attempts, Qwen3-8B-4bit

| bucket | count |
|---|---|
| `TOO_HARD` | 8 |
| `BUDGET_CAPPED` | 2 |
| `FLAKY` | **0** |
| `TOO_EASY` | 0 |

An empty FLAKY band means this model is **below** the boundary everywhere, not at
it. The world does not measure this model - it simply exceeds it. That is a real
result and it is the opposite of the one we want: proof of a boundary needs a
model that sometimes succeeds.

The failure is concentrated and diagnostic. Across 30 episodes the dominant
failures were `ticket_closed` (24), `closed_after_the_work` (18),
`diagnosis_submitted` (18) and `evidence_recorded` (18) - the model reasons its
way to the right answer and then never calls the tool that records it. Only 9 of
30 got as far as being wrong about the *content* (`detection_correct`).

So this sweep measures a protocol barrier, not task difficulty. Under a JSON
tool-call protocol an 8B model cannot reliably complete a submission handshake,
and that saturates long before the reasoning is tested. A frontier model with
native tool calling will clear that barrier and the same tasks will measure
something quite different.

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
| oracle 1.0 (1120/1120 tool calls) | the tasks are solvable and the verifiers accept a correct solution |
| random 0.0 | the verifiers reject noise |
| verify-accuracy 1.000 / 1.000 / 0.000 over 5 corruption families | the verifiers reject *near-misses*, not just noise |
| policy-blind baseline: 0% on every change category | the deployment dimension is load-bearing |

None of that is a model score. The calibration loop has never seen a model,
because `ANTHROPIC_API_KEY` is not set in this environment. That is a missing
credential, not a pending decision.

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
onto when the first results arrive. The scripted policy-blind baseline scores PF
29% here, which is close to that figure for entirely unrelated reasons.
