# -*- coding: utf-8 -*-
"""llama-server HTTP backend for the baseline runner.

Candidate readout = grammar-restricted sampling probabilities:
  POST /completion {prompt: ids, grammar: 'root ::= "A"|"B"|"C"|"D"',
                    n_probs: 4, post_sampling_probs: true, temperature: T}
returns the grammar-masked, renormalized distribution over exactly the
candidate tokens — mathematically identical to nimble's candidate softmax
(logit slicing + softmax at temperature T).
"""
import json
import time
import urllib.request

GRAMMAR_ABCD = 'root ::= "A" | "B" | "C" | "D"'
GRAMMAR_DIGITS = 'root ::= "0" | "1" | "2" | "3"'


class LlamaServerBackend:
    def __init__(self, url="http://127.0.0.1:8099"):
        self.url = url.rstrip("/") + "/completion"

    def _post(self, payload, timeout=600):
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def candidate_probs(self, token_ids, grammar, labels, temperature=1.0):
        """Return (probs in label order, wall seconds). Renormalized restricted
        distribution over exactly the label tokens."""
        t0 = time.perf_counter()
        out = self._post({
            "prompt": list(token_ids),
            "n_predict": 1,
            "temperature": temperature,
            "grammar": grammar,
            "n_probs": len(labels),
            "post_sampling_probs": True,
            "cache_prompt": True,
            # disable truncation samplers so post-sampling probs are exactly
            # softmax(logits / T) restricted to the grammar-allowed labels
            "top_k": 0, "top_p": 1.0, "min_p": 0.0,
        })
        seconds = time.perf_counter() - t0
        by_token = {p["token"]: p["prob"]
                    for p in out["completion_probabilities"][0]["top_probs"]}
        probs = [by_token.get(c, 0.0) for c in labels]
        s = sum(probs)
        return [p / s for p in probs], seconds

    def generate(self, token_ids, max_tokens=8):
        t0 = time.perf_counter()
        out = self._post({
            "prompt": list(token_ids),
            "n_predict": max_tokens,
            "temperature": 0.0,
            "cache_prompt": True,
        })
        seconds = time.perf_counter() - t0
        usage = {"prompt_tokens": out["tokens_evaluated"],
                 "completion_tokens": out["tokens_predicted"]}
        return out["content"], seconds, usage
