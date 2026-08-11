# microsoft/AIOpsLab

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/microsoft__AIOpsLab/`

> All file paths below are **relative to that repo root**. Line numbers refer to the checked-out
> commit present on disk (branch `main`, clean tree).
> Repo self-description: *"AIOpsLab is a holistic framework to enable the design, development, and
> evaluation of autonomous AIOps agents"* — `README.md:23`.
> Cited papers: MLSys 2025 `chen2025aiopslab` and SoCC 2024 `shetty2024building` — `README.md:485-500`.
> arXiv badges: 2501.06706 and 2407.12165 — `README.md:12-13`.

---

## 1. Task taxonomy (C1, C2, C3, C4)

### 1.1 The four task types

Exactly four task classes exist, exported from `aiopslab/orchestrator/tasks/__init__.py:4-7`:

```python
from .detection import DetectionTask
from .localization import LocalizationTask
from .analysis import AnalysisTask
from .mitigation import MitigationTask
```

| Task class | File | Answer type expected | Timing metric key |
|---|---|---|---|
| `DetectionTask` | `aiopslab/orchestrator/tasks/detection.py:18` | `str` = `"Yes"` / `"No"` | `TTD` (`detection.py:76`) |
| `LocalizationTask` | `aiopslab/orchestrator/tasks/localization.py:18` | `list[str]` of service names | `TTL` (`localization.py:80`) |
| `AnalysisTask` | `aiopslab/orchestrator/tasks/analysis.py:17` | `dict` with `system_level` + `fault_type` | `TTA` (`analysis.py:91`) |
| `MitigationTask` | `aiopslab/orchestrator/tasks/mitigation.py:17` | no answer — `submit()` takes no args | `TTM` (`mitigation.py:75`) |

The `Task` base class (`aiopslab/orchestrator/tasks/base.py:14-35`) declares the abstract contract:

```python
class Task:
    """Base class for all tasks."""

    def __init__(self):
        self.results = {}
        self.kubectl = KubeCtl()

    def get_task_description(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def get_instructions(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def get_available_actions(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def perform_action(self, action_name, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method.")

    def add_result(self, key, value):
        """Add an evaluation result to the task."""
        self.results[key] = value
```

### 1.2 Problem counts

`aiopslab/orchestrator/problems/registry.py:36-220` defines `PROBLEM_REGISTRY`. Counted mechanically
from the file (`grep -c '^\s*"[a-zA-Z0-9_-]*":'`):

- **89 registered problem IDs total.**
- By task type (substring match, the same logic `get_problem_ids(task_type)` uses at
  `registry.py:235-238`):
  - `detection` → **34**
  - `localization` → **28**
  - `analysis` → **13**
  - `mitigation` → **14**

Note `README.md:25` says only *"a set of problems"*; the repo's own `CLAUDE.md` claims "60+ problems"
which is now stale — the actual live count is 89.

A further **12 problem IDs are commented out** in the registry and therefore not runnable:
kernel fault ×2 (`registry.py:168-169`), disk wear-out ×2 (`registry.py:170-171`), the five
K8s-operator misoperations ×2 each = 10 (`registry.py:207-216`), and
`redeploy_without_PV-localization-1` (`registry.py:198`).

### 1.3 Applications

Application classes live in `aiopslab/service/apps/`; metadata JSON in `aiopslab/service/metadata/`
(paths wired in `aiopslab/paths.py:30-37`).

| App | Class file | Namespace | Deploy | Used by problems? |
|---|---|---|---|---|
| Social Network (DeathStarBench) | `aiopslab/service/apps/socialnet.py:13` | `test-social-network` | Helm | yes |
| Hotel Reservation (DeathStarBench) | `aiopslab/service/apps/hotelres.py:10` | `test-hotel-reservation` | raw `kubectl apply` (`helm_deploy = False`, `hotelres.py:15`) | yes |
| OpenTelemetry Astronomy Shop | `aiopslab/service/apps/astronomy_shop.py:11` | `astronomy-shop` | remote Helm repo `open-telemetry` (`astronomy_shop.py:27-31`) | yes |
| Flower (federated learning) | `aiopslab/service/apps/flower.py` | `docker` (`flower.json:3`) | docker-compose | yes (2 problems) |
| TiDB Cluster + Operator | `aiopslab/service/apps/tidb_cluster_operator.py` | `tidb-cluster` | Helm operator v1.6.0 | **only via commented-out registry entries** |
| Train Ticket | `aiopslab/service/apps/train_ticket.py` | `train-ticket` | Helm | **no registered problem** |
| Flight Ticket (OpenWhisk serverless) | `aiopslab/service/apps/flight_ticket.py` | `openwhisk` | Helm | **no registered problem** |
| Prometheus (telemetry, not a target) | `aiopslab/service/telemetry/prometheus.py:14` | `observe` | Helm | infra |

**Microservice counts.** The repo states a count for only one app —
`aiopslab/service/metadata/train-ticket.json:4`:

```json
"Desc": "The project is a train ticket booking system based on microservice architecture which contains 41 microservices.",
```

Flower states its topology (`flower.json:4`): *"The current deployment consists of one server and two
clients."* **No microservice count is stated anywhere for Social Network, Hotel Reservation, or
Astronomy Shop** — the agent only ever sees the prose `Desc` + `Supported Operations` list
(see §3).

Problem→app mapping (from `grep 'self.app = '` over `aiopslab/orchestrator/problems/`):

- **Hotel Reservation**: `container_kill`, `disk_woreout`, `kernel_fault`, `misconfig_app`,
  `network_delay`, `network_loss`, `no_op` (hotel variant), `pod_failure`, `pod_kill`,
  `redeploy_without_pv`, `revoke_auth`, `storage_user_unregistered`, `wrong_bin_usage`
- **Social Network**: `assign_non_existent_node`, `auth_miss_mongodb`, `k8s_target_port_misconfig`,
  `no_op` (social variant), `scale_pod`
- **Astronomy Shop**: `ad_service_failure`, `ad_service_high_cpu`, `ad_service_manual_gc`,
  `cart_service_failure`, `image_slow_load`, `kafka_queue_problems`,
  `loadgenerator_flood_homepage`, `payment_service_failure`, `payment_service_unreachable`,
  `product_catalog_failure`, `recommendation_service_cache_failure`, `no_op` (astronomy variant)
- **Flower**: `flower_model_misconfig`, `flower_node_stop`
- **TiDB**: `operator_misoperation/*` (all disabled)

---

## 2. Task definition schema (C6)

### 2.1 The mixin pattern

Every problem is a *pair* of classes: a `<Name>BaseTask` that owns the environment lifecycle, and
one concrete class per task type that multiply-inherits `(BaseTask, <TaskType>Task)`. Full example —
`aiopslab/orchestrator/problems/k8s_target_port_misconfig/target_port.py:20-64`:

```python
class K8STargetPortMisconfigBaseTask:
    def __init__(self, faulty_service: str = "user-service"):
        self.app = SocialNetwork()
        self.kubectl = KubeCtl()
        self.namespace = self.app.namespace
        self.faulty_service = faulty_service
        self.payload_script = (
            TARGET_MICROSERVICES
            / "socialNetwork/wrk2/scripts/social-network/compose-post.lua"
        )

    def start_workload(self):
        print("== Start Workload ==")
        frontend_url = get_frontend_url(self.app)

        wrk = Wrk(rate=10, dist="exp", connections=2, duration=10, threads=2)
        wrk.start_workload(
            payload_script=self.payload_script,
            url=f"{frontend_url}/wrk2-api/post/compose",
        )

    def inject_fault(self):
        print("== Fault Injection ==")
        injector = VirtualizationFaultInjector(namespace=self.namespace)
        injector._inject(
            fault_type="misconfig_k8s",
            microservices=[self.faulty_service],
        )
        print(f"Service: {self.faulty_service} | Namespace: {self.namespace}\n")

    def recover_fault(self):
        print("== Fault Recovery ==")
        injector = VirtualizationFaultInjector(namespace=self.namespace)
        injector._recover(
            fault_type="misconfig_k8s",
            microservices=[self.faulty_service],
        )
        print(f"Service: {self.faulty_service} | Namespace: {self.namespace}\n")


################## Detection Problem ##################
class K8STargetPortMisconfigDetection(K8STargetPortMisconfigBaseTask, DetectionTask):
    def __init__(self, faulty_service: str = "user-service"):
        K8STargetPortMisconfigBaseTask.__init__(self, faulty_service=faulty_service)
        DetectionTask.__init__(self, self.app)
```

**Required fields/methods of a problem** (`README.md:329-344` documents the contract; the
orchestrator calls them at `aiopslab/orchestrator/orchestrator.py:71-89`):

| Member | Who defines it | Who calls it |
|---|---|---|
| `self.app` | BaseTask | `orchestrator.py:71-72` (`prob.app.delete()`, `prob.app.deploy()`), `orchestrator.py:205` (`app.cleanup()`) |
| `self.namespace` | BaseTask | `orchestrator.py:207` |
| `self.faulty_service` | BaseTask | problem's own `eval` |
| `inject_fault()` | BaseTask | `orchestrator.py:78` (inside `CriticalSection`) |
| `recover_fault()` | BaseTask | `orchestrator.py:179`, `:198`, and `atexit` hook `orchestrator.py:233-235` |
| `start_workload()` | BaseTask | `orchestrator.py:82-85` (sync **or** async, detected with `inspect.iscoroutinefunction`) |
| `get_task_description()` | TaskType | `orchestrator.py:87` |
| `get_instructions()` | TaskType | `orchestrator.py:88` |
| `get_available_actions()` | TaskType | `orchestrator.py:89` |
| `perform_action(name,*a,**kw)` | TaskType | `orchestrator.py:130` |
| `eval(soln, trace, duration)` | concrete problem | `orchestrator.py:187-189` |

### 2.2 `eval()` — detection (answer-based, exact string match)

`aiopslab/orchestrator/problems/k8s_target_port_misconfig/target_port.py:66-81`:

```python
    def eval(self, soln: Any, trace: list[SessionItem], duration: float):
        print("== Evaluation ==")
        expected_solution = "Yes"

        if isinstance(soln, str):
            if soln.strip().lower() == expected_solution.lower():
                print(f"Correct detection: {soln}")
                self.add_result("Detection Accuracy", "Correct")
            else:
                print(f"Incorrect detection: {soln}")
                self.add_result("Detection Accuracy", "Incorrect")
        else:
            print("Invalid solution format")
            self.add_result("Detection Accuracy", "Invalid Format")

        return super().eval(soln, trace, duration)
```

This exact block is copy-pasted verbatim into ~20 problem files (verified identical in
`misconfig_app_hotel_res.py:66-81`, `ad_service_failure.py:41-56`,
`kafka_queue_problems.py:41-56`, `container_kill.py:68-83`, `wrong_bin_usage.py:64-79`,
`redeploy_without_pv.py:63-78`, `flower_node_stop/node_stop.py:54-69`,
`flower_model_misconfig/model_misconfig.py:81-96`). The only divergence is `no_op`, where
`expected_solution = "No"` (`aiopslab/orchestrator/problems/no_op/no_op.py:83`) — these are the
false-positive controls (file docstring `no_op.py:1`: *"No operation problem ... to test false
positive."*).

**Verdict: answer-based, case-insensitive exact string match. `Detection Accuracy` is a
*string* (`"Correct"` / `"Incorrect"` / `"Invalid Format"`), not a number or bool.**

### 2.3 `eval()` — localization (answer-based, set membership + partial credit)

`aiopslab/orchestrator/problems/k8s_target_port_misconfig/target_port.py:92-127`:

```python
    def eval(self, soln: Any, trace: list[SessionItem], duration: float):
        print("== Evaluation ==")

        if soln is None:
            print("Solution is None")
            self.add_result("Localization Accuracy", 0.0)
            self.results["success"] = False
            self.results["is_subset"] = False
            super().eval(soln, trace, duration)
            return self.results

        # Calculate exact match and subset
        is_exact = is_exact_match(soln, self.faulty_service)
        is_sub = is_subset([self.faulty_service], soln)

        # Determine accuracy
        if is_exact:
            accuracy = 100.0
            print(f"Exact match: {soln} | Accuracy: {accuracy}%")
        elif is_sub:
            accuracy = (len([self.faulty_service]) / len(soln)) * 100.0
            print(f"Subset match: {soln} | Accuracy: {accuracy:.2f}%")
        else:
            accuracy = 0.0
            print(f"No match: {soln} | Accuracy: {accuracy}%")

        # Add result to the task
        self.add_result("Localization Accuracy", accuracy)

        # Continue with the base evaluation logic
        super().eval(soln, trace, duration)

        self.results["success"] = is_exact or (is_sub and len(soln) == 1)
        self.results["is_subset"] = is_sub

        return self.results
```

Semantics: **precision-style partial credit** — if the agent names the true faulty service plus N-1
extras, accuracy = `100/N`. `success` is only True when the answer is exactly the single ground-truth
service. Helper definitions at `aiopslab/orchestrator/evaluators/quantitative.py:36-66`:

```python
def is_exact_match(pred: int | str | list, target: int | str | list) -> bool:
    """Return True if the prediction is an exact match to the target.
    Also considers ["x"] and "x" as equivalent.
    """
    # Normalize both sides to lists for consistent comparison
    def normalize(value: int | str | list) -> list:
        if isinstance(value, list):
            return value
        return [value]

    return normalize(pred) == normalize(target)


def is_subset(pred: list, target: list) -> bool:
    """Return True if the prediction is a subset of the target."""
    return set(pred).issubset(set(target))
```

Note the naming is confusing: `is_subset([self.faulty_service], soln)` actually asks *"is the
ground truth contained in the agent's answer"*.

### 2.4 `eval()` — analysis (answer-based, 2-field categorical exact match)

`aiopslab/orchestrator/problems/k8s_target_port_misconfig/target_port.py:136-160`:

```python
    def eval(self, soln: Any, trace: list[SessionItem], duration: float):
        print("== Evaluation ==")

        if not isinstance(soln, dict):
            print("Solution is not a dictionary")
            self.results["system_level_correct"] = False
            self.results["fault_type_correct"] = False
            self.results["success"] = False
            super().eval(soln, trace, duration)
            return self.results

        is_sys_level_correct = is_exact_match_lower(
            soln.get("system_level", ""), "Virtualization"
        )
        is_fault_type_correct = is_exact_match_lower(
            soln.get("fault_type", ""), "Misconfiguration"
        )

        self.results["system_level_correct"] = is_sys_level_correct
        self.results["fault_type_correct"] = is_fault_type_correct
        self.results["success"] = is_sys_level_correct and is_fault_type_correct
```

Ground-truth labels for all 13 analysis problems:

| Problem family | `system_level` | `fault_type` | Cite |
|---|---|---|---|
| `k8s_target_port-misconfig-analysis-{1,2,3}` | Virtualization | Misconfiguration | `k8s_target_port_misconfig/target_port.py:148,151` |
| `auth_miss_mongodb-analysis-1` | Application | Misconfiguration | `auth_miss_mongodb/auth_miss_mongodb.py:137-138` |
| `revoke_auth_mongodb-analysis-{1,2}` | Application | Authentication Issue | `revoke_auth/revoke_auth.py:143,146` |
| `user_unregistered_mongodb-analysis-{1,2}` | Application | Network/Storage Issue | `storage_user_unregistered/storage_user_unregistered.py:149,152` |
| `misconfig_app_hotel_res-analysis-1` | Application | Misconfiguration | `misconfig_app/misconfig_app_hotel_res.py:143,146` |
| `scale_pod_zero_social_net-analysis-1` | Virtualization | Operation Error | `scale_pod/scale_pod_social_net.py` (expected_* consts) |
| `assign_to_non_existent_node_social_net-analysis-1` | Virtualization | Dependency Problem | `assign_non_existent_node/assign_non_existent_node_social_net.py` |
| `redeploy_without_PV-analysis-1` | Virtualization | Operation Error | `redeploy_without_pv/redeploy_without_pv.py:142,145` |
| `wrong_bin_usage-analysis-1` | Application | Network/Storage Issue | `wrong_bin_usage/wrong_bin_usage.py:141,144` |

The label vocabulary is fixed and is given to the agent verbatim in the task description
(`aiopslab/orchestrator/tasks/analysis.py:34-46`): system levels
`Hardware | Operating System | Virtualization | Application`; fault types
`Misconfiguration | Code Defect | Authentication Issue | Network/Storage Issue | Operation Error |
Dependency Problem`. So analysis is effectively a **4×6 classification**, graded by
`is_exact_match_lower` (`quantitative.py:49-51`).

### 2.5 `eval()` — mitigation (STATE-BASED — the only task type that inspects the cluster)

`aiopslab/orchestrator/problems/k8s_target_port_misconfig/target_port.py:169-210`:

```python
    def eval(self, soln: Any, trace: list[SessionItem], duration: float) -> dict:
        print("== Evaluation ==")
        super().eval(soln, trace, duration)

        # custom: check if target port has been reset to 9090
        configs = self.kubectl.get_service_json(self.faulty_service, self.namespace)
        target_port = configs["spec"]["ports"][0]["targetPort"]
        all_normal = is_exact_match(target_port, 9090)

        if all_normal:
            # Check if all services (not only faulty service) is back to normal (Running)
            pod_list = self.kubectl.list_pods(self.namespace)
            for pod in pod_list.items:
                if pod.status.container_statuses:
                    # Check container statuses
                    for container_status in pod.status.container_statuses:
                        if (
                            container_status.state.waiting
                            and container_status.state.waiting.reason
                            == "CrashLoopBackOff"
                        ):
                            ...
                            all_normal = False
                        elif (
                            container_status.state.terminated
                            and container_status.state.terminated.reason != "Completed"
                        ):
                            ...
                            all_normal = False
                        elif not container_status.ready:
                            print(f"Container {container_status.name} is not ready")
                            all_normal = False

                if not all_normal:
                    break

        self.results["success"] = all_normal
        return self.results
```

Two other mitigation shapes exist:

- **Readiness-poll only** — `misconfig_app/misconfig_app_hotel_res.py:164-177`:
  ```python
          try:
              self.kubectl.wait_for_ready(self.namespace, sleep=5, max_wait=60)
              self.results["success"] = True
          except Exception as e:
              print(f"Pods are not all ready: {e}")
              self.results["success"] = False
  ```
- **Readiness + deployment-spec assertion** — `wrong_bin_usage/wrong_bin_usage.py:190-208`:
  ```python
          # Check if the deployment was updated to use the right binary
          expected_command = "profile" # Command dictates which binary will be ran, we want to run /go/bin/profile and not /go/bin/geo
          ...
                  if expected_command not in command:
                      print(
                          f"[FAIL] Deployment for container '{container.name}' is using wrong binary: {command}"
                      )
                      self.results["success"] = False
  ```

`Task.sys_status_after_recovery()` (`aiopslab/orchestrator/tasks/base.py:58-81`) contains the same
pod-readiness logic factored out, but its only call site in `orchestrator.py:204` is **commented
out**.

**Summary of done-ness judgement:**
- Detection → **answer-based** (string equality).
- Localization → **answer-based** (set/exact match with partial credit).
- Analysis → **answer-based** (categorical exact match on two fields).
- Mitigation → **state-based** (live `kubectl` queries: pod readiness, service targetPort,
  deployment `command`). The `submit()` call itself carries no information —
  `aiopslab/orchestrator/actions/mitigation.py:28-30`: *"for mitigation task, the submission is valid
  if the solution is submitted / NOTE: this does not mean the solution is correct!"*
- **LLM-judged** is an optional *additional* score layered on all four (see §4).

---

## 3. Input documents / agent context (D1, D3)

### 3.1 What `init_problem()` returns

`aiopslab/orchestrator/orchestrator.py:87-91`:

```python
        task_desc = prob.get_task_description()
        instructions = prob.get_instructions()
        actions = prob.get_available_actions()

        return task_desc, instructions, actions
```

Three artifacts: a **task description**, **format instructions**, and an **API dict**
(`{action_name: docstring}`).

### 3.2 Task description templates (verbatim)

Detection — `aiopslab/orchestrator/tasks/detection.py:28-36`:

```python
        self.task_desc = """\
            You are an expert DevOps engineer assigned to detect anomalies in a deployed service.
            
            Service Details:
            {app_summary}

            You will begin by analyzing the service's state and telemetry, and then submit your solution:
            1. str: "Yes" or "No" to indicate whether there are anomalies detected
            """
```

Localization — `aiopslab/orchestrator/tasks/localization.py:28-38`:

```python
        self.task_desc = """\
            You are an expert DevOps engineer assigned to localize faults in a deployed service.

            Service Details:
            {app_summary}

            You are requested to identify the service(s) where the root cause of the fault lies.
            You will begin by analyzing the service's state and telemetry, and then submit one of two possible solutions:
            1. list[str]: list of faulty components (i.e., service names)
            2. list[]: an empty list if no faults were detected
            """
```

Analysis — `aiopslab/orchestrator/tasks/analysis.py:27-49`:

```python
        self.task_desc = """\
            You are an expert DevOps engineer assigned to do root cause analysis in a deployed service.

            Service Details:
            {app_summary}

            You will begin by analyzing the service's state and telemetry, and then submit one of two possible solutions:
            1. dict[str, str]: A dictionary with two keys: 'system_level' and 'fault_type'.
                - system_level: The system level at which the fault occurred. Please choose from the following options:
                    - 'Hardware'
                    - 'Operating System'
                    - 'Virtualization'
                    - 'Application'
                - fault_type: The type of fault that occurred. Please choose from the following options:
                    - 'Misconfiguration'
                    - 'Code Defect'
                    - 'Authentication Issue'
                    - 'Network/Storage Issue'
                    - 'Operation Error'
                    - 'Dependency Problem'
            
            2. str: `None` if no faults were detected
            """
```

Mitigation — `aiopslab/orchestrator/tasks/mitigation.py:27-35`:

```python
        self.task_desc = """\
            You are an expert DevOps engineer assigned to mitigate anomalies in a deployed service.

            Service Details:
            {app_summary}

            You will begin by analyzing the service's state and telemetry, and then submit a solution that mitigates any detected anomalies.
            Your mitigation can be performed using any of the available APIs.
            """
```

### 3.3 `{app_summary}` — the only environment description the agent gets

`aiopslab/service/apps/base.py:53-69`:

```python
    def get_app_summary(self) -> str:
        """Get a summary of the application metadata in string format.
        NOTE: for human and LLM-readable summaries!
        """
        app_json = self.get_app_json()
        app_name = app_json.get("Name", "")
        namespace = app_json.get("Namespace", "")
        desc = app_json.get("Desc", "")
        supported_operations = app_json.get("Supported Operations", [])
        operations_str = "\n".join([f"  - {op}" for op in supported_operations])

        description = f"Service Name: {app_name}\nNamespace: {namespace}\nDescription: {desc}\nSupported Operations:\n{operations_str}"

        return description
```

Source data, e.g. `aiopslab/service/metadata/social-network.json:1-13`:

```json
{
    "Name": "Social Network",
    "Namespace": "test-social-network",
    "Desc": "A social network with unidirectional follow relationships, implemented with loosely-coupled microservices, communicating with each other via Thrift RPCs.",
    "Supported Operations": [
        "Create text post (optional media: image, video, shortened URL, user tag)",
        "Read post",
        "Read entire user timeline",
        "Receive recommendations on which users to follow",
        "Search database for user or post",
        "Register/Login using user credentials",
        "Follow/Unfollow user"
    ],
    ...
}
```

**Important (D1):** there is **no alert, no incident ticket, no symptom description, no timestamp, no
service-dependency graph, and no service inventory** given to the agent. The agent is told only the
app's name, namespace, one-sentence description, and user-facing operations. It must discover
everything else via `exec_shell` / telemetry APIs.

### 3.4 Instruction template (the action DSL contract)

`aiopslab/orchestrator/tasks/detection.py:38-56`:

```python
        self.instructions = """\
            You will respond with one of the above APIs as your next action.
            Please respond in the following format in a markdown code block:
            ```\n<API_NAME>(<API_PARAM1>, <API_PARAM2> ...)\n```

            For instance, if you want to list files in current directory, your response must be exactly:
            
            ```\nexec_shell("ls -l")\n```

            If you decide that there are no anomalies:

            ```\nsubmit(\"No\")\n```

            Or, if anomalies are found:

            ```\nsubmit(\"Yes\")\n```

            Please respond with only a single API call (a.k.a., action) per turn without any additional words, labels, or prefixes.
            """
```

Mitigation's variant adds (`aiopslab/orchestrator/tasks/mitigation.py:50-53`):

```
            Note:
            - The submit() call for the mitigation task does not take any parameters.
            - A submission via submit() is considered valid if it is made, though this does not necessarily indicate that your solution is correct.
```

### 3.5 The telemetry surface (D3) — how the agent actually gets logs/metrics/traces

All telemetry is exposed as **actions** on `TaskActions` (`aiopslab/orchestrator/actions/base.py`),
not as pre-supplied documents.

**Logs** — `aiopslab/orchestrator/actions/base.py:32-76`. This is a thin wrapper over
`kubectl logs` (or `docker logs` when `namespace == "docker"`), with a **hard-coded label-selector
table per namespace**:

```python
        else:
            kubectl = KubeCtl()
            try:
                if namespace == "test-social-network":
                    user_service_pod = kubectl.get_pod_name(namespace, f"app={service}")
                elif namespace == "test-hotel-reservation":
                    user_service_pod = kubectl.get_pod_name(
                        namespace, f"io.kompose.service={service}"
                    )
                elif namespace == "astronomy-shop":
                    user_service_pod = kubectl.get_pod_name(
                        namespace, f"app.kubernetes.io/name={service}"
                    )
                elif namespace == "default" and "wrk2-job" in service:
                    user_service_pod = kubectl.get_pod_name(namespace, f"job-name=wrk2-job")
                else:
                        raise Exception
                logs = kubectl.get_pod_logs(user_service_pod, namespace)
            except Exception as e:
                return "Error: Your service/namespace does not exist. Use kubectl to check."
```

Note it returns logs from **only the first matching pod** (`get_pod_name` → `pod_info.items[0]`,
`aiopslab/service/kubectl.py:79-84`). Logs are then passed through a timestamp-aware deduplicator
(`base.py:73`, `greedy_compress_lines`), which is **a no-op unless the `LOG_TRIM` env var is set**
(`aiopslab/orchestrator/actions/log_deduplication.py:113-122`):

```python
    log_trim = None
    try:
        value = os.environ.get("LOG_TRIM")
        log_trim = int(value) if value is not None else None
    except ValueError:
        log_trim = None
    if not log_trim or log_trim <= 0:
        return raw_str
```

The same compression is applied to shell output when the command matches
`LOG_COMMAND_PATTERN` (`base.py:22-27`, `base.py:106-107`) — i.e. `kubectl logs|get events|describe`,
`docker logs|events`.

**Metrics** — `aiopslab/orchestrator/actions/base.py:113-141`. Crucially, the action **does not
return metric values; it returns a directory listing**:

```python
        prometheus_url = (
            "http://localhost:32000"  # Replace with your Prometheus server URL
        )
        prometheus_api = PrometheusAPI(prometheus_url, namespace)
        prometheus_api.initialize_pod_and_service_lists(namespace)

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration)
        save_path = os.path.join(os.getcwd(), "metrics_output")

        # Export all metrics and save to the specified path
        save_dir_str = prometheus_api.export_all_metrics(
            start_time=start_time, end_time=end_time, save_path=save_path, step=15
        )

        return save_dir_str
```

`export_all_metrics` writes one CSV per metric under `metrics_output/metric_<ts>/container/` and
returns a rendered folder tree (`aiopslab/observer/metric_api.py:409-419`). The agent must then call
`read_metrics(file_path)` (`base.py:143-164`) to see the numbers, which are dumped as
`df.to_string(index=False)`. The metric whitelist is `normal_metrics` at
`aiopslab/observer/metric_api.py:21-53` — 24 cAdvisor container metrics (CPU seconds/throttling/load,
memory cache/usage/RSS/working-set, cpu period/quota/limits, threads, network rx/tx bytes/packets/
errors/drops). An `istio_metrics` list exists (`metric_api.py:54-66`) but its export block is
**entirely commented out** (`metric_api.py:375-406`).

**Traces** — `aiopslab/orchestrator/actions/base.py:166-190`, same "write CSV, return path" pattern,
backed by Jaeger via `TraceAPI` (`aiopslab/observer/trace_api.py:19`). The processed trace schema is
`trace_id, span_id, parent_span, service_name, operation_name, start_time, duration, has_error,
response` (`trace_api.py:295-307`). Companion reader `read_traces` at `base.py:193-214`.

**What is NOT wired into the agent's tool surface:**
- `aiopslab/observer/log_api.py` (Elasticsearch/Logstash `LogAPI`) — used only by the offline
  collector `aiopslab/observer/observe.py:24-34`, never by any action.
- `aiopslab/service/telemetry/loki.py` (`Loki.query` / `query_range`) — **dead code**; no importer
  anywhere in `aiopslab/` or `clients/`.
- `TaskActions.get_microservice_repo_diff` — body commented out with
  `# NOTE: disabled for now, since seems like a cheat for code changes` (`base.py:217-218`) and it
  carries no `@action` decorator, so it is invisible to `get_actions()`.

### 3.6 A real, complete task prompt (as printed by the CLI)

`TutorialSetup.md:88-185` records the actual rendered prompt for
`misconfig_app_hotel_res-detection-1` (excerpted):

```
You are an expert DevOps engineer who has been tasked with detecting anomalies in a deployed service.

The service you are working with today is described below: Service Name: Hotel Reservation Namespace: test-hotel-reservation Description: A hotel reservation application built
with Go and gRPC, providing backend in-memory and persistent databases, a recommender system for hotel recommendations, and a functionality to place reservations. Supported
Operations:

 • Get profile and rates of nearby hotels available during given time periods
 • Recommend hotels based on user provided metrics
 • Place reservations

You will begin by analyzing the service's state and telemetry, and then submit your solution:

 1 str: Yes or No to indicate whether there are anomalies detected

You are provided with the following APIs to interact with the service:

get_logs Collects relevant log data from a pod using Kubectl.
     Args:
         namespace (str): The namespace in which the service is running.
         service (str): The name of the service.
     Returns:
         str | dict | list[dicts]: Log data as a structured object or a string.

get_metrics Collects metrics data from the service using Prometheus.
...
You are also provided an API to a secure terminal to the service where you can run commands:

exec_shell Execute any shell command in a predefined debugging environment. Note: this is NOT A STATEFUL OR INTERACTIVE shell session. So you cannot execute commands like
"kubectl edit".
...
Finally, you will submit your solution for this task using the following API:

submit Submit if anomalies are detected to the orchestrator for evaluation.
...
At each turn think step-by-step and respond with your action.
╭─────────────────── Environment ───────────────────╮
│ Please take the next action                       │
╰───────────────────────────────────────────────────╯
```

(The wording in `TutorialSetup.md` — *"who has been tasked with"* — is an older revision of the
template; the live code at `tasks/detection.py:29` reads *"assigned to detect anomalies"*.)

The per-turn observation is literally `env_response + "\n" + "Please take the next action"`
(`aiopslab/orchestrator/orchestrator.py:155`, `:173`).

---

## 4. Verification (G1, G4, G5)

### 4.1 Evaluator module layout

`aiopslab/orchestrator/evaluators/` contains exactly three files: `quantitative.py`,
`qualitative.py`, `prompts.py`.

### 4.2 Quantitative metrics (the complete list)

`aiopslab/orchestrator/evaluators/quantitative.py:10-66`:

```python
# Constants
token_model = "gpt-3.5-turbo"
tokenizer = tiktoken.encoding_for_model(token_model)


def num_steps_taken(trace: list[SessionItem]) -> int:
    """Return the number of steps taken in the trace."""
    return len([item for item in trace if item.role == "assistant"])


def out_tokens(trace: list[SessionItem]) -> int:
    """Return the (approx) total token cost of the agent's output."""
    # NOTE: not dollar value, since depends on Agent's model

    agent_steps = "".join([item.content for item in trace if item.role == "assistant"])
    return len(tokenizer.encode(agent_steps, disallowed_special=()))


def in_tokens(trace: list[SessionItem]) -> int:
    """Return the (approx) total token cost of the env's input."""
    ...
```

plus `is_exact_match`, `is_exact_match_lower`, `is_in_range`, `is_subset`, `is_superset`.
`is_in_range` and `is_superset` have **no call sites** in the repo.

Trailing TODO at `quantitative.py:69-71`:

```python
# TODO: once observability is setup, use metrics, traces, logs,
# and wrk2's logs to also observe the (side)-effects of agents' actions
# e.g., latency, throughput, etc.
```

i.e. **no SLO / latency / throughput / blast-radius metric is implemented**.

### 4.3 Is there an LLM judge? — YES, optional, off by default

`aiopslab/orchestrator/tasks/base.py:37-56`:

```python
    def common_eval(self, trace: list[SessionItem]):
        """Common evaluation function across tasks. Both quantitative and (optionally) qualitative evaluation.
        NOTE: This method must be called by the `eval` method of each task.
        ...
        """
        self.add_result("steps", num_steps_taken(trace))
        self.add_result("in_tokens", in_tokens(trace))
        self.add_result("out_tokens", out_tokens(trace))

        if config.get("qualitative_eval"):
            judge = LLMJudge(trace)
            score, judgement = judge.reasoning_score()
            self.add_result("reasoning_judgement", judgement)
            self.add_result("reasoning_score", score)
```

Default is off — `aiopslab/config.yml.example:11-12`:
```yaml
# Flag to enable/disable qualitative evaluation (makes LLM calls)
qualitative_eval: false
```
CI also forces it off (`.github/workflows/integration-test.yml:165`).

**The judge prompt, verbatim** (`aiopslab/orchestrator/evaluators/prompts.py:6-23`):

```python
SCORE_SYSTEM = """Please act as an impartial judge and evaluate the quality of the response provided by an AI assistant towards a Service Operations task displayed below. 
Your evaluation should consider factors such as the helpfulness, relevance, accuracy, depth, creativity, and level of detail of the response. 
Begin your evaluation by providing a short explanation. Be as objective as possible. 
After providing your explanation, you must rate the response on a scale of 1 to 10 by strictly following this format: "[[rating]]", for example: "Rating: [[5]]".

"""

SCORE_TASK = """<|The Start of Assistant A's Interaction with Service|>

{trace}

<|The End of Assistant A's Interaction with Service|>"
"""

SCORER_PROMPTS = {
    "system": SCORE_SYSTEM,
    "user": SCORE_TASK,
}
```

Judge model is hard-pinned (`aiopslab/orchestrator/evaluators/qualitative.py:65-90`):

```python
class GPT4Turbo:
    """An abstraction of the GPT-4 Turbo model (default judge)."""
    ...
            response = client.chat.completions.create(
                messages=payload,  # type: ignore
                model="gpt-4-turbo-2024-04-09",
                max_tokens=1024,
                temperature=0.0,
                top_p=0.95,
                ...
```

Score parsing falls back to `-1` on failure (`qualitative.py:48-62`):

```python
    def _parse_score(self, judgement: str) -> int:
        """Parse the score from the judgement."""
        one_score_pattern = re.compile(r"\[\[(\d+\.?\d*)\]\]")
        one_score_pattern_backup = re.compile(r"\[(\d+\.?\d*)\]")
        ...
        if match:
            score = ast.literal_eval(match.groups()[0])
        else:
            score = -1
        return score
```

Judge calls are cached to `~/cache_dir/llm_cache.json` (`aiopslab/utils/cache.py:10-39`,
`aiopslab/paths.py:23-24`). Note the judge reads `os.getenv("OPENAI_KEY")` (`qualitative.py:77`)
while every client reads `OPENAI_API_KEY` — an env-var name mismatch.

### 4.4 Separating environment failure from model failure (G5)

**There is no explicit separation.** Everything degrades into an observation string:

`aiopslab/orchestrator/orchestrator.py:113-143`:

```python
    async def ask_env(self, input):
        """Ask the environment for the observation given the current action."""
        assert self.session is not None

        try:
            resp = self.parser.parse(input)
        except ResponseParsingError as e:
            self.session.add({"role": "env", "content": str(e)})
            return str(e)

        api, args, kwargs = resp["api_name"], resp["args"], resp["kwargs"]

        # if submit, save solution for eval
        if api == "submit":
            self.session.set_solution(args[0] if len(args) == 1 else args)

        try:
            env_response = self.session.problem.perform_action(api, *args, **kwargs)

            if hasattr(env_response, "error"):
                env_response = str(env_response)
                print("An error occurred:", env_response)
        except InvalidActionError as e:
            env_response = str(e)
        except Exception as e:
            env_response = str(e)
            print("Unhandled exception:", e)

        self.session.add({"role": "env", "content": env_response})

        return env_response
```

Observations:
- A malformed response → `ResponseParsingError` text fed back as the observation, agent keeps going,
  the step still counts toward `steps` and `max_steps`. There is **no retry budget and no
  "invalid response" counter** in results.
- An unknown API → `InvalidActionError` (`aiopslab/utils/status.py:20-23`) → string observation.
- **Any** unexpected exception (K8s API down, port-forward failed, Prometheus unreachable) is
  caught by the bare `except Exception` and handed to the agent as text — indistinguishable in the
  results JSON from a legitimate error message.
- `str` matching is used for env errors: `get_logs` returns literal
  `"Error: Your service/namespace does not exist. Use kubectl to check."` (`actions/base.py:71`);
  `read_metrics` returns `f"error: Metrics file '{file_path}' not found."` (`base.py:156`).

**Max-steps handling** (`orchestrator.py:161-192`): the loop simply runs out; there is no
`timeout`/`truncated` flag written to results. Whether the run ended by `submit()` or by exhausting
`max_steps` is only inferable from `final_state` in the returned dict, which is **not persisted** —
`Session.to_dict()` (`aiopslab/session.py:103-115`) stores `agent, session_id, problem_id,
start_time, end_time, trace, results` and nothing else.

**INVALID_SUBMISSION**: `orchestrator.py:170-171` raises on it —
```python
                elif env_response == SubmissionStatus.INVALID_SUBMISSION:
                    raise ValueError("Invalid submission!")  # TODO (@manish): ask to retry?
```
— but **no action class ever returns it**: `DetectionActions.submit`, `LocalizationActions.submit`,
`AnalysisActions.submit`, `MitigationActions.submit` all unconditionally return
`SubmissionStatus.VALID_SUBMISSION` (`actions/detection.py:29`, `actions/localization.py:28`,
`actions/analysis.py:28`, `actions/mitigation.py:30`). The only path that produces
`INVALID_SUBMISSION` is the separate onboarding `Evaluator` (`aiopslab/onboarding_evaluator.py:139`,
`:145`), which re-evaluates on each submit and lets the human retry.

**Fault cleanup on failure** is defensive (`orchestrator.py:174-181`, `:233-235`):

```python
        except Exception as e:
            # Make sure the fault cleanup function is unregistered
            # after recovering fault ahead because of exceptions
            with CriticalSection():
                print("Some exception happened. Recovering the injected fault...")
                self.session.problem.recover_fault()
                atexit.unregister(exit_cleanup_fault)
            raise e
```

`CriticalSection` (`aiopslab/utils/critical_section.py:5-28`) defers SIGINT so Ctrl-C cannot leave a
fault injected.

---

## 5. Flakiness and nondeterminism (G2)

### 5.1 Faults that self-heal on a timer — the biggest source of nondeterminism

Every Chaos-Mesh symptom fault carries a `duration` and Chaos Mesh un-applies it when it expires:

| Fault | duration | Cite |
|---|---|---|
| `inject_pod_failure` | `"200s"` default | `aiopslab/generators/fault/inject_symp.py:66,76` |
| `inject_network_loss` | `"200s"` default | `inject_symp.py:89,100` |
| `inject_container_kill` | `"200s"` hard-coded | `inject_symp.py:121` |
| `inject_network_delay` | `"200s"` default, latency `"10s"`, jitter `"0ms"` | `inject_symp.py:135-140,162` |
| `inject_pod_kill` | `"200s"` default; problem passes `"100s"` | `inject_symp.py:171`; `problems/pod_kill/pod_kill.py:40` |
| `no_op` | `"200s"` (no-op anyway) | `problems/no_op/no_op.py:64` |

An agent with `max_steps=30` and multi-second telemetry calls can easily exceed 100–200 s, at which
point the environment has already recovered and detection/localization become unanswerable — yet the
ground truth is still `"Yes"` / the faulty service. Nothing in the code re-checks that the fault is
still active at eval time.

### 5.2 Fixed sleeps (complete inventory)

| Sleep | Purpose | Cite |
|---|---|---|
| `time.sleep(6)` after **every** `_inject` | fault propagation | `aiopslab/generators/fault/base.py:51` |
| `time.sleep(3)` after MongoDB revoke-auth pod deletion | | `generators/fault/inject_app.py:65` |
| `time.sleep(10)` after `misconfig_app` image swap | | `inject_app.py:164` |
| `time.sleep(15)` after namespace delete in `redeploy_without_pv` | | `generators/fault/inject_virtual.py:115` |
| `time.sleep(15)` "Waiting for faults to propagate" after `container_stop` | | `inject_virtual.py:179` |
| `time.sleep(25)` in `assign_non_existent_node` | | `problems/assign_non_existent_node/assign_non_existent_node_social_net.py:50` |
| `time.sleep(30)` in `scale_pod` | | `problems/scale_pod/scale_pod_social_net.py:53` |
| `time.sleep(30)` after HotelReservation `deploy_without_wait` | | `service/apps/hotelres.py:79` |
| `time.sleep(10)` / `time.sleep(5)` in HotelReservation `cleanup` (PV reaping) | | `hotelres.py:88,99` |
| `time.sleep(30)` in AstronomyShop / TrainTicket / FlightTicket `delete()` | | `apps/astronomy_shop.py:38`, `apps/train_ticket.py:34`, `apps/flight_ticket.py:38` |
| `time.sleep(5)` polling wrk2 Job status; `time.sleep(5)` after Job delete | | `generators/workload/wrk.py:119,97` |
| `time.sleep(3)` ×2 for kubectl port-forward warmup (Prometheus, Jaeger) | | `observer/metric_api.py:188,210`; `observer/trace_api.py:104,132` |
| `time.sleep(60)` in vLLM client | | `clients/vllm.py:98` |

### 5.3 Readiness polling / waits

- `KubeCtl.wait_for_ready(namespace, sleep=2, max_wait=300)` —
  `aiopslab/service/kubectl.py:114-143`; raises `Exception("[red]Timeout: ...")` after 300 s. Called
  by `Helm.assert_if_deployed` (`service/helm.py:133`), `HotelReservation.deploy`
  (`apps/hotelres.py:71`), and the orchestrator for OpenEBS (`orchestrator.py:63`).
- `KubeCtl.wait_for_namespace_deletion(namespace, sleep=2, max_wait=300)` — `kubectl.py:145-164`.
- `KubeCtl.get_container_runtime(max_wait=60, poll_interval=2)` — `kubectl.py:57-77`; returns `None`
  on timeout, which makes `SymptomFaultInjector.__init__` raise
  `"Could not detect container runtime."` (`inject_symp.py:31-35`).
- `VirtualizationFaultInjector._wait_for_pods_ready` issues a real `kubectl wait`
  (`inject_virtual.py:201-205`) — but it has **no call sites**:
  ```python
      def _wait_for_pods_ready(self, microservices: list[str], timeout: int = 30):
          for service in microservices:
              command = f"kubectl wait --for=condition=ready pod -l app={service} -n {self.namespace} --timeout={timeout}s"
  ```
- The mitigation eval for `misconfig_app` polls with a **shorter** budget than deploy
  (`sleep=5, max_wait=60`, `misconfig_app_hotel_res.py:171`) — a slow-recovering cluster scores
  `success=False`.

### 5.4 Retries

- Port-forward retry loops: `for attempt in range(3)` with 3 s backoff — `observer/metric_api.py:183`
  and `observer/trace_api.py:99`. On exhaustion they only `print("Failed to establish port forwarding
  ...")` and continue with a dead connection.
- Elasticsearch client `max_retries=5, retry_on_timeout=True` — `observer/log_api.py:29-30,39-40`.
- **No retry anywhere in the agent loop**; a `ResponseParsingError` consumes a step.

### 5.5 Port / URL fragility

`TaskActions.get_metrics` hard-codes `prometheus_url = "http://localhost:32000"`
(`actions/base.py:126-128`) while `PrometheusAPI.__init__` picks a *free* port via
`find_free_port(start=32000, end=32100)` and port-forwards `svc/prometheus-server` in namespace
`observe` to it (`observer/metric_api.py:143-145, 156-161, 191`). If 32000 is taken, the forwarder
listens on 32001+ but the Prometheus client still queries 32000.

`TraceAPI` special-cases `astronomy-shop` (pod port-forward on 16686, base URL
`http://localhost:16686/jaeger/ui`) vs everything else (NodePort lookup, then fallback)
— `observer/trace_api.py:26-37`.

### 5.6 Workload generator warmup

`Wrk` (`aiopslab/generators/workload/wrk.py:12-134`) launches wrk2 as a K8s **Job** in namespace
`default`, mounting the Lua payload from a ConfigMap, then blocks polling job status every 5 s
(`wrk.py:110-121`). Typical problem settings are `rate=10, dist="exp", connections=2, duration=10,
threads=2` (e.g. `target_port.py:35`); `container_kill` and `disk_woreout` use `rate=100`
(`container_kill.py:39`, `disk_woreout.py:34`). Astronomy-Shop problems skip wrk entirely —
`ad_service_failure.py:22-23`: *"Workload skipped since AstronomyShop has a built-in load
generator."*

Flower's `start_workload` busy-waits on log content until it sees an error
(`problems/flower_model_misconfig/model_misconfig.py:44-51`):

```python
        print("Waiting for faults to propagate...")
        while True:
            logs = self.docker.get_logs(self.faulty_service)
            if "error" in logs.lower():
                break
            time.sleep(1)
        print("Faults propagated.")
```

This is an **unbounded loop with no timeout**.

### 5.7 Other nondeterminism

- Chaos Mesh selectors use `"mode": "one"` — for multi-replica services the victim pod is chosen
  arbitrarily (`inject_symp.py:76, 99, 122, 158, 190`).
- `get_logs` reads only `items[0]` of the label-matched pods (`kubectl.py:84`).
- LLM judge cache (`utils/cache.py`) makes repeated judging deterministic across runs but only if the
  trace text is byte-identical.
- `PrometheusAPI.query_range` converts all timestamps into `Asia/Shanghai`
  (`observer/metric_api.py:299`) — a hard-coded timezone.

---

## 6. Metrics and reported numbers (G3, H1)

### 6.1 Metric definitions in code

Every `eval()` chain ends in `Task.eval → common_eval`, so **every** result dict carries:

| Key | Definition | Cite |
|---|---|---|
| `steps` | count of `role == "assistant"` items in the trace | `quantitative.py:15-17` |
| `in_tokens` | tiktoken(`gpt-3.5-turbo`) over all non-assistant content | `quantitative.py:28-33` |
| `out_tokens` | tiktoken over all assistant content | `quantitative.py:20-25` |
| `reasoning_score`, `reasoning_judgement` | only when `qualitative_eval: true` | `tasks/base.py:52-56` |

Plus exactly one timing key, set to `Session.get_duration()`:

| Key | Meaning | Cite |
|---|---|---|
| `TTD` — Time To Detect | wall-clock seconds from `session.start()` to `session.end()` | `tasks/detection.py:76` |
| `TTL` — Time To Localize | idem | `tasks/localization.py:80` |
| `TTA` — Time To Analyze | idem | `tasks/analysis.py:91` |
| `TTM` — Time To Mitigate | idem | `tasks/mitigation.py:75` |

`Session.get_duration()` (`aiopslab/session.py:98-101`) is `end_time - start_time`, and
`session.start()` is called **after** deploy/inject/workload (`orchestrator.py:157`), so TT* excludes
setup. **TT* is not "time until the fault was actually resolved" — it is the whole agent episode
duration, including any wasted steps after the fix.**

Task-specific keys:

| Key | Type | Where |
|---|---|---|
| `Detection Accuracy` | `"Correct"` / `"Incorrect"` / `"Invalid Format"` | e.g. `target_port.py:73,76,79` |
| `Localization Accuracy` | float 0–100 | `target_port.py:119` |
| `is_subset` | bool | `target_port.py:125` |
| `system_level_correct`, `fault_type_correct` | bool | `target_port.py:154-155` |
| `success` | bool (all task types except detection) | `target_port.py:124,156,209` |

`framework_overhead` is computed and **printed only** — not added to results
(`orchestrator.py:216-223`):

```python
        total_execution_time = self.execution_end_time - self.execution_start_time
        time_keys = ["TTD", "TTL", "TTA", "TTM"]
        key = next((k for k in time_keys if k in results), None)
        framework_overhead = (
            total_execution_time - results[key]
        )  # Time spent doing everything besides running the agent
        print(f"Framework overhead: {framework_overhead}")
```

(If `results` is empty this line raises `TypeError` on `results[None]` — a latent crash when an
`INVALID_SUBMISSION` path leaves `results == {}`.)

Persistence: `Session.to_json()` writes `data/results/<uuid>_<start_time>.json`
(`session.py:117-123`, `paths.py:18-19`); optional W&B via `USE_WANDB=true`
(`orchestrator.py:31, 194-195`; `session.py:125-127`).

### 6.2 Reported numbers in the repo

**None.** There is no leaderboard, no results table, no baseline scores anywhere in `README.md`,
`TutorialSetup.md`, `CLAUDE.md`, or under `assets/`. `assets/images/` contains only
`aiopslab-arch-open-source.png` (`README.md:20`). Numeric claims live only in the two cited papers
(arXiv 2501.06706, 2407.12165), which are **not vendored** in the repo. The single quantitative claim
in-repo is the (stale) *"60+ problems"* line in `CLAUDE.md`.

---

## 7. Documented failure modes (H3)

Explicitly flagged in-repo:

1. **Kernel fault is broken upstream.** `aiopslab/generators/fault/inject_symp.py:203-205`:
   ```python
   # IMPORTANT NOTE:
   # Kernel fault is not working and is a known bug in chaos-mesh 0> https://github.com/xlab-uiuc/agent-ops/pull/10#issuecomment-2468992285
   # This code is untested as we're waiting for a resolution to the bug to retry.
   ```
   Mirrored at `problems/kernel_fault/kernel_fault.py:5-8` and in the registry
   (`registry.py:165-169`), where both kernel-fault IDs are commented out.
2. **Disk wear-out disabled.** `registry.py:170-171` — `disk_woreout-detection-1` and
   `-localization-1` commented out. The problem itself is unfinished:
   `problems/disk_woreout/disk_woreout.py:22` — `self.faulty_disk = "xxx"  # TODO: need to decide
   which disk?`, and `self.namespace` assignment is commented out (`disk_woreout.py:21`). The
   injector needs a compiled eBPF binary (`generators/fault/inject_os.py:49-56`,
   `generators/fault/bpf_injector/README.md`) run under `sudo`.
3. **All five K8s-operator (TiDB) problems disabled** — `registry.py:206-216`.
4. **`redeploy_without_PV-localization-1` disabled** with
   `# TODO: we need to decide the localization problem in the future`
   (`problems/redeploy_without_pv/redeploy_without_pv.py:82`, `registry.py:198`).
5. **Repo-diff tool deliberately removed as a cheat** — `actions/base.py:217-218`:
   `# @read` / `# NOTE: disabled for now, since seems like a cheat for code changes`.
6. **Mitigation eval acknowledged as too weak for app-level faults** —
   `problems/auth_miss_mongodb/auth_miss_mongodb.py:171-174`:
   ```python
       # TODO: this migigate eval should be a bit different.
       # The error will not be on the container/pod level but the app level,
       # so the possible mitigation task eval should also check
       # whether there are error log appearing.
   ```
7. **Invalid submission has no retry path** — `orchestrator.py:171`:
   `raise ValueError("Invalid submission!")  # TODO (@manish): ask to retry?`
8. **Namespace teardown is knowingly incomplete** — `orchestrator.py:201-204`:
   ```python
        # Beyond recovering from fault,
        # I feel sometimes it is safer to delete the whole namespace.
        # But this will take more time.
        # if not self.session.problem.sys_status_after_recovery():
   ```
9. **Deployment-mode caveat** — `README.md:118`: *"Mode B is convenient for development but some
   fault injectors (e.g., VirtualizationFaultInjector) require Docker on the local machine. Use Mode
   A for full functionality."*
10. **Platform limits** — `CLAUDE.md`: *"Tested on: WSL2 (Ubuntu 22.04) ... The `deploy.py`
    auto-install targets Linux/amd64; macOS and native Windows are not currently supported."*
11. **CI is a single-problem smoke test only** — `.github/workflows/integration-test.yml:31`
    (`name: no-op hotel-reservation smoke test`) running
    `tests/integration/smoke_test.py` with a `DummyAgent` that immediately submits `"No"`
    (`smoke_test.py:29-37`). The workflow itself documents two chronic timeouts it works around:
    OpenEBS image pulls exceeding the hard `max_wait=300s` (`integration-test.yml:86-95`) and
    Prometheus sub-chart pulls doing the same (`integration-test.yml:107-123`).
12. **Astronomy-Shop `paymentFailure` / `imageSlowLoad` need non-boolean variants** —
    `generators/fault/inject_otel.py:31-41`; the final print is nonetheless hard-coded to
    `"set to 'on'"` (`inject_otel.py:52`).
13. **`clients/flash.py` has real bugs**: `hightsight` typo (`flash.py:94`) and
    `diagnose_with_hindsight` returns `None` because it never returns `hindsight`
    (`flash.py:108-115`) — so the "Flash" agent never actually injects hindsight.
14. **`clients/react.py:77` references an undefined name** (`prob_desc=problem_desc` inside
    `init_context`, where the parameter is `problem_desc` — this one is fine — but the module-level
    `problems`/`pid` loop swallows all exceptions at `react.py:129-130`).

---

## 8. Tool surface

### 8.1 How actions are discovered

Decorators mark methods; `get_actions()` reflects over the class and returns
`{method_name: docstring}` — `aiopslab/utils/actions.py:7-48, 51-82`:

```python
def action(method):
    method.is_action = True
    return method

def read(method):
    method.is_action = True
    method.action_type = "read"
    return method

def write(method):
    method.is_action = True
    method.action_type = "write"
    return method


def get_actions(task: str, subtype: str | None = None) -> dict:
    class_name = task.title() + "Actions"
    module = importlib.import_module("aiopslab.orchestrator.actions." + task)
    class_obj = getattr(module, class_name)

    actions = {
        method: getattr(class_obj, method).__doc__.strip()
        for method in dir(class_obj)
        if callable(getattr(class_obj, method))
        and getattr(getattr(class_obj, method), "is_action", False)
    }
    ...
```

**No method in the repo uses `@write`** — every telemetry method is `@read` and `exec_shell`/`submit`
are plain `@action`.

### 8.2 The complete action list (identical for all four task types except `submit`)

`TaskActions` (`aiopslab/orchestrator/actions/base.py:29`) provides 6 shared actions; each
`<Task>Actions` subclass adds exactly one `submit`. That means **all 7 actions below are available to
detection, localization, analysis, AND mitigation agents** — the tool surface does not widen for
mitigation. (`CLAUDE.md`'s claim that mitigation adds "scaling, config patching, restarts" is not
borne out by the code; mitigation is performed through `exec_shell`.)

```python
    @staticmethod
    @read
    def get_logs(namespace: str, service: str) -> str:
        """
        Collects relevant log data from a pod using Kubectl or from a container with Docker.

        Args:
            namespace (str): The namespace in which the service is running.
            service (str): The name of the service.

        Returns:
            str | dict | list[dicts]: Log data as a structured object or a string.
        """
```
(`base.py:32-44`)

```python
    @staticmethod
    @action
    def exec_shell(command: str, timeout: int = 30) -> str:
        """
        Execute any shell command in a predefined debugging environment.
        Note: this is NOT A STATEFUL OR INTERACTIVE shell session. So you cannot
        execute commands like "kubectl edit".

        Args:
            command (str): The command to execute.
            timeout (int): Timeout in seconds for the command execution. Default is 30.

        Returns:
            str: The output of the command.
        """
        BLOCK_LIST: dict[str, str] = {
            "kubectl edit": "Error: Cannot use `kubectl edit`. Use `kubectl patch` instead.",
            "edit svc": "Error: Cannot use `kubectl edit`. Use `kubectl patch` instead.",
            "kubectl port-forward": "Error: Cannot use `kubectl port-forward` because it is an interactive command.",
            "docker logs -f": "Error: Cannot use `docker logs -f`. Use `docker logs` instead.",
            "kubectl logs -f": "Error: Cannot use `kubectl logs -f`. Use `kubectl logs` instead.",
        }
```
(`base.py:78-99` — the blocklist is the only sandboxing.)

```python
    @staticmethod
    @read
    def get_metrics(namespace: str, duration: int = 5) -> str:
        """
        Collects metrics data from the service using Prometheus.
        Args:
            namespace (str): The namespace in which the service is running.
            duration (int): The number of minutes from now to start collecting metrics until now.
        Returns:
            str: Path to the directory where metrics are saved.
        """
```
(`base.py:113-124`)

```python
    @staticmethod
    @read
    def read_metrics(file_path: str) -> str:
        """
        Reads and returns metrics from a specified CSV file.
        Args:
            file_path (str): Path to the metrics file (CSV format).
        Returns:
            str: The requested metrics or an error message.
        """
```
(`base.py:143-154`)

```python
    @staticmethod
    @read
    def get_traces(namespace: str, duration: int = 5) -> str:
        """
        Collects trace data from the service using Jaeger.
        Args:
            namespace (str): The namespace in which the service is running.
            duration (int): The number of minutes from now to start collecting traces until now.
        Returns:
            str: Path to the directory where traces are saved.
        """
```
(`base.py:166-178`)

```python
    @staticmethod
    @read
    def read_traces(file_path: str) -> str:
        """
        Reads and returns traces from a specified CSV file.
        Args:
            file_path (str): Path to the traces file (CSV format).
        Returns:
            str: The requested traces or an error message.
        """
```
(`base.py:193-205`)

Per-task `submit` signatures:

```python
# aiopslab/orchestrator/actions/detection.py:16-29
    @staticmethod
    @action
    def submit(has_anomaly: str) -> SubmissionStatus:
        """
        Submit if anomalies are detected to the orchestrator for evaluation.
        Args:
            has_anomaly (str): "Yes" if anomalies are detected, "No" otherwise.
        Returns:
            SubmissionStatus: The status of the submission.
        """
        # TODO: check if anomalies are in the correct format
        return SubmissionStatus.VALID_SUBMISSION
```

```python
# aiopslab/orchestrator/actions/localization.py:16-28
    def submit(faulty_components: list[str]) -> SubmissionStatus:
        """
        Submit the detected faulty components to the orchestrator for evaluation.
        Args:
            faulty_components (list[str]): List of faulty components (i.e., service names).
        """
```

```python
# aiopslab/orchestrator/actions/analysis.py:16-28
    def submit(analysis: dict[str, str]) -> SubmissionStatus:
        """Submit the analysis solution to the orchestrator for evaluation.
        Args:
            analysis (dict[str]): A dictionary with two keys: 'system_level' and 'fault_type'.
        """
```

```python
# aiopslab/orchestrator/actions/mitigation.py:16-30
    def submit() -> SubmissionStatus:
        """
        Submit once your mitigation solution is complete and ready to be evaluated.
        Args:
            None
        """
        # for mitigation task, the submission is valid if the solution is submitted
        # NOTE: this does not mean the solution is correct!
        return SubmissionStatus.VALID_SUBMISSION
```

### 8.3 Action parsing — a Python-call DSL inside a markdown fence

**Not** OpenAI function-calling / JSON. `aiopslab/orchestrator/parser.py:16-55`:

```python
    def validate(self, response: str):
        actions = re.findall(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        if len(actions) != 1:
            raise ResponseParsingError("""
Format validation failure. Only have one pair of three ticks in your block and check the ticks. 
...
            """)

    def parse(self, response: str) -> dict:
        self.validate(response)
        code_block = self.extract_codeblock(response)
        context = self.extract_context(response)
        api_name = self.parse_api_name(code_block)
        args, kwargs = self.parse_args(
            code_block, is_shell_command=api_name == "exec_shell"
        )
        return {"api_name": api_name, "args": args, "kwargs": kwargs, "context": context}
```

- `parse_api_name` = everything before the first `(` (`parser.py:87-103`).
- Arguments are parsed by **building a synthetic call and running `ast.parse`**
  (`parser.py:146-169`): `parsed = ast.parse(f"func({args_str})")`, then walking
  `ast.Constant / List / Tuple / Dict / keywords`. Supports positional args and kwargs.
- `exec_shell` gets a **special string path** (`parser.py:128-143`): the command must be a
  quoted string, `command=` prefix is stripped, and `\"`/`\'` are unescaped; otherwise
  `ResponseParsingError("Error when parsing response: commands must be quoted strings")`.
- Prose outside the fence is captured as `context` (`parser.py:72-85`) but is **discarded** —
  `ask_env` never reads `resp["context"]`.

Dispatch is by `getattr` on the task's actions object (`tasks/detection.py:67-73`):

```python
    def perform_action(self, action_name, *args, **kwargs):
        action_method = getattr(self.actions, action_name, None)

        if action_method is not None and callable(action_method):
            return action_method(*args, **kwargs)
        else:
            raise InvalidActionError(action_name)
```

### 8.4 Where the shell actually runs

`aiopslab/service/shell.py:19-38`:

```python
    @staticmethod
    def exec(command: str, input_data=None, cwd=None, timeout=30):
        """Execute a shell command on localhost, via SSH, or inside kind's control-plane container."""
        k8s_host = config.get("k8s_host", "localhost")  # Default to localhost
        
        if k8s_host == "kind":
            return Shell.docker_exec("kind-control-plane", command, timeout=timeout)

        elif k8s_host == "localhost":
            ...
            return Shell.local_exec(command, input_data, cwd, timeout=timeout)

        else:
            k8s_user = config.get("k8s_user")
            ssh_key_path = config.get("ssh_key_path", "~/.ssh/id_rsa")
            return Shell.ssh_exec(k8s_host, k8s_user, ssh_key_path, command, timeout=timeout)
```

Three backends: `docker exec` into the kind control-plane, raw `subprocess` on localhost (with a
commented-out safety warning at `shell.py:28-32`), or Paramiko SSH. Default timeout 30 s.

### 8.5 Reference agent clients

`clients/registry.py:14-21`:

```python
        self.AGENT_REGISTRY = {
            "gpt": GPTAgent,
            "qwen": QwenAgent,
            "deepseek": DeepSeekAgent,
            "vllm": vLLMAgent,
            "openrouter": OpenRouterAgent,
            "generic": GenericOpenAIAgent,
        }
```

Files present in `clients/`: `gpt.py`, `gpt_azure_identity.py`, `qwen.py`, `deepseek.py`, `llama.py`,
`vllm.py`, `openrouter.py`, `generic_openai.py`, `react.py`, `flash.py`, `client.py`,
`utils/llm.py`, `utils/templates.py`. **`react.py` and `flash.py` are NOT in the registry** — they
are standalone scripts.

Agent interface (`README.md:224-232`): a class with `async def get_action(self, state: str) -> str`;
the clients additionally implement `init_context(problem_desc, instructions, apis)`.

The clients split the API dict into three buckets and render them into a prompt —
`clients/react.py:66-81`:

```python
        self.shell_api = self._filter_dict(apis, lambda k, _: "exec_shell" in k)
        self.submit_api = self._filter_dict(apis, lambda k, _: "submit" in k)
        self.telemetry_apis = self._filter_dict(
            apis, lambda k, _: "exec_shell" not in k and "submit" not in k
        )
        ...
        self.system_message = DOCS.format(
            prob_desc=problem_desc,
            telemetry_apis=stringify_apis(self.telemetry_apis),
            shell_api=stringify_apis(self.shell_api),
            submit_api=stringify_apis(self.submit_api),
        )
```

Templates — `clients/utils/templates.py:8-67` — three variants: `DOCS` (all APIs, ReAct-style
`Thought:`/`Action:`), `DOCS_SHELL_ONLY` (used by `GPTAgent`, `clients/gpt.py:74-78` — the baseline
GPT agent is **shell-only, no telemetry APIs**), and `AUTOGEN_DOCS` (multi-agent, "Do not execute
commands").

ReAct's extra per-turn nudge — `clients/react.py:18-21`:

```python
RESP_INSTR = """DO NOT REPEAT ACTIONS! Respond with:
Thought: <your thought on the previous output>
Action: <your action towards mitigating>
"""
```

All clients trim history to 120 000 tokens (`gpt.py:29`, `react.py:29`) or 90 000 (`flash.py:24`)
using `tiktoken` for `gpt-4`.

### 8.6 Service interface / MCP

**There is no MCP server.** There is a FastAPI HTTP service — `service.py`:

- `GET /problems` → `ProblemRegistry().get_problem_ids()` (`service.py:71-77`)
- `GET /agents` → `AgentRegistry().get_agent_ids()` (`service.py:80-86`)
- `GET /health` (`service.py:89-94`)
- `POST /simulate` with `SimulationRequest{problem_id, agent_name, max_steps, model,
  repetition_penalty, temperature, top_p, max_tokens}` (`service.py:39-59`), returning
  `SimulationResponse{agent, session_id, problem_id, start_time, end_time, trace, results}`
  (`service.py:61-68`). Default `max_steps` when omitted is **10** (`service.py:141`).

Entrypoint reads `SERVICE_HOST` / `SERVICE_PORT` (default 1818) / `SERVICE_WORKERS`
(`service.py:171-179`).

There are also two human interfaces: `cli.py` (generic REPL, `start <problem_id>`,
`max_steps=30`, `cli.py:137`) and `assessment.py` (an onboarding assessment hard-wired to
`redeploy_without_PV-mitigation-1`, `assessment.py:80`, driven by
`aiopslab/onboarding_evaluator.py`'s `Evaluator` class which loops until `success == True` rather
than for a fixed step budget, `onboarding_evaluator.py:156-186`).

---

## 9. Fault catalogue (full enumeration)

`aiopslab/generators/fault/` contents:

```
__init__.py  base.py  helpers.py
inject_app.py  inject_hw.py  inject_noop.py  inject_operator.py
inject_os.py   inject_otel.py inject_symp.py  inject_virtual.py
bpf_injector/  chaos-yaml/  script/
```

### 9.1 `base.py` — `FaultInjector` (the dispatcher)

`aiopslab/generators/fault/base.py:13-70`. Not an ABC; it provides name-based dispatch:

```python
    def _inject(
        self, fault_type: str, microservices: list[str] = None, duration: str = None
    ):
        if duration:
            self._invoke_method("inject", fault_type, microservices, duration)
        elif microservices:
            self._invoke_method("inject", fault_type, microservices)
        else:
            self._invoke_method("inject", fault_type)
        time.sleep(6)

    def _recover(
        self,
        fault_type: str,
        microservices: list[str] = None,
    ):
        if microservices and fault_type:
            self._invoke_method("recover", fault_type, microservices)
        elif fault_type:
            self._invoke_method("recover", fault_type)

    def _invoke_method(self, action_prefix, *args):
        """helper: injects/recovers faults based on name"""
        method_name = f"{action_prefix}_{args[0]}"
        method = getattr(self, method_name, None)
        if method:
            method(*args[1:])
        else:
            print(f"Unknown fault type: {args[0]}")
```

**This is the naming convention that defines the whole catalogue: `inject_<fault_type>` /
`recover_<fault_type>`.** A typo in `fault_type` silently prints "Unknown fault type" and injects
nothing. `inject_fault(...)` at `base.py:18-40` is marked `# Deprecated method`.

### 9.2 `helpers.py` — process-name tables for OS-level injection

`aiopslab/generators/fault/helpers.py:1-114`. No faults; provides `get_pids_by_name` /
`get_pids_by_name_contain` and hard-coded 15-char-truncated process-name lists:

- `sn_svc_process_names` (11 SocialNetwork services: `ComposePostServ`, `HomeTimelineSer`,
  `MediaService`, `PostStorageServ`, `SocialGraphServ`, `TextService`, `UserService`,
  `UrlShortenServi`, `UserMentionServ`, `UserTimelineSer`, `UniqueIdService`) — `helpers.py:4-16`
- `sn_mongod_process_names`, `sn_redis_process_names`, `sn_memcached_process_names` —
  `helpers.py:19-25`
- `hr_svc_process_names` (9 HotelReservation services: `geo`, `frontend`, `consul`, `profile`,
  `rate`, `recommendation`, `reservation`, `search`, `user`) — `helpers.py:28-38`
- `hr_mongod_process_names`, `hr_memcached_process_names` — `helpers.py:41-44`

### 9.3 `inject_app.py` — `ApplicationFaultInjector` (application layer)

`aiopslab/generators/fault/inject_app.py:13`. Section header at `:30` reads
`############# FAULT LIBRARY ################`. Four faults, numbered A.1–A.4 in the source:

| ID | `inject_` / `recover_` pair | What it does |
|---|---|---|
| **A.1** | `inject_revoke_auth` / `recover_revoke_auth` (`:32-95`) | Execs `revoke-admin-{rate,geo}-mongo.sh` inside the MongoDB pod to `db.revokeRolesFromUser('admin', [{role:'readWrite', db:'geo-db'}])`, then deletes the *dependent service* pod to force the error to surface. Recovery runs `revoke-mitigate-admin-*-mongo.sh`. Targets `mongodb-rate`, `mongodb-geo`. |
| **A.2** | `inject_storage_user_unregistered` / `recover_storage_user_unregistered` (`:97-147`) | Execs `remove-admin-mongo.sh` → `db.dropUser('admin')`, i.e. the app's DB user no longer exists. Recovery re-creates via `remove-mitigate-admin-{rate,geo}-mongo.sh`. |
| **A.3** | `inject_misconfig_app` / `recover_misconfig_app` (`:150-173`) | Swaps the container image of the `geo` service to a deliberately buggy build: `container.image = "yinfangchen/geo:app3"`; recovery restores `"yinfangchen/hotelreservation:latest"`. Docstring: *"NOTE: currently only the geo microservice has a buggy image."* |
| **A.4** | `inject_auth_miss_mongodb` / `recover_auth_miss_mongodb` (`:176-260`) | `helm upgrade` the socialnetwork chart with `url-shorten-mongodb.tls.mode=requireTLS` (+ cert paths) so the app can no longer connect; recovery sets `tls.mode=disabled`. Docstring: *"Inject a fault to require TLS for MongoDB, breaking app connections."* |

Supporting shell scripts (`aiopslab/generators/fault/script/`, mounted as ConfigMaps by
`apps/hotelres.py:27-65`): `k8s-geo-mongo.sh`, `k8s-rate-mongo.sh`, `remove-admin-mongo.sh`,
`remove-mitigate-admin-geo-mongo.sh`, `remove-mitigate-admin-rate-mongo.sh`,
`revoke-admin-geo-mongo.sh`, `revoke-admin-rate-mongo.sh`,
`revoke-mitigate-admin-geo-mongo.sh`, `revoke-mitigate-admin-rate-mongo.sh`. Example
(`script/revoke-admin-geo-mongo.sh`):

```bash
mongo admin -u $ADMIN_USER -p $ADMIN_PWD --authenticationDatabase admin \
     --eval "db.revokeRolesFromUser('$ADMIN_USER', [{role: 'readWrite', db: '$TARGET_DB'}]);"
```

Helper: `delete_service_pods()` (`inject_app.py:23-28`) — kills dependent pods so the fault
manifests. Mapping table `mongo_service_pod_map` (`inject_app.py:17-21`):
`{"mongodb-rate": "rate", "mongodb-geo": "geo", "url-shorten-mongodb": "url-shorten-service"}`.

### 9.4 `inject_virtual.py` — `VirtualizationFaultInjector` (K8s / Docker layer)

`aiopslab/generators/fault/inject_virtual.py:15`. Section header `FAULT LIBRARY` at `:29`. **Eight**
faults (source numbering skips V.2):

| ID | `inject_` / `recover_` pair | What it injects |
|---|---|---|
| **V.1** | `inject_misconfig_k8s` / `recover_misconfig_k8s` (`:32-53`) | Patches the Service so `targetPort` 9090 → **9999** (traffic goes nowhere). Recovery patches 9999 → 9090. Comment: *"Misconfigure service port in Kubernetes - Misconfig"* |
| — | *(V.2 absent from source)* | |
| **V.3** | `inject_scale_pods_to_zero` / `recover_scale_pods_to_zero` (`:56-73`) | `kubectl scale deployment <svc> --replicas=0`; recovery `--replicas=1`. Comment tags it *"Deploy/Operation"* |
| **V.4** | `inject_assign_to_non_existent_node` / `recover_assign_to_non_existent_node` (`:76-108`) | Rewrites the Deployment with `nodeSelector: {kubernetes.io/hostname: "extra-node"}` (a node that doesn't exist) → pods stay Pending. Recovery deletes the `nodeSelector`. Tagged *"Dependency"* |
| **V.5** | `inject_redeploy_without_pv` / `recover_redepoly_without_pv` (`:111-121`) | Deletes the namespace **without** deleting the PVs, sleeps 15 s, then redeploys → PVCs cannot bind to the orphaned Released PVs. Only for HotelReservation. |
| **V.6** | `inject_wrong_bin_usage` / `recover_wrong_bin_usage` (`:125-170`) | Rewrites the Deployment `command` from `["profile"]` to `["geo"]` — the pod runs the *wrong binary* while looking healthy at the container level. Recovery restores `["profile"]`. |
| — | `inject_container_stop` / `recover_container_stop` (`:172-185`) | Docker: `self.docker.get_container(service).stop()` (+15 s propagation sleep); recovery `.start()`. Used by the Flower node-stop problem. |
| — | `inject_model_misconfig` / `recover_model_misconfig` (`:187-198`) | Docker exec `sed -i '24s/84/80/' /app/.flwr/apps/*/task.py` inside a Flower client — changes an ML layer/dimension constant from 84 to 80, breaking training. Recovery is the inverse sed. |

Helpers (`:200-264`): `_wait_for_pods_ready` (unused), `_modify_target_port_config`,
`_get_values_yaml`, `_enable_tls`, `_apply_modified_yaml`, `_get_deployment_yaml`,
`_change_node_selector`, `_write_yaml_to_file`, plus `delete_service_pods` (`:22-27`).

### 9.5 `inject_symp.py` — `SymptomFaultInjector` (Chaos Mesh)

`aiopslab/generators/fault/inject_symp.py:14`. Installs Chaos Mesh **v2.6.2** by Helm into the
`chaos-mesh` namespace on construction (`:19-47`), auto-detecting docker vs containerd runtime and
adding `--set chaosDaemon.runtime=containerd --set chaosDaemon.socketPath=...` when needed. Every
fault writes `/tmp/<experiment_name>.yaml` and applies it (`:49-61`).

| `inject_` / `recover_` pair | Chaos kind / action | Details |
|---|---|---|
| `inject_pod_failure` / `recover_pod_failure` (`:66-84`, `:63-64`) | `PodChaos` / `pod-failure` | mode `one`, duration `200s`, selector `io.kompose.service` |
| `inject_network_loss` / `recover_network_loss` (`:89-109`, `:86-87`) | `NetworkChaos` / `loss` | `loss: 99`, `correlation: 100`, duration `200s` |
| `inject_container_kill` / `recover_container_kill` (`:111-133`) | `PodChaos` / `container-kill` | duration `200s`, explicit `containerNames` |
| `inject_network_delay` / `recover_network_delay` (`:135-169`) | `NetworkChaos` / `delay` | `latency: "10s"`, `jitter: "0ms"`, `correlation: 100`, duration `200s` |
| `inject_pod_kill` / `recover_pod_kill` (`:171-201`) | `PodChaos` / **`pod-failure`** | Deliberately uses `pod-failure` not `pod-kill`; docstring: *"The 'pod-kill' action forcefully deletes pods, causing Kubernetes controllers (Deployment/ReplicaSet) to immediately recreate them. The 'pod-failure' action makes pods unavailable for the specified duration without deletion"* |
| `inject_kernel_fault` / `recover_kernel_fault` (`:206-229`) | `KernelChaos` | `failKernRequest.callchain = [{funcname: "__x64_sys_mount"}]`, `failtype: 0`. **Known-broken** (see §7) |

Static YAML templates mirroring these live in `aiopslab/generators/fault/chaos-yaml/`:
`container-kill.yaml`, `kernal-faults.yaml`, `network-delay.yaml`, `network-loss.yaml`,
`pod-failure.yaml`, `pod-kill.yaml` — reference artifacts, not loaded by the injector (which builds
dicts inline).

### 9.6 `inject_otel.py` — `OtelFaultInjector` (feature-flag faults, Astronomy Shop)

`aiopslab/generators/fault/inject_otel.py:7`. **Does not follow the `inject_<type>` convention** —
it exposes `inject_fault(feature_flag)` / `recover_fault(feature_flag)` (`:13`, `:54`) which patch
the `flagd-config` ConfigMap's `demo.flagd.json` and `kubectl rollout restart deployment flagd`:

```python
        if feature_flag in flagd_data["flags"]:
            if feature_flag == "paymentFailure":
                flagd_data["flags"][feature_flag]["defaultVariant"] = "100%"
            elif feature_flag == "imageSlowLoad":
                flagd_data["flags"][feature_flag]["defaultVariant"] = "10sec"
            else:
                flagd_data["flags"][feature_flag]["defaultVariant"] = "on"
```
(`inject_otel.py:31-37`; recovery sets `"off"` at `:73`.)

**11 feature flags are used by registered problems** (grep over `problems/`):

| Flag | Problem dir | Faulty service |
|---|---|---|
| `adFailure` | `ad_service_failure/ad_service_failure.py:27` | `ad` |
| `adHighCpu` | `ad_service_high_cpu/ad_service_high_cpu.py:27` | `ad` |
| `adManualGc` | `ad_service_manual_gc/ad_service_manual_gc.py:27` | `ad` |
| `cartFailure` | `cart_service_failure/cart_service_failure.py:27` | `cart` |
| `imageSlowLoad` | `image_slow_load/image_slow_load.py:27` | `frontend` |
| `kafkaQueueProblems` | `kafka_queue_problems/kafka_queue_problems.py:27` | `kafka` |
| `loadGeneratorFloodHomepage` | `loadgenerator_flood_homepage/loadgenerator_flood_homepage.py:28` | `frontend` |
| `paymentFailure` | `payment_service_failure/payment_service_failure.py:27` | `payment` |
| `paymentUnreachable` | `payment_service_unreachable/payment_service_unreachable.py:27` | `checkout` |
| `productCatalogFailure` | `product_catalog_failure/product_catalog_failure.py:27` | `product-catalog` |
| `recommendationCacheFailure` | `recommendation_service_cache_failure/recommendation_service_cache_failure.py:27` | `recommendation` |

### 9.7 `inject_os.py` — `OSFaultInjector` (OS layer, eBPF)

`aiopslab/generators/fault/inject_os.py:21`.

| Method | Status |
|---|---|
| `kernel_bug()` (O.1) | `return NotImplementedError` (`:26-27`) — a stub, and note it *returns* rather than raises |
| `inject_disk_woreout()` (O.2) / `recover_disk_woreout()` (`:30-77`) | Finds `mongod` PIDs via `get_pids_by_name`, then runs `sudo generators/fault/bpf_injector/err_inject write -5 <pids...>` — an eBPF syscall-error injector that makes every `write(2)` return `EIO`. Recovery is `sudo rm -rf /sys/fs/bpf/err_inject`. |

The injector binary must be compiled from `aiopslab/generators/fault/bpf_injector/`
(`err_inject.c`, `err_inject.bpf.c`, `Makefile`, `README.md`) against libbpf.

### 9.8 `inject_hw.py` — `HWFaultInjector` (hardware layer)

`aiopslab/generators/fault/inject_hw.py:13-24`. **Entirely a stub** — 24 lines total:

```python
class HWFaultInjector(FaultInjector):
    def _inject(self, microservices: list[str], fault_type: str):
        return NotImplementedError

    ############# FAULT LIBRARY ################

    # H.1
    def hw_bug(self):
        return NotImplementedError
```

No hardware faults exist despite `Hardware` being an offered `system_level` answer in the analysis
task.

### 9.9 `inject_operator.py` — `K8SOperatorFaultInjector` (K8s operator misoperations, TiDB)

`aiopslab/generators/fault/inject_operator.py:7`. Applies a malformed `TidbCluster` CR
(`pingcap.com/v1alpha1`) to namespace `tidb-cluster`; recovery deletes the applied YAML
(`:13-26`, `:232-233`). Five faults:

| `inject_` / `recover_` pair | CR name | Bad field |
|---|---|---|
| `inject_overload_replicas` / `recover_overload_replicas` (`:28-66`) | `overload-tidbcluster` | `tidb.replicas: 100000  # Intentional misconfiguration` |
| `inject_invalid_affinity_toleration` / `recover_invalid_affinity_toleration` (`:68-113`) | `affinity-toleration-fault` | `effect: "TAKE_SOME_EFFECT"  # Buggy: invalid toleration effect` |
| `inject_security_context_fault` / `recover_security_context_fault` (`:115-152`) | `security-context-fault` | `podSecurityContext: {"runAsUser": -1}  # invalid runAsUser value` |
| `inject_wrong_update_strategy` / `recover_wrong_update_strategy` (`:154-191`) | `deployment-update-strategy-fault` | `statefulSetUpdateStrategy: "SomeStrategyForUpdata"  # invalid update strategy` |
| `inject_non_existent_storage` / `recover_non_existent_storage` (`:193-230`) | `non-existent-storage-fault` | `pd.storageClassName: "ThisIsAStorageClass"  # non-existent storage class` |

Observed symptom documented at `problems/operator_misoperation/overload_replicas.py:1-5`:
*"Readiness probe failed: dial tcp 10.244.0.27:4000: connect: connection refused ... Only a few pods
(e.g., 4 out of 100,000 replicas requested) are created successfully."*

**All five are commented out of the registry** (`registry.py:207-216`).

### 9.10 `inject_noop.py` — `NoopFaultInjector` (control condition)

`aiopslab/generators/fault/inject_noop.py:5-15`:

```python
class NoopFaultInjector(FaultInjector):
    def __init__(self, namespace: str):
        super().__init__(namespace)
        self.namespace = namespace
        self.kubectl = KubeCtl()

    def inject_no_op(self, _, __):
        pass

    def recover_no_op(self):
        pass
```

Backs the three `noop_detection_*` problems — the only ones whose ground truth is `"No"`.

### 9.11 Catalogue summary

**8 injector classes; 22 implemented `inject_*`/`recover_*` pairs + 11 OTel feature flags + 2 stubs.**

| Injector | File | Live pairs |
|---|---|---|
| `FaultInjector` (base/dispatcher) | `base.py` | — |
| `ApplicationFaultInjector` | `inject_app.py` | 4 (revoke_auth, storage_user_unregistered, misconfig_app, auth_miss_mongodb) |
| `VirtualizationFaultInjector` | `inject_virtual.py` | 8 (misconfig_k8s, scale_pods_to_zero, assign_to_non_existent_node, redeploy_without_pv, wrong_bin_usage, container_stop, model_misconfig) — 7 pairs + `delete_service_pods` |
| `SymptomFaultInjector` (Chaos Mesh 2.6.2) | `inject_symp.py` | 6 (pod_failure, network_loss, container_kill, network_delay, pod_kill, kernel_fault[broken]) |
| `OtelFaultInjector` | `inject_otel.py` | 1 generic pair × 11 flags |
| `OSFaultInjector` | `inject_os.py` | 1 live (disk_woreout) + 1 stub (kernel_bug) |
| `K8SOperatorFaultInjector` | `inject_operator.py` | 5 (all registry-disabled) |
| `HWFaultInjector` | `inject_hw.py` | 0 (stub) |
| `NoopFaultInjector` | `inject_noop.py` | 1 (no-op) |

---

## 10. Problem registry (full enumeration)

All 89 live IDs from `aiopslab/orchestrator/problems/registry.py:36-220`, grouped by fault family
with exact counts. Line numbers are the registry key's line.

**K8s target-port misconfig — SocialNetwork — 12 problems** (`registry.py:38-73`)
Fault: `misconfig_k8s` (targetPort 9090→9999). Variants by faulty service: `-1` = `user-service`,
`-2` = `text-service`, `-3` = `post-storage-service`.
```
k8s_target_port-misconfig-detection-1     :38     k8s_target_port-misconfig-detection-2     :50
k8s_target_port-misconfig-localization-1  :41     k8s_target_port-misconfig-localization-2  :53
k8s_target_port-misconfig-analysis-1      :44     k8s_target_port-misconfig-analysis-2      :56
k8s_target_port-misconfig-mitigation-1    :47     k8s_target_port-misconfig-mitigation-2    :59
k8s_target_port-misconfig-detection-3     :62     k8s_target_port-misconfig-analysis-3      :68
k8s_target_port-misconfig-localization-3  :65     k8s_target_port-misconfig-mitigation-3    :71
```

**MongoDB auth missing (TLS required) — SocialNetwork — 4 problems** (`registry.py:75-78`)
Fault: `auth_miss_mongodb`; faulty service `url-shorten-mongodb`.
```
auth_miss_mongodb-detection-1 :75   auth_miss_mongodb-localization-1 :76
auth_miss_mongodb-analysis-1  :77   auth_miss_mongodb-mitigation-1   :78
```

**MongoDB revoke-auth — HotelReservation — 8 problems** (`registry.py:80-103`)
Fault: `revoke_auth`. `-1` = `mongodb-geo`, `-2` = `mongodb-rate`.
```
revoke_auth_mongodb-detection-1    :80    revoke_auth_mongodb-detection-2    :92
revoke_auth_mongodb-localization-1 :83    revoke_auth_mongodb-localization-2 :95
revoke_auth_mongodb-analysis-1     :86    revoke_auth_mongodb-analysis-2     :98
revoke_auth_mongodb-mitigation-1   :89    revoke_auth_mongodb-mitigation-2   :101
```

**MongoDB user unregistered (dropUser) — HotelReservation — 8 problems** (`registry.py:105-128`)
Fault: `storage_user_unregistered`. `-1` = `mongodb-geo`, `-2` = `mongodb-rate`.
```
user_unregistered_mongodb-detection-1    :105   user_unregistered_mongodb-detection-2    :117
user_unregistered_mongodb-localization-1 :108   user_unregistered_mongodb-localization-2 :120
user_unregistered_mongodb-analysis-1     :111   user_unregistered_mongodb-analysis-2     :123
user_unregistered_mongodb-mitigation-1   :114   user_unregistered_mongodb-mitigation-2   :126
```

**App misconfig (buggy image) — HotelReservation — 4 problems** (`registry.py:130-133`)
Fault: `misconfig_app`; faulty service `geo`.
```
misconfig_app_hotel_res-detection-1 :130   misconfig_app_hotel_res-localization-1 :131
misconfig_app_hotel_res-analysis-1  :132   misconfig_app_hotel_res-mitigation-1   :133
```

**Scale pods to zero — SocialNetwork — 4 problems** (`registry.py:135-138`)
Fault: `scale_pods_to_zero`; faulty service `user-service`.
```
scale_pod_zero_social_net-detection-1 :135   scale_pod_zero_social_net-localization-1 :136
scale_pod_zero_social_net-analysis-1  :137   scale_pod_zero_social_net-mitigation-1   :138
```

**Assign to non-existent node — SocialNetwork — 4 problems** (`registry.py:140-143`)
Fault: `assign_to_non_existent_node`; faulty service `user-service`.
```
assign_to_non_existent_node_social_net-detection-1    :140
assign_to_non_existent_node_social_net-localization-1 :141
assign_to_non_existent_node_social_net-analysis-1     :142
assign_to_non_existent_node_social_net-mitigation-1   :143
```

**Chaos Mesh container kill — HotelReservation — 2 problems** (`registry.py:145-146`)
Faulty service `geo`, container `hotel-reserv-geo` (`container_kill/container_kill.py:23-24`).
Note: **no `-1` suffix** on these IDs.
```
container_kill-detection :145   container_kill-localization :146
```

**Pod failure — HotelReservation — 2 problems** (`registry.py:148-149`) — faulty service `user`.
```
pod_failure_hotel_res-detection-1 :148   pod_failure_hotel_res-localization-1 :149
```

**Pod kill — HotelReservation — 2 problems** (`registry.py:151-152`) — faulty service `user`,
duration `100s`.
```
pod_kill_hotel_res-detection-1 :151   pod_kill_hotel_res-localization-1 :152
```

**Network loss — HotelReservation — 2 problems** (`registry.py:154-155`) — faulty service `user`.
```
network_loss_hotel_res-detection-1 :154   network_loss_hotel_res-localization-1 :155
```

**Network delay — HotelReservation — 2 problems** (`registry.py:157-158`) — faulty service `user`.
```
network_delay_hotel_res-detection-1 :157   network_delay_hotel_res-localization-1 :158
```

**No-op controls (ground truth = "No") — 3 problems** (`registry.py:160-164`)
```
noop_detection_hotel_reservation-1 :160   (app_name="hotel")
noop_detection_social_network-1    :163   (app_name="social")
noop_detection_astronomy_shop-1    :164   (app_name="astronomy_shop")
```

**Astronomy Shop / OpenTelemetry feature-flag faults — 23 problems** (`registry.py:173-195`)
```
astronomy_shop_ad_service_failure-detection-1                    :173
astronomy_shop_ad_service_failure-localization-1                 :174
astronomy_shop_ad_service_high_cpu-detection-1                   :175
astronomy_shop_ad_service_high_cpu-localization-1                :176
astronomy_shop_ad_service_manual_gc-detection-1                  :177
astronomy_shop_ad_service_manual_gc-localization-1               :178
astronomy_shop_cart_service_failure-detection-1                  :179
astronomy_shop_cart_service_failure-localization-1               :180
astronomy_shop_image_slow_load-detection-1                       :181
astronomy_shop_image_slow_load-localization-1                    :182
astronomy_shop_kafka_queue_problems-detection-1                  :183
astronomy_shop_kafka_queue_problems-localization-1               :184
astronomy_shop_kafka_queue_problems-mitigation-1                 :185   <- only OTel mitigation
astronomy_shop_loadgenerator_flood_homepage-detection-1          :186
astronomy_shop_loadgenerator_flood_homepage-localization-1       :187
astronomy_shop_payment_service_failure-detection-1               :188
astronomy_shop_payment_service_failure-localization-1            :189
astronomy_shop_payment_service_unreachable-detection-1           :190
astronomy_shop_payment_service_unreachable-localization-1        :191
astronomy_shop_product_catalog_service_failure-detection-1       :192
astronomy_shop_product_catalog_service_failure-localization-1    :193
astronomy_shop_recommendation_service_cache_failure-detection-1  :194
astronomy_shop_recommendation_service_cache_failure-localization-1 :195
```

**Redeploy without deleting PV — HotelReservation — 3 problems** (`registry.py:197-200`)
Localization variant is commented out at `:198`.
```
redeploy_without_PV-detection-1 :197   redeploy_without_PV-analysis-1 :199
redeploy_without_PV-mitigation-1 :200
```

**Wrong binary usage — HotelReservation — 4 problems** (`registry.py:202-205`)
Faulty service `profile` (runs the `geo` binary).
```
wrong_bin_usage-detection-1 :202   wrong_bin_usage-localization-1 :203
wrong_bin_usage-analysis-1  :204   wrong_bin_usage-mitigation-1   :205
```

**Flower (Docker deployment) — 2 problems** (`registry.py:218-219`)
```
flower_node_stop-detection       :218   (stops container `supernode-1`)
flower_model_misconfig-detection :219   (sed-patches `clientapp-1` model code)
```

These two are also listed in `DOCKER_REGISTRY` (`registry.py:221-224`), which makes
`get_problem_deployment()` return `"docker"` (`registry.py:245-248`) and causes the orchestrator to
**skip OpenEBS + Prometheus setup entirely** (`orchestrator.py:53-68`).

**Grand total: 12+4+8+8+4+4+4+2+2+2+2+2+3+23+3+4+2 = 89.**

**Commented-out (12 IDs):** `kernel_fault_hotel_reservation-{detection,localization}-1` (`:168-169`),
`disk_woreout-{detection,localization}-1` (`:170-171`),
`operator_{overload_replicas,non_existent_storage,invalid_affinity_toleration,security_context_fault,wrong_update_strategy}-{detection,localization}-1`
(`:207-216`), `redeploy_without_PV-localization-1` (`:198`).

**ID-format inconsistency:** `README.md`/`CLAUDE.md` state the format is
`<problem_type>-<task_type>-<variant>`, but `k8s_target_port-misconfig-detection-1` has an extra
hyphen inside the problem type, and `container_kill-detection`, `flower_node_stop-detection`,
`flower_model_misconfig-detection` have no variant suffix. Since `get_problem_ids(task_type)` does a
plain substring match (`registry.py:237`), all of these still filter correctly.

---

## 11. Notable quotes / raw excerpts

**On the whole framework** — `README.md:23`:
> AIOpsLab is a holistic framework to enable the design, development, and evaluation of autonomous
> AIOps agents that, additionally, serve the purpose of building reproducible, standardized,
> interoperable and scalable benchmarks. AIOpsLab can deploy microservice cloud environments, inject
> faults, generate workloads, and export telemetry data, while orchestrating these components and
> providing interfaces for interacting with and evaluating agents.

**The five components of a problem** — `README.md:311-317`:
> Each problem in AIOpsLab has 5 components:
> 1. *Application*: The application on which the problem is based.
> 2. *Task*: The AIOps task that the agent needs to perform. Currently we support: Detection,
>    Localization, Analysis, and Mitigation.
> 3. *Fault*: The fault being introduced in the application.
> 4. *Workload*: The workload that is generated for the application.
> 5. *Evaluator*: The evaluator that checks the agent's performance.

**Mitigation submission is not a correctness signal** —
`aiopslab/orchestrator/actions/mitigation.py:28-30`:
```python
        # for mitigation task, the submission is valid if the solution is submitted
        # NOTE: this does not mean the solution is correct!
        return SubmissionStatus.VALID_SUBMISSION
```

**The exec_shell blocklist is the entire sandbox** — `aiopslab/orchestrator/actions/base.py:93-99`:
```python
        BLOCK_LIST: dict[str, str] = {
            "kubectl edit": "Error: Cannot use `kubectl edit`. Use `kubectl patch` instead.",
            "edit svc": "Error: Cannot use `kubectl edit`. Use `kubectl patch` instead.",
            "kubectl port-forward": "Error: Cannot use `kubectl port-forward` because it is an interactive command.",
            "docker logs -f": "Error: Cannot use `docker logs -f`. Use `docker logs` instead.",
            "kubectl logs -f": "Error: Cannot use `kubectl logs -f`. Use `kubectl logs` instead.",
        }
```

**A tool was removed because it was too helpful** — `aiopslab/orchestrator/actions/base.py:216-220`:
```python
    @staticmethod
    # @read
    # NOTE: disabled for now, since seems like a cheat for code changes
    def get_microservice_repo_diff(start: int, end: int, token=None) -> list[dict]:
        pass
```

**Chaos Mesh `pod-kill` is not really pod-kill** — `aiopslab/generators/fault/inject_symp.py:174-179`:
```python
        Note: This uses 'pod-failure' action instead of 'pod-kill' to prevent Kubernetes from immediately
        recreating the pod. The 'pod-kill' action forcefully deletes pods, causing Kubernetes controllers
        (Deployment/ReplicaSet) to immediately recreate them. The 'pod-failure' action makes pods unavailable
        for the specified duration without deletion, allowing proper fault injection testing.
```

**Wrong-binary fault (a genuinely subtle one)** — `aiopslab/generators/fault/inject_virtual.py:130-137`:
```python
            # Modify the deployment YAML to use the 'geo' binary instead of the 'profile' binary
            containers = deployment_yaml["spec"]["template"]["spec"]["containers"]
            for container in containers:
                if "command" in container and "profile" in container["command"]:
                    print(
                        f"Changing binary for container {container['name']} from 'profile' to 'geo'."
                    )
                    container["command"] = ["geo"]  # Replace 'profile' with 'geo'
```

**Flower model misconfig is a one-character source edit inside a running container** —
`aiopslab/generators/fault/inject_virtual.py:190`:
```python
            command = f""" docker exec -it {service} sh -c "sed -i '24s/84/80/' /app/.flwr/apps/*/task.py" """
```

**Known-broken kernel fault** — `aiopslab/generators/fault/inject_symp.py:203-205`:
```python
    # IMPORTANT NOTE:
    # Kernel fault is not working and is a known bug in chaos-mesh 0> https://github.com/xlab-uiuc/agent-ops/pull/10#issuecomment-2468992285
    # This code is untested as we're waiting for a resolution to the bug to retry.
```

**No-op problems exist to catch false positives** —
`aiopslab/orchestrator/problems/no_op/no_op.py:1`:
```python
"""No operation problem for HotelReservation or SocialNetwork applications to test false positive."""
```

**Telemetry side-effect metrics are still a TODO** —
`aiopslab/orchestrator/evaluators/quantitative.py:69-71`:
```python
# TODO: once observability is setup, use metrics, traces, logs,
# and wrk2's logs to also observe the (side)-effects of agents' actions
# e.g., latency, throughput, etc.
```

**Invalid submission has no retry path** — `aiopslab/orchestrator/orchestrator.py:170-171`:
```python
                elif env_response == SubmissionStatus.INVALID_SUBMISSION:
                    raise ValueError("Invalid submission!")  # TODO (@manish): ask to retry?
```

**Cleanup is knowingly under-aggressive** — `aiopslab/orchestrator/orchestrator.py:201-205`:
```python
        # Beyond recovering from fault,
        # I feel sometimes it is safer to delete the whole namespace.
        # But this will take more time.
        # if not self.session.problem.sys_status_after_recovery():
        self.session.problem.app.cleanup()
```

**The DSL parser's error message (what an agent sees on a format miss)** —
`aiopslab/orchestrator/parser.py:19-32`:
```
Format validation failure. Only have one pair of three ticks in your block and check the ticks. 
Correct example 1:
I should run:
```
exec_shell("ls")
```

Correct example 2:
Check k8s info 
```
exec_shell("kubectl get services --all-namespaces")
```
```

**Ctrl-C is deferred so faults are never orphaned** —
`aiopslab/utils/critical_section.py:25-28`:
```python
    def signal_handler(self, signum, frame):
        """Handle SIGINT by just setting a flag to delay it."""
        self.signaled = True  # Flag that SIGINT occurred
        print("\nCtrl+C detected! But deferring the effect for consistency...")
```

**The CI smoke-test agent** — `tests/integration/smoke_test.py:29-37`:
```python
class DummyAgent:
    """Zero-cost agent for CI smoke testing — makes no LLM or API calls.

    For a no-op detection task the correct answer is always "No" (no fault was
    injected), so we submit that immediately on the first step.
    """

    async def get_action(self, observation: str) -> str:
        return '```\nsubmit("No")\n```'
```

**Onboarding assessment problem text (a human-facing variant, hard-wired to the PV problem)** —
`assessment.py:24-40`:
```
There's a problem in the kubernetes cluster in the test-hotel-reservation namespace.

The issue is that there are unmet PersistentVolumeClaims (PVCs) because of unbound persistent volumes.

You need to fix the issue and get all the pods into a ready state.

You have access to a shell, take whatever action you deem necessary to resolve the issue.

Once you believe the incident is resolved, run the `submit` command. If your solution is incorrect, it will tell you.
```

---

## Appendix — things explicitly ABSENT from this repo

- **No "agent-cloud interface" / "ACI" terminology anywhere.** A case-insensitive search for
  `agent-cloud`, `agent cloud interface`, and `\bACI\b` across all `*.py`, `*.md`, `*.yaml`, `*.yml`
  returns **zero hits**. The paper's ACI concept maps onto, but is never named in, the
  `Orchestrator` ↔ `ResponseParser` ↔ `TaskActions` triple
  (`aiopslab/orchestrator/orchestrator.py`, `aiopslab/orchestrator/parser.py`,
  `aiopslab/orchestrator/actions/base.py`). `README.md:20` shows an architecture diagram
  (`assets/images/aiopslab-arch-open-source.png`) but adds no ACI text.
- **No MCP server.** The remote interface is plain FastAPI (`service.py`).
- **No reported baseline numbers, leaderboard, or results tables** in any repo file.
- **No hardware-layer faults** (`inject_hw.py` is a stub) despite `Hardware` being an allowed answer.
- **No per-step or SLO-based metric** — only wall-clock TT*, steps, and token counts.
- **No environment-error vs model-error classification** in results; both surface as observation
  strings.
- **No max-steps/truncation flag** in the persisted session JSON.
- **No dependency graph, no alert payload, no incident description** given to the agent.
- **Loki telemetry client is dead code** (`aiopslab/service/telemetry/loki.py`, no importers).
- **Elasticsearch log pipeline (`observer/log_api.py`, `observer/filebeat/`, `observer/logstash/`)
  is offline-only** — not reachable from any agent action.
