# Implemented research build

This build is not yet a replication of all 13 screenshot targets.

| Output | File |
|---|---|
| Local source inventory | data_acquisition_status.md |
| 13D label validation | 13d_label_validation.md |
| 13D filing-return diagnostic | 13d_filing_car.png |
| Extractor tuning evaluation | 13d_extraction_eval_audit.md |
| Extractor previously used holdout evaluation | 13d_extraction_eval_holdout.md |
| News preparation / identifier audit | bfkr_preparation.md |
| Preliminary Figure 4(c) | figure_04c_preview.png |

News regression: 1,127,042 observations, 678 stocks, 2005-01-03 to 2015-12-23.

The news chart uses unadjusted earnings dates and incomplete sample screens. It is not the final Figure 4(c). 13D transcriptions still need independent verification.

## Remaining screenshot work

Figures 1–3 can be built on the project sample with `doit iti_figures` using the saved ITI(13D) run and local market extracts.

Tables 1–5 and 9–11, Figure 4(a–b), and Figure IA.5 do not yet have completed end-to-end builders. Figure 4(c) has a preliminary implementation only. Full-universe ITI scoring, additional model variants, final event studies, and pricing analyses remain unfinished. BCL data for Table 9 remain unavailable.

See README.md for dataset coverage and docs_src/site/project_overview/build.md for the build/data handoff contract.
