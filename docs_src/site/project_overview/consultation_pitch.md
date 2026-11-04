# Consultation Pitch — Draft for Discussion

**P2: Informed Trading Intensity**
Jacob Lerner, Andrew Arbitman, Andrew McLaughlin, and Nate Lee

**1. What does the paper claim?**
A nonlinear model trained on disclosed activist trading detects realized
informed trading better than conventional liquidity measures and has useful
implications for event behavior, return reversal, and future returns.

**2. What does the paper not do that someone would want?**
The historical results do not establish how a model frozen before a later
period performs under subsequent market conditions. A researcher also needs a
reusable workflow that aligns ITI, PIN, and VPIN and diagnoses changes in data
coverage rather than interpreting every change as an economic result.

**3. What will we build?**
Replicate the agreed original exhibits, update the measure beyond the authors'
posted coverage where data allow, and build a reproducible comparison tool.
The proposed extension freezes the trained model before an agreed later period,
compares ITI/PIN/VPIN on a common sample, and reports event behavior and stability
across predefined periods. The deliverable is a feature/scoring workflow,
validation report, and notebook on the published ChartBook site. A regularly
refreshed monitor is optional, subject to data and compute feasibility.

**4. Who would clone it, and what would they do with it?**
An empirical market-microstructure researcher with the required data access
could score their stock-day panel, compare informed-trading measures, inspect
coverage problems, and reproduce the original and later-period evaluations.

**5. How will we know it worked?**
The pipeline reproduces the agreed original results within predeclared,
justified tolerances or explains documented deviations. It generates a later
holdout comparison without tuning on that period, and it rebuilds from a clean
clone. The extension succeeds by producing credible evidence, including a
possible finding that historical performance does not persist.

**Data validation.**
Check historical security links, extracted transaction dates/quantities, sample
attrition, prior-year feature scaling, and TAQ-versus-CRSP volume after accounting
for definitions. Compare rebuilt ITI against the correct original author series
on overlapping stock-days. Report coverage and disagreement by year and stock
size in an original validation table and figure. Freeze numeric acceptance
criteria before examining the computed results.

**Decisions requested at the consultation.**
Confirm the local forthcoming-paper version and screenshot scope; required rows
for insider/short/patient/impatient variants; access to original 13D labels and
SDC events; permitted use of WRDS Intraday Indicators and author-provided model
variants; treatment of the assigned 8-K news substitute; and what extension
scope earns separate credit beyond the already assigned PIN/VPIN benchmark.

**Current status.**
Scaffold and replication plan prepared. Real-data access, pilot feature/label
pipeline, and empirical results are not yet verified. Update this paragraph
with actual pilot evidence before the meeting.
