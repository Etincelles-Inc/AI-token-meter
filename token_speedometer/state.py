import copy
import threading
import time

def empty(message="Waiting for engine timing"):
    item = {"rate": None, "kind": "Unavailable", "new": False, "updated_at": None, "requests": 0}
    return {"read": dict(item), "write": dict(item), "engine": "", "model": "",
            "online": False, "active": 0, "queued": 0, "cache": None, "message": message}

class EventStore:
    """Only numeric timing and model identifiers are retained. No request bodies."""
    def __init__(self):
        self.lock = threading.Lock()
        self.events = {}
        self.active = {}
        self.latest = None
        self.epoch = 0
    def begin(self, engine, model):
        with self.lock:
            key = (engine, model or "")
            self.active[key] = self.active.get(key, 0) + 1
            self.latest = key
        return key
    def finish(self, key):
        with self.lock:
            self.active[key] = max(0, self.active.get(key, 0) - 1)
    def clear(self):
        with self.lock:
            self.events.clear()
            self.active.clear()
            self.epoch += 1
    def observe(self, value, epoch=None):
        with self.lock:
            if epoch is not None and epoch != self.epoch:
                return
            key = (value["engine"], value.get("model") or "")
            self.events[key] = copy.deepcopy(value)
            self.latest = key
            while len(self.events) > 64:
                oldest = min(self.events, key=lambda k: self.events[k].get("observed_at", 0))
                del self.events[oldest]
    def sample(self, model=""):
        with self.lock:
            candidates = [(k, v) for k, v in self.events.items() if not model or k[1] == model]
            selected = max(candidates, key=lambda pair: pair[1].get("observed_at", 0)) if candidates else None
            value = copy.deepcopy(selected[1]) if selected else empty("Route requests through the local capture proxy to receive native timings.")
            value["active"] = sum(n for (_, m), n in self.active.items() if not model or m == model)
            value["queued"] = 0
            if value["active"] and not selected:
                value["message"] = "Request running; waiting for native response timing."
            return value
