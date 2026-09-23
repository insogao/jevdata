# AGENTS.md — 本仓库所有 AI Agent 的唯一入口

> 任何 Agent（人或 AI）接手工作前**只读这一个文件**即可开工，不依赖任何聊天上下文。
>读完 → 领任务 → 干活 → 回写 → 提交。有问题先查本文第 8 节速查表。

---

## 0. 项目 30 秒

为 **Qwen3.5-9B / Nimble-style System-One 审核模型**构造训练数据（v3 规划见
`spec/planning_v3/隐晦犯罪聊天审核数据集_两阶段多Agent构造计划_v3.md`）。
核心资产是 **CASE-YAML-v1 案例**：多轮聊天 + 转账/资金事件 + 隐含意图，
标签（operational_risk 0-3）在生成文本**之前**由 case_spec 决定。

**当前进度**：Stage 1 种子 143,438 条已入库；Stage 2 精修案例 **200 / 10,000**
（accepted 200 = risk0×35 / risk1×17 / risk2×86 / risk3×56 + 6 条 review 挂起），
contrastive 对照对 30 对。

## 1. 控制平面（谁管什么，不要搞混）

| 事实 | 唯一事实源 | 说明 |
|---|---|---|
| 案例/对照对/ID 计数 | `registry/dataset_registry.sqlite` | cases、pairs、counters、tasks、task_claims 五张表 |
| 任务领取与超时 | 同上 `tasks` + `task_claims` 表 | 通过 `src/task_cli.py` 操作，**禁止直接 UPDATE** |
| 单条案例母数据 | `generated/accepted/CASE-*.yaml` | DB 里 `yaml_path` 指向它（相对路径） |
| 大规模种子 | `sources/normalized/<SRC-ID>/seed.jsonl` | 不进 SQLite |
| 数据源登记 | `registry/source_registry.yaml` | 9 个固定 SRC-ID，license/状态 |
| 进程内互斥 | `registry/orchestrator.lock` | orchestrator 写入时持有 |
| 人读快照 | `registry/id_counters.yaml` | **只是快照**，由 `task_cli.py sync-counters` 生成，别手改 |

## 2. 铁律（违反 = 产出作废）

1. **ID 全部由管线发放**（`CASE-/PAIR-/FAM-/LIN-/ARC-/SEED-/TASK-`），禁止手造、禁止复用；ID 不回收，被拒的号作废。
2. **标签先于文本存在**：先有 case_spec（latent_intent + critical_facts + benign_alternatives），再生成聊天。禁止从聊天反推标签。
3. **导出只读 `conversation` + `labels.risk`**；`hidden_case`、`source`、`lineage` 等元数据禁止进入任何模型 prompt（FORMAT_SPEC.md）。
4. **种子限额**：每颗 `SEED-*` 最多被引用 5 次（`seed_usage.json` 由 orchestrator 维护）。
5. **append-only**：cases/pairs 禁止 UPDATE/DELETE 历史行（状态机字段 `status` 除外）；task_claims 只增不改（active→终态一次）。
6. **去重**：同一对话文本（规范化空白后 sha256）不允许两条 accepted。
7. 单条案例必须**双判官通过**（Fact Judge + Risk Judge），分歧 ≥2 档自动进 review，不得自行改判。

## 3. 任务领取协议（核心机制）

领取记录在 SQLite `tasks`（看板）+ `task_claims`（append-only 审计）里。
**每个任务同一时刻只有一个持有者**（`BEGIN IMMEDIATE` 原子领取）。

```bash
python3 src/task_cli.py list                    # 看板：谁持有哪个任务、剩余时间
python3 src/task_cli.py claim --agent <你的名字> # 领取（默认最老 pending；可 --task TASK-XXXX 指定）
python3 src/task_cli.py heartbeat --claim N     # 还活着但快到期 → 续约
python3 src/task_cli.py complete --claim N --accepted 10 --pairs 2   # 完成
python3 src/task_cli.py fail --claim N --reason "..."                # 做不完，主动交还并写原因
```

**超时语义（重要）**：lease 默认 **2 小时**（`TASK_LEASE_SECONDS` 可改）。
你若断流/崩溃，**没有机会回写失败原因**——lease 到期后，任意后续 `claim/list/reap`
会把你的 claim 判为 `expired`，任务自动放回池子给下一个 Agent。
这不是惩罚，是 by design 的失败信号。所以：

- 领任务前估一下工作量；10 条一包通常远小于 2h，够用。
- 批量长任务定期 `heartbeat`。
- 任务被超时判死 3 次后自动 `abandoned`，等人工处理，不要反复重试同一毒任务——先查它是否缺上下文（如 gated 数据、判官不可用）。
- 每次 claim/complete/fail/expired 都会自动追加到 `report/ORCHESTRATOR_LOG.md`，**日志是机器写的，不要手改**。

## 4. 标准工作流（生成分支）

```bash
# 0. orchestrator 出包（一般由主控做，3 任务 × 10 条 = 一批 30）
python3 src/stage2_orchestrate.py build-packets 3 10 <batch_no> <seed>

# 1. 领取
python3 src/task_cli.py claim --agent <你的名字>     # 假设领到 TASK-0027

# 2. 读任务包
crime_chat_dataset/tasks/TASK-0027/packet.json       # case specs + 生成规则引用
crime_chat_dataset/prompts/PRM-DIALOGUE-001.md       # 对话生成规则（版本化，勿自创）

# 3. 为每个 case spec 写生成结果
#    tasks/TASK-0027/cases/<key>.json，格式照抄同目录已有文件：
#    {key, latent_intent, critical_facts[], benign_alternatives[], events[]}
#    events 元素: {"type":"message"|"transfer", "time":"5月9日 10:20", "speaker":"A", "text":...}

# 4. 注册 + 程序验收（天数/事件一致性、转账互验、risk0 禁可疑转账、元词汇泄漏、content-hash 去重）
python3 src/stage2_orchestrate.py register-batch TASK-0027

# 5. 判官
python3 src/stage2_orchestrate.py judge-inputs TASK-0027        # 导出判官输入
#    分别按 PRM-FACTJUDGE-001 / PRM-RISKJUDGE-001 跑双判官
python3 src/stage2_orchestrate.py compare <risk判官输出.jsonl>   # 分歧≥2档自动进 review

# 6. 回写 + 提交
python3 src/task_cli.py complete --claim <N> --accepted <通过数> --pairs <新增对照对>
git add -A && git commit -m "data: TASK-0027 accepted=+10 pairs=+2"
```

## 5. 验收红线（程序会拦，别挑战）

- risk=0 的案例出现可疑转账 → 拒。
- `has_transfer=true` 但事件流里没有转账（或反之）→ 拒。
- 文本里泄漏 latent_intent / 标签暗示词（元词汇泄漏）→ 拒。
- 与已有 accepted 案例 content-hash 重复 → 拒。
- 对话天数与事件时间戳不自洽 → 拒。
- 被拒的 case_id 作废不回收，修好后走新 spec 重新生成。

## 6. 当前待人工 / 待办看板

- **6 条 review 案例**（judge 分歧 ≥2 档）：`SELECT * FROM cases WHERE status='review'`，需人工终审改 `accepted` 或作废。
- **risk1 配比偏低**（17/200）：出包时注意 TASK spec 的 risk 分布（目标见规划 §4.2）。
- **SRC-WGM-001（WildGuardMix）gated 未下载**：有 HF token 后跑 stage1_download。
- Stage 2 总目标 10,000 条，当前 200 条；对照对 30 对，需随 risky 案例量保持 30-40% 覆盖。

## 7. 目录地图

```
spec/planning_v3/          两阶段规划（深度阅读，含数据源调研/taxonomy/预算）
spec/yaml_demo/            CASE-YAML-v1 格式规范 + 20 条示范
crime_chat_dataset/
  registry/                SQLite + source_registry + seed_usage + id_counters(快照)
  tasks/TASK-*/            任务包（packet.json = specs；cases/*.json = 生成结果）
  generated/accepted/      已验收案例 YAML（核心资产）
  generated/judged/        判官输入/输出
  archetypes/              150 个 archetype
  sources/normalized/      Stage 1 种子（14.3 万条）
  taxonomy/                业务 10 类 + SALAD 66 叶类目
  prompts/                 PRM-DIALOGUE/FACTJUDGE/RISKJUDGE（版本化，禁止直接改，改=新版本号）
src/
  task_cli.py              领取/回写/超时 CLI ←—— 多 Agent 协作入口
  stage2_orchestrate.py    出包/注册/判官比较
  stage2_pipeline.py       case→YAML 渲染 + 程序验收 + 注册
  stage1_*.py              下载/归一化
report/                    ORCHESTRATOR_LOG.md(机器写) + 第一轮验证报告
data/benchmark.jsonl       194 条旧 benchmark（第一轮本地验证用，保留）
```

## 8. 常见问题

| 情况 | 处理 |
|---|---|
| claim 报"已被领取且 lease 未到期" | 换任务，或等 lease 到期后自动回收；不要抢 |
| 我写的 claim 变成 expired | 你超时了，重新 claim 即可；3 次后任务 abandoned |
| 领到的任务包是空的/规格过时 | `fail` 交还并写明原因，让主控重新出包 |
| 需要改 prompt / 验收规则 | 禁止原地改；新版本号（PRM-XXX-002）+ 更新本文与 packet 引用 |
| Windows 路径 / 跨机器 | DB 里 yaml_path 已统一为相对路径；不要写绝对路径入库 |
