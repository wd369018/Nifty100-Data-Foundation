"""Day 43 e2e check — Streamlit dashboard and FastAPI run side by side.

Boots uvicorn on one port and streamlit (headless) on another, then
verifies both respond over HTTP on their own ports.

Run: venv\\Scripts\\python.exe scripts/e2e_endpoints.py
Exit code 0 on success, 1 on failure.
"""

import os
import socket
import subprocess
import sys
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(ROOT, "venv", "Scripts", "python.exe")
APP = os.path.join(ROOT, "src", "dashboard", "app.py")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ok(port, path, timeout_s=90.0):
    url = f"http://127.0.0.1:{port}{path}"
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            with httpx.Client(timeout=2.0) as c:
                if c.get(url).status_code == 200:
                    return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def main():
    api_port = _free_port()
    dash_port = _free_port()

    api = subprocess.Popen(
        [
            PYTHON,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    dash = subprocess.Popen(
        [
            PYTHON,
            "-m",
            "streamlit",
            "run",
            APP,
            "--server.headless",
            "true",
            "--server.port",
            str(dash_port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        api_ok = _wait_ok(api_port, "/api/v1/health")
        dash_ok = _wait_ok(dash_port, "/")

        print(f"fastapi  http://127.0.0.1:{api_port}/api/v1/health -> {api_ok}")
        print(f"streamlit http://127.0.0.1:{dash_port}/          -> {dash_ok}")
        passed = api_ok and dash_ok
        print(f"PASS={passed}")
        if not passed:
            sys.exit(1)
    finally:
        for proc in (dash, api):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
