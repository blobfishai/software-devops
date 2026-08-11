#!/usr/bin/env bash
set -u
DEST="$(cd "$(dirname "$0")" && pwd)/repos"
clone() { local cat="$1" url="$2"; local n; n="$(basename "$url" .git)"; local o; o="$(basename "$(dirname "$url")")"
  local d="$DEST/$cat/${o}__${n}"; [ -d "$d/.git" ] && { echo "have $n"; return; }
  mkdir -p "$(dirname "$d")"
  timeout 200 git clone --depth 1 --single-branch --quiet "$url" "$d" 2>/dev/null \
    && echo "ok   $cat/${o}__${n}" || { echo "FAIL $o/$n"; rm -rf "$d"; }; }

# --- more evals / benchmarks / arenas
clone evals https://github.com/SWE-bench/SWE-smith.git
clone evals https://github.com/multi-swe-bench/multi-swe-bench.git
clone evals https://github.com/microsoft/SWE-bench-Live.git
clone evals https://github.com/openai/mle-bench.git
clone evals https://github.com/google-deepmind/mctx.git
clone evals https://github.com/THUDM/AgentBench.git
clone evals https://github.com/web-arena-x/webarena.git
clone evals https://github.com/xlang-ai/OSWorld.git
clone evals https://github.com/GAIR-NLP/DevBench.git
clone evals https://github.com/allenai/ZeroEval.git
clone evals https://github.com/stanford-crfm/helm.git
clone evals https://github.com/EleutherAI/lm-evaluation-harness.git
clone evals https://github.com/salesforce/CodeRL.git
clone evals https://github.com/bigcode-project/bigcode-evaluation-harness.git

# --- more agent harnesses / automation
clone automation https://github.com/Aider-AI/aider.git
clone automation https://github.com/block/goose.git
clone automation https://github.com/continuedev/continue.git
clone automation https://github.com/sweepai/sweep.git
clone automation https://github.com/gptscript-ai/gptscript.git
clone automation https://github.com/stitionai/devika.git

# --- more MCP tool servers (the tool surface we must cover)
clone mcp https://github.com/tacticlaunch/mcp-linear.git
clone mcp https://github.com/zereight/gitlab-mcp.git
clone mcp https://github.com/makenotion/notion-mcp-server.git
clone mcp https://github.com/slackapi/java-slack-sdk.git
clone mcp https://github.com/hashicorp/terraform-mcp-server.git
clone mcp https://github.com/awslabs/mcp.git
clone mcp https://github.com/googleapis/genai-toolbox.git
clone mcp https://github.com/pydantic/logfire-mcp.git
clone mcp https://github.com/dbt-labs/dbt-mcp.git
clone mcp https://github.com/cloudflare/mcp-server-cloudflare.git
clone mcp https://github.com/redis/mcp-redis.git
clone mcp https://github.com/mongodb-js/mongodb-mcp-server.git
clone mcp https://github.com/neondatabase/mcp-server-neon.git
clone mcp https://github.com/stripe/agent-toolkit.git
echo "TOTAL: $(find "$DEST" -maxdepth 3 -name .git | wc -l | tr -d ' ') repos"
