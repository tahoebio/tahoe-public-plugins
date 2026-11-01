#!/bin/sh
# Live probe: one case, mocks off, against a temporary plugin copy.
# EVAL_PROBE_MCP_URL is the staging endpoint. This script does not embed it,
# does not modify the repository plugin, and does not write under plugins/.
# Cases are rendered into the copy. Mocks are not built: the run passes
# --mocks off and uses the copy's real server. Offline tests must not execute it.
set -eu

if [ -z "${EVAL_PROBE_MCP_URL:-}" ]; then
  echo "EVAL_PROBE_MCP_URL is required" >&2
  exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/eval-probe.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/plugin"
cp -R "$ROOT/plugins/tara/." "$WORK/plugin/"

uv run python "$ROOT/scripts/eval_cases.py" "$WORK/plugin/evals"
uv run python "$ROOT/scripts/eval_probe.py" \
  --copy "$WORK/plugin" \
  --url "$EVAL_PROBE_MCP_URL"

claude plugin eval "$WORK/plugin" \
  --case live-probe \
  --mocks off \
  --allow-tools "mcp__plugin_tara_tahoe-public__*" \
  --ablation none \
  --runs 1 \
  --threshold 1.0 \
  --no-publish \
  --trust-plugin \
  --json
