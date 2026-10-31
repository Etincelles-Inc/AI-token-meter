import math

import re

import json

from dataclasses import dataclass

_LABEL = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')

_SAMPLE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([^\s]+)')

@dataclass
class Metrics:
    generated: float
    prompt: float
    active: int
    queued: int
    cache: float
    prefill_tokens: float | None = None
    prefill_seconds: float | None = None
    prefill_count: float | None = None
    prefill_time_count: float | None = None
    decode_tokens: float | None = None
    decode_count: float | None = None
    decode_seconds: float | None = None
    decode_time_count: float | None = None
    first_token_count: float | None = None
    inter_token_seconds: float | None = None
    inter_token_count: float | None = None

def parse_metrics(text, model=None):
    wanted = {
        "vllm:generation_tokens_total": "generated",
        "vllm:prompt_tokens_total": "prompt",
        "vllm:num_requests_running": "active",
        "vllm:num_requests_waiting": "queued",
        "vllm:kv_cache_usage_perc": "cache",
        "vllm:request_prefill_kv_computed_tokens_sum": "prefill_tokens",
        "vllm:request_prefill_time_seconds_sum": "prefill_seconds",
        "vllm:request_prefill_kv_computed_tokens_count": "prefill_count",
        "vllm:request_prefill_time_seconds_count": "prefill_time_count",
        "vllm:request_generation_tokens_sum": "decode_tokens",
        "vllm:request_generation_tokens_count": "decode_count",
        "vllm:request_decode_time_seconds_sum": "decode_seconds",
        "vllm:request_decode_time_seconds_count": "decode_time_count",
        "vllm:time_to_first_token_seconds_count": "first_token_count",
        "vllm:inter_token_latency_seconds_sum": "inter_token_seconds",
        "vllm:inter_token_latency_seconds_count": "inter_token_count",
    }
    values = {key: [] for key in wanted.values()}
    for line in text.splitlines():
        match = _SAMPLE.match(line)
        if not match or match[1] not in wanted:
            continue
        labels = {k: json.loads(chr(34) + v + chr(34)) for k,v in _LABEL.findall(match[2] or "")}
        if model is not None and labels.get("model_name") != model:
            continue
        value = float(match[3])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid server counter")
        values[wanted[match[1]]].append(value)
    if not values["generated"]:
        raise ValueError("No output-token counter for the selected model")
    return Metrics(
        sum(values["generated"]), sum(values["prompt"]),
        round(sum(values["active"])), round(sum(values["queued"])),
        max(values["cache"], default=0.0),
        **{key: sum(values[key]) if values[key] else None for key in ["prefill_tokens", "prefill_seconds", "prefill_count", "prefill_time_count", "decode_tokens", "decode_count", "decode_seconds", "decode_time_count", "first_token_count", "inter_token_seconds", "inter_token_count"]},
    )

class PrefillMeter:
    """Fresh KV tokens / measured prefill duration, for matched completed requests.

    This deliberately does not divide prompt-completion bursts by polling time.
    """
    def __init__(self):
        self.clear()
    def clear(self):
        self.last = None
        self.rate = None
        self.kind = "Waiting for completion"
        self.updated_at = None
        self.requests = 0
        self.new = False
    def update(self, now, metrics):
        self.new = False
        values = (metrics.prefill_tokens, metrics.prefill_seconds,
                  metrics.prefill_count, metrics.prefill_time_count)
        if any(v is None for v in values):
            self.clear()
            self.kind = "Prefill timing unavailable"
            return None
        tokens, seconds, count, time_count = values
        if count != time_count:
            return self.rate  # Skip a scrape taken halfway through a metric update.
        current = (tokens, seconds, count)
        if self.last and any(a < b for a, b in zip(current, self.last)):
            self.clear()
        if self.last is None:
            if count > 0 and seconds > 0:
                self.rate = tokens / seconds
                self.kind = "Run average"
                self.requests = round(count)
        elif count > self.last[2]:
            delta_tokens = tokens - self.last[0]
            delta_seconds = seconds - self.last[1]
            if delta_seconds > 0:
                self.rate = max(0.0, delta_tokens / delta_seconds)
                self.requests = round(count - self.last[2])
                self.kind = "Last prefill" if self.requests == 1 else f"Last {self.requests} prefills"
                self.updated_at = now
                self.new = True
        self.last = current
        return self.rate
    def snapshot(self):
        return {"rate": self.rate, "kind": self.kind, "new": self.new,
                "updated_at": self.updated_at, "requests": self.requests}

class DecodeMeter:
    """Engine-timed decode intervals, with completed-request N-1 / duration.

    Sampling time is used only for display age, never as the rate denominator.
    """
    def __init__(self):
        self.clear()
    def clear(self):
        self.completed = PrefillMeter()
        self.live_last = None
        self.rate = None
        self.kind = "Waiting for decode"
        self.updated_at = None
        self.requests = 0
        self.new = False
    def update(self, now, metrics):
        self.new = False
        live = (metrics.generated, metrics.first_token_count,
                metrics.inter_token_seconds, metrics.inter_token_count)
        valid_live = all(value is not None for value in live)
        if valid_live and self.live_last and any(a < b for a, b in zip(live, self.live_last)):
            self.clear()
        decode_tokens = None
        if metrics.decode_tokens is not None and metrics.decode_count is not None:
            decode_tokens = max(0.0, metrics.decode_tokens - metrics.decode_count)
        completed_metrics = Metrics(0, 0, 0, 0, 0,
            prefill_tokens=decode_tokens, prefill_seconds=metrics.decode_seconds,
            prefill_count=metrics.decode_count, prefill_time_count=metrics.decode_time_count)
        self.completed.update(now, completed_metrics)
        if self.completed.new or self.rate is None:
            self.use_completed()
        if valid_live and self.live_last:
            generated = live[0] - self.live_last[0]
            first_tokens = live[1] - self.live_last[1]
            engine_seconds = live[2] - self.live_last[2]
            interval_count = live[3] - self.live_last[3]
            decode_new_tokens = generated - first_tokens
            if metrics.active > 0 and engine_seconds > 0 and interval_count > 0 and decode_new_tokens > 0:
                self.rate = decode_new_tokens / engine_seconds
                self.kind = "Live engine time"
                self.updated_at = now
                self.new = True
        if metrics.active == 0 and self.completed.rate is not None:
            self.use_completed()
        if valid_live:
            self.live_last = live
        return self.rate
    def use_completed(self):
        self.rate = self.completed.rate
        self.kind = self.completed.kind.replace("prefill", "decode").replace("Prefill", "Decode")
        self.updated_at = self.completed.updated_at
        self.requests = self.completed.requests
        self.new = self.completed.new
    def snapshot(self):
        return {"rate": self.rate, "kind": self.kind, "new": self.new,
                "updated_at": self.updated_at, "requests": self.requests}
