#!/usr/bin/env python3
"""Обёртка над Heretic: автоматическая аблитерация базовой модели.

Heretic сам подбирает направления отказа по слоям и силу подавления,
минимизируя одновременно отказы и KL-дивергенцию к исходной модели.

Пример:
    python scripts/abliterate.py --model Qwen/Qwen3-8B \
        --output models/qwen3-8b-abliterated --trials 60

Требования: активированное venv (scripts/setup.sh), достаточно RAM (см. docs/02).
Загрузка базовой модели идёт через huggingface_hub — для gated-моделей
предварительно: huggingface-cli login
"""
import argparse
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description="Abliterate a HF model with Heretic")
    ap.add_argument("--model", required=True, help="HF id базовой модели, напр. Qwen/Qwen3-8B")
    ap.add_argument("--output", required=True, help="Каталог для сохранения результата (safetensors)")
    ap.add_argument("--trials", type=int, default=60,
                    help="Число Optuna-итераций подбора (больше = точнее и дольше)")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16"],
                    help="Точность загрузки весов")
    ap.add_argument("--max-batch-size", type=int, default=0,
                    help="0 = авто (Heretic сам подберёт под VRAM)")
    args = ap.parse_args()

    os.environ.setdefault("HF_HOME", r"G:\Work\OAI\models\.hf-cache")
    os.makedirs(args.output, exist_ok=True)

    cmd = [
        sys.executable, "-m", "heretic",
        args.model,
        "--output", args.output,
        "--dtype", args.dtype,
        "--n-trials", str(args.trials),
    ]
    if args.max_batch_size > 0:
        cmd += ["--max-batch-size", str(args.max_batch_size)]

    print("Запуск:", " ".join(cmd))
    print("Модель грузится с device_map=auto: часть слоёв уйдёт в RAM — это нормально.\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)

    print(f"""
Готово. Веса сохранены в: {args.output}

Следующие шаги:
  1. Квантование в GGUF:   bash scripts/quantize.sh "{args.output}" q5_k_m
  2. Оценка качества:      python scripts/evaluate.py --base {args.model} \\
                             --ablated http://localhost:8080/v1
  3. Сервинг:              bash scripts/serve.sh <путь к .gguf>
""")


if __name__ == "__main__":
    main()
