"""Leading and lagging economic indicators.

  * Stooq    - daily market series (oil, copper, equities, bond yields) that
               act as fast-moving LEADING signals. Free CSV, no key.
  * Eurostat - monthly HICP inflation, unemployment and economic sentiment
               for IE / NL / BE / euro area. Free JSON-stat API, no key.
  * ONS      - the UK equivalents. Free JSON API, no key.

Each series is reduced to: latest value, change vs prior period, change vs a
year ago, and a direction call, so the brief can say what actually moved.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import re

from .. import config, util

LOG = logging.getLogger("newsflow.indicators")

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
EUROSTAT_URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                "{dataset}?format=JSON&lang=EN&lastTimePeriod=30")
ONS_URL = "https://api.ons.gov.uk/timeseries/{series}/dataset/{dataset}/data"

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


# ------------------------------------------------------------------ Stooq ----
def _stooq(symbol: str) -> dict[str, float]:
    resp = util.get(STOOQ_URL.format(symbol=symbol), retries=2)
    if resp is None or "Date" not in resp.text[:200]:
        return {}
    out: dict[str, float] = {}
    try:
        for row in csv.DictReader(io.StringIO(resp.text)):
            close = row.get("Close")
            date = row.get("Date")
            if date and close not in (None, "", "N/A"):
                out[date] = float(close)
    except (ValueError, csv.Error):
        return {}
    return dict(sorted(out.items())[-800:])


# --------------------------------------------------------------- Eurostat ----
def _eurostat(dataset: str, params: dict, geo: str) -> dict[str, float]:
    url = EUROSTAT_URL.format(dataset=dataset)
    query = dict(params)
    query["geo"] = geo
    resp = util.get(url, retries=2, params=query)
    if resp is None:
        return {}
    try:
        payload = resp.json()
    except ValueError:
        return {}
    return _parse_jsonstat(payload)


def _parse_jsonstat(payload: dict) -> dict[str, float]:
    """Flatten a JSON-stat 2.0 cube down to {period: value} for the time axis."""
    try:
        dim_ids = payload["id"]
        sizes = payload["size"]
        time_pos = dim_ids.index("time")
        time_index = payload["dimension"]["time"]["category"]["index"]
        values = payload["value"]
    except (KeyError, ValueError, TypeError):
        return {}

    # stride of the time dimension in the flattened value array
    stride = 1
    for size in sizes[time_pos + 1:]:
        stride *= size

    # everything except time is expected to be a single selection
    out: dict[str, float] = {}
    for period, idx in time_index.items():
        flat = idx * stride
        value = values.get(str(flat)) if isinstance(values, dict) else None
        if value is None and isinstance(values, list) and flat < len(values):
            value = values[flat]
        if isinstance(value, (int, float)):
            out[_normalise_period(period)] = float(value)
    return dict(sorted(out.items()))


def _normalise_period(period: str) -> str:
    """'2026-07' -> '2026-07-01'; '2026Q2' -> quarter start; '2026' -> year start."""
    period = period.strip()
    if re.fullmatch(r"\d{4}-\d{2}", period):
        return f"{period}-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
        return period
    m = re.fullmatch(r"(\d{4})[-]?Q([1-4])", period, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{(int(m.group(2)) - 1) * 3 + 1:02d}-01"
    if re.fullmatch(r"\d{4}", period):
        return f"{period}-01-01"
    return period


# -------------------------------------------------------------------- ONS ----
def _ons(series: str, dataset: str) -> dict[str, float]:
    resp = util.get(ONS_URL.format(series=series, dataset=dataset), retries=2)
    if resp is None:
        return {}
    try:
        payload = resp.json()
    except ValueError:
        return {}
    for bucket in ("months", "quarters", "years"):
        rows = payload.get(bucket) or []
        if not rows:
            continue
        out: dict[str, float] = {}
        for row in rows:
            iso = _ons_date(row, bucket)
            try:
                value = float(row.get("value"))
            except (TypeError, ValueError):
                continue
            if iso:
                out[iso] = value
        if out:
            return dict(sorted(out.items()))
    return {}


def _ons_date(row: dict, bucket: str) -> str | None:
    year = row.get("year")
    if not year:
        return None
    if bucket == "months":
        month = _MONTHS.get((row.get("month") or "")[:3].upper())
        return f"{year}-{month:02d}-01" if month else None
    if bucket == "quarters":
        q = (row.get("quarter") or "").upper().lstrip("Q")
        return f"{year}-{(int(q) - 1) * 3 + 1:02d}-01" if q.isdigit() else None
    return f"{year}-01-01"


# ------------------------------------------------------------------- main ----
def fetch() -> dict:
    history = util.load_history("indicator_history")
    series_out: list[dict] = []

    for spec in config.STOOQ_SERIES:
        data = _stooq(spec["symbol"])
        merged = util.merge_series(history.get(spec["key"], {}), data)
        merged = util.trim_series(merged, 365 * 3)
        history[spec["key"]] = merged
        series_out.append(_summarise(spec, merged, "daily", "Stooq"))

    for spec in config.EUROSTAT_SERIES:
        for geo, geo_label in spec["geos"].items():
            key = f"{spec['key']}_{geo}"
            data = _eurostat(spec["dataset"], spec["params"], geo)
            merged = util.merge_series(history.get(key, {}), data)
            history[key] = merged
            series_out.append(_summarise(
                {**spec, "key": key, "label": f"{geo_label} - {spec['label']}"},
                merged, "monthly", "Eurostat"))

    for spec in config.ONS_SERIES:
        data = _ons(spec["series"], spec["dataset"])
        merged = util.merge_series(history.get(spec["key"], {}), data)
        history[spec["key"]] = merged
        series_out.append(_summarise(spec, merged, "monthly", "ONS (UK)"))

    util.save_history("indicator_history", history)

    leading = [s for s in series_out if s["class"] == "leading"]
    lagging = [s for s in series_out if s["class"] == "lagging"]
    # Only percentage-change series belong on one shared axis. A rate series
    # (inflation, unemployment, a bond yield) moves in percentage POINTS, and
    # putting 0.10% -> 0.25% on the same bar chart as an equity index as
    # "+150%" would be nonsense.
    movers = sorted(
        [s for s in series_out if s["unit"] == "pct" and s["change_pct"] is not None],
        key=lambda s: -abs(s["change_pct"]),
    )[:6]
    rate_movers = sorted(
        [s for s in series_out if s["unit"] == "pp" and s["change"] is not None],
        key=lambda s: -abs(s["change"]),
    )[:6]
    return {
        "leading": leading,
        "lagging": lagging,
        "all": series_out,
        "movers": movers,
        "rate_movers": rate_movers,
        "available": sum(1 for s in series_out if s["value"] is not None),
        "total": len(series_out),
    }


def _display(delta: float | None, pct: float | None, unit: str) -> str:
    """Rates move in percentage points; levels and indices move in per cent."""
    if unit == "pp":
        return "n/a" if delta is None else f"{delta:+.2f} pp"
    return util.fmt_pct(pct)


def _summarise(spec: dict, series: dict[str, float], frequency: str, source: str) -> dict:
    points = util.series_points(series)
    unit = spec.get("unit", "pct")
    base = {
        "key": spec["key"], "label": spec["label"], "class": spec["class"],
        "why": spec.get("why", ""), "frequency": frequency, "source": source,
        "unit": unit,
        "value": None, "as_of": None, "prev": None, "change": None,
        "change_pct": None, "year_change": None, "year_change_pct": None,
        "change_display": "n/a", "year_change_display": "n/a",
        "points": [], "direction": "flat",
    }
    if not points:
        return base

    as_of, latest = points[-1]
    prev = points[-2][1] if len(points) > 1 else None
    year_ago = util.nearest_on_or_before(series, as_of - dt.timedelta(days=365))
    change_pct = util.pct_change(latest, prev)
    change = (latest - prev) if prev is not None else None
    year_change = (latest - year_ago) if year_ago is not None else None
    base.update({
        "value": latest,
        "as_of": as_of.isoformat(),
        "prev": prev,
        "change": change,
        "change_pct": change_pct,
        "year_change": year_change,
        "year_change_pct": util.pct_change(latest, year_ago),
        "change_display": _display(change, change_pct, unit),
        "year_change_display": _display(year_change, util.pct_change(latest, year_ago), unit),
        "points": points[-260:] if frequency == "daily" else points[-60:],
        "direction": "up" if (change_pct or 0) > 0.02 else "down" if (change_pct or 0) < -0.02 else "flat",
        "observations": len(points),
    })
    return base
