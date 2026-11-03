"""Quick network check for the four data sources (about 1 to 3 minutes).

Run from the project folder, with the environment active:
    python tools/check_network.py

Each line shows whether a source answered, how fast, and the error if it did not. The report
is also saved to logs/network_check_<time>.txt. Nothing is downloaded into the project.
"""
from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PROJECT_UA = "Mozilla/5.0 (compatible; mbs-hedging-research/1.0)"
TIMEOUT = (8, 15)   # seconds to connect, seconds to wait between bytes
lines: list[str] = []


def say(msg: str) -> None:
    print(msg, flush=True)
    lines.append(msg)


def try_get(label: str, url: str, params: dict | None = None, ua: str | None = PROJECT_UA, ipv4_only: bool = False) -> None:
    import urllib3.util.connection as uc
    original = uc.allowed_gai_family
    if ipv4_only:
        uc.allowed_gai_family = lambda: socket.AF_INET
    t0 = time.time()
    try:
        headers = {"User-Agent": ua} if ua else {}
        r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        say(f"  {label:55s} HTTP {r.status_code}, {len(r.content):>9,d} bytes, {time.time() - t0:5.1f} s")
    except Exception as exc:  # report every failure type
        say(f"  {label:55s} FAILED after {time.time() - t0:5.1f} s: {type(exc).__name__}: {str(exc)[:160]}")
    finally:
        uc.allowed_gai_family = original


def main() -> int:
    say(f"Network check {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    say(f"Python {platform.python_version()} at {sys.executable}, requests {requests.__version__}, {platform.platform()}")
    import re
    proxies = {k: re.sub(r"//[^@/]*@", "//", v) for k, v in urllib.request.getproxies().items() if k in ("http", "https", "all")}
    say(f"Proxies Python will use: {proxies or 'none'}")
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        if os.environ.get(var) or os.environ.get(var.lower()):
            say(f"  environment variable {var} is set")
    say("Name lookup:")
    for host in ("fred.stlouisfed.org", "api.stlouisfed.org", "www.fhfa.gov", "query1.finance.yahoo.com"):
        try:
            fams = sorted({"IPv6" if a[0] == socket.AF_INET6 else "IPv4" for a in socket.getaddrinfo(host, 443)})
            say(f"  {host:30s} {', '.join(fams)}")
        except Exception as exc:
            say(f"  {host:30s} FAILED: {type(exc).__name__}: {exc}")

    fred = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    small = {"id": "DGS10", "cosd": "2026-10-01"}
    say("Requests (8 s to connect, 15 s between bytes):")
    try_get("FRED graph CSV, project user agent", fred, small)
    try_get("FRED graph CSV, default Python user agent", fred, small, ua=None)
    try_get("FRED graph CSV, project user agent, IPv4 only", fred, small, ipv4_only=True)
    try_get("FRED API host (no key, a quick 400 reply is fine)", "https://api.stlouisfed.org/fred/series/observations",
            {"series_id": "DGS10", "file_type": "json"})
    try_get("FHFA NMDB page", "https://www.fhfa.gov/data/nmdb")
    try_get("Yahoo chart API (MBB, one month)", "https://query1.finance.yahoo.com/v8/finance/chart/MBB",
            {"range": "1mo", "interval": "1d"})
    say("curl (the Mac's own HTTP client):")
    t0 = time.time()
    try:
        out = subprocess.run(["curl", "-sS", "-m", "20", "-o", os.devnull, "-w", "HTTP %{http_code}, %{size_download} bytes",
                              f"{fred}?id=DGS10&cosd=2026-10-01"], capture_output=True, text=True, timeout=30)
        say(f"  {'FRED graph CSV with curl':55s} {(out.stdout or out.stderr).strip()[:160]}, {time.time() - t0:5.1f} s")
    except Exception as exc:
        say(f"  {'FRED graph CSV with curl':55s} FAILED: {type(exc).__name__}: {exc}")

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    path = logs / f"network_check_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.txt"
    path.write_text("\n".join(lines) + "\n")
    say(f"Saved to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
