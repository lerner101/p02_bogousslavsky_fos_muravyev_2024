"""Recreate approximate references from 1800x2329 RGB renderings of PDF pages 43–45.

Optional reference-maintenance command, NOT part of a research/figure build:
python data_manual/iti_figure_benchmarks/digitize.py --pdf PATH --rendered-dir PATH
Renderings are ignored local work files; committed numeric CSVs suffice to build.
Calibrations apply only to the supplied forthcoming-paper PDF, not other editions.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

DEST = Path(__file__).resolve().parent
CALIBRATION = {
    "figure1": {"x_year_1994": 485, "x_year_2018": 1441, "y_r2_zero": 871, "y_r2_point2": 614},
    "svol": {"x0": 763, "x1": 925.5, "y0": 1269, "value0": .25, "y1": 858, "value1": .40,
             "density_zero_y": 1297, "density_tick_y": 829, "density_tick": .8,
             "left": 630, "right": 1189, "top": 770, "bottom": 1296},
    "rvol": {"x0": 871, "x1": 1029.5, "y0": 1930, "value0": .32, "y1": 1574, "value1": .38,
             "density_zero_y": 2015, "density_tick_y": 1545, "density_tick": .5,
             "left": 630, "right": 1189, "top": 1485, "bottom": 2014},
}
# Direct transcription of Figure 3, preserving printed rounded values and topology.
# node, feature, threshold, mse, samples, value, left, right
TREE = [
    (0, "svol", -.076, .095, 61255, .354, 1, 2),
    (1, "svol", -.387, .067, 31778, .266, 3, 4),
    (2, "rvol", -1.347, .108, 29477, .449, 5, 6),
    (3, "illiq_ov", -.495, .064, 17476, .234, 7, 8),
    (4, "rvol", -.740, .068, 14302, .304, 9, 10),
    (5, "prc", 1.655, .108, 3291, .720, 11, 12),
    (6, "svol", 1.274, .098, 26186, .415, 13, 14),
    (7, None, None, .076, 3478, .286, None, None),
    (8, None, None, .061, 13998, .221, None, None),
    (9, None, None, .083, 3941, .375, None, None),
    (10, None, None, .060, 10361, .278, None, None),
    (11, None, None, .130, 936, .586, None, None),
    (12, None, None, .089, 2355, .773, None, None),
    (13, None, None, .084, 19650, .384, None, None),
    (14, None, None, .130, 6536, .509, None, None),
]


def load_image(folder, page):
    image = Image.open(folder / f"page{page}.png").convert("RGB")
    if image.size != (1800, 2329):
        raise ValueError("Reference calibration requires 1800x2329 page renderings")
    return np.asarray(image).astype(int)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--rendered-dir", type=Path, required=True)
    args = parser.parse_args()
    page = load_image(args.rendered_dir, 43)
    red, green, blue = page[:, :, 0], page[:, :, 1], page[:, :, 2]
    masks = {"iti": (blue > 180) & (red < 80) & (green < 80),
             "controls": (red > 180) & (green < 80) & (blue < 80)}
    c = CALIBRATION["figure1"]
    rows = []
    for year in range(2005, 2019):
        x = round(c["x_year_1994"] + (year - 1994) * (c["x_year_2018"] - c["x_year_1994"]) / 24)
        row = {"year": year, "pixel_x": x}
        for name, mask in masks.items():
            # Red dashes can leave the exact annual x coordinate uncolored.
            radius = 1 if name == "iti" else 5
            ys, _ = np.where(mask[535:860, x-radius:x+radius+1])
            if not len(ys):
                raise ValueError(f"No {name} pixels at year {year}")
            y = float(np.median(ys + 535))
            row[f"{name}_pixel_y"] = y
            row[f"{name}_adjusted_r2"] = .2 * (c["y_r2_zero"] - y) / (c["y_r2_zero"] - c["y_r2_point2"])
        rows.append(row)
    pd.DataFrame(rows).to_csv(DEST / "figure1.csv", index=False, float_format="%.7f")

    page = load_image(args.rendered_dir, 44)
    red, green, blue = page[:, :, 0], page[:, :, 1], page[:, :, 2]
    colored = (blue - red > 60) & (green - red > 20) & (blue > 140)
    # The rasterized bars' dominant fill is RGB(233,233,233); exclude grid lines.
    gray = (np.max(page, axis=2) - np.min(page, axis=2) <= 1) & (red >= 231) & (red <= 235)
    rows = []
    for feature in ["svol", "rvol"]:
        c = CALIBRATION[feature]
        for x in np.linspace(c["left"], c["right"], 100):
            px = round(x)
            ys, _ = np.where(colored[c["top"]:c["bottom"], px-1:px+2])
            y = float(np.median(ys + c["top"])) if len(ys) else np.nan
            column = gray[c["top"]:c["bottom"], px]
            starts = np.flatnonzero(np.convolve(column.astype(int), np.ones(8, dtype=int), mode="valid") == 8)
            bar_y = float(starts[0] + c["top"]) if len(starts) else float(c["density_zero_y"])
            rows.append({"feature": feature, "standardized_value": (x - c["x0"]) / (c["x1"] - c["x0"]),
                         "mean_iti": c["value0"] + (c["y0"] - y) * (c["value1"] - c["value0"]) / (c["y0"] - c["y1"]),
                         "density": max(0, (c["density_zero_y"] - bar_y) * c["density_tick"] / (c["density_zero_y"] - c["density_tick_y"])),
                         "pixel_x": x, "curve_pixel_y": y, "bar_top_pixel_y": bar_y})
    curves = pd.DataFrame(rows)
    curves["mean_iti"] = curves.groupby("feature").mean_iti.transform(lambda x: x.interpolate(limit_area="inside"))
    if curves.mean_iti.isna().any():
        raise ValueError("Blue curve endpoints need calibration review")
    curves.to_csv(DEST / "figure2.csv", index=False, float_format="%.7f")
    pd.DataFrame(TREE, columns=["node", "feature", "threshold", "mse", "filing_days", "mean_iti", "left_child", "right_child"]).astype(
        {"left_child": "Int64", "right_child": "Int64"}).to_csv(DEST / "figure3.csv", index=False)
    provenance = {
        "citation": "Bogousslavsky, Fos, and Muravyev (2024), Informed Trading Intensity; supplied forthcoming-paper PDF",
        "doi": "10.1111/jofi.13320", "pdf_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "pdf_pages": [43, 44, 45], "printed_pages": [41, 42, 43], "rendering_pixels": [1800, 2329],
        "rendering": "macOS PDFKit thumbnailOfSize_forBox_((1800,2400),0), PNG; local renderings are not distributed",
        "calibration": CALIBRATION,
        "method": "RGB pixel tracing with linear axis calibration; annual points for Figure 1, 100 horizontal samples per Figure 2 panel; Figure 3 transcribed from node labels",
        "units": "ITI and R2 are decimal fractions. Density is per unit of standardized feature, using the paper's right-axis percent ticks divided by 100.",
        "approximation": "Figures 1–2 are approximate digitizations, not author-provided numeric results. Raster/axis errors, dashed-line gaps and narrow spikes limit precision; roughly 0.005 R2/ITI resolution, without a formal error guarantee. No smoothing of substantive curve shapes.",
        "tree_notes": ["Preserve printed rounded node values, counts, MSEs and topology.",
                       "Tree root count 61,255 differs from main paper sample count 58,197.",
                       "Caption says about one-third of ITI variation; printed rounded MSEs do not reproduce that claim exactly. Do not infer an exact published R2 from these nodes.",
                       "Left branches follow <= thresholds, consistent with the graphic; caption's generic right-branch wording is not used."],
    }
    (DEST / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
