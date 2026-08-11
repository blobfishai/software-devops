"""The eval harness must run the world end-to-end and report Horizon-style
PF/PC numbers. Exercised with the oracle policy so it costs no tokens."""

import json
import pathlib
import subprocess
import sys

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
    assert len(report["tasks"]) == 76
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
    assert len(json.loads(out.read_text())["tasks"]) == 14

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
