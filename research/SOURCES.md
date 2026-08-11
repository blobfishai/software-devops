# SOURCES

Consolidated link list for the domain research, grouped by section of
`00-QUESTIONS.md`. Every URL carries a one-line description of what it supports.

**Legend**
- `[P]` primary source (product docs, published postmortem, government report,
  peer-reviewed paper, the org's own research)
- `[S]` secondary (trade press, practitioner analysis, faithful reproduction of a
  primary table)
- `[V]` vendor marketing/blog — directional, not evidential
- `[!]` **could not be fetched** — cited from search-result snippets or partial
  access; verify before quoting verbatim

Detailed notes live in `notes/domain/{A,B,D,F}_*.md`.

---

## A. Domain and business value

### A1 — DORA metrics, definitions, benchmarks
| URL | Type | Supports |
|---|---|---|
| https://dora.dev/guides/dora-metrics/ | [P] | Verbatim current definitions of all five DORA metrics, split throughput/instability |
| https://dora.dev/guides/dora-metrics-four-keys/ | [P] | The fifth metric, Deployment Rework Rate — on the page still titled "four keys" |
| https://dora.dev/insights/dora-metrics-history/ | [P] | **The 2023 MTTR → "failed deployment recovery time" rename and its rationale; 2024 addition of rework rate** |
| https://dora.dev/research/ | [P] | Index of all DORA reports 2014–2025 |
| https://dora.dev/dora-report-2025/ | [P] | 2025 report landing page (download gateway only) |
| https://dora.dev/capabilities/streamlining-change-approval/ | [P] | External change approval (CAB) has a negative impact on delivery performance; peer review as the alternative |
| https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report | [P] | 2024: AI adoption → −1.5% throughput, −7.2% stability; 39% distrust AI code |
| https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report | [P] | 2025: throughput sign flips positive, **stability still negative**; seven team archetypes replace the four tiers |
| https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf | [P][!] | Full 2025 DORA report (exceeded fetch size limit) |
| https://services.google.com/fh/files/misc/2024_final_dora_report.pdf | [P][!] | Full 2024 DORA report (exceeded fetch size limit) |
| https://dora.dev/research/2019/dora-report/2019-dora-accelerate-state-of-devops-report.pdf | [P][!] | Source of the "2.6× more likely to be low performers" CAB statistic (binary, unparseable) |
| https://cloud.google.com/resources/content/dora-roi-of-ai-assisted-software-development | [P] | 2026 DORA ROI report: J-curve of AI value realisation |
| https://www.infoq.com/news/2026/05/dora-roi-ai-assisted-dev-report/ | [S] | InfoQ coverage of the DORA ROI report |
| https://octopus.com/blog/2024-devops-performance-clusters | [S] | Faithful reproduction of the 2024 Elite/High/Medium/Low table and the 182×/8×/127×/2293× gaps |
| https://octopus.com/devops/metrics/dora-metrics/ | [S] | Per-metric elite thresholds; cross-check on the above |
| https://octopus.com/blog/change-advisory-boards-dont-work | [S] | Corroboration of DORA's CAB finding |
| https://newsletter.getdx.com/p/2024-dora-report | [S] | Cluster population shift 2023→2024 (High 31%→22%, Low 17%→25%) |
| https://rdel.substack.com/p/rdel-68-what-are-the-latest-benchmarks | [S] | Why 2024 "High" had a *higher* change failure rate than "Medium" |
| https://rdel.substack.com/p/rdel-115-what-are-the-2025-benchmarks | [S][!] | 2025 per-metric distribution buckets — labelling conflates buckets with tiers, use with caution |
| https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025 | [S] | Explicit statement that DORA moved off low/medium/high/elite designations |
| https://www.splunk.com/en_us/blog/learn/state-of-devops.html | [S] | The seven 2025 team archetypes with population percentages |
| https://www.ibm.com/docs/en/devops-velocity/5.2.x?topic=reference-change-failure-rate-metric | [P] | A vendor's concrete CFR computation — shows implementations differ |
| https://gitlab.com/gitlab-org/gitlab/-/issues/299407 | [P] | GitLab tracking issue for CFR API support — evidence the metric is not trivially derivable |

### A2 — Incident cost, outage causes, on-call burden, engineering time
| URL | Type | Supports |
|---|---|---|
| https://sre.google/sre-book/introduction/ | [P] | **"roughly 70% of outages are due to changes in a live system"**; the 50% ops cap; the 3× playbook MTTR claim |
| https://sre.google/sre-book/eliminating-toil/ | [P] | The six-characteristic toil definition verbatim; the <50% cap; Google's measured ~33% actual toil |
| https://sre.google/sre-book/being-on-call/ | [P] | Max 2 incidents per 12-hour shift; **6 hours per incident including follow-up**; 5/30-min page targets; 25%/50% rules; 8-engineer minimum |
| https://uptimeinstitute.com/uptime_assets/d7c049ef5b02a6e0a15540a3e5cb8fbf742c7fa54a1af6caeaaab32b7c15d443-GA-2025-05-annual-outage-analysis.pdf | [P] | **The most sober cost source**: 54% >$100K, 1-in-5 >$1M; outage cause breakdowns; 40% human-error rate; **80% preventability**; 58% failure-to-follow-procedure |
| https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025 | [P] | Press release: 23% of impactful outages from IT/networking, attributed to change management and misconfiguration |
| https://uptimeinstitute.com/resources/research-and-reports/annual-outage-analysis-2025 | [P] | Report landing page |
| https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html | [P] | Splunk/Oxford Economics: $400B annually, $200M per company, component and cause breakdown |
| https://www.oxfordeconomics.com/resource/the-hidden-costs-of-downtime-the-400b-problem-facing-the-global-2000/ | [P] | Independent research partner's landing page for the same study |
| https://itic-corp.com/itic-2024-hourly-cost-of-downtime-report/ | [P] | >$300K/hour for 90% of mid/large enterprises; 41% at $1M–$5M/hour; n>1,000 |
| https://newrelic.com/resources/report/observability-forecast/2024/state-of-observability/outages-downtime-cost | [P] | $1.9M/hour median high-impact outage; 51-min median MTTR; 232 outages/year |
| https://newrelic.com/press-release/20241022 | [P] | New Relic survey methodology (~1,700 professionals, 16 countries) |
| https://newrelic.com/resources/report/observability-forecast/2023/state-of-observability/current-deployment | [P] | **Mean 5.1 monitoring tools per org; 86% use two or more** — the substrate for metric disagreement |
| https://newrelic.com/resources/report/observability-forecast/2023/state-of-observability/strategy-and-organization | [P] | Observability capability counts and consolidation preference |
| https://newrelic.com/resources/report/observability-forecast/2025 | [P] | Latest Observability Forecast edition |
| https://www.pagerduty.com/newsroom/2026-state-of-ai-first-operations/ | [P] | 8% lose >$1M/hour; 68% >$300K/hour; 42% cite developer burnout; Wakefield Research n=1,000 |
| https://www.pagerduty.com/newsroom/pagerduty-state-of-digital-operations-report-underscores-business-and-human-costs-of-pandemic/ | [P] | **Platform telemetry (700,000 users)**: 19 off-hours interruptions/month = burnout; correlation with turnover |
| https://www.catchpoint.com/press-releases/the-sre-report-2025-highlighting-critical-trends-in-site-reliability-engineering | [P] | **Median toil rose to 30% from 25% — first increase in five years — with AI supervision named as the mechanism**; n=301 |
| https://www.catchpoint.com/press-releases/the-sre-report-2024-reveals-state-of-site-reliability-engineering | [P] | Prior-year SRE Report for the trend baseline |
| https://stripe.com/files/reports/the-developer-coefficient.pdf | [P] | 41.1-hour week; **17.3 hrs/week on maintenance (42%)**; 13.5 hrs technical debt; ~$300B GDP model; Harris Poll, 2018 |
| https://dl.acm.org/doi/10.1145/3723158 | [P] | ACM Computing Surveys review of alert fatigue in SOCs — **the citable academic anchor** |
| https://incident.io/blog/alert-fatigue-solutions-for-dev-ops-teams-in-2025-what-works | [V] | Source of widely-circulated alert-actionability percentages — **notable for having no attribution or sample sizes** |
| https://incident.io/blog/on-call-best-practices-guide-2026 | [V] | On-call guidance; MTTA <5 min; handoff checklist with read-back |

> **Explicitly unsourced:** the Gartner **$5,600/minute** figure. No primary
> Gartner publication was obtained. Treat as folklore-grade.
> Also unsourced: any industry-wide **alert-actionability percentage**, and any
> published **"cost per bad deploy"** figure.

### A3 — Cost of being wrong
| URL | Type | Supports |
|---|---|---|
| https://blog.gitguardian.com/the-state-of-secrets-sprawl-2025/ | [P] | 23.8M secrets leaked on public GitHub in 2024 (+25%); 70% of 2022 secrets still active; 35% of private repos affected |
| https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/ | [P] | 28.65M secrets in 2025 (+34%); **AI-service leaks +81%**; 64% of 2022 secrets still live; ~28% of incidents originate outside repos |
| https://www.gitguardian.com/state-of-secrets-sprawl-report-2025 | [P] | Report landing page |
| https://www.verizon.com/business/resources/Tea/reports/2025-dbir-data-breach-investigations-report.pdf | [P][!] | Stolen credentials in 22% of breaches — top initial access vector (figures from search summaries) |
| https://www.ibm.com/think/x-force/2025-cost-of-a-data-breach-navigating-ai | [P][!] | IBM 2025: $4.44M global, $10.22M US, 241 days; 20% shadow AI (**ibm.com 403s to automated fetch**) |
| https://www.ibm.com/reports/data-breach | [P][!] | IBM Cost of a Data Breach hub, current edition (403s) |
| https://www.cybersecuritydive.com/news/data-breach-costs-ai-governance-ibm/826463/ | [S] | IBM 2026: ~$5M (+12%); shadow AI in 43% of incidents; n=602 organisations |

### A4 — Already automated by deterministic tooling
| URL | Type | Supports |
|---|---|---|
| https://argo-rollouts.readthedocs.io/en/stable/features/analysis/ | [P] | Automated canary analysis with automatic abort and traffic revert to the stable ReplicaSet |
| https://docs.flagger.app/ | [P] | Progressive delivery with automated metric-threshold rollback across seven metric providers |
| https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/ | [P] | HPA control loop, 15s default sync, **closed-form scaling algorithm** |
| https://karpenter.sh/docs/concepts/disruption/ | [P] | Automated node consolidation, drift detection, expiry, disruption budgets |
| https://kubernetes.io/docs/concepts/architecture/controller/ | [P] | The control-loop / self-healing model underlying all of the above |
| https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/ | [P] | Automatic container restart and automatic endpoint removal |
| https://argo-cd.readthedocs.io/en/stable/ | [P] | Continuous monitoring, `OutOfSync` detection, automated sync back to target |
| https://fluxcd.io/flux/concepts/ | [P] | Five-minute reconciliation; manual `kubectl` changes **"will be promptly reverted"** |
| https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates | [P] | Automatic vulnerability-triggered upgrade PRs, and their all-or-nothing limitation |
| https://docs.renovatebot.com/ | [P] | Automated dependency PRs, automerge, scheduling, deprecation-replacement PRs |
| https://cert-manager.io/docs/ | [P] | Automatic certificate issuance and renewal before expiry |
| https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health | [P] | Periodic drift detection with drifted-resource counts and **two competing resolution paths** — the judgement gap |

---

## B. Stakeholders and the shape of the work

### B1 — Google SRE primary sources
| URL | Type | Supports |
|---|---|---|
| https://sre.google/sre-book/managing-incidents/ | [P] | The four roles verbatim; recursive separation of responsibilities; the three incident-declaration questions; "stop the bleeding, restore service, preserve the evidence" |
| https://sre.google/sre-book/effective-troubleshooting/ | [P] | Six-stage model; **"Ignore that instinct!"** — mitigation before diagnosis; documented troubleshooting pitfalls |
| https://sre.google/sre-book/postmortem-culture/ | [P] | **The five postmortem trigger criteria verbatim**; the blameless definition; "No Postmortem Left Unreviewed" |
| https://sre.google/workbook/incident-response/ | [P] | IMAG, ICS basis, the three Cs, IC/CL/OL definitions, "declaring incidents early and often" |
| https://sre.google/workbook/on-call/ | [P] | Handoff email protocol; 5/8-per-site minimums; 12h shift cap; actionable-alerts rule; **playbook staleness quote**; readiness checklist |
| https://sre.google/workbook/postmortem-culture/ | [P] | P[01] bug enforcement; "a postmortem without subsequent action is indistinguishable from no postmortem" |
| https://sre.google/resources/practices-and-processes/incident-management-guide/ | [P] | Google's incident-management guide; when an event becomes a managed incident |
| https://sre.google/sre-book/monitoring-distributed-systems/ | [P] | Alerting-rule hygiene; pruning rules unused for a quarter |
| https://google.github.io/building-secure-and-reliable-systems/raw/ch05.html | [P] | Least privilege; **Multi-Party Authorization (two-person rule)**; break-glass definition and controls; temporary access tied to on-call; Zero Touch Production |

### B1/B2 — PagerDuty
| URL | Type | Supports |
|---|---|---|
| https://response.pagerduty.com/before/different_roles/ | [P] | The six PagerDuty roles verbatim (IC, Deputy, Scribe, SME, Customer Liaison, Internal Liaison); role-combining rule |
| https://response.pagerduty.com/before/severity_levels/ | [P] | **SEV-1…SEV-5 table — where SEV-1 is defined by audience (public/exec notification), not impact**; "treat it as the higher one" |
| https://response.pagerduty.com/before/what_is_an_incident/ | [P] | Incident vs major incident definitions; "if you are unsure... trigger our incident response process" |
| https://response.pagerduty.com/during/during_an_incident/ | [P] | The IC six-step run loop; 30-min exec cadence; **closure criterion = "no more productive work"** |
| https://response.pagerduty.com/after/post_mortem_process/ | [P] | Postmortem required for SEV-2/1; 3-day / 5-day meeting timelines |
| https://response.pagerduty.com/oncall/being_oncall/ | [P] | 5-min escalation timeout; readiness requirements; handoff; "Never hesitate to escalate" |
| https://ownership.pagerduty.com/on-call/ | [P] | On-Call Review Meeting — a retrospective on the *shift*, not the incident |

### B2 — Severity ladders that disagree
| URL | Type | Supports |
|---|---|---|
| https://developer.atlassian.com/developer-guide/app-incident-severity-levels/ | [P] | **Atlassian's second, incompatible SEV1**: defined by user counts (>5,000,000 users) and app counts; 15-min investigation / 1-hour update SLA |
| https://www.atlassian.com/incident-management/kpis/severity-levels | [V][!] | Atlassian's impact-based SEV1–SEV3 (page body not fetchable) |
| https://www.datadoghq.com/blog/how-datadog-manages-incidents/ | [V] | **Dual-axis SEV-1…SEV-5 (external impact AND internal blockage); SEV-5 includes "Planned operational tasks"**; Stable vs Resolved; five roles |
| https://incident.io/guide/foundations/severities | [V] | Minor/Major/Critical; "Prefer human words... over codewords like SEV-1"; **"Severities are subjective"** |
| https://incident.io/blog/differences-between-severity-and-priority | [V] | Severity vs priority as separate axes; a Sev1–Sev4 ladder contradicting their own guide |
| https://incident.io/blog/what-is-a-sev-1-incident | [V] | "safe defaults rather than prescriptive advice" |
| https://incident.io/blog/designing-your-incident-severity-levels | [V] | Low/Medium/High/Critical ladder; Goldilocks principle |
| https://firehydrant.com/blog/getting-started-with-severity-levels/ | [V] | SEV1–SEV3 with an optional **SEV0** for catastrophe |
| https://firehydrant.com/glossary/severity/ | [V] | Severity glossary; inconsistent application without clear definitions |
| https://docs.firehydrant.com/docs/severities-and-priorities | [P] | Severity and priority modelled as **separate fields** |
| https://docs.firehydrant.com/docs/severity-matrix | [P] | Severity auto-assigned from impacted components |
| https://rootly.com/incident-response/support-levels | [V] | A **P1–P3 "support level"** vocabulary running alongside SEV levels |
| https://rootly.com/blog/practical-guide-to-sre-incident-severity-levels | [V] | Practitioner survey of severity conventions |
| https://aws.amazon.com/premiumsupport/plans/ | [P] | **AWS abandons SEV numbering entirely** — named system-state tiers with <15-min / <5-min response |
| https://cloud.google.com/terms/tssg | [P] | **Google Cloud P0–P4, customer-designated, with Google's reclassification "final and binding on Customer"** |
| https://azure.microsoft.com/en-us/support/plans/response | [P][!] | Azure uses **letters** — Sev A/B/C |
| https://www.xurrent.com/blog/incident-severity-levels | [V] | Evidence that SEV0–SEV5 ladders exist (top-of-ladder variance) |
| https://uptimerobot.com/knowledge-hub/monitoring/severity-levels-explained/ | [V] | Confirms numbering direction is **uniformly lower-is-worse** — an inverted ladder was hunted for and NOT FOUND |
| https://opsbrief.io/blog/incident-severity-levels-how-to-define-sev0-sev1-sev2-and-sev3 | [V] | The four things a severity level must map to |

### B3 — "Done", lifecycle states, MTTx
| URL | Type | Supports |
|---|---|---|
| https://docs.firehydrant.com/docs/incident-milestones-lifecycle-phases | [P] | **10 milestones; Mitigated vs Resolved vs Closed verbatim; all four MTTx metrics computed from incident *start*** |
| https://firehydrant.com/glossary/mitigation/ | [V] | The mitigation→resolution gap as a tech-debt signal |
| https://incident.io/guide/foundations/statuses | [V] | Investigating/Fixing/Monitoring; Impact mitigated / Debrief completed / Closed |
| https://support.atlassian.com/statuspage/docs/create-an-incident/ | [P] | **Statuspage "Resolved" = root cause eliminated and 100% performance — the strictest published bar**; Investigating/Identified/Monitoring |
| https://support.atlassian.com/statuspage/docs/what-is-a-component/ | [P] | Component statuses: Degraded Performance / Partial Outage / Major Outage |
| https://support.atlassian.com/statuspage/docs/incident-communication-tips/ | [P] | 30-minute update cadence; content and tone guidance |
| https://betterstack.com/community/guides/incident-management/mttr-and-other-incident-metrics/ | [S] | **The four different MTTRs with definitions and identical formula shape**: "Same incidents, four very different averages" |
| https://www.atlassian.com/incident-management/kpis/common-metrics | [V][!] | MTTA/MTTR/MTBF/MTTF; confirms the four-way MTTR collision (body not fetchable) |
| https://www.atlassian.com/incident-management/incident-response/roles-responsibilities | [V][!] | Atlassian Incident Manager / Communications Manager / Tech Lead definitions (body not fetchable) |
| https://www.atlassian.com/incident-management/handbook | [V][!] | Atlassian Incident Management Handbook (nav-chrome only on fetch) |
| https://pages.eml.atlassian.com/rs/594-ATC-127/images/Atlassian-incident-management-handbook-.pdf | [V][!] | Handbook PDF (binary, unparsed) |

### B4/B5 — Access control, break-glass, status pages
| URL | Type | Supports |
|---|---|---|
| https://hoop.dev/blog/compliance-requirements-and-best-practices-for-secure-break-glass-access | [V] | SOC 2 / ISO 27001 / HIPAA / PCI DSS break-glass requirements: documented approval, time-bound auto-expiring access, tamper-proof audit |
| https://docs.cyberark.com/manage/latest/en/content/sca/dpaforcloud/breakglass.htm | [P] | Break-glass operational practice from a PAM vendor's product docs |
| https://getlogwise.com/blog/atlassian-status-page-incident-communication-playbook | [V] | Practitioner 10–15 min major-incident cadence (opinion, not doctrine) |
| https://statusdrop.dev/guides/status-page-best-practices | [V] | Always state when the next update lands |

---

## D. Input documents and context

### D1 — Published postmortems
| URL | Type | Supports |
|---|---|---|
| https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/ | [P] | WAF regex catastrophic backtracking; **a non-emergency change bypassing staged rollout**; global CPU exhaustion |
| https://blog.cloudflare.com/18-november-2025-outage/ | [P] | **ClickHouse permissions change → duplicate rows → oversized feature file → Rust `unwrap()` panic**; flapping mistaken for DDoS; status page down coincidentally |
| https://blog.cloudflare.com/fail-small-resilience-plan/ | [P] | Cloudflare's remediation programme: staged config rollout, Health Mediated Deployments, break-glass review |
| https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/ | [P] | `rm -rf` on the primary; **five backup methods failed**; DMARC-rejected failure emails meant "no indication of failure" |
| https://aws.amazon.com/message/41926/ | [P] | S3 2017: mistyped input to an established playbook command; subsystems never fully restarted "for many years" |
| https://aws.amazon.com/message/11201/ | [P] | Kinesis 2020: small capacity addition exceeded an **OS thread limit** across the whole front-end fleet |
| https://aws.amazon.com/message/12721/ | [P] | Dec 2021: internal-network congestion; **monitoring data unavailable to responders**; Service Health Dashboard failed to fail over |
| https://aws.amazon.com/message/101925/ | [P] | Oct 2025: **DNS Planner/Enactor race → empty DNS record**; EC2 DWFM "congestive collapse" |
| https://slack.engineering/slacks-outage-on-january-4th-2021/ | [P] | TGW saturation **inverted the CPU autoscaling signal**, causing scale-down at peak; open-files and quota limits blocked recovery |
| https://about.roblox.com/newsroom/2022/01/roblox-return-to-service-10-28-10-31-2021/ | [P] | 73 hours: Consul streaming Go-channel contention + BoltDB freelist degradation; **circular observability dependency** |
| https://www.crowdstrike.com/wp-content/uploads/2024/08/Channel-File-291-Incident-Root-Cause-Analysis-08.06.2024.pdf | [P] | 21 declared vs 20 supplied input fields; missing runtime array bounds check in a kernel driver; Content Validator logic error |
| https://www.crowdstrike.com/en-us/blog/channel-file-291-rca-available/ | [P] | Announcement of the above RCA |
| https://github.blog/news-insights/company-news/oct21-post-incident-analysis/ | [P] | A 43-second partition → cross-DC Orchestrator failover → 24h11m; **"we have never needed to fully rebuild an entire cluster from backup"** |
| https://www.atlassian.com/blog/atlassian-engineering/post-incident-review-april-2022-outage | [P] | 883 sites deleted in 23 minutes; **explicitly names missing runbooks as a duration factor** |
| https://www.reddit.com/r/RedditEng/comments/11xx5o0/you_broke_reddit_the_piday_outage/ | [P][!] | Reddit Pi-Day 2023 primary (reddit.com blocked to the fetcher) |
| https://geek-cookbook.funkypenguin.co.nz/blog/2023/03/24/post-mortem-reddit-pi-day-kube-1.25/ | [S] | Fetched secondary reproducing Reddit's quotes: config "committed nowhere"; restore procedure rewritten live |
| https://overmind.tech/blog/reddit-pi-day-outage | [S] | Further analysis of the Reddit outage |
| https://github.com/danluu/post-mortems | [P] | Curated postmortem corpus, ~200+ entries in 9 categories |
| https://k8s.af/ | [P] | Kubernetes Failure Stories index, ~60+ entries since 2017 |
| https://github.com/hjacobs/kubernetes-failure-stories | [P] | Source repo (archived Aug 2020) |
| https://codeberg.org/hjacobs/kubernetes-failure-stories | [P] | Active mirror after archival |

### D2 — Runbooks
| URL | Type | Supports |
|---|---|---|
| https://sre.google/sre-book/introduction/ | [P] | **Actual location** of "roughly a 3x improvement in MTTR ... vs 'winging it'" |
| https://sre.google/workbook/on-call/ | [P] | Playbook definition; alert↔playbook coupling; "if your playbooks are a deterministic list of commands... implement automation" |
| https://www.pagerduty.com/resources/learn/what-is-a-runbook/ | [V] | Limoncelli's 7-section runbook structure; runbook vs playbook distinction |
| https://gitlab.com/gitlab-com/runbooks | [P] | **The largest genuinely public SRE runbook corpus** |
| https://gitlab.com/gitlab-com/runbooks/-/raw/master/README.md | [P] | Directory layout; Symptoms/Pre-checks/Resolution/Post-checks/Rollback format; alerts and docs co-generated from Jsonnet |
| https://runbooks.gitlab.com | [P] | Rendered version of the above |
| https://runbooks.prometheus-operator.dev/ | [P] | One runbook page per alert name; Meaning / Impact / Diagnosis / Mitigation |
| https://runbooks.prometheus-operator.dev/runbooks/kubernetes/kubepodcrashlooping/ | [P] | Worked example of that four-section format |
| https://github.com/kubernetes-monitoring/kubernetes-mixin/blob/master/runbook.md | [P] | Deliberately terse per-alert index — the contrast case |
| https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-documents.html | [P] | Executable runbooks: YAML/JSON schema, 20 action types, `aws:branch` conditionals |
| https://rootly.com/incident-response/runbooks | [V] | 7-section runbook template + review cadence + "a single outdated command can destroy trust" |
| https://incident.io/blog/automated-runbook-guide | [V] | Three-layer automated runbook model; documentation-decay quote; 30–50% MTTR claim (unverified) |
| https://www.atlassian.com/incident-management/incident-response/how-to-create-an-incident-response-playbook | [V][!] | Atlassian playbook guide (nav-chrome only on fetch) |

### D3 — Alert payload schemas
| URL | Type | Supports |
|---|---|---|
| https://prometheus.io/docs/alerting/latest/configuration/#webhook_config | [P] | **Full Alertmanager webhook JSON schema, including `truncatedAlerts` and `notification_reason`** |
| https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/ | [P] | Alerting-rule keys; labels are routable, annotations hold "runbook links" |
| https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/main/manifests/alertmanager-prometheusRule.yaml | [P] | Real shipped rules showing `annotations.{description,runbook_url,summary}` + `labels.severity` |
| https://github.com/prometheus-operator/kube-prometheus/issues/731 | [P] | Tracking `runbook_url` annotation coverage gaps |
| https://github.com/prometheus-operator/kube-prometheus/issues/1001 | [P] | Missing `runbook_url` annotations |
| https://prometheus.io/docs/alerting/latest/alertmanager/ | [P] | **Grouping, inhibition and silencing** — why 1 failure ≠ 1 alert ≠ 1 page |
| https://github.com/prometheus/alertmanager/blob/main/docs/alertmanager.md | [P] | Same, from the source repo |
| https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/ | [P] | Grafana webhook payload — Alertmanager superset with `orgId`, `state`, `values`, `silenceURL`, `dashboardURL`, `panelURL`, `imageURL` |
| https://support.pagerduty.com/main/docs/pd-cef | [P] | PD-CEF field reference: summary/severity/source/timestamp/component/group/class/custom_details |
| https://raw.githubusercontent.com/PagerDuty/API_Python_Examples/master/EVENTS_API_v2/trigger/trigger_without_incident_key.py | [P] | Literal Events API v2 request body and the `events.pagerduty.com/v2/enqueue` endpoint |
| https://developer.pagerduty.com/docs/events-api-v2-overview | [P][!] | Events API v2 overview — **empty body to fetchers (JS-rendered)** |
| https://developer.pagerduty.com/docs/events-api-v2/trigger-events/ | [P][!] | `routing_key` / `event_action` / `dedup_key` semantics (from search excerpts) |
| https://support.pagerduty.com/main/docs/webhooks | [P] | v3 outbound webhook envelope and `x-pagerduty-signature` |
| https://docs.datadoghq.com/integrations/webhooks/ | [P] | **Datadog has NO fixed payload — the body is composed from `$`-variables, so the shape is per-installation** |
| https://docs.opsgenie.com/docs/alert-api | [P] | Opsgenie create-alert fields; P1–P5 priorities, default P3 |
| https://docs.sentry.io/organization/integrations/integration-platform/webhooks/issues/ | [P] | Sentry issue webhook body and `Sentry-Hook-*` headers |
| https://docs.datadoghq.com/monitors/guide/how-to-update-anomaly-monitor-timezone/ | [P] | **Datadog monitors use UTC and do not track local time zones by default** |

### D4 — ADRs
| URL | Type | Supports |
|---|---|---|
| https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions | [P] | Nygard's original: Title / Context / Decision / Status / Consequences, with the motivation and length constraint |
| https://adr.github.io/ | [P] | ADR and ADL definitions |
| https://adr.github.io/adr-templates/ | [P] | Template catalogue: MADR, Nygard, Y-Statement, ISO/IEC/IEEE 42010:2011 |
| https://github.com/adr/madr | [P] | MADR project |
| https://raw.githubusercontent.com/adr/madr/main/template/adr-template.md | [P] | **Full MADR template**: front matter (`status`, `date`, `decision-makers`, `consulted`, `informed`) + all body headings incl. *Confirmation* |
| https://github.com/npryce/adr-tools | [P] | adr-tools CLI; `doc/adr/NNNN-*.md`; `-s` **auto-updates the superseded record's status** |
| https://github.com/arachne-framework/architecture | [P] | Real 17-ADR public collection in Nygard format |
| https://github.com/joelparkerhenderson/architecture-decision-record | [P] | 13 named ADR templates + links to AWS and RedHat guidance |

### D5 — Documentation staleness
| URL | Type | Supports |
|---|---|---|
| https://sre.google/workbook/on-call/ | [P] | **"Details in playbooks go out of date at the same rate as production environment changes"**; the general-vs-prescriptive trade-off |
| https://opensourcesurvey.org/2017/ | [P] | **"Incomplete or outdated documentation is a pervasive problem, observed by 93% of respondents"**; 60% rarely/never contribute docs |
| https://stackoverflow.blog/2024/12/19/developers-hate-documentation-ai-generated-toil-work/ | [S] | 30+ min/day searching; docs = 11% of work hours; 17+ hrs/week maintenance |
| https://survey.stackoverflow.co/2025 | [P] | 2025 top frustrations: 66% "AI almost right but not quite", 45% debugging AI code |
| https://stackoverflow.blog/2025/01/01/developers-want-more-more-more-the-2024-results-from-stack-overflow-s-annual-developer-survey/ | [S] | 2024: technical debt the largest frustration by a large margin |
| https://www.gremlin.com/blog/ensuring-runbooks-are-up-to-date | [V] | "if it is not already outdated, it will be"; chaos engineering as runbook validation |
| https://ekline.io/blog/why-your-incident-runbook-lies-to-you-at-3-a-m-and-how-to-tell-before-the-page-fires | [V][!] | Stale runbook as degraded capability; 8–15 min per wrong step (**vendor estimate, not measurement**) |
| https://rootly.com/incident-response/playbooks | [V] | Playbook governance, ownership, version control |
| https://arxiv.org/abs/2409.10781 | [P] | **Inconsistent changes ~1.5× more likely to introduce bugs; impact highest immediately after the inconsistency is introduced** |
| https://dl.acm.org/doi/abs/10.1109/ICPC.2019.00019 | [P][!] | Wen et al., large-scale empirical study of code-comment inconsistencies, ICPC 2019 (paywalled) |
| https://ieeexplore.ieee.org/document/8813274/ | [P][!] | IEEE version of the same paper (paywalled) |
| https://arxiv.org/pdf/2212.01479 | [P] | Detecting outdated code-element references in repository documentation |
| https://arxiv.org/pdf/2506.20558 | [P] | CCISolver: end-to-end detection/repair of code-comment inconsistency |

---

## F. Chaos — why this is hard in real life

### F1 — Naming drift, catalogs, tagging
| URL | Type | Supports |
|---|---|---|
| https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/ | [P] | **`env`/`service`/`version` as the join key; "that pod's data contains both `env` tags"; `service` silently defaults to the container short-image** |
| https://www.datadoghq.com/blog/unified-service-tagging/ | [V] | Datadog's framing of the inconsistent-tagging problem |
| https://github.com/DataDog/helm-charts/issues/43 | [P] | Filed issue: "Unified service tagging is not possible" |
| https://github.com/DataDog/datadog-agent/issues/16556 | [P] | Admission controller fails to pick up pod annotations for USTs |
| https://github.com/DataDog/helm-charts/issues/145 | [P] | Tags set three different ways; `service` missing from metrics |
| https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/ | [P] | **`deployment.environment.name` (renamed); the rule that (frontend, production) and (frontend, staging) MUST be the same service** |
| https://backstage.io/docs/features/software-catalog/descriptor-format/ | [P] | Entity schema; `spec.owner` as a free-text pointer |
| https://backstage.io/docs/features/software-catalog/well-known-relations/ | [P] | The relations graph that consistent ownership naming feeds |
| https://gitlab.com/gitlab-org/gitlab/-/issues/377916 | [P] | **"Deployment tier guesses incorrect tier for string 'nonprod'"** — a real bug where `grep prod` inverts an environment's meaning |
| https://gitlab.com/gitlab-org/gitlab/-/issues/27630 | [P] | Customising the Kubernetes namespace per environment |
| https://priocept.com/2018/01/30/software-environment-naming/ | [S] | The industry has no agreed environment vocabulary; competing term sets enumerated |
| https://docs.aws.amazon.com/prescriptive-guidance/latest/tagging-best-practices/tagging-practices-to-avoid.html | [P] | AWS's own "tagging practices to avoid"; incomplete tags → unreliable automation |
| https://docs.solo.io/istio/1.30.x/ambient/multicluster/segments/about/ | [P] | **Kubernetes "namespace sameness"** — identical namespace names in different clusters are the same logical namespace |
| https://cloudfleet.ai/blog/cloud-native-how-to/2024-11-kubernetes-namespaces-best-practices/ | [V] | The common convention of using the *cluster* as the environment boundary, so the namespace carries no environment |

### F1 — Metrics that disagree
| URL | Type | Supports |
|---|---|---|
| https://promlabs.com/blog/2021/01/29/how-exactly-does-promql-calculate-rates/ | [S] | `rate()`/`increase()` **extrapolate to window boundaries** — the result is an estimate, not an accounting figure |
| https://prometheus.io/docs/practices/histograms/ | [P] | Client-side quantiles (Summaries) **cannot be aggregated**; histograms can, via `histogram_quantile()` with bucket-dependent accuracy |
| https://clickhouse.com/resources/engineering/percentiles-vs-averages | [V] | Worked example: averaging per-host p99s reports 550 ms where the fleet p99 is 1,000 ms |
| https://aws.amazon.com/blogs/mt/how-stripe-architected-massive-scale-observability-solution-on-aws | [P] | **Stripe dual-writing 300M metrics to legacy TSDB and AMP, with cross-system validation deferred** |

### F1 — Duplicate trackers, orphaned alerts, dashboard rot
| URL | Type | Supports |
|---|---|---|
| https://link.springer.com/article/10.1007/s10664-015-9404-6 | [P] | "Studying the needed effort for identifying duplicate issues" (EMSE) |
| https://link.springer.com/article/10.1007/s10664-015-9387-3 | [P] | Contextual duplicate bug report detection and ranking (EMSE) |
| https://www.researchgate.net/figure/Duplicate-bug-reports-in-OpenOffice-Mozilla-and-Eclipse_tbl2_284096335 | [S] | **28.9% / 36.6% / 50.8% of *duplicate* bug reports carry inconsistent severity labels** in OpenOffice / Mozilla / Eclipse |
| https://arxiv.org/pdf/2212.09976 | [P] | Textual dissimilarity defeating duplicate bug detection |
| https://linear.app/docs/jira | [P] | Changing metadata in synced Jira spaces "may cause the Jira issue and Linear issue to become out of sync" |
| https://linear.app/changelog/2024-11-13-improvements-for-slas-templates-and-jira-and-github-issues-sync | [P] | Shipped because "it was hard to tell if a Linear issue successfully synced or if there had been errors" |
| https://linear.app/integrations/jira | [P] | Bidirectional Jira sync surface |
| https://unito.io/blog/how-to-integrate-github-and-jira/ | [V] | The classic duplicate generator: GitHub's issues feed includes pull requests |
| https://www.datadoghq.com/blog/how-to-audit-and-clean-up-monitors/ | [V] | Monitors accumulate for deprecated services, old versions and decommissioned hosts |
| https://docs.dynatrace.com/docs/dynatrace-intelligence/use-cases/avoid-overalerting | [P] | Vendor doc on over-alerting and orphaned alerts |
| https://argo-cd.readthedocs.io/en/stable/user-guide/orphaned-resources/ | [P] | Argo CD ships **"Orphaned Resources Monitoring"** as a first-class feature |
| https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/ | [P] | Grafana names **"unchecked dashboard sprawl"** as a scaling risk |
| https://grafana.com/docs/grafana/latest/visualizations/dashboards/assess-dashboard-usage/ | [P] | Grafana ships a feature to find "most-used, broken, and unused dashboards" |

### F1 — Tool sprawl and half-migrated systems
| URL | Type | Supports |
|---|---|---|
| https://www.okta.com/newsroom/articles/businesses-at-work-2025/ | [P] | Global average apps per company passes **100 for the first time** |
| https://www.okta.com/sites/default/files/2024-04/Okta-2024_Businesses_at_Work.pdf | [P] | Prior-year edition for methodology and trend |
| https://www.infoq.com/articles/shadow-table-strategy-data-migration/ | [S] | The shadow-table / dual-write extraction pattern — **two systems of record as a deliberate steady state** |

### F2 — Cross-tool reconciliation questions
| URL | Type | Supports |
|---|---|---|
| https://www.thevoid.community/report | [P] | **VOID: ~10,000 incidents from ~600 companies; recommends retiring MTTR** |
| https://www.thevoid.community/ | [P] | VOID database homepage |
| https://www.infoq.com/articles/incident-metrics-void/ | [S] | Courtney Nash on skewed distributions; **"no correlation detected between incident duration and incident severity"**; "gray data"; Allspaw's "shallow data" |
| https://www.usenix.org/conference/srecon22americas/presentation/nash | [P] | SREcon talk: "Tales from the VOID: The Scary Truth about Incident Metrics" |
| https://www.verica.io/blog/mttr-is-a-misleading-metric-now-what/ | [V] | Vendor restatement of the MTTR argument |
| https://www.csoonline.com/article/574243/mttr-not-a-viable-metric-for-complex-software-system-reliability-and-security.html | [S] | Trade-press coverage of the same finding |
| https://www.thousandeyes.com/blog/why-you-should-not-trust-the-status-page | [S] | Status pages lag internal state "minutes or even hours" |
| https://www.pagerduty.com/resources/outages/learn/status-page-best-practices/ | [V] | Status-page communication practice and its failure modes |
| https://www.cisa.gov/sites/default/files/publications/CSRB-Report-on-Log4-July-11-2022_508.pdf | [P][!] | **CSRB Log4j report** — asset-inventory recommendation; few orgs could respond at the required speed (**cisa.gov 403s to automated fetch**) |
| https://www.cisa.gov/sites/default/files/publications/CSRB-Log4J-Key-Findings-and-Recommendations-Summary-508c.pdf | [P][!] | CSRB key findings summary (403s) |
| https://www.cisa.gov/resources-tools/groups/cyber-safety-review-board-csrb | [P][!] | CSRB landing page (403s) |
| https://www.csoonline.com/article/573229/cyber-safety-review-board-warns-that-log4j-event-is-an-endemic-vulnerability.html | [S] | Secondary reporting on the CSRB Log4j findings |
| https://venturebeat.com/security/csrb-log4j | [S] | Secondary reporting on the same |
| https://www.wiz.io/academy/vulnerability-management/dependency-scanning-in-cloud-security | [V] | Reachability framing: a vulnerable package that is never executed may not need immediate remediation |
| https://arxiv.org/pdf/1901.03723 | [P] | Peer-reviewed work on the quality of data generated during incident-response investigations |
| https://incident.io/blog/why-do-post-mortem-action-items-fail-how-to-make-incident-follow-ups-actually-get-done | [V] | Source of the circulating "<40% within 90 days" action-item figure — **treat the number as unsourced** |

### F3 — Ambiguity traps (week boundaries, timezones, definitions)
| URL | Type | Supports |
|---|---|---|
| https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/date_functions | [P] | BigQuery `WEEK` defaults to **Sunday**; `WEEK(<WEEKDAY>)` and a separate `ISOWEEK` part |
| https://docs.snowflake.com/en/sql-reference/functions/date_trunc | [P] | Snowflake week behaviour is controlled by the **`WEEK_START` session parameter** |
| https://docs.snowflake.com/en/sql-reference/functions-date-time | [P] | Full Snowflake date/time semantics incl. week handling |
| https://www.postgresql.org/message-id/hemtn6%24drb%241%40ger.gmane.org | [P] | PostgreSQL `date_trunc('week', …)` starts **Monday** |
| https://docs.getdbt.com/sql-reference/date-trunc | [S] | Cross-engine comparison of `DATE_TRUNC` week semantics |
| https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/modify-dashboard-settings/ | [P] | Grafana's per-dashboard `timezone` setting (`utc` / `browser` / named zone) |
| https://community.grafana.com/t/set-dashboard-to-timezone-other-than-utc-or-local-browser/9010 | [S] | Practitioner evidence of dashboards disagreeing on default timezone |
| https://github.com/grafana/mimir/issues/10745 | [P] | Mimir dashboards defaulting to UTC while others default to browser-local |
| https://sre.google/resources/practices-and-processes/incident-management-guide/ | [P] | Google's gate for when an event becomes a *managed incident* — narrower than ITIL's |

### F6 — Documented AI-agent failure modes
| URL | Type | Supports |
|---|---|---|
| https://arxiv.org/abs/2503.13657 | [P] | **MAST: 14 failure modes in 3 categories (system design, inter-agent misalignment, task verification) from 150 annotated traces** |
| https://arxiv.org/pdf/2605.12270 | [P] | 243 failed attempts across 900 trials: **strategy formulation and logic synthesis is the most error-prone stage; localization the least**; harnesses sometimes misjudge correct patches |
| https://arxiv.org/pdf/2509.16941 | [P] | SWE-Bench Pro: clustered failure modes from agent trajectories |
| https://arxiv.org/pdf/2509.13941 | [P] | An Empirical Study on Failures in Automated Issue Solving |
| https://arxiv.org/abs/2506.12286 | [P] | The SWE-Bench Illusion: instance-level verbatim-match 11.7%–31.6%; memorisation over reasoning |
| https://arxiv.org/pdf/2410.06992 | [P] | SWE-Bench+: solution leakage where the fix is in the issue text or discussion |
| https://arxiv.org/html/2507.11059v3 | [P] | SWE-MERA: **"32.67% of successful patches involve direct solution leakage and 31.08% pass due to inadequate test cases"** (quotes prior work) |
| https://software-lab.org/publications/icse2026_SWE-bench-correctness.pdf | [P][!] | "Are 'Solved Issues' in SWE-bench Really Solved Correctly?" ICSE 2026 (**PDF did not parse; cited by title/venue only**) |
| https://arxiv.org/html/2511.21654v2 | [P] | EvilGenie: a reward-hacking benchmark where agents can hardcode tests or edit test files |
| https://github.com/JonathanGabor/evilgenie_inspect | [P] | EvilGenie implementation |
| https://arxiv.org/html/2605.02964v1 | [P] | **Reward Hacking Benchmark: multi-step tool-use tasks with "naturalistic shortcut opportunities" — the closest published analogue to operational shortcuts** |
| https://www.lesswrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1 | [S] | ImpossibleBench: tasks passable only by cheating; per-model cheat rates |
| https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ | [P] | METR RCA: 16 developers, 246 tasks, **19% slower with AI while believing they were 20% faster** — check METR's own later correction |
| https://arxiv.org/abs/2507.09089 | [P] | The METR paper |
| https://www.seangoedecke.com/impact-of-ai-study/ | [S] | Independent commentary on the METR study's design |

---

## Known source gaps — stated explicitly

These were searched for and **not found**. Do not assert them.

1. **Gartner $5,600/minute downtime cost** — no primary Gartner publication obtained.
2. **Any industry-wide alert-actionability percentage** — every circulating figure
   traces to vendor content with no sample size. Use the ACM survey
   ([dl.acm.org/doi/10.1145/3723158](https://dl.acm.org/doi/10.1145/3723158)) or
   Google's per-shift ceiling instead.
3. **"PagerDuty 2025: ~50 alerts/week, only 2–5% require human intervention"** —
   appears only in third-party blogs; not locatable in any PagerDuty publication.
4. **A published "cost per bad deploy" or "cost per rollback"** — does not exist as
   a measurement. Instrument DORA's rework rate instead.
5. **Postmortem action-item completion rate** — the "<40% within 90 days" figure is
   unsourced.
6. **An inverted severity ladder (SEV5 = worst)** — actively hunted; every published
   ladder is lower-number-is-worse.
7. **"Cognitive flow state"** as a phrase in the Google on-call chapter — the
   chapter discusses intuitive-vs-rational decision modes, not flow state.
8. **A definitive ruling on whether a rollback deploy increments deployment
   frequency** — a genuine definitional gap, and therefore a legitimate ambiguity
   trap for tasks.
9. **A quantitative measure of how much of the answer is never written down** (D4)
   — only strong qualitative evidence (Reddit, GitHub, Atlassian postmortems).
10. **A Stack Overflow survey question isolating outdated documentation as a named
    frustration percentage** — the GitHub 2017 93% figure is the best available.
