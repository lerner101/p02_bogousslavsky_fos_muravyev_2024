"""Summarize completed project Tables 1–4 and available published benchmarks."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_iti_features import sha256
from paper_values import (
    TABLE1_13D_TRADE_MEAN,
    TABLE1_ITI,
    TABLE2,
    TABLE2_R2,
    TABLE3,
    TABLE3_R2,
    TABLE4_A,
    TABLE4_B,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_output/replication'
ML = ROOT / '_data/derived/ml_model'


def compare_regressions(number, reference, r2=None):
    local = pd.read_csv(OUT / f'table{number}.csv')
    rows = []
    for col, values in reference.items():
        for variable, (coefficient, t) in values.items():
            hit = local[local.column.astype(str).eq(str(col)) & local.variable.eq(variable)]
            if len(hit) != 1:
                raise ValueError(f'Missing comparison: Table {number}, {col}, {variable}')
            row = hit.iloc[0]
            rows.append({'table': number, 'column': col, 'variable': variable,
                         'project_coef': row.coef, 'project_t': row.t,
                         'paper_coef': coefficient, 'paper_t': t})
        if r2 is not None:
            hit = local[local.column.astype(str).eq(str(col)) & local.variable.eq('Adj. R2 (within)')].iloc[0]
            rows.append({'table': number, 'column': col, 'variable': 'Adj. R2 (within)',
                         'project_coef': hit.coef, 'paper_coef': r2[col]})
    return pd.DataFrame(rows)


def main():
    references = {2: (TABLE2, TABLE2_R2), 3: (TABLE3, TABLE3_R2),
                  4: ({'a: turnover': {'itrade': TABLE4_A['turn']},
                       'a: ITI': {'itrade': TABLE4_A['ITI']}, **{f'b{k}': v for k, v in TABLE4_B.items()}}, None)}
    comparisons = pd.concat([compare_regressions(n, *refs) for n, refs in references.items()], ignore_index=True)
    comparisons.to_csv(OUT / 'tables_comparison.csv', index=False)
    first = pd.read_csv(OUT / 'table1.csv')
    first['paper_mean'] = np.nan
    first['paper_sd'] = np.nan
    first['paper_sd_within'] = np.nan
    for name, values in TABLE1_ITI.items():
        match = first.variable.eq(f'Author {name}')
        if name == 'ITI(13D)':
            match |= first.variable.eq('Project ITI(13D)')
        first.loc[match, ['paper_mean', 'paper_sd', 'paper_sd_within']] = values
    first.loc[first.variable.eq('13D trade (13D sample)'), 'paper_mean'] = TABLE1_13D_TRADE_MEAN
    first.to_csv(OUT / 'table1_comparison.csv', index=False)
    diagnostics = pd.read_csv(OUT / 'table2_turnover_diagnostics.csv')
    sensitivity = pd.read_csv(OUT / 'table2_turnover_sensitivity.csv')
    sensitive_iti = sensitivity[sensitivity.column.eq(4) & sensitivity.variable.eq('ITI')]
    coverage = json.loads((OUT / 'table1_coverage.json').read_text())
    models = json.loads((ML / 'group_models.json').read_text())
    group_summary = pd.DataFrame([{'group': group, 'roc_auc': r['roc_auc'], 'log_loss': r['log_loss'],
                                   'features': len(r['features'])} for group, r in models['groups'].items()])
    group_summary.to_csv(OUT / 'table3_model_performance.csv', index=False)
    main_predictions = pd.read_parquet(ML / 'oof_predictions.parquet')
    group_predictions = pd.read_parquet(ML / 'group_oof_predictions.parquet')
    keys = ['filing', 'permno', 'date', 'itrade', 'outer_fold']
    pd.testing.assert_frame_equal(main_predictions[keys], group_predictions[keys])
    manifest = json.loads((ML / 'model_manifest.json').read_text())
    for filename, key in [('iti_13d.json', 'model_sha256'), ('features.parquet', 'features_sha256')]:
        if sha256(ML / filename) != manifest[key]:
            raise ValueError(f'Original full-model input changed: {filename}')
    for relative, expected in models['input_sha256'].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f'Group training input changed: {relative}')
    sample_rows = []
    for n in (2, 3, 4):
        table = pd.read_csv(OUT / f'table{n}.csv')
        estimates = table[~table.variable.isin(['Obs.', 'R2 (within)', 'Adj. R2 (within)', 'Filings'])]
        if not np.isfinite(estimates[['coef', 't']]).all().all():
            raise ValueError(f'Nonfinite regression estimates in Table {n}')
        for col, part in table.groupby('column'):
            vals = part.set_index('variable').coef
            sample_rows.append({'table': n, 'column': col, 'observations': int(vals['Obs.']),
                                'filings': int(vals['Filings']), 'within_r2': vals['R2 (within)'],
                                'adjusted_within_r2': vals['Adj. R2 (within)']})
    sizes = pd.DataFrame(sample_rows)
    lines = ['# Tables 1–4: project estimates and published comparisons', '',
             'All regression ITIs are our held-out project estimates. Author scores enter only the explicitly labeled Table 1 benchmark rows; published coefficients never enter estimation.', '',
             '## Table 1: coverage and provenance', '',
             (f"The local supplemental-feature acquisition contains {coverage['acquired_feature_stock_days']:,} stock-days. "
             f"After the saved eligibility screens, excluding all reconstructed 13D windows, and requiring the eight table controls, "
             f"{coverage['complete_control_stock_days']:,} remain ({coverage['start']} to {coverage['end']}). "
             f"Our final model scores {coverage['project_scored_stock_days']:,} of these; "
             f"{coverage['paired_author_stock_days']:,} also have author ITI(13D). "
             f"Our scored dates span {coverage['project_start']} to {coverage['project_end']}."), '',
             ('**This is an available-data descriptive table, not the paper’s full-market Table 1.** Supplemental acquisition was bounded around requested stocks and events. Table 1 follows the existing 2005–July 2019 comparison window; 2004 provides feature warm-up. Missing project scores remain missing. '
             'The saved full model is reused; no author-score fallback or zero imputation is applied. '
             'The author-overlap row provides a comparison restricted to our scored days. '
             'Published Table 1 statistics refer to a substantially broader sample, so differences include selection and coverage effects.'), '',
             first[['variable', 'source', 'mean', 'sd', 'sd_within', 'n', 'paper_mean']].to_markdown(index=False, floatfmt='.5f'), '',
             '## Regression samples and fit', '',
             (f"The held-out sample has {len(main_predictions):,} filing-days in {main_predictions.filing.nunique():,} filings, "
             f"{main_predictions.date.min():%Y-%m-%d}–{main_predictions.date.max():%Y-%m-%d}."), '',
             sizes.to_markdown(index=False, floatfmt='.5f'), '',
             ('Tables 2–4 absorb filing fixed effects and cluster standard errors by filing, reusing the repository estimator. '
             'It uses a G/(G−1) cluster correction; no additional software-specific degrees-of-freedom multiplier is imposed. '
             'Raw within R² and adjusted within R² are exported separately. The latter uses residual degrees of freedom n−filings−regressors '
             'and within-total degrees of freedom n−filings. Published adjusted R² may follow different software conventions.'), '',
             ('Table 2 uses the same complete-control rows for columns 1–3; columns 4–6 additionally require a trade day and observed filer turnover. '
             'All controls are pooled-winsorized at 0.05%/99.95%; ITI and filer turnover are not winsorized. '
             'The eight printed table controls are used, rather than the nine-control Figure 1 caption specification. '
             'Controls use Figure 1 definitions: summed bid/ask share depth divided by CRSP shares outstanding, '
             'share volume and signed share imbalance divided by shares outstanding, lambda multiplied by 1,000, '
             'and the saved raw realized-volatility feature.'), '',
             ('Table 4 matches raw CRSP turnover within filing, without replacement, taking the smallest absolute gaps first. '
             'All pairs satisfy |turnover difference| ≤ 0.00002 and contain one trade day and one non-trade day. '
             'Matching starts with complete-control observations so all panels use the same matched rows. '
             'The paper does not fully specify tie-breaking or replacement; this deterministic greedy rule is an implementation choice.'), '',
              '## Table 2: turnover definition and extraction sensitivity', '',
             ('The saved labels contain a dollar-volume/market-value proxy. The primary table instead computes '
             '(shares bought + shares sold) / (CRSP shares outstanding × 1,000), matching the paper’s share-turnover definition. '
             'The saved labels and trained full model are unchanged. The legacy proxy is retained only as a sensitivity.'), '',
             diagnostics.to_markdown(index=False, floatfmt='.6f'), '',
             ('**Unverified extracted quantities materially affect the turnover regressions.** '
             'Three trade days have gross reported shares exceeding total outstanding shares, and the legacy dollar proxy has nine values above one. '
             'These are diagnostic flags, not an automatic proof of error. The primary table retains them; '
             'the 0.05%/99.95% winsorized and at-most-100% turnover checks are separately labeled sensitivity results. '
             'Neither trimming rule is silently substituted for the paper specification. '
             'The binary trading-day results do not depend on these turnover amounts, although independent trade-label verification remains outstanding.'), '',
             sensitive_iti[['specification', 'coef', 't']].to_markdown(index=False, floatfmt='.5f'), '',
             '## Table 3: feature-group models', '', 
             ('Four new group models use the original sample and outer-fold assignments, with nested five-fold selection over the original 24-candidate grid. '
             'No outer validation outcomes enter tuning. Overlapping stock-days may not cross outer folds. '
             'Only historically unavailable odd-lot counts may remain missing, using native XGBoost routing as in the approved full model.'), '',
             group_summary.to_markdown(index=False, floatfmt='.5f'), '',
             '## Published coefficient comparisons', '', comparisons.to_markdown(index=False, floatfmt='.5f'), '',
             ('The project uses shorter dates, reconstructed labels, bounded supplemental acquisition, and documented feature conventions. '
             'These estimates are a replication on available data, not an exact reproduction of the published sample. '
             'Insider and short-interest training samples and project-specific patient/impatient variants are not estimated here.'), '',
             ('Reproduce with `python -m doit tables`, `python -m doit iti_train_groups`, '
             '`python -m doit table3`, then `python -m doit tables_report`. '
             'Completed feature groups are reused only when input fingerprints and held-out keys match. '
             'A partially trained group is rerun; completed groups are retained.'), '']
    (OUT / 'tables_comparison.md').write_text('\n'.join(lines))
    paths = [ROOT / 'src/replicate_tables.py', ROOT / 'src/report_tables.py', ROOT / 'src/regress.py',
             ROOT / 'src/replicate_iti_figures.py', ROOT / 'src/paper_values.py',
             ML / 'model_manifest.json', ML / 'iti_13d.json', ML / 'raw_features.parquet',
             ML / 'scores.parquet', ML / 'group_models.json', ML / 'group_oof_predictions.parquet',
             ROOT / '_data/derived/panel/table1_local.parquet']
    paths += [ROOT / relative for relative in models['input_sha256']]
    paths += [ROOT / f'_data/wrds/{folder}/{year}.parquet' for year in range(2004, 2020)
              for folder in ('crsp_daily', 'intraday_indicators', 'crsp_taq_links')]
    paths += list((ROOT / '_data/public/iti_original_through_2019').rglob('*.parquet'))
    paths += [OUT / f'table{n}.csv' for n in (1, 2, 3, 4)]
    paths += [OUT / 'table1_coverage.json', OUT / 'table2_turnover_diagnostics.csv', OUT / 'table2_turnover_sensitivity.csv']
    (OUT / 'tables_manifest.json').write_text(json.dumps({
        'input_and_table_sha256': {str(p.relative_to(ROOT)): sha256(p) for p in paths},
        'group_metrics': models['groups'], 'table1_coverage': coverage}, indent=2) + '\n')
    print('Validated Tables 1–4; wrote tables_comparison.md and tables_manifest.json')


if __name__ == '__main__':
    main()
