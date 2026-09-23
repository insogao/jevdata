# 20 条长对话 YAML Demo Pack v2.2

这是后续多 Agent 生成流程的示范包，不是最终训练数据。

- YAML 顶部：ID、标签、隐藏案件卡、血缘、来源、去重等元数据。
- YAML 底部：微信式 1 对 1 原始聊天。
- 正常话题均匀穿插在多日聊天中。
- 同一 case 内不重复相同 side-topic 模板。
- 有风险、边界和 hard negative 三类。
- 转账使用 `【系统消息】...` 直接嵌入聊天原文。

## Risk 分布
Risk0=5, Risk1=2, Risk2=8, Risk3=5

## 长度
粗略 token estimate：min=999, avg=1412.3, max=1775。
该数字只是字符级估算。正式训练时必须用 Qwen3.5 tokenizer 重算。

平均 turn 数：119.3。

## 目录
- `cases/`: 20 条 YAML
- `MANIFEST.yaml`: 唯一 ID 与覆盖索引
- `FORMAT_SPEC.md`: 后续 Agent 的强制格式规范
- `STATS.csv`: 快速统计
