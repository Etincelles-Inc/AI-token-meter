from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
import urllib.request
import urllib.error
from token_speedometer.proxy import CaptureProxy
from token_speedometer.state import EventStore

class ProxyTests(unittest.TestCase):
    def setUp(self):
        outer = self
        self.last_headers = {}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                outer.last_headers = dict(self.headers)
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.path == "/error":
                    self.send_response(429); self.end_headers(); self.wfile.write(b'{"error":"busy"}'); return
                value = {"done": True, "model": "fixture", "eval_count": 150, "eval_duration": 3000000000,
                         "prompt_eval_count": 2000, "prompt_eval_duration": 800000000}
                final = json.dumps(value).encode()
                streaming = self.path == "/stream"
                outer.expected = b'{"response":"PRIVATE_OUTPUT","done":false}\n' + final + b"\n" if streaming else final
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson" if streaming else "application/json")
                self.send_header("X-Engine", "fixture")
                self.end_headers()
                self.wfile.write(outer.expected)
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.upstream.serve_forever, daemon=True); self.thread.start()
        self.store = EventStore()
        self.proxy = CaptureProxy(lambda: {"backend": "ollama", "upstream": f"http://127.0.0.1:{self.upstream.server_port}"}, self.store, 0)
        self.proxy.start()
        self.base = f"http://127.0.0.1:{self.proxy.port}"
    def tearDown(self):
        self.proxy.close(); self.upstream.shutdown(); self.upstream.server_close()
    def request(self, path):
        request = urllib.request.Request(self.base+path,
            data=b'{"model":"fixture","prompt":"PRIVATE_INPUT"}', headers={"Content-Type": "application/json", "Authorization":"Bearer test-secret"})
        return urllib.request.urlopen(request, timeout=5)
    def test_stream_forwarded_unchanged_and_native_timings_captured(self):
        with self.request("/stream") as response:
            self.assertEqual(response.read(), self.expected)
            self.assertEqual(response.headers["X-Engine"], "fixture")
        value = self.store.sample()
        self.assertEqual(value["read"]["rate"], 2500)
        self.assertEqual(value["write"]["rate"], 50)
        encoded = json.dumps(value)
        for private in ["PRIVATE_INPUT", "PRIVATE_OUTPUT", "test-secret"]:
            self.assertNotIn(private, encoded)
        self.assertEqual(self.last_headers["Authorization"], "Bearer test-secret")
    def test_nonstream_capture(self):
        with self.request("/api/generate") as response:
            self.assertEqual(response.read(), self.expected)
        self.assertEqual(self.store.sample()["write"]["rate"], 50)
    def test_upstream_error_passes_through(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/error")
        self.assertEqual(raised.exception.code, 429)
        self.assertEqual(raised.exception.read(), b'{"error":"busy"}')
        raised.exception.close()
    def test_loopback_only_and_numeric_state(self):
        self.assertEqual(self.proxy.server.server_address[0], "127.0.0.1")
        with urllib.request.urlopen(self.base + "/__token_speedometer__/state") as response:
            value = json.load(response)
        self.assertIsNone(value["write"]["rate"])
