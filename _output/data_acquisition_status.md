# Data acquisition status

Snapshot: 2026-11-08T16:20:02.916640+00:00

Completed files only; a readable Parquet footer and matching manifest row count were checked.

Scope: through 2019, including 2004 warm-up history. Wider combined source extracts must be date-filtered before analysis.

| Source | Complete files | Years complete | Rows | Size (GiB) | Completed years |
|---|---:|---:|---:|---:|---|
| compustat_earnings | 1 | — | 543,630 | 0.006 |  |
| crsp_compustat_links | 1 | — | 92,711 | 0.001 |  |
| crsp_daily | 16 | 16/16 | 28,295,929 | 0.739 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| crsp_delistings | 1 | — | 7,448 | 0.000 |  |
| crsp_market | 1 | — | 4,027 | 0.000 |  |
| crsp_names | 1 | — | 42,714 | 0.001 |  |
| crsp_taq_links | 16 | 16/16 | 19,643,596 | 0.005 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| insider_transactions | 16 | 16/16 | 7,615,517 | 0.110 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| intraday_indicators | 16 | 16/16 | 31,622,735 | 5.126 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| markit_lending | 14 | 14/14 | 36,553,471 | 0.822 | 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| sdc_ma | 1 | — | 769,226 | 0.032 |  |
| sec_13d_filings | 15 | 15/15 | 27,622 | 0.210 | 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| sec_13d_index | 15 | 15/15 | 189,305 | 0.005 | 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| sec_cusip_links | 1 | — | 89,957 | 0.003 |  |
| iti_original | 1162 | 16/16 | 10,421,219 | 0.448 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| iti_extended | 60 | 16/16 | 10,916,428 | 0.443 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 |
| pin_legacy_daily | 198 | 9/9 | 2,285,733 | 0.140 | 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012 |
| FF4 daily factors | 1 | 16/16 | 4,027 | 0.000 | 2004–2019 |

Incomplete files (not usable yet): none

Retained later-year WRDS files outside scope: 0. Previously prepared wider public files are also retained.

Stopped later-year partial files (not active downloads): none

Failed extracts: none

Remaining gaps: cleaned/audited 13D labels; exact BFKR news events; BCL CPIE; supplemental intraday inputs; original training artifacts or retrained models.

See docs_src/site/project_overview/data_acquisition.md for scope and definitions.
