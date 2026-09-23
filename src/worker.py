# -*- coding: utf-8 -*-
"""子 agent 一站式入口：领单 → 照工单写作 → 回写完成。

子 agent 只需要三步：
  1. python3 src/worker.py start --agent <你的名字>
     （可选能力声明：--max-risk 1 或 --categories "fraud_scam,travel"）
     → 输出一张工单：任务 id、任务包/规则/输出样例的路径、写回位置
  2. 按工单读任务包 + 写作规则 + 样式参考，为每个 case spec 写一个
     cases/<key>.json（结构照抄输出样例）
  3. python3 src/worker.py done --task <任务id> --agent <你的名字>

注册（register-batch）、判官、入库全部由总控执行，子 agent 不要碰。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_cli import DEFAULT_DB, REPO, claim_task, cmd_complete, connect  # noqa: E402

RULES_FILE = "crime_chat_dataset/prompts/PRM-DIALOGUE-002.md"
FORMAT_EXAMPLE = "crime_chat_dataset/tasks/TASK-0026/cases/b16c018.json"


def _print_workorder(claim_id, row, deadline, as_json=False):
    packet = row["packet_path"]
    n_cases = row["target_count"]
    wo = {
        "task_id": row["task_id"],
        "claim_id": claim_id,
        "lease_deadline": deadline,
        "packet": packet,
        "rules": RULES_FILE,
        "format_example": FORMAT_EXAMPLE,
        "write_to": (f"{packet.rsplit('/', 1)[0]}/cases/<key>.json" if packet else None),
        "expected_cases": n_cases,
        "done_cmd": f"python3 src/worker.py done --task {row['task_id']} --agent <你的名字>",
    }
    if as_json:
        print(json.dumps(wo, ensure_ascii=False, indent=1))
        return
    print("== 工单 ==")
    print(f"任务 id     : {wo['task_id']}（claim={claim_id}，lease 截止 {deadline}）")
    print(f"任务包      : {packet}")
    print(f"  └ 内含 {n_cases} 条 case spec：latent_intent/critical_facts/benign_confusions/"
          "axes/transfer/style_references（样式参考只借鉴手法，禁止抄台词）")
    print(f"写作规则    : {RULES_FILE}   （硬性规则 + 样式参考用法，先读完再动笔）")
    print(f"输出格式样例: {FORMAT_EXAMPLE}")
    print(f"写回位置    : 任务包同目录 cases/<key>.json，每条 spec 一个文件，缺一不可")
    print(f"写完回写    : {wo['done_cmd']}")
    print("注意：不要跑 register/judge，那由总控执行；还活着但快超时就 "
          "python3 src/task_cli.py heartbeat --claim " + str(claim_id))


def cmd_start(conn, args):
    agent = args.agent
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    claim_id, row, deadline = claim_task(conn, agent, args.task, args.lease_seconds,
                                         args.max_risk, categories)
    _print_workorder(claim_id, row, deadline, as_json=args.json)


def cmd_done(conn, args):
    r = conn.execute(
        "SELECT claim_id FROM task_claims WHERE task_id=? AND agent=? AND status='active'",
        (args.task, args.agent)).fetchone()
    if r is None:
        sys.exit(f"任务 {args.task} 没有属于 {args.agent} 的 active claim"
                 "（可能已超时被判死，请重新 start）")
    cases_dir = Path(REPO) / "crime_chat_dataset" / "tasks" / args.task / "cases"
    written = 0
    if cases_dir.exists():
        for f in sorted(cases_dir.glob("*.json")):
            try:
                if json.loads(f.read_text(encoding="utf-8")).get("events"):
                    written += 1
            except Exception:  # noqa: BLE001
                pass
    if written == 0:
        sys.exit(f"{cases_dir} 下没有任何有效产出（含 events 字段），先完成写作再 done；"
                 f"做不完就 python3 src/task_cli.py fail --claim {r['claim_id']} --reason ...")
    ns = argparse.Namespace(claim=r["claim_id"], accepted=written, pairs=0,
                            note=f"worker done: {written} case files written"
                                 + (f"/{args.target} expected" if args.target else ""))
    cmd_complete(conn, ns)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="registry DB 路径（测试用）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start", help="领取任务并打印工单")
    p.add_argument("--agent", required=True)
    p.add_argument("--task", help="指定任务号（默认取最老的 pending）")
    p.add_argument("--max-risk", type=int, help="能力声明：只领包内所有 case risk ≤ N 的任务")
    p.add_argument("--categories", help="能力声明：只领包含这些类目的任务（逗号分隔）")
    p.add_argument("--lease-seconds", type=int, default=7200)
    p.add_argument("--json", action="store_true", help="机器可读输出")
    p = sub.add_parser("done", help="写作完成，回写 claim")
    p.add_argument("--task", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--target", type=int, help="包内期望 case 数（用于备注）")
    args = ap.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    try:
        {"start": cmd_start, "done": cmd_done}[args.cmd](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
