# -*- coding: utf-8 -*-
"""Domain control: score Nimble's OWN eval.jsonl items via the llama-server.

Confirms the merged Bespoke-Nimble-9B Q4 improves on the base model in its
training domain (README: 90.1% adapter vs 66.4% base agreement on their labels).
If merged <= base here, the merge is broken; if merged >> base, the moderation
regression we measured is domain shift, not a broken artifact.
"""
import argparse
import json
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "repos" / "nimble"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nimble.scoring.parallel_schema import prepare_prompts  # noqa: E402
from nimble_compatible_scorer import TokenizerAdapter  # noqa: E402
from llama_server_backend import LlamaServerBackend  # noqa: E402


def adapt_input(row):
    """Mirror nimble/evaluation/evaluate_pilot.py adapt_input()."""
    q = row["input"]["questions"]["decision"]
    if q["type"] == "noul":
        schema = {"decision": {"type": "boolean", "description": q["instructions"]}}
        target = bool(row["reference"]["target"])
    elif q["type"] == "choice":
        schema = {"decision": {"type": "enum", "description": q["instructions"],
                               "choices": list(q["criteria"])}}
        target = row["reference"]["target"]
    else:  # score
        n = len(q["criteria"])
        schema = {"decision": {"type": "enum", "description": q["instructions"],
                               "choices": [str(i) for i in range(n)]}}
        target = str(row["reference"]["target"])
    return row["input"]["state"], schema, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--label", required=True, help="e.g. nimble-q4 or base-q4")
    ap.add_argument("--server-url", default="http://127.0.0.1:8099")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-input-tokens", type=int, default=7000)
    args = ap.parse_args()

    tok = TokenizerAdapter(r"D:\work\jev\models\qwen35-9b-tokenizer")
    backend = LlamaServerBackend(args.server_url)
    rows = []
    with open(r"D:\work\jev\repos\nimble\data\eval.jsonl", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))

    ok, total = 0, 0
    alphabet = string.ascii_uppercase
    for row in rows:
        if total >= args.n:
            break
        state, schema, target = adapt_input(row)
        try:
            prepared = prepare_prompts(tok, state, schema,
                                       max_input_tokens=args.max_input_tokens)
        except ValueError:
            continue  # too long for ctx
        letters = alphabet[:len(prepared.choices[0])]
        grammar = 'root ::= ' + " | ".join(f'"{c}"' for c in letters)
        probs, _ = backend.candidate_probs(prepared.full_ids[0], grammar, letters,
                                           args.temperature)
        pred = probs.index(max(probs))
        try:
            gold = prepared.choices[0].index(target)
        except ValueError:
            continue
        ok += pred == gold
        total += 1
        if total % 10 == 0:
            print(f"  {total}: acc={ok/total:.3f}", flush=True)
    print(f"[{args.label}] domain-control accuracy: {ok}/{total} = {ok/max(total,1):.3f}")


if __name__ == "__main__":
    main()
