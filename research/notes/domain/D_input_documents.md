# D. Input documents and context

Answers **D1–D4** of `00-QUESTIONS.md` (plus a dedicated D5 on documentation
staleness, which the brief called out as a first-class hazard).

> **Three corrections to assumptions in the research brief:**
> 1. The famous **"3x MTTR improvement from playbooks"** claim is in the SRE
>    book's **Introduction** chapter (Emergency Response), **not** in
>    `being-on-call`. `being-on-call` was fetched twice and contains no MTTR
>    multiplier.
> 2. **Roblox's postmortem has moved twice.** `blog.roblox.com/2022/01/…` →
>    `corp.roblox.com/newsroom/…` → `about.roblox.com/newsroom/2022/01/…`.
>    Only the last resolves.
> 3. **`developer.pagerduty.com` cannot be fetched** by URL-to-markdown tooling
>    (every path returns an empty body — JS-rendered). Use
>    `support.pagerduty.com/main/docs/pd-cef` and PagerDuty's own GitHub
>    examples instead.

---

## D1. Real public postmortems

Thirteen fetched and verified. Each entry: title / URL / date / 3-sentence
failure mechanism.

### 1. Details of the Cloudflare outage on July 2, 2019
**URL:** https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/
**Date:** Published 12 Jul 2019; incident 2 Jul 2019, 13:42–14:09 UTC

A new WAF managed rule for XSS detection contained the sub-pattern
`.*(?:.*=.*)`, which in Cloudflare's PCRE-backed Lua WAF caused catastrophic
backtracking — a "match anything followed by anything" construct whose matching
cost exploded exponentially (555 steps for `x=xxxxxxxxxxxxxxxxxxxx`). The rule
was merged at 13:31, built at 13:37, and pushed globally via Quicksilver at
13:42 (p99 propagation 2.29s), pinning CPU to 100% on every machine worldwide;
crucially this *"non-emergency rule change [went] globally into production
without a staged rollout"*, bypassing the normal DOG→PIG→Canary→Global
progression, and a CPU-protection mechanism had previously been removed during a
refactor. At 14:02 the WAF was identified, at 14:07 a pre-built "global kill" was
activated, and CPU normalised by 14:09.

### 2. Cloudflare outage on November 18, 2025
**URL:** https://blog.cloudflare.com/18-november-2025-outage/
**Date:** 18 Nov 2025 (author: Matthew Prince, CEO)

A ClickHouse permissions change at 11:05 UTC made access to underlying `r0`
tables explicit, so the Bot Management feature-file query —
`SELECT name, type FROM system.columns WHERE table = 'http_requests_features'`,
which lacked a database filter — began returning duplicate columns from both
`default` and `r0`, roughly doubling the file's feature count. The Rust FL2 proxy
has a hard limit of **200** ML features with preallocated memory; the oversized
file blew that limit and produced
`thread fl2_worker_thread panicked: called Result::unwrap() on an Err value`,
returning HTTP 5xx across core traffic. Because the ClickHouse change rolled out
gradually, *"every five minutes there was a chance of either a good or a bad set
of configuration files being generated"*, so the flapping initially looked like a
DDoS; bad-file generation was halted at 14:24 and full restoration came at 17:06.
**→ This is the richest single artefact in the corpus. See F/CS-19 and F/CS-18.**

### 3. Postmortem of database outage of January 31 (GitLab)
**URL:** https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/
**Date:** Published 10 Feb 2017; incident 31 Jan 2017

Spam load plus an automated process removing a flagged employee account
overwhelmed the primary Postgres, replication fell behind because *"WAL segments
needed by the secondary were already removed from the primary"*, and during
resynchronisation an engineer ran the removal against the **primary** instead of
the secondary — terminating *"a second or two after noticing their mistake, but
at this point around 300 GB of data had already been removed."* Five recovery
paths then failed in sequence: pg_dump produced nothing because the backup host
ran PostgreSQL 9.2 against a 9.6 production DB; the failure emails were rejected
by DMARC so *"there was no indication of failure"*; replication had collapsed;
the secondary had been wiped; and Azure disk snapshots were never enabled for DB
servers. Recovery used an LVM snapshot from 6 hours earlier, copying 300 GB over
~18 hours, with permanent loss of *"at least 5000 projects, 5000 comments, and
roughly 700 users."*

### 4. Summary of the Amazon S3 Service Disruption (US-EAST-1)
**URL:** https://aws.amazon.com/message/41926/
**Date:** 28 Feb 2017, onset 9:37 AM PST

An S3 team member ran an established playbook command *"intended to remove a
small number of servers"* for a billing-system debug, but *"one of the inputs to
the command was entered incorrectly and a larger set of servers was removed than
intended."* The removed capacity included the **index subsystem** (object
metadata and location) and the **placement subsystem** (which itself depends on
index), forcing a full restart of both. Restart was slow because *"S3 has
experienced massive growth... the process of restarting these services and
running the necessary safety checks to validate the integrity of the metadata
took longer than expected"* — these subsystems *"had not [been] completely
restarted in our larger regions for many years."*

### 5. Summary of the Amazon Kinesis Event (US-EAST-1)
**URL:** https://aws.amazon.com/message/11201/
**Date:** 25 Nov 2020

*"A relatively small addition of capacity that began to be added to the service
at 2:44 AM PST, finishing at 3:47 AM PST"* pushed the Kinesis front-end fleet
over an OS thread limit: each front-end server *"creates operating system threads
for each of the other servers in the front-end fleet"* to build its shard-map
cache, so the new members caused **all** servers to exceed the OS maximum. With
cache construction failing, *"front-end servers were ending up with useless
shard-maps that left them unable to route requests."* Recovery required restarting
a many-thousand-server fleet at *"a few hundred per hour"*, with cascades into
Cognito, CloudWatch, Lambda, ECS/EKS and AutoScaling; full recovery at 10:23 PM
PST — roughly 20 hours.

### 6. Summary of the AWS Service Event (US-EAST-1)
**URL:** https://aws.amazon.com/message/12721/
**Date:** Published 10 Dec 2021; incident 7 Dec 2021

An automated capacity-scaling action on the *main* AWS network *"triggered an
unexpected behavior from a large number of clients inside the internal network"*,
and the connection surge *"overwhelmed the networking devices between the internal
network and the main AWS network"*, with retries sustaining a congestion feedback
loop. Critically, the congestion *"immediately impacted the availability of
real-time monitoring data for our internal operations teams, which impaired their
ability to find the source of congestion and resolve it"* — operators fell back
to logs and initially misread elevated internal DNS errors as the cause. The
Service Health Dashboard also failed to fail over, delaying external comms to
8:22 AM PST; all networking devices recovered by 2:22 PM PST.
**→ Best documented case of "the observability system is inside the blast
radius." Also a status-page failure (F/CS-18).**

### 7. Summary of the Amazon DynamoDB Service Disruption (US-EAST-1)
**URL:** https://aws.amazon.com/message/101925/
**Date:** 19–20 Oct 2025

*"The root cause of this issue was a latent race condition in the DynamoDB DNS
management system that resulted in an incorrect empty DNS record for the
service's regional endpoint"*: a **DNS Planner** builds plans from load-balancer
health and redundant **DNS Enactors** across three AZs apply them via Route53;
one Enactor stalled applying an older plan while a second completed a newer one
and ran cleanup, the staleness check failed to block the older plan overwriting
the newer, and cleanup then deleted it — removing all IPs. DNS was restored at
2:25 AM and caches drained by 2:40 AM, but two cascades followed: EC2's
DropletWorkflow Manager entered *"a state of congestive collapse and was unable to
make forward progress"* until throttled at 4:14 AM, and NLB health checks failed
against newly launched instances until automatic failover was disabled at 9:36
AM. AWS disabled the DNS Planner/Enactor automation worldwide pending a fix and
added an NLB "velocity control mechanism."

### 8. Slack's Outage on January 4th 2021
**URL:** https://slack.engineering/slacks-outage-on-january-4th-2021/
**Date:** Published 1 Feb 2021; incident 4 Jan 2021 (author: Laura Nolan)

On the first Monday after the holidays *"client caches are cold and clients pull
down more data than usual"*, and one of Slack's AWS Transit Gateways saturated
because TGW autoscaling did not keep up with the step change, producing
widespread packet loss. Slack's web tier autoscales on CPU utilisation, so packet
loss **inverted the signal** — *"the threads were spending more time waiting,
which caused CPU utilization to drop"* — causing a scale-*down* just before demand
peaked. The recovery scale-up tried *"to add 1,200 servers to our web tier between
7:01am PST and 7:15am PST"* but hit *"two separate resource bottlenecks (the most
significant one was the Linux open files limit, but we also exceeded an AWS quota
limit)"*; AWS manually enlarged TGW capacity and the network returned to normal by
10:40am PST.

### 9. Roblox Return to Service 10/28–10/31 2021
**URL:** https://about.roblox.com/newsroom/2022/01/roblox-return-to-service-10-28-10-31-2021/
**Date:** Published 20 Jan 2022; incident 28–31 Oct 2021, **73 hours**

Two latent defects in HashiCorp Consul combined: the newly enabled **streaming**
feature *"used fewer concurrency control elements (Go channels) in its
implementation than long polling"*, so *"under very high load … the design of
streaming exacerbates the amount of contention on a single Go channel"*; and
separately Consul's **BoltDB** freelist had pathologically degraded — *"a 4.2GB
log store … only storing 489MB of actual data. 3.8GB is 'empty' space"*, with a
7.8 MB freelist rewritten on every ~16 kB log append. Because Consul underpinned
service discovery, Nomad and Vault, its degradation cascaded platform-wide, and
diagnosis took 13+ hours across four wrong hypotheses partly because *"critical
monitoring systems that would have provided better visibility into the cause of
the outage relied on affected systems, such as Consul"* — a circular
observability dependency. Streaming was disabled at 15:51 on 30 Oct (KV write
latency 2s → 300ms), BoltDB was compacted, and traffic restored via DNS steering.

### 10. External Technical Root Cause Analysis — Channel File 291 (CrowdStrike)
**URL (RCA PDF):** https://www.crowdstrike.com/wp-content/uploads/2024/08/Channel-File-291-Incident-Root-Cause-Analysis-08.06.2024.pdf
**URL (announcement):** https://www.crowdstrike.com/en-us/blog/channel-file-291-rca-available/
**Date:** RCA published 6 Aug 2024; incident 19 Jul 2024
*Caveat: the PDF fetch returned content partly labelled "Falcon Content Update
Preliminary Post-Incident Report"; the RCA title above is as listed on the blog.*

A new IPC Template Type shipped in February 2024 declared **21** input fields but
the sensor's Content Interpreter integration supplied only **20** — *"the number
of fields in the IPC Template Type was not validated at sensor compile time"*, and
*"a runtime array bounds check was missing for Content Interpreter input fields on
Channel File 291."* The mismatch was latent because earlier Template Instances
used a wildcard in the 21st position, which never forced a read of index 21; the
19 July update introduced a non-wildcard criterion for the 21st input, so the
interpreter read past the end of a 20-element array inside a **kernel-mode
driver**, producing an out-of-bounds read and BSOD. *"The Content Validator
contained a logic error"* that let the mismatched instance through.

### 11. October 21 post-incident analysis (GitHub)
**URL:** https://github.blog/news-insights/company-news/oct21-post-incident-analysis/
**Date:** Incident 21 Oct 2018, 22:52 UTC; **24h11m** degradation

Routine replacement of failing 100G optical equipment severed connectivity
between the US East Coast network hub and the primary US East Coast data centre;
*"connectivity between these locations was restored in 43 seconds, but this brief
outage triggered a chain of events that led to 24 hours and 11 minutes of service
degradation."* During the partition, Orchestrator's Raft quorum re-formed on the
West Coast and *"start[ed] failing over clusters to direct writes to the US West
Coast data center"*, but the East Coast primaries *"contained a brief period of
writes that had not been replicated"*, so *"because the database clusters in both
data centers now contained writes that were not present in the other data center,
we were unable to fail the primary back over ... safely."* Recovery required
restoring multi-terabyte MySQL backups from blob storage — and the key admission
is that although *"this procedure is tested daily at minimum … until this incident
we have never needed to fully rebuild an entire cluster from backup."*

### 12. Post-Incident Review on the Atlassian April 2022 outage
**URL:** https://www.atlassian.com/blog/atlassian-engineering/post-incident-review-april-2022-outage
**Date:** Incident 5 Apr 2022, 07:38–08:01 UTC; **up to 14 days** to restore all customers

A deletion script exposed both "mark for deletion" (recoverable) and "permanently
delete" (compliance) modes and accepted either identifier type — *"if a site ID is
passed, a site would be deleted; if an app ID is passed, an app would be
deleted"* — with *"no warning signal to confirm the type of deletion (site or app)
being requested."* *"There was a communication gap between the team that requested
the deletion and the team that ran it. Instead of providing the IDs of the intended
app being marked for deletion, the team provided the IDs of the entire cloud
site"*, and the script *"did not cross-check the provided cloud site IDs."*
883 sites across 775 customers were permanently deleted in 23 minutes; restoration
ran 8–18 April because *"at the time of the incident, we did not have the ability
to select a large set of customer sites and restore all of their inter-connected
products from backups to a previous point in time."*
**→ Explicitly names missing runbooks as a contributing factor — see D5.**

### 13. You Broke Reddit: The Pi-Day Outage
**Primary URL:** https://www.reddit.com/r/RedditEng/comments/11xx5o0/you_broke_reddit_the_piday_outage/
**(NOT FETCHABLE — reddit.com is blocked to the fetch tool.)**
**Fetched secondary reproducing the quotes:** https://geek-cookbook.funkypenguin.co.nz/blog/2023/03/24/post-mortem-reddit-pi-day-kube-1.25/
**Date:** Incident 14 Mar 2023, 314 minutes

An in-place upgrade from Kubernetes 1.23 to 1.24 removed the deprecated
`node-role.kubernetes.io/master` label (Kubernetes renamed master → control-plane
in 1.20 and dropped the old references in 1.24), and Calico's route reflectors
used that exact label in their `nodeSelector` and `peerSelector`, so BGP route
reflection collapsed and cluster networking failed. The configuration was
invisible to responders: *"the route reflector configuration was thus committed
nowhere, leaving us with no record of it"* — the engineers who set it up had left
or moved teams. Recovery fell back to a cluster restore whose documented procedure
*"had been written against a now end-of-life Kubernetes version"* and pre-dated
the switch from Docker to CRI-O, so it *"had to be rewritten live"* during the
incident.
**→ The single best postmortem for D5 (runbook rot) and for F (undocumented
config that exists nowhere).**

### Follow-on: Cloudflare's post-incident programme
**Code Orange: Fail Small — our resilience plan following recent incidents**,
Dane Knecht, 19 Dec 2025 — https://blog.cloudflare.com/fail-small-resilience-plan/.
Prompted by the 18 Nov 2025 outage and a 5 Dec 2025 incident affecting 28% of
applications for ~25 minutes. Commitments: configuration changes get the same
staged rollout as software (no more instant global Quicksilver propagation);
**Health Mediated Deployments** — *"Every team at Cloudflare that owns a service
must define the metrics that indicate a deployment has succeeded or failed, the
rollout plan, and the steps to take if it does not succeed"*; failure-mode reviews
assuming inter-service failure; and *"reviewing and improving all of the break
glass procedures and technology."*

### Curated collections (verified)
- **danluu/post-mortems** — https://github.com/danluu/post-mortems — ~200+ linked
  postmortems, categorised: **Config Errors, Hardware/Power Failures, Conflicts,
  Time, Database, Uncategorized, Other lists, Analysis, Contributors.**
- **kubernetes-failure-stories / k8s.af** — https://k8s.af/ and
  https://github.com/hjacobs/kubernetes-failure-stories (GitHub repo archived
  23 Aug 2020, active mirror at
  https://codeberg.org/hjacobs/kubernetes-failure-stories). ~60+ entries since
  2017. Samples: Skyscanner 2021 "How a couple of characters brought down our
  site"; Spotify 2019 "How Spotify Accidentally Deleted All its Kube Clusters with
  No User Impact"; Monzo 2018 "Anatomy of a Production Kubernetes Outage";
  Nordstrom 2017 "101 Ways to Crash Your Cluster".

---

## D2. What a real runbook looks like

### The canonical MTTR claim — location corrected

**Not in `being-on-call`. It is in Chapter 1, Introduction → Emergency Response**
— https://sre.google/sre-book/introduction/:

> *"The most relevant metric in evaluating the effectiveness of emergency
> response is how quickly the response team can bring the system back to
> health—that is, the MTTR."*
> *"When humans are necessary, we have found that thinking through and recording
> the best practices ahead of time in a 'playbook' produces roughly a 3x
> improvement in MTTR as compared to the strategy of 'winging it.'"*
> *"The hero jack-of-all-trades on-call engineer does work, but the practiced
> on-call engineer armed with a playbook works much better."*

`being-on-call` (https://sre.google/sre-book/being-on-call/) instead pairs
playbooks with drills: *"'Wheel of Misfortune' exercises … are also useful team
activities that can help to hone and improve troubleshooting skills"*, alongside
company-wide DiRT (Disaster Recovery Training).

### Operational definition and the alert↔playbook coupling

**Google SRE Workbook, Ch. 8** — https://sre.google/workbook/on-call/:
> *"Playbooks contain high-level instructions on how to respond to automated
> alerts. They explain the severity and impact of the alert, and include debugging
> suggestions and possible actions to take to mitigate impact and fully resolve
> the alert."*
> *"In SRE, whenever an alert is created, a corresponding playbook entry is
> usually created. These guides reduce stress, the mean time to repair (MTTR), and
> the risk of human error."*
> *"If your playbooks are a deterministic list of commands that the on-call
> engineer runs every time a particular alert fires, we recommend implementing
> automation."*

**That last line is the boundary condition for agent tasks: a fully deterministic
playbook should be a script, not an agent task.** (Consistent with A4.)

### Structures actually published

| Source | Structure |
|---|---|
| **PagerDuty / Limoncelli** ([pagerduty.com/resources/learn/what-is-a-runbook/](https://www.pagerduty.com/resources/learn/what-is-a-runbook/)) | 1. Service Overview; 2. Service Build Information; 3. Instructions for Deploying the Software; 4. Instructions for Common Tasks; 5. "Pager Playbook"; 6. Disaster Recovery Plans; 7. Service Level Agreement |
| **GitLab public runbooks** ([gitlab.com/gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks)) | Symptoms → Pre-checks → Resolution → Post-checks → Rollback (optional) |
| **kube-prometheus** ([runbooks.prometheus-operator.dev](https://runbooks.prometheus-operator.dev/)) | Meaning / Impact / Diagnosis / Mitigation |
| **Rootly** ([rootly.com/incident-response/runbooks](https://rootly.com/incident-response/runbooks)) | Trigger & Detection; Impact Assessment; Containment Actions; Resolution Workflow; Validation & Verification; Communication Plan; Post-Incident Review |
| **AWS SSM Automation** ([docs.aws.amazon.com/systems-manager/latest/userguide/automation-documents.html](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-documents.html)) | Executable: YAML/JSON, sequential steps each built around a single action; 20 action types incl. `executeScript`, `executeAwsApi`, `aws:branch` |

**PagerDuty's runbook-vs-playbook distinction:** *"A playbook deals with the
overarching responses to larger issues and events, and can include multiple
runbooks."* On maintenance: a runbook *"should be constantly tested and updated."*

**GitLab's repo is the largest genuinely public SRE runbook corpus.** README:
https://gitlab.com/gitlab-com/runbooks/-/raw/master/README.md; rendered at
https://runbooks.gitlab.com. Directories: `docs/` (per-system: PostgreSQL, Redis,
Gitaly, CI, monitoring), `howto/` (alerts, deployments, failovers),
`troubleshooting/`, `bin/` (executable helpers), `certificates/`, `dashboards/`,
**`libsonnet/`** (Jsonnet libraries generating **alerts and dashboards from the
same source tree** — i.e. alerts and their docs are co-generated). Stated norm:
every alert references its runbook; an alert with no runbook gets an issue filed.

**Worked example** —
https://runbooks.prometheus-operator.dev/runbooks/kubernetes/kubepodcrashlooping/
— Meaning: *"Pod is in CrashLoop which means the app dies or is unresponsive and
kubernetes tries to restart it automatically."* Diagnosis enumerates
`kubectl get pod`, pod events and logs, template parameter validation, then
candidate causes (resource starvation, dependency failure, misconfiguration,
missing ConfigMaps/secrets, filesystem, permissions, missing capabilities).

**Terse counter-example** —
https://github.com/kubernetes-monitoring/kubernetes-mixin/blob/master/runbook.md
— per alert only name, message template, severity and an external link. Useful
contrast for calibrating how much a runbook actually contains in practice.

**incident.io's automated-runbook layering** —
https://incident.io/blog/automated-runbook-guide — three layers: **trigger and
triage** (dedicated channel, auto-page from alert context), **diagnostics**
(auto-fetch deploy history, metrics, active alerts, dashboard links),
**remediation** (interactive options with approval gates and audit trails).
Claims *"MTTR improvements of 30-50%"* — vendor claim, unverified.

**Atlassian** — handbook at
https://www.atlassian.com/incident-management/handbook and playbook guide at
https://www.atlassian.com/incident-management/incident-response/how-to-create-an-incident-response-playbook.
**Both returned only navigation chrome to the fetcher — no field lists quoted.**

---

## D3. Real alert payloads — exact field names

### Prometheus Alertmanager webhook (the reference schema)
https://prometheus.io/docs/alerting/latest/configuration/#webhook_config

```json
{
  "version": "4",
  "groupKey": "<string>",
  "truncatedAlerts": "<int>",
  "status": "<resolved|firing>",
  "receiver": "<string>",
  "groupLabels": "<object>",
  "commonLabels": "<object>",
  "commonAnnotations": "<object>",
  "externalURL": "<string>",
  "notification_reason": "<string>",
  "alerts": [
    {
      "status": "<resolved|firing>",
      "labels": "<object>",
      "annotations": "<object>",
      "startsAt": "<rfc3339>",
      "endsAt": "<rfc3339>",
      "generatorURL": "<string>",
      "fingerprint": "<string>"
    }
  ]
}
```

Two fields commonly omitted from summaries: **`truncatedAlerts`** (*"how many
alerts have been truncated due to `max_alerts`"* — **a silent data-loss vector for
any agent counting alerts**) and **`notification_reason`**. `groupKey` identifies
the alert grouping for dedup (see F/CS-28); `generatorURL` *"identifies the entity
that caused the alert"*; `fingerprint` identifies the alert.

### Where runbook links actually live
https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/ —
alerting-rule keys are **`alert`, `expr`, `for`, `keep_firing_for`, `labels`,
`annotations`**. Labels are structural and routable (*"any existing conflicting
labels will be overwritten"*); annotations are *"informational labels that can be
used to store longer additional information such as alert descriptions or runbook
links."*

The de-facto convention is the **`runbook_url`** annotation, arriving in the
webhook at `alerts[].annotations.runbook_url`. Verified against a real shipped
manifest —
https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/main/manifests/alertmanager-prometheusRule.yaml:

```yaml
alert: AlertmanagerFailedReload
annotations:
  description: "Configuration has failed to load for {{ $labels.namespace }}/{{ $labels.pod}}."
  runbook_url: https://runbooks.prometheus-operator.dev/runbooks/alertmanager/alertmanagerfailedreload
  summary: Reloading an Alertmanager configuration has failed.
expr: |
  max_over_time(alertmanager_config_last_reload_successful{job="alertmanager-main",container="alertmanager",namespace="monitoring"}[5m]) == 0
for: 10m
labels:
  severity: critical
```

**The standard triple is `annotations.{description, runbook_url, summary}` +
`labels.severity`.** Coverage gaps in this convention are actively tracked:
https://github.com/prometheus-operator/kube-prometheus/issues/731 and
https://github.com/prometheus-operator/kube-prometheus/issues/1001.

### Grafana alerting webhook
https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
— Alertmanager-shaped **superset**.

Top level: `receiver`, `status` (firing|resolved), **`orgId`**, `alerts`,
`groupLabels`, `commonLabels`, `commonAnnotations`, `externalURL`, `version`,
`groupKey`, `truncatedAlerts`, **`title`**, **`state`** (alerting|ok),
**`message`**.
Per alert: `status`, `labels`, `annotations`, `startsAt`, `endsAt`, **`values`**
(the values that triggered the alert), `generatorURL`, `fingerprint`,
**`silenceURL`**, **`dashboardURL`**, **`panelURL`**, **`imageURL`**.

### PagerDuty Events API v2 (PD-CEF)
**Fetch caveat: all `developer.pagerduty.com` paths return empty bodies
(JS-rendered).** Schema sourced from support docs and PagerDuty's own GitHub.

https://support.pagerduty.com/main/docs/pd-cef:

| Field | Type | Required | Notes / examples |
|---|---|---|---|
| `summary` | String | **Yes** | *"A high-level, text summary message of the event."* e.g. `"PING OK - Packet loss = 0%, RTA = 1.41 ms"` |
| `severity` | Enum | **Yes** | **Info, Warning, Error, Critical** |
| `source` | String | **Yes** | *"Specific human-readable unique identifier, such as a hostname"* e.g. `"prod05.theseus.acme-widgets.com"` |
| `timestamp` | Timestamp | Optional | *"When the upstream system detected / created the event."* |
| `component` | String | Optional | *"The part or component of the affected system that is broken."* e.g. `"keepalive"`, `"mysql"` |
| `group` | String | Optional | *"A cluster or grouping of sources."* e.g. `"production-app-stack"` |
| `class` | String | Optional | *"The class/type of the event."* e.g. `"High CPU"`, `"Latency"` |
| `custom_details` | Object | Optional | free-form, e.g. `{"ping time": "1500ms", "load avg": 0.75}` |

Envelope, from a real PagerDuty sample
(https://raw.githubusercontent.com/PagerDuty/API_Python_Examples/master/EVENTS_API_v2/trigger/trigger_without_incident_key.py),
POSTed to `https://events.pagerduty.com/v2/enqueue`:

```json
{
  "routing_key": "",
  "event_action": "trigger",
  "payload": {
    "summary": "Example alert on host1.example.com",
    "source": "monitoringtool:cloudvendor:central-region-dc-01:852559987:cluster/api-stats-prod-003",
    "severity": "critical"
  }
}
```

`event_action` ∈ **trigger | acknowledge | resolve**; **`dedup_key` may be
supplied on the trigger or is generated by PagerDuty and returned; only `trigger`
events create alerts.** Envelope also supports `client`, `client_url`, `images[]`,
`links[]`. *(dedup_key semantics from search excerpts of
https://developer.pagerduty.com/docs/events-api-v2/trigger-events/ — the page
itself will not render. **This resolves the open caveat in F/CS-28.**)*

**PagerDuty v3 outbound webhooks** — https://support.pagerduty.com/main/docs/webhooks
— single JSON object with top-level **`event`** containing `id`, `event_type`,
`resource_type`, `occurred_at`, `agent`, `client`, `data`. Event types include
incident `triggered`, `acknowledged`, `escalated`, `resolved`, `annotated`,
`priority_updated`. Verification header: **`x-pagerduty-signature`**.

### Datadog webhooks — no fixed schema
https://docs.datadoghq.com/integrations/webhooks/ — **Datadog does NOT document a
default JSON payload; the body is author-composed from `$`-variables.** The
documented set includes: `$AGGREG_KEY, $ALERT_CYCLE_KEY, $ALERT_ID, $ALERT_METRIC,
$ALERT_PRIORITY, $ALERT_QUERY, $ALERT_SCOPE, $ALERT_STATUS, $ALERT_TITLE,
$ALERT_TRANSITION, $ALERT_TYPE, $DATE, $DATE_POSIX, $EMAIL, $EVENT_MSG,
$EVENT_TITLE, $EVENT_TYPE, $HOSTNAME, $ID, $INCIDENT_COMMANDER,
$INCIDENT_CUSTOMER_IMPACT, $INCIDENT_PUBLIC_ID, $INCIDENT_SEVERITY,
$INCIDENT_STATUS, $INCIDENT_TITLE, $INCIDENT_URL, $LAST_UPDATED, $LINK,
$LOGS_SAMPLE, $ORG_ID, $ORG_NAME, $PRIORITY, $SECURITY_SIGNAL_*, $SNAPSHOT,
$SYNTHETICS_*, $TAGS, $TAGS[key], $TEXT_ONLY_MSG, $USER, $USERNAME` (plus a
`$CASE_*` family).

**Consequence: Datadog payload shape is per-installation, not standardised.
Unlike Alertmanager/Grafana you cannot write a schema-based parser against it.
This is itself a chaos scenario — see F.**

### Opsgenie Alert API
https://docs.opsgenie.com/docs/alert-api — **`message`** (mandatory), `alias`,
`description`, `responders`, `visibleTo`, `actions`, `tags`, `details`, `entity`,
`source`, `priority`, `user`, `note`. `priority` ∈ **P1–P5**, default **P3**.

### Sentry issue webhook
https://docs.sentry.io/organization/integrations/integration-platform/webhooks/issues/
— header `Sentry-Hook-Resource: issue`, plus `Sentry-Hook-Timestamp` /
`Sentry-Hook-Signature`. Body: `action`, `installation.uuid`, `data.issue.{id,
shareId, shortId, title, culprit, permalink, logger, level, status,
statusDetails, isPublic, platform, project{id,name,slug,platform}, type,
metadata, numComments, assignedTo, count, userCount, firstSeen, lastSeen}`,
`actor`.

### Cross-schema observation — the load-bearing finding

**Only Alertmanager and Grafana share a field vocabulary (Grafana is a superset).
PagerDuty, Datadog, Opsgenie and Sentry each use disjoint names for the same
concepts:**

| Concept | Prometheus | PagerDuty | Datadog | Opsgenie | Sentry |
|---|---|---|---|---|---|
| What broke | `alerts[].annotations.summary` | `payload.summary` | `$EVENT_TITLE` | `message` | `data.issue.title` |
| How bad | `labels.severity` | `payload.severity` (Info/Warning/Error/Critical) | `$ALERT_PRIORITY` | `priority` (P1–P5) | `data.issue.level` |
| Where | `labels.instance` | `payload.source` | `$HOSTNAME` | `entity`/`source` | `data.issue.project` |
| Runbook | `annotations.runbook_url` | — | — | — | — |

**Only Prometheus/Grafana carry a runbook link as a first-class convention.**
This table is directly reusable as a reconciliation task (F/CS-01 generalised to
alert schemas).

---

## D4. ADRs (Architecture Decision Records)

### Canonical origin
**Michael Nygard, "Documenting Architecture Decisions", 15 Nov 2011** —
https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions

Motivation: *"One of the hardest things to track during the life of a project is
the motivation behind certain decisions"* — new joiners either blindly accept
decisions they don't understand or blindly change them without understanding the
consequences. **Five sections:**
- **Title** — short noun phrases.
- **Context** — *"This section describes the forces at play, including
  technological, political, social, and project local."* Value-neutral, factual.
- **Decision** — *"This section describes our response to these forces. It is
  stated in full sentences, with active voice."*
- **Status** — *"A decision may be 'proposed' if the project stakeholders haven't
  agreed with it yet, or 'accepted' once it is agreed. If a later ADR changes or
  reverses a decision, it may be marked as 'deprecated' or 'superseded'…"*
- **Consequences** — both directions: *"all consequences should be listed here,
  not just the 'positive' ones."*

Length constraint is part of the design: one or two pages, so it gets read and
maintained.

### adr.github.io and the template catalogue
https://adr.github.io/ — an ADR *"captures a single AD and its rationale"*, giving
*"the reasons for a chosen architectural decision, along with its trade-offs and
consequences"*; the **Architecture Decision Log (ADL)** is *"the collection of ADRs
created and maintained in a project."*
Templates (https://adr.github.io/adr-templates/): **MADR**, **Nygard ADR**,
**Y-Statement** — *"In the context of `<use case/user story>`, facing `<concern>`
we decided for `<option>` to achieve `<quality>`, accepting `<downside>`"* — and
the **ISO/IEC/IEEE 42010:2011** template.

### MADR — the actual fields
https://raw.githubusercontent.com/adr/madr/main/template/adr-template.md
(repo: https://github.com/adr/madr). YAML front matter:

```yaml
status: "{proposed | rejected | accepted | deprecated | … | superseded by ADR-0123}"
date: {YYYY-MM-DD when the decision was last updated}
decision-makers: {list everyone involved in the decision}
consulted: {list everyone whose opinions are sought … two-way communication}
informed: {list everyone who is kept up-to-date on progress … one-way communication}
```

Body: `# {short title}` → **Context and Problem Statement** → *Decision Drivers*
(optional) → **Considered Options** → **Decision Outcome** → *Consequences*
(optional; "Good, because…" / "Bad, because…") → *Confirmation* (optional but
*"included in many ADRs"* — *"Describe how the implementation / compliance of the
ADR can/will be confirmed … automated or manual fitness function … a test with a
library such as ArchUnit"*) → *Pros and Cons of the Options* → *More Information*.

**Two staleness-management mechanisms are baked into the format:** `date` is
explicitly *"when the decision was last updated"*, and `status` carries an
explicit supersession pointer. Relevant to D5.

### Tooling and real collections
- **adr-tools (Nat Pryce)** — https://github.com/npryce/adr-tools — `doc/adr/`
  with numbered filenames (`0001-record-architecture-decisions.md`). `adr init`,
  `adr new [title]`, and `adr new -s [number] [title]` which creates a superseding
  ADR and **automatically updates the earlier record's status**.
- **Arachne Framework** — https://github.com/arachne-framework/architecture — 17
  ADRs, `adr-###-descriptive-title.md`, starting with ADR-001 "Use ADRs". The
  collection Nygard's format is most often demonstrated against.
- **joelparkerhenderson/architecture-decision-record** —
  https://github.com/joelparkerhenderson/architecture-decision-record — the
  broadest catalogue: templates by **Jeff Tyree and Art Akerman; Michael Nygard;
  EdgeX; arc42; Alexandrian pattern; business case; MADR; Planguage; Paulo Merson;
  Olaf Zimmermann; Gareth Morgan; GIG Cymru NHS Wales; Important Technical
  Decisions (ITDs)**.

---

## D5. Documentation staleness / runbook rot as an incident factor

Ordered from primary postmortem evidence outward. **This is the section with the
strongest evidence base and it directly justifies stale-doc chaos in tasks.**

### (a) Postmortems that explicitly name stale/missing documentation

**Reddit Pi-Day 2023 — the strongest single case.** Two distinct documentation
failures:
1. **Undocumented config, lost with the people who wrote it:** *"The route
   reflector configuration was thus committed nowhere, leaving us with no record
   of it."* The engineers who configured it had left or moved on.
2. **A restore procedure that had rotted:** the documented restore *"had been
   written against a now end-of-life Kubernetes version"* and pre-dated the switch
   from Docker to CRI-O, so it *"had to be rewritten live"* — mid-incident, on a
   314-minute outage.
   (Primary blocked; quotes via
   https://geek-cookbook.funkypenguin.co.nz/blog/2023/03/24/post-mortem-reddit-pi-day-kube-1.25/;
   further analysis https://overmind.tech/blog/reddit-pi-day-outage)

**Atlassian April 2022** — names runbook absence twice, as a first-class
contributor to a **14-day** restoration:
> *"The site-level deletion did not have runbooks that could be quickly automated
> for the scale of this event."*
> *"We have playbooks for product-level incidents, but not for the events of this
> scale, with hundreds of people working simultaneously."*
(https://www.atlassian.com/blog/atlassian-engineering/post-incident-review-april-2022-outage)

**GitHub Oct 2018 — the "documented but never exercised" variant:** *"This
procedure is tested daily at minimum, so the recovery time frame was well
understood, **however until this incident we have never needed to fully rebuild an
entire cluster from backup**."* The documentation existed and was nominally
tested; the end-to-end path had never been walked.
(https://github.blog/news-insights/company-news/oct21-post-incident-analysis/)

**GitLab Jan 2017 — silent-verification rot:** pg_dump ran under 9.2 against a 9.6
production DB and always errored, and *"notifications were sent upon failure, but
because of the Emails being rejected there was no indication of failure."* The
documented backup regime was believed-good and was producing nothing.
(https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/)

**Roblox 2021 and AWS Dec 2021 — the adjacent failure mode:** the diagnostic
*inputs* a runbook depends on were themselves unavailable. Roblox: *"critical
monitoring systems that would have provided better visibility into the cause of
the outage relied on affected systems, such as Consul."* AWS: congestion
*"immediately impacted the availability of real-time monitoring data for our
internal operations teams, which impaired their ability to find the source."*

### (b) The authoritative statement that playbooks go stale

**Google SRE Workbook, Ch. 8 On-Call** — https://sre.google/workbook/on-call/ —
**this is the named, quotable industry source for runbook rot:**

> *"Details in playbooks go out of date at the same rate as production environment
> changes. For daily releases, playbooks might need an update on any given day."*

And the unresolved trade-off, stated as a live disagreement inside Google:

> *"Some SREs at Google advocate keeping playbook entries general so they change
> slowly… Other SREs advocate for step-by-step playbooks to reduce human
> variability and drive down MTTR."*

Maintenance mechanism: *"On-call engineers should update the playbook with fresh
information when the corresponding page fires."*

**Note the direct tension with the 3x-MTTR claim
(https://sre.google/sre-book/introduction/): the more prescriptive the playbook,
the larger the MTTR win *and* the faster it decays.** That tension is itself a
good task premise.

### (c) Named vendor/practitioner sources on runbook rot

- **Gremlin, "Ensuring Runbooks are Up-to-Date"** —
  https://www.gremlin.com/blog/ensuring-runbooks-are-up-to-date — the cleanest
  statement of inevitability: *"One thing that all technical documentation for
  software that is still in active development has in common is that if it is not
  already outdated, it will be."* Root cause: *"The biggest reason that
  documentation doesn't get updated is that time was never scheduled to update
  it."* Remedy is executable validation: chaos experiments that *"precisely target
  a part of your system for failure and then follow the runbook documentation to
  see if the information is adequate."*
- **incident.io** — https://incident.io/blog/automated-runbook-guide — *"Your
  documentation decays faster than your systems change. That runbook written six
  months ago? It probably references deprecated commands, old dashboard URLs, or
  services that no longer exist."*
- **Rootly** — https://rootly.com/incident-response/runbooks — *"A single outdated
  command can destroy trust"*; prescribes quarterly reviews, version control,
  updating runbooks immediately after each post-mortem, visible ownership, and
  archiving runbooks for deprecated systems. Governance companion:
  https://rootly.com/incident-response/playbooks
- **eKline, "Why Your Incident Runbook Lies to You at 3 a.m."** —
  https://ekline.io/blog/why-your-incident-runbook-lies-to-you-at-3-a-m-and-how-to-tell-before-the-page-fires
  — frames it as capability loss: a stale runbook is *"a degraded incident
  response capability."* Attaches a cost model — each wrong step costs ~8–15
  minutes before the responder realises the instruction doesn't match reality, so
  three wrong steps add ~24–45 minutes. **Vendor estimate, not measured data — do
  not cite the minute figures as fact.** (Search-results only, not fetched.)

### (d) Survey evidence on documentation quality

- **GitHub Open Source Survey 2017** — https://opensourcesurvey.org/2017/ — **the
  single most citable number: *"Incomplete or outdated documentation is a
  pervasive problem, observed by 93% of respondents"*, while *"60% of contributors
  say they rarely or never contribute to documentation."***
- **Stack Overflow, "Why do developers love clean code but hate writing
  documentation?" (19 Dec 2024)** —
  https://stackoverflow.blog/2024/12/19/developers-hate-documentation-ai-generated-toil-work/
  — developers spend *"more than 30 minutes a day searching for solutions"*;
  *"documentation often takes up 11% of developers' work hours"*; *"over 17 hours
  a week on maintenance tasks."* Mechanism: docs deprioritised *"due to tight
  deadlines and a focus on delivering working code"*, producing *"informal,
  hard-to-understand documentation that quickly becomes outdated."*
- **Stack Overflow Developer Survey 2024/2025** — https://survey.stackoverflow.co/2025
  and https://stackoverflow.blog/2025/01/01/developers-want-more-more-more-the-2024-results-from-stack-overflow-s-annual-developer-survey/
  — 2024: technical debt was *"the biggest frustration, by a large margin."* 2025:
  top frustration shifted to *"AI solutions that are almost right, but not quite"*
  (66%), then *"Debugging AI-generated code is more time-consuming"* (45%).
  **NO SOURCE FOUND — judgement call:** no Stack Overflow survey question isolates
  *outdated documentation* as a named frustration percentage. The GitHub 2017 93%
  figure remains the best-sourced number for that specific claim.

### (e) Academic work on documentation/comment inconsistency

- **Radmanesh, Imani, Ahmed, Moshirpour, "Investigating the Impact of Code Comment
  Inconsistency on Bug Introducing" (arXiv, 16 Sep 2024)** —
  https://arxiv.org/abs/2409.10781 — **the causal link, quantified:**
  *"Our findings reveal that inconsistent changes are around **1.5 times more
  likely to lead to a bug-introducing commit** than consistent changes… the impact
  of code-comment inconsistency on bug introduction is **highest immediately after
  the inconsistency is introduced and diminishes over time.**"*
  **That second clause is the operationally important one: documentation drift is
  most dangerous in the window right after a change — exactly the window in which
  an incident is most likely.**
- **Wen et al., "A Large-Scale Empirical Study on Code-Comment Inconsistencies",
  ICPC 2019** — https://dl.acm.org/doi/abs/10.1109/ICPC.2019.00019 /
  https://ieeexplore.ieee.org/document/8813274/ (**both paywalled to the
  fetcher**). Mined 1.3 billion AST-level changes across 1,500 systems, with manual
  analysis of 500 commits.
- **"Detecting Outdated Code Element References in Software Repository
  Documentation"** — https://arxiv.org/pdf/2212.01479 — the closest academic
  analogue to "the runbook referenced a service that's been deleted."
- **"CCISolver: End-to-End Detection and Repair of Method-Level Code-Comment
  Inconsistency"** — https://arxiv.org/pdf/2506.20558

### (f) Synthesis — the mechanism, and the counter-mechanisms

**The chain that recurs across the fetched postmortems:**
a system changes → the document describing it is *not on the change's critical
path*, so it silently diverges → the divergence is invisible because *nothing
exercises the document* (GitLab's never-verified pg_dump; GitHub's never-executed
full restore; Reddit's uncommitted route-reflector config) → the divergence is
discovered only under incident conditions, when correcting it is most expensive
(Reddit rewriting the restore procedure live).

**The named counter-mechanisms are all about putting the document on an execution
path:**
- `runbook_url` annotations so every alert carries its doc (kube-prometheus)
- runbooks generated from the same Jsonnet tree as the alerts (GitLab)
- executable runbooks (AWS SSM Automation)
- GameDay / chaos validation of the runbook (Gremlin)
- Wheel of Misfortune drills and DiRT (Google)
- "update the playbook when the page fires" (SRE Workbook)
- MADR's `date: when the decision was last updated` + auto-superseding status
  (adr-tools)
- quarterly review with visible ownership (Rootly)

**Task design implication:** a stale runbook is *realistic* chaos (F5) precisely
when the environment contains the evidence that it is stale — a referenced host
that no longer resolves, a `kubectl` flag removed in the running version, an
alert whose `runbook_url` 404s. That makes it discoverable, not cruel.

---

## D-question answers in one line each

- **D1 — what a real engineer reads:** alert payload → runbook (via
  `runbook_url`) → dashboards → deploy/change history → prior postmortems →
  service catalog for ownership → Slack thread → ADRs for "why is it like this".
  All eight are sourced above.
- **D2 — authoritative vs stale:** the only reliable staleness signals found in
  primary sources are *execution* (does the documented command still work?),
  *reference integrity* (does the host/flag/URL still exist?), and *explicit
  metadata* (MADR `date` + `status: superseded`). Everything else is judgement.
- **D3 — what payloads look like:** see the cross-schema table. Two schemas share
  a vocabulary; four do not; one (Datadog) has no fixed schema at all.
- **D4 — how much is not written down:** **NO QUANTITATIVE SOURCE FOUND.** The
  qualitative evidence is strong and specific: Reddit's route-reflector config was
  *"committed nowhere"*; GitHub's restore path was documented but never walked;
  Atlassian had no runbook for the scale of event that occurred. Treat "the answer
  is not written down" as a documented, recurring condition rather than a
  measurable fraction.
