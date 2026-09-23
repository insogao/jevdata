# 架构研究笔记：Nimble / openjev-sglang / Decider

> 快照位置：`repos/nimble`、`repos/openjev-sglang`、`repos/decider`
> 研究日期：2026-09-23。所有行号引用对应本地快照。

## 0. 一句话总结

Nimble 证明了「Qwen3.5-9B + LoRA + 只读候选 token logits」可以逼近闭源 Jev（holdout 参考标签一致率 90.12% vs base 66.36% vs Jev 93.21%，README.md:429-434）。我们不需要发明任何新东西：**scoring 路径复用 `nimble/scoring/`，serving 路径复用 `openjev-sglang`，训练路径复用 `nimble/training/`**。本轮的全部工作是把这三段拼到我们的审核 schema 和数据上。

---

## 1. Nimble scoring 路径（Phase 1 的复现对象）

### 1.1 Prompt 如何构造（Q1）

`nimble/scoring/parallel_schema.py:87-138 prepare_prompts()`：

1. System prompt 固定（L9-15）：「按 schema 分类 context……只返回单字母 code，不输出推理」。
2. User 内容是 **JSON**：`{"context": <state>, "schema": [每个字段的 name/description/choices]}`，每个 choice 附 one-letter code（`A`–`Z`，L101）+ 可选 description，然后 `\n\nRequested field: "<字段名>"`（L105）。
3. 整条消息用 `apply_chat_template(tokenize=False, add_generation_prompt=True, enable_thinking=False)` 渲染（L108-111）。
4. 用 marker `__PARALLEL_FIELD_TARGET__` 把渲染文本切成 `start + 字段名 + end`（L112-113）：**每个字段一条完整 prompt，但共享同一段前缀**。字段间互不可见（各自独立渲染），保证「每字段独立决策」。
5. 超长直接报错，不截断（L124-125）。训练默认 max 2048（官方 9B recipe），推理 runner 默认 4096。

关键点：context 以 JSON 字符串进 prompt（evaluation/evaluate_pilot.py:19-38 的 `adapt_input()`：noul→boolean `[False,True]`、score→enum `["0","1",...]`）。

### 1.2 enum / boolean → 单 token A/B/C 映射（Q2）

- 枚举：`zip(string.ascii_uppercase, choices)`（L101），第 i 个选项 → 第 i 个大写字母。
- **boolean 默认 `choices_for()` 返回 `[False, True]`（L23）→ A=false, B=true，顺序硬编码一致**（`deploy` 文档也确认 L9-19：布尔编码 A=false / B=true）。
- 候选 token id 不是想当然的 `"A"` 的 id：对每个候选，`tokenizer.encode(prompt + code)` 与 `encode(prompt)` 做**公共前缀差分**（L129-134），要求差分恰好是 1 个普通 token（非 special id），且各候选 token id 互不相同（L135-136）。这处理了 BPE 边界问题。

### 1.3 如何取得 candidate token logits（Q3）

两条实现，同一数学：

**CUDA runner** `nimble/scoring/cuda_scorer.py:47-51`：

```python
def candidate_projection(hidden, weight, token_ids):
    indices = torch.tensor(token_ids, device=weight.device)
    rows = weight.index_select(0, indices).to(hidden.device)
    return hidden.float() @ rows.float().T
```

即 `hidden @ lm_head.weight[candidate_ids].T`——**先取行再投影，FP32 累加小头**（L77-78 显式禁 TF32）。这正是任务书要求的路径。

**MLX runner** `nimble/scoring/parallel_scorer.py:44-47` 同样实现（`selected_weight @ hidden.T`）。

### 1.4 如何避免完整 vocabulary decode（Q4）

- 推理：`backbone(input_ids, use_cache=False).last_hidden_state[:, -1, :]` 取最后位置 hidden（cuda_scorer.py:138），然后**只投影候选行**（L139）。输出张量是 `[batch, n_candidates]`（≤26），词表（~150K）从未被物化。metrics 里回报 `full_vocabulary_projection: False`（L163）自证。
- `parallel` 模式（MLX，parallel_scorer.py:108-149）：prefix 只 prefill 一次进 cache，`broadcast_cache` 广播给所有字段分支，各分支只增量算自己的 suffix（几十个 token），取各分支最后位置 hidden。多个字段取候选 token 的 **union** 投影一次再按行查（L141-146），减少重复行。
- 注意：CUDA runner 目前只有 `independent` 模式（每个字段完整 prefill，cuda_scorer.py:128-129）——共享前缀优化在 CUDA 侧由 serving 层（openjev 的 radix cache）完成，而不是本地 KV cache 广播。

### 1.5 LoRA 挂在哪些 Linear 层（Q5）

`nimble/training/schema_train.py:189`：

```python
targets = [name for name, layer in base.named_modules()
           if isinstance(layer, torch.nn.Linear) and ".language_model." in name]
```

**动态枚举 base 模型中所有名字含 `.language_model.` 的 `nn.Linear`**（Qwen3.5 是多模态壳 `Qwen3_5ForConditionalGeneration`，语言侧全部 Linear：attention q/k/v/o + MLP gate/up/down；视觉侧排除）。空匹配报错。`LoraConfig(r=rank, lora_alpha=2*rank, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")`（L192-193）。

### 1.6 candidate-only cross entropy 如何实现（Q6）

`nimble/training/schema_train.py:46-63`：

```python
logits = model(input_ids=..., attention_mask=..., use_cache=False,
               logits_to_keep=1).logits[:, -1, :].float()      # 只算最后 1 个位置
selected = logits.gather(1, inputs["candidate_ids"])          # 切出候选 token logits
selected = selected.masked_fill(~inputs["candidate_mask"], -inf)
loss = F.cross_entropy(selected, inputs["labels"])            # labels 是 gold 选项下标
```

- `logits_to_keep=1`：前向只保留最后 prompt 位置的 logits，**其他位置从不参与 loss**（不是逐 token 序列 CE，也不是让模型「生成」A）。
- 实现顺序是「**最后位置完整词表 logits → gather 切片**」，不是「hidden 直接乘候选行」。训练时一次前向反正要算 backbone，lm_head 全词表投影只发生在 1 个位置，代价可接受；推理侧（cuda_scorer）才是真正的候选行投影。loss 字段名：`candidate_cross_entropy_at_last_prompt_position`（datasets/export_candidate_training.py:29）。
- **没有 loss 加权**：contrastive 信号来自数据结构（1338 对 base/counterfactual，组内 label 相反，batch 等权）。

### 1.7 contrastive training data 如何生成（Q7）

`nimble/datasets/contrastive_data.py` + `docs/TRAINING_EVAL_CURATION.md`：

- 两种任务：`d2c`（保留 state，为决策合成新上下文）/ `c2d`（为源决策改写上下文），交替分配保持平衡（L110-123）。
- **最小编辑**：对 state JSON 中恰好一个字符串 span 做替换；`old` 必须唯一出现、`old != new`（L47-62）。新流水线量化为「一句话内 ≤8 词的 token diff」（fast_training_dataset.py:420）。
- **label 翻转是硬校验**：`if targets["counterfactual"] == base_target: raise ValueError("Counterfactual must change the target")`（L166-167）。组内 5 变体（base/evidence_removed/counterfactual/paraphrase/distractor；发布版只保留 base+counterfactual）。
- 验证器盲评：验证器看不到提案 label（`labels_hidden: True`），只保留 `agrees && unambiguous` 的行（L256-257）。
- 训练时选项顺序按 `random.Random(f"{seed}:{row_id}")` **逐记录打乱**，防止模型学位置（schema_data.py:26-27）。

### 1.8 temperature calibration 怎么做（Q8）

`nimble/scoring/calibration.py`：

- `softmax(candidate_logits / T)`，T 只影响锐度不影响 argmax。
- 官方 9B checkpoint 拟合值 **T=2.179078721266035**（键为 `(model_id, revision)` 精确匹配，L5-9）。方法：在训练外 300 例上最小化 log loss，另 300 例验收：ECE 0.128→0.066，log loss 0.692→0.555，accuracy 不变。
- 我们自己训的 adapter 需要按同样流程拟合自己的 T。

### 1.9 官方 SGLang deployment 如何调用 openjev-sglang（Q9）

`docs/MODAL_SERVING.md` + `deploy/modal_app.py`：

- serving 镜像 = `lmsysorg/sglang:v0.5.19-cu130` + `uv` 安装 `openjev-sglang @ commit 7f84bedc...`；只拷入 nimble 的 5 个文件（`scoring/{__init__,calibration,parallel_schema}.py` + `nimble/serving/`），**prompt 编译器直接 import openjev 的 `Branch/PreparedRequest`**（nimble/serving/compiler.py）。
- 权重准备：CPU BF16 加载 base → `PeftModel.from_pretrained(...).merge_and_unload(safe_merge=True)` → 存 Volume（modal_app.py:20-58）。**合并后权重 = dense Qwen3.5-9B，无运行时 LoRA 开销**。
- SGLang 启动加 `--json-model-override-args '{"language_model_only": true}'` 规避 0.5.19 初始化视觉处理器。
- 服务温度：归一化前先除以拟合温度 2.179（doc L56）。
- 端点即 TypeSafe 形状 `POST /v1/systemone`，`output_tokens == N_fields + 1`（1 个丢弃的 warmup token）。

---

## 2. openjev-sglang（serving 主参考）

双进程架构：瘦 FastAPI API 进程 + 本机 SGLang 0.5.19（只监听 127.0.0.1），全部走 SGLang 原生 HTTP `/generate`。

### 2.1 shared prefix 在 SGLang 中怎么提交（任务书重点问题）

`src/openjev/service.py:69-85`：

```python
warmup = await self.backend.generate(prepared.prefix_ids)      # ① 先把共享前缀 prefill 进 radix tree
tasks = [asyncio.create_task(self.backend.generate(b.input_ids, b.label_ids))
         for b in prepared.branches]                            # ② 并行提交 N 个完整 input_ids
results = await asyncio.gather(*tasks)
```

**没有用 session/fork/n>1**。每个 branch 提交完整 `prefix+suffix` 的 input_ids，靠 SGLang **radix cache 自动前缀匹配**命中 warmup 已缓存的 KV，只增量算 suffix。warmup 请求 `max_new_tokens=1`，其输出被丢弃。README 明说 radix reuse 是「机会性」的而非 pin 住的 KV session。启动参数硬性禁止 `--disable-radix-cache` / `--disable-cuda-graph`。

### 2.2 candidate 概率读出

`src/openjev/backend.py:39-84`：`POST /generate` 带 `return_logprob=true, token_ids_logprob=<候选label的token id列表>, logprob_start_len=-1, top_logprobs_num=0, max_new_tokens=1`——用 SGLang 的 **selected-token logprobs** 精确取每个候选的 logprob，解析 `meta_info.output_token_ids_logprobs[0]`。归一化在 `scoring.py`：带温度的稳定 softmax（减 peak、`math.fsum`），confidence = `1 − H(p)/log(K)`。

已知坑：SGLang 0.5.19 的 mixed-logprob batch bug（#34719）——解法是 warmup 也请求一个无用 token 的 logprob（`token_ids_logprob=[0]`），让所有请求走同一代码路径。

### 2.3 答案字母标签

`src/openjev/prompts.py:78-93`：`A`–`Z` 再加经验证的单 token 两字母组合（AA, AB...）共 64 个，启动时逐个验证「单 token 且互不重复」。与 nimble 的候选项级验证互补。

### 2.4 可直接复用的部件

- warmup prefill 屏障 + 并行 branch 调度（service.py）——换后端也能套用
- `token_ids_logprob + logprob_start_len=-1` 读出方案 + mixed-logprob 规避
- 取消传播链（自定义 rid + `/abort_request` + sibling 取消 + 断连 watcher）
- 16 并发闸（529+Retry-After）、branch 64 信号量、120s 超时、2MiB body 闸
- evals/ 的 BoolQ/MMLU-Pro 评测基建（Brier/ECE/bootstrap、断点续跑）和 smoke.py

### 2.5 风险点

- 强绑定 SGLang 0.5.19（selected-token logprobs 格式、Rust frontend 缺 cached_tokens、`--mamba-radix-cache-strategy extra_buffer` 是混合 Qwen 特有）
- 默认部署是 B200 + NVFP4 的 35B-A3B；**我们本地 8GB 不可能跑这套 serving**，本轮 serving 相关验证在云 GPU 阶段做
- radix 命中是机会性的；`usage.input_tokens` 按「提交量」计，做成本核算时会误导

---

## 3. Decider（架构参考，方案 B 用）

- **multi-slot readout**（decider/model.py:16-25）：一个 forward，每个问题在 prompt 里有一个 `Answer k: (` slot，从 hidden `[B,T,H]` 按 (行, slot位置) gather 出 `[N,H]`，`F.linear(hs, lm_head.weight[letters])` 一次出 N 个分布。答案字母从不写进上下文 → 题间条件独立、前缀缓存数学等价。
- **schema-first cache**（schema_engine.py）：问题/选项块（state 无关）作为可缓存前缀，跑一次 `use_cache=True` 前向缓存 K/V + delta-net state；请求只算 state 后缀 + slot。按 `(schema_id, batch, len)` 形状分桶 capture/replay CUDA graph。**README 明示这是拿精度换速度，默认关闭**。
- **candidate-only head**：`W = lm_head.weight[letters]`（K=255），整个词表投影被替换为 255 行小投影。
- 35B-A3B MoE：只改加载实现（`grouped_mm`）；训练时 routed experts 全冻结，只训 attention/嵌入/共享专家，保存 overlay。**无 LoRA 代码，全量微调 slot CE**。
- 对我们的启示：branch-style（nimble/openjev，每问题一次额外 prefill）vs multi-slot（decider，一次 forward）。方案 B（35B-A3B multi-slot）大概率直接借用 decider 的 readout + PrefixCache 设计。

---

## 4. 依赖与版本事实

- nimble 训练：`transformers==5.17.0`、`peft==0.21.0`、`accelerate==1.15.0`、torch 2.8.0+cu128；**无 TRL**（原生 Trainer + 自定义 compute_loss）
- serving：`sglang v0.5.19-cu130`、openjev pin commit `7f84bedc`
- 官方 9B recipe（docs/NIMBLE_TRAINING.md:24-36）：base `Qwen/Qwen3.5-9B` rev `c2022362...`、LoRA r16/α32/dropout0.05、LR 5e-5、bs2×ga4=有效8、max_length 2048、1 epoch=335 步、warmup 101、seed 17、BF16。H100 级训练（tune 用 L40S）
- 数据：`data/train.jsonl` 2676 条（1338 对）+ `eval.jsonl` 324 条 holdout，10 域 × 3 原语（choice/noul/score），34 个 source family 与 holdout 完全不相交

## 5. 对本轮执行的直接推论

1. **Phase 1 验证不需要 9B**：schema 编译/A-B-C 映射/logits/softmax/置换不变性全部可用 `Qwen3.5-2B`（BF16 ~4GB，本机 8GB 可跑）验证代码路径；4B/9B 只换权重，代码不变。9B Q4 质量验证用 llama.cpp（GGUF），生产 serving 是云上 SGLang。
2. **cuda_scorer.py 是本地 Phase 1 的主 runner**（它就是「无长文本生成、直接读候选 logits」的参考实现），但注意它要求 CUDA + BF16。Windows + RTX 4060 可跑小模型。
3. **“禁止完整 vocab 投影”的要求在 nimble 推理侧已满足**（候选行投影）；训练侧是「最后位置全词表 + gather」，属可接受实现，记录在案无需优化。
4. **审核 schema 是纯叠加**：`overall_risk ∈ {"0","1","2","3"}` 就是一个 enum 字段，辅助维度各一个 enum/boolean 字段——nimble schema 原生支持（≤26 选项），无需改任何 nimble 代码。
5. 本地 8GB 无法验证的（SGLang 并发、radix 命中率、10 并发吞吐）推迟到云 GPU 阶段（Phase 4/5），不阻塞 Phase 1-3。
