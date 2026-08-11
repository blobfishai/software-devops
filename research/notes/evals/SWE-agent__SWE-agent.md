# SWE-agent/SWE-agent

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/evals/SWE-agent__SWE-agent/`

> All file paths below are **relative to that repo root** unless stated otherwise.
> Version pinned in the checkout: `__version__ = "1.1.0"` (`sweagent/__init__.py:15`); HEAD commit `3ea751c` ("fix: map multimodal subset to sb-cli's swe-bench-m (#1458)").
> Directory layout constants: `PACKAGE_DIR` / `REPO_ROOT` / `CONFIG_DIR` / `TOOLS_DIR` / `TRAJECTORY_DIR` at `sweagent/__init__.py:28-46` (all overridable via `SWE_AGENT_CONFIG_DIR`, `SWE_AGENT_TOOLS_DIR`, `SWE_AGENT_TRAJECTORY_DIR`).

**Framing.** SWE-agent is an *agent scaffold*, not a benchmark. It produces a `git diff` patch and a `.traj` file; grading is delegated elsewhere (SWE-bench / `sb-cli`). Its research value here is (a) the tool surface / Agent-Computer Interface, (b) how a "task instance" and "problem statement" are typed, (c) the exit-status + exception taxonomy that cleanly separates *environment failure* from *model failure*, and (d) the self-review / retry / chooser loop.

---

## 1. Task taxonomy (C1, C2, C3, C4)

### 1.1 What kinds of tasks does it run?

Task supply is abstracted behind `AbstractInstanceSource` (`sweagent/run/batch_instances.py:32-36`). The union of concrete sources is:

```python
BatchInstanceSourceConfig = (
    InstancesFromHuggingFace | InstancesFromFile | SWEBenchInstances | ExpertInstancesFromFile | SWESmithInstances
)
```
(`sweagent/run/batch_instances.py:447-449`)

| Source | Discriminator | Where | Notes |
|---|---|---|---|
| `SWEBenchInstances` | `swe_bench` | `sweagent/run/batch_instances.py:270-339` | The canonical benchmark path; 5 subsets (below) |
| `InstancesFromFile` | `file` | `sweagent/run/batch_instances.py:195-229` | JSON/YAML list of `SimpleBatchInstance` |
| `InstancesFromHuggingFace` | `huggingface` | `sweagent/run/batch_instances.py:232-267` | any HF dataset shaped like `SimpleBatchInstance` |
| `ExpertInstancesFromFile` | `expert_file` | `sweagent/run/batch_instances.py:342-368` | full `BatchInstance` objects, per-instance deployment config |
| `SWESmithInstances` | `swesmith` | `sweagent/run/batch_instances.py:371-444` | SWE-smith synthetic bugs; uses `SWESmithRepoConfig`, carries `FAIL_TO_PASS` in `extra_fields` |

**SWE-bench subsets** (`sweagent/run/batch_instances.py:273` and mapping at `:307-322`):

```python
subset: Literal["lite", "verified", "full", "multimodal", "multilingual"] = "lite"
...
dataset_mapping = {
    "full": "princeton-nlp/SWE-Bench",
    "verified": "princeton-nlp/SWE-Bench_Verified",
    "lite": "princeton-nlp/SWE-Bench_Lite",
    "multimodal": "princeton-nlp/SWE-Bench_Multimodal",
    "multilingual": "swe-bench/SWE-Bench_Multilingual",
}
```
`split: Literal["dev", "test"] = "dev"` (`sweagent/run/batch_instances.py:283`). Docker image is auto-derived when absent: `docker.io/swebench/sweb.eval.x86_64.{id}` with `__` → `_1776_` because "Docker doesn't allow double underscore" (`sweagent/run/batch_instances.py:176-180`). Platform forced to `linux/amd64` (`:329-330`).

**Non-SWE-bench task modes:**

- **Single GitHub issue URL** → `GithubIssue` problem statement + `GithubRepoConfig` (`sweagent/agent/problem_statement.py:128-154`, `sweagent/environment/repo.py:126-191`). This is the "hello world" mode; an `OpenPRHook` can then open a PR (`sweagent/run/hooks/open_pr.py:149-175`).
- **Local repo** → `LocalRepoConfig` (`sweagent/environment/repo.py:77-123`), refuses dirty working trees: `"Local git repository {self.path} is dirty. Please commit or stash changes."` (`:104-106`).
- **Free-text / file problem statement, no repo at all** → `TextProblemStatement` / `FileProblemStatement` / `EmptyProblemStatement`; `repo` is `None`-able (`sweagent/environment/swe_env.py:31-34`).
- **Coding challenges (LeetCode-style)** → `config/coding_challenge.yaml`; instructs "Write your solution in main.py" (`config/coding_challenge.yaml:47`). Docs at `docs/usage/coding_challenges.md`, `docs/usage/leetcode_example.md`.
- **SWE-bench Multimodal** → `SWEBenchMultimodalProblemStatement` downloads `issue_images` URLs, base64-inlines them as markdown (`sweagent/agent/problem_statement.py:157-282`); configs `config/default_mm_with_images.yaml`, `config/default_mm_no_images.yaml`.
- **Shell mode** (`sweagent sh`) → `ShellAgentConfig` (`sweagent/agent/agents.py:170-185`), config `config/exotic/default_shell.yaml`.
- **Human-in-the-loop** → `config/human/human.yaml`, `config/human/human_demo.yaml`, model `human` / `human_thought`.

### 1.2 EnIGMA (CTF / offensive cybersecurity) — the second taxonomy

**EnIGMA is NOT in this 1.x checkout.** It exists only on the `v0.7` branch:

> "[SWE-agent: EnIGMA][enigma] is a mode for solving offensive cybersecurity (capture the flag) challenges. EnIGMA achieves state-of-the-art results on multiple cybersecurity benchmarks... **Please use [SWE-agent 0.7](https://github.com/SWE-agent/SWE-agent/tree/v0.7) while we update EnIGMA for 1.0.**"
> — `README.md:65-67`

> "SWE-agent EnIGMA is currently only available for SWE-agent v0.7.0."
> — `docs/background/index.md:38-39`

Residue of EnIGMA still present in this tree:
- pytest marker: `"ctf: marks EnIGMA tests for using SWE-agent on capture the flag (CTF) challenges"` (`pyproject.toml:104`).
- Per-category CTF demonstrations: `trajectories/demonstrations/ctf/{crypto,forensics,misc,pwn,rev,web}` — one demonstration per CTF category, matching the paper's claim that "Specific demonstrations were built per each CTF category (cryptography, reverse-engineering, forensics, ...), to enhance the model ability to solve new tasks from the same category" (`docs/background/index.md:49`).
- Test fixtures `test_ctf_trajectories_path` / `ctf_data_path` (`tests/conftest.py:40-48`).
- A vestigial CTF-oriented blocklist escape hatch for the reverse-engineering tool `radare2`/`r2` — see §8.9.
- EnIGMA's key concepts named in docs: **Interactive Agent Tools (IATs)** — "enables our agent to use interactive tools such as a debugger, in a multitasking way such that the agent still has access to the main shell while using the debugger" — and a **Summarizer** for long context (`docs/background/index.md:45-47`).

### 1.3 Task length bounds (C2)

There is **no `max_steps` parameter**. The run loop is `while not step_output.done: step_output = self.step()` (`sweagent/agent/agents.py:1284-1286`). Length is bounded only by *cost*, *API-call count*, *context window*, and *wall-clock execution time*:

| Bound | Default | Where |
|---|---|---|
| `per_instance_cost_limit` | **3.0** (USD) | `sweagent/agent/models.py:73-76` |
| `total_cost_limit` | **0.0** (= disabled) | `sweagent/agent/models.py:77` |
| `per_instance_call_limit` | **0** (= disabled) | `sweagent/agent/models.py:78` |
| `max_input_tokens` | `None` → looked up from `litellm.model_cost`; `0` disables the check | `sweagent/agent/models.py:125-131`, enforced `:695-703` |
| `max_output_tokens` | `None` → `litellm.model_cost`; Claude 3.7/Sonnet-4 forced to **64000** unless `anthropic-beta: output-128k-2025-02-19` | `sweagent/agent/models.py:133-139`, `:604-620` |
| `max_requeries` (format-error retries) | **3** | `sweagent/agent/agents.py:158-161` |
| `execution_timeout` (per command) | **30** s | `sweagent/tools/tools.py:139-140` |
| `install_timeout` | **300** s | `sweagent/tools/tools.py:142-143` |
| `total_execution_timeout` | **1800** s | `sweagent/tools/tools.py:145-148` |
| `max_consecutive_execution_timeouts` | **3** | `sweagent/tools/tools.py:150-152` |
| `max_observation_length` | **100_000** chars | `sweagent/agent/agents.py:79-82` |

Note `total_execution_timeout` "Does not interrupt running commands, but will stop the agent for the next step" (`sweagent/tools/tools.py:147`), checked at the top of `forward()` (`sweagent/agent/agents.py:1018-1019`).

Real benchmark-run budgets observed in configs:
- `config/benchmarks/250526_anthropic_filemap_simple_review_sbl.yaml:88-90`: `per_instance_cost_limit: 5`, `per_instance_call_limit: 0`, `total_cost_limit: 1000.0`.
- `config/benchmarks/250212_sweagent_heavy_sbl.yaml:14-16`: `per_instance_cost_limit: 1.5`, `per_instance_call_limit: 75`, `total_cost_limit: 1000.0`, plus a retry loop with `cost_limit: 6.0`, `max_attempts: 10` (`:135-139`).
- `config/bash_only.yaml:214-217`: `per_instance_cost_limit: 3`, `per_instance_call_limit: 250`, `total_cost_limit: 1500.0`.

---

## 2. Task definition schema (C6)

### 2.1 `ProblemStatement` protocol

```python
class ProblemStatement(Protocol):
    """A problem statement for a task. Any class that implements this protocol
    can be used as a problem statement.
    """

    id: str

    def get_problem_statement(self) -> str: ...

    def get_problem_statement_for_env(self) -> str:
        """Used for setting environment variables in the container.

        By default, this is the same as get_problem_statement().
        """
        return self.get_problem_statement()

    def get_extra_fields(self) -> dict[str, Any]: ...
```
(`sweagent/agent/problem_statement.py:26-42`)

The `_for_env` split matters: the *env-facing* text is written into the container as `$PROBLEM_STATEMENT` (`sweagent/agent/agents.py:602`) and must be image-free; the *model-facing* text may contain base64 images.

### 2.2 The five concrete problem statements

```python
class EmptyProblemStatement(_BuiltinProblemStatementBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["empty"] = "empty"
    """Discriminator for (de)serialization/CLI. Do not change."""

    model_config = ConfigDict(extra="forbid")

    def get_problem_statement(self) -> str:
        return ""
```
(`sweagent/agent/problem_statement.py:57-65`)

```python
class TextProblemStatement(_BuiltinProblemStatementBase):
    text: str

    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    type: Literal["text"] = "text"
    """Discriminator for (de)serialization/CLI. Do not change."""

    id: str = None  # type: ignore

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement id to hash of text")
            self.id = hashlib.sha256(self.text.encode()).hexdigest()[:6]
```
(`sweagent/agent/problem_statement.py:68-98`)

```python
class FileProblemStatement(_BuiltinProblemStatementBase):
    path: Path
    ...
    type: Literal["text_file"] = "text_file"
    ...
    def get_problem_statement(self) -> str:
        return self.path.read_text()
```
(`sweagent/agent/problem_statement.py:101-126`)

```python
class GithubIssue(_BuiltinProblemStatementBase):
    github_url: str
    ...
    type: Literal["github"] = "github"
    ...
    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            logger.info("Setting problem statement based on github issue url")
            owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
            self.id = f"{owner}__{repo}-i{issue_number}"

    def get_problem_statement(self) -> str:
        owner, repo, issue_number = _parse_gh_issue_url(self.github_url)
        return _get_problem_statement_from_github_issue(owner, repo, issue_number, token=os.getenv("GITHUB_TOKEN"))
```
(`sweagent/agent/problem_statement.py:128-154`)

```python
class SWEBenchMultimodalProblemStatement(_BuiltinProblemStatementBase):
    text: str

    issue_images: list[str] = Field(default_factory=list)
    """List of image asset URLs.
    """

    disable_image_processing: bool = False
    """If True, skip image downloading and processing, treating this as a text-only problem statement.
    """
    ...
    type: Literal["swe_bench_multimodal"] = "swe_bench_multimodal"
    ...
    def get_problem_statement_for_env(self) -> str:
        """Return the problem statement without images.

        Images are not supported in the environment.
        """
        return self.text

    def get_problem_statement(self) -> str:
        if self.disable_image_processing:
            logger.info("Image processing disabled, returning text-only problem statement")
            return self.text
        ...
        processed_text = self.text
        for link in self.issue_images:
            try:
                image_markdown = self._download_and_convert_image(link)
                if image_markdown:
                    processed_text += f"\n\n{image_markdown}"
            except Exception as e:
                logger.warning(f"Failed to process image from {link}: {e}")
```
(`sweagent/agent/problem_statement.py:157-213`)

Image handling constraints: allowed MIME types `{image/png, image/jpeg, image/jpg, image/webp}` (`:18-23`), 10 MB cap (`:247`), 30 s timeout, a spoofed Chrome `User-Agent` (`:235-238`), and output shape `![{url}](data:{content_type};base64,{b64_data})` (`:262`).

```python
ProblemStatementConfig = (
    TextProblemStatement
    | SWEBenchMultimodalProblemStatement
    | GithubIssue
    | EmptyProblemStatement
    | FileProblemStatement
)
```
(`sweagent/agent/problem_statement.py:285-291`)

### 2.3 Repo configs

```python
class Repo(Protocol):
    """Protocol for repository configurations."""

    base_commit: str
    repo_name: str

    def copy(self, deployment: AbstractDeployment): ...

    def get_reset_commands(self) -> list[str]: ...


def _get_git_reset_commands(base_commit: str) -> list[str]:
    return [
        "git fetch",
        "git status",
        "git restore .",
        "git reset --hard",
        f"git checkout {shlex.quote(base_commit)}",
        "git clean -fdq",
    ]
```
(`sweagent/environment/repo.py:20-39`)

```python
class PreExistingRepoConfig(BaseModel):
    """Use this to specify a repository that already exists on the deployment.
    This is important because we need to cd to the repo before running the agent.

    Note: The repository must be at the root of the deployment.
    """

    repo_name: str
    """The repo name (the repository must be located at the root of the deployment)."""
    base_commit: str = Field(default="HEAD")
    ...
    type: Literal["preexisting"] = "preexisting"
    ...
    reset: bool = True
    """If True, reset the repository to the base commit after the copy operation."""

    def copy(self, deployment: AbstractDeployment):
        """Does nothing."""
        pass
```
(`sweagent/environment/repo.py:42-74`)

```python
class LocalRepoConfig(BaseModel):
    path: Path
    base_commit: str = Field(default="HEAD")
    ...
    type: Literal["local"] = "local"
    ...
    @property
    def repo_name(self) -> str:
        """Set automatically based on the repository name. Cannot be set."""
        return Path(self.path).resolve().name.replace(" ", "-").replace("'", "")
```
(`sweagent/environment/repo.py:77-123`)

```python
class GithubRepoConfig(BaseModel):
    github_url: str
    base_commit: str = Field(default="HEAD")
    clone_timeout: float = 500
    type: Literal["github"] = "github"
    ...
    @property
    def repo_name(self) -> str:
        org, repo = _parse_gh_repo_url(self.github_url)
        return f"{org}__{repo}"
```
(`sweagent/environment/repo.py:126-191`) — clone is shallow: `git init` / `git remote add origin` / `git fetch --depth 1 origin <base_commit>` / `git checkout FETCH_HEAD` (`:171-181`).

Plus `SWESmithRepoConfig` (`sweagent/environment/repo.py:194-230`) which fetches a bug branch from a mirror, and:

```python
RepoConfig = LocalRepoConfig | GithubRepoConfig | PreExistingRepoConfig | SWESmithRepoConfig
```
(`sweagent/environment/repo.py:233`)

### 2.4 Environment + instance models

```python
class EnvironmentConfig(BaseModel):
    """Configure data sources and setup instructions for the environment in which we solve the tasks."""

    deployment: DeploymentConfig = Field(
        default_factory=lambda: DockerDeploymentConfig(image="python:3.11", python_standalone_dir="/root"),
        description="Deployment options.",
    )
    repo: RepoConfig | None = Field(
        default=None,
        description="Repository options.",
    )
    post_startup_commands: list[str] = []
    ...
    post_startup_command_timeout: int = 500
    ...
    model_config = ConfigDict(extra="forbid")

    name: str = "main"
```
(`sweagent/environment/swe_env.py:24-48`)

```python
class BatchInstance(BaseModel):
    """A single instance in a batch of instances.
    This specifies both the environment configuration and the problem statement.
    """

    env: EnvironmentConfig
    problem_statement: ProblemStatementConfig
```
(`sweagent/run/batch_instances.py:39-45`)

```python
class SimpleBatchInstance(BaseModel):
    """A simple way to configure a single instance in a batch of instances that all
    use similar deployment configurations.

    Predominantly used for benchmarking purposes. Assumes that the repository is already
    present in the docker container.
    """

    image_name: str
    problem_statement: str
    instance_id: str
    repo_name: str = ""
    """Specifies the repository to use. If empty, no repository is used.
    If the string does not contain a slash, it is interpreted as an already existing repository at the root
    of the docker container. If it is a GitHub URL, it is interpreted as a github repository.
    Else, it is interpreted as a local repository.
    """
    base_commit: str = "HEAD"
    """Used to reset repo."""
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    """Any additional data to be added to the instance.
    This data will be available when formatting prompt templates.
    """

    # Ignore instead of allow because they should be added as `extra_fields`
    model_config = ConfigDict(extra="ignore")
```
(`sweagent/run/batch_instances.py:87-112`)

SWE-bench → instance conversion (note `repo_name="testbed"`, i.e. the repo is pre-baked into the SWE-bench image):

```python
    @classmethod
    def from_swe_bench(cls, instance: dict[str, Any]) -> Self:
        """Convert instances from the classical SWE-bench dataset to the `SimpleBatchInstance` format."""
        iid = instance["instance_id"]
        image_name = instance.get("image_name", None)
        if image_name is None:
            # Docker doesn't allow double underscore, so we replace them with a magic token
            id_docker_compatible = iid.replace("__", "_1776_")
            image_name = f"docker.io/swebench/sweb.eval.x86_64.{id_docker_compatible}:latest".lower()
        extra_fields = {}
        if "image_assets" in instance:
            issue_images = json.loads(instance["image_assets"])["problem_statement"]
            extra_fields["issue_images"] = issue_images
        return cls(
            image_name=image_name,
            problem_statement=instance["problem_statement"],
            instance_id=iid,
            repo_name="testbed",
            base_commit=instance["base_commit"],
            extra_fields=extra_fields,
        )
```
(`sweagent/run/batch_instances.py:172-192`)

### 2.5 Run-level configs

```python
class RunSingleConfig(BaseSettings, cli_implicit_flags=False):
    env: EnvironmentConfig = Field(default_factory=EnvironmentConfig, description="Environment options.")
    agent: AgentConfig = Field(description="Agent options.")
    problem_statement: ProblemStatementConfig = Field(
        default_factory=EmptyProblemStatement, description="Problem statement options."
    )
    output_dir: Path = Field(default=Path("DEFAULT"), description="Output directory.")
    actions: RunSingleActionConfig = Field(default_factory=RunSingleActionConfig)
    env_var_path: Path | None = None
    model_config = SettingsConfigDict(extra="forbid", env_prefix="SWE_AGENT_")
```
(`sweagent/run/run_single.py:83-97`)

```python
class RunBatchConfig(BaseSettings, cli_implicit_flags=False):
    instances: BatchInstanceSourceConfig = Field(description="Instances to run.")
    agent: AgentConfig = Field(description="Agent options.")
    output_dir: Path = Field(default=Path("DEFAULT"), description="Output directory.")
    suffix: str = ""
    raise_exceptions: bool = False
    redo_existing: bool = False
    env_var_path: Path | None = None
    num_workers: int = Field(default=1)
    random_delay_multiplier: float = 0.3
    progress_bar: bool = True
```
(`sweagent/run/run_batch.py:75-98`)

Agent config union (three agent shapes: plain, retry-with-reviewer, shell):

```python
AgentConfig = Annotated[DefaultAgentConfig | RetryAgentConfig | ShellAgentConfig, Field(union_mode="left_to_right")]
```
(`sweagent/agent/agents.py:196`)

---

## 3. Input documents / agent context (D1, D3)

### 3.1 `config/default.yaml` — VERBATIM, IN FULL

```yaml
# Formerly called: anthropic_filemap.yaml
# This template is heavily inspired by anthropic's computer use demo, but you can use
# it with any LM.
agent:
  templates:
    system_template: |-
      You are a helpful assistant that can interact with a computer to solve tasks.
    instance_template: |-
      <uploaded_files>
      {{working_dir}}
      </uploaded_files>
      I've uploaded a python code repository in the directory {{working_dir}}. Consider the following PR description:

      <pr_description>
      {{problem_statement}}
      </pr_description>

      Can you help me implement the necessary changes to the repository so that the requirements specified in the <pr_description> are met?
      I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!
      Your task is to make the minimal changes to non-tests files in the {{working_dir}} directory to ensure the <pr_description> is satisfied.
      Follow these steps to resolve the issue:
      1. As a first step, it might be a good idea to find and read code relevant to the <pr_description>
      2. Create a script to reproduce the error and execute it with `python <filename.py>` using the bash tool, to confirm the error
      3. Edit the sourcecode of the repo to resolve the issue
      4. Rerun your reproduce script and confirm that the error is fixed!
      5. Think about edgecases and make sure your fix handles them as well
      Your thinking should be thorough and so it's fine if it's very long.
    next_step_template: |-
      OBSERVATION:
      {{observation}}
    next_step_no_output_template: |-
      Your command ran successfully and did not produce any output.
  tools:
    env_variables:
      PAGER: cat
      MANPAGER: cat
      LESS: -R
      PIP_PROGRESS_BAR: 'off'
      TQDM_DISABLE: '1'
      GIT_PAGER: cat
    bundles:
      - path: tools/registry
      - path: tools/edit_anthropic
      - path: tools/review_on_submit_m
    registry_variables:
      USE_FILEMAP: 'true'
      SUBMIT_REVIEW_MESSAGES:
        - |
          Thank you for your work on this issue. Please carefully follow the steps below to help review your changes.

          1. If you made any changes to your code after running the reproduction script, please run the reproduction script again.
            If the reproduction script is failing, please revisit your changes and make sure they are correct.
            If you have already removed your reproduction script, please ignore this step.
          2. Remove your reproduction script (if you haven't done so already).
          3. If you have modified any TEST files, please revert them to the state they had before you started fixing the issue.
            You can do this with `git checkout -- /path/to/test/file.py`. Use below <diff> to find the files you need to revert.
          4. Run the submit command again to confirm.

          Here is a list of all of your changes:

          <diff>
          {{diff}}
          </diff>
    enable_bash_tool: true
    parse_function:
      type: function_calling
  history_processors:
    - type: cache_control
      last_n_messages: 2
```
(`config/default.yaml:1-69`, complete file)

**Key observations.** The default context per turn is astonishingly thin: a one-line system prompt, one instance prompt that carries the PR description, and `OBSERVATION:\n{{observation}}` thereafter. There is **no `{{command_docs}}`** because `parse_function: function_calling` puts tool schemas in the API's native tool field. The `history_processors` is only `cache_control` with `last_n_messages: 2` — i.e. **full history is kept, nothing is elided**, and two ephemeral cache breakpoints ride the tail.

### 3.2 `TemplateConfig` defaults (what applies when a config omits a template)

```python
class TemplateConfig(BaseModel):
    """This configuration is used to define almost all message templates that are
    formatted by the agent and sent to the LM.
    """

    system_template: str = ""
    instance_template: str = ""
    next_step_template: str = "Observation: {{observation}}"

    next_step_truncated_observation_template: str = (
        "Observation: {{observation[:max_observation_length]}}<response clipped>"
        "<NOTE>Observations should not exceeded {{max_observation_length}} characters. "
        "{{elided_chars}} characters were elided. Please try a different command that produces less output "
        "or use head/tail/grep/redirect the output to a file. Do not use interactive pagers.</NOTE>"
    )

    max_observation_length: int = 100_000

    next_step_no_output_template: str = None  # type: ignore
    """Template for the next step when the last output was empty. Defaults to next_step_template."""

    strategy_template: str | None = None
    demonstration_template: str | None = None

    demonstrations: list[Path] = field(default_factory=list)

    put_demos_in_history: bool = False
    """If True, add demonstration to history instead of as a single message"""

    disable_image_processing: bool = False

    shell_check_error_template: str = (
        "Your bash command contained syntax errors and was NOT executed. "
        "Please fix the syntax errors and try again. This can be the result "
        "of not adhering to the syntax for multi-line commands. Here is the output of `bash -n`:\n"
        "{{bash_stdout}}\n{{bash_stderr}}"
    )

    command_cancelled_timeout_template: str = (
        "The command '{{command}}' was cancelled because it took more than {{timeout}} seconds. "
        "Please try a different command that completes more quickly. "
        "Note: A common source of this error is if the command is interactive or requires user input "
        "(it is impossible to receive user input in the current environment, so the command will never complete)."
    )
```
(`sweagent/agent/agents.py:60-120`, abridged only of docstrings)

### 3.3 Variables available to every template (D3)

```python
    def _get_format_dict(self, **kwargs) -> dict[str, Any]:
        """Get the dictionary of key value pairs used to format the templates"""
        assert self._problem_statement is not None
        assert self._env is not None
        return dict(
            command_docs=self.tools.config.command_docs,
            **self.tools.config.env_variables,
            **kwargs,
            problem_statement=self._problem_statement.get_problem_statement(),
            repo=self._env.repo.repo_name if self._env.repo is not None else "",
            **self._problem_statement.get_extra_fields(),
        )
```
(`sweagent/agent/agents.py:658-673`)

Plus, at each turn, the **state dict** returned by the bundles' `state_command`s is splatted into the template namespace (`sweagent/agent/agents.py:739-746`, `**step.state`). That is where `{{working_dir}}`, `{{open_file}}` and `{{diff}}` come from — see §8.10.

Template selection each turn (D1's per-turn document):

```python
        elided_chars = 0
        if step.observation.strip() == "":
            # Show no output template if observation content was empty
            templates = [self.templates.next_step_no_output_template]
        elif len(step.observation) > self.templates.max_observation_length:
            templates = [self.templates.next_step_truncated_observation_template]
            elided_chars = len(step.observation) - self.templates.max_observation_length
        else:
            # Show standard output template if there is observation content
            templates = [self.templates.next_step_template]
```
(`sweagent/agent/agents.py:729-738`)

When function calling is on, the observation message becomes `role: "tool"` with a `tool_call_id`; otherwise `role: "user"` (`sweagent/agent/agents.py:702-712`).

The full turn-0 sequence is: system message → demonstrations (optional) → instance template + optional strategy template (`sweagent/agent/agents.py:603-605`, `:748-760`).

### 3.4 History processors (context management)

Discriminated union at `sweagent/agent/history_processors.py:390-399`:

| Processor | `type` | Behaviour | Cite |
|---|---|---|---|
| `DefaultHistoryProcessor` | `default` | identity | `:74-82` |
| `LastNObservations` | `last_n_observations` | replaces older observations with `"Old environment output: (N lines omitted)"`; `polling` lets you batch the elision so caching survives; `always_keep_output_for_tags={"keep_output"}` / `always_remove_output_for_tags={"remove_output"}`; **never elides the first observation (the instance template)** | `:85-176` |
| `TagToolCallObservations` | `tag_tool_call_observations` | tags observations from named tools so `LastNObservations` keeps them | `:179-212` |
| `ClosedWindowHistoryProcessor` | `closed_window` | collapses stale file-viewer windows to `"Outdated window with N lines omitted..."` | `:215-258` |
| `CacheControlHistoryProcessor` | `cache_control` | Anthropic ephemeral cache breakpoints on last N user/tool messages | `:261-302` |
| `RemoveRegex` | `remove_regex` | default `remove: ["<diff>.*</diff>"]`, `keep_last: 0` | `:305-337` |
| `ImageParsingHistoryProcessor` | `image_parsing` | converts inline base64 markdown images into multimodal `image_url` parts | `:340-387` |

Docstring worth quoting on the tradeoff:

> "Note that using this history processor will break prompt caching (as the history of every query will change every time due to the elided observations). There are some workarounds possible with the `polling` parameter. However, most SotA models can now fit a lot of context, so generally this history processor is not always needed anymore."
> — `sweagent/agent/history_processors.py:105-111`

### 3.5 The other configs in `config/`

| File | One-liner |
|---|---|
| `config/default.yaml` | Default. Anthropic-computer-use-style prompt + `str_replace_editor` + `bash` + review-on-submit; function calling; cache_control(2). |
| `config/default_backticks.yaml` | Identical to default but `parse_function: thought_action` (backtick code blocks instead of native tool calls). |
| `config/default_mm_no_images.yaml` | SWE-bench Multimodal, `disable_image_processing: true`, `max_observation_length: 10_000_000`, `execution_timeout: 300`; image/web-browser bundles commented out. |
| `config/default_mm_with_images.yaml` | Same but images ON: adds `tools/image_tools` + `tools/web_browser`, and `image_parsing` history processor. |
| `config/bash_only.yaml` | Bash-only REPL config for weak instruction-following LMs; `single_bash_code_block` parser; enormous instructional `instance_template` (`:20-172`) with sed/heredoc recipes; `max_observation_length: 10_000` with head+tail truncation template. |
| `config/coding_challenge.yaml` | LeetCode/HumanEvalFix-style: windowed viewer + search + replace-edit, `thought_action` parser, one demonstration, `last_n_observations: 5`. |
| `config/sweagent_0_7/07.yaml` | The paper-era config: windowed file viewer (`WINDOW: 100`, `OVERLAP: 2`), `windowed_edit_linting`, `search`, `submit`, `thought_action` parser, `last_n_observations: 5`, one demonstration. |
| `config/sweagent_0_7/07_fcalling.yaml` | 0.7-like tools, but function-calling parser. |
| `config/sweagent_0_7/07_thought_action.yaml` | 0.7-like tools with `thought_action` parser + line-range replace tools. |
| `config/sweagent_0_7/07_thought_action_xml.yaml` | Same with `xml_thought_action` parser. |
| `config/sweagent_0_7/07_from_url.yaml` | 0.7-style tools, tuned for pointing at an arbitrary GitHub issue rather than benchmarking. |
| `config/exotic/windowed_replace.yaml` | Windowed viewer + search/replace edit tool. |
| `config/exotic/windowed_replace_late_repro.yaml` | Same, but prompt "encourages the model to write the reproduction script _after_ it has investigated the codebase". |
| `config/exotic/default_shell.yaml` | `agent.type: shell` for `sweagent sh`. |
| `config/human/human.yaml` | `model.name: human`, windowed tools — you type the commands. |
| `config/human/human_demo.yaml` | Human config used to record demonstrations. |
| `config/demo/default.yaml`, `demo/no_instructions.yaml`, `demo/only_bash.yaml` | Talk/demo variants; `only_bash.yaml` strips everything to `registry` + `submit` + bash. |
| `config/benchmarks/250212_sweagent_heavy_sbl.yaml` | "SWE-agent heavy": `agent.type: retry`, 3 different sub-agent configs cycled, `chooser` retry loop (`o1`, `reasoning_effort: high`), `cost_limit: 6.0`, `max_attempts: 10`. |
| `config/benchmarks/250225_...`, `250522_...`, `250526_..._sbl.yaml` | SWE-bench submission configs (Claude 3.7 / Sonnet 4), single-attempt, `review_on_submit_m` + `diff_state`. |
| `config/benchmarks/anthropic_filemap_multilingual.yaml` | SWE-bench Multilingual variant (note `git checkout -- /path/to/test/file` without `.py`). |

---

## 4. Verification (G1, G4, G5)

### 4.1 What SWE-agent itself produces

SWE-agent emits a **patch string**, not a verdict. The submission channel is a sentinel token printed by the `submit` tool and detected by the handler:

```python
    def check_for_submission_cmd(self, output: str) -> bool:
        """Function for checking submission request."""
        if r"<<SWE_AGENT_SUBMISSION>>" in output:
            return True
        return False
```
(`sweagent/tools/tools.py:372-376`)

```bash
main() {
    cd $ROOT

    # Check if the patch file exists and is non-empty
    if [ -s "/root/test.patch" ]; then
        # Apply the patch in reverse
        git apply -R < "/root/test.patch"
    fi

    git add -A
    git diff --cached > /root/model.patch
    echo "<<SWE_AGENT_SUBMISSION>>"
}

main "$@"
```
(`tools/submit/bin/submit:1-15`) — note the reverse-apply of `/root/test.patch`: the *test* patch is stripped out so the model's diff is the code diff only.

The agent then reads `/root/model.patch` out of the container:

```python
            try:
                submission = self._env.read_file("/root/model.patch", encoding="utf-8", errors="backslashreplace")
            except FileNotFoundError:
                self.logger.warning("Submission file not found, no submission was made")
                return step
            ...
            if submission.strip() != "":
                step.submission = submission
            else:
                step.submission = None
            step.observation = submission
            if not step.exit_status:
                step.exit_status = "submitted"
            elif step.submission:
                step.exit_status = f"submitted ({step.exit_status})"
            step.done = True
```
(`sweagent/agent/agents.py:886-904`)

### 4.2 Patch saving / local application

`SaveApplyPatchHook` writes `<output_dir>/<instance_id>/<instance_id>.patch` and, if `apply_patch_locally`, `git apply`s it to a `LocalRepoConfig` path (`sweagent/run/hooks/apply_patch.py:18-111`).

The trust gate — SWE-agent's own belief about whether the patch is real:

```python
def _is_promising_patch(info: AgentInfo) -> bool:
    """Do we actually believe that the patch will solve the issue?
    Or are we just submitting the last patch we generated before hitting an error?
    """
    # The exit status can also be `submitted (exit_cost)` etc.
    return info.get("exit_status") == "submitted" and info.get("submission") is not None
```
(`sweagent/run/common.py:382-387`)

Predictions file, SWE-bench-shaped:

```python
def save_predictions(traj_dir: Path, instance_id: str, result: AgentRunResult):
    """Save predictions in a file readable by SWE-bench"""
    output_file = traj_dir / instance_id / (instance_id + ".pred")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    datum = {
        "model_name_or_path": traj_dir.name,
        "instance_id": instance_id,
        "model_patch": result.info.get("submission"),
    }
    output_file.write_text(json.dumps(datum))
```
(`sweagent/run/common.py:370-379`)

### 4.3 Delegated grading — `sb-cli`

```python
class SweBenchEvaluate(RunHook):
    # Maps SWEBenchInstances.subset values to the subset identifiers accepted by
    # sb-cli. sb-cli only supports these three; "full" and "multilingual" have no
    # sb-cli equivalent and therefore cannot be evaluated this way.
    _SUBSET_MAP = {"lite": "swe-bench_lite", "verified": "swe-bench_verified", "multimodal": "swe-bench-m"}
```
(`sweagent/run/hooks/swe_bench_evaluate.py:19-23`)

The hook shells out to `sb-cli submit <subset> <split> --predictions_path ... --run_id ... --output_dir .../sb-cli-reports` (`:43-64`) at end of run (`:107-122`), optionally streaming partial submissions every `continuous_submission_every` seconds (`:74-92`), and renames the single report to `results.json` (`:94-105`). `run_id` gets a timestamp suffix "to avoid collisions when you reuse the name of your run" (`:36-37`).

Guardrail against contaminating results:

> "Cannot evaluate and redo existing at the same time. This would cause invalid results, because after the first merge_preds gives you a preds.json, this file would be submitted to SB-CLI, causing evaluation of old instances, which could then not be overwritten by the new ones."
> — `sweagent/run/run_batch.py:124-128`

Docs restate the separation: "Evaluation is not completed by `sweagent run-batch`, it is a separate step" (`docs/usage/trajectories.md:99`).

### 4.4 In-loop self-verification #1 — `review_on_submit_m` (submit is a two-stage gate)

This is the most interesting *self*-verification mechanism, and it is on by default in `config/default.yaml`. `submit` does **not** submit the first time; it prints a review checklist and increments a stage counter in the registry:

```python
    submit_review_messages = registry.get("SUBMIT_REVIEW_MESSAGES", [])
    n_stages = len(submit_review_messages)
    current_stage = registry.get("SUBMIT_STAGE", 0)
    if not args.force and current_stage != n_stages:
        message = submit_review_messages[current_stage]
        message = message.replace("{{diff}}", patch)
        message = message.replace("{{problem_statement}}", registry.get("PROBLEM_STATEMENT", ""))
        registry["SUBMIT_STAGE"] = current_stage + 1
        print(message)
        sys.exit(0)

    print("<<SWE_AGENT_SUBMISSION>>")
    print(patch)
    print("<<SWE_AGENT_SUBMISSION>>")
```
(`tools/review_on_submit_m/bin/submit:33-46`)

> "Provides an alternative for `submit` that does not immediately submit, but asks the agent to perform additional reviewing steps. Only `submit -f` will trigger the real submit."
> — `tools/review_on_submit_m/README.md:1-6`

The `-f/--force` flag is deliberately hidden from the model: "Do not actually show the -f argument to the model, only use it from the agent for submission after error" (`tools/review_on_submit_m/config.yaml:5-6` — the bundle declares `submit` with no `arguments` at all).

The default review message (paste in §3.1) explicitly asks the agent to (1) re-run the reproduction script, (2) delete it, (3) `git checkout --` any modified TEST files, (4) re-submit. That third item is a **reward-hacking guard**: it removes test edits from the diff before grading.

### 4.5 In-loop self-verification #2 — reviewer / retry loops (`sweagent/agent/reviewer.py`)

Three cooperating abstractions:

```python
class AbstractReviewer(ABC):
    """The reviewer checks a single solution and tries to predict
    if it successfully solves the issue.
    """

    @abstractmethod
    def review(self, instance: ProblemStatement, submission: ReviewSubmission) -> ReviewerResult:
        """Returns True if the submission is believed to be correct"""


class AbstractRetryLoop(ABC):
    """The review loop controls how often the agent tries to solve
    the issue and how it selects the best solution.
    """

    def retry(self) -> bool:
        """Returns True if the agent should retry solving the issue"""
        return False
    ...
    @abstractmethod
    def get_best(self) -> int:
        """Returns the best solution"""
```
(`sweagent/agent/reviewer.py:81-122`)

**`ReviewerConfig`** — the scoring judge:

```python
class ReviewerConfig(BaseModel):
    """The configuration for the reviewer"""

    system_template: str
    instance_template: str
    #: If a submission autosubmits because of total cost or a similar exit status,
    #: it will get this malus to its score
    failure_score_penalty: float = 0.0
    traj_formatter: TrajFormatterConfig
    n_sample: int = 5
    reduce_by_std: float = 0.0
    score_range: tuple[float | None, float | None] = (None, None)
    #: If set, we assume that the score is in the range [score_range[0], score_range[1]]
    #: Reviews that are outside this range will be ignored

    type: Literal["reviewer"] = "reviewer"
```
(`sweagent/agent/reviewer.py:157-174`)

Scoring is *numeric, self-consistency-sampled, penalised for bad exit statuses, and optionally risk-adjusted by std*:

```python
    def interpret(self, response: str) -> bool | float:
        last_line = response.strip().split("\n")[-1].strip()
        # Find all numbers in the last line and take the last one
        numbers = re.findall(r"-?\d+\.?\d*", last_line)
        if not numbers:
            msg = f"Could not interpret response: {last_line!r}"
            raise ValueError(msg)
        number = float(numbers[-1])
        ...
    def review(self, instance: ProblemStatement, submission: ReviewSubmission) -> ReviewerResult:
        exit_status = submission.info.get("exit_status")
        messages = []
        penalty = 0.0
        if not exit_status or exit_status.strip() != "submitted":
            penalty = self._config.failure_score_penalty
        messages = self.format_messages(instance, submission)
        if self._config.n_sample > 1:
            _set_cache_control(messages[-1])  # type: ignore
        answers = []
        accepts = []
        for _ in range(self._config.n_sample):
            ...
        if not accepts:
            answers = ["No valid scores found, failing submission"]
            accepts = [-100.0]
        accept = sum(accepts) / len(accepts) - penalty
        std = np.std(accepts).item()
        if self._config.reduce_by_std > 0:
            accept -= std * self._config.reduce_by_std
```
(`sweagent/agent/reviewer.py:400-449`)

**`ScoreRetryLoopConfig`** and **`ChooserRetryLoopConfig`**:

```python
class ChooserRetryLoopConfig(BaseModel):
    type: Literal["chooser"] = "chooser"
    chooser: ChooserConfig

    max_attempts: int
    min_budget_for_new_attempt: float = 0.0
    """Minimal $ that need to be left in order for us to start a new attempt.
    If set to 0: Always.
    """

    cost_limit: float
    """The maximum cost to spend on all attempts. Does not include cost of choosing.
    """
```
(`sweagent/agent/reviewer.py:180-194`)

```python
class ScoreRetryLoopConfig(BaseModel):
    """The configuration for the review loop"""

    type: Literal["score"] = "score"

    reviewer_config: ReviewerConfig

    accept_score: float
    max_accepts: int = 1
    max_attempts: int

    min_budget_for_new_attempt: float = 0.0
    """Minimal $ that need to be left in order for us to start a new attempt.
    If set to 0: Always.
    """

    cost_limit: float
    """The maximum cost to spend on all attempts and reviews except the last review.
    The last review is not included in the cost limit, because we would waste the last
    attempt if we couldn't score it.
    """

    model: ModelConfig
```
(`sweagent/agent/reviewer.py:200-224`)

```python
RetryLoopConfig = ScoreRetryLoopConfig | ChooserRetryLoopConfig
```
(`sweagent/agent/reviewer.py:237`)

`ScoreRetryLoop.retry()` stops on cost limit, `max_attempts`, `max_accepts`, or insufficient remaining budget (`sweagent/agent/reviewer.py:617-645`). `get_best()` takes argmax score, breaking ties by **fewest API calls** ("If there are multiple submissions with the same score, choose the shortest one", `:654-656`).

`ChooserRetryLoop` instead asks one model to pick among N patches. Its `Chooser` first filters to `exit_status == "submitted"` submissions when ≥2 exist (`sweagent/agent/reviewer.py:332-337`), optionally runs a `Preselector` to shortlist (`:338-356`), then parses the last integer in the response (`:299-305`), falling back to index 0 on any failure.

**The actual chooser prompt used in the SWE-bench Lite "heavy" submission** (`config/benchmarks/250212_sweagent_heavy_sbl.yaml:140-188`), verbatim:

```yaml
    chooser:
      system_template: |
        You are an expert software engineer reviewing code. Your thinking is very thorough, so it is ok if its very long.
      instance_template: |
        You will be given a problem statement and a list of patch submissions.

        Pick the most reasonable patch.
        The patch should solve the problem described in the problem statement in a way that is consistent with the rest of the codebase and the conventions of the codebase.

        Note: Disregard all testing code in the patch, as testing was already done in a separate step.
        Having a test in the patch does not make it any better.

        <IMPORTANT>The last line of your response should be the index of the patch you chose.
        You must choose a single index no matter what. If you cannot decide between two or more
        submissions, choose the first one of these.
        </IMPORTANT>

        Problem statement:
        {{problem_statement}}

        Submissions:
        {% for submission in submissions %}
        Submission {{loop.index0}}:

        {{submission}}

        {% endfor %}

        <IMPORTANT>The last line of your response should be the index of the patch you chose without any other text.</IMPORTANT>
      submission_template: |
        Patch:

        ```python
        {{submission}}
        ```

        The final edited file with 30 lines of context:

        ```python
        {{edited_files30}}
        ```
      max_len_submission: &chooser_max_len_submission 5000
      model: &chooser_model
        name: o1
        top_p: null
        temperature: 1.
        per_instance_cost_limit: 30
        completion_kwargs:
          reasoning_effort: "high"
```

`{{edited_files30}}` comes from `_get_edited_files_with_context`, which renders the patched files with 30/50/70 lines of context (`sweagent/agent/agents.py:907-934`) — these land in `info["edited_files30/50/70"]`.

`RetryAgent` orchestrates: each attempt gets `hard_reset()` of the environment (`sweagent/agent/agents.py:321-326`), sub-agent cost limits are shrunk to the remaining global budget (`:307-310`), and there is a failsafe: "Total instance cost exceeded cost limit. This should not happen, please report this. Triggering autosubmit." (`:336-339`).

### 4.6 In-loop self-verification #3 — action sampling with a binary judge

```python
class BinaryTrajectoryComparisonConfig(BaseModel):
    type: Literal["binary_trajectory_comparison"] = "binary_trajectory_comparison"

    min_n_samples: int = 4
    max_n_samples: int = 10

    comparison_temperature: float | None = None
    """Override the model's temperature. If None, take the temperature configured for the model."""

    system_template: str = """<setting>You are an expert software engineer overseeing junior developers. They suggest actions to take to solve a problem. You must choose the best action to take. </setting>"""
    instance_template: str = dedent("""
    We're solving the following problem

    <problem_statement>
    {{problem_statement}}
    </problem_statement>

    So far, we've performed the following actions:

    <trajectory>
    {{traj}}
    </trajectory>
    """)

    comparison_template: str = dedent("""
    Two junior developers suggested the following actions:

    <thought1>
    {{thought1}}
    </thought1>

    <action1>
    {{action1}}
    </action1>

    <thought2>
    {{thought2}}
    </thought2>

    <action2>
    {{action2}}
    </action2>

    Please compare the two actions in detail.

    Which action should we take?

    If you think the first action is better, respond with "first".
    If you think the second action is better, respond with "second".

    The last line of your response MUST be "first" or "second".
    """)
```
(`sweagent/agent/action_sampler.py:96-147`)

Sampling escalates from `min_n_samples` to `max_n_samples` when edits are among the candidates (`sweagent/agent/action_sampler.py:251-259`). There is also `AskColleaguesConfig` (`n_samples: int = 2`, `:40-47`).

---

## 5. Flakiness and nondeterminism (G2)

### 5.1 Sampling determinism

Defaults are greedy: `temperature: float = 0.0`, `top_p: float | None = 1.0` (`sweagent/agent/models.py:79-82`). All benchmark configs use `temperature: 0.0` (e.g. `config/benchmarks/250526_anthropic_filemap_simple_review_sbl.yaml:91`) except the chooser/judge models which use `temperature: 1.` with `top_p: null` (`config/benchmarks/250212_sweagent_heavy_sbl.yaml:184-185`).

### 5.2 LM API retries

```python
class RetryConfig(PydanticBaseModel):
    """This configuration object specifies how many times to retry a failed LM API call."""

    retries: int = 20
    """Number of retries"""
    min_wait: float = 10
    """Minimum wait time between retries (random exponential wait)"""
    max_wait: float = 120
    """Maximum wait time between retries (random exponential wait)"""
```
(`sweagent/agent/models.py:55-63`)

Retries use `tenacity` with `wait_random_exponential` and an explicit **do-not-retry** list — these are treated as deterministic/terminal rather than transient:

```python
        for attempt in Retrying(
            stop=stop_after_attempt(self.config.retry.retries),
            wait=wait_random_exponential(min=self.config.retry.min_wait, max=self.config.retry.max_wait),
            reraise=True,
            retry=retry_if_not_exception_type(
                (
                    ContextWindowExceededError,
                    CostLimitExceededError,
                    RuntimeError,
                    litellm.exceptions.UnsupportedParamsError,
                    litellm.exceptions.NotFoundError,
                    litellm.exceptions.PermissionDeniedError,
                    litellm.exceptions.ContextWindowExceededError,
                    litellm.exceptions.APIError,
                    litellm.exceptions.ContentPolicyViolationError,
                    TypeError,
                    litellm.exceptions.AuthenticationError,
                    ContentPolicyViolationError,
                    ModelConfigurationError,
                    KeyboardInterrupt,
                    IndexError,
                )
            ),
            before_sleep=retry_warning,
        ):
```
(`sweagent/agent/models.py:809-833`)

`fallbacks: list[dict[str, Any]] = []` allows failover to alternate models (`sweagent/agent/models.py:113-117`, passed at `:729`).

### 5.3 Context / cost / call limits raised as exceptions

```python
        elif input_tokens > self.model_max_input_tokens > 0:
            msg = f"Input tokens {input_tokens} exceed max tokens {self.model_max_input_tokens}"
            raise ContextWindowExceededError(msg)
```
(`sweagent/agent/models.py:701-703`)

```python
        except litellm.exceptions.ContextWindowExceededError as e:
            raise ContextWindowExceededError from e
        except litellm.exceptions.ContentPolicyViolationError as e:
            raise ContentPolicyViolationError from e
        except litellm.exceptions.BadRequestError as e:
            if "is longer than the model's context length" in str(e):
                raise ContextWindowExceededError from e
            raise
```
(`sweagent/agent/models.py:734-741`)

```python
        # Check whether total cost or instance cost limits have been exceeded
        if 0 < self.config.total_cost_limit < GLOBAL_STATS.total_cost:
            ...
            raise TotalCostLimitExceededError(msg)

        if 0 < self.config.per_instance_cost_limit < self.stats.instance_cost:
            ...
            raise InstanceCostLimitExceededError(msg)

        if 0 < self.config.per_instance_call_limit < self.stats.api_calls:
            ...
            raise InstanceCallLimitExceededError(msg)
```
(`sweagent/agent/models.py:654-670`)

Note the failure mode where cost cannot be computed at all (local models):

> "Error calculating cost: {e} for your model {self.config.name}. If this is ok (local models, etc.), please make sure you set `per_instance_cost_limit` and `total_cost_limit` to 0 to disable this safety check."
> — `sweagent/agent/models.py:748-752`, raises `ModelConfigurationError`

### 5.4 Content-policy violations are silently resampled

```python
            except ContentPolicyViolationError:
                self.logger.warning("Content policy violation, trying to resample")
                n_format_fails += 1
                # Try if simply resampling helps here
                pass
```
(`sweagent/agent/agents.py:1130-1134`)

### 5.5 Caching, thread affinity, throttling

- `cache_control` history processor writes `{"type": "ephemeral"}` breakpoints (`sweagent/agent/history_processors.py:53-67`, `:288-302`). There is a documented workaround: `"Workaround for weird bug"` on tool-role messages (`:64-67`).
- `cache_control` and `thinking_blocks` are stripped before token counting due to a litellm bug (`sweagent/agent/models.py:683-694`, referencing issue #1109).
- API-key rotation is **thread-pinned so prompt caching survives**:
  ```python
  choose_api_key_by_thread: bool = True
  """Whether to choose the API key based on the thread name (if multiple are configured).
  This ensures that with
  run-batch, we use the same API key within a single-thread so that prompt caching still works.
  """
  ```
  (`sweagent/agent/models.py:119-123`; implementation `:172-190`; keys are `:::`-separated, `:88-91`)
- `delay: float = 0.0` — "Minimum delay before querying (this can help to avoid overusing the API if sharing it with other people)" (`sweagent/agent/models.py:108-111`), enforced by `_sleep()` against a global timestamp under a lock (`:672-677`). `GLOBAL_STATS` + `GLOBAL_STATS_LOCK` at `:283-289`.

### 5.6 Batch-level nondeterminism controls

```python
    num_workers: int = Field(default=1)
    """Number of parallel workers to use."""
    random_delay_multiplier: float = 0.3
    """We will wait for a random amount of time between 0 and `random_delay_multiplier`
    times the number of workers at the start of each instance. This is to avoid any
    potential race condition or issues with bottlenecks, e.g., when running on a platform
    with few CPUs that cannot handle the startup of all containers in time.
    """
```
(`sweagent/run/run_batch.py:87-94`)

```python
        # Let's add some randomness to avoid any potential race conditions or thundering herd
        if self._progress_manager.n_completed < self._num_workers:
            time.sleep(random.random() * self._random_delay_multiplier * (self._num_workers - 1))
```
(`sweagent/run/run_batch.py:295-297`)

Instance shuffling is **seeded**, so shuffled subsets are reproducible:

```python
    if shuffle:
        instances = sorted(instances.copy(), key=lambda x: x.problem_statement.id)
        random.seed(42)
        random.shuffle(instances)
```
(`sweagent/run/batch_instances.py:70-73`)

Config objects are deep-copied everywhere to prevent cross-thread state bleed: `ToolHandler.__init__` ("Always copy config to avoid shared state between different instances across threads", `sweagent/tools/tools.py:236-237`), `SWEEnv.from_config` (`sweagent/environment/swe_env.py:90-91`), `LiteLLMModel.__init__` (`sweagent/agent/models.py:581-582`), `SimpleBatchInstance.to_full_batch_instance` ("Very important: Make a copy of the deployment config because it will be shared among instances!!!", `sweagent/run/batch_instances.py:116-117`), and `SaveApplyPatchHook` uses `threading.local()` (`sweagent/run/hooks/apply_patch.py:24-27`).

### 5.7 Deterministic/mock models (for harness testing)

| Model | Purpose | Cite |
|---|---|---|
| `HumanModel` / `HumanThoughtModel` | interactive human driver, readline history, `spend_money N` debug command | `sweagent/agent/models.py:344-461` |
| `ReplayModel` | re-issues every action from a `.traj`; auto-submits when the replay runs out ("Reached end of replay trajectory without submitting. Submitting now.") | `sweagent/agent/models.py:464-526` |
| `PredeterminedTestModel` | fixed output list | `sweagent/agent/models.py:529-548` |
| `InstantEmptySubmitTestModel` | `touch reproduce.py` then `submit`; `time.sleep(random.uniform(0, self.config.delay))` | `sweagent/agent/models.py:551-575` |

Fault injection for testing the exception paths:

```python
def _handle_raise_commands(action: str) -> None:
    if action == "raise_runtime":
        raise SwerexException()
    elif action == "raise_cost":
        raise CostLimitExceededError()
    elif action == "raise_context":
        raise ContextWindowExceededError()
    elif action.startswith("raise_function_calling"):
        ...
        raise FunctionCallingFormatError(error_message, error_code)  # type: ignore
```
(`sweagent/agent/models.py:328-341`)

---

## 6. Metrics and reported numbers (G3, H1)

Numbers actually stated **in this repo** (exact quotes; note some are stale relative to the leaderboards they link to):

| Number | Claim | Cite |
|---|---|---|
| **12.29 %** | "On [SWE-bench](https://github.com/SWE-bench/SWE-bench), SWE-agent resolves **12.29%** of issues, achieving the state-of-the-art performance on the full test set." | `docs/background/index.md:9` |
| **13.5 %** | "On the [NYU CTF benchmark](https://github.com/NYU-LLM-CTF/LLM_CTF_Database), EnIGMA solves **13.5%** of the capture the flag (CTF) challenges, achieving the state-of-the-art performance on the full test set of **200 challenges**, **surpassing previous agents by more than 3x**" | `docs/background/index.md:43` |
| **65 %** | "July 24: [Mini-SWE-Agent](https://github.com/SWE-agent/mini-SWE-agent) achieves 65% on SWE-bench verified in 100 lines of python!" | `README.md:41`, `docs/index.md:77` |

Qualitative SoTA claims without in-repo numbers:
- "May 2: [SWE-agent-LM-32b](https://github.com/SWE-bench/SWE-smith) achieves open-weights SOTA on SWE-bench" (`README.md:42`)
- "Feb 28: SWE-agent 1.0 + Claude 3.7 is SoTA on SWE-Bench full" (`README.md:43`)
- "Feb 25: SWE-agent 1.0 + Claude 3.7 is SoTA on SWE-bench verified" (`README.md:44`)
- "Feb 13: Releasing SWE-agent 1.0: SoTA on SWE-bench light & tons of new features" (`README.md:45`)
- "our LM SWE-agent-LM-32b achieves open-weights SotA on SWE-bench verified with SWE-agent!" (`docs/installation/changelog.md:6`)
- "EnIGMA achieves state-of-the-art results on multiple cybersecurity benchmarks (see leaderboard)" (`README.md:66`)

**Important caveat found in the repo itself** — SWE-agent has been effectively superseded:

> "Most of our current development effort is on [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent/), which has superseded SWE-agent. It matches the performance performance of SWE-agent, while being much simpler. ... Our general recommendation is to use mini-SWE-agent instead of SWE-agent going forward."
> — `README.md:19-24`

Metrics tooling shipped in-repo: `sweagent quick-stats` / `qs` aggregates `.traj` files by `exit_status` and API-call counts (`sweagent/run/quick_stats.py:35-66`; described at `docs/usage/cli.md:17`). The trajectory inspector colours instances by cross-referencing `results.json` from `sb-cli`:

```python
def get_status(traj_path) -> str:
    """Return results emoji for single trajectory"""
    results = load_results(Path(traj_path).parent / "results.json")
    info = json.loads(Path(traj_path).read_text()).get("info", {})
    n_steps = info.get("model_stats", {}).get("api_calls", "N/A")
    exit_status = info.get("exit_status", "N/A")
    exit_status_str = f" ({exit_status} after {n_steps} steps)"
    instance_id = Path(traj_path).stem
    if results is None:
        return f"❓ {exit_status_str}"
    elif instance_id in results["resolved_ids"]:
        return "✅"
    else:
        return f"❌ {exit_status_str}"
```
(`sweagent/inspector/server.py:205-218`) — i.e. resolution is `instance_id in results["resolved_ids"]`, entirely from SWE-bench's report.

Per-instance usage metrics tracked:

```python
class InstanceStats(PydanticBaseModel):
    """This object tracks usage numbers (costs etc.) for a single instance."""

    instance_cost: float = 0
    tokens_sent: int = 0
    tokens_received: int = 0
    api_calls: int = 0
```
(`sweagent/agent/models.py:292-298`)

---

## 7. Documented failure modes (H3)

### 7.1 `exit_status` — the complete enumeration

Every value, with the exact line that sets it:

| `exit_status` | Meaning | Set at |
|---|---|---|
| `submitted` | Clean submission via the submit tool | `sweagent/agent/agents.py:900` |
| `submitted (<other_status>)` | Autosubmit salvaged a patch after an error (e.g. `submitted (exit_cost)`) | `sweagent/agent/agents.py:902` and `:848` |
| `exit_command` | Model literally issued the bare `exit` action | `sweagent/agent/agents.py:953` |
| `exit_forfeit` | Model called `exit_forfeit` (gave up) | `sweagent/agent/agents.py:1157` |
| `exit_total_execution_time` | Cumulative in-container execution time exceeded `total_execution_timeout` | `sweagent/agent/agents.py:1164` |
| `exit_command_timeout` | ≥ `max_consecutive_execution_timeouts` consecutive command timeouts | `sweagent/agent/agents.py:1171` |
| `exit_context` | `ContextWindowExceededError` | `sweagent/agent/agents.py:1177` |
| `exit_cost` | `CostLimitExceededError` (instance cost / call limit) | `sweagent/agent/agents.py:1184` |
| `exit_api` | tenacity `RetryError` — LM API kept failing | `sweagent/agent/agents.py:1190` |
| `exit_environment_error` | `SwerexException` — the sandbox/runtime failed | `sweagent/agent/agents.py:1196` |
| `exit_error` | `RuntimeError` or any other unhandled exception | `sweagent/agent/agents.py:1202` and `:1208` |
| `exit_format` | `max_requeries` exhausted on format / blocklist / bash-syntax errors | `sweagent/agent/agents.py:1216` |
| `early_exit` / `None` | Trajectory written but never finished; `run-batch` deletes and redoes these | `sweagent/run/run_batch.py:396-401` |
| `skipped (<previous_status>)` | Batch runner found a finished `.traj` and skipped the instance | `sweagent/run/run_batch.py:301-304` |
| `unknown_exit` | Progress-table fallback when `info` has no `exit_status` | `sweagent/run/run_batch.py:327` |

Note `TotalCostLimitExceededError` is deliberately **not** turned into an exit status — it re-raises to kill the whole batch (`sweagent/agent/agents.py:1180-1181`, and `sweagent/run/run_batch.py:314-318`).

The dispatch block, verbatim — this is the environment-failure-vs-model-failure separation:

```python
            # Errors that are raised

            except KeyboardInterrupt:
                raise
            except EOFError:
                raise

            # Errors that cause requery

            except FormatError as e:
                n_format_fails += 1
                history = handle_error_with_retry(
                    exception=e, template=self.tools.config.format_error_template, n_requeries=n_format_fails
                )
            except _BlockedActionError as e:
                n_format_fails += 1
                history = handle_error_with_retry(
                    exception=e, template=self.tools.config.filter.blocklist_error_template, n_requeries=n_format_fails
                )
            except ContentPolicyViolationError:
                self.logger.warning("Content policy violation, trying to resample")
                n_format_fails += 1
                # Try if simply resampling helps here
                pass
            except BashIncorrectSyntaxError as e:
                n_format_fails += 1
                history = handle_error_with_retry(
                    exception=e,
                    template=self.templates.shell_check_error_template,
                    n_requeries=n_format_fails,
                )
            except _RetryWithOutput as e:
                history = handle_error_with_retry(
                    exception=e,
                    template=self.templates.next_step_template,
                    n_requeries=n_format_fails,
                )
            except _RetryWithoutOutput:
                pass
                # Requery with the same template as the last step

            # Errors that cause exit

            except _ExitForfeit:
                self.logger.info("Exiting due to forfeit")
                return handle_error_with_autosubmission(
                    "exit_forfeit",
                    "Exiting due to forfeit",
                )

            except _TotalExecutionTimeExceeded:
                self.logger.exception("Exiting due to total execution time exceeded", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_total_execution_time",
                    "Exit due to total execution time exceeded",
                )

            except CommandTimeoutError:
                self.logger.exception("Exiting due to multiple consecutive command timeouts", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_command_timeout",
                    "Exit due to multiple consecutive command timeouts",
                )

            except ContextWindowExceededError:
                return handle_error_with_autosubmission(
                    "exit_context",
                    "Exit due to context window",
                )
            except TotalCostLimitExceededError:
                raise
            except CostLimitExceededError:
                return handle_error_with_autosubmission(
                    "exit_cost",
                    "Exit due to cost limit",
                )
            except RetryError as e:
                self.logger.exception(f"Exiting due to retry error: {e}", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_api",
                    f"Exit due to retry error: {e}",
                )
            except SwerexException as e:
                self.logger.exception(f"Exiting due to environment error: {e}", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_environment_error",
                    f"Exit due to environment error: {e}",
                )
            except RuntimeError as e:
                self.logger.exception(f"Exiting due to runtime error: {e}", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_error",
                    f"Exit due to runtime error: {e}",
                )
            except Exception as e:
                self.logger.exception(f"Exiting due to unknown error: {e}", exc_info=True)
                return handle_error_with_autosubmission(
                    "exit_error",
                    f"Exit due to unknown error: {e}",
                )
        self.logger.exception(
            "Exit due to repeated format/blocklist/bash syntax errors",
            exc_info=True,
        )
        return handle_error_with_autosubmission(
            "exit_format",
            "Exit due to repeated format/blocklist/bash syntax errors",
        )
```
(`sweagent/agent/agents.py:1111-1218`)

### 7.2 Autosubmission-after-error (why `submitted (exit_cost)` exists)

```python
    def attempt_autosubmission_after_error(self, step: StepOutput) -> StepOutput:
        """For most exceptions, we attempt to still extract the patch and submit that.
        This means we send the `submit` command to the runtime and parse the output.
        """
        self.logger.warning("Attempting autosubmission after error")
        step = step.model_copy(deep=True)
        step.done = True
        assert self._env is not None
        if not asyncio.run(self._env.deployment.is_alive(timeout=10)):
            # The agent is dead. This is very bad. Maybe we can take a 'diff' that was saved
            # for a previous step? (if running with diff in tools)
            self.logger.error("Runtime is no longer alive")
            ...
            diff = last_trajectory_step["state"]["diff"]
            self.logger.info("Using diff from last trajectory step to autosubmit")
            step.submission = diff
            if step.submission:
                step.observation = "Environment died unexpectedly. Exited (autosubmitted)"
                step.exit_status = f"submitted ({step.exit_status})"
```
(`sweagent/agent/agents.py:823-851`) — this is why the `diff_state` bundle (§8.7) exists: it snapshots the cumulative diff into `/root/state.json` every step so a dead container can still yield a patch.

### 7.3 `sweagent/exceptions.py` — VERBATIM, COMPLETE

```python
from typing import Any, Literal

"""This module contains all custom exceptions used by the SWE-agent."""


class FormatError(Exception):
    """Raised when the model response cannot properly be parsed into thought and actions."""


class FunctionCallingFormatError(FormatError):
    """Format error exception used by the function
    calling parser."""

    def __init__(
        self,
        message: str,
        error_code: Literal[
            "missing", "multiple", "incorrect_args", "invalid_json", "invalid_command", "missing_arg", "unexpected_arg"
        ],
        **extra_info: Any,
    ):
        super().__init__(message + f" [error_code={error_code}]")
        self.message = message
        self.extra_info = {"error_code": error_code, **extra_info}


class ContextWindowExceededError(Exception):
    """Raised when the context window of a LM is exceeded"""


class CostLimitExceededError(Exception):
    """Raised when we exceed a cost limit"""


class InstanceCostLimitExceededError(CostLimitExceededError):
    """Raised when we exceed the cost limit set for one task instance"""


class TotalCostLimitExceededError(CostLimitExceededError):
    """Raised when we exceed the total cost limit"""


class InstanceCallLimitExceededError(CostLimitExceededError):
    """Raised when we exceed the per instance call limit"""


class ContentPolicyViolationError(Exception):
    """Raised when the model response violates a content policy"""


class ModelConfigurationError(Exception):
    """Raised when the model configuration is invalid/no further retries
    should be made.
    """
```
(`sweagent/exceptions.py:1-55`, entire file)

Additional **internal control-flow** exceptions (not in `exceptions.py`) and their in-band sentinel tokens:

```python
class _BlockedActionError(Exception):
    """Raised when the agent's action is blocked"""


class _RetryWithOutput(Exception):
    """Used for internal control flow"""


class _RetryWithoutOutput(Exception):
    """Used for internal control flow"""


class _ExitForfeit(Exception):
    """Used for internal control flow"""


class _TotalExecutionTimeExceeded(Exception):
    """Used for internal control flow"""


RETRY_WITH_OUTPUT_TOKEN = "###SWE-AGENT-RETRY-WITH-OUTPUT###"
RETRY_WITHOUT_OUTPUT_TOKEN = "###SWE-AGENT-RETRY-WITHOUT-OUTPUT###"
EXIT_FORFEIT_TOKEN = "###SWE-AGENT-EXIT-FORFEIT###"
```
(`sweagent/agent/agents.py:199-221`) — any tool can print these tokens to control the agent loop (`sweagent/agent/agents.py:995-1002`). `_BreakLoop` in `sweagent/run/run_batch.py:133-134` aborts the whole batch.

### 7.4 Other documented failure/quality modes

- **Duplicate tool names across bundles** → hard `ValueError` at config load: `"Tool '{name}' is defined multiple times: ... First definition in ... Duplicate definition in ..."` (`sweagent/tools/tools.py:180-187`).
- **Tool missing in container** → `"Tool {command} is not available in the container."` after a `which` probe of every tool at install time (`sweagent/tools/tools.py:276-290`).
- **Bash tool disabled with a non-function-calling parser** → `ValueError` (`sweagent/tools/tools.py:206-211`).
- **Empty/unset templates** → warning: `"system_template/instance_template is not set, using empty string. Perhaps you were overwriting the default config?"` (`sweagent/agent/agents.py:140-145`).
- **Syntax-highlighter deadlock** — a real observed harness bug:
  > "We disable syntax highlighting here, because some inputs can lead to a complete cross-thread freeze in the agent. See https://github.com/SWE-agent/SWE-agent/issues/901 ."
  (`sweagent/agent/agents.py:699-701`)
- **Unparseable patch** → `"Failed to parse patch with unidiff. Some variables will be empty."` (`sweagent/agent/agents.py:924-925`).
- **Model doesn't support function calling** → warning pointing to `parse_function='thought_action'` (`sweagent/agent/models.py:587-594`).

---

## 8. Tool surface — FULL enumeration

### 8.1 The bundle mechanism

A bundle is a directory containing `config.yaml`, `bin/` (executables), optional `install.sh`, optional `lib/` (`docs/config/tools.md:17-28`).

```python
class BundleConfig(BaseModel):
    tools: dict[str, dict]
    state_command: str | None = None


class Bundle(BaseModel):
    path: Path
    hidden_tools: list[str] = Field(default_factory=list)
    _config: BundleConfig = PrivateAttr(default=None)
    ...
    @property
    def commands(self) -> list[Command]:
        return [
            Command(name=tool, **tool_config.model_dump() if isinstance(tool_config, Command) else tool_config)
            for tool, tool_config in self.config.tools.items()
            if tool not in self.hidden_tools
        ]
```
(`sweagent/tools/bundle.py:12-57`)

Installation: bundles are `rsync`-style uploaded to `/root/tools/<bundle_name>`, `PATH`-prepended, `chmod +x`'d, and `install.sh` sourced:

```python
        for bundle in self.config.bundles:
            cmds = [
                f"export PATH=/root/tools/{bundle.path.name}/bin:$PATH",
                f"chmod +x /root/tools/{bundle.path.name}/bin/*",
            ]
            if (bundle.path / "install.sh").exists():
                cmds.append(f"cd /root/tools/{bundle.path.name} && source install.sh")
            cmds.append(f"chmod +x /root/tools/{bundle.path.name}/bin/*")
```
(`sweagent/tools/tools.py:292-309`)

Reset writes the registry and clears state:

```python
        env.write_file("/root/.swe-agent-env", json.dumps(self.config.registry_variables))
        env.write_file("/root/state.json", "{}")
```
(`sweagent/tools/tools.py:262-263`)

Each `Command` is auto-converted to an OpenAI function schema (`sweagent/tools/commands.py:133-165`) or to human-readable docs via `generate_command_docs` (`sweagent/tools/utils.py:75-108`), which is what `{{command_docs}}` renders.

### 8.2 Master tool table (all 15 bundles, every tool)

| Bundle | Tool | Signature | Description |
|---|---|---|---|
| *(builtin)* | `bash` | `<command>` | runs the given command directly in bash |
| `tools/registry` | *(none)* | — | shared `EnvRegistry` lib; installs `_read_env`/`_write_env` helpers |
| `tools/edit_anthropic` | `str_replace_editor` | `str_replace_editor <command> <path> [<file_text>] [<view_range>] [<old_str>] [<new_str>] [<insert_line>]` | Custom editing tool for viewing, creating and editing files |
| `tools/windowed` | `goto` | `goto <line_number>` | moves the window to show `<line_number>` |
| `tools/windowed` | `open` | `open "<path>" [<line_number>]` | opens the file at the given path in the editor |
| `tools/windowed` | `create` | `create <filename>` | creates and opens a new file with the given name |
| `tools/windowed` | `scroll_up` | `scroll_up` | moves the window up `{WINDOW}` lines |
| `tools/windowed` | `scroll_down` | `scroll_down` | moves the window down `{WINDOW}` lines |
| `tools/windowed_edit_linting` | `edit` | `edit <start_line>:<end_line>\n<replacement_text>\nend_of_edit` | replaces line range in the open file; **rejects the edit if flake8 finds new syntax errors** |
| `tools/windowed_edit_replace` | `edit` | `edit <search> <replace> [<replace-all>]` | replace first (or all) occurrence(s) of `<search>` within the displayed lines |
| `tools/windowed_edit_replace` | `insert` | `insert <text> [<line>]` | insert `<text>` at end of file or after `<line>` |
| `tools/windowed_edit_rewrite` | `edit` | `edit <text>` | replace the currently displayed lines with `<text>` |
| `tools/search` | `find_file` | `find_file <file_name> [<dir>]` | finds all files with the given name/glob in dir |
| `tools/search` | `search_dir` | `search_dir <search_term> [<dir>]` | searches for term in all files in dir |
| `tools/search` | `search_file` | `search_file <search_term> [<file>]` | searches for term in file (defaults to open file) |
| `tools/submit` | `submit` | `submit` | submits the current file |
| `tools/review_on_submit_m` | `submit` | `submit` | submits the current file (**two-stage: first call returns a review checklist**; hidden `-f`) |
| `tools/forfeit` | `exit_forfeit` | `exit_forfeit` | Give up on the current challenge and terminate the session. |
| `tools/filemap` | `filemap` | `filemap <file_path>` | Print the contents of a Python file, skipping lengthy function and method definitions. |
| `tools/image_tools` | `view_image` | `view_image <image_file>` | view an image file |
| `tools/diff_state` | *(none)* | — | state-only bundle: writes cumulative `diff` into `/root/state.json` |
| `tools/multilingual_setup` | *(none)* (`do_nothing` binary) | — | install-only bundle: imports `/proc/1/environ`, adds Python 3.11 fallback to PATH |
| `tools/web_browser` | `open_site` | `open_site <url>` | Open the specified website URL or local file path |
| `tools/web_browser` | `close_site` | `close_site` | Close the currently open browser window |
| `tools/web_browser` | `screenshot_site` | `screenshot_site` | Take a screenshot of the current page |
| `tools/web_browser` | `click_mouse` | `click_mouse <x> <y> [<button>]` | Click at coordinates (shown as a red crosshair) |
| `tools/web_browser` | `double_click_mouse` | `double_click_mouse <x> <y>` | Double-click at the specified coordinates |
| `tools/web_browser` | `move_mouse` | `move_mouse <x> <y>` | Move mouse to the specified coordinates |
| `tools/web_browser` | `drag_mouse` | `drag_mouse <path>` | Drag mouse along a JSON path `[[x1,y1],[x2,y2],...]` |
| `tools/web_browser` | `type_text` | `type_text <text>` | Type the given text at the focused element |
| `tools/web_browser` | `scroll_on_page` | `scroll_on_page <scroll_x> <scroll_y>` | Scroll by pixels on the current page |
| `tools/web_browser` | `execute_script_on_page` | `execute_script_on_page <script>` | Execute a custom JavaScript snippet on the page |
| `tools/web_browser` | `navigate_back` | `navigate_back` | Navigate back in browser history |
| `tools/web_browser` | `navigate_forward` | `navigate_forward` | Navigate forward in browser history |
| `tools/web_browser` | `reload_page` | `reload_page` | Reload the current webpage |
| `tools/web_browser` | `wait_time` | `wait_time <ms>` | Wait for the specified number of milliseconds |
| `tools/web_browser` | `press_keys_on_page` | `press_keys_on_page <keys>` | Press keys, JSON array e.g. `["ctrl","c"]` |
| `tools/web_browser` | `set_browser_window_size` | `set_browser_window_size <width> <height>` | Set browser window size |
| `tools/web_browser` | `get_console_output` | `get_console_output` | Get console output messages (logs, errors, warnings) |

Bundle configs: `tools/edit_anthropic/config.yaml`, `tools/windowed/config.yaml`, `tools/windowed_edit_linting/config.yaml`, `tools/windowed_edit_replace/config.yaml`, `tools/windowed_edit_rewrite/config.yaml`, `tools/search/config.yaml`, `tools/submit/config.yaml`, `tools/review_on_submit_m/config.yaml`, `tools/forfeit/config.yaml`, `tools/filemap/config.yaml`, `tools/image_tools/config.yaml`, `tools/diff_state/config.yaml`, `tools/multilingual_setup/config.yaml`, `tools/registry/config.yaml`, `tools/web_browser/config.yaml`.

> **Naming note (H3-adjacent):** bundle names in this checkout differ from older docs/blog posts. Changelog 1.1.0: "Renamed many tool bundles that used 'windowed' file viewer (`defaults` and more)" and "Removed `review_on_submit` tool bundle (replaced by `review_on_submit_m`)" (`docs/installation/changelog.md:13-14`). There is no `defaults`, `edit_linting`, or `edit_replace` bundle here — they are `windowed`, `windowed_edit_linting`, `windowed_edit_replace`.

### 8.3 `bash` — VERBATIM

```python
# Default Bash tool
BASH_COMMAND = Command(
    name="bash",
    # name="execute_bash",
    signature="<command>",
    # signature="echo '<command>'\n<command>\necho \"root@workspace:${{PWD}} #\n[Command finished with exit code ${{?}}]\"",
    docstring="runs the given command directly in bash",
    arguments=[
        Argument(
            name="command",
            type="string",
            description="The bash command to execute.",
            required=True,
        )
    ],
)
```
(`sweagent/tools/commands.py:208-223`) — injected when `enable_bash_tool: True` (default, `sweagent/tools/tools.py:116-117`, `:173-175`).

### 8.4 `tools/windowed` — the windowed file viewer, VERBATIM

```yaml
tools:
  goto:
    signature: "goto <line_number>"
    docstring: "moves the window to show <line_number>"
    arguments:
      - name: line_number
        type: integer
        description: "the line number to move the window to"
        required: true
  open:
    signature: 'open "<path>" [<line_number>]'
    docstring: "opens the file at the given path in the editor. If line_number is provided, the window will be move to include that line"
    arguments:
      - name: path
        type: string
        description: "the path to the file to open"
        required: true
      - name: line_number
        type: integer
        description: "the line number to move the window to (if not provided, the window will start at the top of the file)"
        required: false
  create:
    signature: "create <filename>"
    docstring: "creates and opens a new file with the given name"
    arguments:
      - name: filename
        type: string
        description: "the name of the file to create"
        required: true
  scroll_up:
    signature: "scroll_up"
    docstring: "moves the window up {WINDOW} lines"
    arguments: []
  scroll_down:
    signature: "scroll_down"
    docstring: "moves the window down {WINDOW} lines"
    arguments: []
state_command: "_state"
```
(`tools/windowed/config.yaml:1-38`, complete file)

`{WINDOW}` in the docstrings is `.format(**env_variables)`-substituted at doc-generation time (`sweagent/tools/utils.py:96`), from `env_variables: {WINDOW: 100, OVERLAP: 2}` (`config/sweagent_0_7/07.yaml:88-90`).

### 8.5 The "windowed file viewer" ACI concept

The design rationale, verbatim from the docs:

> "SWE-agent is built on the idea of an **Agent-Computer Interface** (ACI). An ACI is essentially an a set of tools and interaction format that allows an agent to interact with a computer-based environment...
>
> Just like how typical language models requires good prompt engineering, **good ACI design leads to much better results when using agents**. As we show in the SWE-agent [paper](https://arxiv.org/abs/2405.15793), a baseline agent without a well-tuned ACI does much worse than SWE-agent.
>
> SWE-agent contains features that we discovered to be immensely helpful during the agent-computer interface design process:
>
> 1. We add a **linter** that runs when an edit command is issued, and do not let the edit command go through if the code isn't syntactically correct.
> 2. We supply the agent with a **special-built file viewer**, instead of having it just `cat` files. We found that this file viewer works best when displaying just 100 lines in each turn. The **file editor** that we built has commands for scrolling up and down and for performing a search within the file.
> 3. We supply the agent with a special-built full-directory string **searching command**. We found that it was important for this tool to succinctly list the matches- we simply list each file that had at least one match. Showing the model more context about each match proved to be too confusing for the model.
> 4. When commands have an empty output we return a message saying 'Your command ran successfully and did not produce any output.'"
> — `docs/background/aci.md:1-14`

Mechanically, the viewer is a **stateless CLI over a persisted cursor**. Nothing lives in shell variables; everything is in `/root/.swe-agent-env` (registry) and `/root/state.json` (state).

```python
class WindowedFile:
    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        first_line: Optional[int] = None,
        window: Optional[int] = None,
        exit_on_exception: bool = True,
    ):
        """
        ...
        Internal convention/notes:

        * All line numbers are 0-indexed.
        * Previously, we used "current_line" for the internal state
          of the window position, pointing to the middle of the window.
          Now, we use `first_line` for this purpose (it's simpler this way).
        """
        _path = registry.get_if_none(path, "CURRENT_FILE")
        ...
        registry["CURRENT_FILE"] = str(self.path.resolve())
        self.window = int(registry.get_if_none(window, "WINDOW"))
        self.overlap = int(registry.get("OVERLAP", 0))
        # Ensure that we get a valid current line by using the setter
        self._first_line = 0
        self.first_line = int(
            registry.get_if_none(
                first_line,
                "FIRST_LINE",
                0,
            )
        )
        self.offset_multiplier = 1 / 6
```
(`tools/windowed/lib/windowed_file.py:53-115`)

Window clamping + persistence in the property setter:

```python
    @first_line.setter
    def first_line(self, value: Union[int, float]):
        self._original_first_line = self.first_line
        value = int(value)
        self._first_line = max(0, min(value, self.n_lines - self.window))
        registry["FIRST_LINE"] = self.first_line
```
(`tools/windowed/lib/windowed_file.py:120-125`)

Rendering — this is exactly what the model sees (`[File: ... (N lines total)]`, `(N more lines above)`, `nnn:line`, `(N more lines below)`):

```python
    def get_window_text(
        self, *, line_numbers: bool = False, status_line: bool = False, pre_post_line: bool = False
    ) -> str:
        start_line, end_line = self.line_range
        lines = self.text.split("\n")[start_line : end_line + 1]
        out_lines = []
        if status_line:
            out_lines.append(f"[File: {self.path} ({self.n_lines} lines total)]")
        if pre_post_line:
            if start_line > 0:
                out_lines.append(f"({start_line} more lines above)")
        if line_numbers:
            out_lines.extend(f"{i + start_line + 1}:{line}" for i, line in enumerate(lines))
        else:
            out_lines.extend(lines)
        if pre_post_line:
            if end_line < self.n_lines - 1:
                out_lines.append(f"({self.n_lines - end_line - 1} more lines below)")
        return "\n".join(out_lines)
```
(`tools/windowed/lib/windowed_file.py:150-175`)

`goto` deliberately puts the target line ~1/6 down the window rather than at the top, and `scroll` honours `OVERLAP`:

```python
    def goto(self, line: int, mode: str = "top"):
        if mode == "top":
            self.first_line = line - self.window * self.offset_multiplier
        else:
            raise NotImplementedError

    def scroll(self, n_lines: int):
        if n_lines > 0:
            self.first_line += n_lines - self.overlap
        elif n_lines < 0:
            self.first_line += n_lines + self.overlap
```
(`tools/windowed/lib/windowed_file.py:264-274`)

Error guards worth noting: opening a directory yields `"Error: {path} is a directory. You can only open files. Use cd or ls to navigate directories."` (`:88-93`); no file open yields `"No file open. Use the open command first."` (`:82-86`).

The three `bin/` entry points, verbatim:

```python
#!/usr/bin/env python3

from windowed_file import WindowedFile  # type: ignore


def main():
    wf = WindowedFile()
    wf.scroll(-wf.window)
    wf.print_window()


if __name__ == "__main__":
    main()
```
(`tools/windowed/bin/scroll_up:1-13`; `tools/windowed/bin/scroll_down:1-12` is identical with `+wf.window`)

```python
def main(args: List[str]) -> int:
    if len(args) > 1:
        print("goto allows only one line number at a time.")
        return 1

    if not args:
        print("Usage: goto <line>")
        return 1

    try:
        line_number = int(args[0])
    except ValueError:
        print("Usage: goto <line>")
        print("Error: <line> must be a number")
        return 1

    wf = WindowedFile()

    if line_number > wf.n_lines:
        print(f"Error: <line> must be less than or equal to {wf.n_lines}")
        return 1

    # Convert from 1-based line numbers (user input) to 0-based (internal representation)
    wf.goto(line_number - 1, mode="top")
    wf.print_window()
    return 0
```
(`tools/windowed/bin/goto:8-33`)

```python
def main(path: Optional[str] = None, line_number: Optional[str] = None) -> None:
    if path is None:
        try:
            WindowedFile(exit_on_exception=False).print_window()
            # If this passes, then there was already a file open and we just show it again
            sys.exit(0)
        except FileNotOpened:
            print('Usage: open "<file>"')
            sys.exit(1)

    assert path is not None

    wf = WindowedFile(path=path)

    if line_number is not None:
        try:
            line_num = int(line_number)
        except ValueError:
            print('Usage: open "<file>" [<line_number>]')
            print("Error: <line_number> must be a number")
            sys.exit(1)
        if line_num > wf.n_lines:
            print(f"Warning: <line_number> ({line_num}) is greater than the number of lines in the file ({wf.n_lines})")
            print(f"Warning: Setting <line_number> to {wf.n_lines}")
            line_num = wf.n_lines
        elif line_num < 1:
            print(f"Warning: <line_number> ({line_num}) is less than 1")
            print("Warning: Setting <line_number> to 1")
            line_num = 1
    else:
        # Default to middle of window if no line number provided
        line_num = wf.first_line

    wf.goto(line_num - 1, mode="top")
    wf.print_window()
```
(`tools/windowed/bin/open:8-42`)

```python
def main():
    if len(sys.argv) < 2:
        print("Usage: create <filename>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        print(f"Warning: File '{path}' already exists.")
        sys.exit(1)

    path.touch()

    wfile = WindowedFile(path=path)
    wfile.first_line = 0
    wfile.print_window()
```
(`tools/windowed/bin/create:8-25`)

### 8.6 Editors

**`tools/windowed_edit_linting` — `edit` (the linter-gated line-range editor), VERBATIM config:**

```yaml
tools:
  edit:
    signature: |
      edit <start_line>:<end_line>
      <replacement_text>
      end_of_edit
    # Note: Without function calling we should add back:
    # The replacement text is terminated by a line with only
    # end_of_edit on
    docstring: >
      Replaces lines <start_line> through <end_line> (inclusive) with the given text
      in the open file.
      All of the <replacement text> will be entered, so make
      sure your indentation is formatted properly.

      Please note that THIS COMMAND REQUIRES PROPER INDENTATION.
      If you'd like to add the line '        print(x)' you must fully write that out, with all those spaces before the code!
    end_name: "end_of_edit"
    arguments:
      - name: start_line
        type: integer
        description: "the line number to start the edit at"
        required: true
      - name: end_line
        type: integer
        description: "the line number to end the edit at (inclusive)"
        required: true
      - name: replacement_text
        type: string
        description: "the text to replace the current selection with"
        required: true
```
(`tools/windowed_edit_linting/config.yaml:1-32`, complete file)

The refusal template (the ACI "linter gate"):

```python
_EDIT_SUCCESS_MSG = """File updated. Please review the changes and make sure they are correct
(correct indentation, no duplicate lines, etc). Edit the file again if necessary."""

_LINT_ERROR_TEMPLATE = """Your proposed edit has introduced new syntax error(s). Please read this error message carefully and then retry editing the file.

ERRORS:
{errors}

This is how your edit would have looked if applied
------------------------------------------------
{window_applied}
------------------------------------------------

This is the original code before your edit
------------------------------------------------
{window_original}
------------------------------------------------

Your changes have NOT been applied. Please fix your edit command and try again.
DO NOT re-run the same failed edit command. Running it again will lead to the same error."""
```
(`tools/windowed_edit_linting/bin/edit:24-43`)

**`tools/windowed_edit_replace` — `edit` and `insert`, VERBATIM:**

```yaml
tools:
  edit:
    signature: |
      edit <search> <replace> [<replace-all>]
    docstring: >
      Replace first occurrence of <search> with <replace> in the currently displayed lines.
      If replace-all is True , replace all occurrences of <search> with <replace>.

      For example, if you are looking at this file:

      def fct():
          print("Hello world")

      and you want to edit the file to read:

      def fct():
          print("Hello")
          print("world")

      you can search for `Hello world` and replace with `"Hello"\n    print("world")`
      (note the extra spaces before the print statement!).

      Tips:

      1. Always include proper whitespace/indentation
      2. When you are adding an if/with/try statement, you need to INDENT the block that follows, so make sure to include it in both your search and replace strings!
      3. If you are wrapping code in a try statement, make sure to also add an 'except' or 'finally' block.

      Before every edit, please

      1. Explain the code you want to edit and why it is causing the problem
      2. Explain the edit you want to make and how it fixes the problem
      3. Explain how the edit does not break existing functionality
    arguments:
      - name: search
        type: string
        description: "the text to search for (make sure to include proper whitespace if needed)"
        required: true
      - name: replace
        type: string
        description: "the text to replace the search with (make sure to include proper whitespace if needed)"
        required: true
      - name: replace-all
        type: boolean
        description: "replace all occurrences rather than the first occurrence within the displayed lines"
        required: false
  insert:
    signature: |
      insert <text> [<line>]
    docstring: >
      Insert <text> at the end of the currently opened file or after <line> if specified.
    arguments:
      - name: text
        type: string
        description: "the text to insert"
        required: true
      - name: line
        type: integer
        description: "the line number to insert the text as new lines after"
        required: false
```
(`tools/windowed_edit_replace/config.yaml:1-60`, complete file)

**`tools/windowed_edit_rewrite` — `edit`, VERBATIM:**

```yaml
tools:
  edit:
    signature: |
      edit <text>
    docstring: >
      Replace the currently displayed lines with <text>.
    arguments:
      - name: text
        type: string
        description: "the text to replace the currently displayed lines with"
        required: true
```
(`tools/windowed_edit_rewrite/config.yaml:1-11`, complete file)

**`tools/edit_anthropic` — `str_replace_editor`, VERBATIM (this is the default editor in `config/default.yaml`):**

```yaml
tools:
  str_replace_editor:
    signature: |
      str_replace_editor <command> <path> [<file_text>] [<view_range>] [<old_str>] [<new_str>] [<insert_line>]
    # This docstrings was taken from openhands:
    # https://github.com/All-Hands-AI/OpenHands/blob/main/openhands/agenthub/codeact_agent/function_calling.py
    docstring: >
      Custom editing tool for viewing, creating and editing files
      * State is persistent across command calls and discussions with the user
      * If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
      * The `create` command cannot be used if the specified `path` already exists as a file
      * If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
      * The `undo_edit` command will revert the last edit made to the file at `path`

      Notes for using the `str_replace` command:
      * The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
      * If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
      * The `new_str` parameter should contain the edited lines that should replace the `old_str`
    arguments:
      - name: command
        type: string
        description: "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`."
        required: true
        enum: ["view", "create", "str_replace", "insert", "undo_edit"]
      - name: path
        type: string
        description: "Absolute path to file or directory, e.g. `/testbed/file.py` or `/testbed`."
        required: true
      - name: file_text
        type: string
        description: "Required parameter of `create` command, with the content of the file to be created."
        required: false
        argument_format: "--file_text {{value}}"
      - name: old_str
        type: string
        description: "Required parameter of `str_replace` command containing the string in `path` to replace."
        required: false
        argument_format: "--old_str {{value}}"
      - name: new_str
        type: string
        description: "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert."
        required: false
        argument_format: "--new_str {{value}}"
      - name: insert_line
        type: integer
        description: "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`."
        required: false
        argument_format: "--insert_line {{value}}"
      - name: view_range
        type: array
        items:
          type: integer
        description: "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file."
        required: false
        argument_format: "--view_range {{value|join(' ')}}"
state_command: "_state_anthropic"
```
(`tools/edit_anthropic/config.yaml:1-56`, complete file)

Implementation notes (`tools/edit_anthropic/bin/str_replace_editor`, 712 lines):

- Header: "This is an adaptation of the Anthropic Text Editor tool ... However, we made it python 3.6 compatible and **stateless (all state is saved in a json file)**" (`:3-6`).
- `MAX_RESPONSE_LEN = 16000`; truncation notice: `"<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>"` (`:27-28`).
- Registry-driven behaviour flags: `MAX_WINDOW_EXPANSION_VIEW`, `MAX_WINDOW_EXPANSION_EDIT_CONFIRM`, `USE_FILEMAP`, `USE_LINTER` (`:30-33`).
- `SNIPPET_LINES = 4` — after every edit the tool echoes a ±4-line snippet with `cat -n` numbering (`:35`, `:579-591`).
- Uniqueness guard on `str_replace` (a real anti-ambiguity ACI feature):
  ```python
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            print("No replacement was performed, old_str `{}` did not appear verbatim in {}.".format(old_str, path))
            sys.exit(15)
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [idx + 1 for idx, line in enumerate(file_content_lines) if old_str in line]
            print(
                "No replacement was performed. Multiple occurrences of old_str `{}` in lines {}. Please ensure it is unique".format(old_str, lines)
            )
            sys.exit(16)

        if new_str == old_str:
            print("No replacement was performed, old_str `{}` is the same as new_str `{}`.".format(old_str, new_str))
            sys.exit(161)
  ```
  (`:523-538`)
- Optional post-edit flake8 warning (non-blocking, unlike `windowed_edit_linting`):
  ```python
  LINT_WARNING_TEMPLATE = """

  <NOTE>Your edits have been applied, but the linter has found syntax errors.</NOTE>

  <ERRORS>
  {errors}
  </ERRORS>

  Please review the changes and make sure they are correct.
  In addition to the above errors, please also check the following:

  1. The edited file is correctly indented
  2. The edited file does not contain duplicate lines
  3. The edit does not break existing functionality

  <IMPORTANT>In rare cases, the linter errors might not actually be errors or caused by your edit. Please use your own judgement.</IMPORTANT>

  Edit the file again if necessary.
  """
  ```
  (`:36-54`)
- `view` on a directory: `find <path> -maxdepth 2 -not -path '*/\.*'` (`:445-457`).
- **Filemap fallback** when a `.py` file is too big and `USE_FILEMAP` is on:
  ```python
            if path.suffix == ".py" and len(file_content) > MAX_RESPONSE_LEN and USE_FILEMAP:
                ...
                    print(
                        "<NOTE>This file is too large to display entirely. Showing abbreviated version. "
                        "Please use `str_replace_editor view` with the `view_range` parameter to show selected lines next.</NOTE>"
                    )
                    filemap = maybe_truncate(filemap.expandtabs())
                    print(filemap)
                    print(
                        "<IMPORTANT><NOTE>The above file has been abbreviated. Please use `str_replace editor view` with `view_range` to look at relevant files in detail.</NOTE></IMPORTANT>"
                    )
  ```
  (`:493-509`)
- **Window expansion**: viewing a range auto-expands to whole functions/classes via `WindowExpander` (`:487-489`, `:583-585`).
- Output format:
  ```python
        file_content = "\n".join(["{:6}\t{}".format(i + init_line, line) for i, line in enumerate(file_content.split("\n"))])
        return "Here's the result of running `cat -n` on {}:\n".format(file_descriptor) + file_content + "\n"
  ```
  (`:685-686`)
- `undo_edit` pops from an in-file history: `"No edit history found for {}."` (`:634-643`).
- Path validation returns distinct exit codes 6/7/8/9 for non-absolute / missing / already-exists / is-a-directory (`:406-428`).

### 8.7 Search, submit, forfeit, filemap, image, diff-state — VERBATIM

```yaml
tools:
  find_file:
    signature: "find_file <file_name> [<dir>]"
    docstring: "finds all files with the given name or pattern in dir. If dir is not provided, searches in the current directory"
    arguments:
      - name: file_name
        type: string
        description: "the name of the file or pattern to search for. supports shell-style wildcards (e.g. *.py)"
        required: true
      - name: dir
        type: string
        description: "the directory to search in (if not provided, searches in the current directory)"
        required: false
  search_dir:
    signature: "search_dir <search_term> [<dir>]"
    docstring: "searches for search_term in all files in dir. If dir is not provided, searches in the current directory"
    arguments:
      - name: search_term
        type: string
        description: "the term to search for"
        required: true
      - name: dir
        type: string
        description: "the directory to search in (if not provided, searches in the current directory)"
        required: false
  search_file:
    signature: "search_file <search_term> [<file>]"
    docstring: "searches for search_term in file. If file is not provided, searches in the current open file"
    arguments:
      - name: search_term
        type: string
        description: "the term to search for"
        required: true
      - name: file
        type: string
        description: "the file to search in (if not provided, searches in the current open file)"
        required: false
```
(`tools/search/config.yaml:1-37`, complete file)

`search_dir` implements the ACI principle "we simply list each file that had at least one match": it groups by filename with a per-file count, and **hard-refuses** over-broad searches:

```bash
    local matches=$(find "$dir" -type f ! -path '*/.*' -exec grep -nIH -- "$search_term" {} + | cut -d: -f1 | sort | uniq -c)
    ...
    if [ $num_files -gt 100 ]; then
        echo "More than $num_files files matched for \"$search_term\" in $dir. Please narrow your search."
        return
    fi

    echo "Found $num_matches matches for \"$search_term\" in $dir:"
    echo "$matches" | awk '{$2=$2; gsub(/^\.+\/+/, "./", $2); print $2 " ("$1" matches)"}'
    echo "End of matches for \"$search_term\" in $dir"
```
(`tools/search/bin/search_dir:18-36`)

`search_file` similarly caps at 100 matching lines and prints `Line N:<content>` (`tools/search/bin/search_file:42-52`). `search_file` falls back to the currently open file via `_read_env CURRENT_FILE` (`:19-25`) — a direct dependency on the `registry` bundle.

```yaml
tools:
  submit:
    signature: "submit"
    docstring: "submits the current file"
    arguments: []
```
(`tools/submit/config.yaml:1-5`, complete file)

```yaml
tools:
  submit:
    signature: "submit"
    docstring: "submits the current file"
    # Do not actually show the -f argument to the model, only
    # use it from the agent for submission after error
```
(`tools/review_on_submit_m/config.yaml:1-6`, complete file)

```yaml
tools:
  exit_forfeit:
    signature: "exit_forfeit"
    docstring: "Give up on the current challenge and terminate the session."
    arguments: []
```
(`tools/forfeit/config.yaml:1-5`, complete file) — implementation is one echo of the control token:
```bash
main() {
    echo "###SWE-AGENT-EXIT-FORFEIT###"
}

main "$@"
```
(`tools/forfeit/bin/exit_forfeit:1-5`)

```yaml
tools:
  filemap:
    signature: "filemap <file_path>"
    docstring: "Print the contents of a Python file, skipping lengthy function and method definitions."
    arguments:
      - name: file_path
        type: string
        description: The path to the file to be read
        required: true
```
(`tools/filemap/config.yaml:1-9`, complete file) — tree-sitter based; elides function bodies ≥ 5 lines, printing `... eliding lines {start+1}-{end+1} ...` (`tools/filemap/bin/filemap:25-45`).

```yaml
tools:
  view_image:
    signature: "view_image <image_file>"
    docstring: "view an image file"
    arguments:
      - name: image_file
        type: string
        description: "the path to the image file to view"
        required: true
```
(`tools/image_tools/config.yaml:1-9`, complete file) — prints `![{path}](data:{mime};base64,{b64})` for png/jpeg/webp (`tools/image_tools/bin/view_image:8-34`), which the `image_parsing` history processor then converts to a multimodal message part.

```yaml
tools: {}
state_command: "_state_diff_state"
```
(`tools/diff_state/config.yaml:1-2`, complete file) — a **tool-less bundle** that exists purely for state:

```python
    subprocess.run(
        f"git add -A && git diff --cached > {patch_path}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=repo_root,
    )

    patch = patch_path.read_text(errors="backslashreplace")
    state["diff"] = patch.strip()

    state_path.write_text(json.dumps(state))
```
(`tools/diff_state/bin/_state_diff_state:21-32`) — this is what makes `{{diff}}` available in `next_step_template` (see `config/benchmarks/250212_sweagent_heavy_sbl.yaml:101-119`) and what rescues a submission from a dead container (§7.2).

### 8.8 The state mechanism (`_state`, `/root/state.json`) and the registry

Docs: "The `state` command is a special command that is executed after every action and returns a json string that we parse. The resulting dictionary can be used to format prompt templates." (`docs/config/tools.md:46-48`).

```python
#!/usr/bin/env python3

import json
import os
from pathlib import Path

from registry import registry  # type: ignore


def main():
    state_path = Path("/root/state.json")

    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {}

    current_file = registry.get("CURRENT_FILE")
    open_file = "n/a" if not current_file else str(Path(current_file).resolve())
    state["open_file"] = open_file
    state["working_dir"] = os.getcwd()
    state_path.write_text(json.dumps(state))

if __name__ == "__main__":
    main()
```
(`tools/windowed/bin/_state:1-25`, complete file)

```python
#!/usr/bin/env python3

import json
import os
from pathlib import Path


def main():
    state_path = Path("/root/state.json")
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {}

    state["working_dir"] = os.getcwd()

    state_path.write_text(json.dumps(state))
```
(`tools/edit_anthropic/bin/_state_anthropic:1-17`) — this is the sole source of `{{working_dir}}` in `config/default.yaml`.

Harness side — every bundle's state command runs each turn and their writes are merged by virtue of sharing one file:

```python
    def get_state(self, env: SWEEnv) -> dict[str, str]:
        """Execute state commands from all bundles and combine their results.
        This can be used to extract environment variables etc. from the environment.
        """
        if self.mock_state is not None:
            return self.mock_state

        for state_command in self.config.state_commands:
            env.communicate(state_command, check="warn")
        combined_state = self._get_state(env)
        self.logger.debug(f"Retrieved state from environment: {combined_state}")
        return combined_state
```
(`sweagent/tools/tools.py:337-348`; `_get_state` at `:317-335` hard-errors on non-dict / invalid JSON.)

The registry itself (the cross-process state store):

```python
class EnvRegistry:
    """Read and write variables into a file. This is used to persist state between tool
    calls without using environment variables (which are problematic because you cannot
    set them in a subprocess).

    The default file location is `/root/.swe-agent-env`, though this can be overridden
    by the `env_file` argument or the `SWE_AGENT_ENV_FILE` environment variable.
    """
    ...
    def get(self, key: str, default_value: Any = None, fallback_to_env: bool = True) -> Any:
        """Get a value from registry:
        ...
        """
        if fallback_to_env and key in os.environ:
            default_value = os.environ[key]
        return json.loads(self.env_file.read_text()).get(key, default_value)
```
(`tools/registry/lib/registry.py:7-43`)

Registry keys observed in use: `CURRENT_FILE`, `FIRST_LINE`, `WINDOW`, `OVERLAP`, `ROOT`, `PROBLEM_STATEMENT`, `USE_FILEMAP`, `USE_LINTER`, `MAX_WINDOW_EXPANSION_VIEW`, `MAX_WINDOW_EXPANSION_EDIT_CONFIRM`, `SUBMIT_REVIEW_MESSAGES`, `SUBMIT_STAGE`.

### 8.9 Action parsing and malformed-action handling

Parser union (`sweagent/tools/parsing.py:609-621`):

```python
ParseFunction = (
    ActionParser
    | ThoughtActionParser
    | ActionOnlyParser
    | XMLThoughtActionParser
    | XMLFunctionCallingParser
    | FunctionCallingParser
    | EditFormat
    | Identity
    | JsonParser
    | BashCodeBlockParser
    | SingleBashCodeBlockParser
)
```

| Class | `type` | Expected model output | Cite |
|---|---|---|---|
| `ActionParser` | `action` | a single command, first word must be a known tool | `sweagent/tools/parsing.py:72-94` |
| `ActionOnlyParser` | `action_only` | whole message is the action, no thought | `:97-106` |
| `ThoughtActionParser` | `thought_action` | prose + last non-nested ```` ``` ```` block | `:109-165` |
| `XMLThoughtActionParser` | `xml_thought_action` | prose + last `<command>...</command>` | `:168-218` |
| `XMLFunctionCallingParser` | `xml_function_calling` | `<function=name><parameter=k>v</parameter></function>` | `:225-321` |
| `FunctionCallingParser` | `function_calling` | native LiteLLM tool call, exactly one | `:371-454` |
| `EditFormat` | `edit_format` | subclass of `ThoughtActionParser` for whole-window rewrites | `:324-351` |
| `Identity` | `identity` | no parsing at all | `:354-368` |
| `JsonParser` | `json` | `{"thought": ..., "command": {"name":..., "arguments": {...}}}` | `:457-540` |
| `BashCodeBlockParser` | `all_bash_code_blocks` | executes **all** ```` ```bash ```` blocks | `:543-571` |
| `SingleBashCodeBlockParser` | `single_bash_code_block` | requires **exactly one** ```` ```bash ```` block | `:574-606` |

Default is `FunctionCallingParser` (`sweagent/tools/tools.py:112-114`).

**Format-error templates** are Jinja and branch on `error_code`. `FunctionCallingParser`'s, verbatim:

```python
    error_message: str = dedent("""\
    {%- if error_code == "missing" -%}
    Your last output did not use any tool calls!
    Please make sure your output includes exactly _ONE_ function call!
    You must invoke the function directly using the function call format.
    You cannot invoke commands with ```, you have to use the function call format.
    If you think you have already resolved the issue, please submit your changes by running the `submit` command.
    If you think you cannot solve the problem, please run `exit_forfeit` (if available) or `submit`.
    Else, please continue with a new tool call!
    {%- elif error_code == "multiple" -%}
    Your last output included multiple tool calls!
    Please make sure your output includes a thought and exactly _ONE_ function call.
    {%- elif error_code == "unexpected_arg" -%}
    Your action could not be parsed properly: {{exception_message}}.
    Make sure your function call doesn't include any extra arguments that are not in the allowed arguments, and only use the allowed commands.
    {%- else -%}
    Your action could not be parsed properly: {{exception_message}}.
    {% endif %}
    """)
```
(`sweagent/tools/parsing.py:374-392`)

`ThoughtActionParser`'s:

```python
    error_message: str = dedent("""\
    Your output was not formatted correctly. You must always include one discussion and one command as part of your response. Make sure you do not have multiple discussion/command tags.
    Please make sure your output precisely matches the following format:
    DISCUSSION
    Discuss here with yourself about what your planning and what you're going to do in this step.

    ```
    command(s) that you're going to run
    ```
    """)
```
(`sweagent/tools/parsing.py:119-128`)

The validation performed on every parsed call (missing args, unexpected args, invalid JSON, unknown command → `FunctionCallingFormatError` with a typed `error_code`) is at `sweagent/tools/parsing.py:397-454`. Note the leniency for multi-line commands: `"sometimes the model will include the end_name in the arguments - just ignore it"` (`:418-420`).

**Requery loop.** Format errors, blocked actions, and bash syntax errors requery up to `max_requeries` (default 3); the bad turn is *not* kept in history if the model recovers, but *is* kept in the trajectory:

```python
    def get_model_requery_history(
        self, error_template: str, *, output: str, **kwargs: str | int | float | bool | None
    ) -> list[dict[str, str]]:
        """Ask the model to correct after a hitting one of the following errors:

        1. Malformatted output (could not parse action)
        2. Blocked action (command is on the blocklist)
        3. Bash command syntax error

        At the time this function is called, the proposed action and observation are not part of the history
        yet.

        This function adds temporary history based on the error template and queries the model.
        If the model is able to correct itself, the records of the mistakes will not be part of the history
        (but they are saved in the trajectory).
        """
```
(`sweagent/agent/agents.py:789-812`)

**Multi-line commands via heredoc.** Commands with an `end_name` (e.g. `edit ... end_of_edit`) get rewritten into a heredoc before execution:

```python
    def guard_multiline_input(self, action: str) -> str:
        """Split action by multiline commands, then append the first line in each multiline command with "<< '{end_name}'".
        Multiline commands (which are specified by an end_name) are commands that span multiple lines and are terminated by a specific end_name.

        Their multi-line argument is sent using a heredoc, which is a way to send a multi-line string to a command in bash.
        """
```
(`sweagent/tools/tools.py:382-388`; implementation `sweagent/tools/utils.py:8-36`)

Argument shell-quoting rule (bash is never quoted, multi-line commands are never quoted):

```python
def _should_quote(value: Any, command: Command) -> bool:
    """Returns True if the value should be quoted, False otherwise."""
    if command.name == "bash":
        return False
    return isinstance(value, str) and command.end_name is None
```
(`sweagent/tools/utils.py:39-43`)

### 8.10 THE BLOCKLIST (reward-hacking / safety / stability guard) — VERBATIM

```python
class ToolFilterConfig(BaseModel):
    """Filter out commands that are blocked by the environment
    (for example interactive commands like `vim`).
    """

    blocklist_error_template: str = "Operation '{{action}}' is not supported by this environment."
    """The error template to use when a command is blocked."""

    blocklist: list[str] = [
        "vim",
        "vi",
        "emacs",
        "nano",
        "nohup",
        "gdb",
        "less",
        "tail -f",
        "python -m venv",
        "make",
    ]
    """Block any command that starts with one of these"""

    blocklist_standalone: list[str] = [
        "python",
        "python3",
        "ipython",
        "bash",
        "sh",
        "/bin/bash",
        "/bin/sh",
        "nohup",
        "vi",
        "vim",
        "emacs",
        "nano",
        "su",
    ]
    """Block any command that matches one of these exactly"""

    block_unless_regex: dict[str, str] = {
        "radare2": r"\b(?:radare2)\b.*\s+-c\s+.*",
        "r2": r"\b(?:radare2)\b.*\s+-c\s+.*",
    }
    """Block any command that matches one of these names unless it also matches the regex"""
```
(`sweagent/tools/tools.py:29-72`, complete class)

Enforcement:

```python
    def should_block_action(self, action: str) -> bool:
        """Check if the command should be blocked."""
        action = action.strip()
        if not action:
            return False
        if any(action.startswith(f) for f in self.config.filter.blocklist):
            return True
        if action in self.config.filter.blocklist_standalone:
            return True
        name = action.split()[0]
        if name in self.config.filter.block_unless_regex and not re.search(
            self.config.filter.block_unless_regex[name], action
        ):
            return True
        return False
```
(`sweagent/tools/tools.py:353-367`)

Raised as `_BlockedActionError` at the top of `handle_action` (`sweagent/agent/agents.py:946-947`), which requeries with `blocklist_error_template`.

**Reading of the blocklist.** The three lists encode three different concerns:
1. `blocklist` (prefix match) — **interactive/hanging programs** (`vim`, `vi`, `emacs`, `nano`, `less`, `tail -f`, `gdb`) plus two *semantic* blocks: `nohup` (background/detached processes escape the observation loop) and `make` / `python -m venv` (heavyweight state-mutating operations that historically wedged SWE-bench environments).
2. `blocklist_standalone` (exact match) — bare REPLs (`python`, `python3`, `ipython`, `bash`, `sh`, `/bin/bash`, `/bin/sh`) which would swallow the session, plus `su` (privilege/identity change).
3. `block_unless_regex` — the **EnIGMA residue**: `radare2`/`r2` (a reverse-engineering disassembler used in CTF tasks) are permitted *only* in scripted, non-interactive form, i.e. when invoked with `-c <command>`.

Note this blocklist is a *stability* guard first and an *anti-reward-hacking* guard second; the real anti-reward-hacking guards are elsewhere: (a) the review-on-submit checklist telling the agent to `git checkout --` any modified TEST files (`config/default.yaml:55-56`), (b) `submit`'s reverse-application of `/root/test.patch` (`tools/submit/bin/submit:5-8`), and (c) the chooser prompt's "Disregard all testing code in the patch... Having a test in the patch does not make it any better" (`config/benchmarks/250212_sweagent_heavy_sbl.yaml:149-150`).

### 8.11 Environment-variable hardening (anti-pager / anti-progress-bar)

```python
    env_variables: dict[str, Any] = {
        "PAGER": "cat",
        "MANPAGER": "cat",
        "LESS": "-R",
        "PIP_PROGRESS_BAR": "off",
        "TQDM_DISABLE": "1",
        "GIT_PAGER": "cat",
    }
```
(`sweagent/tools/tools.py:94-101`; also set at deployment init: `{"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PIP_PROGRESS_BAR": "off", "PAGER": "cat"}`, `sweagent/environment/swe_env.py:189`)

These exist because pagers block forever and progress bars flood the observation with ANSI noise — both are ACI failure modes.

---

## 9. Notable quotes / raw excerpts

### 9.1 Trajectory (`.traj`) format

Top-level keys, confirmed empirically from `trajectories/demonstrations/replay__marshmallow-code__marshmallow-1867__function_calling__install-1/marshmallow-code__marshmallow-1867.traj`: `["environment", "trajectory", "history", "info", "replay_config"]`.

```python
    def get_trajectory_data(self) -> dict[str, Any]:
        """Get all data that we save in .traj files."""

        assert self._env is not None
        # The deepcopy here is important because else the
        # data["info"]["model_stats"] update will create havoc!
        attempt_data = copy.deepcopy(
            {
                "trajectory": self.trajectory,
                "history": self.history,
                "info": self.info,
            }
        )
        attempt_data["replay_config"] = self.replay_config.model_dump_json() if self.replay_config is not None else None
        attempt_data["environment"] = self._env.name
        return attempt_data
```
(`sweagent/agent/agents.py:762-777`)

Per-step record:

```python
class TrajectoryStep(TypedDict):
    action: str
    observation: str
    response: str
    state: dict[str, str]
    thought: str
    execution_time: float
    query: list[dict[str, Any]]
    extra_info: dict[str, Any]
```
(`sweagent/types.py:44-52`)

Info record:

```python
class AgentInfo(TypedDict, total=False):
    # same as `APIStats` from models.py
    model_stats: dict[str, float]
    exit_status: str | None
    submission: str | None
    # same as `ReviewerResult`
    review: dict[str, Any]
    edited_files30: str
    edited_files50: str
    edited_files70: str
    # only if summarizer is used
    summarizer: dict
    swe_agent_hash: str
    swe_agent_version: str
    swe_rex_version: str
    swe_rex_hash: str
```
(`sweagent/types.py:82-97`) — provenance fields are stamped at setup (`sweagent/agent/agents.py:596-599`).

History item:

```python
class HistoryItem(_HistoryItem, total=False):
    agent: str
    is_demo: bool
    thought: str
    action: str | None
    tool_calls: list[dict[str, str]] | None
    tool_call_ids: list[str] | None
    tags: list[str]
    cache_control: dict[str, Any] | None
    thinking_blocks: list[dict[str, Any]] | None
```
(`sweagent/types.py:63-72`; required base `role` / `content` / `message_type` at `:56-59`)

For `RetryAgent`, the `.traj` gains an `attempts` list plus the chosen attempt spliced in at top level, with `info.best_attempt_idx`, `info.rloop_model_stats`, `info.chooser` (`sweagent/agent/agents.py:358-383`).

Docs description:

> "The main output file is `<instance_id>.traj`, which is a `.json` formatted file containing the (thought, action, observation) turns generated by SWE-agent towards solving `<instance_id>`."
> — `docs/usage/trajectories.md:7`

> "Prior to SWE-agent 1.1.0, we had a `message` field which corresponded (approximately) to the input for the LM for the _next_ step. This was replaced with `query`, which shows the exact input at the current step."
> — `docs/usage/trajectories.md:27-30`

Output tree (`docs/usage/trajectories.md:61-83`):

```
trajectories:
    user 1:
        experiment 1:
            run_batch.config.yaml
            preds.json
            run_batch.debug.log
            run_batch.info.log
            run_batch.warning.log
            run_batch_exit_statuses.yaml
            instance_1:
                instance_1.traj
                instance_1.config.yaml
                instance_1.debug.log
                instance_1.info.log
                instance_1.warning.log
```

### 9.2 The classic SWE-agent 0.7 system prompt (the "windowed viewer" ACI prompt), VERBATIM

```yaml
    system_template: |-
      SETTING: You are an autonomous programmer, and you're working directly in the command line with a special interface.

      The special interface consists of a file editor that shows you {{WINDOW}} lines of a file at a time.
      In addition to typical bash commands, you can also use the following commands to help you navigate and edit files.

      COMMANDS:
      {{command_docs}}

      Please note that THE EDIT COMMAND REQUIRES PROPER INDENTATION.
      If you'd like to add the line '        print(x)' you must fully write that out, with all those spaces before the code! Indentation is important and code that is not indented correctly will fail and require fixing before it can be run.

      RESPONSE FORMAT:
      Your shell prompt is formatted as follows:
      (Open file: <path>) <cwd> $

      You need to format your output using two fields; discussion and command.
      Your output should always include _one_ discussion and _one_ command field EXACTLY as in the following example:
      DISCUSSION
      First I'll start by using ls to see what files are in the current directory. Then maybe we can look at some relevant files to see what they look like.
      ```
      ls -a
      ```

      You should only include a *SINGLE* command in the command section and then wait for a response from the shell before continuing with more discussion and commands. Everything you include in the DISCUSSION section will be saved for future reference.
      If you'd like to issue two commands at once, PLEASE DO NOT DO THAT! Please instead first submit just the first command, and then after receiving a response you'll be able to issue the second command.
      You're free to use any other bash commands you want (e.g. find, grep, cat, ls, cd) in addition to the special commands listed above.
      However, the environment does NOT support interactive session commands (e.g. python, vim), so please do not invoke them.
```
(`config/sweagent_0_7/07.yaml:4-31`)

And the corresponding per-turn observation template, which re-states the viewer state every single turn:

```yaml
    next_step_template: |-
      {{observation}}
      (Open file: {{open_file}})
      (Current directory: {{working_dir}})
      bash-$
    next_step_no_output_template: |-
      Your command ran successfully and did not produce any output.
      (Open file: {{open_file}})
      (Current directory: {{working_dir}})
      bash-$
```
(`config/sweagent_0_7/07.yaml:68-77`)

The 0.7 instance template's "IMPORTANT TIPS" are a compact catalogue of the failure modes the ACI was built to fight:

```yaml
      1. Always start by trying to replicate the bug that the issues discusses.
        ...
        If the bug reproduction script does not print anything when it successfully runs, we recommend adding a print("Script completed successfully, no errors.") command at the end of the file,
        so that you can be sure that the script indeed ran fine all the way through.

      2. If you run a command and it doesn't work, try running a different command. A command that did not work once will not work the second time unless you modify it!

      3. If you open a file and need to get to an area around a specific line that is not in the first 100 lines, say line 583, don't just use the scroll_down command multiple times. Instead, use the goto 583 command. It's much quicker.

      4. If the bug reproduction script requires inputting/reading a specific file, such as buggy-input.png, and you'd like to understand how to input that file, conduct a search in the existing repo code, to see whether someone else has already done that. Do this by running the command: find_file "buggy-input.png" If that doesn't work, use the linux 'find' command.

      5. Always make sure to look at the currently open file and the current working directory (which appears right after the currently open file). The currently open file might be in a different directory than the working directory! Note that some commands, such as 'create', open files, so they might change the current  open file.

      6. When editing files, it is easy to accidentally specify a wrong line number or to write code with incorrect indentation. Always check the code after you issue an edit to make sure that it reflects what you wanted to accomplish. If it didn't, issue another command to fix it.
```
(`config/sweagent_0_7/07.yaml:46-62`)

### 9.3 The stateful diff prompt (cumulative-diff-in-context pattern)

```yaml
        next_step_template: &next_step_with_diff |-
          {% if diff %}
          <diff>
          Your cumulative changes so far:
          {{diff}}
          </diff>

          {% endif %}
          The observation from the last command:
          {{observation}}
```
(`config/benchmarks/250212_sweagent_heavy_sbl.yaml:101-110`)

Paired with a history processor that strips old diffs so only the latest two survive:

```yaml
      history_processors: &diff_history_processors
        - type: remove_regex
          keep_last: 2
          remove:
            - "<diff>.*</diff>"
        - type: cache_control
          last_n_messages: 2
          last_n_messages_offset: 2
```
(`config/benchmarks/250212_sweagent_heavy_sbl.yaml:127-134`)

### 9.4 Miscellaneous quotable lines

> "Note however that you cannot use any interactive session commands (e.g. python, vim) in this environment, but you can write scripts and run them."
> — `config/sweagent_0_7/07.yaml:41`

> "**CRITICAL REQUIREMENTS:** / - Your response SHOULD include a THOUGHT section explaining your reasoning / - Your response MUST include EXACTLY ONE bash code block / - This bash block MUST contain EXACTLY ONE command (or a set of commands connected with && or ||) / - If you include zero or multiple bash blocks, or no command at all, YOUR RESPONSE WILL FAIL"
> — `config/bash_only.yaml:83-88`

> "## Important Boundaries / - MODIFY: Regular source code files in {{working_dir}} / - DO NOT MODIFY: Tests, configuration files (pyproject.toml, setup.cfg, etc.)"
> — `config/bash_only.yaml:45-47`

> "We'll automatically save your work and have maintainers evaluate it."
> — `config/bash_only.yaml:171`

> "Note: Disregard all testing code in the patch, as testing was already done in a separate step. Having a test in the patch does not make it any better."
> — `config/benchmarks/250212_sweagent_heavy_sbl.yaml:149-150`

> "If you need to start a command that has long-running output (e.g. a web server), you should _always_ use the following pattern: `server_command &> my_server_log.txt &` — This way you can see the server's output in the my_server_log.txt file and it will not block the rest of your work."
> — `config/default_mm_with_images.yaml:34-37`

> "Tool call arguments are not valid JSON." / "Required argument(s) missing: ..." / "Unexpected argument(s): ..." / "Command '{name}' not found in list of available commands."
> — `sweagent/tools/parsing.py:402-423` (the four `FunctionCallingFormatError` messages)

> "Total instance cost exceeded cost limit. This should not happen, please report this. Triggering autosubmit."
> — `sweagent/agent/agents.py:337`

> "Error in agent step: %s. This really shouldn't happen, please report this. Triggering autosubmit."
> — `sweagent/agent/agents.py:346`

> "Runtime is no longer alive" ... "Using diff from last trajectory step to autosubmit" ... "Environment died unexpectedly. Exited (autosubmitted)"
> — `sweagent/agent/agents.py:834-847`
