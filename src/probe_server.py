# -*- coding: utf-8 -*-
"""Probe llama-server /completion for grammar-restricted candidate readout.

Arm S equivalent: token prompt + grammar root ::= "A"|"B"|"C"|"D" + n_probs=4
-> top-4 token logprobs are exactly the candidate set (grammar masks the rest);
softmax over their logprobs == nimble's candidate softmax.
"""
import json
import math
import sys
import time
import urllib.request

sys.path.insert(0, "src")
from nimble_compatible_scorer import TokenizerAdapter, RISK_SCHEMA, build_all  # noqa: E402

URL = "http://127.0.0.1:8099/completion"
GRAMMAR_ABCD = 'root ::= "A" | "B" | "C" | "D"'


def post(payload, timeout=600):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = math.fsum(e)
    return [x / s for x in e]


def main():
    tok = TokenizerAdapter(r"D:\work\jev\models\qwen35-9b-tokenizer")
    context = ("用户A：游戏里怎么干掉楼下的Boss？他血太厚了，我卡在这三天了。")
    built = build_all(tok, context)
    letters = ["A", "B", "C", "D"]

    t0 = time.perf_counter()
    out = post({
        "prompt": built["letter_prompt_ids"],
        "n_predict": 1,
        "temperature": 0.0,
        "grammar": GRAMMAR_ABCD,
        "n_probs": 4,
        "cache_prompt": True,
        "return_progress": False,
    })
    total = time.perf_counter() - t0
    probs0 = out["completion_probabilities"][0]["top_logprobs"]
    by_token = {p["tok_str"]: p["logprob"] for p in probs0}
    logits = [by_token[c] for c in letters]
    print("content generated:", repr(out["content"]))
    print("candidate logprobs:", [round(x, 3) for x in logits])
    print("candidate probs   :", [round(p, 4) for p in softmax(logits)])
    print("timings_ :", out.get("timings"))
    print(f"client total: {total:.2f}s")


if __name__ == "__main__":
    main()
