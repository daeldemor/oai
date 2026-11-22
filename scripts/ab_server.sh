#!/usr/bin/env bash
# A/B замер llama-server: поднять, снять compute-буфер, прогнать bench_ctx.py, остановить.
# Использование: scripts/ab_server.sh <exe> <tag> "<аргументы сервера>" <fill...>
# Переменные окружения (например LLAMA_ATTN_REL_SPLIT=0) передаются серверу как есть.
set -u
EXE=$1; TAG=$2; ARGS=$3; shift 3
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
export PATH="/c/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.5/bin/x64:$PATH"
M=${MODEL:-C:/Users/rmari/.lmstudio/models/AtomicChat/Inkling-2-Mini-Uncensored-GGUF/Inkling-2-Mini-Uncensored-AD-IQ3_S.gguf}
LOG=logs/ab-$TAG.log
# shellcheck disable=SC2086
"$EXE" -m "$M" --port 8080 --parallel 1 -ngl 999 --flash-attn on --jinja --load-mode none -b 2048 -lv 4 $ARGS > "$LOG" 2>&1 &
PID=$!
for _ in $(seq 1 150); do sleep 2; curl -s localhost:8080/health | grep -q ok && break; kill -0 $PID 2>/dev/null || { echo "[$TAG] server died"; tail -5 "$LOG"; exit 1; }; done
grep -E "CUDA0 compute buffer size" "$LOG" | tail -1 | sed "s/^.*CUDA0/[$TAG] CUDA0/"
echo "[$TAG] VRAM used: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/bench_ctx.py --fill "$@" --depths ${DEPTHS:-0.5} --log "logs/ab-$TAG.json" | sed "s/^/[$TAG] /"
taskkill //F //IM "$(basename "$EXE")" >/dev/null 2>&1; sleep 3
