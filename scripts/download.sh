#!/usr/bin/env bash
# Скачивание готового abliterated/heretic GGUF с Hugging Face.
#
# Использование:
#   bash scripts/download.sh <repo> [паттерн_кванта] [lmstudio|local]
#
# Примеры:
#   bash scripts/download.sh mradermacher/gemma-4-12B-it-uncensored-heretic-GGUF Q5_K_M
#   bash scripts/download.sh DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF IQ4_XS local
#
# lmstudio (по умолчанию) — кладёт в каталог LM Studio, файл сразу виден
# в LM Studio и Bionic. local — в X:\OAI-models\ (SSD).
set -euo pipefail

REPO="${1:?укажите репозиторий, напр. mradermacher/gemma-4-12B-it-uncensored-heretic-GGUF}"
PATTERN="${2:-Q5_K_M}"
TARGET="${3:-lmstudio}"

echo "== Список GGUF в $REPO =="
FILES=$(curl -fsSL "https://huggingface.co/api/models/$REPO" \
  | python -c "import sys,json; [print(f['rfilename']) for f in json.load(sys.stdin)['siblings'] if f['rfilename'].endswith('.gguf')]")
echo "$FILES"

FILE=$(echo "$FILES" | grep -i "$PATTERN" | head -1 || true)
if [ -z "$FILE" ]; then
  echo
  echo "[!!] Файл с паттерном '$PATTERN' не найден. Выберите из списка выше"
  exit 1
fi

PUBLISHER="${REPO%%/*}"
NAME="${REPO##*/}"
if [ "$TARGET" = "lmstudio" ]; then
  DEST="/c/Users/rmari/.lmstudio/models/$PUBLISHER/$NAME"
else
  DEST="/x/OAI-models/$NAME"
fi
mkdir -p "$DEST"

echo
echo "== Качаю $FILE -> $DEST =="
curl -fSL --progress-bar -o "$DEST/$FILE" \
  "https://huggingface.co/$REPO/resolve/main/$FILE"

echo
echo "Готово: $DEST/$FILE"
if [ "$TARGET" = "lmstudio" ]; then
  echo "Модель появится в LM Studio (и Bionic) после перезапуска приложения."
else
  echo "Запуск: bash scripts/serve.sh \"$DEST/$FILE\""
fi
