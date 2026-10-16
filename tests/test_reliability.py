import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_reliability import resample_blocks,memory_stats


class ReliabilityRules(unittest.TestCase):
    def test_constant_paired_difference_is_preserved(self):
        blocks={(s,d):[10,20,30,9,100] for s in ('A','B') for d in ('2025-04-26','2025-04-27','2025-04-28')}
        result=resample_blocks(blocks,repeats=20)
        q=result['summaries']['error_difference_pp']
        self.assertEqual(q['estimate'],-1.)
        self.assertEqual(q['resampling_low'],-1.)
        self.assertEqual(q['resampling_high'],-1.)
        self.assertEqual(result['n'],60)

    def test_resampling_reproducible_and_holdout_is_one_station(self):
        blocks={('A','2025-04-26'):[10,20,30,9,100],('A','2025-04-27'):[8,24,16,6,80]}
        a=resample_blocks(blocks,repeats=20,seed=4)
        self.assertEqual(a,resample_blocks(blocks,repeats=20,seed=4))
        self.assertEqual(a['station_count'],1)

    @unittest.skipUnless(sys.platform=='win32','Windows-specific counters')
    def test_process_memory_counters_valid(self):
        m=memory_stats()
        self.assertGreater(m['working_set_mib'],0)
        self.assertGreaterEqual(m['peak_working_set_mib'],m['working_set_mib'])
