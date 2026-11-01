#!/bin/sh
# Record a live eval through the local proxy and keep the runner's evidence.
# Needs EVAL_UPSTREAM_URL and EVAL_TOKEN_FILE. Nothing is written under plugins/.
# Offline tests may execute this script only with a stub runner on PATH.
set -eu

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "usage: scripts/eval_record.sh RUN_DIR" >&2
  exit 2
fi
if [ -z "${EVAL_UPSTREAM_URL:-}" ] || [ -z "${EVAL_TOKEN_FILE:-}" ]; then
  echo "EVAL_UPSTREAM_URL and EVAL_TOKEN_FILE are required" >&2
  exit 2
fi

RUN_DIR=$1
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
MAX_COST_USD=${MAX_COST_USD:-20}
WORK=$(mktemp -d "${TMPDIR:-/tmp}/eval-record.XXXXXX")
PROXY_PID=
cleanup() {
  if [ -n "$PROXY_PID" ]; then
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT
mkdir -p "$RUN_DIR/eval-recording" "$WORK/out" "$WORK/plugin"
cp -R "$ROOT/plugins/tara/." "$WORK/plugin/"
uv run python "$ROOT/scripts/eval_cases.py" "$WORK/plugin/evals"

uv run python "$ROOT/scripts/eval_proxy.py" record \
  --upstream "$EVAL_UPSTREAM_URL" \
  --token-file "$EVAL_TOKEN_FILE" \
  --out "$RUN_DIR/eval-recording" \
  --port-file "$WORK/port" &
PROXY_PID=$!

i=0
while [ ! -s "$WORK/port" ]; do
  i=$((i + 1))
  if [ "$i" -ge 200 ]; then
    echo "proxy did not bind" >&2
    exit 1
  fi
  sleep 0.1
done
PORT=$(cat "$WORK/port")
uv run python "$ROOT/scripts/eval_probe.py" --copy "$WORK/plugin" --port "$PORT"

runner_status=0
claude plugin eval "$WORK/plugin" \
  --tag release \
  --mocks off \
  --allow-tools "mcp__plugin_tara_tahoe-public__*" \
  --ablation none \
  --runs 1 \
  --max-cost-usd "$MAX_COST_USD" \
  --threshold 1.0 \
  --no-publish \
  --trust-plugin \
  --output-dir "$WORK/out" \
  --json "$WORK/result.json" || runner_status=$?

copy_if_present() {
  src=$1
  dest=$2
  if [ -f "$src" ]; then
    cp "$src" "$dest"
  else
    echo "missing result file: $dest" >&2
  fi
}

copy_if_present "$WORK/out/aggregate-result.json" "$RUN_DIR/eval-live-aggregate-result.json"
copy_if_present "$WORK/out/report.html" "$RUN_DIR/eval-live-report.html"
copy_if_present "$WORK/result.json" "$RUN_DIR/eval-live-result.json"

checker_status=0
if [ -f "$RUN_DIR/eval-live-aggregate-result.json" ]; then
  uv run python "$ROOT/scripts/check_evals.py" \
    --from-aggregate "$RUN_DIR/eval-live-aggregate-result.json" \
    --out "$RUN_DIR/eval-record.json" || checker_status=$?
else
  echo "no aggregate to check" >&2
  checker_status=1
fi

disclosure_status=0
if [ -f "$RUN_DIR/eval-recording/responses.json" ]; then
  uv run python -c '
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(1 if payload.get("disclosure_hits") else 0)
' "$RUN_DIR/eval-recording/responses.json" || disclosure_status=$?
else
  echo "missing result file: $RUN_DIR/eval-recording/responses.json" >&2
  disclosure_status=1
fi

if [ "$runner_status" -ne 0 ]; then
  exit "$runner_status"
fi
if [ "$disclosure_status" -ne 0 ]; then
  exit "$disclosure_status"
fi
exit "$checker_status"
