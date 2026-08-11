# commit-0/commit0

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/commit-0__commit0/`

All relative paths below are rooted at that directory. Clone state: `README.md:1-3`
carries an "Updates — Sep 28, 2024" note, so this is a late-2024/2025 checkout.

**One-line characterisation:** commit0 inverts SWE-bench. Instead of "here is a repo
and a bug, emit a small patch", it is "here is a repo with **every function body
deleted**, rewrite the whole library from its docstrings and make ~1–40 000 unit tests
pass." It is the corpus's only *from-scratch synthesis* benchmark, and the only one
whose primary metric is **continuous (fraction of tests passing)** rather than binary.

---

## 1. Task taxonomy (C1, C2, C3, C4)

### The core claim

`README.md:22`:

> The benchmark consists of **57 core Python libraries**. The challenge is to rebuild
> these libraries and pass their unit tests. All libraries have:
>
> * Significant test coverage
> * Detailed specification and documentation
> * Lint and type checking

**Note a real discrepancy:** the prose says 57, but the code says **56**. Verified by
importing the constants module:

```
$ python3 -c "from commit0.harness.constants import SPLIT_ALL, SPLIT_LITE; print(len(SPLIT_ALL), len(SPLIT_LITE))"
56 16
```

`commit0/harness/constants.py:105-162` defines `SPLIT_ALL` (56 entries) and
`commit0/harness/constants.py:87-104` defines `SPLIT_LITE` (16 entries, a strict
subset). The shipped test-ID data agrees with 56:

```
$ ls commit0/data/test_ids | grep -v '__' | wc -l
56
```

So: **56 repos in `all`, 16 in `lite`.** Treat "57" in the README as stale prose.

### `SPLIT_LITE` — the 16-repo working set

`commit0/harness/constants.py:87-104`, verbatim:

```python
SPLIT_LITE = [
    "tinydb",
    "simpy",
    "deprecated",
    "wcwidth",
    "voluptuous",
    "cachetools",
    "imapclient",
    "marshmallow",
    "jinja",
    "cookiecutter",
    "portalocker",
    "parsel",
    "pyjwt",
    "chardet",
    "babel",
    "minitorch",
]
```

### `SPLIT_ALL` — the 56 repos

`commit0/harness/constants.py:105-162`. The full list (order as in source):

`statsmodels, python-progressbar, xarray, imbalanced-learn, web3.py, scrapy, seaborn,
pypdf, pexpect, pytest, pylint, joblib, dulwich, virtualenv, minitorch, networkx,
requests, sphinx, jedi, moviepy, loguru, paramiko, geopandas, bitstring, fastapi,
chardet, tornado, python-prompt-toolkit, attrs, PyBoy, pydantic, filesystem_spec,
tlslite-ng, graphene, mimesis, babel, dnspython, portalocker, cookiecutter, pyjwt,
python-rsa, more-itertools, simpy, click, fabric, jinja, flask, sqlparse, marshmallow,
imapclient, tinydb, cachetools, voluptuous, parsel, wcwidth, deprecated`

Every repo is *also* addressable as its own split
(`commit0/harness/constants.py:163-218` defines `SPLIT_<REPO>` constants;
`:220-279` assembles the `SPLIT` dict with 58 keys = 56 repos + `all` + `lite`).

### A second, hidden task family: SWE-bench and "simple" benchmarks

commit0 is not one benchmark; the harness dispatches on dataset name to **three**
`Spec` subclasses (`commit0/harness/spec.py:335-365`):

```python
def make_spec(
    instance: Union[RepoInstance, SimpleInstance], dataset_type: str, absolute: bool
) -> Spec:
    ...
    if dataset_type == "commit0":
        return Commit0Spec(...)
    elif dataset_type == "swebench":
        return SWEBenchSpec(...)
    elif dataset_type == "simple":
        return SimpleSpec(...)
    else:
        raise NotImplementedError(
            f"{dataset_type} is not supported.\nWe only support commit0 and swebench instances for now."
        )
```

Dataset-type detection (`commit0/harness/run_pytest_ids.py:64-77`):

```python
if "swe" in dataset_name:
    repo_name = example["instance_id"]
    dataset_type = "swebench"
elif (
    "humaneval" in dataset_name
    or "mbpp" in dataset_name
    or "bigcodebench" in dataset_name
    or "codecontests" in dataset_name
):
    repo_name = example["instance_id"]
    dataset_type = "simple"
else:
    repo_name = example["repo"].split("/")[-1]
    dataset_type = "commit0"
```

So commit0 the *harness* also runs SWE-bench, HumanEval, MBPP, BigCodeBench and
CodeContests. And the SWE-bench instances are shipped:

```
$ ls commit0/data/test_ids | grep '__' | wc -l
1000        # = 500 instances x {fail_to_pass, pass_to_pass}
```
e.g. `commit0/data/test_ids/astropy__astropy-12907#fail_to_pass.bz2`. 500 instances
is the size of SWE-bench Verified.

**C4 relevance:** commit0 is the clearest evidence in this corpus that *"run pytest in
a container and diff the pass set"* is the domain's consensus verification substrate —
one harness serves five different benchmarks with the same machinery.

### C2 — how long is a task?

Very long, and the repo quantifies it. `docs/table.md` lists per-library test counts.
Computed from that file:

```
repos listed:  54
total tests:   138,479
top:  web3.py 40,433 | statsmodels 17,669 | xarray 15,643 | mimesis 6,159 |
      babel 5,663 | networkx 5,440 | pydantic 5,091 | jedi 3,854
bottom: simpy 140 | moviepy 109 | python-rsa 86 | wcwidth 38 | portalocker 38
```

The harness hard-codes its own totals (`docs/render_submissions.py:189-192`):

```python
split_to_total_tests = {
    "lite": 3628,
    "all": 140926,
}  # hard-coded to skip running it later
```

**Three orders of magnitude of variance in a single benchmark** (38 tests for
`portalocker` vs 40 433 for `web3.py`). That is a task-length distribution no other
repo in this corpus matches.

Files touched: the agent must edit **every source file containing a stubbed function**.
The file-selection heuristic is `agent/agent_utils.py:166-193`:

```python
def _find_files_to_edit(base_dir: str, src_dir: str, test_dir: str) -> list[str]:
    """Identify files to remove content by heuristics.
    We assume source code is under [lib]/[lib] or [lib]/src.
    We exclude test code. ...
    """
    files = collect_python_files(os.path.join(base_dir, src_dir))
    test_files = collect_test_files(os.path.join(base_dir, test_dir))
    files = list(set(files) - set(test_files))

    # don't edit __init__ files
    files = [f for f in files if "__init__" not in f]
    # don't edit __main__ files
    files = [f for f in files if "__main__" not in f]
    # don't edit confest.py files
    files = [f for f in files if "conftest.py" not in f]
    return files
```

and files are then filtered to those literally containing a `pass` stub, skipping
anything over 1500 lines (`agent/agent_utils.py:244-251`):

```python
for file_path in files:
    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as file:
        content = file.read()
        if len(content.splitlines()) > 1500:
            continue
        if "    pass" in content:
            filtered_files.append(file_path)
```

Timeout defaults are **1800 s (30 min) per repo** for both `test` and `evaluate`
(`README.md`, the `--timeout` rows of the Test and Evaluate option tables).

### C3 — single-shot vs long-horizon

**Long-horizon, and explicitly iterative.** `agent/configs/base.yaml:19` sets
`max_iteration: 3`, mapped onto Aider's reflection loop
(`agent/agents.py:135`):

```python
coder.max_reflections = self.max_iteration
```

The agent can be configured to run tests and lint *between* iterations and feed the
errors back (`agent/agents.py:92-99, 139-146`):

```python
if test_cmd:
    auto_test = True
...
if test_first:
    test_errors = coder.commands.cmd_test(test_cmd)
    if test_errors:
        coder.run(test_errors)
elif lint_first:
    coder.commands.cmd_lint(fnames=fnames)
else:
    coder.run(message)
```

Crucially, files are processed in **topological dependency order** — the agent writes
leaf modules before the modules that import them
(`agent/agent_utils.py:212-230`):

```python
def topological_sort_based_on_dependencies(
    pkg_paths: list[str],
) -> tuple[list[str], dict]:
    """Topological sort based on dependencies."""
    module_set = ModuleSet([str(p) for p in pkg_paths])
    ...
    import_dependencies_files = ignore_cycles(import_dependencies)
    return import_dependencies_files, import_dependencies
```

with an explicit cycle-breaking fallback (`agent/agent_utils.py:196-209`):

```python
def ignore_cycles(graph: dict) -> list[str]:
    """Ignore the cycles in the graph."""
    ts = TopologicalSorter(graph)
    try:
        return list(ts.static_order())
    except CycleError as e:
        # ... remove the first node in the cycle and try again.
        cycle_nodes = e.args[1]
        node_to_remove = cycle_nodes[0]
        graph.pop(node_to_remove, None)
        return ignore_cycles(graph)
```

This is a genuinely interesting design idea: **the benchmark author supplies the task
*ordering*, not just the task.** Worth stealing for multi-step task design.

---

## 2. Task definition schema (C6)

### The instance record — verbatim

`commit0/harness/constants.py:7-22`:

```python
class RepoInstance(BaseModel):
    instance_id: str
    repo: str
    base_commit: str
    reference_commit: str
    setup: dict
    test: Dict[str, str]
    src_dir: str

    def __getitem__(self, item: str):
        return getattr(self, item)

    def keys(self) -> KeysView[str]:
        """Return the field names of the model as dictionary keys."""
        return self.__annotations__.keys()
```

Contrast with SWE-bench's instance: there is **no `problem_statement` field and no
`patch` field**. The task is defined entirely by *two commits*:

- `base_commit` — the **stubbed** repo (all bodies removed)
- `reference_commit` — the **complete** repo (the gold implementation)

and by `test`, a dict carrying `test_dir` and `test_cmd`
(used at `commit0/harness/spec.py:181` and `commit0/harness/evaluate.py:53,64`).

The lightweight variant, for HumanEval/MBPP-style datasets
(`commit0/harness/constants.py:24-35`):

```python
class SimpleInstance(BaseModel):
    instance_id: str
    prompt: str
    canonical_solution: str
    test: str
```

### Test-status vocabulary

`commit0/harness/constants.py:61-64` — the same four SWE-bench-style transition
buckets:

```python
FAIL_TO_PASS = "FAIL_TO_PASS"
FAIL_TO_FAIL = "FAIL_TO_FAIL"
PASS_TO_PASS = "PASS_TO_PASS"
PASS_TO_FAIL = "PASS_TO_FAIL"
```

`commit0/harness/constants.py:288-294`:

```python
class TestStatus(Enum):
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    XFAIL = "XFAIL"
```

**The `ResolvedStatus` enum is the important one** —
`commit0/harness/constants.py:282-285`:

```python
class ResolvedStatus(Enum):
    NO = "RESOLVED_NO"
    PARTIAL = "RESOLVED_PARTIAL"
    FULL = "RESOLVED_FULL"
```

A **`PARTIAL` state exists**, which SWE-bench's binary resolution does not have.

### Test IDs are shipped, not derived

`commit0/harness/get_pytest_ids.py:13-27`:

```python
def main(repo: str, verbose: int) -> List[List[str]]:
    repo = repo.lower()
    repo = repo.replace(".", "-")
    commit0_path = os.path.dirname(commit0.__file__)
    if "__" in repo:
        in_file_fail = read(f"{commit0_path}/data/test_ids/{repo}#fail_to_pass.bz2")
        in_file_pass = read(f"{commit0_path}/data/test_ids/{repo}#pass_to_pass.bz2")
    else:
        in_file_fail = read(f"{commit0_path}/data/test_ids/{repo}.bz2")
        in_file_pass = ""
    out = [in_file_fail, in_file_pass]
```

For commit0 repos there is only a `fail_to_pass` set (everything fails on a stubbed
repo, so `pass_to_pass` is empty) — a neat consequence of the from-scratch framing.
Example content:

```
$ python3 -c "import bz2; print(bz2.open('commit0/data/test_ids/tinydb.bz2','rt').read())" | head -5
tests/test_middlewares.py::test_caching
tests/test_middlewares.py::test_caching_read
tests/test_middlewares.py::test_caching_write_many
tests/test_middlewares.py::test_caching_flush
tests/test_middlewares.py::test_caching_flush_manually
```
(201 test IDs for tinydb.)

### Definition of done — state-based, and *graded*

Two distinct definitions coexist:

1. **Continuous (the headline metric):** fraction of the repo's tests that pass.
   `commit0/harness/evaluate.py:139`:
   ```python
   passed = (status["passed"] + status["xfail"]) / sum(status.values())
   ```
2. **Binary "resolved" (for the leaderboard's repo count):**
   `docs/render_submissions.py:291-303`:
   ```python
   resolved = False
   if "passed" in pytest_info["summary"]:
       if "skipped" in pytest_info["summary"]:
           resolved = (
               pytest_info["summary"]["passed"]
               + pytest_info["summary"]["skipped"]
               == pytest_info["summary"]["total"]
           )
       else:
           resolved = (
               pytest_info["summary"]["passed"]
               == pytest_info["summary"]["total"]
           )
   ```
   i.e. resolved ⇔ *every* test passes (skips forgiven).

Both are **purely state-based test execution**. **There is no LLM judge anywhere in
commit0** — no judge prompt, no model call in the harness. Verification is `pytest`
plus a JSON report, full stop.

There is a **third, non-test** notion of done: **lint and type-check must also pass**
(§4).

---

## 3. Input documents / agent context (D1, D3)

commit0 is unusual in that **the context is configurable along six axes**, and the
paper's ablation surface is visible in the config. `agent/class_types.py:4-24`:

```python
@dataclass
class AgentConfig:
    agent_name: str
    model_name: str
    use_user_prompt: bool
    user_prompt: str
    use_topo_sort_dependencies: bool
    add_import_module_to_context: bool
    use_repo_info: bool
    max_repo_info_length: int
    use_unit_tests_info: bool
    max_unit_tests_info_length: int
    use_spec_info: bool
    max_spec_info_length: int
    use_lint_info: bool
    run_entire_dir_lint: bool
    max_lint_info_length: int
    pre_commit_config_path: str
    run_tests: bool
    max_iteration: int
    record_test_for_each_commit: bool
```

### The context blocks, verbatim

`agent/agent_utils.py:15-21` — the section headers that structure the prompt:

```python
PROMPT_HEADER = ">>> Here is the Task:\n"
REFERENCE_HEADER = "\n\n>>> Here is the Reference for you to finish the task:\n"
REPO_INFO_HEADER = "\n\n>>> Here is the Repository Information:\n"
UNIT_TESTS_INFO_HEADER = "\n\n>>> Here are the Unit Tests Information:\n"
LINT_INFO_HEADER = "\n\n>>> Here is the Lint Information:\n"
SPEC_INFO_HEADER = "\n\n>>> Here is the Specification Information:\n"
IMPORT_DEPENDENCIES_HEADER = "\n\n>>> Here are the Import Dependencies:\n"
```

### The default task prompt — verbatim

`agent/configs/base.yaml:8`:

```yaml
user_prompt: "Here is your task:\nYou need to implement all functions with 'NotImplementedError('IMPLEMENT ME HERE')' and pass the unit tests.\nDo not change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.\nWhen you generate code, you must maintain the original formatting of the function stubs (such as whitespaces), otherwise we will not able to search/replace blocks for code modifications, and therefore you will receive a score of 0 for your generated code."
```

Three separate instructions worth noting:
- what to do: *"implement all functions with `NotImplementedError('IMPLEMENT ME HERE')`"*
- an **anti-cheat constraint**: *"Do not change the names of existing functions or
  classes, as they may be referenced from ... unit tests"*
- a **scaffold constraint with a stated penalty**: maintain whitespace *"otherwise ...
  you will receive a score of 0"*

Full default config, `agent/configs/base.yaml:4-19`:

```yaml
agent_config:
  agent_name: "aider"
  model_name: "claude-3-5-sonnet-20240620"
  use_user_prompt: false
  user_prompt: "..."
  use_repo_info: false
  use_unit_tests_info: false
  use_spec_info: false
  use_lint_info: false
  pre_commit_config_path: .pre-commit-config.yaml
  run_tests: True
  max_repo_info_length: 10000
  max_unit_tests_info_length: 10000
  max_spec_info_length: 10000
  max_lint_info_length: 10000
  max_iteration: 3
```

and the shipped override, `agent/configs/agent.yaml:6-13`:

```yaml
agent_config:
  use_user_prompt: false
  use_repo_info: false
  use_unit_tests_info: false
  use_spec_info: false
  use_lint_info: true
  pre_commit_config_path: .pre-commit-config.yaml
  run_tests: false
```

### Assembly

`agent/agent_utils.py:346-397`:

```python
def get_message(
    agent_config: AgentConfig,
    repo_path: str,
    test_files: list[str] | None = None,
) -> str:
    """Get the message to Aider."""
    prompt = f"{PROMPT_HEADER}" + agent_config.user_prompt

    if agent_config.use_unit_tests_info and test_files:
        unit_tests_info = f"\n{UNIT_TESTS_INFO_HEADER} "
        for test_file in test_files:
            unit_tests_info += get_file_info(
                file_path=Path(os.path.join(repo_path, test_file)), prefix=""
            )
        unit_tests_info = unit_tests_info[: agent_config.max_unit_tests_info_length]
    else:
        unit_tests_info = ""

    # TODO: assuming we have specification, which we currently do not have
    if agent_config.use_repo_info:
        repo_info = (
            f"\n{REPO_INFO_HEADER} "
            + get_dir_info(
                dir_path=Path(repo_path), prefix="", max_depth=2, include_stubs=False
            )[: agent_config.max_repo_info_length]
        )
    else:
        repo_info = ""

    if agent_config.use_spec_info:
        with bz2.open("spec.pdf.bz2", "rb") as in_file:
            with open("spec.pdf", "wb") as out_file:
                out_file.write(in_file.read())
        spec_info = (
            f"\n{SPEC_INFO_HEADER} "
            + get_specification(specification_pdf_path=Path(repo_path, "spec.pdf"))[
                : agent_config.max_spec_info_length
            ]
        )
    else:
        spec_info = ""

    message_to_agent = prompt + repo_info + unit_tests_info + spec_info

    return message_to_agent
```

### D1/D3 — the input document types, concretely

This is the most directly relevant part of commit0 for question D1. The agent can be
handed:

| Context type | How it is produced | Citation |
|---|---|---|
| **Repo tree** (depth-2 directory listing, optionally with function stubs inline) | `get_dir_info()` | `agent/agent_utils.py:64-114` |
| **Function stubs with type hints** — extracted by regex, not AST | `extract_function_stubs()` | `agent/agent_utils.py:30-61` |
| **Unit-test signatures** (test file stubs, not bodies) | `get_file_info()` | `agent/agent_utils.py:117-123` |
| **The library's PDF specification** — the real ReadTheDocs PDF, text-extracted with PyMuPDF | `get_specification()` | `agent/agent_utils.py:414-426` |
| **Lint output** from a pre-commit run (ruff + pyright) | `get_lint_cmd()` | `agent/agent_utils.py:537-559` |
| **Import dependencies** — full source of each already-written dependency module | `update_message_with_dependencies()` | `agent/agent_utils.py:400-411` |

**The PDF spec is a standout.** `docs/table.md` links each library to its official
documentation PDF (e.g. `https://tinydb.readthedocs.io/_/downloads/en/v4.8.0/pdf/`),
and the harness extracts text page-by-page:

```python
def get_specification(specification_pdf_path: Path) -> str:
    """Get the reference for a given specification PDF path."""
    # TODO: after pdf_to_text is available, use it to extract the text from the PDF
    document = fitz.open(specification_pdf_path)
    text = ""
    for page_num in range(len(document)):
        page = document.load_page(page_num)  # loads the specified page
        text += page.get_text()  # type: ignore
    return text
```
(`agent/agent_utils.py:414-426`)

This is the only benchmark in the corpus that feeds the agent a **real, human-authored
specification document** as first-class task context — exactly the "design docs / API
specs" category from question D1. The `max_spec_info_length: 10000` cap
(`agent/configs/base.yaml:17`) means the spec is *truncated*, which is itself a
realistic hazard.

Dependency injection is full-source, not summaries
(`agent/agent_utils.py:400-411`):

```python
def update_message_with_dependencies(message: str, dependencies: list[str]) -> str:
    """Update the message with the dependencies."""
    if len(dependencies) == 0:
        return message
    import_dependencies_info = f"\n{IMPORT_DEPENDENCIES_HEADER}"
    for dependency in dependencies:
        with open(dependency, "r") as file:
            import_dependencies_info += (
                f"\nHere is the content of the file {dependency}:\n{file.read()}"
            )
    message += import_dependencies_info
    return message
```

---

## 4. Verification (G1, G4, G5)

### Mechanism: Docker/Modal/E2B + pytest + JSON report

Three interchangeable execution backends (`commit0/harness/constants.py:66-71`):

```python
# Evaluation backends
EVAL_BACKENDS = ["local", "modal", "e2b"]
# Use absolute for docker and modal. Backends with sudo access
ABSOLUTE_REPO_DIR = "/testbed"
# Use relative for e2b, with no sudo access
RELATIVE_REPO_DIR = "testbed"
```

implemented in `commit0/harness/execution_context.py` (classes `Docker`, `Modal`,
`E2B`, imported at `commit0/harness/run_pytest_ids.py:25-30`).

The eval script itself, `commit0/harness/spec.py:172-184`:

```python
def make_eval_script_list(self) -> list[str]:
    """Run the tests."""
    diff_path = "/patch.diff" if self.absolute else "../patch.diff"
    eval_script_list = [
        f"cd {self.repo_directory}",
        "source .venv/bin/activate",
        f"git reset --hard {self.instance['base_commit']}",
        f"git apply --allow-empty -v {diff_path}",
        "git status",
        f"{self.instance['test']['test_cmd']} --json-report --json-report-file=report.json --continue-on-collection-errors{{coverage}} {{test_ids}} > test_output.txt 2>&1",
        "echo $? > pytest_exit_code.txt",
    ]
    return eval_script_list
```

Note three deliberate choices:
- **`git reset --hard {base_commit}` before applying** — the agent's work is
  reconstituted as a patch onto a *pristine stub state*, so nothing the agent did to
  the working tree outside its diff survives.
- **`--continue-on-collection-errors`** — a single unimportable module must not zero
  the whole repo's score. This is a partial-credit-preserving choice.
- **`echo $? > pytest_exit_code.txt`** — the exit code is captured separately from the
  log, so "pytest crashed" is distinguishable from "tests failed".

Also note `commit0/harness/spec.py:36-43`:

```python
@property
def eval_script(self) -> str:
    self.eval_script_list = self.make_eval_script_list()
    return (
        "\n".join(["#!/bin/bash", "set -uxo pipefail"] + self.eval_script_list)
        + "\n"
    )
    # Don't exit early because we need to revert tests at the end
```

`set -uxo pipefail` **without `-e`** — deliberately not fail-fast, with the reason
stated in the comment. Compare the setup script at `:28-34`, which *does* use
`set -euxo pipefail`. Setup failing is fatal; grading failing is not.

### Scoring: per-test-ID lookup into the JSON report

`commit0/harness/evaluate.py:109-148` — the whole grading function:

```python
with open(report_file, "r") as file:
    report = json.load(file)
# new version of pytest json
if "created" in report:
    tests = {x["nodeid"]: x["call"] for x in report["tests"] if "call" in x}
# old version of pytest json
else:
    tests = {
        x["nodeid"]: {"outcome": x["outcome"], "duration": x["duration"]}
        for x in report
        if x["when"] == "call"
    }
status = []
runtimes = []
no_runs = 0
for test_id in test_ids:
    if test_id in tests and tests[test_id] is not None:
        status.append(tests[test_id]["outcome"])
        runtimes.append(tests[test_id]["duration"])
        no_runs += 1
    else:
        status.append("failed")
        runtimes.append(0)
status = Counter(status)
if no_runs == 0:
    total = 0
else:
    total = sum(runtimes)
if "xfail" not in status:
    status["xfail"] = 0
passed = (status["passed"] + status["xfail"]) / sum(status.values())
```

**Key G5 observation — and a criticism.** Line 130: a test ID that is *absent from the
report* is scored `"failed"`, not "errored" or "not run". So a container that crashed,
a collection error, or an OOM is silently scored as **model failure**. The only
protection is a missing-report branch at `commit0/harness/evaluate.py:98-108`, which
also records zero:

```python
if not os.path.exists(report_file):
    out.append(
        {
            "name": name,
            "sum": 0,
            "passed": 0,
            "num_passed": 0,
            "num_tests": len(test_ids),
        }
    )
    continue
```

**commit0 does not separate environment failure from model failure at the run level.**
Both collapse to a score of 0. This is the weakest G5 story in the corpus and is worth
citing as a negative example. The only place the distinction survives is the
submission renderer, which carries a `failed_to_run` marker
(`docs/render_submissions.py:278-289`):

```python
if "failed_to_run" in pytest_info:
    resolved = False
    if write_submission:
        submission_repo_page += (
            f"\n## Failed to run pytests for test `{pytest_group}`\n"
            f"```\n{pytest_info['failed_to_run']}\n```"
        )
        pytest_details = "Pytest failed"
        duration = "Failed."
    evaluate_numbers.append(0.0)
```
— i.e. it is *displayed* differently but still **scored 0.0**.

The build/eval pipeline does have a distinct error type
(`commit0/harness/utils.py:16-28`):

```python
class EvaluationError(Exception):
    def __init__(self, repo: str, message: str, logger: logging.Logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.repo = repo
        self.log_file = ""  # logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.repo}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )
```

and the log sentinels distinguish install/test/timeout outcomes
(`commit0/harness/constants.py:296-304`):

```python
INSTALL_FAIL = ">>>>> Init Failed"
INSTALL_PASS = ">>>>> Init Succeeded"
INSTALL_TIMEOUT = ">>>>> Init Timed Out"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"
```

These eight sentinels *are* a proper taxonomy — they just do not reach the score.

### G4 — reward-hacking guards (commit0's best contribution)

**1. Shallow clone to hide the answer.** This is the standout guard, and the comment
says exactly why. `commit0/harness/spec.py:116-130`:

```python
setup_commands = [
    # Use --depth 1 for shallow clone to prevent agents from accessing
    # git history and exploiting it to retrieve original implementations
    f"git clone --depth 1 -o origin https://github.com/{repo} {self.repo_directory}",
    f"chmod -R 777 {self.repo_directory}",  # So nonroot user can run tests
    f"cd {self.repo_directory}",
    # Fetch both commits needed: env_setup_commit for setup and base_commit for later reset
    f"git fetch --depth 1 origin {env_setup_commit} {base_commit}",
    f"git reset --hard {env_setup_commit}",
    # Remove the remote so the agent won't see newer commits.
    "git remote remove origin",
    f"uv venv --python {specs['python']}",
    "source .venv/bin/activate",
    "which python",
]
```

Two distinct attacks are closed here:
- `--depth 1` → the agent cannot `git log` its way to the original implementation.
- `git remote remove origin` → the agent cannot `git fetch` the upstream fix.

The identical pair appears in `SWEBenchSpec` too
(`commit0/harness/spec.py:226-234`), with the same comments.

**2. Name-stability constraint in the prompt** — the agent is told not to rename
functions/classes because tests reference them (`agent/configs/base.yaml:8`).

**3. Test files are excluded from the editable set** — `_find_files_to_edit` subtracts
`collect_test_files(test_dir)` and drops `conftest.py`
(`agent/agent_utils.py:183-192`). The agent is never handed a test file to edit.

**4. Reset before grading** — `git reset --hard {base_commit}` then apply the diff
(`commit0/harness/spec.py:178-179`), so only the diff counts.

**5. Lint + type-check as an independent gate.** `commit0/harness/lint.py:13-34`
embeds a fixed pre-commit config:

```python
config = """repos:
# Standard hooks
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.3.0
  hooks:
  - id: check-case-conflict
  - id: mixed-line-ending

- repo: https://github.com/astral-sh/ruff-pre-commit
  # Ruff version.
  rev: v0.6.1
  hooks:
    # Run the linter.
    - id: ruff
      args: [ --fix ]
    # Run the formatter.
    - id: ruff-format

- repo: https://github.com/RobertCraigie/pyright-python
  rev: v1.1.376
  hooks:
    - id: pyright"""
```

executed as (`commit0/harness/lint.py:74-81`):

```python
config_file = Path(".commit0.pre-commit-config.yaml")
if not config_file.is_file():
    config_file.write_text(config)
command = ["pre-commit", "run", "--config", config_file, "--files"] + files
try:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    print(result.stdout)
    sys.exit(result.returncode)
```

**Pinned versions** (`ruff v0.6.1`, `pyright v1.1.376`, `pre-commit-hooks v4.3.0`) —
determinism by version pinning. `README.md:26` lists "Lint and type checking" as a
first-class property of every library. This is the corpus's only benchmark with a
*static-analysis* gate alongside tests.

### What is NOT guarded

- The agent runs `pytest` locally with the **same tests** used for grading
  (`run_tests: True` in `agent/configs/base.yaml:14`). Test-set visibility is by
  design — commit0 treats the tests as part of the spec. Contrast terminal-bench and
  SWE-Lancer, which hide them.
- Nothing prevents the agent from writing code that special-cases test inputs.
- Nothing detects `pip install <the-real-library>`. The venv is agent-writable and the
  shallow clone guard does not cover PyPI.

---

## 5. Flakiness and nondeterminism (G2)

commit0's approach is **structural determinism** rather than retries. Evidence:

1. **Content-addressed images.** The Docker image key is a hash of the setup script
   (`commit0/harness/spec.py:50-63`):
   ```python
   @property
   def repo_image_key(self) -> str:
       """The key for the environment image is based on the hash of the environment script list.
       If the environment script list changes, the image will be rebuilt automatically.

       Note that old images are not automatically deleted, so consider cleaning up old images periodically.
       """
       hash_object = hashlib.sha256()
       hash_object.update(str(self.setup_script).encode("utf-8"))
       hash_value = hash_object.hexdigest()
       val = hash_value[:22]  # 22 characters is still very likely to be unique
       repo = self.repo.split("/")[-1].split("__")[-1].split("-")[0]
       return f"commit0.repo.{repo}.{val}:v0".lower()
   ```
   Change the setup, get a new image automatically. No stale-environment class of bug.

2. **Pinned platform** (`commit0/harness/spec.py:93-95`):
   ```python
   @property
   def platform(self) -> str:
       return "linux/x86_64"
   ```

3. **Pinned linter/type-checker versions** (`commit0/harness/lint.py:13-34`).

4. **`--continue-on-collection-errors`** (`commit0/harness/spec.py:181`) so one broken
   import does not cascade.

5. **Handles two pytest-json-report schema versions** — an explicit robustness measure
   (`commit0/harness/evaluate.py:111-120`):
   ```python
   # new version of pytest json
   if "created" in report:
       ...
   # old version of pytest json
   else:
       ...
   ```

6. **Long timeouts** — 1800 s default for both `test` and `evaluate` (`README.md`
   option tables), plus `--num-cpus` and `--num-workers` knobs.

7. **Cycle-tolerant topological sort** (`agent/agent_utils.py:196-209`) so dependency
   ordering never crashes on a real-world import cycle.

8. **Retries are delegated to the agent, not the harness.** `docs/agent.md:44-45`:
   > * Aider automatically retries certain API errors. ...
   > * When increasing `--max-parallel-repos`, be mindful of aider's **60-second retry
   >   timeout**. Set this value according to your API tier to avoid RateLimitErrors
   >   stopping processes.

   Note the failure mode named there: **rate limits stopping processes** — an
   environment failure that scores as a model failure.

**There is no `n_attempts` / best-of-N anywhere in the harness.** One run, one number.
Combined with the §4 finding that missing tests score as failures, commit0's
flakiness posture is: *make the environment deterministic, then trust one run.*

---

## 6. Metrics and reported numbers (G3, H1)

### Metric definitions, exact

**Primary — average pass rate** (`docs/render_submissions.py:364`):
```python
avg_pass_rate = sum(evaluate_numbers) / len(evaluate_numbers)
```
where each `evaluate_numbers` entry is one repo's
`pytest_info["summary"]["passed"] / num_tests`
(`docs/render_submissions.py:334-335`). Note this is the **unweighted mean over
repos**, so `portalocker` (38 tests) counts as much as `web3.py` (40 433). A
deliberate choice, and a different answer than test-weighted micro-averaging would
give.

The CLI reports the same thing (`commit0/harness/evaluate.py:149-156`):

```python
print("repo,runtime,num_passed/num_tests")
out = sorted(out, key=lambda x: x["sum"], reverse=True)
for x in out:
    print(f"{x['name']},{x['sum']},{x['num_passed']}/{x['num_tests']}")
total_runtime = sum([x["sum"] for x in out])
averaged_passed = sum([x["passed"] for x in out]) / len(out)
print(f"total runtime: {total_runtime}")
print(f"average pass rate: {averaged_passed}")
```

**Secondary — repos resolved** (binary, all-tests-pass; see §2).

**Tertiary — test duration.** `total_duration` is tracked and shown on the leaderboard
(`docs/render_submissions.py:330, 371`). commit0 is the only repo in the corpus that
puts **runtime of the produced code** on the leaderboard — i.e. it partially measures
*implementation quality*, not just correctness. A naive `O(n²)` reimplementation that
passes will rank worse on duration.

### The leaderboard schema

`docs/render_submissions.py:172-174`:

```python
leaderboard_header = """\n\n## Leaderboard ({split})
| Name | Repos Resolved (/{num_repos}) | Avg. pass rate | Test Duration (s) | Date | Analysis | Github |
|------|:-------------------------:|:--------------------:|:--------------------:|:----------:|----|----| """
```

Two leaderboards are maintained, `lite` and `all`, and an `all` submission
automatically also produces a `lite` row computed over the lite subset
(`docs/render_submissions.py:377-392`) — so lite and all numbers are directly
comparable for the same system.

`mkdocs.yml:9` registers `analysis.md` as the Leaderboard page.

### Reported numbers found IN the repo

**None.** `docs/analysis.md` is generated at build time
(`docs/render_submissions.py:394-400`) and is **not committed**; `docs/` contains no
result tables. `docs/baseline.md` is a 5-line stub in full
(`docs/baseline.md:1-7`):

```markdown
# Baseline

Commit0 contains a baseline system based on
the [Aider](https://aider.chat/) code generation
system.

...
```

The literal `...` is in the file. **So there are no pass-rate anchors for commit0 in
this corpus** — that is a genuine gap, not an oversight in this note.

What *is* in the repo as scale anchors:
- `docs/render_submissions.py:189-192`: `lite` = **3 628** tests, `all` = **140 926**
  tests.
- `docs/table.md`: per-repo test counts (54 rows; sum 138 479; range 38 – 40 433).

### Difficulty instrumentation

`docs/render_submissions.py:100-169` computes **blank-repo difficulty metrics** —
i.e. how much work each task actually is:

```python
blank_repo_metrics = {
    ...
}
...
blank_repo_metrics["functions_to_edit"].append(...)
...
blank_repo_metrics["no_tokens_in_spec"] = tokenizer(
    concatted_spec, return_tensors="pt"
).input_ids.shape[-1]
```

exposed via the `--get_blank_details` flag (`docs/render_submissions.py:409-411`):

```python
"--get_blank_details",
...
help="Get difficulty metrics of blank repository",
```

So difficulty is characterised by **(number of functions to write, spec token count)**
— a quantitative, pre-run difficulty estimate. This is directly useful for question
H4 ("how do we deepen a task honestly"): commit0's answer is *count the functions and
the spec tokens*.

---

## 7. Documented failure modes (H3)

**There is no failure-mode analysis document in this repo.** No postmortem, no error
taxonomy, no "how agents fail" section in `docs/`. This is the honest answer.

What can be inferred from defensive code:

| Defence | Implied failure | Citation |
|---|---|---|
| `--depth 1` + `git remote remove origin`, with the comment *"to prevent agents from accessing git history and exploiting it to retrieve original implementations"* | **Agents cheat by reading git history.** This is a *stated, observed* exploit, not a hypothetical. | `commit0/harness/spec.py:117-118, 124-125` |
| *"Do not change the names of existing functions or classes"* | Agents rename things and break the test contract | `agent/configs/base.yaml:8` |
| *"you must maintain the original formatting of the function stubs (such as whitespaces), otherwise we will not able to search/replace blocks ... you will receive a score of 0"* | **Scaffold-level failure**: the edit format breaks and the whole run is lost | `agent/configs/base.yaml:8` |
| `if len(content.splitlines()) > 1500: continue` | Very large files defeat the agent / blow context, so they are excluded from the task | `agent/agent_utils.py:248-249` |
| `ignore_cycles()` recursion | Real repos have import cycles; naive ordering crashes | `agent/agent_utils.py:196-209` |
| `--continue-on-collection-errors` | One unimportable module otherwise zeroes an entire repo | `commit0/harness/spec.py:181` |
| aider 60-second retry timeout warning | **Rate limits stop processes** — an infra failure that reads as a model failure | `docs/agent.md:45` |
| `max_*_info_length: 10000` caps on all four context blocks | Context overflow | `agent/configs/base.yaml:15-18` |

The single most quotable item is the git-history exploit comment. It is the clearest
statement anywhere in this corpus that **agents will read the repo's own history to
find the answer**, and that a benchmark must actively prevent it.

---

## 8. Tool surface

commit0 does **not define its own agent tool surface**. It delegates entirely to
[Aider](https://aider.chat/). `README.md` (Agent Config table) says so:

> `agent_name` | str | Agent to use, we only support [aider](https://aider.chat/) for now. | `aider`

The integration is `agent/agents.py:61-155`. The abstract contract is minimal
(`agent/agents.py:32-39`):

```python
class Agents(ABC):
    def __init__(self, max_iteration: int):
        self.max_iteration = max_iteration

    @abstractmethod
    def run(self) -> AgentReturn:
        """Start agent"""
        raise NotImplementedError
```

and the extension point is documented at `docs/agent.md:39`:

> Refer to `class Agents` in `agent/agents.py`. You can design your own agent by
> inheriting `Agents` class and implement the `run` method.

The effective tool surface handed to Aider (`agent/agents.py:121-137`):

```python
io = InputOutput(
    yes=True,
    input_history_file=input_history_file,
    chat_history_file=chat_history_file,
)
coder = Coder.create(
    main_model=self.model,
    fnames=fnames,
    auto_lint=auto_lint,
    auto_test=auto_test,
    lint_cmds={"python": lint_cmd},
    test_cmd=test_cmd,
    io=io,
)
coder.max_reflections = self.max_iteration
coder.stream = True
```

So the agent gets:
- **a fixed file set** (`fnames`) — it does not search or open files itself; the
  harness pre-selects them in dependency order
- **`auto_lint` with a fixed lint command** — `python -m commit0 lint <repo> --files ...`
  (`agent/agent_utils.py:552-556`)
- **`auto_test` with a fixed test command**
- **`yes=True`** — all confirmations auto-accepted, i.e. no human in the loop
- edits happen via Aider's search/replace diff format (hence the whitespace-preservation
  instruction in the prompt)

**Notably absent:** no bash tool, no shell, no file browser, no web access. commit0's
ACI is far narrower than SWE-agent's or terminal-bench's — it is an *editor-only*
surface. That is the whole design: the difficulty is meant to be synthesis, not
navigation.

Cost tracking is scraped out of Aider's log with a regex
(`agent/agents.py:47-58`):

```python
def get_money_cost(self) -> float:
    """Get accumulated money cost from log file"""
    last_cost = 0.0
    with open(self.log_file, "r") as file:
        for line in file:
            if "Tokens:" in line and "Cost:" in line:
                match = re.search(
                    r"Cost: \$\d+\.\d+ message, \$(\d+\.\d+) session", line
                )
                if match:
                    last_cost = float(match.group(1))
    return last_cost
```

### CLI surface (the human/harness commands)

`commit0/harness/constants.py:73-84`:

```python
COMMANDS = [
    "clone",
    "build",
    "test",
    "test-reference",
    "get-tests",
    "evaluate",
    "evaluate-reference",
    "lint",
    "save",
]
```

Note `test-reference` / `evaluate-reference` — you can run the **gold** implementation
through the same pipeline, which is the correct way to establish that a task is
solvable and that the environment works. `commit0/harness/run_pytest_ids.py:113-115`:

```python
commit_id = ""
if branch == "reference":
    commit_id = example["reference_commit"]
```

That is the closest thing commit0 has to an environment-health check, and it is a good
pattern: **an oracle run through the identical harness path.**

---

## 9. Notable quotes / raw excerpts

**The framing** (`README.md:11`):
> <a href="https://commit-0.github.io/">Commit0</a> is a from scratch AI coding
> challenge. **Can you create a library from commit 0?**

**What every library must have** (`README.md:22-26`):
> The benchmark consists of 57 core Python libraries. The challenge is to rebuild these
> libraries and pass their unit tests. All libraries have:
> * Significant test coverage
> * Detailed specification and documentation
> * Lint and type checking

**What the environment provides** (`README.md:28-32`):
> Commit0 is an interactive environment that makes it easy to design and test new
> agents. You can:
> * Efficiently run tests in isolated environments
> * Distribute testing and development across cloud systems
> * Track and log all changes made throughout.

**The anti-cheat comment — the most citable line in the repo**
(`commit0/harness/spec.py:117-118`):
```python
# Use --depth 1 for shallow clone to prevent agents from accessing
# git history and exploiting it to retrieve original implementations
```

**And its companion** (`commit0/harness/spec.py:124-125`):
```python
# Remove the remote so the agent won't see newer commits.
"git remote remove origin",
```

**On not exiting early during grading** (`commit0/harness/spec.py:43`):
```python
# Don't exit early because we need to revert tests at the end
```

**On agent-side retries and rate limits** (`docs/agent.md:44-45`):
> * Aider automatically retries certain API errors. ...
> * When increasing `--max-parallel-repos`, be mindful of aider's 60-second retry
>   timeout. Set this value according to your API tier to avoid RateLimitErrors
>   stopping processes.

---

## Takeaways for our own task design

1. **The `reference_commit` / `base_commit` pair is a cleaner task definition than a
   prose problem statement.** Two commits fully specify the task, the oracle, and the
   diff, with no natural-language ambiguity. `commit0/harness/constants.py:7-14`.
2. **`--depth 1` + `git remote remove origin` is the minimum viable answer-hiding
   guard** for any task built from a real repo. The comment at
   `commit0/harness/spec.py:117-118` says agents were actually exploiting history.
3. **Partial credit changes what a benchmark can measure.** `ResolvedStatus.PARTIAL`
   plus a continuous pass rate lets commit0 rank systems that would all score 0 on a
   binary metric. Directly relevant to H2/H4.
4. **Dependency-ordered task decomposition** (`agent/agent_utils.py:212-230`) is a
   transferable idea: the harness, not the agent, decides the order of work.
5. **Runtime on the leaderboard** is a cheap way to penalise correct-but-terrible
   implementations (`docs/render_submissions.py:371`).
6. **Negative lesson for G5:** commit0 scores a missing test result as `"failed"`
   (`commit0/harness/evaluate.py:130`) and a missing report as `0`
   (`:98-108`). It has an eight-value log sentinel taxonomy
   (`commit0/harness/constants.py:296-304`) that never reaches the score. **Do not
   repeat this.** Carry the distinction all the way to the metric.
