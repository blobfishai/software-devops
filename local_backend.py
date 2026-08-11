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
- {"done": ...} RECORDS NOTHING. It only ends the episode. If the assignment asks you to submit, report or record something, you must call that tool FIRST - your reasoning is not an answer until a tool has stored it.
- Reply {"done": ...} only when the assignment is genuinely complete."""

# Which tool an instruction demands before the episode may end. Blocking a
# premature exit is documented harness practice rather than coaching: cline
# enumerates `completion_without_submit` as a mistake reason, and claude-code
# ships a Stop-hook that blocks exit when the required action is absent from the
# transcript (research/notes/automation/_WORKFLOW_PATTERNS.md:44,412,415).
REQUIRED_SUBMIT = (
    ("submit_diagnosis", "submit_diagnosis"),
    ("submit_answer", "submit_answer"),
)
MAX_NUDGES = 2
# cline detects loops on a key-sorted argument signature, soft at 3 and hard at 5
# (research/notes/automation/cline__cline.md). Without this an 8B model will
# retry the same malformed call until the turn budget runs out, which measures
# the harness rather than the task.
LOOP_SOFT, LOOP_HARD = 3, 5


def load(model_id="mlx-community/Qwen3-8B-4bit"):
    global _MODEL, _TOK
    if _MODEL is None:
        from mlx_lm import load as _load
        _MODEL, _TOK = _load(model_id)
    return _MODEL, _TOK


def _tool_digest(tools, limit=None):
    """The full tool menu, every tool, every argument name.

    This used to show only the first 48 of 82 tools with arguments truncated to
    four optionals. That silently hid both submission tools and the entire vendor
    layer: 40 of 76 tasks required at least one tool the model could not see. The
    model was told by the instruction to call `submit_diagnosis`, could not see
    its schema, and looped guessing argument names - which the loop then scored as
    task difficulty. A cloud model receives all 82 JSON schemas, so hiding a third
    of the surface was a harness defect masquerading as a result.

    Names and argument names are never abbreviated, because those are the parts
    the model has to reproduce exactly. Only prose is trimmed."""
    subset = tools[:limit] if limit else tools
    lines = []
    for t in subset:
        params = t.get("json_schema", {}).get("parameters", {})
        req = params.get("required", [])
        opt = [k for k in (params.get("properties") or {}) if k not in req]
        sig = ", ".join(req + ["%s?" % o for o in opt])
        line = "%s(%s) - %s" % (t["name"], sig, t["description"][:110])
        # A controlled vocabulary must never be what gets trimmed: a model that
        # cannot see the allowed values guesses, gets rejected, and then edits
        # its answer rather than its argument.
        props = params.get("properties") or {}
        for k in req + opt:
            choices = (props.get(k) or {}).get("enum")
            if choices:
                line += "\n    %s: one of %s" % (k, "|".join(str(c) for c in choices))
        lines.append(line)
    if limit and len(tools) > limit:
        # No silent caps: if the menu is bounded, say what was dropped.
        lines.append("[%d further tools withheld by --tool-limit]" % (len(tools) - limit))
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
                max_tokens=220, tool_limit=None):
    """Drive one episode with a local model. Returns the same shape as the cloud
    path in eval_model.py so calibrate.py consumes it unchanged."""
    from mlx_lm import generate
    model, tok = load(model_id)
    menu = _tool_digest(world.tools, tool_limit)
    transcript, calls = [], 0
    turn, nudges = 0, 0
    seen = {}
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
            required = next((tool for marker, tool in REQUIRED_SUBMIT
                             if marker in task["instruction"]), None)
            if required and not any(l.startswith(required + "(") for l in transcript) \
                    and nudges < MAX_NUDGES:
                nudges += 1
                transcript.append("BLOCKED_EXIT -> %s not called yet" % required)
                history.append({"role": "assistant", "content": json.dumps(call)})
                history.append({"role": "user", "content":
                                "You have not recorded anything. Your conclusion is not an "
                                "answer until it is stored. Call %s now with your finding, "
                                "then finish." % required})
                continue
            transcript.append("done(%s)" % str(call.get("done"))[:120])
            break
        name = str(call.get("tool", ""))
        args = call.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        sig = "%s:%s" % (name, json.dumps(args, sort_keys=True))
        seen[sig] = seen.get(sig, 0) + 1
        if seen[sig] >= LOOP_HARD:
            transcript.append("LOOP_ABORT -> %s repeated %d times" % (name, seen[sig]))
            break
        out = world.call_tool(sid, name, args)
        calls += 1
        line = "%s(%s) -> %s" % (name, json.dumps(args)[:140], json.dumps(out)[:220])
        transcript.append(line)
        if verbose:
            print("      %s" % line[:170])
        history.append({"role": "assistant", "content": json.dumps(call)})
        msg = json.dumps(out)[:900]
        if seen[sig] == LOOP_SOFT:
            msg += ("\n\nYou have now made this exact call %d times. It is not working. "
                    "Change the arguments or try a different approach." % LOOP_SOFT)
        history.append({"role": "user", "content": msg})
        # keep the window small enough for an 8B model to stay coherent
        if len(history) > 15:
            history = history[:2] + history[-12:]
    return {"turns": turn + 1, "tool_calls": calls, "transcript": "\n".join(transcript)}
