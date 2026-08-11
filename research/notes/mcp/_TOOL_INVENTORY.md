# Consolidated MCP tool inventory — 10 servers, 596 tools

**Compiled:** 2026-08-11, from source reads of the ten repos under `/Users/samuelchien/dev/software-devops/research/repos/mcp/`.
**Per-server detail (params, return shapes, file:line citations):** the sibling files in this directory. This document is the index and the cross-tool analysis.
**Answers:** E2 (what each MCP server exposes), E3 (where the MCP surface is narrower than the REST API), E4 (overlaps), E6 (auth / pagination / rate limits / error shapes).

## Server summary

| Server | Commit | Lang | Tools | Read | Write | Notes file |
|---|---|---|---|---|---|---|
| github/github-mcp-server | `eff4c3c` | Go | **116** (117 registrations) | 59 | 58 | `github__github-mcp-server.md` |
| grafana/mcp-grafana | `460e62e` | Go | **105** (111 call sites) | 85 | 20 | `grafana__mcp-grafana.md` |
| PagerDuty/pagerduty-mcp-server | `22adbf1` | Python | **103** | 63 | 40 | `PagerDuty__pagerduty-mcp-server.md` |
| sooperset/mcp-atlassian | `12fb6fa` | Python | **98** (63 Jira + 35 Confluence) | 58 | 40 | `sooperset__mcp-atlassian.md` |
| modelcontextprotocol/servers | `76d64c8` | TS + Py | **58** across 7 servers | — | — | `modelcontextprotocol__servers.md` |
| getsentry/sentry-mcp | `a5323d0` | TS | **53** (only **9** advertised) | 39 | 14 | `getsentry__sentry-mcp.md` |
| containers/kubernetes-mcp-server | `7e6f76a` | Go | **52** across 8 toolsets | 36 | 16 | `containers__kubernetes-mcp-server.md` |
| elastic/mcp-server-elasticsearch | `9e64b84` | Rust | **5** | 5 | 0 | `elastic__mcp-server-elasticsearch.md` |
| snyk/snyk-ls | `1cf40fc` | Go | **4** (partial — impl moved out) | 2 | 2 | `snyk__snyk-ls.md` |
| GLips/Figma-Context-MCP | `c083d65` | TS | **2** | 1 | 1 | `GLips__Figma-Context-MCP.md` |

All commit hashes verified with `git -C <repo> rev-parse --short HEAD` on 2026-08-11. GitHub's count (116 unique names) was verified two ways — every `Name: "…"` literal in `pkg/github/*.go` and the 116 schema snapshots in `pkg/github/__toolsnaps__/`.

**Three counts that are not what they look like:**
- **Sentry advertises 9 of 53.** `packages/mcp-core/src/tools/surfaces.ts:17` — the other 44 are catalog-only, reachable exclusively via `search_sentry_tools` → `execute_sentry_tool`. A client's `tools/list` sees nine.
- **Kubernetes ships 2 of 8 toolsets by default** (`core` + `config`, `pkg/config/config_default.go:17`). The kiali / kubevirt / netobserv / tekton / kcp tools require opt-in.
- **Snyk's real tool surface is not in this repo.** `mcp_extension/README.md:1-3`: "Implementation has been moved to https://github.com/snyk/studio-mcp." Only four tool names (`snyk_auth`, `snyk_trust`, `snyk_sca_scan`, `snyk_code_scan`) are evidenced here, from `llms-install.md:43` and `AGENT.md:70-72`.

**R/W convention below:** taken from each server's own annotation (`readOnlyHint` / `destructiveHint`) where one exists, otherwise from the operation's semantics. Where a server's own annotation is misleading, it is flagged inline.

---

# Inventory by domain category

Tools are filed by **what they do**, not by which server they live in — that is what makes the overlaps visible.

## 1. Source control — repositories, files, commits, branches

| Tool | Server | R/W |
|---|---|---|
| `search_repositories`, `search_code`, `search_commits` | GitHub | R |
| `get_file_contents`, `get_file_blame`, `get_repository_tree` | GitHub | R |
| `get_commit`, `list_commits` | GitHub | R |
| `list_branches`, `list_tags`, `get_tag` | GitHub | R |
| `list_releases`, `get_latest_release`, `get_release_by_tag` | GitHub | R |
| `list_repository_collaborators`, `ui_get` | GitHub | R |
| `list_gists`, `get_gist` | GitHub | R |
| `list_starred_repositories` | GitHub | R |
| `create_or_update_file`, `push_files`, `delete_file` | GitHub | **W** |
| `create_repository`, `fork_repository`, `create_branch` | GitHub | **W** |
| `create_gist`, `update_gist` | GitHub | **W** |
| `star_repository`, `unstar_repository` | GitHub | **W** |
| `git_status`, `git_diff`, `git_diff_staged`, `git_diff_unstaged`, `git_log`, `git_show`, `git_branch` | mcp/git | R |
| `git_add`, `git_commit`, `git_reset`, `git_create_branch`, `git_checkout` | mcp/git | **W** |
| `jira_get_issue_development_info`, `jira_get_issues_development_info` | Jira | R (returns branches/commits/PRs linked to an issue — a source-control view *inside* the tracker) |

## 2. Code review — pull requests

| Tool | Server | R/W |
|---|---|---|
| `pull_request_read`, `list_pull_requests`, `search_pull_requests` | GitHub | R |
| `create_pull_request`, `update_pull_request`, `merge_pull_request`, `update_pull_request_branch` | GitHub | **W** |
| `update_pull_request_title`, `update_pull_request_body`, `update_pull_request_state`, `update_pull_request_draft_state` | GitHub | **W** |
| `request_pull_request_reviewers`, `request_copilot_review` | GitHub | **W** |
| `create_pull_request_review`, `pull_request_review_write`, `submit_pending_pull_request_review`, `delete_pending_pull_request_review` | GitHub | **W** |
| `add_pull_request_review_comment`, `add_comment_to_pending_review`, `add_reply_to_pull_request_comment`, `add_pull_request_review_comment_reaction` | GitHub | **W** |
| `resolve_review_thread`, `unresolve_review_thread` | GitHub | **W** |

## 3. Issue tracking & project management

**GitHub Issues / Projects**

| Tool | Server | R/W |
|---|---|---|
| `issue_read`, `list_issues`, `search_issues` | GitHub | R |
| `list_issue_types`, `list_issue_fields`, `get_label`, `list_label` | GitHub | R |
| `find_duplicate` | GitHub | R |
| `issue_dependency_read` | GitHub | R |
| `projects_list`, `projects_get` | GitHub | R |
| `create_issue`, `issue_write`, `add_issue_comment` | GitHub | **W** |
| `update_issue_title`, `update_issue_body`, `update_issue_assignees`, `update_issue_labels`, `update_issue_milestone`, `update_issue_type`, `update_issue_state`, `set_issue_fields` | GitHub | **W** |
| `add_sub_issue`, `remove_sub_issue`, `reprioritize_sub_issue`, `sub_issue_write` | GitHub | **W** |
| `issue_dependency_write`, `label_write`, `projects_write` | GitHub | **W** |
| `add_issue_reaction`, `add_issue_comment_reaction` | GitHub | **W** |
| `assign_copilot_to_issue`, `assign_copilot_to_issue_with_intent` | GitHub | **W** |

**Jira**

| Tool | Server | R/W |
|---|---|---|
| `jira_get_issue`, `jira_search` (JQL), `jira_get_project_issues` | Jira | R |
| `jira_search_fields`, `jira_get_field_options`, `jira_get_create_fields`, `jira_get_project_fields` | Jira | R |
| `jira_get_transitions`, `jira_batch_get_changelogs`, `jira_get_issue_dates` | Jira | R |
| `jira_get_worklog`, `jira_download_attachments`, `jira_get_issue_images` | Jira | R |
| `jira_get_agile_boards`, `jira_get_board_issues`, `jira_get_sprints_from_board`, `jira_get_sprint_issues` | Jira | R |
| `jira_get_link_types`, `jira_get_project_epic_hierarchy`, `jira_get_cross_project_dependencies` | Jira | R |
| `jira_get_all_projects`, `jira_search_projects`, `jira_get_project_issue_types`, `jira_get_project_versions`, `jira_get_project_components` | Jira | R |
| `jira_get_issue_proforma_forms`, `jira_get_proforma_form_details` | Jira | R |
| `jira_get_issue_watchers`, `jira_search_assignable_users`, `jira_get_user_profile` | Jira | R |
| `jira_create_issue`, `jira_batch_create_issues`, `jira_update_issue`, `jira_delete_issue`, `jira_move_issue` | Jira | **W** |
| `jira_assign_issue`, `jira_transition_issue`, `jira_add_comment`, `jira_edit_comment`, `jira_add_worklog` | Jira | **W** |
| `jira_link_to_epic`, `jira_create_issue_link`, `jira_create_remote_issue_link`, `jira_remove_issue_link` | Jira | **W** |
| `jira_create_sprint`, `jira_update_sprint`, `jira_add_issues_to_sprint`, `jira_move_issues_to_backlog` | Jira | **W** |
| `jira_create_version`, `jira_batch_create_versions`, `jira_update_version` | Jira | **W** |
| `jira_add_watcher`, `jira_remove_watcher`, `jira_update_proforma_form_answers` | Jira | **W** |

**Collaboration / notifications (GitHub)**

| Tool | Server | R/W |
|---|---|---|
| `list_discussions`, `get_discussion`, `get_discussion_comments`, `list_discussion_categories` | GitHub | R |
| `list_notifications`, `get_notification_details` | GitHub | R |
| `discussion_comment_write` | GitHub | **W** |
| `dismiss_notification`, `mark_all_notifications_read`, `manage_notification_subscription`, `manage_repository_notification_subscription` | GitHub | **W** |

## 4. CI/CD & build

| Tool | Server | R/W |
|---|---|---|
| `actions_list`, `actions_get`, `get_job_logs` | GitHub | R |
| `actions_run_trigger` | GitHub | **W** |
| `tekton_pipelinerun_logs`, `tekton_taskrun_logs` | k8s | R |
| `tekton_pipeline_start`, `tekton_task_start`, `tekton_pipelinerun_lifecycle`, `tekton_taskrun_restart` | k8s | **W** |

> **Gap worth noting.** Across ten servers this is the *entire* CI/CD surface: 4 GitHub Actions tools and 6 Tekton tools (the latter opt-in). No Jenkins, CircleCI, GitLab CI, Argo, or Spinnaker MCP server exists in this corpus.

## 5. Observability — metrics, logs, traces, profiles, dashboards

**Dashboards, folders, snapshots (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `search_dashboards`, `search_folders` | Grafana | R |
| `get_dashboard_by_uid`, `get_dashboard_summary`, `get_dashboard_property`, `get_dashboard_panel_queries` | Grafana | R |
| `get_panel_image`, `run_panel_query`, `get_query_examples`, `get_resource_description` | Grafana | R |
| `list_snapshots`, `get_snapshot` | Grafana | R |
| `update_dashboard`, `create_folder`, `create_snapshot`, `delete_snapshot`, `generate_deeplink` | Grafana | **W** |

**Datasources (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `list_datasources`, `get_datasource`, `check_datasources_health` | Grafana | R |
| `create_datasource`, `update_datasource` | Grafana | **W** |

**Metrics — Prometheus (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `query_prometheus`, `query_prometheus_histogram` | Grafana | R |
| `list_prometheus_metric_names`, `list_prometheus_metric_metadata`, `list_prometheus_label_names`, `list_prometheus_label_values` | Grafana | R |

**Logs — Loki (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `query_loki_logs`, `query_loki_stats`, `query_loki_patterns` | Grafana | R |
| `list_loki_label_names`, `list_loki_label_values`, `analyze_loki_labels`, `suggest_loki_alloy_label_config` | Grafana | R |

**Profiling — Pyroscope (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `query_pyroscope`, `list_pyroscope_profile_types`, `list_pyroscope_label_names`, `list_pyroscope_label_values` | Grafana | R |

**Other datasources (Grafana) — the long tail**

| Tool | Server | R/W |
|---|---|---|
| `query_elasticsearch`, `query_quickwit` | Grafana | R |
| `query_cloudwatch`, `list_cloudwatch_namespaces`, `list_cloudwatch_metrics`, `list_cloudwatch_dimensions` | Grafana | R |
| `query_graphite`, `query_graphite_density`, `list_graphite_metrics`, `list_graphite_tags` | Grafana | R |
| `list_clickhouse_tables`, `describe_clickhouse_table`, `list_snowflake_tables`, `describe_snowflake_table` | Grafana | R |
| `list_athena_catalogs`, `list_athena_databases`, `list_athena_tables`, `describe_athena_table` | Grafana | R |
| `query_clickhouse`, `query_snowflake`, `query_athena`, `query_influxdb` | Grafana | **W** (annotated non-read-only — arbitrary SQL) |

**Annotations, Sift, Asserts, assistant (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `get_annotations`, `get_annotation_tags` | Grafana | R |
| `create_annotation`, `update_annotation` | Grafana | **W** |
| `list_sift_investigations`, `get_sift_investigation`, `get_sift_analysis` | Grafana | R |
| `find_error_pattern_logs`, `find_slow_requests` | Grafana | **W** (creates a Sift investigation) |
| `get_assertions` | Grafana | R |
| `ask_assistant` | Grafana | **W** |
| `agento11y_manage_conversations`, `agento11y_manage_generations`, `agento11y_manage_agents`, `agento11y_manage_evaluators`, `agento11y_manage_eval_rules`, `agento11y_manage_eval_collections` | Grafana | R (read-only variants; W variants also registered) |

**Search backend — Elasticsearch (direct)**

| Tool | Server | R/W |
|---|---|---|
| `list_indices`, `get_mappings`, `get_shards` | Elasticsearch | R |
| `search` (Query DSL), `esql` (ES\|QL) | Elasticsearch | R |

**Tracing / profiling / replay (Sentry)**

| Tool | Server | R/W |
|---|---|---|
| `search_events`, `get_trace_details`, `get_span_details` | Sentry | R |
| `get_profile`, `get_profile_details`, `get_replay_details` | Sentry | R |

**Cluster telemetry (Kubernetes)**

| Tool | Server | R/W |
|---|---|---|
| `events_list`, `pods_log`, `nodes_log` | k8s | R |
| `pods_top`, `nodes_top`, `nodes_stats_summary` | k8s | R |
| `kiali_get_mesh_traffic_graph`, `kiali_get_mesh_status`, `kiali_list_mesh_clusters`, `kiali_get_resource_details` | k8s (opt-in) | R |
| `kiali_list_traces`, `kiali_get_trace_details`, `kiali_get_pod_performance`, `kiali_get_logs`, `kiali_get_metrics` | k8s (opt-in) | R |
| `netobserv_list_flows`, `netobserv_get_flow_metrics`, `netobserv_export_flows` | k8s (opt-in) | R |

**Plugins / provisioning / raw escape hatch (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `search_plugin_information`, `get_plugin` | Grafana | R |
| `list_provisioning_repositories`, `validate_provisioning_file` | Grafana | R |
| `install_plugin` | Grafana | **W** |
| `grafana_api_request` | Grafana | **W** (raw Grafana HTTP API passthrough — bypasses every other tool's shaping) |

## 6. Error tracking (Sentry)

| Tool | Server | R/W |
|---|---|---|
| `search_issues`, `get_issue_details`, `search_issue_events` | Sentry | R |
| `get_event_stacktrace`, `get_issue_breadcrumbs`, `get_issue_activity`, `get_issue_tag_values`, `get_issue_user_reports`, `get_event_attachment` | Sentry | R |
| `find_organizations`, `find_projects`, `find_teams`, `find_dsns` | Sentry | R |
| `find_releases`, `get_release_details` | Sentry | R |
| `find_dashboards`, `get_dashboard_details` | Sentry | R |
| `find_alert_rules`, `get_alert_rule` | Sentry | R |
| `find_monitors`, `get_monitor_details`, `find_uptime_monitors`, `get_uptime_monitor_details` | Sentry | R |
| `search_ai_conversations`, `get_ai_conversation_details` | Sentry | R |
| `get_snapshot`, `get_snapshot_image`, `get_latest_base_snapshot` | Sentry | R |
| `search_docs`, `get_doc`, `get_sentry_resource`, `whoami` | Sentry | R |
| `search_sentry_tools` | Sentry | R (tool discovery — gateway to the 44 hidden tools) |
| `update_issue`, `add_issue_note` | Sentry | **W** |
| `analyze_issue_with_seer` | Sentry | **W** (triggers Sentry's AI root-cause agent) |
| `execute_sentry_tool` | Sentry | **W** (dispatcher for catalog tools) |
| `create_uptime_monitor`, `update_uptime_monitor`, `delete_uptime_monitor` | Sentry | **W** |
| `create_project`, `update_project`, `create_team`, `add_team_to_project`, `remove_team_from_project` | Sentry | **W** |
| `create_dsn`, `update_dsn` | Sentry | **W** |

## 7. Alerting, on-call & incident management

**Alert rules & routing (Grafana)**

| Tool | Server | R/W |
|---|---|---|
| `alerting_manage_rules`, `alerting_manage_routing` | Grafana | R (read-only variant) / **W** (write variant, separately registered) |
| `list_alert_groups`, `get_alert_group` | Grafana | R |

**On-call (Grafana OnCall)**

| Tool | Server | R/W |
|---|---|---|
| `list_oncall_schedules`, `get_oncall_shift`, `get_current_oncall_users`, `list_oncall_teams`, `list_oncall_users` | Grafana | R |

**Incidents (Grafana Incident)**

| Tool | Server | R/W |
|---|---|---|
| `list_incidents`, `get_incident` | Grafana | R |
| `create_incident`, `add_activity_to_incident` | Grafana | **W** |

**PagerDuty — incidents, alerts, notes**

| Tool | Server | R/W |
|---|---|---|
| `list_incidents`, `get_incident`, `get_past_incidents`, `get_related_incidents`, `get_outlier_incident` | PagerDuty | R |
| `list_alerts_from_incident`, `get_alert_from_incident` | PagerDuty | R |
| `list_incident_notes`, `list_log_entries`, `get_log_entry` | PagerDuty | R |
| `list_incident_workflows`, `get_incident_workflow` | PagerDuty | R |
| `create_incident`, `manage_incidents`, `add_responders`, `add_note_to_incident`, `start_incident_workflow` | PagerDuty | **W** |

**PagerDuty — services, escalation, schedules**

| Tool | Server | R/W |
|---|---|---|
| `list_services`, `get_service`, `get_technical_service_dependencies` | PagerDuty | R |
| `list_business_services`, `get_business_service_dependencies` | PagerDuty | R |
| `list_escalation_policies`, `get_escalation_policy` | PagerDuty | R |
| `list_oncalls`, `list_schedules`, `get_schedule`, `list_schedule_users` | PagerDuty | R |
| `list_schedule_v3_rotations`, `get_schedule_v3_rotation`, `list_schedule_v3_rotation_events`, `get_schedule_v3_rotation_event` | PagerDuty | R |
| `list_schedule_v3_custom_shifts`, `get_schedule_v3_custom_shift`, `list_schedule_v3_overrides`, `get_schedule_v3_override` | PagerDuty | R |
| `list_priorities` | PagerDuty | R |
| `create_service`, `update_service` | PagerDuty | **W** |
| `create_escalation_policy`, `update_escalation_policy` | PagerDuty | **W** |
| `create_schedule`, `update_schedule`, `create_schedule_override` | PagerDuty | **W** |
| `delete_schedule_v3`, `create_schedule_v3_rotation`, `delete_schedule_v3_rotation`, `create_schedule_v3_rotation_event`, `update_schedule_v3_rotation_event`, `delete_schedule_v3_rotation_event` | PagerDuty | **W** |
| `create_schedule_v3_custom_shifts`, `update_schedule_v3_custom_shift`, `delete_schedule_v3_custom_shift` | PagerDuty | **W** |
| `create_schedule_v3_overrides`, `update_schedule_v3_override`, `delete_schedule_v3_override` | PagerDuty | **W** |

**PagerDuty — change events, orchestration, status pages, analytics, integrations**

| Tool | Server | R/W |
|---|---|---|
| `list_change_events`, `get_change_event`, `list_service_change_events`, `list_incident_change_events` | PagerDuty | R |
| `list_event_orchestrations`, `get_event_orchestration`, `get_event_orchestration_router`, `get_event_orchestration_service`, `get_event_orchestration_global` | PagerDuty | R |
| `list_alert_grouping_settings`, `get_alert_grouping_setting` | PagerDuty | R |
| `list_status_pages`, `list_status_page_severities`, `list_status_page_impacts`, `list_status_page_statuses`, `get_status_page_post`, `list_status_page_post_updates` | PagerDuty | R |
| `get_incident_metrics_all`, `get_incident_metrics_by_service`, `get_incident_metrics_by_team`, `get_responder_metrics`, `get_responder_load_metrics` | PagerDuty | R |
| `list_webhook_subscriptions`, `get_webhook_subscription`, `list_extension_schemas`, `get_extension_schema` | PagerDuty | R |
| `update_event_orchestration_router`, `append_event_orchestration_router_rule` | PagerDuty | **W** |
| `create_alert_grouping_setting`, `update_alert_grouping_setting`, `delete_alert_grouping_setting` | PagerDuty | **W** |
| `create_status_page_post`, `create_status_page_post_update` | PagerDuty | **W** |
| `create_webhook_subscription`, `update_webhook_subscription`, `delete_webhook_subscription` | PagerDuty | **W** |

**IT service management (Jira Service Management)**

| Tool | Server | R/W |
|---|---|---|
| `jira_get_service_desk_for_project`, `jira_get_service_desk_queues`, `jira_get_queue_issues` | Jira | R |
| `jira_get_request_types`, `jira_get_request_type_fields`, `jira_get_issue_sla` | Jira | R |
| `jira_create_customer_request` | Jira | **W** |

## 8. Kubernetes, deploy & infrastructure

| Tool | Server | R/W |
|---|---|---|
| `namespaces_list`, `projects_list`, `configuration_contexts_list`, `targets_list`, `configuration_view` | k8s | R |
| `resources_list`, `resources_get` | k8s | R |
| `pods_list`, `pods_list_in_namespace`, `pods_get` | k8s | R |
| `helm_list` | k8s | R |
| `kcp_workspaces_list`, `kcp_workspace_describe` | k8s (opt-in) | R |
| `vm_guest_info`, `vm_troubleshoot` | k8s (opt-in) | R |
| `resources_create_or_update`, `resources_delete`, `resources_scale` | k8s | **W** |
| `pods_delete`, `pods_run`, `pods_exec` | k8s | **W** (`pods_exec` is arbitrary in-container command execution) |
| `helm_install`, `helm_uninstall` | k8s | **W** |
| `kiali_manage_istio_config` | k8s (opt-in) | **W** |
| `vm_clone`, `vm_create`, `vm_lifecycle` | k8s (opt-in) | **W** |
| `kiali_manage_istio_config_read` | k8s (opt-in) | R |

## 9. Security scanning

| Tool | Server | R/W |
|---|---|---|
| `list_code_scanning_alerts`, `get_code_scanning_alert` | GitHub | R (SAST / CodeQL) |
| `get_code_quality_finding` | GitHub | R |
| `list_secret_scanning_alerts`, `get_secret_scanning_alert` | GitHub | R |
| `list_dependabot_alerts`, `get_dependabot_alert` | GitHub | R (SCA) |
| `list_global_security_advisories`, `get_global_security_advisory` | GitHub | R |
| `list_repository_security_advisories`, `list_org_repository_security_advisories` | GitHub | R |
| `snyk_sca_scan` | Snyk | R (scan) |
| `snyk_code_scan` | Snyk | R (scan) |
| `snyk_auth`, `snyk_trust` | Snyk | **W** (side effects: auth flow, folder trust) |

> **No write path.** Not one server in this corpus can create a security exception, dismiss an alert, approve an ignore, or open a fix PR from a finding. Remediation is entirely out of the MCP surface.

## 10. Knowledge base & documentation

| Tool | Server | R/W |
|---|---|---|
| `confluence_search` (CQL), `confluence_get_page`, `confluence_get_page_children`, `confluence_get_space_page_tree` | Confluence | R |
| `confluence_get_comments`, `confluence_get_inline_comments`, `confluence_get_labels` | Confluence | R |
| `confluence_get_page_history`, `confluence_get_page_diff`, `confluence_get_page_views` | Confluence | R (**staleness signals** — see Overlap 11) |
| `confluence_get_attachments`, `confluence_download_attachment`, `confluence_download_content_attachments`, `confluence_get_page_images` | Confluence | R |
| `confluence_list_page_templates`, `confluence_get_page_template` | Confluence | R |
| `confluence_get_page_restrictions`, `confluence_check_content_permissions`, `confluence_get_space_permissions`, `confluence_search_user` | Confluence | R |
| `confluence_create_page`, `confluence_update_page`, `confluence_update_page_section`, `confluence_create_page_from_template` | Confluence | **W** |
| `confluence_delete_page`, `confluence_move_page`, `confluence_copy_page` | Confluence | **W** |
| `confluence_add_comment`, `confluence_reply_to_comment`, `confluence_add_inline_comment`, `confluence_add_label` | Confluence | **W** |
| `confluence_upload_attachment`, `confluence_upload_attachments`, `confluence_delete_attachment` | Confluence | **W** |
| `confluence_set_page_restrictions` | Confluence | **W** |
| `search_docs`, `get_doc` | Sentry | R (product documentation) |
| `read_graph`, `search_nodes`, `open_nodes` | mcp/memory | R (agent's own knowledge graph) |
| `create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations` | mcp/memory | **W** |

## 11. Design

| Tool | Server | R/W |
|---|---|---|
| `get_figma_data` | Figma | R |
| `download_figma_images` | Figma | **W** (writes image files to local disk; read-only against Figma) |

## 12. Identity, teams & permissions (cross-cutting)

| Tool | Server | R/W |
|---|---|---|
| `get_me`, `get_teams`, `get_team_members`, `search_users`, `search_orgs` | GitHub | R |
| `whoami` | Sentry | R |
| `list_teams`, `list_users_by_org`, `list_all_roles`, `get_role_details`, `get_role_assignments`, `list_user_roles`, `list_team_roles`, `get_resource_permissions` | Grafana | R |
| `list_users`, `get_user_data`, `list_teams`, `get_team`, `list_team_members` | PagerDuty | R |
| `create_user`, `create_team`, `update_team`, `delete_team`, `add_team_member`, `remove_team_member` | PagerDuty | **W** |
| `jira_get_user_profile`, `confluence_search_user` | Atlassian | R |

## 13. Agent infrastructure (reference servers — not vendor tools)

| Tool | Server | R/W |
|---|---|---|
| `read_file`, `read_text_file`, `read_media_file`, `read_multiple_files`, `get_file_info` | mcp/filesystem | R |
| `list_directory`, `list_directory_with_sizes`, `directory_tree`, `search_files`, `list_allowed_directories` | mcp/filesystem | R |
| `write_file`, `edit_file`, `create_directory`, `move_file` | mcp/filesystem | **W** |
| `fetch` | mcp/fetch | R (HTTP GET → markdown, the only paginated reference tool) |
| `get_current_time`, `convert_time` | mcp/time | R |
| `sequentialthinking` | mcp/sequentialthinking | R (pure reasoning scratchpad) |
| `echo`, `get-sum`, `get-env`, `get-tiny-image`, `get-annotated-message`, `get-structured-content`, `get-resource-links`, `get-resource-reference`, `gzip-file-as-resource`, `toggle-simulated-logging`, `toggle-subscriber-updates`, `trigger-long-running-operation` | mcp/everything | protocol demo |
| `get-roots-list`, `trigger-elicitation-request`, `trigger-url-elicitation`, `trigger-sampling-request`, `trigger-sampling-request-async`, `trigger-elicitation-request-async`, `simulate-research-query` | mcp/everything | protocol demo (registered only if the client advertises the capability) |

---

# E6 — auth, pagination, rate limits, error shapes at a glance

| Server | Credential | Pagination | Rate limits | Error shape |
|---|---|---|---|---|
| **GitHub** | PAT `GITHUB_PERSONAL_ACCESS_TOKEN`, GitHub App, or interactive OAuth — mutually exclusive. Per-tool declared OAuth scopes, hierarchy-expanded; tools **hidden** when the token lacks scope | `page` (≥1, default 1) + `perPage` (1–100, default 30); GraphQL tools use `after` cursor and drop `page`; Actions tools use snake_case `per_page` | Bespoke message `"…: GitHub API rate limit exceeded. Retry after 42s."` — **no retry/backoff anywhere** | `IsError: true` + one text block `"<handler message>: <go error string>"`. Truncation is per-tool and inconsistent: `Minimal*` projections, opt-in `fields` filtering, a 5000-line log window, `truncated`/`has_more` flags, 1 MB `ResourceLink` cutoff |
| **Grafana** | `GRAFANA_URL` + `GRAFANA_SERVICE_ACCOUNT_TOKEN` (or `_TOKEN_FILE`, re-read per call for rotation); per-request `X-Grafana-URL` / `X-Grafana-Service-Account-Token`; separate *caller* bearer auth with constant-time compare | Loki `limit` default 10 / max 100, fetches `limit+1` to detect truncation; dashboard search 50/max 100 + 1-indexed `page`; datasources 50/100 + `offset`; alert rules default & max 200 | none anywhere | `CallToolResult{IsError:true}` with the raw wrapped Go error string; `*HardError` escalates to a JSON-RPC protocol error. **Responses >10 MB error instead of truncating**: `"response body exceeds maximum size of %d bytes; try narrowing your query"` |
| **PagerDuty** | `PAGERDUTY_USER_API_KEY` (REST v2, no OAuth). The `From` header is auto-set from `GET /users/me`; if that fails the server degrades to "account-level auth" and three tools refuse | One helper wrapping the SDK's `iter_all`, breaking at `maximum_records`. `MAX_RESULTS=1000`, `MAXIMUM_PAGINATION_LIMIT=100`, `DEFAULT_PAGINATION_LIMIT=20`. Caps vary per tool; `list_users` does **not** paginate at all; only `list_alert_grouping_settings` uses cursors | not handled | `ValueError` for blank/placeholder IDs; `RuntimeError("PagerDuty v3 Schedules API error (HTTP {status}): …")`. Several failures return **plain strings, not exceptions**. Truncation = a warning string appended when `count == MAX_RESULTS` |
| **Atlassian** | Per-product: Cloud prefers OAuth then `JIRA_USERNAME`+`JIRA_API_TOKEN`; Server/DC prefers `JIRA_PERSONAL_TOKEN`. Multi-user HTTP via `Bearer`/`Token`/`Basic` + `X-Atlassian-*` headers; unauthenticated HTTP **refused** unless `ALLOW_GLOBAL_CRED_FALLBACK=true` | No global scheme — per-tool `Field` constraints, mostly `le=50`. **`jira_search` `limit` has no upper bound** despite its "(1-50)" description; same for `jira_get_queue_issues`. Cloud-only `page_token` cursor on `jira_search`. The global clamp is disabled by default | not handled | All tools wrapped by `handle_tool_errors` → `ToolError("Error calling tool '<unprefixed name>': <detail>")`. Disabled and unknown tools both return byte-identical `NotFoundError("Unknown tool: …")`. **`confluence_get_page` returns failures as ordinary `{"error": …}` data with no `isError` flag.** No body truncation at all; only a 50 MB attachment cap |
| **Sentry** | Three paths: stdio user token (`SENTRY_ACCESS_TOKEN`, scopes `org:read project:read project:write team:read team:write event:write`), stdio OAuth device-code (sentry.io only), or Cloudflare OAuth / `Sentry-Bearer`. Per-tool `requiredScopes` is **deprecated** — the live gate is `skills` | Three coexisting schemes: hard `RESULT_LIMIT = 25` + `hasMore` boolean **with no cursor**; real opaque cursors on 3 tools; plain `limit` (1–100, default 10) elsewhere. Underlying client auto-paginates at `per_page=100` | 429 is rendered as an **Input Error** | Never thrown — always `{content:[{type:"text",text:<markdown>}], isError:true}` (explicit "DO NOT change this to throw" comment). Fixed templates: `**Input Error**`, `**Configuration Error**`, `**AI Provider Error**`, `**Authorization Expired**`, `**Error**` + `**Event ID**`. "Too many results" degrades to `hasMore:true` or `"… [truncated]"` + `truncatedFields[]` |
| **Kubernetes** | kubeconfig (`--kubeconfig` → `KUBECONFIG` → `~/.kube/config`) or in-cluster; per-request Bearer pass-through builds a derived rest.Config with only the caller's token; RFC8693 / keycloak / entra-obo token exchange. `require_oauth` rejects `cluster_auth_mode=kubeconfig` to preserve per-user audit | Label/field selectors only. **No limit, no continue token, no truncation** in core. `pods_log` `tail` defaults to 100; no `since`/`limitBytes`. Only netobserv caps bodies (4 MiB hard error / 2 MiB silent CSV truncate) | none | `IsError: true` + one TextContent of `err.Error()` verbatim: `failed to <verb> <noun>: <client-go StatusError>`. Denied resources → `resource not allowed: <gvk>` from a RoundTripper |
| **Elasticsearch** | `ES_URL` + (`ES_API_KEY` \| `ES_USERNAME`+`ES_PASSWORD`); HTTP `Authorization` header overrides per request | **None.** Paging is whatever the model writes into `query_body` / ES\|QL `LIMIT`. `_cat` tools return every row. No cap, no truncation | none | Every upstream failure becomes a **JSON-RPC protocol error**, not a tool result. `error_for_status_code()` discards the ES error body, so `index_not_found_exception` detail is lost. `get_mappings` **panics** on a non-matching wildcard |
| **Figma** | `FIGMA_API_KEY` (→ `X-Figma-Token`) or `FIGMA_OAUTH_TOKEN` (→ `Authorization: Bearer`); scopes *File content: Read*, *Dev resources: Read* | None — trees, not pages. `nodeId` scoping is the size lever; `depth` exists but the schema tells the model not to use it. No cap, no truncation | Classified but not acted on: `RETRYABLE_STATUSES = {408,425,429,500,502,503,504}` tagged for telemetry only | `isError:true` + one text block. 429 and 403 produce long diagnostic messages built from response headers/body — the 403 text literally instructs the LLM: *"explain the specific reason from the response body above to the user in plain language"* |
| **Snyk** | Interactive `snyk_auth` tool (not an env var); `snyk_trust <abs path>` is a **second gate**. LS side uses `SNYK_TOKEN`/`SNYK_API` | None — CLI scans, not paged lists | none | **Exit codes carry meaning**: 0 = no issues, **1 = issues found (not a failure)**, 2 = retryable failure, 3 = no supported projects. Real errors concatenate stdout + `"\n\n\nSTDERR output:\n"` + stderr |
| **mcp reference** | No auth on any of the seven. `filesystem` sandboxes to allowed dirs (roots **override** rather than merge); `git`'s `--repository` sandbox is **off by default** | Only `fetch` paginates — offset-based with the cursor embedded in prose: `"Content truncated. Call the fetch tool with a start_index of {n}…"` | none | Mixed: git `raise_exceptions=True`, fetch `False`, time re-wraps everything into `ValueError("Error processing mcp-server-time query: …")`. `git_branch` with a bad `branch_type` returns a **successful** result whose text is `Invalid branch type: …` |

## E3 — where each MCP surface is narrower than the REST API (summary)

Detail and citations live in each per-server note; the recurring patterns:

1. **No remediation anywhere.** Ten servers, zero ability to dismiss a security alert, file an exception, or open a fix PR from a finding.
2. **Kubernetes omits the operational verbs**: no port-forward, no `rollout` (any verb), no cordon/drain, no `kubectl cp`, no attach, no log follow/since, no watch, no deletecollection, no helm upgrade/rollback/history, and status subresource writes are stripped. Server-side apply with `Force: true` is the *only* write path.
3. **Elasticsearch exposes no writes at all** and only two `_cat` endpoints — no cluster health, no ILM, no snapshot, no scroll/PIT, no `_count`, no `_field_caps`.
4. **Figma is entirely read-only against Figma**: no comments, no versions, no webhooks, no variables, no team/project APIs; component extraction and prototype data are open roadmap items.
5. **Sentry hides 44 of 53 tools** behind a discovery tool, so the *effective* surface a naive client sees is nine.
6. **Atlassian's writes exist but administration does not** — no project/workflow/permission-scheme administration.
7. **PagerDuty's README omits registered tools** (every `*_schedule_v3_*` plus `create_user`), so the documented surface is narrower than the real one — the opposite of the usual direction.
8. **Snyk's platform API is absent**: no org-wide issue listing, no ignore/policy management, no `monitor`, no SBOM.
9. **GitHub gates by scope at registration time**, so an under-scoped token makes tools *disappear* rather than fail — an agent cannot tell "not permitted" from "not supported".
10. **The reference repo archived its vendor servers**: GitHub, GitLab, Google Drive, Google Maps, PostgreSQL, Puppeteer, Redis, Sentry, Slack, SQLite, Brave Search, AWS KB Retrieval, EverArt all moved to `modelcontextprotocol/servers-archived`, while the README 70 lines later still advertises `server-github` and `server-postgres` in its config example.

---

# OVERLAPS (E4) — where two servers answer the same question with different values

Each entry: the question a human actually asks, the competing tools, and **why the answers diverge**. These are the joins that make a task hard for an honest reason.

### 1. "How many open bugs are there?" — Jira vs GitHub Issues
- **Jira:** `jira_search` with JQL (`type = Bug AND status != Done`), `jira_get_project_issues`.
- **GitHub:** `list_issues` / `search_issues` (`label:bug state:open`).
- **Why they diverge:** Jira status is a per-project configurable *workflow* with a separate `resolution` field — "Done" is not a fixed value and `jira_get_project_issue_types` / `jira_search_fields` exist precisely because the schema is per-project. GitHub has only `open`/`closed`. The same defect frequently exists as *both* a Jira key and a GitHub issue: `jira_get_issue_development_info` returns the branches, commits and PRs linked to an issue, proving the two are cross-referenced but not reconciled. GitHub ships `find_duplicate` as a first-class tool — duplicate issues are a documented reality, not an edge case. Any single-source count is wrong; a union needs a link table that neither tool exposes.

### 2. "What is the error rate for checkout?" — Prometheus vs Loki vs Elasticsearch vs Sentry
- **Prometheus:** `query_prometheus` (`rate(http_requests_total{status=~"5.."}[5m])`).
- **Loki:** `query_loki_logs` / `query_loki_stats` (count of `level=error`).
- **Elasticsearch:** `search` / `esql`, or the *same* cluster via Grafana's `query_elasticsearch`.
- **Sentry:** `search_events` (event-level) or `search_issues` (grouped).
- **Why they diverge:** (a) **Sampling** — Sentry SDKs sample; the event count is a fraction of reality. (b) **Grouping** — Sentry `search_issues` returns *issues*, `search_events` returns *events*; these differ by orders of magnitude and both are legitimately "errors". (c) **Counter resets** — Prometheus counters reset on pod restart, so a crashlooping service under-reports via `rate()` exactly when it is most broken. (d) **Label vs field naming** — `service` (Prom) vs `service.name` (ES/OTel) vs `app` (k8s label) vs Sentry project slug; `list_prometheus_label_values` and `get_mappings` exist because nobody remembers which. (e) **Windows** — Prometheus `step`, Loki `limit` (default 10, max 100!), ES `size`, Sentry's `RESULT_LIMIT = 25` all cut the data differently. (f) **Retention** — Loki, ES indices and Sentry quotas expire at different horizons, so "last month" may be answerable in one and not the others.

### 3. "What broke?" — Sentry vs logs vs Kubernetes events vs Grafana Sift
- **Sentry:** `get_issue_details` + `get_event_stacktrace` + `get_issue_breadcrumbs`.
- **Logs:** `query_loki_logs`, or `pods_log` / `nodes_log` directly.
- **Kubernetes:** `events_list`, `pods_get`, `pods_top`, `nodes_stats_summary`.
- **Grafana:** `find_error_pattern_logs`, `get_sift_analysis`, `get_assertions`.
- **Why they diverge:** an **OOMKill** appears in `events_list` and `pods_top`, as a 502 spike in Prometheus, and *not at all* in Sentry — the process dies before the SDK flushes. A **CrashLoopBackOff** is a k8s event and a pod-log tail; Sentry sees silence. Conversely an unhandled exception in a healthy pod is a rich Sentry stack trace with no infrastructure signal whatsoever. An agent that consults one source will confidently produce the wrong root cause; the four sources are not redundant, they are complementary and each has a blind spot.

### 4. "Who is on call right now?" — PagerDuty vs Grafana OnCall (and PagerDuty vs itself)
- **PagerDuty:** `list_oncalls`, `get_schedule`, `list_schedule_users`.
- **Grafana OnCall:** `get_current_oncall_users`, `list_oncall_schedules`, `get_oncall_shift`, `list_oncall_teams`.
- **Why they diverge:** these are two independent on-call systems that many organisations run simultaneously (Grafana OnCall for alert routing, PagerDuty for paging). An override entered in one is invisible to the other. **Worse, PagerDuty overlaps itself**: v2 (`list_schedules`, `get_schedule`, `create_schedule_override`) and v3 (`list_schedule_v3_rotations`, `list_schedule_v3_overrides`, `create_schedule_v3_overrides`) coexist in the same MCP server, and the v3 tools are absent from the README's tool table. Two tools, same schedule, different models — and the notes record that `list_schedules` transparently redirects some GETs to v3.

### 5. "Is there an active incident, and is it customer-facing?" — PagerDuty vs Grafana Incident vs JSM vs status page
- **PagerDuty:** `list_incidents`, `get_incident`, `list_priorities`.
- **Grafana:** `list_incidents`, `get_incident`.
- **Jira Service Management:** `jira_get_queue_issues`, `jira_get_issue_sla`.
- **Status page:** `list_status_pages`, `get_status_page_post`, `list_status_page_post_updates`.
- **Why they diverge:** the **severity vocabularies are per-tenant configurable and different in each system** — PagerDuty has `urgency` (high/low) *and* a separate `priority` (`list_priorities`), Grafana Incident has its own severity, Jira has a priority field, and the status page has yet another enum, which is why PagerDuty exposes `list_status_page_severities`, `list_status_page_impacts` and `list_status_page_statuses` as three separate lookup tools. "Customer-facing" exists **only** on the status page — no incident object carries it. An agent asked "how many customer-facing incidents this week" must join PagerDuty incidents to status-page posts through a relationship that is not exposed as a tool.

### 6. "Which alerts are firing?" — Grafana vs PagerDuty vs Sentry
- **Grafana:** `list_alert_groups`, `get_alert_group`, `alerting_manage_rules` (read variant).
- **PagerDuty:** `list_alerts_from_incident`, `get_alert_from_incident`, `list_event_orchestrations`.
- **Sentry:** `find_alert_rules`, `get_alert_rule`, `find_monitors`, `find_uptime_monitors`.
- **Why they diverge:** a Grafana alert that routes into PagerDuty exists **twice** — once as a Grafana alert instance and once as a PagerDuty alert attached to an incident — with different IDs and different timestamps (Grafana stamps at rule evaluation, PagerDuty at ingest). PagerDuty's `list_alert_grouping_settings` and event orchestration mean N Grafana alerts may collapse into 1 PagerDuty incident, so counts will never match. Sentry alert rules and uptime monitors watch overlapping conditions on their own thresholds, entirely independently.

### 7. "What version is actually running?" — GitHub vs Sentry vs Kubernetes vs Grafana vs Helm vs PagerDuty
- **GitHub:** `list_releases`, `get_latest_release`, `get_release_by_tag`, `list_tags`.
- **Sentry:** `find_releases`, `get_release_details`.
- **Kubernetes:** `pods_get` / `resources_get` (container image tag), `helm_list` (chart + app version).
- **Grafana:** `get_annotations` (deploy annotations).
- **PagerDuty:** `list_change_events`, `list_service_change_events`.
- **Why they diverge:** each is created by a different actor at a different moment — the GitHub release at tag-cut, the Sentry release at SDK init or a CI step, the image tag at deploy, the Grafana annotation only if the CD pipeline bothers to post one, the PagerDuty change event only if an integration is wired. **Rollbacks break all of them**: GitHub still reports v2.3.0 as latest while the cluster runs v2.2.9, Sentry has both releases, and the Grafana annotation stream may show a deploy with no corresponding rollback marker. The running image tag is the only ground truth, and it is the one an agent is least likely to check.

### 8. "Are we exposed to this CVE?" — GitHub Dependabot vs Snyk (and CodeQL vs Snyk Code)
- **GitHub:** `list_dependabot_alerts`, `get_dependabot_alert`, `list_global_security_advisories`, `list_repository_security_advisories`.
- **Snyk:** `snyk_sca_scan`.
- **Why they diverge:** Dependabot is **asynchronous and branch-scoped** — it reflects the manifest/lockfile on the default branch after GitHub's dependency graph updates, so a fix merged five minutes ago still shows as vulnerable. Snyk scans the **working tree at call time**, so it sees uncommitted changes GitHub cannot. Severity scales differ (GitHub low/moderate/high/critical vs Snyk Critical/High/Medium/Low) and the advisory databases are not identical. The SAST pair is worse: `list_code_scanning_alerts` (CodeQL rule IDs) vs `snyk_code_scan` (Snyk rule IDs) flag overlapping-but-different findings on the same file with no shared identifier. And `snyk_sca_scan` **exits 1 when it finds anything** — an agent that treats non-zero as failure will report "scan failed" when the correct answer is "12 criticals".

### 9. "What does this service depend on, and who owns it?" — PagerDuty vs Kiali vs Confluence vs the repo
- **PagerDuty:** `list_services`, `get_technical_service_dependencies`, `list_business_services`, `get_business_service_dependencies`, `list_escalation_policies`.
- **Kubernetes/Kiali:** `kiali_get_mesh_traffic_graph` (observed traffic), `resources_list`.
- **Confluence:** `confluence_search` (an architecture page someone drew).
- **GitHub:** `get_file_contents` on CODEOWNERS — note there is **no dedicated ownership tool** anywhere in the corpus.
- **Why they diverge:** PagerDuty's service catalogue and dependency graph are **hand-maintained** and drift; Kiali's mesh graph is **observed reality** and only shows edges that carried traffic in the query window. Service names differ per tool (`checkout-svc` in PagerDuty, `checkout` namespace in k8s, `checkout_service` as a Prometheus label, "Checkout Platform" in Confluence). Ownership lives in an escalation policy, a CODEOWNERS file, a Jira component and a wiki table, and these four disagree routinely.

### 10. "What changed recently?" — local git vs GitHub vs PagerDuty vs Grafana vs Jira vs Confluence
- **Local:** `git_log`, `git_diff`, `git_status`.
- **GitHub:** `list_commits`, `get_commit`, `list_pull_requests`.
- **PagerDuty:** `list_change_events`, `list_incident_change_events`.
- **Grafana:** `get_annotations`.
- **Jira:** `jira_batch_get_changelogs` (field-level history).
- **Confluence:** `confluence_get_page_history`, `confluence_get_page_diff`.
- **Why they diverge:** the local working copy can be dirty, ahead, or behind — `git_status` and `list_commits` routinely disagree, and the reference git server's repo sandbox is off by default so it may not even be looking at the right checkout. Change events and annotations only exist where someone wired the integration. Jira changelogs record *when a field flipped*, which is often hours after the actual work.

### 11. "What's the runbook, and can I trust it?" — Confluence vs repo docs vs Sentry docs vs the agent's own memory
- **Confluence:** `confluence_search`, `confluence_get_page`.
- **Repo:** `get_file_contents` on `docs/`, `search_code`.
- **Sentry:** `search_docs`, `get_doc` (product docs, not yours).
- **Agent memory:** `search_nodes`, `read_graph`.
- **Why this one is special:** Confluence uniquely exposes **staleness signals as tools** — `confluence_get_page_history` (when it last changed), `confluence_get_page_diff` (what changed), and `confluence_get_page_views` (whether anyone still reads it). Repo docs are versioned with the code and therefore usually fresher but less complete. This is the clearest case in the corpus where the *right* behaviour is to check provenance rather than trust the first hit — and the tools to do so exist.

### 12. Intra-server overlaps (same server, two answers)
- **Sentry `search_issues` vs `search_events`** — grouped vs raw. Both are "how many errors"; the numbers differ by orders of magnitude.
- **Sentry direct tools vs `execute_sentry_tool`** — the same capability reachable two ways, with only 9 of 53 discoverable normally.
- **Kubernetes `pods_top` / `nodes_top` (metrics-server, instantaneous, windowed) vs Grafana `query_prometheus` (scraped time series)** — same CPU/memory question, different numbers because of scrape interval, rate window and metrics-server's own averaging.
- **Elasticsearch twice over** — the Elasticsearch MCP `search` / `esql` (direct, raw) vs Grafana `query_elasticsearch` (through a datasource that pins an index pattern and time field). Same cluster, different results.
- **PagerDuty schedules v2 vs v3** (see Overlap 4).
- **Grafana `grafana_api_request`** — a raw HTTP passthrough that can answer *any* Grafana question while bypassing every other tool's shaping, limits and read-only annotations.
- **GitHub `get_label`** is registered twice, in the `issues` and `labels` toolsets — 117 registrations for 116 names.

### 13. "Who is this person?" — identity has no shared key
`get_me` (GitHub), `whoami` (Sentry), `get_user_data` (PagerDuty), `jira_get_user_profile`, `confluence_search_user`, `list_users_by_org` (Grafana), `list_users` (PagerDuty). Email is the only plausible join key and it differs per system (corporate SSO vs personal GitHub account vs a PagerDuty login). Every cross-tool attribution question — "who deployed this", "who owns this alert", "who last touched this file" — silently depends on a join the corpus provides no tool for.

---

## Notes for building the simulated world

- **Weight the world by the real distribution.** GitHub, Grafana, PagerDuty and Atlassian carry ~70% of all tools; Figma, Elasticsearch and Snyk are tiny. A mock with even coverage would misrepresent the domain.
- **Reproduce read/write asymmetry.** Observability is 85/20 read-heavy (Grafana); source control is nearly 50/50 (GitHub 59/58). Security scanning is 100% read with no remediation path at all.
- **Reproduce the gating.** Read-only mode, `--enable-write-tools`, toolset selection and scope-based tool hiding mean the tool list an agent sees is configuration-dependent. In GitHub and Kubernetes, unavailable writes **vanish from `tools/list`** rather than failing — so "I can't do that" and "that isn't supported" are indistinguishable.
- **Reproduce the error idioms, not a generic error.** They are wildly inconsistent: Sentry returns formatted markdown with `**Input Error**` headings; Kubernetes returns a raw client-go `StatusError`; Elasticsearch throws away the ES error body entirely; Atlassian's `confluence_get_page` returns failure as ordinary data with no `isError`; Snyk signals "found issues" with exit code 1.
- **Reproduce the truncation idioms.** Grafana errors above 10 MB instead of truncating; Sentry emits `hasMore: true` with no cursor; GitHub uses five different mechanisms across its toolsets; Kubernetes and Elasticsearch have none at all.
- **The absent tools are as informative as the present ones.** No Slack, no CI beyond GitHub Actions and Tekton, no Terraform, no feature flags, no status-page write outside PagerDuty, no CODEOWNERS/ownership lookup, no spreadsheet. That is where E5's "data lives outside the system of record" pressure comes from.
