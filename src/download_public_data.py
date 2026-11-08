"""Download public source archives, then run prepare_public_data.py separately.

The source ITI ZIP contains wider history; preparation retains 2004–2019.
No WRDS credentials are needed. Total archive downloads are about 1.5 GB.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import is_zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "ITIs_extended_1993_2024.zip": "https://www.dropbox.com/scl/fi/hypqrf51w15v4jgrq4srk/ITIs_extended_1993_2024.zip?dl=1&rlkey=qqxm5doaiqr5grwrfwrwayulu",
    "cpie_data.zip": "https://github.com/edwinhu/pin-code/releases/download/legacy-1993-2012/cpie_data.zip",
    "F-F_Research_Data_Factors_daily_CSV.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip",
    "F-F_Momentum_Factor_daily_CSV.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip",
    "InformationTradingVolatility_DataFile.csv": "https://www.dropbox.com/s/ilw2l2pb9nh6kpm/InformationTradingVolatility_DataFile.csv?dl=1",
}


def valid_download(path, name):
    if not path.is_file():
        return False
    if name.endswith(".zip"):
        return is_zipfile(path)
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            return {"ticker", "date", "CC_day_type", "CO_day_type", "OC_day_type"}.issubset(
                reader.fieldnames or []) and next(reader, None) is not None
    except (OSError, UnicodeError, csv.Error):
        return False


def main():
    dest = ROOT / "_data" / "public"
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "_data" / "metadata" / "public_downloads.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name, url in SOURCES.items():
        target = dest / name
        if valid_download(target, name):
            print("Already saved:", name, flush=True)
            continue
        temporary = target.with_suffix(target.suffix + ".part")
        print("Downloading:", name, flush=True)
        with requests.get(url, stream=True, timeout=(20, 120)) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    stream.write(chunk)
        if not valid_download(temporary, name):
            raise ValueError(f"Response was not the expected ZIP/CSV source: {name}")
        temporary.replace(target)
        manifest[name] = {"source_url": url, "bytes": target.stat().st_size,
                          "retrieved_utc": datetime.now(timezone.utc).isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("Saved:", name, flush=True)


if __name__ == "__main__":
    main()
