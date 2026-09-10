"""Diagnostic for the container-freight sources.

There is no free, documented API for container spot rates, so the collector
scrapes public pages. When a publisher changes its markup this script says what
the page actually serves now - status, size, embedded JSON blobs and any
date/value pairs it can find - so the selectors in
pipeline/fetchers/freight.py can be re-pinned without guesswork.

    python scripts/probe_freight.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline import util  # noqa: E402

CANDIDATES = [
    ("FBX landing page", "https://fbx.freightos.com/"),
    ("FBX index API (a)", "https://fbx.freightos.com/api/index/FBX11"),
    ("FBX index API (b)", "https://terminal.freightos.com/api/index/FBX11"),
    ("Freightos data page", "https://www.freightos.com/freight-resources/freight-rate-index/"),
    ("Drewry WCI", "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/"
                   "world-container-index-assessed-by-drewry"),
    ("SSE SCFI", "https://en.sse.net.cn/indices/scfinew.jsp"),
    ("SSE index home", "https://en.sse.net.cn/indices/indexichome.jsp"),
    ("Xeneta XSI", "https://www.xeneta.com/xeneta-shipping-index"),
]

JSON_BLOB = re.compile(
    r'<script[^>]*(?:id="__NEXT_DATA__"|type="application/json")[^>]*>(.*?)</script>', re.S)
ASSIGNED = re.compile(r'(?:window\.__[A-Z_]+__|var\s+\w+)\s*=\s*(\{.*?\});', re.S)
DATE_VALUE = re.compile(r'"?(?:date|day|x)"?\s*:\s*"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?'
                        r'[^}]{0,80}?"?(?:value|price|close|y)"?\s*:\s*([0-9.]+)', re.I)
MONEY_NEAR = re.compile(r'([A-Za-z ]{0,40}?)\$\s*([0-9][0-9,]{2,7})')


def show(name: str, url: str) -> None:
    print(f"\n{'=' * 72}\n{name}\n{url}")
    resp = util.get(url, retries=1, headers={
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    if resp is None:
        print("  -> no response (blocked, 404 or timeout)")
        return
    body = resp.text
    print(f"  status 200 · {resp.headers.get('content-type', '?')} · {len(body):,} chars")

    try:
        payload = resp.json()
        print(f"  JSON response, top-level keys: {list(payload)[:12]}")
        print("  sample: " + json.dumps(payload)[:400])
        return
    except ValueError:
        pass

    for label, pattern in (("embedded JSON block", JSON_BLOB), ("assigned JS object", ASSIGNED)):
        for match in list(pattern.finditer(body))[:2]:
            blob = match.group(1)
            print(f"  {label}: {len(blob):,} chars, starts {blob[:160]!r}")
            pairs = DATE_VALUE.findall(blob)
            if pairs:
                print(f"    -> {len(pairs)} date/value pairs, e.g. {pairs[:4]}")

    pairs = DATE_VALUE.findall(body)
    if pairs:
        print(f"  raw date/value pairs in page: {len(pairs)}, e.g. {pairs[:4]}")

    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    money = MONEY_NEAR.findall(text)[:8]
    if money:
        print(f"  dollar figures with context: {[(c.strip()[-40:], v) for c, v in money]}")
    for term in ("composite", "Rotterdam", "Genoa", "FBX", "SCFI", "Comprehensive Index"):
        idx = text.lower().find(term.lower())
        if idx != -1:
            print(f"  ...{term}: {text[max(0, idx - 60):idx + 140]!r}")


def main() -> int:
    for name, url in CANDIDATES:
        try:
            show(name, url)
        except Exception as exc:  # noqa: BLE001 - a diagnostic must not abort
            print(f"  probe error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
