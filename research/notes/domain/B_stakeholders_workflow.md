# B. Stakeholders and the shape of the work

Answers **B1–B5** of `00-QUESTIONS.md`.

**Source-reliability note.** Several `atlassian.com/incident-management/*`
marketing pages are client-rendered and returned only navigation chrome to
automated fetching. Quotes attributed to those URLs come from **search-result
snippets quoting those pages**, not from a direct fetch, and are marked
`[SNIPPET ONLY]`. Atlassian content on `developer.atlassian.com` and
`support.atlassian.com/statuspage` **was** fetched directly and is marked
`[FETCHED]`. The DORA 2019 report PDF and the Atlassian handbook PDF returned
unparseable binary.

---

## B0. What counts as an incident — the entry gate, and it does not agree

Three primary sources give three different gates:

- **Google SRE** — declare an incident if: *"Do you need to involve a second
  team in fixing the problem? / Is the outage visible to customers? / Is the
  issue unsolved even after an hour's concentrated analysis?"*
  ([sre.google/sre-book/managing-incidents/](https://sre.google/sre-book/managing-incidents/))
- **PagerDuty** — an incident is *"Any unplanned disruption or degradation of
  service that is actively affecting customers ability to use PagerDuty"*; a
  **major** incident is *"Any incident that requires a coordinated response
  between multiple teams."*
  ([response.pagerduty.com/before/what_is_an_incident/](https://response.pagerduty.com/before/what_is_an_incident/))
  PagerDuty biases toward over-declaring: *"If you are unsure of whether
  response is required, trigger our incident response process."*
- **Google SRE Workbook (IMAG)** lists *"Declaring incidents early and often"*
  as a basic principle
  ([sre.google/workbook/incident-response/](https://sre.google/workbook/incident-response/)).

**The conflict, stated precisely:** Google's gate is *multi-team OR
customer-visible OR >1hr unsolved*. PagerDuty's gate is *customer-affecting*,
with multi-team only escalating it to **major**. A single-team, hour-long,
non-customer-visible problem **is an incident at Google and is not one at
PagerDuty**. Any question of the form "how many incidents did we have" inherits
this.

---

## B1. The canonical workflow, stage by stage

### B1.1 Detection and paging

- Paging response-time targets: *"Typical values are 5 minutes for user-facing
  or otherwise highly time-critical services, and 30 minutes for less
  time-sensitive systems."*
  ([sre.google/sre-book/being-on-call/](https://sre.google/sre-book/being-on-call/))
- The target is **derived from the error budget**, not chosen: for
  *"4 nines of availability in a given quarter (99.99%), the allowed quarterly
  downtime is around 13 minutes."* (same)
- Alert quality gate: *"All alerts should be immediately actionable. There
  should be an action we expect a human to take immediately after they receive
  the page that the system is unable to take itself."*
  ([sre.google/workbook/on-call/](https://sre.google/workbook/on-call/))
- PagerDuty: *"We recommend you set your escalation timeout to 5 minutes"*, and
  *"Never hesitate to escalate"*
  ([response.pagerduty.com/oncall/being_oncall/](https://response.pagerduty.com/oncall/being_oncall/)).

### B1.2 Acknowledgement

- PagerDuty: *"Team alert escalation happens within 5 minutes, set/stagger your
  notification timeouts (push, SMS, phone, etc.) accordingly."* (same URL)
- Readiness is a precondition, not a separate stage: *"Have your laptop and
  Internet with you"*, *"Be prepared (environment is set up, a current working
  copy of the necessary repositories is local and functioning...)"* (same URL)
- incident.io targets **MTTA under 5 minutes** for critical systems, escalating
  to secondary at 5–15 minutes of no acknowledgement
  ([incident.io/blog/on-call-best-practices-guide-2026](https://incident.io/blog/on-call-best-practices-guide-2026)).

### B1.3 Triage and troubleshooting

- Google's six-stage model: *"Problem Report, Triage, Examine, Diagnose, Test
  and Treat, and Cure"*
  ([sre.google/sre-book/effective-troubleshooting/](https://sre.google/sre-book/effective-troubleshooting/)).
- **Mitigation precedes diagnosis — this is the load-bearing instruction:**
  *"Your first response in a major outage may be to start troubleshooting and
  try to find a root cause as quickly as possible. **Ignore that instinct!**"*
  Instead *"your course of action should be to make the system work as well as
  it can under the circumstances."* And: *"Stopping the bleeding should be your
  first priority; you aren't helping your users if the system dies while you're
  root-causing."* With the aviation analogy: *"Novice pilots are taught that
  their first responsibility in an emergency is to fly the airplane;
  troubleshooting is secondary."* (same URL)
- Documented troubleshooting failure modes: chasing irrelevant symptoms into
  *"wild goose chases"*, unsafe hypothesis testing, *"wildly improbable
  theories"*, and spurious correlations mistaken for causation. (same URL)
  **These map almost one-to-one onto documented agent failure modes — see F6.**

### B1.4 Roles and command structure

**Google SRE Book — four roles**
([sre.google/sre-book/managing-incidents/](https://sre.google/sre-book/managing-incidents/)):
- **Incident Command** — *"holds the high-level state about the incident. They
  structure the incident response task force, assigning responsibilities
  according to need and priority."*
- **Operational Work** — *"The Ops lead works with the incident commander to
  respond to the incident by applying operational tools to the task at hand."*
- **Communication** — *"the public face of the incident response task force"*.
- **Planning** — *"supports Ops by dealing with longer-term issues, such as
  filing bugs, ordering dinner, arranging handoffs, and tracking how the system
  has diverged from the norm."*

**Recursive separation of responsibilities** — *"A clear separation of
responsibilities allows individuals more autonomy than they might otherwise
have, since they need not second-guess their colleagues."* When workload
becomes excessive, leaders delegate and **create subincidents**, with members
reporting status upward. (same URL)

**Google SRE Workbook — IMAG, three roles**
([sre.google/workbook/incident-response/](https://sre.google/workbook/incident-response/)):
- *"Google's incident response system is based on the Incident Command System
  (ICS)"*, branded **Incident Management At Google (IMAG)**.
- The three Cs: *"Coordinate response effort. Communicate between incident
  responders, within the organization, and to the outside world. Maintain
  control over the incident response."*
- **IC**: *"Commands and coordinates the incident response, delegating roles as
  needed. By default, the IC assumes all roles that have not been delegated
  yet."* **CL**: *"the public face of the incident response team."* **OL**:
  *"works to respond to the incident by applying operational tools to mitigate
  or resolve the incident."* And *"the CL and OL report to the IC."*
- **Difference from the SRE Book: the Workbook drops the Planning role
  entirely.** The "IC absorbs undelegated roles" rule is new in the Workbook.

**PagerDuty — six roles**
([response.pagerduty.com/before/different_roles/](https://response.pagerduty.com/before/different_roles/)):
- **Incident Commander** — *"acts as the single source of truth of what is
  currently happening and what is going to happen during a major incident"*;
  *"the single authority on system status"*.
- **Deputy** — *"a direct support role for the Incident Commander"*, a
  **"hot standby"** who manages the incident call.
- **Scribe** — *"documents the timeline of an incident as it progresses and
  makes sure all important decisions and data are captured"*.
- **Subject Matter Expert (SME/Resolver)** — *"a domain expert or designated
  owner of a component or service"*.
- **Customer Liaison** — *"responsible for interacting with customers"*.
- **Internal Liaison** — *"responsible for interacting with internal
  stakeholders...or mobilizing additional responders"*.
- Elastic staffing: *"It is not intended that every role be filled by a
  different person for every incident."*

### B1.5 During the incident — the run loop

PagerDuty's IC sequence
([response.pagerduty.com/during/during_an_incident/](https://response.pagerduty.com/during/during_an_incident/)):
1. *"Announce on the call and in Slack that you are the incident commander, who
   you have designated as deputy...and scribe."*
2. Identify obvious causes and *"delegate investigation to relevant experts."*
3. *"Identify investigation & repair actions (roll back, rate-limit services,
   etc) and delegate actions to relevant service experts."*
4. Monitor severity; decide whether public announcement is needed.
5. *"Keep track of your span of control. If the response starts to become
   larger...consider splitting off sub-teams."*
6. *"Once the incident has recovered or is actively recovering, you can announce
   that the incident is over."*

- Internal cadence: *"Provide regular status updates in Slack (roughly every
  30mins) to the executive team."* (same URL)
- Google's co-equal third priority, which most vendor playbooks omit:
  *"Stop the bleeding, restore service, and **preserve the evidence for
  root-causing**."*
  ([sre.google/sre-book/managing-incidents/](https://sre.google/sre-book/managing-incidents/))
  Also: prepare documentation in advance, trust participants with full autonomy
  within their roles, **practice routinely**, and **rotate roles**.

### B1.6 Postmortem / review

**Google's postmortem triggers, verbatim**
([sre.google/sre-book/postmortem-culture/](https://sre.google/sre-book/postmortem-culture/)):
- *"User-visible downtime or degradation beyond a certain threshold"*
- *"Data loss of any kind"*
- *"On-call engineer intervention (release rollback, rerouting of traffic, etc.)"*
- *"A resolution time above some threshold"*
- *"A monitoring failure (which usually implies manual incident discovery)"*

**Three of the five are process facts, not impact facts.** Any rollback, any
manual discovery, and any data loss trigger a postmortem regardless of customer
impact — materially broader than a severity gate.

**Blameless principle** (same URL): *"For a postmortem to be truly blameless, it
must focus on identifying the contributing causes of the incident without
indicting any individual or team for bad or inappropriate behavior."* And:
*"A blamelessly written postmortem assumes that everyone involved in an incident
had good intentions and did the right thing with the information they had."*
Named practices: *"Avoid Blame and Keep It Constructive"*, *"No Postmortem Left
Unreviewed"* — an *"unreviewed postmortem might as well never have existed"*.

**PagerDuty's trigger is severity-gated instead**: postmortems required for
*"every major incident (SEV-2/1)"*, owner designated by the IC *"either at the
end of a major incident call or very shortly after"*, meeting *"scheduled within
3 calendar days for a SEV-1 and 5 business days for a SEV-2"*
([response.pagerduty.com/after/post_mortem_process/](https://response.pagerduty.com/after/post_mortem_process/)).

**Workbook adds enforcement**: *"all postmortems which follow a user-affecting
outage must have at least one P[01] bug associated with them"*, and warns
*"If you reward engineers for writing postmortems, but not for closing the
associated action items, you risk an unvirtuous cycle of unclosed postmortems."*
Plus the line that defines "done": *"To our users, a postmortem without
subsequent action is indistinguishable from no postmortem."*
([sre.google/workbook/postmortem-culture/](https://sre.google/workbook/postmortem-culture/))

### B1.7 The load model of the on-call job itself

- **Ceiling:** *"the maximum number of incidents per day is 2 per 12-hour
  on-call shift."*
  ([sre.google/sre-book/being-on-call/](https://sre.google/sre-book/being-on-call/));
  Workbook restates *"We target a maximum of two incidents per on-call shift"*
  ([sre.google/workbook/on-call/](https://sre.google/workbook/on-call/)).
- **The derivation is the interesting part:** *"dealing with the tasks involved
  in an on-call incident—root-cause analysis, remediation, and follow-up
  activities like writing a postmortem and fixing bugs—takes 6 hours."*
  Two incidents × 6 hours ≈ a 12-hour shift, so **the stated capacity of an
  on-call shift has ~zero slack.** This is the single best quantitative
  justification for an agent in this domain.
- **The 25%/50% rules:** *"we strive to invest at least 50% of SRE time into
  engineering: of the remainder, no more than 25% can be spent on-call, leaving
  up to another 25% on other types of operational, nonproject work."*
- **Team size:** *"the minimum number of engineers needed for on-call duty from
  a single-site team is eight"*; Workbook: *"a bare minimum of five people per
  site... in a multisite, 24/7 configuration, and eight people in a single-site,
  24/7 configuration"*, plus a spare each — *"six engineers per site (multisite)
  or nine per site (single-site)."*
- **Shift length:** *"We recommend limiting shift lengths to 12 hours"*;
  *"24 hours of on-call duty without reprieve isn't a sustainable setup."*
- **Stress and cognition:** the chapter frames two competing modes —
  *"Intuitive, automatic, and rapid action"* vs *"Rational, focused, and
  deliberate cognitive functions"* — and states stress hormones *"can impair
  cognitive functions and cause suboptimal decision making"* producing
  *"unreflective and unconsidered (but immediate) action."* Mitigations named:
  *"Clear escalation paths, Well-defined incident-management procedures, A
  blameless postmortem culture."*
  **NO SOURCE FOUND for the exact phrase "cognitive flow state" in this
  chapter — that is a paraphrase, not a quotation. Do not cite it as one.**
- **Compensation:** time-off-in-lieu or cash *"capped at some proportion of
  overall salary"*, deliberately, as *"a limit on the amount of on-call work
  that will be taken on by any individual."*
- **Readiness:** Google's Mountain View team maintains *"a checklist of two
  dozen focus areas for people to practice before going on-call"* — administering
  production jobs, traffic draining, rolling back pushes, rate-limiting unwanted
  traffic, increasing serving capacity, describing architecture and dependencies
  ([sre.google/workbook/on-call/](https://sre.google/workbook/on-call/)).

---

## B2. Severity conventions — and the fact that they disagree

### B2.1 Ten published ladders side by side

| Org | Scheme | Top | Bottom | Basis |
|---|---|---|---|---|
| PagerDuty | SEV-1…SEV-5 | SEV-1 | SEV-5 | Public/exec notification + customer impact |
| Atlassian (ITSM) | SEV1…SEV3 | SEV1 | SEV3 | Impact severity |
| Atlassian (app ecosystem) | SEV1…SEV3 | SEV1 | SEV3 | **User counts, app counts, capability tier, duration** |
| Datadog | SEV-1…SEV-5 + "Unknown" | SEV-1 | SEV-5 | Dual axis: external impact AND internal blockage |
| incident.io (guide) | **Minor / Major / Critical** | Critical | Minor | Impact; numbering explicitly rejected |
| incident.io (blog) | Sev1…Sev4 | Sev1 | Sev4 | Impact |
| GitLab | S1…S4 | S1 Critical | S4 Low | Impact |
| AWS Support | **Named, no numbers** | "Business/mission-critical system down" | "General guidance" | System state |
| Azure Support | **Letters** Sev A/B/C | Sev A | Sev C | Business impact |
| Google Cloud Support | P0, P1…P4 | **P0** (above P1) | P4 | Impact — **but customer-designated** |

### B2.2 Where "SEV1" concretely means different things

- **PagerDuty's SEV-1 is about audience, not impact.** SEV-1 = *"Critical issue
  that warrants public notification and liaison with executive teams"*; SEV-2 =
  *"Critical system issue actively impacting many customers' ability to use the
  product."* Both trigger major incident response. **So the SEV-1/SEV-2 boundary
  at PagerDuty is "do we go public and call executives", not "how broken is it."**
  ([response.pagerduty.com/before/severity_levels/](https://response.pagerduty.com/before/severity_levels/))
- **Atlassian's SEV1 is about impact magnitude** — *"a critical incident with
  very high impact"*: customer data loss, security breach, client-facing service
  down for all customers. SEV2 = *"major incident with significant impact"*;
  SEV3 = *"a minor incident with low impact"*.
  `[SNIPPET ONLY]` ([atlassian.com/incident-management/kpis/severity-levels](https://www.atlassian.com/incident-management/kpis/severity-levels))
- **Atlassian publishes two mutually incompatible SEV1 definitions.** Its
  developer-facing ladder defines **SEV 1 – CRITICAL** by raw scale:
  *"more than 5,000,000 users or more than 100 apps"*, or C1 capability outages
  over 2 hours; SEV 2 = *"100,001-5,000,000 users or 11-100 apps"*; SEV 3 =
  *"1,000-100,000 users or 3-10 apps"*.
  `[FETCHED]` ([developer.atlassian.com/developer-guide/app-incident-severity-levels/](https://developer.atlassian.com/developer-guide/app-incident-severity-levels/))
  **An outage affecting 200,000 users is SEV2 on one Atlassian page and could be
  SEV1 on the other.**
- **Datadog's ladder has two orthogonal axes.** SEV-1 is *"Impacts a large
  number of customers or a broad feature"* externally, but *"Threatens production
  stability or halts productivity / Blocks most teams"* internally. Its **SEV-5
  explicitly includes "Planned operational tasks"** — Datadog files planned work
  on the incident severity scale, which is **not an incident at all** under
  PagerDuty's definition.
  ([datadoghq.com/blog/how-datadog-manages-incidents/](https://www.datadoghq.com/blog/how-datadog-manages-incidents/))
- **Three-level vs five-level is a real fork.** Atlassian's SEV3 ("minor
  incident with low impact") occupies the space of PagerDuty's SEV-4 *and* SEV-5
  combined (SEV-4 = *"Minor issues requiring action, but not affecting customer
  ability to use the product"*; SEV-5 = *"Cosmetic issues or bugs"*).
  **A cosmetic bug is a SEV3 at Atlassian and a SEV5 at PagerDuty.**
- **incident.io recommends abolishing the numbers**: *"Prefer human words like
  Low, Medium, over codewords like SEV-1 or P1."* Ladder: Minor / Major /
  Critical, where Critical = *"Issues causing very high impact to customers.
  Immediate response is required (e.g. a full outage or data breach)."*
  ([incident.io/guide/foundations/severities](https://incident.io/guide/foundations/severities))
  **…and then contradicts itself in its own marketing**, running a Sev1–Sev4
  ladder where Sev4 is *"typically cosmetic or informational issues"*
  ([incident.io/blog/differences-between-severity-and-priority](https://incident.io/blog/differences-between-severity-and-priority)).
- **incident.io concedes the whole thing is soft:** *"Severities are subjective.
  It might not be clear whether something is Critical or Major, and in the vast
  majority of cases, it really doesn't matter."* And: *"Every organization will
  have its own spin on these, so consider this a set of 'safe defaults' rather
  than prescriptive advice."*
  ([incident.io/blog/what-is-a-sev-1-incident](https://incident.io/blog/what-is-a-sev-1-incident))
- **Cloud vendors abandon SEV vocabulary entirely.** AWS uses system-state names
  — *"Business/mission-critical system down"* … *"General guidance"* — with
  response <15 min (Enterprise) or <5 min from an Incident Management Engineer
  (Unified Operations) `[FETCHED]`
  ([aws.amazon.com/premiumsupport/plans/](https://aws.amazon.com/premiumsupport/plans/)).
  Azure uses **letters**, Sev A/B/C `[SNIPPET ONLY]`
  ([azure.microsoft.com/en-us/support/plans/response](https://azure.microsoft.com/en-us/support/plans/response)).
- **Google Cloud inserts a level above P1 and lets the customer set it.**
  P1 = *"Critical Impact – Service Unusable in Production"*, with a **P0** above
  it for mission-critical provisioned environments. And: *"Customer designates
  P1-P4 priority upon submission of Requests. Google will review Customer's
  priority designation and may reclassify designations... Any such determination
  made by Google is final and binding on Customer."*
  `[FETCHED]` ([cloud.google.com/terms/tssg](https://cloud.google.com/terms/tssg))
  **The only ladder found where the reporting party sets severity and the
  responding party holds unilateral, contractually final reclassification power.**

### B2.3 Numbering direction — the honest answer

**Direction is consistent across every published ladder found: lower number =
worse.** Stated explicitly: *"the number rises as impact falls, so SEV1 is a
critical outage and SEV4 or SEV5 is a cosmetic or low-impact issue."*
([uptimerobot.com/knowledge-hub/monitoring/severity-levels-explained/](https://uptimerobot.com/knowledge-hub/monitoring/severity-levels-explained/))

**An inverted ladder (SEV5 = worst) was actively hunted for and NOT FOUND in any
published source. Reporting the absence rather than manufacturing the
disagreement.**

The real disagreement is at the **top and the length**: whether the ladder
starts at SEV0/P0 or SEV1/P1, whether it ends at 3, 4 or 5, and whether it uses
digits, letters or words. SEV0–SEV5 ladders exist
([xurrent.com/blog/incident-severity-levels](https://www.xurrent.com/blog/incident-severity-levels));
Google Cloud runs P0–P4; Atlassian runs SEV1–SEV3; Azure runs A–C.
**"SEV1" is therefore not even reliably the top of the ladder.**

### B2.4 Severity vs priority — a second axis most ladders conflate

- incident.io separates them: *"Severity levels classify an incident based on
  the impact it will have on your business or your customers"* vs *"An
  incident's priority level determines when it should be addressed. The severity
  level is a consideration in determining the priority level, but it's not the
  only factor."* Priority ladder: P1 *"needs to be handled immediately"*;
  P2 *"urgent, but you don't necessarily need to mobilize your response team in
  the middle of the night"*; P3 *"can be handled the next business day"*;
  P4 *"can address...during regular maintenance"*.
  ([incident.io/blog/differences-between-severity-and-priority](https://incident.io/blog/differences-between-severity-and-priority))
- FireHydrant models them as separate fields
  ([docs.firehydrant.com/docs/severities-and-priorities](https://docs.firehydrant.com/docs/severities-and-priorities)).
- **Google Cloud collapses the two**: it calls the field *priority* but defines
  every level by *impact*. ([cloud.google.com/terms/tssg](https://cloud.google.com/terms/tssg))
- Tie-break rule: PagerDuty says *"If you are unsure which level an incident
  is...treat it as the higher one"*, deferring severity review to post-incident.
- What severity should be wired to: *"Every severity level should map to four
  things: who gets notified, how fast they respond, what communication cadence
  they maintain, and whether a post-incident review is mandatory."*
  ([opsbrief.io/blog/incident-severity-levels-how-to-define-sev0-sev1-sev2-and-sev3](https://opsbrief.io/blog/incident-severity-levels-how-to-define-sev0-sev1-sev2-and-sev3))

---

## B3. What "done" means at each stage — and where definitions collide

### B3.1 Mitigated ≠ resolved ≠ closed

**FireHydrant draws the sharpest line** `[FETCHED]`
([docs.firehydrant.com/docs/incident-milestones-lifecycle-phases](https://docs.firehydrant.com/docs/incident-milestones-lifecycle-phases)):
- **Mitigated** = *"When the system is no longer exhibiting problems to users,
  but the team is still monitoring the situation."*
- **Resolved** = *"When the system is confirmed to be working again with no
  relapse."*
- **Closed** = *"Indicates all tasks mid- and post-incident are completed."*

Full 10-milestone model: **Started** (*"When the affected system began having
problems"*) → **Detected** (*"When a monitoring system (or human) noticed"*) →
**Acknowledged** → **Investigating** → **Identified** → **Mitigated** →
**Resolved** → **Retrospective Started** → **Retrospective Completed** →
**Closed**. FireHydrant argues the *gap* is the metric: time between mitigation
and resolution *"can provide valuable insight into tech debt lurking in your
systems"*
([firehydrant.com/glossary/mitigation/](https://firehydrant.com/glossary/mitigation/)).

**Datadog uses "stable"** for the same idea: *"Once an incident's impact on
customers is completely contained, we declare it stable."* Resolution is a
**higher** bar requiring causal understanding: *"Once the effects of an incident
have been contained and its root causes are sufficiently well-understood to
justify confidence that it will not immediately recur, we declare the incident
resolved."*
([datadoghq.com/blog/how-datadog-manages-incidents/](https://www.datadoghq.com/blog/how-datadog-manages-incidents/))

**incident.io splits on the operational/learning boundary** `[FETCHED]`:
**"Impact mitigated"** = *"things are back to normal, and it's time to start
learning"*; **"Debrief completed"**; **"Closed"** = *"the post-incident process
is over."* In-incident statuses: **Investigating** = *"we think something is
wrong, but we're not sure what it is yet"*; **Fixing**; **Monitoring** = *"we
think it's fixed, but want to double-check!"* Minimum viable set is just
**Ongoing** and **Resolved**
([incident.io/guide/foundations/statuses](https://incident.io/guide/foundations/statuses)).

**Google never uses "resolved" as a state at all** — it uses *"Stop the
bleeding, restore service, and preserve the evidence for root-causing"*
([sre.google/sre-book/managing-incidents/](https://sre.google/sre-book/managing-incidents/))
and *"The on-call engineer minimizes user impact first, then makes sure the
issues are fully addressed"*
([sre.google/workbook/on-call/](https://sre.google/workbook/on-call/)).

### B3.2 The four incompatible definitions of "resolved" — the core conflict

**This is the sharpest B3 finding. Four primary sources, four different bars:**

1. **PagerDuty — lowest bar, defined by responder attention.** The incident ends
   when *"there's no more productive work to be done for the incident right
   now."* The IC may announce it over *"once the incident has recovered **or is
   actively recovering**"* — i.e. **before recovery completes**.
   ([response.pagerduty.com/during/during_an_incident/](https://response.pagerduty.com/during/during_an_incident/))
2. **FireHydrant — mid bar, defined by stability.** *"the system is confirmed to
   be working again with no relapse"*; temporary fixes removed; root cause not
   required.
3. **Datadog — higher bar, defined by causal confidence.** Root causes
   *"sufficiently well-understood to justify confidence that it will not
   immediately recur."*
4. **Atlassian Statuspage — highest bar, defined by cause elimination.**
   **Resolved** = *"the root cause of the issue has been eliminated and your
   systems are back to 100% performance."* `[FETCHED]`
   ([support.atlassian.com/statuspage/docs/create-an-incident/](https://support.atlassian.com/statuspage/docs/create-an-incident/))

**Consequence, and this is a task in itself:** an outage mitigated by a rollback
with the underlying bug still in the codebase is legitimately **"Resolved"** in
PagerDuty and FireHydrant terms and legitimately **NOT resolved** in Statuspage
terms. **Any system syncing an internal tracker to a public status page will
emit either a false "Resolved" or a stuck-open incident, depending on
direction.** Statuspage's **Monitoring** = *"you believe you have successfully
fixed the issue and are waiting for the symptoms to subside"* is the correct
public analogue of "mitigated" — the mapping is Monitoring↔Mitigated, **not**
Resolved↔Mitigated.

Other Statuspage statuses `[FETCHED]`: **Investigating** = *"you are seeing the
symptoms of an issue but are unaware what the root cause"*; **Identified** =
*"you have found the root cause of the incident and are working on a fix."*
Component statuses: **Degraded Performance** = *"working but is slow or otherwise
impacted in a minor way"*; **Partial Outage** = *"completely broken for a subset
of customers"*; **Major Outage** = *"completely unavailable"*
([support.atlassian.com/statuspage/docs/what-is-a-component/](https://support.atlassian.com/statuspage/docs/what-is-a-component/)).

### B3.3 "Closed" is contested too — postmortem action items

- Google: *"To our users, a postmortem without subsequent action is
  indistinguishable from no postmortem"*, enforced by *"all postmortems which
  follow a user-affecting outage must have at least one P[01] bug associated
  with them."*
  ([sre.google/workbook/postmortem-culture/](https://sre.google/workbook/postmortem-culture/))
- FireHydrant makes it a formal state: **Closed** requires *"all tasks mid- and
  post-incident are completed"*, strictly after **Retrospective Completed**.
- PagerDuty puts a clock on it: 3 calendar days (SEV-1) / 5 business days
  (SEV-2) to the postmortem meeting, which *"generally last 15-30 minutes."*

### B3.4 MTTx — the ambiguity is documented, not folklore

**MTTR is genuinely four different metrics.** Better Stack `[FETCHED]`
([betterstack.com/community/guides/incident-management/mttr-and-other-incident-metrics/](https://betterstack.com/community/guides/incident-management/mttr-and-other-incident-metrics/)):
- **Mean Time to Recovery** — failure → fully operational.
- **Mean Time to Respond** — *from the first failure alert* (excludes detection lag).
- **Mean Time to Repair** — repairs-begin → repairs-complete.
- **Mean Time to Resolve** — *"resolution is defined as a point in time when the
  cause of an incident is identified and fixed."*
- All four share the identical formula shape `sum of periods / number of
  incidents`, **which is exactly why they get silently interchanged.** The stated
  consequence: *"Same incidents, four very different averages, depending on which
  clock you start."*

Atlassian confirms the four-way collision — *"MTTR can stand for mean time to
repair, resolve, respond, or recovery"* — with **MTTA** = time to acknowledge,
**MTBF** = time between failures, **MTTF** = expected lifetime of a
non-repairable system. `[SNIPPET ONLY]`
([atlassian.com/incident-management/kpis/common-metrics](https://www.atlassian.com/incident-management/kpis/common-metrics))

**A second, less-discussed ambiguity: the start timestamp.** FireHydrant
computes **all four** of its metrics from **incident start**: MTTD = detection −
start, MTTA = acknowledgment − start, MTTM = mitigation − start, MTTR =
resolution − start. But incident.io and PagerDuty treat **MTTA as alert→ack**.
**FireHydrant's MTTA includes undetected time; incident.io's does not. Two tools
can report MTTA for the same incident and differ by the entire detection
window.** (Sources as above.)

Google sidesteps MTTR entirely, using **error budget / allowed downtime** — *"the
allowed quarterly downtime is around 13 minutes"* for 99.99%.
See also **F/CS-22**: the VOID argues MTTR is statistically invalid as a metric
at all.

---

## B4. Approvals, access control, and what the agent is not allowed to do

### B4.1 Change approval, CAB, and the DORA finding

- **Primary source:** *"DORA's research shows that these approaches have a
  negative impact on software delivery performance"*, referring to *"approval by
  people external to the team proposing the change: a change advisory board
  (CAB) or a senior manager."* `[FETCHED]`
  ([dora.dev/capabilities/streamlining-change-approval/](https://dora.dev/capabilities/streamlining-change-approval/))
- **The statistic:** external formal approval processes made respondents
  **2.6× more likely to be low performers**, from the 2019 Accelerate State of
  DevOps Report; external approvals were negatively correlated with lead time,
  deployment frequency and restore time, and had **no correlation with change
  fail rate**.
  **CAVEAT: the 2.6× figure is NOT on the dora.dev capability page (verified by
  direct fetch). It appears in search snippets citing
  [dora.dev/research/2019/dora-report/2019-dora-accelerate-state-of-devops-report.pdf](https://dora.dev/research/2019/dora-report/2019-dora-accelerate-state-of-devops-report.pdf),
  which returned unparseable binary. Verify before quoting.**
- **No evidence of the intended benefit:** DORA found no evidence that a more
  formal approval process is associated with lower change failure rates.
- **What DORA recommends instead:** *"Use peer review to meet the goal of
  segregation of duties, with reviews, comments, and approvals captured in the
  team's development platform"*, plus continuous testing, continuous integration,
  and comprehensive monitoring and observability.
- **The regulatory constraint that must still be satisfied:** *"changes must be
  approved by someone other than the author, thus ensuring that no individual has
  end-to-end control over a process."* — **structurally the two-person rule,
  satisfied by peer review rather than a board.**
- Secondary corroboration:
  [octopus.com/blog/change-advisory-boards-dont-work](https://octopus.com/blog/change-advisory-boards-dont-work)

### B4.2 Production access, break-glass, and the two-person rule

Primary source: Google's *Building Secure and Reliable Systems*, Ch. 5
`[FETCHED]`
([google.github.io/building-secure-and-reliable-systems/raw/ch05.html](https://google.github.io/building-secure-and-reliable-systems/raw/ch05.html)):

- **Least privilege:** *"users should have the minimum amount of access needed to
  accomplish a task, regardless of whether the access is from humans or
  systems."* Rationale: *"Unnecessary privilege leads to a growing surface area
  for possible mistakes, bugs, or compromise."*
- **Multi-Party Authorization (two-person rule):** *"Involving another person is
  one classic way to ensure a proper access decision."* Benefits include
  *"Preventing mistakes or unintentional violations of policy"*, *"Discouraging
  bad actors"*, and — notably — *"Auditing past actions for incident response or
  postmortem analysis."*
- **Break-glass, definition:** *"A breakglass mechanism provides access to your
  system in an emergency situation and bypasses your authorization system
  completely."*
- **Break-glass, controls:** *"The ability to use a breakglass mechanism should
  be highly restricted. In general, it should be available only to your SRE
  team."*; *"All uses of a breakglass mechanism should be closely monitored."*;
  and the requirement most often skipped — *"The breakglass mechanism should be
  tested regularly by the team(s) responsible for production services."*
- **Temporary access as the routine alternative:** *"You can grant temporary
  access in a structured and scheduled way (e.g., during on-call rotations, or via
  expiring group memberships) or in an on-demand fashion."* — **this ties
  elevated production privilege to the on-call shift boundary, making the handoff
  also a privilege transfer.**
- **Zero Touch Production:** *"The specific goal of these interfaces—like Zero
  Touch Production (ZTP)...and Zero Touch Networking (ZTN)—is to make Google safer
  and reduce outages by removing direct human access to production roles."*
  **This is the strongest single statement of what an agent should and should not
  be allowed to do: act through tooled, audited interfaces, never by direct
  production access.**
- **Fallback:** *"you can fall back to a heavily monitored and restricted proxy
  machine (or bastion)."*
- Compliance framing (secondary): SOC 2 / ISO 27001 / HIPAA / PCI DSS require
  documented approval, **time-bound access that auto-expires**, and tamper-proof
  command-level audit trails for break-glass
  ([hoop.dev/blog/compliance-requirements-and-best-practices-for-secure-break-glass-access](https://hoop.dev/blog/compliance-requirements-and-best-practices-for-secure-break-glass-access),
  [docs.cyberark.com/manage/latest/en/content/sca/dpaforcloud/breakglass.htm](https://docs.cyberark.com/manage/latest/en/content/sca/dpaforcloud/breakglass.htm)).

---

## B5. Handoffs, role name collisions, and status pages

### B5.1 On-call handoff

- **Google Workbook, minimal formal protocol:** *"At the start of each shift, the
  on-call engineer reads the handoff from the previous shift"* and *"At the end of
  the shift, the on-call engineer sends a handoff email to the next engineer
  on-call."* `[FETCHED]`
  ([sre.google/workbook/on-call/](https://sre.google/workbook/on-call/))
- **PagerDuty:** *"When your on-call 'shift' ends, let the next on-call know
  about issues that have not been resolved yet and other experiences of note."*
  ([response.pagerduty.com/oncall/being_oncall/](https://response.pagerduty.com/oncall/being_oncall/))
- **PagerDuty runs a retrospective on the shift itself**, not just on incidents:
  an *"On-Call Review Meeting"* at shift end to *"catch problems before they
  become trends."* `[FETCHED]`
  ([ownership.pagerduty.com/on-call/](https://ownership.pagerduty.com/on-call/))
- **incident.io's handoff content checklist** `[FETCHED]`: *"Active incidents:
  Current status, next steps, and severity for anything unresolved"*; *"Silenced
  alerts and upcoming deploys: What's muted, why, when it expires, and any risky
  changes"*; *"Relevant runbooks and dashboards: Specific URLs, not 'check
  Datadog'."* Format: a 30-minute weekly handoff with **both** engineers present,
  and **the incoming responder should summarize back** before the outgoing
  engineer disengages — a read-back confirmation, not a one-way email.
  ([incident.io/blog/on-call-best-practices-guide-2026](https://incident.io/blog/on-call-best-practices-guide-2026))
  **Note the silenced-alerts item: it is the human-process counterpart of
  F/CS-28.**
- **Escalation-policy structure:** primary → secondary at 5–15 min no-ack →
  engineering manager at 15 min → director/VP at 30 min, and *"Every escalation
  level must map to a specific person"* — never generic email addresses. (same)
- Google's cross-incident handoff sits in the **Planning** role, whose duties
  explicitly include *"arranging handoffs"*.
  **NO SOURCE FOUND for a detailed Google "follow-the-sun" incident handoff
  protocol** — the Workbook incident-response chapter does not describe one.
- **Unverified:** the claim that PagerDuty recommends the second escalation layer
  be *the prior week's on-call* appeared in search results attributed to PagerDuty
  docs but **was not confirmed in a direct fetch**. Treat as unverified.

### B5.2 Role definitions consolidated — and where the names collide

| Function | Google SRE Book | Google IMAG | PagerDuty | Atlassian | Datadog |
|---|---|---|---|---|---|
| Command | Incident Command | **Incident Commander** | **Incident Commander** | **Incident Manager** | **Incident Commander** |
| Deputy/standby | — | — | **Deputy** (hot standby) | — | — |
| Technical execution | **Ops lead** | **Operations Lead** | **SME / Resolver** | **Tech Lead** | **Workstream Leads** |
| External comms | Communication | **Communications Lead** | **Customer Liaison** | **Communications Manager** | **Customer Liaisons** |
| Internal comms | Communication | Communications Lead | **Internal Liaison** | Communications Manager | **Communications Leads** |
| Record-keeping | (Planning) | — | **Scribe** | (Tech Lead, secondary) | — |
| Sustainment/logistics | **Planning** | — | — | — | — |
| Executive interface | — | — | Internal Liaison | Comms Manager (secondary) | **Executive Leads** |

Definitions not already quoted:
- **Atlassian Incident Manager** — has overall responsibility and authority,
  coordinates and directs all facets of the response, empowered to page
  additional responders, and *"as a rule of thumb, the incident manager is
  responsible for all roles and responsibilities until they designate that role
  to someone else."* `[SNIPPET ONLY]`
  ([atlassian.com/incident-management/incident-response/roles-responsibilities](https://www.atlassian.com/incident-management/incident-response/roles-responsibilities))
- **Atlassian Communications Manager** — *"the person familiar with public
  communications, possibly from the customer support or public relations teams"*;
  *"is usually also the person who updates the status page."* `[SNIPPET ONLY]`
- **Atlassian Tech Lead** — *"typically a senior technical responder responsible
  for developing theories about what's broken and why, deciding on changes, and
  running the technical team during the incident."* `[SNIPPET ONLY]`
- **Datadog** — Incident Commander, **Workstream Leads** (coordinate multi-front
  responses), Communications Leads, **Executive Leads**, Customer Liaisons
  ([datadoghq.com/blog/how-datadog-manages-incidents/](https://www.datadoghq.com/blog/how-datadog-manages-incidents/)).

**Naming collisions any tooling must model:**
1. **No consistent name for the top role**: "Incident Commander"
   (Google/PagerDuty/Datadog) vs **"Incident Manager"** (Atlassian) — same
   function, different label.
2. **"Ops Lead" and "Tech Lead" are not the same role.** Google's Ops Lead
   *applies operational tools* (executes mitigations); Atlassian's Tech Lead
   *develops theories about what's broken and why* (diagnoses). One is an
   executor, the other a diagnostician-manager.
3. **Scribe exists as a standalone role only at PagerDuty.** Google folds it into
   Planning; Atlassian into Tech Lead's secondary duties; Datadog omits it.
4. **Google's Planning role has no analogue anywhere else.** Sustainment work —
   handoffs, food, bug-filing, tracking divergence from normal — is **unowned**
   in the PagerDuty, Atlassian and Datadog models.
5. **The one near-universal agreement:** the IC absorbs all undelegated roles —
   Google IMAG (*"By default, the IC assumes all roles that have not been
   delegated yet"*), PagerDuty (roles may be combined), Atlassian (*"responsible
   for all roles and responsibilities until they designate that role to someone
   else"*).

### B5.3 Status pages and communication cadence

- **Statuspage cadence:** *"Provide updates every 30 minutes (or whatever cadence
  is appropriate for the situation)"* until resolution. `[FETCHED]`
  ([support.atlassian.com/statuspage/docs/incident-communication-tips/](https://support.atlassian.com/statuspage/docs/incident-communication-tips/))
- **Statuspage content guidance:** initially *"Quickly acknowledge the issue,
  briefly summarize the known impact, promise further updates"*; throughout,
  *"honesty, clarity, and transparency"* in *"layman's terms"*; *"Own the
  problem"* with *"empathy, and apologize when necessary"*; maintain
  *"consistent (and relevant) updates across all communication channels."*
- **PagerDuty's internal cadence matches at ~30 min** — the Internal Liaison
  provides *"regular status updates in Slack (roughly every 30mins) to the
  executive team."*
- **Atlassian's app-ecosystem SLA is tighter and clocked from incident start**:
  for SEV 1 & 2, *"Incident response teams start an investigation within 15
  minutes of being paged and publish an initial status update within 1 hour of the
  incident start time."* `[FETCHED]`
  ([developer.atlassian.com/developer-guide/app-incident-severity-levels/](https://developer.atlassian.com/developer-guide/app-incident-severity-levels/))
- **Who writes it:** Atlassian assigns status-page updates to the Communications
  Manager; PagerDuty assigns public channels to the Customer Liaison and requires
  the IC to authorise external communication (*"the single authority on system
  status"*).
- **Cadence disagreement:** Statuspage's 30-minute default vs practitioner
  guidance of every 10–15 minutes for major incidents even when technical status
  has not materially changed, plus always stating exactly when the next update
  will land — **secondary sources, practitioner opinion, not vendor doctrine**
  ([getlogwise.com/blog/atlassian-status-page-incident-communication-playbook](https://getlogwise.com/blog/atlassian-status-page-incident-communication-playbook),
  [statusdrop.dev/guides/status-page-best-practices](https://statusdrop.dev/guides/status-page-best-practices)).
- **The status-page/internal-tracker semantic mismatch in B3.2 is the
  load-bearing integration risk**, and connects directly to F/CS-18.

---

## Explicit gaps

- **"Cognitive flow state"** in the Google on-call chapter — **NO SOURCE FOUND**.
  The chapter discusses intuitive-vs-rational decision modes under stress; it
  does not use "flow state".
- **An inverted severity ladder (SEV5 = worst)** — **NO SOURCE FOUND** after
  targeted searching.
- **Atlassian severity / roles / MTTx pages** — bodies not fetchable; quotes are
  from search snippets citing those URLs.
- **DORA "2.6× more likely to be low performers"** — not on the dora.dev
  capability page (verified); only in snippets citing the 2019 PDF.
- **PagerDuty "second escalation layer = prior week's on-call"** — not confirmed
  in direct fetch.
- **GitLab S1–S4 wording** — handbook.gitlab.com redirected to an auth endpoint;
  low confidence on exact wording.
- **Google IMAG on severity, follow-the-sun handoffs, lifecycle checklists** —
  confirmed genuinely absent from the Workbook chapter, not missed.
