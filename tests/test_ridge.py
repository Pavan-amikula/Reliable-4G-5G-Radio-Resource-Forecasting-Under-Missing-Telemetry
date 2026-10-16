import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from train_ridge import pipeline


class RidgeProtocol(unittest.TestCase):
    def test_imputer_and_scaler_are_training_only(self):
        x=np.array([[1.,np.nan],[3.,8.],[5.,12.]])
        model=pipeline(1.)
        model.fit(x,np.array([2.,4.,6.]))
        imputer=model.named_steps['simpleimputer']
        scaler=model.named_steps['standardscaler']
        np.testing.assert_allclose(imputer.statistics_,[3.,10.])
        before=scaler.mean_.copy()
        model.predict(np.array([[1e6,np.nan]]))
        np.testing.assert_array_equal(scaler.mean_,before)
        self.assertEqual(scaler.n_samples_seen_,3)

    def test_empty_training_column_stays_usable(self):
        model=pipeline(.1)
        model.fit(np.array([[1.,np.nan],[2.,np.nan],[3.,np.nan]]),np.array([1.,2.,3.]))
        self.assertTrue(np.isfinite(model.predict(np.array([[4.,np.nan]]))).all())
