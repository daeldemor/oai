#!/usr/bin/env python3
"""Перекодирует Q4_K down-эксперты GGUF в Q5_1, чтобы файл принял движок Strata.

Зачем: нативные expert-ядра Strata берут gate/up в Q4_K/Q5_K/Q6_K/Q8_0, а down —
только в Q5_1/Q5_0/Q4_1/Q4_0/Q8_0/Q5_K/Q6_K/IQ4_*. Обычный llama.cpp-квант Q4_K_M
кладёт часть down-экспертов в Q4_K, и движок падает на загрузке:
    "blk.N.experts are Q4_K/Q4_K, which the native expert kernels do not take".

Перекодирование без потерь по смыслу: суб-блок Q4_K (32 веса, w = d*sc*q - dmin*m,
q в 0..15) ложится в блок Q5_1 (32 веса, w = d'*q + m') один в один: d' = d*sc,
m' = -dmin*m, q тот же. Единственная погрешность — округление d' и m' до float16
(<= 2^-12 относительно, на порядки ниже шага квантования). Остальные тензоры и
метаданные копируются байт в байт.

Пример:
    python -I scripts/strata_fix_down.py \
        X:/OAI-models/qwen36-heretic/<имя>-Q4_K_M.gguf \
        X:/OAI-models/qwen36-heretic-strata/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf --verify
"""
import argparse
import mmap
import struct
import sys

import numpy as np

Q4_K, Q5_1 = 12, 7
Q4_K_BLOCK, Q5_1_BLOCK = 144, 24  # байт на 256 и на 32 веса
SCALAR = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
COPY_CHUNK = 64 << 20
VERIFY_BLOCKS = 1 << 16  # суперблоков Q4_K за один шаг сверки


def read_str(buf, pos):
    (n,) = struct.unpack_from("<Q", buf, pos)
    return buf[pos + 8:pos + 8 + n].decode("utf-8"), pos + 8 + n


def skip_value(buf, pos, vtype):
    """Возвращает (значение или None, позиция после значения)."""
    if vtype in SCALAR:
        fmt = "<" + SCALAR[vtype]
        return struct.unpack_from(fmt, buf, pos)[0], pos + struct.calcsize(fmt)
    if vtype == 8:
        return read_str(buf, pos)
    if vtype == 9:
        etype, count = struct.unpack_from("<IQ", buf, pos)
        pos += 12
        if etype in SCALAR:
            return None, pos + count * struct.calcsize("<" + SCALAR[etype])
        for _ in range(count):
            _, pos = skip_value(buf, pos, etype)
        return None, pos
    raise ValueError(f"неизвестный тип метаданных GGUF: {vtype}")


def parse(buf):
    """Разбирает заголовок: (конец KV-секции, alignment, тензоры, начало данных)."""
    if buf[:4] != b"GGUF":
        raise ValueError("не GGUF-файл")
    version, n_tensors, n_kv = struct.unpack_from("<IQQ", buf, 4)
    if version not in (2, 3):
        raise ValueError(f"GGUF версии {version} не поддерживается")
    pos, alignment = 24, 32
    for _ in range(n_kv):
        key, pos = read_str(buf, pos)
        (vtype,) = struct.unpack_from("<I", buf, pos)
        value, pos = skip_value(buf, pos + 4, vtype)
        if key == "general.alignment":
            alignment = int(value)
    kv_end = pos
    tensors = []
    for _ in range(n_tensors):
        name, pos = read_str(buf, pos)
        (n_dims,) = struct.unpack_from("<I", buf, pos)
        dims = struct.unpack_from(f"<{n_dims}Q", buf, pos + 4)
        ttype, offset = struct.unpack_from("<IQ", buf, pos + 4 + 8 * n_dims)
        pos += 4 + 8 * n_dims + 12
        tensors.append({"name": name, "dims": dims, "type": ttype, "offset": offset})
    data_start = -(-pos // alignment) * alignment
    # размер тензора (с выравнивающим хвостом) — расстояние до следующего по смещению
    order = sorted(tensors, key=lambda t: t["offset"])
    for cur, nxt in zip(order, order[1:]):
        cur["span"] = nxt["offset"] - cur["offset"]
    order[-1]["span"] = len(buf) - data_start - order[-1]["offset"]
    return kv_end, alignment, tensors, data_start


def q4k_parts(raw):
    """Q4_K -> (шкалы [nb,8], минимумы [nb,8], 4-битные коды [nb,8,32])."""
    blocks = np.frombuffer(raw, dtype=np.uint8).reshape(-1, Q4_K_BLOCK)
    d = blocks[:, 0:2].copy().view(np.float16).astype(np.float32)      # [nb,1]
    dmin = blocks[:, 2:4].copy().view(np.float16).astype(np.float32)
    s = blocks[:, 4:16]
    sc = np.empty((len(blocks), 8), dtype=np.uint8)
    mn = np.empty((len(blocks), 8), dtype=np.uint8)
    sc[:, :4] = s[:, 0:4] & 63
    mn[:, :4] = s[:, 4:8] & 63
    sc[:, 4:] = (s[:, 8:12] & 0x0F) | ((s[:, 0:4] >> 6) << 4)
    mn[:, 4:] = (s[:, 8:12] >> 4) | ((s[:, 4:8] >> 6) << 4)
    qs = blocks[:, 16:].reshape(-1, 4, 32)
    q = np.empty((len(blocks), 8, 32), dtype=np.uint8)
    q[:, 0::2] = qs & 0x0F   # младшие нибблы — чётный суб-блок пары
    q[:, 1::2] = qs >> 4     # старшие — нечётный
    return d * sc, dmin * mn, q


def q4k_to_q51(raw):
    scale, minimum, q = q4k_parts(raw)
    out = np.zeros((scale.shape[0], 8, Q5_1_BLOCK), dtype=np.uint8)
    out[:, :, 0:2] = scale.astype(np.float16)[..., None].view(np.uint8)
    out[:, :, 2:4] = (-minimum).astype(np.float16)[..., None].view(np.uint8)
    # qh (пятый бит) остаётся нулём: коды 0..15
    out[:, :, 8:24] = q[:, :, :16] | (q[:, :, 16:] << 4)
    return out.tobytes()


def q4k_dequant(raw):
    scale, minimum, q = q4k_parts(raw)
    return (scale[..., None] * q - minimum[..., None]).reshape(-1)


def q51_dequant(raw):
    blocks = np.frombuffer(raw, dtype=np.uint8).reshape(-1, Q5_1_BLOCK)
    d = blocks[:, 0:2].copy().view(np.float16).astype(np.float32)
    m = blocks[:, 2:4].copy().view(np.float16).astype(np.float32)
    qh = blocks[:, 4:8].copy().view(np.uint32)
    qs = blocks[:, 8:24]
    j = np.arange(16, dtype=np.uint32)
    lo = (qs & 0x0F) | (((qh >> j) & 1) << 4).astype(np.uint8)
    hi = (qs >> 4) | (((qh >> (j + 16)) & 1) << 4).astype(np.uint8)
    return (np.concatenate([lo, hi], axis=1) * d + m).reshape(-1)


def open_gguf(path):
    """(файл, разобранный заголовок). mmap только на разбор заголовка: данные читаем обычным read."""
    f = open(path, "rb")
    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as buf:
        parsed = parse(buf)
        header = buf[:parsed[0]]
    return f, header, parsed


def read_at(f, pos, n):
    f.seek(pos)
    return f.read(n)


def is_target(t):
    return t["type"] == Q4_K and "ffn_down_exps" in t["name"]


def n_weights(t):
    n = 1
    for dim in t["dims"]:
        n *= dim
    return n


def convert(src_path, dst_path):
    src, header, (_, alignment, tensors, data_start) = open_gguf(src_path)
    targets = [t for t in tensors if is_target(t)]
    if not targets:
        print("Q4_K down-экспертов нет — файл уже подходит, ничего не делаю.")
        return False

    # новые смещения: тензоры в исходном порядке, каждый с выравниванием
    new_offset, plan = 0, []
    for t in sorted(tensors, key=lambda t: t["offset"]):
        if is_target(t):
            n = n_weights(t)
            if n % 256 or n // 256 * Q4_K_BLOCK > t["span"]:
                raise ValueError(f"{t['name']}: размер не сходится с Q4_K")
            size = n // 32 * Q5_1_BLOCK
        else:
            size = t["span"]
        padded = -(-size // alignment) * alignment
        plan.append((t, new_offset, size, padded))
        t["new_offset"], t["new_type"] = new_offset, Q5_1 if is_target(t) else t["type"]
        new_offset += padded

    with open(dst_path, "wb") as out:
        out.write(header)
        for t in tensors:  # порядок записей в таблице тензоров сохраняется
            name = t["name"].encode("utf-8")
            out.write(struct.pack("<Q", len(name)) + name)
            out.write(struct.pack(f"<I{len(t['dims'])}Q", len(t["dims"]), *t["dims"]))
            out.write(struct.pack("<IQ", t["new_type"], t["new_offset"]))
        out.write(b"\0" * (-out.tell() % alignment))
        new_data_start = out.tell()
        for t, offset, size, padded in plan:
            assert out.tell() == new_data_start + offset
            begin = data_start + t["offset"]
            if is_target(t):
                out.write(q4k_to_q51(read_at(src, begin, n_weights(t) // 256 * Q4_K_BLOCK)))
                print(f"  {t['name']}: Q4_K -> Q5_1")
            else:
                for pos in range(begin, begin + size, COPY_CHUNK):
                    out.write(read_at(src, pos, min(COPY_CHUNK, begin + size - pos)))
            out.write(b"\0" * (padded - size))
    src.close()
    print(f"Перекодировано тензоров: {len(targets)}. Записано: {dst_path}")
    return True


def verify(src_path, dst_path):
    a, head_a, (_, _, ta, start_a) = open_gguf(src_path)
    b, head_b, (_, _, tb, start_b) = open_gguf(dst_path)
    ok = head_a == head_b and [t["name"] for t in ta] == [t["name"] for t in tb]
    worst = 0.0
    for x, y in zip(ta, tb):
        pa, pb = start_a + x["offset"], start_b + y["offset"]
        if is_target(x):
            ok &= y["type"] == Q5_1 and x["dims"] == y["dims"]
            n_blocks = n_weights(x) // 256
            for blk in range(0, n_blocks, VERIFY_BLOCKS):  # кусками, чтобы не держать float32 всего тензора
                cnt = min(VERIFY_BLOCKS, n_blocks - blk)
                ref = q4k_dequant(read_at(a, pa + blk * Q4_K_BLOCK, cnt * Q4_K_BLOCK))
                got = q51_dequant(read_at(b, pb + blk * 8 * Q5_1_BLOCK, cnt * 8 * Q5_1_BLOCK))
                worst = max(worst, float(np.abs(ref - got).max()) / (float(np.abs(ref).max()) or 1.0))
        else:
            ok &= x["type"] == y["type"] and x["dims"] == y["dims"] and x["span"] <= y["span"]
            for off in range(0, x["span"], COPY_CHUNK):
                n = min(COPY_CHUNK, x["span"] - off)
                if read_at(a, pa + off, n) != read_at(b, pb + off, n):
                    ok = False
                    print(f"  РАСХОЖДЕНИЕ: {x['name']}")
                    break
    print(f"Проверка: {'OK' if ok else 'ОШИБКА'}; макс. отклонение перекодированных весов "
          f"= {worst:.2e} от максимального веса в блоке сверки")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Q4_K down-эксперты GGUF -> Q5_1 (для Strata)")
    ap.add_argument("src", help="исходный GGUF (например, Q4_K_M)")
    ap.add_argument("dst", help="куда записать результат")
    ap.add_argument("--verify", action="store_true",
                    help="после записи сверить результат с исходником (второй полный проход чтения)")
    args = ap.parse_args()
    if convert(args.src, args.dst) and args.verify and not verify(args.src, args.dst):
        sys.exit(1)


if __name__ == "__main__":
    main()
