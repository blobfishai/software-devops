"""OpenAI-compatible cloud backend with native tool calling.

The local backend asks a small model for tool calls as JSON, because a 4-bit 8B
model has no tool-calling API. That protocol turned out to dominate its results:
the model reasoned correctly and then failed the submission handshake, and three
harness defects hid behind that failure mode before they were found.

This backend removes the confound entirely. The model receives all 84 tools as
JSON Schema function definitions and calls them through the provider's own
tool-calling API, which is the harness a frontier model actually runs under. What
remains is the task.

Works against any OpenAI-compatible endpoint; configured here for DeepSeek.

    export DEEPSEEK_API_KEY=...
    python3 calibrate.py --policy deepseek --model deepseek-v4-pro --attempts 3
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.request

PROVIDERS = {
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-pro",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
}

SYSTEM = """You are an on-call software engineer at NovaCart. You work by calling \
the tools available to you; you have no other way to observe or change anything.

Two things are easy to get wrong here:

- A result with "ok": false means the call did nothing. Read it and adjust.
- Company policy is not in your instructions. It is in the knowledge base. Use \
search_docs and get_document to find the relevant standard and follow it.

Stating a conclusion is not the same as recording one. If the assignment asks you \
to submit, report, resolve or close something, that is a tool call, and the work \
is not finished until you have made it. Finish when the assignment is genuinely \
complete."""

_CTX = None


def _ctx():
    """A CA bundle, because the framework Python on this machine ships without one."""
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            _CTX = ssl.create_default_context()
    return _CTX


def tool_specs(tools):
    """Every tool as a function schema. No truncation, no subsetting: hiding a
    third of the surface is what invalidated the first calibration sweep."""
    out = []
    for t in tools:
        params = t.get("json_schema", {}).get("parameters", {}) or {}
        params = json.loads(json.dumps(params))          # defensive copy
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        out.append({"type": "function",
                    "function": {"name": t["name"],
                                 "description": t["description"][:1024],
                                 "parameters": params}})
    return out


def _post(url, key, payload, timeout=180, attempts=4):
    body = json.dumps(payload).encode()
    last = None
    for i in range(attempts):
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
                return json.loads(r.read()), None
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            last = "HTTP %s: %s" % (e.code, detail)
            if e.code in (400, 401, 403, 404):
                return None, last                        # not worth retrying
        except Exception as e:  # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(min(2 ** i, 20))
    return None, last


RESULT_BUDGET = 12000


def _fit(out, budget=RESULT_BUDGET):
    """Serialise a tool result, dropping ROWS rather than characters when it is
    too large.

    Slicing the JSON string was the obvious thing and it is quietly destructive:
    an unfiltered list_tickets() is 28,888 characters, so a 4,000-character cap
    handed the model a blob cut off mid-string - invalid JSON, no indication that
    anything was missing, and no way to tell "there are no more tickets" from
    "you were shown 14% of them". Dropping whole rows keeps the result parseable
    and says what was withheld, which is the difference between a limit and a
    trap.
    """
    blob = json.dumps(out)
    if len(blob) <= budget:
        return blob
    rows = out.get("rows") if isinstance(out, dict) else None
    if isinstance(rows, list) and rows:
        total = len(rows)

        def build(n):
            # Build exactly what will be RETURNED, so the search measures the real
            # payload. Sizing a shorter trial than the result overshoots the budget
            # by the difference, which is how the first version of this overflowed.
            kept = dict(out)
            kept["rows"] = rows[:n]
            kept["truncated"] = {
                "shown": n, "total": total, "omitted": total - n,
                "hint": "this result was too large to return in full; narrow it with "
                        "the filter arguments this tool accepts"}
            return kept

        lo, hi = 0, total
        while lo < hi:                      # largest prefix of rows that fits
            mid = (lo + hi + 1) // 2
            if len(json.dumps(build(mid))) <= budget:
                lo = mid
            else:
                hi = mid - 1
        return json.dumps(build(lo))
    # not a row list: say so plainly rather than emitting broken JSON
    return json.dumps({"truncated": True, "bytes": len(blob),
                       "hint": "result too large to return in full; request a "
                               "narrower slice",
                       "head": blob[:budget - 400]})


def run_episode(world, task, sid, model, max_turns, verbose=False,
                provider="deepseek", guidance="standard", max_tokens=2048):
    """Drive one episode through the provider's native tool-calling API.

    Returns the same shape as local_backend.run_episode so calibrate.py and
    eval_model.py consume it unchanged.
    """
    cfg = PROVIDERS[provider]
    key = os.environ.get(cfg["key_env"], "")
    if not key:
        return {"turns": 0, "tool_calls": 0,
                "transcript": "HARNESS: %s is not set" % cfg["key_env"]}

    prompt_text = (task.get("instruction_guided") if guidance == "guided"
                   else None) or task["instruction"]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt_text}]
    specs = tool_specs(world.tools)

    transcript, calls, turn = [], 0, 0
    prompt_tokens = completion_tokens = 0

    for turn in range(max_turns):
        data, err = _post(cfg["url"], key,
                          {"model": model, "messages": messages,
                           "tools": specs, "tool_choice": "auto",
                           "max_tokens": max_tokens, "temperature": 1.0})
        if data is None:
            # A provider failure is a harness fault, never the agent's, and must
            # be labelled so the calibration loop does not score it as difficulty.
            transcript.append("HARNESS: provider error: %s" % err)
            break
        u = data.get("usage") or {}
        prompt_tokens += u.get("prompt_tokens", 0)
        completion_tokens += u.get("completion_tokens", 0)

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        messages.append({k: v for k, v in msg.items()
                         if k in ("role", "content", "tool_calls", "reasoning_content")}
                        or {"role": "assistant", "content": ""})

        if not tool_calls:
            transcript.append("done(%s)" % str(msg.get("content") or "")[:160].replace("\n", " "))
            break

        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception:  # noqa: BLE001
                args = {}
                transcript.append("MALFORMED_ARGS %s -> %s" % (name, str(raw)[:120]))
            if not isinstance(args, dict):
                args = {}
            out = world.call_tool(sid, name, args)
            calls += 1
            line = "%s(%s) -> %s" % (name, json.dumps(args)[:160], json.dumps(out)[:220])
            transcript.append(line)
            if verbose:
                print("      %s" % line[:180])
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                             "content": _fit(out)})

    return {"turns": turn + 1, "tool_calls": calls,
            "transcript": "\n".join(transcript),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens}


QUALITY_JUDGE = """You are grading the ENGINEERING QUALITY of an on-call engineer's work: not whether the fix was correct, which is graded separately, but whether the work was done well - evidence gathered before conclusions, the change explained, the right people told, the trail left behind legible to whoever picks this up next.

Reply with a single JSON object: {"score": <0.0-1.0>, "why": "<one sentence>"}."""


def judge_quality(provider, model, task, verdict, transcript, max_tokens=1200):
    """LLM judge for the quality dimension, through the same provider as the run.

    Returns None rather than a number when the judge cannot be reached, because a
    judge that quietly returns 0.0 on an API error scores the model for our
    outage.
    """
    cfg = PROVIDERS[provider]
    key = os.environ.get(cfg["key_env"], "")
    if not key:
        return None
    signals = "\n".join("- [%s] %s: %s" % ("PASS" if a["passed"] else "FAIL",
                                            a["name"], a["message"])
                         for a in (verdict.get("assertions") or [])
                         if a["dimension"] == "quality")
    body = ("TASK:\n%s\n\nWHAT THE AGENT DID (tool calls in order):\n%s\n\n"
            "DETERMINISTIC QUALITY SIGNALS:\n%s\n"
            % (task.get("instruction", "")[:2000], (transcript or "")[:6000], signals))
    data, err = _post(cfg["url"], key,
                      {"model": model, "max_tokens": max_tokens, "temperature": 0.0,
                       "messages": [{"role": "system", "content": QUALITY_JUDGE},
                                    {"role": "user", "content": body}]})
    if data is None:
        return None
    choice = (data.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    if not text and choice.get("finish_reason") == "length":
        # A reasoning model can spend the whole budget thinking and emit nothing.
        # Silently returning None here made the judge decline to score exactly the
        # sloppy transcripts it exists to catch, because those are the ones it
        # deliberates over longest.
        return None
    try:
        start = text.index("{")
        score = float(json.loads(text[start:text.rindex("}") + 1])["score"])
    except Exception:  # noqa: BLE001
        return None
    return max(0.0, min(1.0, score))
