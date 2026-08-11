"""The eval harness must run the world end-to-end and report Horizon-style
PF/PC numbers. Exercised with the oracle policy so it costs no tokens."""

import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

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

    # The category-free form of the same guard, and a stronger one: every task the
    # policy-blind agent actually PERTURBS must fail. A hardcoded read-only list
    # drifted every time a family was added - cross_system, attribution and
    # code_implementation each broke it in turn - which measured the task mix
    # rather than difficulty.
    sys.path.insert(0, str(ROOT))
    import eval_model as EM
    world_tasks = {t["task_id"]: t for t in
                   json.loads((ROOT / "world" / "tasks.json").read_text())}
    # Dropping a knowledge-base read is not itself a policy violation: looking a
    # standard up is instrumental, and no check grades it. What must be fatal is
    # skipping an actual procedural step - staging, a canary, an acknowledgement,
    # comms, migration ordering.
    # POLICY_STEPS mixes two different things. Some are procedural ACTIONS - the
    # canary, the acknowledgement, the announcement - and skipping one is a policy
    # violation. The rest are instrumental READS: looking up a standard, opening a
    # CI run, checking the traffic split. Skipping a read is not a violation, it is
    # working from memory, and it is only wrong when it produces a wrong answer.
    INSTRUMENTAL = {"search_docs", "get_document", "get_ci_run", "list_migrations",
                    "get_traffic_stats"}
    survived = []
    for rec in rep["tasks"]:
        task = world_tasks[rec["task_id"]]
        ref = [c for c in task.get("expected_calls", [])
               if c["tool"] not in INSTRUMENTAL]
        naive = [c for c in EM.naive_calls(task) if c["tool"] not in INSTRUMENTAL]
        skipped_procedure = (json.dumps(naive, sort_keys=True)
                             != json.dumps(ref, sort_keys=True))
        if skipped_procedure and rec["passed"]:
            survived.append(rec["task_id"])
    assert not survived, (
        "policy-blind agent passed %d task(s) whose reference solution it changed: %s. "
        "Each has a policy step that no longer affects the verdict."
        % (len(survived), survived[:8]))
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


def test_a_large_tool_result_is_narrowed_not_severed():
    """Capping a tool result by slicing its JSON string is quietly destructive.
    An unfiltered list_tickets() is 28,888 characters, so a 4,000-character cap
    handed the model a blob cut off mid-string: invalid JSON, no indication that
    anything was missing, and no way to distinguish "there are no more tickets"
    from "you were shown 14% of them". That is the same shape as every other
    defect this harness has produced - the model is denied evidence and cannot
    tell that it was.
    """
    import tempfile
    sys.path.insert(0, str(ROOT))
    from serve import World
    import cloud_backend

    world = World(ROOT / "world", tempfile.mkdtemp(prefix="fit_"))
    out = world.call_tool(world.create_session(), "list_tickets", {})
    assert len(json.dumps(out)) > cloud_backend.RESULT_BUDGET, \
        "pick a tool whose unfiltered result actually overflows"

    fitted = cloud_backend._fit(out)
    parsed = json.loads(fitted)                       # must still be valid JSON
    assert len(fitted) <= cloud_backend.RESULT_BUDGET
    assert parsed["truncated"]["omitted"] > 0
    assert parsed["truncated"]["shown"] == len(parsed["rows"])
    assert parsed["truncated"]["shown"] + parsed["truncated"]["omitted"] \
        == parsed["truncated"]["total"]
    assert "narrow" in parsed["truncated"]["hint"]

    # a result that fits is passed through untouched
    small = world.call_tool(world.create_session(), "get_service", {"service": "payments"})
    assert json.loads(cloud_backend._fit(small)) == small


def test_shard_merge_refuses_to_average_across_worlds(tmp_path):
    """A long sweep can be split across processes because episodes are
    independent. Rejoining them must refuse two things rather than paper over
    them: shards from different worlds, and shards from different models. A pass
    rate averaged across two worlds is a measurement of neither - which is
    exactly the failure that voided a sweep earlier, when a rebuild swapped the
    database underneath a running task set."""
    sys.path.insert(0, str(ROOT))
    import analyse_run

    def shard(path, world, model, ids):
        p = tmp_path / path
        p.write_text(json.dumps({
            "world_id": world, "model": model, "guidance": "standard", "split": "all",
            "tasks": [{"task_id": i, "outcome": "resolved", "passed": True,
                       "score": 1.0, "category": "c", "difficulty": "hard",
                       "tool_calls": 3} for i in ids]}))
        return str(p)

    a = shard("a.json", "w1", "m1", ["t1", "t2"])
    b = shard("b.json", "w1", "m1", ["t2", "t3"])       # t2 overlaps
    merged = analyse_run.load([a, b])
    assert [t["task_id"] for t in merged["tasks"]] == ["t1", "t2", "t3"], \
        "an overlapping task was counted twice"

    other_world = shard("c.json", "w2", "m1", ["t4"])
    with pytest.raises(AssertionError, match="different worlds"):
        analyse_run.load([a, other_world])

    other_model = shard("d.json", "w1", "m2", ["t5"])
    with pytest.raises(AssertionError, match="different models"):
        analyse_run.load([a, other_model])


def test_the_export_produces_a_package_matching_the_world(tmp_path):
    """The deliverable is produced by a separate command from the world build, so
    nothing forces the two to agree. A world rebuilt without a re-export yields
    verifiers for tasks that no longer exist - and a consumer would never notice,
    because the package is internally consistent and only wrong relative to the
    world it claims to grade.

    dist/ is build output and is not tracked, so this exports fresh rather than
    inspecting whatever happens to be on this machine: a test that depends on an
    untracked directory passes or fails on an accident of the working tree.
    """
    out = tmp_path / "harbor"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "export_harbor.py"), "--out", str(out)],
        capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr

    world = json.loads((ROOT / "world" / "world.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    mw = manifest.get("world_id") or (manifest.get("world") or {}).get("world_id")
    assert mw == world["world_id"], "export built %s but world/ is %s" % (mw, world["world_id"])

    shipped = [l for l in (out / "tasks" / "tasks.jsonl").read_text().splitlines() if l.strip()]
    assert len(shipped) == world["counts"]["tasks"]
    verifiers = list((out / "verifiers").glob("verify_*.py"))
    assert len(verifiers) == world["counts"]["tasks"], \
        "every task must ship a verifier: %d tasks, %d verifiers" % (
            world["counts"]["tasks"], len(verifiers))


def test_pass_hat_k_is_computed_and_degrades_with_k(tmp_path):
    """tau-bench's reliability metric: pass^k is the probability that all k
    independent attempts succeed. A model at 60% on one attempt and 20% at k=4 is
    unreliable in a way a single pass rate hides completely, so this is one of the
    three things that would count as evidence the world measures capability rather
    than luck. It had never been exercised.

    A deterministic policy must give 1.000 at every k - anything else means the
    metric is reading noise from the harness.
    """
    out = tmp_path / "pk.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "oracle",
         "--trials", "3", "--limit", "4", "--out", str(out)],
        capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text())
    assert report["trials"] == 3
    phk = report["pass_hat_k"]
    assert {str(k) for k in (1, 2, 3)} <= set(phk), phk
    assert all(abs(v - 1.0) < 1e-9 for v in phk.values()), \
        "a deterministic policy must be perfectly reliable at every k: %s" % phk
    # pass^k can never increase with k: it is the chance ALL k attempts succeed
    vals = [phk[str(k)] for k in (1, 2, 3)]
    assert all(a >= b - 1e-9 for a, b in zip(vals, vals[1:])), \
        "pass^k increased with k, which is impossible: %s" % phk


@pytest.mark.parametrize("args", [
    ["--policy", "oracle", "--category", "aiops_detection", "--limit", "2"],
    ["--policy", "oracle", "--split", "heldout", "--limit", "3"],
    ["--policy", "oracle", "--guidance", "guided", "--limit", "2"],
    ["--policy", "oracle", "--trials", "2", "--limit", "2"],
    ["--estimate"],
])
def test_eval_model_cli_surface_actually_runs(args, tmp_path):
    """--trials carried two bugs for its whole existence - a pass rate above 100%
    and a non-zero exit on a healthy world - purely because nothing ever ran it.
    Every flag a user is told about in the README gets exercised here, so the next
    unused option fails loudly rather than on the day someone tries it."""
    cmd = [sys.executable, str(ROOT / "eval_model.py")] + args
    if "--estimate" not in args:
        cmd += ["--out", str(tmp_path / "r.json")]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, "%s failed: %s" % (args, proc.stderr[-400:])
    if "--estimate" in args:
        assert "input tokens" in proc.stdout
        return
    report = json.loads((tmp_path / "r.json").read_text())
    assert 0.0 <= report["pass_rate"] <= 1.0, \
        "pass_rate out of range for %s: %s" % (args, report["pass_rate"])
    assert report["world_id"]


@pytest.mark.parametrize("args", [
    ["--policy", "naive", "--guidance", "guided", "--attempts", "1", "--limit", "2"],
    ["--policy", "naive", "--attempts", "2", "--limit", "2",
     "--category", "aiops_detection"],
])
def test_calibrate_cli_surface_actually_runs(args, tmp_path):
    out = tmp_path / "c.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "calibrate.py")] + args + ["--out", str(out)],
        capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, "%s failed: %s" % (args, proc.stderr[-400:])
    report = json.loads(out.read_text())
    # provenance: a bucket distribution is only interpretable against its world
    assert report["world_id"] and report["guidance"] and report["buckets"]


def test_the_llm_judge_refuses_rather_than_pretends():
    """--quality-judge llm accepted a scripted policy and then silently did
    nothing: the run looked judged and was not. It now refuses, because a flag
    that accepts a request and ignores it is worse than one that declines.

    The judge itself has the same failure shape. Its first budget was 300 tokens,
    and a reasoning model spent all of it thinking and emitted no content - so the
    judge returned its "unreachable" sentinel on exactly the sloppy transcripts it
    exists to catch, because those are the ones it deliberates over longest.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "oracle",
         "--quality-judge", "llm", "--limit", "1"],
        capture_output=True, text=True, timeout=300)
    assert proc.returncode == 2, "a judge with no model to ask must refuse"
    assert "needs a model policy" in proc.stderr

    sys.path.insert(0, str(ROOT))
    import cloud_backend
    assert cloud_backend.judge_quality.__defaults__[0] >= 1000, \
        "the judge budget is small enough for a reasoning model to spend it all thinking"
    # with no credential it must return None, never a number it did not earn
    import os
    saved = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        assert cloud_backend.judge_quality("deepseek", "m", {"instruction": "x"},
                                           {"assertions": []}, "trace") is None
    finally:
        if saved is not None:
            os.environ["DEEPSEEK_API_KEY"] = saved


def test_world_content_is_never_mistaken_for_our_own_outage():
    """`classify_outcome` briefly searched the transcript for harness symptoms, and
    one symptom was the string "API ". The world ships a status page post titled
    "API latency affecting some customers" and documents called "API deprecation"
    and "API gateway" - so any agent that read them had its failure relabelled as
    our infrastructure failing and DELETED from the pass rate, since harness
    episodes are excluded rather than counted.

    Six real failures vanished this way in a live sweep, inflating PF from 65.4%
    to 84.6% before it was caught. Loose English markers are matched against the
    error field only; the transcript is searched solely for symptoms specific
    enough to be unambiguous there.
    """
    sys.path.insert(0, str(ROOT))
    from eval_model import classify_outcome, HARNESS_TRANSCRIPT_MARKERS

    trace = ('list_status_page_posts({}) -> {"rows": [{"title": "API latency '
             'affecting some customers"}]}')
    verdict = {"error": "assertion: correctness/legacy_retired - /v1/orders must be retired"}
    assert classify_outcome(False, None, trace, verdict, 7, 30, "model") == "agent", \
        "world content in a transcript was read as our outage"

    # a genuine provider failure still lands as harness, from the transcript
    assert all(m.startswith("HARNESS:") for m in HARNESS_TRANSCRIPT_MARKERS), \
        "transcript-matched markers must be unambiguous, not English phrases"
    assert classify_outcome(False, None, "HARNESS: provider error: HTTP 429", {},
                            3, 30, "model") == "harness"
    # and from the error field, where loose markers are safe
    assert classify_outcome(False, "HTTPError 500", "", {}, 3, 30, "model") == "harness"


def test_reports_written_before_the_fix_are_repaired(tmp_path):
    """The bug's footprint is exactly recoverable, so reports already on disk are
    corrected rather than thrown away: an episode is misattributed only if marked
    `harness` while its recorded error carries no harness or environment symptom."""
    sys.path.insert(0, str(ROOT))
    import analyse_run

    tasks = [
        # misattributed: a real model failure, wrongly excluded
        {"task_id": "a", "outcome": "harness", "passed": False, "turns": 7,
         "error": "assertion: correctness/legacy_retired"},
        # misattributed and out of budget
        {"task_id": "b", "outcome": "harness", "passed": False, "turns": 30,
         "error": "assertion: correctness/fault_type_correct"},
        # genuinely our infrastructure - must stay excluded
        {"task_id": "c", "outcome": "harness", "passed": False, "turns": 4,
         "error": "HTTPError 503 from the provider"},
        # world-side breakage - excluded, but relabelled correctly
        {"task_id": "d", "outcome": "harness", "passed": False, "turns": 4,
         "error": "no such table: widgets"},
        {"task_id": "e", "outcome": "resolved", "passed": True, "turns": 5, "error": None},
    ]
    out = {t["task_id"]: t["outcome"] for t in analyse_run.repair_attribution(tasks)}
    assert out == {"a": "agent", "b": "capped", "c": "harness", "d": "environment",
                   "e": "resolved"}, out


def test_a_sharded_run_reports_incomplete_coverage(tmp_path):
    """A sharded run that quietly evaluates 77 of 83 tasks produces a pass rate
    that looks complete and is not - which happened, when a shell read loop
    dropped the last task of every shard. The runner must notice and say so."""
    out = tmp_path / "sharded.json"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "run_sharded.py"), "--policy", "oracle",
         "--shards", "3", "--category", "aiops_detection", "--out", str(out)],
        capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    merged = json.loads(out.read_text())
    world = json.loads((ROOT / "world" / "tasks.json").read_text())
    want = {t["task_id"] for t in world if t["category"] == "aiops_detection"}
    assert {t["task_id"] for t in merged["tasks"]} == want, \
        "a deliberate subset must be evaluated in full"
    # a subset is not "incomplete"; only a run that misses its own scope is
    assert "INCOMPLETE" not in proc.stdout, proc.stdout
    assert "incomplete" not in merged

    sys.path.insert(0, str(ROOT))
    import analyse_run
    short = analyse_run.load([str(out)], expected=sorted(want) + ["tsk_never_ran"])
    assert short["incomplete"] == ["tsk_never_ran"]


def test_repair_leaves_correctly_attributed_reports_alone():
    """The repair pass rewrites `harness` episodes whose recorded error carries no
    harness symptom. That was right for reports from the buggy version, and wrong
    for anything newer: a provider outage is recorded in the transcript, which is
    not in the report, so a legitimate harness episode looks identical to a
    misattributed one from the outside.

    Reports now record WHY an outcome was chosen at the moment it was chosen, and
    repair skips any record carrying that field.
    """
    sys.path.insert(0, str(ROOT))
    import analyse_run

    old_style = [{"task_id": "a", "outcome": "harness", "passed": False, "turns": 5,
                  "error": "assertion: correctness/legacy_retired"}]
    assert analyse_run.repair_attribution(old_style)[0]["outcome"] == "agent"

    new_style = [{"task_id": "b", "outcome": "harness", "passed": False, "turns": 5,
                  "error": "assertion: correctness/legacy_retired",
                  "outcome_reason": "matched 'HARNESS: provider error'"}]
    assert analyse_run.repair_attribution(new_style)[0]["outcome"] == "harness", \
        "a self-describing report was second-guessed by the repair pass"


def test_terminal_adapter_enumerates_and_parses():
    """terminal-bench tasks run in the containers they ship rather than inside the
    simulation. The parts that can be tested without docker are the two that were
    actually wrong: what counts as a runnable task, and how a test result is read
    out of pytest output."""
    sys.path.insert(0, str(ROOT))
    import terminal_adapter as TA

    names = TA.list_tasks()
    assert len(names) > 100, "expected terminal-bench tasks on disk, found %d" % len(names)
    for n in names[:5]:
        d = TA.TASKS / n
        assert (d / "Dockerfile").exists() and (d / "run-tests.sh").exists(), n

    assert TA.parse_tests("== 3 passed in 0.04s ==") == (3, 0)
    assert TA.parse_tests("== 1 failed, 2 passed ==") == (2, 1)
    assert TA.parse_tests("collected 0 items\n2 errors") == (0, 2)
    # the failure mode that produced a 0% oracle: tests never ran at all
    assert TA.parse_tests("uv: command not found") == (0, 0)


def test_terminal_adapter_runs_the_container_with_a_network():
    """The first oracle run scored 0% with a correct solution, because the container
    had --network none and terminal-bench's own run-tests.sh installs curl and uv
    before it can grade anything. The container boundary is the isolation that
    matters; the network is not optional."""
    src = (ROOT / "terminal_adapter.py").read_text()
    run_block = src[src.index("def run_task("):src.index("def main(")]
    # the flag itself, not the comment that explains why it is absent
    code = "\n".join(l for l in run_block.splitlines() if not l.strip().startswith("#"))
    assert '"--network", "none"' not in code, (
        "the task container must not be network-isolated: terminal-bench's grader "
        "installs its own dependencies before it can run")
