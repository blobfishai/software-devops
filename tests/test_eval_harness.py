"""The eval harness must run the world end-to-end and report Horizon-style
PF/PC numbers. Exercised with the oracle policy so it costs no tokens."""

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_oracle_policy_scores_perfect(tmp_path):
    out = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "oracle",
         "--out", str(out)],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report["pass_rate"] == 1.0
    assert report["mean_score"] == 1.0
    # read the count rather than restate it: a hard-coded number turns every
    # legitimate addition to the world into a spurious test failure
    counts = json.loads((ROOT / "world" / "world.json").read_text())["counts"]
    assert len(report["tasks"]) == counts["tasks"]
    for t in report["tasks"]:
        assert t["passed"] and t["score"] == 1.0
        assert "correctness" in t["dimensions"]
    assert "Horizon-SWE-PF" in proc.stdout and "100.0%" in proc.stdout


def test_split_selection_and_missing_key(tmp_path):
    out = tmp_path / "heldout.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "oracle",
         "--split", "heldout", "--out", str(out)],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    splits = json.loads((ROOT / "world" / "world.json").read_text())["splits"]
    assert len(json.loads(out.read_text())["tasks"]) == len(splits["heldout"])
    assert splits["heldout"], "the heldout split is empty"
    assert not (set(splits["heldout"]) & set(splits["train"])), "splits overlap"

    env_no_key = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "model"],
        capture_output=True, text=True, timeout=120, env=env_no_key)
    assert proc.returncode == 2
    assert "ANTHROPIC_API_KEY" in proc.stderr


def test_policy_blind_baseline_fails_the_change_tasks(tmp_path):
    """Difficulty guard. A scripted agent that makes the correct technical fix but
    ignores every documented policy must fail every task that involves shipping a
    change. If this starts passing, the tasks have gone soft."""
    out = tmp_path / "naive.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "naive", "--out", str(out)],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    rep = json.loads(out.read_text())
    by_cat = {}
    for t in rep["tasks"]:
        by_cat.setdefault(t["category"], []).append(t["passed"])

    # The meaningful guard: a policy-blind agent must pass NO task that ships a
    # change. A global threshold would drift every time a read-only family is
    # added, which is a property of the task mix, not of difficulty.
    change = ["error_rate_reduction", "latency_optimization", "feature_flag",
              "security_incident", "api_migration", "multi_service_rollout"]
    for c in change:
        assert not any(by_cat[c]), "%s must be policy-sensitive, got %s" % (c, by_cat[c])

    # Its overall pass rate must therefore be exactly the read-only share: read-only
    # families have no deployment policy to violate, so they legitimately survive.
    read_only = [c for c in by_cat if c.startswith("aiops_")
                 or c in ("reconciliation", "judgement", "flaky_test")]
    expected = sum(len(by_cat[c]) for c in read_only) / len(rep["tasks"])
    assert abs(rep["pass_rate"] - expected) < 0.02, (
        "policy-blind pass rate %.3f should equal the read-only share %.3f - anything "
        "higher means a change task stopped being policy-sensitive"
        % (rep["pass_rate"], expected))
    assert all(by_cat["aiops_detection"])


def test_naive_baseline_still_gets_the_technical_fix_right(tmp_path):
    """The baseline is meant to isolate process, not competence: correctness should
    stay high even as deployment collapses."""
    out = tmp_path / "naive2.json"
    subprocess.run([sys.executable, str(ROOT / "eval_model.py"), "--policy", "naive",
                    "--out", str(out)], capture_output=True, text=True, timeout=300, check=True)
    rep = json.loads(out.read_text())
    fixes = [t for t in rep["tasks"] if t["category"] == "error_rate_reduction"]
    for t in fixes:
        assert t["dimension_fractions"]["correctness"] == 1.0, t["task_id"]
        assert t["dimension_fractions"]["deployment"] < 1.0, t["task_id"]


def test_harbor_export_is_self_contained_and_faithful(tmp_path):
    """Requirement: the world ships in Harbor format and a lab can score a
    rollout without importing anything of ours. Every verifier must be
    standalone, and a solved rollout must score 1.0 through it."""
    import pathlib as _p
    import sys as _s
    import tempfile as _t
    out = tmp_path / "harbor"
    proc = subprocess.run([sys.executable, str(ROOT / "export_harbor.py"),
                           "--out", str(out)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr

    for required in ("task.yaml", "manifest.json", "tasks/tasks.jsonl",
                     "verifiers/verifier_index.json", "environment/db.sqlite",
                     "environment/run.sh", "rewards/reward_config.json", "Dockerfile"):
        assert (out / required).exists(), required

    manifest = json.loads((out / "manifest.json").read_text())
    index = json.loads((out / "verifiers" / "verifier_index.json").read_text())
    lines = [json.loads(x) for x in
             (out / "tasks" / "tasks.jsonl").read_text().splitlines() if x.strip()]
    assert len(lines) == len(index) == manifest["counts"]["tasks"]
    assert manifest["scoring"]["weights"] == {"correctness": 0.6, "deployment": 0.3,
                                              "quality": 0.1}

    # a verifier must not import anything from this repository
    body = (out / "verifiers" / ("verify_%s.py" % lines[0]["task_id"])).read_text()
    for forbidden in ("from serve", "import serve", "build.", "tasks_def", "tools_src"):
        assert forbidden not in body, forbidden

    # and a solved rollout must score 1.0 through it
    _s.path.insert(0, str(ROOT))
    from serve import World as _W
    runtime = _t.mkdtemp()
    world = _W(_p.Path(ROOT / "world"), runtime)
    task = {t["task_id"]: t for t in world.tasks}["tsk_payments_retry"]
    sid = world.create_session()
    for c in task["expected_calls"]:
        world.call_tool(sid, c["tool"], c.get("args", {}))
    db = _p.Path(runtime) / (sid + ".db")
    v = json.loads(subprocess.run(
        [sys.executable, str(out / "verifiers" / "verify_tsk_payments_retry.py"), str(db)],
        capture_output=True, text=True, timeout=120).stdout)
    assert v["passed"] is True and v["reward"] == 1.0 and v["score"] == 1.0, v


def test_fault_attribution_depends_on_who_made_the_call():
    """A model that invents a tool name has made an agent error; a scripted
    reference solution that does the same is OUR bug. Conflating them sends you
    hunting for environment bugs that do not exist - a first calibration sweep
    flagged four tasks TASK_FAULT for exactly that reason."""
    sys.path.insert(0, str(ROOT))
    from calibrate import looks_environmental
    trace = 'get_alerts({}) -> {"ok": false, "error": "unknown tool: get_alerts"}'
    assert looks_environmental(trace, {}, "model") == []
    assert looks_environmental(trace, {}, "scripted") == ["unknown tool"]

    badargs = 'submit_diagnosis({...}) -> {"error": "bad arguments for submit_diagnosis"}'
    assert looks_environmental(badargs, {}, "model") == []
    assert looks_environmental(badargs, {}, "scripted")

    # world-side faults count against the world no matter who tripped them
    for t in ('x -> no such table: widgets', 'y -> Traceback (most recent call last)'):
        assert looks_environmental(t, {}, "model")
        assert looks_environmental(t, {}, "scripted")
    assert looks_environmental("", {"error": "verifier execution failed: boom"}, "model")


def test_the_model_can_see_every_tool_its_task_requires():
    """A harness that hides tools scores its own blind spot as task difficulty.

    The first calibration sweep showed only the first 48 of 82 tools, which hid
    both submission tools and the whole vendor layer from the model - 40 of 76
    tasks needed at least one tool that was never on the menu. The model was
    instructed to call `submit_diagnosis`, could not see its schema, and looped
    guessing argument names until the turn budget ran out. That is a harness
    defect, and it was being reported as TOO_HARD.
    """
    sys.path.insert(0, str(ROOT))
    import local_backend
    tools = json.loads((ROOT / "world" / "tools.json").read_text())
    tasks = json.loads((ROOT / "world" / "tasks.json").read_text())
    menu = local_backend._tool_digest(tools)

    required = {c["tool"] for t in tasks for c in t.get("expected_calls", [])}
    unlisted = sorted(n for n in required if (n + "(") not in menu)
    assert not unlisted, "tools a reference solution needs but the model never sees: %s" % unlisted

    # argument names must survive verbatim: they are what the model must reproduce
    by_name = {t["name"]: t for t in tools}
    for name in ("submit_diagnosis", "submit_answer"):
        line = next(l for l in menu.splitlines() if l.startswith(name + "("))
        props = by_name[name].get("json_schema", {}).get("parameters", {}).get("properties", {})
        missing = [p for p in props if p not in line]
        assert not missing, "%s hides arguments %s from the model" % (name, missing)


def test_bad_argument_errors_say_what_is_accepted():
    """An error that names only what was wrong makes a model guess. The runtime
    returns the accepted signature so a wrong call is recoverable in one turn."""
    sys.path.insert(0, str(ROOT))
    from serve import World
    w = World(ROOT / "world", tempfile.mkdtemp(prefix="argerr_"))
    out = w.call_tool(w.create_session(), "submit_diagnosis",
                      {"scope": "payments", "finding": "slo breach"})
    assert out["ok"] is False
    assert "fault_detected" in out["accepts"]["required"]
    assert "evidence" in out["accepts"]["optional"]
    assert out["hint"].startswith("submit_diagnosis(")


def test_the_harbor_package_works_outside_this_repo():
    """The deliverable is dist/harbor, and it has to work for someone who does not
    have this repository. harbor_selftest.py copies the package and the world to a
    temp directory, then runs each shipped verifier as a subprocess with no repo on
    sys.path, no repo in cwd and a stripped environment - checking both halves:
    an untouched world is rejected, and the reference solution is accepted.

    Run over a sample here so the suite stays fast; the full 82-task sweep is
    `python3 harbor_selftest.py`.
    """
    proc = subprocess.run([sys.executable, str(ROOT / "harbor_selftest.py"), "--limit", "6"],
                          capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "free-reward 0" in proc.stdout, proc.stdout
    assert "failures 0, missing 0" in proc.stdout, proc.stdout


def test_a_provider_outage_is_never_scored_as_difficulty():
    """An API that rate-limits, times out or 500s tells you nothing about the task.
    It must land in TASK_FAULT alongside world-side breakage rather than TOO_HARD,
    or a bad afternoon on someone else's service becomes a difficulty measurement."""
    sys.path.insert(0, str(ROOT))
    from calibrate import looks_environmental
    trace = "HARNESS: provider error: HTTP 429: rate limit exceeded"
    assert looks_environmental(trace, {}, "model"), "a provider outage read as agent failure"
    assert looks_environmental(trace, {}, "scripted")


def test_eval_model_does_not_delete_a_models_own_mistakes_from_the_pass_rate():
    """eval_model EXCLUDES harness and environment episodes from the pass rate, so
    anything misfiled as `environment` is not merely mislabelled - it is deleted
    from the denominator, and every score built on it is inflated.

    This file used to treat "unknown tool" and "bad arguments for" as environment
    faults unconditionally. calibrate.py was fixed for exactly this and eval_model
    was not, which is how a rule duplicated in two files drifts. A model guessing
    a tool name is an agent error; a scripted policy hitting the same error means
    we wrote the reference solution wrong.
    """
    sys.path.insert(0, str(ROOT))
    from eval_model import classify_outcome

    guess = 'get_alerts({}) -> {"ok": false, "error": "unknown tool: get_alerts"}'
    assert classify_outcome(False, None, guess, {}, 3, 30, "model") == "agent"
    assert classify_outcome(False, None, guess, {}, 3, 30, "scripted") == "environment"

    badargs = 'submit_diagnosis(...) -> {"error": "bad arguments for submit_diagnosis"}'
    assert classify_outcome(False, None, badargs, {}, 3, 30, "model") == "agent"
    assert classify_outcome(False, None, badargs, {}, 3, 30, "scripted") == "environment"

    # world-side breakage counts against the world no matter who tripped it
    for who in ("model", "scripted"):
        assert classify_outcome(False, None, "x -> no such table: widgets", {}, 3, 30, who) \
            == "environment"
    # a provider outage is a harness outcome, never the agent's
    assert classify_outcome(False, None, "HARNESS: provider error: HTTP 429", {}, 3, 30,
                            "model") == "harness"
    # and a pass is a pass
    assert classify_outcome(True, None, guess, {}, 3, 30, "model") == "resolved"
