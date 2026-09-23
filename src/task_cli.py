# -*- coding: utf-8 -*-
"""Task claim / lease CLI — 多 Agent 任务领取与超时判死的唯一入口.

设计要点（对应 AGENTS.md 任务协议）:
- tasks 表 = 任务看板（pending/in_progress/completed/abandoned/cancelled）
- task_claims 表 = append-only 领取审计（每次领取一行，含领取时间与 lease 截止时间）
- 超时语义: agent 断流无法回写是常态，lease（默认 2h）到期后由任意后续命令
  惰性清扫（reap）判为 expired，任务放回 pending；attempts>=MAX_ATTEMPTS 判 abandoned 等人工。
- 原子性: BEGIN IMMEDIATE 串行化并发领取。
- 所有状态变化自动追加到 report/ORCHESTRATOR_LOG.md（机器落盘，告别手写日志漂移）。

用法见 `python src/task_cli.py -h`。仅用标准库。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "crime_chat_dataset"
TASKS = DATA / "tasks"
DEFAULT_DB = DATA / "registry" / "dataset_registry.sqlite"
LOG = REPO / "report" / "ORCHESTRATOR_LOG.md"

DEFAULT_LEASE_SECONDS = int(os.environ.get("TASK_LEASE_SECONDS", "7200"))  # 2h
MAX_ATTEMPTS = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks(
  task_id TEXT PRIMARY KEY, batch_id TEXT, packet_path TEXT, target_count INTEGER,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_claims(
  claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL, agent TEXT NOT NULL,
  status TEXT NOT NULL,              -- active|completed|failed|expired
  attempts INTEGER NOT NULL,
  claimed_at TEXT NOT NULL, lease_expires_at TEXT NOT NULL, closed_at TEXT,
  accepted INTEGER, pairs INTEGER, note TEXT);
"""


def now() -> datetime:
    return datetime.now()


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    return conn


def log_line(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y-%m-%d %H:%M")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"- {stamp} | task_cli: {msg}\n")


# ---------------------------------------------------------------- backfill

def backfill(conn: sqlite3.Connection) -> None:
    """把已存在的 tasks/TASK-* 目录登记进看板（幂等）。"""
    stale = {"TASK-0009", "TASK-0010", "TASK-0011"}  # 6f38267 丢弃的过期包
    if not TASKS.exists():
        return
    for d in sorted(TASKS.glob("TASK-*")):
        tid = d.name
        if conn.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone():
            continue
        pkt_path = d / "packet.json"
        batch_id = target = None
        if pkt_path.exists():
            try:
                pkt = json.loads(pkt_path.read_text(encoding="utf-8"))
                batch_id, target = pkt.get("batch_id"), pkt.get("target_count")
            except Exception:  # noqa: BLE001
                pass
        has_output = any(
            (f.read_text(encoding="utf-8").find('"_registered"') >= 0)
            for f in sorted((d / "cases").glob("*.json"))
        ) if (d / "cases").exists() else False
        if tid in stale:
            status, note = "cancelled", "stale packet（种子限额修复前生成，见 git 6f38267）"
        elif has_output:
            status, note = "completed", "backfill: 产出已入库并提交（git 历史）"
        else:
            status, note = "pending", ""
        stamp = iso(now())
        conn.execute(
            "INSERT OR IGNORE INTO tasks VALUES (?,?,?,?,?,?,?,?)",
            (tid, batch_id, str(pkt_path.relative_to(REPO)) if pkt_path.exists() else None,
             target, status, 1 if status == "completed" else 0, stamp, stamp))
        if note:
            conn.execute(
                "INSERT INTO task_claims(task_id, agent, status, attempts, claimed_at, "
                "lease_expires_at, closed_at, note) VALUES (?,?,?,?,?,?,?,?)",
                (tid, "backfill", status, 1, stamp, stamp, stamp, note))
    conn.commit()


# ---------------------------------------------------------------- reap

def reap(conn: sqlite3.Connection) -> int:
    """把过期 active claim 判为 expired；任务按 attempts 决定回池或废弃。"""
    t = iso(now())
    rows = conn.execute(
        "SELECT claim_id, task_id, agent, attempts, lease_expires_at FROM task_claims "
        "WHERE status='active' AND lease_expires_at < ?", (t,)).fetchall()
    for r in rows:
        conn.execute("UPDATE task_claims SET status='expired', closed_at=?, "
                     "note=COALESCE(note,'')||' lease超时无回写' WHERE claim_id=?", (t, r["claim_id"]))
        tr = conn.execute("SELECT attempts FROM tasks WHERE task_id=?", (r["task_id"],)).fetchone()
        if tr is None:
            continue
        if tr["attempts"] >= MAX_ATTEMPTS:
            conn.execute("UPDATE tasks SET status='abandoned', updated_at=? WHERE task_id=?",
                         (t, r["task_id"]))
            dest = f"abandoned（已试 {tr['attempts']} 次，等人工）"
        else:
            conn.execute("UPDATE tasks SET status='pending', updated_at=? WHERE task_id=?",
                         (t, r["task_id"]))
            dest = f"重新入池（attempts {tr['attempts']}/{MAX_ATTEMPTS}）"
        log_line(f"EXPIRED claim={r['claim_id']} {r['task_id']} agent={r['agent']} "
                 f"lease截止={r['lease_expires_at']} -> {dest}")
    if rows:
        conn.commit()
    return len(rows)


# ---------------------------------------------------------------- commands

def cmd_init(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    backfill(conn)
    n = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    print(f"tasks 表就绪，共 {n} 个任务。看板: python {Path(__file__).name} list")


def _packet_ok(row: sqlite3.Row, max_risk, categories) -> bool:
    """按任务包内容过滤（敏感模型路由）：包内任何 case 超 max_risk 则跳过；
    指定 categories 时要求包内至少含一个该类目 case。"""
    if max_risk is None and not categories:
        return True
    try:
        pkt = json.loads((REPO / row["packet_path"]).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    cases = pkt.get("cases", [])
    if max_risk is not None and any(c.get("risk", 0) > max_risk for c in cases):
        return False
    if categories and not any(c.get("top_category") in categories for c in cases):
        return False
    return True


def claim_task(conn: sqlite3.Connection, agent: str, task_id=None, lease_seconds=DEFAULT_LEASE_SECONDS,
               max_risk=None, categories=None):
    """原子领取一个 pending 任务（可按能力过滤），返回 (claim_id, task_row, deadline)。"""
    reap(conn)
    deadline = iso(now() + timedelta(seconds=lease_seconds))
    t = iso(now())
    conn.execute("BEGIN IMMEDIATE")
    try:
        if task_id:
            rows = [conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()]
            if rows[0] is None:
                sys.exit(f"任务 {task_id} 不存在（先 build-packets 或检查任务号）")
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status='pending' ORDER BY task_id").fetchall()
        picked = None
        for row in rows:
            if row is None:
                continue
            if row["status"] == "pending" and _packet_ok(row, max_risk, categories):
                picked = row
                break
        if picked is None:
            sys.exit("没有匹配能力的 pending 任务"
                     + ("（可放宽 --max-risk/--categories，或等总控按缺口出包）"
                        if (max_risk or categories) else
                        "。用 stage2_orchestrate.py build-packets 生成新批次。"))
        cur = conn.execute(
            "INSERT INTO task_claims(task_id, agent, status, attempts, claimed_at, lease_expires_at) "
            "VALUES (?,?,?,?,?,?)",
            (picked["task_id"], agent, "active", picked["attempts"] + 1, t, deadline))
        conn.execute("UPDATE tasks SET status='in_progress', attempts=attempts+1, updated_at=? "
                     "WHERE task_id=?", (t, picked["task_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    log_line(f"CLAIM claim={cur.lastrowid} {picked['task_id']} agent={agent} "
             f"lease={lease_seconds}s 截止={deadline}")
    return cur.lastrowid, picked, deadline


def cmd_claim(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    agent = args.agent or os.environ.get("AGENT_NAME") or f"{socket.gethostname()}:{os.getpid()}"
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    claim_id, row, deadline = claim_task(conn, agent, args.task, args.lease_seconds,
                                         args.max_risk, categories)
    print(f"已领取 claim={claim_id} {row['task_id']} agent={agent}")
    print(f"  lease 截止: {deadline}（{args.lease_seconds}s；还活着但快到期就 heartbeat）")
    if row["packet_path"]:
        print(f"  任务包: {row['packet_path']}")
    print(f"  完成: task_cli.py complete --claim {claim_id} --accepted N --pairs N")


def _active_claim(conn: sqlite3.Connection, claim_id: int) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM task_claims WHERE claim_id=?", (claim_id,)).fetchone()
    if r is None:
        sys.exit(f"claim {claim_id} 不存在")
    if r["status"] != "active":
        sys.exit(f"claim {claim_id} 状态为 {r['status']}（非 active），可能是 lease 已过期被判死")
    return r


def cmd_heartbeat(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    t = now()
    with conn:
        r = _active_claim(conn, args.claim)
        if args.agent and r["agent"] != args.agent:
            sys.exit(f"claim {args.claim} 属于 {r['agent']}，无权续约")
        new_deadline = iso(t + timedelta(seconds=args.extend_seconds))
        conn.execute("UPDATE task_claims SET lease_expires_at=? WHERE claim_id=?",
                     (new_deadline, args.claim))
    print(f"claim {args.claim} 续约至 {new_deadline}")


def cmd_complete(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    t = iso(now())
    with conn:
        r = _active_claim(conn, args.claim)
        conn.execute("UPDATE task_claims SET status='completed', closed_at=?, accepted=?, pairs=?, "
                     "note=? WHERE claim_id=?", (t, args.accepted, args.pairs, args.note, args.claim))
        conn.execute("UPDATE tasks SET status='completed', updated_at=? WHERE task_id=?",
                     (t, r["task_id"]))
    log_line(f"COMPLETE claim={args.claim} {r['task_id']} agent={r['agent']} "
             f"accepted={args.accepted} pairs={args.pairs}" + (f" | {args.note}" if args.note else ""))
    print(f"claim {args.claim} 已完成。记得 git commit："
          f"data: {r['task_id']} accepted=+{args.accepted} pairs=+{args.pairs}")


def cmd_fail(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    t = iso(now())
    with conn:
        r = _active_claim(conn, args.claim)
        conn.execute("UPDATE task_claims SET status='failed', closed_at=?, note=? WHERE claim_id=?",
                     (t, args.reason, args.claim))
        tr = conn.execute("SELECT attempts FROM tasks WHERE task_id=?", (r["task_id"],)).fetchone()
        if tr["attempts"] >= MAX_ATTEMPTS:
            conn.execute("UPDATE tasks SET status='abandoned', updated_at=? WHERE task_id=?",
                         (t, r["task_id"]))
            dest = "abandoned（等人工）"
        else:
            conn.execute("UPDATE tasks SET status='pending', updated_at=? WHERE task_id=?",
                         (t, r["task_id"]))
            dest = f"重新入池（attempts {tr['attempts']}/{MAX_ATTEMPTS}）"
    log_line(f"FAILED claim={args.claim} {r['task_id']} agent={r['agent']} 原因={args.reason} -> {dest}")
    print(f"claim {args.claim} 标记失败，任务{dest}")


def cmd_list(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    reap(conn)
    print("== 任务看板 ==")
    rows = conn.execute("SELECT * FROM tasks ORDER BY task_id").fetchall()
    for r in rows:
        print(f"  {r['task_id']}  {r['status']:<11} attempts={r['attempts']}  "
              f"target={r['target_count']}  batch={r['batch_id'] or '-'}")
    counts = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY status").fetchall()
    print("  小计: " + ", ".join(f"{r[0]}={r[1]}" for r in counts))
    active = conn.execute("SELECT * FROM task_claims WHERE status='active' ORDER BY claim_id").fetchall()
    if active:
        print("== 持有中的 claim ==")
        for a in active:
            left = int((parse(a["lease_expires_at"]) - now()).total_seconds() / 60)
            print(f"  claim={a['claim_id']} {a['task_id']} agent={a['agent']} "
                  f"剩余约 {left} 分钟（截止 {a['lease_expires_at']}）")


def cmd_sync_counters(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    rows = conn.execute("SELECT name, value FROM counters ORDER BY name").fetchall()
    out = REPO / "crime_chat_dataset" / "registry" / "id_counters.yaml"
    lines = [
        "# ID 计数器快照 —— 由 `python src/task_cli.py sync-counters` 生成。",
        "# 唯一事实源是 SQLite counters 表（dataset_registry.sqlite）；此文件仅供人读。",
        "schema: ID-COUNTERS-v1",
        "synced_at: " + iso(now()),
        "counters:",
    ]
    lines += [f"  {r['name']}: {r['value']}" for r in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写 {out.relative_to(REPO)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="registry DB 路径（测试用）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建表 + 回填存量任务目录（幂等）")
    p = sub.add_parser("claim", help="原子领取一个 pending 任务")
    p.add_argument("--agent", help="agent 名字（默认 $AGENT_NAME 或 host:pid）")
    p.add_argument("--task", help="指定任务号（默认取最老的 pending）")
    p.add_argument("--max-risk", type=int, help="能力过滤：只领包内所有 case risk 均 ≤ N 的任务")
    p.add_argument("--categories", help="能力过滤：只领包含这些一级类目的任务（逗号分隔）")
    p.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS,
                   help=f"lease 时长，默认 {DEFAULT_LEASE_SECONDS}s（2h），超时无回写判失败")
    p = sub.add_parser("heartbeat", help="续约 lease（还活着但快到期时用）")
    p.add_argument("--claim", type=int, required=True)
    p.add_argument("--agent", help="校验持有者")
    p.add_argument("--extend-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    p = sub.add_parser("complete", help="任务完成回写")
    p.add_argument("--claim", type=int, required=True)
    p.add_argument("--accepted", type=int, default=0)
    p.add_argument("--pairs", type=int, default=0)
    p.add_argument("--note", default="")
    p = sub.add_parser("fail", help="还活着但做不完：主动交还并写原因")
    p.add_argument("--claim", type=int, required=True)
    p.add_argument("--reason", required=True)
    sub.add_parser("list", help="看板 + 持有中的 claim（顺带清扫超时）")
    sub.add_parser("reap", help="只清扫超时 claim")
    sub.add_parser("sync-counters", help="把 SQLite counters 同步到 id_counters.yaml")

    args = ap.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    try:
        backfill(conn)
        {"init": cmd_init, "claim": cmd_claim, "heartbeat": cmd_heartbeat,
         "complete": cmd_complete, "fail": cmd_fail, "list": cmd_list,
         "reap": lambda c, a: print(f"清扫了 {reap(c)} 条过期 claim"),
         "sync-counters": cmd_sync_counters}[args.cmd](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
