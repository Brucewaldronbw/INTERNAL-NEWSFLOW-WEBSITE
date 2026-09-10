"""China/Far East -> Europe container freight rates.

There is no single free, guaranteed-stable public API for container spot
rates, so this module tries several public providers in order and records
which one answered. Every successful reading is appended to
data/freight_history.json, so the historical graph deepens every day even
if a provider changes its markup and drops out.

Providers (all public pages/endpoints, no key):
  * Freightos FBX  - FBX11 (China/EA -> N. Europe), FBX13 (-> Med)
  * Drewry WCI     - composite + Shanghai->Rotterdam / Shanghai->Genoa
  * SSE / SCFI     - Shanghai Containerized Freight Index
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re

from .. import config, util

LOG = logging.getLogger("newsflow.freight")

FBX_CANDIDATES = [
    "https://fbx.freightos.com/api/index/{code}",
    "https://terminal.freightos.com/api/index/{code}",
    "https://fbx.freightos.com/api/fbx?index={code}",
]
DREWRY_URL = ("https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/"
              "world-container-index-assessed-by-drewry")
SCFI_URL = "https://en.sse.net.cn/indices/scfinew.jsp"

_MONEY = re.compile(r"\$?\s*([0-9][0-9,]{2,7}(?:\.[0-9]+)?)")


def _num(text: str) -> float | None:
    m = _MONEY.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ------------------------------------------------------------------- FBX ----
def _walk_for_series(node, out: dict[str, float]) -> None:
    """FBX payload shapes have moved around; harvest any {date, value} pairs."""
    if isinstance(node, dict):
        date = node.get("date") or node.get("day") or node.get("timestamp") or node.get("x")
        value = node.get("value") or node.get("price") or node.get("close") or node.get("y")
        if date is not None and isinstance(value, (int, float)):
            iso = _to_iso(date)
            if iso:
                out[iso] = float(value)
        for v in node.values():
            _walk_for_series(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_for_series(v, out)


def _to_iso(value) -> str | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return dt.datetime.utcfromtimestamp(seconds).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(value[:10], fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _fetch_fbx(code: str) -> tuple[dict[str, float], str | None]:
    for template in FBX_CANDIDATES:
        url = template.format(code=code)
        resp = util.get(url, retries=2)
        if resp is None:
            continue
        try:
            payload = resp.json()
        except ValueError:
            continue
        series: dict[str, float] = {}
        _walk_for_series(payload, series)
        if series:
            LOG.info("FBX %s: %s points from %s", code, len(series), url)
            return series, url
    return {}, None


# ---------------------------------------------------------------- Drewry ----
DREWRY_LANES = {
    "WCI_COMPOSITE": r"composite\s*index[^$]{0,120}?\$\s*([0-9,]+)",
    "WCI_SHA_RTM": r"Shanghai\s*(?:to|–|-|—)\s*Rotterdam[^$]{0,200}?\$\s*([0-9,]+)",
    "WCI_SHA_GOA": r"Shanghai\s*(?:to|–|-|—)\s*Genoa[^$]{0,200}?\$\s*([0-9,]+)",
}


def _fetch_drewry() -> tuple[dict[str, float], str | None]:
    resp = util.get(DREWRY_URL, retries=2)
    if resp is None:
        return {}, None
    text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"\s+", " ", text)
    found: dict[str, float] = {}
    for key, pattern in DREWRY_LANES.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                found[key] = float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    if found:
        LOG.info("Drewry WCI: %s", found)
    return found, DREWRY_URL if found else None


# ------------------------------------------------------------------ SCFI ----
def _fetch_scfi() -> tuple[float | None, str | None]:
    resp = util.get(SCFI_URL, retries=2)
    if resp is None:
        return None, None
    text = re.sub(r"<[^>]+>", " ", resp.text)
    m = re.search(r"Comprehensive Index[^0-9]{0,80}([0-9][0-9,.]{2,10})", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "")), SCFI_URL
        except ValueError:
            return None, None
    return None, None


# ------------------------------------------------------------------ main ----
def fetch() -> dict:
    store = util.load_history("freight_history")
    history: dict[str, dict[str, float]] = store.get("series", {})
    sources: dict[str, str] = store.get("sources", {})
    today = dt.date.today().isoformat()

    for code in ("FBX11", "FBX13"):
        series, src = _fetch_fbx(code)
        if series:
            history[code] = util.merge_series(history.get(code, {}), series)
            sources[code] = src or "Freightos FBX"

    drewry, src = _fetch_drewry()
    for key, value in drewry.items():
        history[key] = util.merge_series(history.get(key, {}), {today: value})
        sources[key] = src or DREWRY_URL

    scfi, src = _fetch_scfi()
    if scfi is not None:
        history["SCFI"] = util.merge_series(history.get("SCFI", {}), {today: scfi})
        sources["SCFI"] = src or SCFI_URL

    for key in list(history):
        history[key] = util.trim_series(history[key], config.FREIGHT_HISTORY_DAYS)

    util.save_history("freight_history", {"series": history, "sources": sources,
                                          "updated": today})

    lanes = [_build_lane(lane, history.get(lane["key"], {}), sources.get(lane["key"]))
             for lane in config.FREIGHT_LANES]
    available = [l for l in lanes if l["value"] is not None]
    return {
        "lanes": lanes,
        "available": available,
        "any_data": bool(available),
        "headline": available[0] if available else None,
    }


def _build_lane(lane: dict, series: dict[str, float], source: str | None) -> dict:
    points = util.series_points(series)
    if not points:
        return {**lane, "value": None, "as_of": None, "changes": {}, "points": [],
                "source": source, "unit": "USD / 40ft" if lane["key"] != "SCFI" else "index"}
    as_of, latest = points[-1]
    changes = {
        label: util.pct_change(latest, util.nearest_on_or_before(series, as_of - dt.timedelta(days=days)))
        for label, days in (("1w", 7), ("1m", 30), ("3m", 91), ("1y", 365))
    }
    return {
        **lane,
        "value": latest,
        "as_of": as_of.isoformat(),
        "changes": changes,
        "points": points,
        "observations": len(points),
        "source": source,
        "unit": "index" if lane["key"] == "SCFI" else "USD / 40ft container",
    }
