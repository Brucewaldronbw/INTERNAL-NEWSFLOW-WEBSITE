"""Probe every configured source and report which ones answered.

Run it in CI (or locally) to see at a glance whether a publisher has moved,
renamed or retired a feed:

    python scripts/source_report.py

Writes a markdown table to stdout and, when running in GitHub Actions, to the
job summary. Exit code is 0 unless a whole category is dead - a single dead
feed is expected from time to time and must not fail the build.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline import config, util                     # noqa: E402
from pipeline.fetchers import freight, fx, indicators, news  # noqa: E402

OK, DEAD = "ok", "no data"


def probe(name: str, category: str, fn) -> dict:
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - a probe must never abort the report
        return {"name": name, "category": category, "status": f"error: {exc}", "count": 0}
    count = len(result) if hasattr(result, "__len__") else int(bool(result))
    return {"name": name, "category": category,
            "status": OK if count else DEAD, "count": count}


def main() -> int:
    start = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    rows: list[dict] = []

    for pair in config.FX_PAIRS:
        rows.append(probe(f"ECB EXR {pair['key']}", "FX",
                          lambda c=pair["code"]: fx._from_ecb(c, start)))
        rows.append(probe(f"Frankfurter {pair['key']}", "FX",
                          lambda c=pair["code"]: fx._from_frankfurter(c, start)))

    for code in ("FBX11", "FBX13"):
        rows.append(probe(f"Freightos {code}", "Freight",
                          lambda c=code: freight._fetch_fbx(c)[0]))
    rows.append(probe("Drewry WCI", "Freight", lambda: freight._fetch_drewry()[0]))
    rows.append(probe("SSE / SCFI", "Freight", lambda: freight._fetch_scfi()[0]))

    for spec in config.MARKET_SERIES:
        rows.append(probe(f"Yahoo {spec['label']}", "Indicators",
                          lambda s=spec["yahoo"]: indicators._yahoo(s)))
        rows.append(probe(f"Stooq {spec['label']} (fallback)", "Indicators",
                          lambda s=spec["stooq"]: indicators._stooq(s)))
    for spec in config.ECB_YIELD_SERIES:
        rows.append(probe(f"ECB {spec['label']}", "Indicators",
                          lambda s=spec["sdmx"]: indicators._ecb_series(s)))
    for spec in config.BOE_SERIES:
        rows.append(probe(f"BoE {spec['label']}", "Indicators",
                          lambda s=spec["code"]: indicators._boe(s)))
    for spec in config.EUROSTAT_SERIES:
        geo = next(iter(spec["geos"]))
        rows.append(probe(f"Eurostat {spec['dataset']} ({geo})", "Indicators",
                          lambda s=spec, g=geo: indicators._eurostat(s["dataset"], s["params"], g)))
    for spec in config.ONS_SERIES:
        rows.append(probe(f"ONS {spec['key']}", "Indicators",
                          lambda s=spec: indicators._ons(s["path"])))

    for feed in config.OFFICIAL_FEEDS:
        rows.append(probe(f"{feed['country']} · {feed['source']}", "Official feeds",
                          lambda u=feed["url"], s=feed["source"], c=feed["country"]:
                          news._parse_feed(u, official=True, source=s, country=c)))

    for sweep in config.OFFICIAL_SITE_SWEEPS:
        query = f'site:{sweep["site"]} ({sweep["terms"]})'
        url = config.GOOGLE_NEWS.format(q=urllib.parse.quote(query))
        rows.append(probe(f"{sweep['country']} · {sweep['source']} (site sweep)",
                          "Official feeds",
                          lambda u=url, s=sweep["source"], c=sweep["country"]:
                          news._parse_feed(u, official=True, source=s, country=c)))

    for theme in config.NEWS_THEMES:
        query = theme["queries"][0]
        url = config.GOOGLE_NEWS.format(q=urllib.parse.quote(query))
        rows.append(probe(f"News sweep · {theme['key']}", "News sweeps",
                          lambda u=url, c=theme["country"]:
                          news._parse_feed(u, official=False, source=None, country=c)))

    lines = ["# Source health", "",
             f"Checked {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M UTC}", ""]
    failures_by_category: dict[str, list[str]] = {}
    for category in ("FX", "Freight", "Indicators", "Official feeds", "News sweeps"):
        subset = [r for r in rows if r["category"] == category]
        if not subset:
            continue
        alive = sum(1 for r in subset if r["status"] == OK)
        lines += [f"## {category} — {alive}/{len(subset)} responding", "",
                  "| Source | Status | Items |", "|---|---|---|"]
        for row in subset:
            mark = "✅" if row["status"] == OK else "⚠️"
            lines.append(f"| {row['name']} | {mark} {row['status']} | {row['count']} |")
            if row["status"] != OK:
                failures_by_category.setdefault(category, []).append(row["name"])
        lines.append("")
        if alive == 0:
            lines.append(f"**Every {category} source failed — this needs attention.**\n")

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        pathlib.Path(summary).write_text(report, encoding="utf-8")

    dead_categories = [c for c in ("FX", "Indicators", "Official feeds", "News sweeps")
                       if not any(r["status"] == OK for r in rows if r["category"] == c)]
    if dead_categories:
        print(f"::error::no source responded for: {', '.join(dead_categories)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
