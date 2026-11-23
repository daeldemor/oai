"""Замер prefill/decode через OpenAI-совместимый /v1/chat/completions со стримингом.
python -I scripts/bench_openai.py --url http://127.0.0.1:8080 --fill 0 --gen 256 [--key KEY] [--model M]
--fill N: дописать в промпт ~N токенов текста (для глубины контекста)."""
import argparse, json, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8080")
ap.add_argument("--fill", type=int, default=0)
ap.add_argument("--gen", type=int, default=256)
ap.add_argument("--key", default="")
ap.add_argument("--model", default="inkling")
ap.add_argument("--salt", default="", help="префикс, чтобы не попасть в кэш промпта")
ap.add_argument("--prompt", default="Напиши на Python функцию быстрой сортировки с комментариями и тестами.")
a = ap.parse_args()

filler = ""
if a.fill:
    para = ("The history of the lighthouse begins with simple fires on hilltops. Sailors relied on them to avoid "
            "rocks and to find harbours at night; over centuries the towers grew taller and the lamps brighter. ")
    filler = para * max(1, a.fill // 40) + "\n\nSummarize the text above in one sentence, then: "
msgs = [{"role": "user", "content": a.salt + filler + a.prompt}]
body = {"model": a.model, "messages": msgs, "max_tokens": a.gen, "temperature": 0, "stream": True,
        "stream_options": {"include_usage": True}, "reasoning_effort": "none"}
req = urllib.request.Request(a.url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + a.key} if a.key else {})})
t0 = time.time(); t_first = None; n = 0; usage = None; text = []
with urllib.request.urlopen(req, timeout=7200) as r:
    for line in r:
        line = line.decode("utf-8", "replace").strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        d = json.loads(line[5:])
        if d.get("usage"):
            usage = d["usage"]
        for ch in d.get("choices", []):
            delta = ch.get("delta", {})
            piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
            if piece:
                if t_first is None:
                    t_first = time.time()
                n += 1; text.append(piece)
t1 = time.time()
pt = usage.get("prompt_tokens") if usage else None
ct = usage.get("completion_tokens") if usage else n
ttft = (t_first or t1) - t0
dec = (ct - 1) / (t1 - t_first) if t_first and ct and ct > 1 and t1 > t_first else 0
print(json.dumps({"prompt_tokens": pt, "completion_tokens": ct, "ttft_s": round(ttft, 2),
                  "prefill_tok_s": round(pt / ttft, 1) if pt else None, "decode_tok_s": round(dec, 1)}, ensure_ascii=False))
print("".join(text)[:300].replace("\n", " "))
