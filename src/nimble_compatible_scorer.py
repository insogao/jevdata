"""Minimal Nimble-compatible scorer on a local GGUF backend.

Reuses nimble/scoring/parallel_schema.py verbatim (prompt construction, schema
validation, A/B/C candidate mapping) and swaps the model backend for
llama-cpp-python. Readout = last-position logits sliced at the candidate token
ids, softmax over candidates — same semantics as nimble.scoring.cuda_scorer's
candidate_projection + softmax, just served from a Q4 GGUF.

Only single-field overall_risk = A/B/C/D is supported in this phase.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

# Import the untouched Nimble prompt/schema code.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "repos" / "nimble"))
from nimble.scoring.parallel_schema import (  # noqa: E402
    SYSTEM_PROMPT,
    choice_key,
    prepare_prompts,
    validate_schema,
)

def ensure_cuda_dlls():
    """Make the NVIDIA wheels' DLLs loadable before llama_cpp imports."""
    import glob
    import os
    root = Path(__file__).resolve().parents[1] / ".venv" / "Lib" / "site-packages"
    for d in glob.glob(str(root / "nvidia" / "*" / "bin")) + glob.glob(str(root / "nvidia" / "*" / "lib")):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]

RISK_SCHEMA = {
    "overall_risk": {
        "type": "enum",
        "description": (
            "Overall content risk level for a content-moderation decision. "
            "0 = safe; 1 = mild/questionable, allowed but borderline; "
            "2 = violation of policy; 3 = severe violation (serious real-world harm, "
            "actionable illegal instructions, or explicit severe content)."
        ),
        "choices": ["0", "1", "2", "3"],
        "choice_descriptions": {
            "0": "Safe: no policy concern.",
            "1": "Mild: edgy, borderline discussion, no real harm potential.",
            "2": "Violation: clear policy violation (insults/harassment, mild illegal "
                 "solicitation, non-graphic harmful content).",
            "3": "Severe: actionable instructions for serious harm, credible threats, "
                 "CSAM, terrorism, self-harm encouragement, or similar.",
        },
    },
}

DIGIT_RISK_SCHEMA = {
    "overall_risk": {
        "type": "enum",
        "description": RISK_SCHEMA["overall_risk"]["description"],
        "choices": ["0", "1", "2", "3"],
        "choice_descriptions": RISK_SCHEMA["overall_risk"]["choice_descriptions"],
    },
}


class TokenizerAdapter:
    """Give llama.cpp token ids the transformers tokenizer renders/prompts."""

    def __init__(self, tokenizer_dir):
        from transformers import AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True,
                            enable_thinking=False):
        return self.tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=add_generation_prompt,
                                            enable_thinking=enable_thinking)

    def encode(self, text, add_special_tokens=False):
        return self.tok.encode(text, add_special_tokens=add_special_tokens)

    @property
    def all_special_ids(self):
        return self.tok.all_special_ids


class LlamaCppBackend:
    """Prefill token ids, read last-position logits, greedy-generate."""

    def __init__(self, gguf_path, n_ctx=4096, n_gpu_layers=-1, verbose=False):
        from llama_cpp import Llama

        self.llm = Llama(model_path=str(gguf_path), n_ctx=n_ctx,
                         n_gpu_layers=n_gpu_layers, verbose=verbose,
                         seed=17, logits_all=False)
        self.n_vocab = self.llm.n_vocab()

    def _logits_last(self):
        # llama-cpp-python keeps the raw context handle in _ctx (0.3.x).
        ctx = getattr(self.llm, "_ctx", None) or getattr(self.llm, "ctx", None)
        if ctx is None or not hasattr(ctx, "get_logits"):
            raise RuntimeError("llama-cpp-python context does not expose get_logits")
        return ctx.get_logits()

    def candidate_logits(self, token_ids, candidate_ids):
        """Return (candidate logits list, prefill_seconds). Nimble-style readout."""
        self.llm.reset()
        t0 = time.perf_counter()
        self.llm.eval(list(token_ids))
        ptr = self._logits_last()
        prefill = time.perf_counter() - t0
        return [ptr[t] for t in candidate_ids], prefill

    def generate(self, token_ids, max_tokens=8, stop=None):
        """Greedy decode over the FULL vocabulary (unconstrained generative readout)."""
        self.llm.reset()
        t0 = time.perf_counter()
        out = self.llm.create_completion(prompt=list(token_ids), max_tokens=max_tokens,
                                         temperature=0.0, top_p=1.0, stop=stop or [])
        seconds = time.perf_counter() - t0
        return out["choices"][0]["text"], seconds, out["usage"]

    def candidate_logits_and_digit_control(self, prompt_ids, letter_ids, digit_ids):
        """One forward serving both letter readout (nimble prompt) reuse."""
        raise NotImplementedError


def softmax(xs, temperature=1.0):
    m = max(xs)
    exps = [math.exp((x - m) / temperature) for x in xs]
    s = math.fsum(exps)
    return [e / s for e in exps]


def nimble_digit_prompt(tok, context):
    """Generative-arm prompt: same nimble JSON layout, but the model answers with
    the choice value (0-3) instead of a letter code. enable_thinking=False."""
    fields = [{
        "name": "overall_risk",
        "description": RISK_SCHEMA["overall_risk"]["description"],
        "choices": [{"code": v, "value": v, "description": d}
                    for v, d in zip(["0", "1", "2", "3"],
                                    RISK_SCHEMA["overall_risk"]["choice_descriptions"].values())],
    }]
    content = (json.dumps({"context": context, "schema": fields}, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e")
               + "\n\nRequested field: overall_risk")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content}]
    return tok.apply_chat_template(messages, tokenize=False,
                                   add_generation_prompt=True, enable_thinking=False)


def digit_token_ids(tok, prompt_text):
    """Token ids the generative arm would emit for 0-3 (for the free-logit control)."""
    ids = []
    for d in "0123":
        combined = tok.encode(prompt_text + d, add_special_tokens=False)
        base = tok.encode(prompt_text, add_special_tokens=False)
        suffix = combined[len(base):]
        if combined[:len(base)] != base or len(suffix) != 1 or suffix[0] in tok.all_special_ids:
            raise ValueError(f"digit {d} is not one ordinary token at the answer boundary")
        ids.append(suffix[0])
    if len(set(ids)) != 4:
        raise ValueError("digit token ids are not distinct")
    return ids


def letter_token_ids(tok, prompt_text):
    ids = []
    for c in "ABCD":
        combined = tok.encode(prompt_text + c, add_special_tokens=False)
        base = tok.encode(prompt_text, add_special_tokens=False)
        suffix = combined[len(base):]
        if combined[:len(base)] != base or len(suffix) != 1 or suffix[0] in tok.all_special_ids:
            raise ValueError(f"choice code {c} is not one ordinary token at the answer boundary")
        ids.append(suffix[0])
    if len(set(ids)) != 4:
        raise ValueError("choice token ids are not distinct")
    return ids


def build_all(tok, context):
    """Prepare both arms for one item. Returns dict with prompt ids + candidate ids."""
    prepared = prepare_prompts(tok, context, RISK_SCHEMA, max_input_tokens=4096)
    assert prepared.names == ["overall_risk"]
    letter_prompt = prepared.full_ids[0]
    letters = prepared.candidate_ids[0]
    gen_prompt_text = nimble_digit_prompt(tok, context)
    gen_prompt = tok.encode(gen_prompt_text, add_special_tokens=False)
    digits = digit_token_ids(tok, gen_prompt_text)
    return {
        "letter_prompt_ids": letter_prompt,
        "letter_ids": letters,
        "gen_prompt_ids": gen_prompt,
        "digit_ids": digits,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gguf", default="models/Qwen3.5-9B-Q4_K_M.gguf")
    ap.add_argument("--tokenizer-dir", default="models/qwen35-9b-tokenizer")
    ap.add_argument("--context", help="single-text smoke test")
    ap.add_argument("--n-gpu-layers", type=int, default=-1)
    ap.add_argument("--n-ctx", type=int, default=4096)
    args = ap.parse_args()

    tok = TokenizerAdapter(args.tokenizer_dir)
    backend = LlamaCppBackend(args.gguf, n_ctx=args.n_ctx, n_gpu_layers=args.n_gpu_layers)

    context = args.context or (
        "用户A：游戏里怎么干掉楼下的Boss？他血太厚了，我卡在这三天了。")
    built = build_all(tok, context)

    # Arm S: candidate logits (System-One / nimble)
    clogits, prefill_s = backend.candidate_logits(built["letter_prompt_ids"], built["letter_ids"])
    probs = softmax(clogits)
    # Arm G: unconstrained greedy generation (digit answer)
    text, gen_seconds, usage = backend.generate(built["gen_prompt_ids"], max_tokens=8)
    # Control: digit logits under the generative prompt (free control readout)
    dlogits, prefill_g = backend.candidate_logits(built["gen_prompt_ids"], built["digit_ids"])
    dprobs = softmax(dlogits)

    print(json.dumps({
        "context": context,
        "system_one": {"letters": list("ABCD"), "logits": clogits, "probs": probs,
                       "argmax": int(max(range(4), key=lambda i: clogits[i])),
                       "prefill_seconds": round(prefill_s, 3)},
        "generative": {"raw_output": text,
                       "usage": usage,
                       "seconds": round(gen_seconds, 3)},
        "digit_control": {"logits": dlogits, "probs": dprobs,
                          "argmax": int(max(range(4), key=lambda i: dlogits[i])),
                          "prefill_seconds": round(prefill_g, 3)},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
