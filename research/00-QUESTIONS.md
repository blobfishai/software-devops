# Research questions — the software-engineering agent world

The purpose of this document is to stop us from inventing a world and calling it
realistic. Every question below must be answered **with a citation** — a file in
`research/repos/`, a URL in `research/SOURCES.md`, or an explicit note that the
answer is a judgement call with no source. Answers land in `01-THESIS.md`.

Research is deliberately multi-round. Round 1 answers what the corpus states
directly. Round 2 asks what the corpus *implies* but never says, which is where
the interesting tasks live.

---

## A. Domain and business value

- **A1.** What is this domain, precisely? Where does "software engineering agent"
  end and "DevOps / SRE / platform engineering agent" begin? Do the benchmarks
  agree on the boundary?
- **A2.** Who pays for an agent here, and for what outcome? Cost per incident,
  engineer hours, MTTR, change failure rate, release throughput?
- **A3.** What does the business lose when the agent is wrong? Rank the failure
  costs: a bad deploy, a missed regression, a leaked secret, a wrong diagnosis,
  a wasted engineer-hour.
- **A4.** Which parts of this work are *already* automated by deterministic
  tooling, and therefore uninteresting as agent tasks?

## B. Stakeholders and the shape of the work

- **B1.** Who are the humans in the loop? On-call engineer, service owner, EM,
  SRE, security, release manager, support. What does each hand the agent, and
  what do they expect back?
- **B2.** Where does work *originate*? Alert, ticket, customer complaint, code
  review, scheduled audit, a colleague's Slack message?
- **B3.** What does "done" mean to each stakeholder, and do those definitions
  conflict? (An SRE's "mitigated" is not a PM's "fixed".)
- **B4.** What is the agent explicitly *not* allowed to do, and who enforces it?
- **B5.** What approvals or handoffs interrupt the workflow, and how does an
  agent represent "I am blocked on a human"?

## C. Task taxonomy

- **C1.** What task types do the benchmarks in the corpus actually contain?
  Enumerate per repo, with counts where stated.
- **C2.** What is the *distribution* of task length — how many tool calls, how
  many files touched, how many services?
- **C3.** Which tasks are single-shot (patch a repo) versus long-horizon
  (investigate → change → ship → verify → communicate)?
- **C4.** Which task types appear in more than one benchmark? Those are the
  domain's consensus tasks.
- **C5.** What task types appear in *articles and postmortems* but in **no**
  benchmark? Those are the gaps worth building.
- **C6.** For each task type: what is the verifiable definition of done, and is
  it state-based, answer-based, or judged?

## D. Input documents and context

- **D1.** What documents does a real engineer read to do this work? Runbooks,
  ADRs, design docs, postmortems, API specs, dashboards, alert payloads,
  PR descriptions, commit history, Slack threads, on-call handoff notes.
- **D2.** Which of those are *authoritative* versus *stale*, and how does a real
  engineer tell? (Stale documentation is a first-class hazard, not noise.)
- **D3.** What do real alert payloads, CI logs, and incident timelines actually
  look like? Field names, formats, verbosity.
- **D4.** How much of the answer is typically *not* written down anywhere?

## E. Tools and integrations

- **E1.** Which tools does this domain actually use? Enumerate by category:
  source control, issue tracking, CI/CD, deploy/orchestration, observability,
  error tracking, incident management, security scanning, knowledge base,
  communication, spreadsheets.
- **E2.** For each tool, what does its **MCP server** expose — exact tool names,
  arguments, return shapes? (Cite the server repo.)
- **E3.** For each tool, what does its **REST API** expose that the MCP server
  does not? Where is the MCP surface narrower than reality?
- **E4.** Which tools *overlap*, so that the same fact exists in two places with
  different values? (Jira vs Linear, Datadog vs Prometheus, Sentry vs logs.)
- **E5.** Where does data live outside a system of record — a spreadsheet, a
  local SQLite, a wiki table someone maintains by hand, a CSV export?
- **E6.** What are the real authentication, rate-limit, and pagination
  behaviours that shape how an agent must call these tools?

## F. Chaos — why this is hard in real life

- **F1.** What are the documented ways this data is inconsistent in practice?
  Duplicate tickets, drifting service names, environments named differently per
  tool, stale dashboards, orphaned alerts, half-migrated systems.
- **F2.** Which reconciliation questions do humans actually ask that require
  joining across tools? ("How many customer-facing incidents this week?" needs
  incidents + status page + severity conventions that differ per team.)
- **F3.** What ambiguity exists in the *request itself*? ("This week" — calendar
  week or trailing 7 days? Which timezone? Does a rolled-back deploy count?)
- **F4.** What traps punish an agent that trusts a single source?
- **F5.** Which chaos is realistic versus merely cruel? (A task should be hard
  because reality is messy, not because we hid the data.)

## G. Evaluation design

- **G1.** How does each benchmark in the corpus verify a task? Exact mechanism.
- **G2.** What do they do about flakiness, and what does that tell us?
- **G3.** What metrics do they report, and what does each metric fail to
  capture?
- **G4.** What reward-hacking have they observed or guarded against?
- **G5.** How do they separate *environment failure* from *model failure*?
  (Critical: our calibration loop must not mistake our own bugs for difficulty.)
- **G6.** What is their task-generation process, and how much is human-authored?

## H. Difficulty and calibration

- **H1.** What reported pass rates exist per benchmark and per model? Those are
  our difficulty anchors.
- **H2.** What makes a task *flaky* for a model rather than simply hard? Which
  boundary conditions produce partial success?
- **H3.** What are the documented failure modes — where do agents actually go
  wrong? (Premature completion, ignoring policy, tunnel vision on one tool,
  hallucinated state, giving up, loops.)
- **H4.** How do we deepen an easy task honestly — more tool calls, more
  services, more ambiguity, longer horizon — without making it merely tedious?

---

## Round 2 questions (asked only after Round 1 is answered)

- **R1.** Which of our existing 63 tasks has no analogue anywhere in the corpus?
  Is that a novel contribution or a sign we invented something unrealistic?
- **R2.** Which corpus task types do we currently have *no* coverage of?
- **R3.** Where does our world's chaos differ from documented real chaos?
- **R4.** Which of our tools has an MCP surface that does not match the real
  server's surface, and does that matter for transfer?
