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
    # 空壳校验：native 里没有任何非空文本的种子不允许静默入库（PSD 事故防线）
    def has_text(o):
        if isinstance(o, str):
            return bool(o.strip())
        if isinstance(o, dict):
            return any(has_text(v) for v in o.values())
        if isinstance(o, list):
            return any(has_text(v) for v in o)
        return False

    empty = [i for i, r in enumerate(rows) if not has_text(r.get("native"))]
    if len(empty) > max(1, len(rows) // 100):
        raise SystemExit(
            f"{source_id}: {len(empty)}/{len(rows)} 条种子无任何文本（示例行 {empty[:3]}），"
            "字段映射可能错了，拒绝写入。先核对 raw 文件的真实字段名。")
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
    """raw 行格式（实测）: {"context", "response", "rots", "safety_label": "__casual__",
    "safety_annotations", "dialogue_id", "response_id", "episode_done"} —— 每行是对白中的
    一步（context 为对方上一句，response 为本句），按 dialogue_id 分组、response_id 排序
    还原多轮会话；safety_label 带 __ 下划线，需剥壳后再映射弱标签。"""
    by_dialog = {}
    path = RAW / "SRC-PSD-001" / "train.json"
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by_dialog.setdefault(r.get("dialogue_id"), []).append(r)
    rows = []
    for did, turns in by_dialog.items():
        turns.sort(key=lambda t: t.get("response_id", 0))
        rows.append(_psd_seed(did, turns))
    rows.sort(key=lambda r: r["seed_id"])
    write("SRC-PSD-001", rows[:60000])


def _psd_seed(did, turns):
    order = ["casual", "possibly_needs_caution", "probably_needs_caution",
             "needs_caution", "needs_intervention"]

    def strip(label):
        return (label or "").strip("_")

    # 会话还原：context 与上一行 response 相同则不重复；说话人按 A/B 交替
    convo, last = [], None
    for t in turns:
        for key in ("context", "response"):
            text = (t.get(key) or "").strip()
            if not text or text == last:
                continue
            convo.append({"speaker": "A" if len(convo) % 2 == 0 else "B", "text": text})
            last = text
    labels = [strip(t.get("safety_label")) for t in turns]
    worst = max((order.index(x) for x in labels if x in order), default=-1)
    weak = order[worst] if worst >= 0 else "unknown"
    return {
        "seed_id": seed_id("SRC-PSD-001", f"dialog-{did}"),
        "source_id": "SRC-PSD-001",
        "native": {"turns": convo[:40],
                   "safety_labels": [l for l in labels if l]},
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
