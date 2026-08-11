"""Local model backend, so the calibration loop can run without a cloud credential.

Uses mlx_lm against a locally cached model. The point is not to benchmark a small
model for its own sake - it is that a real, uncontaminated model driving the tools
produces evidence the scripted oracle structurally cannot: whether the tasks are
navigable from the instruction alone, and where a model actually breaks.

The model sees the same task instruction and the same tools a cloud model would.
Tool calls are requested as JSON, because a 4-bit 8B model has no native
tool-calling API; that is a harness difference and it is recorded as one.
"""

import json
import re

_MODEL = None
_TOK = None

SYSTEM = """You are an on-call software engineer at NovaCart. You act ONLY by \
calling tools.

Reply with a single JSON object and nothing else, in one of two forms:

  {"tool": "<tool_name>", "args": {...}}
  {"done": "<one sentence summary>"}

Rules:
- One tool call per reply. No prose, no markdown, no code fences.
- Check each result: a result with "ok": false means the call did nothing.
- Company policy is NOT in your instructions. It is in the knowledge base - use \
search_docs and get_document to find it, and follow it.
- Reply {"done": ...} only when the assignment is genuinely complete."""


def load(model_id="mlx-community/Qwen3-8B-4bit"):
    global _MODEL, _TOK
    if _MODEL is None:
        from mlx_lm import load as _load
        _MODEL, _TOK = _load(model_id)
    return _MODEL, _TOK


def _tool_digest(tools, limit=48):
    """A compact tool menu. The full 82-tool schema set does not fit usefully in
    an 8B context, so tools are listed by name and required args only."""
    lines = []
    for t in tools[:limit]:
        params = t.get("json_schema", {}).get("parameters", {})
        req = params.get("required", [])
        opt = [k for k in (params.get("properties") or {}) if k not in req]
        sig = ", ".join(req + ["%s?" % o for o in opt[:4]])
        lines.append("%s(%s) - %s" % (t["name"], sig, t["description"][:90]))
    return "\n".join(lines)


def extract_call(text):
    """Pull the first JSON object out of a reply, tolerating fences and prose."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:  # noqa: BLE001
                    start = None
    return None


def run_episode(world, task, sid, model_id, max_turns, verbose=False,
                max_tokens=220, tool_limit=48):
    """Drive one episode with a local model. Returns the same shape as the cloud
    path in eval_model.py so calibrate.py consumes it unchanged."""
    from mlx_lm import generate
    model, tok = load(model_id)
    menu = _tool_digest(world.tools, tool_limit)
    transcript, calls = [], 0
    turn = 0
    history = [
        {"role": "system", "content": SYSTEM + "\n\nTOOLS:\n" + menu},
        {"role": "user", "content": task["instruction"]},
    ]
    for turn in range(max_turns):
        prompt = tok.apply_chat_template(history, add_generation_prompt=True,
                                         enable_thinking=False)
        raw = generate(model, tok, prompt=prompt, max_tokens=max_tokens, verbose=False)
        call = extract_call(raw)
        if call is None:
            history.append({"role": "assistant", "content": raw[:400]})
            history.append({"role": "user",
                            "content": 'Reply with ONE JSON object only: '
                                       '{"tool": "...", "args": {...}} or {"done": "..."}'})
            transcript.append("MALFORMED -> %s" % raw[:120].replace("\n", " "))
            continue
        if "done" in call and "tool" not in call:
            transcript.append("done(%s)" % str(call.get("done"))[:120])
            break
        name = str(call.get("tool", ""))
        args = call.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        out = world.call_tool(sid, name, args)
        calls += 1
        line = "%s(%s) -> %s" % (name, json.dumps(args)[:140], json.dumps(out)[:220])
        transcript.append(line)
        if verbose:
            print("      %s" % line[:170])
        history.append({"role": "assistant", "content": json.dumps(call)})
        history.append({"role": "user", "content": json.dumps(out)[:900]})
        # keep the window small enough for an 8B model to stay coherent
        if len(history) > 15:
            history = history[:2] + history[-12:]
    return {"turns": turn + 1, "tool_calls": calls, "transcript": "\n".join(transcript)}
