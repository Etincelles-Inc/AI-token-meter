import unittest
from token_speedometer.idle_display import IdleDisplay
from token_speedometer.adapters import observation

class IdleDisplayTests(unittest.TestCase):
    def sample(self, active=0, stamp=10):
        return observation(2000, 50, "test", "model", "Native timing", stamp, active=active, queued=0)
    def test_zero_at_five_seconds_without_changing_engine_sample(self):
        meter=IdleDisplay();sample=self.sample()
        self.assertEqual(meter.apply(10,sample)["write"]["rate"],50)
        self.assertEqual(meter.apply(14.99,sample)["write"]["rate"],50)
        self.assertEqual(meter.apply(15,sample)["write"]["rate"],0)
        self.assertEqual(meter.apply(15,sample)["read"]["rate"],0)
        self.assertEqual(sample["write"]["rate"],50)
    def test_active_request_is_not_idle_when_timing_is_delayed(self):
        meter=IdleDisplay()
        meter.apply(10,self.sample(active=1))
        self.assertEqual(meter.apply(40,self.sample(active=1))["write"]["rate"],50)
        self.assertEqual(meter.apply(41,self.sample())["write"]["rate"],50)
        self.assertEqual(meter.apply(46,self.sample())["write"]["rate"],0)
    def test_zero_stays_until_a_new_reading_even_if_request_starts(self):
        meter=IdleDisplay();sample=self.sample()
        meter.apply(10,sample);meter.apply(15,sample)
        self.assertEqual(meter.apply(16,self.sample(active=1))["write"]["rate"],0)
        self.assertEqual(meter.apply(17,self.sample(active=1,stamp=17))["write"]["rate"],50)
    def test_repeated_new_flag_does_not_reset_idle_timeout(self):
        meter=IdleDisplay();sample=self.sample()
        self.assertTrue(sample["write"]["new"])
        for now in range(10,16):result=meter.apply(now,sample)
        self.assertEqual(result["write"]["rate"],0)
    def test_only_dial_with_new_measurement_wakes_up(self):
        meter=IdleDisplay();sample=self.sample()
        meter.apply(10,sample);meter.apply(15,sample)
        sample["read"]["updated_at"]=16
        value=meter.apply(16,sample)
        self.assertEqual(value["read"]["rate"],2000)
        self.assertEqual(value["write"]["rate"],0)
    def test_offline_is_unavailable_not_falsely_idle(self):
        from token_speedometer.state import empty
        meter=IdleDisplay();sample=empty()
        meter.apply(0,sample)
        self.assertIsNone(meter.apply(20,sample)["write"]["rate"])
