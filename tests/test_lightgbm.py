import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from train_lightgbm import model_for


class LightGBMProtocol(unittest.TestCase):
    def test_cpu_budget_and_zeros(self):
        model=model_for(15)
        self.assertEqual(model.n_jobs,2)
        self.assertEqual(model.n_estimators,300)
        self.assertFalse(model.get_params()['zero_as_missing'])
        self.assertEqual(model.get_params()['device_type'],'cpu')

    def test_missing_inputs_work_and_prediction_does_not_refit(self):
        x=np.arange(120,dtype=float).reshape(60,2)
        x[::3,1]=np.nan
        model=model_for(15)
        model.fit(x,np.arange(60,dtype=float))
        before=model.predict(x[:4])
        model.predict(np.array([[0.,np.nan]]))
        np.testing.assert_array_equal(before,model.predict(x[:4]))
        self.assertTrue(np.isfinite(before).all())
