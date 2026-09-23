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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage2_pipeline as P  # noqa: E402

ROOT = P.ROOT
TASKS = ROOT / "tasks"
RISKS = [0, 0, 0, 0, 1, 1, 2, 2, 2, 3]  # per-10 template distribution
REL = ["陌生人", "熟人", "同事", "上下级", "商务关系", "亲友", "中间人关系"]
OBF = {0: ["low", "medium"], 1: ["medium", "high"], 2: ["medium", "high"], 3: ["high", "extreme"]}
FLIP = {3: 0, 2: 0, 1: 0}


def build_packets(n_agents=4, per_agent=10, seed=23, batch="BATCH-PILOT-002"):
    rng = random.Random(seed)
    archetypes = [json.loads(l) for l in (ROOT / "archetypes" / "archetypes.jsonl").open(encoding="utf-8")]
    by_cat = {}
    for a in archetypes:
        by_cat.setdefault(a["top_category"], []).append(a)
    cats = sorted(by_cat)

    specs = []
    n_pairs = per_agent * n_agents // 5  # ~20% of cases are risky siblings
    pair_anchors = []
    for i in range(per_agent * n_agents):
        cat = cats[i % len(cats)]
        arc = rng.choice(by_cat[cat])
        risk = RISKS[i % len(RISKS)]
        if risk not in arc["allowed_risk_levels"]:
            risk = arc["allowed_risk_levels"][0]
        key = f"case_{i + 1:02d}"
        has_transfer = rng.random() < (0.9 if risk >= 2 else 0.55)
        spec = {
            "key": key, "archetype_id": arc["archetype_id"], "top_category": cat,
            "subtype": arc["subtype"], "risk": risk,
            "illicit_likelihood": risk if risk >= 2 else (1 if risk == 1 else 0),
            "evidence_strength": rng.choice(["weak", "medium", "strong"]),
            "review_required": risk >= 2,
            "roles": arc["roles"], "signals": arc["observable_signals"],
            "benign_confusions": arc["benign_confusions"],
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
        key = f"case_{len(specs) + 1:02d}"
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
    for a in range(n_agents):
        chunk = specs[a * per_agent:(a + 1) * per_agent]
        tid = f"TASK-{a + 1:04d}"
        d = TASKS / tid
        (d / "cases").mkdir(parents=True, exist_ok=True)
        (d / "packet.json").write_text(json.dumps({
            "task_id": tid, "batch_id": batch, "workflow_version": P.WORKFLOW,
            "prompt_id": "PRM-DIALOGUE-001",
            "generator_rules_file": "crime_chat_dataset/prompts/PRM-DIALOGUE-001.md",
            "target_count": len(chunk), "cases": chunk,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{tid}: {len(chunk)} specs -> {d / 'packet.json'}")
    print(f"total {len(specs)} specs, {n_pairs} contrastive pairs planned")


def register_batch(task_ids):
    conn = P.db()
    packets = {}
    for tid in task_ids:
        pkt = json.loads((TASKS / tid / "packet.json").read_text(encoding="utf-8"))
        for c in pkt["cases"]:
            packets[c["key"]] = c
        for f in sorted((TASKS / tid / "cases").glob("case_*.json")):
            try:
                gen = json.loads(f.read_text(encoding="utf-8"))
                spec = packets[gen["key"]]
            except Exception as e:  # noqa: BLE001
                print(f"SKIP {f.name}: unreadable ({e})")
                continue
            events = gen.get("events") or []
            is_sib = bool(spec.get("sibling_of"))
            fam_seq = conn.execute("SELECT value FROM counters WHERE name='FAM'").fetchone()[0] + (0 if is_sib else 1)
            case = {
                "identity": {"family_id": f"FAM-{fam_seq:07d}", "lineage_id": f"LIN-{fam_seq:07d}",
                             "archetype_id": spec["archetype_id"], "variant_id": spec["variant"]},
                "source": {"source_ids": ["SRC-SYN-001"], "source_type": "synthetic_subagent"},
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
            print(cid, status, "risk", spec["risk"], f"({f.name}, {tid})", errs or "")
        # register pairs within this packet
        keys = {c["key"] for c in pkt["cases"]}
        for c in pkt["cases"]:
            if c.get("sibling_of") and c["sibling_of"] in keys:
                a = conn.execute("SELECT case_id, risk FROM cases WHERE yaml_path LIKE ?",
                                 (f"%{c['sibling_of']}%",)).fetchone()
                b = conn.execute("SELECT case_id, risk FROM cases WHERE yaml_path LIKE ?",
                                 (f"%{c['key']}%",)).fetchone()
                if a and b:
                    pa = {"identity": {"case_id": a[0]}, "labels": {"risk": a[1]}}
                    pb = {"identity": {"case_id": b[0]}, "labels": {"risk": b[1]}}
                    pid, flip = P.register_pair(conn, "minimal_edit", pa, pb)
                    print(pid, f"{a[0]} <-> {b[0]} flip={flip}")
    conn.close()


def judge_inputs(task_ids):
    out = ROOT / "generated" / "judged" / "inputs"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for tid in task_ids:
        for f in sorted((TASKS / tid / "cases").glob("case_*.json")):
            gen = json.loads(f.read_text(encoding="utf-8"))
            reg = gen.get("_registered")
            if not reg or reg["status"] != "accepted":
                continue
            (out / f"{reg['case_id']}.txt").write_text(
                P.render_conversation(gen["events"]), encoding="utf-8")
            n += 1
    print(f"{n} conversation-only files -> {out}")


def compare(judgement_file):
    conn = sqlite3.connect(DB)
    rows = [json.loads(l) for l in Path(judgement_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    agree = disagree = 0
    for r in rows:
        if r.get("judge") != "PRM-RISKJUDGE-001":
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
        build_packets(n_agents=int(sys.argv[2]) if len(sys.argv) > 2 else 4,
                      per_agent=int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    elif cmd == "register-batch":
        register_batch(sys.argv[2:])
    elif cmd == "judge-inputs":
        judge_inputs(sys.argv[2:])
    elif cmd == "compare":
        compare(sys.argv[2])
