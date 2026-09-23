# -*- coding: utf-8 -*-
"""Build and validate the moderation benchmark JSONL from benchmark_data.ITEMS.

Checks:
  - risk in {0,1,2,3}; dims keys known and boolean
  - contrastive pairs: exactly 2 members, same category prefix tag, risk actually flips
  - no duplicate texts; category tags known
Outputs data/benchmark.jsonl with fields:
  {id, category, pair_id, text, risk, dims}
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_data import ITEMS, CATEGORIES  # noqa: E402

KNOWN_DIMS = {"violence", "sexual", "self_harm", "fraud", "illegal", "actionable", "fictional"}


def main():
    errors, seen_text = [], set()
    rows = []
    for i, (cat, pair, text, risk, dims) in enumerate(ITEMS):
        if cat not in CATEGORIES:
            errors.append(f"item {i}: unknown category {cat}")
        if risk not in (0, 1, 2, 3):
            errors.append(f"item {i}: bad risk {risk}")
        if not text.strip():
            errors.append(f"item {i}: empty text")
        if text in seen_text:
            errors.append(f"item {i}: duplicate text: {text[:40]}")
        seen_text.add(text)
        unknown = set(dims) - KNOWN_DIMS
        if unknown:
            errors.append(f"item {i}: unknown dims {unknown}")
        if any(not isinstance(v, bool) for v in dims.values()):
            errors.append(f"item {i}: dims values must be bool")
        rows.append({"id": f"mod-{i:04d}", "category": cat, "pair_id": pair,
                     "text": text, "risk": risk, "dims": dims})

    # pair validation
    by_pair = {}
    for r in rows:
        if r["pair_id"]:
            by_pair.setdefault(r["pair_id"], []).append(r)
    for pid, members in sorted(by_pair.items()):
        if len(members) != 2:
            errors.append(f"pair {pid}: has {len(members)} members, expected 2")
        elif members[0]["risk"] == members[1]["risk"]:
            errors.append(f"pair {pid}: labels do not flip ({members[0]['risk']}=={members[1]['risk']})")

    dist = Counter(r["risk"] for r in rows)
    print(f"items: {len(rows)}  pairs: {len(by_pair)}")
    print("risk distribution:", dict(sorted(dist.items())))
    print("category distribution:", dict(Counter(r['category'] for r in rows)))
    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    out = Path(__file__).resolve().parents[1] / "data" / "benchmark.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
