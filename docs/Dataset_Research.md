# Real cellular PRB/RB forecasting datasets: verified selection and independent audit

Research date: 16 October 2026. This note uses primary repositories, dataset records and author publications. Source coverage and independently measured findings are identified below.

## Decision

**Keep Zenodo Dataset_02 as the leading 15-minute real-network forecasting candidate, with an observed-target-only preprocessing protocol and an explicit row-identity caveat.** It supports a defensible radio-load forecasting project. It does not yet justify promising general congestion prediction, real network control or energy savings. Use ITU/Zindi as an independent hourly beam-level forecasting benchmark, subject to checking PRB units and obtaining the files through its normal terms flow.

The most consequential finding is that the downloaded commercial-network CSV files have repeated station/sector/timestamp keys, but **every nonempty utilization measurement has a unique key**. A usable observed-only forecast dataset can therefore be constructed without resolving ambiguous energy-only rows. Do not treat the raw 1.8 million rows per file as 1.8 million distinct cell-time utilization observations.

## 1. Primary source facts for the leading dataset

Sources: [Zenodo record](https://zenodo.org/records/17815388), [official README](https://zenodo.org/records/17815388/files/README.md?download=1), [accepted Scientific Data manuscript](https://www.nature.com/articles/s41597-026-07723-0_reference.pdf), DOI [10.1038/s41597-026-07723-0](https://doi.org/10.1038/s41597-026-07723-0).

The accepted descriptor reports commercial Slovak-network measurements at 15-minute intervals; Table 2 lists Dataset_01/02/03 as 35/64/84 days, 25/63/264 stations, and 302,052/3,601,840/30,213,561 records. Dataset_02 is LTE1800/NR2100. Table 4 defines both RB-utilization fields as percentages; Table 1 gives these carriers 20 MHz bandwidth. Thus bandwidth affects absolute resources represented by a percentage, not an extra percentage normalization. Energy is Wh per 15 minutes at radio-unit/baseband level, shared across configurations. Missing utilization generally reflects low load, but broadly absent/zero telemetry with absent energy indicates unavailable intervals. The descriptor claims no duplicate station/sector/timestamp tuples; the independent audit below finds otherwise. These are publisher statements, not an assumption that every release row is correct.

README confirms CC BY 4.0, UTC timestamps, preservation of missing/zero data, technology-specific counters, and the requirement to cite both data and descriptor. Current compressed sizes: Dataset_01 8.3 MB, Dataset_02 49.4 MB, Dataset_03 709.4 MB. Start with Dataset_02 for laptop feasibility.

The PDF downloaded successfully through Python urllib even though web-tool PDF fetches encountered a publisher redirect. Local supporting copy: `ran_descriptor.pdf`; searchable extract: `ran_descriptor.txt`.

## 2. Independent byte-level audit of Dataset_02

Source: actual [Dataset_02.zip](https://zenodo.org/records/17815388/files/Dataset_02.zip?download=1), included in the project. MD5 **7d9c1c019e5d18bf318b4e4ad9393d91**, matching the publisher's checksum. Uncompressed CSV sizes: NR134,905,388 bytes; LTE136,612,918 bytes. Streaming standard-library CSV analysis was used; no model training or tuning occurred.

| Audit item | 5G NR2100 | 4G LTE1800 |
|---|---:|---:|
| Raw rows | 1,800,920 | 1,800,920 |
| Stations appearing anywhere | 63 | 63 |
| Station-sector groups anywhere | 184 | 184 |
| Unique station/sector/timestamp keys | 722,545 | 722,545 |
| Nonempty target rows | 690,499 | 643,732 |
| Unique keys among nonempty target rows | 690,499 | 643,732 |
| Keys with multiple nonempty target measurements | 0 | 0 |
| Stations with observed target | 59 | 59 |
| Station-sector groups with observed target | 174 | 174 |
| Raw rows with blank target | 1,110,421 | 1,157,188 |
| Observed-target minimum / maximum, % | 2.50 / 92.46 | 0.00 / 74.51 |
| Observed target >=80%, records | 143 | 0 |
| Observed-target median, % | 4.16 | 11.08 |
| Observed-target 99th percentile, % | 38.93 | 66.86 |

Both files span **2025-02-07 19:45 UTC through 2025-05-05 07:15 UTC**, with measurements on **64 distinct dates**, not a continuous full three-month history. Per-cell recording windows differ. The dates span a wider calendar window than the descriptor's 64-day observation count.

### Repeated keys require care

Each file has 722,137 keys appearing multiple times: 365,899 appear twice, 356,238 three times, and 408 keys once. There are **zero identical complete duplicate rows**. Repeated keys contain different energy values and frequently blank technology counters. In the inspected conflicting samples, one record contains the technology-specific KPI vector while other records at the same key carry energy-only data. This may reflect omitted radio/baseband identity or export padding, but the actual cause is **unverified** and should be clarified with the authors before energy modeling.

Example: NR Site96, sector1, 2025-02-25 20:45 has three rows at that key. Their radio/baseband energies are 96/85, 59/88, and 0/20 Wh. Only the middle row has NR metrics, including utilization4.73%. These cannot be repaired using `drop_duplicates(keep='first')`, summing energy, or replacing every missing utilization with zero.

The observed utilization values have no key collisions, so selecting nonempty target rows produces unique target series. Their raw counts and high-load counts above therefore also equal unique observed target counts.

### Missingness interpretation

The raw blank-target percentages are 61.66% NR and64.26% LTE, but these **are not independently missing observations at distinct cell-time keys** because many rows are the padded repeated-key records. Do not describe them simply as 62–64% missing time-series data.

There are 32,046 unique grid keys without an observed NR target and78,813 without an observed LTE target, relative to the722,545 keys present in the CSV. Additional clock intervals are absent between observed timestamps. The blank-target rows never have a positive DL volume or positive DL/UL volume/active-user indicator in this release, consistent with the authors' low-traffic explanation, but the row-identity ambiguity prevents blindly converting all blanks to zero.

An observed-only analysis should retain a complete 15-minute time grid, missingness flags, and explicit availability rules. Do not remove missing timestamps then take positional shifts, which can falsely label a gap as a15-minute forecast. Do not impute evaluation ground truth and count it as observed accuracy. A separate documented zero-imputation sensitivity experiment can be considered after clarifying the export schema.

Across observed-target series, all174 NR groups have at least one uninterrupted7-day run,166 have a14-day run. For LTE,80 groups have a7-day run and49 a14-day run. These are longest-run eligibility counts, not a claim that each group has uninterrupted64-day coverage. At80%, the143 NR records cover15 station-sector groups/13stations and62 contiguous15-minute episodes. Episodes are split whenever adjacent high records differ by more than15minutes; this is an audit definition, not a service-incident label.

### Reproducibility files

- `audit_ran_data.py`: streaming counts, target ranges, timestamp coverage and per-cell continuity.
- `audit_ran_duplicates.py`: full-row versus key multiplicity and conflicting examples.
- `audit_ran_valid_keys.py`: uniqueness of all nonempty utilization observations.
- `dataset_02_audit.json`, `dataset_02_duplicates.json`, `dataset_02_valid_keys.json`: machine-readable audit results.
- `dataset_02_high_load.json`: threshold episode audit, if generated.

## 3. Alternatives and what they actually support

| Candidate | Primary evidence | Suitability and limits |
|---|---|---|
| ITU/Zindi beam-level traffic | [Official data page](https://zindi.world/competitions/spatio-temporal-beam-level-traffic-forecasting-challenge/data), [full challenge and license](https://zindi.world/competitions/spatio-temporal-beam-level-traffic-forecasting-challenge) | Five weeks, hourly,2,880 beams=30 stations×3cells×32beams. PRB, throughput volume/time and user-count files total142.8 MB. Official competition target is DLThpVol, not PRB. PRB can be a separate research target after checking its numeric units/normalization. Rules explicitly permit commercial/research/education use under CC BY-SA4.0. Sign-in/acceptance may be needed for downloads. No15-minute forecasts from hourly measurements. Challenge test week labels should not be assumed available. |
| Tsinghua NetData | [Author repository](https://github.com/tsinghua-fib-lab/NetData) | Commercial measurement reports with explicit PRB usage ratio in %, traffic KB, users, BBU/RRU energy kWh and sleep/shutdown counters. Parent collection exceeds10k4G/5k5G stations, but published portion is only one weekday and one weekend day. Four CSVs. Useful broad cross-sectional energy/load case study, poor primary dataset for weekly time-series generalization. README does not clearly supply cadence/license in retrieved listing; do not assume either. |
| VERGE Real-5G-Network-Dataset | [Project repository](https://github.com/VERGE-PROJECT/Real-5G-Network-Dataset) | Contains descriptions of live-network PRB, users, throughput and other counters. README explicitly says actual dataset cannot be shared on GitHub due to sensitivity. A collaboration lead, not a ready downloadable primary dataset. |
| CTTC OAI-KPM | [Author repository](https://github.com/CTTCADAPTRU/OAI-KPM-dataset) | CC0; workbook; described as five weeks/~10,080 samples with PRB, throughput, latency. Controlled OAI/RFSim emulation with generated iperf3 traffic, not live subscriber demand. Useful later integration/testbed exercise. README examples imply5-minute sequence steps while file name references1000ms; verify real cadence in workbook before use. |
| Telecom Italia Milan | [Depositor dataset](https://doi.org/10.7910/DVN/EGZHFV) | CDR-derived SMS/call/internet activity, ODbL. Good urban traffic benchmark, does not preserve this project's direct PRB-counter target. Do not rename traffic activity as measured PRB utilization. |
| Almeida et al. commercial5G forecasting | [Publisher article](https://www.sciencedirect.com/science/article/pii/S0140366424003219) | Strong methodological precedent for LightGBM/load forecasting, but publisher data-availability statement says data are confidential. A paper to read, not an accessible training dataset. |

The official ITU page describes real-world scenarios, while operator provenance and PRB counter semantics require the provided materials; unlike the Zenodo record, it should not be described as independently audited for this project. No Zindi or NetData CSVs were downloaded here.

## 4. What is and is not established

**Established:** the leading ZIP genuinely includes distinct observed utilization traces, published percent units, multiple real stations, a public reuse license and a manageable download. A long enough subset exists to examine daily behavior; per-cell continuity must guide eligibility.

**Not established:** general congestion warning quality, service degradation labels, unseen-operator transfer, causal energy savings, geographic neighbors, or live network actuation. Low observed5G load and only143 high-load records at an80% experimental threshold make broad warning-performance promises premature. Numeric threshold choice must be justified and tested; percentile-defined busy periods should be called busy-load events rather than universally congested service.

Recommended practical scope: leakage-controlled, multi-horizon, uncertainty-aware load forecasting; compare persistence/daily seasonal baselines and practical boosting; add missingness robustness, calibration and cross-station tests; deliver a recorded-data replay dashboard and prediction API. Energy-aware decision support can be an explicitly modeled extension after resolving the energy row identity. This is a stronger, supportable portfolio contribution than an unsupported claim to autonomous RAN optimization.

## Source refs for parent citation lookup

- Zenodo: `turn1search1`.
- Official README: `turn2view0`.
- Scientific Data landing/abstract: `turn3view0` (full PDF fetched independently with urllib).
- Zindi data: `turn3view1`; full rules/CC BY-SA: `turn3view2`.
- NetData: `turn1search0`, `turn1search2`.
- VERGE private-data caveat: `turn13view1` / `turn10view3`.
- OAI-KPM: `turn10view1`.
- Almeida commercial5G and confidentiality: `turn26search0`.

Parent should open cited source URLs itself before citing those refs in the final answer, per web-tool instructions.
