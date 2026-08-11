#!/usr/bin/env python3
"""Rule 2: an LLM judge that refuses ungrounded additions to the world.

Every new task, tool or mock-data artifact must cite evidence from the research
corpus. This judge does two things, in order:

  1. A deterministic pre-check. The claimed citation must actually exist: the
     file must be present under research/, and the quoted snippet must really
     appear in it. A citation that does not resolve is rejected before any model
     is called - no LLM is required to catch a fabricated file path, and
     fabricated citations are the failure mode we care most about.

  2. An LLM judgement, only for artifacts that pass the pre-check: does the
     evidence actually *support* the design decision, or is it merely adjacent?

Usage:
    python3 research/grounding_judge.py --check artifact.json
    python3 research/grounding_judge.py --check-all build/generated/

Artifact schema:
    {"kind": "task|tool|mock_data", "id": "...", "claim": "what we built and why",
     "evidence": [{"path": "research/notes/evals/...md", "quote": "..."}]}

Without ANTHROPIC_API_KEY the judge still runs stage 1 and reports stage 2 as
"unjudged" rather than silently passing.
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
API_URL = "https://api.anthropic.com/v1/messages"

RUBRIC = """You are auditing whether a design decision in a simulated benchmark \
world is genuinely grounded in research evidence, or whether it was invented and \
given a decorative citation.

You will receive a CLAIM (what was built and why) and EVIDENCE (verbatim quotes \
from a research corpus of real benchmark repos, MCP servers, and published \
sources).

Judge only one thing: does the evidence actually support this specific decision?

Reject if the evidence is merely topically adjacent, if it supports a weaker or \
different claim, or if the specific numbers, field names, tool names or \
mechanisms in the claim do not appear in the evidence. Accept when the evidence \
directly warrants the decision, including reasonable engineering translation \
from a real system into a simulated one - but the *substance* must come from the \
evidence, not from plausibility.

Reply with ONLY a JSON object:
{"grounded": true|false, "confidence": 0.0-1.0, "reason": "<one sentence>", \
"unsupported": ["<any specific element of the claim the evidence does not cover>"]}"""


def check_citations(artifact):
    """Stage 1: do the cited files exist and contain the quoted text?"""
    problems = []
    ev = artifact.get("evidence") or []
    if not ev:
        return ["no evidence cited at all"]
    for e in ev:
        p = ROOT / e.get("path", "")
        if not p.exists():
            problems.append("cited file does not exist: %s" % e.get("path"))
            continue
        quote = (e.get("quote") or "").strip()
        if not quote:
            problems.append("citation with no quote: %s" % e.get("path"))
            continue
        try:
            body = p.read_text(errors="ignore")
        except Exception as exc:  # noqa: BLE001
            problems.append("cited file unreadable: %s (%s)" % (e.get("path"), exc))
            continue
        # tolerate whitespace reflow, nothing else
        norm = " ".join(body.split())
        if " ".join(quote.split()) not in norm:
            problems.append("quote not found in %s: %r" % (e.get("path"), quote[:80]))
    return problems


def judge(artifact, api_key, model="claude-sonnet-5"):
    """Stage 2: does the evidence actually support the claim?"""
    body = "CLAIM:\n%s\n\nEVIDENCE:\n%s\n" % (
        artifact.get("claim", ""),
        "\n\n".join("--- %s ---\n%s" % (e["path"], e["quote"])
                    for e in artifact.get("evidence", [])))
    payload = {"model": model, "max_tokens": 400, "system": RUBRIC,
               "messages": [{"role": "user", "content": body}]}
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        out = json.loads(resp.read())
    text = "".join(b.get("text", "") for b in out.get("content", []))
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def review(artifact, api_key):
    problems = check_citations(artifact)
    result = {"id": artifact.get("id"), "kind": artifact.get("kind"),
              "citations_resolve": not problems, "problems": problems}
    if problems:
        result["verdict"] = "REJECTED (citation does not resolve)"
        return result
    if not api_key:
        result["verdict"] = "unjudged (no ANTHROPIC_API_KEY; citations do resolve)"
        return result
    try:
        j = judge(artifact, api_key)
    except Exception as exc:  # noqa: BLE001
        result["verdict"] = "unjudged (judge call failed: %s)" % exc
        return result
    result.update(j)
    result["verdict"] = "ACCEPTED" if j.get("grounded") else "REJECTED (not supported)"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="append", default=[])
    ap.add_argument("--check-all", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    paths = [pathlib.Path(p) for p in args.check]
    if args.check_all:
        paths += sorted(pathlib.Path(args.check_all).glob("*.json"))
    if not paths:
        print("nothing to check", file=sys.stderr)
        return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    results = []
    for p in paths:
        blob = json.loads(p.read_text())
        for artifact in (blob if isinstance(blob, list) else [blob]):
            r = review(artifact, api_key)
            results.append(r)
            print("%-46s %s" % (r.get("id", p.name), r["verdict"]))
            for prob in r.get("problems", []):
                print("      · %s" % prob)
            if r.get("unsupported"):
                print("      · unsupported: %s" % "; ".join(r["unsupported"]))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(results, indent=2) + "\n")
    bad = [r for r in results if r["verdict"].startswith("REJECTED")]
    print("\n%d artifact(s), %d rejected" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
