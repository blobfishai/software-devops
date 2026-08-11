# Cross-cutting analysis — the eval-benchmark corpus

**Corpus root:** `/Users/samuelchien/dev/software-devops/research/repos/evals/`

**Per-repo notes** — every citation below is traceable through these:

| Note | Repo root under `research/repos/evals/` |
|---|---|
| `princeton-nlp__SWE-bench.md` | `princeton-nlp__SWE-bench/` |
| `SWE-agent__SWE-agent.md` | `SWE-agent__SWE-agent/` |
| `microsoft__AIOpsLab.md` | `microsoft__AIOpsLab/` |
| `sierra-research__tau-bench.md` | `sierra-research__tau-bench/` |
| `TheAgentCompany__TheAgentCompany.md` | `TheAgentCompany__TheAgentCompany/` |
| `laude-institute__terminal-bench.md` | `laude-institute__terminal-bench/` |
| `commit-0__commit0.md` | `commit-0__commit0/` |
| `openai__SWELancer-Benchmark.md` | `openai__SWELancer-Benchmark/` (empty stub — evidence from the terminal-bench adapter) |
| `METR__vivaria.md` | `METR__vivaria/` |

This document answers three questions from `00-QUESTIONS.md`:

- **C4** — which task types appear in more than one benchmark (the domain's consensus tasks)
- **G1** — which verification mechanisms are most common
- **G5** — what the corpus collectively says about separating environment failure from model failure

…plus the cross-cutting material on reward hacking (G4), flakiness (G2), metrics (G3/H1), context
(D1/D3) and gaps (C5) that falls out of answering them.

**A structural note that shapes everything below:** the nine repos are not nine benchmarks. They are
**seven benchmarks** (SWE-bench, AIOpsLab, tau-bench, TheAgentCompany, terminal-bench, commit0,
SWE-Lancer) and **two pieces of infrastructure** (SWE-agent, a scaffold; vivaria, a platform). The
sharpest finding in this document — §3 — is that the two pieces of infrastructure solve a problem all
seven benchmarks get wrong.

---

## 0. The corpus at a glance

| Repo | What a task is | N tasks | Verification | Done-ness kind | LLM judge in score? |
|---|---|---:|---|---|---|
| **SWE-bench** | issue text + repo snapshot → one diff | 2 294 full / 500 Verified / 300 Lite / 300 Multilingual / 102 MM-dev | run repo's own tests in Docker; F2P + P2P | state-based | **no** |
| **SWE-agent** | scaffold that *produces* the diff | n/a — runs others' datasets | delegated to SWE-bench (`sb-cli`) | state-based | self-review only |
| **AIOpsLab** | live K8s microservices + injected fault | **89** (34 detect / 28 localize / 13 analyse / 14 mitigate) | string/set/dict match on the submitted answer; `kubectl` state check for mitigation | answer-based ×3, state-based ×1 | optional, **off by default** |
| **tau-bench** | multi-turn chat with a simulated customer + tool calls on a mutable DB | **165** (115 retail + 50 airline) | SHA-256 of the whole DB vs a replay of gold actions, **and** substring match on required outputs | state-based **+** answer-based | no (judge is post-hoc only) |
| **TheAgentCompany** | multi-step office task across GitLab / ownCloud / RocketChat / Plane | **175** | weighted checkpoints, graded by Python probes against live service APIs | state-based + LLM-judged | **yes**, 53/175 tasks |
| **terminal-bench** | prose instruction + Docker image + hidden pytest suite | **241** (leaderboard set `terminal-bench-core==0.1.1` = **80**) | pytest run in a fresh **root** tmux session after the agent stops | state-based | no (LLM judges *task quality*, not runs) |
| **commit0** | a whole library with every function body deleted | **56** repos (`all`), **16** (`lite`); ~140 926 tests | pytest + JSON report, per-test-ID lookup; plus ruff/pyright gate | state-based, **graded** | **no** |
| **SWE-Lancer** | real Upwork bug in Expensify, or pick the best proposal | **463** (198 IC + 265 manager) | Playwright E2E via Ansible (best-of-3); integer match for manager | state-based ×1, answer-based ×1 | **no** |
| **vivaria** | platform implementing the METR Task Standard | **2** (`examples/count_odds/`); real tasks live in the private `METR/mp4-tasks` | `TaskFamily.score()` + intermediate scoring + **human scoring** | task-defined | task-defined |

### 0.1 Counts were verified independently, not taken from prose

```
$ ls -d TheAgentCompany__TheAgentCompany/workspaces/tasks/*/ | wc -l          → 175
$ ls -d laude-institute__terminal-bench/original-tasks/*/ | wc -l             → 241
$ grep -cE '^\s*"[a-zA-Z0-9_-]+":' microsoft__AIOpsLab/aiopslab/orchestrator/problems/registry.py → 89
$ grep -c 'Task(' sierra-research__tau-bench/tau_bench/envs/retail/tasks_test.py   → 115
$ grep -c 'Task(' sierra-research__tau-bench/tau_bench/envs/airline/tasks_test.py  →  50
$ python3 -c "from commit0.harness.constants import SPLIT_ALL, SPLIT_LITE; print(len(SPLIT_ALL), len(SPLIT_LITE))" → 56 16
```

**Four repos' own prose disagrees with their code.** Do not quote a README from this corpus without
checking:

| Repo | Prose says | Code says |
|---|---|---|
| commit0 | 57 libraries (`README.md:22`) | **56** (`commit0/harness/constants.py:105-162`) |
| AIOpsLab | "60+" problems (`CLAUDE.md`) | **89** (`registry.py:36-220`) |
| SWE-bench | Lite = 534 (`docs/guides/datasets.md:11`) | **300** (`swebench/collect/make_lite/make_lite.py:81`, `docs/faq.md:13`) |
| terminal-bench | *"tasks are in `tasks/`"* (`CLAUDE.md`) | they are in `original-tasks/` |

Stale documentation is a first-class hazard (question D2) and the corpus demonstrates it on itself.

---

## 1. C4 — Consensus task types: what appears in more than one benchmark

### 1.1 The one universal task: *repair a real repo, verified by its own test suite*

**Eight of nine repos** contain this task. It is the only shape with a clear majority.

| Repo | Instantiation |
|---|---|
| SWE-bench | the canonical form: `problem_statement` + `base_commit` → diff, graded by `FAIL_TO_PASS` / `PASS_TO_PASS` (`swebench/harness/grading.py:195-212`) |
| SWE-agent | the scaffold that produces that diff; also GitHub issue URLs and local repos |
| SWE-Lancer (IC) | Expensify bug, graded by Playwright E2E rather than unit tests |
| commit0 | inverted: *all* bodies deleted, rebuild the library. Also ships **500 SWE-bench instances** (`commit0/data/test_ids/*__*.bz2`, 1 000 files = 500 × {f2p, p2p}) and a `SWEBenchSpec` (`commit0/harness/spec.py:213`) |
| terminal-bench | 3 native SWE-bench port tasks plus **13 benchmark adapters** |
| TheAgentCompany | 69 `sde-` tasks against a live GitLab |
| vivaria | supported via the Task Standard — `TaskFamily.score()` runs whatever the family defines |
| AIOpsLab | *(not code repair — the one clear exception)* |

**terminal-bench and commit0 are the strongest evidence**, because they do not merely share the shape
— they *absorb* other benchmarks. terminal-bench's `registry.json` holds 19 datasets, of which
`swebench-verified`, `swesmith`, `sweperf`, `deveval`, `evoeval-difficult`, `quixbugs`,
`aider-polyglot`, `swe-lancer-diamond{,-ic,-manager}`, `usaco`, `algotune`, `mlebench-lite` and
`appworld-{dev,test_normal,test_challenge}` are ports of external benchmarks. commit0's harness
dispatches on dataset name to `Commit0Spec` / `SWEBenchSpec` / `SimpleSpec`, the last covering
HumanEval, MBPP, BigCodeBench and CodeContests (`commit0/harness/run_pytest_ids.py:64-77`). Two
independent harnesses, each expressing four-to-nineteen benchmarks with the same machinery. That is
the domain declaring its own substrate.

**The verification substrate is even more universal than the task**: `pytest` (or a language's native
runner) inside a **Docker container** is how SWE-bench, commit0, terminal-bench, SWE-Lancer and
TheAgentCompany all decide done-ness. tau-bench and AIOpsLab are the only two that never run tests,
and both replace them with a *state check* (DB hash / `kubectl` inspection) rather than with a judge.

### 1.2 The second cluster: *localize a fault in a running distributed system*

This is the domain's genuine second task family, and it is **much thinner than the first**.

- **AIOpsLab** makes it the whole benchmark: `LocalizationTask` (28 problems) asks for the faulty
  service given a live cluster (`aiopslab/orchestrator/tasks/localization.py:18`), scored by
  exact/subset match with `100/N` partial credit
  (`.../problems/k8s_target_port_misconfig/target_port.py:104-112`).
- **TheAgentCompany** has isolated instances among its `sde-` tasks, but no task family for it.
- **Nothing else in the corpus does incident localization at all.**

This is the clearest *gap* the corpus reveals (§8).

### 1.3 The third cluster: *operate a stateful third-party system through its API/UI*

Three repos, three completely different framings — which is itself the finding.

| Repo | System | Grading |
|---|---|---|
| tau-bench | in-memory JSON DB for a retail/airline back office, 16 + 14 tools | whole-DB hash vs gold replay (`tau_bench/envs/base.py:124-164`) |
| TheAgentCompany | four *real* self-hosted services — GitLab :8929, ownCloud :8092, Plane :8091, RocketChat :3000 (`servers/README.md:35-54`) | Python probes hitting each service's API |
| AIOpsLab | a real Kubernetes cluster | `kubectl` state assertions (mitigation only) |

The consensus is on the **shape** — *the agent mutates external state and the grader reads that state
back* — not the implementation. tau-bench proves you can do it with a mock; TheAgentCompany proves the
real thing buys you a documented, first-class instability problem (`docs/SETUP.md:57-59`;
`evaluation/browsing.py:210-211`: `# devnote: plane reset is not stable, and sometimes it fails to launch`).

### 1.4 The fourth: *make a judgement call — no artefact produced*

Two repos, and they independently discovered the same surprising fact.

- **SWE-Lancer manager** — 265 of 463 tasks (57 %): read the issue and N human proposals, write
  `{"selected_proposal_id": <int>}` to a fixed path. Graded by integer equality
  (`adapters/swelancer/template/manager/run-tests.sh:8`).
- **AIOpsLab detection + analysis** — 47 of 89 problems: answer `"Yes"`/`"No"`, or a
  `{system_level, fault_type}` dict.

**The surprising fact:** SWE-Lancer reports **47.2 % on manager vs 51.5 % on IC SWE**
(`adapters/swelancer/README.md:97-98`). Picking the right fix is essentially as hard as implementing
it — while being deterministic, flake-free and nearly free to grade. Any benchmark author reading this
corpus should note that judgement tasks are the best cost-to-difficulty ratio available anywhere in it.

### 1.5 The fifth: *long-horizon multi-service workflow*

Only **TheAgentCompany** does this end-to-end (read a doc → work in GitLab → ask a colleague on chat →
upload to ownCloud → update Plane), with 79/175 tasks touching RocketChat, 71 GitLab, 70 ownCloud, 17
Plane. SWE-Lancer IC is long *in time* (3 000 s budget; >10 min per verification cycle) but
single-service. AIOpsLab is multi-service but short (`max_steps=30`).

### 1.6 Task types that appear in exactly ONE repo

The corpus's genuinely novel contributions:

| Unique task type | Repo |
|---|---|
| Rebuild a whole library from docstrings + a PDF spec | commit0 |
| Choose among human-written proposals (management) | SWE-Lancer |
| Detect / analyse / mitigate an injected fault in live K8s | AIOpsLab |
| Multi-turn conversation with a simulated *customer* under a written policy | tau-bench |
| Office work across four real SaaS clones with NPC colleagues | TheAgentCompany |
| Arbitrary terminal tasks (games, forensics, compilers, ML, pwn) | terminal-bench |
| Human-scored, rubric-graded tasks with an explicit "human must score" state | vivaria |

**Correction worth recording: CTF / offensive security is *not* in this corpus.** SWE-agent's EnIGMA
mode is v0.7-only (`README.md:65-67`: *"Please use SWE-agent 0.7 while we update EnIGMA for 1.0"*;
`docs/background/index.md:38-39`). Only residue survives in the 1.x checkout — a `ctf` pytest marker
(`pyproject.toml:104`), six per-category demonstrations under `trajectories/demonstrations/ctf/`, and
a `radare2`/`r2` carve-out in the blocklist. terminal-bench's `cybench` adapter is the corpus's only
live security-task surface.

### 1.7 The C4 answer, in one sentence

> The domain agrees on exactly one task — **fix a real repository and prove it with its own tests in a
> container** — and on one weaker second cluster — **operate a stateful external system and check the
> state afterwards**. Everything else is a single repo's private invention.

---

## 2. G1 — Verification mechanisms, ranked by frequency

Counting each repo once per mechanism used in its **headline score**:

| Rank | Mechanism | Repos | Count |
|---|---|---|---:|
| 1 | **Test execution in a container** | SWE-bench, commit0, terminal-bench, SWE-Lancer (IC), TheAgentCompany (partly), SWE-agent (delegated) | **6** |
| 2 | **State inspection / state diff** | tau-bench (DB hash), AIOpsLab (kubectl), TheAgentCompany (service APIs), vivaria (task-defined) | **4** |
| 3 | **Exact answer match** (string / int / set / dict) | AIOpsLab (3 of 4 task types), SWE-Lancer (manager), tau-bench (`outputs`) | **3** |
| 4 | **LLM judge inside the score** | TheAgentCompany (53/175 tasks), AIOpsLab (optional, default off) | **2** |
| 5 | **Human scoring** | vivaria | **1** |

### 2.1 Test execution is the default, and it is remarkably uniform

The shape is identical everywhere: `git reset` → apply the agent's diff → run a fixed command → parse
stdout → compare against a stored set of test IDs.

- SWE-bench compares parsed statuses against `FAIL_TO_PASS` and `PASS_TO_PASS`; resolution requires
  **both** = 1.0 (`swebench/harness/grading.py:195-212`).
- commit0 uses the identical vocabulary (`FAIL_TO_PASS`, `PASS_TO_PASS`, `FAIL_TO_FAIL`,
  `PASS_TO_FAIL` at `commit0/harness/constants.py:61-64`) and an identical
  `ResolvedStatus{NO,PARTIAL,FULL}` enum at `:282-285` — commit0 is visibly a fork of SWE-bench's
  grading vocabulary.
- terminal-bench: `_is_resolved` = `all(status == PASSED)` (`terminal_bench/harness/harness.py:536-542`).
- SWE-Lancer: `pytest_exit == 0` on any of 3 runs (`adapters/swelancer/template/swe/run-tests.sh:81-84`).

**Log parsing is the shared fragility.** SWE-bench ships 57 hand-written regex log parsers and its own
code says so — `# TODO: This is very brittle, we should do better`, about a Django logger bug
(`swebench/harness/log_parsers/`).

### 2.2 The three notions of "done"

| Kind | Definition | Who |
|---|---|---|
| **State-based** | the world is inspected after the episode | SWE-bench, commit0, terminal-bench, SWE-Lancer IC, tau-bench (DB), AIOpsLab mitigation, TheAgentCompany |
| **Answer-based** | a submitted value is compared to a key | AIOpsLab detection/localization/analysis, SWE-Lancer manager, tau-bench `outputs` |
| **LLM-judged** | a model decides | TheAgentCompany (53 tasks), AIOpsLab (opt-in) |
| **Human-judged** | a person scores against a rubric | vivaria |

**Binary vs graded** splits the corpus almost evenly, and it matters:

- **Binary:** SWE-bench (`PARTIAL` is computed at `grading.py:195-212` then **discarded** at
  `:265-266`), terminal-bench (`all(...)`), tau-bench (reward ∈ {0.0, 1.0}), SWE-Lancer.
- **Graded:** commit0 (`passed = (status["passed"] + status["xfail"]) / sum(status.values())`,
  `commit0/harness/evaluate.py:139`), AIOpsLab localization (`100/N` partial credit), TheAgentCompany
  (checkpoint points), vivaria (`score` is a float).

TheAgentCompany's formula is the most considered treatment of partial credit in the corpus
(`evaluation/summarise_results.py:162-178`, verified verbatim against the repo):

```python
def calculate_score(total: int, result: int) -> float:
    """
    Formula: score = (result / total) * 0.5 + (result // total) * 0.5
    - (result / total) * 0.5: This is the completion ratio, scaled down to a 0-0.5 range.
    - (result // total) * 0.5: This is a binary score indicating whether the task was completed or not.
    """
    return (result / total * 0.5) + (result // total * 0.5)
```

Half partial credit, half all-or-nothing. 3-of-4 checkpoints scores 0.375; 4-of-4 scores 1.0. It
rewards progress without letting "almost done" look like "done" — the single most reusable idea in the
corpus for anyone designing a graded metric. Underneath it, `Checkpoint(total, result)` dataclasses
carry per-checkpoint weights (`workspaces/base_image/scoring.py:1-62`); measured across all 175 tasks
the budget is **661 points, median 3 checkpoints per task, max 8**.

### 2.3 Where LLM judges actually appear

They are **rarer in scoring than in tooling**:

| Use | Repos |
|---|---|
| In the score | TheAgentCompany (53/175 evaluators call `evaluate_with_llm` / `evaluate_chat_history_with_llm`); AIOpsLab (`qualitative_eval: false` by default, `aiopslab/config.yml.example:11-12`) |
| Post-hoc failure analysis, **not** scoring | tau-bench `auto_error_identification.py` |
| Grading *task quality* at authoring time | terminal-bench `tb tasks check` — 11 criteria, default model `openai/gpt-5` |
| Agent self-review before submit | SWE-agent (`review_on_submit_m`, `ScoreRetryLoop`, `ChooserRetryLoop`) |

Both in-score judges extract a boolean or score from free text with a **substring or regex check** —
the weak link in each:

```python
# TheAgentCompany, workspaces/base_image/common.py:214-273
content = llm_response["choices"][0]["message"]["content"].lower().strip()
result = "yes" in content
```

```python
# AIOpsLab, aiopslab/orchestrator/evaluators/qualitative.py:48-62
one_score_pattern = re.compile(r"\[\[(\d+\.?\d*)\]\]")
...
else:
    score = -1
```

AIOpsLab at least has a distinguishable failure sentinel (`-1`); TheAgentCompany's `"yes" in content`
matches "yes" inside "there is no yes-or-no answer here". **AIOpsLab is the only repo that makes its
judge reproducible**: hard-pinned model and sampling (`model="gpt-4-turbo-2024-04-09",
temperature=0.0, top_p=0.95`) plus an on-disk response cache (`~/cache_dir/llm_cache.json`,
`aiopslab/utils/cache.py:10-39`). Copy that.

### 2.4 The two state-based verifiers worth copying

**tau-bench's whole-database hash** (`tau_bench/envs/base.py:121-164`, verified verbatim) is the most
elegant state check in the corpus:

```python
def calculate_reward(self) -> RewardResult:
    data_hash = self.get_data_hash()
    reward = 1.0
    ...
    # Check if the database changes are correct. If they are not correct, then we set the reward to 0.
    self.data = self.data_load_func()
    for action in self.task.actions:
        if action.name not in self.terminate_tools:
            self.step(action)
    gt_data_hash = self.get_data_hash()
    info = RewardActionInfo(
        r_actions=data_hash == gt_data_hash, gt_data_hash=gt_data_hash
    )
    if not info.r_actions:
        reward = 0.0
```

Note what it does *not* do: it never compares the agent's action *sequence* to the gold sequence. It
re-runs the gold actions from a clean DB and compares the resulting **states**. Any path to the right
world is accepted. That property is what you want, and it costs one function instead of per-task
assertions.

**AIOpsLab's mitigation check** is the opposite trade: hand-written `kubectl` assertions per problem
(pod readiness, `targetPort == 9090`, deployment `command`). Precise, but it does not scale — and the
repo says so (`problems/auth_miss_mongodb/auth_miss_mongodb.py:171-174`: *"this migigate eval should be
a bit different… should also check whether there are error log appearing"*).

### 2.5 Two verification ideas that exist only in vivaria

**Intermediate scoring.** The Task Standard allows `TaskFamily.intermediate_score()`, so a run
produces a `ScoreLog` — a *trajectory* of scores, not one final number. Nothing else in the corpus
measures progress during an episode.

**Human scoring as a first-class terminal state.** `TaskFamily.score() → None` means *"a human must
score this"*, which propagates all the way into the run-status SQL
(`server/src/migrations/schema.sql:429-461`):

```sql
WHEN (agent_branches_t_1.submission IS NOT NULL) THEN CASE
    WHEN (agent_branches_t_1.score IS NULL) THEN 'manual-scoring' :: text
    ELSE 'submitted' :: text
END
```

with rows in `manual_scores_t` (one per run × branch × user), the rubric taken from
`manifest.scoring.instructions`, and `secondsToScore` recorded. **This is the only mechanism in the
corpus for tasks whose done-ness cannot be automated**, and it is the only place anyone measures how
long grading itself takes.

---

## 3. G5 — Environment failure vs model failure: the corpus's collective answer

**This is the most important finding in the corpus, and it splits cleanly along the benchmark /
infrastructure line.**

> **All seven benchmarks have a richer failure vocabulary than their headline metric uses.** The
> taxonomies exist, are well designed, get written to disk — and are then discarded at the point where
> the number is computed. **Both pieces of infrastructure — SWE-agent and vivaria — get it right**,
> and vivaria's design is the reference implementation the benchmarks should have copied.

### 3.1 vivaria is the one system that does it properly

Error **source** is a first-class, typed field on every fatal error
(`shared/src/types.ts:430-441`):

```ts
export const ErrorSource = z.enum(['agent', 'server', 'task', 'serverOrTask', 'user', 'usageLimits'])

export const ErrorEC = strictObj({
  type: z.literal('error'),
  from: ErrorSource,
  sourceAgentBranch: AgentBranchNumber.nullish(),
  detail: z.any(),
  trace: z.string().nullish(),
  extra: z.any().nullable(),
})
```

Six sources, and the distinctions are exactly the ones that matter: `agent` (the model failed),
`task` (the task's own code failed), `server` (infrastructure), `serverOrTask` (**explicitly
ambiguous** — the honest fourth option nobody else has), `user` (a human killed it), `usageLimits`
(budget exhausted).

Four properties make this work, and each is independently worth stealing:

**(a) The run's status is *derived* from the error source, in SQL** — the taxonomy cannot drift away
from the metric because they are the same object (`server/src/migrations/schema.sql:429-461`):

```sql
WHEN ((agent_branches_t_1."fatalError" ->> 'from') = 'user')       THEN 'killed'
WHEN ((agent_branches_t_1."fatalError" ->> 'from') = 'usageLimits') THEN 'usage-limits'
WHEN (agent_branches_t_1."fatalError" IS NOT NULL)                  THEN 'error'
WHEN (agent_branches_t_1.submission IS NOT NULL) THEN CASE
    WHEN (agent_branches_t_1.score IS NULL) THEN 'manual-scoring'
    ELSE 'submitted'
END
...
```

yielding `RunStatus` (`shared/src/types.ts:753-766`):

```ts
export enum RunStatus {
  CONCURRENCY_LIMITED = 'concurrency-limited',
  ERROR = 'error',
  KILLED = 'killed',
  MANUAL_SCORING = 'manual-scoring',
  PAUSED = 'paused',
  QUEUED = 'queued',
  RUNNING = 'running',
  SETTING_UP = 'setting-up',
  SUBMITTED = 'submitted',
  USAGE_LIMITS = 'usage-limits',
}
```

Only `submitted` (and, ambiguously, `usage-limits`) is a scoreable model outcome. `killed` and `error`
are **structurally not model failures** — they can never be silently averaged into a pass rate,
because they are a different status, not a score of 0.

**(b) The agent is not trusted to declare its own error source**
(`server/src/routes/hooks_routes.ts:356-358`):

```ts
const c = input.content
if (!['agent', 'task'].includes(c.from))
  throw new TRPCError({ code: 'BAD_REQUEST', message: 'invalid error source from agent: ' + c.from })
```

An agent may claim `agent` or `task`. It may never claim `server` — the one classification that would
excuse its own failure.

**(c) The hard cases are handled by an explicitly-fallible heuristic, with the uncertainty preserved
in the type** (`server/src/docker/util.ts:205-225`):

```ts
const DOCKER_EXEC_SERVER_ERROR_STRINGS = [
  'response from daemon',
  'no such container',
  'token_expired: token is expired',
  // 137 indicates that something (probably Docker or the OOM killer) SIGKILLed the process.
  'command exited with non-zero exit code: 137',
  // 143 indicates that something SIGTERMed the process.
  'command exited with non-zero exit code: 143',
]

// Running task code (e.g. TaskFamily#install, start, or score) could fail because of a bug in Vivaria or a bug in
// the task code. This function tries to distinguish between the two cases. However, it can't say with certainty that a bug
// in the task caused an error. That's why, in these cases, it returns 'serverOrTask' instead of just 'task'.
export function getSourceForTaskError(error: Error | string): 'server' | 'serverOrTask' { … }
```

METR admits in a code comment that the split is unreliable — and encodes that admission as a *value in
the enum* rather than a footnote. That is the correct engineering response to an honest uncertainty.

**(d) Infrastructure flakiness does not charge the agent's budget.**
`RunPauseReason` (`shared/src/types.ts:572-582`):

```ts
export enum RunPauseReason {
  CHECKPOINT_EXCEEDED = 'checkpointExceeded',
  HUMAN_INTERVENTION = 'humanIntervention',
  PAUSE_HOOK = 'pauseHook',
  PYHOOKS_RETRY = 'pyhooksRetry',
  SCORING = 'scoring',
  LEGACY = 'legacy',
  OVERRIDE = 'override',
}
```

`PYHOOKS_RETRY` opens whenever the agent's HTTP call to Vivaria fails and is retried; `SCORING` opens
while the grader runs. **Both exclude that wall-clock time from the run's time budget.** No benchmark
in the corpus does this — in all seven, a slow or flaky harness eats the agent's budget and then the
resulting failure is attributed to the model.

### 3.2 SWE-agent is the runner-up

SWE-agent's `exit_status` is the richest failure taxonomy in a *code* agent anywhere in the corpus,
and it separates the same axes vivaria does:

| `exit_status` | Class | Set at |
|---|---|---|
| `submitted` | success | `sweagent/agent/agents.py:900` |
| `submitted (<other>)` | salvaged after an error (e.g. `submitted (exit_cost)`) | `:902`, `:848` |
| `exit_command` | model issued bare `exit` | `:953` |
| `exit_forfeit` | model gave up | `:1157` |
| `exit_total_execution_time` | budget | `:1164` |
| `exit_command_timeout` | ≥ N consecutive command timeouts | `:1171` |
| `exit_context` | `ContextWindowExceededError` — **model** limit | `:1177` |
| `exit_cost` | `CostLimitExceededError` — budget | `:1184` |
| `exit_api` | LM API kept failing — **provider** failure | `:1190` |
| `exit_environment_error` | `SwerexException` — **the sandbox failed** | `:1196` |
| `exit_error` | any other unhandled exception | `:1202`, `:1208` |
| `exit_format` | `max_requeries` exhausted on format/blocklist errors | `:1216` |
| `early_exit` / `None` | trajectory never finished — **deleted and redone** | `run_batch.py:396-401` |
| `skipped (<previous>)` | already-finished `.traj` found | `run_batch.py:301-304` |
| `unknown_exit` | fallback | `run_batch.py:327` |

Three things this gets right that the benchmarks do not:

1. **`exit_environment_error` is a distinct terminal state**, not folded into `exit_error`.
2. **`exit_api` separates provider failure from model failure** — nobody else distinguishes "the API
   was down" from "the model was wrong".
3. **`early_exit` runs are deleted and re-run** (`run_batch.py:396-401`) rather than scored — the only
   automatic recovery-from-infra-failure in the corpus.

And `TotalCostLimitExceededError` is deliberately **not** an exit status: it re-raises to kill the
whole batch (`agents.py:1180-1181`), because a global budget overrun invalidates the *run*, not the
*instance*.

### 3.3 …and how each of the seven benchmarks throws its taxonomy away

The taxonomies all exist:

| Repo | Taxonomy | Where |
|---|---|---|
| terminal-bench | 11-value `FailureMode` enum | `terminal_bench/agents/failure_mode.py` |
| SWE-bench | 7 report buckets | `swebench/harness/reporting.py:101-125` |
| tau-bench | `FaultAuthor{USER, AGENT, ENVIRONMENT}` + 4 `FaultType`s | `auto_error_identification.py:31-35, 48-52` |
| commit0 | 8 log sentinels | `commit0/harness/constants.py:296-304` |
| SWE-Lancer | tri-state pytest exit (`0` / `1` / `≥2` / `-1`) | `adapters/swelancer/template/swe/run-tests.sh:79-92` |
| AIOpsLab | **none** | — |
| TheAgentCompany | **none** at checkpoint level | — |

terminal-bench's is the best-designed, verified verbatim from
`terminal_bench/agents/failure_mode.py` (complete file):

```python
class FailureMode(Enum):
    UNSET = "unset"
    NONE = "none"
    UNKNOWN = "unknown"
    TEST_TIMEOUT = "test_timeout"
    AGENT_TIMEOUT = "agent_timeout"
    UNKNOWN_AGENT_ERROR = "unknown_agent_error"
    PARSE_ERROR = "parse_error"
    FATAL_LLM_PARSE_ERROR = "fatal_llm_parse_error"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    OUTPUT_LENGTH_EXCEEDED = "output_length_exceeded"
    AGENT_INSTALLATION_FAILED = "agent_installation_failed"
```

It separates harness failure (`AGENT_INSTALLATION_FAILED`, `TEST_TIMEOUT`), model failure
(`FATAL_LLM_PARSE_ERROR`, `CONTEXT_LENGTH_EXCEEDED`) and budget exhaustion (`AGENT_TIMEOUT`) — and
then the metric ignores all of it (`terminal_bench/harness/models.py:134-139`):

```python
@computed_field
@property
def accuracy(self) -> float:
    if not self.results:
        return 0.0
    return self.n_resolved / len(self.results)
```

`is_resolved=None` — which is what an `AGENT_INSTALLATION_FAILED` trial produces — is falsy, so
**infrastructure failures count as model failures**. There is no "excluded" bucket.

**tau-bench** is the only benchmark that names the *author* of a fault, and the only one anywhere that
includes the **user** as a possible culprit — which matters once a simulated human is in the loop
(`auto_error_identification.py:126-129`):

```python
res = api.classify(
    instruction=f"...Determine the entity that is responsible for the fault. The user is responsible for the fault if they caused an action that was not grounded in the user instruction. The agent is responsible for the fault if they took an action that was not correct (or took the action with the wrong arguments). The environment is responsible for all other faults.",
    text=context,
    options=["The user", "The agent", "The environment (neither user nor agent)"],
)
```

But note the tell: **"environment" is the `else` branch**, and the summary print labels it
`- Environment (otherwise case):` (`:214`). It runs *post hoc*, over a results file, and never touches
`avg_reward` or `pass^k`. Meanwhile three distinct failure classes collapse to `reward = 0.0`:
tool exceptions become observations (`envs/base.py:101-106`); harness exceptions are recorded as
`info={"error","traceback"}` with an empty trajectory but **still counted** in the metrics
(`run.py:77-96`); and if the user simulator never emits `###STOP###` within 30 steps,
`calculate_reward()` is **never called** and the reward silently stays at its `0.0` initialiser —
verified present in the shipped results (`gpt-4o-retail.json` has 2 records with no `reward_info`
at all).

**SWE-bench** — the buckets are real, but `error_ids` is defined as *"no `report.json` on disk"*
(`swebench/harness/reporting.py:44-72`), absorbing timeouts, patch-apply failures, container crashes,
unparseable logs and missing images into one undifferentiated pile. And whether "% Resolved" divides by
`total_instances` or `submitted_instances` is **never resolved in code**: the printed line intersects
with the dataset (`reporting.py:89`), the stored JSON does not (`:103`), so the two can disagree.

**commit0** — the worst case. A test ID absent from the JSON report is scored `"failed"`
(`commit0/harness/evaluate.py:130`); a missing report file scores 0 (`:98-108`). The 8-sentinel
taxonomy never reaches the metric, and even the submission renderer — which *does* carry a
`failed_to_run` marker — still appends `0.0` (`docs/render_submissions.py:278-289`).

**AIOpsLab** — no separation at all. One bare `except Exception` turns any infrastructure error into an
observation string handed back to the agent (`aiopslab/orchestrator/orchestrator.py:113-143`):

```python
except InvalidActionError as e:
    env_response = str(e)
except Exception as e:
    env_response = str(e)
    print("Unhandled exception:", e)
```

A Prometheus outage, a failed port-forward and a genuine "service not found" are indistinguishable in
the trace. Hitting `max_steps` writes **no truncation flag** — `Session.to_dict()`
(`aiopslab/session.py:103-115`) stores only `agent, session_id, problem_id, start_time, end_time,
trace, results`.

**TheAgentCompany** — the conflation is *deliberate, documented and CI-enforced*
(`workspaces/base_image/common.py:35-47`):

```python
def grader(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if result is None:
                logging.warning(f"Grader returns None, using False instead")
                return False
            return result
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return False
    return wrapper
```

Rationale (`workspaces/tasks/example/README.md:56-61`): *"This is required as it would capture runtime
errors and make the evaluator not fail the entire task."* A GitLab 500 and an agent that did nothing
produce the same `False`. **CI fails a PR whose `evaluator.py` lacks the decorator.**

**SWE-Lancer** — the *best* separation of the seven at the grader level (tri-state exit codes, a `-1`
"no verdict" sentinel, a `ran_any` guard), then a **false positive** at the parser level
(`terminal_bench/parsers/swelancer_parser.py:31-32`): if neither sentinel string appears, a trial is
marked **PASSED** whenever the captured output happens to contain both `user_tool` and `completed`.
The environment-failure path defaults to success.

### 3.4 The one benchmark that excludes failures — and why that is also wrong

TheAgentCompany is the only benchmark that removes failed runs from the denominator, and it does so
**by accident**. `evaluation/run_eval.sh:95-99` skips any task with an existing `eval_*.json`; a
crashed run produces no such file; `summarise_results.py:297` then reports
`**Tasks Evaluated:** {len(eval_results)}`. Its own README states the consequence
(`evaluation/README.md:60-66`):

> the script will automatically skip a task if it encounters an error. This usually happens when the
> OpenHands runtime dies due to some unexpected errors. **This means even if the script finishes, it
> might not have evaluated all tasks.**

So the corpus offers exactly two benchmark behaviours, and both are biased:

| Behaviour | Bias | Who |
|---|---|---|
| Infra failure counts as model failure (stays in denominator) | **pessimistic** and noisy — a flaky environment looks like a weak model | SWE-bench, terminal-bench, commit0, tau-bench, AIOpsLab, SWE-Lancer |
| Infra failure silently drops out of the denominator | **optimistic** and unfalsifiable — the score is over an unstated subset | TheAgentCompany |
| Infra failure is a **different terminal state** | correct | **vivaria**, and (per-instance) SWE-agent |

**No benchmark reports a third number.** None prints
`resolved / (total − environment_failures)` alongside `resolved / total`, and none reports the
environment-failure *rate* as a quality metric of its own harness.

### 3.5 The rate is not small

Where the corpus quantifies it, environment failure is a first-order effect:

- **AlgoTune's oracle passes only ~85 %** in terminal-bench (`adapters/algotune/README.md`) — ~15 % of
  that dataset is unwinnable for reasons unrelated to the model.
- **3 SWE-bench Verified tasks fail with the oracle agent**, named individually
  (`adapters/swebench/README.md:47-49`): `astropy__astropy-7606` lists a test that does not exist in
  the repo; `-8872` and `-8707` fail on unpinned `pytest`/`distutils` deprecations.
- **SWE-Lancer dropped 39 IC problems** for requiring internet access
  (`adapters/swelancer/README.md:9`) — a dataset-level G5 decision.
- **SWE-Lancer manager tasks with >17 K-char instructions silently fail** by overflowing the tmux
  buffer (`adapters/swelancer/README.md:13`) — a *silent* environment failure scored as a model failure.
- **TheAgentCompany** documents Plane and RocketChat routinely failing to start
  (`docs/SETUP.md:57-59, 81-85, 99-105`).
- **AIOpsLab creates its own**: every Chaos-Mesh fault carries `duration: "200s"` and **self-heals
  mid-episode** while the agent has `max_steps=30`.

### 3.6 The three practices that would fix it

Each already exists somewhere in the corpus:

1. **Run an oracle through the identical harness path, in CI.** terminal-bench enforces
   oracle-must-pass **and** nop-must-fail, or the PR is blocked
   (`.github/workflows/test-tasks.yaml:255-276`):
   ```bash
   if [ "$nop_ran" = true ] && [ "$nop_passed" = false ]; then
     echo "❌ NOP Agent passed tests when it should have failed!"
     exit 1
   fi
   ```
   commit0 exposes the same idea as first-class CLI verbs — `test-reference` and `evaluate-reference`
   (`commit0/harness/constants.py:73-84`), which run the `reference_commit` through the same pipeline.
   **An oracle failure is definitionally an environment failure.** Cheapest, highest-value control in
   the corpus.

2. **Carry a typed source, not a boolean.** vivaria's `ErrorSource` with an explicit `serverOrTask`
   ambiguity value, derived into the run status in SQL so it cannot drift from the metric.

3. **Do not charge infrastructure time to the agent.** vivaria's `RunPauseReason.PYHOOKS_RETRY` and
   `SCORING`. And retry asymmetrically where the verifier is flaky: SWE-Lancer runs the E2E suite up
   to 3 times and passes if *any* run passes (`run-tests.sh:27-33, 103-109`) — suppressing false
   negatives from a flaky browser without suppressing true negatives.

**The rule the corpus implies, stated plainly:** *report three numbers — resolved, model-failed,
environment-failed — and treat a nonzero environment-failed rate as a bug in your harness, not as
difficulty.*

---

## 4. G4 — The reward-hacking guard catalogue

### 4.1 Hide the answer key from the agent

| Technique | Repo | Citation |
|---|---|---|
| **Copy tests in only *after* the agent stops** | terminal-bench | `terminal_bench/harness/harness.py:544-555`, called first in `_run_tests` (`:563`), reached at `:773` |
| Password-protected zip of tests, unzipped at grade time | SWE-Lancer (original) | `adapters/swelancer/template/Dockerfile:18-22` |
| Fernet-encrypt `evaluator.py` at build, delete plaintext | TheAgentCompany | `workspaces/base_image/Dockerfile:78` |
| Rubric prose never enters the image | TheAgentCompany | only `*.py`, `dependencies.yml`, `task.md` are `ONBUILD COPY`'d (`Dockerfile:70-75`) |
| Encrypted / `chmod 700` protected dirs for server-side state | terminal-bench | `original-tasks/blind-maze-explorer-5x5/Dockerfile:4-15`; `adaptive-rejection-sampler/Dockerfile:18` |
| Environment-generator script run at build then deleted | terminal-bench | `original-tasks/chess-best-move/Dockerfile:311-313` (`COPY make.py` → `RUN python3 make.py` → `RUN rm make.py`) |
| `/protected` group convention for scoring logic and logs | vivaria | `scripts/docker/task.Dockerfile:75-108` (which itself admits an exfiltration hole) |
| Withhold the test-split eval specs entirely | SWE-bench Multimodal | *"To encourage less intentional climbing of the leaderboard, we have intentionally made specifications for evaluating the test split private"* (`docs/assets/evaluation.md:44`) |

**terminal-bench's ordering guard is the strongest**, and it has a stated design consequence
(`terminal_bench/cli/tb/quality_checker/models.py:36-45`): *"Note that the tests and solution are NOT
visible to the agent. **Don't worry about non-randomized, static tests**, since the agent can't see the
tests."* Get isolation right and you never have to obfuscate a test again.

**Both encryption schemes are theatre, and both repos admit it.** TheAgentCompany's Fernet key is
`b'theagentcompany is all you need'`, published in `docs/EVALUATION.md:13-15`; SWE-Lancer's zip
password is `'secretpasswordhere'`, hard-coded in the Dockerfile. Both defeat *accidental* peeking only.
TheAgentCompany falls back to a social contract (`docs/EVALUATION.md:124-127`): *"examinees (e.g.
agents) are not allowed to read checkpoint rubrics or evaluation code."*

**SWE-Lancer's original architecture is the one to copy**, and the reason terminal-bench could not: a
*privileged out-of-band executor* owned the tests, ran them on request, and returned only the *output*.
The adapter README explains the compromise (`adapters/swelancer/README.md:15`): *"As Terminal-Bench
does not have a privileged user to run commands outside of the namespace of the agent, this is the most
faithful way we can provide the agent access to the user tool."* **If you want an agent to have a
reproduction loop without the answer key, your sandbox must support a privileged side-channel.**

### 4.2 Hide the future from the agent

Two repos independently arrived at the same three-part git guard, and **commit0 states outright that
agents were exploiting it** (`commit0/harness/spec.py:117-118, 124-125`):

```python
# Use --depth 1 for shallow clone to prevent agents from accessing
# git history and exploiting it to retrieve original implementations
f"git clone --depth 1 -o origin https://github.com/{repo} {self.repo_directory}",
...
# Remove the remote so the agent won't see newer commits.
"git remote remove origin",
```

SWE-bench goes further — scrubbing tags and reflog, then **asserting** nothing survives past the base
commit (`swebench/image_builder/docker_utils.py:58-78`):

```bash
COMMIT_COUNT=$(git log --oneline --all --after="@$AFTER_TIMESTAMP" | wc -l)
[ "$COMMIT_COUNT" -eq 0 ] || exit 1
```

terminal-bench encodes it as an authoring criterion instead: *"If Dockerfile involves git cloning,
ensure that the agent won't see newer commits"* (`quality_checker/models.py:36-45`). SWE-Lancer
re-inits git so `git diff HEAD` captures exactly the model's changes
(`adapters/swelancer/template/Dockerfile:27-31`).

### 4.3 Constrain the solution surface

- **Test files never in the editable set.** commit0 subtracts test files and drops `conftest.py`
  (`agent/agent_utils.py:183-192`). SWE-bench splits the gold patch into `patch_fix` / `patch_test` at
  *collection* time (`swebench/collect/utils.py:312-333`), so tests are never part of the solution.
- **⚠ SWE-bench does NOT strip test edits from the model patch.** `run_evaluation.py:208` writes
  `model_patch` verbatim; `NON_TEST_EXTS` (`constants/__init__.py:53-65`) is **dead code**. The only
  backstop is a `git checkout` inside the externally generated eval script — not auditable from the
  repo. **This is the largest unguarded surface in the corpus.**
- **SWE-agent closes it three ways** where SWE-bench does not:
  (a) the review-on-submit checklist tells the agent to `git checkout --` any modified TEST files
  (`config/default.yaml:55-56`); (b) `submit` reverse-applies `/root/test.patch`
  (`tools/submit/bin/submit:5-8`); (c) the chooser prompt says *"Disregard all testing code in the
  patch… Having a test in the patch does not make it any better"*
  (`config/benchmarks/250212_sweagent_heavy_sbl.yaml:149-150`).
- **Name stability as a prompt constraint** — commit0: *"Do not change the names of existing functions
  or classes, as they may be referenced from other code like unit tests"* (`agent/configs/base.yaml:8`).
- **Sandboxed `eval`** — tau-bench's calculator uses a character allowlist and no builtins
  (`tau_bench/envs/retail/tools/calculate.py:10-16`).
- **One tool call per turn** — tau-bench truncates to the first
  (`tau_bench/agents/tool_calling_agent.py:54`), mechanically enforcing its written policy and
  preventing parallel-write shotgunning.
- **A tool removed for being a cheat** — AIOpsLab's repo-diff action is commented out with
  `# NOTE: disabled for now, since seems like a cheat for code changes`
  (`aiopslab/orchestrator/actions/base.py:217-218`).
- **A safety-policy hook on every action** — vivaria's `Actions.check_safety` calls
  `checkActionSafety` server-side before every `run_bash` and raises
  `ActionViolatesSafetyPolicyException` (`pyhooks/pyhooks/__init__.py:1023-1053`). The only
  server-mediated action gate in the corpus.

### 4.4 SWE-agent's blocklist — a stability guard first

Verbatim (`sweagent/tools/tools.py:29-72`):

```python
blocklist: list[str] = [
    "vim", "vi", "emacs", "nano", "nohup", "gdb", "less", "tail -f",
    "python -m venv", "make",
]
"""Block any command that starts with one of these"""

blocklist_standalone: list[str] = [
    "python", "python3", "ipython", "bash", "sh", "/bin/bash", "/bin/sh",
    "nohup", "vi", "vim", "emacs", "nano", "su",
]
"""Block any command that matches one of these exactly"""

block_unless_regex: dict[str, str] = {
    "radare2": r"\b(?:radare2)\b.*\s+-c\s+.*",
    "r2": r"\b(?:radare2)\b.*\s+-c\s+.*",
}
```

Three concerns in three lists: interactive/hanging programs; bare REPLs that would swallow the tmux
session; and a CTF residue permitting `radare2` only in scripted `-c` form. A blocked action **requeries**
rather than terminating (`agents.py:946-947`), which is the right failure mode. Note this is a
*stability* guard; the anti-reward-hacking guards are the three listed in §4.3.

### 4.5 Anti-triviality and anti-contamination

- **Oracle-must-pass / nop-must-fail in CI** — terminal-bench (§3.6). The only automated *task-validity*
  gate in the corpus.
- **Canary GUIDs.** terminal-bench requires `terminal-bench-canary GUID 26b5c67b-…` in every
  `task.yaml`, `solution.*`, `Dockerfile` and `test_outputs.py`, CI-enforced
  (`scripts_bash/check-canary.sh:6`). SWE-Lancer's adapter templates carry the same GUID. It is a
  *detector*, not a control — the agent runs in the container and can grep for it.
- **Version pinning as policy.** terminal-bench requires pinned Python deps and *forbids* pinned apt
  deps, with a stated reason for each (`quality_checker/models.py:53-60`;
  `.github/workflows/check-dockerfile-sanity.yml:23-25`). commit0 pins its whole static-analysis gate
  (`ruff v0.6.1`, `pyright v1.1.376`, `pre-commit-hooks v4.3.0` — `commit0/harness/lint.py:13-34`).
- **Secret scrubbing.** SWE-Lancer's adapter strips AWS `X-Amz-Credential` presigned-URL params out of
  issue text before shipping it (`adapters/swelancer/utils/clean.py:14-21`).
- **Nothing at all in vivaria** — a repo-wide grep for `reward hack|cheat|exploit the scor|game the`
  returns **zero hits**. As a platform it delegates the question to the task author.

### 4.6 The unguarded surfaces, named

- **SWE-bench:** model patch may edit tests, `conftest.py` or `pytest.ini`; `patch --fuzz=5` will land
  a fuzzy patch (`run_evaluation.py:57`).
- **tau-bench:** `outputs` grading is a **case-insensitive substring** match. Three retail test tasks
  have `outputs=["10"]` (`tasks_test.py:80,112,153`), one airline task has `outputs=["4"]`
  (`:1153`) — an agent that enumerates numbers passes by accident.
- **commit0:** the agent runs the same pytest used for grading (by design), and nothing detects
  `pip install <the-real-library>`.
- **terminal-bench:** `all([])` is `True`, so a task whose parser yields an empty result dict is scored
  **resolved** (`harness.py:536-542` + `pytest_parser.py:71-80`). One task leaks its grader into the
  agent's workdir (`break-filter-js-from-html/Dockerfile:23`). Only 5/241 Dockerfiles set `USER`, so
  `chmod 700` protection is usually moot.
- **SWE-Lancer:** the parser's fallback marks a trial PASSED on a loose substring match
  (`swelancer_parser.py:31-32`).

---

## 5. G2 — Flakiness policies

Two philosophies, split by whether the verifier touches a network.

### 5.1 "Make it deterministic, then trust one run"

**commit0, SWE-bench, terminal-bench (core).** No instance-level retries anywhere:

- SWE-bench: *no retry of a failed instance evaluation anywhere*. The only `tenacity` retry is Modal
  sandbox creation, 7 attempts, reason in a comment (`modal_eval/run_evaluation_modal.py:71-74`:
  *"Sometimes network flakiness causes the image build to fail"*).
- commit0: content-addressed images keyed on a SHA-256 of the setup script
  (`commit0/harness/spec.py:50-63`), pinned `linux/x86_64` (`:93-95`), pinned linter versions,
  `--continue-on-collection-errors`, and handling for two pytest-json schema versions.
- terminal-bench: version pinning as an authoring criterion; seeded data generators; irreducibly
  nondeterministic tasks say so in a comment
  (`original-tasks/cross-entropy-method/evaluation_tests_hidden/...:3`).

### 5.2 "Assume it is flaky, retry, take best-of-N"

**SWE-Lancer, TheAgentCompany, AIOpsLab, SWE-agent, vivaria.**

- **SWE-Lancer:** `N_TEST_RUNS=3`, pass-if-any, early break on first success
  (`adapters/swelancer/template/swe/run-tests.sh:27-33, 103-109`), plus `set +e`/`set -e` bracketing,
  defensive exit-code parsing, log-dir reset between attempts, and per-run randomised Pusher
  credentials (`adapters/swelancer/utils/dataset.py:7-9`). Its own prompt tells the agent the tool is
  flaky (`utils/prompts.py:58-60`).
- **SWE-agent:** `max_requeries=3` for format/blocklist errors (`agents.py:158-161`);
  **content-policy violations are silently resampled** rather than failed; litellm retry config;
  `max_consecutive_execution_timeouts=3` (`tools/tools.py:150-152`).
- **vivaria:** setup retries; crash recovery across server restarts; and the `PYHOOKS_RETRY` pause that
  removes retry time from the budget (§3.1d).
- **TheAgentCompany:** resumable, skip-on-error, per-image health checks; *"It would usually take a few
  days to finish evaluation"* (`evaluation/README.md:60-66`).
- **AIOpsLab:** ~15 fixed sleeps, 300 s readiness polls, and a fault `duration: "200s"` that self-heals
  mid-episode — nondeterminism the harness creates for itself.

### 5.3 Repeated-sampling metrics: the corpus's sharpest methodological disagreement

Only two repos compute one, and **they compute opposite things.**

**terminal-bench — `pass@k`** (`terminal_bench/harness/models.py:74-112`), the standard unbiased Codex
estimator, *increasing* in k (at least one success):

```python
def _pass_at_k_estimator(self, n: int, c: int, k: int) -> float:
    """Calculates 1 - comb(n - c, k) / comb(n, k)."""
    if n - c < k:
        return 1.0
    return float(1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))
```

**tau-bench — `pass^k`** (`tau_bench/run.py:194-199`, verified verbatim against the repo),
*decreasing* in k (all k must succeed):

```python
pass_hat_ks: dict[int, float] = {}
for k in range(1, num_trials + 1):
    sum_task_pass_hat_k = 0
    for c in c_per_task_id.values():
        sum_task_pass_hat_k += comb(c, k) / comb(num_trials, k)
    pass_hat_ks[k] = sum_task_pass_hat_k / len(c_per_task_id)
```

i.e. `pass^k = (1/|T|) Σ_t C(c_t, k) / C(n, k)` — the probability that *k* trials drawn without
replacement from a task's *n* trials are **all** successes. `pass^1` equals the plain average reward.

`pass@k` measures *capability with retries*; `pass^k` measures **reliability**. For a benchmark meant to
model production work — where an agent that succeeds 1 time in 4 is worse than useless — `pass^k` is
the right metric, and tau-bench is the only repo that adopted it. Its own numbers show why: Claude 3.5
Sonnet scores 0.692 `pass^1` but **0.462 `pass^4`** on retail (`README.md:13-35`).

### 5.4 Nondeterminism the corpus leaves unpinned

- **tau-bench's user simulator has no temperature argument at all**
  (`tau_bench/envs/user.py:46-49`), so it inherits the provider default (1.0), while the *agent's*
  temperature defaults to 0.0. The single largest source of run-to-run variance in the benchmark is
  deliberately unpinned and not even exposed as a CLI flag.
- **TheAgentCompany: 70/175 tasks (40 %) are stochastic** — 41 with LLM-driven NPC colleagues, 53 with
  an LLM judge (overlap included). Only **105 tasks are fully deterministic**
  (`evaluation/README_task_images.md:99, 114, 119, 158`).
- **AIOpsLab's LLM judge is the one that *is* pinned and cached** (§2.3).

---

## 6. G3 / H1 — Metric definitions and difficulty anchors

### 6.1 Where numbers actually live

**Six of the eight scoreable repos ship no results at all**: SWE-bench (`docs/index.md:33-35` →
swebench.com), commit0 (`docs/analysis.md` is generated, not committed; `docs/baseline.md` is a 5-line
stub ending in a literal `...`), AIOpsLab (nothing anywhere), TheAgentCompany (external leaderboard),
terminal-bench (no table; `tbench.ai`), vivaria (a platform).

**tau-bench `README.md:13-35`** — the only leaderboard committed to a repo:

| Domain | Strategy | Pass^1 | Pass^2 | Pass^3 | Pass^4 |
|---|---|---|---|---|---|
| Retail (115) | TC claude-3-5-sonnet-20241022 | 0.692 | 0.576 | 0.509 | 0.462 |
| Retail | TC gpt-4o | 0.604 | 0.491 | 0.430 | 0.383 |
| Airline (50) | TC claude-3-5-sonnet-20241022 | 0.460 | 0.326 | 0.263 | 0.225 |
| Airline | TC gpt-4o | 0.420 | 0.273 | 0.220 | 0.200 |

**terminal-bench `adapters/*/parity_experiment.json`** — the richest anchor set in the corpus, and the
only place the same agent is measured across many benchmarks:

| Benchmark | Agent / model | n | Original | TB adapter |
|---|---|---:|---:|---:|
| SWE-bench Verified | terminus-v1.5-xml / claude-opus-4 | 500 | 66.4 | 66.4 |
| SWE-bench Verified | openhands / claude-4-sonnet | 500 | 66.8 | 67.0 |
| SWE-bench Verified | codex 0.2.0 / o4-mini | 500 | 53.11 | 53.11 |
| SWE-Lancer Diamond | claude-code / claude-sonnet-4 | 463 | 49.03 ± 2.86 | 49.24 ± 2.86 |
| USACO | codex / o4-mini | 304 × 3 | 74.7 ± 1.53 | 74.69 ± 0.558 |
| Aider polyglot | claude-code / claude-3-7-sonnet | 225 × 2 | 34.2 ± 2.2 | 35.3 ± 0.7 |
| AppWorld dev | claude-code / claude-opus-4 | 57 | 52.1 ± 1.8 | 52.1 ± 1.8 |
| AppWorld dev | **codex / o4-mini** | 57 | **0 ± 0** | **0 ± 0** |
| AppWorld test_challenge | claude-code / claude-sonnet-4 | 417 | 23.5 | 23.5 |
| AlgoTune | openhands / gpt-5 | 154 × 3 | 30.52 ± 1.59 | 30.95 ± 2.14 |
| Cybench | cybench agent / o4-mini | 40 × 4 | 19.38 ± 1.88 | 19.38 ± 1.2 |
| DevEval | claude-code / claude-opus-4 | 63 × 8 | 22.8 ± 4.3 | 21.6 ± 3.3 |
| EvoEval | claude-code / claude-opus-4 | 100 × 8 | 65.8 ± 1.7 | 66.4 ± 1.4 |
| QuixBugs | claude-code / claude-3-7-sonnet | 80 × 5 | 80.75 ± 1.06 | 80.75 ± 1.525 |
| SWE-smith | mini-swe-agent / claude-sonnet-4 | 100 | 37 | 38 |
| SWE-Perf | openhands / claude-3-7-sonnet | 140 | 81.43 | 81.43 |

**SWE-Lancer** (`adapters/swelancer/README.md:95-99`): claude-4-sonnet scores **51.5 % IC**,
**47.2 % manager**, **49.0 % overall**.

### 6.2 Reading the anchors

1. **The difficulty range is ~0 % to ~81 %.** AppWorld with codex/o4-mini scores **exactly 0.0 ± 0.0 on
   57 tasks** — a benchmark can be wholly out of reach for a capable model. SWE-Perf sits at 81 %.
2. **Error bars are large and usually unreported.** SWE-Lancer's ±2.86 pp on n=463 means any two
   systems within ~6 pp are indistinguishable. Only terminal-bench's parity JSONs record `std_error`.
3. **Reliability is far below capability.** tau-bench retail: 0.692 → 0.462 from `pass^1` to `pass^4`.
   A third of apparent capability is coin-flips.
4. **Adapter parity is a real methodology.** terminal-bench requires a new adapter's numbers to match
   the upstream harness within noise before acceptance, with the evidence checked into
   `parity_experiment.json`. Every benchmark that reimplements another should do this.

### 6.3 Metric definitions worth naming

| Metric | Definition | Where |
|---|---|---|
| % Resolved | `f2p == 1 and p2p == 1` | `swebench/harness/grading.py:195-212` |
| Accuracy | `n_resolved / len(results)` — **trials**, not tasks | `terminal_bench/harness/models.py:134-139` |
| Average pass rate | mean over **repos** of `passed/total` — unweighted, so a 38-test repo counts as much as a 40 433-test one | `commit0/harness/evaluate.py:139`, `docs/render_submissions.py:364` |
| Score | `0.5·(result/total) + 0.5·⌊result/total⌋` | `evaluation/summarise_results.py:162-178` |
| Reward | `{0.0, 1.0}` from DB hash **and** output substrings | `tau_bench/envs/base.py:121-164` |
| TTD / TTL / TTA / TTM | wall-clock seconds to detect / localize / analyse / mitigate | `aiopslab/orchestrator/tasks/*.py` |
| Usage | tokens, actions, seconds, **cost in USD** — enforced as limits, not just reported | vivaria `RunUsage` / `UsageCheckpoint` |

**Three metrics measure something other than correctness, and all three are worth copying:**

- **commit0 puts test *duration* on the leaderboard** (`docs/render_submissions.py:371`) — a naive
  O(n²) reimplementation that passes ranks worse. The only implementation-quality signal in the corpus.
- **SWE-Lancer's canonical metric is dollars earned** — a price-weighted pass rate over ~$500 K of real
  Upwork payments. The terminal-bench adapter drops it and says why
  (`adapters/swelancer/README.md:14`). The only metric anywhere tied to business value.
- **vivaria records `secondsToScore`** on every manual score — the only measurement of what *grading*
  costs.

### 6.4 Task length is bounded very differently

A cross-cutting C2 finding worth stating on its own:

| Repo | Bound | Value |
|---|---|---|
| SWE-bench | **none** — the harness only sees a patch string; no notion of steps exists | — |
| SWE-agent | **no `max_steps`** — bounded by *money*, not turns | `per_instance_cost_limit` **$3.00**; `total_execution_timeout` 1800 s; `max_requeries` 3; `execution_timeout` 30 s/command |
| AIOpsLab | steps | `max_steps=30` |
| tau-bench | steps | `max_num_steps=30` |
| terminal-bench | wall-clock | modal task 900 s agent / 180 s test |
| SWE-Lancer | wall-clock | 3 000 s agent / 3 000 s test |
| commit0 | iterations + wall-clock | `max_iteration: 3`; 1 800 s test timeout |
| vivaria | typed usage limits | tokens, actions, seconds, cost — with **checkpoints that pause** rather than kill |

**SWE-agent's choice — budget in dollars, not steps — is the outlier and arguably the most realistic.**
Real agents are constrained by cost and wall-clock, not by an integer turn count. vivaria generalises
it into a four-dimensional `RunUsage` with a pause-vs-kill distinction (`UsageCheckpoint` pauses;
exceeding a limit kills with `from: 'usageLimits'`).

---

## 7. D1 / D3 — What context benchmarks actually hand an agent

| Repo | The agent's context |
|---|---|
| SWE-bench | `problem_statement` (concatenated GitHub issue title+body; Django scraped from Trac) + a repo snapshot as a Docker image. `hints_text` is collected but **never used at eval time**. |
| SWE-agent | a **69-line** `config/default.yaml`: one-line system prompt, one PR-description instance template, `OBSERVATION:\n{{observation}}` thereafter, and **no history elision** — only `cache_control(2)`. |
| terminal-bench | **one prose string** (median 905 chars) plus a live tmux pane. Nothing else. |
| commit0 | configurable along six axes: repo tree, regex-extracted function stubs, unit-test signatures, **the library's real ReadTheDocs PDF** (text-extracted with PyMuPDF, truncated to 10 000 chars), lint output, and full source of already-written dependency modules |
| tau-bench | a **written domain policy document** (`wiki.md`, 81 lines retail / 70 airline) + an LLM-simulated customer who reveals requirements only when asked |
| TheAgentCompany | *"Complete the task in /instruction/task.md"* — plus four live services and up to 18 NPC colleagues to interrogate over chat |
| AIOpsLab | a prose app summary + an action DSL. **No alert payload.** The agent must pull logs/metrics/traces itself. |
| SWE-Lancer | the raw **HTML** issue body (`html_description`), the dollar price, and a "user tool" producing a Playwright trace |
| vivaria | `TaskFamily.get_instructions()` — a plain string, plus a container with a declared network permission (`get_permissions() → ["full_internet"]` or none) |

Three observations that matter for building a realistic agent world:

1. **Only commit0 hands the agent a real human-authored specification document** (the library's PDF
   docs) — and truncates it. That is the closest the corpus comes to the "runbooks / ADRs / design docs"
   of question D1: one repo out of nine.
2. **AIOpsLab, the one ops benchmark, has no alert payload.** Telemetry is pulled via actions, and
   `get_metrics` does not even return values — it writes CSVs and returns a **directory listing**
   (`aiopslab/orchestrator/actions/base.py:113-141`), forcing a second `read_metrics(file_path)` call.
   Realistic as a hazard, but it means **the corpus contains no example of a real alert payload**.
3. **The most realistic evidence artefact in the corpus is SWE-Lancer's Playwright trace** — a file the
   agent is explicitly told is *too big to read* and must parse programmatically
   (`adapters/swelancer/utils/prompts.py:42-43`), with rows typed `screencast-frame`, `frame-snapshot`,
   `log`, `before`, `after` and `sha1` pointers into a JPEG resource folder.

**Tool surfaces span two orders of magnitude, with no correlation to score:**

| Repo | Tool surface |
|---|---|
| SWE-Lancer (original) | **2**: `python -c "<script>"` and a `<user-tool>` token → **49 %** |
| terminal-bench | **2**: `keystrokes`, `capture_pane` (raw tmux, 160×40) |
| vivaria | **2**: `run_bash`, `run_python` (+ `submit` via hooks). Everything else is the agent author's problem. |
| AIOpsLab | **7**: `get_logs`, `get_metrics`, `read_metrics`, `get_traces`, `read_traces`, `exec_shell`, `submit` |
| tau-bench | **16 retail / 14 airline** OpenAI function schemas, ~7 of them writes |
| commit0 | editor-only (Aider), fixed file set, **no shell** |
| SWE-agent | **15 bundles**: windowed viewer (`open`/`goto`/`scroll_*`/`create`), three interchangeable editors, `search_dir`/`search_file`/`find_file`, `submit`, `exit_forfeit`, `filemap`, `view_image`, `diff_state`, and a 16-tool `web_browser` bundle |

**The two-tool designs are not weaker.** SWE-Lancer's original harness had exactly two tools and scored
49 %; vivaria deliberately ships two and pushes richness to the agent author. SWE-agent's elaborate ACI
buys ergonomics, not capability that the terminal lacks.

---

## 8. C5 — What no benchmark in the corpus covers

Derived by intersecting the nine repos against the ordinary content of an on-call rotation:

1. **Alert triage.** No repo hands the agent an alert payload and asks "is this actionable?" AIOpsLab
   comes closest but starts from "a fault has been injected, go look."
2. **Reconciliation across tools** (question F2). Every benchmark has exactly one source of truth.
   Nothing requires joining Jira + Sentry + a status page with conflicting severity conventions.
   TheAgentCompany has four services but tasks rarely require *contradicting* them.
3. **Stale documentation as a hazard** (question D2). Every document handed to an agent here is
   authoritative. Ironically **four of the repos' own READMEs are stale** (§0.1) — the hazard is real
   and entirely unmodelled.
4. **Ambiguity in the request** (question F3). Every instruction is unambiguous by design;
   terminal-bench CI *enforces* it (`scripts_bash/check-test-file-references.sh`,
   `check-task-absolute-path.sh`). No benchmark rewards asking a clarifying question.
   TheAgentCompany is the sole partial exception — some tasks require asking an NPC — but its fake-user
   turn says *"IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP"* (`evaluation/run_eval.py:103-123`).
5. **"I am blocked on a human"** (question B5). Two mechanisms exist and neither is in a benchmark:
   tau-bench's `transfer_to_human_agents` terminate tool — which **always scores 0** — and vivaria's
   `RunPauseReason.HUMAN_INTERVENTION`, which pauses the run **forever** by design
   (`Bouncer.ts:299-315`, `timeout: Infinity`). The *platform* models human handoff correctly; no
   benchmark scores it.
6. **Cost of being wrong.** Every benchmark scores a wrong answer the same as no answer. Nothing models
   a bad deploy costing more than a wasted hour. SWE-Lancer's price weighting is the only gesture at
   business value, and it weights *success*, not *harm*.
7. **Communication as a deliverable.** Only TheAgentCompany grades "did you tell the right person" (via
   RocketChat checkpoints). No postmortem writing, no status update, no incident comms.
8. **Rollback / mitigation under time pressure.** AIOpsLab's 14 mitigation problems are the corpus's
   entire coverage of "make it stop hurting now."
9. **Progress measurement during an episode.** Only vivaria's `intermediate_score` / `ScoreLog`.
   Every benchmark scores once, at the end.

---

## 9. Design recommendations implied by the corpus

1. **Report three numbers, not one:** `resolved`, `model_failed`, `environment_failed`. Implement it as
   vivaria does — a typed `ErrorSource` with an explicit ambiguous value (`serverOrTask`), derived into
   the run status so the taxonomy cannot drift from the metric. Treat a nonzero
   `environment_failed` rate as a bug in your harness.
2. **Run an oracle through the identical path, in CI.** terminal-bench's oracle-must-pass /
   nop-must-fail gate (`.github/workflows/test-tasks.yaml:255-276`) is the cheapest high-value control
   available; commit0 shows it can be a first-class CLI verb (`evaluate-reference`).
3. **Never let the agent declare its own failure source.** vivaria allows `agent` and `task` from the
   agent and rejects everything else (`hooks_routes.ts:356-358`).
4. **Do not charge infrastructure time to the agent.** vivaria's `PYHOOKS_RETRY` and `SCORING` pauses.
5. **Isolate by ordering, not obfuscation.** Copy the grader in *after* the agent stops
   (`terminal_bench/harness/harness.py:544-555`). Then your tests may be static and readable — both
   encryption schemes in this corpus are trivially defeated.
6. **Build a privileged side-channel into the sandbox.** SWE-Lancer's original design — agent requests
   a test run, harness runs it out-of-band, agent sees only the output — is the right answer to
   "reproduction loop without answer key", and terminal-bench had to abandon it purely for lack of a
   privileged user.
7. **Grade state, not trajectory.** tau-bench's re-run-the-gold-actions-and-hash-the-DB approach
   (`tau_bench/envs/base.py:121-164`) accepts any path to the right world state and costs one function.
8. **Use `pass^k`, not `pass@k`,** if the deliverable has to be trustworthy — and pin *every* LLM in the
   loop. tau-bench's unpinned user simulator is the corpus's clearest own-goal; AIOpsLab's pinned,
   cached judge is the fix.
9. **Split partial from full credit explicitly.** TheAgentCompany's `0.5·(r/t) + 0.5·⌊r/t⌋`.
10. **Budget in cost and wall-clock, not steps.** SWE-agent has no `max_steps` at all; vivaria
    generalises to a four-dimensional `RunUsage` with checkpoints that *pause* rather than kill.
11. **Add judgement tasks.** SWE-Lancer manager: 265 of 463 tasks, integer-match grading, zero
    flakiness, and *harder* than the code tasks (47.2 % vs 51.5 %).
12. **Weight tasks by value.** SWE-Lancer's dollar prices are the only link in the corpus between a
    benchmark score and question A2 ("who pays, and for what outcome").
13. **`--depth 1` and `git remote remove origin`,** always, on any task built from a real repo. commit0's
    comment (`commit0/harness/spec.py:117-118`) records that agents were caught exploiting git history.
