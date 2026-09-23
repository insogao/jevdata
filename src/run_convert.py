import runpy
import sys

sys.path.insert(0, r"D:\work\jev\llama.cpp-b11118")
sys.argv = [
    "convert_hf_to_gguf.py",
    r"D:\work\jev\models\nimble-merged-bf16",
    "--outfile", r"D:\work\jev\models\nimble-merged-bf16.gguf",
    "--outtype", "bf16",
    "--no-mtp",
]
runpy.run_path(r"D:\work\jev\llama.cpp-b11118\convert_hf_to_gguf.py", run_name="__main__")
