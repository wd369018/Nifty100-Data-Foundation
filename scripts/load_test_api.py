"""Day 43 load test — 10 concurrent screener API calls finish in < 10 s.

Boots a real uvicorn server on an ephemeral port, fires 10 concurrent
GET /api/v1/screener requests from threads, then shuts the server down.

Run: venv\\Scripts\\python.exe scripts/load_test_api.py
Exit code 0 on success, 1 on failure.
"""

import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(ROOT, "venv", "Scripts", "python.exe")
CONCURRENCY = 10
LIMIT_S = 10.0


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port, timeout_s=60.0):
    url = f"http://127.0.0.1:{port}/api/v1/health"
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            with httpx.Client(timeout=2.0) as c:
                if c.get(url).status_code == 200:
                    return True
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    return False


def main():
    port = _free_port()
    server = subprocess.Popen(
        [
            PYTHON,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_ready(port):
            print("FAIL: server did not become ready")
            sys.exit(1)

        def one_call(_):
            with httpx.Client(timeout=30.0) as c:
                start = time.perf_counter()
                r = c.get(
                    f"http://127.0.0.1:{port}/api/v1/screener",
                    params={"min_roe": "15"},
                )
                elapsed = (time.perf_counter() - start) * 1000
                body = r.json()
                return r.status_code, body["count"], elapsed

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            results = list(pool.map(one_call, range(CONCURRENCY)))
        total = time.perf_counter() - start

        ids = {code for code, _, _ in results}
        counts = {n for _, n, _ in results}
        per_call_ms = [e for _, _, e in results]

        print(f"requests={CONCURRENCY}")
        print(f"total_seconds={total:.2f}")
        print(f"all_status_200={ids == {200}}")
        print(f"counts_consistent={len(counts) == 1} (count={counts})")
        print(f"mean_call_ms={sum(per_call_ms) / len(per_call_ms):.1f}")
        print(f"max_call_ms={max(per_call_ms):.1f}")
        print(f"limit_seconds={LIMIT_S}")
        passed = total < LIMIT_S and ids == {200} and len(counts) == 1
        print(f"PASS={passed}")

        if not passed:
            sys.exit(1)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
