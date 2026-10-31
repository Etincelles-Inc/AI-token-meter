"""Normalize engine-native timing; never infer token counts from text."""
import json
import math
import re
import urllib.request
from .config import auth_headers
from .vllm_core import parse_metrics, PrefillMeter, DecodeMeter

def finite(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0 else None

def ratio(tokens, seconds):
    tokens, seconds = finite(tokens), finite(seconds)
    return tokens / seconds if tokens is not None and seconds and seconds > 0 else None

def observation(read, write, engine, model, basis, now, **extra):
    def item(rate):
        return {"rate": finite(rate), "kind": basis, "new": rate is not None,
                "updated_at": now, "requests": 1}
    return {"read": item(read), "write": item(write), "engine": engine, "model": model or "",
            "online": True, "message": "", "observed_at": now, **extra}

def response_timing(payload, engine, model, now):
    """Recognize native fields only; ordinary OpenAI usage is insufficient."""
    if not isinstance(payload, dict):
        return None
    model = payload.get("model") or model or ""
    if payload.get("done") and ("eval_duration" in payload or "prompt_eval_duration" in payload):
        read = ratio(payload.get("prompt_eval_count"), (finite(payload.get("prompt_eval_duration")) or 0) / 1e9)
        write = ratio(payload.get("eval_count"), (finite(payload.get("eval_duration")) or 0) / 1e9)
        return observation(read, write, "ollama", model, "Ollama native / last request", now)
    timings = payload.get("timings")
    if isinstance(timings, dict):
        read = finite(timings.get("prompt_per_second"))
        if read is None:
            read = ratio(timings.get("prompt_n"), (finite(timings.get("prompt_ms")) or 0) / 1000)
        write = finite(timings.get("predicted_per_second"))
        if write is None:
            write = ratio(timings.get("predicted_n"), (finite(timings.get("predicted_ms")) or 0) / 1000)
        if read is not None or write is not None:
            return observation(read, write, "llamacpp", model, "llama.cpp native timing", now)
    native = payload.get("token_speedometer")
    if isinstance(native, dict):
        read = ratio(native.get("uncached_prompt_tokens"), native.get("prefill_seconds"))
        count = finite(native.get("output_tokens"))
        write = ratio(max(0, count - 1) if count is not None else None, native.get("decode_seconds"))
        if read is not None or write is not None:
            return observation(read, write, engine or "native", model, "Engine timing hook", now)
    return None

def series(text):
    pattern = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([^\s]+)')
    labels = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')
    result = []
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            try:
                value = finite(match[3])
                tag = {k: json.loads('"' + v + '"') for k, v in labels.findall(match[2] or "")}
                if value is not None:
                    result.append((match[1], tag, value))
            except (ValueError, json.JSONDecodeError):
                continue
    return result

def fetch(url, config, timeout=3):
    request = urllib.request.Request(url, headers={"Accept": "application/json, text/plain", **auth_headers(config)})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(4_000_000).decode("utf-8")

def models(config, backend=None):
    backend = backend or config["backend"]
    path = "/api/tags" if backend == "ollama" else "/v1/models"
    value = json.loads(fetch(config["upstream"] + path, config))
    return [x["name"] for x in value.get("models", [])] if backend == "ollama" else [x["id"] for x in value.get("data", [])]

def detect(config):
    if config["backend"] != "auto":
        return dict(config)
    bases = [config["upstream"]]
    if config["upstream"] == "http://127.0.0.1:8000":
        bases += ["http://127.0.0.1:11434", "http://127.0.0.1:8080"]
    for base in bases:
        candidate = {**config, "upstream": base}
        try:
            parsed = series(fetch(base + "/metrics", candidate, timeout=1))
            for prefix, backend in [("vllm:", "vllm"), ("llamacpp:", "llamacpp")]:
                if any(n.startswith(prefix) for n, _, _ in parsed):
                    return {**candidate, "backend": backend}
        except (OSError, ValueError):
            pass
        try:
            value = json.loads(fetch(base + "/api/version", candidate, timeout=1))
            if "version" in value:
                return {**candidate, "backend": "ollama"}
        except (OSError, ValueError):
            pass
    raise RuntimeError("No supported engine found. Choose Engine / model.")

class MetricsAdapter:
    def __init__(self):
        self.read_meter = PrefillMeter()
        self.write_meter = DecodeMeter()
        self.last_llama = None
        self.last_llama_sample = None
    def sample(self, text, config, now):
        backend, model = config["backend"], config.get("model") or None
        rows = series(text)
        if backend == "vllm":
            choices = sorted({labels["model_name"] for name, labels, _ in rows if name.startswith("vllm:") and "model_name" in labels})
            selected = model or (choices[0] if len(choices) == 1 else None)
            metrics = parse_metrics(text, selected)
            self.read_meter.update(now, metrics)
            self.write_meter.update(now, metrics)
            return {"read": self.read_meter.snapshot(), "write": self.write_meter.snapshot(),
                    "engine": "vLLM", "model": selected or "All models (time-weighted)",
                    "online": True, "active": metrics.active, "queued": metrics.queued,
                    "cache": metrics.cache, "message": ""}
        values = {}
        for name, labels, value in rows:
            if model and labels.get("model_name") not in (None, model):
                continue
            values[name] = values.get(name, 0) + value
        keys = ["llamacpp:prompt_tokens_total", "llamacpp:prompt_seconds_total",
                "llamacpp:tokens_predicted_total", "llamacpp:tokens_predicted_seconds_total"]
        if not all(k in values for k in keys):
            raise ValueError("llama.cpp timing metrics unavailable; enable --metrics or use the capture proxy.")
        current = tuple(values[k] for k in keys)
        reset = self.last_llama is None or any(a < b for a, b in zip(current, self.last_llama))
        prior = (0, 0, 0, 0) if reset else self.last_llama
        dt = [a - b for a, b in zip(current, prior)]
        previous = self.last_llama_sample
        read = ratio(dt[0], dt[1]) if dt[1] else (previous["read"]["rate"] if previous else None)
        write = ratio(dt[2], dt[3]) if dt[3] else (previous["write"]["rate"] if previous else None)
        output = observation(read, write, "llama.cpp", model or "Server model",
                             "Run average" if reset else "llama.cpp engine timing", now,
                             active=round(values.get("llamacpp:requests_processing", 0)),
                             queued=round(values.get("llamacpp:requests_deferred", 0)), cache=None)
        for key, seconds in [("read", dt[1]), ("write", dt[3])]:
            if not reset and not seconds and previous:
                output[key] = {**previous[key], "new": False}
        self.last_llama, self.last_llama_sample = current, output
        return output
