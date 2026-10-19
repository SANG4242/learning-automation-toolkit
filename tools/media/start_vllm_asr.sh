#!/usr/bin/env bash
set -euo pipefail
: "${QWEN_ASR_MODEL:=Qwen/Qwen3-ASR-1.7B}"
: "${QWEN_ASR_PORT:=8000}"
: "${QWEN_GPU_MEMORY_UTILIZATION:=0.85}"
exec vllm serve "$QWEN_ASR_MODEL" \
  --host 127.0.0.1 \
  --port "$QWEN_ASR_PORT" \
  --dtype float16 \
  --max-model-len 4096 \
  --gpu-memory-utilization "$QWEN_GPU_MEMORY_UTILIZATION" \
  --limit-mm-per-prompt '{"audio": {"count": 1, "length": 32768}}' \
  --hf-overrides '{"architectures":["Qwen3ASRRealtimeGeneration"]}'
