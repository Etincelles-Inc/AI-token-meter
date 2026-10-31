import copy
import threading
import time
from .adapters import MetricsAdapter, detect, fetch
from .state import EventStore, empty

class Controller:
    def __init__(self, config):
        self.lock = threading.Lock()
        self.config = dict(config)
        self.value = empty()
        self.store = EventStore()
        self.stopped = threading.Event()
        self.revision = 0
        self.thread = threading.Thread(target=self.poll, daemon=True, name="engine-metrics")
    def get_config(self):
        with self.lock: return dict(self.config)
    def configure(self, config):
        with self.lock:
            self.config = dict(config)
            self.store.clear()
            self.revision += 1
            self.value = empty()
    def snapshot(self):
        with self.lock: return copy.deepcopy(self.value)
    def start(self): self.thread.start()
    def close(self): self.stopped.set()
    def poll(self):
        seen, adapter, resolved = -1, None, None
        health_at = 0
        while not self.stopped.is_set():
            with self.lock:
                revision, config = self.revision, dict(self.config)
            try:
                if revision != seen:
                    resolved = detect(config)
                    adapter, seen = MetricsAdapter(), revision
                    health_at = 0
                    with self.lock:
                        if revision == self.revision:
                            # Resolve auto-detection for the capture proxy as well.
                            self.config.update(backend=resolved["backend"], upstream=resolved["upstream"])
                backend = resolved["backend"]
                if backend in ("vllm", "llamacpp"):
                    value = adapter.sample(fetch(resolved["upstream"] + "/metrics", resolved), resolved, time.monotonic())
                else:
                    if backend == "ollama" and time.monotonic() - health_at > 5:
                        fetch(resolved["upstream"] + "/api/version", resolved)
                        health_at = time.monotonic()
                    value = self.store.sample(resolved.get("model", ""))
                    value["engine"] = value.get("engine") or backend
                    value["model"] = value.get("model") or resolved.get("model", "")
                    value["online"] = backend == "ollama" or value["online"] or value["active"] > 0
                with self.lock:
                    if revision == self.revision:
                        self.value = value
            except Exception as exc:
                with self.lock:
                    if revision == self.revision:
                        self.value = empty(str(exc))
                if resolved is None:
                    seen = -1
            self.stopped.wait(1)
