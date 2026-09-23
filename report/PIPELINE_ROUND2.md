# 第二轮工作报告：数据工程启动（Stage 1 + Stage 2 Pilot）

> 2026-09-23。依据 `spec/planning_v3/隐晦犯罪聊天审核数据集_两阶段多Agent构造计划_v3.md`
> 与 `spec/yaml_demo/`（CASE-YAML-v1 正式示范版）执行。
> 第一轮本地自测结论已按指示合并为 `report/SELFTEST_ROUND1.md`，旧模型与逐条测试数据已清理（释放 ~66GB）。

## 已完成

### 1. 控制平面（计划 §34-54）
- `crime_chat_dataset/registry/source_registry.yaml`：9 个固定 Source ID 全部登记
  （WGM gated / SCC、CVX restricted / AML 仅登记 / AEG、SAL、BSD、PSD、BCC 已下载）
- `registry/dataset_registry.sqlite`：cases + pairs + counters 表（Stable ID、append-only）
- `registry/id_counters.yaml`、`prompts/PRM-DIALOGUE-001 / FACTJUDGE-001 / RISKJUDGE-001`（版本化）

### 2. Stage 1A 下载（hf-mirror，~1.27GB）
| Source | 状态 | 说明 |
|---|---|---|
| SRC-SAL-001 Salad-Data | ✓ | base+attack set |
| SRC-AEG-001 Aegis 2.0 | ✓ | 25,007 + val/test |
| SRC-BSD-001 BothBosu | ✓ | 1,600 条 |
| SRC-PSD-001 ProsocialDialog | ✓ | train/valid/test |
| SRC-BCC-001 Banking Corpus | ✓ | 1.1GB CSV（300k 会话） |
| SRC-WGM-001 WildGuardMix | gated=auto | 需 HF 账号接受条款，登记未下载 |

### 3. Stage 1B 归一化（弱标签原则，不强拍 0/1/2/3）
| Source | Seeds | 弱标签 |
|---|---:|---|
| SRC-SAL-001 | 21,318 | harmful + 3级类目 |
| SRC-AEG-001 | 28,216 | harmful + violated categories |
| SRC-PSD-001 | 42,304 | casual→needs_intervention 五档 |
| SRC-BCC-001 | 50,000（采样） | benign |
| SRC-BSD-001 | 1,600 | scam/non-scam 原生标签 |
合计 **143,438 seeds**，位于 `sources/normalized/<SRC-ID>/seed.jsonl`。

### 4. Stage 1C/2A：taxonomy + archetypes
- `taxonomy/business_taxonomy_v1.json`：10 个业务一级类
- `taxonomy/source_taxonomy_SALAD.json`：SALAD 6→16→**66 个叶类目**（供 archetype 扩充）
- `archetypes/archetypes.jsonl`：**150 个 archetype**（每类 12-15 个；含 roles/latent_facts/
  observable_signals/benign_confusions/allowed_risk_levels/safety_constraints）

### 5. Stage 2 管线核心（`src/stage2_pipeline.py` + `stage2_pilot.py`）
- case spec → 事件流 → CASE-YAML-v1 渲染（conversation 缩进、导出规则只读
  `conversation` + `labels.risk`）
- 程序验收：天数/事件一致性、has_transfer 与转账事件互相校验、risk0 禁可疑转账、
  元词汇泄漏检查、归一化 content hash
- SQLite registry：case 状态 + contrastive pair（label flip 程序验证）
- **验收曾真实拦截 2 条坏样本**（刷单案写了转账台词但缺内联转账事件），修复后通过——
  说明 acceptance rule 不是摆设

### 6. Pilot 6 条（BATCH-PILOT-001，全部 accepted）
| case | risk | 类别 | 说明 |
|---|---|---|---|
| CASE-0000019 | 3 | bribery_corruption | 设备采购中标当日经中间人转付回扣 |
| CASE-0000020 | 0 | none | **CASE-19 的 contrastive sibling**（同骨架，资金改为对公咨询费，PAIR-0000007 flip 验证通过） |
| CASE-0000021 | 2 | fraud_scam | 刷单返利：小额返→连单垫付→解冻金 |
| CASE-0000022 | 0 | none | **CASE-21 的 contrastive sibling**（正规客服外包+报销，PAIR-0000008） |
| CASE-0000023 | 0 | none | hard negative：老地方/那个数的二手吉他面交 |
| CASE-0000024 | 0 | none | hard negative：新闻制毒案讨论 + 点券代充 |

6 条均通过 Fact Judge（critical facts 全部可指认、无标签泄漏）与 Risk Judge（与 target 一致），
judge 记录在 `generated/judged/pilot_judgements.jsonl`。

## 与目标规模的差距（诚实清单）
- Pilot 500：当前 6/500。对话由会话模型按 PRM-DIALOGUE-001 撰写，**扩量必须接真正的
  生成模型 API**（Orchestrator 循环、Task Packet、Checkpoint 的代码骨架已在管线中，
  但 generate_dialogue 的远程调用、Fact/Risk Judge 的双 Judge 分歧处理尚未接入）
- Stage 1 Broad 30k-50k：seeds 已就绪，`export/broad_train.jsonl` 尚未导出
  （需要先定 Broad 导出 schema：context + weak label 三档）
- WildGuardMix 需要 HF 账号接受条款后才能下载；Scam Corpus / COVA-X 需申请
- 多 Judge（Risk 2/3 双 Judge + Reviewer）、语义去重（embedding 聚类）、coverage dashboard 未建
- 现有 194 条 benchmark 按计划冻结，未参与任何训练/调参

## 下一步优先级
1. 接入生成模型 API，跑 Orchestrator 循环把 pilot 扩到 50-100 条（覆盖 10 个一级类 × risk 0-3 × contrastive）
2. 导出 `broad_train.jsonl` v0（弱标签三档 benign/suspicious/high_risk）
3. Stage 2B 中检：人工抽查自然度与 shortcut（transfer→risk、模糊词→risk）
4. 申请 WildGuardMix / COVA-X 访问
