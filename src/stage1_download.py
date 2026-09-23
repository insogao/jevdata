# -*- coding: utf-8 -*-
"""Stage 1A: download public sources via HF mirror into sources/raw/<SRC-ID>/.

Logs every file to sources/download_log.jsonl (append-only provenance).
Gated/restricted sources are NOT downloaded (see source_registry.yaml).
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
ROOT = Path(__file__).resolve().parents[1] / "crime_chat_dataset"

# source_id -> (hf_repo, allow_patterns)
PLAN = {
    "SRC-AEG-001": ("nvidia/Aegis-AI-Content-Safety-Dataset-2.0", ["*.json", "README*"]),
    "SRC-SAL-001": ("OpenSafetyLab/Salad-Data", ["base_set.json", "attack_enhanced_set.json", "README*"]),
    "SRC-BSD-001": ("BothBosu/scam-dialogue", ["*.csv", "README*"]),
    "SRC-PSD-001": ("allenai/prosocial-dialog", ["*.json", "README*"]),
    "SRC-BCC-001": ("talkmap/banking-conversation-corpus", ["*.csv", "README*"]),
}


def log(entry):
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with (ROOT / "sources" / "download_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[{entry['ts']}] {entry['event']}: {entry.get('detail','')}", flush=True)


def main():
    from huggingface_hub import snapshot_download

    for source_id, (repo, patterns) in PLAN.items():
        dest = ROOT / "sources" / "raw" / source_id
        dest.mkdir(parents=True, exist_ok=True)
        log({"event": "download_start", "source_id": source_id, "repo": repo})
        try:
            path = snapshot_download(repo_id=repo, repo_type="dataset",
                                     local_dir=str(dest), allow_patterns=patterns,
                                     max_workers=4)
            files = sorted(p.name for p in Path(path).rglob("*") if p.is_file() and not p.name.startswith("."))
            log({"event": "download_done", "source_id": source_id,
                 "detail": f"{len(files)} files", "files": files})
        except Exception as e:  # noqa: BLE001
            log({"event": "download_failed", "source_id": source_id, "detail": repr(e)[:300]})
            sys.exit_code = 1
    log({"event": "all_done"})


if __name__ == "__main__":
    main()
