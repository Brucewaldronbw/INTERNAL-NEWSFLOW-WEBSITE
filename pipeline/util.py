"""Shared helpers: resilient HTTP, JSON history store, logging, formatting."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import pathlib
import time
from typing import Any

import requests

from . import config

LOG = logging.getLogger("newsflow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OFFLINE = os.environ.get("NEWSFLOW_OFFLINE", "").lower() in ("1", "true", "yes")

_SESSION: requests.Session | None = None


def session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "*/*"})
        _SESSION = s
    return _SESSION


def get(url: str, *, retries: int = 3, timeout: int | None = None, **kw) -> requests.Response | None:
    """GET with retry/backoff. Returns None instead of raising - a dead source
    must never take the whole brief down."""
    if OFFLINE:
        LOG.info("offline mode: skipping GET %s", url)
        return None
    timeout = timeout or config.HTTP_TIMEOUT
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            resp = session().get(url, timeout=timeout, **kw)
            if resp.status_code == 200:
                return resp
            LOG.warning("GET %s -> HTTP %s (attempt %s/%s)", url, resp.status_code, attempt, retries)
            if resp.status_code in (400, 401, 403, 404, 410):
                return None  # not going to get better by retrying
        except requests.RequestException as exc:
            LOG.warning("GET %s failed: %s (attempt %s/%s)", url, exc, attempt, retries)
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    return None


# ------------------------------------------------------------ history store --
def load_history(name: str) -> dict[str, Any]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        LOG.error("could not read history %s: %s", path, exc)
        return {}


def save_history(name: str, payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str))
    LOG.info("wrote %s (%s keys)", path.name, len(payload))


def merge_series(existing: dict[str, float], new: dict[str, float]) -> dict[str, float]:
    """Merge date->value maps, new values win, result sorted by date."""
    merged = dict(existing)
    merged.update({k: v for k, v in new.items() if v is not None})
    return dict(sorted(merged.items()))


def trim_series(series: dict[str, float], days: int) -> dict[str, float]:
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return {k: v for k, v in series.items() if k >= cutoff}


# ---------------------------------------------------------------- formatting --
def pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or not old:
        return None
    return (new - old) / abs(old) * 100.0


def fmt_num(v: float | None, dp: int = 4) -> str:
    if v is None:
        return "n/a"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:,.{dp}f}"


def fmt_pct(v: float | None, dp: int = 2) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.{dp}f}%"


def arrow(v: float | None) -> str:
    if v is None:
        return "-"
    if v > 0.02:
        return "▲"
    if v < -0.02:
        return "▼"
    return "▬"


def nearest_on_or_before(series: dict[str, float], target: dt.date) -> float | None:
    """Value at the last observation on or before `target` (markets close, gaps)."""
    key = target.isoformat()
    candidates = [d for d in series if d <= key]
    if not candidates:
        return None
    return series[max(candidates)]


def series_points(series: dict[str, float]) -> list[tuple[dt.date, float]]:
    out = []
    for k, v in sorted(series.items()):
        try:
            out.append((dt.date.fromisoformat(k), float(v)))
        except (ValueError, TypeError):
            continue
    return out
