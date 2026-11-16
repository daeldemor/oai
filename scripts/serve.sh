#!/usr/bin/env bash
# Запуск OpenAI-совместимого сервера llama.cpp под 16 ГБ VRAM.
# Использование: bash scripts/serve.sh path/to/model.gguf [ctx_size]
set -euo pipefail

GGUF="${1:?укажите путь к .gguf}"
CTX="${2:-16384}"
PORT="${PORT:-8080}"

# llama-server: официальный релиз llama.cpp b12427 (CUDA 13.5), распакован
# в llama.cpp-bin/ (содержит все CUDA-DLL; бэкенды LM Studio не подходят —
# им не хватает cudart/cublas вне приложения). Переопределяется LLAMA_SERVER_BIN.
SERVER_BIN="${LLAMA_SERVER_BIN:-/g/Work/OAI/llama.cpp-bin/llama-server.exe}"
# NB: Strata тоже слушает :8080 по умолчанию — не запускайте одновременно
# или задайте другой PORT.

EXTRA_ARGS=()
# CPU_MOE=all  — все эксперты MoE на CPU (требует RAM > веса модели!).
# CPU_MOE=N    — эксперты первых N слоёв на CPU, остальные на GPU
#                (правильный режим при 32 ГБ RAM: 21.8-ГБ модель целиком
#                в RAM не помещается и уходит в своп — 0.12 ток/с).
if [ "${CPU_MOE:-0}" = "all" ]; then
  EXTRA_ARGS+=(--cpu-moe)
elif [ "${CPU_MOE:-0}" != "0" ]; then
  EXTRA_ARGS+=(--n-cpu-moe "$CPU_MOE")
fi

exec "$SERVER_BIN" \
  --model "$GGUF" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --parallel "${PARALLEL:-1}" \
  --n-gpu-layers 999 \
  --flash-attn on \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --jinja \
  --temp 0.7 --top-p 0.95 \
  "${EXTRA_ARGS[@]}"
# Пояснения:
#   --n-gpu-layers 999   — все слои на GPU (сработает для моделей из configs/models.yaml)
#   --cache-type-* q8_0  — квантованный KV-кэш: экономия VRAM на длинном контексте
#   --flash-attn         — обязательно на RTX 50xx
# Если модель не влезает — уменьшите слои: --n-gpu-layers 40 (и т.д. вниз),
# остаток уйдёт на 9800X3D, скорость упадёт плавно, без падения.
