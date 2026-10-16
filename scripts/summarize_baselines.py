"""Create a readable summary using saved measurements only (no rerun)."""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/baselines_v1"
m = json.loads((OUT / "split_manifest.json").read_text(encoding="utf-8"))
metrics = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
coverage = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
lines = [
    "# Stage 1: measured extraction and naive forecasting baselines", "",
    "Measured on 16 October 2026 using the included Dataset_02 archive. No learned model has been trained.", "",
    f"Extracted {m['observed_rows']:,} observed targets across {len(m['series'])} technology/band/station/sector series, with {m['grid_slots']:,} first-to-last clock slots. Blank targets remain unavailable.", "",
    "Stations: " + ", ".join(sorted({s['station'] for s in m['series']}, key=lambda s:int(s.split()[-1]))) + ".",
    f"Station holdout: {m['station_holdout']} (four series). Remaining stations supply 16 development series.", "",
    "## Frozen protocol", "",
    m["cohort_rule"], "",
    f"Selection window: {m['selection_start']} through {m['selection_end_exclusive']} exclusive. Each selected series needed at least 941/1344 observed slots (70%); actual minimum was " + str(min(s['early_observations'] for s in m['series'])) + ". This favors well-observed early stations and does not represent all 59 observed stations.", "",
    "| Partition | Start UTC inclusive | End UTC exclusive |", "|---|---|---|",
]
for s in m["splits"]:
    lines.append(f"| {s['name']} | {s['start_inclusive']} | {s['end_exclusive']} |")
lines += ["", m["split_rationale"], "", m["evaluation_policy"], "",
          "Daily seasonal predicts y(t+h-24h), rather than y(t-24h). It may issue a forecast when the current reading is absent; persistence requires a current observed reading. Paired comparison requires both predictions and observed ground truth. No input or ground-truth zero filling occurs.", "",
          "Holdout is a station-exclusion protocol for later models, not evidence of learned cross-station transfer from naive methods. It uses its own causal target history at replay time. Features carry role labels; exclude holdout rows from every learned fitting/preprocessing/tuning/calibration step.", "",
          "## Final-period baseline results", "",
          "Errors are percentage points. Both models below use exactly the same scored rows within each technology/horizon/role.", "",
          "| Role | Technology | Horizon min | Paired rows | Persistence MAE / RMSE | Daily seasonal MAE / RMSE |", "|---|---|---:|---:|---:|---:|"]
lookup = {(r['role'],r['technology'],r['horizon_minutes'],r['model']):r for r in metrics['aggregates'] if r['split']=='test' and r['sample']=='paired'}
for role in ("development", "station_holdout"):
    for tech in ("LTE", "NR"):
        for h in (15,30,60):
            p = lookup[(role,tech,h,'persistence')]
            s = lookup[(role,tech,h,'daily_seasonal')]
            lines.append(f"| {role} | {tech} | {h} | {p['n']:,} | {p['mae_pp']:.3f} / {p['rmse_pp']:.3f} | {s['mae_pp']:.3f} / {s['rmse_pp']:.3f} |")
totals = defaultdict(Counter)
for row in coverage:
    if row['split'] == 'test':
        totals[(row['role'],row['technology'],row['horizon_minutes'])].update({k:v for k,v in row.items() if k not in ('role','split','technology','band_mhz','station','sector','horizon_minutes')})
lines += ["", "## Scored-row coverage in the final period", "",
          "Grid origins have in-partition future timestamps. Observed future labels may still lack current or seasonal inputs. Counts include missing-clock intervals; they are not raw padded-row missingness rates.", "",
          "| Role | Technology | Horizon min | Grid origins | Observed future labels | Persistence scored | Seasonal scored | Paired / observed labels |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
for (role,tech,h), c in sorted(totals.items()):
    n = c['observed_future_target']
    lines.append(f"| {role} | {tech} | {h} | {c['grid_origins']:,} | {n:,} | {c['persistence_available']:,} | {c['daily_seasonal_available']:,} | {c['paired_available']:,} / {n:,} ({100*c['paired_available']/n:.1f}%) |")
lines += ["", "Persistence has lower pooled MAE than daily seasonal on all paired final-period technology/horizon groups in this selected cohort. This is a descriptive baseline result, without statistical significance or a learned-model improvement claim.", "",
          "## Files and limits", "",
          "- `data/processed/observed_v1.sqlite`: unique observed percentages, full keys, archive member and source CSV row (header is row 1).",
          "- `data/processed/manifest_v1.json`: hashes, early cohort counts, per-series gap histograms and frozen cutoffs.",
          "- `outputs/baselines_v1/forecasts.csv.gz`: labels and both forecasts; blanks denote abstention. Missing labels are counted in coverage, never scored.",
          "- `outputs/baselines_v1/features.csv.gz`: full first-to-last grid, exact history lags, observed-only last-hour mean/count and age; blank lag fields signal unavailable inputs. No future label or future KPI is an input.",
          "- `outputs/baselines_v1/metrics.json`: available-row and paired-row pooled/macro errors plus per-series errors, including training/tuning/calibration where permitted.",
          "- `outputs/baselines_v1/coverage.json`: per-series origin, missing-label, input availability and boundary-purge counts.",
          "- `outputs/baselines_v1/split_manifest.json`: frozen protocol and extraction/evaluation code hashes.", "",
          "Validation: eight protocol regression checks passed. The saved-artifact validator checked all 286,331 forecast rows against extracted targets, exact input timestamps, roles and split boundaries; it recomputed all 816 per-series metric groups. SHA-256 checks confirmed all 12 protected original raw/audit/research/audit-script/instruction files were unchanged.", "",
          "The row cap is 180,000 observations; grid cap 200,000 rows. SQLite cache is capped at 16 MiB; no peak-process RAM benchmark was performed. Only one series is loaded for feature generation. Raw files and prior audits were not rewritten; no complete audit was rerun.", "",
          m['time_policy'], "",
          "Other KPI uniqueness and availability remain unverified, so no field-wise merge was attempted. Energy is excluded. No congestion model, uncertainty calibration, missing-input stress experiment or live deployment is claimed. The large recording gap remains missing rather than bridged. Natural gaps and synthetic outages have not been compared yet.", "",
          "The final period has now been evaluated for these fixed baselines. Preserve the cutoffs and policies; use training/tuning for subsequent model decisions, calibration for intervals, and avoid choosing later changes from final-test scores.", "",
          "Next single stage: implement a small CPU Ridge model using the same causal PRB-history features, train-only preprocessing and tuning-only selection, then compare on identical scored rows. Add other KPIs only after verifying their uniqueness and timing.", "",
          "Dataset attribution: Lehoczky et al., Performance Management Counters from Live 5G, 4G and 2G Radio Access Network, Zenodo dataset version https://doi.org/10.5281/zenodo.17815388; descriptor https://doi.org/10.1038/s41597-026-07723-0. CC BY 4.0. Extraction and derived forecasts are project transformations.", ""]
path = ROOT / "docs/Stage_1_Results.md"
path.write_text("\n".join(lines), encoding="utf-8")
print(path)
