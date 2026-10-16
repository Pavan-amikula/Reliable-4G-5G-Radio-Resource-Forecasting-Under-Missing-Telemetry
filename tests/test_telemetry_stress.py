import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from stress_telemetry import features_at,fallback,hidden


class TelemetryStressRules(unittest.TestCase):
    def test_removed_timestamp_cannot_survive_in_lags_or_mean(self):
        visible={0:10.,1800:30.}
        x,age,last=features_at(visible,sorted(visible),2700)
        self.assertTrue(np.isnan(x[0]))
        self.assertEqual(x[1],30.)
        self.assertTrue(np.isnan(x[2]))
        self.assertEqual(x[6],2)
        self.assertEqual(x[7],20.)
        self.assertEqual(age,15.)
        self.assertEqual(last,30.)

    def test_future_values_cannot_change_features(self):
        a=features_at({0:5.,900:9.},[0,900],900)[0]
        b=features_at({0:5.,900:9.,1800:100.},[0,900,1800],900)[0]
        np.testing.assert_allclose(a,b,equal_nan=True)

    def test_stale_cutoff_and_zero(self):
        self.assertEqual(fallback(False,60.,0.,25.),(0.,'stale_persistence',False))
        self.assertEqual(fallback(False,75.,10.,25.),(None,'abstain',False))
        self.assertEqual(fallback(False,None,None,25.),(None,'abstain',False))
        self.assertEqual(fallback(True,0.,10.,25.),(25.,'fresh_model',True))

    def test_hour_mask_has_four_consecutive_slots_each_day(self):
        flags=[hidden('Site 16','1',i*900,'synthetic_hour') for i in range(96)]
        ids=np.flatnonzero(flags)
        self.assertEqual(len(ids),4)
        np.testing.assert_array_equal(np.diff(ids),[1,1,1])

    def test_schedule_deterministic(self):
        a=[hidden('Site 16','1',i*900,'synthetic_drop10') for i in range(100)]
        b=[hidden('Site 16','1',i*900,'synthetic_drop10') for i in range(100)]
        self.assertEqual(a,b)
