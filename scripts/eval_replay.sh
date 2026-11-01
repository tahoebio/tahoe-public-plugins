#!/bin/sh
# Replay a recording through the local proxy and keep the runner's evidence.
# Nothing is written under plugins/. A failing runner still leaves its files.
# Offline tests may execute this script only with a stub runner on PATH.
set -eu

if [ "$#" -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  echo "usage: scripts/eval_replay.sh RECORDING_DIR RUN_DIR" >&2
  exit 2
fi

RECORDING_DIR=$1
RUN_DIR=$2
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
MAX_COST_USD=${MAX_COST_USD:-20}
WORK=$(mktemp -d "${TMPDIR:-/tmp}/eval-release.XXXXXX")
PROXY_PID=
cleanup() {
  if [ -n "$PROXY_PID" ]; then
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT
mkdir -p "$RUN_DIR" "$WORK/out" "$WORK/plugin"
cp -R "$ROOT/plugins/tara/." "$WORK/plugin/"
uv run python "$ROOT/scripts/eval_cases.py" "$WORK/plugin/evals"

uv run python "$ROOT/scripts/eval_proxy.py" replay \
  --recording "$RECORDING_DIR" \
  --port-file "$WORK/port" \
  --misses "$RUN_DIR/eval-replay-misses.jsonl" &
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

copy_if_present "$WORK/out/aggregate-result.json" "$RUN_DIR/eval-replay-aggregate-result.json"
copy_if_present "$WORK/out/report.html" "$RUN_DIR/eval-replay-report.html"
copy_if_present "$WORK/result.json" "$RUN_DIR/eval-replay-result.json"

checker_status=0
if [ -f "$RUN_DIR/eval-replay-aggregate-result.json" ]; then
  uv run python "$ROOT/scripts/check_evals.py" \
    --from-aggregate "$RUN_DIR/eval-replay-aggregate-result.json" \
    --out "$RUN_DIR/eval-replay-record.json" || checker_status=$?
else
  echo "no aggregate to check" >&2
  checker_status=1
fi

if [ "$runner_status" -ne 0 ]; then
  exit "$runner_status"
fi
exit "$checker_status"
