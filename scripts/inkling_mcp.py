"""MCP-сервер инструментов Inkling для веб-чата Strata (stdio, JSON-RPC 2.0, только стандартная библиотека).

Инструменты как у прежнего llama-server --agent: read_file, file_glob_search, grep_search, write_file, edit_file,
exec_shell_command, get_info. Доступ ко всему компьютеру, без песочницы и без ограничения папкой.

Рабочая папка (для относительных путей и команд) и режим подтверждений читаются при каждом вызове из
%LOCALAPPDATA%\\inkling\\agent-state.json: {"cwd": "...", "bypass": false}. Лаунчер меняет его без перезапуска модели.
Без bypass перед write_file, edit_file и exec_shell_command показывается окно Windows «Разрешить?»; чтение и поиск
идут без вопросов.

Запуск (его делает сервер Strata по "mcp_servers" в конфиге):  python -I scripts/inkling_mcp.py
"""
from __future__ import annotations

import ctypes
import datetime
import fnmatch
import json
import os
import platform
import re
import subprocess
import time
import sys
from pathlib import Path

STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "inkling" / "agent-state.json"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
MAX_OUT = 30000
PROTOCOL = "2025-06-18"


def state() -> dict:
    try:
        s = json.loads(STATE.read_text(encoding="utf-8-sig"))
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def workdir() -> Path:
    cwd = state().get("cwd")
    if cwd and Path(cwd).is_dir():
        return Path(cwd)
    return Path.home()


def resolve(p: str | None) -> Path:
    if not p:
        return workdir()
    q = Path(os.path.expandvars(os.path.expanduser(p.strip().strip('"'))))
    return q if q.is_absolute() else workdir() / q


def clip(text: str, limit: int = MAX_OUT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [обрезано: показано {limit} из {len(text)} символов]"


def read_text(p: Path) -> str:
    data = p.read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


# ------------------------------------------------------------------ подтверждение
MB_YESNO, MB_ICONWARNING, MB_DEFBUTTON2, MB_TOPMOST, MB_SETFOREGROUND = 0x4, 0x30, 0x100, 0x40000, 0x10000
IDYES = 6


def confirm(title: str, details: str) -> bool:
    if state().get("bypass") is True:
        return True
    if sys.platform != "win32":
        return False
    text = clip(details, 1500) + "\n\nРазрешить?"
    flags = MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_TOPMOST | MB_SETFOREGROUND
    return ctypes.windll.user32.MessageBoxW(None, text, "Inkling: " + title, flags) == IDYES


class Denied(Exception):
    pass


# ------------------------------------------------------------------ инструменты
def t_read_file(a: dict) -> str:
    p = resolve(a.get("path"))
    lines = read_text(p).splitlines()
    start = max(1, int(a.get("offset") or 1))
    limit = int(a.get("limit") or 2000)
    chunk = lines[start - 1:start - 1 + limit]
    body = "\n".join(f"{i}\t{line}" for i, line in enumerate(chunk, start))
    more = len(lines) - (start - 1 + len(chunk))
    tail = f"\n... [ещё {more} строк, читайте с offset={start + len(chunk)}]" if more > 0 else ""
    return clip(f"{p} ({len(lines)} строк)\n{body}{tail}")


def walk(base: Path, deadline: float):
    """Файлы под base, без служебных папок; останавливается по времени (огромные деревья: модели, сборки)."""
    for root, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        if time.monotonic() > deadline:
            yield None
            return
        for n in names:
            yield Path(root) / n


def glob_match(rel: str, pattern: str) -> bool:
    """fnmatch по пути с /; «**/» означает ноль или больше папок (fnmatch и так пускает * через /)."""
    variants = {pattern, pattern.replace("/**/", "/")}
    if pattern.startswith("**/"):
        variants.add(pattern[3:])
    return any(fnmatch.fnmatch(rel, v) for v in variants)


def t_glob(a: dict) -> str:
    base = resolve(a.get("path"))
    pattern = (a.get("pattern") or "*").replace("\\", "/")
    recursive = "**" in pattern or "/" in pattern.strip("/")
    out, note = [], ""
    if not recursive:                                 # простой шаблон: только эта папка
        for f in sorted(base.glob(pattern)):
            out.append(str(f) + ("\\" if f.is_dir() else ""))
    else:
        for f in walk(base, time.monotonic() + 30):
            if f is None:
                note = "\n... [поиск остановлен через 30 с: папка слишком большая, сузьте path]"
                break
            if glob_match(f.relative_to(base).as_posix(), pattern):
                out.append(str(f))
    if len(out) > 500:
        out, note = out[:500], "\n... [показаны первые 500]"
    return clip(("\n".join(out) if out else f"ничего не найдено: {pattern} в {base}") + note)


def t_grep(a: dict) -> str:
    base = resolve(a.get("path"))
    flags = re.IGNORECASE if a.get("ignore_case") else 0
    rx = re.compile(a["pattern"], flags)
    glob = a.get("glob")
    hits = []
    files = [base] if base.is_file() else walk(base, time.monotonic() + 30)
    for f in files:
        if f is None:
            hits.append("... [поиск остановлен через 30 с: папка слишком большая, сузьте path или glob]")
            break
        if glob and not glob_match(f.name, glob) and not glob_match(f.relative_to(base).as_posix(), glob):
            continue
        try:
            if f.stat().st_size > 5_000_000:
                continue
            text = read_text(f)
        except OSError:
            continue
        if "\x00" in text[:4096]:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{f}:{i}: {line.strip()[:300]}")
                if len(hits) >= 300:
                    return clip("\n".join(hits) + "\n... [показаны первые 300 совпадений]")
    return clip("\n".join(hits) if hits else "совпадений нет")


def t_write(a: dict) -> str:
    p = resolve(a.get("path"))
    content = a.get("content", "")
    action = "перезаписать" if p.exists() else "создать"
    if not confirm("запись файла", f"{action} файл:\n{p}\n\n{len(content)} символов:\n{content[:600]}"):
        raise Denied
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline="")
    return f"записано {len(content)} символов в {p}"


def t_edit(a: dict) -> str:
    p = resolve(a.get("path"))
    old, new = a.get("old_string", ""), a.get("new_string", "")
    text = read_text(p)
    n = text.count(old) if old else 0
    if n == 0:
        return f"error: old_string не найден в {p}"
    if n > 1 and not a.get("replace_all"):
        return f"error: old_string встречается {n} раз в {p}; уточните его или передайте replace_all=true"
    if not confirm("правка файла", f"файл:\n{p}\n\nбыло:\n{old[:500]}\n\nстанет:\n{new[:500]}"):
        raise Denied
    text = text.replace(old, new) if a.get("replace_all") else text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8", newline="")
    return f"заменено {n if a.get('replace_all') else 1} вхождений в {p}"


def t_exec(a: dict) -> str:
    cmd = a["command"]
    cwd = resolve(a.get("cwd"))
    timeout = min(max(int(a.get("timeout_s") or 120), 1), 1800)
    if not confirm("команда", f"папка: {cwd}\n\n{cmd}"):
        raise Denied
    full = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $OutputEncoding=[Text.Encoding]::UTF8; " + cmd
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", full], cwd=str(cwd),
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", errors="replace")
        return clip(f"error: команда не уложилась в {timeout} с\n{out}")
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    res = f"код выхода {r.returncode}\n{out}"
    if err.strip():
        res += f"\n[stderr]\n{err}"
    return clip(res)


def t_info(a: dict) -> str:
    return json.dumps({
        "cwd": str(workdir()), "home": str(Path.home()), "os": platform.platform(),
        "shell": "Windows PowerShell 5.1 (exec_shell_command)", "user": os.environ.get("USERNAME", ""),
        "date": datetime.date.today().isoformat(),
        "confirmations": "выключены (bypass)" if state().get("bypass") is True else "перед записью и командами",
    }, ensure_ascii=False)


S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
TOOLS = [
    ("read_file", t_read_file, "Прочитать текстовый файл (строки с номерами). Относительный путь считается от рабочей папки.",
     {"path": S, "offset": I, "limit": I}, ["path"]),
    ("file_glob_search", t_glob, "Найти файлы по glob-шаблону, например **/*.py. path - папка поиска (по умолчанию рабочая).",
     {"pattern": S, "path": S}, ["pattern"]),
    ("grep_search", t_grep, "Искать регулярное выражение в файлах папки (или в одном файле). glob фильтрует имена файлов.",
     {"pattern": S, "path": S, "glob": S, "ignore_case": B}, ["pattern"]),
    ("write_file", t_write, "Создать или перезаписать файл целиком (UTF-8).", {"path": S, "content": S}, ["path", "content"]),
    ("edit_file", t_edit, "Заменить в файле точный фрагмент old_string на new_string (replace_all - все вхождения).",
     {"path": S, "old_string": S, "new_string": S, "replace_all": B}, ["path", "old_string", "new_string"]),
    ("exec_shell_command", t_exec, "Выполнить команду Windows PowerShell 5.1 на этом компьютере и вернуть вывод. "
     "cwd - папка запуска (по умолчанию рабочая), timeout_s - до 1800 с.", {"command": S, "cwd": S, "timeout_s": I}, ["command"]),
    ("get_info", t_info, "Рабочая папка, ОС, оболочка, дата и режим подтверждений.", {}, []),
]
BY_NAME = {t[0]: t[1] for t in TOOLS}


def tool_list() -> list[dict]:
    return [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": props, "required": req}}
            for n, _, d, props, req in TOOLS]


def result(text: str) -> dict:
    # isError: Strata сама допишет модели «error: » перед текстом, поэтому свой префикс снимаем
    err = text.startswith("error:")
    return {"content": [{"type": "text", "text": text[6:].strip() if err else text}], "isError": err}


def call(name: str, args: dict) -> dict:
    fn = BY_NAME.get(name)
    if fn is None:
        return result(f"error: нет инструмента {name}")
    try:
        return result(fn(args or {}))
    except Denied:
        return result("error: пользователь отклонил это действие")
    except Exception as e:  # ошибка инструмента уходит модели текстом
        return result(f"error: {type(e).__name__}: {e}")


def main() -> None:
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        try:
            msg = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:
            continue                                  # уведомления (initialized, cancelled) ответа не ждут
        if method == "initialize":
            ver = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
            result = {"protocolVersion": ver, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "inkling-tools", "version": "1.0"}}
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            p = msg.get("params") or {}
            result = call(p.get("name", ""), p.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
            out.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n"); out.flush()
            continue
        out.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}, ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()


if __name__ == "__main__":
    main()
