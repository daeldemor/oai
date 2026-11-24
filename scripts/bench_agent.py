"""Агентный стенд: одни и те же задачи с инструментами на llama.cpp и на Strata.

Запуск (сервер на 127.0.0.1:8080 уже поднят):
    python scripts/bench_agent.py --engine llama --reps 3 --out bench/agent
Каждая задача идёт в свежей копии тестового проекта (без сети). Инструменты те же, что в чате Strata
(scripts/inkling_mcp.py), подтверждения выключены, рабочая папка = копия проекта. История разговора
собирается клиентом и отправляется целиком на каждом шаге, как это делают веб-чаты.
Результат: JSONL с одной строкой на прогон задачи и сводка в конце.
"""
from __future__ import annotations

import argparse, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inkling_mcp as M  # noqa: E402

URL = "http://127.0.0.1:8080"
SAMPLING = {"temperature": 0.8, "top_p": 0.95, "top_k": 40, "min_p": 0.05}
MAX_ROUNDS, MAX_TOKENS, TASK_TIMEOUT = 30, 8192, 900
SYSTEM = ("Всегда отвечай на русском языке, если пользователь явно не попросил другой язык. "
          "Ты работаешь в папке проекта {cwd} и можешь пользоваться инструментами.")

# ---------------------------------------------------------------- тестовый проект
TOOLS_PY = {
    "tools/dates.py": "import datetime\nimport re\n\n\ndef parse_date(s):\n    return datetime.date.fromisoformat(s)\n\n\n"
                      "def is_weekend(d):\n    return d.weekday() >= 5\n\n\ndef week_of(d):\n    return d.isocalendar()[1]\n",
    "tools/money.py": "import decimal\n\n\ndef to_cents(x):\n    return int(decimal.Decimal(str(x)) * 100)\n\n\n"
                      "def from_cents(c):\n    return c / 100\n",
    "tools/text.py": "import re\nimport string\nimport unicodedata\n\n\ndef slug(s):\n    s = unicodedata.normalize('NFKD', s)\n"
                     "    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')\n\n\ndef words(s):\n    return s.split()\n\n\n"
                     "def title(s):\n    return string.capwords(s)\n\n\ndef count(s, ch):\n    return s.count(ch)\n",
    "tools/net.py": "import socket\n\n\ndef free_port():\n    with socket.socket() as s:\n        s.bind(('', 0))\n"
                    "        return s.getsockname()[1]\n",
}
FILES = {
    "README.md": "# demo-service\n\nСервис-пример для проверки агента. Порт по умолчанию 8080.\n",
    "config.json": '{\n  "server": {"host": "127.0.0.1", "port": 8080},\n  "health": "http://127.0.0.1:8080/health",\n'
                   '  "workers": 2\n}\n',
    "deploy.ps1": "$Port = 8080\nWrite-Host \"Deploying on port $Port\"\nStart-Process app.exe -ArgumentList \"--port 8080\"\n",
    "docs/notes.md": "# Заметки\n\nСервер слушает порт 8080 (см. config.json).\n\nПеременные окружения:\n"
                     "- `DEMO_LOG_LEVEL` - уровень логов (info по умолчанию)\n- `DEMO_CACHE_DIR` - папка кэша\n"
                     "- `DEMO_MAX_WORKERS` - сколько воркеров запускать\n- `DEMO_TIMEOUT_S` - таймаут запроса в секундах\n"
                     "- `DEMO_FEATURE_X` - включает экспериментальную функцию X\n",
    "src/pricing.py": "def total(items, discount=0.0):\n    \"\"\"Сумма позиций (price * qty) со скидкой discount (0.1 = 10%).\"\"\"\n"
                      "    s = 0\n    for price, qty in items:\n        s += price + qty\n    return round(s * (1 - discount), 2)\n",
    "tests/test_pricing.py": "import sys, unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
                             "from pricing import total\n\n\nclass T(unittest.TestCase):\n    def test_total(self):\n"
                             "        self.assertEqual(total([(10.0, 2), (5.5, 4)]), 42.0)\n\n    def test_discount(self):\n"
                             "        self.assertEqual(total([(100.0, 1)], 0.25), 75.0)\n\n\nif __name__ == '__main__':\n    unittest.main()\n",
}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@example.invalid",
                        "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@example.invalid"})


def make_project(root: Path) -> dict:
    """Тестовый проект с историей git. Возвращает факты для проверок."""
    if root.exists():
        def unlock(fn, path, _):                       # объекты git в Windows read-only
            os.chmod(path, 0o666)
            fn(path)
        shutil.rmtree(root, onerror=unlock)
    root.mkdir(parents=True)
    def put(rel, text):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    git(root, "init", "-q", "-b", "main")
    for rel in ("README.md", "config.json", "deploy.ps1", "docs/notes.md"):
        put(rel, FILES[rel])
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "Каркас сервиса и конфиг")
    put("tools/money.py", TOOLS_PY["tools/money.py"]); put("tools/net.py", TOOLS_PY["tools/net.py"])
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "Денежные и сетевые утилиты")
    put("tools/dates.py", TOOLS_PY["tools/dates.py"])
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "Утилиты для дат")
    put("tools/text.py", TOOLS_PY["tools/text.py"]); put("src/pricing.py", FILES["src/pricing.py"])
    put("tests/test_pricing.py", FILES["tests/test_pricing.py"])
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "Текстовые утилиты, расчёт цены и тесты")
    h = subprocess.run(["git", "log", "--format=%h", "--diff-filter=A", "--", "tools/dates.py"], cwd=root,
                       capture_output=True, text=True).stdout.split()[0]
    return {"dates_commit": h}


def py_stats(text: str) -> tuple[int, int, int]:
    lines = text.count("\n")
    defs = len(re.findall(r"^def ", text, re.M))
    imports = len(re.findall(r"^(?:import|from) ", text, re.M))
    return lines, defs, imports


# ---------------------------------------------------------------- задачи и проверки
def chk_search(root, ans, facts):
    need = ["config.json", "deploy.ps1", "notes.md", "README"]
    return all(n.lower() in ans.lower() for n in need), f"упомянуты {[n for n in need if n.lower() in ans.lower()]}"


def chk_env(root, ans, facts):
    names = re.findall(r"DEMO_[A-Z_]+", FILES["docs/notes.md"])
    got = [n for n in names if n in ans]
    return len(got) == len(names), f"{len(got)}/{len(names)} переменных"


def chk_bugfix(root, ans, facts):
    if (root / "tests/test_pricing.py").read_text(encoding="utf-8") != FILES["tests/test_pricing.py"]:
        return False, "тест изменён"
    r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_pricing", "-q"], cwd=root, capture_output=True, text=True)
    return r.returncode == 0, "тесты проходят" if r.returncode == 0 else "тесты падают"


def chk_port(root, ans, facts):
    cfg, dep = (root / "config.json").read_text(encoding="utf-8"), (root / "deploy.ps1").read_text(encoding="utf-8")
    notes = (root / "docs/notes.md").read_text(encoding="utf-8")
    ok = "8080" not in cfg and "8080" not in dep and cfg.count("9090") == 2 and dep.count("9090") == 2 and "8080" in notes
    try:
        json.loads(cfg)
    except ValueError:
        return False, "config.json сломан"
    return ok, f"cfg9090={cfg.count('9090')} dep9090={dep.count('9090')} docs8080={'8080' in notes}"


def chk_git(root, ans, facts):
    return facts["dates_commit"] in ans, f"нужен {facts['dates_commit']}"


def report_rows(root):
    p = root / "report.md"
    if not p.exists():
        return None
    rows = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        cells = [c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
        for name in TOOLS_PY:
            base = Path(name).name
            if cells and any(base in c for c in cells[:1]):
                rows[name] = [int(x) for x in re.findall(r"(?<![\w.])\d+(?![\w.])", " ".join(cells[1:]))]
    return rows


def chk_report(root, ans, facts):
    rows = report_rows(root)
    if rows is None:
        return False, "нет report.md"
    bad = [n for n, t in TOOLS_PY.items() if rows.get(n, [])[:2] != list(py_stats(t)[:2])]
    return not bad, f"неверно: {bad}" if bad else "все строки верны"


def chk_imports(root, ans, facts):
    rows = report_rows(root)
    if rows is None:
        return False, "нет report.md"
    bad = [n for n, t in TOOLS_PY.items() if py_stats(t)[2] not in rows.get(n, [])[2:]]
    return not bad, f"неверно импорты: {bad}" if bad else "колонка импортов верна"


TASKS = [
    ("search", ["Найди все файлы проекта, где упоминается порт 8080. Перечисли путь и номер строки."], [chk_search]),
    ("env", ["Прочитай docs/notes.md и перечисли все переменные окружения, которые там описаны, с назначением каждой."], [chk_env]),
    ("bugfix", ["Тесты в tests/test_pricing.py падают. Найди причину, исправь код в src (тест не трогай) и убедись, "
                "что тесты проходят: python -m unittest tests.test_pricing"], [chk_bugfix]),
    ("port", ["Замени порт 8080 на 9090 во всех файлах проекта, кроме папки docs и README.md. Потом проверь, что "
              "в этих файлах 8080 не осталось."], [chk_port]),
    ("git", ["По истории git найди коммит, в котором появилась функция parse_date. Назови его короткий хеш и сообщение."],
     [chk_git]),
    ("report", ["Для каждого .py файла в папке tools посчитай число строк и число функций (строки, начинающиеся с def). "
                "Запиши отчёт report.md с таблицей: файл | строки | функции. Числа получи командами, а не на глаз.",
                "Добавь в report.md колонку «импорты»: число строк, начинающихся с import или from."],
     [chk_report, chk_imports]),
]


# ---------------------------------------------------------------- ресурсы
class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop, self.min_avail, self.max_vram, self.max_gpu = False, 1e9, 0, 0

    def run(self):
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(f"f{i}", ctypes.c_ulonglong) for i in range(7)]
        while not self.stop:
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            self.min_avail = min(self.min_avail, m.f1 / 2**30)
            try:
                o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10).stdout.split(",")
                self.max_vram = max(self.max_vram, int(o[0]) / 1024); self.max_gpu = max(self.max_gpu, int(o[1]))
            except Exception:
                pass
            time.sleep(3)


# ---------------------------------------------------------------- агентный цикл
def post(path, body, timeout=1800):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def strata_last():
    try:
        with urllib.request.urlopen(URL + "/metrics", timeout=10) as r:
            q = json.load(r)["requests"][0]
        return {"prompt_n": q.get("prompt_tokens"), "cached": q.get("reused"), "prompt_ms": q.get("prompt_ms"),
                "gen_n": q.get("output_tokens"), "gen_ms": q.get("decode_ms")}
    except Exception:
        return {}


def timings(resp, engine):
    if engine == "strata":
        return strata_last()
    t = resp.get("timings") or {}
    return {"prompt_n": (t.get("prompt_n") or 0) + (t.get("cache_n") or 0), "cached": t.get("cache_n"),
            "prompt_ms": t.get("prompt_ms"), "gen_n": t.get("predicted_n"), "gen_ms": t.get("predicted_ms")}


def run_turn(messages, tools, engine, deadline, log):
    """Один ход пользователя: шаги модели с инструментами до текстового ответа. Возвращает ответ."""
    for rnd in range(MAX_ROUNDS):
        if time.time() > deadline:
            log["timeout"] = True
            return ""
        body = {"model": "inkling", "messages": messages, "tools": tools, "max_tokens": MAX_TOKENS, **SAMPLING}
        t0 = time.time()
        try:
            resp = post("/v1/chat/completions", body, timeout=max(60, deadline - time.time()))
        except Exception as e:
            log["errors"].append(f"{type(e).__name__}: {e}"[:200])
            return ""
        wall = time.time() - t0
        ch = resp["choices"][0]
        msg, fin = ch.get("message") or {}, ch.get("finish_reason")
        st = {"wall": round(wall, 2), "finish": fin, **timings(resp, engine),
              "think_chars": len(msg.get("reasoning_content") or ""), "calls": len(msg.get("tool_calls") or [])}
        log["rounds"].append(st)
        if fin == "length":
            log["length"] += 1
        calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if not calls:
            messages.append({"role": "assistant", "content": content})
            return content
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"].split("__")[-1]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            key = name + json.dumps(args, sort_keys=True, ensure_ascii=False)
            log["repeats"] += key in log["_seen"]
            log["_seen"].append(key)
            out = M.call(name, args)
            text = out["content"][0]["text"]
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": ("error: " + text) if out["isError"] else text})
    log["max_rounds"] = True
    return ""


def padding(tokens: int) -> list[dict]:
    """Прошлый ход разговора на ~tokens токенов (справочный текст), чтобы задача шла на длинном контексте."""
    if tokens <= 0:
        return []
    src = (Path(__file__).resolve().parents[1] / "docs" / "02-research.md").read_text(encoding="utf-8")
    text = (src * (tokens * 3 // max(1, len(src)) + 1))[: tokens * 3]
    return [{"role": "user", "content": "Справочный материал к проекту, просто прочитай и ответь «Принято».\n\n" + text},
            {"role": "assistant", "content": "Принято."}]


def run_task(name, prompts, checks, engine, work: Path, pad: int = 0):
    root = work / f"{name}"
    facts = make_project(root)
    M.state = lambda: {"cwd": str(root), "bypass": True}
    M.RECENT.clear()
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}}
             for t in M.tool_list()]
    messages = [{"role": "system", "content": SYSTEM.format(cwd=root)}] + padding(pad)
    rec = {"engine": engine, "task": name, "pad": pad, "turns": []}
    t0, deadline = time.time(), time.time() + TASK_TIMEOUT
    for prompt, check in zip(prompts, checks):
        messages.append({"role": "user", "content": prompt})
        log = {"rounds": [], "errors": [], "length": 0, "repeats": 0, "_seen": [], "timeout": False, "max_rounds": False}
        ts = time.time()
        ans = run_turn(messages, tools, engine, deadline, log)
        ok, why = check(root, ans, facts)
        log["calls"] = [k[:160] for k in log.pop("_seen")]
        rec["turns"].append({"ok": ok, "why": why, "secs": round(time.time() - ts, 1), "answer": ans[:400], **log})
    rec["ok"] = all(t["ok"] for t in rec["turns"])
    rec["secs"] = round(time.time() - t0, 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, choices=["llama", "strata"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--out", default="bench/agent")
    ap.add_argument("--pad", type=int, default=0, help="токенов прошлой истории перед задачей (длинный контекст)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    path = out / f"{a.engine}_pad{a.pad // 1000}k_{stamp}.jsonl"
    work = Path(tempfile.gettempdir()) / "inkbench" / a.engine
    want = set(filter(None, a.tasks.split(",")))
    sampler = Sampler(); sampler.start()
    for rep in range(a.reps):
        for name, prompts, checks in TASKS:
            if want and name not in want:
                continue
            rec = run_task(name, prompts, checks, a.engine, work, a.pad)
            rec.update(rep=rep, min_ram_avail_gb=round(sampler.min_avail, 1), max_vram_gb=round(sampler.max_vram, 1))
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            rounds = sum(len(t["rounds"]) for t in rec["turns"])
            print(f"{a.engine} rep{rep} {name}: {'OK ' if rec['ok'] else 'FAIL'} {rec['secs']:6.1f}s rounds={rounds} "
                  f"length={sum(t['length'] for t in rec['turns'])} repeats={sum(t['repeats'] for t in rec['turns'])} "
                  f"| {' / '.join(t['why'] for t in rec['turns'])}", flush=True)
    sampler.stop = True
    print("saved", path)


if __name__ == "__main__":
    main()
