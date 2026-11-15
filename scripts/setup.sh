#!/usr/bin/env bash
# Создание venv и установка зависимостей (Git Bash, Windows).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=py
$PY -3.11 -m venv .venv 2>/dev/null || python -m venv .venv
source .venv/Scripts/activate

python -m pip install --upgrade pip

# torch/torchvision закреплены в requirements.txt; CUDA-индекс как extra —
# pip выберет 2.14.1+cu130 (локальная метка старше CPU-сборки с PyPI).
# RTX 50xx (Blackwell, sm_120) нужен cu128+; cu124 не подходит.
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu130

python -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" || \
  echo "[warn] torch без CUDA ($(python -c 'import torch; print(torch.__version__)')) — проверьте индекс на pytorch.org"

echo
echo "Готово. Активируйте окружение:  source .venv/Scripts/activate"
echo "Проверка окружения:             python scripts/check_env.py"
