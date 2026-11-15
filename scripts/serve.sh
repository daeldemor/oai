#!/usr/bin/env bash
# Запуск OpenAI-совместимого сервера llama.cpp под 16 ГБ VRAM.
# Использование: bash scripts/serve.sh path/to/model.gguf [ctx_size]
set -euo pipefail

GGUF="${1:?укажите путь к .gguf}"
CTX="${2:-16384}"
PORT="${PORT:-8080}"

# llama-server: по умолчанию берём CUDA-сборку, уже поставленную с LM Studio.
# Переопределяется переменной LLAMA_SERVER_BIN.
SERVER_BIN="${LLAMA_SERVER_BIN:-/c/Users/rmari/.lmstudio/extensions/backends/llama.cpp-win-x86_64-nvidia-cuda-avx2-2.55.0/llama-server.exe}"
# NB: Strata тоже слушает :8080 по умолчанию — не запускайте одновременно
# или задайте другой PORT.

exec "$SERVER_BIN" \
  --model "$GGUF" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --n-gpu-layers 999 \
  --flash-attn \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --jinja \
  --temp 0.7 --top-p 0.95
# Пояснения:
#   --n-gpu-layers 999   — все слои на GPU (сработает для моделей из configs/models.yaml)
#   --cache-type-* q8_0  — квантованный KV-кэш: экономия VRAM на длинном контексте
#   --flash-attn         — обязательно на RTX 50xx
# Если модель не влезает — уменьшите слои: --n-gpu-layers 40 (и т.д. вниз),
# остаток уйдёт на 9800X3D, скорость упадёт плавно, без падения.
