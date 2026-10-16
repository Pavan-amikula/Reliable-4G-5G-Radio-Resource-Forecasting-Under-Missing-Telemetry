import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from train_intervals import pinball,calibration_amount,adjusted,interval_metrics,predict_quantiles


class FixedPrediction:
    def __init__(self,value): self.value=value
    def predict(self,x): return np.full(len(x),self.value)


class IntervalRules(unittest.TestCase):
    def test_pinball_asymmetry(self):
        self.assertAlmostEqual(pinball([10],[0],.95),9.5)
        self.assertAlmostEqual(pinball([0],[10],.95),.5)

    def test_finite_sample_rank_and_nonshrinking(self):
        q=np.tile([0.,1.,2.],(9,1))
        self.assertEqual(calibration_amount(np.arange(9.),q),6.)
        self.assertEqual(calibration_amount(np.ones(9),q),0.)
        with self.assertRaises(ValueError):calibration_amount(np.ones(1),q[:1])

    def test_clipping_and_widening(self):
        q=np.array([[1.,50.,99.]])
        result=adjusted(q,5.)
        np.testing.assert_array_equal(result,[[0.,50.,100.]])
        np.testing.assert_array_equal(q,[[1.,50.,99.]])

    def test_crossing_repaired_before_scoring(self):
        q,cross=predict_quantiles([FixedPrediction(70),FixedPrediction(30),FixedPrediction(50)],np.zeros((2,1)))
        np.testing.assert_array_equal(q,[[30,50,70],[30,50,70]])
        self.assertTrue(cross.all())

    def test_metrics_and_boundary_inclusion(self):
        m=interval_metrics([0.,5.,10.],[[0,1,2],[4,5,6],[8,9,10]])
        self.assertEqual(m['coverage'],1.)
        self.assertEqual(m['mean_width_pp'],2.)
