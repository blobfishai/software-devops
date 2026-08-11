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
    assert len(report["tasks"]) == 63
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
    assert len(json.loads(out.read_text())["tasks"]) == 12

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
    assert rep["pass_rate"] < 0.40, "policy-blind agent should not clear 40%%: %s" % rep["pass_rate"]

    by_cat = {}
    for t in rep["tasks"]:
        by_cat.setdefault(t["category"], []).append(t["passed"])
    change = ["error_rate_reduction", "latency_optimization", "feature_flag",
              "security_incident", "api_migration", "multi_service_rollout"]
    for c in change:
        assert not any(by_cat[c]), "%s must be policy-sensitive, got %s" % (c, by_cat[c])
    # the read-only diagnostics have no deployment policy to violate, so they survive
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
