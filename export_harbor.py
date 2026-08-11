#!/usr/bin/env python3
"""Export the world in Harbor format.

Harbor is the delivery format a lab actually consumes: a self-contained
directory with the environment, the task list as JSONL, one standalone verifier
per task, and a manifest that pins every artifact by digest.

Layout (matching fleet_world_factory/stages/s09_harbor.py):

    <out>/
      task.yaml                     Harbor task configuration
      manifest.json                 artifact digests + counts
      README.md
      Dockerfile  docker-compose.yml
      environment/
        db.sqlite                   the seeded world
        schema.sql  seed.sql
        tools/<tool>.py             one file per tool
        server.py  run.sh  setup.sh  reset.sh  requirements.txt
      tasks/
        tasks.jsonl                 one task per line
        task_configs/<task_id>.json
      verifiers/
        verify_<task_id>.py         def verify(db_path) -> dict
        verifier_index.json
      rewards/reward_config.json
      reports/  agent_traces/

Each verifier is standalone: `python3 verifiers/verify_x.py world.db` prints a
JSON verdict, so a lab can score a rollout without importing anything of ours.

    python3 export_harbor.py --out dist/harbor
"""

import argparse
import hashlib
import json
import pathlib
import shutil
import sqlite3
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent

VERIFIER_TEMPLATE = '''#!/usr/bin/env python3
"""Standalone verifier for {task_id}.

    python3 {fname} /path/to/world.db

Prints a JSON verdict. Horizon-SWE-PF is the binary `passed` (every correctness
and deployment check must hold; engineering quality is scored but excluded).
Horizon-SWE-PC is the weighted composite in `score`.
"""
import hashlib
import json
import sqlite3
import sys

TASK_ID = {task_id!r}
CATEGORY = {category!r}
WEIGHTS = {{"correctness": 0.6, "deployment": 0.3, "quality": 0.1}}


def verify(db_path):
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    conn.row_factory = sqlite3.Row
    ns = {{"conn": conn, "sqlite3": sqlite3, "json": json, "hashlib": hashlib,
          "db_path": db_path, "DB_PATH": db_path, "final_answer": "", "answer": ""}}
    ns["get_db"] = lambda: conn
    checks, err = [], None
    try:
        exec(compile(VCODE, "<vcode>", "exec"), ns)
    except AssertionError as e:
        err = "assertion: %s" % e
    except Exception as e:  # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)
    finally:
        conn.close()
    checks = ns.get("_checks") or []
    dims = {{}}
    for dim, name, ok, msg in checks:
        d = dims.setdefault(dim, [0, 0])
        d[1] += 1
        d[0] += 1 if ok else 0
    total_w = sum(WEIGHTS[d] for d in dims) or 1.0
    score = round(sum(WEIGHTS[d] / total_w * (v[0] / v[1]) for d, v in dims.items()), 4) \\
        if dims else 0.0
    hard = [(d, n, m) for d, n, ok, m in checks
            if not ok and d in ("correctness", "deployment")]
    return {{
        "task_id": TASK_ID,
        "category": CATEGORY,
        "passed": bool(checks) and not hard,
        "reward": 1.0 if (checks and not hard) else 0.0,
        "score": score,
        "dimensions": {{d: "%d/%d" % (v[0], v[1]) for d, v in sorted(dims.items())}},
        "assertions": [{{"dimension": d, "name": n, "passed": bool(ok), "message": m}}
                       for d, n, ok, m in checks],
        "failure_reason": err or ("; ".join("%s/%s" % (d, n) for d, n, _ in hard) or ""),
    }}


VCODE = r"""
{vcode}
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: %s <world.db>" % sys.argv[0], file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(verify(sys.argv[1]), indent=2))
'''

RUN_SH = """#!/usr/bin/env bash
# Start the world server. REST + MCP on $PORT (default 8080).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 environment/server.py --world environment --port "${PORT:-8080}"
"""

SETUP_SH = """#!/usr/bin/env bash
# Harbor setup: nothing to install. The environment is Python 3.12 stdlib only.
set -euo pipefail
python3 --version
echo "environment ready: $(python3 -c "import sqlite3,json,pathlib;print('stdlib ok')")"
"""

RESET_SH = """#!/usr/bin/env bash
# Restore the pristine world between tasks.
set -euo pipefail
cd "$(dirname "$0")"
cp -f db.sqlite.snapshot db.sqlite
echo "world reset"
"""

DOCKERFILE = """FROM python:3.12-slim
WORKDIR /harbor
COPY . .
RUN chmod +x environment/*.sh
EXPOSE 8080
HEALTHCHECK CMD python3 -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/healthz')"
CMD ["bash", "environment/run.sh"]
"""

COMPOSE = """services:
  world:
    build: .
    ports: ["8080:8080"]
    environment:
      PORT: "8080"
"""


def sha256(path):
    h = hashlib.sha256()
    h.update(pathlib.Path(path).read_bytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="world")
    ap.add_argument("--out", default="dist/harbor")
    args = ap.parse_args()

    src = ROOT / args.world
    out = pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    for sub in ("environment/tools", "tasks/task_configs", "verifiers", "rewards",
                "reports", "agent_traces"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    world = json.loads((src / "world.json").read_text())
    tools = json.loads((src / "tools.json").read_text())
    tasks = json.loads((src / "tasks.json").read_text())

    # ---- environment
    shutil.copyfile(src / "environment.db", out / "environment" / "db.sqlite")
    shutil.copyfile(src / "environment.db", out / "environment" / "db.sqlite.snapshot")
    shutil.copyfile(src / "schema.sql", out / "environment" / "schema.sql")
    shutil.copyfile(src / "seed.sql", out / "environment" / "seed.sql")
    shutil.copyfile(ROOT / "serve.py", out / "environment" / "server.py")
    for t in tools:
        (out / "environment" / "tools" / ("%s.py" % t["name"])).write_text(t["source_code"])
    shutil.copyfile(src / "tools_combined.py", out / "environment" / "tools_combined.py")
    shutil.copyfile(src / "tools.json", out / "environment" / "tool_schemas.json")
    for name, body in (("run.sh", RUN_SH), ("setup.sh", SETUP_SH), ("reset.sh", RESET_SH)):
        p = out / "environment" / name
        p.write_text(body)
        p.chmod(0o755)
    (out / "environment" / "requirements.txt").write_text("# stdlib only\n")

    # ---- tasks.jsonl + per-task configs
    lines, index = [], []
    for t in tasks:
        rec = {
            "task_id": t["task_id"],
            "category": t.get("category", ""),
            "difficulty": t.get("difficulty", "medium"),
            "instruction": t["instruction"],
            "required_tools": t.get("required_tools", []),
            "verifier": "verifiers/verify_%s.py" % t["task_id"],
            "max_steps": max(20, len(t.get("expected_calls", [])) * 3),
            "split": ("heldout" if t["task_id"] in world["splits"]["heldout"] else "train"),
        }
        lines.append(json.dumps(rec))
        (out / "tasks" / "task_configs" / ("%s.json" % t["task_id"])).write_text(
            json.dumps({**rec, "instruction_guided": t.get("instruction_guided", "")},
                       indent=2) + "\n")

        fname = "verify_%s.py" % t["task_id"]
        vp = out / "verifiers" / fname
        vp.write_text(VERIFIER_TEMPLATE.format(
            task_id=t["task_id"], category=t.get("category", ""), fname=fname,
            vcode=t["vcode"].replace("\\", "\\\\").replace('"""', '\\"\\"\\"')))
        vp.chmod(0o755)
        index.append({"task_id": t["task_id"], "vcode_path": "verifiers/" + fname,
                      "vcode_sha256": sha256(vp), "verification_mode": "exact_state",
                      "attribution_safe": True, "weak_vcode": False,
                      "category": t.get("category", "")})
    (out / "tasks" / "tasks.jsonl").write_text("\n".join(lines) + "\n")
    (out / "verifiers" / "verifier_index.json").write_text(json.dumps(index, indent=2) + "\n")

    # ---- rewards
    (out / "rewards" / "reward_config.json").write_text(json.dumps({
        "scheme": "horizon-swe",
        "pass_fail": {"metric": "passed",
                      "definition": "every correctness and deployment check holds; "
                                    "engineering quality is scored but excluded"},
        "partial_credit": {"metric": "score",
                           "weights": {"correctness": 0.6, "deployment": 0.3,
                                       "quality": 0.1}},
        "no_llm_judge_in_reward_path": True,
    }, indent=2) + "\n")

    # ---- top level
    (out / "task.yaml").write_text(textwrap.dedent("""\
        # Harbor Task Configuration
        name: software_devops_environment
        version: "2.0.0"
        description: "End-to-end software engineering and SRE environment with %d verifiable tasks"

        environment:
          type: sqlite_mcp
          database: environment/db.sqlite
          tools_dir: environment/tools/
          server: environment/server.py
          protocols: [rest, mcp]

        tasks:
          source: tasks/tasks.jsonl
          count: %d

        verification:
          type: vcode
          scripts_dir: verifiers/
          index: verifiers/verifier_index.json
          standalone: true

        rewards:
          config: rewards/reward_config.json

        settings:
          timeout_per_task: 900
          max_steps: 60
          require_final_answer: false
          stop_on_exact_retry_loop: 3
          stop_on_semantic_no_progress: 5
          reset_between_tasks: true
        """ % (len(tasks), len(tasks))))
    (out / "Dockerfile").write_text(DOCKERFILE)
    (out / "docker-compose.yml").write_text(COMPOSE)

    cats = {}
    for t in tasks:
        cats[t.get("category", "?")] = cats.get(t.get("category", "?"), 0) + 1
    conn = sqlite3.connect(str(out / "environment" / "db.sqlite"))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")]
    rows = sum(conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in tables)
    conn.close()

    manifest = {
        "kind": "harbor.environment",
        "version": "2.0.0",
        "world_id": world["world_id"],
        "world_digest": world["world_digest"],
        "domain": "software engineering / devops / sre",
        "counts": {"tasks": len(tasks), "tools": len(tools), "tables": len(tables),
                   "rows": rows, "categories": cats},
        "splits": {k: len(v) for k, v in world["splits"].items()},
        "artifacts": {},
        "scoring": {"pf": "passed", "pc": "score",
                    "weights": {"correctness": 0.6, "deployment": 0.3, "quality": 0.1}},
    }
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.stat().st_size < 40_000_000:
            manifest["artifacts"][str(p.relative_to(out))] = sha256(p)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    (out / "README.md").write_text(textwrap.dedent("""\
        # software-devops — Harbor environment

        An executable software-engineering and SRE world: %d services over a database,
        cache, queue, object store and CDN, an editable monorepo with commit history, a
        traffic generator that turns deployed state into live metrics, and %d tools
        spanning both a first-party stack and vendor-shaped surfaces (Jira, Linear,
        GitHub Issues, Prometheus, Sentry, PagerDuty, Confluence, spreadsheets, a local
        SQLite) whose data deliberately disagrees.

        **%d tasks** across %d categories, graded by executable verifiers with no LLM in
        the reward path.

        ## Run

        ```bash
        bash environment/setup.sh
        bash environment/run.sh          # REST + MCP on :8080
        # or
        docker compose up
        ```

        ## Score a rollout

        Every verifier is standalone - no imports from this repo required:

        ```bash
        python3 verifiers/verify_tsk_payments_retry.py environment/db.sqlite
        ```

        ```json
        { "task_id": "...", "passed": true, "reward": 1.0, "score": 1.0,
          "dimensions": {"correctness": "7/7", "deployment": "4/4", "quality": "5/5"} }
        ```

        ## Scoring

        - **PF** (`passed`): every correctness and deployment check holds. Engineering
          quality is scored but excluded, so style never rescues a broken rollout.
        - **PC** (`score`): 0.6 correctness + 0.3 deployment + 0.1 quality.

        ## Episode protocol

        `POST /sessions` -> `POST /sessions/<id>/tools/<tool>` -> `POST /sessions/<id>/verify`,
        or MCP at `POST /mcp` with `task_start` / `task_verify`. Sessions fork the database,
        so concurrent rollouts never collide.
        """ % (10, len(tools), len(tasks), len(cats))))

    n_files = sum(1 for p in out.rglob("*") if p.is_file())
    print("harbor export -> %s" % out)
    print("  %d tasks, %d tools, %d verifiers, %d files"
          % (len(tasks), len(tools), len(index), n_files))
    print("  manifest pins %d artifacts by sha256" % len(manifest["artifacts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
