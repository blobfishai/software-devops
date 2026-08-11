# Reproducing the AIOpsLab use case

[microsoft/AIOpsLab](https://github.com/microsoft/AIOpsLab) is the closest
neighbour to this project: an agent–cloud benchmark for AIOps on real
microservices. Its *use case* is different from Horizon-SWE, and that
difference is what makes it a useful test of whether this world generalises.

| | Horizon-SWE | AIOpsLab |
|---|---|---|
| Agent output | a change carried to production | **a submitted finding** |
| Task taxonomy | 7 engineering-workflow categories | detection → localization → analysis → mitigation |
| Grading | final world state | the answer, plus trace |
| Headline metrics | PF / PC | TTD / TTL / TTA / TTM, steps, success rate |

This world already covered **mitigation** — all 50 Horizon-SWE tasks are
mitigation under AIOpsLab's taxonomy. What it lacked was the diagnostic half:
tasks where the agent must *say what is wrong* rather than fix it.

## What was added

**`submit_diagnosis(...)`** — the analogue of AIOpsLab's `submit()` API. Rather
than free text, it takes a typed finding so grading stays executable:

```
submit_diagnosis(scope, fault_detected, service, fault_type, offending_key, evidence)
```

`fault_type` is drawn from a fixed taxonomy — `misconfig`, `missing_retry`,
`missing_timeout`, `resource_exhaustion`, `unbounded_prefetch`, `cache_disabled`,
`n_plus_one_query`, `cdn_bypass`, `bad_release`, `feature_flag_regression`,
`none`. The tool rejects internally inconsistent submissions (claiming a fault
while reporting `fault_type='none'`, or naming a service that does not exist).

Submissions land in a `diagnoses` table. **The answer key is never in the
database** — expected findings live only in the task specs, so no tool can read
them.

**12 tasks** over the faults already planted in the world:

- **detection (4)** — is this service violating an SLO? Includes a healthy
  service, so a false positive costs the reward exactly as a miss does.
- **localization (4)** — a given alarm is firing; which service is responsible?
- **analysis (4)** — full root cause: service + fault type + the exact
  offending config key, confirmed against the source and its commit history.

**Read-only enforcement.** AIOpsLab's diagnostic tasks are observational, so
every diagnostic verifier asserts the episode made no mutating call — no merge,
deploy, flag toggle, migration, rollback or alarm resolution. Investigating by
"fixing it and seeing what changed" fails.

**Metrics.** AIOpsLab reports time-to-detect / localize / analyze. The discrete
analogue here is the tool call at which the finding was submitted, reported per
category, alongside a step budget enforced as a quality check:

```
  AIOpsLab-style diagnostics: 12 tasks
    detection          time-to-detect    mean 5.0 tool calls (n=4)
    localization       time-to-localize  mean 6.0 tool calls (n=4)
    analysis           time-to-analyze   mean 8.0 tool calls (n=4)
```

**pass^k.** While adding a second benchmark's metrics, the harness also picked
up [τ-bench](https://github.com/sierra-research/tau-bench)'s reliability
metric — `pass^k = C(c, k) / C(n, k)` averaged over tasks, the probability that
*k* independent attempts all succeed:

```bash
python3 eval_model.py --model claude-sonnet-5 --category aiops_analysis --trials 4
```

## What did not carry over

Two things about AIOpsLab are deliberately *not* reproduced, and it is worth
being clear about them:

- **Live fault injection into real containers.** AIOpsLab injects faults into
  actual Kubernetes workloads (`inject_fault(microservices=[...],
  fault_type="misconfig")`). This world's faults are seeded deterministically
  instead. That trades AIOpsLab's fidelity for reproducibility and a verifier
  that cannot flake — the right trade for an eval you re-run per model, but it
  is a real difference, not an equivalence.
- **Wall-clock TTD/TTM.** Real elapsed time is meaningless in a simulator, so
  steps are used instead and labelled as such.

## Running it

```bash
python3 eval_model.py --policy oracle --category aiops_detection \
                     --category aiops_localization --category aiops_analysis --trials 3
```

Adversarial coverage lives in `tests/test_world.py`: a wrong service, a wrong
fault type, a false-positive detection, and a mutating investigation each lose
the reward.
