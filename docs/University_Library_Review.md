# University-library review — 16 October 2026

Focused literature review using Scopus discovery and selected IEEE and ACM records. This note records access scope, inspected methods and relevance to short-horizon radio-resource forecasting.

## Source coverage

| Site | Material inspected | Evidence scope |
|---|---|---|
| Scopus through BTH proxy | Page says “Brought to you by Blekinge Institute of Technology”; document search completed | Search results and one paper's indexed abstract/metadata read |
| IEEE Xplore | Banner says access provided by BLEKINGE TEKNISKA HOGSKOLA; matched paper marked included in digital subscription | Article HTML full-text sections inspected, including methods and simulation setup |
| ACM Digital Library | Search and paper page accessible; selected paper marked Free access | Abstract and references inspected; university authentication was not established from the ACM page, and PDF full text was not read |

Screenshot of the IEEE access banner and selected paper: `docs/IEEE_BTH_Access.jpg`.

## Searches performed

Scopus: Article title, Abstract, Keywords field:

```text
("physical resource block" OR "PRB utilization" OR "resource block usage") AND (forecast* OR predict*)
```

The visible result count was 69 documents. The list was ordered by date newest. This is one focused discovery search, not a systematic review of all 69 documents. Selected record: https://www-scopus-com.miman.bib.bth.se/pages/publications/105032123842?origin=resultslist.

IEEE: exact phrase `"AI-Empowered Multivariate Probabilistic Forecasting"`, producing one result, then its article page was opened.

ACM: exact phrase `"mobile traffic forecasting"`, producing 14 results in the ACM Full-Text Collection, then the resource-usage paper below was opened.

## Paper 1: multivariate probabilistic PRB forecasting

Kasuluru, Blanco, Vaca-Rubio, Zeydan and Bel. *AI-Empowered Multivariate Probabilistic Forecasting: A Key Enabler for Sustainability in Open RAN*. IEEE Transactions on Network and Service Management, 2026.

- Publisher page: https://ieeexplore.ieee.org/document/11418715/
- DOI: https://doi.org/10.1109/TNSM.2026.3669847
- Methods inspected in Section IV: deterministic multivariate LSTM, GPVAR, and Temporal Fusion Transformer (TFT). GPVAR models a predictive distribution; TFT uses quantile forecasts. Calendar information is included where described.
- Section VI explicitly describes a dataset generated from simulated traffic and user mobility. It describes a 50-base-station scenario and 15,000 users; this experiment uses two base stations and their summed PRB allocation.
- Forecast horizon: 48 hours; context: 120 hours. These are different from our 15/30/60-minute task.
- The text describes a 70:30 split, training/validation within the first portion, and approximately one month of training data. This review does not establish a leakage-safe split implementation or inspect source code.
- Power savings are calculated with a power model and switching policy in a simulation assessment. They are not measured savings from our network dataset and cannot be transferred to our project.
- Readable full-text sections inspected: problem definition, forecasting models, metrics, simulation setup/results and conclusion. Image-only numerical result tables were not independently transcribed or checked.

Project implication (our judgment): this supports examining probabilistic PRB forecasting, but does not establish that GPVAR or TFT will beat CPU tree models on our data. Candidate selection remains open until data fit, evaluation and laptop costs are compared. No paper score is a project score.

## Paper 2: resource prediction for a slice broker

Gutterman, Grinshpun, Sharma and Zussman. *RAN Resource Usage Prediction for a 5G Slice Broker*. ACM MobiHoc 2019, pages 231–240.

- Publisher page: https://dl.acm.org/doi/10.1145/3323679.3326521
- DOI: https://doi.org/10.1145/3323679.3326521
- Abstract inspected: uses an LTE testbed, defines REVA (resource availability for a very active bearer), and introduces X-LSTM compared with LSTM and ARIMA.
- Its REVA prediction task is different from predicting commercial station/sector RB-utilization percentages. Its reported accuracy and provisioning improvements cannot be compared directly with our MAE/RMSE.
- The abstract and references were read. PDF methods, hyperparameters, horizon, chronological split, data accessibility and reproducibility have not yet been verified.

Project implication (our judgment): relevant context for time-series resource prediction; ARIMA and LSTM are literature candidates, but this paper alone does not justify selecting X-LSTM for our project.

## Additional leads, not yet reviewed

- Scopus result: *PRB-RUPFormer: A Recursive Unified Probabilistic Transformer for Residual PRB Forecasting*, IEEE DySPAN 2026. Its citation DOI was also visible on the ACM page: https://doi.org/10.1109/DySPAN69846.2026.11571152. Abstract/full text not inspected in this review.
- ACM result: *UoMo: A Universal Model of Mobile Traffic Forecasting for Wireless Network Optimization*, KDD 2025, https://doi.org/10.1145/3711896.3737272. Search listing only; target fit, data and compute not verified.

## Method selection

The focused comparison is recorded in [Methods_Comparison.md](Methods_Comparison.md), with implementation evidence in [CPU_Methods_Evidence.md](CPU_Methods_Evidence.md). This literature search is not an exhaustive systematic review.
