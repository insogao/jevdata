# -*- coding: utf-8 -*-
"""Stage 1B: normalize downloaded public sources -> normalized/<SRC-ID>/seed.jsonl
with deterministic SEED ids, native labels preserved, weak risk labels only.
Stage 1 rule: NO forced exact 0/1/2/3 (plan §0.1)."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "crime_chat_dataset"
RAW = ROOT / "sources" / "raw"
NORM = ROOT / "sources" / "normalized"


def seed_id(source_id, native_key):
    return f"SEED-{source_id}-{hashlib.sha256(native_key.encode()).hexdigest()[:16]}"


def write(source_id, rows):
    out = NORM / source_id
    out.mkdir(parents=True, exist_ok=True)
    with (out / "seed.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{source_id}: {len(rows)} seeds -> {out/'seed.jsonl'}")


def norm_aegis():
    rows = []
    for split in ("train", "validation", "test"):
        data = json.load(open(RAW / "SRC-AEG-001" / f"{split}.json", encoding="utf-8"))
        for r in data:
            ann = r.get("safety_annotation", {})
            cats = ann.get("categories", r.get("categories_violated", []))
            rows.append({
                "seed_id": seed_id("SRC-AEG-001", f"{split}-{r.get('id', r['prompt'][:64])}"),
                "source_id": "SRC-AEG-001", "split": split,
                "native": {"prompt": r.get("prompt"), "response": r.get("response"),
                           "categories": cats},
                "weak": {"risk_binary": "harmful" if cats else "unknown",
                         "category": cats[0] if cats else None},
            })
    write("SRC-AEG-001", rows)


def norm_salad():
    rows = []
    data = json.load(open(RAW / "SRC-SAL-001" / "base_set.json", encoding="utf-8"))
    tax = {}
    for r in data:
        rows.append({
            "seed_id": seed_id("SRC-SAL-001", f"base-{r['qid']}"),
            "source_id": "SRC-SAL-001",
            "native": {"question": r["question"], "source": r.get("source"),
                       "cat1": r.get("1-category"), "cat2": r.get("2-category"),
                       "cat3": r.get("3-category")},
            "weak": {"risk_binary": "harmful", "category": r.get("3-category")},
        })
        if r.get("3-category"):
            tax.setdefault(r.get("1-category"), {}).setdefault(r.get("2-category"), set()).add(r.get("3-category"))
    write("SRC-SAL-001", rows)
    tax_out = {c: {s: sorted(t) for s, t in subs.items()} for c, subs in tax.items()}
    (ROOT / "taxonomy" / "source_taxonomy_SALAD.json").write_text(
        json.dumps(tax_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  SALAD taxonomy: {sum(len(s) for c in tax_out.values() for s in c.values())} leaf categories")


def norm_bosu():
    rows = []
    with open(RAW / "SRC-BSD-001" / "scam-dialogue_all.csv", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f)):
            rows.append({
                "seed_id": seed_id("SRC-BSD-001", f"all-{i}"),
                "source_id": "SRC-BSD-001",
                "native": {"dialogue": r["dialogue"], "type": r.get("type")},
                "weak": {"risk_binary": r.get("label"), "category": r.get("type")},
            })
    write("SRC-BSD-001", rows)


def norm_prosocial():
    rows = []
    cur, cur_id, levels = [], None, []
    path = RAW / "SRC-PSD-001" / "train.json"
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            did = r.get("dialogue_id")
            if did != cur_id and cur:
                rows.append(_psd_seed(cur_id, cur, levels))
                cur, levels = [], []
            cur_id = did
            cur.append(r)
            levels.append(r.get("safety_label"))
    if cur:
        rows.append(_psd_seed(cur_id, cur, levels))
    write("SRC-PSD-001", rows[:60000])


def _psd_seed(did, turns, levels):
    order = ["casual", "possibly_needs_caution", "probably_needs_caution",
             "needs_caution", "needs_intervention"]
    worst = max((order.index(x) for x in levels if x in order), default=-1)
    weak = order[worst] if worst >= 0 else "unknown"
    return {
        "seed_id": seed_id("SRC-PSD-001", f"dialog-{did}"),
        "source_id": "SRC-PSD-001",
        "native": {"turns": [{"speaker": t.get("speaker"), "text": t.get("text")} for t in turns][:40]},
        "weak": {"risk_binary": weak, "category": weak},
    }


def norm_banking(cap=50000):
    rows = []
    with open(RAW / "SRC-BCC-001" / "banking_300k.csv", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader):
            if i >= cap:
                break
            rows.append({
                "seed_id": seed_id("SRC-BCC-001", f"row-{i}"),
                "source_id": "SRC-BCC-001",
                "native": {k: v for k, v in r.items() if k},
                "weak": {"risk_binary": "benign", "category": "normal_banking"},
            })
    write("SRC-BCC-001", rows)


if __name__ == "__main__":
    norm_salad()
    norm_aegis()
    norm_bosu()
    norm_prosocial()
    norm_banking()
