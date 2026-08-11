"""Solvability lint: can every task be solved from evidence inside the world?

A self-play probe found a task whose "correct" answer required attributing alert
firings to a service through a label (`edge_cache_service`) that resolved to
nothing. A careful agent would have reasoned better than the answer key and
failed. That is withheld data rather than contradictory data, which the research
names as the line between realistic chaos and cruel chaos
(research/notes/domain/F_chaos_scenarios.md, F5).

These tests find the whole class rather than that one instance.
"""

import json
import pathlib
import sqlite3

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect("file:%s?mode=ro" % (ROOT / "world" / "environment.db"), uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def resolvable(conn):
    """Every name a task could have to reason about, and what it resolves to."""
    canon = {r[0] for r in conn.execute("SELECT name FROM services")}
    alias = {r[0]: r[1] for r in conn.execute("SELECT alias, canonical FROM service_aliases")}
    return canon, alias


def test_every_alerting_label_resolves_to_a_service(db):
    """An alert rule whose service_label resolves to nothing cannot be attributed
    to an incident by any evidence in the world."""
    canon, alias = resolvable(db)
    unresolved = []
    for r in db.execute("SELECT rule_id, name, service_label FROM alert_rules"):
        lab = r["service_label"]
        if not lab:
            continue          # cluster-wide rules legitimately have no service
        if lab not in canon and lab not in alias:
            unresolved.append((r["rule_id"], r["name"], lab))
    # A rule naming a service that no longer exists is deliberate chaos (CS-13),
    # but it must be *detectably* orphaned, not silently unattributable.
    orphans = [u for u in unresolved if "legacy" in u[2] or "legacy" in u[1].lower()]
    genuine = [u for u in unresolved if u not in orphans]
    assert not genuine, (
        "alert rules whose service_label resolves to nothing and are not marked "
        "legacy/orphaned: %s" % genuine)


def test_every_prometheus_label_resolves(db):
    canon, alias = resolvable(db)
    bad = [r[0] for r in db.execute("SELECT DISTINCT label_service FROM prom_series")
           if r[0] not in canon and r[0] not in alias]
    assert not bad, "Prometheus service labels that resolve to nothing: %s" % bad


def test_every_vendor_service_reference_resolves(db):
    """PagerDuty, Sentry and the spreadsheet each spell services their own way.
    Every spelling must map back, or the naming chaos becomes unsolvable."""
    canon, alias = resolvable(db)
    problems = []
    for table, col in (("pd_services", "name"), ("sentry_projects", "slug"),
                       ("owner_spreadsheet", "service_label")):
        for r in db.execute("SELECT %s FROM %s" % (col, table)):
            v = r[0]
            if v and v not in canon and v not in alias:
                problems.append("%s.%s=%r" % (table, col, v))
    assert not problems, "vendor service spellings with no alias: %s" % problems


def test_every_task_answer_is_derivable_from_a_readable_source(db):
    """Each reconciliation and judgement task declares required_sources; every one
    must be reachable by at least one read tool."""
    tools = json.loads((ROOT / "world" / "tools.json").read_text())
    readable = set()
    for t in tools:
        readable.update(t.get("read_tables", []))
    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    missing = []
    for t in tasks:
        for c in t.get("expected_calls", []):
            if c["tool"] != "submit_answer":
                continue
            for src in c.get("args", {}).get("sources", []):
                if src not in readable:
                    missing.append((t["task_id"], src))
    assert not missing, "answers cite sources no tool can read: %s" % missing


def test_no_task_depends_on_a_tool_the_world_does_not_have(db):
    tools = {t["name"] for t in json.loads((ROOT / "world" / "tools.json").read_text())}
    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    unknown = sorted({c["tool"] for t in tasks for c in t.get("expected_calls", [])} - tools)
    assert not unknown, "reference solutions call tools that do not exist: %s" % unknown


def test_documented_policies_are_all_discoverable(db):
    """Every policy a verifier enforces but the prompt no longer states must be
    findable in the knowledge base."""
    body = " ".join(r[0] + " " + r[1] for r in db.execute("SELECT title, body FROM documents"))
    required = ["staging", "canary", "promote_canary", "apply_migration", "test_fix",
                "3 consecutive green", "50 percentage", "use_secret_manager",
                "#security", "postmortem", "status page"]
    missing = [k for k in required if k not in body]
    assert not missing, "policies enforced but not documented anywhere: %s" % missing
