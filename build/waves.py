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
    SYMPTOM = {
        "payments": "card payments are being declined that should not be",
        "checkout": "customers cannot complete a purchase",
        "search": "search is taking so long people give up",
        "catalog": "product pages are slow to show a price",
        "inventory": "stock reservations are failing at the last step",
        "media-service": "product images take too long to appear",
        "notifications": "order confirmation emails are not arriving",
        "analytics-worker": "the overnight reports came out wrong",
        "api-gateway": "everything feels slow, across the whole site",
        "storefront-web": "a customer said the site felt sluggish yesterday",
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
            "scope": "report-%s" % service, "service": service,
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


WAVES = {
    1: [w1_detection, w1_flaky_triage, w1_vulnerabilities],
    2: [w2_dependency_span],
    3: [w3_symptom_only],
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
