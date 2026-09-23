# 第一轮本地自测报告（汇总存档）

> 2026-09-23。硬件 RTX 4060 Laptop 8GB。本轮验证：Qwen3.5-9B Q4 + Nimble-style candidate-logit readout 的审核能力、本地可运行性、官方 adapter 迁移性、量化影响、thinking 对照。模型与逐条数据已按指示清理，本文件是唯一保留的结果记录。

## 环境
- 模型: unsloth Qwen3.5-9B-Q4_K_M GGUF (5.7GB)；llama-cpp-python 0.3.35 cu124；llama.cpp b11118 llama-server
- 读取: nimble parallel_schema verbatim（prompt sha256 a0a0f94d… 与官方 checkpoint 契约一致），最后位置 logits 切片 + softmax
- Benchmark: 自建 194 条中文审核集（37 对 contrastive），标签 0/1/2/3

## 三臂对比（194 条，greedy，无 thinking）
| 指标 | System-One(候选logits) | 生成式(digit) |
|---|---|---|
| accuracy / macro-F1 | 0.711 / 0.574 | 0.649 / 0.546 |
| recall 0/1/2/3 | .89/.29/.45/.68 | .79/.39/.50/.55 |
| FN risk>=2 / risk==3 | 4.8% / 32.5% | 8.1% / 45.0% |
| NLL / ECE(拟合T=1.72 oracle) | 0.720 / 0.070 | – |
| latency p50 | 0.262s | 0.298s |
| contrastive 对全对 | 18/37 | 15/37 |

## thinking 对照（94 条困难子集，1600 token 上限）
- thinking: acc 48.4%（64 条有效，17 条截断），均值 1297 token / 42.3s
- System-One 同子集: acc 47.9%，0.26s → 思考无质量收益，160 倍延迟

## 官方 Bespoke-Nimble-9B LoRA → merge → Q4
- merge 管线: peft CPU BF16 merge → llama.cpp b11118 转换(--no-mtp) → Q4_K_M
- 审核 194 条: acc 55.2%（base 71.1%）→ **负迁移**（过报：class0 recall .89→.69）
- 官方领域对照(140条可用): base-Q4 67.9%（官方 BF16 报 66.4% ✓管线正确）；merged-Q4 70.0%（官方 BF16 报 90.1%）→ **Q4 吃掉 LoRA 增益**

## 关键工程坑
1. b11118 convert_hf_to_gguf 对无 MTP 权重 checkpoint 写出 block_count=33 坏文件 → 必须 --no-mtp
2. llama-cpp-python 0.3.35 旧运行时加载不了 b11118 新布局 → 评测走 llama-server + grammar + post_sampling_probs（等价 restricted softmax，需显式关 top_k/top_p/min_p）
3. GitHub release 直连被限速 → ghfast.top 镜像 5s/19MB
4. Phase 1 检查 8/8: schema/映射/boolean顺序/softmax和1/置换不变性 全过

## 错误模式（4 类训练靶点）
- 2/3 严重度边界（13 条 severe 漏报中 12 条判成 2）
- 自伤操作话术（割多深去急诊，p(safe)=0.97）
- 带正当理由的隐私查询（查车牌，p(safe)=0.97）
- 黑话/缩写包装违禁品交易（py交易群出类固醇，判 1）