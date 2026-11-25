# Figures 1–3: project ITI versus the published paper

Generated figures: 1, 2, 3. Project sample: 65,752 filing-days, 1,655 filings; 2005-01-03–2018-12-31.

Project estimates use saved project held-out predictions and the saved XGBoost model. Published curves are digitized benchmarks, never inputs to estimation. No XGBoost retraining or acquisition is performed.

Reference: supplied forthcoming-paper PDF, printed pp. 41–43 (PDF pp. 43–45); DOI 10.1111/jofi.13320. Figures 1–2 are approximate numerical digitizations. Figure 3 preserves printed rounded nodes.

## Figure 1: annual adjusted R²

Both project regressions use identical complete filing-days, an intercept, and pooled 0.05%/99.95% winsorized controls. The primary nine-control specification follows the caption and includes price impact. The archived-script eight-control specification remains a same-sample sensitivity column. No filing fixed effects are added to this annual specification.

|      year |   common_days |   iti_adjusted_r2 |   controls_adjusted_r2 |   controls8_adjusted_r2 |   paper_iti_adjusted_r2 |   paper_controls_adjusted_r2 |
|----------:|--------------:|------------------:|-----------------------:|------------------------:|------------------------:|-----------------------------:|
| 2005.0000 |     4748.0000 |            0.0474 |                 0.0195 |                  0.0196 |                  0.1152 |                       0.0506 |
| 2006.0000 |     6994.0000 |            0.0542 |                 0.0212 |                  0.0202 |                  0.1156 |                       0.0420 |
| 2007.0000 |     8503.0000 |            0.0436 |                 0.0227 |                  0.0228 |                  0.1136 |                       0.0307 |
| 2008.0000 |     6262.0000 |            0.0395 |                 0.0181 |                  0.0181 |                  0.1354 |                       0.0440 |
| 2009.0000 |     2018.0000 |            0.1257 |                 0.0706 |                  0.0689 |                  0.2475 |                       0.0996 |
| 2010.0000 |     4314.0000 |            0.1025 |                 0.0461 |                  0.0461 |                  0.2257 |                       0.0521 |
| 2011.0000 |     4243.0000 |            0.1076 |                 0.0556 |                  0.0555 |                  0.1821 |                       0.0498 |
| 2012.0000 |     4278.0000 |            0.1001 |                 0.0523 |                  0.0522 |                  0.2074 |                       0.0498 |
| 2013.0000 |     4053.0000 |            0.0555 |                 0.0298 |                  0.0300 |                  0.1307 |                       0.0381 |
| 2014.0000 |     5550.0000 |            0.0642 |                 0.0323 |                  0.0320 |                  0.1525 |                       0.0401 |
| 2015.0000 |     4606.0000 |            0.0652 |                 0.0329 |                  0.0331 |                  0.1128 |                       0.0397 |
| 2016.0000 |     3520.0000 |            0.0471 |                 0.0284 |                  0.0263 |                  0.1093 |                       0.0233 |
| 2017.0000 |     2965.0000 |            0.0647 |                 0.0264 |                  0.0248 |                  0.1183 |                       0.0109 |
| 2018.0000 |     3698.0000 |            0.0629 |                 0.0382 |                  0.0377 |                  0.0840 |                       0.0187 |

## Figure 2: partial dependence

For each displayed value, replace only that feature for every retained training observation, predict with the saved final model, and average over the full sample. All 41 columns are retained; odd-lot NaNs remain native. Display ranges match the published curves; project histograms divide by the full observation count and bin width, so displayed density need not integrate to one when tails fall outside the panel. Published densities use the printed secondary-axis calibration. No published curve is extrapolated or smoothed.

| feature   |   display_lower |   display_upper |   project_fraction_outside |
|:----------|----------------:|----------------:|---------------------------:|
| rvol      |         -1.5205 |          2.0063 |                     0.0557 |
| svol      |         -0.8185 |          2.6215 |                     0.0988 |

## Figure 3: surrogate trees

Project sample R²: 0.7625. This is the surrogate's fit to held-out ITI, not classifier performance. It uses depth 3, minimum leaf fraction 1%, squared-error splits, and random seed 0. Published tree nodes are transcribed rather than fit to project data. Both panels use the same ITI color scale.

- Preserve printed rounded node values, counts, MSEs and topology.
- Tree root count 61,255 differs from main paper sample count 58,197.
- Caption says about one-third of ITI variation; printed rounded MSEs do not reproduce that claim exactly. Do not infer an exact published R2 from these nodes.
- Left branches follow <= thresholds, consistent with the graphic; caption's generic right-branch wording is not used.

## Interpretation limits

The project uses a shorter sample, reconstructed filing labels, and documented feature/missing-data conventions. Differences cannot be attributed to sample dates alone. Published curve precision is limited by raster resolution, axis calibration, dashed-line gaps and narrow spikes. The eight-versus-nine control discrepancy and the paper's tree sample-count/fit inconsistencies are preserved explicitly.
