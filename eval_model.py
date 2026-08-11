#!/usr/bin/env python3
"""Evaluate a model on the software-devops world (stdlib only).

  # sanity-check the harness with no API key and no tokens spent
  python3 eval_model.py --policy oracle

  # evaluate a model (needs ANTHROPIC_API_KEY)
  python3 eval_model.py --model claude-sonnet-5 --split heldout
  python3 eval_model.py --model claude-fable-5 --task tsk_gateway_rollback_sev1 -v

Each task runs in its own session fork, so tasks never contaminate each other.
Scoring is Horizon-SWE-style: binary `passed` (all checks) plus the graded
Horizon-PC `score` broken out by dimension (feature correctness 0.6,
deployment & DevOps 0.3, engineering quality 0.1). No LLM judge is involved —
verification is the world's executable verifier.
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile
import time
import math
import re
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from serve import World  # noqa: E402

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

SYSTEM_PROMPT = """You are an autonomous software engineer on call at NovaCart, \
a mid-size e-commerce SaaS. You have real tools for the whole engineering \
stack: tickets, pull requests, CI, deployments, feature flags, metrics, SLOs, \
alerts, logs, runbooks, dependency scanning, incidents, and chat.

Work the assignment end to end. Investigate before you change anything \
(logs and runbooks explain root causes and company policy), then carry the \
change all the way through to production and close the loop.

Company rules matter and are checked:
- A pull request carries structured changes; it only takes effect once CI \
passes and it is merged, and it only reaches an environment once deployed.
- Company policy is NOT in your instructions. It lives in the knowledge base: \
use search_docs / get_document to find the deployment, migration, incident, \
feature-flag, API-deprecation, security and flaky-test policies, and follow \
them. Deviating from a documented policy is scored as a failure.
- Do not fabricate state: never invent services, tests, or findings. Only \
change what the assignment requires.

Call tools one step at a time and check their results — a tool that returns \
ok=false did nothing. When the assignment is fully complete, reply with a \
short summary of what you did."""


def anthropic_tools(world):
    out = []
    for t in world.tools:
        schema = t.get("json_schema", {}).get("parameters") or {
            "type": "object", "properties": {}, "required": []}
        out.append({"name": t["name"],
                    "description": t["description"],
                    "input_schema": schema})
    return out


def call_api(api_key, model, messages, tools, max_tokens=4096, retries=5):
    payload = {"model": model, "max_tokens": max_tokens,
               "system": SYSTEM_PROMPT, "messages": messages, "tools": tools}
    data = json.dumps(payload).encode()
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(
            API_URL, data=data,
            headers={"content-type": "application/json",
                     "x-api-key": api_key,
                     "anthropic-version": API_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError("API %s: %s" % (e.code, body)) from None
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("exhausted API retries")


def run_model_episode(world, task, sid, api_key, model, max_turns, verbose):
    tools = anthropic_tools(world)
    messages = [{"role": "user", "content": task.get("_prompt") or task["instruction"]}]
    calls = 0
    log = []
    for turn in range(max_turns):
        resp = call_api(api_key, model, messages, tools)
        blocks = resp.get("content", [])
        messages.append({"role": "assistant", "content": blocks})
        tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
        if verbose:
            for b in blocks:
                if b.get("type") == "text" and b.get("text", "").strip():
                    print("      · %s" % b["text"].strip()[:150])
        if not tool_uses:
            break
        results = []
        for tu in tool_uses:
            out = world.call_tool(sid, tu["name"], tu.get("input") or {})
            calls += 1
            if verbose:
                print("      → %s(%s) %s" % (
                    tu["name"],
                    json.dumps(tu.get("input") or {})[:80],
                    json.dumps(out)[:90]))
            log.append("%s(%s) -> %s" % (tu["name"], json.dumps(tu.get("input") or {})[:160],
                                          json.dumps(out)[:160]))
            results.append({"type": "tool_result", "tool_use_id": tu["id"],
                            "content": json.dumps(out)[:4000],
                            "is_error": World._is_structured_error(out)})
        messages.append({"role": "user", "content": results})
    return {"turns": turn + 1, "tool_calls": calls, "transcript": "\n".join(log)}


def run_oracle_episode(world, task, sid, verbose):
    calls = 0
    log = []
    for c in task.get("expected_calls", []):
        out = world.call_tool(sid, c["tool"], c.get("args", {}))
        calls += 1
        if verbose:
            print("      → %s %s" % (c["tool"], json.dumps(out)[:80]))
        log.append("%s(%s)" % (c["tool"], json.dumps(c.get("args", {}))[:160]))
    return {"turns": 0, "tool_calls": calls, "transcript": "\n".join(log)}


def steps_to_answer(transcript):
    """AIOpsLab reports time-to-detect / localize / analyze. The discrete
    analogue here is the tool call at which the finding was submitted."""
    for i, line in enumerate(transcript.split("\n"), 1):
        if line.startswith("submit_diagnosis("):
            return i
    return None


def pass_hat_k(successes, n, k):
    """tau-bench pass^k: the probability that all k independently sampled
    trials of a task succeed, estimated as C(c, k) / C(n, k)."""
    if k > n or n == 0:
        return None
    return math.comb(successes, k) / math.comb(n, k) if successes >= k else 0.0


def dimension_breakdown(verdict):
    dims = {}
    for a in verdict.get("assertions") or []:
        d = dims.setdefault(a["dimension"], [0, 0])
        d[1] += 1
        if a["passed"]:
            d[0] += 1
    return {k: "%d/%d" % (v[0], v[1]) for k, v in sorted(dims.items())}


def dimension_fractions(verdict):
    """Per-dimension pass fraction, for the Horizon-SWE-PC composite."""
    dims = {}
    for a in verdict.get("assertions") or []:
        d = dims.setdefault(a["dimension"], [0, 0])
        d[1] += 1
        if a["passed"]:
            d[0] += 1
    return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in dims.items()}


QUALITY_RUBRIC = """You are grading one dimension of a software-engineering benchmark: \
ENGINEERING QUALITY (worth 10% of the composite score).

Judge only: commit scope (was the change minimal and focused?), code maintainability, \
and documentation/communication (ticket hygiene, PR description, status updates). \
Apply penalties for security issues, non-performant choices, and unproductive loops \
(repeated identical failing actions).

Do NOT re-judge whether the feature works or whether deployment was done correctly - \
those are scored separately by executable verifiers.

Reply with ONLY a JSON object: {"score": <float 0..1>, "reasons": "<one sentence>"}."""


def llm_quality_score(api_key, model, task, verdict, transcript):
    """Optional LLM judge for the engineering-quality dimension (the blog uses
    an LLM judge here; the deterministic checks remain the default)."""
    checks = "\n".join("- [%s] %s: %s" % ("PASS" if a["passed"] else "FAIL",
                                           a["name"], a["message"])
                        for a in (verdict.get("assertions") or [])
                        if a["dimension"] == "quality")
    body = ("TASK:\n%s\n\nWHAT THE AGENT DID (tool calls in order):\n%s\n\n"
            "DETERMINISTIC QUALITY SIGNALS:\n%s\n" %
            (task["instruction"][:2000], transcript[:6000], checks))
    payload = {"model": model, "max_tokens": 512,
               "system": QUALITY_RUBRIC,
               "messages": [{"role": "user", "content": body}]}
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": API_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in out.get("content", []))
        m = re.search(r'\{.*\}', text, re.S)
        return max(0.0, min(1.0, float(json.loads(m.group(0))["score"])))
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=str(pathlib.Path(__file__).parent / "world"))
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--policy", choices=["model", "oracle"], default="model")
    ap.add_argument("--split", choices=["train", "heldout", "all"], default="all")
    ap.add_argument("--category", action="append", default=None,
                    help="restrict to these Horizon-SWE categories (repeatable)")
    ap.add_argument("--guidance", choices=["standard", "guided"], default="standard",
                    help="standard = realistic ticket, policy must be discovered from the "
                         "knowledge base; guided = same task with the procedure spelled out")
    ap.add_argument("--trials", type=int, default=1,
                    help="run each task k times and report tau-bench pass^k reliability")
    ap.add_argument("--quality-judge", choices=["deterministic", "llm"],
                    default="deterministic",
                    help="how to score the 10%% engineering-quality dimension")
    ap.add_argument("--task", action="append", default=None,
                    help="run only these task ids (repeatable)")
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--out", default=None, help="write a JSON report here")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    world_dir = pathlib.Path(args.world)
    runtime = tempfile.mkdtemp(prefix="sdw_eval_")
    world = World(world_dir, runtime)
    splits = world.meta.get("splits", {})

    tasks = world.tasks
    if args.category:
        want = set(args.category)
        tasks = [t for t in tasks if t.get("category") in want]
    if args.task:
        wanted = set(args.task)
        tasks = [t for t in tasks if t["task_id"] in wanted]
    elif args.split != "all" and splits.get(args.split):
        wanted = set(splits[args.split])
        tasks = [t for t in tasks if t["task_id"] in wanted]
    if not tasks:
        print("no tasks selected", file=sys.stderr)
        return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if args.policy == "model" and not api_key:
        print("ANTHROPIC_API_KEY is not set. Use --policy oracle to smoke-test "
              "the harness without an API key.", file=sys.stderr)
        return 2

    label = args.model if args.policy == "model" else "oracle"
    print("evaluating %s on %s (%d task%s, split=%s)\n"
          % (label, world.summary()["world_id"], len(tasks),
             "" if len(tasks) == 1 else "s", args.split))

    records = []
    trials = {}
    for task in tasks:
      tid = task["task_id"]
      for trial in range(max(1, args.trials)):
        if trial == 0:
            print("  %-32s %-7s " % (tid, task.get("difficulty", "")), end="", flush=True)
        sid = world.create_session()
        started = time.time()
        try:
            if args.policy == "oracle":
                if args.verbose:
                    print()
                stats = run_oracle_episode(world, task, sid, args.verbose)
            else:
                if args.verbose:
                    print()
                task = dict(task)
                task["_prompt"] = (task.get("instruction_guided") if args.guidance == "guided"
                                   else task["instruction"])
                stats = run_model_episode(world, task, sid, api_key, args.model,
                                          args.max_turns, args.verbose)
            err = None
        except Exception as e:  # noqa: BLE001
            stats = {"turns": 0, "tool_calls": 0, "transcript": ""}
            err = "%s: %s" % (type(e).__name__, e)
        verdict = world.verify(sid, tid)
        fr = dimension_fractions(verdict)
        judged = None
        if args.quality_judge == "llm" and args.policy == "model":
            judged = llm_quality_score(api_key, args.model, task, verdict,
                                       stats.get("transcript", ""))
            if judged is not None:
                fr["quality"] = judged
        W = {"correctness": 0.6, "deployment": 0.3, "quality": 0.1}
        tw = sum(W[d] for d in fr) or 1.0
        pc = round(sum(W[d] / tw * v for d, v in fr.items()), 4)
        rec = {"task_id": tid, "category": task.get("category"),
               "difficulty": task.get("difficulty"),
               "passed": bool(verdict.get("passed")), "score": pc,
               "dimension_fractions": {k: round(v, 3) for k, v in sorted(fr.items())},
               "quality_judge": "llm" if judged is not None else "deterministic",
               "dimensions": dimension_breakdown(verdict),
               "tool_calls": stats["tool_calls"], "turns": stats["turns"],
               "steps_to_answer": steps_to_answer(stats.get("transcript", "")),
               "seconds": round(time.time() - started, 1),
               "error": err or verdict.get("error")}
        trials.setdefault(tid, []).append(bool(rec["passed"]))
        if trial > 0:
            continue
        records.append(rec)
        mark = "PASS" if rec["passed"] else "FAIL"
        extra = ""
        if rec.get("steps_to_answer"):
            extra = "  answer@%d" % rec["steps_to_answer"]
        print("%s  score=%.2f  %s  calls=%d%s"
              % (mark, rec["score"],
                 " ".join("%s %s" % (k[:4], v) for k, v in rec["dimensions"].items()),
                 rec["tool_calls"], extra))
        if not rec["passed"] and rec["error"]:
            print("        %s" % str(rec["error"])[:220])

    n = len(records)
    passed = sum(1 for r in records if r["passed"])
    mean_score = sum(r["score"] for r in records) / n
    print("\n  Horizon-SWE-PF  (pass rate, correctness+deployment must be perfect) : %.1f%%  (%d/%d)"
          % (100.0 * passed / n, passed, n))
    print("  Horizon-SWE-PC  (0.6 correctness / 0.3 deployment / 0.1 quality)     : %.1f"
          % (100.0 * mean_score))
    cats = {}
    for r in records:
        c = cats.setdefault(r.get("category") or "?", [0, 0, 0.0])
        c[1] += 1
        c[0] += 1 if r["passed"] else 0
        c[2] += r["score"]
    if len(cats) > 1:
        print("\n  by category:")
        for c in sorted(cats):
            p_, t_, sc = cats[c]
            print("    %-24s PF %3.0f%%  PC %4.1f   (%d task%s)"
                  % (c, 100.0 * p_ / t_, 100.0 * sc / t_, t_, "" if t_ == 1 else "s"))

    diag = [r for r in records if (r.get("category") or "").startswith("aiops_")]
    if diag:
        solved = [r for r in diag if r["passed"] and r.get("steps_to_answer")]
        print("\n  AIOpsLab-style diagnostics: %d task%s"
              % (len(diag), "" if len(diag) == 1 else "s"))
        for cat, label in [("aiops_detection", "time-to-detect"),
                           ("aiops_localization", "time-to-localize"),
                           ("aiops_analysis", "time-to-analyze")]:
            g = [r for r in solved if r.get("category") == cat]
            if g:
                print("    %-18s %-17s mean %.1f tool calls (n=%d)"
                      % (cat.split("_")[1], label,
                         sum(r["steps_to_answer"] for r in g) / len(g), len(g)))
    if args.trials > 1:
        n = args.trials
        print("\n  tau-bench reliability over %d trials per task:" % n)
        for k in range(1, n + 1):
            vals = [pass_hat_k(sum(v), len(v), k) for v in trials.values()]
            vals = [v for v in vals if v is not None]
            if vals:
                print("    pass^%d  %.3f" % (k, sum(vals) / len(vals)))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(
            {"world_id": world.summary()["world_id"], "policy": args.policy,
             "model": args.model if args.policy == "model" else None,
             "split": args.split, "guidance": args.guidance, "pass_rate": passed / n,
             "mean_score": mean_score, "trials": args.trials,
             "pass_hat_k": {str(k): (lambda vs: sum(vs) / len(vs) if vs else None)(
                 [v for v in (pass_hat_k(sum(x), len(x), k) for x in trials.values())
                  if v is not None])
                 for k in range(1, args.trials + 1)},
             "tasks": records}, indent=2) + "\n")
        print("  report: %s" % args.out)
    return 0 if passed == n or args.policy == "model" else 1


if __name__ == "__main__":
    sys.exit(main())
