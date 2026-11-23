"""Проверка длинного контекста: факт («иголка») на заданной глубине в ~N токенах текста, вопрос в конце.
python -I scripts/needle_test.py --url http://127.0.0.1:8080 --tokens 300000 --depth 0.3 [--key KEY] [--model M]"""
import argparse, json, random, time, urllib.request
ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8080"); ap.add_argument("--tokens", type=int, default=300000)
ap.add_argument("--depth", type=float, default=0.3); ap.add_argument("--key", default=""); ap.add_argument("--model", default="inkling")
a = ap.parse_args()
rnd = random.Random(7)
words = ("harbour lamp keeper tower storm rock coast signal beam night ship fog lens island wave stone light "
         "sailor chart tide wind bell cliff lantern route").split()
paras = []
n_par = a.tokens // 60
for i in range(n_par):
    paras.append(" ".join(rnd.choice(words) for _ in range(45)) + ".")
code = "VIOLET-%04d" % rnd.randint(1000, 9999)
paras.insert(int(n_par * a.depth), f"Important: the secret passphrase of the lighthouse keeper is {code}. Remember it.")
prompt = "\n".join(paras) + "\n\nWhat is the secret passphrase of the lighthouse keeper? Answer with the passphrase only."
body = {"model": a.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 64, "temperature": 0,
        "reasoning_effort": "none"}
req = urllib.request.Request(a.url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + a.key} if a.key else {})})
t0 = time.time()
with urllib.request.urlopen(req, timeout=7200) as r:
    d = json.load(r)
dt = time.time() - t0
ans = d["choices"][0]["message"].get("content") or ""
u = d.get("usage", {})
print(json.dumps({"expected": code, "answer": ans.strip()[:80], "found": code in ans, "prompt_tokens": u.get("prompt_tokens"),
                  "seconds": round(dt, 1)}, ensure_ascii=False))
