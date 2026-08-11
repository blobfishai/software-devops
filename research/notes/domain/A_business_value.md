# A. Domain and business value

Answers **A1–A4** of `00-QUESTIONS.md`.

> **Headline correction to a stale premise in the brief.** There is no *current*
> DORA elite/high/medium/low benchmark. **2024 was the last four-tier report;
> the 2025 report replaced tiers with seven team archetypes plus per-metric
> distribution buckets.** Also: the "four keys" are now **five** metrics, and
> "time to restore service / MTTR" was **renamed and redefined** in 2023. Any
> artefact we build that shows a "DORA tier" gauge is behind the research.

---

## A1. DORA metrics — current definitions, the renames, and the benchmarks

### Current canonical definitions (verbatim, primary source)

From [dora.dev/guides/dora-metrics/](https://dora.dev/guides/dora-metrics/),
split into **throughput** and **instability** groups:

| Metric | DORA's definition (verbatim) | Group |
|---|---|---|
| **Change Lead Time** | *"The amount of time it takes for a change to go from committed to version control to deployed in production"* | Throughput |
| **Deployment Frequency** | *"The number of deployments over a given period or the time between deployments"* | Throughput |
| **Change Fail Rate** | *"The ratio of deployments that require immediate intervention following a deployment. Likely resulting in a rollback of the changes or a 'hotfix'"* | Instability |
| **Failed Deployment Recovery Time** | *"The time it takes to recover from a deployment that fails and requires immediate intervention"* | Instability |
| **Deployment Rework Rate** | *"The ratio of deployments that are unplanned but happen as a result of an incident in production"* | Instability |

The fifth metric is documented on
[dora.dev/guides/dora-metrics-four-keys/](https://dora.dev/guides/dora-metrics-four-keys/)
— **note the irony that the page titled "four keys" itself documents five.**

### The renames, dated and sourced

- **2023 — MTTR was renamed and redefined.** *"The metric historically known as
  'mean time to recover (MTTR)' or 'time to restore service' was renamed and
  redefined as failed deployment recovery time."* Rationale: prior definitions
  did not distinguish a failure caused by a software change from one caused by
  external factors such as a data-centre outage; the new definition is scoped
  strictly to **change-induced** impairment
  ([dora.dev/insights/dora-metrics-history/](https://dora.dev/insights/dora-metrics-history/)).
- **2024 — rework rate was added.** *"DORA researchers identified that change
  failure rate... acted as a proxy for the amount of rework a team must perform.
  To test this, they introduced a fifth metric: deployment rework rate."* (same)

**Consequence for agent design (important):** change fail rate and failed
deployment recovery time are now **deployment-scoped, not incident-scoped**. An
agent measured on "MTTR" against generic incidents **is not measuring the DORA
metric**. This is a live ambiguity trap — see F/CS-26.

### The 2024 benchmark table (the last four-tier one)

| Level | Deployment frequency | Change lead time | Change failure rate | Failed deployment recovery time |
|---|---|---|---|---|
| Elite | On demand | Less than a day | 5% | Less than an hour |
| High | Daily to weekly | 1 day to 1 week | **20%** | Less than a day |
| Medium | Weekly to monthly | 1 week to 1 month | **10%** | Less than a day |
| Low | Monthly to biannually | 1 to 6 months | 40% | 1 week to 1 month |

Reproduced from the 2024 DORA report at
[octopus.com/blog/2024-devops-performance-clusters](https://octopus.com/blog/2024-devops-performance-clusters)
— **secondary (vendor blog); the 2024 report PDF
([services.google.com/fh/files/misc/2024_final_dora_report.pdf](https://services.google.com/fh/files/misc/2024_final_dora_report.pdf))
exceeded the automated fetch size limit and was not read directly.**
Cross-check at [octopus.com/devops/metrics/dora-metrics/](https://octopus.com/devops/metrics/dora-metrics/).

**The High-vs-Medium change-failure-rate inversion is real, not a transcription
error.** In 2024, High had a *higher* CFR (20%) than Medium (10%) because DORA's
clustering weights throughput over failure avoidance — *"frequent deployments
were more important than fewer failures"*
([rdel.substack.com/p/rdel-68-what-are-the-latest-benchmarks](https://rdel.substack.com/p/rdel-68-what-are-the-latest-benchmarks)).

Gaps between extremes (2024): elite performers deploy **182×** more, with **8×**
lower change failure rates, **127×** faster change lead times, and recover from
a failed deployment **2,293×** faster (Octopus, above). Cluster populations
shifted markedly: High shrank from **31% of respondents in 2023 to 22% in
2024**; Low rose from **17% to 25%**
([newsletter.getdx.com/p/2024-dora-report](https://newsletter.getdx.com/p/2024-dora-report)).

### The 2025 change: tiers retired

- The 2025 report replaced Elite/High/Medium/Low with **seven team archetypes**
  derived from cluster analysis over delivery performance *and human factors*
  (burnout, friction, valuable work)
  ([cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report)).
- Stated plainly by a third party: DORA *"moved away from traditional
  low/medium/high/elite performance designations to per metric buckets"*
  ([faros.ai/blog/key-takeaways-from-the-dora-report-2025](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025)).
- The seven archetypes with population shares: Foundational Challenges 10%,
  Legacy Bottleneck 11%, Constrained by Process 17%, High Impact/Low Cadence 7%,
  Stable and Methodical 15%, Pragmatic Performers 20%, Harmonious
  High-Achievers 20%
  ([splunk.com/en_us/blog/learn/state-of-devops.html](https://www.splunk.com/en_us/blog/learn/state-of-devops.html)).
  **Secondary reproduction of DORA's table; shares sum to 100 and match the two
  archetypes named in the Google Cloud primary. Reliable but not primary.**
- Full 2025 report PDF:
  [services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf)
  (exceeded fetch limit).
- Report index: [dora.dev/research/](https://dora.dev/research/).

### AI's measured effect on delivery — the most relevant finding in this section

- **2024:** a 25% increase in AI adoption was associated with a **1.5% decrease
  in delivery throughput** and a **7.2% reduction in delivery stability**, while
  improving documentation quality (+7.5%), code quality (+3.4%) and code review
  speed (+3.1%). 75% relied on AI for at least one daily responsibility;
  **39% reported little or no trust in AI-generated code**
  ([cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report](https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report)).
- **2025 — the throughput sign flipped, the stability sign did not:** *"a
  positive relationship between AI adoption on both software delivery throughput
  and product performance,"* but *"AI adoption does continue to have a negative
  relationship with software delivery stability."* 90% use AI at work, 80%+
  believe it increased their productivity, **30% report little or no trust in
  AI-generated code**
  ([cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report)).
- Central 2025 thesis: **"AI doesn't fix a team; it amplifies what's already
  there"** — value comes from the surrounding platform, workflow clarity and team
  alignment. 90% of organisations have adopted at least one internal platform.
  (same)
- 2026 follow-on: DORA's *"ROI of AI-assisted Software Development"* models
  first-year adoption cost, learning curves, and a **J-curve** of value
  realisation
  ([cloud.google.com/resources/content/dora-roi-of-ai-assisted-software-development](https://cloud.google.com/resources/content/dora-roi-of-ai-assisted-software-development);
  coverage: [infoq.com/news/2026/05/dora-roi-ai-assisted-dev-report/](https://www.infoq.com/news/2026/05/dora-roi-ai-assisted-dev-report/)).
  Report body not fetched.

**Design implication.** The one consistent, multi-year, direction-stable DORA
finding about AI is that **it degrades delivery stability**. An agent in this
domain enters a space where the state of the art already measurably increases
change failure rate. Guardrails, verification and rollback are not
nice-to-haves — they are the specific failure mode the research names. This is
the strongest argument that our valuable tasks are the **verification and
reconciliation** ones, not the code-writing ones.

---

## A2. What incidents cost, on-call costs, and where engineering time goes

### Cost of downtime — the published spread, and why the sources disagree

- **Gartner's $5,600/minute (~$336,000/hour), 2014.** The most-cited number in
  the field, widely reproduced without attribution, and widely criticised as
  outdated. **NO PRIMARY SOURCE OBTAINED — treat as folklore-grade unless the
  original 2014 Gartner publication is obtained directly. Do not build a
  business case on it alone.**
- **Splunk / Oxford Economics, "The Hidden Costs of Downtime" (June 2024):**
  downtime costs Global 2000 companies **$400 billion annually** — **9% of
  profits**, ~**$200M per company per year**. US $256M, Europe $198M, APAC
  $187M. Per-company components: **$49M revenue impact** (75-day recovery),
  **$22M regulatory fines**, **$19M ransomware/extortion**, **$16M SLA
  penalties**. Stock price falls up to **9%** after a single incident, taking
  **79 days** to recover. Causes: **56% security incidents, 44%
  application/infrastructure**, with **human error the number one cause across
  both**. Methodology: 2,000 executives, 53 countries, 10 industries, with
  Oxford Economics
  ([newsroom.cisco.com/.../conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html);
  [oxfordeconomics.com/resource/the-hidden-costs-of-downtime-the-400b-problem-facing-the-global-2000/](https://www.oxfordeconomics.com/resource/the-hidden-costs-of-downtime-the-400b-problem-facing-the-global-2000/)).
  *Vendor press release, but named independent research partner and disclosed
  methodology. Note Splunk's domain now redirects to Cisco's newsroom.*
- **ITIC 2024 Hourly Cost of Downtime Survey:** *"The average cost of a single
  hour of downtime now exceeds **$300,000** for over **90% of mid-size and large
  enterprises**"*, and **41% say hourly downtime costs $1M to over $5M**,
  exclusive of litigation and penalties. Methodology: **1,000+ firms worldwide,
  Nov 2023 – mid-March 2024**
  ([itic-corp.com/itic-2024-hourly-cost-of-downtime-report/](https://itic-corp.com/itic-2024-hourly-cost-of-downtime-report/)).
  *Self-selected respondent estimates — perception data.*
- **New Relic 2024 Observability Forecast:** median hourly cost of a
  high-business-impact outage **$1.9 million**; **62%** said at least $1M/hour;
  **38%** experience such an outage **at least once per week**; median **MTTR 51
  minutes**, median **MTTD 37 minutes**; median annual downtime **77 hours**;
  median **232 outages per year** across all impact levels
  ([newrelic.com/resources/report/observability-forecast/2024/state-of-observability/outages-downtime-cost](https://newrelic.com/resources/report/observability-forecast/2024/state-of-observability/outages-downtime-cost);
  methodology ~1,700 professionals, 16 countries:
  [newrelic.com/press-release/20241022](https://newrelic.com/press-release/20241022)).
- **PagerDuty 2026 State of AI-First Operations:** **8%** lose **>$1M/hour**
  during unplanned disruptions, **34%** lose ≥$500K/hour, **68%** lose
  >$300K/hour. Non-financial: brand damage 52%, recovery costs 50%, reduced
  productivity 48%, **developer burnout 42%**. 59% actively use AI in operational
  workflows. Methodology: 1,000 director-level+ respondents, seven markets,
  Wakefield Research, March 2026
  ([pagerduty.com/newsroom/2026-state-of-ai-first-operations/](https://www.pagerduty.com/newsroom/2026-state-of-ai-first-operations/)).
- **Uptime Institute Annual Outage Analysis 2025** — *the most methodologically
  sober source here.* *"More than half (**54%**) of the respondents... say their
  most recent significant, serious or severe outage cost more than **$100,000**,
  with **one in five** saying that their most recent outage cost more than
  **$1 million**."* Uptime explicitly warns: *"Data relating to outages should be
  treated skeptically. All methodologies used to track the frequency, severity
  and costs of outages are subject to uncertainty."*
  ([uptimeinstitute.com/uptime_assets/...GA-2025-05-annual-outage-analysis.pdf](https://uptimeinstitute.com/uptime_assets/d7c049ef5b02a6e0a15540a3e5cb8fbf742c7fa54a1af6caeaaab32b7c15d443-GA-2025-05-annual-outage-analysis.pdf),
  read page-by-page from the primary PDF; press release:
  [uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025](https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025);
  landing: [uptimeinstitute.com/resources/research-and-reports/annual-outage-analysis-2025](https://uptimeinstitute.com/resources/research-and-reports/annual-outage-analysis-2025)).

**Reconciliation.** The range spans ~$100K/hour (Uptime, actual most-recent
outage) to $1.9M/hour (New Relic, self-reported high-impact outages among
observability buyers). **They are not measuring the same thing.** Use **Uptime
for a conservative floor** and **New Relic / ITIC for a large-enterprise
ceiling**. Never present them as a single range.

### Outage causes — how much is change- and config-shaped

- **Google SRE, the canonical figure:** *"SRE has found that roughly **70% of
  outages are due to changes in a live system**."*
  ([sre.google/sre-book/introduction/](https://sre.google/sre-book/introduction/))
  **This is the number to use for "how much of reliability risk is
  change-shaped."**
- **Uptime 2025, most recent impactful data-centre outage (n=97):** Power 54%,
  Cooling 13%, Network 12%, IT systems 11%, colocation 3%, third-party 2%, fire
  suppression 2%, fire 1%, infosec 1%. Critically: *"Outages from IT and
  networking issues increased in 2024, totaling **23%** of impactful outages.
  This rise is likely caused by increased IT and network complexity, leading to
  issues with **change management and misconfigurations**."* (Uptime PDF, Fig. 3)
- **Uptime 2025, most common cause of *IT service* outages (n=412):**
  Networking/connectivity **30%**, IT system/software **23%**, Power 18%, none
  10%, third-party IT service (public cloud, SaaS) 8%, cooling 7%, other 4%.
  (Fig. 4) **Note the ranking inverts between the facility layer and the IT
  service layer.**
- **Human error (n=397):** **40%** of organisations had a significant/serious/
  severe IT service outage caused by human error in the past three years. Causes:
  **staff failing to follow procedure 58%**, incorrect processes/procedures 45%,
  installation issues 24%, in-service 19%, insufficient staff 18%, preventative
  maintenance frequency 16%, design/omissions 14%. **Failure-to-follow-procedure
  rose 10 percentage points year over year.** (Fig. 12)
- **Preventability — the strongest single line in this whole file:** *"four in
  five (**80%**) operators believe that better management and processes would
  have prevented their organization's most recent downtime incident... This
  proportion is consistent with previous years' data."* (Fig. 13)
- **Baseline context:** outage frequency and severity are declining for a fourth
  consecutive year; only **9%** of 2024 incidents were serious or severe, *"the
  lowest level recorded by Uptime to date"*; **53%** reported an outage in the
  past three years, down from 60% (2022), 69% (2021), 78% (2020). (Fig. 1)
  **An agent must beat an already-improving trend.**

### On-call burden and alert fatigue

- **Google SRE's hard ceiling:** *"the maximum number of incidents per day is
  **2 per 12-hour on-call shift**"*, justified because *"dealing with the tasks
  involved in an on-call incident—root-cause analysis, remediation, and follow-up
  activities like writing a postmortem and fixing bugs—takes **6 hours**"* on
  average. The distribution *"should be very flat over time, with a likely
  **median value of 0**."*
  ([sre.google/sre-book/being-on-call/](https://sre.google/sre-book/being-on-call/))
  **This is the authoritative, citable on-call load standard — and note that
  most of the 6 hours is follow-up, not remediation.**
- **PagerDuty telemetry-based burnout thresholds (platform data, not a survey):**
  two interruptions/month/user is good, seven is bad, **19 is a sign of
  burnout**. "Burned Out" responders (top 10% most-interrupted) average **19
  non-working-hour interruptions per month — 10× the median responder**. Off-hour
  (6–10pm) interruptions rose 9% YoY; holiday/weekend +7%; over a third worked
  the equivalent of **two extra hours per day, totalling an extra 12 weeks of
  work**. *"a high correlation between employee turnover and after-hours
  interruptions."* Basis: **16,000 customers, 700,000 users, Jan 2019 – Apr
  2021**
  ([pagerduty.com/newsroom/pagerduty-state-of-digital-operations-report-underscores-business-and-human-costs-of-pandemic/](https://www.pagerduty.com/newsroom/pagerduty-state-of-digital-operations-report-underscores-business-and-human-costs-of-pandemic/)).
  *Dated but unusually strong evidence type.*
- **Alert actionability is a genuine evidence gap.** Widely circulated figures
  ("85% false positives", "67% of alerts ignored", "only 3% actionable",
  "healthy systems achieve 30–50% actionable") appear in vendor content **with no
  source attribution and no sample sizes**
  ([incident.io/blog/alert-fatigue-solutions-for-dev-ops-teams-in-2025-what-works](https://incident.io/blog/alert-fatigue-solutions-for-dev-ops-teams-in-2025-what-works)).
  A companion incident.io piece cites no survey data at all, grounding itself in
  Google's per-shift ceiling instead
  ([incident.io/blog/on-call-best-practices-guide-2026](https://incident.io/blog/on-call-best-practices-guide-2026)).
  **NO CREDIBLE PRIMARY SOURCE FOUND for industry-wide alert-actionability
  percentages.** The frequently-repeated "PagerDuty 2025: ~50 alerts/week, only
  2–5% require human intervention" claim appears only in third-party blogs and
  **could not be located in any PagerDuty publication — do not cite it.** If the
  number is needed, cite Google's per-shift ceiling or derive it from the target
  org's own paging data. For the academic framing of alert fatigue, use the ACM
  Computing Surveys review ([dl.acm.org/doi/10.1145/3723158](https://dl.acm.org/doi/10.1145/3723158)).

### Where engineering time goes

- **The exact toil definition, six characteristics** — quote verbatim from
  [sre.google/sre-book/eliminating-toil/](https://sre.google/sre-book/eliminating-toil/):
  *Manual* — *"manually running a script that automates some task"* still counts,
  because the hands-on time is toil; *Repetitive* — *"work you do over and
  over"*; *Automatable* — *"If a machine could accomplish the task just as well
  as a human, or the need for the task could be designed away"*; *Tactical* —
  *"interrupt-driven and reactive, rather than strategy-driven and proactive"*;
  *No enduring value* — *"If your service remains in the same state after you
  have finished a task, the task was probably toil"*; *O(n) with service growth*
  — *"If the work involved in a task scales up linearly with service size,
  traffic volume, or user count."*
- **The 50% cap, stated two ways.** Toil chapter: *"Our SRE organization has an
  advertised goal of keeping operational work (i.e., toil) **below 50%** of each
  SRE's time."* Introduction: *"Google places a **50% cap** on the aggregate
  'ops' work for all SREs—tickets, on-call, manual tasks, etc.... This cap
  ensures that the SRE team has enough time in their schedule to make the service
  stable and operable"*
  ([sre.google/sre-book/eliminating-toil/](https://sre.google/sre-book/eliminating-toil/),
  [sre.google/sre-book/introduction/](https://sre.google/sre-book/introduction/)).
  Rationale: without the cap, ops load grows linearly with service size, forcing
  continuous hiring just to stand still.
- **Actual measured toil at Google:** *"Quarterly surveys of Google's SREs show
  that the average time spent toiling is about **33%**"*, with a structural floor
  of 25–33% from on-call mechanics and an individual range from **0% to 80%**.
  (same) *Useful calibration: even the org that invented the discipline runs at a
  third toil.*
- **Toil is measurably rising again.** Catchpoint SRE Report 2025: median share
  of work spent on toil **rose to 30% from 25% in 2024**, *"after five years of
  steady decline."* The report's framing: *"the expectation was that AI would
  reduce toil, not exacerbate it,"* and manual supervision of AI systems that are
  *"mostly right, or make subtle and hard-to-predict errors, can easily raise the
  operational load of a team, as AI is at best 'a co-worker you can't trust.'"*
  Methodology: **n=301, Jul–Aug 2024**, North America 68% / Europe 16% / Asia 11%
  ([catchpoint.com/press-releases/the-sre-report-2025-highlighting-critical-trends-in-site-reliability-engineering](https://www.catchpoint.com/press-releases/the-sre-report-2025-highlighting-critical-trends-in-site-reliability-engineering);
  prior year: [catchpoint.com/press-releases/the-sre-report-2024-reveals-state-of-site-reliability-engineering](https://www.catchpoint.com/press-releases/the-sre-report-2024-reveals-state-of-site-reliability-engineering)).
  *Small n and NA skew — but this is the most directly on-point finding here:
  the first measured toil increase in five years coincides with AI adoption, and
  the named mechanism is supervision overhead.*
- **Stripe, "The Developer Coefficient" (Sept 2018)** — figures read directly
  from the PDF
  ([stripe.com/files/reports/the-developer-coefficient.pdf](https://stripe.com/files/reports/the-developer-coefficient.pdf)):
  average developer week **41.1 hours**; **17.3 hours/week on maintenance** (bad
  code, debugging, refactoring, modifying) = **42% of the work week**; of which
  **13.5 hours** is technical debt and **3.8 hours** is bad code. Self-rated
  productivity 68.4%. Top hindrance: **maintenance of legacy systems / technical
  debt, 52%**. Morale: work overload 81%, changing priorities causing discarded
  code 79%, not being given time to fix poor-quality code 79%. Economic model:
  18M developers × $51,000 GDP per developer = $918B, × **31.6% efficiency loss**
  = **~$300B annual global GDP shortfall**; bad code alone ≈ **$85B/year**.
  Methodology: Stripe with **Harris Poll**, >1,000 developers and >1,000 C-level
  executives across US, UK, France, Germany, Singapore.
  *Caveat: 2018 data, and the GDP extrapolation is a model resting on an Evans
  Data population figure, not a measurement.*

---

## A3. What the business loses when the agent is wrong

Ranked by evidence quality, not by intuition.

### 1. A leaked secret — best-instrumented, and the fastest-growing category

- **GitGuardian State of Secrets Sprawl 2025 (2024 data):** **23.8 million
  secrets** leaked on public GitHub in 2024, **+25% YoY**, from **1.4 billion
  commits** analysed. **70% of secrets leaked in 2022 remained active.** Generic
  secrets 58% of leaks. **4.6% of public repositories** contain a secret versus
  **35% of private repositories.** AWS IAM keys appear in **8% of private repos
  (5× the public rate)**. **15% of commit authors** leaked a secret. Beyond code:
  Slack 2.4% of corporate channels, Jira 6.1% of tickets; DockerHub had **7,000
  valid AWS keys** still exposed in image layers
  ([blog.gitguardian.com/the-state-of-secrets-sprawl-2025/](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2025/)).
- **2026 edition (2025 data):** **28.65 million** new hardcoded secrets, **+34%
  YoY**. **AI-service secrets hit 1,275,105 — an 81% surge**, including
  **113,000 leaked DeepSeek API keys**. By January 2026, **64%** of valid
  2022-vintage secrets were still active. **46% of critical secrets are missed by
  validation-only prioritisation.** Internal repos are ~**6× more likely** than
  public ones to contain hardcoded secrets, and **~28% of incidents originate
  outside repositories entirely**
  ([blog.gitguardian.com/the-state-of-secrets-sprawl-2026/](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/)).
  **Directly relevant: agents that handle credentials operate in the
  fastest-growing leak category.**
- **Credentials are the dominant breach vector.** Verizon 2025 DBIR: stolen
  credentials used in **22% of breaches** — leading initial access vector for the
  second consecutive year (phishing 16%); **88% of basic web application
  attacks** involved stolen credentials
  ([verizon.com/business/resources/Tea/reports/2025-dbir-data-breach-investigations-report.pdf](https://www.verizon.com/business/resources/Tea/reports/2025-dbir-data-breach-investigations-report.pdf)).
  **Figures from search summaries, PDF body not fetched — verify before quoting.**

### 2. A breach

- **IBM Cost of a Data Breach 2025:** global average **$4.44M**, down from
  **$4.88M** (first decline in five years, driven by faster containment); **mean
  time to identify and contain 241 days**, lowest in nine years. **US average
  $10.22M.** Attackers used AI in **16% of breaches**; **unauthorised ("shadow")
  AI tools were involved in 20% of breaches**
  ([ibm.com/think/x-force/2025-cost-of-a-data-breach-navigating-ai](https://www.ibm.com/think/x-force/2025-cost-of-a-data-breach-navigating-ai)).
  **IBM's domain returns HTTP 403 to automated fetching — these figures are
  transcribed from search-result summaries of that page. High confidence
  (multiple independent summaries agree) but verify in a browser.**
- **IBM 2026 edition:** average **~$5M, +12%** over 2025. **Shadow AI's share of
  security incidents more than doubled YoY, to 43%.** **92%** of organisations
  suffering attacks on their AI models failed to properly control access; only
  four in ten limited access to their AI systems; **more than two-thirds had no
  governance process to limit shadow AI.** Methodology: 602 organisations
  breached Mar 2025 – Feb 2026, 17 industries, 16 countries
  ([cybersecuritydive.com/news/data-breach-costs-ai-governance-ibm/826463/](https://www.cybersecuritydive.com/news/data-breach-costs-ai-governance-ibm/826463/);
  report hub: [ibm.com/reports/data-breach](https://www.ibm.com/reports/data-breach)).

### 3. A bad deploy / wrong diagnosis / missed regression

**NO PUBLISHED "cost per bad deploy" or "cost per rollback" figure exists.**
This was searched for specifically. Every number in circulation is a derived
model, not a measurement. The defensible composition, built from separately
sourced inputs:

> ~**70%** of outages are change-induced
> ([sre.google/sre-book/introduction/](https://sre.google/sre-book/introduction/))
> × change failure rate of **5%** (elite) to **40%** (low)
> ([octopus.com/blog/2024-devops-performance-clusters](https://octopus.com/blog/2024-devops-performance-clusters))
> × median high-impact outage cost **$1.9M/hour** at **51-minute median MTTR**
> ([newrelic.com/resources/report/observability-forecast/2024/state-of-observability/outages-downtime-cost](https://newrelic.com/resources/report/observability-forecast/2024/state-of-observability/outages-downtime-cost))
> ⇒ a defensible per-failed-deploy expected cost for a given org.

**The composition is a judgement call; each input is separately sourced.**

The closest *published* proxy is DORA's **deployment rework rate**, introduced
in 2024 precisely because change failure rate was serving as a proxy for rework
volume ([dora.dev/insights/dora-metrics-history/](https://dora.dev/insights/dora-metrics-history/)).
**Recommendation: instrument rework rate rather than hunting for an industry
average.**

### 4. A wasted engineer-hour

The cheapest failure by a wide margin, but the one with the best-measured base
rate: 17.3 hours/week already goes to maintenance (Stripe), 30% of SRE work is
toil (Catchpoint), and Google budgets 6 hours per incident. **A wrong agent
answer that costs an engineer an hour is a rounding error; a wrong agent answer
that an engineer *trusts* is not** — see the METR perception-vs-reality gap in
F6, where developers believed AI sped them up 20% while measurement showed a
slowdown.

---

## A4. Already fully automated — therefore uninteresting as agent tasks

All of the following are solved by controllers and reconciliation loops. An
agent that "monitors and rolls back deployments" or "scales the cluster" is
re-implementing shipped, battle-tested software.

### Progressive delivery, canary analysis, automated rollback

- **Argo Rollouts** performs automated canary analysis against metric providers
  and aborts automatically: *"An AnalysisTemplate is a template spec which
  defines how to perform a canary analysis, such as the metrics which it should
  perform, its frequency, and the values which are considered successful or
  failed."* *"If the metric is measured to be less than 95%, and there are three
  such measurements, the analysis is considered Failed. **The failed analysis
  causes the Rollout to abort.**"* For blue/green: *"If post-promotion Analysis
  fails or errors, the Rollout enters an aborted state and **switches traffic
  back to the previous stable Replicaset**."* Providers: Prometheus, Datadog, New
  Relic, CloudWatch
  ([argo-rollouts.readthedocs.io/en/stable/features/analysis/](https://argo-rollouts.readthedocs.io/en/stable/features/analysis/)).
- **Flagger** implements canary, A/B and blue/green mirroring, *"gradually
  shifting traffic to the new version while measuring metrics and running
  conformance tests"*, with automated rollback on threshold breach
  ([docs.flagger.app/](https://docs.flagger.app/)).

### Autoscaling

- **Kubernetes HPA:** *"A HorizontalPodAutoscaler automatically updates a
  workload resource... with the aim of automatically scaling capacity to match
  demand."* It is *"a control loop that runs intermittently... the default
  interval is 15 seconds"*, using
  `desiredReplicas = ceil(currentReplicas × currentMetricValue / desiredMetricValue)`
  with a 0.1 default tolerance
  ([kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)).
  **A closed-form algorithm — an LLM adds latency and nondeterminism to a problem
  that has a formula.**
- **Karpenter** automates node provisioning, consolidation, drift detection and
  expiry; drift is detected structurally — *"A NodeClaim will be detected as
  drifted if the values in its owning NodePool/EC2NodeClass do not match the
  values in the NodeClaim"* — with `consolidationPolicy: WhenEmptyOrUnderutilized`
  and disruption budgets pacing changes
  ([karpenter.sh/docs/concepts/disruption/](https://karpenter.sh/docs/concepts/disruption/)).

### Self-healing and GitOps reconciliation

- **Kubernetes controllers:** *"controllers are control loops that watch the
  state of your cluster, then make or request changes where needed"*; *"control
  loops automatically fix failures"*
  ([kubernetes.io/docs/concepts/architecture/controller/](https://kubernetes.io/docs/concepts/architecture/controller/)).
- **Liveness/readiness probes:** *"If a container fails its liveness probe more
  times than the configured tolerance, **the kubelet restarts that container**"*;
  *"If the readiness probe returns a failed state, the EndpointSlice controller
  **removes the Pod's IP address from the EndpointSlices**"*
  ([kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)).
  **Restart-on-hang and drain-on-unready are already free.**
- **Argo CD:** *"a Kubernetes controller which continuously monitors running
  applications and compares the current, live state against the desired target
  state (as specified in the Git repo)"*; deviation is `OutOfSync`, with
  automatic or manual sync back
  ([argo-cd.readthedocs.io/en/stable/](https://argo-cd.readthedocs.io/en/stable/)).
- **Flux:** the loop *"runs every five minutes by default"*, and — critically —
  *"**If you make any changes to the cluster using `kubectl edit/patch/delete`,
  they will be promptly reverted**"*
  ([fluxcd.io/flux/concepts/](https://fluxcd.io/flux/concepts/)).
  **Config drift in Kubernetes is a solved problem.**

### Dependency updates

- **Dependabot security updates:** *"when a Dependabot alert is raised for a
  vulnerable dependency... Dependabot automatically tries to fix it"*, raising a
  PR *"to update the dependency to the minimum version that includes the patch."*
  Limitation: all-or-nothing per repo, and weaker handling of indirect
  dependencies outside npm
  ([docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates](https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates)).
- **Renovate:** finds package files automatically including in monorepos, opens
  PRs, supports automerge, scheduling, and automatic replacement PRs *"to migrate
  from a deprecated dependency to the community suggested replacement"*
  ([docs.renovatebot.com/](https://docs.renovatebot.com/)).
  **The residual problem — deciding whether a major-version bump is safe and
  fixing the breakage — is NOT automated. That is the agent-shaped gap, not PR
  creation.**

### Certificate lifecycle

- **cert-manager:** *"cert-manager creates TLS certificates for workloads... and
  **renews the certificates before they expire**"*, across ACME/Let's Encrypt,
  Vault and private PKI ([cert-manager.io/docs/](https://cert-manager.io/docs/)).
  **Certificate expiry as an incident class is essentially eliminated in
  Kubernetes environments.**

### Infrastructure drift detection

- **HCP Terraform health assessments:** *"Drift detection helps you identify
  situations where your actual infrastructure no longer matches the configuration
  defined in Terraform."* Assessments run periodically, reporting drifted-resource
  counts and proposing either reverting the drift or updating the configuration
  ([developer.hashicorp.com/terraform/cloud-docs/workspaces/health](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health)).
  **Detection and diff are automated; deciding *which* of the two resolutions is
  correct for a given drift is judgement — and that is where an agent adds value.**

### Synthesis: what is left

Deterministic tooling has fully solved **detection**, **reconciliation to a
declared state**, and **mechanical remediation toward a known-good target**.
What remains unsolved and genuinely agent-shaped:

1. Deciding **why** a canary failed, and whether the fix is a code change or a
   threshold change.
2. Resolving drift where **the live state is correct and the declaration is
   stale** (Terraform's two resolution paths — choosing between them).
3. Triaging a **major-version dependency bump that breaks the build**.
4. Writing the **postmortem and the follow-up bug**.
5. Converting a **novel alert into a runbook**.

Items 4 and 5 map exactly onto Google's stated 6-hour per-incident cost, **most
of which is follow-up rather than remediation**
([sre.google/sre-book/being-on-call/](https://sre.google/sre-book/being-on-call/)).

---

## Three things worth carrying into the thesis

1. **The DORA tier premise is stale.** No current elite/high/medium/low
   benchmark exists; 2025 uses seven archetypes and per-metric buckets.
2. **The strongest business case is not speed.** It is Uptime's **80%
   preventability** + **58% failure-to-follow-procedure** + Google's **70% of
   outages are change-induced**. All three land on the same target: *procedure
   adherence around change.* That is far better evidenced than any
   downtime-cost-per-minute number.
3. **The most credible counter-evidence is the most on-point.** DORA measures AI
   *worsening* delivery stability two years running; Catchpoint measures toil
   *rising* for the first time in five years with **AI supervision named as the
   mechanism**. An honest positioning must address supervision overhead head-on
   rather than assume the agent nets out positive.
