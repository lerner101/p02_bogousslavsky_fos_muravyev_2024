# BFKR news preparation

```json
{
  "source": "_data/public/InformationTradingVolatility_DataFile.csv",
  "sha256": "33fb626e68141f7a91bc54d9828fe330aa50bd3d7615dc008811de603079ee24",
  "source_rows": 1952175,
  "source_tickers": 896,
  "date_range": [
    "2000-01-03",
    "2015-12-31"
  ],
  "link_counts": {
    "linked": 1328872,
    "unmatched": 623303
  },
  "linked_rows_by_year": {
    "2004": 65237,
    "2005": 118733,
    "2006": 114475,
    "2007": 114121,
    "2008": 116156,
    "2009": 115883,
    "2010": 117196,
    "2011": 116593,
    "2012": 114583,
    "2013": 114232,
    "2014": 112175,
    "2015": 109488
  },
  "earnings_rows": 305410,
  "earnings_timing": "Raw Compustat rdq; no after-hours volume adjustment"
}
```

Link outcomes by year:

```
year  link_status
2000  unmatched      119922
2001  unmatched      119827
2002  unmatched      122791
2003  unmatched      123742
2004  linked          65237
      unmatched       57817
2005  linked         118733
      unmatched        4536
2006  linked         114475
      unmatched        5086
2007  linked         114121
      unmatched        5235
2008  linked         116156
      unmatched        6659
2009  linked         115883
      unmatched        6305
2010  linked         117196
      unmatched        5039
2011  linked         116593
      unmatched        5795
2012  linked         114583
      unmatched        7582
2013  linked         114232
      unmatched        9080
2014  linked         112175
      unmatched       11339
2015  linked         109488
      unmatched       12548
```

Unmatched, ambiguous and duplicate stock-days are retained only in news_link_audit.parquet. Dates outside the local CRSP name history can be unmatched.
