#!/usr/bin/env bash
# Serve a local model on the CPU with vLLM (OpenAI-compatible API on port 8000).
# Usage: ./serve_local_llm.sh [model] [port]
#   ./serve_local_llm.sh                    # Qwen/Qwen3-0.6B
#   ./serve_local_llm.sh Qwen/Qwen3-1.7B
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${1:-Qwen/Qwen3-0.6B}"
PORT="${2:-8000}"

# vLLM's CPU wheels need Intel OpenMP (shipped in the venv) and TCMalloc preloaded.
export LD_PRELOAD="/usr/lib/libtcmalloc_minimal.so.4:$PWD/.venv-vllm/lib/libiomp5.so${LD_PRELOAD:+:$LD_PRELOAD}"
# Memory for the KV cache, in GiB. Small, since we send short prompts one at a time.
export VLLM_CPU_KVCACHE_SPACE="${VLLM_CPU_KVCACHE_SPACE:-2}"
# Leave one core free for the API server and the Flask app.
export VLLM_CPU_NUM_OF_RESERVED_CPU="${VLLM_CPU_NUM_OF_RESERVED_CPU:-1}"

exec .venv-vllm/bin/vllm serve "$MODEL" \
  --port "$PORT" \
  --dtype bfloat16 \
  --max-model-len 4096 \
  --max-num-seqs 2
