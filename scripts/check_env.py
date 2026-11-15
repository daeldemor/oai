#!/usr/bin/env python3
"""Проверка окружения для локальной аблитерации и инференса."""
import os
import platform
import shutil
import subprocess
import sys

OK, WARN, FAIL = "[OK]", "[!!]", "[--]"


def check(name, fn):
    try:
        status, msg = fn()
    except Exception as e:  # noqa: BLE001
        status, msg = FAIL, str(e)
    print(f"{status} {name}: {msg}")
    return status != FAIL


def gpu():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version",
         "--format=csv,noheader"],
        capture_output=True, text=True, check=True).stdout.strip()
    name, total, free, drv = [p.strip() for p in out.split(",")]
    free_mb = int(free.split()[0])
    status = OK if free_mb > 12_000 else WARN
    return status, f"{name}, VRAM {total} (свободно {free}), драйвер {drv}"


def cuda_torch():
    import torch
    if not torch.cuda.is_available():
        return FAIL, "torch установлен, но CUDA недоступна (нужна cu-сборка torch)"
    return OK, f"torch {torch.__version__}, CUDA {torch.version.cuda}, " \
               f"GPU: {torch.cuda.get_device_name(0)}"


def ram():
    import ctypes

    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPage", ctypes.c_ulonglong), ("ullAvailPage", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExt", ctypes.c_ulonglong)]

    stat = MEMSTAT()
    stat.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_gb = stat.ullTotalPhys / 2**30
    status = OK if total_gb >= 30 else WARN
    return status, f"{total_gb:.0f} ГБ (32 ГБ железа отображается как ~31; для аблитерации 14B нужно >=30)"


def disk():
    usage = shutil.disk_usage("G:\\")
    free_gb = usage.free / 2**30
    status = OK if free_gb >= 100 else WARN
    return status, f"G: свободно {free_gb:.0f} ГБ (bf16-загрузки до ~30 ГБ на модель)"


def tools():
    msgs = []
    for t in ("git", "ffmpeg"):
        msgs.append(f"{t}: {'есть' if shutil.which(t) else 'нет'}")
    return OK, "; ".join(msgs)


def lmstudio_models():
    root = os.path.expanduser(r"~/.lmstudio/models")
    found = []
    for dirpath, _dirs, files in os.walk(root):
        found += [os.path.join(dirpath, f) for f in files if f.endswith(".gguf")]
    if not found:
        return WARN, "GGUF-модели в LM Studio не найдены"
    listing = "; ".join(os.path.basename(f) for f in found)
    return OK, f"найдено {len(found)} GGUF: {listing}"


def main():
    print(f"Python {sys.version.split()[0]} на {platform.system()} {platform.release()}\n")
    results = [
        check("GPU (nvidia-smi)", gpu),
        check("PyTorch + CUDA", cuda_torch),
        check("Оперативная память", ram),
        check("Диск G:", disk),
        check("Утилиты", tools),
        check("LM Studio модели", lmstudio_models),
    ]
    print()
    if all(results):
        print("Окружение готово к работе.")
    else:
        print("Есть проблемы — см. пункты [--] выше.")
        sys.exit(1)


if __name__ == "__main__":
    main()
