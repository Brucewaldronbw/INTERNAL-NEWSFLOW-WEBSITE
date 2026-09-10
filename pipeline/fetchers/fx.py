"""EUR/CNY and EUR/GBP spot + history.

Source chain (first that answers wins, per pair):
  1. ECB Data Portal SDMX  - the official euro FX reference rate, no key
  2. Frankfurter.app       - ECB-derived mirror, no key
  3. open.er-api.com       - latest only, keeps today's card alive
Everything successfully fetched is merged into data/fx_history.json so the
chart keeps its depth even when a source has an outage.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import logging

from .. import config, util

LOG = logging.getLogger("newsflow.fx")

ECB_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.{code}.EUR.SP00.A"
           "?startPeriod={start}&format=csvdata")
FRANKFURTER_URL = "https://api.frankfurter.app/{start}..?from=EUR&to={code}"
ERAPI_URL = "https://open.er-api.com/v6/latest/EUR"


def _from_ecb(code: str, start: str) -> dict[str, float]:
    resp = util.get(ECB_URL.format(code=code, start=start))
    if resp is None:
        return {}
    out: dict[str, float] = {}
    try:
        for row in csv.DictReader(io.StringIO(resp.text)):
            period, value = row.get("TIME_PERIOD"), row.get("OBS_VALUE")
            if period and value not in (None, "", "NaN"):
                out[period] = float(value)
    except (ValueError, csv.Error) as exc:
        LOG.warning("ECB parse failed for %s: %s", code, exc)
        return {}
    LOG.info("ECB returned %s observations for EUR/%s", len(out), code)
    return out


def _from_frankfurter(code: str, start: str) -> dict[str, float]:
    resp = util.get(FRANKFURTER_URL.format(code=code, start=start))
    if resp is None:
        return {}
    try:
        rates = resp.json().get("rates", {})
    except ValueError:
        return {}
    out = {d: float(v[code]) for d, v in rates.items() if code in v}
    LOG.info("Frankfurter returned %s observations for EUR/%s", len(out), code)
    return out


def _from_erapi(codes: list[str]) -> dict[str, dict[str, float]]:
    resp = util.get(ERAPI_URL)
    if resp is None:
        return {}
    try:
        payload = resp.json()
        rates = payload.get("rates", {})
        day = dt.date.today().isoformat()
    except ValueError:
        return {}
    return {c: {day: float(rates[c])} for c in codes if c in rates}


def fetch() -> dict:
    """Return {'pairs': [...card data...], 'history': {key: {date: rate}}}."""
    history = util.load_history("fx_history")
    start = (dt.date.today() - dt.timedelta(days=config.FX_HISTORY_DAYS + 30)).isoformat()

    fresh: dict[str, dict[str, float]] = {}
    for pair in config.FX_PAIRS:
        code = pair["code"]
        series = _from_ecb(code, start) or _from_frankfurter(code, start)
        if series:
            fresh[pair["key"]] = series

    missing = [p["code"] for p in config.FX_PAIRS if p["key"] not in fresh]
    if missing:
        LOG.warning("falling back to open.er-api for %s", missing)
        latest = _from_erapi(missing)
        for pair in config.FX_PAIRS:
            if pair["code"] in latest:
                fresh[pair["key"]] = latest[pair["code"]]

    cards = []
    for pair in config.FX_PAIRS:
        key = pair["key"]
        merged = util.merge_series(history.get(key, {}), fresh.get(key, {}))
        merged = util.trim_series(merged, config.FX_HISTORY_DAYS)
        history[key] = merged
        cards.append(_build_card(pair, merged))

    util.save_history("fx_history", history)
    return {"pairs": cards, "history": history}


def _build_card(pair: dict, series: dict[str, float]) -> dict:
    points = util.series_points(series)
    if not points:
        return {**pair, "value": None, "as_of": None, "changes": {}, "stale": True,
                "high_52w": None, "low_52w": None, "points": []}

    as_of, latest = points[-1]
    today = dt.date.today()
    windows = {
        "1d": as_of - dt.timedelta(days=1),
        "1w": as_of - dt.timedelta(days=7),
        "1m": as_of - dt.timedelta(days=30),
        "3m": as_of - dt.timedelta(days=91),
        "1y": as_of - dt.timedelta(days=365),
    }
    changes = {
        label: util.pct_change(latest, util.nearest_on_or_before(series, when))
        for label, when in windows.items()
    }

    cutoff = (as_of - dt.timedelta(days=365)).isoformat()
    last_year = [v for d, v in series.items() if d >= cutoff]
    return {
        **pair,
        "value": latest,
        "as_of": as_of.isoformat(),
        "stale": (today - as_of).days > 5,
        "changes": changes,
        "high_52w": max(last_year) if last_year else None,
        "low_52w": min(last_year) if last_year else None,
        "points": points,
        "observations": len(points),
    }
