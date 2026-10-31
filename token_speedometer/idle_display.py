"""Presentation-only idle timeout. Original engine measurements stay intact."""
import copy

class IdleDisplay:
    def __init__(self, seconds=5.0):
        self.seconds = seconds
        self.identity = None
        self.idle_since = None
        self.signatures = {}
        self.zeroed = set()

    def apply(self, now, sample):
        value = copy.deepcopy(sample)
        identity = (sample.get("engine"), sample.get("model"))
        if identity != self.identity or not sample.get("online"):
            self.identity = identity
            self.idle_since = None
            self.signatures.clear()
            self.zeroed.clear()
        if not sample.get("online"):
            return value
        busy = sample.get("active", 0) > 0 or sample.get("queued", 0) > 0
        new_reading = False
        for key in ("read", "write"):
            item = sample[key]
            signature = (item.get("updated_at"), item.get("rate"), item.get("kind"), item.get("requests"))
            if signature != self.signatures.get(key) and item.get("rate") is not None:
                self.zeroed.discard(key)
                new_reading = True
            self.signatures[key] = signature
        if busy:
            self.idle_since = None
        elif self.idle_since is None or new_reading:
            self.idle_since = now
        if self.idle_since is not None and now - self.idle_since >= self.seconds:
            self.zeroed.update(("read", "write"))
        for key in self.zeroed:
            value[key] = {"rate": 0.0, "kind": "Idle / awaiting new reading", "new": False,
                          "updated_at": None, "requests": 0, "idle_zeroed": True}
        value["idle_zeroed"] = bool(self.zeroed)
        return value
