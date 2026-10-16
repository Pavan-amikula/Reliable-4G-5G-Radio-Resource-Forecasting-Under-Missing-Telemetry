# Development and evaluation rules

Reliable 4G/5G Radio Resource Forecasting Under Missing Telemetry forecasts real 4G/5G radio-resource utilization 15, 30 and 60 minutes ahead. Read [the project overview](docs/START_HERE.md), [research notes](docs/Network_PRB_Research.md) and [reproduction guide](docs/Reproduce.md) before modifying the pipeline.

## Environment

The verified environment is Windows x64, Python 3.13.4, an i7-1165G7 and 16 GB RAM. Use a virtual environment and the pinned dependencies. Experiments run on CPU with bounded tuning and two numerical threads. Reuse the included dataset and saved audits.

## Data integrity

- Utilization is already a percentage. Preserve observed zeros and leave missing readings missing.
- Raw station/sector/timestamp keys repeat across padded and energy-only rows. Extract unique nonempty utilization targets; do not select an arbitrary first row.
- Preserve the raw archive, processed observations and saved experimental evidence. Use a new output version for a new experiment.
- Other KPI fields require independent uniqueness and availability checks before merging. Energy modeling is outside the current scope.

## Forecasting protocol

- Match historical inputs and future labels by exact timestamps within each series.
- Use chronological cutoffs shared across cells. Remove training examples whose labels cross a partition boundary.
- Fit preprocessing and models on training data only. Choose settings on tuning data only.
- Use the separate calibration period for range adjustment. Do not tune on final-test results.
- Keep Site 53 out of fitting, preprocessing, model selection and calibration.
- Keep later actual readings out of prediction inputs, including in historical replay.

## Validation and reporting

Run `scripts/verify_project.py`, `python -m pip check` and the test suite as described in the reproduction guide. Report the population, scored-row availability and limitations with each result. Distinguish simulated missing inputs from natural gaps, and measured findings from proposed extensions. Historical replay does not establish live deployment, congestion detection, guaranteed ranges or energy savings.
