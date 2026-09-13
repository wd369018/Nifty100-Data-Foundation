"""Ad-hoc AppTest smoke test for the 8 dashboard screens (Sprint 4).

Run:  venv\\Scripts\\python.exe -m scripts.dev_smoke_dashboard
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NIFTY100_LINK_CHECK"] = "0"

PAGES_DIR = ROOT / "src" / "dashboard" / "pages"
PAGES = sorted(PAGES_DIR.glob("*.py"))


def main():
    failures = 0
    for page in PAGES:
        started = time.time()
        try:
            from streamlit.testing.v1 import AppTest

            at = AppTest.from_file(str(page), default_timeout=60)
            at.run()
            elapsed = time.time() - started
            ok = not at.exception
            status = "OK" if ok else "EXCEPTION"
            print(f"[{status}] {page.name}  ({elapsed:.1f}s)")
            if at.exception:
                failures += 1
                print(at.exception)
        except Exception as e:
            failures += 1
            print(f"[ERROR] {page.name}: {type(e).__name__}: {e}")

    print("\n== Profile page interaction: 5 tickers ==")
    from streamlit.testing.v1 import AppTest

    profile = PAGES_DIR / "02_profile.py"
    tickers = ["TCS", "SBIN", "HINDUNILVR", "RELIANCE", "SUNPHARMA"]
    for ticker in tickers:
        at = AppTest.from_file(str(profile), default_timeout=60)
        started = time.time()
        at.run()
        at.text_input[0].set_value(ticker).run()
        elapsed = time.time() - started
        status = "OK" if not at.exception else "EXCEPTION"
        print(f"  {ticker}: {status} ({elapsed:.1f}s)")
        if at.exception:
            failures += 1

    print(f"\nFailures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
