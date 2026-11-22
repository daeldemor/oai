#!/usr/bin/env bash
# Конвертация safetensors -> GGUF F16 -> квант (llama.cpp).
# Использование: bash scripts/quantize.sh X:/OAI-models/qwen3-8b-abliterated q5_k_m
set -euo pipefail

MODEL_DIR="${1:?укажите каталог с safetensors}"
QUANT="${2:-q5_k_m}"
LLAMA_DIR="${LLAMA_CPP_DIR:-/g/Work/OAI/llama.cpp}"
OUT_DIR="$MODEL_DIR/gguf"
mkdir -p "$OUT_DIR"

if [ ! -d "$LLAMA_DIR" ]; then
  echo "Клонирую llama.cpp в $LLAMA_DIR ..."
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
  pip install -r "$LLAMA_DIR/requirements.txt" || true
fi

BASE=$(basename "$MODEL_DIR")
F16="$OUT_DIR/${BASE}-f16.gguf"
QGGUF="$OUT_DIR/${BASE}-${QUANT}.gguf"

echo "== safetensors -> GGUF F16 =="
python "$LLAMA_DIR/convert_hf_to_gguf.py" "$MODEL_DIR" \
  --outfile "$F16" --outtype f16

echo "== quantize -> ${QUANT} =="
# Бинарник llama-quantize: либо собранный, либо скачанный релиз
QUANTIZE_BIN="${LLAMA_QUANTIZE_BIN:-$LLAMA_DIR/build/bin/llama-quantize}"
if [ ! -x "$QUANTIZE_BIN" ] && ! command -v llama-quantize >/dev/null; then
  echo "llama-quantize не найден. Скачайте релиз llama.cpp для Windows (CUDA-сборку)"
  echo "или соберите:  cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release"
  echo "F16 GGUF уже готов: $F16"
  exit 1
fi

$(command -v llama-quantize || echo "$QUANTIZE_BIN") "$F16" "$QGGUF" "$QUANT"
echo "Готово: $QGGUF"
