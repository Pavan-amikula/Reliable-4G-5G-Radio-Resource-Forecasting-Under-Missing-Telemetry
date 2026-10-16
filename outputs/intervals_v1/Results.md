# Forecast ranges: measured results

The point forecast remains the earlier model chosen using tuning data. Separate LightGBM models estimate a lower value, a middle value and an upper value. The target is a range containing about 90 out of 100 actual readings, while remaining as narrow as practical. This is a target, not a guarantee.

We trained models using training rows, chose tree size using tuning only, then adjusted the ranges using a separate later calibration period. That adjustment was saved before opening final-test tables. The excluded station supplied no training, tuning or calibration rows.

## How often did the actual reading fall inside?

Coverage means the fraction of actual readings inside the range. Width is the average distance between its lower and upper ends, in percentage points. Wider ranges can cover more readings but be less useful. The final rows below are out-of-calibration measurements; calibration scores in the JSON are in-sample diagnostics.

| Station group | Network | Ahead | Readings | Inside before adjustment | Inside after adjustment | Width before | Width after |
|---|---|---:|---:|---:|---:|---:|---:|
| Familiar | 4G | 15 min | 6,859 | 88.2% | 91.2% | 13.29 | 14.14 |
| Familiar | 4G | 30 min | 6,823 | 85.1% | 90.8% | 14.78 | 16.57 |
| Familiar | 4G | 60 min | 6,782 | 83.8% | 90.7% | 15.78 | 18.11 |
| Familiar | 5G | 15 min | 7,138 | 88.1% | 91.2% | 4.91 | 5.07 |
| Familiar | 5G | 30 min | 7,130 | 88.3% | 91.7% | 5.91 | 6.02 |
| Familiar | 5G | 60 min | 7,114 | 88.1% | 91.3% | 6.35 | 6.44 |
| Excluded station | 4G | 15 min | 1,643 | 88.3% | 92.7% | 9.71 | 10.56 |
| Excluded station | 4G | 30 min | 1,629 | 84.0% | 93.6% | 10.76 | 12.55 |
| Excluded station | 4G | 60 min | 1,609 | 81.2% | 92.8% | 11.45 | 13.77 |
| Excluded station | 5G | 15 min | 1,786 | 90.9% | 93.3% | 2.52 | 2.67 |
| Excluded station | 5G | 30 min | 1,784 | 90.2% | 93.4% | 2.94 | 3.05 |
| Excluded station | 5G | 60 min | 1,780 | 91.1% | 94.9% | 3.19 | 3.28 |

## What this does and does not show

The adjustment only widens the original range; it never narrows it. Both bounds stay between 0% and 100%. Quantile crossings are repaired by sorting the three quantile predictions before calibration. Crossing counts are saved. No test answers adjust the correction.

Readings at adjacent times and sectors are related. Because of that dependence and later distribution changes, this procedure does not guarantee 90% coverage for every station, time or future period. We measure coverage and width instead of claiming certainty. Per-sector and fixed load-band metrics, quantile losses, tail misses and interval scores are saved. Sparse high-load groups cannot establish reliable congestion-warning quality.

## Files and their purposes

- 18 `.joblib` files: fitted lower/middle/upper models for each technology and forecast period.
- `selection.json` and `tuning_trials.json`: choices fixed before calibration.
- `calibration.json`: the range-widening amounts fixed before test access.
- `forecasts.csv.gz`: actual readings, separate point predictions, raw and adjusted ranges.
- `metrics.json`: inside-range counts/fractions, widths and other error measures, including each sector and load band.
- `crossings.json`: frequency of unordered raw quantile predictions.
- `coverage.json`: number of eligible questions with ranges.
- `run_manifest.json`: versions, hashes, timing and fixed rules.

Full script time: 28.5 seconds, 36 bounded CPU fits, two threads. Peak process memory has not been measured.

Next process: test what happens when inputs disappear, using clearly labeled artificial outages and separate natural-gap checks. API and recorded-data replay dashboard remain later stages. No live network operation or energy savings have been demonstrated.

Method references: [Conformalized Quantile Regression, Romano et al.](https://papers.nips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html); [LightGBM quantile objective](https://lightgbm.readthedocs.io/en/stable/Parameters.html). Our non-shrinking, physically clipped chronological implementation is documented in selection.json; standard exchangeability-based claims are not assumed.
