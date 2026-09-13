"""Archive the Sprint 6 deliverables into output/final_deliverables/.

Run:  venv\\Scripts\\python.exe scripts/archive_deliverables.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "output" / "final_deliverables"

DELIVERABLES = [
    ("output/cluster_labels.csv", "file"),
    ("output/cluster_profile.csv", "file"),
    ("output/outlier_report.csv", "file"),
    ("output/portfolio_stats.csv", "file"),
    ("output/perf_notes.md", "file"),
    ("reports/elbow_plot.png", "file"),
    ("reports/correlation_heatmap.png", "file"),
    ("reports/pytest_report.html", "file"),
    ("docs/openapi.json", "file"),
    ("docs/nifty100.postman_collection.json", "file"),
    ("docs/analyst_guide.pdf", "file"),
    ("docs/acceptance_checklist.pdf", "file"),
    ("docs/sprint6_review.md", "file"),
    ("src/api", "dir"),
]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    copied, missing = [], []
    for rel, kind in DELIVERABLES:
        src = ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        target = DEST / src.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if kind == "dir":
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
        copied.append(rel)

    print(f"archived to {DEST}")
    for rel in copied:
        print(f"  + {rel}")
    if missing:
        print("not yet available (regenerate at Day 45):")
        for rel in missing:
            print(f"  - {rel}")


if __name__ == "__main__":
    main()
