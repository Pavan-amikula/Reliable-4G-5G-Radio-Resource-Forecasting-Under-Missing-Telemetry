import sys
from pathlib import Path
import unittest
import numpy as np
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from train_hgb import model_for


class HGBProtocol(unittest.TestCase):
    def test_no_internal_random_validation(self):
        model=model_for(15)
        self.assertIs(model.early_stopping,False)
        self.assertEqual(model.max_iter,200)
        self.assertEqual(model.max_leaf_nodes,15)

    def test_missing_inputs_and_deterministic_prediction(self):
        x=np.arange(120,dtype=float).reshape(60,2)
        x[::3,1]=np.nan
        model=model_for(15)
        with threadpool_limits(limits=2):
            model.fit(x,np.arange(60,dtype=float))
            before=model.predict(x[:5])
            model.predict(np.array([[1e6,np.nan]]))
            np.testing.assert_array_equal(before,model.predict(x[:5]))
        self.assertTrue(np.isfinite(before).all())
        self.assertEqual(model.n_iter_,200)
