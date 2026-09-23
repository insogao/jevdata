# -*- coding: utf-8 -*-
"""Thinking-arm control: same model, enable_thinking=True, greedy decode up to
`--max-tokens` tokens, then answer digit. Quantifies the ceiling that
no-think System-One readout is measured against.

Subset: all items with risk>=1 plus every safe item System-One flagged >=2
(false-positive direction). Reads report/baseline_results.csv for the latter.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nimble_compatible_scorer import (LlamaCppBackend, RISK_SCHEMA,  # noqa: E402
                                      TokenizerAdapter, ensure_cuda_dlls)


def parse_answer(text):
    """Last digit 0-3 in the text after </think> (the answer digit typically ends
    the reply). Returns -2 if thinking never closed (token cap hit), -1 if closed
    but no digit found."""
    if "</think>" not in text:
        return -2
    tail = text.split("</think>")[-1]
    digits = [ch for ch in tail if ch in "0123"]
    return int(digits[-1]) if digits else -1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gguf", default="models/Qwen3.5-9B-Q4_K_M.gguf")
    ap.add_argument("--tokenizer-dir", default="models/qwen35-9b-tokenizer")
    ap.add_argument("--benchmark", default="data/benchmark.jsonl")
    ap.add_argument("--baseline-csv", default="report/baseline_results.csv")
    ap.add_argument("--out", default="report/thinking_results.csv")
    ap.add_argument("--max-tokens", type=int, default=700)
    args = ap.parse_args()

    ensure_cuda_dlls()
    from nimble_compatible_scorer import nimble_digit_prompt

    items = {r["id"]: r for r in (json.loads(l) for l in open(args.benchmark, encoding="utf-8"))}
    flagged = set()
    for r in csv.DictReader(open(args.baseline_csv, encoding="utf-8")):
        if int(r["risk"]) == 0 and int(r["s_pred"]) >= 2:
            flagged.add(r["id"])
    subset = [r for rid, r in sorted(items.items())
              if r["risk"] >= 1 or rid in flagged]
    print(f"thinking subset: {len(subset)} items ({len(flagged)} false-positive safes included)")

    tok = TokenizerAdapter(args.tokenizer_dir)
    backend = LlamaCppBackend(args.gguf, n_ctx=4096)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "risk", "t_pred", "raw_tail", "gen_tokens", "seconds"])
        for i, item in enumerate(subset):
            prompt = nimble_digit_prompt(tok, item["text"])
            # render with thinking enabled via the real chat template
            fields = [{
                "name": "overall_risk",
                "description": RISK_SCHEMA["overall_risk"]["description"],
                "choices": [{"code": v, "value": v, "description": d}
                            for v, d in zip(["0", "1", "2", "3"],
                                            RISK_SCHEMA["overall_risk"]["choice_descriptions"].values())],
            }]
            content = (json.dumps({"context": item["text"], "schema": fields}, ensure_ascii=False)
                       .replace("<", "\\u003c").replace(">", "\\u003e")
                       + "\n\nRequested field: overall_risk")
            messages = [{"role": "system", "content":
                         "Classify the context using the supplied schema. Reason briefly inside "
                         "<think></think>, then output only the chosen value (0-3)."},
                        {"role": "user", "content": content}]
            text = tok.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True, enable_thinking=True)
            ids = tok.encode(text, add_special_tokens=False)
            t0 = time.perf_counter()
            out = backend.llm.create_completion(prompt=ids, max_tokens=args.max_tokens,
                                                temperature=0.0, top_p=1.0)
            seconds = time.perf_counter() - t0
            out_text = out["choices"][0]["text"]
            n_gen = out["usage"]["completion_tokens"]
            pred = parse_answer(out_text)
            w.writerow([item["id"], item["risk"], pred, out_text[-50:].replace("\n", " "),
                        n_gen, round(seconds, 2)])
            f.flush()
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(subset)}", flush=True)
    print("done:", args.out)


if __name__ == "__main__":
    main()
