"""Loopback-only capture proxy. Payloads are forwarded, not logged or stored."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from .adapters import response_timing
from .config import auth_headers

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
       "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length", "accept-encoding"}

class CaptureProxy:
    def __init__(self, config_getter, store, port=18630):
        self.config_getter, self.store = config_getter, store
        outer = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args):
                pass
            def do_GET(self):
                if self.path == "/__token_speedometer__/state":
                    value = outer.store.sample(outer.config_getter().get("model", ""))
                    data = json.dumps(value, allow_nan=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.forward()
            def do_POST(self): self.forward()
            def do_OPTIONS(self): self.forward()
            def do_DELETE(self): self.forward()
            def forward(self):
                config = dict(outer.config_getter())
                key = None
                epoch = outer.store.epoch
                self.response_started = False
                if not self.path.startswith("/") or self.path.startswith("//") or urlsplit(self.path).scheme:
                    self.send_error(400, "Only upstream-relative paths are accepted.")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 0 or length > 32 * 1024 * 1024 or self.headers.get("Transfer-Encoding"):
                        self.send_error(413, "Use a Content-Length request of at most 32 MiB.")
                        return
                    body = self.rfile.read(length) if length else None
                    model = ""
                    if body:
                        try:
                            request_value = json.loads(body)
                            model = request_value.get("model", "") if isinstance(request_value, dict) else ""
                        except (ValueError, UnicodeDecodeError):
                            pass
                    key = outer.store.begin(config["backend"], model)
                    headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
                    headers["Accept-Encoding"] = "identity"
                    for k, v in auth_headers(config).items():
                        headers.setdefault(k, v)
                    request = urllib.request.Request(config["upstream"] + self.path, data=body,
                                                     headers=headers, method=self.command)
                    try:
                        response = urllib.request.urlopen(request, timeout=600)
                    except urllib.error.HTTPError as exc:
                        response = exc
                    with response:
                        self.response_started = True
                        self.send_response(response.status)
                        for k, v in response.headers.items():
                            if k.lower() not in HOP:
                                self.send_header(k, v)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        streaming = any(kind in response.headers.get("Content-Type", "").lower()
                                        for kind in ["event-stream", "ndjson", "jsonlines"])
                        captured = bytearray()
                        while True:
                            chunk = response.readline(65536) if streaming else response.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                            if len(captured) + len(chunk) <= 2_000_000:
                                captured.extend(chunk)
                            else:
                                captured.clear()
                            if streaming and chunk.endswith(b"\n"):
                                self.observe(bytes(captured), config, model, epoch)
                                captured.clear()
                        if not streaming and captured:
                            self.observe(bytes(captured), config, model, epoch)
                    self.close_connection = True
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True
                except Exception:
                    if not self.wfile.closed and not self.response_started:
                        try:
                            self.send_error(502, "The configured inference server is unavailable.")
                        except OSError:
                            pass
                    self.close_connection = True
                finally:
                    if key:
                        outer.store.finish(key)
            def observe(self, raw, config, model, epoch):
                try:
                    line = raw.strip()
                    if line.startswith(b"data:"):
                        line = line[5:].strip()
                    if not line or line == b"[DONE]":
                        return
                    value = json.loads(line)
                    result = response_timing(value, config["backend"], model, time.monotonic())
                    if result:
                        result["observed_at"] = time.monotonic()
                        outer.store.observe(result, epoch)
                except (ValueError, TypeError, UnicodeDecodeError, KeyError):
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.thread = None
    @property
    def port(self):
        return self.server.server_address[1]
    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="capture-proxy")
        self.thread.start()
    def close(self):
        if self.thread:
            self.server.shutdown()
        self.server.server_close()
