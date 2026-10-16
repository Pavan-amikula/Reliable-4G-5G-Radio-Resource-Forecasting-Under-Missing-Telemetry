# Run the included project on Windows

These instructions cover restarting the service, preparing an environment and reproducing the saved experiments. Opening the screen uses existing models and does not require retraining.

## 1. Existing environment: open the screen

In PowerShell, from the project directory:

```powershell
.\.venv\Scripts\python.exe -m networkprb.api --port 8765
```

Expected: `NetworkPRB historical replay API: http://127.0.0.1:8765`. Keep that terminal running and open that address. Stop with Ctrl+C. If the port is occupied by the existing service, open its screen instead of starting a duplicate. An alternative port can be supplied with `--port 8766`.

## 2. A separate computer or fresh environment

Keep the included `data/`, `outputs/`, `networkprb/`, `scripts/`, `tests/`, `docs/`, dependency lock and project instructions together. Do not copy `.venv`; recreate it. The verified environment is **Windows x64, Python 3.13.4, CPU only**. Other Python versions have not been validated with the saved model artifacts. The current environment passes package and model loading checks; these instructions have not been tested as a clean-machine installation.

Check the intended interpreter, then create its environment:

```powershell
py -3.13 --version
py -3.13 -m venv --without-pip .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install --dry-run --only-binary=:all: -r requirements-ml-lock.txt
```

Expected: a compatible wheel resolution for the pinned packages. Stop if resolution fails; do not silently change versions of libraries used to save the models. If compatible, install and check:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-ml-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

No NVIDIA GPU, activation command or execution-policy change is needed. Always use this environment's explicit Python path. Saved `.joblib` files are Python model objects: load the included locally generated trusted artifacts only.

## 3. Verify without retraining

```powershell
.\.venv\Scripts\python.exe scripts\verify_project.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: integrity and package checks pass, six forecast groups load, 20 series are available, and 41 tests pass. This verifies existing artifacts and behavior; it is not a rerun of the complete raw-data audits or all forecasting evaluations. If a check fails, inspect its reported file or package before proceeding.

## 4. Understand experiment reproduction

The included processed tables and trained models are already built. Training scripts deliberately refuse to overwrite existing experiment directories. To reproduce from scratch, make a **separate fresh workspace** containing the original raw archive, source, lock file and instructions, without the generated processed tables or experiment output directories. Keep the delivered workspace intact. Run each stage separately:

```powershell
.\.venv\Scripts\python.exe scripts\forecast_baselines.py extract
.\.venv\Scripts\python.exe scripts\forecast_baselines.py evaluate
.\.venv\Scripts\python.exe scripts\build_supervised.py
.\.venv\Scripts\python.exe scripts\train_ridge.py
.\.venv\Scripts\python.exe scripts\train_hgb.py
.\.venv\Scripts\python.exe scripts\train_lightgbm.py
.\.venv\Scripts\python.exe scripts\train_intervals.py
.\.venv\Scripts\python.exe scripts\stress_telemetry.py
.\.venv\Scripts\python.exe scripts\summarize_stress.py
.\.venv\Scripts\python.exe scripts\check_reliability.py
```

Expected sequence: clean observations → fixed baselines → exact-time tables → three model comparisons → ranges → missing-input checks → reliability/compute checks. Keep fixed splits, cohort, calibration separation and tuning choices. Timing and memory numbers vary by machine. Do not edit features or settings based on the already viewed final-test results. No dataset download is needed.

After starting the service in that separate workspace, `scripts/check_api.py` and `scripts/check_dashboard.py` record HTTP checks at port 8765. They preserve existing evidence rather than overwriting it. Artifact validators for intervals, stress and reliability are also included; the saved validation reports remain the record of the earlier runs.

## What to share

For a complete local copy, retain raw and processed data, trained artifacts, evidence, code and docs together. `.venv` and Python caches are disposable environment files. Retain dataset CC BY 4.0 attribution and retain the MIT notice for the original project code; see [LICENSE](../LICENSE) and [NOTICE.md](../NOTICE.md). The root `manifest_sha256.json` records the current documentation and source snapshot. Experiment-specific manifests retain the fingerprints recorded for each run; `verify_project.py` checks the saved data and experimental artifacts.
