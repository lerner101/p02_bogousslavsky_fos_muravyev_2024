"""Explicit staged ITI workflow, recording progress and stopping on any error.

python src/run_iti_pipeline.py --collect --workers 4
Acquisition is bounded to training histories and ten scoring stocks, not the full
stock universe. Reruns reuse completed TAQ days; training and reports are rebuilt.
"""
import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    args = parser.parse_args()
    out = ROOT / "_output/ml_model"
    out.mkdir(parents=True, exist_ok=True)
    steps = []
    if args.collect:
        steps.append(["collect_iti_taq.py", "--workers", str(args.workers)])
    steps += [["build_iti_features.py"], ["train_iti.py"], ["score_iti.py"], ["compare_iti.py"]]
    state = {"started_utc": datetime.now(UTC).isoformat(), "completed_steps": [], "status": "running"}
    for step in steps:
        state["current_step"] = step[0]
        (out / "run_status.json").write_text(json.dumps(state, indent=2))
        result = subprocess.run([sys.executable, str(ROOT / "src" / step[0]), *step[1:]], cwd=ROOT, check=False)
        if result.returncode:
            state.update(status="failed", exit_code=result.returncode)
            (out / "run_status.json").write_text(json.dumps(state, indent=2))
            raise SystemExit(result.returncode)
        state["completed_steps"].append(step[0])
    state.update(status="complete", finished_utc=datetime.now(UTC).isoformat())
    (out / "run_status.json").write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
