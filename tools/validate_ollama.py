"""Optional local integration check; sends a synthetic request, never downloads a model."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

def get(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default="http://127.0.0.1:18630")
    parser.add_argument("--engine", default="http://127.0.0.1:11434")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default=".evidence-private/ollama-validation.json")
    args = parser.parse_args()
    available = {item["name"] for item in get(args.engine + "/api/tags")["models"]}
    if args.model not in available:
        raise SystemExit("Selected model is not already downloaded; no download attempted.")
    stopped, gpu_samples = threading.Event(), []
    def monitor():
        while not stopped.is_set():
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                                     "--format=csv,noheader,nounits"], capture_output=True, text=True)
            gpu_samples.append(result.stdout.strip())
            stopped.wait(.4)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    records = "\n".join(f"item_{i}: count={i*17+3}, unit_price={i%19+1}" for i in range(120))
    prompt = "Validation run " + datetime.datetime.now(datetime.timezone.utc).isoformat() + "\nWrite a Python inventory validation module for these synthetic records. Include type annotations and validation functions. Output code only.\n" + records
    body = {"model": args.model, "prompt": prompt, "stream": True, "keep_alive": "5m",
            "options": {"num_ctx": 8192, "num_predict": 256, "temperature": 0, "num_gpu": 99}}
    final = None
    try:
        request = urllib.request.Request(args.proxy + "/api/generate", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            for line in response:
                value = json.loads(line)
                if value.get("error"):
                    raise RuntimeError(value["error"])
                if value.get("done"):
                    final = value
        if not final:
            raise RuntimeError("No native final timing was returned.")
        state = get(args.proxy + "/__token_speedometer__/state")
        counts = {key: final[key] for key in ["prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"]}
        expected = {"read": counts["prompt_eval_count"] / (counts["prompt_eval_duration"] / 1e9),
                    "write": counts["eval_count"] / (counts["eval_duration"] / 1e9)}
        for key in ("read", "write"):
            assert abs(state[key]["rate"] - expected[key]) < 1e-8, (key, state, expected)
        loaded = get(args.engine + "/api/ps")["models"]
        selected = next(item for item in loaded if item["name"] == args.model)
        assert selected["size_vram"] > 0, "No model allocation on GPU"
        report = {"date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "engine": get(args.engine + "/api/version"), "model": args.model,
                  "native_fields": counts, "expected_tok_s": expected,
                  "captured_tok_s": {key:state[key]["rate"] for key in ("read", "write")},
                  "model_size": selected["size"], "model_size_vram": selected["size_vram"],
                  "gpu_samples": gpu_samples, "result": "PASS", "scope": "Integration check, not isolated performance benchmark"}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: report[key] for key in ["result", "native_fields", "captured_tok_s", "model_size", "model_size_vram"]}, indent=2))
    finally:
        stopped.set()
        thread.join(timeout=3)

if __name__ == "__main__":
    main()
