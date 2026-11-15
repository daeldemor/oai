#!/usr/bin/env bash
# Создание venv и установка зависимостей (Git Bash, Windows).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=py
$PY -3.11 -m venv .venv 2>/dev/null || python -m venv .venv
source .venv/Scripts/activate

python -m pip install --upgrade pip

# PyTorch с CUDA ставим ПЕРВЫМ, иначе requirements притянет CPU-сборку с PyPI.
# RTX 50xx (Blackwell, sm_120) поддерживается только с cu128+; cu124 не подходит.
pip install torch --index-url https://download.pytorch.org/whl/cu128 || \
  echo "[warn] CUDA-сборка torch не встала — проверьте индекс на pytorch.org для вашей версии CUDA"
pip install -r requirements.txt

echo
echo "Готово. Активируйте окружение:  source .venv/Scripts/activate"
echo "Проверка окружения:             python scripts/check_env.py"
