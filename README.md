# Qwen3.5-9B System-One / Jev-like 审核模型实验（第一轮：本地量化推理验证）

> **AI Agent / 协作者请从 [AGENTS.md](AGENTS.md) 进入**：任务领取、超时规则、工作流、验收红线都在那里，本 README 只描述第一轮实验本身。

目标：验证 **Qwen3.5-9B 在不生成思考/答案、只读取候选 token logits（Nimble-style System-One）
时，复杂审核能力相对普通生成式到底损失多少**，以及 8GB 本机能否运行。
LoRA 训练与 SGLang serving 推迟到云 GPU 阶段。

## 目录

```
repos/nimble          bespokelabsai/nimble 快照（prompt/schema/scoring 复用来源）
repos/openjev-sglang  ekzhang/openjev-sglang 快照（serving 参考，本轮未部署）
repos/decider         Mapika/decider 快照（架构参考，方案 B 用）
models/               Qwen3.5-9B-Q4_K_M.gguf + tokenizer 文件
src/
  nimble_compatible_scorer.py  最小 Nimble 兼容评分器（verbatim 复用 nimble prepare_prompts）
  benchmark_data.py            审核 benchmark 数据（194 条，37 对 contrastive minimal-edit）
  build_benchmark.py           校验并导出 data/benchmark.jsonl
  phase1_checks.py             Phase 1 正确性检查（8 项）
  run_baseline.py              三臂评测 + 指标（accuracy/F1/recall/FN/NLL/Brier/ECE/latency）
report/                结论与数据（见下）
```

## 复现

```bash
python -m venv .venv
.venv/Scripts/pip install transformers huggingface_hub \
  https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-cu124/llama_cpp_python-0.3.35-py3-none-win_amd64.whl \
  nvidia-cuda-runtime-cu12 nvidia-cublas-cu12

# 模型（HF 直连不可用时设 HF_ENDPOINT=https://hf-mirror.com）
# models/Qwen3.5-9B-Q4_K_M.gguf   <- unsloth/Qwen3.5-9B-GGUF
# models/qwen35-9b-tokenizer/     <- Qwen/Qwen3.5-9B 的 tokenizer 文件

.venv/Scripts/python src/build_benchmark.py      # 构建并校验 benchmark
.venv/Scripts/python src/phase1_checks.py        # 8/8 通过
.venv/Scripts/python src/run_baseline.py         # 全量评测 → report/
```

## 报告文件

- `report/architecture.md` 三个参考项目的研究结论（prompt 构造/A-B-C 映射/候选投影/LoRA/温度校准/SGLang 提交方式）
- `report/baseline_results.csv` 逐条预测（三臂）
- `report/baseline_summary.json` 汇总指标
- `report/calibration_results.csv` 温度校准前后
- `report/latency_results.csv` 单流延迟与显存
- `report/error_cases.md` 漏报/误报案例分析
- `report/conclusion.md` 第一轮结论（是否进入 LoRA）
