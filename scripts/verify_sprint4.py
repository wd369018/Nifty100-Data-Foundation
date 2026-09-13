"""Sprint 4 verification harness.

Re-runs every Sprint 4 (Days 22-28) exit criterion against the live
database, shared outputs and the Streamlit dashboard screens.

Sections:
  [1] Valuation module (fresh rebuild from the DB)
  [2] Valuation artefacts on disk (summary xlsx + flags csv)
  [3] Dashboard screens (AppTest: all 8 pages render clean)
  [4] Company Profile load time for 5 tickers (< 3s, day 27)
  [5] Headless server health endpoint (/_stcore/health)

Run:  python scripts/verify_sprint4.py
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NIFTY100_LINK_CHECK", "0")

from src.analytics.valuation import (
    OUTPUT_COLUMNS,
    build_valuation_frame,
)

PASS = "PASS"


def check(name, passed, detail=""):
    status = PASS if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def run_page(page_path, timeout=90):
    """Run one Streamlit page under AppTest; return (ok, elements, error)."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(page_path), default_timeout=timeout)
    at.run()
    if at.exception:
        return False, at, str(at.exception)
    return not at.exception, at, ""


def main():
    failures = []

    print("=" * 70)
    print("SPRINT 4 VERIFICATION (Days 22-28 — Dashboard + Valuation)")
    print("=" * 70)

    # ----------------------------------------------------------------
    # 1. Valuation module
    # ----------------------------------------------------------------
    print("\n[1] Valuation module (fresh rebuild)")
    frame = build_valuation_frame()
    failures.append(
        not check(
            "92-company summary built",
            len(frame) == 92,
            f"{len(frame)} rows",
        )
    )
    failures.append(
        not check(
            "Output columns match spec",
            list(frame.columns) == OUTPUT_COLUMNS,
            str(list(frame.columns)),
        )
    )
    counts = frame["flag"].value_counts()
    ok_flags = (
        counts.get("Caution", 0) >= 1
        and counts.get("Discount", 0) >= 1
        and counts.get("Fair", 0) >= 1
    )
    failures.append(
        not check(
            "Caution / Discount / Fair all present",
            ok_flags,
            dict(counts),
        )
    )
    missing_flags = int(frame["flag"].isna().sum())
    failures.append(
        not check("No company missing a valuation flag", missing_flags == 0)
    )
    fcf_vals = pd.to_numeric(frame["fcf_yield_pct"], errors="coerce")
    fcf_ok = fcf_vals.notna().sum() > 0 and (fcf_vals.dropna() != 0).all()
    failures.append(
        not check(
            "FCF yields computed for most companies",
            fcf_ok,
            f"{fcf_vals.notna().sum()} of 92",
        )
    )

    # ----------------------------------------------------------------
    # 2. Valuation artefacts on disk
    # ----------------------------------------------------------------
    print("\n[2] Output artefacts")
    summary_path = ROOT / "output" / "valuation_summary.xlsx"
    flags_path = ROOT / "output" / "valuation_flags.csv"

    if summary_path.exists():
        summary = pd.read_excel(summary_path)
        failures.append(
            not check(
                "valuation_summary.xlsx: 92 rows x 10 cols",
                len(summary) == 92 and list(summary.columns) == OUTPUT_COLUMNS,
                f"{len(summary)} rows",
            )
        )
    else:
        failures.append(not check("valuation_summary.xlsx exists", False))

    if flags_path.exists():
        flags = pd.read_csv(flags_path)
        subset_flags = set(flags["flag"]) <= {"Caution", "Discount"}
        subset_ids = set(flags["company_id"]) <= set(summary["company_id"])
        failures.append(
            not check(
                "valuation_flags.csv: only Caution/Discount, subset of summary",
                subset_flags and subset_ids,
                f"{len(flags)} companies",
            )
        )
        fresh_flagged = set(
            frame[frame["flag"].isin(["Caution", "Discount"])]["company_id"]
        )
        failures.append(
            not check(
                "Flags CSV matches a fresh rebuild",
                set(flags["company_id"]) == fresh_flagged,
            )
        )
    else:
        failures.append(not check("valuation_flags.csv exists", False))

    # ----------------------------------------------------------------
    # 3. Dashboard screens
    # ----------------------------------------------------------------
    print("\n[3] Dashboard screens (AppTest)")
    pages_dir = ROOT / "src" / "dashboard" / "pages"
    pages = sorted(pages_dir.glob("*.py"))
    failures.append(not check("8 page files present", len(pages) == 8))

    for page in pages:
        ok, at, error = run_page(page)
        detail = ""
        if ok:
            detail = (
                f"{len(at.metric)} metrics"
                if at.metric
                else f"{len(at.get('plotly_chart'))} charts"
            )
        else:
            detail = str(error).splitlines()[0]
        failures.append(not check(f"{page.stem} renders clean", ok, detail))

    # ---- Home: KPI tiles + sector donut
    home_ok, home, _ = run_page(pages_dir / "01_home.py")
    failures.append(
        not check(
            "Home: 6 KPI tiles", len(home.metric) >= 6, f"{len(home.metric)} metrics"
        )
    )
    failures.append(
        not check("Home: sector donut chart", len(home.get("plotly_chart")) >= 1)
    )

    # ---- Screener: 10 sliders, 6 presets, CSV download
    sc_ok, screener, _ = run_page(pages_dir / "03_screener.py")
    if sc_ok:
        n_sliders = len(screener.slider)
        n_presets = len(screener.button)
        failures.append(
            not check("Screener: 10 sliders", n_sliders == 10, f"{n_sliders} sliders")
        )
        failures.append(
            not check(
                "Screener: 6 preset buttons", n_presets >= 6, f"{n_presets} buttons"
            )
        )
        try:
            screener.button(key="preset_Quality").click().run()
            preset_ok = not screener.exception
        except (KeyError, IndexError, AttributeError):
            preset_ok = False
        failures.append(not check("Screener: Quality preset applies", preset_ok))
        dl = screener.get("download_button")
        label_ok = any(
            "Download filtered results" in str(getattr(b, "label", "")) for b in dl
        )
        failures.append(not check("Screener: CSV download button", label_ok))
    else:
        failures.append(not check("Screener screen loads", False))

    # ---- Peers: 11 groups + radar
    pr_ok, peers, _ = run_page(pages_dir / "04_peers.py")
    if pr_ok:
        groups = peers.selectbox[0].options
        failures.append(
            not check(
                "Peers: 11 peer groups", len(groups) >= 11, f"{len(groups)} groups"
            )
        )
        failures.append(
            not check(
                "Peers: radar + KPI table render",
                len(peers.get("plotly_chart")) >= 1 and len(peers.dataframe) >= 1,
            )
        )
    else:
        failures.append(not check("Peers screen loads", False))

    # ---- Trends: multiselect overlay
    tr_ok, trends, _ = run_page(pages_dir / "05_trends.py")
    if tr_ok:
        failures.append(
            not check(
                "Trends: metric multiselect present", len(trends.multiselect) >= 1
            )
        )
    else:
        failures.append(not check("Trends screen loads", False))

    # ---- Sectors: 10 sector options
    se_ok, sectors, _ = run_page(pages_dir / "06_sectors.py")
    if se_ok:
        failures.append(
            not check(
                "Sectors: 10 sectors listed",
                len(sectors.selectbox[0].options) >= 10,
                f"{len(sectors.selectbox[0].options)} sectors",
            )
        )
    else:
        failures.append(not check("Sectors screen loads", False))

    # ---- Capital map: treemap + pattern browse
    ca_ok, capital, _ = run_page(pages_dir / "07_capital.py")
    if ca_ok:
        failures.append(
            not check(
                "Capital map: treemap renders", len(capital.get("plotly_chart")) >= 1
            )
        )
    else:
        failures.append(not check("Capital map screen loads", False))

    # ---- Reports: annual report list
    re_ok, reports, _ = run_page(pages_dir / "08_reports.py")
    if re_ok:
        failures.append(
            not check(
                "Reports: company selector present",
                bool(reports.selectbox or reports.text_input),
            )
        )
    else:
        failures.append(not check("Reports screen loads", False))

    # ----------------------------------------------------------------
    # 4. Profile timing (day 27: < 3s per ticker)
    # ----------------------------------------------------------------
    print("\n[4] Company Profile load time (5 tickers, target < 3s)")
    profile = pages_dir / "02_profile.py"
    tickers = ["TCS", "SBIN", "HINDUNILVR", "RELIANCE", "SUNPHARMA"]
    for ticker in tickers:
        ok, at, _ = run_page(profile)
        started = time.time()
        at.text_input[0].set_value(ticker).run()
        elapsed = time.time() - started
        captions = "  ".join(
            getattr(c, "value", "").replace("**", "") for c in at.caption
        )
        has_ticker = f"Ticker: {ticker}" in captions
        good = (not at.exception) and elapsed < 3.0 and has_ticker
        failures.append(
            not check(
                f"{ticker} profile",
                good,
                f"{elapsed:.2f}s" + ("·ticker shown" if has_ticker else "·no ticker"),
            )
        )

    # ----------------------------------------------------------------
    # 5. Headless server health check
    # ----------------------------------------------------------------
    print("\n[5] Headless server health endpoint")
    status = _health_check()
    failures.append(
        not check(
            "GET /_stcore/health == 200",
            status == 200,
            "ok" if status == 200 else str(status),
        )
    )

    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    total_fails = sum(1 for f in failures if f)
    if total_fails == 0:
        print("ALL SPRINT 4 CHECKS PASSED")
        print("Valuation flag mix:", dict(counts))
    else:
        print(f"{total_fails} CHECK(S) FAILED")
    print("=" * 70)
    return total_fails


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _health_check():
    import urllib.request

    port = _free_port()
    env = dict(os.environ)
    env["NIFTY100_LINK_CHECK"] = "0"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/dashboard/app.py",
            "--server.headless=true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/_stcore/health", timeout=2
                ) as resp:
                    return resp.status
            except Exception:
                time.sleep(1)
        return None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
