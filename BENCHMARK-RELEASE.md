# DevOpsBench-100 v3 release evidence

DevOpsBench-100 v3 is a 100-task benchmark of realistic software engineering,
SRE, incident, delivery, security, and cross-system work in the isolated
NovaCart sandbox. The employee prompts describe business outcomes and
conflicting context; they do not prescribe a tool sequence. Agents must resolve
task identity, distinguish current from retired authority, reconcile live
systems, choose among plausible branches, make bounded changes, leave a scoped
handoff, and reopen the persisted result.

This document reports local release evidence only. The v3 Harbor and Hugging
Face trees are prepared but are not described as published until registry
round-trip checks complete. No model score is a v3 leaderboard result until a
real agent finishes all 100 exact-release tasks with inspectable trajectories.

## Release shape

- 100 tasks across 19 operational families; 38 expert, 31 hard, 29 medium,
  and 2 easy.
- 97 typed MCP tools over 72 SQLite tables and 1,451 seeded world rows.
- 100 distinct raw reference tool-name sequences; maximum pair similarity
  `0.960000`.
- 100 distinct semantic action graphs; maximum pairwise Jaccard `0.100000`.
- 20–25 task-specific contextual reads before task work.
- 27–58 calls per reference trajectory (median 37; 3,716 total).
- 28 agent-visible evidence files per task: 2,800 globally unique files in
  CSV, EML, JSON, LOG, Markdown, PDF, SQL, TXT, XLSX, and YAML.
- 71–86 public, task-specific rubric criteria per task and three explicit
  options with exactly one evidence-supported branch.
- High-level prompts are 98–219 words, have no exact duplicates, and have a
  maximum pairwise token Jaccard of `0.709924`.

The asset room contains current and retired controls, tracker identities,
GitHub records, Slack conversations, PagerDuty change history, ownership and
release workbooks, live telemetry/runtime exports, security context, email,
and lineage records. Oracle state, reference plans, and verifier code are not
part of the agent-visible asset room.

## Causal verifier

The in-pack MCP runtime records every request as `(sequence, tool, canonical
arguments, success)`. The deterministic verifier combines the original
task-specific state assertions with exact argument-aware evidence checks:

- all task-scoped Jira, GitHub, Confluence, Slack, PagerDuty, owner-workbook,
  and category-specific live-state selectors must be present and successful;
- all causal evidence must precede the first source-system mutation;
- the original task-specific state transition and blast-radius invariants must
  hold;
- exactly one task-scoped completion handoff must be persisted after source
  work; and
- the exact case-room conversation must be reopened after the handoff.

The verifier grades causal dependencies, not one arbitrary total order among
independent evidence reads. It makes no network, model, clock, or random call.
Verification remains outside the agent-facing MCP surface and is protected by
a per-task capability token whose plaintext is not stored in the world image.

## Executed qualification

`python3 benchmark/devopsbench100/run_suite.py` executed 1,200 pristine-world
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

Every negative control applies to every task. There were zero false accepts.
The first `wrong_value` design was deliberately rejected during development
because changing an intermediate write could be superseded later. The released
control instead preserves the operational state while persisting a precise
false completion claim, which all 100 verifiers reject.

Measured reports are committed under
`benchmark/devopsbench100/reports/`. The sealed release contains 4,715 files;
manifest SHA-256:
`a7dafeae4b7e5408ce4d74fdd2b5a6be270b009be01f217c28a4d6fbeb707e62`.
Generated `__pycache__`, `.pyc`, and `.pyo` files are removed before sealing.

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
