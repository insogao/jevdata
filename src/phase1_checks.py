# -*- coding: utf-8 -*-
"""Phase 1 correctness checks for the nimble-compatible candidate path.

Checks (from the experiment plan):
  1. dataset loads (build_benchmark passed separately)
  2. schema compiles (validate_schema)
  3. candidate token A/B/C/D mapping is correct (decode == letters)
  4. scorer returns finite logits
  5. softmax probabilities sum to 1
  6. option-order permutation: argmax follows the VALUE, not the position
  7. boolean A=false / B=true ordering fixed
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nimble_compatible_scorer import (LlamaCppBackend, RISK_SCHEMA,  # noqa: E402
                                      TokenizerAdapter, ensure_cuda_dlls)
from nimble.scoring.parallel_schema import choices_for, prepare_prompts  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def softmax(xs):
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = math.fsum(exps)
    return [e / s for e in exps]


def main():
    ensure_cuda_dlls()
    tok = TokenizerAdapter("models/qwen35-9b-tokenizer")
    backend = LlamaCppBackend("models/Qwen3.5-9B-Q4_K_M.gguf", n_ctx=4096)

    context = "联机时被人用挂恶心了，举报通道在哪？"

    # 2. schema compiles
    try:
        prepared = prepare_prompts(tok, context, RISK_SCHEMA, 4096)
        check("schema_compiles", True)
    except Exception as e:  # noqa: BLE001
        check("schema_compiles", False, str(e))
        return

    # 3. candidate mapping: decoded single tokens == A/B/C/D
    prompt = prepared.full_ids[0]
    letters = prepared.candidate_ids[0]
    decoded = [tok.tok.decode([t]) for t in letters]
    check("candidate_mapping_ABCD", decoded == ["A", "B", "C", "D"], str(decoded))

    # 7. boolean ordering: choices_for gives [False, True] -> A=false, B=true
    bool_field = {"verdict": {"type": "boolean", "description": "test"}}
    check("boolean_order_false_true", choices_for(bool_field["verdict"]) == [False, True])
    bprep = prepare_prompts(tok, context,
                            {"verdict": {"type": "boolean", "description": "Is this safe?"}},
                            4096)
    bdecoded = [tok.tok.decode([t]) for t in bprep.candidate_ids[0]]
    check("boolean_candidate_ids_AB", bdecoded == ["A", "B"], str(bdecoded))

    # 4. scorer returns finite logits; 5. softmax sums to 1
    logits, prefill = backend.candidate_logits(prompt, letters)
    check("logits_finite", all(math.isfinite(x) for x in logits), str([round(x, 2) for x in logits]))
    probs = softmax(logits)
    check("softmax_sums_to_1", abs(math.fsum(probs) - 1.0) < 1e-9, f"sum={math.fsum(probs):.12f}")

    # 6. permutation consistency: reorder choices, argmax must follow the value
    base_pred = max(range(4), key=lambda i: logits[i])
    perm = [2, 3, 0, 1]  # new_choices[i] = old_choices[perm[i]]
    schema_perm = {
        "overall_risk": {
            "type": "enum",
            "description": RISK_SCHEMA["overall_risk"]["description"],
            "choices": [RISK_SCHEMA["overall_risk"]["choices"][j] for j in perm],
            "choice_descriptions": RISK_SCHEMA["overall_risk"]["choice_descriptions"],
        }
    }
    prep2 = prepare_prompts(tok, context, schema_perm, 4096)
    logits2, _ = backend.candidate_logits(prep2.full_ids[0], prep2.candidate_ids[0])
    pred2 = max(range(4), key=lambda i: logits2[i])
    # value predicted in both settings must match
    value_a = prepared.choices[0][base_pred]
    value_b = prep2.choices[0][pred2]
    check("permutation_consistency", value_a == value_b,
          f"base argmax={base_pred}({value_a}) perm argmax={pred2}({value_b})")
    # the model's text is identical, so logits for the same option should be close.
    # Absolute logits DO shift a little with option order (attention sees the whole
    # schema) — nimble shuffles per-record in training for exactly this reason —
    # so only bound the shift loosely; decisions are covered by the check above.
    same_value_logits = [(logits[base_pred], logits2[pred2])]
    check("permutation_logit_stable",
          abs(same_value_logits[0][0] - same_value_logits[0][1]) < 1.5,
          f"{same_value_logits[0][0]:.3f} vs {same_value_logits[0][1]:.3f}")

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
