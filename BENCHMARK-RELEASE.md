# DevOpsBench-100 v3.2 release evidence

DevOpsBench-100 v3.2 is a 100-task benchmark of realistic software engineering,
SRE, incident, delivery, security, and cross-system work in the isolated
NovaCart sandbox. The employee prompts describe business outcomes and
conflicting context; they do not prescribe a tool sequence. Agents must resolve
task identity, distinguish current from retired authority, reconcile live
systems, derive a graded capacity-plan decision from evidence scattered across
providers, choose among costed alternatives, make bounded changes, leave a
content-graded handoff, and reopen the persisted result.

This document reports local release evidence only. The v3.2 Harbor and Hugging
Face trees are prepared but are not described as published until registry
round-trip checks complete. No model score is a v3.2 leaderboard result until a
real agent finishes all 100 exact-release tasks with inspectable trajectories.

## Release shape

- 100 tasks across 19 operational families; 38 expert, 31 hard, 29 medium,
  and 2 easy.
- 97 typed MCP tools over 72 SQLite tables and 1,451 seeded world rows.
- 100 distinct raw reference tool-name sequences; maximum pair similarity
  `0.956522`.
- 100 distinct semantic action graphs; maximum pairwise Jaccard `0.142857`.
- 24–30 task-specific contextual reads before task work; 18 are materially
  causal and individually contracted.
- 34–73 calls per reference trajectory (median 46; 4,563 total).
- 33 agent-visible evidence files per task: 3,300 globally unique files in
  CSV, EML, JSON, LOG, Markdown, PDF, SQL, TXT, XLSX, and YAML.
- 16 public semantic milestones per task totaling exactly 100 points, and
  three explicit costed options with exactly one evidence-supported branch.
- High-level prompts are 135–219 words, have no exact duplicates, and have a
  maximum pairwise token Jaccard of `0.606195`.

The asset room contains current and retired controls, tracker identities,
GitHub records, Slack conversations, PagerDuty change history, ownership and
release workbooks, live telemetry/runtime exports, security context, email,
lineage records, and the capacity-plan sources: the change-readiness standard,
the vendor capacity order, the change approval record, the Linear reservation
register, and the customer cutover notice. Oracle state, reference plans, and
verifier code are not part of the agent-visible asset room.

## Graded capacity-plan decision model (new in v3.2)

Every task carries a task-specific, fully graded decision chain in the domain's
own terms:

- **Requirement** — healthy replicas per zone (Confluence change-readiness
  standard) x production zones (PagerDuty scale record).
- **Coverage with exclusions** — the observed pool (PagerDuty) minus replicas
  reserved for another team's freeze (Linear register) yields the usable pool
  and the uncovered gap.
- **Third-party input** — the CloudCap vendor order (Jira `VEND-n`) supplies
  independently confirmed standard and expedited delivery dates and the
  expedite fee.
- **Internal constraint** — completions land in the published change windows on
  the current operating control page.
- **Three costed alternatives** — `standard_capacity_plan`,
  `expedite_capacity`, and `release_reserved_capacity`, each carrying an exact
  outcome date, an incremental cost in USD, an approval state, a control
  status, and a consequence; exactly one is recommended, one is
  `AVAILABLE_NOT_RECOMMENDED`, and one is `ADDITIONAL_APPROVAL_REQUIRED`.
- **Control-date comparison** — the recommended outcome is compared with the
  customer cutover published on the status page into a signed
  `outcome_vs_control_days` variance and an honest `ON_TIME`/`LATE` status
  (both statuses occur across the release, as do both authorised
  recommendations).
- **Approval record** — change approval `CHG-n` (Jira) is applied to the
  selected scope on every task; the reserved-release plan stays outside current
  authority.
- **Decision record** — the reference persists all 23 graded fields (every
  intermediate quantity, every option outcome, cost, approval reference,
  variance, and timing status) as the case reconciliation answer, after its
  evidence and before the handoff.
- **Content-graded handoff** — the case-room handoff must state the selected
  option, its outcome date, the approval reference, the timing status, and the
  binding vendor/window constraint; a completion marker alone no longer grades
  the handoff.

The published task JSON carries the machine-readable contract: a
`decision_model` (facts, per-field calculations, and the option table),
`expected.answer` + `expected.answer_checks`, an `answer_schema`,
`required_investigations` (18 contracted pre-mutation reads with the milestone
and verifier check that grade each), `post_write_verifications` (the
per-mutation provider readbacks exported from the sealed trace contract), and
`allowed_write_tables`.

## Causal verifier

The in-pack MCP runtime records every request as `(sequence, tool, canonical
arguments, success)`. The deterministic verifier combines the original
task-specific state assertions with exact argument-aware evidence checks:

- all task-scoped Jira, GitHub, Confluence, Slack, PagerDuty, owner-workbook,
  Linear, status-page, vendor-order, approval-record, readiness-standard, and
  category-specific live-state selectors must be present and successful;
- all causal evidence must precede the first source-system mutation, and every
  decision-record field is graded against the value derivable only from that
  evidence;
- the original task-specific state transition and blast-radius invariants must
  hold;
- persisted provider state must be read back after the final source mutation;
- the decision record must precede exactly one task-scoped completion handoff,
  which is graded on its stated option, outcome, approval, constraint, and
  timing; and
- the exact case-room conversation must be reopened after the handoff.

The verifier grades causal dependencies, not one arbitrary total order among
independent evidence reads. It makes no network, model, clock, or random call.
Verification remains outside the agent-facing MCP surface and is protected by
a per-task capability token whose plaintext is not stored in the world image.

## Executed qualification

`python3 benchmark/devopsbench100/run_suite.py` executed 1,400 pristine-world
episodes from the built task packs:

| Gate | Result |
|---|---:|
| Oracle reward 1.0 | 100 / 100 |
| Exact deterministic replay | 100 / 100 |
| Wrong verifier token rejected | 100 / 100 |
| `noop` rejected | 100 / 100 |
| `shortcut` rejected | 100 / 100 |
| `state_only` rejected | 100 / 100 |
| `incomplete_read` rejected | 100 / 100 |
| `write_before_read` rejected | 100 / 100 |
| `missing_readback` rejected | 100 / 100 |
| `unauthorized_write` rejected | 100 / 100 |
| `wrong_value` rejected | 100 / 100 |
| `wrong_decision` rejected | 100 / 100 |
| `wrong_evidence` rejected | 100 / 100 |
| `wrong_answer` rejected | 100 / 100 |
| `unapproved_option` rejected | 100 / 100 |

Every negative control applies to every task. There were zero false accepts.
The two v3.2 controls attack the decision model directly: `wrong_answer`
replays a perfect operational episode whose decision record ignores the
reservation (wrong usable pool and gap), and `unapproved_option` replays a
perfect episode whose record and handoff select the plan that needs approval
beyond the recorded change approval. All 100 verifiers reject both.

Measured reports are committed under `benchmark/devopsbench100/reports/`. The
sealed release file inventory and manifest SHA-256 are recorded in
`benchmark/devopsbench100/reports/release-manifest.json`. Generated
`__pycache__`, `.pyc`, and `.pyo` files are removed before sealing.

## Reproduce locally

```bash
PYTHONPATH=. python3 benchmark/devopsbench100/builder.py
PYTHONPATH=. python3 -m unittest benchmark.devopsbench100.tests.test_realism -v
PYTHONPATH=. python3 benchmark/devopsbench100/run_suite.py
PYTHONPATH=. python3 benchmark/devopsbench100/finalize.py
```

The build and qualification are local and deterministic. Registry publication,
published-tree digest checks, the full Dockerized Harbor oracle run, and the
100-task real-model leaderboard are separate release operations and must be
reported only from their resulting artifacts.
