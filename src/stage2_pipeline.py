# -*- coding: utf-8 -*-
"""Stage 2 pipeline core: case specs -> YAML mother files -> program acceptance.

The dialogue itself comes from a generator (PRM-DIALOGUE-001); in this offline
pilot the session model authored the events directly into cases/pilot_events/.
Program checks + registry + hash/dedup are automated here; judge passes are
recorded in generated/judged/*.jsonl per PRM-FACTJUDGE-001 / PRM-RISKJUDGE-001.
"""
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "crime_chat_dataset"
DB = ROOT / "registry" / "dataset_registry.sqlite"
WORKFLOW = "DATASET-WF-v2.0"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cases(
  case_id TEXT PRIMARY KEY, family_id TEXT, lineage_id TEXT, archetype_id TEXT,
  risk INTEGER, category TEXT, has_transfer INTEGER, status TEXT,
  content_hash TEXT, split TEXT, yaml_path TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS pairs(
  pair_id TEXT PRIMARY KEY, focus_fact TEXT, case_a TEXT, case_b TEXT,
  risk_a INTEGER, risk_b INTEGER, flip_verified INTEGER);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER);
INSERT OR IGNORE INTO counters(name, value) VALUES
 ('CASE', 0), ('PAIR', 0), ('FAM', 0), ('LIN', 0), ('ARC', 0);
"""


def db():
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA_SQL)
    return conn


def next_id(conn, name):
    v = conn.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()[0] + 1
    conn.execute("UPDATE counters SET value=? WHERE name=?", (v, name))
    return v


META_WORDS = ("风险等级", "标签", "审核员", "案件卡", "target_label", "risk级")


def render_conversation(events):
    """events -> human transcript with 【date】 headers and inline system transfers."""
    out, cur_day = [], None
    for e in events:
        day = e["time"].split(" ")[0]
        if day != cur_day:
            out.append(f"【{day}】")
            cur_day = day
        if e["type"] == "message":
            out.append(f"{e['speaker']}：{e['text']}")
        elif e["type"] == "transfer":
            out.append(f"【系统消息】{e['from']} 向 {e['to']} 转账 {e['amount']} 元，已收款。")
        elif e["type"] in ("image", "voice"):
            out.append(f"{e['speaker']}：[{e['type']}：{e.get('note','')}]")
    return "\n".join(out)


def estimate_tokens(events):
    text = render_conversation(events)
    return int(len(re.findall(r"[\u4e00-\u9fff]", text)) * 1.5 + len(text) // 3)


def program_checks(case):
    errs = []
    events = case["events"]
    if not events:
        errs.append("empty events")
    days = {e["time"].split(" ")[0] for e in events}
    if len(days) < max(2, case["attributes"]["duration_days"] // 2):
        errs.append(f"too few distinct days: {sorted(days)}")
    conv = render_conversation(events)
    for w in META_WORDS:
        if w in conv:
            errs.append(f"meta word leaked: {w}")
    if case["attributes"].get("has_transfer"):
        if not any(e["type"] == "transfer" for e in events):
            errs.append("has_transfer=true but no transfer event")
    n_transfers = sum(1 for e in events if e["type"] == "transfer")
    if n_transfers and not case["attributes"].get("has_transfer"):
        errs.append("transfer event present but has_transfer=false")
    if case["labels"]["risk"] == 0 and case["attributes"].get("suspicious_transfer_count", 0) > 0:
        errs.append("risk0 with suspicious transfer count > 0")
    return errs


def content_hash(case):
    norm = re.sub(r"\s+", "", render_conversation(case["events"]))
    return "sha256:" + hashlib.sha256(norm.encode()).hexdigest()


def register_case(conn, case):
    cid = f"CASE-{next_id(conn, 'CASE'):07d}"
    case["identity"]["case_id"] = cid
    errs = program_checks(case)
    case["dedup"]["content_hash"] = content_hash(case)
    dup = conn.execute("SELECT case_id FROM cases WHERE content_hash=? AND status='accepted'",
                       (case["dedup"]["content_hash"],)).fetchone()
    if dup:
        errs.append(f"duplicate content of {dup[0]}")
    status = "accepted" if not errs else "rejected"
    out_dir = ROOT / "generated" / status
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = out_dir / f"{cid}.yaml"
    yaml_path.write_text(render_yaml(case, status), encoding="utf-8")
    conn.execute(
        "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, case["identity"]["family_id"], case["identity"]["lineage_id"],
         case["identity"]["archetype_id"], case["labels"]["risk"], case["labels"]["category"],
         int(case["attributes"]["has_transfer"]), status, case["dedup"]["content_hash"],
         case.get("split", "unassigned"),
         yaml_path.relative_to(ROOT.parent).as_posix(),  # 相对路径，跨机器可用
         time.strftime("%Y-%m-%dT%H:%M:%S")))
    conn.commit()
    return cid, status, errs


def render_yaml(c, status):
    ind = "\n".join("  " + ln for ln in render_conversation(c["events"]).split("\n"))
    ev_lines = []
    for e in c["events"]:
        day = e["time"].split(" ")[0]
        ev_lines.append((day, e))
    attr = c["attributes"]
    return f"""schema_version: CASE-YAML-v1

identity:
  case_id: {c['identity']['case_id']}
  family_id: {c['identity']['family_id']}
  lineage_id: {c['identity']['lineage_id']}
  archetype_id: {c['identity']['archetype_id']}
  variant_id: {c['identity'].get('variant_id', 'v01')}

source:
  source_ids:
  {json.dumps(c['source']['source_ids'], ensure_ascii=False, indent=2).lstrip('[').rstrip(']').replace(chr(10), chr(10)+'  ')}
  source_type: {c['source'].get('source_type', 'synthetic_pilot')}
{('  source_seed_ids:' + chr(10) + chr(10).join('  - ' + x for x in c['source'].get('source_seed_ids', []))) if c['source'].get('source_seed_ids') else ''}

lineage:
  root_case_id: {c['lineage'].get('root_case_id')}
  parent_case_id: {c['lineage'].get('parent_case_id')}
  generation_type: {c['lineage'].get('generation_type', 'original')}

labels:
  risk: {c['labels']['risk']}
  category: {c['labels']['category']}
  illicit_likelihood: {c['labels'].get('illicit_likelihood', c['labels']['risk'])}
  evidence_strength: {c['labels'].get('evidence_strength', 'medium')}
  review_required: {str(c['labels'].get('review_required', c['labels']['risk'] >= 2)).lower()}

hidden_case:
  latent_intent: {c['hidden_case']['latent_intent']}
  critical_evidence:
{chr(10).join('  - ' + str(x) for x in c['hidden_case']['critical_evidence'])}
  benign_alternatives:
{chr(10).join('  - ' + str(x) for x in c['hidden_case'].get('benign_alternatives', ['未识别']))}

attributes:
  duration_days: {attr['duration_days']}
  turn_count: {attr['turn_count']}
  approximate_tokens_estimate: {estimate_tokens(c['events'])}
  relationship: {attr.get('relationship', 'acquaintance')}
  obfuscation: {attr.get('obfuscation', 'medium')}
  has_transfer: {str(attr['has_transfer']).lower()}
  normal_transfer_count: {attr.get('normal_transfer_count', 0)}
  suspicious_transfer_count: {attr.get('suspicious_transfer_count', 0)}
  format: wechat_1to1_transcript

generation_signature:
  top_category: {c['labels']['category']}
  subtype: {c['generation_signature']['subtype']}
  risk: {c['labels']['risk']}
  relationship: {attr.get('relationship', 'acquaintance')}
  obfuscation: {attr.get('obfuscation', 'medium')}
  has_transfer: {str(attr['has_transfer']).lower()}

execution:
  workflow_version: {WORKFLOW}
  prompt_id: {c['execution'].get('prompt_id', 'PRM-DIALOGUE-001')}
  agent_id: {c['execution'].get('agent_id', 'AGT-SESSION-001')}
  model_id: {c['execution'].get('model_id', 'MOD-SESSION-001')}
  batch_id: {c['execution'].get('batch_id', 'BATCH-PILOT-001')}

dedup:
  content_hash: {c['dedup']['content_hash']}
pipeline_status: {status}
title: {c.get('title', c['identity']['case_id'])}
conversation: |-
{ind}
"""


def register_pair(conn, focus_fact, case_a, case_b):
    pid = f"PAIR-{next_id(conn, 'PAIR'):07d}"
    flip = (case_a["labels"]["risk"] != case_b["labels"]["risk"])
    conn.execute("INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?,?,?)",
                 (pid, focus_fact, case_a["identity"]["case_id"],
                  case_b["identity"]["case_id"], case_a["labels"]["risk"],
                  case_b["labels"]["risk"], int(flip)))
    conn.commit()
    return pid, flip
