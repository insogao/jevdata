# -*- coding: utf-8 -*-
"""Run the moderation baseline on local Qwen3.5-9B GGUF.

Arms:
  system_one : nimble letter prompt, candidate-logit softmax over {A,B,C,D} (no generation)
  generative : digit prompt, unconstrained greedy generation (no thinking), parse 0-3
  digit_ctrl : digit prompt, candidate-logit softmax over digit tokens (free control)

Metrics per arm: accuracy, macro-F1, per-class recall/precision, risk>=2 FN,
risk==3 FN, NLL, Brier, ECE (logit arms only), latency stats, pair accuracy.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def ensure_cuda_dlls():
    import glob
    import os
    root = Path(__file__).resolve().parents[1] / ".venv" / "Lib" / "site-packages"
    for d in glob.glob(str(root / "nvidia" / "*" / "bin")) + glob.glob(str(root / "nvidia" / "*" / "lib")):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def load_items(path):
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            items.append(json.loads(line))
    return items


def softmax(xs, temperature=1.0):
    m = max(xs)
    exps = [math.exp((x - m) / temperature) for x in xs]
    s = math.fsum(exps)
    return [e / s for e in exps]


def fit_temperature(logits_list, labels, lo=0.5, hi=10.0, iters=60):
    """Golden-section search for the T minimizing NLL (oracle fit; note in report)."""
    def nll(t):
        total = 0.0
        for xs, y in zip(logits_list, labels):
            p = softmax(xs, t)[y]
            total -= math.log(max(p, 1e-12))
        return total / len(labels)

    for _ in range(iters):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        if nll(m1) < nll(m2):
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2, nll((lo + hi) / 2)


def ece(probs_list, labels, bins=10):
    """Expected calibration error over max-prob confidence."""
    total, n = 0.0, len(probs_list)
    conf_pairs = [(max(p), 1.0 if max(range(len(p)), key=lambda i: p[i]) == y else 0.0)
                  for p, y in zip(probs_list, labels)]
    for b in range(bins):
        lo_b, hi_b = b / bins, (b + 1) / bins
        bucket = [(c, a) for c, a in conf_pairs
                  if (b == 0 and lo_b <= c <= hi_b) or (b > 0 and lo_b < c <= hi_b)]
        if bucket:
            conf = sum(c for c, _ in bucket) / len(bucket)
            acc = sum(a for _, a in bucket) / len(bucket)
            total += len(bucket) / n * abs(conf - acc)
    return total


def brier_multiclass(probs_list, labels):
    total = 0.0
    for p, y in zip(probs_list, labels):
        total += sum((pi - (1 if i == y else 0)) ** 2 for i, pi in enumerate(p))
    return total / len(probs_list)


def macro_f1(conf, n_classes=4):
    f1s = []
    for c in range(n_classes):
        tp = conf[c][c]
        fp = sum(conf[r][c] for r in range(n_classes)) - tp
        fn = sum(conf[c]) - tp
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / n_classes


def confusion_and_metrics(preds, golds, probs_list=None, n_classes=4):
    conf = [[0] * n_classes for _ in range(n_classes)]
    for p, g in zip(preds, golds):
        conf[g][p] += 1
    acc = sum(conf[i][i] for i in range(n_classes)) / len(golds)
    recall = [conf[c][c] / sum(conf[c]) if sum(conf[c]) else 0.0 for c in range(n_classes)]
    prec = []
    for c in range(n_classes):
        col = sum(conf[r][c] for r in range(n_classes))
        prec.append(conf[c][c] / col if col else 0.0)
    fn_ge2 = sum(1 for p, g in zip(preds, golds) if g >= 2 and p < 2)
    fn_eq3 = sum(1 for p, g in zip(preds, golds) if g == 3 and p < 3)
    n_ge2 = sum(1 for g in golds if g >= 2)
    n_eq3 = sum(1 for g in golds if g == 3)
    out = {
        "accuracy": acc,
        "macro_f1": macro_f1(conf),
        "recall_per_class": recall,
        "precision_per_class": prec,
        "confusion": conf,
        "fn_rate_risk_ge2": fn_ge2 / n_ge2 if n_ge2 else None,
        "fn_rate_risk_eq3": fn_eq3 / n_eq3 if n_eq3 else None,
        "fn_count_risk_ge2": fn_ge2,
        "fn_count_risk_eq3": fn_eq3,
        "n_risk_ge2": n_ge2,
        "n_risk_eq3": n_eq3,
    }
    if probs_list is not None:
        nll = -sum(math.log(max(probs_list[i][g], 1e-12)) for i, g in enumerate(golds)) / len(golds)
        out["nll"] = nll
        out["brier"] = brier_multiclass(probs_list, golds)
        out["ece"] = ece(probs_list, golds)
    return out


GEN_PARSE_FAIL = -1


def parse_generative(text):
    """Extract 0-3 from generative output; return GEN_PARSE_FAIL if absent."""
    for ch in text.strip():
        if ch in "0123":
            return int(ch)
    return GEN_PARSE_FAIL


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gguf", default="models/Qwen3.5-9B-Q4_K_M.gguf")
    ap.add_argument("--tokenizer-dir", default="models/qwen35-9b-tokenizer")
    ap.add_argument("--benchmark", default="data/benchmark.jsonl")
    ap.add_argument("--out", default="report")
    ap.add_argument("--out-prefix", default="baseline")
    ap.add_argument("--temperature", type=float,
                    help="apply this fitted temperature to candidate softmax (argmax unchanged); "
                         "e.g. 2.179 for the official Bespoke-Nimble-9B checkpoint")
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--server-url", help="use a running llama-server (e.g. http://127.0.0.1:8099) "
                                         "instead of in-process llama-cpp-python; candidate readout "
                                         "via grammar-restricted post-sampling probabilities")
    ap.add_argument("--n-ctx", type=int, default=4096)
    ap.add_argument("--limit", type=int, help="only first N items")
    ap.add_argument("--skip-generative", action="store_true")
    args = ap.parse_args()

    ensure_cuda_dlls()
    from nimble_compatible_scorer import (LlamaCppBackend, TokenizerAdapter,
                                          build_all, nimble_digit_prompt)
    from benchmark_data import ITEMS  # noqa: F401  (benchmark jsonl is built from it)

    items = load_items(args.benchmark)
    if args.limit:
        items = items[:args.limit]
    print(f"items: {len(items)}")

    tok = TokenizerAdapter(args.tokenizer_dir)
    T = args.temperature if args.temperature is not None else 1.0
    if args.server_url:
        from llama_server_backend import (LlamaServerBackend, GRAMMAR_ABCD,
                                          GRAMMAR_DIGITS)
        backend = LlamaServerBackend(args.server_url)
    else:
        backend = LlamaCppBackend(args.gguf, n_ctx=args.n_ctx, n_gpu_layers=args.n_gpu_layers)
    from nimble_compatible_scorer import RISK_SCHEMA  # noqa: E402

    rows = []
    t_start = time.perf_counter()
    for i, item in enumerate(items):
        built = build_all(tok, item["text"])
        # --- Arm S: system-one candidate readout (letter prompt) ---
        if args.server_url:
            s_probs, s_prefill = backend.candidate_probs(built["letter_prompt_ids"],
                                                         GRAMMAR_ABCD, "ABCD", T)
            s_pred = max(range(4), key=lambda j: s_probs[j])
            s_logits = None
        else:
            s_logits, s_prefill = backend.candidate_logits(built["letter_prompt_ids"],
                                                           built["letter_ids"])
            s_probs = softmax(s_logits, T) if T else softmax(s_logits)
            s_pred = max(range(4), key=lambda j: s_logits[j])
        row = {
            "id": item["id"], "category": item["category"], "pair_id": item["pair_id"],
            "risk": item["risk"],
            "s_pred": s_pred, "s_logits": s_logits, "s_probs": s_probs,
            "s_prefill_s": round(s_prefill, 4),
        }
        # --- Arm G: generative greedy (digit prompt) ---
        if not args.skip_generative:
            text, g_seconds, usage = backend.generate(built["gen_prompt_ids"], max_tokens=8)
            g_pred = parse_generative(text)
            # --- Arm D: digit-logit control on the same generative prompt ---
            if args.server_url:
                d_probs, d_prefill = backend.candidate_probs(built["gen_prompt_ids"],
                                                             GRAMMAR_DIGITS, "0123", T)
                d_pred = max(range(4), key=lambda j: d_probs[j])
                d_logits = None
            else:
                d_logits, d_prefill = backend.candidate_logits(built["gen_prompt_ids"],
                                                               built["digit_ids"])
                d_probs = softmax(d_logits, T) if T else softmax(d_logits)
                d_pred = max(range(4), key=lambda j: d_logits[j])
            row.update({
                "g_raw": text.strip()[:60], "g_pred": g_pred, "g_seconds": round(g_seconds, 4),
                "d_pred": d_pred, "d_logits": d_logits, "d_probs": d_probs,
                "d_prefill_s": round(d_prefill, 4),
            })
        rows.append(row)
        done = i + 1
        if done % 10 == 0 or done == len(items):
            elapsed = time.perf_counter() - t_start
            print(f"  {done}/{len(items)} elapsed={elapsed:.0f}s", flush=True)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    golds = [r["risk"] for r in rows]

    # ---------- metrics per arm ----------
    summary = {}
    s_probs_list = [[r["s_probs"][j] for j in range(4)] for r in rows]
    summary["system_one"] = confusion_and_metrics([r["s_pred"] for r in rows], golds, s_probs_list)
    summary["system_one"]["latency_p50_s"] = sorted(r["s_prefill_s"] for r in rows)[len(rows) // 2]
    summary["system_one"]["latency_mean_s"] = sum(r["s_prefill_s"] for r in rows) / len(rows)
    if not args.skip_generative:
        summary["generative"] = confusion_and_metrics([r["g_pred"] for r in rows], golds)
        summary["generative"]["parse_fail"] = sum(1 for r in rows if r["g_pred"] == GEN_PARSE_FAIL)
        summary["generative"]["latency_p50_s"] = sorted(r["g_seconds"] for r in rows)[len(rows) // 2]
        summary["generative"]["latency_mean_s"] = sum(r["g_seconds"] for r in rows) / len(rows)
        d_probs_list = [[r["d_probs"][j] for j in range(4)] for r in rows]
        summary["digit_control"] = confusion_and_metrics([r["d_pred"] for r in rows], golds, d_probs_list)
        summary["digit_control"]["latency_p50_s"] = sorted(r["d_prefill_s"] for r in rows)[len(rows) // 2]

    # ---------- calibration (oracle temperature fit, see report caveat) ----------
    if args.temperature or args.server_url:
        summary["temperature_applied"] = T
        summary["temperature_source"] = ("official checkpoint fit (argmax unaffected)"
                                         if args.temperature else "server-side temperature")
    else:
        T_fit, nll_fit = fit_temperature([r["s_logits"] for r in rows], golds)
        cal_probs = [softmax(r["s_logits"], T_fit) for r in rows]
        summary["system_one"]["fitted_temperature"] = T_fit
        summary["system_one"]["nll_at_fitted_T"] = nll_fit
        summary["system_one"]["ece_at_fitted_T"] = ece(cal_probs, golds)
        summary["system_one"]["brier_at_fitted_T"] = brier_multiclass(cal_probs, golds)
        if not args.skip_generative:
            Td, nll_d = fit_temperature([r["d_logits"] for r in rows], golds)
            cal_d = [softmax(r["d_logits"], Td) for r in rows]
            summary["digit_control"]["fitted_temperature"] = Td
            summary["digit_control"]["nll_at_fitted_T"] = nll_d
            summary["digit_control"]["ece_at_fitted_T"] = ece(cal_d, golds)
            summary["digit_control"]["brier_at_fitted_T"] = brier_multiclass(cal_d, golds)

    # ---------- pair accuracy (both members correct) ----------
    by_pair = {}
    for r in rows:
        if r["pair_id"]:
            by_pair.setdefault(r["pair_id"], []).append(r)
    pair_stats = {}
    for arm in ("s_pred", "g_pred", "d_pred"):
        if arm == "g_pred" and args.skip_generative:
            continue
        both = sum(1 for members in by_pair.values()
                   if len(members) == 2 and all(m[arm] == m["risk"] for m in members))
        flipped = sum(1 for members in by_pair.values()
                      if len(members) == 2 and members[0][arm] != members[1][arm])
        pair_stats[arm] = {"pair_both_correct": both, "n_pairs": len(by_pair),
                           "pair_pred_separated": flipped}
    summary["pairs"] = pair_stats

    # ---------- write CSV ----------
    import csv
    csv_path = out_dir / f"{args.out_prefix}_results.csv"
    fields = ["id", "category", "pair_id", "risk",
              "s_pred", "s_probs", "s_prefill_s",
              "g_pred", "g_raw", "g_seconds", "d_pred", "d_probs", "d_prefill_s"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            rr = dict(r)
            rr["s_probs"] = json.dumps([round(p, 4) for p in r["s_probs"]])
            if "d_probs" in rr:
                rr["d_probs"] = json.dumps([round(p, 4) for p in r["d_probs"]])
            w.writerow(rr)

    (out_dir / f"{args.out_prefix}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
