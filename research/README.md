# Research-first world building

This directory is the evidence base for the world in `world/`. The rule is that
nothing enters the world because it sounds plausible — every task, tool and mock
row has to trace back to something in here.

## The workflow

```
00-QUESTIONS.md   the questions the world must answer before we build anything
repos/            25 cloned repos: domain evals, agent harnesses, MCP servers
notes/            question-driven findings, every claim carrying a citation
  evals/          benchmark task taxonomies, verification, metrics, failure modes
  mcp/            the real tool surfaces we mock against
  automation/     what harnesses define as correct agent workflow
  domain/         business value, stakeholders, input documents, chaos scenarios
SOURCES.md        consolidated links
01-THESIS.md      the synthesis: answers, framing, and what it implies for the world
artifacts/        proposed additions awaiting grounding judgement
```

## The two rules

**Rule 1 — everything mocked and runnable.** An eval, workflow or MCP surface we
researched has to be executable inside the world, not merely described.

**Rule 2 — grounded or it does not ship.** `grounding_judge.py` gates every new
task, tool or mock artifact. It works in two stages: a deterministic check that
the cited file exists and really contains the quoted text (this catches
fabricated citations without needing a model at all), then an LLM judgement on
whether the evidence actually *supports* the decision rather than merely sitting
near it. With no API key the second stage reports `unjudged` rather than
silently passing.

```bash
python3 research/grounding_judge.py --check research/artifacts/deepened_tasks.json
```

## The calibration loop

`calibrate.py` runs each task up to three times and sorts it:

| bucket | meaning | action |
|---|---|---|
| `TOO_EASY` | passed first attempt | deepen it (`deepen_tasks.py`) |
| `FLAKY` | passed some, failed others | **keep** — the capability boundary |
| `TOO_HARD` | failed all three | record the failure mode |
| `SUSPECT_ENV` | failed with world-side symptoms | fix the environment first |

That last bucket exists because a loop that cannot tell a broken world from a
hard task will happily report our own bugs as difficulty. Failed trials are
screened for markers like `unknown tool`, `bad arguments for`, `no such table`
and verifier crashes; a legitimate policy refusal is *not* such a marker and
counts as genuine difficulty.

```bash
python3 calibrate.py --policy naive          # dry-run the loop, no API spend
python3 calibrate.py --model claude-sonnet-5 --category flaky_test
python3 deepen_tasks.py --from research/calibration.json
```
