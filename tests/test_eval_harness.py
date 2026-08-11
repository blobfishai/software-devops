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
    assert len(report["tasks"]) == 50
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
    assert len(json.loads(out.read_text())["tasks"]) == 9

    env_no_key = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval_model.py"), "--policy", "model"],
        capture_output=True, text=True, timeout=120, env=env_no_key)
    assert proc.returncode == 2
    assert "ANTHROPIC_API_KEY" in proc.stderr
