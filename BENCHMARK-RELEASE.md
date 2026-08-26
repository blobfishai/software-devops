# DevOpsBench-100 — release notes

**Dataset:** `blobfishai/devopsbench-100` v1.0.0 (built locally; NOT published — no
`harbor publish`, no `hf upload`, no pushes of any kind were run).

DevOpsBench-100 is a 100-task curation of this repository's NovaCart world
(187 tasks total), packaged to CounselBench-100 parity: one official Harbor
schema-1.4 task pack per task, a `dataset.toml` with real per-pack content
digests, and a Hugging Face release tree — all deterministic, stdlib-only,
with no LLM, network, clock, or randomness anywhere in the reward path.

## What was built

```
dist/devopsbench-100/
  harbor/tasks/dob100-NNN-<slug>/   100 self-contained Harbor 1.4 packs
    task.toml                       name = "blobfishai/dob100-NNN-<slug>", [metadata]
                                    benchmark stats, deterministic_verifier = true,
                                    [[environment.mcp_servers]] streamable-http
    instruction.md                  the UNGUIDED ticket (guided variant noted in
                                    metadata, full text in the HF per-task JSON)
    environment/docker-compose.yaml main + world services; DOB_TASK_ID baked in
    environment/Dockerfile          digest-pinned public python:3.12-slim
    environment/world/              server.py + tools.json + tools_combined.py +
                                    environment.db + verify_task.py + spec.json +
                                    Dockerfile (same pinned base; no private registry)
    solution/solve.py|.sh           replays the exact reference trajectory over the
                                    LIVE MCP surface; also asserts no meta-tool leak
    tests/test.sh                   POSTs token-gated /verify, writes
                                    $HARBOR_LOGS|$VERIFIER_LOG_DIR/verifier/
                                    {report.json,reward.json,reward.txt}
  harbor/dataset/dataset.toml       100 [[tasks]] entries with sha256 content
                                    digests (verified equal to harbor's own
                                    Packager.compute_content_hash for all 100)
  huggingface/                      data/tasks.jsonl, tasks/*.json (incl. guided
                                    instruction), world/ source, verifiers/ (100
                                    standalone scripts), trajectories/ (100 executed
                                    oracle JSONLs), reports/, README.md card,
                                    LICENSE-CODE (Apache-2.0), LICENSE-DATA (CC-BY-4.0)
  reports/{build,qualification}.json
```

Committed sources: `benchmark/devopsbench100/{curate.py,catalog.json,builder.py,
run_suite.py,runtime/server.py,reports/}`. The `dist/` tree is build output
(gitignored, reproducible bit-for-bit from the committed sources).

### Security model (CounselBench capability-token pattern)

`verification_token(bench_id) = sha256("DevOpsBench-100 verifier capability::" + bench_id)`.
The world image stores only the token's sha256 digest (`spec.json`); the token
itself appears only in `tests/test.sh`, which Harbor runs outside the agent
container. A wrong/missing token gets a 404. The agent-facing MCP surface
serves the 97 world tools ONLY — the upstream blobfish meta-tools
(`task_start`/`task_verify`/`task_list`/`episode_abort`/`world_info`) are not
reachable, so there is no agent-facing verify/solution/free-reward surface.
`solve.py` asserts this on every run.

## Curation (committed as benchmark/devopsbench100/catalog.json)

All 187 candidates were MEASURED (oracle replay + pristine + applicable
adversaries; `reports/curation-measurements.json`): 187/187 oracle-pass,
185/187 fully control-clean. The two exceptions
(`tsk_rcn_checkout_error_rate`, `tsk_rcn_distinct_checkout_bugs`) accept the
`wrong_source` adversary and were excluded. Selection rules: every one of the
19 categories represented; the 14 flagship families shipped whole (incl. all
judgement/restraint, human_gated, horizon, handover, workspace,
code_implementation tasks); diagnostic families sampled hardest-first with
`aiops_detection` capped at 5 (well under the ~15 ceiling, so breadth-wave
permutations do not crowd out depth); curated preferred over wave-generated;
harder difficulty and longer reference trajectories preferred. Result: 38
expert / 31 hard / 29 medium / 2 easy; reference trajectories 4–34 calls
(median 13, 1,318 total); 0 duplicate prompts.

## Measured qualification (all numbers from executed runs in this session)

`python3 benchmark/devopsbench100/run_suite.py` — 371 episodes executed
against the PACK's own world code (`reports/qualification.json`):

| Gate | Result |
|---|---|
| Oracle replay, reward 1.0 | **100/100** |
| Determinism (2nd pristine replay, reports exactly identical) | **100/100** |
| Wrong-token /verify rejection | **100/100** |
| Negative control: pristine world | **0/100 false accepts** |
| Negative control: naive (policy-blind) | **0/53 false accepts** (53 applicable) |
| Negative control: shortcut | **0/7 false accepts** (7 applicable) |
| Negative control: wrong_source | **0/11 false accepts** (11 applicable) |

A negative control counts as applicable exactly the way
`tests/test_eval_harness.py` defines it: only when it actually perturbs the
procedure-relevant reference steps (naive/shortcut) or when the task pins a
source of truth (wrong_source). The pristine control applies to all 100.

Repo gates at head (this branch):

- `harbor_selftest.py` full sweep: **187/187** verifiers accept the reference
  solution and reject an untouched world; failures 0, missing 0, free-reward 0.
- `python3 -m pytest tests/ -q`: **112 passed, 3 failed** — all three failures
  (`test_terminal_adapter_enumerates_and_parses`,
  `test_the_corpus_map_is_generated_not_hand_written`,
  `test_the_parity_report_does_not_drift_from_the_generated_corpus_map`) are
  missing-corpus-clone failures ("expected terminal-bench tasks on disk,
  found 0"): they require the 57 cloned third-party benchmark repos, which
  this fresh clone does not carry. They touch nothing in the world, tasks,
  verifiers, or this release, and are unaffected by this branch's commits.
- Dataset digests: all 100 `dataset.toml` digests re-verified equal to
  harbor v0.21.0's own `Packager.compute_content_hash`.

Dockerized Harbor probe (harbor 0.21.0, Docker/Colima, run from
`~/.cache/bf-audit/devopsbench/`): **2/2 oracle trials passed with reward
1.0, 0 errored trials** (`dob100-049-payments-retry`: 19/19 reference calls
over live MCP, verifier report 7/7 correctness + 4/4 deployment + 7/7
quality; `dob100-001-rca-analytics-egress-blocked`: passed 1.0). test.sh
wrote `verifier/report.json`, `reward.json`, and `reward.txt` into the
Harbor logs directory in both trials.

`finalize.py` sealed `release-manifest.json`: 2,015 files, manifest sha256
`9e2b0c33018dbe1601c3add67d98916caaf1a9537da22719571c0a7d2da37b4e`.

## Reproduce

```bash
# 1. re-measure + re-curate (rewrites catalog.json deterministically)
python3 benchmark/devopsbench100/curate.py

# 2. build the release tree
python3 benchmark/devopsbench100/builder.py            # -> dist/devopsbench-100

# 3. qualification (oracle x2, token gate, negative controls, trajectories)
python3 benchmark/devopsbench100/run_suite.py

# 4. repo gates
python3 -m pytest tests/ -q
python3 harbor_selftest.py

# 5. seal the manifest
python3 benchmark/devopsbench100/finalize.py

# 6. dockerized probe (any pack; run from a $HOME-mounted path under Colima)
cd ~/.cache/bf-audit/devopsbench
harbor run -p tasks/dob100-049-payments-retry -a oracle -o jobs -q -y
```

## Honest caveats

- **Dockerized probe covers 2 packs, not 100.** The full 100-pack oracle +
  determinism + negative-control sweep ran in-process against the pack world
  code (the same files the containers run); only 2 packs were additionally
  proven through the full `harbor run` Docker path.
- **Shared world, non-isolated knowledge.** All 100 packs bake the same
  NovaCart database. An agent that memorizes the world across tasks is not
  prevented by pack isolation (each trial does start from the pristine seed).
- **Negative-control applicability is per-task.** naive/shortcut/wrong_source
  are only adversarial where they differ from the reference procedure
  (53/7/11 of 100 respectively); the pristine control covers all 100. Tasks
  where a control degenerates to the oracle are not counted as rejections.
- **Wave-generated tasks are included** where they out-rank curated ones on
  the depth criteria: 6 of 100 tasks have `tsk_w*` ids (answers derived from
  the built DB by build/waves.py); 84 are hand-curated and 10 are ports.
  Tagged per task in `catalog.json`.
- **Repo pytest is 112/115** on this branch; the 3 failures are
  corpus-clone-dependent (details above), not world or verifier failures.
- **30 cross_system/handover tasks are ports** of TheAgentCompany task
  *shapes*, re-grounded on NovaCart state (8 cross_system + 2 handover
  selected); AIOps families reproduce microsoft/AIOpsLab task structure. No
  third-party text or gold answers ship in the release.
- **Determinism is report-level.** The two oracle replays produce byte-identical
  verifier reports; the SQLite files themselves may differ in
  non-semantic bytes (free pages, timestamps written by tools) and are not
  compared.
- **`verify` reports include tool-call counters** (successful/failed calls),
  which are deterministic for scripted replays but will naturally vary for
  live agents; the reward is unaffected.
- **Nothing was published.** Harbor org/dataset names are prepared
  (`blobfishai/devopsbench-100`) but no registry, hub, HF, or git push was
  performed from this session.
