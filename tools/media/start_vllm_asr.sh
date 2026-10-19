#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
DATA_DIR="${QWEN_ASR_DATA_DIR:-${LEARNING_TOOLS_DATA_DIR:-$ROOT/.local}}"
MODEL="${QWEN_ASR_MODEL:-Qwen/Qwen3-ASR-1.7B}"
PORT="${QWEN_ASR_PORT:-8000}"
HOST="${QWEN_ASR_HOST:-127.0.0.1}"
IDLE_TIMEOUT="${QWEN_ASR_IDLE_TIMEOUT:-300}"
VENV="${QWEN_ASR_VENV:-$HOME/vllm-env}"
mkdir -p "$DATA_DIR"
if [ -f "$VENV/bin/activate" ]; then source "$VENV/bin/activate"; fi
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
export VLLM_DISABLE_FLASHINFER="${VLLM_DISABLE_FLASHINFER:-1}"
export VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS="${VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS:-0}"
UTIL="${QWEN_GPU_MEMORY_UTILIZATION:-}"
if [ -z "$UTIL" ]; then
  UTIL=$(python -c 'import torch; free,total=torch.cuda.mem_get_info(); print(f"{min(.95,max(.50,free/total-.02)):.2f}")')
  sleep 3
fi
exec 9>"$DATA_DIR/asr-service.lock"
if ! flock -n 9; then echo 'ASR launcher already running'; exit 1; fi
HEARTBEAT="$DATA_DIR/.vllm_heartbeat"
PID_FILE="$DATA_DIR/asr-service.pid"
STOP_FILE="$DATA_DIR/asr-stop-request"
if [ -e "$STOP_FILE" ]; then mv "$STOP_FILE" "$STOP_FILE.previous.$(date +%s%N)"; fi
SERVER_PID=''
cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -TERM -- "-$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 10); do kill -0 "$SERVER_PID" 2>/dev/null || break; sleep 1; done
    if kill -0 "$SERVER_PID" 2>/dev/null; then kill -KILL -- "-$SERVER_PID" 2>/dev/null || true; fi
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE" "$STOP_FILE"
}
trap cleanup EXIT
trap 'exit 0' INT TERM
if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "Port $PORT is already serving; connect to it instead of starting another server."
  exit 1
fi
touch "$HEARTBEAT"
printf 'Model: %s\nPort: %s\nGPU utilization: %s\nIdle timeout: %ss\n' "$MODEL" "$PORT" "$UTIL" "$IDLE_TIMEOUT"
setsid vllm serve "$MODEL" \
  --host "$HOST" --port "$PORT" --dtype float16 \
  --max-model-len 4096 --gpu-memory-utilization "$UTIL" \
  --limit-mm-per-prompt '{"audio": {"count": 1, "length": 32768}}' \
  --hf-overrides '{"architectures":["Qwen3ASRRealtimeGeneration"]}' \
  >>"$DATA_DIR/vllm.log" 2>&1 &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" > "$PID_FILE"
READY=0
for _ in $(seq 1 180); do
  kill -0 "$SERVER_PID" 2>/dev/null || { echo 'vLLM exited; see vllm.log'; exit 1; }
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then READY=1; touch "$HEARTBEAT"; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then echo 'vLLM startup timed out'; exit 1; fi
echo 'vLLM ready; progress is in vllm.log'
while kill -0 "$SERVER_PID" 2>/dev/null; do
  if [ -e "$STOP_FILE" ]; then echo 'Stopping managed ASR for alignment'; exit 0; fi
  NOW=$(date +%s)
  LAST=$(stat -c %Y "$HEARTBEAT" 2>/dev/null || echo "$NOW")
  if [ "$IDLE_TIMEOUT" -gt 0 ] && [ "$((NOW - LAST))" -ge "$IDLE_TIMEOUT" ]; then
    echo 'ASR idle timeout; releasing GPU'
    exit 0
  fi
  sleep 2
done
wait "$SERVER_PID"
