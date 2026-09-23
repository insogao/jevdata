# -*- coding: utf-8 -*-
"""Stage 2 orchestrator: task packets -> sub-agent generation -> registration
-> blind judge inputs -> judgement comparison.

Subcommands:
  build-packets   : sample case specs, write tasks/TASK-*/packet.json
  register-batch  : validate+register every case JSON produced by generators
  judge-inputs    : export conversation-only txt for blind judging
  compare         : compare judge risk vs target, update registry
"""
import json
import random
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage2_pipeline as P  # noqa: E402

ROOT = P.ROOT
TASKS = ROOT / "tasks"
RISKS = [0, 0, 0, 0, 1, 1, 2, 2, 2, 3]  # per-10 template distribution（无 DB 时的兜底模板）
RISK_SHARE = {0: 0.35, 1: 0.20, 2: 0.30, 3: 0.15}  # 规划 §4.2 目标配比
REL = ["陌生人", "熟人", "同事", "上下级", "商务关系", "亲友", "中间人关系"]
OBF = {0: ["low", "medium"], 1: ["medium", "high"], 2: ["medium", "high"], 3: ["high", "extreme"]}
FLIP = {3: 0, 2: 0, 1: 0}


def _load_seed_refs():
    """Sample style/structure references from normalized sources.

    返回 {"harmful": [...], "normal": [...]}。全部经过非空过滤（PSD 空壳事故防线）：
    文本为空的 seed 一律不入池。normal 池渲染成 "A: .../B: ..." 的对话样式。"""
    refs = {"harmful": [], "normal": []}

    def add(kind, d, text):
        text = (text or "").strip()
        # 过滤空文本与 REDACTED 类占位（零样式信息量）
        if not text or len(text) < 8 or text.upper() in {"REDACTED", "N/A", "[REDACTED]"}:
            return
        refs[kind].append({"seed_id": d["seed_id"], "text": text[:280]})

    def rows(src):
        p = ROOT / "sources" / "normalized" / src / "seed.jsonl"
        if not p.exists():
            return
        with open(p, encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

    for d in rows("SRC-SAL-001"):
        add("harmful", d, d["native"].get("question"))
    for d in rows("SRC-AEG-001"):
        add("harmful", d, d["native"].get("prompt"))
    for d in rows("SRC-BCC-001"):
        nat = d["native"]
        add("normal", d, f"{nat.get('speaker','agent')}: {nat.get('text','')}")
    for d in rows("SRC-PSD-001"):
        # "自然节奏"参考只要日常档（casual/possibly）；needs_caution 以上属敏感对话，不作样式参考
        if d.get("weak", {}).get("risk_binary") not in ("casual", "possibly_needs_caution"):
            continue
        turns = d["native"].get("turns")[:6]
        add("normal", d, "\n".join(f"{t.get('speaker','?')}: {t.get('text','')}" for t in turns))
    return refs


def _deficits(total_target=10000, cats=None):
    """相对规划目标（§4.1 总量 / §4.2 risk 配比 / 10 个一级类均分 risky 份额）的剩余缺口。
    只读 DB；返回 (按 risk 缺口, 按一级类缺口)。负数 = 该格已超配。"""
    conn = sqlite3.connect(P.DB)
    by_risk = dict(conn.execute(
        "SELECT risk, COUNT(*) FROM cases WHERE status='accepted' GROUP BY risk"))
    by_cat = dict(conn.execute(
        "SELECT category, COUNT(*) FROM cases WHERE status='accepted' AND category!='none' GROUP BY category"))
    conn.close()
    if not cats:
        cats = sorted(by_cat) or ["none"]
    d_risk = {r: round(RISK_SHARE[r] * total_target - by_risk.get(r, 0)) for r in sorted(RISK_SHARE)}
    per_cat = (1 - RISK_SHARE[0]) * total_target / max(1, len(cats))
    d_cat = {c: round(per_cat - by_cat.get(c, 0)) for c in cats}
    return d_risk, d_cat


def build_packets(n_agents=3, per_agent=10, seed=23, batch_no=2, rebalance=False,
                  only_categories=None, max_risk=None):
    batch = f"BATCH-AUTO-{batch_no:03d}"
    # 批号碰撞防护：同批号并发 build-packets 会让 sibling 拆到不同包且 key 重复（0042/0043 事故）
    for pkt in TASKS.glob("TASK-*/packet.json"):
        try:
            if json.loads(pkt.read_text(encoding="utf-8")).get("batch_id") == batch:
                sys.exit(f"批号 {batch} 已存在（{pkt.parent.name}），换一个 batch_no")
        except Exception:  # noqa: BLE001
            pass
    rng = random.Random(seed)
    seed_refs = _load_seed_refs()
    usage_path = ROOT / "registry" / "seed_usage.json"
    usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else {}
    # 样式参考一次性台账：用过即焚，保证每个 agent 拿到的参考案例全局全新
    style_usage_path = ROOT / "registry" / "style_seed_usage.json"
    style_usage = json.loads(style_usage_path.read_text(encoding="utf-8")) if style_usage_path.exists() else {}

    def pick_ref(kind):
        pool = [r for r in seed_refs[kind] if usage.get(r["seed_id"], 0) < 5] or seed_refs[kind]
        r = rng.choice(pool)
        usage[r["seed_id"]] = usage.get(r["seed_id"], 0) + 1
        return r

    def pick_fresh_refs(kind, n, case_key):
        """n 条一次性样式参考：排除台账里已用过的（全局唯一），案例内也互不重复。
        只供参考思路，不写入 source_seed_ids；池子耗尽时回退到台账复用并标记 reuse。"""
        pool = [r for r in seed_refs[kind] if r["seed_id"] not in style_usage]
        fallback = not pool
        if fallback:
            pool = seed_refs[kind]
        seen, out = set(), []
        while len(out) < n and len(seen) < len(pool):
            r = rng.choice(pool)
            if r["seed_id"] in seen:
                continue
            seen.add(r["seed_id"])
            style_usage[r["seed_id"]] = {"case_key": case_key, "batch": batch,
                                         "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                         **({"reuse": True} if fallback else {})}
            out.append(r)
        return out
    # globally unique keys: b<batch>c<seq>
    key_seq = [0]
    def new_key():
        key_seq[0] += 1
        return f"b{batch_no:02d}c{key_seq[0]:03d}"
    archetypes = [json.loads(l) for l in (ROOT / "archetypes" / "archetypes.jsonl").open(encoding="utf-8")]
    by_cat = {}
    for a in archetypes:
        by_cat.setdefault(a["top_category"], []).append(a)
    cats = sorted(by_cat)
    # 能力定制：only_categories/max_risk 用于给特定模型出包（如敏感模型 max_risk=1）
    if only_categories:
        cats = [c for c in cats if c in set(only_categories)]
        if not cats:
            sys.exit(f"only_categories={only_categories} 没有匹配任何 archetype 类目")
    if max_risk is not None:
        cats = [c for c in cats if any(min(a["allowed_risk_levels"]) <= max_risk
                                       for a in by_cat[c])]
        if not cats:
            sys.exit(f"max_risk={max_risk} 下没有任何类目可选")
    # 缺口感知派单：按 §4.2 配比与 10 类均分把最缺的类目/档位排到队首（默认关闭）
    cat_order, d_risk = list(cats), None
    if rebalance:
        d_risk, d_cat = _deficits(cats=cats)
        cat_order = sorted(cats, key=lambda c: -d_cat.get(c, 0))
        print(f"rebalance: 类目优先级 {cat_order[:3]}...；risk 缺口 {d_risk}")

    specs = []
    n_pairs = per_agent * n_agents // 5  # ~20% of cases are risky siblings
    pair_anchors = []
    for i in range(per_agent * n_agents):
        cat = cat_order[i % len(cat_order)]
        arcs = by_cat[cat]
        if max_risk is not None:
            fits = [a for a in arcs if min(a["allowed_risk_levels"]) <= max_risk]
            arcs = fits or arcs
        arc = rng.choice(arcs)
        risk = RISKS[i % len(RISKS)]
        if rebalance and d_risk:
            allowed = sorted((r for r in arc["allowed_risk_levels"]
                              if r in d_risk and (max_risk is None or r <= max_risk)),
                             key=lambda r: -d_risk[r])
            if allowed:
                risk = rng.choice(allowed[:2])  # 缺口最大的两档里随机，保多样性
        if max_risk is not None and risk > max_risk:
            ok = sorted(r for r in arc["allowed_risk_levels"] if r <= max_risk)
            risk = ok[0] if ok else risk
        if risk not in arc["allowed_risk_levels"]:
            risk = arc["allowed_risk_levels"][0]
        key = new_key()
        has_transfer = rng.random() < (0.9 if risk >= 2 else 0.55)
        spec = {
            "key": key, "archetype_id": arc["archetype_id"], "top_category": cat,
            "subtype": arc["subtype"], "risk": risk,
            "illicit_likelihood": risk if risk >= 2 else (1 if risk == 1 else 0),
            "evidence_strength": rng.choice(["weak", "medium", "strong"]),
            "review_required": risk >= 2,
            "roles": arc["roles"], "signals": arc["observable_signals"],
            "benign_confusions": arc["benign_confusions"],
            "seed_reference": pick_ref("harmful" if risk >= 2 else "normal"),
            # 样式参考一次性发放：风险案例多看"意图如何藏在正常话题里"，良性案例多看真实对话节奏。
            # 参考只给思路，禁止抄台词（见 PRM-DIALOGUE-002）；用过即焚，跨批次不重复。
            "style_references": {
                "concealment_like": pick_fresh_refs("harmful", 2 if risk >= 1 else 1, key),
                "natural_rhythm_like": pick_fresh_refs("normal", 1 if risk >= 1 else 2, key),
            },
            "sibling_of": None, "variant": "v01", "flip_hint": None,
            "axes": {
                "relationship": rng.choice(REL),
                "obfuscation": rng.choice(OBF[risk]),
                "duration_days": rng.randint(2, 6),
                "message_target": rng.randint(40, 80),
                "side_topics": rng.randint(3, 5),
            },
            "transfer": {
                "has_transfer": has_transfer,
                "normal_transfer_count": 1 if (has_transfer and risk <= 1) else 0,
                "suspicious_transfer_count": 1 if (has_transfer and risk >= 2) else 0,
            },
        }
        specs.append(spec)
        if risk >= 2 and len(pair_anchors) < n_pairs and rng.random() < 0.6:
            pair_anchors.append((key, arc, cat))

    # build siblings for chosen anchors
    sib_idx = set()
    for anchor_key, arc, cat in pair_anchors:
        base = next(s for s in specs if s["key"] == anchor_key)
        key = new_key()
        sib = json.loads(json.dumps(base))
        sib.update({
            "key": key, "risk": FLIP.get(base["risk"], 0),
            "illicit_likelihood": 0, "evidence_strength": "strong",
            "review_required": False, "sibling_of": anchor_key,
            "variant": "v02", "category": "none",
            "flip_hint": f"把决定性事实翻转为良性（参考 benign_confusions: {arc['benign_confusions']}），"
                         f"其余对话骨架保持一致，只改 1-2 个关键事件/台词",
            "transfer": {"has_transfer": base["transfer"]["has_transfer"],
                         "normal_transfer_count": 1 if base["transfer"]["has_transfer"] else 0,
                         "suspicious_transfer_count": 0},
        })
        specs.append(sib)
        sib_idx.add(key)

    rng.shuffle(specs)
    # remove overflow beyond per_agent*n_agents
    specs = specs[:per_agent * n_agents]
    TASKS.mkdir(parents=True, exist_ok=True)
    existing = [int(d.name.split('-')[1]) for d in TASKS.glob('TASK-*') if d.name.split('-')[1].isdigit()]
    next_tid = (max(existing) + 1) if existing else 1
    for a in range(n_agents):
        chunk = specs[a * per_agent:(a + 1) * per_agent]
        tid = f"TASK-{next_tid + a:04d}"
        d = TASKS / tid
        (d / "cases").mkdir(parents=True, exist_ok=True)
        (d / "packet.json").write_text(json.dumps({
            "task_id": tid, "batch_id": batch, "workflow_version": P.WORKFLOW,
            "prompt_id": "PRM-DIALOGUE-002",
            "generator_rules_file": "crime_chat_dataset/prompts/PRM-DIALOGUE-002.md",
            "target_count": len(chunk), "cases": chunk,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{tid}: {len(chunk)} specs -> {d / 'packet.json'}")
    usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=1), encoding="utf-8")
    style_usage_path.write_text(json.dumps(style_usage, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total {len(specs)} specs, {n_pairs} contrastive pairs planned, "
          f"seed_usage saved, style refs consumed: {len(style_usage)}")


def register_batch(task_ids):
    conn = P.db()
    packets = {}
    key2cid = {}
    for tid in task_ids:
        pkt = json.loads((TASKS / tid / "packet.json").read_text(encoding="utf-8"))
        for c in pkt["cases"]:
            packets[c["key"]] = c
        for f in sorted((TASKS / tid / "cases").glob("*.json")):
            try:
                gen = json.loads(f.read_text(encoding="utf-8"))
                spec = packets[gen["key"]]
            except Exception as e:  # noqa: BLE001
                print(f"SKIP {f.name}: unreadable ({e})")
                continue
            if gen.get("_registered", {}).get("case_id"):
                print(f"SKIP {f.name}: already {gen['_registered']['case_id']}")
                continue
            events = gen.get("events") or []
            is_sib = bool(spec.get("sibling_of"))
            fam_seq = conn.execute("SELECT value FROM counters WHERE name='FAM'").fetchone()[0] + (0 if is_sib else 1)
            case = {
                "identity": {"family_id": f"FAM-{fam_seq:07d}", "lineage_id": f"LIN-{fam_seq:07d}",
                             "archetype_id": spec["archetype_id"], "variant_id": spec.get("variant", "v01")},
                 "source": {"source_ids": ["SRC-SYN-001"],
                            "source_seed_ids": ([spec["seed_reference"]["seed_id"]]
                                                if isinstance(spec.get("seed_reference"), dict) else []),
                            "source_type": "synthetic_subagent"},
                "lineage": {"root_case_id": None, "parent_case_id": None,
                            "generation_type": "contrastive_sibling" if is_sib else "original"},
                "labels": {"risk": spec["risk"], "category": spec["top_category"] if spec["risk"] >= 1 else "none",
                           "illicit_likelihood": spec["illicit_likelihood"],
                           "evidence_strength": spec["evidence_strength"],
                           "review_required": spec["review_required"]},
                "hidden_case": {"latent_intent": gen.get("latent_intent", ""),
                                "critical_evidence": gen.get("critical_facts", []),
                                "benign_alternatives": gen.get("benign_alternatives",
                                                               spec.get("benign_confusions", []))},
                "attributes": {"duration_days": spec["axes"]["duration_days"],
                               "turn_count": sum(1 for e in events if e.get("type") == "message"),
                               "relationship": spec["axes"]["relationship"],
                               "obfuscation": spec["axes"]["obfuscation"],
                               "has_transfer": spec["transfer"]["has_transfer"],
                               "normal_transfer_count": spec["transfer"]["normal_transfer_count"],
                               "suspicious_transfer_count": spec["transfer"]["suspicious_transfer_count"]},
                "generation_signature": {"subtype": spec["subtype"]},
                "execution": {"prompt_id": "PRM-DIALOGUE-001", "agent_id": tid,
                              "model_id": "MOD-SESSION-SUBAGENT", "batch_id": pkt["batch_id"]},
                "dedup": {}, "title": f"{spec['top_category']}/{spec['subtype']}",
                "events": events,
            }
            cid, status, errs = P.register_case(conn, case)
            gen["_registered"] = {"case_id": cid, "status": status, "errors": errs}
            f.write_text(json.dumps(gen, ensure_ascii=False, indent=1), encoding="utf-8")
            key2cid[gen["key"]] = cid
            print(cid, status, "risk", spec["risk"], f"({f.name}, {tid})", errs or "")
    # register pairs (base and sibling both within this batch)
    for tid in task_ids:
        pkt = json.loads((TASKS / tid / "packet.json").read_text(encoding="utf-8"))
        for c in pkt["cases"]:
            sib = c.get("sibling_of")
            if sib and sib in key2cid and c["key"] in key2cid:
                a, b = key2cid[sib], key2cid[c["key"]]
                ra = conn.execute("SELECT risk FROM cases WHERE case_id=?", (a,)).fetchone()[0]
                rb = conn.execute("SELECT risk FROM cases WHERE case_id=?", (b,)).fetchone()[0]
                pa = {"identity": {"case_id": a}, "labels": {"risk": ra}}
                pb = {"identity": {"case_id": b}, "labels": {"risk": rb}}
                pid, flip = P.register_pair(conn, "minimal_edit", pa, pb)
                print(pid, f"{a} <-> {b} flip={flip}")
    conn.close()


def judge_inputs(task_ids):
    out = ROOT / "generated" / "judged" / "inputs"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for tid in task_ids:
        for f in sorted((TASKS / tid / "cases").glob("*.json")):
            gen = json.loads(f.read_text(encoding="utf-8"))
            reg = gen.get("_registered")
            if not reg or reg["status"] != "accepted":
                continue
            (out / f"{reg['case_id']}.txt").write_text(
                P.render_conversation(gen["events"]), encoding="utf-8")
            n += 1
    print(f"{n} conversation-only files -> {out}")


def compare(judgement_file):
    conn = sqlite3.connect(P.DB)
    rows = [json.loads(l) for l in Path(judgement_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    agree = disagree = 0
    for r in rows:
        if r.get("pass") != "risk":
            continue
        cid, jr = r["case_id"], r["out"]["operational_risk"]
        tr = conn.execute("SELECT risk, status FROM cases WHERE case_id=?", (cid,)).fetchone()
        if not tr:
            continue
        delta = abs(jr - tr[0])
        if delta >= 2:
            disagree += 1
            conn.execute("UPDATE cases SET status='review', split='judge_disagreement' WHERE case_id=?", (cid,))
            print(f"DISAGREE {cid}: target={tr[0]} judge={jr} -> review")
        else:
            agree += 1
    conn.commit()
    print(f"agreement(±1): {agree}, disagreement(>=2): {disagree}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build-packets":
        build_packets(n_agents=int(sys.argv[2]) if len(sys.argv) > 2 else 3,
                      per_agent=int(sys.argv[3]) if len(sys.argv) > 3 else 10,
                      batch_no=int(sys.argv[4]) if len(sys.argv) > 4 else 2,
                      seed=int(sys.argv[5]) if len(sys.argv) > 5 else 23,
                      rebalance=len(sys.argv) > 6 and sys.argv[6] == "1",
                      only_categories=(sys.argv[7].split(",") if len(sys.argv) > 7 and sys.argv[7] else None),
                      max_risk=(int(sys.argv[8]) if len(sys.argv) > 8 and sys.argv[8] else None))
    elif cmd == "shortfall":
        total = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
        cats = sorted({json.loads(l)["top_category"]
                       for l in open(ROOT / "archetypes" / "archetypes.jsonl", encoding="utf-8")})
        dr, dc = _deficits(total, cats)
        print(f"目标总量 {total}（§4.2 配比）。剩余缺口（负数=已超配）：")
        print("[按 risk 档]")
        for r in sorted(dr):
            print(f"  risk{r}: {dr[r]:+d}")
        print("[按一级类] 缺口升序 = 最缺先补")
        for c, v in sorted(dc.items(), key=lambda kv: kv[1]):
            print(f"  {c}: {v:+d}")
    elif cmd == "status":
        import glob as _g
        acc = len(_g.glob(str(ROOT / "generated" / "accepted" / "CASE-*.yaml")))
        conn = sqlite3.connect(P.DB)
        pr = conn.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]
        by = conn.execute("SELECT risk, COUNT(*) FROM cases WHERE status='accepted' GROUP BY risk ORDER BY risk").fetchall()
        conn.close()
        print(f"accepted={acc} pairs={pr} by_risk={by}")
    elif cmd == "register-batch":
        register_batch(sys.argv[2:])
    elif cmd == "judge-inputs":
        judge_inputs(sys.argv[2:])
    elif cmd == "compare":
        compare(sys.argv[2])
