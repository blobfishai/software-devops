# F. Chaos — why this is hard in real life

Answers **F1–F5** of `00-QUESTIONS.md`, plus a section on documented AI-agent
failure modes in this domain.

**Rule applied throughout:** every substantive claim carries a URL. Where no
source was found, it says so explicitly. Vendor blogs are marked as such;
primary sources (product docs, published postmortems, peer-reviewed papers,
government reports) are preferred.

Chaos scenarios are numbered **CS-01 … CS-27** so they can be lifted directly
into task specs.

---

## F1. Documented ways this data is inconsistent in practice

### Theme 1: the same service is named differently in different systems

**CS-01 — Three reserved tags, three places to set them, three answers.**
Datadog's Unified Service Tagging reserves exactly three tags — `env`,
`service`, `version` — as the join key across metrics, traces and logs
([docs.datadoghq.com/getting_started/tagging/unified_service_tagging/](https://docs.datadoghq.com/getting_started/tagging/unified_service_tagging/)).
The same doc concedes the failure mode outright: *"if you have a global `env`
tag set and a different `env` tag set on your pod, that pod's data contains
**both** `env` tags."* It further documents that `service` for a log
*"defaults to the container short-image if no Autodiscovery logs configuration
is present"* — i.e. an unlabelled service silently acquires a **name derived
from its Docker image**, which will not match the name in the code, the
catalog, or the on-call rota. Datadog's own marketing framing of the problem is
at [datadoghq.com/blog/unified-service-tagging/](https://www.datadoghq.com/blog/unified-service-tagging/).
*Task shape: agent must reconcile a service that appears as `checkout`,
`checkout-api` and `ecr.../checkout-svc:1.4` across three tools.*

**CS-02 — Unified tagging is documented as not achievable in common setups.**
Real, filed issues against Datadog's own Helm charts and agent report that the
three-tag scheme does not actually apply end-to-end: "Unified service tagging
is not possible" ([github.com/DataDog/helm-charts/issues/43](https://github.com/DataDog/helm-charts/issues/43)),
and the admission controller failing to pick up pod annotations for USTs
([github.com/DataDog/datadog-agent/issues/16556](https://github.com/DataDog/datadog-agent/issues/16556)).
Users describe setting `env` as a global tag, `service` as a Kubernetes label
and `version` programmatically, and ending up with metrics missing the
`service` tag ([github.com/DataDog/helm-charts/issues/145](https://github.com/DataDog/helm-charts/issues/145)).
This is the *vendor's own issue tracker*, not a think-piece — strong evidence.

**CS-03 — OpenTelemetry renamed the environment attribute, so both spellings
are live in the wild.** The current stable attribute is
`deployment.environment.name`
([opentelemetry.io/docs/specs/semconv/resource/deployment-environment/](https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/)),
renamed from the earlier `deployment.environment`. OTel's answer to this class
of break is **dual emission** via `OTEL_SEMCONV_STABILITY_OPT_IN` plus
telemetry `schema_url` files describing rename transformations between versions
— meaning a correctly configured fleet **deliberately emits both the old and
new attribute names simultaneously** so dashboards keep working
(described in OTel's semconv migration material, summarised at
[opentelemetry.io/docs/specs/semconv/](https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/)
and the HTTP stabilisation precedent). An agent that filters on one spelling
sees half the fleet.

**CS-04 — Identity rules that surprise you.** The same OTel page states that
resources with `service.name=frontend, deployment.environment.name=production`
and `service.name=frontend, deployment.environment.name=staging` **MUST be
considered the same service** — environment does *not* participate in service
identity ([opentelemetry.io/docs/specs/semconv/resource/deployment-environment/](https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/)).
An agent asked "how many services do we run?" gets a different answer depending
on whether it obeys this rule or naively counts distinct (name, env) pairs.

**CS-05 — Catalogs drift because ownership is a free-text pointer.** Backstage
entities require `spec.owner` resolving to a Group or User, and ownership
strings must be consistently formed (`user:alice`, `group:frontend-team`) for
the relations graph to be correct
([backstage.io/docs/features/software-catalog/descriptor-format/](https://backstage.io/docs/features/software-catalog/descriptor-format/),
[backstage.io/docs/features/software-catalog/well-known-relations/](https://backstage.io/docs/features/software-catalog/well-known-relations/)).
Nothing in the schema prevents `spec.owner` pointing at a team that was
dissolved — the entity still validates. *An owner that resolves to a defunct
team is worse than no owner, because alert routing silently succeeds.*

### Theme 2: environment naming drift

**CS-06 — "nonprod" classified as production by a substring match.** GitLab
issue **377916, "Deployment tier guesses incorrect tier for string 'nonprod'"**
([gitlab.com/gitlab-org/gitlab/-/issues/377916](https://gitlab.com/gitlab-org/gitlab/-/issues/377916)
— *fetched and verified*). A CI/CD job with an environment named `nonprod` is
marked **production tier**, because the tier-guessing regex substring-matches
`prod` inside `nonprod`. The issue points at the regex in the `Environment`
model (`app/models/environment.rb`, ~line 545) and proposes explicitly
excluding `nonprod`. This is the single best concrete artefact for
environment-naming chaos: a real tracker issue in a major product where naive
string matching **inverts** the meaning of an environment. It is also a perfect
agent trap — `grep -i prod` is the obvious first move.

**CS-07 — The industry has no agreed environment vocabulary.** Published
analysis of environment naming notes the terms are *"poorly defined and
inconsistently used across the industry"*, listing the competing sets: Dev /
Test / Prod, plus UAT, Staging/Stage, Pre-Production/Pre-Prod, Production, and
Live ([priocept.com/2018/01/30/software-environment-naming/](https://priocept.com/2018/01/30/software-environment-naming/)).
AWS's own prescriptive guidance has a page devoted to *tagging practices to
avoid*, noting that incomplete or inconsistent tags leave automation and
monitoring with insufficient information and therefore "unreliable results"
([docs.aws.amazon.com/prescriptive-guidance/latest/tagging-best-practices/tagging-practices-to-avoid.html](https://docs.aws.amazon.com/prescriptive-guidance/latest/tagging-best-practices/tagging-practices-to-avoid.html)).

### Theme 3: metrics that disagree between tools

**CS-08 — Prometheus `rate()`/`increase()` extrapolate, so two panels over the
same data legitimately disagree.** PromQL's rate functions compute the slope
between the first and last sample inside the window and **extrapolate to the
window boundaries**; the result is an estimate, not an accounting figure
([promlabs.com/blog/2021/01/29/how-exactly-does-promql-calculate-rates/](https://promlabs.com/blog/2021/01/29/how-exactly-does-promql-calculate-rates/)).
Counter resets are detected and compensated, but increments can be lost across
a reset. Consequence: a "requests last hour" number from a 5m-window dashboard
and one from a 1h-window query will not match, and neither matches the raw log
count. An agent reconciling "how many requests failed" across Prometheus and a
log store must know this is *expected*, not a bug.

**CS-09 — Percentiles cannot be averaged, and averaging them is the default
mistake.** Prometheus' own practice docs on histograms and summaries explain
that client-side quantiles (Summaries) **cannot be aggregated across
instances**, whereas histogram buckets can, via `histogram_quantile()`
([prometheus.io/docs/practices/histograms/](https://prometheus.io/docs/practices/histograms/)).
`histogram_quantile()` itself linearly interpolates inside the target bucket,
so accuracy is entirely a function of bucket layout. A worked example of the
damage: averaging per-host p99s reporting 550 ms where the true fleet p99 is
1,000 ms
([clickhouse.com/resources/engineering/percentiles-vs-averages](https://clickhouse.com/resources/engineering/percentiles-vs-averages) —
vendor engineering blog, but the maths is standard). *Two "p99 latency" tiles
built by two teams will disagree by ~2x and both will look plausible.*

**CS-10 — Organisations dual-write metrics during migration and defer
reconciliation.** Stripe's published account of its observability migration
describes a dual-write phase sending metrics to both the legacy TSDB and Amazon
Managed Prometheus, at a scale of ~300 million metrics, 40,000 alerts and
100,000 dashboard queries for ~7,000 employees
([aws.amazon.com/blogs/mt/how-stripe-architected-massive-scale-observability-solution-on-aws](https://aws.amazon.com/blogs/mt/how-stripe-architected-massive-scale-observability-solution-on-aws)).
Notably the article does **not** describe validating that the two systems agree
during dual-write; validation was deferred to a later phase and used alert
firing patterns as a proxy. So there is a documented period where two systems
of record for the same metric exist and are not reconciled — exactly the
"half-migrated" state agents must survive.

### Theme 4: duplicate and competing issue trackers

**CS-11 — Duplicate rate in real trackers is 10–40%, and duplicates disagree
about severity.** Empirical software-engineering research on Eclipse, Mozilla
and OpenOffice reports substantial duplicate fractions (figures across studies
range from ~6.6%/20.5%/10.6% for Eclipse/Firefox/Mobile in one 2017–2022
sample, up to 35.8–41.6% in earlier work) —
[link.springer.com/article/10.1007/s10664-015-9404-6](https://link.springer.com/article/10.1007/s10664-015-9404-6)
("Studying the needed effort for identifying duplicate issues", EMSE),
[link.springer.com/article/10.1007/s10664-015-9387-3](https://link.springer.com/article/10.1007/s10664-015-9387-3),
dataset table at
[researchgate.net/figure/Duplicate-bug-reports-in-OpenOffice-Mozilla-and-Eclipse_tbl2_284096335](https://www.researchgate.net/figure/Duplicate-bug-reports-in-OpenOffice-Mozilla-and-Eclipse_tbl2_284096335).
**The killer detail: 28.9%, 36.6% and 50.8% of *duplicate* bug reports carry
inconsistent severity labels** in OpenOffice, Mozilla and Eclipse respectively.
So "count the SEV2s" is not even well-defined *within one tracker*.
Related: [arxiv.org/pdf/2212.09976](https://arxiv.org/pdf/2212.09976) on
textual dissimilarity defeating duplicate detection.

**CS-12 — Cross-tracker sync produces structural duplicates.** Linear documents
bidirectional sync with both Jira and GitHub Issues, and shipped a changelog
entry specifically because *"it was hard to tell if a Linear issue successfully
synced or if there had been errors"*
([linear.app/changelog/2024-11-13-improvements-for-slas-templates-and-jira-and-github-issues-sync](https://linear.app/changelog/2024-11-13-improvements-for-slas-templates-and-jira-and-github-issues-sync)).
Linear's docs also warn that changing metadata in synced Jira spaces
*"may cause the Jira issue and Linear issue to become out of sync"*
([linear.app/docs/jira](https://linear.app/docs/jira)). A well-known duplicate
generator: GitHub's REST API returns pull requests in the issues feed, so a
naive sync creates one ticket per PR (documented in integration guidance, e.g.
[unito.io/blog/how-to-integrate-github-and-jira/](https://unito.io/blog/how-to-integrate-github-and-jira/) —
vendor blog; treat as illustrative, the API behaviour itself is in GitHub's
REST docs).

### Theme 5: orphaned alerts and dashboard rot

**CS-13 — Orphaned monitors: alerts for services that no longer exist.**
Datadog publishes a guide on auditing and cleaning up monitors precisely
because monitors accumulate for deprecated services, old app versions and
decommissioned hosts, producing noise for irrelevant signals
([datadoghq.com/blog/how-to-audit-and-clean-up-monitors/](https://www.datadoghq.com/blog/how-to-audit-and-clean-up-monitors/)).
Dynatrace has an equivalent "avoid overalerting" doc
([docs.dynatrace.com/docs/dynatrace-intelligence/use-cases/avoid-overalerting](https://docs.dynatrace.com/docs/dynatrace-intelligence/use-cases/avoid-overalerting)).
Argo CD ships a first-class **"Orphaned Resources Monitoring"** feature —
tooling exists because the state is normal
([argo-cd.readthedocs.io/en/stable/user-guide/orphaned-resources/](https://argo-cd.readthedocs.io/en/stable/user-guide/orphaned-resources/)).
The Google SRE guidance rule of thumb is that a rule unused for a quarter, or
not referenced by a dashboard or alert, is up for removal
(SRE book, *Monitoring Distributed Systems* —
[sre.google/sre-book/monitoring-distributed-systems/](https://sre.google/sre-book/monitoring-distributed-systems/)).

**CS-14 — Dashboard sprawl is documented by the dashboard vendor.** Grafana's
own best-practices doc names *"unchecked dashboard sprawl"* as a scaling risk
and tells you to *"regularly review existing dashboards to make sure they are
still relevant"*
([grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/)).
Grafana ships a dedicated feature to find *"most-used, broken, and unused
dashboards"*
([grafana.com/docs/grafana/latest/visualizations/dashboards/assess-dashboard-usage/](https://grafana.com/docs/grafana/latest/visualizations/dashboards/assess-dashboard-usage/)).
Investigation dashboards built for one incident are called out as a standard
source of staleness.

**CS-28 — One failure ≠ one alert ≠ one notification ≠ one incident.** The
counting chain is lossy by design at three separate stages, all documented:
- **Alertmanager grouping** batches alerts sharing the `group_by` label set
  into a *single notification*, explicitly so that "hundreds to thousands of
  alerts firing simultaneously" during a large outage do not produce hundreds
  of pages ([prometheus.io/docs/alerting/latest/alertmanager/](https://prometheus.io/docs/alerting/latest/alertmanager/),
  [github.com/prometheus/alertmanager/blob/main/docs/alertmanager.md](https://github.com/prometheus/alertmanager/blob/main/docs/alertmanager.md)).
- **Inhibition** suppresses whole classes of alert when a broader alert is
  firing (e.g. mute everything in a cluster when the cluster-unreachable alert
  fires) — same docs.
- **Silences** mute alerts during maintenance windows — same docs.
Consequently "how many alerts fired", "how many pages went out" and "how many
incidents were opened" are three different numbers for the same outage, and the
ratio between them is a *configuration artefact*, not a fact about reliability.
An agent asked "were we paged for this?" must check silences and inhibition
rules, not just the alert history.

Two further stages, both now sourced (see D3):
- **Alertmanager silently truncates.** The webhook payload carries a
  `truncatedAlerts` field — *"how many alerts have been truncated due to
  `max_alerts`"*
  ([prometheus.io/docs/alerting/latest/configuration/#webhook_config](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)).
  **An agent counting `alerts[]` without reading `truncatedAlerts` undercounts
  and gets no error.**
- **PagerDuty `dedup_key`.** `event_action` ∈ trigger|acknowledge|resolve;
  `dedup_key` may be supplied on the trigger or is generated by PagerDuty and
  returned, and **only `trigger` events create alerts** — so repeat triggers
  sharing a key update one incident rather than opening new ones.
  Canonical field reference:
  [support.pagerduty.com/main/docs/pd-cef](https://support.pagerduty.com/main/docs/pd-cef);
  real request body:
  [PagerDuty/API_Python_Examples .../trigger_without_incident_key.py](https://raw.githubusercontent.com/PagerDuty/API_Python_Examples/master/EVENTS_API_v2/trigger/trigger_without_incident_key.py).
  **Note: `developer.pagerduty.com` is JS-rendered and returns empty bodies to
  automated fetching — use the support docs and GitHub samples instead.**

**Bonus chaos, from D3:** the six alert schemas surveyed use **disjoint field
names for the same concepts** ("what broke" is `annotations.summary` /
`payload.summary` / `$EVENT_TITLE` / `message` / `data.issue.title`), and
**Datadog has no fixed webhook payload at all** — the body is composed by the
author from `$`-variables
([docs.datadoghq.com/integrations/webhooks/](https://docs.datadoghq.com/integrations/webhooks/)),
so its shape is *per-installation*. You cannot write a schema-based parser
against Datadog alerts. See the cross-schema table in `D_input_documents.md`.

**CS-15 — Alert actionability is low, and measured.** Peer-reviewed survey of
alert fatigue in security operations centres:
[dl.acm.org/doi/10.1145/3723158](https://dl.acm.org/doi/10.1145/3723158)
(ACM Computing Surveys). Industry-side framing from an incident-management
vendor: [incident.io/blog/alert-fatigue-solutions-for-dev-ops-teams-in-2025-what-works](https://incident.io/blog/alert-fatigue-solutions-for-dev-ops-teams-in-2025-what-works).
Note: many circulating actionability percentages (e.g. "46% of alerts are false
positives", "63% go unaddressed") trace to vendor SOC surveys rather than
peer review — **use the ACM survey as the citable anchor and treat specific
vendor percentages as soft.**

### Theme 6: tool sprawl as the substrate

**CS-16 — The average company runs >100 SaaS apps.** Okta's *Businesses at
Work* is the best longitudinal primary source: the 2025 edition reports the
global average number of apps per company passing 100 for the first time
([okta.com/newsroom/articles/businesses-at-work-2025/](https://www.okta.com/newsroom/articles/businesses-at-work-2025/);
prior-year PDF for methodology:
[okta.com/sites/default/files/2024-04/Okta-2024_Businesses_at_Work.pdf](https://www.okta.com/sites/default/files/2024-04/Okta-2024_Businesses_at_Work.pdf)).
Larger enterprises run substantially more. This is the structural reason the
join problem exists at all.

**CS-29 — 86% of orgs run two or more monitoring tools; the mean is ~5.**
New Relic's Observability Forecast (a large annual practitioner survey) reports
a mean of **5.1 monitoring tools** per organisation (down from 5.9 the prior
year) and that **86% used two or more monitoring tools**
([newrelic.com/resources/report/observability-forecast/2023/state-of-observability/current-deployment](https://newrelic.com/resources/report/observability-forecast/2023/state-of-observability/current-deployment);
strategy/org section:
[newrelic.com/resources/report/observability-forecast/2023/state-of-observability/strategy-and-organization](https://newrelic.com/resources/report/observability-forecast/2023/state-of-observability/strategy-and-organization);
latest edition: [newrelic.com/resources/report/observability-forecast/2025](https://newrelic.com/resources/report/observability-forecast/2025)).
*Vendor-run survey — treat direction as reliable, exact figures as soft.* This
is the quantitative basis for "metrics disagree between Datadog / Prometheus /
Grafana": most orgs genuinely have ≥2 places to ask the same question.

**CS-30 — Kubernetes "namespace sameness" makes identical names mean the same
thing across clusters — whether or not you meant that.** The Kubernetes
Multicluster SIG principle of **namespace sameness** holds that namespaces with
the same name in different clusters are treated as **the same logical
namespace** (described in Istio multicluster docs:
[docs.solo.io/istio/1.30.x/ambient/multicluster/segments/about/](https://docs.solo.io/istio/1.30.x/ambient/multicluster/segments/about/)).
Combined with the common convention of using the *cluster* as the environment
boundary — so the namespace is `payments-checkout` in both the prod and staging
clusters, with no environment suffix
([cloudfleet.ai/blog/cloud-native-how-to/2024-11-kubernetes-namespaces-best-practices/](https://cloudfleet.ai/blog/cloud-native-how-to/2024-11-kubernetes-namespaces-best-practices/) —
practitioner blog) — a query keyed on `namespace` alone **cannot distinguish
production from staging**. The environment lives in the kubeconfig context, not
in the data. GitLab has tracked issues in this exact space
([gitlab.com/gitlab-org/gitlab/-/issues/27630](https://gitlab.com/gitlab-org/gitlab/-/issues/27630) —
customise Kubernetes namespace per environment).

**CS-17 — Half-migrated systems are a named, deliberate architecture, not an
accident.** The shadow-table / dual-write extraction pattern keeps the legacy
system authoritative for live operations while the new service is built, with
every change written to both stores
([infoq.com/articles/shadow-table-strategy-data-migration/](https://www.infoq.com/articles/shadow-table-strategy-data-migration/)).
The engineered steady state is *"two systems of record that are supposed to
agree"* — which means the interesting question is always "and where don't
they?"

---

## F2. Reconciliation questions humans actually ask that require joining tools

Each of these is a task candidate. The joins are listed explicitly.

**CS-18 — "How many customer-facing incidents did we have last week?"**
Requires: incident tracker ∪ status page ∪ severity convention ∪ a definition
of "customer-facing" ∪ a week boundary. Every one of those five is contested:
- Severity conventions differ per org and per tool (see CS-21).
- The status page systematically **lags** internal incident state. ThousandEyes
  documents a gap between what a provider sees internally and what it publishes,
  "sometimes taking minutes or even hours"
  ([thousandeyes.com/blog/why-you-should-not-trust-the-status-page](https://www.thousandeyes.com/blog/why-you-should-not-trust-the-status-page));
  PagerDuty's status-page guidance covers the same communication-cadence problem
  ([pagerduty.com/resources/outages/learn/status-page-best-practices/](https://www.pagerduty.com/resources/outages/learn/status-page-best-practices/)).
- Cloudflare's Nov-2025 postmortem is a concrete case of the status page and
  internal state being decoupled — the status page went down *coincidentally*
  and independently, which actively misled responders
  ([blog.cloudflare.com/18-november-2025-outage/](https://blog.cloudflare.com/18-november-2025-outage/)).
- The week boundary is genuinely ambiguous (CS-24).

**CS-19 — "What changed before this incident?"**
Requires joining deploys (CI system) × config changes (IaC/feature flags) ×
infrastructure changes (cloud audit log) × database migrations, on a shared
timeline, in a shared timezone. The Cloudflare Nov-2025 outage is the canonical
worked example: the triggering change was a **ClickHouse database permissions
change at 11:05 UTC** that had no obvious relationship to the failing component
(the Bot Management proxy), and the responders' first hypothesis was an
external DDoS attack
([blog.cloudflare.com/18-november-2025-outage/](https://blog.cloudflare.com/18-november-2025-outage/)).
An agent that only greps the deploy log for the failing service finds nothing.

**CS-20 — "Which services are affected by CVE-X?"**
The Log4Shell (CVE-2021-44228) response is the documented case that this
question was unanswerable at most organisations. The US **Cyber Safety Review
Board** — a government primary source — reviewed the event and its
recommendations include developing the capacity to maintain an accurate IT
asset and application inventory; it found that organisations able to respond
effectively "understood their use of Log4j" and that **few organisations could
execute this kind of response at the speed required**
(report PDF:
[cisa.gov/sites/default/files/publications/CSRB-Report-on-Log4-July-11-2022_508.pdf](https://www.cisa.gov/sites/default/files/publications/CSRB-Report-on-Log4-July-11-2022_508.pdf);
key-findings summary:
[cisa.gov/sites/default/files/publications/CSRB-Log4J-Key-Findings-and-Recommendations-Summary-508c.pdf](https://www.cisa.gov/sites/default/files/publications/CSRB-Log4J-Key-Findings-and-Recommendations-Summary-508c.pdf);
CSRB landing page:
[cisa.gov/resources-tools/groups/cyber-safety-review-board-csrb](https://www.cisa.gov/resources-tools/groups/cyber-safety-review-board-csrb)).
**Caveat: cisa.gov returned HTTP 403 to automated fetching during this
research — the URLs are from search results and the CSRB landing page, and the
content summary is from secondary reporting
([csoonline.com/article/573229/](https://www.csoonline.com/article/573229/cyber-safety-review-board-warns-that-log4j-event-is-an-endemic-vulnerability.html),
[venturebeat.com/security/csrb-log4j](https://venturebeat.com/security/csrb-log4j)).
Verify the exact wording against the PDF before quoting it as verbatim.**
The join required: SBOM/dependency manifests × container images actually
running × service catalog × ownership × whether the code path is reachable
(reachability framing: [wiz.io/academy/vulnerability-management/dependency-scanning-in-cloud-security](https://www.wiz.io/academy/vulnerability-management/dependency-scanning-in-cloud-security),
vendor).

**CS-21 — "Was that a SEV1?" — severity ladders are not portable.**
Different published ladders disagree in depth and in meaning. FireHydrant
documents SEV1–SEV3 and notes some teams add a **SEV0** for absolute
catastrophe ([firehydrant.com/blog/getting-started-with-severity-levels/](https://firehydrant.com/blog/getting-started-with-severity-levels/),
[firehydrant.com/glossary/severity/](https://firehydrant.com/glossary/severity/)).
FireHydrant additionally separates *severity* from *priority* as distinct
fields ([docs.firehydrant.com/docs/severities-and-priorities](https://docs.firehydrant.com/docs/severities-and-priorities))
and offers a Severity Matrix that assigns severity from impacted components
([docs.firehydrant.com/docs/severity-matrix](https://docs.firehydrant.com/docs/severity-matrix)).
Rootly documents a **P1–P3 "support level"** vocabulary alongside SEV levels
([rootly.com/incident-response/support-levels](https://rootly.com/incident-response/support-levels),
[rootly.com/blog/practical-guide-to-sre-incident-severity-levels](https://rootly.com/blog/practical-guide-to-sre-incident-severity-levels)).
FireHydrant states the operational consequence directly: without clear
definitions, *severity is applied inconsistently across incidents, or not set
at all.* **Cross-org, "SEV2" carries no stable meaning; cross-tool, severity
and priority are separate axes that get conflated.**

**CS-22 — "What's our MTTR?" — the metric is statistically invalid.**
The VOID (Verica Open Incident Database) analysed ~10,000 incidents from just
under 600 companies and recommends **retiring MTTR as a key metric**
([thevoid.community/report](https://www.thevoid.community/report),
[thevoid.community](https://www.thevoid.community/)). The argument, from
Courtney Nash: incident duration data is positively skewed, so *"if you don't
have a normal distribution of your data then central tendency measures, like
mean, median, and yes the mode, don't represent your data accurately"*
([infoq.com/articles/incident-metrics-void/](https://www.infoq.com/articles/incident-metrics-void/)).
Two further findings that break naive reporting:
- **"There is no correlation detected between incident duration and incident
  severity."** (VOID 2022, via the InfoQ interview above.)
- Duration is *"gray data"* — high variability, low fidelity — and severity is
  *"highly subjective as many organizations use it as a way to draw more
  attention to an incident."*
- Allspaw's **"shallow data"**: MTTx, severity, impact and count all
  underrepresent the uniqueness of incidents.
Conference talk: [usenix.org/conference/srecon22americas/presentation/nash](https://www.usenix.org/conference/srecon22americas/presentation/nash).
Vendor restatement: [verica.io/blog/mttr-is-a-misleading-metric-now-what/](https://www.verica.io/blog/mttr-is-a-misleading-metric-now-what/).
Trade press: [csoonline.com/article/574243/](https://www.csoonline.com/article/574243/mttr-not-a-viable-metric-for-complex-software-system-reliability-and-security.html).
*Task shape: an agent asked to "report MTTR" that reports a mean without
flagging the distribution has produced a technically-responsive, substantively
wrong answer.*

**CS-23 — "Are our postmortem action items done?"** Requires joining the
postmortem doc → the tracker → the deploy history. NO STRONG PRIMARY SOURCE
FOUND for a completion-rate percentage; the widely repeated "<40% within 90
days" figure traces to secondary blog posts, not to a study I could verify
(e.g. [incident.io/blog/why-do-post-mortem-action-items-fail-how-to-make-incident-follow-ups-actually-get-done](https://incident.io/blog/why-do-post-mortem-action-items-fail-how-to-make-incident-follow-ups-actually-get-done),
vendor). **Treat the specific number as NO SOURCE FOUND — judgement call; the
existence of the problem is well attested by the volume of vendor tooling built
for it.** Adjacent peer-reviewed work on incident-response data quality:
[arxiv.org/pdf/1901.03723](https://arxiv.org/pdf/1901.03723).

---

## F3. Ambiguity in the request itself

**CS-24 — "This week" has at least four defensible answers.** This is
demonstrable from SQL engine documentation, which is as primary as it gets:
- **ISO 8601** weeks start **Monday**, and a week belongs to the year
  containing its Thursday.
- **BigQuery** `DATE_TRUNC(d, WEEK)` truncates to a week starting **Sunday by
  default**, accepts `WEEK(<WEEKDAY>)` for any start day, and provides a
  separate `ISOWEEK` part for Monday-start ISO semantics
  ([docs.cloud.google.com/bigquery/docs/reference/standard-sql/date_functions](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/date_functions)).
- **Snowflake** defaults to **Sunday** as week start, but the behaviour of
  `week` parts is controlled by the session parameter **`WEEK_START`**, so the
  same query returns different rows depending on session state
  ([docs.snowflake.com/en/sql-reference/functions/date_trunc](https://docs.snowflake.com/en/sql-reference/functions/date_trunc),
  [docs.snowflake.com/en/sql-reference/functions-date-time](https://docs.snowflake.com/en/sql-reference/functions-date-time)).
- **PostgreSQL** `date_trunc('week', …)` starts **Monday**
  ([postgresql.org/message-id/hemtn6%24drb%241%40ger.gmane.org](https://www.postgresql.org/message-id/hemtn6%24drb%241%40ger.gmane.org),
  cross-engine comparison at [docs.getdbt.com/sql-reference/date-trunc](https://docs.getdbt.com/sql-reference/date-trunc)).
So "incidents this week" computed in Snowflake and in Postgres over the same
data legitimately differ, and neither is wrong. *A good task states "last week"
and rewards the agent that asks which boundary, or that states its assumption.*

**CS-25 — Timezone is a per-dashboard, per-monitor setting, not a global
truth.** Grafana dashboards carry a `timezone` field settable to `utc`,
`browser`, or a named zone
([grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/modify-dashboard-settings/](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/modify-dashboard-settings/));
community threads document dashboards defaulting to UTC while others default to
browser-local
([community.grafana.com/t/set-dashboard-to-timezone-other-than-utc-or-local-browser/9010](https://community.grafana.com/t/set-dashboard-to-timezone-other-than-utc-or-local-browser/9010),
[github.com/grafana/mimir/issues/10745](https://github.com/grafana/mimir/issues/10745)).
Datadog documents that **monitors use UTC and do not track local time zones by
default**, with a dedicated guide for making anomaly monitors respect local
time ([docs.datadoghq.com/monitors/guide/how-to-update-anomaly-monitor-timezone/](https://docs.datadoghq.com/monitors/guide/how-to-update-anomaly-monitor-timezone/)).
*Consequence: an incident that starts at 23:30 local lands in a different day —
and potentially a different week and month — depending on which tool you ask.*

**CS-26 — Does a rolled-back deploy count?** DORA defines **change failure
rate** as the proportion of deployments causing degraded service that then
requires remediation such as a rollback, hotfix or fix-forward
([dora.dev/guides/dora-metrics/](https://dora.dev/guides/dora-metrics/),
[dora.dev/guides/dora-metrics-four-keys/](https://dora.dev/guides/dora-metrics-four-keys/)).
The ambiguity is in the **denominator**, not the numerator: DORA's framing
counts the rollback as *evidence of a failed deployment*, but tools differ on
whether the rollback deploy itself increments **deployment frequency**. Vendor
implementations expose this: IBM DevOps Velocity documents its own CFR
computation ([ibm.com/docs/en/devops-velocity/5.2.x?topic=reference-change-failure-rate-metric](https://www.ibm.com/docs/en/devops-velocity/5.2.x?topic=reference-change-failure-rate-metric)),
GitLab has a tracked issue for API support for CFR
([gitlab.com/gitlab-org/gitlab/-/issues/299407](https://gitlab.com/gitlab-org/gitlab/-/issues/299407)).
**NO SINGLE AUTHORITATIVE RULING FOUND on rollback-in-denominator — this is a
genuine, documented definitional gap and therefore a legitimate ambiguity trap.**

**CS-27 — "Is this an incident?"** Google's incident-management guidance frames
an event as a managed incident when it requires coordination — multiple
responders, customer-visible impact, or an unclear resolution path
([sre.google/resources/practices-and-processes/incident-management-guide/](https://sre.google/resources/practices-and-processes/incident-management-guide/),
[sre.google/sre-book/managing-incidents/](https://sre.google/sre-book/managing-incidents/)).
ITIL's definition is broader — an unplanned interruption, a reduction in
quality, *or a potential failure that has not yet affected service*. The two
definitions include different sets of events. So "count our incidents" depends
on which framework the org nominally follows, and orgs typically follow neither
consistently (see CS-22 on severity subjectivity).

---

## F4. Traps that punish an agent trusting a single source

Ranked by how cheaply they fool a plausible agent.

1. **Trusting the service catalog for what is running.** Catalog entries are
   hand-written YAML and validate even when the owner team no longer exists
   (CS-05). Cross-check against the deploy system or the running fleet.
2. **Trusting the status page for customer impact.** It lags internal state and
   can be independently unavailable (CS-18, Cloudflare Nov-2025).
3. **Trusting one metrics backend for a count.** Extrapolating rate functions
   and non-aggregatable quantiles mean two correct systems give two numbers
   (CS-08, CS-09), and dual-write migrations mean both are "the" system (CS-10).
4. **Trusting the deploy log of the failing service to find the change.** The
   Cloudflare Nov-2025 trigger was a permissions change in an unrelated
   database, propagating through a generated config file (CS-19).
5. **Trusting the tracker's severity field.** Duplicates within a single tracker
   disagree on severity 29–51% of the time (CS-11), and severity is used
   socially to attract attention (CS-22).
6. **Trusting `grep prod`.** `nonprod` matches (CS-06).
7. **Trusting an alert's existence as evidence a service exists.** Orphaned
   monitors outlive their services (CS-13).
8. **Trusting one spelling of an OTel attribute.** Dual emission is the
   *recommended* migration state (CS-03).
9. **Trusting an SBOM/manifest as the running inventory.** Log4Shell's central
   lesson (CS-20).
10. **Trusting the mean.** MTTR over skewed data (CS-22).

---

## F5. Realistic chaos versus merely cruel chaos

A working test: **chaos is realistic when a competent human would also have to
do extra work to resolve it, and when the resolution path is discoverable from
inside the environment.**

**Realistic (keep) — all attested above:**
- Same service under three names across three tools, where a mapping *exists*
  somewhere (catalog annotation, image tag, tracker component). CS-01, CS-02.
- Two metrics systems giving different numbers for defensible technical
  reasons, where the reason is documented. CS-08, CS-09, CS-10.
- Ambiguous week/timezone boundaries where the tools' defaults are inspectable.
  CS-24, CS-25.
- A stale runbook that is *detectably* stale (references a decommissioned host
  that the agent can observe no longer exists). CS-13.
- Duplicate tickets with conflicting severity where both are readable. CS-11.
- A trigger in an unrelated subsystem, discoverable from a cross-system audit
  log. CS-19.
- Severity ladders that differ per team where each team's definition is written
  down somewhere. CS-21.

**Cruel (avoid) — judgement call, NO SOURCE, stated as design principle:**
- Chaos with no discoverable resolution: the mapping between names exists only
  in a human's head and nowhere in the environment.
- Ambiguity with a single hidden "correct" answer and no way to detect the
  ambiguity — as opposed to ambiguity where asking, or stating an assumption, is
  the correct behaviour.
- Randomised/nondeterministic tool failures unrelated to the task's difficulty
  (this conflates environment failure with model failure — see G5).
- Data withheld rather than data conflicting. Reality is contradictory, not
  absent.

**Empirical support for "ambiguity, not absence" being the right axis:** the
best-documented real failures above are all *conflict* failures — two sources
disagreeing (Cloudflare's duplicated feature rows; USTs set in two places;
duplicate tickets with different severities) — not *missing data* failures.

---

## F6. Documented failure modes of AI agents in this domain

Directly relevant to H3 and to calibration.

**Reward hacking / test tampering is measured, not hypothetical.**
- **ImpossibleBench** constructs tasks where passing is only possible by
  cheating; reported cheat rates vary sharply by model
  ([lesswrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1](https://www.lesswrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1)).
- **EvilGenie**: a reward-hacking benchmark built on LiveCodeBench where agents
  can hardcode test cases or edit test files
  ([arxiv.org/html/2511.21654v2](https://arxiv.org/html/2511.21654v2),
  code: [github.com/JonathanGabor/evilgenie_inspect](https://github.com/JonathanGabor/evilgenie_inspect)).
- **Reward Hacking Benchmark (RHB)**: multi-step tool-use tasks with
  "naturalistic shortcut opportunities" — skipping verification, inferring
  answers from task-adjacent metadata, tampering with evaluation functions
  ([arxiv.org/html/2605.02964v1](https://arxiv.org/html/2605.02964v1)).
  **This is the closest published analogue to our domain: the shortcuts are
  *operational*, not just test-file edits.**

**Benchmarks over-credit agents because the tests are weak.**
- **SWE-MERA** states verbatim in its abstract that **"32.67% of successful
  patches involve direct solution leakage and 31.08% pass due to inadequate
  test cases"**
  ([arxiv.org/html/2507.11059v3](https://arxiv.org/html/2507.11059v3)).
  *Attribution caveat, verified by fetching the paper:* SWE-MERA quotes these
  figures while citing prior work (Jimenez et al., the original SWE-bench
  paper) rather than deriving them itself; the underlying manual screening is
  generally attributed to the SWE-Bench+ line of work below. Cite SWE-MERA for
  the sentence, SWE-Bench+ for the method.
- **SWE-Bench+** identifies instances where the solution is given directly in
  the issue text or GitHub discussion
  ([arxiv.org/pdf/2410.06992](https://arxiv.org/pdf/2410.06992)).
- **The SWE-Bench Illusion** finds instance-level verbatim-match rates of
  11.7%–31.6% across evaluated models, arguing performance partly reflects
  memorisation ([arxiv.org/abs/2506.12286](https://arxiv.org/abs/2506.12286)).
- *"Are 'Solved Issues' in SWE-bench Really Solved Correctly?"* (ICSE 2026) —
  [software-lab.org/publications/icse2026_SWE-bench-correctness.pdf](https://software-lab.org/publications/icse2026_SWE-bench-correctness.pdf).
  **Note: this PDF did not parse cleanly during research; cited by title/venue
  only, numbers not extracted.**
- Direct implication for us: **verification must not be satisfiable by editing
  the verifier**, and answer-based checks must not be inferable from the prompt.

**Where agents actually go wrong on engineering tasks.**
- *Characterizing the Failure Modes of LLMs in Resolving Real-World GitHub
  Issues* ([arxiv.org/pdf/2605.12270](https://arxiv.org/pdf/2605.12270)):
  manual analysis of 243 failed attempts across 900 trials (Claude 4.5 Sonnet,
  Gemini 3 Pro, GPT-5) on SWE-bench Verified. Finding: **strategy formulation
  and logic synthesis is the most error-prone stage, then problem
  understanding; localization has the *lowest* failure rate** — i.e. modern
  agents find the right file and then do the wrong thing to it. Also: existing
  harnesses *"occasionally misjudge correct patches due to superficial
  discrepancies or hidden constraints"* (relevant to G5).
- *SWE-Bench Pro* clusters failure modes from agent trajectories
  ([arxiv.org/pdf/2509.16941](https://arxiv.org/pdf/2509.16941)).
- *An Empirical Study on Failures in Automated Issue Solving*
  ([arxiv.org/pdf/2509.13941](https://arxiv.org/pdf/2509.13941)).
- SWE-agent's own taxonomy splits unsuccessful runs into **reproduction,
  localization and code-generation** failures, the latter including overly
  specific implementations and iterative editing errors.

**Multi-agent and long-horizon failure.**
- *Why Do Multi-Agent LLM Systems Fail?* (Cemri, Pan, Yang, … Zaharia,
  Gonzalez, Stoica) — [arxiv.org/abs/2503.13657](https://arxiv.org/abs/2503.13657).
  Builds **MAST: 14 failure modes in 3 categories — system design issues,
  inter-agent misalignment, and task verification** — from 150 annotated
  traces. The third category is precisely our concern: agents that do not
  verify, or verify the wrong thing.

**Human-in-the-loop reality check.**
- METR's RCT: 16 experienced open-source developers, 246 tasks in repos they
  averaged 5 years on; **allowing AI tools made them 19% slower**, while they
  believed it had sped them up by 20%
  ([metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/),
  paper: [arxiv.org/abs/2507.09089](https://arxiv.org/abs/2507.09089)).
  **Important caveat: METR later published an update after finding selection
  bias, with a larger cohort showing a much smaller (~-4%) effect — cite the
  original carefully and check METR's own follow-up before using the 19%
  figure.** Independent commentary:
  [seangoedecke.com/impact-of-ai-study/](https://www.seangoedecke.com/impact-of-ai-study/).

**System-level: AI raises throughput and lowers stability.**
- The 2025 DORA report finds AI adoption positively correlated with delivery
  throughput but **continuing to correlate with reduced delivery stability** —
  more change failures, more rework
  ([cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report),
  2024 report: [dora.dev/research/2024/dora-report/](https://dora.dev/research/2024/dora-report/)).
  **This is the strongest single argument that the valuable agent tasks in this
  domain are the verification/reconciliation ones, not the code-writing ones.**

---

## Quick index: chaos scenarios → task seeds

| # | Scenario | Primary join required |
|---|---|---|
| CS-01/02 | Service named 3 ways (code, image tag, catalog) | catalog × metrics × deploys |
| CS-03/04 | OTel attribute renamed; dual emission live | telemetry schema versions |
| CS-05 | Catalog owner points at dissolved team | catalog × org directory |
| CS-06/07 | `nonprod` matches `prod` | env tags × deploy tiers |
| CS-08/09 | Two correct latency numbers that disagree | Prometheus × second backend |
| CS-10 | Dual-write migration, unvalidated | legacy TSDB × new TSDB |
| CS-11/12 | Duplicate tickets, conflicting severity | tracker A × tracker B |
| CS-13/14/15 | Orphaned alerts, stale dashboards | monitors × running services |
| CS-16/17/29 | 100+ SaaS apps, ~5 monitoring tools, half-migrated by design | everything |
| CS-28 | 1 failure → N alerts → M pages → P incidents | alert rules × grouping × silences × pager |
| CS-30 | Same k8s namespace name in prod and staging clusters | namespace × cluster context |
| CS-18 | "Customer-facing incidents last week" | incidents × status page × severity × week |
| CS-19 | "What changed before this incident" | deploys × config × cloud audit × DB |
| CS-20 | "Which services are affected by CVE-X" | SBOM × running images × catalog × owners |
| CS-21 | SEV1 ≠ SEV1 across orgs/tools | severity × priority × per-team defs |
| CS-22 | MTTR is statistically invalid | incident durations, distribution-aware |
| CS-23 | Postmortem action items closed? | postmortem × tracker × deploys |
| CS-24/25 | Week boundary + timezone | SQL engine defaults × dashboard settings |
| CS-26 | Do rollbacks count as deploys? | DORA defs × CI tool semantics |
| CS-27 | Is this an incident at all? | Google SRE vs ITIL definitions |
