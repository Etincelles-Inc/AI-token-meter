import unittest
from token_speedometer.vllm_core import Metrics, PrefillMeter, DecodeMeter, parse_metrics

class PrefillTests(unittest.TestCase):
    @staticmethod
    def metric(tokens, seconds, count, time_count=None):
        return Metrics(100, 1000000, 1, 0, .1, tokens, seconds, count, count if time_count is None else time_count)
    def test_uses_measured_prefill_time_not_scrape_interval(self):
        meter = PrefillMeter()
        meter.update(0, self.metric(100000, 100, 1))
        self.assertEqual(meter.update(1, self.metric(220000, 180, 2)), 1500)
        self.assertTrue(meter.new)
        self.assertEqual(meter.kind, "Last prefill")
    def test_initial_average_is_explicitly_labeled(self):
        meter = PrefillMeter()
        self.assertEqual(meter.update(10, self.metric(20000, 10, 2)), 2000)
        self.assertEqual(meter.kind, "Run average")
        self.assertFalse(meter.new)
    def test_no_new_completion_keeps_last_observation(self):
        meter = PrefillMeter()
        meter.update(0, self.metric(1000, 1, 1))
        meter.update(1, self.metric(3000, 3, 2))
        self.assertEqual(meter.update(8, self.metric(3000, 3, 2)), 1000)
        self.assertFalse(meter.new)
        self.assertEqual(meter.updated_at, 1)
    def test_multiple_completions_are_time_weighted(self):
        meter = PrefillMeter()
        meter.update(0, self.metric(1000, 1, 1))
        self.assertEqual(meter.update(1, self.metric(4000, 3, 3)), 1500)
        self.assertEqual(meter.requests, 2)
    def test_reset_has_no_negative_or_artificial_peak(self):
        meter = PrefillMeter()
        meter.update(0, self.metric(100000, 100, 20))
        self.assertIsNone(meter.update(1, self.metric(0, 0, 0)))
        self.assertEqual(meter.update(2, self.metric(1000, 2, 1)), 500)
    def test_mismatched_histogram_counts_wait_for_consistent_scrape(self):
        meter = PrefillMeter()
        meter.update(0, self.metric(1000, 1, 1))
        self.assertEqual(meter.update(1, self.metric(9000, 1, 2, 1)), 1000)
        self.assertFalse(meter.new)
        self.assertEqual(meter.update(2, self.metric(9000, 5, 2)), 2000)
    def test_missing_timing_does_not_fall_back_to_cached_prompt_rate(self):
        meter = PrefillMeter()
        self.assertIsNone(meter.update(0, Metrics(10, 100000, 1, 0, .1)))
        self.assertEqual(meter.kind, "Prefill timing unavailable")

class DecodeTests(unittest.TestCase):
    @staticmethod
    def metric(generated, first, interval_seconds, intervals, active=1,
               total=None, requests=None, decode_seconds=None):
        return Metrics(generated, 0, active, 0, .1,
            decode_tokens=total, decode_count=requests, decode_seconds=decode_seconds,
            decode_time_count=requests, first_token_count=first,
            inter_token_seconds=interval_seconds, inter_token_count=intervals)
    def test_live_rate_uses_engine_seconds_not_polling_gap(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(0, 0, 0, 0))
        self.assertAlmostEqual(meter.update(200, self.metric(150, 1, 3, 149)), 149 / 3)
        self.assertEqual(meter.kind, "Live engine time")
    def test_completed_rate_excludes_first_output_token(self):
        meter = DecodeMeter()
        value = meter.update(0, self.metric(150, 1, 3, 149, active=0, total=150, requests=1, decode_seconds=3))
        self.assertAlmostEqual(value, 149 / 3)
        self.assertEqual(meter.kind, "Run average")
    def test_latest_completed_request_uses_its_decode_duration(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(150, 1, 3, 149, active=0, total=150, requests=1, decode_seconds=3))
        value = meter.update(60, self.metric(251, 2, 5, 249, active=0, total=251, requests=2, decode_seconds=5))
        self.assertEqual(value, 50)
        self.assertEqual(meter.kind, "Last decode")
    def test_idle_does_not_turn_engine_speed_into_zero(self):
        meter = DecodeMeter()
        m = self.metric(101, 1, 2, 100, active=0, total=101, requests=1, decode_seconds=2)
        self.assertEqual(meter.update(0, m), 50)
        self.assertEqual(meter.update(1000, m), 50)
        self.assertFalse(meter.new)
    def test_speculative_chunk_count_is_not_token_count(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(0, 0, 0, 0))
        self.assertEqual(meter.update(1, self.metric(151, 1, 3, 40)), 50)
    def test_first_token_is_subtracted_once_per_request_not_per_refresh(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(0, 0, 0, 0))
        self.assertEqual(meter.update(1, self.metric(51, 1, 1, 20)), 50)
        self.assertEqual(meter.update(10, self.metric(101, 1, 2, 40)), 50)
    def test_first_token_only_has_no_decode_rate(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(0, 0, 0, 0))
        self.assertIsNone(meter.update(1, self.metric(1, 1, 0, 0)))
    def test_reset_discards_old_live_baseline(self):
        meter = DecodeMeter()
        meter.update(0, self.metric(50000, 100, 1000, 20000))
        self.assertIsNone(meter.update(1, self.metric(0, 0, 0, 0)))
        self.assertEqual(meter.update(2, self.metric(101, 1, 2, 25)), 50)
    def test_completed_fallback_when_live_counters_absent(self):
        meter = DecodeMeter()
        m = Metrics(101, 0, 0, 0, .1, decode_tokens=101, decode_count=1, decode_seconds=2, decode_time_count=1)
        self.assertEqual(meter.update(10, m), 50)
    def test_one_token_completed_request_has_no_division_by_zero(self):
        meter = DecodeMeter()
        self.assertIsNone(meter.update(0, self.metric(1, 1, 0, 0, active=0, total=1, requests=1, decode_seconds=0)))
