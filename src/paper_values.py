"""Published values from Bogousslavsky, Fos and Muravyev (2024), for comparison.

Tables are transcribed from the paper text; figure values are read off the
plots (about +/-0.003) and are approximate.
"""

ITI_NAMES = ["ITI(13D)", "ITI(insider)", "ITI(short)", "ITI(patient)", "ITI(impatient)"]

# Table 1 (full sample): mean, SD, within-stock SD for the ITI measures, plus the
# trade-indicator means in each training sample.
TABLE1_ITI = {
    "ITI(13D)": (0.2745, 0.1595, 0.1558), "ITI(patient)": (0.2038, 0.1452, 0.1427),
    "ITI(impatient)": (0.4213, 0.1375, 0.1322), "ITI(insider)": (0.4786, 0.1578, 0.1569),
    "ITI(short)": (0.4460, 0.0787, 0.0670),
}
TABLE1_13D_TRADE_MEAN = 0.3603
TABLE1_13D_ROWS = 58_197

# Table 2: day-with-13D-trade (cols 1-3) and 13D turnover on trade days (cols 4-6)
# on ITI and controls, filing FE. (coef, t); R2 is the paper's adjusted R2.
TABLE2 = {
    1: {"ITI": (0.697, 43.572)},
    2: {"es": (-3.412, -4.053), "lambda": (-1.186, -4.822), "depth": (34.360, 8.996),
        "rvol": (-0.832, -6.149), "turn": (1.377, 9.845), "oi": (0.379, 0.748),
        "abs_oi": (6.732, 10.534), "ret": (-0.083, -1.258)},
    3: {"ITI": (0.604, 36.648), "es": (-0.807, -1.098), "lambda": (-0.589, -2.599),
        "depth": (21.323, 8.037), "rvol": (-0.361, -3.475), "turn": (0.640, 6.110),
        "oi": (0.294, 0.703), "abs_oi": (2.613, 4.781), "ret": (-0.030, -0.511)},
    4: {"ITI": (0.007, 22.184)},
    5: {"es": (0.099, 3.179), "lambda": (-0.024, -5.275), "depth": (-0.096, -1.135),
        "rvol": (0.000, 0.111), "turn": (0.039, 8.284), "oi": (0.073, 3.065),
        "abs_oi": (0.180, 6.329), "ret": (-0.008, -3.375)},
    6: {"ITI": (0.004, 13.657), "es": (0.108, 3.505), "lambda": (-0.020, -4.673),
        "depth": (-0.132, -1.603), "rvol": (0.001, 0.329), "turn": (0.037, 7.885),
        "oi": (0.071, 3.092), "abs_oi": (0.161, 5.811), "ret": (-0.007, -3.064)},
}
TABLE2_R2 = {1: 0.0986, 2: 0.0461, 3: 0.1073, 4: 0.0692, 5: 0.2579, 6: 0.2756}

# Table 3: day with 13D trade on feature-group ITIs, filing FE.
TABLE3 = {
    1: {"ITI": (0.697, 43.572)},
    2: {"ITI(liquidity)": (0.596, 24.561)},
    3: {"ITI(return)": (0.510, 18.963)},
    4: {"ITI(volatility)": (0.498, 19.266)},
    5: {"ITI(volume)": (0.671, 39.235)},
    6: {"ITI(liquidity)": (0.289, 17.945), "ITI(return)": (0.239, 14.256),
        "ITI(volatility)": (0.208, 12.912), "ITI(volume)": (0.526, 36.533)},
}
TABLE3_R2 = {1: 0.0986, 2: 0.0412, 3: 0.0264, 4: 0.0278, 5: 0.0769, 6: 0.1043}

# Table 4: turnover-matched 13D sample. Panel (a) differences; panel (b) col 1 and 3 ITI.
TABLE4_A = {"turn": (0.000, 1.027), "ITI": (0.033, 5.253)}
TABLE4_B = {1: {"ITI": (0.509, 5.445)}, 3: {"ITI": (0.507, 5.284)}}
TABLE4_OBS = 2_388
TABLE4_TURN_GAP = 0.00002  # max |turnover difference| for a matched pair

# Table 10 Panel (a): coefficient, t-stat. Columns 1-5 (column 6 adds PIN).
TABLE10 = {
    1: {"ITI(13D)": (0.0126, 6.82)},
    2: {"ITI(13D)": (0.0117, 4.67), "ITI(insider)": (0.0119, 4.82), "ITI(short)": (-0.0084, -1.29)},
    3: {"ITI(patient)": (0.0006, 0.28), "ITI(impatient)": (0.0158, 6.51)},
    4: {"ITI(13D)": (0.0053, 2.22), "ITI(insider)": (0.0107, 4.42), "ITI(short)": (-0.0201, -2.79),
        "ITI(patient)": (-0.003, -1.43), "ITI(impatient)": (0.0163, 5.83)},
    5: {"ITI(13D)": (0.0061, 3.23), "ITI(insider)": (0.0094, 5.69), "ITI(short)": (-0.0065, -1.26),
        "ITI(patient)": (-0.0038, -1.85), "ITI(impatient)": (0.0164, 5.25)},
}
TABLE10_NOBS = 3_484_923

# Table 11: deciles Low..High then H-L. Panel (a) raw, Panel (b) FF4 alpha.
TABLE11_RAW = {
    "ITI(13D)": [0.0071, 0.0079, 0.0083, 0.0088, 0.0089, 0.0087, 0.0099, 0.0099, 0.0106, 0.0115, 0.0044],
    "ITI(insider)": [0.0072, 0.0078, 0.0085, 0.0090, 0.0089, 0.0096, 0.0094, 0.0103, 0.0103, 0.0109, 0.0037],
    "ITI(short)": [0.0085, 0.0086, 0.0086, 0.0089, 0.0093, 0.0088, 0.0095, 0.0098, 0.0099, 0.0098, 0.0014],
    "ITI(patient)": [0.0079, 0.0082, 0.0085, 0.0088, 0.0090, 0.0091, 0.0097, 0.0095, 0.0101, 0.0109, 0.0030],
    "ITI(impatient)": [0.0064, 0.0077, 0.0080, 0.0088, 0.0093, 0.0094, 0.0099, 0.0103, 0.0104, 0.0115, 0.0051],
}
TABLE11_RAW_HL_T = {"ITI(13D)": 4.9, "ITI(insider)": 3.3, "ITI(short)": 1.0,
                    "ITI(patient)": 3.9, "ITI(impatient)": 5.1}
TABLE11_ALPHA = {
    "ITI(13D)": [-0.0003, 0.0005, 0.0007, 0.0014, 0.0017, 0.0013, 0.0027, 0.0027, 0.0035, 0.0049, 0.0052],
    "ITI(insider)": [0.0003, 0.0010, 0.0016, 0.0020, 0.0018, 0.0024, 0.0021, 0.0028, 0.0025, 0.0026, 0.0022],
    "ITI(short)": [0.0017, 0.0016, 0.0015, 0.0017, 0.0020, 0.0014, 0.0021, 0.0024, 0.0025, 0.0022, 0.0005],
    "ITI(patient)": [0.0008, 0.0007, 0.0011, 0.0014, 0.0016, 0.0018, 0.0024, 0.0023, 0.0027, 0.0041, 0.0034],
    "ITI(impatient)": [-0.0006, 0.0004, 0.0006, 0.0015, 0.0018, 0.0021, 0.0025, 0.0030, 0.0032, 0.0048, 0.0054],
}
TABLE11_ALPHA_HL_T = {"ITI(13D)": 6.2, "ITI(insider)": 2.9, "ITI(short)": 0.5,
                      "ITI(patient)": 4.2, "ITI(impatient)": 5.7}

# Table 5: coefficient, t-stat.
TABLE5 = {
    1: {"ret": (-0.004, -1.774)},
    2: {"ret": (-0.014, -4.477), "ITI(13D)": (0.002, 23.553), "ret*ITI(13D)": (0.031, 6.445)},
    3: {"ret": (-0.006, -1.977), "ITI(13D)": (0.002, 20.001), "ret*ITI(13D)": (0.034, 5.830),
        "ret*turn": (0.008, 0.541), "ret*rvol": (-0.029, -1.652), "ret*ES%": (-0.756, -4.936)},
}
TABLE5_NOBS = 16_814_168

DAYS = list(range(-10, 11))
# Figure 4(a), 4(b) and IA.5, read off the plots.
FIG4A = [-0.003, -0.004, -0.006, -0.005, -0.004, -0.003, -0.003, -0.002, 0.005, 0.018,
         0.095, 0.044, 0.034, 0.026, 0.020, 0.017, 0.011, 0.009, 0.008, 0.007, 0.006]
FIG4B_LARGE = [0.0, -0.003, -0.005, -0.003, 0.0, 0.0, 0.001, 0.004, 0.013, 0.030,
               0.155, 0.090, 0.064, 0.048, 0.039, 0.034, 0.027, 0.023, 0.021, 0.019, 0.019]
FIG4B_SMALL = [0.0, -0.002, -0.004, -0.003, -0.002, -0.002, -0.001, 0.0, 0.002, 0.006,
               0.058, 0.014, 0.018, 0.014, 0.012, 0.009, 0.005, 0.003, 0.002, 0.002, 0.002]
FIGIA5 = [0.003, 0.003, 0.0065, 0.0105, 0.004, 0.011, 0.0135, 0.018, 0.021, 0.0235,
          0.27, 0.307, 0.248, 0.21, 0.186, 0.179, 0.162, 0.145, 0.133, 0.132, 0.125]
FIGIA5_EVENTS = 1_577

# Figure 4(c): ITI around news events (excluding earnings), days -5..5, read off the plot.
NEWS_DAYS = list(range(-5, 6))
FIG4C = [-0.0012, 0.0006, 0.0010, 0.0018, 0.0063, 0.0120, 0.0065, 0.0032, 0.0006, -0.0001, -0.0001]

# Table IA.6 Panel (b): XGBoost out-of-sample metrics on the 13D sample.
IA6_XGB = {"roc_auc": 0.7084, "log_loss": 0.5940, "mae": 0.3763}
