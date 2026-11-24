"""Сводка прогонов scripts/bench_agent.py: llama против Strata по каждой задаче и в целом.

    python scripts/bench_agent_report.py bench/agent/llama_pad0k_*.jsonl bench/agent/strata_pad0k_*.jsonl
"""
import json, sys
from collections import defaultdict
from pathlib import Path


def load(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def stats(rows):
    rounds = [s for r in rows for t in r["turns"] for s in t["rounds"]]
    new_tok = sum(max(0, (s.get("prompt_n") or 0) - (s.get("cached") or 0)) for s in rounds)
    p_ms = sum(s.get("prompt_ms") or 0 for s in rounds)
    g_n = sum(s.get("gen_n") or 0 for s in rounds)
    g_ms = sum(s.get("gen_ms") or 0 for s in rounds)
    follow = [t["rounds"][0] for r in rows for t in r["turns"][1:] if t["rounds"]]
    return {
        "runs": len(rows),
        "ok": sum(r["ok"] for r in rows),
        "secs": sum(r["secs"] for r in rows),
        "rounds": len(rounds),
        "length": sum(t["length"] for r in rows for t in r["turns"]),
        "repeats": sum(t["repeats"] for r in rows for t in r["turns"]),
        "timeouts": sum(t["timeout"] or t["max_rounds"] for r in rows for t in r["turns"]),
        "errors": sum(len(t["errors"]) for r in rows for t in r["turns"]),
        "think_k": sum(s["think_chars"] for s in rounds) / 1000,
        "prefill": new_tok / (p_ms / 1000) if p_ms else 0,
        "decode": g_n / (g_ms / 1000) if g_ms else 0,
        "cached_pct": 100 * sum(s.get("cached") or 0 for s in rounds) / max(1, sum(s.get("prompt_n") or 0 for s in rounds)),
        "follow_wall": sum(s["wall"] for s in follow) / len(follow) if follow else None,
        "min_ram": min((r.get("min_ram_avail_gb") or 99) for r in rows),
        "max_vram": max((r.get("max_vram_gb") or 0) for r in rows),
    }


def main():
    rows = load(sys.argv[1:])
    by_engine = defaultdict(list)
    for r in rows:
        by_engine[r["engine"]].append(r)
    engines = sorted(by_engine)
    print("По задачам (успешно/прогонов, среднее время, шагов в среднем):")
    tasks = sorted({r["task"] for r in rows})
    for task in tasks:
        cells = []
        for e in engines:
            rr = [r for r in by_engine[e] if r["task"] == task]
            if rr:
                n_rounds = sum(len(t["rounds"]) for r in rr for t in r["turns"]) / len(rr)
                cells.append(f"{e}: {sum(r['ok'] for r in rr)}/{len(rr)}, {sum(r['secs'] for r in rr) / len(rr):6.1f} с, {n_rounds:4.1f} шага")
        print(f"  {task:8} " + " | ".join(cells))
    print("\nВ целом:")
    keys = [("ok", "решено", "{:.0f}"), ("runs", "прогонов", "{:.0f}"), ("secs", "время всего, с", "{:.0f}"),
            ("rounds", "шагов", "{:.0f}"), ("length", "обрывов length", "{:.0f}"), ("repeats", "повторных вызовов", "{:.0f}"),
            ("timeouts", "таймаут/лимит шагов", "{:.0f}"), ("errors", "ошибок связи", "{:.0f}"),
            ("think_k", "размышлений, тыс. символов", "{:.1f}"), ("prefill", "чтение промпта, ток/с", "{:.0f}"),
            ("decode", "генерация, ток/с", "{:.1f}"), ("cached_pct", "промпт из кэша, %", "{:.1f}"),
            ("follow_wall", "первый шаг после нового сообщения, с", "{:.1f}"), ("min_ram", "мин. свободно RAM, ГБ", "{:.1f}"),
            ("max_vram", "макс. VRAM, ГБ", "{:.1f}")]
    st = {e: stats(by_engine[e]) for e in engines}
    print(f"  {'':40}" + "".join(f"{e:>12}" for e in engines))
    for k, label, f in keys:
        print(f"  {label:40}" + "".join(f"{(f.format(st[e][k]) if st[e][k] is not None else '-'):>12}" for e in engines))


if __name__ == "__main__":
    main()
