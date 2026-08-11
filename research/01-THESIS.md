# 01 — Thesis: what the research says, and what it forced us to build

Answers every question in `00-QUESTIONS.md` (A1–H4, then R1–R4) from the notes on
disk. Every substantive claim carries a citation: a note file, a URL from
`SOURCES.md`, or an explicit `JUDGEMENT CALL — no source`. Where the corpus
contradicts itself, both positions are stated.

---

## Framing

This domain is the **change-and-operate loop around a running service**: a change
is proposed, reviewed, tested, merged, deployed through environments, observed in
production, and — when it goes wrong — detected, localized, mitigated, explained
and closed out. It is not "writing code". Google's SRE organisation puts a number
on where the work goes: an on-call incident costs about **6 hours** including
root-cause analysis, remediation, postmortem and follow-up bugs, which is why the
stated ceiling is **2 incidents per 12-hour shift** — a shift with roughly zero
slack ([sre.google/sre-book/being-on-call/](https://sre.google/sre-book/being-on-call/)).
Most of those six hours is follow-up, not fixing.

What an agent is actually asked to do here is **reconcile and verify**, not
author. Deterministic tooling already owns detection, reconciliation to a declared
state, and mechanical remediation toward a known-good target: Argo Rollouts aborts
a failing canary by itself, Flux reverts out-of-band `kubectl` edits within five
minutes, cert-manager renews certificates before expiry, HPA is a closed-form
equation (`research/notes/domain/A_business_value.md` §A4). What survives
automation is judgement: *why* the canary failed, *which* of two conflicting
sources is right, *whether* a major-version bump is safe, *what* the postmortem
says.

What makes it hard is that the evidence is contradictory rather than absent. The
same service is `checkout` in code, `checkout-svc` in PagerDuty,
`checkout_service` as a Prometheus label and an image tag in Datadog; `nonprod`
matches a naive `grep prod` and is classified production-tier by GitLab's own
regex ([gitlab.com/gitlab-org/gitlab/-/issues/377916](https://gitlab.com/gitlab-org/gitlab/-/issues/377916));
"resolved" means four incompatible things across PagerDuty, FireHydrant, Datadog
and Statuspage; **28.9–50.8% of *duplicate* bug reports carry inconsistent
severity labels** inside a single tracker
(`research/notes/domain/F_chaos_scenarios.md` CS-01, CS-06, CS-11;
`research/notes/domain/B_stakeholders_workflow.md` §B3.2).

The single most important design consequence for a simulated world: **environment
failure must be structurally distinguishable from model failure, and chaos must be
discoverable rather than hidden.** The eval corpus proves both halves. Seven
benchmarks build rich failure taxonomies and discard them at the moment the number
is computed, so a flaky harness reads as a weak model — and the rate is
first-order: AlgoTune's *oracle* passes only ~85% through terminal-bench's harness
(`research/notes/evals/_CROSS_CUTTING.md` §3.5). Meanwhile the line between
realistic difficulty and cruelty is entirely whether the resolution path exists
inside the environment: conflicting data with a discoverable mapping is reality;
withheld data is not (`research/notes/domain/F_chaos_scenarios.md` §F5).

---

## A. Domain and business value

**A1 — What is this domain, and where is the boundary?**
The benchmarks disagree. Eight of nine repos define the domain as *repair a real
repository, verified by its own tests in a container*; only AIOpsLab treats the
running system as the object of work, with **89** problems split 34 detect / 28
localize / 13 analyse / 14 mitigate. So in the published literature "software
engineering agent" means repo-patching, and "DevOps/SRE agent" is essentially a
one-repo domain. DORA's metric set is what joins them: throughput (change lead
time, deployment frequency) plus instability (change fail rate, failed deployment
recovery time, deployment rework rate) spans code and operations in one
instrument.
*Source: `notes/evals/_CROSS_CUTTING.md` §1.1–1.2;
[dora.dev/guides/dora-metrics/](https://dora.dev/guides/dora-metrics/).*

**A2 — Who pays, and for what outcome?**
The published cost-of-downtime range spans an order of magnitude and the notes
refuse to blend it: Uptime Institute 2025 (54% of most-recent outages cost >$100K,
one in five >$1M) is the conservative floor; New Relic's $1.9M/hour median for
high-impact outages at 51-minute median MTTR is the enterprise ceiling. The
best-evidenced case is not speed but procedure adherence around change:
**~70% of outages are change-induced**, **80% of operators believe better process
would have prevented their most recent incident**, and **58% of human-error
outages are staff failing to follow procedure** (up 10 points YoY). Gartner's
$5,600/minute has **no primary source obtained** — treat as folklore.
*Source: `notes/domain/A_business_value.md` §A2;
[sre.google/sre-book/introduction/](https://sre.google/sre-book/introduction/).*

**A3 — What does the business lose when the agent is wrong?**
Ranked by evidence quality. (1) **A leaked secret** — best-instrumented and
fastest-growing: 28.65M new hardcoded secrets in 2025 (+34% YoY), AI-service
secrets +81% to 1,275,105; stolen credentials led 22% of breaches. (2) **A
breach** — IBM's 2025 global average $4.44M. (3) **A bad deploy / wrong diagnosis
/ missed regression** — **no published per-bad-deploy figure exists**; the notes
compose one (70% change-induced × CFR 5–40% × $1.9M/hour at 51-min MTTR) and label
the composition a judgement call. (4) **A wasted engineer-hour** is cheapest — but
a wrong answer an engineer *trusts* is not, per METR's RCT where developers
believed AI sped them up 20% while measurement showed a 19% slowdown (METR later
found selection bias and a much smaller ~−4% effect).
*Source: `notes/domain/A_business_value.md` §A3; `notes/domain/F_chaos_scenarios.md` §F6.*

**A4 — What is already automated, and therefore uninteresting?**
Progressive delivery with automatic abort (Argo Rollouts, Flagger), autoscaling
(HPA is a published formula; Karpenter), self-healing and GitOps reconciliation
(Flux: *"If you make any changes to the cluster using `kubectl edit/patch/delete`,
they will be promptly reverted"*), dependency PRs (Dependabot, Renovate),
certificate renewal (cert-manager), and Terraform drift *detection*. The Workbook
states the boundary outright: *"If your playbooks are a deterministic list of
commands that the on-call engineer runs every time a particular alert fires, we
recommend implementing automation."* What remains is judgement: why the canary
failed, which side of a drift is correct, whether a major bump is safe, writing
the postmortem, converting a novel alert into a runbook.
*Source: `notes/domain/A_business_value.md` §A4; `notes/domain/D_input_documents.md` §D2.*

---

## B. Stakeholders and the shape of the work

**B1 — Who are the humans, and what do they expect?**
Four published role models, and they collide. Google SRE Book: Incident Command,
Operational Work, Communication, **Planning**. Google IMAG: IC, Comms Lead, Ops
Lead — the Workbook **drops Planning entirely**. PagerDuty: six roles including
**Deputy** and **Scribe**. Atlassian calls the top role **Incident Manager**, and
its **Tech Lead develops theories about what is broken** — a diagnostician, unlike
Google's Ops Lead who *applies operational tools*. Near-universal agreement: the
IC absorbs every undelegated role. Consequence: sustainment work — handoffs, bug
filing, tracking divergence from normal — is **unowned** outside Google's model.
*Source: `notes/domain/B_stakeholders_workflow.md` §B1.4, §B5.2.*

**B2 — Where does work originate?**
An alert payload (Alertmanager / Grafana / PagerDuty / Opsgenie / Sentry
webhooks, field names catalogued in D3), a ticket, a customer-visible symptom via
the status page, or a scheduled audit. But the *entry gate itself is contested*:
Google declares an incident on **multi-team OR customer-visible OR unsolved after
an hour**; PagerDuty on **customer-affecting**, with multi-team merely escalating
it to *major*. A single-team, hour-long, non-customer-visible problem is an
incident at Google and is not one at PagerDuty — and every "how many incidents did
we have" question inherits that.
*Source: `notes/domain/B_stakeholders_workflow.md` §B0.*

**B3 — What does "done" mean, and do the definitions conflict?**
Four incompatible bars. PagerDuty: the incident ends when *"there's no more
productive work to be done right now"*, and may be called over *"once the incident
has recovered **or is actively recovering**"*. FireHydrant: *"working again with no
relapse"*. Datadog: root causes *"sufficiently well-understood to justify
confidence that it will not immediately recur"*. Statuspage: *"the root cause of
the issue has been eliminated and your systems are back to 100% performance"*. An
outage mitigated by rollback with the bug still in the codebase is legitimately
Resolved in two and legitimately not in the other two — so any tracker↔status-page
sync emits a false "Resolved" or a stuck-open incident. The correct mapping is
Statuspage **Monitoring ↔ Mitigated**.
*Source: `notes/domain/B_stakeholders_workflow.md` §B3.1–B3.2.*

**B4 — What is the agent not allowed to do, and who enforces it?**
Google's *Building Secure and Reliable Systems* Ch. 5: least privilege;
Multi-Party Authorization; break-glass *"bypasses your authorization system
completely"* and must be SRE-restricted, monitored, and **tested regularly**;
temporary access tied to the on-call shift boundary. The target posture is **Zero
Touch Production** — *"removing direct human access to production roles"* — i.e.
act through tooled, audited interfaces. Enforcement is the authorization system
plus the audit trail, with the regulatory floor that *"changes must be approved by
someone other than the author"*. DORA adds the counterweight: external
change-approval boards have a **negative** effect on delivery performance and **no**
correlation with change fail rate. (The "2.6× more likely to be low performers"
figure is **not** on the dora.dev page and survives only in snippets of an
unparseable PDF.)
*Source: `notes/domain/B_stakeholders_workflow.md` §B4.1–B4.2.*

**B5 — What interrupts the workflow, and how does an agent say "I am blocked"?**
Handoff practice is documented (Google's shift-end email; incident.io's 30-minute
handoff with a **read-back confirmation**, silenced alerts, upcoming deploys and
*specific runbook URLs, not "check Datadog"*). On representing blockage the eval
corpus is stark: **two mechanisms exist and zero benchmarks score them** —
tau-bench's `transfer_to_human_agents` always scores 0, and vivaria's
`RunPauseReason.HUMAN_INTERVENTION` pauses forever by design (`timeout:
Infinity`). The automation corpus supplies the shape: blocked-on-human should be
**durable state** — an event in the trace — not a held socket; cline's
`ToolApprovalRequest` times out to *denied* after 5 minutes.
*Source: `notes/evals/_CROSS_CUTTING.md` §8; `notes/automation/_WORKFLOW_PATTERNS.md` §2.7.*

---

## C. Task taxonomy

**C1 — What task types do the benchmarks contain?**
Nine repos are **seven benchmarks plus two pieces of infrastructure**. SWE-bench:
2,294 full / 500 Verified / 300 Lite. AIOpsLab: 89 problems (34/28/13/14).
tau-bench: 165 (115 retail + 50 airline). TheAgentCompany: 175 office tasks across
four self-hosted services. terminal-bench: 241 (leaderboard core 80). commit0: 56
libraries (16 lite), ~140,926 tests. SWE-Lancer: 463 (198 IC + 265 manager).
vivaria: a platform with 2 examples. Every count was verified from code, because
**four repos' prose disagrees with their own code** (commit0 says 57 / is 56;
AIOpsLab says "60+" / is 89; SWE-bench docs say Lite = 534 / is 300).
*Source: `notes/evals/_CROSS_CUTTING.md` §0, §0.1.*

**C2 — What is the distribution of task length?**
The corpus does not measure tool calls; it bounds episodes, differently in every
repo. SWE-bench has **no notion of steps at all**. SWE-agent has **no
`max_steps`** — it budgets in **money** ($3.00/instance, 1,800s). AIOpsLab and
tau-bench cap at **30 steps**; terminal-bench at 900s agent / 180s test;
SWE-Lancer at 3,000s; commit0 at 3 iterations; vivaria at four typed dimensions
(tokens, actions, seconds, USD) with checkpoints that *pause* rather than kill. On
files touched, only SWE-bench **Lite** caps size (≤1 file, ≤3 hunks, ≥40 words);
full and Verified have none. TheAgentCompany's budget is 661 points over 175
tasks, median 3 checkpoints, max 8.
*Source: `notes/evals/_CROSS_CUTTING.md` §6.4; `notes/evals/princeton-nlp__SWE-bench.md` §1.5.*

**C3 — Single-shot versus long-horizon?**
Overwhelmingly single-shot. Only **TheAgentCompany** runs a multi-service workflow
end to end (79/175 tasks touch RocketChat, 71 GitLab, 70 ownCloud, 17 Plane).
SWE-Lancer IC is long *in time* but single-service; AIOpsLab is multi-service but
30 steps. Nothing in the corpus grades investigate → change → ship → verify →
communicate as one episode.
*Source: `notes/evals/_CROSS_CUTTING.md` §1.5.*

**C4 — What are the consensus tasks?**
Exactly one, plus a weak second. Universal: **fix a real repository and prove it
with its own tests in a container** (8 of 9 repos; the substrate — pytest in
Docker — is even more universal than the task). Weak second: **operate a stateful
external system and read the state back** (tau-bench's mock DB, TheAgentCompany's
real services, AIOpsLab's cluster) — consensus on shape, not implementation. A
third, smaller cluster is **make a judgement call with no artefact**. Everything
else is a single repo's private invention.
*Source: `notes/evals/_CROSS_CUTTING.md` §1.7.*

**C5 — What appears in postmortems but in no benchmark?**
Nine gaps: alert triage from a raw payload; **reconciliation across tools** (every
benchmark has exactly one source of truth); stale documentation as a hazard (every
document handed to an agent is authoritative — while four repos' own READMEs are
stale); ambiguity in the request (terminal-bench CI *enforces* unambiguity;
TheAgentCompany's fake user says *"YOU SHOULD NEVER ASK FOR HUMAN HELP"*);
blocked-on-human; cost of being wrong (a wrong answer scores identically to no
answer everywhere); communication as a deliverable; rollback under time pressure
(AIOpsLab's 14 mitigation problems are the entire coverage); and in-episode
progress measurement.
*Source: `notes/evals/_CROSS_CUTTING.md` §8.*

**C6 — Verifiable definition of done, per task type?**
Four kinds: **state-based** (SWE-bench, commit0, terminal-bench, SWE-Lancer IC,
tau-bench's whole-DB SHA-256, AIOpsLab mitigation, TheAgentCompany);
**answer-based** (AIOpsLab detection/localization/analysis, SWE-Lancer manager,
tau-bench `outputs`); **LLM-judged** (TheAgentCompany 53/175; AIOpsLab opt-in);
**human-judged** (vivaria only). Binary vs graded splits the corpus nearly evenly,
and the most considered partial-credit formula is TheAgentCompany's
`0.5·(result/total) + 0.5·⌊result/total⌋` — it rewards progress without letting
"almost done" look like "done".
*Source: `notes/evals/_CROSS_CUTTING.md` §2.2.*

---

## D. Input documents and context

**D1 — What does a real engineer read?**
In order: alert payload → runbook (reached via the `runbook_url` annotation) →
dashboards → deploy/change history → prior postmortems → service catalog for
ownership → Slack thread → ADRs for "why is it like this". Published runbook
structures differ — PagerDuty/Limoncelli's seven sections; GitLab's Symptoms →
Pre-checks → Resolution → Post-checks → Rollback; kube-prometheus's Meaning /
Impact / Diagnosis / Mitigation; AWS SSM's executable YAML. ADRs follow Nygard's
five sections or MADR, whose front matter carries `date` and a supersession
pointer.
*Source: `notes/domain/D_input_documents.md` §D1, §D2, §D4.*

**D2 — Authoritative versus stale, and how does a human tell?**
Only three reliable staleness signals appear in primary sources: **execution**
(does the command still work?), **reference integrity** (does the host/flag/URL
still exist?), and **explicit metadata** (MADR's `date` plus `status:
superseded`). Everything else is judgement. Confluence is the one tool in the MCP
corpus exposing staleness *as tools* — page history, page diff, page views. The
authoritative statement is Google's: *"Details in playbooks go out of date at the
same rate as production environment changes."* The corpus disagrees with itself on
the remedy: some Google SREs want general playbooks that change slowly, others
step-by-step ones that drive down MTTR — the more prescriptive the playbook, the
larger the MTTR win **and** the faster the decay.
*Source: `notes/domain/D_input_documents.md` §D5(b); `notes/mcp/_TOOL_INVENTORY.md` Overlap 11.*

**D3 — What do real alert payloads look like?**
Alertmanager is the reference schema (`version, groupKey, truncatedAlerts, status,
receiver, groupLabels, commonLabels, commonAnnotations, externalURL,
notification_reason` plus per-alert `status, labels, annotations, startsAt,
endsAt, generatorURL, fingerprint`), with the de-facto convention
`annotations.{description, runbook_url, summary}` + `labels.severity`. Grafana is
a superset; PagerDuty PD-CEF requires `summary`/`severity`/`source`; Opsgenie
requires `message` with P1–P5 defaulting to P3. **Datadog has no fixed payload at
all** — the body is composed from `$`-variables, so its shape is per-installation
and no schema-based parser can be written. Only Prometheus and Grafana share a
vocabulary, and only they carry a runbook link as a first-class convention.
*Source: `notes/domain/D_input_documents.md` §D3.*

**D4 — How much is not written down?**
**NO QUANTITATIVE SOURCE FOUND.** The qualitative evidence is specific: Reddit's
Pi-Day route-reflector config was *"committed nowhere"* and its authors had left;
GitHub's cluster-restore was documented and tested daily yet *"until this incident
we have never needed to fully rebuild an entire cluster from backup"*; Atlassian
had playbooks *"but not for the events of this scale"*. Treat it as a documented
recurring condition, not a measurable fraction.
*Source: `notes/domain/D_input_documents.md` §D5(a).*

---

## E. Tools and integrations

**E1 — Which tools does the domain use?**
Ten MCP servers, read at pinned commits, expose **596 tools**: GitHub 116, Grafana
105, PagerDuty 103, Atlassian 98 (63 Jira + 35 Confluence), reference servers 58,
Sentry 53, Kubernetes 52, Elasticsearch 5, Snyk 4, Figma 2. Categories: source
control, code review, issue tracking, **CI/CD (only 4 GitHub Actions tools + 6
opt-in Tekton tools in the entire corpus)**, observability, error tracking,
incident/on-call, security scanning, knowledge base, Kubernetes.
*Source: `notes/mcp/_TOOL_INVENTORY.md` §Server summary.*

**E2 — What do the MCP servers expose?**
Names, arguments and return shapes are catalogued per server in
`research/notes/mcp/*.md`. Three counts are not what they look like: **Sentry
advertises only 9 of its 53 tools** (44 are catalog-only, reachable via
`search_sentry_tools` → `execute_sentry_tool`); **Kubernetes ships 2 of 8 toolsets
by default**; and **Snyk's real surface has moved out of the repo**, leaving four
evidenced names.
*Source: `notes/mcp/_TOOL_INVENTORY.md` §Server summary.*

**E3 — Where is the MCP surface narrower than reality?**
Ten recurring patterns. Sharpest: **no remediation anywhere** — across ten servers
nothing can dismiss a security alert, file an exception, or open a fix PR from a
finding; security scanning is 100% read. Kubernetes omits the operational verbs
(no port-forward, `rollout`, cordon/drain, helm upgrade/rollback). Elasticsearch
exposes no writes. And **GitHub gates by scope at registration**, so an
under-scoped token makes tools *vanish* — an agent cannot distinguish "not
permitted" from "not supported".
*Source: `notes/mcp/_TOOL_INVENTORY.md` §E3.*

**E4 — Which tools overlap with different values?**
Thirteen documented overlaps. The three that matter most: *"What version is
actually running?"* — GitHub, Sentry, Kubernetes, Grafana annotations, Helm and
PagerDuty change events each record it at a different moment by a different actor,
**rollbacks break all of them**, and the running image tag is the only ground
truth and the one an agent is least likely to check. *"Is there an active
incident, and is it customer-facing?"* — **"customer-facing" exists only on the
status page; no incident object carries it.** *"Who is this person?"* — identity
has no shared key; email is the only plausible join and differs per system.
*Source: `notes/mcp/_TOOL_INVENTORY.md` Overlaps 5, 7, 13.*

**E5 — Where does data live outside a system of record?**
The inventory answers by absence: across ten servers there is **no Slack, no CI
beyond Actions and Tekton, no Terraform, no feature flags, no ownership/CODEOWNERS
lookup, and no spreadsheet**. Ownership in particular lives simultaneously in an
escalation policy, a CODEOWNERS file, a Jira component and a wiki table — *"and
these four disagree routinely"*. That absence is exactly where the
outside-the-system-of-record pressure comes from.
*Source: `notes/mcp/_TOOL_INVENTORY.md` §Notes; Overlap 9.*

**E6 — Real auth, rate-limit and pagination behaviour?**
Wildly inconsistent, and the inconsistency shapes how an agent must call them.
Pagination: Sentry runs **three coexisting schemes**, including a hard
`RESULT_LIMIT = 25` with a `hasMore` boolean **and no cursor**; Kubernetes and
Elasticsearch have **no pagination, no limit, no truncation at all**. Rate limits:
essentially nobody retries or backs off — Figma classifies retryable statuses *for
telemetry only*, Sentry renders a 429 as an *Input Error*. Truncation: Grafana
**errors above 10 MB instead of truncating**. Error shapes: Snyk signals "found
issues" with **exit code 1**; Atlassian's `confluence_get_page` returns failure as
ordinary data with **no `isError` flag**.
*Source: `notes/mcp/_TOOL_INVENTORY.md` §E6.*

---

## F. Chaos

**F1 — Documented ways the data is inconsistent.**
Thirty numbered scenarios in six themes: service-name drift (Datadog's own docs
concede a pod can carry *both* `env` tags, and an unlabelled service silently
takes a `service` name derived from its Docker image); environment naming (GitLab
issue 377916 — a job named `nonprod` is classified **production tier** by a
substring-matching regex); metrics that legitimately disagree (`rate()`
extrapolates; averaging per-host p99s can report 550 ms where the fleet p99 is
1,000 ms; Stripe's dual-write migration deferred reconciliation entirely);
duplicate trackers (10–40% duplicate rates, **28.9% / 36.6% / 50.8%** with
inconsistent severity); orphaned alerts and dashboard sprawl; and tool sprawl as
substrate (>100 SaaS apps per company; mean **5.1** monitoring tools, **86%**
running two or more).
*Source: `notes/domain/F_chaos_scenarios.md` §F1, CS-01…CS-30.*

**F2 — Which reconciliation questions require joining tools?**
Six, each a task candidate. *"How many customer-facing incidents last week?"*
needs incidents ∪ status page ∪ severity convention ∪ a definition of
customer-facing ∪ a week boundary — **all five contested**, and the status page
systematically lags internal state. *"What changed before this incident?"* —
Cloudflare's Nov-2025 outage is canonical: the trigger was a **ClickHouse
permissions change** unrelated to the failing Bot Management proxy, and the first
hypothesis was a DDoS. Also *"Which services are affected by CVE-X?"* (Log4Shell /
CSRB), *"Was that a SEV1?"*, *"What's our MTTR?"* (the VOID recommends retiring
it: duration is positively skewed and **has no correlation with severity**), and
*"Are our postmortem action items done?"*
*Source: `notes/domain/F_chaos_scenarios.md` §F2, CS-18…CS-23.*

**F3 — What ambiguity exists in the request itself?**
"This week" has at least four defensible answers, demonstrable from SQL engine
docs: ISO 8601 starts Monday; BigQuery `DATE_TRUNC(WEEK)` defaults to **Sunday**;
Snowflake defaults to Sunday but obeys the session parameter `WEEK_START`;
PostgreSQL starts **Monday**. Timezone is per-dashboard and per-monitor, not
global — Datadog monitors use UTC and do not track local zones by default. And
**"does a rolled-back deploy count?"** has **NO SINGLE AUTHORITATIVE RULING**:
DORA counts the rollback as evidence of a failed deployment, but tools differ on
whether the rollback deploy itself increments deployment frequency.
*Source: `notes/domain/F_chaos_scenarios.md` §F3, CS-24…CS-27.*

**F4 — What traps punish an agent that trusts a single source?**
Ranked by how cheaply they fool a plausible agent: trusting the service catalog
for what is running (catalog YAML validates even when the owner team no longer
exists); the status page for customer impact; one metrics backend for a count; the
failing service's deploy log to find the change; the tracker's severity field;
**`grep prod`** — `nonprod` matches; an alert's existence as evidence the service
exists; one spelling of an OTel attribute when dual emission is the *recommended*
migration state; an SBOM as the running inventory; and the mean.
*Source: `notes/domain/F_chaos_scenarios.md` §F4.*

**F5 — Realistic versus merely cruel chaos.**
The working test: **chaos is realistic when a competent human would also have to
do extra work AND the resolution path is discoverable from inside the
environment.** Keep: one service under three names *where a mapping exists
somewhere*; two metrics systems disagreeing for documented reasons; ambiguous
week/timezone boundaries whose defaults are inspectable; a *detectably* stale
runbook. Avoid: a mapping that exists only in a human's head; ambiguity with a
hidden correct answer and no way to detect it; randomised tool failures unrelated
to difficulty; and **data withheld rather than data conflicting**. The empirical
support is that every best-documented real failure is a *conflict* failure, not a
*missing data* failure; the "cruel" list itself is labelled a design principle
with no source.
*Source: `notes/domain/F_chaos_scenarios.md` §F5.*

---

## G. Evaluation design

**G1 — How does each benchmark verify?**
By frequency: **test execution in a container** (6 repos — identical shape
everywhere: `git reset` → apply diff → run a fixed command → parse stdout →
compare against stored test IDs); **state inspection** (4); **exact answer match**
(3); **LLM judge inside the score** (2); **human scoring** (vivaria only). Two are
worth copying: tau-bench re-runs the *gold actions* from a clean DB and compares
SHA-256 hashes — it never compares action sequences, so any path to the right
world is accepted, at the cost of one function; AIOpsLab takes the opposite trade
with per-problem `kubectl` assertions and its own code admits this does not scale.
The shared fragility is log parsing: SWE-bench ships 57 hand-written regex parsers
under the comment *"# TODO: This is very brittle, we should do better"*.
*Source: `notes/evals/_CROSS_CUTTING.md` §2.*

**G2 — What do they do about flakiness, and what does that tell us?**
Two philosophies, split by whether the verifier touches a network. *Make it
deterministic and trust one run*: commit0 (content-addressed images keyed on a
SHA-256 of the setup script, pinned platform and linters), SWE-bench (no
instance-level retry anywhere), terminal-bench (version pinning as an authoring
criterion). *Assume it is flaky*: SWE-Lancer runs the E2E suite 3× and passes if
any run passes; vivaria retries and **excludes retry time from the budget**. The
lesson is that flakiness is a property of the *verifier* — and the corpus's own
own-goal is that **tau-bench's user simulator has no temperature argument at
all**, inheriting the provider default 1.0 while the agent runs at 0.0.
*Source: `notes/evals/_CROSS_CUTTING.md` §5.*

**G3 — What metrics do they report, and what does each miss?**
`% Resolved` = F2P and P2P both 1.0 — SWE-bench computes a PARTIAL status then
**discards it**. terminal-bench's `accuracy = n_resolved / len(results)` counts
**trials, not tasks**, and folds infrastructure failures in as zeros. commit0's
average pass rate is an **unweighted mean over repos**, so a 38-test repo counts
as much as a 40,433-test one. tau-bench uses `pass^k` (decreasing, all must
succeed) where terminal-bench uses `pass@k` (increasing) — the corpus's sharpest
methodological disagreement. Three metrics measure something other than
correctness and all are worth copying: commit0 puts **test duration** on the
leaderboard; SWE-Lancer's canonical metric is **dollars earned** over ~$500K of
real Upwork payments — the only metric tied to business value; vivaria records
`secondsToScore`, the only measurement of what grading costs.
*Source: `notes/evals/_CROSS_CUTTING.md` §5.3, §6.3.*

**G4 — What reward hacking have they observed or guarded against?**
Observed, not hypothetical: commit0's code comment records agents exploiting git
history to retrieve original implementations, hence `--depth 1` and
`git remote remove origin`; SWE-bench scrubs tags and reflog and *asserts* no
commit survives past the base commit. Isolation-by-ordering is the strongest
guard — terminal-bench copies tests in only **after** the agent stops, which makes
static readable tests safe. Both encryption schemes in the corpus are theatre and
both repos admit it. The unguarded surfaces are named: SWE-bench **does not strip
test edits from the model patch** (`NON_TEST_EXTS` is dead code); tau-bench's
`outputs` grading is a case-insensitive **substring** match over bare small
integers. External work bounds the problem: SWE-MERA reports **32.67% of
successful patches involve direct solution leakage and 31.08% pass due to
inadequate test cases**.
*Source: `notes/evals/_CROSS_CUTTING.md` §4; `notes/domain/F_chaos_scenarios.md` §F6.*

**G5 — How do they separate environment failure from model failure?**
The most important finding in the corpus, and it splits along the
benchmark/infrastructure line. **All seven benchmarks have a richer failure
vocabulary than their headline metric uses** — terminal-bench's 11-value
`FailureMode`, SWE-bench's 7 buckets, tau-bench's `FaultAuthor{USER, AGENT,
ENVIRONMENT}`, commit0's 8 log sentinels — and every one is discarded when the
number is computed. **vivaria is the reference implementation**: `ErrorSource =
['agent','server','task','serverOrTask','user','usageLimits']` is typed onto every
fatal error; run status is *derived from it in SQL* so taxonomy and metric cannot
drift; the agent may claim only `agent` or `task`, never `server`; the ambiguous
case is preserved as a value in the enum; and `PYHOOKS_RETRY`/`SCORING` pauses
**remove infrastructure time from the agent's budget**. SWE-agent is runner-up,
with `exit_environment_error` and `exit_api` as distinct states and `early_exit`
runs deleted and re-run. The corpus offers only two benchmark behaviours, both
biased: infra failure counts as model failure (pessimistic, six repos), or
silently drops out of the denominator (optimistic and unfalsifiable,
TheAgentCompany, by accident). **No benchmark reports a third number.**
*Source: `notes/evals/_CROSS_CUTTING.md` §3.*

**G6 — What is the task-generation process?**
It ranges from fully automated to fully manual. **SWE-bench is automated**: keep
only merged PRs that close ≥1 issue, have a non-empty non-test patch, a non-empty
problem statement and a test patch; Lite then applies seven human-chosen filters
and samples 300. **terminal-bench is human-authored** through a wizard, then
LLM-checked against 11 criteria and CI-gated by oracle-must-pass /
nop-must-fail. **AIOpsLab is entirely hand-written**, with 12 problem IDs
commented out because their injectors are broken. **tau-bench is hybrid** —
schemas human-designed, seed strings GPT-generated, composition code-generated,
because *"code-based database construction is more reliable than GPT-based"* — and
its train split is explicitly `annotator="synthetic"`. **TheAgentCompany is 175
hand-written evaluator/checkpoint pairs**; **vivaria outsources authoring
entirely**.
*Source: `notes/evals/princeton-nlp__SWE-bench.md` §1.5–1.6;
`notes/evals/laude-institute__terminal-bench.md` §2.10;
`notes/evals/microsoft__AIOpsLab.md`; `notes/evals/sierra-research__tau-bench.md`;
`notes/evals/METR__vivaria.md` §1.2.*

---

## H. Difficulty and calibration

**H1 — What pass rates exist?**
terminal-bench's adapter parity files are the richest anchor set, since one agent
is measured across many benchmarks: SWE-bench Verified 66.4% / 67.0% / 53.1%;
SWE-Lancer Diamond 49.0 ± 2.86; USACO 74.7; Aider polyglot 34.2; AppWorld dev 52.1
with claude-opus-4 and **exactly 0.0 ± 0.0 with codex/o4-mini on 57 tasks**;
AlgoTune 30.5; Cybench 19.4; QuixBugs 80.8; SWE-Perf 81.4. SWE-Lancer splits 51.5%
IC vs 47.2% manager. tau-bench is the only leaderboard committed to a repo: retail
0.692 `pass^1` → **0.462 `pass^4`**; airline 0.460 → 0.225. Six of eight scoreable
repos ship no results at all; AIOpsLab publishes nothing.
*Source: `notes/evals/_CROSS_CUTTING.md` §6.1–6.2.*

**H2 — What makes a task flaky for a model rather than simply hard?**
Reliability sits far below capability — a third of tau-bench retail's apparent
capability is coin-flips. Error bars are large and usually unreported:
SWE-Lancer's ±2.86 pp on n=463 means any two systems within ~6 pp are
indistinguishable, and only terminal-bench records `std_error`. The documented
boundary conditions producing partial success are budget- or context-shaped:
tau-bench's 30-step cap means an episode whose simulated user never emits
`###STOP###` **never calls `calculate_reward()` and silently keeps its 0.0
initialiser** (two such records exist in the shipped results); SWE-Lancer manager
tasks with >17K-character instructions **silently fail by overflowing the tmux
buffer**.
*Source: `notes/evals/_CROSS_CUTTING.md` §3.5, §5.4, §6.2.*

**H3 — Where do agents actually go wrong?**
Manual analysis of 243 failed attempts across 900 trials on SWE-bench Verified
finds **strategy formulation and logic synthesis is the most error-prone stage,
then problem understanding, and localization has the *lowest* failure rate** —
agents find the right file and then do the wrong thing to it. SWE-agent's
15-value `exit_status` separates `exit_forfeit` (gave up), `exit_command_timeout`,
`exit_context`, `exit_format` and `exit_environment_error`. MAST catalogues 14
multi-agent failure modes in three categories, the third being **task
verification** — agents that do not verify, or verify the wrong thing. Google's
troubleshooting chapter names the human versions that map almost one-to-one: wild
goose chases, unsafe hypothesis testing, *"wildly improbable theories"*, spurious
correlation mistaken for causation.
*Source: `notes/domain/F_chaos_scenarios.md` §F6; `notes/evals/_CROSS_CUTTING.md` §3.2;
`notes/domain/B_stakeholders_workflow.md` §B1.3.*

**H4 — How do we deepen an easy task honestly?**
Two quantitative answers and one constraint. commit0 characterises difficulty as
**(number of functions to write, spec token count)** — a mechanical, pre-run
estimate. terminal-bench requires `expert_time_estimate_min` and
`junior_time_estimate_min` on every task (45 and 180 minutes for a `medium`), a
human-effort anchor; it stores no human pass rate. The constraint is F5: added
difficulty must stay **discoverable from inside the environment**, so the honest
levers are more tool calls, more services, more ambiguity and a longer horizon,
and the dishonest lever is withholding data. A fourth lever the corpus does not
name but our world uses is **removing procedure from the prompt while keeping it
in the knowledge base** — turning instruction-following into discovery without
adding tedium.
*Source: `notes/evals/commit-0__commit0.md` §6;
`notes/evals/laude-institute__terminal-bench.md` §1.7;
`notes/domain/F_chaos_scenarios.md` §F5; `README.md` §"Instruction design".*

---

## Round 2 — what we actually built

Shipped: **53 tables, 1,181 rows, 72 tools, 68 tasks** across 11 categories (7
Horizon-SWE + 3 AIOpsLab-style + reconciliation), 38 repo files, 417 commits, 30
documents, split 55 train / 13 heldout, difficulty 2 easy / 29 medium / 24 hard /
13 expert (`world/world.json`).

**R1 — Which of our tasks has no analogue in the corpus?**
Three. (a) The **five reconciliation tasks** — no benchmark requires joining
sources that *contradict each other*; C5 gap #2 states every benchmark has exactly
one source of truth. (b) **Graded ordering constraints over an append-only audit
log** — staging before production, canary ≤25% before promote, code deployed
before its flag is enabled, alert acknowledged before resolved. The automation
corpus proposes exactly this as verifier check V24 ("the post-mortem is created
**before** the incident is resolved") and **no benchmark implements it**. (c) The
**`assumption_recorded` check** — C5 gap #4 records that no benchmark rewards
handling ambiguity. This is a novel contribution rather than an invention because
each maps to a documented real question: CS-18, CS-08/CS-10, CS-11/CS-12, CS-06,
CS-05.
*Source: `notes/evals/_CROSS_CUTTING.md` §8; `notes/automation/_WORKFLOW_PATTERNS.md`
§4.1 V24; `build/task_specs.py` reconciliation suite.*

**R2 — Which corpus task types have we no coverage of?**
Eight. **Alert triage from a raw payload** — we have an `alerts` table but no
PD-CEF- or Alertmanager-shaped payload, so none of CS-28's grouping / silence /
`truncatedAlerts` semantics. **Postmortem writing** — named in A4 as one of the
five surviving agent-shaped jobs, absent from all 68 tasks. **Converting a novel
alert into a runbook.** **Rebuild a library from its spec** (commit0). **Choose
among human-written proposals** — SWE-Lancer's manager split is 265 of 463 tasks,
deterministic, flake-free and *harder* than the IC tasks (47.2% vs 51.5%); we have
zero. **Multi-turn conversation with a stakeholder who reveals requirements only
when asked** (tau-bench). **Human/rubric-scored tasks** (vivaria). **Security
exploitation / CTF.**
*Source: `notes/evals/_CROSS_CUTTING.md` §1.4, §1.6, §8; `build/task_specs.py`.*

**R3 — Where does our chaos differ from documented real chaos?**
Two structural differences and a coverage gap. It is **authored from the CS-##
catalogue rather than harvested** — `build/vendors.py` names the research file and
tags each conflict with its CS number, so every conflict is traceable, but none
was observed by us in the wild. And it is **quarantined**: `service_aliases`,
`owner_spreadsheet`, `local_deploy_log`, `issue_links`, `prom_series`,
`sentry_issues`, `status_page_posts` and `pd_incidents` are referenced by **zero**
non-reconciliation verifiers, so 63 of 68 tasks run against a clean single-source
world. We implement CS-01, CS-05, CS-06, CS-08/CS-10 (counter reset plus 25%
Sentry sampling), CS-11/CS-12 and CS-18. We do **not** implement CS-28 (alert
grouping, inhibition, silences, `truncatedAlerts`), CS-03/CS-04 (OTel dual
emission), CS-13/CS-14 (orphaned monitors, dashboard rot), CS-20 (CVE
reachability), CS-22 (MTTR over a skewed distribution), CS-25 (per-dashboard
timezone), or CS-26 — our deploy-count task *tells* the agent to exclude
rollbacks rather than leaving the genuine ambiguity in place.
*Source: `build/vendors.py` header; `build/tasks_def.py`;
`notes/domain/F_chaos_scenarios.md`.*

**R4 — Where does our MCP surface diverge, and does it matter?**
We ship **72 tools** against **596** across ten real servers, and the names
deliberately mirror the originals (`jira_search`, `query_prometheus`,
`pd_list_incidents`, `sentry_search_issues`, `confluence_search`), so vocabulary
should transfer. Four divergences matter. **No pagination, rate limits, truncation
or per-server error idioms** — E6 shows these are wildly inconsistent in reality
and directly shape how an agent must call a tool; our uniform surface trains none
of it. **We do not model tools that vanish** — GitHub and Kubernetes hide writes
the token cannot perform, so "not permitted" and "not supported" are
indistinguishable. **We expose write paths the real corpus lacks** —
`resolve_alert`, `publish_status_update`, `set_feature_flag`,
`shift_endpoint_traffic`; security remediation in particular is 100% absent from
all ten servers. And **`read_owner_spreadsheet` / `query_local_deploy_log` have no
MCP analogue anywhere** — deliberately, since E5's pressure comes precisely from
data outside the system of record. Net: names and shapes transfer; **calling
discipline does not**.
*Source: `notes/mcp/_TOOL_INVENTORY.md` §E3, §E6, §Notes; `world/tools.json`.*

---

## What the research changed

| Decision | The finding that forced it |
|---|---|
| Never render a "DORA tier" gauge; treat the set as **five** metrics; never equate "MTTR" with a DORA metric | 2024 was the last four-tier report; 2025 replaced tiers with seven archetypes and per-metric buckets. MTTR was **renamed and redefined in 2023** as *failed deployment recovery time*, scoped strictly to change-induced impairment, and *deployment rework rate* was added in 2024 — so an agent measured on "MTTR" over generic incidents is not measuring DORA. (`notes/domain/A_business_value.md` §A1) |
| Adopt a typed error source as the model for environment-vs-model attribution | vivaria's `ErrorSource = ['agent','server','task','serverOrTask','user','usageLimits']`, derived into run status **in SQL** so the taxonomy cannot drift from the metric; the agent may never claim `server`; the honestly ambiguous case is a value in the enum. (`notes/evals/_CROSS_CUTTING.md` §3.1) |
| Do not trust a failure taxonomy to survive to the metric — wire it to the score or it is decoration | All seven benchmarks build one and discard it: terminal-bench computes an 11-value `FailureMode`, then `accuracy = n_resolved / len(results)` ignores it, so `AGENT_INSTALLATION_FAILED` counts as a model failure. (`notes/evals/_CROSS_CUTTING.md` §3.3) |
| Chaos must be **discoverable, not hidden** — every conflict resolves from evidence inside the world | F5's test: realistic chaos is what a competent human would also have to work through, with the resolution path present. Reality is *contradictory*, not *absent*; every best-documented real failure is a conflict failure. (`notes/domain/F_chaos_scenarios.md` §F5) |
| Treat a nonzero environment-failure rate as a harness bug; gate on an oracle | The rate is first-order: **AlgoTune's oracle passes only ~85%**; **3 SWE-bench Verified tasks fail with the oracle agent**, named individually; SWE-Lancer dropped 39 IC problems for needing internet; >17K-char manager instructions silently overflow tmux. (`notes/evals/_CROSS_CUTTING.md` §3.5) |
| Grade **state**, not trajectory — verifiers are SQL over the final DB plus an ordering log | tau-bench re-runs gold actions from a clean DB and compares hashes rather than action sequences: any path to the right world is accepted, at the cost of one function. (`notes/evals/_CROSS_CUTTING.md` §2.4) |
| Keep policy out of the prompt and in the knowledge base | The 3× playbook MTTR win plus *"playbooks go out of date at the same rate as production environment changes"* make documentation both load-bearing and decaying; an agent that never reads it should fail. (`notes/domain/D_input_documents.md` §D2, §D5) |
| Score the **ordering** of side effects, not just end state | The automation corpus's V24 (approval before merge; postmortem before resolution) is asserted by shipped harnesses and implemented by no benchmark. (`notes/automation/_WORKFLOW_PATTERNS.md` §4.1) |
| Ship negative controls and an adversarial verifier audit | SWE-bench does not strip test edits from the model patch (`NON_TEST_EXTS` is dead code) — the largest unguarded surface in the corpus; commit0's code records agents exploiting git history. (`notes/evals/_CROSS_CUTTING.md` §4.2, §4.6) |
| Weight the world by the real tool distribution; reproduce read/write asymmetry | GitHub, Grafana, PagerDuty and Atlassian carry ~70% of 596 tools; observability is ~85/20 read-heavy; security scanning is 100% read with no remediation path at all. (`notes/mcp/_TOOL_INVENTORY.md` §Notes) |

---

## Open questions and known weaknesses

1. **No model has been run, so difficulty is uncalibrated.** Everything we know
   comes from scripted baselines (`oracle` 100% PF, `naive` 30%, `merged_only`
   32%, `no_verify` 83%, `shortcut` 89%), and the README concedes these "do not
   calibrate against the blog's reported ~25.5% for a real model". The corpus
   supports the caution: the observed range across benchmarks is 0% to 81%, and
   AppWorld scores **exactly 0.0 ± 0.0** for one capable model on 57 tasks.

2. **Our chaos is authored, not harvested.** Every conflict traces to a CS-##
   scenario rather than to an incident we observed, so the *distribution* of chaos
   is ours, not reality's. We have nothing equivalent to danluu/post-mortems'
   ~200 real cases or the VOID's ~10,000 incidents behind our choices.

3. **Chaos is quarantined to 5 of 68 tasks.** Zero non-reconciliation verifiers
   touch any vendor table, so 63 tasks run in a world where every fact has one
   source. The world *contains* multi-tracker duplicates and a stale owner
   spreadsheet; almost nothing *makes an agent care*.

4. **Only 1 of 5 localization tasks requires true cross-service reasoning.** The
   `shortcut` baseline — which names whichever service the alarm names — scores
   **80%** there. Only `tsk_localize_checkout_latency` (checkout's p99 breaches
   because *payments* blocks on a 30s downstream timeout) demands the join. That
   is the wrong shape given the finding that **localization has the lowest failure
   rate** of any stage for modern agents: the category rewards what models already
   do well.

5. **The reconciliation `consulted_X` check reads the agent's own `sources`
   string, not the trace.** `_used(qid, system)` tests whether a system name
   appears in the submitted payload, so an agent can name a system it never
   queried. The audit log already backs `_mutating_calls()`; this check should be
   derived from read calls in `audit_events`.

6. **`_answer_num` reproduces tau-bench's substring-match weakness.** It takes the
   first numeric token from the answer, and three of five expected answers are `1`
   or `2` — a guesser passes `answer_correct` the way an enumerating agent passes
   tau-bench's `outputs=["10"]` tasks. The `assumptions` and `sources` checks are
   the only defence, and per (5) both are self-declared.

7. **Our own README is stale — the exact hazard the research documents.** It says
   "50 tasks", then "all 62 tasks", then "63 tasks", with 41/9 train-heldout and
   23 medium / 16 hard / 11 expert, while `world.json` says **68 tasks, 11
   categories, 55/13, 2/29/24/13** and lists a `reconciliation` category the
   README's table omits. This is precisely what `_CROSS_CUTTING` §0.1 catalogues in
   four benchmark repos; we now demonstrate it on ourselves.

8. **We named vivaria's `ErrorSource` as the model and have not implemented it.**
   The verifier emits `passed` plus a weighted score; there is no error-source
   enum, no `environment_failed` bucket, no third number, and no equivalent of
   `PYHOOKS_RETRY` to keep harness time off the agent's clock. The corpus's single
   strongest recommendation is currently a design note, not code.

9. **No repeated-sampling metric.** We report a binary `passed` and a composite
   score from one run. tau-bench's own numbers (0.692 → 0.462) show a third of
   apparent capability is noise; for production-shaped work `pass^k` is correct.

10. **No blocked-on-human terminal state, and no reward for asking.** B5 and C5
    gap #5 identify this as a real gap in the field, and we reproduce it. We reward
    *recording an assumption*, the weaker half; the stronger half — asking a
    bounded clarifying question before mutating state — is unmodelled.

11. **Cost of being wrong is unmodelled.** Every wrong answer scores like no
    answer (C5 gap #6), despite A3 ranking a leaked secret orders of magnitude
    above a wasted engineer-hour. SWE-Lancer's dollar weighting is the only
    published gesture at this, and it weights *success*, not *harm*.

12. **No alert payload realism.** D3 catalogues six schemas with disjoint field
    names and one (Datadog) with no fixed schema at all; our `alerts` table is a
    single internal shape. An agent trained here will never have met
    `truncatedAlerts`, `dedup_key`, or a `$`-variable-composed Datadog body.

13. **One thing we did get right and should not lose:** the `hint` field in
    `task_specs.py` is consumed **only by the oracle's PR body**, never by the
    agent-facing instruction — the same discipline as SWE-bench's `hints_text`,
    which is collected and never used at eval time
    (`notes/evals/princeton-nlp__SWE-bench.md` §3.2).
