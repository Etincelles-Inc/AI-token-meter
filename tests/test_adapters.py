import json
import unittest
from unittest.mock import patch
from token_speedometer.adapters import response_timing, MetricsAdapter, detect, series
from token_speedometer.config import validate_config
from token_speedometer.state import EventStore
from token_speedometer.vllm_core import parse_metrics

class AdapterTests(unittest.TestCase):
    def test_ollama_native_nanoseconds_not_polling_time(self):
        payload = {"done": True, "model": "coder", "prompt_eval_count": 2000, "prompt_eval_duration": 800000000,
                   "eval_count": 150, "eval_duration": 3000000000}
        value = response_timing(payload, "ollama", "", 800)
        self.assertEqual(value["read"]["rate"], 2500)
        self.assertEqual(value["write"]["rate"], 50)
        self.assertEqual(value["observed_at"], 800)
    def test_llama_prefers_engine_reported_rates(self):
        value = response_timing({"timings": {"prompt_per_second": 1500, "predicted_per_second": 51}}, "llamacpp", "m", 0)
        self.assertEqual(value["read"]["rate"], 1500)
        self.assertEqual(value["write"]["rate"], 51)
    def test_hook_excludes_first_token_once(self):
        value = response_timing({"token_speedometer": {"uncached_prompt_tokens": 2000, "prefill_seconds": .8,
            "output_tokens": 151, "decode_seconds": 3}}, "native", "m", 0)
        self.assertEqual(value["read"]["rate"], 2500)
        self.assertEqual(value["write"]["rate"], 50)
    def test_openai_usage_does_not_invent_native_timing(self):
        self.assertIsNone(response_timing({"usage": {"prompt_tokens": 2000, "completion_tokens": 150}}, "native", "m", 0))
    def test_zero_duration_missing_fields_do_not_divide_by_zero(self):
        value = response_timing({"done": True, "eval_duration": 0, "eval_count": 1}, "ollama", "m", 0)
        self.assertIsNone(value["write"]["rate"])
        self.assertIsNone(value["read"]["rate"])
    def test_model_labels_escape_and_filter(self):
        text = 'vllm:generation_tokens_total{model_name="a\\\\b"} 10\nvllm:generation_tokens_total{model_name="other"} 900'
        self.assertEqual(parse_metrics(text, "a\\b").generated, 10)
        self.assertEqual(parse_metrics(text).generated, 910)
    def test_model_absent_is_unavailable(self):
        with self.assertRaises(ValueError):
            parse_metrics('vllm:generation_tokens_total{model_name="other"} 900', "wanted")
    def test_auto_detect_ollama_even_when_metrics_404(self):
        def fake(url, *_args, **_kwargs):
            if url.endswith("/metrics"):
                raise OSError("404")
            return '{"version":"1.0"}'
        with patch("token_speedometer.adapters.fetch", side_effect=fake):
            result = detect(validate_config({"upstream": "http://127.0.0.1:11434"}))
        self.assertEqual(result["backend"], "ollama")
    def test_llama_idle_holds_previous_engine_timing(self):
        metrics = "\n".join(f"{k} {v}" for k, v in {
            "llamacpp:prompt_tokens_total": 2000, "llamacpp:prompt_seconds_total": 1,
            "llamacpp:tokens_predicted_total": 100, "llamacpp:tokens_predicted_seconds_total": 2}.items())
        adapter = MetricsAdapter()
        first = adapter.sample(metrics, {"backend": "llamacpp", "model": ""}, 1)
        later = adapter.sample(metrics, {"backend": "llamacpp", "model": ""}, 99)
        self.assertEqual(first["write"]["rate"], 50)
        self.assertEqual(later["write"]["rate"], 50)
        self.assertEqual(later["write"]["updated_at"], 1)
        self.assertFalse(later["write"]["new"])
    def test_unsafe_urls_rejected(self):
        for url in ["file:///tmp/a", "http://user:pass@localhost", "http://localhost?key=secret"]:
            with self.assertRaises(ValueError):
                validate_config({"upstream": url})
    def test_store_model_selection_and_privacy(self):
        store = EventStore()
        for name, now in [("one", 1), ("two", 2)]:
            store.observe(response_timing({"done": True, "eval_count": 100, "eval_duration": 2000000000},
                                         "ollama", name, now))
        self.assertEqual(store.sample()["model"], "two")
        self.assertEqual(store.sample("one")["model"], "one")
        self.assertNotIn("prompt", json.dumps(store.sample()))

    def test_store_rejects_response_from_old_connection(self):
        store = EventStore()
        old_epoch = store.epoch
        store.clear()
        value = response_timing({"done":True,"eval_count":100,"eval_duration":1000000000}, "ollama","old",0)
        store.observe(value, old_epoch)
        self.assertIsNone(store.sample()["write"]["rate"])
