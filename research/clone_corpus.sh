#!/usr/bin/env bash
# Acquire the research corpus for the software-engineering agent domain.
# Three categories, mirroring the brief: domain evals, domain automation/skills,
# domain MCP tool servers. Shallow clones only; the corpus is gitignored.
set -u
DEST="$(cd "$(dirname "$0")" && pwd)/repos"
mkdir -p "$DEST"

clone() {  # clone <category> <url>
  local cat="$1" url="$2"
  local name; name="$(basename "$url" .git)"
  local owner; owner="$(basename "$(dirname "$url")")"
  local dir="$DEST/$cat/${owner}__${name}"
  if [ -d "$dir/.git" ]; then echo "have  $cat/${owner}__${name}"; return 0; fi
  mkdir -p "$(dirname "$dir")"
  if timeout 240 git clone --depth 1 --single-branch --quiet "$url" "$dir" 2>/dev/null; then
    echo "ok    $cat/${owner}__${name}  ($(du -sh "$dir" 2>/dev/null | cut -f1))"
  else
    echo "FAIL  $cat/${owner}__${name}"; rm -rf "$dir"
  fi
}

# ---- 1. domain evals / benchmarks / arenas -------------------------------
clone evals https://github.com/princeton-nlp/SWE-bench.git
clone evals https://github.com/SWE-agent/SWE-agent.git
clone evals https://github.com/microsoft/AIOpsLab.git
clone evals https://github.com/sierra-research/tau-bench.git
clone evals https://github.com/TheAgentCompany/TheAgentCompany.git
clone evals https://github.com/laude-institute/terminal-bench.git
clone evals https://github.com/commit-0/commit0.git
clone evals https://github.com/openai/SWELancer-Benchmark.git
clone evals https://github.com/METR/vivaria.git
clone evals https://github.com/openai/evals.git

# ---- 2. domain automation / agent harnesses / skills ---------------------
clone automation https://github.com/All-Hands-AI/OpenHands.git
clone automation https://github.com/anthropics/claude-code.git
clone automation https://github.com/anthropics/anthropic-cookbook.git
clone automation https://github.com/danielmiessler/fabric.git
clone automation https://github.com/github/awesome-copilot.git

# ---- 3. domain MCP tool servers -----------------------------------------
clone mcp https://github.com/modelcontextprotocol/servers.git
clone mcp https://github.com/github/github-mcp-server.git
clone mcp https://github.com/getsentry/sentry-mcp.git
clone mcp https://github.com/grafana/mcp-grafana.git
clone mcp https://github.com/sooperset/mcp-atlassian.git
clone mcp https://github.com/PagerDuty/pagerduty-mcp-server.git
clone mcp https://github.com/containers/kubernetes-mcp-server.git
clone mcp https://github.com/GLips/Figma-Context-MCP.git
clone mcp https://github.com/elastic/mcp-server-elasticsearch.git
clone mcp https://github.com/snyk/snyk-ls.git

echo
echo "corpus: $(find "$DEST" -maxdepth 2 -name .git | wc -l | tr -d ' ') repos, $(du -sh "$DEST" 2>/dev/null | cut -f1)"
