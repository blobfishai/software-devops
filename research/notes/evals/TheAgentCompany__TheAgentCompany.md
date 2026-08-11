# TheAgentCompany/TheAgentCompany

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/TheAgentCompany__TheAgentCompany/`

> Repo state at time of reading: single commit `98b68ef` ("Fix MongoDB image reference in setup script (#1086)"), branch `main` (shallow clone — `git log --oneline` returns one entry).
> Paper: arXiv 2412.14161 (`README.md:18`, `README.md:203-211`). Benchmark version pinned at **1.0.0** everywhere (`evaluation/run_eval.sh:39`).
> All citations below are **relative to the repo root** shown above.

---

## 1. Task taxonomy (C1, C2, C3, C4) — full category enumeration with counts

### 1.1 Exact directory counts (measured, not remembered)

Command run: `ls workspaces/tasks/ | sed 's/-.*//' | sort | uniq -c`

| Prefix | Task dirs | Notes |
|---|---:|---|
| `sde` | **69** | Software engineer |
| `hr` | **29** | Human resources |
| `pm` | **28** | Project/product manager |
| `admin` | **15** | Administrator |
| `ds` | **14** | Data scientist |
| `finance` | **12** | Finance staff |
| `research` | **2** | `research-answer-questions-on-paper`, `research-reproduce-figures` |
| `qa` | **2** | `qa-escalate-emergency`, `qa-update-issue-status-according-to-colleagues` |
| `ml` | **2** | `ml-generate-gradcam`, `ml-grade-exam` |
| `example` | **1** | The developer-facing template task (`workspaces/tasks/example/`) |
| `bm` | **1** | `bm-classify-nationality` |
| **TOTAL** | **175** | |

Cross-check #1 — the published image list in `workspaces/README.md:38-212` contains exactly **175** `ghcr.io/theagentcompany/*` lines, and the same prefix histogram (69 sde / 29 hr / 28 pm / 15 admin / 14 ds / 12 finance / 2 research / 2 qa / 2 ml / 1 example / 1 bm).

Cross-check #2 — `workspaces/README.md:23`:

> "tasks is the folder for definitions of all 175 tasks"

Cross-check #3 — `docs/EVALUATION.md:24`:

> "TheAgentCompany 1.0.0 evaluation consists of 175 tasks. Each task is a Docker image."

Cross-check #4 — `README.md:139`: "A complete list of 175 task images can be found here."

Cross-check #5 — `evaluation/README_task_images.md:81` shows `"total_tasks": 175` in the generator's own output schema.

### 1.2 The OFFICIAL scoring taxonomy is only 7 buckets

The aggregation script collapses the 11 raw prefixes into **7 nature categories**. `evaluation/summarise_results.py:152-160`:

```python
def get_task_nature_category(task_name: str) -> str:
    """
    Get the nature category of the task.
    """
    task_nature = task_name.split('-')[0]
    if task_nature.lower() in ['sde', 'pm', 'ds', 'admin', 'hr', 'finance']:
        return task_nature
    else:
        return "other"
```

and the report loop at `evaluation/summarise_results.py:326`:

```python
for task_nature in ['sde', 'pm', 'ds', 'admin', 'hr', 'finance', 'other']:
```

So the canonical reported taxonomy is:

| Official category | Tasks | Composition |
|---|---:|---|
| sde | 69 | |
| hr | 29 | |
| pm | 28 | |
| admin | 15 | |
| ds | 14 | |
| finance | 12 | |
| **other** | **8** | `bm` 1 + `example` 1 + `ml` 2 + `qa` 2 + `research` 2 |
| **Total** | **175** | |

Note the `example` task is *included* in the released image list (`workspaces/README.md:68`: `ghcr.io/theagentcompany/example-image:1.0.0`) and in the eval sweep (`evaluation/run_eval.sh:92` iterates over every dir in `workspaces/tasks/`), so 175 includes the template task.

### 1.3 The README's own role/data-type taxonomy

`README.md:172-199` (verbatim):

```
## Exciting Features

- Diverse task roles:
  - Software Engineer
  - Product Manager
  - Data Scientist
  - Human Resource
  - Financial Staff
  - Administrator
- Diverse data types:
  - Coding tasks
  - Conversational tasks
  - Mathematical reasoning
  - Image processing
  - Text comprehension
- Multiple Agent Interaction
- Comprehensive scoring system
  - Result-based evaluation (primary)
  - Subcheckpoints checking (secondary)
- Multiple evaluation methods:
  - Deterministic evaluators
  - LLM-based evaluators
```

Note the README's 6 listed roles map onto the 6 named scoring categories; `other` (research/ml/qa/bm) is not advertised.

### 1.4 Second axis: service dependency (this is also reported per-category)

Every task declares its service deps in `dependencies.yml`. Measured counts across the 175 tasks:

| Service | Tasks depending on it |
|---|---:|
| rocketchat | **79** |
| gitlab | **71** |
| owncloud | **70** |
| plane | **17** |
| (empty deps file) | **1** |

`evaluation/summarise_results.py:338` reports per-service aggregates for exactly `['gitlab', 'plane', 'rocketchat', 'owncloud']`. Allowed values are documented in `workspaces/tasks/example/dependencies.yml:2`:

> "Available options are: rocketchat, gitlab, plane, and owncloud (all in lower cases)."

### 1.5 Third axis: NPC (colleague-chat) tasks vs. not

**41 of 175 tasks ship a `scenarios.json`** (measured: `ls workspaces/tasks/*/scenarios.json | wc -l` → 41). Breakdown by prefix:

| Prefix | NPC tasks |
|---|---:|
| hr | 14 |
| pm | 8 |
| admin | 8 |
| sde | 6 |
| finance | 3 |
| qa | 1 |
| example | 1 |
| **Total** | **41** |

This is confirmed independently by `evaluation/README_task_images.md:114`: `"excluded_scenarios_count": 41`, and `evaluation/README_task_images.md:146`: "Output: 134 task image URLs, excluded 41 tasks with scenarios.json".

There is a first-class run mode for these: `evaluation/run_eval.sh:41-43`

```bash
# RUN_NPC_TASKS_ONLY is a flag to run only tasks that have scenarios.json defined
# When true, tasks without scenarios.json will be skipped
RUN_NPC_TASKS_ONLY=false
```

### 1.6 Fourth axis: LLM-judged vs. purely deterministic

**53 of 175 evaluators call an LLM judge** (measured: `grep -l -E "evaluate_with_llm|evaluate_chat_history_with_llm|llm_complete" workspaces/tasks/*/evaluator.py | wc -l` → 53). Split:
- `evaluate_with_llm` used in **26** evaluators
- `evaluate_chat_history_with_llm` used in **25** evaluators
- (overlap exists; a few use raw `llm_complete`, e.g. `workspaces/tasks/ml-generate-gradcam/evaluator.py:94`)

Confirmed by `evaluation/README_task_images.md:119`: `"excluded_llm_count": 53` and `evaluation/README_task_images.md:152`: "Output: 122 task image URLs, excluded 53 tasks with LLM function calls".

Combined "fully deterministic, no NPC" subset: **105 tasks** (`evaluation/README_task_images.md:99` `"total_tasks": 105`, and `:158` "excluded 70 tasks (41 scenarios.json + 53 LLM functions, with overlap)").

So: **70/175 = 40% of TheAgentCompany tasks have a stochastic component** (LLM judge and/or LLM-driven NPC colleague).

### 1.7 Points budget per category (measured)

Parsing the literal first argument of `Checkpoint(N, ...)` in every `workspaces/tasks/*/evaluator.py`:

| Category | Tasks | Total points | Avg pts/task |
|---|---:|---:|---:|
| sde | 69 | 242 | 3.51 |
| pm | 28 | 71 | 2.54 |
| ds | 14 | 69 | 4.93 |
| admin | 15 | 56 | 3.73 |
| hr | 29 | 117 | 4.03 |
| finance | 12 | 54 | 4.50 |
| other | 8 | 52 | 6.50 |
| **TOTAL** | **175** | **661** | **3.78** |

Caveat: 25 of the 175 evaluators construct `Checkpoint(...)` with a computed/variable total rather than an int literal (e.g. `workspaces/tasks/pm-update-plane-issue-from-gitlab-status/evaluator.py`, `workspaces/tasks/hr-get-valid-password/evaluator.py`), so 661 is a lower bound on the literal-parseable budget.

Independent cross-check by parsing the human-readable `checkpoints.md` header line `"This task has N points in total"` (present in 147/175 files): **639 declared points** (sde 240, hr 127, pm 87, ds 52, admin 51, finance 41, other 41). The two methods agree to within ~3%.

Checkpoint-count distribution per task (literal parse): min 0 (variable-total tasks), max 8, median 3, mean 2.70. Point distribution: max 12, median 4.

---

## 2. Task definition schema (C6)

### 2.1 The canonical on-disk layout

`workspaces/README.md:5-19`:

```
├── base_image/
│   ├── Dockerfile
│   ├── init.sh
│   ├── eval.py
│   └── ...
├── tasks/
│   └── admin-arrange-meeting-rooms-image/
│       ├── Dockerfile
│       ├── evaluator.py
│       ├── checkpoints.md
│       ├── dependencies.yml
│       ├── task.md
|   └── ...
```

`workspaces/README.md:21-28` (verbatim, and note the **bolded "only"**):

> - base_image is the folder that contains shared functions, evaluation utilities, image build scripts, and other scaffolds.
> - tasks is the folder for definitions of all 175 tasks, within which
>   - Dockerfile defines the environment of each task setup
>   - evaluator.py defines all checkpoint grading functions
>   - checkpoints.md is the documentation for grading functions (for human reference only)
>   - dependencies.yml defines the list of service dependencies
>   - task.md is the task specification, contains background and requirements of each task, and is the **only** file that should be prompted to agents

### 2.2 Measured file inventory across all 175 task dirs

| File | Count | Mandatory? |
|---|---:|---|
| `task.md` | 175 | yes (CI-enforced) |
| `checkpoints.md` | 175 | yes (CI-enforced) |
| `evaluator.py` | 175 | yes (CI-enforced) |
| `Dockerfile` | 175 | yes (CI-enforced) |
| `dependencies.yml` | 175 | yes (CI-enforced) |
| `Makefile` | 175 | yes (CI-enforced) |
| `scenarios.json` | 41 | optional (NPC tasks) |
| `README.md` | 10 | optional |
| `pre_init.py` | 6 | optional |
| `populate_data.py` | 6 | optional |
| `post_init.py` | 2 | optional |
| task-specific data (CSV/XLSX/PDF/PPTX/JAVA/GO/PT…) | many | optional |

There is **no `checkpoints.yml`** and **no `utils.py`** convention — checkpoints are prose in `checkpoints.md` and code in `evaluator.py`.

### 2.3 Runtime layout inside the task container

`README.md:88-102`:

```
/utils
├── evaluator.py.enc
├── init.sh
├── config.py
├── common.py
├── eval.py
├── npc
├── ...
/instruction
├── task.md
├── ...
/workspace
├── ...
```

`README.md:104-106`:

> where `/utils/init.sh` is the script you must run to initialize the task environment,
> `/utils/eval.py` is the entrypoint to run the grading functions, and
> `/instruction/task.md` is the task instruction for the examinee, i.e. your agent.

The three directories are created in `workspaces/base_image/Dockerfile:6-23`, with an explicit access comment on line 6:

```dockerfile
# create utils directory (examinee MUST not access this directory)
RUN mkdir -p /utils
...
# create instruction directory (examinee should read instructions from here)
RUN mkdir -p /instruction
# create and set up working directory (for examinee to complete its task)
RUN mkdir -p /workspace
WORKDIR /workspace
```

The task-file → container-path wiring is a set of Docker `ONBUILD` triggers in the base image, `workspaces/base_image/Dockerfile:68-79`:

```dockerfile
################## ONBUILD (child images) SETUP #############
# persist utilities files in the exam image
ONBUILD COPY *.py /utils/

ONBUILD COPY dependencies.yml /utils/

# persist instruction files needed by the examinee
ONBUILD COPY task.md /instruction/

# prevent examinee from accessing evaluator
ONBUILD RUN python /utils/encrypt.py && rm /utils/evaluator.py /utils/encrypt.py
```

That last line is the mechanism that hides the rubric from the agent (see §3.4).

### 2.4 CI-enforced schema (structural validation)

`.github/validate_task_structure.sh` hard-fails a PR unless every task dir satisfies:

- lowercase dir name (`:7-11`)
- `task.md` exists (`:16-20`)
- `evaluator.py` exists **and contains at least one `@grader` annotation** (`:22-31`):
  ```bash
  # Check for at least one @grader annotator
  if ! grep -q "@grader" evaluator.py; then
      echo "Error: evaluator.py must contain at least one @grader annotator, see example task for reference"
      exit 1
  fi
  ```
- `Dockerfile` exists and starts `FROM ghcr.io/theagentcompany/task-base-image:1.0.0` (`:33-41`)
- `Dockerfile` contains **no `CMD` and no `ENTRYPOINT`** (`:42-52`), with rationale:
  > "we don't allow CMD or ENTRYPOINT in task Dockerfiles, because OpenHands, or any other agent might need to build their custom images on top of the task image, and override the default CMD or ENTRYPOINT"
- `Makefile` exists, has a `build` target, and `IMAGE_NAME=<dir>-image` / `CONTAINER_NAME=<dir>` (`:54-78`)
- `checkpoints.md` exists (`:80-84`)
- `dependencies.yml` exists and passes `.github/validate_dependencies.py` (`:86-92`)

### 2.5 Representative task A — `sde-close-an-issue` (minimal deterministic SDE task)

Files: `Dockerfile`, `Makefile`, `checkpoints.md`, `dependencies.yml`, `evaluator.py`, `task.md` (6 files, no NPC).

`workspaces/tasks/sde-close-an-issue/task.md` (complete, 1 line):

```
Go to http://the-agent-company.com:8929/root/openhands/-/issues/3797, reply with "Closing due to inactivity", and close the issue.
```

`workspaces/tasks/sde-close-an-issue/checkpoints.md` (complete):

```markdown
# Checkpoints

This task has 2 points in total. 

## Checkpoint 1 (1pts)

"inactivity" keyword appears in the comment

## Checkpoint 2 (1pt)

issue is closed
```

`workspaces/tasks/sde-close-an-issue/evaluator.py` (complete):

```python
import requests

import logging
from typing import List

from scoring import Result, Checkpoint
from common import *

project_path = "root/openhands" 
issue_iid = "3797"
target_comment = "Closing due to inactivity"


@grader
def grade_checkpoint1():
    try:
        comments_response = make_gitlab_request(project_path, f"issues/{issue_iid}/notes")
        comments_response.raise_for_status()
        comments_data = comments_response.json()
        has_target_comment = any(target_comment in comment['body'] for comment in comments_data)
        
        return has_target_comment
    except Exception as e:
        logging.error(f"Get comment failed: {e}")
        return False


@grader
def grade_checkpoint2():
    try: 
        issue_response = make_gitlab_request(project_path, f"issues/{issue_iid}")
        issue_response.raise_for_status()
        issue_data = issue_response.json()
        return issue_data['state'] == 'closed'
    except Exception as e:
        logging.error(f"Error fetching issue status: {e}")
    return False


def grade_checkpoints(trajectory="") -> Result:
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints)

    passed1 = grade_checkpoint1()
    checkpoints.append(Checkpoint(1, int(passed1)))

    passed2 = grade_checkpoint2()
    checkpoints.append(Checkpoint(1, int(passed2)))

    return result
```

`workspaces/tasks/sde-close-an-issue/Dockerfile` (complete, 1 line): `FROM ghcr.io/theagentcompany/task-base-image:1.0.0`
`workspaces/tasks/sde-close-an-issue/dependencies.yml` (complete): `- gitlab`

### 2.6 Representative task B — `pm-update-sprint-cycles` (PM, Plane + RocketChat, `bonus_for_completing_final`)

`workspaces/tasks/pm-update-sprint-cycles/task.md` (complete):

```
Move all unfinished issues from the current sprint to the next sprint for the project "RisingWave" and inform the relevant assignees in the `#project-streamdb` channel on Rocket.Chat.
Access Plane at http://the-agent-company.com:8091/. Navigate to 'Cycles' in the "RisingWave" project. Identify all issues that remain "To Do" or "In Progress" or "Backlog" in the active sprint.

Move Issues to Next Sprint. Select each unfinished issue and change its sprint assignment to the upcoming sprint cycle.

Notify Assignees on Rocket.Chat. at http://the-agent-company.com:3000/project-streamdb In the `#project-streamdb` channel, post a message tagging the relevant team members for each issue using the format:
     '@AssigneeName, your issue [Issue Title/ID] has been moved to the next sprint. Please prioritize it accordingly.'
```

`workspaces/tasks/pm-update-sprint-cycles/checkpoints.md` (complete) — note the naming convention "Checkpoint Final":

```markdown
# Checkpoints

Total checkpoints worth 4 points.

## Checkpoint 1 (1pt)

Accessed Plane and navigated to "RisingWave" > "Cycles" for the active sprint.

## Checkpoint 2 (2pts)

Identified all unfinished issues (To Do, In Progress, or Blocked) in the active sprint and moved them to the upcoming sprint cycle.


## Checkpoint Final (1pts)

Notified assignees on Rocket.Chat #project-streamdb channel about moved issues, using the specified format:
'@AssigneeName, your issue [Issue Title/ID] has been moved to the next sprint. Please prioritize it accordingly.'
```

`workspaces/tasks/pm-update-sprint-cycles/evaluator.py:48-141` (abridged — checkpoint bodies + the scoring assembly):

```python
@grader
def grade_checkpoint1(trajectory):
    """Check if the evaluator accessed 'RisingWave' project and navigated to 'Cycles'."""
    # This check can be simulated by a keyword in the trajectory, e.g., accessing "Cycles" section
    return "RisingWave" in trajectory and "Cycles" in trajectory

@grader
def grade_checkpoint2():
    """Check if specific issues are present in the 'Sprint 2' cycle."""
    project_name = "RisingWave"
    required_issue_names = {
        "Identify necessary operators and requirements",
        "Conduct memory usage analysis"
    }
    project_id = get_plane_project_id(project_name)
    ...
    sprint_2_cycle_id = get_cycle_id_by_name(project_id, "Sprint 2")
    ...
    issues_in_sprint_2 = get_plane_issues_by_project_cycle(project_id, sprint_2_cycle_id)
    issue_names_in_sprint_2 = {issue.get("name") for issue in issues_in_sprint_2}
    return required_issue_names.issubset(issue_names_in_sprint_2)

@grader
def grade_checkpoint_final():
    """Confirm that notification messages were posted to Rocket.Chat ..."""
    keywords = [
    ["liu_qiang", "identify necessary operators and requirements"],
    ["zhang_wei", "conduct memory usage analysis"]
    ]
    if not check_rocketchat_message_posted_keyword_set(rocket, "project-streamdb", keywords):
        return False
    return True

def grade_checkpoints(trajectory=""):
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints, bonus_for_completing_final)

    # Checkpoint 1: Access 'RisingWave' project and navigate to 'Cycles'
    passed1 = grade_checkpoint1(trajectory)
    checkpoints.append(Checkpoint(1, int(passed1)))

    # Checkpoint 2: Identify unfinished issues and move them to the next sprint
    passed2 = grade_checkpoint2()
    checkpoints.append(Checkpoint(2, 2 * int(passed2)))

    # Checkpoint 3: Notify assignees on Rocket.Chat
    passed3 = grade_checkpoint_final()
    checkpoints.append(Checkpoint(1, int(passed3)))

    return result
```

Key structural detail: checkpoint 2 is worth 2 points and the code writes `Checkpoint(2, 2 * int(passed2))` — i.e. **within a single checkpoint the score is all-or-nothing**; partial credit lives *between* checkpoints, not inside one. (`ds-predictive-modeling` is the exception, §2.7.)

### 2.7 Representative task C — `ds-predictive-modeling` (DS, graded ML metrics, tiered score inside one checkpoint)

`workspaces/tasks/ds-predictive-modeling/task.md` (complete):

```
On our office cloud at http://the-agent-company.com:8092/, find "/Documents/Financials/stock_train_raw.csv", 
build a machine learning pipeline in scikit-learn to predict the daily closing price of stock. 
Save your model's predictions to the test data "/Documents/Financials/stock_test.csv" as "/Documents/Financials/stock_test_answer.csv" 
with one column named "Close Price". You will be evaluated on Mean Squared Error 
(MSE), Mean Absolute Error (MAE), and R² score, with a focus on maximizing the R² score.
```

`workspaces/tasks/ds-predictive-modeling/checkpoints.md` (complete):

```markdown
# Checkpoints
This task has 3 points in total. 

## Checkpoint 1 (3pts)
3 credit granted if MSE < 500, MAE < 10, R^2 score > 0.8
2 credits granted if MSE < 550, MAE < 20, R^2 score > 0.7
No credits granted if MSE > 550, MAE > 20, R^2 score < 0.7
```

`workspaces/tasks/ds-predictive-modeling/evaluator.py` (complete):

```python
from typing import List
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scoring import Result, Checkpoint
from common import grader, check_file_in_owncloud_directory, get_binary_file_content_owncloud
from io import BytesIO
import logging

@grader
def grade_checkpoint1():
    file_name = "stock_test_answer.csv"
    dir_name = "Documents/Financials"
    if not check_file_in_owncloud_directory(file_name, dir_name):
        return 0

    content = get_binary_file_content_owncloud(file_name, dir_name)
    if not content:
        logging.warning("Failed to download content {file_name}")
        return 0

    try:
        stock_test_answer = pd.read_csv(BytesIO(content))
    except Exception as e:
        logging.warning(f"Failed to read {file_name}: {e}")
        return 0
    
    golden_answer = pd.read_csv('/utils/golden_answer.csv')

    actual, pred = golden_answer['Close Price'], stock_test_answer['Close Price']
    mse = mean_squared_error(actual, pred)
    mae = mean_absolute_error(actual, pred)
    r2 = r2_score(actual, pred)

    logging.info(f'On private test dataset, MSE: {mse}, MAE: {mae}, R^2: {r2}')
    
    # 3 credit granted if MSE < 500, MAE < 10, R^2 score > 0.8
    if mse < 500 and mae < 10 and r2 > 0.8:
        return 3
    # 2 credits granted if MSE < 550, MAE < 20, R^2 score > 0.7
    elif mse < 550 and mae < 20 and r2 > 0.7:
        return 2
    # No credits granted if MSE > 550, MAE > 20, R^2 score < 0.7
    else:
        return 0


def grade_checkpoints(trajectory="") -> Result:
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints)
    checkpoints.append(Checkpoint(3, int(grade_checkpoint1())))

    return result
```

This is the clearest example of a **graded (non-binary) checkpoint**: `grade_checkpoint1` returns 0/2/3 and it is passed straight into `Checkpoint(3, ...)`. The golden answer is a **private held-out CSV baked into the image** at `/utils/golden_answer.csv` (`workspaces/tasks/ds-predictive-modeling/Dockerfile:8`: `COPY golden_answer.csv /utils`) — the agent cannot read `/utils`.

### 2.8 Representative task D — `hr-check-attendance-multiple-days-department-with-chat` (HR, NPC + spreadsheet, 4 files of task data)

Files: `april-attendance-data.csv`, `checkpoints.md`, `department.txt`, `dependencies.yml`, `Dockerfile`, `evaluator.py`, `Makefile`, `scenarios.json`, `task.md`.

`Dockerfile` (complete):

```dockerfile
FROM ghcr.io/theagentcompany/task-base-image:1.0.0

# install libraries needed for evaluation
RUN pip install pandas==2.2.3
RUN pip install openpyxl==3.1.5

COPY scenarios.json /npc

COPY april-attendance-data.csv /utils
COPY department.txt /utils
```

Note: the *ground-truth* copies of the data go to `/utils` (hidden), the *agent-facing* copies live in ownCloud. `department.txt` is the golden department mapping the agent has to reconstruct **by chatting with three NPCs**:

```
• Technical: Sarah Johnson, Li Ming, Zhang Wei, Wang Fang, Mike Chen, Emily Zhou, Liu Qiang, Alex Turner, Emma Lewis, Jessica Chen
• Sales/Marketing: Mark Johnson, Jessica Lee
• HR: Chen Xinyi
• Finance: David Wong
• Product/UX: Huang Jie, Sophia Rodriguez
• Documentation: Priya Sharma
```

Evaluator assembly (`workspaces/tasks/hr-check-attendance-multiple-days-department-with-chat/evaluator.py:131-180`):

```python
@grader
def grade_checkpoint1(trajectory):
    urls = ["dir=/Documents/Human%20Resources%20Team/Attendance"]
    return all(url in trajectory for url in urls)

@grader
def grade_checkpoint2():
    chat_history1 = get_rocketchat_personal_chat_history(rocket, "Chen Xinyi")
    chat_history2 = get_rocketchat_personal_chat_history(rocket, "David Wong")
    chat_history3 = get_rocketchat_personal_chat_history(rocket, "Mark Johnson")
    return len(chat_history1) > 0 and len(chat_history2) > 0 and len(chat_history3) > 0

@grader
def grade_checkpoint3():
    if not check_excel_file_exists("/workspace/department-april-attendance.xlsx"):
        return False
    ...
    return set(df.columns).issuperset(set(["department", "departmentaverageworklength", ...]))

@grader
def grade_checkpoint4():
    agent_output = standardize_df(read_excel("/workspace/department-april-attendance.xlsx"))
    department_df = parse_department_data('/utils/department.txt')
    employee_df = analyze_csv('/utils/april-attendance-data.csv')
    merge_expected_df = standardize_df(aggregate_by_department(...))
    ...
    return compare_row_by_row(agent_output, merge_expected_df)

def grade_checkpoints(trajectory=""):
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints, bonus_for_completing_final)
    checkpoints.append(Checkpoint(1, grade_checkpoint1(trajectory)))
    checkpoints.append(Checkpoint(1, grade_checkpoint2()))
    checkpoints.append(Checkpoint(1, grade_checkpoint3()))
    checkpoints.append(Checkpoint(1, grade_checkpoint4()))
    return result
```

The ground truth is recomputed *in Python inside the evaluator* (`analyze_csv` at `:62-101`, `aggregate_by_department` at `:108-119`) and compared numerically with `abs(answer - expected) < 1e-5` (`:57`). Column names are normalised before comparison (`standardize_df`, `:122-128`: strip spaces, lowercase, strip hyphens) — a deliberate leniency so cosmetic formatting differences don't fail the agent.

Also note a genuine bug: the task text says `"department-april-attendace.xlsx"` (`task.md:8`, typo'd) but the evaluator checks `"/workspace/department-april-attendance.xlsx"` (`evaluator.py:147`) and `checkpoints.md:15` says `"department-april-attendance.xlsx"`.

### 2.9 The developer-facing spec of `grade_checkpoints`

`workspaces/tasks/example/README.md:14-38`:

> Every task folder should have a `checkpoints.md` that documents the checkpoint rubrics.
>
> Every task folder must have an `evaluator.py` that can be run to grade the examinee's work. The `evaluator.py` must not have a main function. Instead, it must have a `grade_checkpoints` function that returns a `Result` object.

```python
def grade_checkpoints(trajectory="") -> Result:
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints, bonus_for_completing_final)

    passed1 = grade_checkpoint1(trajectory)
    checkpoints.append(Checkpoint(1, int(passed1)))

    passed2 = grade_checkpoint2()
    checkpoints.append(Checkpoint(1, int(passed2)))

    passed3 = grade_final_checkpoint()
    checkpoints.append(Checkpoint(2, 2 * int(passed3)))

    return result
```

Note the subtle-but-important trick: `Result` holds a **reference** to the same `checkpoints` list that is mutated afterwards, so returning `result` (constructed before any checkpoint ran) still yields the populated list.

`workspaces/tasks/example/evaluator.py:1-11` states the quality bar for evaluators:

```python
"""Summary of evaluator for example task

You don't have to write a summary for the evaluator, although documentation is
strongly encouraged.

A good evaluator should:
1. be robust - it shouldn't abort because of its own bug or lack of fail over mechanism
2. be deterministic and idempotent
3. grant partial credits if possible
4. encourage but not require trajectory for grading
"""
```

---

## 3. Input documents / agent context (D1, D3)

### 3.1 What the agent is actually prompted with

`evaluation/run_eval.py:129-132`:

```python
    instruction = "Complete the task in /instruction/task.md"

    if 'gitlab' in dependencies:
        instruction += "\n\nGitlab username is 'root' and password is 'theagentcompany'"
```

`README.md:153-158` confirms this is the baseline prompt and hints at an alternative:

> Now you can prompt the agent to work on the task. The task instruction is in `/instruction/task.md`.
> In the baseline experiments, [the initial prompt] is as simple as
> > Complete the task in /instruction/task.md
> but you could choose to extract the content in `/instruction/task.md` and include in the system prompt.

The fake-user turn injected when the agent stalls (`evaluation/run_eval.py:103-123`):

```python
def codeact_user_response(state: State) -> str:
    msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'If you think you have solved the task, please finish the interaction.\n'
        'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP.\n'
    )

    if state.history:
        # check if the agent has tried to talk to the user 3 times, if so, let the agent know it can give up
        user_msgs = [...]
        if len(user_msgs) >= 2:
            # let the agent know that it can give up when it has tried 3 times
            return (
                msg
                + 'If you want to give up, run: <execute_bash> exit </execute_bash>.\n'
            )
    return msg
```

Login is done *for* the agent before it starts, so credential handling is not part of the eval (`evaluation/browsing.py:155-159`):

> Logs in to all the websites that are needed for the evaluation. Once logged in, the sessions would be cached in the browser, so OpenHands agent doesn't need to log in to these websites again.

`docs/EVALUATION.md:78-86` says benchmark users may choose any login method:

> "all services require username and password. We allow benchmark users to use whatever ways they want to provide the username and password. You could add username and password to the prompt, or cache the login session cookie in the browser. For reference, in the baseline evaluation, we use OpenHands platform to deterministically login to all services before letting the agent work on the task."

### 3.2 One FULL rich `task.md` — `hr-internal-tooling-slides` (the longest in the repo, 1973 bytes)

```markdown
Develop slides to introduce the products and main internal tools used by TAC, aimed at onboarding new hires, serving as a foundational overview for new employees. This presentation should cover the purpose and functionalities of each tool, with detailed descriptions for RocketChat, GitLab, Owncloud, and Plane. Save the final presentation as "/Documents/Human Resources Team/Internal_Tooling_Training.pptx" at OwnCloud (http://the-agent-company.com:8092). Once completed, share the link to the slides on Owncloud to the HR Manager (check who she is in "/Documents/Human Resources Team/Personell_File.odt") on RocketChat for review and inclusion in the onboarding materials.

* In the first slide, provide a reasonable theme and title.
* According to TAC_overview.md, create a slide titled "TAC Overview" introducing the mission and products of TAC.
* RocketChat: Navigate to RocketChat at http://the-agent-company.com:3000/. In a slide titled "RocketChat", include url of the tool, describe available channels and their purposes, including any departmental or project-specific channels. Introduce which channels are default channels.
* GitLab: Navigate to Gitlab at http://the-agent-company.com:8929/. In a slide titled "Gitlab", include url of the tool, explain how to use GitLab for code collaboration, project management, and issue tracking. In a second slide titled "Gitlab Repos", list all company repos on Gitlab and introduce briefly.
* OwnCloud: Navigate to OwnCloud at http://the-agent-company.com:8092. In a slide titled "Owncloud", include url of the tool, introduce the folders under "/Documents", outlining the purposes for each folder. 
* Plane: Navigate to Plane at http://the-agent-company.com:8091/. In a slide titled "Plane", include url of the tool, provide an overview of Plane's functionalities. Describe how to use the analytics page to track project metrics.

Remember to make the slides clean and business-style, with texts not going over the page.
```

Observations for D1/D3:
- The fictional company is **"TAC" / "The Agent Company"**, hosted at the synthetic domain `the-agent-company.com`. Service URLs are always given inline in the task text (`docs/EVALUATION.md:69`: "If any web service is involved in the task, the URL of the service is provided in the task instruction.").
- Tasks routinely require **cross-service navigation** (ownCloud → RocketChat → GitLab → Plane) and **indirection** (the agent must *look up* who the HR Manager is in an .odt file rather than being told).
- Note this task deliberately does **not** name the colleague — the agent has to derive identity from a document. Compare `admin-arrange-meeting-rooms/task.md`, which is written in first-person colloquial voice ("Good morning! We're facing a scheduling challenge at office...") and ends with "please tell the answer to Chen Xinyi on RocketChat: http://the-agent-company.com:3000/. Oh btw, please also write the answer down in /workspace/ans.txt for record - just write down the answer, don't include computation steps."

### 3.3 A social/temporal task — `qa-escalate-emergency/task.md` (complete)

```
You are a quality engineer. Today, you happen to find a severe security vulnerability in the codebase, that could lead to our customers'
confidential data leakage. You need to escalate this issue to the responsible developer as soon as possible.

Goto http://the-agent-company.com:3000/, find Zhang Wei, and tell them about this emergency. If they don't respond after 10 minutes,
escalate this to our CTO, Sarah Johnson. Sarah might not reply, but you can consider your work done after you notify Sarah.
```

with a **wall-clock** checkpoint (`workspaces/tasks/qa-escalate-emergency/evaluator.py:26-41`):

```python
@grader
def grade_checkpoint3():
    chat_with_sde = get_rocketchat_personal_chat_history(rocket, SDE_NAME, content_only=False)
    chat_with_cto = get_rocketchat_personal_chat_history(rocket, CTO_NAME, content_only=False)
    try:
        # check whether the first message sent to CTO is at least 10 minutes after the first message sent to SDE
        ...
        time_diff = timestamp_cto - timestamp_sde
        return time_diff >= 600
```

### 3.4 Where the checkpoints are hidden from the agent

Three layers:

1. **Rubric prose is never copied into the image.** Only `*.py`, `dependencies.yml` and `task.md` are `ONBUILD COPY`'d (`workspaces/base_image/Dockerfile:70-75`). `checkpoints.md` never enters the container.
2. **`evaluator.py` is Fernet-encrypted at image build time and the plaintext deleted** (`workspaces/base_image/Dockerfile:78`):
   ```dockerfile
   ONBUILD RUN python /utils/encrypt.py && rm /utils/evaluator.py /utils/encrypt.py
   ```
   `workspaces/base_image/encrypt.py` (complete key derivation):
   ```python
   key_bytes = b'theagentcompany is all you need'
   def pad_key(key):
       while len(key) < 32:
           key += b'\x00'
       return key[:32]
   fernet = Fernet(base64.urlsafe_b64encode(pad_key(key_bytes)))
   ```
   The decryption key is **hardcoded and publicly documented** — `docs/EVALUATION.md:13-15`:
   > "To prevent the agent from peeking at the evaluator code, all `/utils/evaluator.py` files, which contain the grading functions, are encrypted. The evaluator entrypoint, `/utils/eval.py`, contains the decryption code, and you need to pass the decryption key as an environment variable when you run it: `DECRYPTION_KEY='theagentcompany is all you need'`."

   So this is **obfuscation, not security** — an agent with shell access and the public repo could decrypt `/utils/evaluator.py.enc` itself. It only defeats accidental/naive peeking.
3. **Social contract**, `docs/EVALUATION.md:124-127`:
   > "Benchmark users are allowed to inspect checkpoint rubrics to ensure the trajectory contains all necessary information used in graders, but examinees (e.g. agents) are not allowed to read checkpoint rubrics or evaluation code."

Note the eval harness itself decrypts at grade time (`workspaces/base_image/eval.py:22-59`) and **writes the plaintext back to `/utils/evaluator.py`** (line 47-48) — i.e. after grading, the evaluator source is sitting in the container in the clear.

### 3.5 The simulated colleagues (NPCs)

**Global roster: 18 profiles** (17 humans + 1 "theagentcompany AI") in `servers/rocketchat/npc/npc_definition.json`, mirrored by 17 RocketChat credential entries in `workspaces/base_image/npc/npc_credential.json`.

Full name list: theagentcompany AI, Sarah Johnson, Li Ming, Zhang Wei, Wang Fang, Mike Chen, Emily Zhou, Liu Qiang, Priya Sharma, Mark Johnson, Jessica Lee, Chen Xinyi, David Wong, Huang Jie, Sophia Rodriguez, Alex Turner, Emma Lewis, Jessica Chen.

A real entry (`servers/rocketchat/npc/npc_definition.json`, second element):

```json
{
  "first_name": "Sarah",
  "last_name": "Johnson",
  "age": 42,
  "occupation": "CTO",
  "gender": "Woman",
  "gender_pronoun": "She/Her",
  "public_info": "Responsibilities: Technical strategy planning, R&D team leadership, new technology assessment; Project: Oversees all technical projects; Skills: N/A",
  "slack_channels": "All technical channels, #general, #tech-talk"
}
```

The **full org chart** is documented as a table in `servers/rocketchat/npc/NPC.md:30-48`. Selected rows:

| Name | User Name | Occupation | Channels |
|---|---|---|---|
| Sarah Johnson | sarah_johnson | CTO | All technical channels, #general, #tech-talk |
| Li Ming | li_ming | Database Team Project Manager (JanusGraph) | #project-graphdb, #engineering, #tech-talk |
| Zhang Wei | zhang_wei | Senior Software Engineer, Streaming DB (RisingWave; Rust) | #project-streamdb, #engineering, #tech-talk |
| Wang Fang | wang_fang | AI Researcher (OpenHands) | #project-ai, #engineering, #tech-talk |
| Mike Chen | mike_chen | Senior SWE, AI Team (llama.cpp; C++/CUDA) | #project-ai, #engineering, #tech-talk |
| Emily Zhou | emily_zhou | SWE, Web Crawler Team (Colly; Go) | #project-webcrawler, #engineering, #tech-talk |
| Liu Qiang | liu_qiang | Quality Assurance Engineer | All project channels |
| Priya Sharma | priya_sharma | Documentation Engineer | All project channels |
| Mark Johnson | mark_johnson | Sales Director | #sales-marketing, #general |
| Jessica Lee | jessica_lee | Marketing Manager | #sales-marketing, #general |
| Chen Xinyi | chen_xinyi | Human Resources Manager | #hr-announcements, #general |
| David Wong | david_wong | Finance Director | #general |
| Huang Jie | huang_jie | Product Manager, Search (OpenSearch) | #project-search, #product, #tech-talk |
| Sophia Rodriguez | sophia_rodriguez | UX Designer | All project channels, #product |
| Alex Turner | alex_turner | SWE, Low-Code Platform (Node-RED) | #project-lowcode, #engineering |
| Emma Lewis | emma_lewis | SWE, API Team (API-server) | #engineering, #tech-talk |
| Jessica Chen | jessica_chen | Frontend SWE (E-commerce redesign) | #project-ecommerce, #frontend, #tech-talk |

**15 pre-baked RocketChat channels** (`servers/rocketchat/npc/NPC.md:10-26`): engineering(2), general, help-desk(14), hr-announcements(3), kudos(19), product(4), project-ai(6), project-graphdb(6), project-lowcode(5), project-search(5), project-streamdb(5), project-webcrawler(6), random(8), sales-marketing(3), tech-talk(12).

The **full NPC persona schema** is in `servers/rocketchat/npc/NPC_CONFIG.md:5-24` — including psychometrics and a `secret` field:

```json
{
  "first_name": "Alex", "last_name": "Johnson", "age": 29,
  "occupation": "Front-End Engineer",
  "profile_picture": "https://www.svgrepo.com/svg/88702/avatar",
  "gender": "Male", "gender_pronoun": "He/Him",
  "public_info": "Alex is a front-end engineer with a passion for creating intuitive and responsive web interfaces...",
  "big_five": "Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism",
  "moral_values": ["Integrity", "Responsibility", "Fairness"],
  "schwartz_personal_values": ["Achievement", "Self-Direction", "Benevolence"],
  "personality_and_values": "Alex values creativity and precision in his work... Alex is a bit impatient with general questions and prefers to focus on specific tasks.",
  "decision_making_style": "Analytical and collaborative...",
  "secret": "Alex once considered switching to a full-stack role but ultimately stuck with front-end development due to his love for design.",
  "model_id": "front-end-engineer-001",
  "mbti": "INTP"
}
```

Personas are **global**, task context is **per-task** — `workspaces/tasks/example/README.md:140-156`:

> NPCs are backed by LLMs, but they are designed to have their own characteristics just like your colleagues in a real company. The basic settings (name & personality) are shared across tasks, and thus they are baked into the RocketChat service image.
> However, different tasks might have different scenario settings. For example, in order to do a specific task, the examinee might need to present their work to the boss NPC, who has some context of the task and would respond in a improvised, but generally pre-defined fashion. This context is defined in each individual task image.

### 3.6 `scenarios.json` — the per-task NPC brief (quoted verbatim)

Minimal one-NPC example, `workspaces/tasks/sde-reply-community-issue-by-asking-npc/scenarios.json` (complete):

```json
{
  "Mike Chen": {
    "extra_info": "Someone will ask you to solve a bug.",
    "strategy_hint": "If someone asks about OpenHands' issue #4158, you can respond with: 'Adding a few seconds to the timeout limit can resolve most timeout issues."
  }
}
```

Three-NPC information-distribution example, `workspaces/tasks/hr-check-attendance-multiple-days-department-with-chat/scenarios.json` (complete):

```json
{
  "Chen Xinyi": {
    "extra_info": "Someone will ask you about who are in the finance or in the technical department.",
    "strategy_hint": "Answer that David Wong is in the finance department if asked. Answer Sarah Johnson, Li Ming, Zhang Wei, Wang Fang, Mike Chen, Emily Zhou, Liu Qiang, Alex Turner, Emma Lewis, and Jessica Chen are in the technical department if asked."
  },
  "David Wong": {
    "extra_info": "Someone will ask you about who are in the sales/marketing or in the HR department.",
    "strategy_hint": "Answer that Chen Xinyi is in the HR department if asked. Answer Mark Johnson and Jessica Lee are in the sales/marketing department if asked."
  },
  "Mark Johnson": {
    "extra_info": "Someone will ask you about about who are in the Product/UX or in the documentation department.",
    "strategy_hint": "Answer that Huang Jie and Sophia Rodriguez are in the Product/UX department if asked. Answer Priya Sharma is in the documentation department if asked."
  }
}
```

A 17-NPC "onboarding relay" example, `workspaces/tasks/example/scenarios.json` — the agent must chain-introduce itself through the whole company, each NPC pointing at the next:

```json
{
  "Alex Turner": {
    "extra_info": "Someone will introduce themselves to you with a greeting and ask you for the company's wiki page. The company's wiki page is http://the-agent-company.com:8929/root/doc/-/wikis, which stores company-wide documentation that can be especially useful for new hires.",
    "strategy_hint": "You should only tell the AI agent the wiki page URL if they ask related questions. If you don't know the answer to a question, you could refer the AI agent to the wiki. Only if they ask who to talk to next, instruct them to introduce themselves to Chen Xinyi."
  },
  "Chen Xinyi": {
    "extra_info": "Someone will introduce themselves to you with a greeting.",
    "strategy_hint": "Introduce yourself back to the person. Then instruct them to introduce themselves to David Wong."
  },
  ...
  "Zhang Wei": {
    "extra_info": "Someone will introduce themselves to you with a greeting.",
    "strategy_hint": "Introduce yourself back to the person. Tell them there is no need to chat further with anyone else"
  }
}
```

### 3.7 How `scenarios.json` becomes an NPC goal prompt

`workspaces/base_image/npc/server.py:29-57` (complete function) — the fields are wrapped in pseudo-XML tags and appended to a fixed goal string:

```python
def get_scenarios(npc_first_name):
    with open(scenarios_file_path, 'r') as file:
        json_data = json.load(file)

    agent_scenario = json_data.get(npc_first_name)
    if not agent_scenario:
        raise RuntimeError("Didn't find the NPC scenarios in file")

    agent_goal = "You goal is to collaborate with AI agent in the working space."
    if "extra_info" in agent_scenario:
        agent_goal += " <extra_info>" + agent_scenario["extra_info"] + "</extra_info>"
    if "strategy_hint" in agent_scenario:
        agent_goal += " <strategy_hint>" + agent_scenario["strategy_hint"] + "</strategy_hint>"
    if "clarification_hint" in agent_scenario:
        agent_goal += " <clarification_hint>" + agent_scenario["clarification_hint"] + "</clarification_hint>"

    # sotopia is an agent-agent interaction framework, but here we are using it between
    # agent (NPC) and examinee. The framework requires us to define a goal for both
    # counter-parties, even though sotopia doesn't really control examinee.
    examinee_goal = "You need to seek help from another agent to complete your work."
    return  {
        "codename": "working_space_1" + npc_first_name,
        "scenario": "People are working in a startup communicating through rocketchat. There is an AI agent working with them.",
        "agent_goals": [
            examinee_goal,
            agent_goal
        ]
    }
```

The NPC role-play system prompt itself lives in `workspaces/base_image/npc/human_user_agent.py:31-46`:

```
Imagine you are {agent}, your task is to act/speak as {agent} would, keeping in mind {agent}'s social goal.
You can find {agent}'s goal (or background) in the 'Here is the context of the interaction' field.
Note that {agent}'s goal is only visible to you.
You should try your best to achieve {agent}'s goal in a way that align with their character traits. Please be aware that the tools available to AI agents are not accessible to you, so don't follow their arguments of using tools.
Additionally, maintaining the conversation's naturalness and realism is essential (e.g., do not repeat what other people has already said before).
IMPORTANT: You are communicating with other agents only through rocketchat, so any information you want to share with others should be outputted through rocketchat with the `speak` action. Don't say something like 'I have sent the information to your inbox'.
{history}.
You are at Turn #{turn_number}. Your available action types are
{action_list}.
Note: You can "leave" this conversation if 1. you have achieved your social goals, 2. this conversation makes you uncomfortable, 3. you find it uninteresting/you lose your patience, 4. or for other reasons you want to leave.

Please only generate a JSON string including the action type and the argument.
Your action should follow the given format:
{format_instructions}
```

NPCs are launched one process per NPC at task init (`workspaces/base_image/npc/run_multi_npc.py:21-29`), with a 30-second warm-up sleep. Conversation is bounded by `RuleBasedTerminatedEvaluator(max_turn_number=20, max_stale_turn=4)` (`workspaces/base_image/npc/server.py:142`).

---

## 4. Verification (G1, G4, G5) — checkpoint/scoring mechanism

### 4.1 The shared scoring library: `workspaces/base_image/scoring.py` (complete, 157 lines)

```python
from dataclasses import dataclass
from typing import List, Callable, Optional

@dataclass
class Checkpoint:
    total: int
    result: int
    
    def __post_init__(self):
        if not isinstance(self.total, int):
            raise TypeError(f"total must be an integer, got {type(self.total)}")
        if not isinstance(self.result, int):
            raise TypeError(f"result must be an integer, got {type(self.result)}")
        if self.total < 0:
            raise ValueError(f"total cannot be negative, got {self.total}")
        if self.result < 0:
            raise ValueError(f"result cannot be negative, got {self.result}")
        if self.result > self.total:
            raise ValueError(f"result ({self.result}) cannot be greater than total ({self.total})")

@dataclass
class Result:
    checkpoints: List[Checkpoint]
    scoring_strategy: Optional[Callable[[List[Checkpoint]], dict]] = None
    
    def __post_init__(self):
        if self.scoring_strategy is None:
            # Default scoring strategy: simple sum
            self.scoring_strategy = lambda checkpoints: {
                "total": sum(cp.total for cp in checkpoints),
                "result": sum(cp.result for cp in checkpoints)
            }
    
    @property
    def final_score(self) -> dict:
        return self.scoring_strategy(self.checkpoints)
    ...
    def to_dict(self) -> dict:
        """Convert the Result instance to a dictionary."""
        return {
            "checkpoints": [
                {"total": cp.total, "result": cp.result}
                for cp in self.checkpoints
            ],
            "final_score": self.final_score
        }
```
(`workspaces/base_image/scoring.py:1-62`)

**Partial credit** therefore works as: each `Checkpoint` carries a weight (`total`, an int) and an earned score (`result`, an int, `0 <= result <= total`). Weights are heterogeneous — 1pt for "found the right page", 2-3pts for the substantive final action. The per-task raw score is `(sum(result), sum(total))` — modulated by a per-task strategy.

### 4.2 The three scoring strategies (and how often each is used)

Measured across all 175 `evaluator.py` files:

| Strategy | Tasks | Source |
|---|---:|---|
| default (plain sum) | **112** | `scoring.py:28-32` |
| `bonus_for_completing_final` | **54** | `scoring.py:66-85` |
| `bonus_for_completing_any` | **7** | `scoring.py:89-120` |
| `bonus_for_completing_any_of_given_checkpoints` | **2** | `scoring.py:122-156` |

(`bonus_for_completing_any` users: `bm-classify-nationality`, `ds-organise-report-sus-data`, `finance-budget-variance`, `finance-invoice-matching`, `hr-create-career-ladder`, `hr-create-employee-manual`, `hr-salary-analysis`, `pm-prepare-meeting-with-customers`, `pm-monthly-attendance-slides` — 9 import lines, 9 call sites; the `_of_given_checkpoints` users are `pm-copy-plane-issues-to-gitlab` and `pm-update-project-milestones`.)

`scoring.py:65-85` — **"full credit if you finished"**:

```python
# Strategy: get full score if final checkpoint completes
def bonus_for_completing_final(checkpoints: List[Checkpoint]) -> dict:
    """
    If the final checkpoint is completed successfully (full score),
    award full points for all previous checkpoints.
    """
    if not checkpoints:
        return {"total": 0, "result": 0}
    
    total = sum(cp.total for cp in checkpoints)
    
    # Check if final checkpoint got full score
    final_checkpoint = checkpoints[-1]
    if final_checkpoint.result == final_checkpoint.total:
        # Award full points for all checkpoints
        result = sum(cp.total for cp in checkpoints)
    else:
        # Normal scoring
        result = sum(cp.result for cp in checkpoints)
    
    return {"total": total, "result": result}
```

`scoring.py:88-120` — **"don't punish a missing trajectory"** (this is the key robustness escape hatch, and the docstring explains exactly why):

```python
# Strategy: get credit for 1st checkpoint as long as any checkpoint passes
def bonus_for_completing_any(checkpoints: List[Checkpoint]) -> dict:
    """
    If any checkpoint is completed successfully (full score),
    award full points for the 1st checkpoint, regardless of its completion.

    The rationale is many tasks check trajectory as part of their 1st checkpoint,
    and the information to look up in the trajectory is necessary for any follow-up
    checkpoint to complete. Thus, as long as any follow-up task completes, the 1st
    checkpoint should be considered as complete, even if the trajectory is missing,
    or doesn't contain the keyword that the evaluator is looking for.
    """
```

`scoring.py:122-156` — same idea but restricted to a nominated subset, e.g. `Result(checkpoints, bonus_for_completing_any_of_given_checkpoints([3, 4]))` at `workspaces/tasks/pm-copy-plane-issues-to-gitlab/evaluator.py:50`. Note the 1-indexed→0-indexed conversion at `scoring.py:141`: `[checkpoints[i - 1] for i in given_checkpoints]`.

> Documentation caveat: `workspaces/tasks/example/README.md:45-48` refers to `bonus_for_completing_all`, which **does not exist** in `scoring.py`. The real name is `bonus_for_completing_final`. The README also says "In `base_image/scoring.py` you can find two pre-defined strategies" — there are actually three.

### 4.3 The `@grader` decorator — the per-checkpoint safety net

`workspaces/base_image/common.py:35-47` (complete):

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

Documented rationale, `workspaces/tasks/example/README.md:56-61`:

> Note that `common.py` contains a decorator, `@grader`, which can be used to annotate each individual `grade_checkpoint[X]` function. This is required as it would capture runtime errors and make the evaluator not fail the entire task. Annotated checkpoint functions would return `False` if any runtime error occurs, and is not already captured by the checkpoint function itself. CI would fail if there's no grader annotator in the entire `evaluator.py`.

**Important consequence for G5:** the `@grader` design deliberately **conflates environment failure with agent failure** at the checkpoint level. A GitLab 500, a network blip, or a bug in the evaluator all render as `False` = 0 points, indistinguishable from the agent not doing the work. The only signal is a log line.

### 4.4 The eval entrypoint: `workspaces/base_image/eval.py`

Flow (`eval.py:70-109`):
1. `decrypt_and_execute()` — Fernet-decrypt `/utils/evaluator.py.enc` → write plaintext `/utils/evaluator.py` → `importlib` load → bind `grade_checkpoints` (`:22-59`). Decryption failure raises `RuntimeError("Failed to decrypt evaluator")` (`:44`).
2. Load trajectory file if given; on any read error, warn and use `""` (`:61-68`).
3. `result = grade_checkpoints(trajectory)` (`:93`).
4. Type/shape assertions (`:95-99`):
   ```python
   if not isinstance(result, Result):
       raise TypeError(f"grade_checkpoints must return Result type, got {type(result)}")
   
   if not result.checkpoints:
       raise ValueError(f"Result must have at least one checkpoint, got {result}")
   ```
5. Dump `result.to_dict()` to `--result_path` (default `./result.json`).
6. Any exception → `logging.error("Failed to grade the task", exc_info=True); sys.exit(1)` (`:107-109`).

Invocation contract (`README.md:162-168`, `docs/EVALUATION.md:97-103`):

```bash
LITELLM_API_KEY=<environment_llm_api_key> \
LITELLM_BASE_URL=<environment_llm_base_url> \
LITELLM_MODEL=<environment_llm_model_name> \
DECRYPTION_KEY='theagentcompany is all you need' \
python_default /utils/eval.py --trajectory_path TRAJECTORY_PATH --output_path OUTPUT_PATH
```

(Note: docs say `--output_path`, the actual argparse flag is `--result_path` — `eval.py:80`. The harness uses the correct one: `evaluation/run_eval.py:170`.)

### 4.5 Trajectory-based checkpoints (the "did you look at it" signal)

**65 of 175 evaluators** contain the string `in trajectory` (measured). Typical form (`workspaces/tasks/example/evaluator.py:27-29`):

```python
@grader
def grade_checkpoint1(trajectory):
    return "8929/root/api-server" in trajectory
```

The trajectory is the OpenHands JSON event log, mounted into the container at `/outputs/traj_<task>.json` (`evaluation/run_eval.py:41`, `:53-54`, `:292`). Design guidance, `workspaces/tasks/example/README.md:63-76`:

> Some tasks require the examinee to conduct a series of steps, but not every step can be validated easily. For example, whether the examinee has accessed a web page is hard to validate programmatically. In this case, it is okay for benchmark developers to validate the trajectory file that documents the steps conducted. For example, whether a specific URL appears in the trajectory file.
> There's no specific format requirement on the trajectory file, but it MUST document the necessary steps conducted by the examinee. A trajectory file usually includes the URLs accessed, the commands run, the files modified, etc.
> **Note: benchmark developers shall use the trajectory file as the last resort.**

And `docs/EVALUATION.md:120-124`:

> "Note that trajectory file is optional. It is often used to grant partial credits. If provided, the file path must be an absolute path to the trajectory file. There is no specific requirement on the trajectory file's content and format, but it MUST record all steps conducted by the examinee (no matter it's agent or human being)."

**Reward-hacking exposure:** these are plain substring matches over the agent's own log. An agent that merely echoes the URL string (e.g. `echo "root/openhands/-/issues/4158"`) earns the point without visiting the page. TheAgentCompany contains no defense against this beyond the "last resort" guidance and the fact that most tasks put only 1 of N points on trajectory.

### 4.6 Where results are aggregated

- Per-task JSON written by the evaluator inside the container → moved to host as `eval_<task>-image.json` (`evaluation/run_eval.py:293`, `:298-299`).
- Trajectory saved as `traj_<task>-image.json` (`evaluation/run_eval.py:41`).
- Aggregation: `evaluation/summarise_results.py` — globs `eval_*.json` and `traj_*.json` from an outputs dir (`:135-148`), reads each `final_score.total` / `final_score.result` (`:78-82`), joins with per-task `dependencies.yml` for the service breakdown (`:250-260`), prints a Markdown report.
- Run: `poetry run python summarise_results.py <outputs_path>` (`evaluation/README.md:95`).

---

## 5. Flakiness and nondeterminism (G2)

### 5.1 Stochastic graders — 53/175 tasks (30%)

The judge extracts a boolean by **substring-matching `"yes"`** in the lowercased response (`workspaces/base_image/common.py:264-267`) — see §5.6 for the full quote. Any judge output containing "yes" anywhere (including "yes, but no" or a chain-of-thought that mentions "yes") passes. There is **no temperature setting, no seed, no self-consistency, no retry, no schema enforcement**.

`docs/EVALUATION.md:6-11` sets a floor on the judge model:

> "Since many tasks require LLMs to evaluate the results, and/or require NPCs backed by LLMs to play the roles of coworkers, we require you to provide an LLM API key as "environment LLM config". This LLM API key does not need to be the same as the one you use for your agent(s). **It needs to be as powerful as or at least close to `claude-3-5-sonnet-20241022` or `gpt-4o`.** For reference, all baseline results used `claude-3-5-sonnet-20241022` as the environment LLM. Please provide the environment LLM model you use when you submit your results to the leaderboard."

So **the evaluation result is a function of which environment LLM you chose** — the leaderboard requires you to declare it.

### 5.2 Stochastic environment — 41/175 tasks with LLM-driven NPCs

NPCs are Sotopia `LLMAgent`s driven by the same environment LLM (`workspaces/base_image/npc/run_one_npc.py:36-41`), with `temperature: float = 0.7` as the default in `agenerate_action_human` (`workspaces/base_image/npc/human_user_agent.py:17`). The NPC decides *whether to answer at all* and may `leave` the conversation (`human_user_agent.py:41`). If a checkpoint says "answer that David Wong is in the finance department", the NPC may paraphrase, refuse, or drift.

`servers/rocketchat/npc/NPC.md:96-106` documents known NPC limitations bluntly:

> * When run one NPC, NPC will reply only when your send massage. It will talk with you TURN by TURN
> * When multiple NPC in one channel, they will only reply your message. NPC cannot talk with each other in channel. If you send one message, all NPC will reply you. We can let only related agent reply. It is feasible, but not support now. Unless you need this feature, or just keep design concise.
> * **One NPC can run great now. Because of above problem. Unless neccessary in your task, don't use multiple NPC.**
> * Direct message multiple NPC will not cause mess. It run great now.

### 5.3 Wall-clock dependence

`workspaces/tasks/qa-escalate-emergency/evaluator.py:38`: `return time_diff >= 600` — the task scores a point only if ≥10 real minutes elapsed between messaging Zhang Wei and Sarah Johnson. This couples the score to agent latency, model speed, and network conditions.

Three SDE unit-test tasks block on `time.sleep(5)` while a server boots (`sde-write-a-unit-test-for-append_file-function/evaluator.py:29`, `.../scroll_down.../evaluator.py:28`, `.../search_file.../evaluator.py:31`); `sde-run-rising-wave-locally/evaluator.py:49` sleeps 8s and uses `subprocess.run(..., timeout=0.1)` at `:17`.

### 5.4 Bounded agent budget (affects reproducibility of the *agent* side)

`evaluation/run_eval.py:37-55`:

```python
    config = OpenHandsConfig(
        run_as_openhands=False,
        max_budget_per_task=4,
        max_iterations=100,
        save_trajectory_path=...,
        sandbox=SandboxConfig(
            base_container_image=base_container_image,
            enable_auto_lint=True,
            # using host network to access the host machine from the container
            use_host_network=True,
            # large enough timeout, since some testcases take very long to run
            timeout=300,
            ...
        ),
        ...
    )
```

i.e. **$4 budget cap, 100 iteration cap, 300s per-command timeout**. History condensation is explicitly disabled (`AgentConfig(enable_prompt_extensions=False, enable_history_truncation=False, enable_som_visual_browsing=False, condenser=NoOpCondenserConfig())`, `:57-62`) — so long tasks can hit context limits rather than truncate.

Evaluator command timeout: 600s (`evaluation/run_eval.py:173`). Task init timeout: 900s (`evaluation/run_eval.py:96`).

### 5.5 Service instability is a first-class, documented problem

`evaluation/browsing.py:210-211` (devnote directly above the Plane login script):

```python
    # devnote: plane reset is not stable, and sometimes it fails to launch
    # in which case the login action will fail, and then we would skip the task
```

`evaluation/README.md:60-66`:

> The script is idempotent. If you run it again, it will resume from the last checkpoint.
> It would usually take a few days to finish evaluation.
>
> Note: the script will automatically skip a task if it encounters an error. This usually happens when the OpenHands runtime dies due to some unexpected errors. This means even if the script finishes, it might not have evaluated all tasks. You can manually resume the evaluation by running the script again.

`docs/SETUP.md:57-59`:

> "Occasionally, you might see some service stuck in a not ready state. Server issue is usually not too concerning from evaluation correctness perspective, as task images all contain health check logic in their initialization scripts. They do need human intervention to recover at times."

`docs/SETUP.md:81-85` ("Plane not ready") and `docs/SETUP.md:99-105` ("RocketChat not ready" — the bitnami/mongodb M1 bug) are dedicated troubleshooting sections.

Resume/skip logic (`evaluation/run_eval.sh:95-99`):

```bash
    # Check if evaluation file exists
    if [ -f "$OUTPUTS_PATH/eval_${task_name}-image.json" ]; then
        echo "Skipping $task_name - evaluation file already exists"
        continue
    fi
```

**Consequence:** a task that errored out has no `eval_*.json`, so it is simply absent from `summarise_results.py`'s denominator (`:297`: `**Tasks Evaluated:** {len(eval_results)}`). Reported "Overall Score" is over *completed* runs, not over 175. A published number must be read together with its Tasks-Evaluated count.

### 5.6 Test mode makes CI deterministic (but blind)

`workspaces/base_image/config.py:2-3`:
```python
# In test mode, we use mock servers and mock LLM responses
TEST_MODE = os.environ.get('TAC_TEST_MODE', False)
```
`workspaces/base_image/common.py:52-54`:
```python
def llm_complete(messages):
    if TEST_MODE:
        return {'choices': [{'message': {"content": "Hello, how are you?","role": "user"}}]}
```
`workspaces/base_image/common.py:23-32` mocks RocketChat entirely:
```python
class MockRocketChatClient:
    class JsonResponse:
        def json(self):
            return {'users': [], 'messages': []}
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return self.JsonResponse()
        return method
```

CI runs every evaluator in this mode, explicitly acknowledging it proves nothing about correctness (`.github/validate_evaluators.sh:26-31`):

```bash
  # Run the container and execute the evaluator
  # The evaluator would almost always say 0 marks granted, but that's
  # fine, we only run it to make sure it at least compiles
  docker run -e TAC_TEST_MODE=true --rm task-image sh -c \
    "echo '127.0.0.1 the-agent-company.com' >> /etc/hosts; \
    DECRYPTION_KEY='theagentcompany is all you need' python_default /utils/eval.py"
```

And the workflow header, `.github/workflows/validate_task_images.yml:1-2`:

> "This workflow only validates task images without pushing them to registry / it acts as a sanity checker **without verifying correctness of tasks' contents**"

### 5.7 State reset between tasks

`workspaces/base_image/reset.sh` (complete logic): for each of `rocketchat plane gitlab owncloud`, if the service name appears in `/utils/dependencies.yml`, POST `http://the-agent-company.com:2999/api/reset-<service>`, then poll `/api/healthcheck/<service>` every 5s up to **180 attempts = 15 minutes** (`reset.sh:18-19`, `:41-42`) before erroring.

Only declared dependencies are reset (`workspaces/tasks/example/dependencies.yml:5-7`: "The dependencies are used to decide which service(s) need to be restored to the initial state before evaluation starts"), and `workspaces/tasks/example/README.md:102-108` gives the reason:

> "For efficiency purpose, benchmark users are not required to reset all service states between task runs - they only need to reset services that are needed by the task."

**This means cross-task contamination is possible**: a task that mutates GitLab but doesn't declare `gitlab` leaves that state for the next task.

`docs/EVALUATION.md:52-53`: "This might take up to 10 minutes since the initialization script would reset all the data in dependent services and blocking wait until all health checks pass."

---

## 6. Metrics and reported numbers (G3, H1)

### 6.1 THE score formula (the single most important artifact)

`evaluation/summarise_results.py:162-178` (complete, verbatim):

```python
def calculate_score(total: int, result: int) -> float:
    """
    Calculate the score as a number between 0 and 1.

    Formula: score = (result / total) * 0.5 + (result // total) * 0.5
    Explanation:
    - (result / total) * 0.5: This is the completion ratio, scaled down to a 0-0.5 range.
    - (result // total) * 0.5: This is a binary score indicating whether the task was completed or not.
    
    Args:
        total: Total possible points
        result: Actual points achieved
        
    Returns:
        Score as a number between 0 and 1
    """
    return (result / total * 0.5) + (result // total * 0.5)
```

So the per-task score is

```
Score = 0.5 · (result / total)  +  0.5 · ⌊result / total⌋
```

- Half the weight is **partial completion** (fraction of checkpoint points earned).
- Half is **full completion** (integer division: 1 iff `result == total`, else 0).
- Range [0, 1]. A task with 3/4 points scores 0.375; 4/4 scores 1.0.

This is the paper's "full completion vs partial completion" formulation implemented literally.

`evaluation/summarise_results.py:180-191`:

```python
def is_perfect_completion(total: int, result: int) -> bool:
    """
    Check if the task achieved perfect completion.
    ...
    """
    return total > 0 and total == result
```

### 6.2 Reported metric surface

`evaluation/summarise_results.py:282-344` prints:

Per-task table: `| Filename | Total | Result | Score | Steps | Cost |` with a `⭐` marker for perfect completions (`:287-293`).

Summary block (`:296-305`):
- `**Tasks Evaluated:** N`
- `**Perfect Completions:** X/N (P%)`
- `**Overall Score:** mean(score) × 100 %`
- `**Average Steps:** mean(steps)`
- `**Average Cost (USD):** mean(cost)`

Statistics block (`:314-320`): Highest / Lowest / Median / Average Task Score.

Per-nature-category block (`:322-332`): for each of `sde, pm, ds, admin, hr, finance, other` → "Perfect Completions for X (%)" and "Average Score for X".

Per-service block (`:334-344`): same two metrics for each of `gitlab, plane, rocketchat, owncloud`.

### 6.3 Steps and cost definitions

`evaluation/summarise_results.py:91-117` — a "step" is one distinct LLM response id in the trajectory:

```python
def analyze_traj_json_file(filepath: str) -> Tuple[int, float]:
    """
    Analyze a single trajectory JSON file and extract the steps and tokens
    for each step. Then estimate the cost based on the tokens and the model type.
    Note: this is assuming there's no prompt caching at all.
    """
    ...
        for action in data:
            if "tool_call_metadata" in action:
                if action["tool_call_metadata"]["model_response"]["id"] != response_id:
                    response_id = action["tool_call_metadata"]["model_response"]["id"]
                else:
                    # openhands displays the same model response meta data multiple times, when
                    # a single LLM call leads to multiple actions and observations.
                    continue
                steps += 1
                ...
                cost += calculate_cost(model, prompt_tokens, completion_tokens)
```

Cost is a **hardcoded price table**, not the provider's billing (`:10-62`). The set of models with entries is direct evidence of which models were benchmarked and when:

| Model pattern | Prompt $/tok | Completion $/tok | Price-list date in comment |
|---|---|---|---|
| `claude-3-5-sonnet` | 0.000003 | 0.000015 | accessed 12/11/2024 |
| `claude-3-7-sonnet` | 0.000003 | 0.000015 | accessed 05/08/2025 |
| `gpt-4o` | 0.0000025 | 0.00001 | accessed 12/11/2024 |
| `gemini-1.5-pro` | 0.00000125 | 0.000005 (×2 if >128k prompt) | accessed 12/11/2024 |
| `gemini-2.0-flash-exp` | 0.0000001 | 0.0000004 | accessed 05/14/2025 |
| `gemini-2.5-pro-preview-05-06` | 0.00000125 / 0.0000025 >200k | 0.00001 / 0.000015 >200k | accessed 05/08/2025 |
| `qwen2-72b` (Together) | 0.0000009 combined | | accessed 12/11/2024 |
| `qwen2p5-72b` (Together) | 0.0000012 combined | | accessed 12/14/2024 |
| `llama-v3p1-405b-instruct` (Fireworks) | 0.000003 combined | | accessed 12/11/2024 |
| `llama-v3p1-70b-instruct` (Fireworks) | 0.0000009 combined | | |
| `llama-v3p3-70b-instruct` (Fireworks) | 0.0000009 combined | | |
| `amazon.nova-pro-v1:0` (Bedrock) | 0.0000008 | 0.0000032 | accessed 12/11/2024 |

Unknown model → `raise ValueError(f"Unknown model: {model}")` (`:61-62`).

### 6.4 Reported model scores IN the repo: **none**

Exhaustive grep of `README.md`, `docs/*.md`, `evaluation/README.md`, `workspaces/README.md` for `%` returned **zero** score lines. There is **no results table in this repository**. Numbers live in two external places:

- Leaderboard: `https://the-agent-company.com/#/leaderboard` (`README.md:19`)
- Raw experiment outputs: `https://github.com/TheAgentCompany/experiments/tree/main/evaluation/1.0.0/20241217_OpenHands-0.14.2-sonnet-20241022` (`evaluation/README.md:98`) — the directory name itself is the only in-repo record of a baseline configuration: **OpenHands 0.14.2 + claude-3-5-sonnet-20241022, run 2024-12-17, benchmark v1.0.0**.

Baseline hardware, stated twice: "As a reference, we used Amazon EC2 t3.2xlarge instances for baselines" (`README.md:48`, `evaluation/README.md:15`). Runtime: "It would usually take a few days to finish evaluation" (`evaluation/README.md:61`). Storage: "you should have docker and docker compose installed, and 30+ GB of free disk space" (`README.md:47`).

### 6.5 Reproducibility knobs a submitter must declare

1. Agent LLM (`--agent-llm-config`) and **environment LLM** (`--env-llm-config`) — the latter drives both NPCs and LLM judges (`evaluation/README.md:53-54`).
2. Task image version (`--version`, only `1.0.0` supported — `evaluation/README.md:57`).
3. Whether NPC-only mode was used (`--run-npc-tasks-only`).
4. Tasks Evaluated count (since failures are silently skipped).

---

## 7. Documented failure modes (H3)

### 7.1 Direct finding: the paper's agent-failure taxonomy is NOT in this repo

I grepped `docs/`, `README.md`, `evaluation/README.md`, `workspaces/README.md` for `failure|fail to|unable to|common sense|social skill|deceiv|UI`. The **only** hits are infrastructure troubleshooting:

- `docs/SETUP.md:83`: "We have seen cases where plane services fail to start due to some internal errors."
- `docs/SETUP.md:101`: "If you are using Macbook M1, you might see RocketChat never ready due to failure of `bitnami/mongodb` container..."

The paper's qualitative failure analysis (lack of common sense, poor social skills, incompetence in browsing UIs, self-deception) is in arXiv 2412.14161, **not** in the repository. `docs/BACKGROUND.md` is a pre-benchmark design proposal and contains no results analysis. **Any claim about TAC's agent failure taxonomy must be sourced to the paper, not this repo.**

### 7.2 What the repo DOES document as failure modes

**(a) Agent completes the task but the evaluator's trajectory keyword is missing.** This is the explicit motivation for an entire scoring strategy — `workspaces/base_image/scoring.py:92-99`:

> "The rationale is many tasks check trajectory as part of their 1st checkpoint, and the information to look up in the trajectory is necessary for any follow-up checkpoint to complete. Thus, as long as any follow-up task completes, the 1st checkpoint should be considered as complete, even if the trajectory is missing, or doesn't contain the keyword that the evaluator is looking for."

**(b) Evaluator's own bugs crashing the grading run.** `workspaces/tasks/example/evaluator.py:6-11` — "A good evaluator should: 1. be robust - it shouldn't abort because of its own bug or lack of fail over mechanism". Enforced by `@grader` + CI check.

**(c) Runtime death mid-task.** `evaluation/README.md:63-66`: "the script will automatically skip a task if it encounters an error. This usually happens when the OpenHands runtime dies due to some unexpected errors."

**(d) Login/pre-login failure = task skipped.** `evaluation/run_eval.py:278-285` retries init + pre_login once, then propagates:
```python
    try:
        pre_login(runtime, dependencies, ...)
    except Exception as e:
        logger.error(f"Failed to pre-login: {e}")

        # before giving up, let's try to init and login again
        init_task_env(runtime, args.server_hostname, env_llm_config)
        pre_login(runtime, dependencies, ...)
```

**(e) NPC multi-agent breakdown.** `servers/rocketchat/npc/NPC.md:100-104` — NPCs cannot converse with each other; all NPCs in a channel reply to every message; "Unless neccessary in your task, don't use multiple NPC."

**(f) Agents asking the human for help.** Hard-coded out: `'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP.\n'` (`evaluation/run_eval.py:107`), with a give-up escape after 3 attempts.

**(g) Agents that should refuse / say "no".** `finance-nonqualified-bill-ask-for-reimburse` is a designed negative-result task — the correct behaviour is to *decline* reimbursement and cite the policy. The evaluator penalises hallucinating an amount (`workspaces/tasks/finance-nonqualified-bill-ask-for-reimburse/evaluator.py:18-23`):
```python
    if any([word in text for word in ["85.6", "25.0", "$"]]):
        return False
    
    return sum([phrase.lower() in text.lower() for phrase in [
        "not qualified", "Credit card statements not accepted as receipts"
    ]])
```
and `checkpoints.md:5-6` notes the deliberate synthetic-artifact trap:
> "Note that the bill is not a real statement, but a AI-generated fake one. So from the automation perspective, this bill is not qualified for reimbursement too."

**(h) Agent polluting the `python` alias.** `workspaces/base_image/Dockerfile:25-26`:
```dockerfile
# create a softlink in case "python" alias is polluted
RUN ln -s /usr/local/bin/python3 /usr/local/bin/python_default
```
The evaluator always runs as `python_default`, defending against the agent breaking `python` during its work.

---

## 8. Tool surface / simulated environment (services)

### 8.1 The four services, with URLs, ports and credentials

Verbatim from `servers/README.md:35-54`:

```
## GitLab
* service url: http://the-agent-company.com:8929
* root email: `root@local`
* root password: `theagentcompany`

## ownCloud
* service url: http://the-agent-company.com:8092
* username: `theagentcompany`
* password: `theagentcompany`

## Plane
* service url: http://the-agent-company.com:8091
* email: `agent@company.com`
* password: `theagentcompany`
* API_KEY:`plane_api_83f868352c6f490aba59b869ffdae1cf`

## RocketChat
* service url: http://the-agent-company.com:3000
* email: `theagentcompany`
* password: `theagentcompany`
```

Same constants in code (`workspaces/base_image/config.py:12-37`), incl. `GITLAB_ACCESS_TOKEN = "root-token"` (`:25`) and `PLANE_WORKSPACE_SLUG = "tac"` (`:32`).

| Service | Role in the sim | Port | Image |
|---|---|---:|---|
| GitLab | code hosting, issues, MRs, wikis, CI, releases | 8929 (+8930 https, 2424 ssh) | `ghcr.io/theagentcompany/servers-gitlab:1.0.0` |
| ownCloud | "office cloud" / file drive (+Collabora office suite) | 8092 (Collabora 9980) | `ghcr.io/theagentcompany/servers-owncloud:1.0.0` + `collabora/code:24.04.9.2.1` |
| RocketChat | company chat, DMs + channels, NPC colleagues | 3000 | `registry.rocket.chat/rocketchat/rocket.chat:5.3.0` (+ `bitnamilegacy/mongodb:5.0`) |
| Plane | project management (projects, cycles/sprints, issues, analytics) | 8091 | `servers-plane-{admin,frontend,backend,space,proxy}:1.0.0` |
| api-server | control plane: reset + healthcheck for all four | 2999 | `ghcr.io/theagentcompany/servers-api-server:1.0.0` |
| redis-stack | Sotopia NPC profile store | 6379 | `redis/redis-stack-server:7.4.0-v0` |

Ports from `servers/docker-compose.yml:18-21` (gitlab), `:31-32` (owncloud), `:46-48` (collabora), `:90-91` (rocketchat), `:111-113` (redis); Plane port from `workspaces/base_image/config.py:30`; api-server from `servers/api-server/api-server.py:95`.

Full image pull list: `servers/Makefile:182-200` (20 images).

### 8.2 The synthetic hostname mechanism

All tasks address services as `the-agent-company.com`. `servers/README.md:7-11`:

> "`the-agent-company.com` is a real domain where we host the project website with the leaderboard. For benchmarking purpose, all tasks assume this domain hosts the services. Since this domain does not really host any of the following services, you need to change your `/etc/hosts` file to point to your own server ip..."

In the task container this is done automatically at init (`workspaces/base_image/init.sh:6-9`):

```sh
# Use synthetic service hostname, the-agent-company.com in tasks and point it
# to the real service host
SERVICE_IP=$(ping -c 1 ${SERVER_HOSTNAME:-localhost} | grep PING | awk -F'[()]' '{print $2}')
echo "$SERVICE_IP the-agent-company.com" >> /etc/hosts
```

`docs/EVALUATION.md:55-56`: "Most importantly, the initialization script would add the server's IP to the `/etc/hosts` file, so that the agent can visit the services using the synthetic `the-agent-company.com` hostname."

### 8.3 The api-server control plane

`servers/api-server/api-server.py` exposes exactly 8 endpoints:

| Endpoint | Method | Action |
|---|---|---|
| `/api/reset-owncloud` | POST | synchronous `make reset-owncloud` (restart) — `:6-11` |
| `/api/reset-rocketchat` | POST | async `make reset-sotopia-redis` + `make reset-rocketchat` — `:13-17` |
| `/api/reset-plane` | POST | async `make reset-plane` — `:19-22` |
| `/api/reset-gitlab` | POST | synchronous `make reset-gitlab` — `:24-31` |
| `/api/healthcheck/owncloud` | GET | HTTP 200 on :8092 |
| `/api/healthcheck/gitlab` | GET | HTTP 200 on :8929 |
| `/api/healthcheck/rocketchat` | GET | **composite**: rocketchat + redis + sotopia NPC profiles — `:43-53` |
| `/api/healthcheck/plane` | GET | can list projects via API — `:55-58` |
| `/api/healthcheck/redis`, `/api/healthcheck/sotopia` | GET | `:60-88` |

The composite RocketChat check is notable (`api-server.py:47-53`):

```python
    # Sotopia is optional if no NPC is needed for the task,
    # but for simplicity, we always check Sotopia NPC profiles are correctly
    # loaded whenever RocketChat service is needed
    _, sotopia_code = healthcheck_sotopia()
    code = 200 if redis_code == 200 and rocketchat_code == 200 and sotopia_code == 200 else 400
```

Reset semantics per service (`servers/Makefile`): GitLab and ownCloud reset = **stop, `rm -f` container, `up` again** from the pre-baked image (`:58-64`, `:143-149`). RocketChat reset = **mongorestore from a db.dump** (`:83-84`: `docker exec -i rocketchat-mongodb sh -c 'mongorestore --drop --archive' < ./rocketchat/db.dump`). Sotopia redis reset = container recreate (`:102-108`).

### 8.4 Task-container tool surface

`workspaces/base_image/Dockerfile`: base `python:3.12`, plus `iputils-ping`, `vim` (`:3`), `requests==2.32.3`, `cryptography==44.0.0` (`:29-30`), `rocketchat_API==1.32.0`, `sotopia==0.1.2`, `hiredis==3.0.0`, `litellm==1.23.16` (`:40-44`). `PYTHONPATH="/utils:$PYTHONPATH"` (`:65`). Individual tasks layer their own deps (e.g. `pandas==2.2.3`, `openpyxl==3.1.5`, `scikit-learn==1.5.2`, `numpy==2.1.2`, `torch`).

Browser: not required. `docs/EVALUATION.md:71-77`:

> "Your agent doesn't have to do browsing in the container environment. The baseline agent installs a headless chrome in the container for browsing purposes, but your agent doesn't have to. It could, for example, use a normal browser on a computer just like what human beings do."

### 8.5 The shared evaluator helper library (`workspaces/base_image/common.py`, 808 lines)

This is the surface every task evaluator reuses. Grouped:

- **Scaffolding**: `grader` (`:35`), `llm_complete` (`:52`), `MockRocketChatClient` (`:23`)
- **RocketChat**: `create_rocketchat_client` (`:64`), `get_rocketchat_personal_chat_history` (`:82`), `num_rocketchat_users_contacted` (`:112`), `get_rocketchat_channel_history` (`:132`), `get_rocketchat_channel_room_id` (`:169`), `check_rocketchat_message_posted` (`:176`)
- **LLM judging**: `evaluate_with_llm` (`:214`), `evaluate_chat_history_with_llm` (`:284`), `download_image_from_url` (`:199`)
- **GitLab**: `make_gitlab_request` (`:316`), `get_gitlab_project_id` (`:334`), `get_gitlab_merge_request_by_title` (`:358`), `get_gitlab_file_in_mr` (`:382`)
- **ownCloud (WebDAV)**: `get_owncloud_url_in_file` (`:402`), `download_owncloud_content` (`:416`), `check_and_download_file` (`:458`), `check_file_in_owncloud_directory` (`:526`), `get_binary_file_content_owncloud` (`:559`)
- **Plane**: `get_all_plane_projects` (`:600`), `get_plane_project_id` (`:612`), `get_plane_project_all_issues` (`:627`), `get_plane_state_id_dict` (`:639`), `get_plane_issue_details` (`:683`), `get_plane_cycle_details` (`:698`), `get_plane_issues_by_project_cycle` (`:713`), `get_plane_state_details` (`:733`), `create_plane_issue` (`:772`), `add_plane_issue_to_cycle` (`:783`)
- **Repo checks**: `PROJECT_FILES` + `check_repo_exists` (`:577-597`)
- **Slides**: `get_all_texts_from_slide` (`:795`)

### 8.6 The real open-source repos baked into GitLab

`workspaces/base_image/common.py:577-585` — used to verify a clone actually happened, by checking for a signature file:

```python
# Use the unique file name to check if the repository is cloned correctly.
PROJECT_FILES = {
    'openhands': '.openhands_instructions',
    'janusgraph': '.backportrc.json',
    'colly': 'xmlelement_test.go',
    'streamlit': '.ruff.toml',
    'risingwave': 'risedev.yml',
    'bustub': 'CMakeLists.txt'
}
```

Other repos referenced by task names: `api-server`, `copilot-arena-server`, `sotopia`, `llama.cpp`, `node-red`, `opensearch`, `doc` (the wiki repo at `http://the-agent-company.com:8929/root/doc/-/wikis`, cited in `workspaces/tasks/example/scenarios.json:3`).

Adding a repo is a ~10-hour image rebuild — `servers/Makefile:36-39`:
> "# rebuild destroys the gitlab image and start from scratch / useful when you have new data to bake into the image / Note: this will take at least 10 hours to build since we have quite a few large repositories to bake into the image"

### 8.7 Task lifecycle (`workspaces/base_image/init.sh`, complete)

```sh
########## PRE INIT PHASE ############
# /etc/hosts rewrite
echo "Resetting services..."
bash /utils/reset.sh
[ -f /utils/pre_init.sh ]  && bash /utils/pre_init.sh
[ -f /utils/pre_init.py ]  && python_default /utils/pre_init.py

########## RUN INITIALIZATION ########
# set up task-specific NPC ENV, only if NPC is required
[ -f /npc/scenarios.json ] && python_default /npc/run_multi_npc.py
# populate task-specific data if applicable
[ -f /utils/populate_data.py ] && python_default /utils/populate_data.py

########## POST INIT PHASE ###########
[ -f /utils/post_init.sh ] && bash /utils/post_init.sh
[ -f /utils/post_init.py ] && python_default /utils/post_init.py
```

Purpose of the hooks, `workspaces/tasks/example/README.md:119-131`:

> "A common use case for `pre_init.py` is to check whether services involved in the task are ready and in a clean state. For example, it could check access to a wiki page, check existence of some repository, issue, pull request in GitLab, and check existence of an user in RocketChat. **If sanity checks fail, it could either fail the whole script, or attempt to fix/reset the environment.**
> A common use case for `post_init.py` is to validate the initialization process. For example, in the task image, initialization step launches NPC(s). Post-init step could check if the OpenAI key is valid and NPCs are working."

Real example (`workspaces/tasks/sde-close-all-gitlab-issues/pre_init.py:19-36`) — paginates all GitLab projects and `raise Exception("No issue found")` if the fixture data is missing, i.e. **fail the task setup rather than silently score 0**. This is the closest thing in the repo to environment-failure-vs-agent-failure disambiguation, and only 6 tasks have it.

---

## 9. Notable quotes / raw excerpts

**On the benchmark's purpose** — `README.md:28-29`:
> "TheAgentCompany measures the progress of these LLM agents' performance on performing real-world professional tasks, by providing an extensible benchmark for evaluating AI agents that interact with the world in similar ways to those of a digital worker: by browsing the Web, writing code, running programs, and communicating with other coworkers."

**On task provenance (O\*NET grounding)** — `docs/BACKGROUND.md:20`:
> "We plan on referencing the O*NET database (https://www.onetonline.org/), which is a database of all the jobs performed by workers in the US created by the US Department of Labor. It also contains information about tasks performed within the context of each job, abilities required to perform each task, and other pieces of relevant information."

**On why WebArena wasn't enough** — `docs/BACKGROUND.md:10-13`:
> "- Despite some grounding in realistic data, the process of creating tasks from this data was quite heuristic, and no consideration was made for how important or time consuming the tasks are.
> - The tasks are biased towards those important for academics in computer science, and not reflective of tasks performed by the entire population"

**Evaluator design philosophy** — `docs/BACKGROUND.md:49-53`:
> "- Execution-based evaluations: write programs to verify the final state, might be difficult for some tasks (e.g. plot a graph)
> - Step-based evaluations: check the steps produced by the agents, possibly have partial scores.
> - Checkpoint-based evaluations: have verifiable checkpoints along the way of more complex tasks, e.g. check if the website is live if the task involves starting up a server first."

**The scoring formula** — `evaluation/summarise_results.py:165-168`:
> ```
> Formula: score = (result / total) * 0.5 + (result // total) * 0.5
> Explanation:
> - (result / total) * 0.5: This is the completion ratio, scaled down to a 0-0.5 range.
> - (result // total) * 0.5: This is a binary score indicating whether the task was completed or not.
> ```

**The LLM judge, in full** — `workspaces/base_image/common.py:214-273`:

```python
def evaluate_with_llm(content: str, predicate: str, additional_prompt: str = '', image_path: str = None, image_type: str = IMAGE_JPEG):
    """
    Evaluates if a predicate can be inferred from the content/image, judged by LLM
    """
    if image_path is not None and image_type not in [IMAGE_JPEG, IMAGE_PNG]:
        logging.warning(f"Invalid image type: {image_type}")
        return False
    if not content and not image_path:
        logging.warning(f"Both content and image are empty, cannot evaluate")
        return False
    elif content and image_path:
        query = f'Does the content """{content}""" and following picture indicate {predicate}?'
    elif content:
        query = f'Does the content """{content}""" indicate {predicate}?'
    else:
        query = f'Does the following picture indicate {predicate}?'

    query += f' Please answer "yes" if it does, or "no" if it does not. {additional_prompt}'
    content = [
        {
            "type": "text",
            "text": query
        }
    ]
    if image_path:
        try:
            with open(image_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logging.error(f"Failed to read image from {image_path}: {e}")
            return False
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_type};base64,{base64_image}"
            }
        })

    try:
        # Construct LLM query
        llm_messages = [{
            "role": "user",
            "content": content
        }]

        # Call LLM for evaluation
        llm_response = llm_complete(llm_messages)
        logging.info("LLM evaluation completed", extra={"response": llm_response})

        # Extract and process response
        content = llm_response["choices"][0]["message"]["content"].lower().strip()

        # Evaluate result
        result = "yes" in content
        if result:
            logging.info(f'Predicate "{predicate}" evaluated to "{result}"')
        else:
            logging.warning(f'Predicate "{predicate}" evaluated to "{result}"')

        return result
```

**The exact judge prompt template** (assembled from the branches above):

| Case | Template |
|---|---|
| text only | `Does the content """{content}""" indicate {predicate}? Please answer "yes" if it does, or "no" if it does not. {additional_prompt}` |
| image only | `Does the following picture indicate {predicate}? Please answer "yes" if it does, or "no" if it does not. {additional_prompt}` |
| text + image | `Does the content """{content}""" and following picture indicate {predicate}? Please answer "yes" if it does, or "no" if it does not. {additional_prompt}` |

**Boolean extraction**: `result = "yes" in llm_response["choices"][0]["message"]["content"].lower().strip()` (`common.py:264-267`). Note this is a substring test, not equality — `"maybe yes"`, `"yesterday"`, `"the answer is not yes"` all evaluate to `True`.

**The chat-history judge** — `workspaces/base_image/common.py:284-314`:

```python
def evaluate_chat_history_with_llm(rocket_client, username: str, predicate: str):
    """
    Evaluates chat history from RocketChat server against a given predicate using LLM.
    ...
    Example:
        >>> result = evaluate_chat_history_with_llm(
        ...     rocket_client,
        ...     "Liu Qiang",
        ...     "the person receiving the feedback had an average job performance"
        ... )
    """
    try:
        messages = get_rocketchat_personal_chat_history(rocket_client, username)
        if not messages:
            logging.warning(f"No chat history found for user: {username}")
            return False
        
        return evaluate_with_llm(str(messages), predicate)
```

**Image judging in practice** — `workspaces/tasks/ds-visualize-data-in-pie-and-bar-chart/evaluator.py:7-24` (complete grading logic for a whole task):

```python
@grader
def grade_checkpoint1():
    """Validate pie chart"""
    return evaluate_with_llm(
        content="",
        predicate="The picture contains a pie chart, with the value of Garlic being the highest, Sweet potato being the second highest, Chinese vegetables and Kale being the least.",
        image_path=PIE_CHART_FILE
    )
```

**A custom two-image judge** (only place in the repo where two images go into one call) — `workspaces/tasks/ml-generate-gradcam/evaluator.py:121-133`:

```python
@grader
def grade_checkpoint1():
    """Compare the visual similarity of generated GradCAM visualizations"""
    try:
        return compare_images_with_llm(
            '/workspace/gradcam_output.jpg', 
            '/utils/reference_gradcam.jpg',
            'Do these two GradCAM visualizations highlight similar regions in the image?',
            'Focus on the regions highlighted in red/orange and their intensity patterns.'
        )
```
paired with deterministic tensor checks in the same task (`cosine_similarity(...) > 0.8`, `:167-168` and `:188-189`).

**A text judge that compares against a template + spec** — `workspaces/tasks/hr-new-grad-job-description/evaluator.py:22-28`:

```python
    if "[Insert Information]" in final_content:
        print("some placeholder still present in the final job description.")
        return False

    predicate = f'a successful combination of the markdown template \"\"{template_content}\"\" and the requirement file \"\"{requirement_content}'
    additional_prompt = 'Pay special consideration to all of the numerical details. '
    return evaluate_with_llm(final_content, predicate, additional_prompt)
```

**Rubric secrecy** — `docs/EVALUATION.md:13-15`:
> "To prevent the agent from peeking at the evaluator code, all `/utils/evaluator.py` files, which contain the grading functions, are encrypted. The evaluator entrypoint, `/utils/eval.py`, contains the decryption code, and you need to pass the decryption key as an environment variable when you run it: `DECRYPTION_KEY='theagentcompany is all you need'`."

**Examinee/examiner boundary** — `docs/EVALUATION.md:124-127`:
> "Benchmark users are allowed to inspect checkpoint rubrics to ensure the trajectory contains all necessary information used in graders, but examinees (e.g. agents) are not allowed to read checkpoint rubrics or evaluation code."

**No time limit** — `docs/EVALUATION.md:89-90`:
> "Once the examinee has finished its work (we don't enforce timing), run the below command in the container to grade the exam."

**Task authoring guidance (rubric leakage prevention)** — `workspaces/tasks/example/README.md:8-12`:
> "Every task folder should have a `task.md` that describes the task. It shall not contain detailed step-by-step guidelines unless absolutely necessary. **It shall not contain rubrics used for grading.**"

**Difficulty is tunable via the Dockerfile** — `workspaces/tasks/example/README.md:84-87`:
> "The Dockerfile should contain necessary environments you'd like to provide with the examinee. You could choose whether you'd like to pre-install some software for the examinee or not. Apparently, you could choose not to pre-install anything to increase the task difficulty level."

**Credential-discovery as an explicit sub-difficulty** — `workspaces/tasks/example/README.md:159-161`:
> "## Gitlab (optional)
> Some tasks require the examinee to push the code to the gitlab. So they need to figure out by themselves without providing the credential to them"

**Sotopia is being used off-label** — `workspaces/base_image/npc/server.py:46-49`:
> "sotopia is an agent-agent interaction framework, but here we are using it between agent (NPC) and examinee. The framework requires us to define a goal for both counter-parties, even though sotopia doesn't really control examinee."

**The bridge hack for LiteLLM model names** — `workspaces/base_image/npc/run_one_npc.py:20-23`:
```python
# HACK: sotopia is not compatible with LITELLM, so we have to remove
# "openai/" prefix, if any, from the model name.
if MODEL_NAME.startswith("openai/"):
    MODEL_NAME = MODEL_NAME[7:]  # Skip first 7 characters ("openai/")
```

**Hardcoded decryption key in the harness** — `evaluation/run_eval.py:169`:
```python
        f"DECRYPTION_KEY='theagentcompany is all you need' "  # Hardcoded Key
```

**Eval sweep cleans docker between tasks** — `evaluation/run_eval.sh:121-125`:
```bash
    # Prune unused images and volumes
    docker image rm "$task_image"
    docker images "ghcr.io/all-hands-ai/runtime" -q | xargs -r docker rmi -f
    docker volume prune -f
    docker system prune -f
```

**A representative "ask a colleague, then act" task, end to end** — `workspaces/tasks/sde-reply-community-issue-by-asking-npc/task.md` (complete):
```
Navigate to the openhands's gitlab at http://the-agent-company.com:8929/root/openhands

* find issue #4158
* Ask Mike Chen about this issue on http://the-agent-company.com:3000
* reply the issue
```
graded by (`.../evaluator.py:30-76`):
```python
@grader
def grade_checkpoint1(trajectory: str):
    return 'root/openhands/-/issues/4158' in trajectory

@grader
def grade_checkpoint2(username='Mike Chen'):
    msgs = get_rocketchat_personal_chat_history(rocket, username=username)
    return bool(msgs)

@grader
def grade_checkpoint3():
    issue_notes = get_gitlab_issue_notes()
    if issue_notes:
        return any(issue_note.get('id') not in [127283, 127284, 127285] for issue_note in issue_notes)
    else:
        return False

@grader
def grade_checkpoint4(username='Mike Chen'):
    issue_notes = get_gitlab_issue_notes()
    target = None
    ...
    return evaluate_chat_history_with_llm(rocket, username=username, predicate=target)


def grade_checkpoints(trajectory="") -> Result:
    checkpoints: List[Checkpoint] = []
    result = Result(checkpoints)

    checkpoints.append(Checkpoint(1, int(grade_checkpoint1(trajectory))))
    checkpoints.append(Checkpoint(1, int(grade_checkpoint2())))
    checkpoints.append(Checkpoint(1, int(grade_checkpoint3())))
    checkpoints.append(Checkpoint(2, 2 * int(grade_checkpoint4())))

    return result
```
Note checkpoint 3 detects "the agent posted *something* new" by excluding three hardcoded pre-existing note IDs — a fingerprint of the pre-baked GitLab data. Checkpoint 4 uses the agent's *own reply* as the LLM predicate against the NPC chat history, i.e. "is your public answer consistent with what your colleague told you privately?"

---

## Appendix: measurement commands used

```bash
cd .../TheAgentCompany__TheAgentCompany
ls workspaces/tasks/ | sed 's/-.*//' | sort | uniq -c | sort -rn   # prefix histogram
ls workspaces/tasks/ | wc -l                                       # 175
grep -c 'ghcr.io/theagentcompany' workspaces/README.md             # 175
ls workspaces/tasks/*/scenarios.json | wc -l                       # 41
grep -l -E "evaluate_with_llm|evaluate_chat_history_with_llm|llm_complete" \
     workspaces/tasks/*/evaluator.py | wc -l                       # 53
grep -l "bonus_for_completing_final" workspaces/tasks/*/evaluator.py | wc -l   # 54
grep -l "in trajectory" workspaces/tasks/*/evaluator.py | wc -l    # 65
for s in gitlab plane rocketchat owncloud; do
  echo -n "$s: "; grep -l "^- $s" workspaces/tasks/*/dependencies.yml | wc -l
done                                                               # 71/17/79/70
```
