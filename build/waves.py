"""Generate task waves by composing the world's own state.

Volume is not depth, and a permutation is not a task. What makes these worth
generating is that each asks a question whose answer is DERIVED from the built
database rather than written down: change the seed and the expected answer moves
with it, so a wave cannot drift into being wrong the way a hand-written answer
key does. The engine reads the database AFTER it is built, so it can never
generate a task about an entity that does not exist or assert a value the world
does not hold.

Waves run in increasing order of what they demand:

  1 breadth      the same question asked of every entity it applies to. Shallow
                 on purpose: it is the floor, and a model that cannot clear it is
                 not being measured by anything above.
  2 span         the fault is one hop from the symptom, so the service the alarm
                 names is not the service to change.
  3 ambiguity    the target is not named; the request carries a customer-visible
                 symptom and the agent selects what it is about.
  4 horizon      the work continues past the fix into verification and comms, so
                 stopping when the diff is right fails.
  5 composition  several faults at once, or an answer that exists only in the
                 join of systems that disagree.

Every generated task goes through the gates a hand-written one does: its verifier
must fail on the pristine seed, its reference solution must replay through the
real tools, and the replay must then score exactly 1.0. A wave that produces
something unverifiable does not ship it - the build fails and says which.
"""

import sqlite3


def _rows(db, sql, args=()):
    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# wave 1 — breadth
# ---------------------------------------------------------------------------

def w1_detection(db):
    """Is this service violating this specific SLO, right now?

    One task per SLO the world defines, each answer computed from the production
    metric against the threshold. Two of the twelve pairs are healthy, which is
    the whole point: without them a model that always answers "yes" scores 83%
    and looks capable.
    """
    out = []
    for r in _rows(db, """
            SELECT s.service, s.metric, s.threshold, m.value
            FROM slos s JOIN service_metrics m
              ON m.service = s.service AND m.metric = s.metric
            WHERE m.environment = 'production'
            ORDER BY s.service, s.metric"""):
        breaching = r["value"] > r["threshold"]
        short = "errors" if "error" in r["metric"] else "latency"
        out.append({
            "generator": "detection", "category": "aiops_detection",
            "wave": 1, "axis": "breadth",
            "id": "w1_detect_%s_%s" % (r["service"].replace("-", "_"), short),
            "scope": r["service"], "service": r["service"],
            "fault_detected": breaching,
            "fault_type": "unclassified" if breaching else "none",
            "difficulty": "easy" if breaching else "medium",
            "budget": 8,
            "evidence": ("%s %s is %g against a %g threshold, which %s the SLO"
                         % (r["service"], r["metric"], r["value"], r["threshold"],
                            "breaches" if breaching else "satisfies")),
            "ticket": ("SLO-%d" % (7100 + len(out)), "medium",
                       "Is %s meeting its %s objective?" % (r["service"], short)),
        })
    return out


def w1_flaky_triage(db):
    """Is this test intermittent, or did it fail for a reason?

    The catalogue marks six tests flaky and six passing. Quarantining a test that
    is not flaky hides a real defect, so a wave containing only flaky tests would
    reward quarantining everything.
    """
    out = []
    for r in _rows(db, "SELECT service, name, status FROM tests_catalog "
                       "ORDER BY service, name"):
        flaky = r["status"] == "flaky"
        out.append({
            "generator": "detection", "category": "aiops_detection",
            "wave": 1, "axis": "breadth",
            "id": "w1_triage_%s" % r["name"].replace(".", "_").replace("-", "_").lower(),
            "scope": r["service"], "service": r["service"],
            "fault_detected": flaky, "fault_type": "unclassified" if flaky else "none",
            "difficulty": "medium", "budget": 8,
            "evidence": ("the test catalogue records %s as %s"
                         % (r["name"], r["status"])),
            "ticket": ("QA-%d" % (7200 + len(out)), "medium",
                       "Is %s intermittent, or did it fail for a reason?" % r["name"]),
        })
    return out


def w1_vulnerabilities(db):
    """Is this service still exposed to this CVE?

    Three of four are open and one is already remediated, so "yes" is not a
    strategy.
    """
    out = []
    for r in _rows(db, "SELECT cve, package, service, severity, status FROM "
                       "vulnerabilities ORDER BY cve"):
        exposed = r["status"] != "remediated"
        out.append({
            "generator": "detection", "category": "aiops_detection",
            "wave": 1, "axis": "breadth",
            "id": "w1_cve_%s" % r["cve"].replace("-", "_").lower(),
            "scope": r["service"], "service": r["service"],
            "fault_detected": exposed,
            "fault_type": "unclassified" if exposed else "none",
            "difficulty": "medium", "budget": 8,
            "evidence": ("%s in %s is recorded as %s for %s"
                         % (r["cve"], r["package"], r["status"], r["service"])),
            "ticket": ("SEC-%d" % (7300 + len(out)), "high",
                       "Is %s still exposed to %s?" % (r["service"], r["cve"])),
        })
    return out


# ---------------------------------------------------------------------------
# wave 2 — span: the fault is one hop from the symptom
# ---------------------------------------------------------------------------

def w2_dependency_span(db):
    """A service is breaching, and so is something it depends on.

    Wave 1 asks whether a service is healthy. This asks which service to change,
    when the one carrying the alarm is downstream of the one carrying the fault.
    Only edges where BOTH ends are breaching are emitted - where the dependency is
    healthy there is no span to traverse and the honest answer is the alarmed
    service itself, which wave 1 already covers.
    """
    breaching = {r["service"] for r in _rows(db, """
        SELECT s.service FROM slos s JOIN service_metrics m
          ON m.service = s.service AND m.metric = s.metric
        WHERE m.environment = 'production' AND m.value > s.threshold""")}
    out = []
    for r in _rows(db, "SELECT service, depends_on, kind FROM service_dependencies "
                       "ORDER BY service, depends_on"):
        up, down = r["depends_on"], r["service"]
        if down not in breaching or up not in breaching:
            continue
        alert = _rows(db, "SELECT alert_id FROM alerts WHERE service=? AND status='firing' "
                          "LIMIT 1", (down,))
        if not alert:
            continue
        out.append({
            "generator": "localization", "category": "aiops_localization",
            "wave": 2, "axis": "span",
            "id": "w2_span_%s_from_%s" % (down.replace("-", "_"), up.replace("-", "_")),
            "scope": str(alert[0]["alert_id"]), "service": up,
            "fault_type": "unclassified", "offending_key": "",
            "difficulty": "hard", "budget": 12,
            "evidence": ("%s is alarming, but it calls %s over %s and %s is itself "
                         "breaching its objective; the alarm follows the dependency "
                         "rather than originating where it fires"
                         % (down, up, r["kind"], up)),
            "ticket": ("SPAN-%d" % (7400 + len(out)), "high",
                       "Alarm on %s - is %s where the fault is?" % (down, down)),
        })
    return out


# ---------------------------------------------------------------------------
# wave 3 — ambiguity: the target is not named
# ---------------------------------------------------------------------------

def w3_symptom_only(db):
    """The same detection question, asked the way a person would ask it.

    Wave 1 names the service. This gives the customer-visible symptom and the
    agent works out what it is about, which is the difference between reading a
    dashboard and taking a report.
    """
    # Written the way a customer describes a problem, which is to say without
    # naming a service - "my card keeps getting refused", not "payments is
    # erroring". Two of these used to name the service they were asking about,
    # which made the task look hard and grade easy.
    SYMPTOM = {
        "payments": "my card keeps getting refused at the last step, and my bank says "
                    "there is nothing wrong with it",
        "checkout": "I can put things in the basket but I cannot finish buying them",
        "search": "I type in the box and wait, and I gave up before anything appeared",
        "catalog": "the product page loads but the price takes ages to show up",
        "inventory": "it lets me order something and then says it is unavailable",
        "media-service": "the pictures take forever to appear on product pages",
        "notifications": "I bought something an hour ago and still have no email",
        "analytics-worker": "the numbers in this morning's report do not add up",
        "api-gateway": "the whole site feels slow today, every page of it",
        "storefront-web": "someone mentioned the site felt sluggish yesterday",
    }
    metrics = {(r["service"], r["metric"]): (r["value"], r["threshold"]) for r in _rows(db, """
        SELECT s.service, s.metric, s.threshold, m.value FROM slos s
        JOIN service_metrics m ON m.service = s.service AND m.metric = s.metric
        WHERE m.environment = 'production'""")}
    out = []
    for service, symptom in sorted(SYMPTOM.items()):
        pairs = [(k, v) for k, v in metrics.items() if k[0] == service]
        if not pairs:
            continue
        breaching = any(v > t for _, (v, t) in pairs)
        (_, metric), (value, threshold) = sorted(pairs)[0]
        out.append({
            "generator": "detection", "category": "aiops_detection",
            "wave": 3, "axis": "ambiguity",
            "id": "w3_symptom_%s" % service.replace("-", "_"),
            # NOT "report-<service>": the whole axis is that the target is not
            # named, and putting it in the scope string hands the answer over in
            # the same sentence that asks for it. The ticket number is opaque.
            "scope": "SUP-%d" % (7500 + len(out)), "service": service,
            "symptom": ("Support passed this on from a customer: \"%s\". Nobody has "
                        "attached it to a service yet." % symptom),
            "fault_detected": breaching,
            "fault_type": "unclassified" if breaching else "none",
            "difficulty": "hard", "budget": 12,
            "evidence": ("the report points at %s; its %s is %g against a %g threshold"
                         % (service, metric, value, threshold)),
            "ticket": ("SUP-%d" % (7500 + len(out)), "high",
                       "Customer report: %s" % symptom[:52]),
        })
    return out


# ---------------------------------------------------------------------------
# wave 5 — composition: several faults at once
# ---------------------------------------------------------------------------

# The world's concurrent faults, each with the service and mechanism that is
# actually responsible. Drawn from the seeded state rather than invented: every
# one is the answer to a hand-written task elsewhere in the suite, which is what
# makes attributing them together a different question rather than a longer one.
CONCURRENT_FAULTS = [
    {"scope": "media-upload-stalls", "symptom": "media uploads are stalling",
     "service": "media-service", "fault_type": "node_unhealthy",
     "offending_key": "node-b3",
     "reads": [{"tool": "k8s_pods_list", "args": {"service": "media-service"}},
               {"tool": "k8s_nodes_list", "args": {"node": "node-b3"}}],
     "evidence": "both replicas sit on node-b3, which reports DiskPressure at 97%"},
    {"scope": "gateway-latency-surge", "symptom": "api-gateway p99 is 1030ms against 250ms",
     "service": "api-gateway", "fault_type": "bad_release", "offending_key": "v5.1.0",
     "reads": [{"tool": "list_deployments",
                "args": {"service": "api-gateway", "environment": "production"}}],
     "evidence": "p99 moved when v5.1.0 was promoted; it leaks an upstream connection "
                 "per request, so only a rollback recovers it"},
    {"scope": "checkout-error-spike", "symptom": "checkout errors are 5.5% against 1.0%",
     "service": "checkout", "fault_type": "feature_flag_regression",
     "offending_key": "instant_refunds",
     "reads": [{"tool": "list_feature_flags", "args": {"environment": "production"}}],
     "evidence": "checkout errors track the instant_refunds rollout rather than any deploy"},
    {"scope": "analytics-connection-refused",
     "symptom": "analytics cannot reach the replica",
     "service": "analytics-worker", "fault_type": "misconfig",
     "offending_key": "pg-replica",
     "reads": [{"tool": "check_network_path", "args": {"blocked_only": True}}],
     "evidence": "the path is REFUSED at the transport layer, so a network policy rather "
                 "than capacity"},
    {"scope": "catalog-latency-sawtooth", "symptom": "catalog latency arrives in waves",
     "service": "catalog", "fault_type": "resource_exhaustion",
     "offending_key": "heap_used_pct",
     "reads": [{"tool": "get_runtime_stats", "args": {"service": "catalog"}}],
     "evidence": "94% heap, 780ms p99 GC pause, 41 collections a minute"},
    {"scope": "payments-error-rate", "symptom": "payments errors are 4.2% against 1.0%",
     "service": "payments", "fault_type": "missing_retry",
     "offending_key": "notifications_retry_max_attempts",
     "reads": [{"tool": "search_logs", "args": {"service": "payments"}}],
     "evidence": "the notifications call times out with no retry configured"},
]


def w5_attribution(db):
    """Several symptoms at once, each with its own cause.

    Composition rather than length: the cheap strategy - find the most dramatic
    thing in the estate and attribute everything to it - fails every task here,
    and it is the strategy a frontier model actually used when asked why media
    uploads were stalling.

    Triples are drawn so that no two tasks share the same set, and so that each
    set spans at least three distinct fault mechanisms. A triple of three
    misconfigs would be a longer task; a triple spanning a node, a release and a
    flag is a different one.
    """
    faults = CONCURRENT_FAULTS
    combos, seen = [], set()
    for i in range(len(faults)):
        for j in range(i + 1, len(faults)):
            for k in range(j + 1, len(faults)):
                trio = (faults[i], faults[j], faults[k])
                kinds = {f["fault_type"] for f in trio}
                services = {f["service"] for f in trio}
                if len(kinds) < 3 or len(services) < 3:
                    continue           # not a composition, just a longer list
                key = tuple(sorted(f["scope"] for f in trio))
                if key in seen:
                    continue
                seen.add(key)
                combos.append(trio)
    out = []
    for n, trio in enumerate(combos[:12]):     # a spread, not the whole cross product
        out.append({
            "generator": "attribution", "category": "attribution",
            "wave": 5, "axis": "composition",
            "id": "w5_attr_%s" % "_".join(f["service"].split("-")[0] for f in trio),
            "difficulty": "expert",
            "items": [dict(f) for f in trio],
            "ticket": ("MULTI-%d" % (7600 + n), "critical",
                       "Three alarms at once - one incident or three?"),
        })
    return out


# ---------------------------------------------------------------------------
# wave 6 — ported clerical work, generated across the filter space
# ---------------------------------------------------------------------------

def w6_filter_and_act(db):
    """TheAgentCompany's sde/pm shape: filter one system, act in another.

    The queue of portable source tasks is long and they reduce to a handful of
    shapes over a filter. Generating them is honest only if each task asks a
    DIFFERENT question, so a candidate is dropped when its result set duplicates
    one already emitted, is empty, or is everything - a filter that selects all
    issues is not a filter and a model that ignores it scores full marks.
    """
    issues = _rows(db, "SELECT number, repo, title, state, labels, created_day "
                       "FROM github_issues ORDER BY number")
    if not issues:
        return []
    all_nums = [i["number"] for i in issues]

    def select(state=None, label=None, repo=None, since=None):
        out = []
        for i in issues:
            if state and i["state"] != state:
                continue
            if label and label not in [x.strip() for x in i["labels"].split(",")]:
                continue
            if repo and i["repo"] != repo:
                continue
            if since is not None and i["created_day"] < since:
                continue
            out.append(i["number"])
        return out

    labels = sorted({x.strip() for i in issues for x in i["labels"].split(",") if x.strip()})
    repos = sorted({i["repo"] for i in issues})
    filters = []
    for lb in labels:
        filters.append(({"state": "open", "label": lb},
                        "open and labelled '%s'" % lb))
    for rp in repos:
        filters.append(({"state": "open", "repo": rp},
                        "open in %s" % rp))
    for day in (404, 410, 416):
        filters.append(({"state": "open", "since": day},
                        "open and raised on day %d or later" % day))
    for lb in ("priority", "customer-report", "regression"):
        for day in (404, 412):
            filters.append(({"state": "open", "label": lb, "since": day},
                            "open, labelled '%s', and raised on day %d or later" % (lb, day)))

    MODES = [("report", "#eng"), ("copy", "#eng"), ("count", "#eng")]
    out, seen_sets = [], set()
    for spec, prose in filters:
        want = select(**spec)
        if not want or len(want) == len(all_nums):
            continue                       # empty, or not a filter at all
        key = tuple(want)
        if key in seen_sets:
            continue                       # a different filter, the same question
        seen_sets.add(key)
        mode, channel = MODES[len(out) % len(MODES)]
        titles = {i["number"]: i["title"] for i in issues}
        excluded = [n for n in all_nums if n not in want]
        base = {
            "generator": "crosssystem", "category": "cross_system",
            "wave": 6, "axis": "ported-clerical",
            "source_repo": "TheAgentCompany",
            "source_path": ("research/repos/evals/TheAgentCompany__TheAgentCompany/"
                            "workspaces/tasks/sde-collect-open-issues"),
            "mode": mode, "channel": channel,
            "expected": want, "excluded": excluded,
            "difficulty": "hard" if len(spec) > 2 else "medium",
            "id": "w6_%s_%d" % (mode, len(out)),
        }
        if mode == "report":
            base["ask"] = ("Post one message to %s naming every issue that is %s. "
                           "Anything outside that filter must not appear - the list is "
                           "acted on as written." % (channel, prose))
            base["report_body"] = ("Issues %s: " % prose) + "; ".join(
                "%d %s" % (n, titles[n]) for n in want)
            base["ticket"] = ("W6-%04d" % len(out), "medium",
                              "Report the issues that are %s" % prose)
        elif mode == "copy":
            base["copy_service"] = ""
            base["copy_titles"] = {n: titles[n] for n in want}
            base["ask"] = ("Every issue that is %s needs a matching ticket on our board, "
                           "citing the issue number it came from. Nothing outside the "
                           "filter gets copied. Tell %s once they are mirrored."
                           % (prose, channel))
            base["ticket"] = ("W6-%04d" % len(out), "high",
                              "Mirror the issues that are %s" % prose)
        else:
            base["question_id"] = "Q-W6-%d" % len(out)
            base["answer"] = len(want)
            base["sources"] = ["github_issues"]
            base["assumptions"] = "Counted issues that are %s." % prose
            base["ask"] = ("How many issues are %s? Submit the number with "
                           "submit_answer(question_id='Q-W6-%d', answer=..., "
                           "sources=[...])." % (prose, len(out)))
            base["ticket"] = ("W6-%04d" % len(out), "medium",
                              "How many issues are %s?" % prose)
        out.append(base)
    return out


WAVES = {
    1: [w1_detection, w1_flaky_triage, w1_vulnerabilities],
    2: [w2_dependency_span],
    3: [w3_symptom_only],
    5: [w5_attribution],
    6: [w6_filter_and_act],
}


def generate(db, waves=(1,)):
    """Spec dicts ready for tasks_def, derived from the built database."""
    out = []
    seen = set()
    for w in waves:
        for fn in WAVES.get(w, []):
            for spec in fn(db):
                if spec["id"] in seen:
                    continue           # a wave must never emit the same task twice
                seen.add(spec["id"])
                out.append(spec)
    return out
