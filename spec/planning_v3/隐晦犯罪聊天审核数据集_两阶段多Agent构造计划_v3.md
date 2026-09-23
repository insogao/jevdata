# 隐晦犯罪/高风险聊天审核数据集：两阶段数据工程与多 Agent 构造计划（v3）

> 目标：为 Qwen3.5-9B / System-One / Nimble-style 审核模型构造一个以**多轮聊天 + 转账/资金事件 + 隐含意图**为核心的训练与评测数据集。  
> 核心原则：**不让单个生成模型凭空“编犯罪聊天”**。公开数据负责提供风险类型、真实/半真实语言分布、正常金融对话和交易模式；AI 负责把这些结构重新组合成自然中文、多轮、带事件轨迹的数据，并通过独立 Judge 与程序规则验收。

---



# 0. v3 总纲：两阶段数据工程

本项目从 v3 起正式拆成两个数据阶段。两阶段使用同一套 Source ID、Seed ID、Case ID、Registry、任务状态机和版本管理，但**数据目标、质量门槛、标签粒度和生产方式不同**。

```text
Stage 1：Broad / Public Data
公开数据下载、归一化、taxonomy、seed、弱标签
        ↓
建立“广覆盖风险世界”
        ↓
可用于 Broad LoRA 预适配

Stage 2：Curated / Business Data
以上述公开数据和 taxonomy 为基础
        ↓
生成业务化微信 1 对 1 长对话
        ↓
精确 0/1/2/3 + hard negative + contrastive
        ↓
可用于高质量 LoRA 精修
```

两阶段不能混为一个池。

---

## 0.1 Stage 1：公开数据广覆盖准备

### 目标

Stage 1 的任务不是直接得到最终业务训练集，而是：

1. 下载、登记和版本化目前掌握的公开数据；
2. 统一 Source ID / Seed ID；
3. 抽取风险 taxonomy；
4. 抽取案例结构、角色关系、对话推进、资金事件模式；
5. 形成广覆盖的 normalized seed pool；
6. 尽可能保留公开数据原始标签；
7. 对没有精确标签的数据使用粗粒度 weak labels；
8. 为 Stage 2 提供“灵感来源”和 coverage 依据；
9. 可选：导出 Broad LoRA 训练集。

### Stage 1 不追求

Stage 1 不要求每条数据都有精确：

```text
risk = 0 / 1 / 2 / 3
```

如果只能可靠判断：

```text
benign
suspicious
high_risk
```

或者：

```text
review_required = true / false
```

就保持粗标签。

**禁止为了统一格式，让弱 Judge 强行给所有公开数据拍一个精确 0/1/2/3。**

### Stage 1 数据来源

固定 Source ID：

```text
SRC-WGM-001  WildGuardMix
SRC-AEG-001  NVIDIA Aegis 2.0
SRC-SAL-001  SALAD-Bench / Salad-Data
SRC-SCC-001  Scam Conversation Corpus
SRC-CVX-001  COVA-X / ScamLingua
SRC-BSD-001  BothBosu scam-dialogue
SRC-PSD-001  ProsocialDialog
SRC-BCC-001  Banking Conversation Corpus
SRC-AML-001  IBM AMLSim
```

### Stage 1 来源分工

| 来源 | Stage 1 主要职责 |
|---|---|
| WildGuardMix | harmful/benign 边界、adversarial 表达、风险 seed |
| Aegis 2.0 | safety taxonomy、多轮风险结构 |
| SALAD | 最大化风险类别覆盖，构建 taxonomy |
| Scam Conversation Corpus | 真实诈骗对话语言与推进方式 |
| COVA-X | 大规模诈骗对话结构 |
| BothBosu | scam/non-scam 对照与管线测试 |
| ProsocialDialog | 0/1/2 边界与“需要警惕但不违法” |
| Banking Conversation Corpus | 正常金融、付款、转账 hard-negative seed |
| AMLSim | 资金事件与交易 pattern overlay |

### Stage 1 数据输出

建议目录：

```text
stage1_public/
├── sources/
│   ├── source_registry.yaml
│   ├── licenses/
│   └── raw/
├── normalized/
│   ├── SRC-WGM-001/
│   ├── SRC-AEG-001/
│   └── ...
├── seeds/
│   ├── seed_registry.parquet
│   └── seed_registry.jsonl
├── taxonomy/
│   ├── source_taxonomy/
│   └── merged_taxonomy_v1.yaml
├── archetype_seeds/
│   └── archetype_seed_pool.yaml
├── export/
│   ├── broad_train.jsonl
│   └── broad_eval.jsonl
└── report/
    ├── source_coverage.md
    ├── license_status.md
    ├── label_quality.md
    └── taxonomy_gaps.md
```

### Stage 1 推荐规模

第一轮不强求全部公开数据都导入训练。

目标先形成：

```text
30k–50k 可用 Broad examples
```

重点是覆盖：

```text
风险类型
表达方式
正常金融聊天
诈骗推进
资金行为
多轮上下文
长尾类别
```

而不是追求每个来源全部吃完。

### Stage 1 Acceptance

一条 normalized seed 可以进入 Stage 1 accepted pool，需要：

- Source ID 明确；
- Seed ID 唯一；
- 来源许可状态已登记；
- 原始标签保留；
- 归一化过程可追溯；
- 不含真实敏感个人信息；
- 不因翻译/重写而改变原始语义方向；
- 若 weak label 不确定，必须保留 uncertainty；
- 不强制精确 severity。

---

## 0.2 Stage 2：高质量业务数据准备

Stage 2 以 Stage 1 的：

```text
taxonomy
+ source seeds
+ archetype seeds
+ normal financial patterns
+ scam dialogue patterns
+ AML transaction patterns
```

作为输入。

目标不再是“广”，而是：

> **构造真正接近线上业务的微信式 1 对 1 长对话，并精确教会模型风险边界。**

### Stage 2 目标格式

每条母数据统一为一个 YAML：

```yaml
schema_version: CASE-YAML-v1

identity:
  case_id: CASE-...
  family_id: FAM-...
  lineage_id: LIN-...
  archetype_id: ARC-...

source:
  source_ids:
    - SRC-...
  source_seed_ids:
    - SEED-...

labels:
  risk: 2
  category: bribery_corruption
  illicit_likelihood: 2
  evidence_strength: medium
  review_required: true

hidden_case:
  latent_intent: "..."
  critical_evidence:
    - "..."
  benign_alternatives:
    - "..."

attributes:
  duration_days: 4
  approximate_tokens: 2600
  topic_switches: 7
  has_transfer: true

conversation: |-
  【9月12日】

  A：……
  B：……

  【系统消息】A 向 B 转账 800 元，已收款。

  ……
```

训练 exporter 只允许读取：

```python
input_text = sample["conversation"]
target = sample["labels"]["risk"]
```

### Stage 2 的关键要求

必须重点构造：

```text
1 对 1 微信式长聊天
跨数小时 / 数天
1000–8000 token
话题穿插
证据跨距离分布
正常转账 + 可疑转账并存
隐晦表达
共享背景
角色关系
Hard Negative
Contrastive sibling
```

高风险样本不是靠敏感词，而要靠：

```text
角色关系
+ 对价
+ 上下文
+ 时间顺序
+ 资金事件
+ 事前 / 事后确认
```

形成证据闭环。

### Stage 2 推荐规模

第一版：

```text
Pilot      500
验证版    3,000
正式 v1  8,000–12,000
```

正式 v1 建议目标：

```text
10,000 curated cases
```

其中大致：

```text
Risk 0：35%
Risk 1：20%
Risk 2：30%
Risk 3：15%
```

并要求：

```text
30–40% risky/ambiguous cases 有 contrastive sibling
至少约 35% Level-0 属于 hard negative / semi-hard negative
25–35% 样本包含 transfer event
transfer-containing cases 中至少一半不能是高风险 shortcut
```

### Stage 2 Acceptance

一条 case 必须通过：

```text
Case Spec
↓
Dialogue Generator
↓
Fact Judge
↓
Risk Judge
↓
Dedup
↓
Coverage Check
↓
Accepted
```

对 Risk 2/3 建议双 Judge。

---

## 0.3 两阶段与 LoRA 训练的对应关系

数据阶段和 LoRA 阶段直接对应：

```text
Base Qwen3.5-9B
        ↓
Stage 1 Broad Dataset
        ↓
LoRA Stage A：Broad Adaptation
        ↓
保存 adapter_stage_A
        ↓
Stage 2 Curated Dataset
        ↓
LoRA Stage B：Precision Alignment
        ↓
adapter_stage_B
```

建议第一轮消融同时训练：

```text
LoRA-1：只用 Stage 2 curated
LoRA-2：Stage 1 broad → Stage 2 curated
LoRA-3：Stage 1 + Stage 2 混合
```

这样可以真正验证 Stage 1 是否有价值。

Stage 2 精修时建议保留：

```text
10–20% Stage 1 replay
```

防止精品阶段把长尾能力训窄。

---

## 0.4 Stage 1 与 Stage 2 的标签策略不同

### Stage 1

优先可靠粗标签：

```text
category
risk_binary
review_required
benign / suspicious / high-risk
source-native label
```

精确 `risk 0/1/2/3` 不是强制。

### Stage 2

必须有：

```text
risk 0/1/2/3
category
illicit_likelihood
evidence_strength
review_required
```

Stage 2 才是最终 decision boundary 的主要老师。

---

## 0.5 两阶段共享同一控制平面

Stage 1 和 Stage 2 共享：

```text
SQLite Registry
YAML Case Source
Parquet Snapshot
Task Packet
Checkpoint
Versioned Prompt
Stable ID
```

推荐：

```text
SQLite
→ 唯一事实源、任务状态、ID、seed usage、lineage、coverage

YAML
→ Stage 2 单条 case 母数据

Parquet
→ Stage 1 大规模 normalized seed
→ coverage 分析
→ 训练/统计快照
```

不要用 Parquet 承担 task lock，也不要把全部 case 文本塞进 SQLite 当唯一母数据。

---

## 0.6 任务交接规则

任意 Agent 接手时只读取：

```text
registry/
task packet
checkpoint
source registry
schema version
prompt version
```

不得依赖前任 Agent 的聊天上下文。

因此即使：

```text
Agent A → Agent B
GPT → Claude → Qwen
本地 → 云端
```

也可以继续工作。




## 1. 任务背景与目标

实际业务流量中，大部分是正常聊天，少部分是涉及违法违规活动的对话。真正需要识别的高风险对话往往：

- 不直接出现明显犯罪关键词；
- 多轮上下文才能看出意图；
- 参与者彼此有共享背景，常用省略、代词、黑话、模糊指代；
- 风险线索可能来自“聊天 + 转账 + 时间关系”的组合；
- 单句看起来正常，但整段轨迹高风险；
- 某些风险只在“目的”“对价关系”“角色关系”“事件顺序”中体现；
- 很多正常聊天同样会出现“钱、货、东西、搞定、老地方、按之前说的”等模糊表达，因此 hard negative 极其重要。

本项目的目标不是训练“敏感词分类器”，而是训练模型识别：

**多轮上下文中的隐含意图、角色关系、对价关系、资金事件与异常行为组合。**

---

# 2. 核心设计原则

## 2.1 公开数据不是直接拼接训练，而是分工使用

不同公开数据集承担不同角色：

- **安全风险数据集**：提供犯罪/风险 taxonomy、边界案例、行为类型；
- **诈骗对话数据集**：提供多轮骗局的语言节奏、关系推进和社工结构；
- **正常金融/银行对话**：提供大量“涉及钱但完全正常”的 hard negative；
- **AML/交易模拟数据**：提供转账结构和资金事件模式；
- **Prosocial/普通对话安全数据**：提供“可疑但不一定违法”的中间层；
- **AI 自建案例**：只用于补公开数据覆盖不到的业务类型和中文语境。

禁止简单把英文数据机翻后直接作为最终训练主力。

推荐流程：

```text
公开数据
  ↓
抽取：风险类别 / 行为结构 / 角色关系 / 事件结构 / 对话策略
  ↓
Case Spec（隐藏案件卡）
  ↓
中文多轮聊天 + 资金事件重构
  ↓
Contrastive / Hard Negative
  ↓
独立 Judge
  ↓
程序校验
  ↓
训练集
```

## 2.2 标签必须“先于聊天生成”存在

每一条样本必须先创建隐藏 `case_spec`，由它定义真实意图和目标标签，再生成聊天。

禁止：

```text
生成聊天
→ 同一个模型读一遍
→ 自己给自己打标签
```

必须：

```text
case_spec 先定义 label
→ generator 只负责生成自然聊天
→ judge 独立验证是否符合 case_spec
→ 程序决定是否接受/丢弃
```

## 2.3 不把“犯罪严重性”和“证据强度”混成一个变量

建议保留多个标签：

- `operational_risk`: 线上最终风险等级 0/1/2/3
- `illicit_likelihood`: 对话确实涉及违法/违规活动的可信程度
- `evidence_strength`: weak / medium / strong
- `offense_type`: 风险类型
- `transfer_relevance`: none / weak / medium / strong
- `review_required`: bool
- `intent_stage`: probe / negotiate / execute / pay / aftermath / unclear

其中 `operational_risk` 用于主训练目标，其余用于：
- 多字段 System-One；
- 误差分析；
- 数据质检；
- 后续二阶段模型或人工复核。

---

# 3. 推荐公开数据集

## 3.1 WildGuardMix

**用途：风险类别 seed、adversarial 表达、harmful/benign 边界。**

来源：
- Hugging Face: https://huggingface.co/datasets/allenai/wildguardmix

公开信息：
- WildGuardTrain 约 86,759 examples；
- 约 87% synthetic，11% in-the-wild user-LLM interactions，2% annotator-written；
- 包含 vanilla / adversarial harmful 与 benign prompts；
- 带 prompt harmfulness、response harmfulness、refusal 等标签。

在本项目中不要直接当“犯罪聊天数据”，而是抽取：

```text
风险类别
隐晦表达方式
规避表达
边界案例
benign vs harmful 对照结构
```

推荐作用权重：**15% primary seed origin**

## 3.2 NVIDIA Aegis 2.0

**用途：安全 taxonomy、复杂风险类别、multi-turn safety 标注结构。**

来源：
- Hugging Face: https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0

公开信息：
- 约 25,007 个 user prompts / prompt-response / multi-turn samples；
- validation 1,245，test 1,964；
- 另含约 5,000 refusal samples；
- 有额外 Topic-Following 数据；
- License: CC-BY-4.0。

本项目主要用它：
- 补充风险 taxonomy；
- 提取“普通表述但含高风险语义”的结构；
- 提取多轮场景中的风险判定方法。

推荐作用权重：**10% primary seed origin**

## 3.3 SALAD-Bench / Salad-Data

**用途：最大化风险类型多样性，防止生成器只想到少数犯罪套路。**

来源：
- GitHub: https://github.com/OpenSafetyLab/SALAD-BENCH
- Hugging Face: https://huggingface.co/datasets/OpenSafetyLab/Salad-Data

公开信息：
- 21,318 base harmful questions；
- 6 个一级领域；
- 16 个二级任务；
- 约 65–66 个细粒度类别；
- Apache-2.0；
- 还有 attack-enhanced / defense-enhanced variations。

本项目不直接把 harmful question 当聊天，而是抽取：

```text
6 → 16 → 65/66 三级 taxonomy
```

再映射成业务相关的：

```text
违法交易
诈骗
腐败/利益输送
隐私侵害
暴力威胁/策划
性交易/剥削
违禁品交易
洗钱/资金掩饰
敲诈/勒索
盗窃/抢劫相关
其他高风险活动
```

推荐作用权重：**15% primary seed origin**

## 3.4 Scam Conversation Corpus

**用途：真实骗子对话的语言节奏和多平台沟通方式。**

来源：
- Zenodo: https://zenodo.org/records/15212527

说明：
- Restricted dataset；
- conversations with scammers；
- 由 GPT-4o honeypot 与真实诈骗者互动采集；
- 可能跨多个 communication platforms；
- 需按其访问要求申请。

价值不在“直接拿原文训练”，而在于分析：
- 如何建立信任；
- 如何逐步推进要求；
- 如何模糊表达目的；
- 如何从正常聊天过渡到资金要求；
- 如何在对方怀疑时调整话术；
- 多平台迁移的上下文结构。

如果获得访问权限，推荐作用权重：**10% primary seed origin**

若无权限，则由 COVA-X + BothBosu 替代。

## 3.5 COVA-X / ScamLingua

**用途：大规模、多轮、带结构 metadata 的诈骗对话 seed。**

来源：
- https://scamlingua.org/

公开信息：
- 约 11,000 条 synthetic English multi-turn scam conversations；
- 完全 synthetic；
- 由 Qwen 2.5 14B 本地生成；
- 带 scam_type、outcome_label、turn count、victim parameters 等 metadata；
- 需要申请；
- 明确限制为 defensive research / detection / prevention 等用途。

本项目使用方式：
- 不直接复制文本；
- 读取其 scam type / progression / outcome structure；
- 映射成中文社交聊天的 case spec；
- 与正常聊天 hard negative 配对。

推荐作用权重：**10% primary seed origin**

## 3.6 BothBosu / scam-dialogue

**用途：容易获取的小规模多轮 scam / non-scam seed。**

来源：
- https://huggingface.co/datasets/BothBosu/scam-dialogue

公开信息：
- 约 1,600 条；
- synthetic multi-turn phone conversations；
- scam / non-scam binary；
- scam types 包括 SSN/refund/support/reward；
- non-scam 包括 delivery/insurance/telemarketing/wrong number；
- Apache-2.0。

用途：
- 测试数据管线；
- 抽取“同一风格下 scam 与 benign 的对照结构”；
- 不作为主要犯罪多样性来源。

推荐作用权重：**5% primary seed origin**

## 3.7 ProsocialDialog

**用途：多轮安全边界和“需要警惕但未必违法”的中间风险层。**

来源：
- https://huggingface.co/datasets/allenai/prosocial-dialog

公开信息：
- 58K dialogues；
- 331K utterances；
- 497K safety labels；
- safety levels 包括 casual / possibly_needs_caution / probably_needs_caution / needs_caution / needs_intervention；
- CC-BY-4.0。

本项目主要用于：
- Level 0 / Level 1 / Level 2 边界；
- 构造“可疑、令人不适、需要关注，但不应直接判定犯罪”的样本；
- 防止模型把一切异常语言都推到高风险。

推荐作用权重：**10% primary seed origin**

## 3.8 Banking Conversation Corpus

**用途：大规模正常金融/转账 hard negative。**

来源：
- https://huggingface.co/datasets/talkmap/banking-conversation-corpus

公开信息：
- 约 300,000 个 synthetic conversations；
- 5.53M utterance rows；
- MIT；
- 包含大量 bills、payments、account、refund、transfer、identity 等金融语言。

注意其 dataset card 文案中存在“banking / telecom”表述不完全一致，使用前由 agent 实际抽样确认内容分布。

本项目最重要用途：

```text
出现“钱、付款、账户、转账、退款”等词
≠ 犯罪
```

用于构建：
- 正常转账；
- 报销；
- 垫付款；
- 购买服务；
- 退款；
- 借款归还；
- 商务结算；
- 家庭转账；
- 正常佣金；
- 正常项目付款。

推荐作用权重：**15% primary seed origin**

## 3.9 IBM AMLSim

**用途：提供资金事件结构，而不是提供聊天文本。**

来源：
- https://github.com/IBM/AMLSim

AMLSim 用于生成 synthetic banking transaction data 和已知 money-laundering patterns 的 multi-agent simulator。

本项目中不要把 AMLSim 当“文本数据集”。

它的作用是为聊天生成器提供：

```text
转账次数
金额级别
时间间隔
付款前后顺序
多主体资金链
资金拆分/聚合的抽象模式
```

这些事件结构可以 overlay 到：
- 高风险聊天；
- 可疑但不确定聊天；
- 完全正常聊天。

推荐作用：**10% transaction-pattern overlay**

注意：该 10% 不与 primary seed origin 严格互斥；它是额外的事件结构层。

---

# 4. 推荐最终训练集比例

## 4.1 第一版目标规模

建议先做：

**8,000–12,000 条高质量 case**

第一版建议 10,000 条。

## 4.2 按 operational_risk 分布

| Risk | 比例 | 目标 |
|---|---:|---|
| 0 | 35% | 正常聊天、正常转账、hard negative |
| 1 | 20% | 可疑但证据不足、正常解释仍充分 |
| 2 | 30% | 多线索相互印证，高风险 |
| 3 | 15% | 意图基本明确、证据高度一致 |

这不是线上真实分布。

线上 calibration / shadow-test 集必须尽量接近真实流量分布。

## 4.3 按 primary seed origin 分布

| Primary Seed | 比例 |
|---|---:|
| SALAD / WildGuard / Aegis 风险 taxonomy 派生 | 35% |
| Scam Conversation / COVA-X / BothBosu | 20% |
| Banking / Prosocial hard negatives | 25% |
| 自建业务 gap cases | 20% |

AMLSim 作为 orthogonal overlay：
- 约 25–35% 全体样本加入 transaction events；
- 其中不能只给 risky case 加转账；
- 至少一半 transaction-containing samples 应来自 benign / ambiguous cases。

这样防止模型学成：

```text
出现 transfer event → 高风险
```

---

# 5. 第一版业务 Risk Taxonomy

建议总控 Agent 首先从 SALAD / WildGuard / Aegis 提取完整 taxonomy，然后映射到业务 taxonomy。

第一版业务顶层可以包括：

1. `fraud_scam`
2. `bribery_corruption`
3. `contraband_illicit_trade`
4. `violence_extortion`
5. `sexual_transaction_exploitation`
6. `privacy_doxxing`
7. `money_laundering_obfuscation`
8. `theft_robbery_property_crime`
9. `coercion_blackmail`
10. `other_illicit_coordination`

每个一级类再拆成 5–20 个 `case_archetype`。

目标：

**至少 150 个 archetype，理想 250–400 个。**

注意：
- archetype 描述应聚焦“角色关系、事件模式、对话证据和正常混淆项”；
- 不记录可操作的犯罪技巧；
- 不生成现实可执行的规避执法方案；
- 不记录具体实施步骤。

---

# 6. Case Archetype 数据结构

```json
{
  "archetype_id": "bribery_intermediary_001",
  "top_category": "bribery_corruption",
  "subtype": "intermediary_benefit_exchange",
  "roles": ["beneficiary", "intermediary", "decision_influencer"],
  "latent_facts": [
    "存在利益交换",
    "付款与某项结果存在语义关联",
    "至少一方有意避免直接说明付款目的"
  ],
  "observable_signals": [
    "前后文出现结果/事情完成后的付款暗示",
    "角色之间存在共享背景",
    "支付事件在关键对话附近发生"
  ],
  "benign_confusions": [
    "合法服务费",
    "垫付款归还",
    "正常佣金",
    "项目结算"
  ],
  "allowed_risk_levels": [1, 2, 3],
  "safety_constraints": {
    "no_operational_crime_instructions": true,
    "no_real_personal_data": true,
    "no_real_account_numbers": true
  }
}
```

---

# 7. Case Spec：每一条样本生成前必须存在

每个子 Agent 不允许直接“自由创作聊天”。

先从 archetype 生成隐藏 `case_spec`：

```json
{
  "case_id": "case_0001823",
  "family_id": "family_00491",
  "archetype_id": "bribery_intermediary_001",
  "target_labels": {
    "operational_risk": 2,
    "illicit_likelihood": 2,
    "evidence_strength": "medium",
    "offense_type": "bribery_corruption",
    "transfer_relevance": "strong",
    "review_required": true
  },
  "roles": {"A": "role_1", "B": "role_2"},
  "conversation_stage": "payment",
  "style_axes": {
    "relationship": "熟人",
    "register": "微信口语",
    "verbosity": "low",
    "obfuscation": "high",
    "turn_count": 18,
    "noise_ratio": 0.35
  },
  "event_plan": {
    "has_transfer": true,
    "transfer_position": "after_key_exchange",
    "normal_side_topics": 2
  },
  "critical_facts": ["关键事实1", "关键事实2"],
  "contrastive_target": {
    "enabled": true,
    "flip_fact": "payment_purpose",
    "target_risk_after_flip": 0
  }
}
```

---

# 8. 对话事件统一格式

不要只存拼接文本。

统一保存为 event stream：

```json
{
  "events": [
    {
      "event_id": 1,
      "time": "10:31",
      "type": "message",
      "speaker": "A",
      "text": "..."
    },
    {
      "event_id": 2,
      "time": "10:35",
      "type": "transfer",
      "from": "A",
      "to": "B",
      "amount_bucket": "medium",
      "status": "received"
    },
    {
      "event_id": 3,
      "time": "10:36",
      "type": "message",
      "speaker": "B",
      "text": "..."
    }
  ]
}
```

建议只使用 synthetic amount / amount bucket / synthetic IDs，禁止真实个人信息。

---

# 9. 数据多样性控制轴

每个 case 由程序随机抽取多个变化轴，而不是让 LLM 自己想。

### 人际关系
- 陌生人
- 熟人
- 同事
- 上下级
- 商务关系
- 亲友
- 中间人关系

### 对话阶段
- 初次试探
- 建立信任
- 协商
- 等待结果
- 付款
- 事后确认
- 善后
- 中途取消

### 隐晦程度
- low
- medium
- high
- extreme

### 聊天长度
- 6–10 turns
- 11–20 turns
- 21–40 turns
- 40+ turns

### 语言风格
- 微信短句
- 商务口语
- 年轻人口语
- 极简回复
- 中英混合
- 错别字/口语缩写
- 方言感（适度，不使用固定地域刻板印象）

### 信息缺失
- 不说对象
- 不说用途
- 不说金额
- 不说时间
- 用代词/共享背景
- 多次省略主语

### 干扰信息
- 工作闲聊
- 家庭话题
- 吃饭/出行
- 正常转账
- 报销
- 购物
- 日常抱怨
- 语音/图片占位

---

# 10. Contrastive Pair 设计

至少 **30–40% risky/ambiguous cases** 应有 contrastive sibling。

原则：
- 绝大多数聊天保持一致；
- 只改变一个决定性事实；
- label 应明显翻转或降低；
- 不靠敏感词删除来翻转；
- 允许改 1–2 个 event 或关键上下文事实。

必须保存：

```json
{
  "pair_id": "pair_00931",
  "focus_fact": "payment_purpose",
  "source_case": "case_001",
  "contrastive_case": "case_002"
}
```

---

# 11. Hard Negative 计划

Hard Negative 是本项目核心。

至少 35% Level-0 样本应满足：

```text
包含表面可疑元素
但整体属于正常行为
```

建议覆盖：
- 正常转账 + 模糊短句；
- 垫付款归还；
- 私人借款；
- 二手交易；
- 合法佣金；
- 报销；
- 商务款项；
- 家庭汇款；
- 正常退款；
- 合法服务费；
- 项目尾款；
- 朋友代买；
- 新闻/历史事件讨论；
- 游戏/小说中的犯罪描述；
- 对过去犯罪事件的转述而非参与。

目标是阻止模型学成：

```text
钱 + 模糊表达 = 犯罪
```

---

# 12. Multi-Agent 总体执行架构

建议一个 Orchestrator 不断分派小批次任务：

```text
Orchestrator
   │
   ├── Source Agent
   ├── Taxonomy Agent
   ├── Archetype Agent
   ├── Case-Spec Agent
   ├── Dialogue Generator Agent
   ├── Contrastive Agent
   ├── Fact Judge
   ├── Risk Judge
   ├── Diversity/Dedup Agent
   └── Export Agent
```

---

# 13. 子 Agent 每批只处理 5–10 条

推荐：

```text
Case-Spec Agent：10 specs / call
Dialogue Agent：5 cases / call
Contrastive Agent：5 pairs / call
Judge Agent：10 cases / call
```

不要让一个 Agent 一次生成 100 条。

---

# 14. Orchestrator 工作循环

```text
1. 查看 taxonomy coverage
2. 找当前最缺的 category / archetype / risk level / style
3. 分配 5–10 个 case_spec
4. 调 Dialogue Agents 生成
5. 调 Contrastive Agents 生成 sibling
6. 调 Fact Judge
7. 调 Risk Judge
8. 程序规则验收
9. Dedup
10. 写入 accepted/
11. 更新 coverage dashboard
12. 重复
```

总控禁止只按固定顺序批量生成，应该优先补 coverage 最差的格子。

---

# 15. 子 Agent 输出协议

每个子 Agent 必须输出 JSONL，不要自然语言解释。

### Dialogue Generator 输出

```json
{
  "case_id": "...",
  "events": [...],
  "generator_metadata": {
    "model": "...",
    "agent_id": "...",
    "batch_id": "..."
  }
}
```

Agent 无权修改：

```text
target_labels
archetype_id
critical_facts
contrastive_target
```

---

# 16. Fact Judge

Fact Judge **不看 target label**。

只回答事实：

```json
{
  "case_id": "...",
  "facts": {
    "shared_background": true,
    "money_event_present": true,
    "money_event_semantically_related": true,
    "normal_explanation_strength": "medium",
    "intent_is_implicit": true,
    "critical_fact_1_present": true,
    "critical_fact_2_present": true
  },
  "evidence_event_ids": [2, 5, 7],
  "confidence": 0.87
}
```

Fact Judge 不输出最终 risk。

---

# 17. Risk Judge

Risk Judge 输入：
- events
- risk rubric

不输入：
- generator 的 target label
- hidden_case 真相

输出：

```json
{
  "operational_risk": 2,
  "illicit_likelihood": 2,
  "evidence_strength": "medium",
  "offense_type": "bribery_corruption",
  "review_required": true,
  "confidence": 0.81
}
```

---

# 18. Acceptance Rule

一条样本只有在以下条件全部满足时才能进入 accepted：

1. Fact Judge 确认 critical facts 存在；
2. 生成文本没有泄漏 hidden_case 或标签；
3. Risk Judge 与 target label 一致，或只在允许容差内偏差；
4. 对话自然度达标；
5. 没有重复模板；
6. 没有真实 PII；
7. 没有生成可直接用于实施犯罪的操作性教程；
8. contrastive pair 的 label flip 得到验证；
9. `family_id` 与 split 规则一致。

不满足则 reject。原则上优先丢弃，而不是人工强改 label。

---

# 19. 多 Judge 机制

对 Risk 2/3 样本建议：
- Judge A
- Judge B

都通过才 accepted。

若 disagreement：

```text
→ Reviewer Agent
```

Reviewer Agent 只能：
- accept target
- downgrade
- reject

不能重新生成内容。

对 Risk 0/1 可使用单 Judge + 随机抽检。

---

# 20. Dedup / Diversity 检查

至少三层：

### Exact
- normalized hash

### Lexical
- n-gram Jaccard
- 重复短语统计

### Semantic
- embedding cosine similarity

建议：
- 高相似 case 只保留一个；
- contrastive pair 例外，但必须有 pair_id；
- 监控高频模板词；
- 发现 synthetic watermark 后，降低对应模板权重。

重点监控是否过度使用：

```text
“按之前说的”
“老地方”
“那个事情”
“你懂的”
“剩下的之后再说”
```

不是禁用，而是避免它们变成 shortcut。

---

# 21. Coverage Dashboard

总控持续维护：

```text
category × subtype
risk level
conversation stage
relationship
obfuscation level
turn length
has_transfer
transfer_relevance
language style
contrastive status
source origin
```

推荐输出：

```text
report/coverage.csv
report/coverage_gaps.md
```

---

# 22. Train / Calibration / Test 切分

禁止随机 row split。

必须按照：

```text
family_id
archetype family
source family
```

做 group split。

同一个 contrastive pair 必须始终在同一 split。

推荐：

```text
train        80%
calibration  10%
test         10%
```

另外保留现有 194 条 benchmark：

**永久冻结，不允许参与训练、prompt tuning、temperature tuning。**

---

# 23. 测试集额外要求

至少两套：

## Test-Hard
风险类别较均衡，专门测能力。

## Test-Natural
尽量模拟真实线上分布，用于测：
- false positive
- precision
- alert volume
- calibration
- threshold

---

# 24. Nimble / System-One 导出格式

训练阶段只把：

```text
events
+ schema
```

给模型。

隐藏字段不能进 prompt。

主任务建议：

```text
Question:
综合整段聊天和事件轨迹，风险等级是什么？

A = 0
B = 1
C = 2
D = 3
```

辅助字段可以保留：
- illicit likelihood
- transfer relevance
- review required
- offense category

第一轮 LoRA 先以主风险等级为核心，减少变量。

---

# 25. 第一版 10K 数据生产预算

建议：

```text
3,500  Risk 0
2,000  Risk 1
3,000  Risk 2
1,500  Risk 3
```

其中：

```text
2,500–3,500 cases 含 transfer event
3,000–4,000 cases 属于 contrastive family
至少 3,500 Level-0 是 hard negative 或 semi-hard negative
```

这些集合允许重叠。

---

# 26. 两阶段长任务执行顺序（v3）

> 本节取代 v2 的 Phase 0–6 线性定义。

## Stage 1A：Source Ingestion

- 建立 `source_registry.yaml`
- 下载/申请可访问来源
- 保存 license / access restriction
- 给每条源数据分配 deterministic `SEED-*`
- 不改动原始文件

## Stage 1B：Normalization

- 转统一 normalized schema
- 保留 source-native labels
- 中文化时优先抽取结构，不直接机翻为最终业务训练文本
- 写入 provenance 和转换版本

## Stage 1C：Taxonomy / Seed Pool

- 各来源独立抽 taxonomy
- 合并去重
- 建立 business taxonomy
- 建立 archetype seed pool
- 建 coverage dashboard

## Stage 1D：Broad Dataset Export

目标先导出：

```text
30k–50k broad examples
```

允许 weak label。

冻结：

```text
stage1_public_v1
```

之后才进入可选 Broad LoRA Stage A。

---

## Stage 2A：Archetype Construction

从 Stage 1 的 taxonomy 和 seed pool 生成：

```text
150 minimum
250 target
400 stretch
```

个业务 archetype。

## Stage 2B：Pilot 500

生成 500 条长对话 YAML。

人工/高级 Judge 检查：

- 自然度
- 长上下文
- 话题穿插
- 转账 shortcut
- 风险边界
- hard negative
- synthetic watermark

不通过则停止扩量。

## Stage 2C：Scale to 3K

达到 3K 后做一次 zero-shot / 小 LoRA 验证。

重点检查：

```text
transfer → risk
模糊词 → risk
长对话 → risk
某 generator 风格 → risk
```

是否成为 shortcut。

## Stage 2D：Scale to 10K

Orchestrator 根据 coverage gap 定向补齐，不平均撒点。

冻结：

```text
stage2_curated_v1
```

## Stage 2E：Split

按 family / lineage / source family group split：

```text
train
calibration
test_hard
test_natural
```

现有历史 194 条 benchmark 永久冻结，不进入训练。

## Stage 2F：Training Export

从 YAML 母数据导出：

```text
Nimble
Decider
SFT
其他 classifier
```

格式。

原始 YAML 永不为了某个训练框架修改。

## Stage 2G：LoRA 消融

正式训练至少比较：

```text
Curated-only
Broad → Curated
Broad + Curated mixed
```

BF16 先评测，再做量化阶梯：

```text
Q8 / Q6 / Q5 / Q4
```


# 27. 目录结构

```text
crime_chat_dataset/
├── README.md
├── sources/
│   ├── manifest.json
│   ├── raw/
│   └── normalized/
├── taxonomy/
│   ├── source_*.json
│   └── business_taxonomy_v1.json
├── archetypes/
│   └── archetypes.jsonl
├── case_specs/
│   ├── pending/
│   ├── accepted/
│   └── rejected/
├── generated/
│   ├── raw/
│   ├── judged/
│   ├── accepted/
│   └── rejected/
├── pairs/
│   └── contrastive.jsonl
├── splits/
│   ├── train.jsonl
│   ├── calibration.jsonl
│   ├── test_hard.jsonl
│   └── test_natural.jsonl
├── export/
│   ├── nimble_train.jsonl
│   └── nimble_eval.jsonl
└── report/
    ├── coverage.csv
    ├── coverage_gaps.md
    ├── source_stats.md
    ├── judge_agreement.csv
    ├── dedup_stats.md
    └── final_dataset_card.md
```

---

# 28. `sources/manifest.json` 必填字段

```json
{
  "name": "WildGuardMix",
  "url": "https://huggingface.co/datasets/allenai/wildguardmix",
  "license": "CHECK_DATASET_CARD",
  "access": "public",
  "role": ["taxonomy", "risk_seed"],
  "direct_training_use": false,
  "notes": "used primarily as structural seed"
}
```

所有来源在使用前必须实际核对 license 和使用限制。

Restricted / research-only 数据不允许擅自转入商业训练集。

---

# 29. 安全约束

这是 defensive detection 数据项目。

所有生成 agent 必须遵守：

- 不生成现实可直接执行的犯罪教程；
- 不生成规避侦查/执法的操作步骤；
- 不生成真实个人信息；
- 不生成真实账号、电话、地址、银行卡；
- 不需要描述具体制备、武器、入侵、逃避检测的方法；
- 高风险样本重点表现“关系、意图、对价、时间、资金、隐晦表达”，而不是实施细节；
- 如果 source 中有可操作危险细节，在归一化阶段抽象化。

---

# 30. 子 Agent 通用任务模板

每次 Orchestrator 分发任务时，必须包含：

```text
TASK_TYPE:
BATCH_ID:
INPUT_FILES:
TARGET_COUNT: 5-10

TARGET_CATEGORY:
TARGET_RISK_LEVELS:
TARGET_STYLE_AXES:
TARGET_SOURCE_ORIGIN:

OUTPUT_SCHEMA:
OUTPUT_PATH:

CONSTRAINTS:
- Do not change target labels.
- Do not reveal hidden case metadata in dialogue.
- Do not add real personal data.
- Do not include operational criminal instructions.
- Avoid common synthetic clichés unless specifically required.
- Return JSONL only.

QUALITY_GATE:
...
```

---

# 31. Orchestrator 停止条件

不是“生成到 10,000 就结束”。

只有同时满足才结束：

1. accepted ≥ target count；
2. 所有一级风险类别都有足够覆盖；
3. 主要 archetype 没有明显空洞；
4. Level 0 hard negatives 足够；
5. transfer / non-transfer 都有覆盖；
6. contrastive coverage 达标；
7. Judge agreement 达标；
8. dedup rate 不再异常升高；
9. Test-Hard 与 Test-Natural 均冻结；
10. Dataset Card 完成。

---

# 32. 推荐第一轮关键指标

数据质量：

```text
Judge agreement
Reject rate
Duplicate rate
Contrastive flip success
Category coverage
Risk balance
Transfer balance
```

模型指标：

```text
accuracy
macro-F1
FN risk>=2
FN risk==3
catastrophic FN
false positive rate
ECE
Brier
contrastive-pair exact accuracy
```

最重要：

```text
FN risk>=2
catastrophic FN
false positive under natural distribution
```

---

# 33. 总体建议

不要把项目理解成：

```text
“让 AI 生成 10,000 条犯罪聊天”
```

应该理解成：

```text
“建立 250+ 案件 archetypes
× 多维变化轴
× 正常混淆项
× 转账事件结构
× contrastive siblings
× 独立 Judge
→ 得到 10,000 条高质量案件轨迹”
```

真正的资产不是那 10,000 条文本，而是：

```text
taxonomy
+ archetypes
+ case generator
+ judge pipeline
+ coverage dashboard
```

一旦这套生产线稳定，以后可以持续生成 50K、100K，并且根据模型错误自动补充新的 case family，而不会再次陷入“同一个 prompt 生成一堆大同小异聊天”的模式。


---

# 34. 控制平面：唯一编码、Registry、任务交接与幂等执行

> 本节为 v2 的强制执行规范。目标是：无论更换 Agent、模型、Prompt、机器、执行批次，任务都能从磁盘状态继续运行，而不依赖任何聊天上下文或某个 Agent 的“记忆”。

## 34.1 核心原则

整个数据工程必须遵守四条原则：

1. **Stable ID**：任何可复用实体一旦创建 ID，永久不变。
2. **Registry is truth**：Registry 是唯一事实来源，不以聊天记录、Agent 记忆或临时描述为准。
3. **Append-only provenance**：生成历史、Judge 历史、模型版本、Prompt 版本只追加，不覆盖。
4. **Idempotent task**：同一个任务重复执行不会产生未追踪的重复数据；每个任务必须有 `task_id` 与 `idempotency_key`。

---

# 35. ID Namespace 规范

统一采用以下 namespace：

```text
SRC-xxxx      公开/私有数据来源
SEED-xxxx     来源中的一条 seed
TAX-xxxx      taxonomy 节点
ARC-xxxx      case archetype
FAM-xxxx      case family
LIN-xxxx      lineage / 血缘树
CASE-xxxx     最终/候选 case
PAIR-xxxx     contrastive pair
BATCH-xxxx    批次
TASK-xxxx     子 Agent 任务
AGT-xxxx      Agent 身份
MOD-xxxx      模型/推理端版本
PRM-xxxx      Prompt 版本
JDG-xxxx      Judge 配置
EXP-xxxx      exporter 版本
RUN-xxxx      一次具体执行
```

ID 不编码可变业务含义，避免后续重命名导致 ID 失效。显示名、类别等放在 metadata。

---

# 36. 当前公开数据来源的固定 Source ID

以下 Source ID 从 v2 起固定，不允许后续 Agent 自行重命名：

| Source ID | 数据源 | 主要用途 | 默认 direct training |
|---|---|---|---|
| `SRC-WGM-001` | WildGuardMix | 风险 taxonomy、adversarial/benign 边界 | false |
| `SRC-AEG-001` | NVIDIA Aegis 2.0 | safety taxonomy、多轮安全边界 | false |
| `SRC-SAL-001` | SALAD-Bench / Salad-Data | 扩展风险类别、case seed | false |
| `SRC-SCC-001` | Scam Conversation Corpus | 真实诈骗语言结构与推进节奏 | false / 受访问限制 |
| `SRC-CVX-001` | COVA-X / ScamLingua | 多轮诈骗结构、诈骗类型 seed | false / 需核许可 |
| `SRC-BSD-001` | BothBosu scam-dialogue | 小规模 scam/non-scam seed、管线验证 | false |
| `SRC-PSD-001` | ProsocialDialog | Level 0/1/2 边界、社会风险 hard negative | false |
| `SRC-BCC-001` | Banking Conversation Corpus | 正常金融/转账 hard negative | false |
| `SRC-AML-001` | IBM AMLSim | 资金事件结构 overlay | false |

后续新增来源必须由 Orchestrator 分配新的 `SRC-*`，并先写入 `sources/source_registry.yaml`，再允许子 Agent 使用。

---

# 37. Source Seed 唯一编码

每条公开数据或外部 seed 必须映射成唯一 `seed_id`。

推荐 deterministic 方案：

```text
SEED-{source_id}-{source_native_key}
```

例如：

```text
SEED-SRC-WGM-001-train-00018372
SEED-SRC-SAL-001-base-00001277
```

若来源没有稳定 row id，则使用标准化内容哈希前 16 位：

```text
SEED-SRC-XXX-001-{sha256(normalized_source_text)[:16]}
```

同一 seed 的派生数量必须可统计。

默认限制：

```text
accepted descendants per seed <= 5
```

若某个 seed 需要超过限制，必须由 Orchestrator 明确写入 override 原因。

---

# 38. Case 身份与血缘

每个 case 至少必须具有：

```yaml
identity:
  case_id: CASE-000001823
  family_id: FAM-00000491
  lineage_id: LIN-00000931
  archetype_id: ARC-00000117
  variant_id: v03
```

含义：

- `case_id`：每条数据唯一。
- `family_id`：同一个“案件母题”的所有变体共享。
- `lineage_id`：从同一个 root/seed 派生的改写、contrastive、长上下文版共享。
- `archetype_id`：更高层的案件结构模板。
- `variant_id`：该 family 内的变体编号。

同时保存：

```yaml
lineage:
  parent_case_id: CASE-000001817
  root_case_id: CASE-000001751
  source_seed_ids:
    - SEED-SRC-SAL-001-base-00001277
  generation_type: contrastive
```

---

# 39. Generation Signature：控制覆盖与防止类型过量

每个 case 必须计算一个结构签名：

```yaml
generation_signature:
  top_category: bribery_corruption
  subtype: intermediary_payment
  risk: 2
  token_bucket: 2k_4k
  duration_bucket: 3_7_days
  relationship: business
  obfuscation: high
  topic_switch_bucket: high
  has_transfer: true
  suspicious_transfer: true
  normal_transfer: true
```

Orchestrator 每次分配任务前必须先查询 signature coverage。

如果某个 signature 已明显过量，则禁止继续生成同类，除非目标是专项补强。

---

# 40. Content Hash 与 Semantic Cluster

每个 accepted case 至少保存：

```yaml
dedup:
  content_hash: sha256:...
  normalized_hash: sha256:...
  semantic_cluster_id: SCL-00000271
```

三层去重：

```text
exact hash
→ 完全重复

normalized hash
→ 仅标点/日期/格式不同

semantic cluster
→ 换词但结构高度相似
```

Contrastive siblings 允许高语义相似，但必须有相同 `pair_id` 和清晰 `focus_fact`。

---

# 41. Agent、模型、Prompt 必须有版本 ID

不允许只写“GPT”“Claude”“Qwen”。

每次生成必须记录：

```yaml
execution:
  agent_id: AGT-DIALOGUE-007
  model_id: MOD-OPENAI-XXXX-001
  prompt_id: PRM-DIALOGUE-003
  judge_config_id: JDG-RISK-002
  workflow_version: DATASET-WF-v2.0
  run_id: RUN-20260923-000187
  batch_id: BATCH-20260923-018
```

Prompt 文件必须独立版本化：

```text
prompts/
  PRM-CASESPEC-001.md
  PRM-DIALOGUE-001.md
  PRM-DIALOGUE-002.md
  PRM-FACTJUDGE-001.md
  PRM-RISKJUDGE-001.md
```

Prompt 改变时创建新版本，不覆盖旧版本。

这允许后续分析：

```text
不同模型
不同 Prompt
不同 Agent
```

是否产生不同风格或不同数据质量。

---

# 42. Canonical Registry

建议使用 SQLite 作为唯一主 Registry，同时导出 CSV/JSON 供人工检查。

主库：

```text
registry/dataset_registry.sqlite
```

建议核心表：

```text
sources
seeds
taxonomy_nodes
archetypes
families
lineages
cases
pairs
tasks
runs
agents
models
prompts
judgements
exports
```

CSV 只是 snapshot，不是写入主库。

---

# 43. Case 状态机

每个 case 必须有明确状态：

```text
planned
→ spec_created
→ generated
→ fact_judged
→ risk_judged
→ dedup_checked
→ accepted
   或 rejected
→ split_assigned
→ exported
```

任何 Agent 只能执行其负责的状态迁移。

例如 Dialogue Agent 只能：

```text
spec_created → generated
```

不能直接标记 accepted。

Risk Judge 也不能自行修改聊天。

---

# 44. Task 状态机与 Claim Lock

每个子 Agent 任务必须持久化为：

```text
tasks/TASK-xxxx/task.yaml
```

状态：

```text
pending
→ claimed
→ running
→ completed
```

异常：

```text
failed
expired
cancelled
```

`claimed` 时必须写：

```yaml
claim:
  agent_id: AGT-...
  claimed_at: ...
  lease_expires_at: ...
```

这样两个 Agent 不会同时处理同一批数据。

lease 超时后 Orchestrator 才能重新派发。

---

# 45. Idempotency Key

每个任务必须有 deterministic `idempotency_key`。

示例：

```text
sha256(
  task_type
  + sorted(input_ids)
  + prompt_id
  + workflow_version
  + target_signature
)
```

Orchestrator 分发任务前查询：

```text
是否存在相同 idempotency_key 且 completed？
```

如果存在：

```text
禁止再次执行
```

除非明确设置：

```yaml
force_rerun: true
rerun_reason: "..."
```

---

# 46. 完整 Task Packet：任何模型都可以接手

任何 Agent 任务都不能依赖之前的聊天上下文。

一个完整任务目录：

```text
tasks/TASK-00001827/
├── task.yaml
├── instructions.md
├── input_manifest.json
├── input/
├── output/
├── checkpoint.yaml
└── result_manifest.json
```

`task.yaml` 必须包含：

```yaml
task_id: TASK-00001827
task_type: generate_dialogue
status: pending

workflow_version: DATASET-WF-v2.0
prompt_id: PRM-DIALOGUE-003

input_ids:
  - CASE-00001823
  - CASE-00001824

target_count: 5

constraints:
  min_tokens: 1500
  max_tokens: 3500
  participants: 2
  format: wechat_transcript
  no_label_mutation: true

output_schema_version: CASE-YAML-v1

idempotency_key: "..."
```

一个新 Agent 只需要读取这个目录，就可以继续任务。

---

# 47. Checkpoint：长任务中途可交接

每处理一条或一个小批次，Agent 必须更新：

```yaml
task_id: TASK-00001827
completed_ids:
  - CASE-...
  - CASE-...

pending_ids:
  - CASE-...

failed_ids: []

last_checkpoint_at: ...
notes: "..."
```

因此 Agent 被终止、模型切换、机器重启，都只需要从 `pending_ids` 继续。

禁止只在任务结束时一次性写结果。

---

# 48. Agent 交接协议

新 Agent 接手时必须按固定顺序：

```text
1. 读取 workflow_version
2. 读取 source_registry
3. 读取 task.yaml
4. 读取 checkpoint.yaml
5. 只处理 pending_ids
6. 检查 Registry 是否已有输出
7. 执行
8. 原子写 output
9. 更新 Registry
10. 更新 checkpoint
```

禁止：

- 根据聊天记忆推断当前进度；
- 重新生成已经 completed 的 case；
- 自行修改 Source ID；
- 自行创建不登记的 archetype；
- 覆盖其他 Agent 的 accepted 结果。

---

# 49. YAML 母数据格式 v1

最终一条 case 推荐：

```yaml
schema_version: CASE-YAML-v1

identity:
  case_id: CASE-000001823
  family_id: FAM-00000491
  lineage_id: LIN-00000931
  archetype_id: ARC-00000117
  variant_id: v03

source:
  source_ids:
    - SRC-SAL-001
  source_seed_ids:
    - SEED-SRC-SAL-001-base-00001277

lineage:
  root_case_id: CASE-000001751
  parent_case_id: CASE-000001817
  generation_type: long_context_contrastive

labels:
  risk: 2
  category: bribery_corruption
  illicit_likelihood: 2
  evidence_strength: medium
  review_required: true

hidden_case:
  latent_intent: "..."
  critical_evidence:
    - "..."
  benign_alternatives:
    - "..."

attributes:
  approximate_tokens: 2460
  duration_days: 4
  turn_count: 67
  topic_switches: 7
  obfuscation: high
  has_transfer: true
  normal_transfer_count: 1
  suspicious_transfer_count: 1

generation_signature:
  top_category: bribery_corruption
  subtype: intermediary_payment
  risk: 2
  token_bucket: 2k_4k
  relationship: business
  obfuscation: high
  has_transfer: true

execution:
  agent_id: AGT-DIALOGUE-007
  model_id: MOD-XXXX-001
  prompt_id: PRM-DIALOGUE-003
  run_id: RUN-20260923-000187
  batch_id: BATCH-20260923-018
  workflow_version: DATASET-WF-v2.0

dedup:
  content_hash: "sha256:..."
  normalized_hash: "sha256:..."
  semantic_cluster_id: SCL-00000271

conversation: |-
  【9月12日】

  A：……
  B：……

  【系统消息】A 向 B 转账 300 元，已收款。

  ……
```

模型训练时只能读取：

```text
conversation
```

目标读取：

```text
labels.risk
```

---

# 50. Orchestrator 每轮调度算法

每轮生成前：

```text
1. 读取 Registry
2. 计算 coverage
3. 计算 source_seed usage
4. 计算 lineage size
5. 计算 semantic cluster size
6. 找 coverage gap
7. 按 gap 创建 Task Packet
8. 分配 5–10 个 case 给子 Agent
9. 等待结果落盘
10. Judge / Dedup
11. 更新 Registry
12. 下一轮
```

Orchestrator 不应该通过“我觉得这个方向还不错”来分配任务，而应该通过数据统计决定。

---

# 51. 默认配额与防过量规则

第一版建议设置：

```text
单一 source_seed accepted descendants <= 5
单一 lineage accepted cases <= 8
单一 archetype 占全体 <= 3%
单一 semantic cluster 占全体 <= 0.5%
同一 generation_signature 默认 <= 25
```

这些阈值不是永久固定，可由 coverage report 调整。

任何 override 都必须写明：

```yaml
override:
  reason: "model error analysis requires targeted oversampling"
  approved_by: "orchestrator"
```

---

# 52. 模型风格变化的处理

不同模型/Agent 产生不同写作风格不是问题，反而可以增加语言多样性。

但必须记录：

```text
model_id
prompt_id
agent_id
run_id
```

并在 Coverage Dashboard 中增加：

```text
generator_model distribution
prompt_version distribution
```

避免某个模型生成的数据占比过高。

如果一个模型产生明显 synthetic watermark，则可以：

```text
按 model_id 回溯全部 descendants
→ 降权 / 重写 / 剔除
```

不会污染整个数据集。

---

# 53. 任务交接的最低交付物

任何 Agent 完成一个阶段时，必须留下：

```text
Registry 已更新
Task 状态明确
Checkpoint 已更新
Result manifest 存在
所有新 ID 已登记
所有新文件路径已登记
所有失败项有 reason
```

没有这些，就视为任务未完成。

---

# 54. 控制平面目录

```text
crime_chat_dataset/
├── registry/
│   ├── dataset_registry.sqlite
│   ├── source_registry.yaml
│   ├── id_counters.yaml
│   └── snapshots/
├── prompts/
│   ├── PRM-*.md
│   └── manifest.yaml
├── tasks/
│   └── TASK-*/
├── runs/
│   └── RUN-*/
├── sources/
├── taxonomy/
├── archetypes/
├── cases/
├── pairs/
├── splits/
├── export/
└── report/
```

---

# 55. 最终原则

本项目以后不依赖“某个 Agent 记得之前做过什么”。

唯一可信状态是：

```text
Registry
+ Task Packet
+ Checkpoint
+ Versioned Prompt
+ Versioned Schema
```

任何模型都只是在执行这些状态文件定义的任务。

这样即使：

```text
GPT → Claude → Qwen → 另一个本地 Agent
```

连续交接，仍然可以准确知道：

- 哪些 Source 已经处理；
- 哪些 seed 已经被使用几次；
- 哪些 archetype 过量/不足；
- 哪些 case 属于同一 lineage；
- 哪些任务已经完成；
- 哪些数据已经被 Judge；
- 哪些数据可以进入训练；
- 哪些数据必须禁止再次生成。
