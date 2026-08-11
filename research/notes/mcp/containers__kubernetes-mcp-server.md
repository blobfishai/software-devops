# containers/kubernetes-mcp-server — MCP tool surface

**Source:** `/Users/samuelchien/dev/software-devops/research/repos/mcp/containers__kubernetes-mcp-server` @ git commit `7e6f76a` (`git -C /Users/samuelchien/dev/software-devops/research/repos/mcp/containers__kubernetes-mcp-server rev-parse --short HEAD`), read 2026-08-11

**Language / framework:** Go (`go 1.26.4`, `go.mod:3`). MCP server built on the official Go SDK `github.com/modelcontextprotocol/go-sdk v1.7.0` (`go.mod:14`, used at `pkg/mcp/mcp.go:15` / `pkg/mcp/mcp.go:127`). Tool input schemas are `github.com/google/jsonschema-go v0.4.3` `*jsonschema.Schema` values (`go.mod:12`, `pkg/api/toolsets.go:9`, `pkg/api/toolsets.go:239`). CLI is cobra (`go.mod:17`, `pkg/kubernetes-mcp-server/cmd/root.go`). Binary name `kubernetes-mcp-server` (`pkg/version/version.go:6`).

**Registration entrypoint:**
- Toolset packages self-register in `init()` → `toolsets.Register(&Toolset{})` (e.g. `pkg/toolsets/core/toolset.go:52`), into the global registry at `pkg/toolsets/toolsets.go:17` (`func Register`) backed by `toolsetReg` (`pkg/toolsets/toolsets.go:11`).
- All toolset packages are blank-imported to trigger those `init()`s at `pkg/mcp/modules.go:4`–`pkg/mcp/modules.go:11`.
- The server converts and installs tools into the SDK in `func (s *Server) applyToolsets` — `pkg/mcp/mcp.go:219` (collection at `pkg/mcp/mcp.go:387` `collectApplicableTools`; conversion at `pkg/mcp/tools_gosdk.go:17` `ServerToolToGoSdkTool`; SDK `AddTool` via `commitItems` at `pkg/mcp/mcp.go:298`).

**Toolsets:** exact names (from `GetName()`):
| Toolset | `GetName()` cite | Default? |
|---|---|---|
| `config` | `pkg/toolsets/config/toolset.go:15` | ✓ |
| `core` | `pkg/toolsets/core/toolset.go:21` | ✓ |
| `helm` | `pkg/toolsets/helm/toolset.go:15` | |
| `kcp` | `pkg/toolsets/kcp/toolset.go:15` | |
| `kiali` | `pkg/toolsets/kiali/toolset.go:20` → `pkg/toolsets/kiali/internal/defaults/defaults.go:4` (`DefaultToolsetName = "kiali"`, overridable at build time via `ToolsetNameOverride()`, `pkg/toolsets/kiali/internal/defaults/defaults.go:8`) | |
| `kubevirt` | `pkg/toolsets/kubevirt/toolset.go:21` | |
| `netobserv` | `pkg/toolsets/netobserv/toolset.go:17` → `pkg/toolsets/netobserv/internal/defaults/defaults.go:4` | |
| `tekton` | `pkg/toolsets/tekton/toolset.go:16` | |

Defaults are `["core", "config"]` — `pkg/config/config_default.go:17` (`Toolsets: []string{"core", "config"}` inside `BaseDefault()`); downstream builds may override via `defaultOverrides()` (`pkg/config/config_default.go:31`).

Selection: `--toolsets` comma-separated flag (`pkg/kubernetes-mcp-server/cmd/root.go:181`, flag name constant `flagToolsets = "toolsets"` at `pkg/kubernetes-mcp-server/cmd/root.go:78`) or TOML `toolsets` (`pkg/config/config.go:61`). Names are validated against the registry by `toolsets.Validate` (`pkg/toolsets/toolsets.go:37`, called from `pkg/config/config.go:545`); an unknown name errors with `invalid toolset name: %s, valid names are: %s` (`pkg/toolsets/toolsets.go:40`). The configured names are resolved to `api.Toolset` instances in `Configuration.Toolsets()` (`pkg/mcp/mcp.go:41`).

Note: there is **no** `metrics` toolset. `pkg/metrics/` is OpenTelemetry/Prometheus server telemetry, not an MCP toolset. Kubernetes metrics live in `core` (`pods_top`, `nodes_top`, `nodes_stats_summary`).

---

## Full tool list (52 tools)

Legend: **R** = `ReadOnlyHint: true`; **W** = write (ReadOnlyHint absent or false). "Destructive" = `DestructiveHint: true`.

### `config` (3 tools) — `pkg/toolsets/config/toolset.go:22` → `initConfiguration()` `pkg/toolsets/config/configuration.go:39`
- `configuration_contexts_list` — R — list kubeconfig context names + server URLs — `pkg/toolsets/config/configuration.go:43`
- `targets_list` — R — generic "list available targets" tool; renamed to `{targetParameterName}_list` by the mutator before registration — `pkg/toolsets/config/configuration.go:67` (rename logic `pkg/mcp/tool_mutator.go:26` `TargetsListToolName`, `pkg/mcp/tool_mutator.go:74` `WithTargetListTool`)
- `configuration_view` — R — return the current kubeconfig as YAML — `pkg/toolsets/config/configuration.go:86`

`configuration_contexts_list` and `targets_list` are mutually exclusive and both are dropped when the provider is single-target — `pkg/mcp/tool_filter.go:23` `ShouldIncludeTargetListTool` (single-target drop at `pkg/mcp/tool_filter.go:29`; kubeconfig/non-kubeconfig exclusivity at `pkg/mcp/tool_filter.go:38`–`pkg/mcp/tool_filter.go:44`).

### `core` (19 tools) — `pkg/toolsets/core/toolset.go:28`
- `events_list` — R — list Kubernetes events (all namespaces or one), optional field selector — `pkg/toolsets/core/events.go:17`
- `namespaces_list` — R — list namespaces — `pkg/toolsets/core/namespaces.go:19`
- `projects_list` — R — list OpenShift Projects; hidden unless a target exposes `project.openshift.io/v1 Project` (only when target-compat filtering is enabled) — `pkg/toolsets/core/namespaces.go:41` (filter `pkg/toolsets/core/namespaces.go:54`)
- `nodes_log` — R — kubelet/node logs via the API-server proxy — `pkg/toolsets/core/nodes.go:22`
- `nodes_stats_summary` — R — kubelet Summary API stats (incl. PSI) — `pkg/toolsets/core/nodes.go:52`
- `nodes_top` — R — node CPU/memory from the metrics server — `pkg/toolsets/core/nodes.go:72`
- `pods_list` — R — list pods in all namespaces — `pkg/toolsets/core/pods.go:20`
- `pods_list_in_namespace` — R — list pods in one namespace — `pkg/toolsets/core/pods.go:45`
- `pods_get` — R — get a single Pod — `pkg/toolsets/core/pods.go:75`
- `pods_delete` — W, **Destructive** — delete a Pod (plus its managed Service/Route if created by `pods_run`) — `pkg/toolsets/core/pods.go:99`
- `pods_top` — R — pod CPU/memory from the metrics server — `pkg/toolsets/core/pods.go:123`
- `pods_exec` — W, **Destructive** — exec a command in a pod container — `pkg/toolsets/core/pods.go:157`
- `pods_log` — R — container logs — `pkg/toolsets/core/pods.go:191`
- `pods_run` — W (DestructiveHint false) — create a Pod from an image, optional exposed port — `pkg/toolsets/core/pods.go:229`
- `resources_list` — R — list any GVK, optional namespace/label/field selector — `pkg/toolsets/core/resources.go:37`
- `resources_get` — R — get any GVK by name — `pkg/toolsets/core/resources.go:75`
- `resources_create_or_update` — W, **Destructive** — Server-Side Apply of a full YAML/JSON manifest — `pkg/toolsets/core/resources.go:107`
- `resources_delete` — W, **Destructive** — delete any GVK by name, optional gracePeriodSeconds — `pkg/toolsets/core/resources.go:127`
- `resources_scale` — W, **Destructive** — read or set `.spec.replicas` via the `scale` subresource — `pkg/toolsets/core/resources.go:163`

### `helm` (3 tools) — `pkg/toolsets/helm/toolset.go:22`
- `helm_install` — W (DestructiveHint false) — install a chart (Wait=true, 5m timeout) — `pkg/toolsets/helm/helm.go:16` (impl `pkg/helm/helm.go:37`, wait/timeout `pkg/helm/helm.go:53`–`pkg/helm/helm.go:54`)
- `helm_list` — R — list releases in a namespace or all namespaces — `pkg/toolsets/helm/helm.go:49`
- `helm_uninstall` — W, **Destructive** — uninstall a release (Wait=true, 5m timeout) — `pkg/toolsets/helm/helm.go:72` (impl `pkg/helm/helm.go:98`)

### `kcp` (2 tools) — `pkg/toolsets/kcp/toolset.go:22`
- `kcp_workspaces_list` — R — list kcp workspaces — `pkg/toolsets/kcp/workspaces.go:18`
- `kcp_workspace_describe` — R — describe one workspace by name/path — `pkg/toolsets/kcp/workspaces.go:37`

### `kiali` (11 tools) — `pkg/toolsets/kiali/toolset.go:27`. Names are `defaults.ToolsetName() + "<suffix>"`, i.e. `kiali_*` by default. All are forced `ClusterAware=false` (`pkg/toolsets/kiali/toolset.go:43`–`pkg/toolsets/kiali/toolset.go:45`).
- `kiali_get_mesh_traffic_graph` — R — service-to-service traffic topology/metrics — `pkg/toolsets/kiali/tools/get_mesh_traffic_graph.go:16` (annotations `:41`)
- `kiali_get_mesh_status` — R — mesh/control-plane/observability health — `pkg/toolsets/kiali/tools/get_mesh_status.go:16` (annotations `:25`)
- `kiali_manage_istio_config_read` — R — list/get Istio + Gateway API + Inference API config — `pkg/toolsets/kiali/tools/manage_istio_config_read.go:16` (annotations `:68`)
- `kiali_manage_istio_config` — W, **Destructive** — create/patch/delete Istio & Gateway API config — `pkg/toolsets/kiali/tools/manage_istio_config.go:16` (annotations `:62`)
- `kiali_list_mesh_clusters` — R — list mesh clusters Kiali can reach — `pkg/toolsets/kiali/tools/list_clusters.go:16` (annotations `:25`)
- `kiali_get_resource_details` — R — list resources or get details for one — `pkg/toolsets/kiali/tools/list_or_get_resources.go:16` (annotations `:47`)
- `kiali_list_traces` — R — list distributed traces for a service — `pkg/toolsets/kiali/tools/list_traces.go:16` (annotations `:54`)
- `kiali_get_trace_details` — R — one trace's span hierarchy — `pkg/toolsets/kiali/tools/get_traces_details.go:16` (annotations `:31`)
- `kiali_get_pod_performance` — R — pod CPU/mem vs requests/limits, human-readable text — `pkg/toolsets/kiali/tools/get_pod_performance.go:16` (annotations `:52`)
- `kiali_get_logs` — R — pod/workload logs via Kiali — `pkg/toolsets/kiali/tools/get_logs.go:16` (annotations `:67`)
- `kiali_get_metrics` — R — compact JSON Istio metrics summary — `pkg/toolsets/kiali/tools/get_metrics.go:16` (annotations `:78`)

### `kubevirt` (5 tools) — `pkg/toolsets/kubevirt/toolset.go:28`
- `vm_clone` — W, **Destructive** — clone a VM via `VirtualMachineClone` — `pkg/toolsets/kubevirt/vm/clone/tool.go:19` (annotations `:39`)
- `vm_create` — W, **Destructive** — create a VirtualMachine (Halted by default) — `pkg/toolsets/kubevirt/vm/create/tool.go:25` (annotations `:105`)
- `vm_guest_info` — R — QEMU guest-agent OS/network/user info — `pkg/toolsets/kubevirt/vm/guestagent/tool.go:30` (annotations `:52`)
- `vm_lifecycle` — W, **Destructive** — start/stop/restart a VM — `pkg/toolsets/kubevirt/vm/lifecycle/tool.go:28` (annotations `:49`)
- `vm_troubleshoot` — R — automated VM root-cause diagnostics report — `pkg/toolsets/kubevirt/vm/troubleshoot/tool.go:26` (annotations `:55`; GVK-compat filter `:63`)

### `netobserv` (3 tools) — `pkg/toolsets/netobserv/toolset.go:24`. Names are `defaults.ToolsetName() + "<suffix>"`, i.e. `netobserv_*` by default. All three use the shared `readOnlyAnnotations()` helper (`pkg/toolsets/netobserv/tools/schema.go:73`) → R, non-destructive, idempotent, open-world.
- `netobserv_list_flows` — R — list flow records from Loki — `pkg/toolsets/netobserv/tools/list_flows.go:10` (annotations `:16`)
- `netobserv_get_flow_metrics` — R — aggregated topology/time-series flow metrics — `pkg/toolsets/netobserv/tools/get_flow_metrics.go:52` (annotations `:58`)
- `netobserv_export_flows` — R — export flows as CSV — `pkg/toolsets/netobserv/tools/export_flows.go:24` (annotations `:30`)

### `tekton` (6 tools) — `pkg/toolsets/tekton/toolset.go:23`
- `tekton_pipeline_start` — W (DestructiveHint false) — create a PipelineRun for a Pipeline — `pkg/toolsets/tekton/pipeline.go:19` (annotations `:41`)
- `tekton_pipelinerun_lifecycle` — W, **Destructive** — restart or cancel a PipelineRun — `pkg/toolsets/tekton/pipelinerun.go:33` (annotations `:36`)
- `tekton_pipelinerun_logs` — R — logs for all TaskRuns of a PipelineRun — `pkg/toolsets/tekton/pipelinerun.go:48` (annotations `:78`)
- `tekton_task_start` — W (DestructiveHint false) — create a TaskRun for a Task — `pkg/toolsets/tekton/task.go:19` (annotations `:41`)
- `tekton_taskrun_restart` — W (DestructiveHint false) — recreate a TaskRun with the same spec — `pkg/toolsets/tekton/taskrun.go:26` (annotations `:42`)
- `tekton_taskrun_logs` — R — logs from a TaskRun's pod — `pkg/toolsets/tekton/taskrun.go:54` (annotations `:80`)

### Tool annotations

The annotation struct is `api.ToolAnnotations` with `Title`, `ReadOnlyHint *bool`, `DestructiveHint *bool`, `IdempotentHint *bool`, `OpenWorldHint *bool` — `pkg/api/toolsets.go:245`–`pkg/api/toolsets.go:264`. They are copied onto the SDK tool in `ServerToolToGoSdkTool` at `pkg/mcp/tools_gosdk.go:38`–`pkg/mcp/tools_gosdk.go:44`; note `ReadOnlyHint` and `IdempotentHint` are dereferenced with `false` default (`pkg/mcp/tools_gosdk.go:40`, `:42`) while `DestructiveHint`/`OpenWorldHint` are passed through as pointers (`:41`, `:43`).

Filtering by `--read-only` / `--disable-destructive` happens in **one** place — `func (c *Configuration) isToolApplicable`, `pkg/mcp/mcp.go:68`:

```go
if c.ReadOnly && !ptr.Deref(tool.Tool.Annotations.ReadOnlyHint, false) {   // pkg/mcp/mcp.go:69
    return false
}
if c.DisableDestructive && ptr.Deref(tool.Tool.Annotations.DestructiveHint, false) { // pkg/mcp/mcp.go:72
    return false
}
```

So `--read-only` keeps only tools with an explicit `ReadOnlyHint: true`; `--disable-destructive` removes only tools with an explicit `DestructiveHint: true`. Same function also applies `enabled_tools` allowlist (`pkg/mcp/mcp.go:75`), `disabled_tools` denylist (`pkg/mcp/mcp.go:78`) and target-compatibility filters (`pkg/mcp/mcp.go:81`). It is composed into the tool filter at `pkg/mcp/mcp.go:388`. Flags: `--read-only` `pkg/kubernetes-mcp-server/cmd/root.go:183`, `--disable-destructive` `pkg/kubernetes-mcp-server/cmd/root.go:184`; TOML keys `read_only` / `disable_destructive` `pkg/config/config.go:58`/`pkg/config/config.go:60`.

Concretely, with `--read-only` the surviving core tools are the R-marked ones above (`events_list`, `namespaces_list`, `projects_list`, `nodes_*`, `pods_list`, `pods_list_in_namespace`, `pods_get`, `pods_top`, `pods_log`, `resources_list`, `resources_get`); `pods_run` and `tekton_*_start` are dropped even though they are not destructive, because they carry no `ReadOnlyHint`.

---

## Key tools

| Tool | Params (`name`: type — required/optional) | Returns (concrete shape) | Source |
|---|---|---|---|
| `resources_list` | `apiVersion`: string — required; `kind`: string — required; `namespace`: string — optional (empty = all namespaces); `labelSelector`: string — optional (regex-constrained, `pkg/toolsets/core/toolset.go:11`); `fieldSelector`: string — optional (regex `pkg/toolsets/core/toolset.go:14`) | Text depends on `--list-output` (default `table`, `pkg/config/config_default.go:16`). Table mode: kubectl-style plaintext table from `printers.NewTablePrinter` with `WithKind/Wide/ShowLabels` (`pkg/output/output.go:141`–`:146`), plus `structuredContent` = `[]map[string]any` keyed by column names, with `Namespace` injected (`pkg/output/output.go:153`–`:176`). YAML mode: YAML text + `structuredContent` = list items as `[]map[string]any` (`pkg/output/output.go:67`–`:82`). Handler `pkg/toolsets/core/resources.go:240` | `pkg/toolsets/core/resources.go:37` |
| `resources_get` | `apiVersion`: string — required; `kind`: string — required; `name`: string — required; `namespace`: string — optional | **Always YAML**, regardless of `--list-output` — handler calls `output.Yaml.PrintObjStructured` directly (`pkg/toolsets/core/resources.go:275`). `managedFields` stripped (`pkg/output/output.go:192`). `structuredContent` = the object as `map[string]any` (`pkg/output/output.go:79`–`:80`) | `pkg/toolsets/core/resources.go:75` |
| `resources_create_or_update` | `resource`: string — required (complete YAML or JSON manifest; `\n---\n` separated multi-doc supported, `pkg/kubernetes/resources.go:59`) | Text: `"# The following resources (YAML) have been created or updated successfully\n"` + YAML of the applied objects (`pkg/toolsets/core/resources.go:301`). No structuredContent. Applied via Server-Side Apply with `FieldManager: "kubernetes-mcp-server"`, `Force: true` (`pkg/kubernetes/resources.go:194`–`:195`); `.status` is stripped from the input (`pkg/kubernetes/resources.go:68`) | `pkg/toolsets/core/resources.go:107` |
| `resources_delete` | `apiVersion`: string — required; `kind`: string — required; `name`: string — required; `namespace`: string — optional; `gracePeriodSeconds`: integer — optional | Literal text `"Resource deleted successfully"` (`pkg/toolsets/core/resources.go:341`) | `pkg/toolsets/core/resources.go:127` |
| `pods_list` | `labelSelector`: string — optional; `fieldSelector`: string — optional. (No `namespace`; all namespaces.) | `params.ListOutput.PrintObj(ret)` → table text by default, YAML if `--list-output yaml`. **No structuredContent** (PrintObj returns a string only) — `pkg/toolsets/core/pods.go:276`, interface `pkg/output/output.go:35` | `pkg/toolsets/core/pods.go:20` |
| `pods_log` | `name`: string — required; `namespace`: string — optional; `container`: string — optional (auto-resolved if empty, `pkg/kubernetes/pods.go:123`–`:128`); `tail`: integer — optional, default 100, min 0; `previous`: boolean — optional | Raw log text. If empty: `"The pod %s in namespace %s has not logged any message yet"` (`pkg/toolsets/core/pods.go:399`) | `pkg/toolsets/core/pods.go:191` |
| `pods_exec` | `name`: string — required; `command`: array of string — required; `namespace`: string — optional; `container`: string — optional | stdout; falls back to stderr if stdout empty; if both empty: `"The executed command in pod %s in namespace %s has not produced any output"` (`pkg/toolsets/core/pods.go:375`–`:381`) | `pkg/toolsets/core/pods.go:157` |
| `pods_top` | `all_namespaces`: boolean — optional, default `true`; `namespace`: string — optional; `name`: string — optional; `label_selector`: string — optional | kubectl `top`-style plaintext table rendered by `metricsutil.NewTopCmdPrinter(...).PrintPodMetrics` (`pkg/toolsets/core/pods.go:341`–`:342`). Not YAML, not JSON | `pkg/toolsets/core/pods.go:123` |
| `events_list` | `namespace`: string — optional (empty = all namespaces); `fieldSelector`: string — optional | `"# The following events (YAML format) were found:\n"` + YAML map (`pkg/toolsets/core/events.go:62`); if none: `"# No events found"` (`pkg/toolsets/core/events.go:56`) | `pkg/toolsets/core/events.go:17` |
| `namespaces_list` | `fieldSelector`: string — optional | `params.ListOutput.PrintObj(ret)` → table text (default) or YAML — `pkg/toolsets/core/namespaces.go:76` | `pkg/toolsets/core/namespaces.go:19` |
| `helm_install` | `chart`: string — required; `values`: object — optional; `name`: string — optional (generated if absent); `namespace`: string — optional | YAML of a simplified release map: `name`, `namespace`, `revision`, `chart`, `chartVersion`, `appVersion`, `status`, `lastDeployed` (RFC1123Z) — `pkg/helm/helm.go:70` + `pkg/helm/helm.go:178`–`:198` | `pkg/toolsets/helm/helm.go:16` |
| `helm_list` | `namespace`: string — optional; `all_namespaces`: boolean — optional (default false, `pkg/toolsets/helm/helm.go:135`) | YAML array of the same simplified release maps (`pkg/helm/helm.go:91`); if none: literal `"No Helm releases found"` (`pkg/helm/helm.go:89`) | `pkg/toolsets/helm/helm.go:49` |
| `configuration_view` | `minified`: boolean — optional, default `true` (`pkg/toolsets/config/configuration.go:175`) | kubeconfig serialized as YAML via `output.MarshalYaml` (`pkg/toolsets/config/configuration.go:183`) | `pkg/toolsets/config/configuration.go:86` |

Additional injected parameter: when the provider is multi-target, every cluster-aware tool gets an extra optional string property named after the provider's target parameter (`"context"` for the kubeconfig provider — `pkg/kubernetes/provider_kubeconfig.go:16`), described as `"Optional parameter selecting which %s to run the tool in. Defaults to %s if not set"` — `pkg/mcp/tool_mutator.go:29` (`WithTargetParameter`), property builder `pkg/mcp/tool_mutator.go:54`. Tools opting out set `ClusterAware: ptr.To(false)` (e.g. `pkg/toolsets/config/configuration.go:56`, `pkg/toolsets/kiali/toolset.go:44`).

---

## Resources

**None.** Every registered toolset returns `nil` from both `GetResources()` and `GetResourceTemplates()`:
`pkg/toolsets/config/toolset.go:33`/`:37`, `pkg/toolsets/core/toolset.go:44`/`:48`, `pkg/toolsets/helm/toolset.go:33`/`:37`, `pkg/toolsets/kcp/toolset.go:32`/`:36`, `pkg/toolsets/kiali/toolset.go:70`/`:74`, `pkg/toolsets/kubevirt/toolset.go:45`/`:49`, `pkg/toolsets/netobserv/toolset.go:36`/`:40`, `pkg/toolsets/tekton/toolset.go:36`/`:40`.

The machinery exists (`api.ServerResource` `pkg/api/toolsets.go:140`, `api.ServerResourceTemplate` `pkg/api/toolsets.go:160`, collection at `pkg/mcp/mcp.go:425` and `pkg/mcp/mcp.go:242`–`:243`) but nothing is registered. The auto-generated README sections are correspondingly empty (`README.md:903`–`:906`, `README.md:910`–`:913`).

## Prompts

`pkg/prompts/` holds the *config-defined* prompt engine (`prompts.ToServerPrompts` `pkg/prompts/prompts.go:11`; `{{arg}}` substitution `pkg/prompts/prompts.go:55`; required-arg validation `pkg/prompts/prompts.go:28`–`:34`). Users may declare arbitrary prompts in TOML via `prompts = [...]` (`pkg/config/config.go:67`); those are merged over toolset prompts, config winning on name collision (`pkg/mcp/mcp.go:420`–`:421`, `pkg/prompts/prompts.go:71`).

Built-in prompts registered by toolsets (16 total):

**core (1)** — `pkg/toolsets/core/toolset.go:38` → `initHealthChecks()` `pkg/toolsets/core/health_check.go:21`
- `cluster-health-check` — args: `namespace` (optional), `check_events` (optional) — `pkg/toolsets/core/health_check.go:26` (args `:31`, `:36`)

**kiali (11)** — `pkg/toolsets/kiali/toolset.go:49`
- `mesh-list-applications` — arg `namespace` (optional) — `pkg/toolsets/kiali/prompts/list_resources.go:16`
- `mesh-list-namespaces` — no args — `pkg/toolsets/kiali/prompts/list_resources.go:36`
- `mesh-list-services` — arg `namespace` (optional) — `pkg/toolsets/kiali/prompts/list_resources.go:49`
- `mesh-list-workloads` — arg `namespace` (optional) — `pkg/toolsets/kiali/prompts/list_resources.go:69`
- `list-istio-config` — arg `namespace` (optional) — `pkg/toolsets/kiali/prompts/list_resources.go:89`
- `mesh-topology` — no args — `pkg/toolsets/kiali/prompts/list_resources.go:160`
- `mesh-health-check` — arg `namespace` (optional) — `pkg/toolsets/kiali/prompts/mesh_health_check.go:16`
- `traffic-topology` — arg `namespaces` (**required**) — `pkg/toolsets/kiali/prompts/traffic_topology.go:19` (arg `:24`)
- `service-troubleshoot` — args `namespace` (required), `service` (required), `workload` (optional) — `pkg/toolsets/kiali/prompts/service_troubleshoot.go:16`
- `trace-analysis` — args `namespace` (required), `service` (required) — `pkg/toolsets/kiali/prompts/trace_analysis.go:16`
- `istio-config-review` — arg `namespace` (required) — `pkg/toolsets/kiali/prompts/istio_config_review.go:16`

**kubevirt (2)** — `pkg/toolsets/kubevirt/toolset.go:38`
- `vm-troubleshoot` — args `namespace` (required), `name` (required) — `pkg/toolsets/kubevirt/vm_troubleshoot.go:24` (args `:29`, `:34`)
- `windows-golden-image` — args `winImageDownloadURL` (required), `namespace`, `windowsVersion`, `pipelineVersion` — `pkg/toolsets/kubevirt/windows_golden_image.go:66` (args `:71`, `:76`, `:81`, `:86`)

**tekton (1)** — `pkg/toolsets/tekton/toolset.go:32`
- `pipeline-troubleshoot` — args `namespace` (required), `name` (required) — `pkg/toolsets/tekton/pipeline_troubleshoot.go:23` (args `:28`, `:33`)

`config`, `helm`, `kcp`, `netobserv` return `nil` prompts (`pkg/toolsets/config/toolset.go:28`, `pkg/toolsets/helm/toolset.go:28`, `pkg/toolsets/kcp/toolset.go:28`, `pkg/toolsets/netobserv/toolset.go:32`).

---

## Auth model

**Cluster credential resolution (strategy):** `resolveStrategy` — `pkg/kubernetes/provider.go:103`. Order: explicit `cluster_provider_strategy` → if `kubeconfig` path set, `kubeconfig` → if `InClusterConfig()` succeeds, `in-cluster` → else `kubeconfig` (`pkg/kubernetes/provider.go:104`–`:116`).

**kubeconfig:** `NewKubeconfigManager` uses `clientcmd.NewDefaultPathOptions()` (i.e. `KUBECONFIG` env / `~/.kube/config`) and overrides `LoadingRules.ExplicitPath` with `--kubeconfig` when set — `pkg/kubernetes/manager.go:36`–`:39`. Flag: `--kubeconfig` (`pkg/kubernetes-mcp-server/cmd/root.go:180`, constant `pkg/kubernetes-mcp-server/cmd/root.go:77`); TOML `kubeconfig` (`pkg/config/config.go:48`). Context resolution: explicit → `current-context` → sole context auto-selected → error listing available contexts — `pkg/kubernetes/manager.go:67`–`:105`.

**In-cluster:** `NewInClusterManager` (`pkg/kubernetes/manager.go:107`) uses `rest.InClusterConfig()` (`pkg/kubernetes/manager.go:116`) and refuses if `--kubeconfig` is also set (`pkg/kubernetes/manager.go:108`–`:110`).

**Per-request bearer-token pass-through:** `Manager.Derived` reads the `Authorization` context value (`pkg/kubernetes/manager.go:169`, key `OAuthAuthorizationHeader = HeaderKey("Authorization")` at `pkg/kubernetes/kubernetes.go:30`). If a `Bearer ` token is present it builds a derived `rest.Config` carrying **only** the token plus server-verification TLS (CA bundle / server name), explicitly clearing kubeconfig `AuthInfos` and impersonation — `pkg/kubernetes/manager.go:192`–`:215`. If no token, it falls back to kubeconfig credentials **unless** `require_oauth` is true, in which case it errors `"oauth token required"` — `pkg/kubernetes/manager.go:179`–`:185`. The header is put on the context by `authHeaderPropagationMiddleware` (`pkg/mcp/mcp.go:175`).

**cluster_auth_mode:** `"passthrough"` (default) or `"kubeconfig"` — `pkg/config/config.go:115`, `ResolveClusterAuthMode` `pkg/config/config.go:742`. `kubeconfig` mode is rejected together with `require_oauth=true` (all users would share one cluster identity, breaking per-user audit) — `pkg/config/config.go:755`–`:757`.

**OAuth (`--require-oauth`):** flag at `pkg/kubernetes-mcp-server/cmd/root.go:186` (hidden, `:187`); TOML `require_oauth` `pkg/config/config.go:71`. HTTP enforcement lives in `pkg/http/authorization.go`: missing token → 401 with `WWW-Authenticate` + `error="missing_token"` (`pkg/http/authorization.go:93`, writer at `pkg/http/authorization.go:22`–`:24`); empty token → `error="invalid_token"` (`:106`); OIDC provider down → `error="temporarily_unavailable"` (`:141`); invalid token → `error="invalid_token"` (`:165`). Audience is appended to the challenge when `oauth_audience` is set (`pkg/http/authorization.go:83`). Offline validation: `JWTClaims.ValidateOffline` (`pkg/http/authorization.go:207`), online: `ValidateWithProvider` (`pkg/http/authorization.go:219`). `require_oauth` without `authorization_url` is refused unless `skip_jwt_verification=true` — `pkg/config/config.go:637`–`:651` (flag `--skip-jwt-verification` `pkg/kubernetes-mcp-server/cmd/root.go:192`).

**Token exchange (`pkg/tokenexchange/`):** strategies `rfc8693` (`pkg/tokenexchange/rfc8693_exchanger.go`), `keycloak-v1` (`pkg/tokenexchange/keycloak_v1_exchanger.go`), `entra-obo` (`pkg/tokenexchange/entra_obo_exchanger.go`); registry `pkg/tokenexchange/registry.go`. Configured by `token_exchange_strategy`, `sts_client_id`, `sts_client_secret`, `sts_audience`, `sts_scopes`, `sts_auth_style` (`params`|`header`|`assertion`|`federated`) — `pkg/config/config.go:96`–`:111`; validation `pkg/config/config.go:659`–`:692`. The exchanged token replaces the original in the Authorization context value — `pkg/kubernetes/token_exchange.go:60`, `:80`, `:116`, `:200`. Token exchange requires `require_oauth=true` (`pkg/config/config.go:762`–`:764`). Provider wiring: `WithTokenExchange` `pkg/kubernetes/provider.go:56`, `newTokenExchangingProvider` `pkg/kubernetes/provider.go:93`. `pkg/oauth/state.go` holds the shared OAuth state.

**RBAC implications:** because the derived client carries the caller's bearer token, all Kubernetes RBAC applies as that user. Additionally the server can pre-check RBAC with `SelfSubjectAccessReview` when `validation_enabled=true` (`pkg/config/config.go:168`; validators wired at `pkg/kubernetes/accesscontrol_round_tripper.go:66`–`:71`; `pkg/kubernetes/rbac_validator.go:45` emits a permission-denied validation error). `resources_list` also degrades gracefully: if the caller cannot `list` cluster-wide it silently narrows to the configured/default namespace — `pkg/kubernetes/resources.go:35`–`:37`.

---

## Pagination

**Label / field selectors:** yes. `resources_list` accepts `labelSelector` and `fieldSelector` (`pkg/toolsets/core/resources.go:54`, `:59`), both regex-constrained (`pkg/toolsets/core/toolset.go:11`, `pkg/toolsets/core/toolset.go:14`). Same for `pods_list` / `pods_list_in_namespace` (`pkg/toolsets/core/pods.go:25`, `:30`, `:54`, `:59`), `namespaces_list` (`pkg/toolsets/core/namespaces.go:24`), `events_list` (`pkg/toolsets/core/events.go:26`), `pods_top` `label_selector` (`pkg/toolsets/core/pods.go:141`), `nodes_top` `label_selector` (`pkg/toolsets/core/nodes.go:81`).

**Limits / continue tokens: NOT exposed.** `api.ListOptions` embeds the full `metav1.ListOptions` (which has `Limit` and `Continue`) — `pkg/api/kubernetes.go:20`–`:23` — but the tool input schemas expose only `labelSelector` / `fieldSelector`, and the handlers only ever set `LabelSelector`, `FieldSelector`, and `AsTable` (`pkg/toolsets/core/resources.go:206`–`:225`, `pkg/toolsets/core/pods.go:264`–`:268`). The options struct is passed straight to `DynamicClient().…List(ctx, options.ListOptions)` (`pkg/kubernetes/resources.go:41`), so the server always requests an unbounded list.

**Truncation of large lists: none for core Kubernetes tools.** No truncation logic exists in `pkg/output/output.go` or `pkg/kubernetes/resources.go`. The only size guard on the whole path is the *inbound* HTTP body limit `max_body_bytes`, default 16 MiB (`pkg/config/config_default.go:21`), which does not bound responses.

**netobserv is the exception** — responses are byte-capped: JSON endpoints at 4 MiB (`maxJSONResponseBodySize = 4 << 20`, `pkg/netobserv/netobserv.go:175`, used at `pkg/netobserv/netobserv.go:179`) where exceeding it is a hard error `"netobserv API response exceeded maximum allowed size of %d bytes"` (`pkg/netobserv/netobserv.go:232`); CSV export at 2 MiB (`DefaultExportMaxBodyBytes = 2 << 20`, `pkg/toolsets/netobserv/tools/defaults.go:14`, used at `pkg/toolsets/netobserv/tools/export_flows.go:45`) where the body is silently truncated and flagged (`pkg/netobserv/netobserv.go:234`–`:235`). netobserv flow queries also default to `limit = 100` (`DefaultLimit = 100`, `pkg/toolsets/netobserv/tools/defaults.go:5`, schema default `pkg/toolsets/netobserv/tools/schema.go:31`) and `DefaultTimeRangeSeconds = 300` (`pkg/toolsets/netobserv/tools/defaults.go:4`).

**Pod logs:** `tail` — optional integer, **default 100**, minimum 0 — schema at `pkg/toolsets/core/pods.go:208`–`:213`, default value `kubernetes.DefaultTailLines` = `int64(100)` (`pkg/kubernetes/pods.go:28`). The default is applied server-side too: if `tail <= 0` the handler passes 0 and `PodsLog` sets `TailLines = ptr.To(DefaultTailLines)` (`pkg/kubernetes/pods.go:136`–`:142`; handler passes `p.OptionalInt64("tail", 0)` at `pkg/toolsets/core/pods.go:391`). `previous` boolean is optional (`pkg/toolsets/core/pods.go:215`). **There is no `since` / `sinceSeconds` / `sinceTime` / `limitBytes` parameter** — `v1.PodLogOptions` is constructed with only `Container` and `Previous` plus `TailLines` (`pkg/kubernetes/pods.go:132`–`:142`).

**Node logs:** `tailLines` — optional integer, schema default 100, minimum 0, and **0 means all logs** per the description (`pkg/toolsets/core/nodes.go:35`–`:40`).

**Kiali logs:** `tail` default `DefaultTail = 50` (`pkg/toolsets/kiali/tools/defaults.go:16`, schema `pkg/toolsets/kiali/tools/get_logs.go:41`–`:45`); Kiali list default `DefaultLimit = 10`, `DefaultLookbackSeconds = 600` (`pkg/toolsets/kiali/tools/defaults.go:15`, `:17`).

---

## Rate limits

**Server-side MCP rate limiting exists but is off by default.** `HTTPConfig.RateLimitRPS` — "When set to 0 (default), rate limiting is disabled" — `pkg/config/http_config.go:23`; `RateLimitBurst` `pkg/config/http_config.go:29`, falling back to `DefaultRateLimitBurst = 10` when zero (`pkg/config/http_config.go:7`, applied at `pkg/mcp/mcp.go:168`–`:170`). Implementation: per-session `rate.Limiter` keyed by session ID, stale entries reaped every 5 minutes with a 10-minute idle threshold, sessions with an empty ID (STDIO pre-init) bypass it — `pkg/mcp/middleware.go:331`–`:369`, installed at `pkg/mcp/mcp.go:163`. Negative values are rejected at validation (`pkg/config/http_config.go:34`–`:41`). `BaseDefault()` does not set `RateLimitRPS`, so the effective default is 0/disabled (`pkg/config/config_default.go:19`–`:22`).

**Kubernetes client-side rate limits (QPS/Burst)** are only overridden from env vars `KUBE_CLIENT_QPS` / `KUBE_CLIENT_BURST`, described as "primarily useful for tests" — `pkg/kubernetes/manager.go:235`–`:239` (`applyRateLimitFromEnv`, called at `pkg/kubernetes/manager.go:151`); otherwise client-go defaults apply.

**No per-tool or per-user quota mechanism found.**

---

## Error shapes

**Transport shape.** Tool handlers return `*api.ToolCallResult` whose `Error` field is a non-protocol error meant for the model (`pkg/api/toolsets.go:73`). It becomes an MCP `CallToolResult` with `IsError: true` and a single `TextContent` whose text is exactly `err.Error()` — `pkg/mcp/mcp.go:639`–`:649` (`NewStructuredResult`), and identically in `NewTextResult` `pkg/mcp/mcp.go:604`–`:614`. The handler wrapper is `pkg/mcp/tools_gosdk.go:100`. So the model sees the *raw Go error string*, no JSON envelope, no error code.

**Literal formats for core tools** (the `%w`-wrapped k8s error is client-go's `StatusError`, e.g. `pods "nope" not found` or `pods is forbidden: User "x" cannot list resource "pods" in API group "" in the namespace "y"`):

| Situation | Literal string sent to the model | Cite |
|---|---|---|
| `resources_list` API error | `failed to list resources: <k8s error>` | `pkg/toolsets/core/resources.go:238` |
| `resources_get` API error | `failed to get resource: <k8s error>` | `pkg/toolsets/core/resources.go:273` |
| `resources_create_or_update` API error | `failed to create or update resources: <k8s error>` | `pkg/toolsets/core/resources.go:295` |
| `resources_delete` API error | `failed to delete resource: <k8s error>` | `pkg/toolsets/core/resources.go:339` |
| `resources_scale` API error | `failed to get/update resource scale: <k8s error>` | `pkg/toolsets/core/resources.go:381` |
| `pods_get` API error | `failed to get pod %s in namespace %s: <k8s error>` | `pkg/toolsets/core/pods.go:306` |
| `pods_log` API error | `failed to get pod %s log in namespace %s: <k8s error>` | `pkg/toolsets/core/pods.go:397` |
| `pods_exec` API error | `failed to exec in pod %s in namespace %s: <k8s error>` | `pkg/toolsets/core/pods.go:371` |
| `pods_list` API error | `failed to list pods in all namespaces: <k8s error>` | `pkg/toolsets/core/pods.go:274` |
| `events_list` API error | `failed to list events in all namespaces: <k8s error>` | `pkg/toolsets/core/events.go:53` |
| helm install failure | `failed to install helm chart '%s': <error>` | `pkg/toolsets/helm/helm.go:128` |
| missing required arg (example) | `failed to get resource, missing argument name` | `pkg/toolsets/core/resources.go:258` |
| bad apiVersion | `failed to get resource, invalid argument apiVersion` (from `pkg/kubernetes/…`→`errors.New("invalid argument apiVersion")`) | `pkg/toolsets/core/resources.go:417` |

**Side channel:** NotFound/Forbidden/etc. are *also* classified and emitted as MCP log notifications (not as the tool result) — `pkg/mcplog/k8s.go:13` `classifyK8sError`; e.g. NotFound → level Info, `"Resource not found - it may not exist or may have been deleted"` (`pkg/mcplog/k8s.go:19`); Forbidden → level Error, `"Permission denied - check RBAC permissions for " + operation` (`pkg/mcplog/k8s.go:21`); Unauthorized → `"Authentication failed - check cluster credentials"` (`pkg/mcplog/k8s.go:23`); TooManyRequests → `"Rate limited - too many requests to the cluster"` (`pkg/mcplog/k8s.go:39`). Dispatched from `pkg/mcp/tools_gosdk.go:98`.

**Denied resources.** Configured **only** via TOML `denied_resources` (`pkg/config/config.go:41`) — **there is no `--denied-resources` CLI flag** (see the full flag list at `pkg/kubernetes-mcp-server/cmd/root.go:69`–`:93`). Enforcement is at the HTTP RoundTripper layer, not in the tool layer: `AccessControlRoundTripper.RoundTrip` maps URL→GVR→GVK and calls `isAllowed` (`pkg/kubernetes/accesscontrol_round_tripper.go:113`); on denial it returns the literal error:

```
resource not allowed: <gvk.String()>          // pkg/kubernetes/accesscontrol_round_tripper.go:114
```

which surfaces to the model wrapped by the calling tool, e.g. `failed to list resources: resource not allowed: /v1, Kind=Secret`. Matching semantics: an entry with empty `Kind` denies the whole Group/Version (`pkg/kubernetes/accesscontrol_round_tripper.go:169`–`:173`), otherwise exact Group+Version+Kind (`pkg/kubernetes/accesscontrol_round_tripper.go:174`–`:178`). Wiring: `DeniedResourcesProvider: baseConfig` at `pkg/kubernetes/kubernetes.go:77`; interface `pkg/api/config.go:61`.

**Other RoundTripper-level errors:**
- Unknown GVK: `Resource %s does not exist in the cluster` with code `RESOURCE_NOT_FOUND` — `pkg/kubernetes/accesscontrol_round_tripper.go:106`–`:109`.
- Confirmation declined: `action requires confirmation` (`confirmation.ErrConfirmationDenied`, `pkg/confirmation/confirmation.go:15`), converted to a `PERMISSION_DENIED` validation error at `pkg/kubernetes/confirmation_validator.go:37`–`:39`.
- Validation error type & codes: `pkg/api/validation.go:35` (`ErrorCodePermissionDenied`), `pkg/api/validation.go:58` (`NewPermissionDeniedError(verb, resource, namespace)`).

**Destructive-op confirmation (E6).** Two layers:
1. **Tool-level**, before the handler runs: `confirmation.CheckToolRules(ctx, cfg, &sessionElicitor{}, tool.Tool.Name, tool.Tool.Annotations.DestructiveHint)` — `pkg/mcp/tools_gosdk.go:71`–`:76`; on error the result is `NewTextResult("", confirmErr)` i.e. `IsError: true` with text `action requires confirmation`. Implementation `pkg/confirmation/confirmation.go:20`.
2. **Kube-level**, inside the RoundTripper: `ConfirmationValidator` is appended when rules exist — `pkg/kubernetes/accesscontrol_round_tripper.go:73`–`:75`; `confirmation.CheckKubeRules` `pkg/confirmation/confirmation.go:33`.

Rules are declared in TOML `confirmation_rules` (`pkg/config/config.go:181`) as `api.ConfirmationRule` with tool-level fields `tool`, `destructive` **xor** kube-level fields `verb`, `kind`, `group`, `version`, `name`, `namespace`, plus `message` — `pkg/api/confirmation.go:8`–`:20`; mixing the two families is a startup error (`pkg/api/confirmation.go:37`). Confirmation is delivered over the MCP **elicitation** protocol (`pkg/confirmation/confirmation.go:48`–`:54`, elicitor `pkg/mcp/elicit.go:17`, not-supported detection `pkg/mcp/elicit.go:35`). If the client does not support elicitation, `confirmation_fallback` decides: `"deny"` → `ErrConfirmationDenied`; `"allow"` (the shipped default, `pkg/config/config_default.go:18`) → proceed with a warning log — `pkg/confirmation/confirmation.go:56`–`:62`. Valid values enforced at `pkg/config/config.go:619`.

---

## Not exposed (E3)

Verified by grepping the whole `pkg/` tree — the following kubectl/Kubernetes capabilities have **no** tool and no implementation:

- **`kubectl port-forward`** — no `portforward` / `PortForward` symbol anywhere in `pkg/` (grep for `portforward|PortForward|port-forward` over `pkg/` returns zero non-doc hits).
- **`kubectl rollout` (status / undo / restart / pause / resume)** — no `rollout` symbol in `pkg/`. Restarting a Deployment requires round-tripping through `resources_get` → edit → `resources_create_or_update`.
- **`kubectl cordon` / `uncordon` / `drain`** — no `cordon`/`drain` symbol in `pkg/`. Node tools are read-only (`nodes_log`, `nodes_stats_summary`, `nodes_top` — `pkg/toolsets/core/nodes.go:22`, `:52`, `:72`).
- **`kubectl apply --server-side` toggle** — SSA is not optional, it is the *only* write path: `resources_create_or_update` always applies with `FieldManager: "kubernetes-mcp-server"` and `Force: true` — `pkg/kubernetes/resources.go:193`–`:196`. There is no client-side apply, no strategic-merge patch, and no JSON-patch tool. The tool description explicitly warns that omitted fields are removed (`pkg/toolsets/core/resources.go:108`).
- **`kubectl cp`** — no copy tool; file transfer would have to go through `pods_exec`.
- **`kubectl attach`** — not exposed; only one-shot `pods_exec` (`pkg/toolsets/core/pods.go:157`).
- **Streaming / `--follow` logs** — `pods_log` has no `follow` parameter and `PodLogOptions` sets only `Container`, `Previous`, `TailLines` (`pkg/kubernetes/pods.go:132`–`:142`).
- **`--since` / `--since-time` / `--limit-bytes` on logs** — absent (same cite).
- **Watch / informers for the model** — `WatchTargets` (`pkg/kubernetes/provider.go:28`) is internal reload plumbing; no `resources_watch` tool exists.
- **`.status` writes** — deliberately stripped from any applied manifest: "remove the status from the resource, disallowing agent from directly editing (only controllers should be allowed to do this)" — `pkg/kubernetes/resources.go:67`–`:68`.
- **`deletecollection`** — the verb is recognized for validation (`pkg/kubernetes/accesscontrol_round_tripper.go:295`) but no tool issues one; `resources_delete` requires a `name` (`pkg/toolsets/core/resources.go:153`).
- **Impersonation** — the impersonate RoundTripper exists (`pkg/kubernetes/impersonate_roundtripper.go`) but is commented out with a TODO explaining it "Won't work because not all client-go clients use the shared context (e.g. discovery client uses context.TODO())" — `pkg/kubernetes/manager.go:157`–`:160`. `Impersonate` is explicitly zeroed on the derived config (`pkg/kubernetes/manager.go:208`).
- **`--denied-resources` CLI flag** — the deny list is TOML-only; the flag does not exist (`pkg/config/config.go:41` vs. flag list `pkg/kubernetes-mcp-server/cmd/root.go:69`–`:93`).
- **Full tool replacement on reload** — TODO comment: "No option to perform a full replacement of tools. s.server.SetTools(tools...)" — `pkg/mcp/mcp.go:220`–`:221`.
- **`helm upgrade`** — no such tool; `helm_install` carries a TODO to "consider replacing implementation with equivalent to: helm upgrade --install" and its `IdempotentHint` is deliberately `nil` — `pkg/toolsets/helm/helm.go:44`.
- **`helm rollback` / `helm history` / `helm repo` / `helm template`** — only `helm_install`, `helm_list`, `helm_uninstall` exist (`pkg/toolsets/helm/toolset.go:23`–`:25`).

---

## Notes for mocking

- **52 tools total**, but a fresh default install exposes only **22** (`core` 19 + `config` 3), and `config`'s two target-list tools are dropped in single-target mode (`pkg/mcp/tool_filter.go:29`) — so a realistic stdio/kubeconfig mock advertises **20**: 19 core + `configuration_view`. Everything else requires an explicit `--toolsets` opt-in (`pkg/config/config_default.go:17`).
- **Output format is a global switch, not per-tool.** `--list-output` defaults to `table` (`pkg/config/config_default.go:16`), so `resources_list`, `pods_list`, `pods_list_in_namespace`, `namespaces_list`, `projects_list` return **kubectl-style plaintext tables**, not YAML. Mocks that always emit YAML will not match the default. `resources_get`, `pods_get`, `events_list`, `configuration_view` are always YAML regardless (`pkg/toolsets/core/resources.go:275`, `pkg/toolsets/core/pods.go:308`, `pkg/toolsets/core/events.go:62`, `pkg/toolsets/config/configuration.go:183`).
- **Some tools return structuredContent, most do not.** `resources_list` / `resources_get` / `configuration_contexts_list` / netobserv tools do (`pkg/api/toolsets.go:86` `NewToolCallResultFull`, `pkg/toolsets/netobserv/tools/result.go:18`); `pods_list`, `namespaces_list`, `pods_log`, `pods_top` etc. return text only (`PrintObj`, `pkg/output/output.go:35`). Slices are auto-wrapped as `{"items": …}` to satisfy the MCP object requirement — `pkg/mcp/mcp.go:663`–`:664`.
- **Errors are bare strings, never structured.** `IsError: true` + one `TextContent` containing `err.Error()` verbatim (`pkg/mcp/mcp.go:640`–`:648`). Mock error text should be `failed to <verb> <noun>: <client-go StatusError text>`, per the table above.
- **Multi-target injects an extra `context` property into almost every tool schema** (`pkg/mcp/tool_mutator.go:29`, name from `pkg/kubernetes/provider_kubeconfig.go:16`). Kiali, kcp, and the config tools opt out via `ClusterAware: false`. A schema-diffing mock must model this or it will mismatch on multi-context kubeconfigs.
- **`targets_list` is renamed before it is ever advertised** to `{targetParameterName}_list` (e.g. `cluster_list`) — `pkg/mcp/tool_mutator.go:74`. Do not mock the literal name `targets_list` for non-kubeconfig providers.
- **`pods_log` silently defaults to the last 100 lines** (`pkg/kubernetes/pods.go:28`, `:141`) and `pods_top` defaults `all_namespaces=true` (`pkg/toolsets/core/pods.go:131`). Empty-result cases return sentence-shaped strings, not empty strings (`pkg/toolsets/core/pods.go:399`, `:380`, `pkg/toolsets/core/events.go:56`, `pkg/helm/helm.go:89`).
- **No pagination anywhere in core.** No `limit`, no `continue`, no truncation (`pkg/api/kubernetes.go:20`, `pkg/kubernetes/resources.go:41`). A mock cluster with 10k pods will produce one enormous text block; that is faithful behavior, not a bug to paper over.
- **Destructive tools can block on elicitation.** If `confirmation_rules` are configured and the client lacks elicitation support with `confirmation_fallback = "deny"`, the tool returns `IsError: true` / `action requires confirmation` *without touching the cluster* (`pkg/mcp/tools_gosdk.go:71`, `pkg/confirmation/confirmation.go:58`). Default fallback is `"allow"` (`pkg/config/config_default.go:18`).
- **Writes are always Server-Side Apply with `Force: true`** and `.status` stripped (`pkg/kubernetes/resources.go:68`, `:193`–`:196`). A mock apply endpoint should expect `PATCH` with `application/apply-patch+yaml`, field manager `kubernetes-mcp-server`, and should return the *merged* object — the tool echoes it back under a `# The following resources (YAML) have been created or updated successfully` header (`pkg/toolsets/core/resources.go:301`).
- **Tool lists are dynamic.** They are re-derived and re-installed on kubeconfig change / SIGHUP reload (`pkg/mcp/mcp.go:219`, `pkg/mcp/mcp.go:200`), emitting `tools/list_changed` unless `--stateless` (`pkg/mcp/mcp.go:138`, flag `pkg/kubernetes-mcp-server/cmd/root.go:185`). A long-lived mock session should tolerate list-changed notifications.
