# BFKR news data and Figure 4(c)

The public VIP dataset linked by Boudoukh, Feldman, Kogan and Richardson is now
available locally at `_data/public/InformationTradingVolatility_DataFile.csv`.
It contains 1,952,175 ticker/date rows, 896 tickers, January 2000–December 2015,
and the `CC_day_type`, `CO_day_type` and `OC_day_type` classifications. The CSV is
about 37.2 MiB. It stays outside Git; a new checkout needs its own copy.

Source: the authors' paper links
[InformationTradingVolatility_DataFile.csv](https://www.dropbox.com/s/ilw2l2pb9nh6kpm/InformationTradingVolatility_DataFile.csv?dl=1).

## Prepare

```bash
python src/prepare_bfkr_news.py
```

This links exact ticker symbols to dated CRSP name records with common-stock
share codes 10/11. Ambiguous links and duplicate resulting stock-days are excluded
from the usable dataset and retained in the audit file. No current-ticker or
nearest-date backfill is applied. The local name extract only includes records
overlapping 2004 onward, so the earlier years have incomplete linking coverage.

Outputs in `_data/derived/bfkr/`:

- `news_daily.parquet`: uniquely linked news classifications.
- `news_link_audit.parquet`: all source rows and link outcomes.
- `earnings_unadjusted.parquet`: raw Compustat `rdq`, linked with effective-date
  primary CCM LC/LU records; **no after-hours adjustment**.
- `manifest.json`: source hash, counts, coverage and earnings-timing limitation.

The preparation report is `_output/bfkr_preparation.md`.

## Preliminary analysis

```bash
python src/analyze_bfkr_news.py --preview
# Or run preparation and analysis together:
doit bfkr_preview
```

The preview defaults to 2005–2015 and uses original posted ITI, not the extended
vintage. It uses ITI(impatient), all-news days (`CC_day_type` 1/2/3), stock fixed
effects and standard errors clustered by stock and date. It requires all three
13D-trained ITI series to be present, as in the authors' analysis. Bands are
coefficient +/- twice the standard error, following their export code.

The authors' `ITI_main.py` excludes earnings +/-2 observations and then constructs
the +/-5 news regressors by shifting within the remaining BFKR rows for each
stock. This implementation preserves that ordering. Positive plotted event days
mean days after news. Shifts follow supplied observations rather than calendar
days; no-news records must be retained. Raw weekend earnings dates are mapped to
the next market trading date in preview mode.

The preview **does not reproduce the final screenshot sample**: it uses raw
earnings dates and omits the paper's universe/control-completeness selection.
The labels on the chart and report identify those limitations. It writes
`_output/figure_04c_preview.{png,csv,json,md}` and saves the actual regression
sample to `_data/derived/bfkr/figure_04c_preview_sample.parquet`.

## Final analysis inputs

```bash
python src/analyze_bfkr_news.py \
  --controls /path/to/paper_screened_controls.parquet \
  --earnings /path/to/adjusted_earnings.parquet \
  --start-year 2000 --end-year 2015
```

The controls file must contain unique `permno,date` keys and the paper-defined
`ES%`, `lambda`, `depth`, `rvol`, `turn`, `OI`, `|OI|`, `ret`. It must already apply
the dated common-stock universe, prior-month price/market-cap screens and the
paper's other sample rules. The plotted no-controls specification still requires
all eight controls to be observed, following the authors' code. This command
estimates that plotted specification; it does not estimate the additional
with-controls robustness regression.

The earnings file must contain unique `permno,date` event keys, with the
after-hours volume adjustment already implemented and dates on the market
calendar. It must cover the entire analysis interval, including its boundaries.
The current repository does not build these final inputs yet. Exact 2000–2015
coverage also requires expanding the historical names, earnings and ITI inputs
beyond their current local preparation ranges. Final mode writes `figure_04c`
outputs, but correctness still depends on the supplied inputs; the mode is not
automatic certification of equality with the paper.
