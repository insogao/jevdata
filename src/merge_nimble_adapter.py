# -*- coding: utf-8 -*-
"""Merge bespokelabs/Bespoke-Nimble-9B LoRA into the pinned Qwen3.5-9B base.

Mirrors nimble's own deploy path (deploy/modal_app.py prepare_model):
CPU BF16 load -> PeftModel -> merge_and_unload -> save_pretrained.
RAM peak ~20GB of 31.7GB available; output is a dense BF16 HF checkpoint.
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-dir", default="models/qwen35-9b-base")
    ap.add_argument("--adapter-dir", default="models/nimble-adapter")
    ap.add_argument("--out-dir", default="models/nimble-merged-bf16")
    args = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import Qwen3_5ForConditionalGeneration

    print("loading base (bf16, cpu, low-mem)...", flush=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.base_dir, dtype=torch.bfloat16, attn_implementation="eager",
        low_cpu_mem_usage=True)
    model.config.use_cache = False

    print("attaching adapter...", flush=True)
    model = PeftModel.from_pretrained(model, args.adapter_dir)

    print("merging (safe_merge)...", flush=True)
    model = model.merge_and_unload(safe_merge=True)

    print("verifying no lora layers remain...", flush=True)
    leftover = [n for n, m in model.named_modules() if "lora_" in n.lower()]
    assert not leftover, leftover[:5]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print("saving dense checkpoint...", flush=True)
    model.save_pretrained(out, safe_serialization=True, max_shard_size="5GB")
    # tokenizer for the converter (copy adapter's pinned copies if present)
    tok_files = ["tokenizer.json", "tokenizer_config.json", "chat_template.jinja"]
    import shutil
    for f in tok_files:
        src = Path(args.adapter_dir) / f
        if not src.exists():
            src = Path(args.base_dir) / f
        if src.exists():
            shutil.copy(src, out / f)
    print("saved to", out)


if __name__ == "__main__":
    sys.exit(main())
