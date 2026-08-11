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
import collections
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


POLICY_STEPS = {"search_docs", "get_document", "acknowledge_alert", "post_message",
                "publish_status_update", "assess_canary", "promote_canary", "list_migrations",
                "get_ci_run", "get_traffic_stats"}


def naive_calls(task):
    """Strip the policy-driven work out of the reference solution: no knowledge-base
    lookup, no staging rehearsal, no canary, no comms, no alarm acknowledgement, and
    traffic moved in one jump. What survives is the technically-correct fix."""
    out = []
    for c in task.get("expected_calls", []):
        t, a = c["tool"], dict(c.get("args", {}))
        if t in POLICY_STEPS:
            continue
        if t in ("deploy_service", "apply_migration") and a.get("environment") == "staging":
            continue
        if t == "deploy_service":
            a.pop("canary_percent", None)          # straight to 100% in production
        out.append({"tool": t, "args": a})
    # collapse staged traffic shifts into a single move per endpoint
    last = {}
    for i, c in enumerate(out):
        if c["tool"] == "shift_endpoint_traffic":
            last[(c["args"]["service"], c["args"]["path"])] = i
    keep = [i for i, c in enumerate(out)
            if c["tool"] != "shift_endpoint_traffic"
            or last[(c["args"]["service"], c["args"]["path"])] == i]
    return [out[i] for i in keep]


def merged_only_calls(task):
    """The classic agent failure: treats a merged pull request as done. Everything
    up to and including the merge, nothing that carries it to an environment."""
    out = []
    for c in task.get("expected_calls", []):
        if c["tool"] in ("deploy_service", "promote_canary", "assess_canary",
                         "apply_migration", "rollback_deployment", "shift_endpoint_traffic"):
            continue
        out.append(c)
    return out


def no_verify_calls(task):
    """Ships the change correctly but never closes the loop: no metric check, no
    alarm handling, no incident update, no comms, no ticket update."""
    return [c for c in task.get("expected_calls", [])
            if c["tool"] not in ("query_metrics", "acknowledge_alert", "resolve_alert",
                                 "resolve_error_event", "update_incident", "post_message",
                                 "publish_status_update", "update_ticket", "create_ticket",
                                 "get_slo_status", "list_alerts")]


def shortcut_calls(task):
    """Takes the forbidden shortcut wherever the world offers one: quarantines a
    flaky test instead of fixing it, and blames whichever service the alarm names
    instead of tracing the fault to its source."""
    out = []
    for c in task.get("expected_calls", []):
        t, a = c["tool"], json.loads(json.dumps(c.get("args", {})))
        if t == "open_pull_request":
            for ch in a.get("changes", []):
                if ch.get("change_type") == "test_fix":
                    ch["payload"]["action"] = "quarantine"
        if t == "submit_diagnosis" and str(a.get("scope", "")).isdigit():
            a["service"] = ALARMED_SERVICE.get(str(a["scope"]), a.get("service", ""))
        out.append({"tool": t, "args": a})
    return out


# which service each seeded alarm is raised on - the lazy answer
ALARMED_SERVICE = {"9601": "payments", "9602": "search", "9603": "checkout",
                   "9604": "api-gateway", "9605": "catalog", "9606": "inventory",
                   "9607": "media-service", "9608": "notifications",
                   "9609": "analytics-worker", "9610": "checkout"}

SCRIPTED = {"oracle": lambda t: t.get("expected_calls", []), "shortcut": shortcut_calls,
            "naive": naive_calls, "merged_only": merged_only_calls,
            "no_verify": no_verify_calls}


def run_scripted_episode(world, task, sid, verbose, policy):
    calls, log = 0, []
    for c in SCRIPTED[policy](task):
        out = world.call_tool(sid, c["tool"], c.get("args", {}))
        calls += 1
        if verbose:
            print("      → %s %s" % (c["tool"], json.dumps(out)[:80]))
        log.append("%s(%s)" % (c["tool"], json.dumps(c.get("args", {}))[:160]))
    return {"turns": 0, "tool_calls": calls, "transcript": "\n".join(log)}


def run_naive_episode(world, task, sid, verbose):
    calls = 0
    log = []
    for c in naive_calls(task):
        out = world.call_tool(sid, c["tool"], c.get("args", {}))
        calls += 1
        if verbose:
            print("      → %s %s" % (c["tool"], json.dumps(out)[:80]))
        log.append("%s(%s)" % (c["tool"], json.dumps(c.get("args", {}))[:160]))
    return {"turns": 0, "tool_calls": calls, "transcript": "\n".join(log)}


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


# vivaria is the only benchmark in the corpus that types this and derives run
# status from it in SQL so the two cannot drift; everyone else collects a rich
# failure vocabulary and averages it away at scoring time
# (research/notes/evals/METR__vivaria.md, research/notes/evals/_CROSS_CUTTING.md).
# Environment failure is first-order here, not noise: AlgoTune's own oracle passes
# only ~85%, and three SWE-bench Verified tasks fail with the oracle agent.
ERROR_SOURCE = ("agent", "harness", "environment", "serverOrTask", "capped", "user")
# Symptoms of OUR infrastructure failing. Only ever matched against the error
# field, never the transcript: these are loose English phrases, and a transcript
# is full of world content that legitimately contains them. Widening the search to
# the transcript deleted six genuine model failures from a pass rate, because the
# world ships a status page post titled "API latency affecting some customers" and
# documents called "API deprecation" and "API gateway".
HARNESS_MARKERS = ("API ", "exhausted API retries", "urlopen", "HTTPError", "timed out")
# The one harness symptom recorded in the transcript rather than the error field,
# and specific enough to be safe there.
HARNESS_TRANSCRIPT_MARKERS = ("HARNESS: provider error", "HARNESS: DEEPSEEK_API_KEY",
                              "HARNESS: OPENAI_API_KEY")
# Symptoms that mean the WORLD is broken, whoever tripped them.
ENVIRONMENT_MARKERS = ("no such table", "database is locked", "verifier execution failed",
                       "Traceback", "InternalError")
# Symptoms that are the world's fault only when a SCRIPTED policy hits them. A
# script calls exactly what it was written to call, so "unknown tool" means we
# wrote the reference solution wrong. A model generates tool names and arguments
# freely, so the same error is the agent guessing - and vivaria's rule applies: an
# agent is never permitted to attribute its own mistake to the server.
#
# This file used to treat all of these as `environment` unconditionally, which
# silently EXCLUDED such episodes from the pass rate. A model that guessed a tool
# name had its failure deleted rather than counted, inflating every score built on
# it. calibrate.py was fixed for this weeks before eval_model.py was, which is
# exactly how a duplicated rule drifts.
CALLER_DEPENDENT_MARKERS = ("unknown tool", "bad arguments for",
                            "missing required parameter")


def classify_outcome(passed, err, transcript, verdict, turns, max_turns, caller="model"):
    """Attribute an episode. An agent may never be blamed for a harness fault, an
    agent may never blame the world for its own guess, and a budget exhaustion is
    its own outcome rather than a failure."""
    if passed:
        return "resolved"
    blob = "%s %s" % (err or "", verdict.get("error") or "")
    hay = "%s %s" % (blob, transcript or "")
    if any(m in blob for m in HARNESS_MARKERS) or \
            any(m in hay for m in HARNESS_TRANSCRIPT_MARKERS):
        return "harness"
    markers = ENVIRONMENT_MARKERS
    if caller == "scripted":
        markers = markers + CALLER_DEPENDENT_MARKERS
    if any(m in hay for m in markers):
        return "environment"
    if turns >= max_turns:
        return "capped"
    return "agent"


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
    ap.add_argument("--policy", choices=["model", "deepseek", "openai", "oracle", "naive",
                                        "merged_only", "no_verify", "shortcut"],
                    default="model",
                    help="scripted baselines that map the difficulty surface for free: "
                         "naive ignores every documented policy; merged_only treats merging the "
                         "pull request as the finish line; no_verify ships the fix but never "
                         "checks or closes anything")
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
    ap.add_argument("--limit", type=int, default=None,
                    help="evaluate only the first N selected tasks (cheap smoke test)")
    ap.add_argument("--estimate", action="store_true",
                    help="estimate the token cost of this run and exit without calling the API")
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
    if args.limit:
        tasks = tasks[:args.limit]
    if not tasks:
        print("no tasks selected", file=sys.stderr)
        return 2

    if args.estimate:
        tool_tokens = len(json.dumps(anthropic_tools(world))) / 3.6
        sys_tokens = len(SYSTEM_PROMPT) / 3.6
        steps = {t["task_id"]: len(t.get("expected_calls", [])) for t in world.tasks}
        turns = [min(args.max_turns, max(6, int(steps.get(t["task_id"], 10) * 1.6)))
                 for t in tasks]
        # each turn resends system + tools + the conversation so far
        in_tok = sum(int((sys_tokens + tool_tokens) * n + 700 * n * (n + 1) / 2)
                     for n in turns)
        out_tok = sum(260 * n for n in turns)
        print("cost estimate for %d task%s (policy=model, guidance=%s, max-turns=%d)"
              % (len(tasks), "" if len(tasks) == 1 else "s", args.guidance, args.max_turns))
        print("  tool schemas   ~%6.1fk tokens resent every turn" % (tool_tokens / 1000))
        print("  projected      ~%6.1fM input tokens, ~%5.0fk output tokens"
              % (in_tok / 1e6, out_tok / 1000))
        print("  assumes ~1.6 turns per oracle step, capped at --max-turns; a model that "
              "flails costs more")
        print("\n  multiply by your model's per-token price. To sanity-check cheaply first:")
        print("    python3 eval_model.py --model <id> --limit 2 --category aiops_detection")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if args.policy == "model" and not api_key:
        print("ANTHROPIC_API_KEY is not set. Use --policy oracle to smoke-test "
              "the harness without an API key.", file=sys.stderr)
        return 2

    if args.quality_judge == "llm" and args.policy not in ("model", "deepseek", "openai"):
        # A flag that accepts a request and does nothing is worse than one that
        # refuses: the run looks judged and is not.
        print("--quality-judge llm needs a model policy (model, deepseek, openai); "
              "policy=%s has no model to ask." % args.policy, file=sys.stderr)
        return 2
    label = args.model if args.policy in ("model", "deepseek", "openai") else args.policy
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
            if args.policy not in ("model", "deepseek", "openai"):
                if args.verbose:
                    print()
                stats = run_scripted_episode(world, task, sid, args.verbose, args.policy)
            else:
                if args.verbose:
                    print()
                task = dict(task)
                task["_prompt"] = (task.get("instruction_guided") if args.guidance == "guided"
                                   else task["instruction"])
                if args.policy in ("deepseek", "openai"):
                    import cloud_backend
                    stats = cloud_backend.run_episode(
                        world, task, sid, args.model, args.max_turns, args.verbose,
                        provider=args.policy, guidance=args.guidance)
                else:
                    stats = run_model_episode(world, task, sid, api_key, args.model,
                                              args.max_turns, args.verbose)
            err = None
        except Exception as e:  # noqa: BLE001
            stats = {"turns": 0, "tool_calls": 0, "transcript": ""}
            err = "%s: %s" % (type(e).__name__, e)
        verdict = world.verify(sid, tid)
        fr = dimension_fractions(verdict)
        judged = None
        if args.quality_judge == "llm" and args.policy in ("deepseek", "openai"):
            import cloud_backend
            judged = cloud_backend.judge_quality(args.policy, args.model, task,
                                                 verdict, stats.get("transcript", ""))
        elif args.quality_judge == "llm" and args.policy == "model":
            judged = llm_quality_score(api_key, args.model, task, verdict,
                                       stats.get("transcript", ""))
            if judged is not None:
                fr["quality"] = judged
        W = {"correctness": 0.6, "deployment": 0.3, "quality": 0.1}
        tw = sum(W[d] for d in fr) or 1.0
        pc = round(sum(W[d] / tw * v for d, v in fr.items()), 4)
        caller = ("model" if args.policy in ("model", "deepseek", "openai") else "scripted")
        outcome = classify_outcome(bool(verdict.get("passed")), err,
                                   stats.get("transcript", ""), verdict,
                                   stats.get("turns", 0), args.max_turns, caller)
        # WHICH checks failed, not just how many. A pass rate says a model cleared
        # the bar; only the named checks say which bar, and whether the failure was
        # getting the engineering wrong or getting the procedure wrong.
        failed_checks = [{"dimension": a["dimension"], "name": a["name"]}
                         for a in (verdict.get("assertions") or []) if not a["passed"]]
        # Why this outcome, recorded at the moment it is decided. A later reader
        # cannot recompute it: the transcript is not in the report, so an episode
        # marked `harness` because of a provider error is indistinguishable from
        # one marked `harness` by a bad marker - which is exactly the ambiguity
        # that made repairing the "API " misattribution delicate.
        reason = {"resolved": "passed", "capped": "turn budget exhausted",
                  "agent": "the agent got it wrong"}.get(outcome)
        if reason is None:
            hay = "%s %s" % (err or verdict.get("error") or "",
                             stats.get("transcript", ""))
            hit = next((m for m in HARNESS_MARKERS + HARNESS_TRANSCRIPT_MARKERS
                        + ENVIRONMENT_MARKERS + CALLER_DEPENDENT_MARKERS if m in hay), "?")
            reason = "matched %r" % hit
        rec = {"outcome": outcome, "outcome_reason": reason,
               "failed_checks": failed_checks,
               "prompt_tokens": stats.get("prompt_tokens", 0),
               "completion_tokens": stats.get("completion_tokens", 0),
               "task_id": tid, "category": task.get("category"),
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
        # Every episode is a row. Previously only the first trial was recorded, so
        # under --trials 3 the headline pass rate was computed from a third of the
        # evidence while pass^1 used all of it, and the two could disagree.
        rec["trial"] = trial
        records.append(rec)
        if trial > 0:
            continue                       # ...but only the first is printed
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
    outcomes = collections.Counter(r.get("outcome", "agent") for r in records)
    scored = outcomes["resolved"] + outcomes["agent"] + outcomes["capped"]
    print("\n  outcomes: %s" % "  ".join("%s=%d" % (k, v) for k, v in outcomes.most_common()))
    if outcomes["harness"] or outcomes["environment"]:
        print("  !! %d episode(s) failed for harness/environment reasons and are EXCLUDED "
              "from the pass rate - they are our fault, not the model's"
              % (outcomes["harness"] + outcomes["environment"]))
    print("\n  Horizon-SWE-PF  (pass rate over %d attributable episodes) : %.1f%%  (%d/%d)"
          % (scored, 100.0 * passed / max(1, scored), passed, scored))
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
        # NOT `n`: that is the episode count, and rebinding it here corrupted both
        # the reported pass_rate (which went above 1.0 under --trials) and the
        # oracle self-check exit code, so `--policy oracle --trials 3` reported a
        # broken world for a world that was fine.
        k_max = args.trials
        print("\n  tau-bench reliability over %d trials per task:" % k_max)
        for k in range(1, k_max + 1):
            vals = [pass_hat_k(sum(v), len(v), k) for v in trials.values()]
            vals = [v for v in vals if v is not None]
            if vals:
                print("    pass^%d  %.3f" % (k, sum(vals) / len(vals)))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(
            {"world_id": world.summary()["world_id"], "policy": args.policy,
             "model": args.model if args.policy in ("model", "deepseek", "openai") else None,
             "split": args.split, "guidance": args.guidance, "pass_rate": passed / n,
             "mean_score": mean_score, "trials": args.trials,
             "outcomes": dict(outcomes),
             "attributable_episodes": scored,
             # What the run cost. A lab choosing whether to run this deserves the
             # number next to the score, not a separate estimate.
             "spend": {"prompt_tokens": sum(r.get("prompt_tokens", 0) for r in records),
                       "completion_tokens": sum(r.get("completion_tokens", 0)
                                                for r in records),
                       "episodes": len(records)},
             "pass_hat_k": {str(k): (lambda vs: sum(vs) / len(vs) if vs else None)(
                 [v for v in (pass_hat_k(sum(x), len(x), k) for x in trials.values())
                  if v is not None])
                 for k in range(1, args.trials + 1)},
             "tasks": records}, indent=2) + "\n")
        print("  report: %s" % args.out)
    return 0 if passed == n or args.policy != "oracle" else 1


if __name__ == "__main__":
    sys.exit(main())
