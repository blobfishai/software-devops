# princeton-nlp/SWE-bench

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/princeton-nlp__SWE-bench/`

Clone state: `swebench.__version__ == "5.0.0rc"` (`swebench/__init__.py:1`), HEAD =
`ec9181d65aca823e8fd8d07a61bdcd39914564ef`, "Fix three harness bugs that silently drop instances (#635)",
dated Mon Aug 10 2026. Note the `CHANGELOG.md` in the repo stops at `[2.0.12] - 7/21/2024` (`CHANGELOG.md:7`) —
it has **not** been updated for the 3.x/4.x/5.x line, so the CHANGELOG is misleading about the state of this tree.
This is a heavily refactored 5.x tree: the old `swebench/harness/test_spec/` package and the giant
`MAP_REPO_VERSION_TO_SPECS` / `SPECS_*` install-command constants **no longer exist in this repo** (see §2 and §8).

All paths below are relative to that repo root.

---

## 1. Task taxonomy (C1, C2, C3, C4)

### 1.1 Dataset variants and stated counts

Five variants are named in this tree. Counts as *stated in the repo* (they disagree with each other in one place —
noted below):

`docs/faq.md:11-17`:

```
SWE-bench offers five main datasets:

- **SWE-bench**: The full benchmark with 2,294 instances
- **SWE-bench Lite**: A smaller subset with 300 instances
- **SWE-bench Verified**: 500 instances verified by engineers as solvable
- **SWE-bench Multimodal**: 100 _development_ instances with screenshots and UI elements (test eval is on [the SWE-bench API](https://www.swebench.com/sb-cli).)
- **SWE-bench Multilingual**: 300 instances spanning 9 languages and 42 repositories
```

`docs/guides/datasets.md:9-15` gives a table that **contradicts** the FAQ on Lite:

```
| **SWE-bench** | Full benchmark with diverse repositories | 2,294 instances | Comprehensive evaluation |
| **SWE-bench Lite** | Smaller subset for quick evaluations | 534 instances | Faster iteration, development |
| **SWE-bench Verified** | Expert-verified solvable problems | 500 instances | High-quality evaluation |
| **SWE-bench Multimodal** | Includes screenshots and UI elements | 100 dev instances (500 test) | Testing multimodal capabilities |
| **SWE-bench Multilingual** | 9 programming languages, 42 repositories | 300 instances | Cross-lingual evaluation |
```

The authoritative per-split numbers are in `docs/assets/evaluation.md:36-45`:

```
You can run evaluation for the following (`dataset_name`, `split`)
* `princeton-nlp/SWE-bench_Lite`, `test` (300 task instances)
* `princeton-nlp/SWE-bench_Verified`, `test` (500)
* `princeton-nlp/SWE-bench`, `dev` (225)
* `princeton-nlp/SWE-bench`, `test` (2294)
* `princeton-nlp/SWE-bench_Multimodal`, `dev` (102)

You *cannot* run evaluation on the `test` split of `princeton-nlp/SWE-bench_Multimodal` using this repository (517 instances).
To encourage less intentional climbing of the leaderboard, we have intentionally made specifications for evaluating the test split private.
```

So: Lite test = 300 (the "534" in `datasets.md` appears to be an error; `swebench/collect/make_lite/make_lite.py:81`
literally does `test = take_subset(test, 300, "test")`). Multimodal dev is 100 (faq) vs 102 (evaluation.md) — use 102.
Multimodal test = 517 and is **not locally evaluable**.

**SWE-smith is NOT in this repo.** It is only referenced as a sibling project for *training-data* generation
(`README.md:130`, `docs/reference/versioning.md:3-11`, `swebench/collect/README.md:3-10`). No SWE-smith code here.

### 1.2 CLI aliases (canonical variant list)

`swebench/cli/_datasets.py:3-12`:

```python
DATASET_ALIASES = {
    "full": "SWE-bench/SWE-bench",
    "swe-bench": "SWE-bench/SWE-bench",
    "lite": "SWE-bench/SWE-bench_Lite",
    "verified": "SWE-bench/SWE-bench_Verified",
    "multimodal": "SWE-bench/SWE-bench_Multimodal",
    "mm": "SWE-bench/SWE-bench_Multimodal",
    "multilingual": "SWE-bench/SWE-bench_Multilingual",
    "ml": "SWE-bench/SWE-bench_Multilingual",
}
```

Legacy alias handling also lives in `swebench/harness/utils.py:134-143` (`"swe-bench"`, `"lite"`, etc.).

### 1.3 Language / repo coverage

The per-repo log-parser maps in `swebench/collect/build_local_datasets.py` are the best in-repo census of repo coverage:

- OG (Python-only): 18 repos — `build_local_datasets.py:72-91` (astropy, django, marshmallow, matplotlib, seaborn,
  flask, requests, pvlib, xarray, pydicom, astroid, pylint, pytest, pyvista, scikit-learn, sqlfluff, sphinx, sympy).
- Multilingual: 46 repo entries — `build_local_datasets.py:94-141`. Languages covered by the parser choices:
  C (redis, jq, nlohmann/json, micropython, valkey, fmt), Go (caddy, terraform, prometheus, hugo, gin),
  Java (gson, druid, javaparser, lombok, lucene, rxjava), JavaScript/TS (calypso, Chart.js, marked, p5.js,
  react-pdf, babel, vuejs/core, docusaurus, immutable-js, three.js, preact, axios), PHP (phpspreadsheet,
  laravel/framework, php-cs-fixer, carbon), Ruby (jekyll, fluentd, fastlane, fpm, faker, rubocop),
  Rust (ripgrep, bat, ruff, tokio, coreutils, nushell, axum).
- Multimodal: 24 repo entries — `build_local_datasets.py:144-170`, all JS/web front-end (lighthouse, prism,
  alibaba-fusion/next, bpmn-js, carbon, eslint, grommet, highlight.js, openlayers, prettier, quarto-cli, scratch-gui, …).

### 1.4 Task shape: single-shot patch, not long-horizon

The task is **one diff**. `docs/assets/evaluation.md:7-16`:

```
For each task instance of the SWE-bench dataset, given an issue (`problem_statement`) + codebase (`repo` + `base_commit`), your model should attempt to write a diff patch prediction.

Each prediction must be formatted as follows:
{
    "instance_id": "<Unique task instance ID>",
    "model_patch": "<.patch file content string>",
    "model_name_or_path": "<Model name here (i.e. SWE-Llama-13b)>",
}
```

The harness never sees the trajectory, tool calls, or turn count — only `model_patch`
(`swebench/harness/run_evaluation.py:205-212`). There is **no notion of episode length, steps, or budget anywhere
in the harness**. Long-horizon behaviour is entirely the harness-external agent's business.

### 1.5 How big is one task?

For SWE-bench Lite, the size is bounded explicitly by the construction filters (`swebench/collect/make_lite/README.md:4-11`):

```
SWE-bench lite consists of 300 test instances and 23 development instances; both subsets of the full SWE-bench splits.
- We remove instances with images, external hyperlinks, references to specific commit shas and references to other pull requests or issues.
- We remove instances that have fewer than 40 words in the problem statement.
- We remove instances that edit more than 1 file.
- We remove instances where the gold patch has more than 3 edit hunks
- We remove instances that create or remove files.
- We remove instances that contain tests with error message checks.
- Finally, we sample 300 test instances and 23 development instances from the remaining instances.
```

Implemented in `swebench/collect/make_lite/criteria.py`: `leq_n_files(patch_text, n=1)` (`criteria.py:158-163`),
`leq_n_hunks(patch_text, n=3)` (`criteria.py:166-172`), `leq_n_words(text, n=50)` (`criteria.py:175-179`, but called
with 40 at `make_lite.py:21`), `contains_non_modified_files` (`criteria.py:107-112`) rejects added/removed files.
There is also an unused-in-lite `leq_n_code_lines(patch_text, n=25)` (`criteria.py:145-155`).

**Full SWE-bench and Verified have no such size caps** — a gold patch may span many files/hunks. There is nothing in
this repo that measures or bounds task size for those.

### 1.6 How instances are built (`swebench/collect/`)

Pipeline (per `swebench/collect/README.md:21-27` and `docs/reference/cli.md:78-95`):

1. `print_pulls.py` — scrape every PR of a repo to `<repo>-prs.jsonl`.
2. `build_dataset.py` — convert PRs into candidate instances. `create_instance()` at `build_dataset.py:21-48`.
3. `versioning/get_versions.py` — attach a `version` string per instance (`docs/reference/cli.md:87-95`).
4. (external) dockerfile-gen repos — install/test specs, Dockerfiles, eval scripts (see §8).
5. `build_local_datasets.py` — join HF columns with `eval_script`/`log_parser`/`eval_type`/`image`.

Filtering gates in `build_dataset.py`:

```python
def is_valid_pull(pull: dict) -> bool:          # build_dataset.py:51-64
    if pull["merged_at"] is None:
        return False
    if "resolved_issues" not in pull or len(pull["resolved_issues"]) < 1:
        return False
    return True

def is_valid_instance(instance: dict) -> bool:  # build_dataset.py:67-80
    if instance["patch"] is None or instance["patch"] == "":
        return False
    if instance["problem_statement"] is None or instance["problem_statement"] == "":
        return False
    return True

def has_test_patch(instance: dict) -> bool:     # build_dataset.py:83-94
    if instance["test_patch"] is None or instance["test_patch"].strip() == "":
        return False
    return True
```

So the *only* instances that reach evaluation are merged PRs that (a) close ≥1 issue, (b) have a non-empty
non-test patch, (c) have a non-empty problem statement, and (d) touch tests.

Issue linkage is regex-based on `<keyword> #<number>` in title + body + commit messages
(`swebench/collect/utils.py:78-109`), with `PR_KEYWORDS = {close, closes, closed, fix, fixes, fixed, resolve,
resolves, resolved}` (`swebench/collect/utils.py:21-31`).

---

## 2. Task definition schema (C6)

### 2.1 The dataset row — `SWEbenchInstance` TypedDict

`swebench/types.py:9-21` — this is the **exact** typed schema:

```python
class SWEbenchInstance(TypedDict):
    repo: str
    instance_id: str
    base_commit: str
    patch: str
    test_patch: str
    problem_statement: str
    hints_text: str
    created_at: str
    version: str
    FAIL_TO_PASS: str
    PASS_TO_PASS: str
    environment_setup_commit: str
```

Note `FAIL_TO_PASS` / `PASS_TO_PASS` are typed `str` because on HuggingFace they are JSON-encoded lists; the harness
decodes them lazily: `json.loads(f2p) if isinstance(f2p, str) else f2p` (`swebench/harness/utils.py:213-214`).

### 2.2 The four harness-only columns added at dataset-build time

This is the big 5.x change. The row consumed by the harness carries four extra fields, injected by
`swebench dataset build`:

`swebench/collect/build_local_datasets.py:196-210`:

```python
METADATA_FIELDS = {"log_parser", "eval_type", "eval_script", "image"}

BASE_REQUIRED_FIELDS = {
    "repo", "instance_id", "base_commit", "patch", "test_patch",
    "problem_statement", "hints_text", "created_at", "version",
    "FAIL_TO_PASS", "PASS_TO_PASS",
}
```

`swebench/collect/build_local_datasets.py:265-276`:

```python
def add_metadata(ex):
    repo = ex["repo"]
    if repo not in parser_map:
        raise ValueError(...)
    ex["log_parser"] = parser_map[repo]
    ex["eval_type"] = "fail_only" if repo in fail_only_repos else "pass_and_fail"
    ex["eval_script"] = eval_scripts[ex["instance_id"]]
    ex["image"] = get_image_name(ex["instance_id"])
    return ex
```

Per-dataset extra required fields (`build_local_datasets.py:298-348`, mirrored at `swebench/cli/dataset.py:55-68`):

| dataset | extra required fields | generator | splits built |
|---|---|---|---|
| SWE-bench | `environment_setup_commit` | `og` | dev, test |
| SWE-bench_Lite | `environment_setup_commit` | `og` | dev, test |
| SWE-bench_Verified | `environment_setup_commit`, `difficulty` | `og` | (all) |
| SWE-bench_Multilingual | — | `multilingual` | (all) |
| SWE-bench_Multimodal | `image_assets` | `multimodal` | dev, test |

Every row is hard-validated: `validate_no_missing` raises on a missing or `None` field
(`build_local_datasets.py:218-231`, called at `:281-282`).

Image name derivation, `build_local_datasets.py:185-189` (kept in sync with `image_spec.py:35-43`):

```python
def get_image_name(instance_id: str) -> str:
    key = f"sweb.eval.x86_64.{instance_id}:latest".lower()
    namespace = os.environ.get("SWEBENCH_IMAGE_NAMESPACE", "swebench")
    return f"{namespace}/{key}".replace("__", "_1776_") if namespace else key
```

(The `__` → `_1776_` substitution exists because "docker hub doesn't allow dunders in image names",
`swebench/image_builder/image_spec.py:41-42`.)

### 2.3 `TestSpec` — the runtime object the harness actually grades against

`swebench/types.py:24-46`:

```python
@dataclass
class TestSpec:
    """
    A dataclass that represents a test specification for evaluation of a single instance of SWE-bench.
    Assumes images are already built and available.
    """
    instance_id: str
    image: str
    eval_script_list: list[str]
    repo: str
    version: str
    FAIL_TO_PASS: list[str]
    PASS_TO_PASS: list[str]
    log_parser: str = ""
    eval_type: str = ""

    @property
    def eval_script(self):
        return (
            "\n".join(["#!/bin/bash", "set -uxo pipefail"] + self.eval_script_list)
            + "\n"
        )
```

Built by `make_test_spec` (`swebench/harness/utils.py:198-217`) — note that the TestSpec is now a *pure projection of
the dataset row*; it computes nothing:

```python
def make_test_spec(instance: dict) -> TestSpec:
    """
    Build a TestSpec from a dataset instance.

    The instance dict must contain: instance_id, image, repo, version,
    FAIL_TO_PASS, PASS_TO_PASS, log_parser, eval_type, eval_script.
    """
```

`parse_eval_script` strips the shebang and `set -uxo pipefail` back out on ingest so the property can re-add them
(`swebench/harness/utils.py:189-195`). The `set -x` is load-bearing: the Maven and Gradle parsers key off the traced
command lines (`swebench/harness/log_parsers/java.py:26-28`: *"Assumes we run evaluation with set -x"*).

### 2.4 Key-name constants

`swebench/harness/constants/__init__.py:30-33`:

```python
FAIL_TO_PASS = "FAIL_TO_PASS"
FAIL_TO_FAIL = "FAIL_TO_FAIL"
PASS_TO_PASS = "PASS_TO_PASS"
PASS_TO_FAIL = "PASS_TO_FAIL"
```

There is **no** `KEY_INSTANCE_ID`/`KEY_MODEL`/`KEY_PREDICTION` constant family in this version — prediction keys are
inline string literals (`"instance_id"`, `"model_patch"`, `"model_name_or_path"`) throughout, e.g.
`swebench/harness/run_evaluation.py:170`, `:208`, `:235`, `swebench/harness/utils.py:36-42`.

### 2.5 A real (abridged) instance example

The repo does **not** ship a full task-instance fixture. The only checked-in data file is a raw GitHub PR object used
to smoke-test the collector: `tests/test_data/pvlib.jsonl` (1 line, 17,877 bytes, 36 top-level keys). Its
task-relevant fields:

```json
{
  "html_url": "https://github.com/pvlib/pvlib-python/pull/1",
  "number": 1,
  "title": "Update README.md",
  "body": "Removed unneeded \\* in readme.\n",
  "state": "closed",
  "merged_at": "2015-02-17T01:02:03Z",
  "resolved_issues": [],
  "base": {"sha": "e8dd1d9bdaff50319fde60397d704061290f19de"},
  "diff_url": "https://github.com/pvlib/pvlib-python/pull/1.diff"
}
```

(That PR resolves no issues, so `is_valid_pull` would reject it — it exists to exercise the code path, not to be a
task.) A synthetic instance stub used by the report test is `tests/test_evaluation.py:11-15`:

```python
TEST_INSTANCE = collections.defaultdict(lambda: "test")
TEST_INSTANCE[PASS_TO_PASS] = "[]"
TEST_INSTANCE["repo"] = "pvlib/pvlib-python"
TEST_INSTANCE["version"] = "0.1"
TEST_INSTANCE[FAIL_TO_PASS] = "[]"
```

The doc-level schema description is `docs/guides/datasets.md:45-83` (includes `difficulty` for Verified and
`image_assets` for Multimodal, and notes that for Multimodal `test`, `patch`/`test_patch`/`image_assets` are empty).

### 2.6 Done-ness: state-based, not answer-based, **no LLM judge**

Done-ness is decided purely by executing the repo's own test suite in a container and pattern-matching the resulting
stdout with a hand-written per-repo regex parser (§4). There is **no LLM judge anywhere in this repo** — grep for
model/API calls under `swebench/harness/` returns nothing; the only OpenAI/Anthropic usage is in
`swebench/inference/run_api.py`, which *generates* patches and never grades them. Grading = `get_eval_report`
(`swebench/harness/grading.py:215-271`), which is deterministic set arithmetic over parsed test statuses.

---

## 3. Input documents / agent context (D1, D3)

### 3.1 What the task nominally hands the model

Per `docs/assets/evaluation.md:7`: *"given an issue (`problem_statement`) + codebase (`repo` + `base_commit`)"*.
So the two canonical inputs are:

- `problem_statement` — the concatenated title+body of every GitHub issue the PR closes
  (`swebench/collect/utils.py:248-266`):

  ```python
  text = ""
  all_hint_texts = list()
  for issue_number in pull["resolved_issues"]:
      issue = repo.call_api(repo.api.issues.get, owner=..., repo=..., issue_number=issue_number)
      if issue is None:
          continue
      title = issue.title if issue.title else ""
      body = issue.body if issue.body else ""
      text += f"{title}\n{body}\n"
  ```

  Django is special-cased and scraped from Trac instead of GitHub (`swebench/collect/utils.py:246-247`,
  implementation at `:337-407`, hitting `https://code.djangoproject.com/ticket/{issue_number}`).

- The repo snapshot at `base_commit` — realised as a Docker image, not as text. The clone is deliberately
  *time-sanitised* so future information cannot leak (`swebench/image_builder/docker_utils.py:58-78`):

  ```python
  return [
      f"git clone -o origin {branch} --single-branch https://github.com/{repo} {workdir}",
      f"chmod -R 777 {workdir}",  # So nonroot user can run tests
      f"cd {workdir}",
      f"git reset --hard {base_commit}",
      "git remote remove origin",
      f"TARGET_TIMESTAMP=$(git show -s --format=%ct {base_commit})",
      'git tag -l | while read tag; do TAG_COMMIT=$(git rev-list -n 1 "$tag"); TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); if [[ $TAG_TIME -gt $TARGET_TIMESTAMP ]]; then git tag -d "$tag"; fi; done',
      "git reflog expire --expire=now --all",
      "git gc --prune=now --aggressive",
      "AFTER_TIMESTAMP=$((TARGET_TIMESTAMP + 1))",
      'COMMIT_COUNT=$(git log --oneline --all --after="@$AFTER_TIMESTAMP" | wc -l)',
      '[ "$COMMIT_COUNT" -eq 0 ] || exit 1',
      "cd - || true",
  ]
  ```

  That is: single-branch shallow-ish clone, hard reset to `base_commit`, origin removed, every tag newer than the base
  commit deleted, reflog expired, aggressive gc, and then a **hard assertion that zero commits after the base commit
  survive** (`exit 1` otherwise). This is the anti-future-leak guard.

### 3.2 `hints_text` — collected, never used at eval time

`hints_text` is the set of issue comments posted **before the PR's first commit** (`swebench/collect/utils.py:269-309`):

```python
commit_time = commits[0].commit.author.date  # str
commit_time = time.mktime(time.strptime(commit_time, "%Y-%m-%dT%H:%M:%SZ"))
all_comments = repo.get_all_loop(repo.api.issues.list_comments, issue_number=issue_number, quiet=True)
...
for comment in all_comments:
    comment_time = time.mktime(time.strptime(comment.updated_at, "%Y-%m-%dT%H:%M:%SZ"))  # use updated_at instead of created_at
    if comment_time < commit_time:
        comments.append(comment)
    else:
        break
    # only include information available before the first commit was created
```

Grep confirms `hints_text` is **never read by the harness** — its only consumers are the collector
(`swebench/collect/build_dataset.py:46`), the required-field list (`build_local_datasets.py:205`), and the RAG
dataset column list (`swebench/inference/make_datasets/create_text_dataset.py:169`). Whether an agent sees hints is
entirely up to the agent scaffold; SWE-bench does not hand them over.

### 3.3 `environment_setup_commit` — now vestigial

Grep shows `environment_setup_commit` appears **only** in `swebench/types.py:21`, the required-field lists
(`build_local_datasets.py:305,316,327`; `cli/dataset.py:56,57,60`), and the RAG column list
(`create_text_dataset.py:176`). Nothing in `swebench/harness/` or `swebench/image_builder/` reads it in 5.x — the
environment is now baked into the pre-built instance image by the external dockerfile generator, so the
env-setup commit no longer selects anything at runtime.

### 3.4 Where a prompt actually gets constructed

Only in the *inference* subpackage, which is the paper's RAG baseline, not the benchmark itself.
`swebench/inference/make_datasets/create_instance.py:165-190` (`prompt_style_2`):

```python
def prompt_style_2(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_text = make_code_text(instance["readmes"])
    code_text = make_code_text(instance["file_contents"])
    instructions = (
        "I need you to solve this issue by generating a single patch file that I can apply "
        + "directly to this repository using git apply. Please respond with a single patch "
        + "file in the following format."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise, "<issue>", problem_statement, "</issue>",
        "<code>", readmes_text, code_text, "</code>",
        instructions, "<patch>", PATCH_EXAMPLE, "</patch>",
    ]
    return "\n".join(final_text)
```

Variants: `prompt_style_3` (`:221-256`), `full_file_gen` (`:259-284`), `prompt_style_2_edits_only` (`:193-218`),
registered in `PROMPT_FUNCTIONS` (`:296-301`). A worked few-shot diff is `PATCH_EXAMPLE`
(`create_instance.py:21-…`, a euclidean/bresenham diff).

Context sources, per `docs/guides/create_rag_datasets.md:20-45`:
- `--file_source oracle` — exactly the files touched by the gold patch (`get_oracle_filenames`,
  `create_instance.py:326-338` — it parses `instance["patch"]`, i.e. **oracle retrieval leaks the gold file set**).
- `--file_source bm25` — BM25 hits from `bm25_retrieval.py`, top-`k`, truncated to `--max_context_len`
  (`create_instance.py:304-323`, `create_text_dataset.py:86-95` forbids `max_context_len` with `oracle`/`all`).
- `--file_source all` — whole repo.

Repo is materialised for prompt-building by `AutoContextManager` → `ContextManager.__enter__`
(`swebench/inference/make_datasets/utils.py:148-158`): `git reset --hard {base_commit} && git clean -fdxq`, cloning
from the mirror org `https://…@github.com/swe-bench-repos/<owner>__<repo>.git`
(`swebench/inference/make_datasets/utils.py:186-190`).

**No real `problem_statement` string is checked into this repo.** The closest thing is the prediction example in
`docs/guides/evaluation.md:59-61` (a `sympy__sympy-20590` sympify diff).

---

## 4. Verification (G1, G4, G5)

### 4.1 End-to-end mechanism

`docs/reference/harness.md:36-44`:

```
1. **Setup**: Prepare Docker images for each instance
2. **Patch Application**: Apply the model-generated patch to the codebase
3. **Test Execution**: Run the repository's test suite
4. **Grading**: Determine if the patch resolves the issue
5. **Reporting**: Calculate metrics and generate reports
```

Docker is mandatory — `docs/faq.md:87-89`: *"Can I run evaluations without using Docker? **No.** Docker is required
for consistent evaluation environments."*

### 4.2 Container creation

`swebench/harness/run_evaluation.py:71-144`. Image is pulled if absent, else `EvaluationError`
(`run_evaluation.py:88-100`). Container name is deterministic (`run_evaluation.py:104`):

```python
container_name = f"sweb.eval.{test_spec.instance_id.lower()}.{run_id}"
```

Ghost containers are force-removed first (`:106-113`), and on a 409/Conflict the name gets a unix-timestamp suffix
(`:123-135`). Run as `CONTAINER_USER = "root"` in `CONTAINER_WORKDIR = "/testbed"` with
`CONTAINER_SECURITY_OPT = ["seccomp=unconfined"]` (`swebench/image_builder/constants/__init__.py:6-9`), the comment
explaining: *"Docker's default seccomp profile blocks CLONE_NEWUSER, which browser sandboxes need"* — i.e. so
Multimodal's headless-browser test suites can start.

### 4.3 Patch application — 4-command escalation ladder + reverse check

`swebench/harness/run_evaluation.py:53-58`:

```python
GIT_APPLY_CMDS = [
    "git apply --verbose",
    "git apply --verbose --3way",
    "git apply --verbose --reject",
    "patch --batch --forward --fuzz=5 -p1 -i",
]
```

`swebench/harness/run_evaluation.py:205-252`:

```python
patch_file = Path(log_dir / "patch.diff")
patch_file.write_text(pred["model_patch"] or "")
copy_to_container(container, patch_file, PurePosixPath(CONTAINER_PATCH_FILE))   # /tmp/patch.diff

applied_patch = False
for attempt, git_apply_cmd in enumerate(GIT_APPLY_CMDS):
    if attempt:
        # a failed attempt (notably --reject) leaves partial state behind,
        # which makes every later command fail; restart from a pristine tree
        container.exec_run(
            ["/bin/bash", "-c", "git checkout -- . ; git clean -fd"],
            workdir=CONTAINER_WORKDIR, user=CONTAINER_USER,
        )
    val = container.exec_run(f"{git_apply_cmd} {CONTAINER_PATCH_FILE}", ...)
    if val.exit_code == 0:
        applied_patch = True
        break
if not applied_patch:
    # the chain can leave the patch fully applied while each command still exited non-zero
    reverse_check = container.exec_run(
        f"git apply --check --reverse {CONTAINER_PATCH_FILE}", ...)
    if reverse_check.exit_code == 0:
        applied_patch = True
if not applied_patch:
    raise EvaluationError(instance_id, f"{APPLY_PATCH_FAIL}:\n{...}", logger)
```

Two notable robustness hacks here: the inter-attempt `git checkout -- . ; git clean -fd` reset, and the
`git apply --check --reverse` fallback that treats "already fully applied" as success.

`patch --fuzz=5` is a real leniency: a model patch with wrong context lines can still land.

### 4.4 Test execution

`swebench/harness/run_evaluation.py:266-288`:

```python
eval_file = Path(log_dir / "eval.sh")
eval_file.write_text(test_spec.eval_script)
copy_to_container(container, eval_file, PurePosixPath("/eval.sh"))

test_output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
test_output_path = log_dir / LOG_TEST_OUTPUT
with open(test_output_path, "w") as f:
    f.write(test_output)
    if timed_out:
        f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
        raise EvaluationError(instance_id, f"Test timed out after {timeout} seconds.", logger)
```

The eval script itself is **not in this repo** — it arrives as the `eval_script` dataset column, generated by the
external `sb_dockerfile_gen` package (`swebench/collect/build_local_datasets.py:31-40`, §8). What the harness knows
about it is only the two sentinel markers it must emit (§4.6).

`exec_run_with_timeout` (`swebench/harness/docker_utils.py:109-146`) runs the exec in a thread, `join(timeout)`, and
on timeout sends `kill -TERM <pid>` to the exec's PID. Output decode is `errors="replace"` — *"test output is
arbitrary bytes; a stray non-UTF-8 byte must not kill the run"* (`docker_utils.py:145-146`), one of the three
silent-instance-drop bugs fixed in HEAD.

### 4.5 Pre/post `git diff` — recorded but NOT enforced

`swebench/harness/run_evaluation.py:256-302`:

```python
git_diff_output_before = container.exec_run("git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR)...
...
git_diff_output_after  = container.exec_run("git -c core.fileMode=false diff", workdir=CONTAINER_WORKDIR)...
logger.info(f"Git diff after:\n{git_diff_output_after}")
if git_diff_output_after != git_diff_output_before:
    logger.info("Git diff changed after running eval script")
```

This is **logging only**. A drift between before/after does not fail, flag, or downgrade the instance. Same in the
Modal path (`swebench/harness/modal_eval/run_evaluation_modal.py:334-340`).

### 4.6 Log parsing: raw stdout → per-test status map

`swebench/harness/constants/__init__.py:41-50` defines the sentinels:

```python
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
APPLY_PATCH_PASS = ">>>>> Applied Patch"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"
START_TEST_OUTPUT = ">>>>> Start Test Output"
END_TEST_OUTPUT = ">>>>> End Test Output"
```

`swebench/harness/grading.py:35-71` — this is the gate every instance passes through:

```python
def get_logs_eval(test_spec: TestSpec, log_fp: str) -> tuple[dict[str, str], bool]:
    log_parser = PARSER_REGISTRY[test_spec.log_parser]
    with open(log_fp) as f:
        content = f.read()
        bad_codes = list(filter(lambda x: x in content,
            [APPLY_PATCH_FAIL, RESET_FAILED, TESTS_ERROR, TESTS_TIMEOUT]))
        if bad_codes:
            return {}, False
        elif not (START_TEST_OUTPUT in content and END_TEST_OUTPUT in content):
            # Test patch did not apply (should not happen at all)
            return {}, False
        content = content.split(START_TEST_OUTPUT)[1].split(END_TEST_OUTPUT)[0]
        return log_parser(content, test_spec), True
```

Only the text **between** the two markers is parsed. This is a genuine substring scan of the whole log for the bad
codes — a test that happens to print `">>>>> Tests Errored"` would zero out the instance.

`TestStatus` enum (`swebench/harness/constants/__init__.py:12-17`): `FAILED, PASSED, SKIPPED, ERROR, XFAIL`.

Status predicates (`swebench/harness/grading.py:23-31`) — note `XFAIL` counts as a pass, and **absent counts as fail**:

```python
def test_passed(case: str, sm: dict[str, str]) -> bool:
    return case in sm and sm[case] in [TestStatus.PASSED.value, TestStatus.XFAIL.value]

def test_failed(case: str, sm: dict[str, str]) -> bool:
    return case not in sm or sm[case] in [TestStatus.FAILED.value, TestStatus.ERROR.value]
```

`SKIPPED` therefore satisfies neither predicate under `PASS_AND_FAIL` — a skipped F2P test lands in neither
`success` nor `failure`, silently shrinking the F2P denominator (see §6).

`PARSER_REGISTRY` has **57 named parsers** (`swebench/harness/log_parsers/__init__.py:41-107`), split by language:
Python 20, JavaScript 21, C 5, Ruby 5, Java 3, Go 1, PHP 1, Rust 1.

Parsers are pure regex/line scanners. Example — the pytest parser (`swebench/harness/log_parsers/python.py:7-26`):

```python
def parse_log_pytest(log: str, test_spec: TestSpec) -> dict[str, str]:
    test_status_map = {}
    for line in log.split("\n"):
        if any([line.startswith(x.value) for x in TestStatus]):
            if line.startswith(TestStatus.FAILED.value):
                line = line.replace(" - ", " ")
            test_case = line.split()
            if len(test_case) <= 1:
                continue
            test_status_map[test_case[1]] = test_case[0]
    return test_status_map
```

The Django parser is the ugliest and the author says so (`swebench/harness/log_parsers/python.py:125-136`):

```
# TODO: This is very brittle, we should do better
# There's a bug in the django logger, such that sometimes a test output near the end gets
# interrupted by a particular long multiline print statement.
```

Maven has no way to report passes, so each test is run individually and `BUILD SUCCESS|FAILURE` is matched
(`swebench/harness/log_parsers/java.py:6-20`):

```
Annoyingly maven will not print the tests that have succeeded. For this log
parser to work, each test must be run individually, and then we look for
BUILD (SUCCESS|FAILURE) in the logs.
```

### 4.7 FAIL_TO_PASS vs PASS_TO_PASS, and the two eval types

`swebench/harness/grading.py:90-101` (the docstring is the canonical definition):

```
Metric Definitions (Gold Result Pair + Eval Result):
- Fail-Pass (F2P) + P: Success (Resolution)
- Pass-Pass (P2P) + P: Success (Maintenance)
- Fail-Pass (F2P) + F: Failure
- Pass-Pass (P2P) + F: Failure

Miscellaneous Definitions
- Fail-Fail (F2F) + F: Failure Maintenance
- Pass-Fail (P2F) + F: Not considered
- Fail-Fail (F2F) + P: Success (Extra Credit)
- Pass-Fail (P2F) + P: Not considered
```

`EvalType` (`swebench/harness/constants/__init__.py:20-22`) has two modes, dispatched at
`swebench/harness/grading.py:103-121`:

```python
def check_pass_and_fail(test_case, eval_status_map, success, failed):
    if test_passed(test_case, eval_status_map):
        # Assume silent success for now (test case not in eval_sm)
        success.append(test_case)
    elif test_failed(test_case, eval_status_map):
        failed.append(test_case)

def check_fail_only(test_case, eval_status_map, success, failed):
    if (test_case in eval_status_map
        and eval_status_map[test_case] == TestStatus.FAILED.value):
        failed.append(test_case)
    else:
        success.append(test_case)

check_test_case = (check_pass_and_fail if eval_type == EvalType.PASS_AND_FAIL else check_fail_only)
```

`fail_only` is **strictly more lenient**: absence from the status map counts as success. It exists because some JS
reporters only print failures. `FAIL_ONLY_REPOS` (`swebench/harness/constants/__init__.py:67-77`) documents the
motivating case:

```python
FAIL_ONLY_REPOS = {
    "chartjs/Chart.js",
    "processing/p5.js",
    "markedjs/marked",
    "bpmn-io/bpmn-js",
    "openlayers/openlayers",
    # eslint's log parser (parse_log_eslint) only records failing tests from
    # the `--reporter min` output, so it must be graded fail-only; otherwise
    # every gold eslint instance is (incorrectly) marked unresolved.
    "eslint/eslint",
}
```

Confirmed by `parse_log_eslint` (`swebench/harness/log_parsers/javascript.py:70-80`) which only ever writes
`TestStatus.FAILED.value`. **Caveat:** the `FAIL_ONLY_REPOS` constant in `harness/constants` is now **dead code** —
grep shows no importer. The live sets are `FAIL_ONLY_REPOS_{OG,MULTILINGUAL,MULTIMODAL}` in
`swebench/collect/build_local_datasets.py:92,142,171-178`, and OG/Multilingual are both **empty sets**, so only the
6 multimodal repos actually get `eval_type = "fail_only"`.

### 4.8 `ResolvedStatus` and the resolution rule

`swebench/harness/constants/__init__.py:6-9`:

```python
class ResolvedStatus(Enum):
    NO = "RESOLVED_NO"
    PARTIAL = "RESOLVED_PARTIAL"
    FULL = "RESOLVED_FULL"
```

`swebench/harness/grading.py:195-212`:

```python
def get_resolution_status(report: dict[str, dict[str, Any]]) -> str:
    """
    Criteria:
        - If fail-to-pass (Resolution) = 1 and pass-to-pass (Maintenance) = 1 -> FULL
        - If (fail-to-pass (Resolution) < 1 and > 0) and pass-to-pass (Maintenance) = 1 -> PARTIAL
        - Otherwise -> NO
    """
    f2p = compute_fail_to_pass(report)
    p2p = compute_pass_to_pass(report)
    if f2p == 1 and p2p == 1:
        return ResolvedStatus.FULL.value
    elif f2p < 1 and f2p > 0 and p2p == 1:
        return ResolvedStatus.PARTIAL.value
    else:
        return ResolvedStatus.NO.value
```

`PARTIAL` is computed but **discarded** — `get_eval_report` only ever sets `resolved=True` on `FULL`
(`swebench/harness/grading.py:265-266`):

```python
if get_resolution_status(report) == ResolvedStatus.FULL.value:
    report_map[instance_id]["resolved"] = True
```

### 4.9 The per-instance report

`swebench/harness/grading.py:233-271`:

```python
report_map[instance_id] = {
    "patch_is_None": False,
    "patch_exists": False,
    "patch_successfully_applied": False,
    "resolved": False,
}
if prediction["model_patch"] is None:
    report_map[instance_id]["patch_is_None"] = True
    return report_map
report_map[instance_id]["patch_exists"] = True
eval_status_map, found = get_logs_eval(test_spec, test_log_path)
if not found:
    return report_map
report_map[instance_id]["patch_successfully_applied"] = True
...
if include_tests_status:
    report_map[instance_id]["tests_status"] = report
```

Note the naming lie: `patch_successfully_applied` is set from `get_logs_eval`'s `found` flag, i.e. "the log was
parseable and contained no bad codes", not "git apply exited 0".

Written to `report.json` per instance (`LOG_REPORT = "report.json"`, `swebench/harness/constants/__init__.py:37`;
written at `run_evaluation.py:317-319`). On-disk layout:
`logs/run_evaluation/<run_id>/<model_name>/<instance_id>/{run_instance.log, test_output.txt, patch.diff, eval.sh, report.json}`
(`run_evaluation.py:171`, `:174`, `:194`, `:207`, `:266`, `:277`).

### 4.10 Reward-hacking guards — what exists and what does **not**

**Does the harness strip test-file edits from the model patch? NO.** There is no filtering of `model_patch` at all in
this version. `run_evaluation.py:208` writes it verbatim: `patch_file.write_text(pred["model_patch"] or "")`.
`NON_TEST_EXTS` still sits in `swebench/harness/constants/__init__.py:53-65` but is **dead code** (no importer per
grep). Likewise `swebench/utils.py:34-43` has a `get_modified_files(patch)` helper that nothing calls.

What actually protects the benchmark, in order:

1. **The gold `test_patch` is separated at collection time**, so tests are never part of the solution surface.
   `swebench/collect/utils.py:312-333`:

   ```python
   for hunk in PatchSet(patch):
       if any(test_word in hunk.path for test_word in ["test", "tests", "e2e", "testing"]):
           patch_test += str(hunk)
       else:
           patch_fix += str(hunk)
   return patch_fix, patch_test
   ```

   (Path-substring based — a source file under a directory containing "test" would be misclassified.)

2. **The eval script re-checks-out the test files, after the model patch is applied.** This lives in the external
   generator, but its shape is visible in a checked-in log fixture — `tests/test_log_parsers_java.py:79-87`:

   ```
   + mvnd test -B -Dtest=com.example.Test#testOne
   [INFO] BUILD SUCCESS
   + mvnd test -B -Dtest=com.example.Test#testTwo
   + : '>>>>> End Test Output'
   + git checkout somefile.java
   [INFO] BUILD SUCCESS
   ```

   i.e. `git checkout <test files>` runs and is traced by `set -x`, after the `>>>>> End Test Output` marker.
   In 5.x this whole script is data, not code, so the guard is **not auditable from this repository**.

3. **Only text between `START_TEST_OUTPUT` and `END_TEST_OUTPUT` is graded** (`grading.py:70`), so output the agent
   emits outside that window is ignored — but output the agent causes *inside* the window is fully trusted.

4. **Future-info scrubbing of the git history** at image build (`image_builder/docker_utils.py:58-78`, §3.1) —
   prevents finding the actual upstream fix commit in the container.

5. **Multimodal test-split specs are withheld**: *"To encourage less intentional climbing of the leaderboard, we have
   intentionally made specifications for evaluating the test split private"* (`docs/assets/evaluation.md:44`).

**Gaps worth naming explicitly:**
- Nothing prevents a model patch from editing test files, conftest, or `pytest.ini`; the only backstop is the
  external eval script's `git checkout`, which by construction only restores files the *gold test patch* touched.
- Nothing prevents monkey-patching the test runner from within *source* files.
- The `git diff` before/after comparison would catch tree mutation by the eval script, but it only logs (§4.5).
- `patch --fuzz=5` (`run_evaluation.py:57`) will land a fuzzy patch.

---

## 5. Flakiness and nondeterminism (G2)

### 5.1 Timeouts

- Per-instance test timeout, default **1800 s**: `run_evaluation.py:599-605` (`-t/--timeout`, `default=1_800`),
  CLI mirror `swebench/cli/evaluate.py:28`. Hitting it raises `EvaluationError` → instance is counted as an
  **error**, not as unresolved (`run_evaluation.py:282-288`, §6).
- Docker client timeout, env-overridable: `run_evaluation.py:60-61`

  ```python
  DOCKER_CLIENT_TIMEOUT = int(os.environ.get("SWEBENCH_DOCKER_TIMEOUT", "1800"))
  DOCKER_CLIENT_POOL_SIZE = int(os.environ.get("SWEBENCH_DOCKER_POOL_SIZE", "128"))
  ```
- Container stop: `docker stop --time=15` then `docker kill`, with subprocess timeouts of 30 s/10 s
  (`swebench/harness/docker_utils.py:66-99`).
- Modal sandbox default timeout is 30 min (`modal_eval/run_evaluation_modal.py:78-80`); the Modal *function* timeout
  is 120 min "to account for image build time" (`:235-236`).

### 5.2 Retries

- **No retry of a failed instance evaluation anywhere.** One shot per instance per run.
- The only retry in the codebase is Modal sandbox creation, 7 attempts with exponential backoff
  (`modal_eval/run_evaluation_modal.py:71-74`):

  ```python
  @tenacity.retry(stop=tenacity.stop_after_attempt(7),
                  wait=tenacity.wait_exponential(multiplier=1, min=4, max=10))
  def _get_sandbox(self, timeout: int | None = None):
      # Sometimes network flakiness causes the image build to fail, so we retry a few times.
  ```
- GitHub API rate limiting in the collector retries indefinitely on a 5-minute poll
  (`swebench/collect/utils.py:60-76`, `:152-166`).

### 5.3 `run_id` and resume semantics

`--run_id` is **required** (`run_evaluation.py:606-612`; `assert len(run_id) > 0` at `:507`). It names the log
directory and the container. Resume is implicit and report-file-based:

```python
if report_path.exists():
    return instance_id, json.loads(report_path.read_text())     # run_evaluation.py:189-190
```

and, in bulk, `get_dataset_from_preds` (`run_evaluation.py:446-466`):

```python
if completed_ids and exclude_completed:
    print(f"{len(completed_ids)} instances already run, skipping...")
    dataset = [i for i in dataset if i["instance_id"] not in completed_ids]
```

Consequence: **reusing a `run_id` silently reuses old verdicts**. Modal resumes on directory existence, which is
coarser (`modal_eval/run_evaluation_modal.py:424-429`: `if log_dir.exists(): continue`).

### 5.4 Concurrency

`run_threadpool` with `max_workers` (`swebench/harness/utils.py:71-94`); `max_workers <= 0` falls back to sequential
(`:72-73`). Exceptions inside a worker are caught and only counted (`:85-88`), so a failing instance does not abort
the run.

Sizing advice, `README.md:113-119`:

```
> SWE-bench evaluation can be resource intensive
> We recommend running on an `x86_64` machine with at least 120GB of free storage, 16GB of RAM, and 8 CPU cores.
> We recommend using fewer than `min(0.75 * os.cpu_count(), 24)` for `--max_workers`.
```

`docs/reference/harness.md:146-153` gives wall-clock for Lite: 16-core/12 workers ≈30 min at `cache_level=env`,
8-core/6 workers ≈50 min.

### 5.5 Images, caching, namespace, `--force_rebuild`

In 5.x the harness **assumes images already exist** and only pulls (`run_evaluation.py:88-100`,
`run_instances` docstring at `:350-351`: *"Expects instances to have pre-built images"*). Building is a separate step:

```
swebench images build verified -j 8           # build/pull images ahead of time
swebench images check multilingual            # verify images exist on the registry
swebench images clean --run-id <run_id>       # remove leftover containers
```
(`README.md:98-102`)

- `--force-rebuild` (`swebench/cli/images.py:29`, `image_builder/prepare_images.py:209-211`) → `remove_image` for
  each spec before building (`image_builder/docker_build.py:132-134`).
- `--namespace` selects a registry prefix; `None` means build locally
  (`image_spec.py:32-33`, `:40-43`, `:50-51`; `prepare_images.py:215-220` uses `optional_str` so `--namespace ''`
  means None). The README warns ARM users to pass `--namespace ''` because published images are Linux/x86
  (`README.md:79-83`).
- Existence check before build: `filter_image_specs` (`prepare_images.py:103-120`) and
  `build_instance_image` (`docker_build.py:167-182`).
- `swebench images check` hits `client.images.get_registry_data(name)` per image in a thread pool and exits non-zero
  if any are missing (`swebench/cli/images.py:95-109`) — *"catches a stale or partially-pushed image set in seconds
  rather than one instance at a time"* (`docs/reference/cli.md:57-58`).

The `--cache_level {none,base,env,instance}` and `--clean` flags documented at `docs/guides/docker_setup.md:92-110`
and `docs/reference/harness.md:115-126` **no longer exist** in `run_evaluation.py`'s argparse (`:556-625`) — the docs
are stale relative to the 5.x refactor.

### 5.6 Container-name collisions

Documented explicitly in `swebench/cli/images.py:118-122`:

```
Remove leftover evaluation containers.

A killed run leaves containers holding their names, and the next attempt
fails with a 409 conflict.
```

Handled two ways: pre-emptive force-remove (`run_evaluation.py:106-113`) and the 409 → timestamp-suffix retry
(`:123-135`). `swebench/harness/remove_containers.py:29-48` matches on the `sweb.eval.<instance_id>.<run_id>` prefix
and force-removes.

### 5.7 Known nondeterminism sources visible in the code

- **Interleaved log output.** Both Java parsers carry explicit race-condition handling and unit tests named
  `test_interleaved_logs_race_condition` / `test_interleaved_commands_race_condition`
  (`swebench/harness/log_parsers/java.py:12-14`, `:100-102`; `tests/test_log_parsers_java.py:30`, `:63`) —
  test name and status can arrive on different lines. The parsers fall back to FIFO matching
  (`java.py:48-56`) and warn when a test has no result (`java.py:58-63`, `:141-145`).
- **Buffered output past the end marker** — `tests/test_log_parsers_java.py:79-92` covers
  `BUILD SUCCESS` appearing *after* `>>>>> End Test Output`.
- **Non-UTF-8 bytes in test output** — previously aborted an instance; now `errors="replace"`
  (`docker_utils.py:145-146`).
- **Seccomp** — browser-sandbox tests previously failed to start (`image_builder/constants/__init__.py:8-9`).
- **`git tag` deletion / gc** in the clone script is time-dependent on the base commit timestamp
  (`image_builder/docker_utils.py:70-76`).
- The three fixes above are exactly HEAD's commit body: *"Default images build --tag to latest so make_image_spec
  does not assert / Run eval containers with seccomp unconfined so browser sandboxes can start / Decode test output
  with errors=replace so a stray byte cannot abort an instance"*.

**There is no flaky-instance denylist, no repeat-N-times, no majority-vote, and no per-instance variance tracking
anywhere in this repo.** `docs/faq.md:103-108` ("My evaluation is stuck or taking too long") is the only flakiness
troubleshooting guidance and it is generic.

### 5.8 Re-grading without re-running

`--rewrite_reports` re-parses saved `test_output.txt` and rewrites `report.json` with no containers
(`run_evaluation.py:175-188`, `:422-444`), surfaced as `swebench report <run_id>`
(`swebench/cli/evaluate.py:67-99`). `docs/reference/cli.md:34-36`:

```
Recompute verdicts from a finished run's saved logs, without starting
containers. Useful after a log-parser fix, since the test output is already on disk.
```

This is a real reproducibility property: parser bugs can be retro-fixed without re-executing, meaning
**published numbers are a function of the parser version, not just the run**.

---

## 6. Metrics and reported numbers (G3, H1)

### 6.1 The two ratios

`swebench/harness/grading.py:174-192`:

```python
def compute_fail_to_pass(report) -> float:
    total = len(report[FAIL_TO_PASS]["success"]) + len(report[FAIL_TO_PASS]["failure"])
    if total == 0:
        return 1
    return len(report[FAIL_TO_PASS]["success"]) / total

def compute_pass_to_pass(report) -> float:
    total = len(report[PASS_TO_PASS]["success"]) + len(report[PASS_TO_PASS]["failure"])
    if total == 0:
        # TODO: Don't factor in p2p metrics
        return 1
    return len(report[PASS_TO_PASS]["success"]) / total
```

Both **return 1 when the denominator is 0**. Combined with the `SKIPPED`-falls-through-both-predicates behaviour
(§4.6), an instance whose F2P tests were all skipped scores `f2p == 1` and can be marked resolved. This is the
single most load-bearing sharp edge in the grading code.

### 6.2 "% Resolved"

`resolved` per instance = `get_resolution_status(report) == "RESOLVED_FULL"` (`grading.py:265-266`),
i.e. **every** F2P test passes **and** **every** P2P test passes. The aggregate is
`resolved_instances / total_instances` — the harness prints the counts but **never computes a percentage**:
`docs/faq.md:39` defines *"**Resolution rate**: The percentage of submitted instances that were successfully
resolved"*, `docs/guides/evaluation.md:145` says *"Percentage of submitted instances successfully resolved"*.
Note both docs say **submitted**, while the report JSON's natural denominator is `total_instances` — a real
ambiguity the repo never resolves in code.

### 6.3 Report JSON schema

`swebench/harness/reporting.py:101-125` — verbatim:

```python
report = {
    "total_instances": len(full_dataset),
    "submitted_instances": len(predictions),
    "completed_instances": len(completed_ids),
    "resolved_instances": len(resolved_ids),
    "unresolved_instances": len(unresolved_ids),
    "empty_patch_instances": len(empty_patch_ids),
    "error_instances": len(error_ids),
    "completed_ids": list(sorted(completed_ids)),
    "incomplete_ids": list(sorted(incomplete_ids)),
    "empty_patch_ids": list(sorted(empty_patch_ids)),
    "submitted_ids": list(sorted(predictions.keys())),
    "resolved_ids": list(sorted(resolved_ids)),
    "unresolved_ids": list(sorted(unresolved_ids)),
    "error_ids": list(sorted(error_ids)),
    "schema_version": 2,
}
if client:
    report.update({
        "unstopped_instances": len(unstopped_containers),
        "unstopped_containers": list(sorted(unstopped_containers)),
        "unremoved_images": list(sorted(unremoved_images)),
    })
```

Written to `<model_name_or_path>.<run_id>.json` in CWD (`reporting.py:126-133`). `schema_version == 2` is asserted by
`tests/test_evaluation.py:29`.

### 6.4 Exact bucket assignment

`swebench/harness/reporting.py:44-72` — the classification is a strict if/elif chain per instance:

```python
for instance in full_dataset:
    instance_id = instance["instance_id"]
    if instance_id not in predictions:
        incomplete_ids.add(instance_id); continue
    prediction = predictions[instance_id]
    if prediction.get("model_patch", None) in ["", None]:
        empty_patch_ids.add(instance_id); continue
    report_file = RUN_EVALUATION_LOG_DIR / run_id / prediction["model_name_or_path"].replace("/", "__") / prediction["instance_id"] / LOG_REPORT
    if report_file.exists():
        completed_ids.add(instance_id)
        report = json.loads(report_file.read_text())
        if report[instance_id]["resolved"]:
            resolved_ids.add(instance_id)
        else:
            unresolved_ids.add(instance_id)
    else:
        error_ids.add(instance_id)
```

Key implications:
- `incomplete` = no prediction at all. `empty_patch` = prediction with `""`/`None`. Neither is `error`.
- `error` = "no `report.json` on disk", which absorbs **timeouts, patch-apply failures, container crashes,
  unparseable logs, and image-not-found alike**. There is no distinction between infra failure and model failure in
  the report. (`unresolved` requires a parseable run that simply didn't pass.)
- `submitted_instances = len(predictions)` — the *whole* predictions dict, not intersected with the dataset, while
  the printed line at `reporting.py:89` does intersect (`len(set(predictions.keys()) & dataset_ids)`). Printed and
  JSON values can therefore disagree.
- Empty-patch instances are also filtered out *before* running (`run_evaluation.py:468-480`), so they never even get
  a container.

Printed summary (`reporting.py:88-98`):

```
Total instances / Instances submitted / Instances completed / Instances incomplete /
Instances resolved / Instances unresolved / Instances with empty patches / Instances with errors /
Unstopped containers / Unremoved images
```

Matching FAQ description at `docs/faq.md:30-39`.

### 6.5 Leaderboard numbers in the repo

**None.** `docs/index.md:33-35` only says *"You can find the full leaderboard at [swebench.com](https://swebench.com)!"*
and `mkdocs.yml:55` links out. No score table, no baseline accuracy, no per-model results are checked in.
`README.md:34` points Multimodal submissions at `sb-cli`. `docs/blog/index.md` is an empty stub (2 lines).
The `docs/20240627_docker/README.md` and `docs/reports/20240405_eval_bug/README.md` reports linked from
`README.md:36` and `CHANGELOG.md:70` **do not exist in this clone** (`docs/` contains only
`api assets blog css faq.md guides index.md installation.md other_languages README.md reference`).

---

## 7. Documented failure modes (H3)

The repo documents *harness* failure modes well and *agent* failure modes essentially not at all.

**Agent-side failure modes: not documented.** There is no error taxonomy, no "why models fail" analysis, no
qualitative study in `docs/`. The closest thing is the metric buckets in §6.4 (empty patch / error / unresolved) and
the output-format hint at `docs/faq.md:97-99`:

```
### What format should my model's output be in?

Your model should produce a diff or patch that can be applied to the original code. The exact format depends on the instance, but we typically recommend the diff generated by `git diff`.
```

**Harness-side failure modes, documented:**

| Failure | Where documented |
|---|---|
| Stuck / slow evaluation → fewer workers, check Docker limits, check disk | `docs/faq.md:103-108` |
| Docker network errors on build | `docs/faq.md:110-116` |
| Insufficient disk space (≥120 GB, up to ~2 TB at `cache_level=instance`) | `docs/guides/docker_setup.md:96-101`, `docs/reference/harness.md:119-124` |
| Build failures → inspect `logs/build_images` | `docs/guides/docker_setup.md:140-142` |
| Permission issues (docker group) | `docs/guides/docker_setup.md:144-146` |
| Worker over-subscription slows things down | `docs/guides/docker_setup.md:130`, `docs/reference/harness.md:155-161` |
| ARM/M-series needs `--namespace ''` | `README.md:79-83`; *"Support for `arm64` machines is experimental"* `README.md:121` |
| Leftover containers → 409 conflict on next run | `swebench/cli/images.py:118-122` |
| Stale/partial image set | `docs/reference/cli.md:57-58` |
| Log-parser bugs are the common cause of wrong verdicts, fixable via re-grade | `docs/reference/cli.md:34-36` |

**In-code acknowledged fragility:**

- `swebench/harness/grading.py:45` — `TODO(john-b-yang): Check this is working properly...` on `get_logs_eval`.
- `swebench/harness/grading.py:51` — `# TODO fix constant here` on the bad-codes list.
- `swebench/harness/grading.py:190` — `# TODO: Don't factor in p2p metrics` on the empty-denominator = 1 case.
- `swebench/harness/log_parsers/python.py:92-94` — `# TODO: Temporary, exclusive fix for django__django-7188`.
- `swebench/harness/log_parsers/python.py:125-136` — `# TODO: This is very brittle, we should do better`.
- `swebench/harness/grading.py:66` — `# Test patch did not apply (should not happen at all)`.
- `swebench/harness/modal_eval/run_evaluation_modal.py:164-166` — **Modal eval is currently broken**:

  ```python
  # TODO: setup_env_script and install_repo_script are not part of the
  # current TestSpec dataclass.  This method needs to be updated to work
  # with pre-built images or to source these scripts from elsewhere.
  env_script = test_spec.setup_env_script
  ```

  `TestSpec` (`swebench/types.py:24-46`) has neither attribute, so `--modal` will raise `AttributeError`.
  This is not flagged in any doc; `README.md:104` and `docs/reference/cli.md:26` still advertise `--modal`.
- Repo-specific hacks in the Modal path: `"Hack for pylint"` writing cgroup cpu.shares
  (`run_evaluation_modal.py:68-69`), `# django hack` rewriting `locale-gen` (`:309-310`),
  `# pylint hack` clearing `PYTHONPATH` (`:316-318`), and `sys.setrecursionlimit(10000)` (`:319-320`).

**Collection is officially frozen** — `docs/assets/collection.md:4-17`:

```
> [!IMPORTANT]
> (03/02/2025) At this time, we are temporarily not actively supporting queries around SWE-bench task instance creation.
...
> Therefore, we kindly request that at this time, *please do not create more issues in this repository around creating new task instances*.
```

Mirrored at `README.md:133`. Note the tutorial link `docs/guides/collection.md` referenced from
`swebench/collect/README.md:14` is **broken** — the file is at `docs/assets/collection.md`.

---

## 8. Tool surface

**SWE-bench provides no tools to the model. The entire interface is one string: `model_patch`.**

- The harness's only input from the agent is `{"instance_id", "model_name_or_path", "model_patch"}`
  (`docs/guides/evaluation.md:49-54`, consumed at `run_evaluation.py:170`, `:208`, `:235`).
- The container the model would need is created *only for grading*, after the fact
  (`run_evaluation.py:200-202`). The agent never touches it.
- No editor, no shell, no file-read API, no search tool, no MCP surface, no turn loop exists in this repo.
  Agent scaffolds (SWE-agent, mini-swe-agent, SWE-ReX) are separate projects listed at `README.md:139-153`.

**There is an inference module**, but it is the paper's baseline harness, not part of the benchmark
(`docs/reference/inference.md:12-17`):

```
- `make_datasets`: Contains scripts to generate new datasets for SWE-bench inference with your own prompts and issues
- `run_api.py`: Generates completions using API models (OpenAI, Anthropic) for a given dataset
- `run_llama.py`: Runs inference using Llama models (e.g., SWE-Llama)
- `run_live.py`: Generates model completions for new issues on GitHub in real time
```

It is single-shot text-in/patch-out: build a prompt (§3.4) → one completion → extract the diff
(`swebench/inference/make_datasets/utils.py:130-138`, which prefers a ```diff/```patch fenced block).
It is deliberately not wired into the CLI — `docs/reference/cli.md:106-110`:
*"The inference utilities are not exposed through `swebench` and are run this way: `python -m swebench.inference.run_api --help`"*.

**What the harness assumes exists outside itself** (the 5.x split, the single biggest structural fact about this tree):

1. **The three dockerfile-generator repos.** `swebench/collect/build_local_datasets.py:22-40`:

   ```python
   # override with SWEBENCH_DOCKERFILE_REPOS=/path/to/checkouts
   _REPO_ROOT = Path(os.environ.get("SWEBENCH_DOCKERFILE_REPOS", Path.home() / "code"))
   DOCKERFILE_REPOS = {
       "og": _REPO_ROOT / "swe-bench-dockerfiles",
       "multilingual": _REPO_ROOT / "swe-bench-multilingual-dockerfiles",
       "multimodal": _REPO_ROOT / "swe-bench-multimodal-dockerfiles",
   }
   _EVAL_GEN_SCRIPT = """\
   import json, sys
   sys.path.insert(0, sys.argv[1])
   from sb_dockerfile_gen import _get_eval_script
   ...
   """
   ```

   `docs/assets/collection.md:56-58` states the migration outright:

   ```
   * Specify repository+version-specific installation commands in the matching dockerfile repository
     (`swe-bench-dockerfiles`, `swe-bench-multilingual-dockerfiles`, `swe-bench-multimodal-dockerfiles`),
     under `src/sb_dockerfile_gen/`. These used to live in `harness/constants.py`, which no longer holds them.
   ```

   Consequently **`MAP_REPO_VERSION_TO_SPECS`, `MAP_VERSION_TO_INSTALL_*`, and all `SPECS_*` constants are absent
   from this repository** (grep returns nothing). `docs/assets/collection.md:69-79` still documents the old
   `MAP_VERSION_TO_INSTALL` shape (`{"python": "3.x", "packages": ..., "install": "pip install -e .",
   "pip_packages": [...]}`) as if it were in `constants.py` — stale.

   Dockerfiles are read as `<repo>/src/dockerfiles/<instance_id>.Dockerfile`
   (`image_builder/prepare_images.py:16`, `:19-36`); `--dockerfile_repo` is **required**
   (`prepare_images.py:230-235`) and may be a local path, `owner/repo`, or a GitHub URL
   (`prepare_images.py:64-100`).

2. **`swebench/resources/swebench-og/`** — 500 checked-in conda `environment.yml` lockfiles
   (e.g. `swebench/resources/swebench-og/pytest-dev__pytest/5262/environment.yml`, pinning
   `python=3.9.20`, `pluggy==0.11.0`, `prefix: /opt/miniconda3/envs/testbed`), covering 13 repos. These are the
   pinned-dependency residue of the old install specs.

3. **`sb-cli`** for hosted AWS evaluation and for Multimodal test-split submission (`README.md:34`, `:124`,
   `docs/guides/evaluation.md:82-95`).

**Other in-repo surface:** the `swebench` Typer CLI (`swebench/cli/cli.py:11-32`) with `eval`, `report`,
`images {build,check,clean}`, `dataset {build,collect,versions}`; and `swebench/versioning/` for version assignment
(`MAP_REPO_TO_VERSION_PATHS` at `versioning/constants.py:2-22`, per-repo web scrapers under
`swebench/versioning/extract_web/get_versions_{astropy,matplotlib,pvlib-python,pydicom,sqlfluff,xarray}.py`).

**Testing surface of the benchmark itself is thin:** 5 test files, ~226 lines total (`tests/`). CI is a single
ubuntu-latest pytest job (`.github/workflows/pytest.yaml:26-57`). `tests/test_cli.py:12-29` actually runs a full gold
evaluation of `sympy__sympy-20590` in CI.

---


## 9. Notable quotes / raw excerpts

Most load-bearing excerpts are already quoted verbatim in context above; this section indexes them and adds the ones
that had no natural home.

### 9.1 Index of the quotes that matter most

| What it shows | Citation | Quoted in |
|---|---|---|
| F2P/P2P/F2F/P2F metric definitions | `swebench/harness/grading.py:90-101` | §4.7 |
| `RESOLVED_FULL` is the only thing that counts | `swebench/harness/grading.py:195-212`, `:265-266` | §4.8 |
| Empty denominator ⇒ score 1 (`# TODO: Don't factor in p2p metrics`) | `swebench/harness/grading.py:179-192` | §6.1 |
| "Assume silent success for now (test case not in eval_sm)" | `swebench/harness/grading.py:103-108` | §4.7 |
| Absent test ⇒ failed; `XFAIL` ⇒ passed | `swebench/harness/grading.py:23-31` | §4.6 |
| Bad-code substring scan zeroes the instance | `swebench/harness/grading.py:52-67` | §4.6 |
| eslint forces `fail_only` or "every gold eslint instance is (incorrectly) marked unresolved" | `swebench/harness/constants/__init__.py:72-76` | §4.7 |
| 4-command apply ladder + `--fuzz=5` + reverse-apply fallback | `swebench/harness/run_evaluation.py:53-58`, `:236-245` | §4.3 |
| Model patch written verbatim, never filtered | `swebench/harness/run_evaluation.py:208` | §4.10 |
| `git diff` before/after is logged, never enforced | `swebench/harness/run_evaluation.py:299-302` | §4.5 |
| Future-commit scrub with `[ "$COMMIT_COUNT" -eq 0 ] \|\| exit 1` | `swebench/image_builder/docker_utils.py:70-76` | §3.1 |
| Test/source split by path substring `["test","tests","e2e","testing"]` | `swebench/collect/utils.py:326-333` | §4.10 |
| Hints fenced to comments before the first PR commit | `swebench/collect/utils.py:299-306` | §3.2 |
| Eval script's post-grade `git checkout <test file>` (traced) | `tests/test_log_parsers_java.py:81-87` | §4.10 |
| Report JSON schema, `schema_version: 2` | `swebench/harness/reporting.py:101-125` | §6.3 |
| `error` bucket = "no report.json", absorbing infra + timeout + apply failure | `swebench/harness/reporting.py:54-72` | §6.4 |
| Modal path broken (`test_spec.setup_env_script` no longer exists) | `swebench/harness/modal_eval/run_evaluation_modal.py:162-167` | §7 |
| Install specs moved out of `harness/constants.py` | `docs/assets/collection.md:56-58` | §8 |
| Multimodal test split deliberately private | `docs/assets/evaluation.md:43-45` | §1.1, §4.10 |
| Instance collection frozen since 03/02/2025 | `docs/assets/collection.md:4-17` | §7 |

### 9.2 Quotes not shown above

**The one-line task definition** — `README.md:53-54`:

> SWE-bench is a benchmark for evaluating large language models on real world software issues collected from GitHub.
> Given a *codebase* and an *issue*, a language model is tasked with generating a *patch* that resolves the described problem.

**Django's log parser, in full** — `swebench/harness/log_parsers/python.py:125-136`:

```python
# TODO: This is very brittle, we should do better
# There's a bug in the django logger, such that sometimes a test output near the end gets
# interrupted by a particular long multiline print statement.
# We have observed this in one of 3 forms:
# - "{test_name} ... Testing against Django installed in {*} silenced.\nok"
# - "{test_name} ... Internal Server Error: \/(.*)\/\nok"
# - "{test_name} ... System check identified no issues (0 silenced).\nok"
patterns = [
    r"^(.*?)\s\.\.\.\sTesting\ against\ Django\ installed\ in\ ((?s:.*?))\ silenced\)\.\nok$",
    r"^(.*?)\s\.\.\.\sInternal\ Server\ Error:\ \/(.*)\/\nok$",
    r"^(.*?)\s\.\.\.\sSystem check identified no issues \(0 silenced\)\nok$",
]
```

**Resource envelope** — `README.md:113-121`:

```
> SWE-bench evaluation can be resource intensive
> We recommend running on an `x86_64` machine with at least 120GB of free storage, 16GB of RAM, and 8 CPU cores.
> We recommend using fewer than `min(0.75 * os.cpu_count(), 24)` for `--max_workers`.
>
> If running with Docker desktop, make sure to increase your virtual disk space to ~120 free GB. Set max_workers to be consistent with the above for the CPUs available to Docker.
>
> Support for `arm64` machines is experimental.
```

**The 5.x CLI surface, in the author's own words** — `README.md:87-102`:

```bash
swebench eval verified --gold                 # reference patches
swebench eval multimodal --gold -i carbon-design-system__carbon-10188
swebench eval full -p preds.jsonl --modal     # run on Modal
swebench report <run_id> -d verified          # re-grade saved logs, no containers

swebench images build verified -j 8           # build/pull images ahead of time
swebench images check multilingual            # verify images exist on the registry
swebench images clean --run-id <run_id>       # remove leftover containers
```

**Why images are selected through a dataset** — `docs/reference/cli.md:45-46`:

```
Images are per instance but selected through a dataset, because the Dockerfile
comes from the instance row.
```

**Docker is non-negotiable** — `docs/faq.md:87-89`:

```
### Can I run evaluations without using Docker?

No. Docker is required for consistent evaluation environments. This ensures that the evaluation is reproducible across different systems.
```

**Container security opt, and why** — `swebench/image_builder/constants/__init__.py:8-9`:

```python
# Docker's default seccomp profile blocks CLONE_NEWUSER, which browser sandboxes need
CONTAINER_SECURITY_OPT = ["seccomp=unconfined"]
```

**Repo-specific hacks still live in the Modal runner** — `swebench/harness/modal_eval/run_evaluation_modal.py:68-69`,
`:309-310`, `:315-320`:

```python
# Hack for pylint
self.write_file("/sys/fs/cgroup/cpu/cpu.shares", "2048")
...
# django hack
eval_script = eval_script.replace("locale-gen", "locale-gen en_US.UTF-8")
...
run_command = "cd /testbed"
# pylint hack
if "pylint" in test_spec.instance_id:
    run_command += " && PYTHONPATH="
# increase recursion limit for testing
run_command += " && python3 -c 'import sys; sys.setrecursionlimit(10000)'"
```
