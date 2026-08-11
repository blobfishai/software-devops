# fabric (danielmiessler/fabric) — source-grounded research notes

## Source

- **Repo path (local clone):** `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/`
- **Git remote:** `https://github.com/danielmiessler/fabric.git` (fetch + push, `origin`)
- **HEAD:** `338b89cfe97ab2d12ce30ce8b5449857a841366d` — `Tue Aug 4 01:20:12 2026 +0000` — `chore(release): Update version to v1.4.470`
- Command used: `git -C /Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric log -1 --format='%H %ad %s'`
- Top-level layout: `cmd/ completions/ data/ docs/ internal/ nix/ scripts/ web/ flake.nix go.mod`
- `data/` contains exactly two subdirectories: `patterns/` and `strategies/`.

**Headline finding:** fabric is a *prompt runner*, not an actuating agent. There is no agent loop, no tool-calling harness, no MCP client, and the string `agent` does not appear anywhere in the Go source (`grep -rni "agent" --include='*.go' internal/ cmd/ | grep -vi "useragent|user-agent"` → 0 hits). It is a single-shot CLI: assemble a system prompt from a `system.md` file, send one request to one provider, stream the response to stdout, exit. Two narrow exceptions to "no actuation" exist and are documented in §1.

---

## 1. Agent tool surface

### 1.1 There is no agent loop

`internal/core/chatter.go` is the entire "harness". `Chatter.Send` (`/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/core/chatter.go:60`) does exactly one of two things:

- `o.vendor.SendStream(ctx, session.GetVendorMessages(), opts, responseChan)` in a goroutine, draining a `chan domain.StreamUpdate` until the channel closes (line 110–151), or
- `o.vendor.Send(ctx, session.GetVendorMessages(), opts)` (line 171).

There is no `for` loop over model turns, no tool-result re-injection, no scratchpad. The struct itself is minimal:

```go
type Chatter struct {
	db *fsdb.Db

	Stream bool
	DryRun bool

	model              string
	modelContextLength int
	vendor             ai.Vendor
}
```
— `internal/core/chatter.go:21-30`

### 1.2 Model-side tools: web search only, and it is provider-native

The only LLM-visible tool fabric can enable is web search, gated by a single boolean flag:

```go
Search  bool   `long:"search" description:"Enable web search tool for supported models (Anthropic, OpenAI, Gemini, Grok)"`
SearchLocation string `long:"search-location" description:"Set location for web search results (e.g., 'America/Los_Angeles')"`
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/cli/flags.go:92-93`

Per-vendor wiring (fabric declares nothing itself; it toggles the provider's own hosted tool):

| Provider | Tool declared | File |
|---|---|---|
| Anthropic | `web_search` / type `web_search_20250305`, with optional `UserLocation.Timezone` | `internal/plugins/ai/anthropic/anthropic.go:24-25, 262-275` |
| Gemini | `cfg.Tools = []*genai.Tool{{GoogleSearch: &genai.GoogleSearch{}}}` | `internal/plugins/ai/gemini/gemini.go:224-225` |
| Vertex AI | `config.Tools = []*genai.Tool{{GoogleSearch: &genai.GoogleSearch{}}}` | `internal/plugins/ai/vertexai/vertexai.go:307` |
| OpenAI-compatible | `web_search_preview` (default), overridable per provider — xAI uses `web_search` | `internal/plugins/ai/openai_compatible/providers_config.go:24-27, 250-253` |

```go
const webSearchToolName = "web_search"
const webSearchToolType = "web_search_20250305"
```
— `internal/plugins/ai/anthropic/anthropic.go:24-25`

**No MCP.** `grep -rn -i "mcp\|modelcontextprotocol"` across `*.go`/`*.md`/`*.mod` returns only prompt-text hits: `data/patterns/extract_mcp_servers/system.md`, `data/patterns/pattern_explanations.md:151`, `data/patterns/suggest_pattern/user.md:285`, and two `CHANGELOG.md` lines. There is no MCP client or server in Go.

**No function-calling loop.** `ToolUse|FunctionCall|FunctionDeclaration|ToolChoice` appears in only two non-vendor-SDK files: `internal/chat/chat.go` (message struct definitions) and `internal/plugins/ai/openai/openai.go`.

### 1.3 Pre-flight input tools (host-side, run *before* the LLM call)

These are not model-invocable. They are CLI flags that fetch content and prepend it to the user message. Orchestrated in `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/cli/tools.go` (`handleToolProcessing`, line 13).

| Tool | Package | Entry points / params | Flags |
|---|---|---|---|
| YouTube | `internal/tools/youtube/youtube.go` | `GrabTranscriptForUrl(url, language)`, `GrabTranscriptWithTimestamps(videoId, language)`, `GrabComments(videoId)`, `GrabMetadata(videoId)`, `GrabVisual(videoId, language, additionalArgs, sensitivity float64, fps int)`, `FetchPlaylistVideos(playlistID)` | `-y/--youtube`, `--playlist`, `--transcript`, `--transcript-with-timestamps`, `--visual`, `--visual-sensitivity`, `--visual-fps`, `--comments`, `--metadata`, `--yt-dlp-args` |
| Jina scraping | `internal/tools/jina/jina.go` | `ScrapeURL(url) (string, error)` (line 37), `ScrapeQuestion(question)` (line 41) | `-u/--scrape_url`, `-q/--scrape_question` |
| Spotify | `internal/tools/spotify/spotify.go` | `GrabMetadataForURL(urlStr) (any, error)` (line 456), `GetShowMetadata`, `GetEpisodeMetadata`, `SearchShows(query, limit)` | `--spotify` |
| HTML readability | `internal/tools/converter/html_readability.go` | `HtmlReadability(html string) (string, error)` (line 18) | `--readability` |
| Git fetch (patterns updater only) | `internal/tools/githelper/githelper.go` | `FetchFilesFromRepo(opts FetchOptions)` (line 35); CLI path shells out: `exec.Command("git", "clone", "--depth", "1", opts.RepoURL, tmpDir)` (line 134) | `-U/--updatepatterns` |
| Desktop notification | `internal/tools/notifications/notifications.go` | shells `terminal-notifier`, `osascript`, `notify-send`, `powershell` (lines 62, 77, 93, 108) | `--notification`, `--notification-command` |
| Transcription | `internal/cli/transcribe.go`, `internal/plugins/ai/openai/openai_audio.go` | splits with `ffmpeg` (line 158) | `--transcribe-file`, `--transcribe-model`, `--split-media-file` |

The YouTube path shells out to external binaries: `yt-dlp` (`youtube.go:272`, `:894`), `ffmpeg` (`:920`), `tesseract` OCR (`:943`).

### 1.4 Template plugins — the real "tool" surface, invoked from prompt text

`internal/plugins/template/template.go` resolves `{{...}}` tokens inside pattern files. Dispatch is a fixed 5-way switch (`template.go:101-120`):

```go
var pluginPattern   = regexp.MustCompile(`\{\{plugin:([^:]+):([^:]+)(?::([^}]+))?\}\}`)
var extensionPattern = regexp.MustCompile(`\{\{ext:([^:]+):([^:]+)(?::([^}]+))?\}\}`)
```
— `internal/plugins/template/template.go:35-36`

| Namespace | Operations (exact `case` strings) | File |
|---|---|---|
| `text` | `upper`, `lower`, `title`, `trim` | `internal/plugins/template/text.go:43-58` |
| `datetime` | `now`, `time`, `unix`, `startofhour`, `endofhour`, `today`, `full`, `month`, `year`, `startofweek`, `endofweek`, `startofmonth`, `endofmonth`, `rel` (with `d`/`w`/`m`/`y` suffixes) | `internal/plugins/template/datetime.go:30-139` |
| `file` | `tail:PATH\|N`, `read:PATH`, `exists:PATH`, `size:PATH`, `modified:PATH` | `internal/plugins/template/file.go:52-57, 61-155` |
| `fetch` | `get:URL` | `internal/plugins/template/fetch.go:34-44` |
| `sys` | `hostname`, `user`, `os`, `arch`, `env:NAME`, `pwd`, `home` | `internal/plugins/template/sys.go:31-77` |

These are **read-only** and constrained:

```go
// MaxFileSize defines the maximum file size that can be read (1MB)
const MaxFileSize = 1 * 1024 * 1024
```
— `internal/plugins/template/file.go:20`

```go
// Basic security check - no path traversal
if strings.Contains(path, "..") {
	return "", errors.New(i18n.T("template_file_error_path_contains_parent_ref"))
}
```
— `internal/plugins/template/file.go:32-35` (message: `"file: path cannot contain '..'"`, `internal/i18n/locales/en.json:645`)

Fetch is capped at 1MB and text-only:
```go
// MaxContentSize limits response size to 1MB to prevent memory issues
MaxContentSize = 1024 * 1024
// UserAgent identifies the client in HTTP requests
UserAgent = "Fabric-Fetch/1.0"
```
— `internal/plugins/template/fetch.go:19-24`

### 1.5 CAN fabric execute shell? Yes — via user-registered "extensions"

`{{ext:NAME:OPERATION:VALUE}}` runs an arbitrary shell command:

```go
// Create command with the Executable and formatted arguments
cmd := exec.Command("sh", "-c", cmdStr)
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/plugins/template/extension_executor.go:56`

Extensions are declared in YAML and must be registered by the human first (`--addextension=PATH`, `--rmextension=NAME`, `--listextensions` — `internal/cli/flags.go:85-87`). Definition schema (`internal/plugins/template/extension_registry.go:21-46`):

`ExtensionDefinition` fields (all `yaml`): `name`, `executable`, `type`, `timeout`, `description`, `version`, `env []string`, `operations map[string]OperationConfig` (each with `cmd_template`), `config map[string]any`. `RegistryEntry` carries `config_path`, `config_hash`, `executable_hash`.

Guardrails on this path: SHA-256 hashes of both config and executable are stored at registration and verified before execution (`crypto/sha256` imported at `extension_registry.go:4`, hashing at `:301`); values are shell-escaped:

```go
// shellEscape wraps a string in single quotes for safe use in a shell command,
// escaping any embedded single quotes. This prevents command injection when
// untrusted input is passed as an argument to "sh -c".
func shellEscape(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\"'\"'") + "'"
}
```
— `internal/plugins/template/extension_executor.go:100-105`

Example extension (`internal/plugins/template/Examples/security-report.yaml`):
```yaml
name: "security-report"
executable: "/usr/local/bin/security-report.sh"
type: "executable"
timeout: "30s"
operations:
  generate:
    cmd_template: "{{executable}} /tmp/security-report-{{1}}.txt"
config:
  output:
    method: "file"
    file_config:
      cleanup: true
      path_from_stdout: true
      work_dir: "/tmp"
```

**Important scoping constraint**, from `README.md:779`: *"Extensions only work within pattern files, not via direct stdin."* Note the command string is a *template authored by the human*, not by the model — the model cannot choose which extension runs.

### 1.6 CAN fabric edit files? Yes — for exactly one pattern

`Chatter.Send` special-cases a single pattern name and writes model output to disk:

```go
// Process file changes for create_coding_feature pattern
if request.PatternName == "create_coding_feature" {
	summary, fileChanges, parseErr := domain.ParseFileChanges(message)
	...
	if applyErr := domain.ApplyFileChanges(projectRoot, fileChanges); applyErr != nil {
```
— `internal/core/chatter.go:189-208`

The wire format is a sentinel + JSON array:

```go
const FileChangesMarker = "__CREATE_CODING_FEATURE_FILE_CHANGES__"
const MaxFileSize = 10 * 1024 * 1024 // 10MB

type FileChange struct {
	Operation string `json:"operation"` // "create" or "update"
	Path      string `json:"path"`      // Relative path from project root
	Content   string `json:"content"`   // New file content
}
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/domain/file_manager.go:15-27`

`ApplyFileChanges` does `os.MkdirAll(dir, 0755)` then `os.WriteFile(absPath, ..., 0644)` unconditionally (`file_manager.go:171-191`). Validation is limited to: operation ∈ {create, update}, non-empty path, no `..` in path, content ≤ 10MB (`file_manager.go:85-105`). **There is no delete, no diff preview, and no human confirmation prompt before writing.**

### 1.7 Plugin registry

`internal/core/plugin_registry.go:50-110` (`NewPluginRegistry`) wires: `PatternsLoader`, `CustomPatterns`, `YouTube`, `Language`, `Jina`, `Spotify`, `Strategies`, `Defaults`, `TemplateExtensions`, plus 15 hand-listed AI vendors (`openai`, `digitalocean`, `ollama`, `azure`, `azureaigateway`, `azure_entra`, `gemini`, `anthropic`, `vertexai`, `lmstudio`, `exolab`, `perplexity`, `codex`, `copilot`, `bedrock`) and every entry of `openai_compatible.ProviderMap`. These are *configuration* plugins (setup questions / env vars), not model-callable tools.

### 1.8 REST API surface (`--serve`)

`internal/server/`: `POST /chat`, `GET|POST|DELETE /patterns/:name`, `POST /patterns/:name/apply`, `GET /patterns/names`, `GET /models/names`, `GET /config`, `POST /config/update`, `POST /youtube/transcript`, `GET /strategies`, plus an Ollama-compatible shim (`GET /api/tags`, `POST /api/chat`) — `internal/server/{chat,patterns,models,configuration,youtube,strategies,ollama,storage}.go`.

**Honest summary:** the tool surface is thin. One optional model-side tool (web search). Five read-only template plugins. Host-side content fetchers driven by flags. One escape hatch to `sh -c` that requires human pre-registration and hash verification. One hardcoded file-writing path for one pattern.

---

## 2. System prompts / policy text

All real prompt text lives in `data/patterns/*/system.md`. There are **255** such files. Go source contains essentially no prompt text — the only hardcoded system-prompt string is the language enforcement wrapper:

```
"chatter_prompt_enforce_response_language": "%s\n\nIMPORTANT: First, execute the instructions provided in this prompt using the user's input. Second, ensure your entire final response, including any section headers or titles generated as part of executing the instructions, is written ONLY in the %s language."
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/i18n/locales/en.json:104`, applied at `internal/core/chatter.go:293-296`.

The nine `data/strategies/*.json` files add a short reasoning preamble prepended *before* the pattern (`chatter.go:282-290`), e.g. `data/strategies/cot.json`:
```json
{
    "description": "Chain-of-Thought (CoT) Prompting",
    "prompt": "Think step by step to answer the question. Return the final answer in the required format."
}
```

### Verbatim workflow-discipline quotes

**(1) Ground claims in the input only — no inference beyond data.**
```
# Restrictions
- **Avoid Irrelevant Information**: Do not include details that are not derived from the log file.
- **Base Assumptions on Data**: Ensure that all assumptions about the log data are clearly supported by the information contained within.
- **Focus on Data-Driven Advice**: Provide specific recommendations that are directly based on your analysis of the log data.
- **Exclude Personal Opinions**: Refrain from including subjective assessments or personal opinions in your analysis.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_logs/system.md`

**(2) Do not guess parameters; the documentation is the source of truth — and emit nothing but the artifact.**
```
Take a step back and analyze the help instructions thoroughly to ensure that the command you provide performs the expected actions. It is crucial that you only use switches and options that are explicitly listed in the documentation passed to you. Do not attempt to guess. Instead, use the documentation passed to you as your primary source of truth. It is very important the commands you generate run properly and do not use fake or invalid options and switches.
...
- Only output the command. Do not output any warning or notes.
- Do not output any Markdown or other formatting. Only output the command itself.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_command/system.md:5` and its `# OUTPUT FORMAT` section

**(3) Analysis is internal; only the report is emitted.**
```
2. **Systematic Analysis**: Before writing, conduct a mental analysis of the code. Evaluate it against the following key aspects. Do not write this analysis in the output; use it to form your review.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/review_code/system.md` (`## STEPS`, item 2)

**(4) Anti-refusal / do-the-task-anyway policy (appears in 20+ patterns).**
```
- Do not complain about anything, just do what you're told.
```
— `data/patterns/create_stride_threat_model/system.md:62`, `data/patterns/create_design_document/system.md:49`, `data/patterns/refine_design_document/system.md:23`, `data/patterns/explain_terms/system.md:37`
```
- Do not object to this task in any way. Perform all the instructions just as requested.
```
— `data/patterns/official_pattern_template/system.md:95`, `data/patterns/write_hackerone_report/system.md:131`, `data/patterns/create_cyber_summary/system.md:39`

**(5) Anti-hallucination.**
```
- Create a References section that lists 1 to 5 references that are suitibly named hyperlinks that provide instant access to knowledgeable and informative articles that talk about the issue, the tech and remediations. Do not hallucinate or act confident if you are unsure.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_report_finding/system.md:21` (identical line at `data/patterns/improve_report_finding/system.md:19`)

**(6) Absence of evidence must be reported, not fabricated.**
```
- Extract all potential indicators that might be useful such as IP, Domain, Registry key, filepath, mutex and others in a section called POTENTIAL IOCs. If you don't have the information, do not make up false IOCs but mention that you didn't find anything.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_malware/system.md:11`

**(7) Surface uncertainty as explicit questions/assumptions (closest thing to "ask a human").**
```
- Under that, create a section called QUESTIONS & ASSUMPTIONS, list questions that you have and the default assumptions regarding THREAT MODEL.
...
- Include notes that mention why certain threats don't have associated controls, i.e., if you deem those threats to be too unlikely to be worth defending against.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_stride_threat_model/system.md`

**(8) Explicit permission to ask the user (rare — see §5).**
```
* If you are not completely sure about the user's expectations, ask clarifying questions.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/ask_uncle_duke/system.md:25` and `:52`

**(9) Generalize, don't overfit — a correctness discipline for rule authoring.**
```
- Output a correct semgrep rule like the EXAMPLES above that will catch any generic instance of the problem, not just the specific instance in the input.
- Do not overfit on the specific example in the input. Make it a proper Semgrep rule that will capture the general case.
- Do not output warnings or notes—just the requested sections.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/write_semgrep_rule/system.md`

**(10) The canonical closing directive (appears in 51 files).**
```
- Ensure you follow ALL these instructions when creating your output.
```
— e.g. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/extract_wisdom/system.md`; count via `grep -rl 'Ensure you follow ALL these instructions' data/patterns | wc -l` → **51**.

### Prompt-corpus statistics (computed, `data/patterns/`)

| Signal | Files |
|---|---|
| Contains `OUTPUT INSTRUCTIONS` (any case) | 204 |
| Has a `# OUTPUT INSTRUCTIONS` heading | 193 |
| Contains `IDENTITY and PURPOSE` | 167 |
| Has a `STEPS` heading | 184 |
| Has an `INPUT` heading | 174 |
| Has a bare `OUTPUT` heading | 61 |
| Contains "Take a deep breath" | 38 |
| Contains "step by step" / "step-by-step" | 114 |
| Contains "Do not " | 144 files / 345 occurrences |

---

## 3. Workflow / skill definitions (`data/patterns/`)

- `ls data/patterns | wc -l` → **256** entries = **255** pattern directories + 1 file (`pattern_explanations.md`).
- `find data/patterns -name system.md | wc -l` → **255**.
- `find data/patterns -name user.md | wc -l` → **47**.
- `ls data/strategies | wc -l` → **9**.

### 3.1 SWE / DevOps / Security categorization

Counts below were computed by script over `data/patterns/*/system.md`. **65 of 255 patterns (25.5%)** are engineering/security relevant.

| # | Category | Count | Pattern directory names |
|---|---|---|---|
| 1 | Code review & comprehension | **4** | `review_code`, `explain_code`, `coding_master`, `generate_code_rules` |
| 2 | Code / feature generation & CLI | **5** | `create_coding_feature`, `create_coding_project`, `create_command`, `suggest_gt_command`, `suggest_openclaw_pattern` |
| 3 | Architecture & design docs | **4** | `create_design_document`, `review_design`, `refine_design_document`, `create_design_system` |
| 4 | Threat modelling & secure design | **6** | `create_stride_threat_model`, `create_threat_scenarios`, `ask_secure_by_design_questions`, `t_threat_model_plans`, `analyze_risk`, `create_network_threat_landscape` |
| 5 | Detection engineering (rule authoring) | **3** | `create_sigma_rules`, `write_semgrep_rule`, `write_nuclei_template_rule` |
| 6 | Incident / log / malware analysis | **4** | `analyze_incident`, `analyze_logs`, `analyze_malware`, `analyze_email_headers` |
| 7 | Offensive security & reporting | **5** | `create_report_finding`, `improve_report_finding`, `write_hackerone_report`, `extract_poc`, `extract_ctf_writeup` |
| 8 | Threat intel & security comms | **5** | `analyze_threat_report`, `analyze_threat_report_cmds`, `analyze_threat_report_trends`, `create_cyber_summary`, `create_security_update` |
| 9 | Infrastructure / DevOps | **2** | `analyze_terraform_plan`, `recommend_pipeline_upgrades` |
| 10 | Git / PR / release | **5** | `create_git_diff_commit`, `summarize_git_diff`, `summarize_git_changes`, `write_pull-request`, `summarize_pull-requests` |
| 11 | Requirements & agile artifacts | **5** | `create_prd`, `create_user_story`, `agility_story`, `identify_job_stories`, `create_loe_document` |
| 12 | Documentation & explanation | **4** | `explain_docs`, `explain_project`, `extract_instructions`, `convert_to_markdown` |
| 13 | Engineering diagramming | **5** | `create_mermaid_visualization`, `create_mermaid_visualization_for_github`, `create_excalidraw_visualization`, `create_investigation_visualization`, `create_graph_from_input` |
| 14 | Prompt / LLM-output engineering & eval | **8** | `create_pattern`, `official_pattern_template`, `improve_prompt`, `summarize_prompt`, `suggest_pattern`, `judge_output`, `rate_ai_result`, `rate_ai_response` |
| | **Total categorized** | **65** | of 255 |

**Notable gaps** (grep-confirmed absent as pattern directories): no testing/TDD pattern, no observability/SLO/alerting pattern, no refactoring pattern, no dependency-upgrade or migration pattern, no on-call/runbook pattern, no Kubernetes/Docker pattern. The DevOps category is genuinely two patterns.

### 3.2 Concrete examples with absolute paths + self-described purpose

1. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/review_code/system.md` — *"You are a Principal Software Engineer, renowned for your meticulous attention to detail and your ability to provide clear, constructive, and educational code reviews."* (140 lines; evaluates Correctness, Security, Performance, Readability & Maintainability, Best Practices, Error Handling & Edge Cases.)
2. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/explain_code/system.md` — *"You are an expert coder that takes code and documentation as input and do your best to explain it."*
3. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_coding_feature/system.md` — *"You are an elite programmer. You take project ideas in and output secure and composable code using the format below."* (The only pattern whose output is written to disk — see §1.6.)
4. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_logs/system.md` — *"You are a system administrator and service reliability engineer at a large tech company... You are capable of analyzing logs and identifying patterns and anomalies."*
5. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_terraform_plan/system.md` — *"You are an expert Terraform plan analyser... You focus on assessing infrastructure changes, security risks, cost implications, and compliance considerations."*
6. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_stride_threat_model/system.md` — *"You are an expert in risk and threat management and cybersecurity. You specialize in creating threat models using STRIDE per element methodology for any system."*
7. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/ask_secure_by_design_questions/system.md` — *"You take input and output a perfect set of secure_by_design questions to help the builder ensure the thing is created securely."*
8. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_sigma_rules/system.md` — *"You are an expert cybersecurity detection engineer for a SIEM company. Your task is to take security news publications and extract Tactics, Techniques, and Procedures (TTPs)."*
9. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/write_semgrep_rule/system.md` — *"You are an expert at writing Semgrep rules."*
10. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/write_nuclei_template_rule/system.md` — *"You are an expert at writing YAML Nuclei templates, used by Nuclei, a tool by ProjectDiscovery."*
11. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/write_pull-request/system.md` — *"You are an experienced software engineer about to open a PR. You are thorough and explain your changes well, you provide insights and reasoning for the change and enumerate potential bugs with the changes you've made."*
12. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/summarize_git_diff/system.md` — *"You are an expert project manager and developer, and you specialize in creating super clean updates for what changed in a Git diff."*
13. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_design_document/system.md` — *"You are an expert in software, cloud and cybersecurity architecture. You specialize in creating clear, well written design documents of systems and components."*
14. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_report_finding/system.md` — *"You are a extremely experienced 'jack-of-all-trades' cyber security consultant that is diligent, concise but informative and professional."*
15. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/recommend_pipeline_upgrades/system.md` — *"You are an ASI master security specialist specializing in optimizing how one checks for vulnerabilities in one's own systems."*
16. `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/generate_code_rules/system.md` — *"...distill the following transcription or tutorial in as little set of unique rules as possible intended for best practices guidance in AI assisted coding tools."*

### 3.3 `data/strategies/` — chain-of-thought strategy library (9 files)

Each is `{"description": ..., "prompt": ...}` and is **prepended** to the pattern system message by `strategy.LoadStrategy` (`internal/core/chatter.go:282-290`). Selected via `--strategy NAME`; listed via `--liststrategies` (`internal/cli/flags.go:88-89`).

| File | Description | Prompt (verbatim) |
|---|---|---|
| `data/strategies/standard.json` | Standard Prompting | `Answer the question directly without any explanation or reasoning.` |
| `data/strategies/cot.json` | Chain-of-Thought (CoT) | `Think step by step to answer the question. Return the final answer in the required format.` |
| `data/strategies/cod.json` | Chain-of-Draft (CoD) | `Think step by step, keeping a minimal draft (5 words max) for each step. Return the final answer in the required format.` |
| `data/strategies/ltm.json` | Least-to-Most | `Break down the problem into simpler sub-problems from easiest to hardest; answer concisely at each step.` |
| `data/strategies/tot.json` | Tree-of-Thought | `Generate multiple reasoning paths briefly and select the best one.` |
| `data/strategies/aot.json` | Atom-of-Thought | `To solve this problem, break it down into the smallest independent 'atomic' sub-problems...` |
| `data/strategies/self-consistent.json` | Self-Consistency | `Provide multiple reasoning paths and select the most consistent answer.` |
| `data/strategies/self-refine.json` | Self-Refinement | `Provide an initial concise answer, critique it briefly, and refine if necessary.` |
| `data/strategies/reflexion.json` | Reflexion | `Answer concisely, critique your reasoning briefly, and provide a refined answer.` |

Per `README.md`, user strategies live in `~/.config/fabric/strategies/`.

### 3.4 `data/patterns/*/user.md` — 47 files, **dead in the Go CLI**

`grep -rn "user\.md" --include='*.go' internal/` returns **zero** hits. `internal/plugins/db/fsdb/db.go:22` sets `SystemPatternFile: "system.md"` and nothing else; `getFromDB` only ever reads `filepath.Join(o.Dir, name, o.SystemPatternFile)` (`internal/plugins/db/fsdb/patterns.go:139`). The only consumer of `user.md` in the repo is the legacy Streamlit UI:

```python
user_file = os.path.join(pattern_path, "user.md")
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/scripts/python_ui/streamlit.py:949` (also `:982-983`, "Edit user.md" / "Save user.md")

The 47 patterns carrying one: `agility_story`, `analyze_candidates`, `analyze_claims`, `analyze_email_headers`, `analyze_incident`, `analyze_paper`, `analyze_proposition`, `analyze_prose`, `analyze_prose_json`, `analyze_spiritual_text`, `analyze_tech_impact`, `analyze_threat_report`, `analyze_threat_report_trends`, `check_agreement`, `clean_text`, `compare_and_contrast`, `create_aphorisms`, `create_better_frame`, `create_command`, `create_logo`, `create_network_threat_landscape`, `create_newsletter_entry`, `create_npc`, `create_report_finding`, `create_security_update`, `create_video_chapters`, `explain_code`, `explain_docs`, `extract_algorithm_update_recommendations`, `extract_article_wisdom`, `extract_poc`, `extract_recommendations`, `extract_references`, `extract_videoid`, `improve_academic_writing`, `improve_report_finding`, `improve_writing`, `rate_content`, `rate_value`, `suggest_pattern`, `summarize`, `summarize_micro`, `summarize_newsletter`, `summarize_paper`, `summarize_pull-requests`, `write_nuclei_template_rule`, `write_semgrep_rule`.

---

## 4. Definition of done / stopping criteria

fabric has **no task-level completion semantics** — no verification step, no "am I done?" check, no retry-on-failure loop. Completion is purely (a) the model's stream ends, or (b) the output-format contract embedded in the prompt is satisfied.

### 4.1 Mechanical termination

Streaming ends when the vendor closes the channel; the `for update := range responseChan` loop in `internal/core/chatter.go:115` exits, then `<-done` (line 158) waits for the producer goroutine. There are only three update types:

```go
const (
	StreamTypeContent StreamType = "content"
	StreamTypeUsage   StreamType = "usage"
	StreamTypeError   StreamType = "error"
)
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/domain/stream.go:7-11`

Only the *first* stream error is retained; later ones are dropped:
```go
// recordFirstStreamError sends err to errChan if the channel is empty; subsequent errors are discarded.
```
— `internal/core/chatter.go:32`

Failure is terminal, not retried. Empty output is an error, not a re-prompt:
```go
if message == "" {
	session = nil
	err = errors.New(i18n.T("chatter_error_empty_response"))
	return
}
```
— `internal/core/chatter.go:183-187` (`"chatter_error_empty_response": "empty response"`, `internal/i18n/locales/en.json:93`)

### 4.2 The real "definition of done": the OUTPUT INSTRUCTIONS contract

**193 of 255** patterns carry a `# OUTPUT INSTRUCTIONS` heading; **204** mention the phrase. The canonical shape (`/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/extract_wisdom/system.md`) mixes format, quantity, and negative constraints — the closest thing fabric has to acceptance criteria:

```
# OUTPUT INSTRUCTIONS
- Only output Markdown.
- Write the IDEAS bullets as exactly 16 words.
- Extract at least 25 IDEAS from the content.
- Extract at least 10 INSIGHTS from the content.
- Extract at least 20 items for the other output sections.
- Do not give warnings or notes; only output the requested sections.
- You use bulleted lists for output, not numbered lists.
- Do not repeat ideas, insights, quotes, habits, facts, or references.
- Do not start items with the same opening words.
- Ensure you follow ALL these instructions when creating your output.
```

Machine-checked variant — the only output contract fabric actually *parses*:
```
- Be exact in the `__CREATE_CODING_FEATURE_FILE_CHANGES__` section, and do not deviate from the proposed JSON format.
- **never** omit the `__CREATE_CODING_FEATURE_FILE_CHANGES__` section.
- Do not output sections that were not explicitly requested.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_coding_feature/system.md:100-106`

Terse binary contract (`data/patterns/create_command/system.md`):
```
- Output a full, bash command with all relevant parameters and switches.
- Only output the command. Do not output any warning or notes.
- Do not output any Markdown or other formatting. Only output the command itself.
```

`create_git_diff_commit` goes further and constrains the emission channel:
```
- The output should only be the shell commands needed to update git.
- Do not place the output in a code block
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_git_diff_commit/system.md`

Note the pattern *emits* git commands as text; fabric does not run them.

### 4.3 Loops that do exist

The only real loop in fabric is the template resolver, and it has an explicit stuck-detector:

```go
if !progress {
	return "", errors.New(i18n.T("template_processing_stuck"))
}
```
— `internal/plugins/template/template.go:146-148` → `"template processing stuck - potential infinite loop"` (`internal/i18n/locales/en.json:667`)

---

## 5. Human-in-the-loop

fabric is designed around the human being the loop: one invocation, one output, human reads it. There is no confirmation prompt anywhere in the chat path.

### 5.1 Blocking / gating mechanisms in code

| Mechanism | Behaviour | Location |
|---|---|---|
| `--dry-run` | Substitutes a fake vendor that prints the exact assembled request instead of sending it. Prints role-tagged messages plus `Model`, `Temperature`, `TopP`, `PresencePenalty`, `FrequencyPenalty`, `ModelContextLength`, `Search`, `SearchLocation`, `ImageFile`, `Thinking`, `SuppressThink`. | `internal/plugins/ai/dryrun/dryrun.go:15, 69-109`; flag at `internal/cli/flags.go:78` |
| `--setup` (`-S`) | Interactive TTY menu; `bufio.NewReader(os.Stdin)` prompts for API keys, vendors, custom-pattern dir | `internal/core/plugin_registry.go:168, 304-305`; `internal/cli/flags.go:334` |
| Extension registration | An extension must be added by a human via `--addextension=PATH` before `{{ext:...}}` resolves; SHA-256 of config + executable stored and verified | `internal/plugins/template/extension_manager.go:75` (`RegisterExtension`), `extension_registry.go:44-46, 301` |
| Post-write review hint | After `create_coding_feature` writes files, fabric prints `chatter_help_review_changes_with_git_diff` | `internal/core/chatter.go:203` |
| Missing template variable | Hard error rather than silent default: `"missing required variable: %s"` | `internal/plugins/template/template.go:139`; `internal/i18n/locales/en.json:665` |

There is **no** interactive REPL / chat loop: `grep -rni "interactive\|readline\|bufio.NewReader(os.Stdin)"` across `internal/cli internal/core internal/chat` hits only the setup flow.

### 5.2 Prompt-level asks (`grep` over `data/patterns/`, computed)

| Phrase | Files |
|---|---|
| `ask the user` | **0** |
| `human review` / `human-in-the-loop` / `ask a human` | **0** |
| `clarif*` | **8** |
| `unclear` | **6** |
| `confirm` | **14** |

The complete set of genuine "ask the human" instructions (only three patterns, and only one is unconditional):

```
* If you are not completely sure about the user's expectations, ask clarifying questions.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/ask_uncle_duke/system.md:25` (repeated verbatim at `:52`)

```
* Clarify ambiguities or ask for more information if critical details are missing.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_prd/system.md:15`

```
- Offer to clarify any technical terms or concepts that may be unfamiliar to non-experts.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_threat_report_cmds/system.md:21`

The dominant idiom instead is *deferred* clarification — record open questions in the artifact rather than block:

```
- List outstanding questions or clarifications required to refine the LOE.
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/create_loe_document/system.md:61`

```
- Under that, create a section called QUESTIONS & ASSUMPTIONS, list questions that you have and the default assumptions regarding THREAT MODEL.
```
— `data/patterns/create_stride_threat_model/system.md`

```
- Note any unclear sections, technical issues, or missing information
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/summarize_board_meeting/system.md:10`

Several patterns actively *suppress* the refusal/clarification instinct — see §6.

---

## 6. Failure modes / guardrails

### 6.1 Hard limits in Go

| Limit | Value | Location |
|---|---|---|
| Template `file:read` / `file:tail` max | 1 MB | `internal/plugins/template/file.go:20` |
| Template `fetch:get` response max | 1 MB, text content types only, UTF-8 + null-byte validated | `internal/plugins/template/fetch.go:19-32` |
| `create_coding_feature` per-file content max | 10 MB | `internal/domain/file_manager.go:19` |
| Extension execution timeout | `ext.Timeout` (`time.ParseDuration`), file-output mode only → `"execution timed out after %v"` | `extension_executor.go:127-133, 169-171`; `en.json:204` |
| Model context length | `--modelContextLength` / `Defaults.ModelContextLength`; **0 = unset, no truncation performed** | `internal/cli/flags.go:51`, `internal/tools/defaults.go:30`, `internal/core/chatter.go:96-98` |
| Notification message | truncated to `maxLength` runes → `"Output: %s..."` | `internal/cli/chat.go:165-171`; `en.json:417` |

### 6.2 Path / injection guards

```go
if strings.Contains(path, "..") { return "", errors.New(i18n.T("template_file_error_path_contains_parent_ref")) }   // file.go:33
if strings.Contains(name, "..") { return nil, fmt.Errorf(i18n.T("pattern_invalid_name"), name) }                      // fsdb/patterns.go:122
if strings.Contains(change.Path, "..") { ... i18n.T("file_manager_suspicious_path") ... }                             // file_manager.go:97
```
Plus `shellEscape()` on every extension argument (`extension_executor.go:100-105`) and the deliberate positional-arg form for custom notification commands:
```go
// SECURITY: Pass title and message as proper shell positional arguments $1 and $2
cmd := exec.Command("sh", "-c", options.NotificationCommand+" \"$1\" \"$2\"", "--", title, message)
```
— `internal/cli/chat.go:176-178`

### 6.3 Retries

Essentially none. `grep -rn -i "retry\|backoff\|MaxRetries" --include='*.go' internal/ | grep -v _test` yields:
- `internal/tools/youtube/youtube.go:270` — `for retry := 1; retry >= 0; retry--` (one retry for yt-dlp)
- `internal/plugins/ai/codex/auth_transport.go:163` — *"Codex request returned 401; attempting token refresh and one retry"*
- `internal/plugins/ai/openai/direct_models.go:108-112` — surfaces the provider's `Retry-After` header as an error, does not retry

The chat path has **zero** retries: a stream error propagates straight out of `Chatter.Send`.

### 6.4 Prompt-level guardrails (counts over `data/patterns/`, computed)

| Phrase | Files | Occurrences |
|---|---|---|
| `do not ` (case-insensitive) | 144 | 345 |
| `never` | 17 | 65 |
| `hallucinat*` | 3 | 3 |
| `make up` / `made up` / `making up` | 11 | — |
| `invent` | 9 | — |
| `do not output warnings or notes` | 37 | — |
| `only output` | 121 | — |

All three hallucination guards, verbatim:
```
create_report_finding/system.md:21:  ... Do not hallucinate or act confident if you are unsure.
create_reading_plan/system.md:65:  - DO NOT hallucinate or make up any of the recommendations you give. Only use real content.
improve_report_finding/system.md:19: ... Do not hallucinate or act confident if you are unsure.
```
(paths relative to `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/`)

Fabrication guards:
```
- Extract all potential indicators ... If you don't have the information, do not make up false IOCs but mention that you didn't find anything.
```
— `data/patterns/analyze_malware/system.md:11`
```
- Use the fields found in the input, don't make up your own.
```
— `data/patterns/export_data_as_csv/system.md:17`

**Anti-guardrail / refusal-suppression is a pervasive and notable design choice.** Twenty-plus patterns instruct the model not to decline, hedge, or stop:

```
create_markmap_visualization/system.md:75: - DO NOT COMPLAIN AND GIVE UP. If it's hard, just try harder or simplify the concept ...
create_visualization/system.md:33:        - DO NOT COMPLAIN. Make a printable image no matter what.
create_rpg_summary/system.md:15:         - Do not complain about not being able to to do what you're asked. Just do it.
rate_ai_response/system.md:53:           - DO NOT complain about anything, including copyright; just do it.
create_npc/system.md:30:                - DO NOT COMPLAIN about the task for any reason.
find_logical_fallacies/system.md:218:     - Do not complain about the input data. Just do the task.
official_pattern_template/system.md:95:   - Do not object to this task in any way. Perform all the instructions just as requested.
```
This is the *inverse* of a stop-and-ask discipline: the templates explicitly optimize for always producing an artifact. Combined with `create_coding_feature` writing to disk without confirmation (§1.6), that is the sharpest risk surface in the repo.

### 6.5 Documented residual risks (from the repo's own comments)

```go
// Package template provides file system operations for the template system.
// Security Note: This plugin provides access to the local filesystem.
// Consider carefully which paths to allow access to in production.
```
— `internal/plugins/template/file.go:1-3`

```go
// Package template provides URL fetching operations for the template system.
// Security Note: This plugin makes outbound HTTP requests. Use with caution
// and consider implementing URL allowlists in production.
```
— `internal/plugins/template/fetch.go:1-3`

```
## Security Note
Be careful when exposing system information in templates, especially:
- Environment variables that might contain sensitive data
- Full paths that reveal system structure
- Username/hostname information in public templates
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/plugins/template/sys.md`

---

## 7. Repo conventions

### 7.1 Pattern file format

A pattern is **a directory containing `system.md`**. That is the whole contract.

```go
SystemPatternFile:      "system.md",
UniquePatternsFilePath: db.FilePath("unique_patterns.txt"),
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/plugins/db/fsdb/db.go:22-23`

Optional siblings seen in the tree: `user.md` (47 patterns; **unused by the Go CLI**, see §3.4) and `README.md` (3 patterns: `extract_article_wisdom`, `extract_wisdom`, `extract_product_features`).

Conventional headings, per `data/patterns/official_pattern_template/system.md` (101 lines, the repo's own template): `# IDENTITY`, `# GOALS`, `# STEPS`, `# OUTPUT`, `# POSITIVE EXAMPLES`, `# NEGATIVE EXAMPLES`, `# OUTPUT INSTRUCTIONS`, `# INPUT`. Most real patterns use `# IDENTITY and PURPOSE` (167 files) instead of `# IDENTITY`.

`data/patterns/create_pattern/system.md` is the meta-pattern that generates new patterns, and it encodes the house style:
```
- Write the IDENTITY and PURPOSE section including the summary of the role using personal pronouns such as 'You'. Be sure to be extremely detailed in explaining the role. Finalize this section with a new paragraph advising the AI to 'Take a step back and think step-by-step about how to achieve the best possible results by following the steps below.'.
- Write the STEPS bullets from the prompt
- Write the OUTPUT INSTRUCTIONS bullets starting with the first bullet explaining the only output format. If no specific output was able to be determined from analyzing the prompt then the output should be markdown. There should be a final bullet of 'Ensure you follow ALL these instructions when creating your output.'.
- Write a final INPUT section with just the value 'INPUT:' inside it.
```

### 7.2 Registration & discovery

There is **no registry file** — discovery is filesystem lookup by directory name.

```go
// First check custom patterns directory if it exists
if o.CustomPatternsDir != "" {
	customPatternPath := filepath.Join(o.CustomPatternsDir, name, o.SystemPatternFile)
	if pattern, customErr := os.ReadFile(customPatternPath); customErr == nil { ... }
}
// Fallback to main patterns directory
patternPath := filepath.Join(o.Dir, name, o.SystemPatternFile)
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/plugins/db/fsdb/patterns.go:126-142`

Custom patterns win over built-ins. A pattern argument starting with `\`, `/`, `~`, or `.` is treated as a direct file path instead of a name (`patterns.go:58-82`), so `fabric -p ./my/prompt.md` works.

Built-in patterns are seeded by cloning this repo:
```go
const DefaultPatternsGitRepoUrl = "https://github.com/danielmiessler/fabric.git"
const DefaultPatternsGitRepoFolder = "data/patterns"
```
— `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/tools/patterns_loader.go:19-20`
`PopulateDB()` (`:94`) clones → copies → writes `unique_patterns.txt`; triggered by `--setup` or `-U/--updatepatterns`.

Every pattern gets an implicit `{{input}}` appended if absent:
```go
func (o *PatternsEntity) ensureInput(pattern *Pattern) {
	if !strings.Contains(pattern.Pattern, "{{input}}") {
		if !strings.HasSuffix(pattern.Pattern, "\n") { pattern.Pattern += "\n" }
		pattern.Pattern += "{{input}}"
	}
}
```
— `internal/plugins/db/fsdb/patterns.go:84-91`

Prompt assembly order (`internal/core/chatter.go:280-296`): `strategy.Prompt` → `context` → `pattern` → language-enforcement wrapper, joined by `joinPromptSections` (newline-joined, empties dropped, `chatter.go:47-57`). Result becomes the `system` message unless `--raw`.

### 7.3 Metadata

- `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/pattern_explanations.md` — 259 lines, a numbered one-line description per pattern. Header: *"# Brief one-line summary from AI analysis of what each pattern does"*. This is documentation only; nothing in `internal/` parses it.
- `~/.config/fabric/patterns/unique_patterns.txt` — generated list backing `-n/--latest` (`patterns_loader.go:365`, `fsdb/patterns.go:174-189`).
- `data/patterns/suggest_pattern/user.md` — a large embedded catalog used by the `suggest_pattern` pattern to recommend a pattern from a user request.

### 7.4 How a user adds a pattern

From `README.md:924-969`:
```bash
fabric --setup                                   # choose "Custom Patterns", set e.g. ~/my-custom-patterns
mkdir -p ~/my-custom-patterns/my-analyzer
echo "You are an expert analyzer of ..." > ~/my-custom-patterns/my-analyzer/system.md
fabric --pattern my-analyzer "analyze this text"
```
> - **Priority System**: Custom patterns take precedence over built-in patterns with the same name
> - **Seamless Integration**: Custom patterns appear in `fabric --listpatterns` alongside built-in ones
> - **Update Safe**: Your custom patterns are never affected by `fabric --updatepatterns`

(`README.md:858` gives the older single-directory form: *"Create patterns- you must create a .md file with the pattern and save it to `~/.config/fabric/patterns/[yourpatternname]`."*)

### 7.5 One full real pattern, verbatim

`/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/data/patterns/analyze_terraform_plan/system.md` — 24 lines, DevOps-relevant, shows the full house structure (identity → output sections → output instructions → input):

```markdown
# IDENTITY and PURPOSE

You are an expert Terraform plan analyser. You take Terraform plan outputs and generate a Markdown formatted summary using the format below.

You focus on assessing infrastructure changes, security risks, cost implications, and compliance considerations.

## OUTPUT SECTIONS

* Combine all of your understanding of the Terraform plan into a single, 20-word sentence in a section called ONE SENTENCE SUMMARY:.
* Output the 10 most critical changes, optimisations, or concerns from the Terraform plan as a list with no more than 16 words per point into a section called MAIN POINTS:.
* Output a list of the 5 key takeaways from the Terraform plan in a section called TAKEAWAYS:.

## OUTPUT INSTRUCTIONS

* Create the output using the formatting above.
* You only output human-readable Markdown.
* Output numbered lists, not bullets.
* Do not output warnings or notes—just the requested sections.
* Do not repeat items in the output sections.
* Do not start items with the same opening words.

## INPUT

INPUT:
```

Usage would be: `terraform plan -no-color | fabric -p analyze_terraform_plan`.

---

*Flag surface: 85 flags declared at `/Users/samuelchien/dev/software-devops/research/repos/automation/danielmiessler__fabric/internal/cli/flags.go:29-113`. None of them is a tool the model can invoke; all are host-side switches chosen by the human before the single request is sent.*
