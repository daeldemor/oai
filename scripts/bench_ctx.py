#!/usr/bin/env python3
"""Скорость и качество на длинном контексте для запущенного llama-server.

Для каждой глубины заполнения: промпт из текстов проекта нужной длины,
в него на заданную глубину вставлена «иголка» (секретный код). Модель
просят назвать код. Меряем prefill (ток/с), генерацию (ток/с) по timings
llama-server и то, нашла ли модель иголку.

Использование:
  python scripts/bench_ctx.py --url http://127.0.0.1:8080 --fill 4000 16000 60000
  python scripts/bench_ctx.py --url ... --fill 120000 --depths 0.1 0.5 0.9 --log logs/ctx.json

Между запусками кэш промпта сбрасывается (cache_prompt=false), чтобы
prefill мерялся честно.
"""
import argparse
import json
import random
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
QUESTION = "\n\nВопрос: какой секретный код упомянут в тексте выше? Ответь только кодом."


def corpus():
    parts = []
    for pat in ("docs/*.md", "scripts/*.py", "scripts/*.sh", "configs/*.yaml", "README.md"):
        for p in sorted(ROOT.glob(pat)):
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(parts)


def n_tokens(url, text):
    r = requests.post(f"{url}/tokenize", json={"content": text}, timeout=120)
    r.raise_for_status()
    return len(r.json()["tokens"])


def build_prompt(url, base, target, depth, code):
    # Сколько символов на токен у этого корпуса — по образцу.
    sample = base[:20000]
    cpt = len(sample) / n_tokens(url, sample)
    reps = int(target * cpt / len(base)) + 1
    text = (base + "\n\n") * reps
    text = text[: int(target * cpt)]
    pos = int(len(text) * depth)
    needle = f"\n\nВажно: секретный код — {code}. Запомни его.\n\n"
    return text[:pos] + needle + text[pos:]


def run(url, prompt, max_tokens):
    payload = {
        "messages": [{"role": "user", "content": prompt + QUESTION}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "cache_prompt": False,
        "reasoning_effort": "none",
    }
    t0 = time.time()
    r = requests.post(f"{url}/v1/chat/completions", json=payload, timeout=3600)
    r.raise_for_status()
    d = r.json()
    msg = d["choices"][0]["message"]
    return {
        "wall_s": round(time.time() - t0, 1),
        "prompt_n": d["timings"]["prompt_n"],
        "prefill_tps": round(d["timings"]["prompt_per_second"], 1),
        "gen_n": d["timings"]["predicted_n"],
        "gen_tps": round(d["timings"]["predicted_per_second"], 1),
        "answer": (msg.get("content") or "").strip(),
        "reasoning": (msg.get("reasoning_content") or "")[-300:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--fill", type=int, nargs="+", required=True, help="длина промпта в токенах")
    ap.add_argument("--depths", type=float, nargs="+", default=[0.5], help="глубина иголки, 0..1")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    base = corpus()
    rows = []
    for fill in args.fill:
        for depth in args.depths:
            code = f"{random.randint(1000, 9999)}-{random.choice('КЛМНПРСТ')}{random.randint(10, 99)}"
            prompt = build_prompt(args.url, base, fill, depth, code)
            res = run(args.url, prompt, args.max_tokens)
            res.update(fill=fill, depth=depth, code=code, found=code in res["answer"] + res["reasoning"])
            rows.append(res)
            print(f"fill={res['prompt_n']:>7} depth={depth:.2f} prefill={res['prefill_tps']:>8} t/s "
                  f"gen={res['gen_tps']:>6} t/s wall={res['wall_s']:>6}s found={res['found']} "
                  f"answer={res['answer'][:40]!r}", flush=True)
    if args.log:
        Path(args.log).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
