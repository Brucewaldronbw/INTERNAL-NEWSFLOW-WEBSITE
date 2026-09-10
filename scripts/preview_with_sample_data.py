"""Render the site + email from SYNTHETIC data, with no network access.

This exists so template and layout changes can be checked offline. The numbers
it produces are randomly generated and are NOT real market data - the preview
is written to a scratch directory, never over the published site.

    python scripts/preview_with_sample_data.py /tmp/preview
"""
from __future__ import annotations

import datetime as dt
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline import charts as charts_mod          # noqa: E402
from pipeline import render, util                  # noqa: E402
from pipeline.config import FREIGHT_LANES, FX_PAIRS  # noqa: E402
from pipeline.fetchers.fx import _build_card       # noqa: E402
from pipeline.fetchers.freight import _build_lane  # noqa: E402
from pipeline.fetchers.indicators import _summarise  # noqa: E402

random.seed(11)
TODAY = dt.date.today()


def walk(start: float, drift: float, vol: float, days: int) -> dict[str, float]:
    out, value = {}, start
    for i in range(days):
        value = max(0.001, value * (1 + random.gauss(drift, vol)))
        out[(TODAY - dt.timedelta(days=days - i)).isoformat()] = round(value, 6)
    return out


def monthly(start: float, drift: float, vol: float, months: int) -> dict[str, float]:
    out, value = {}, start
    for i in range(months):
        value = max(0.05, value + random.gauss(drift, vol))
        month = TODAY.replace(day=1) - dt.timedelta(days=30 * (months - i))
        out[month.replace(day=1).isoformat()] = round(value, 2)
    return out


def main(out_root: str) -> None:
    out = pathlib.Path(out_root)
    assets = out / "assets" / "charts"

    fx = {"pairs": [
        _build_card(FX_PAIRS[0], walk(7.55, 0.0001, 0.0035, 500)),
        _build_card(FX_PAIRS[1], walk(0.842, 0.0, 0.0028, 500)),
    ]}

    freight_raw = {
        "FBX11": walk(2150, 0.0006, 0.021, 420),
        "FBX13": walk(2880, 0.0004, 0.019, 420),
        "WCI_SHA_RTM": walk(2600, 0.0003, 0.020, 420),
        "WCI_SHA_GOA": walk(3100, 0.0003, 0.020, 420),
        "WCI_COMPOSITE": walk(2400, 0.0003, 0.018, 420),
        "SCFI": walk(1480, 0.0002, 0.022, 420),
    }
    lanes = [_build_lane(l, freight_raw.get(l["key"], {}), "sample data")
             for l in FREIGHT_LANES]
    available = [l for l in lanes if l["value"] is not None]
    freight = {"lanes": lanes, "available": available, "any_data": True,
               "headline": available[0]}

    specs = [
        ({"key": "brent", "label": "Brent crude (USD/bbl)", "class": "leading",
          "why": "Input cost & freight surcharge pressure"}, walk(78, 0.0, 0.014, 400), "daily", "Stooq"),
        ({"key": "stoxx", "label": "Euro Stoxx 50", "class": "leading",
          "why": "Equity market discounts future earnings"}, walk(4900, 0.0004, 0.009, 400), "daily", "Stooq"),
        ({"key": "de10y", "label": "German 10y Bund yield (%)", "class": "leading",
          "why": "Euro-area growth & inflation expectations", "unit": "pp"}, walk(2.4, 0.0, 0.012, 400), "daily", "Stooq"),
        ({"key": "esi_IE", "label": "Ireland - Economic sentiment", "class": "leading",
          "why": "Survey-based turning-point signal"}, monthly(99, 0.1, 1.4, 36), "monthly", "Eurostat"),
        ({"key": "hicp_IE", "label": "Ireland - HICP inflation, annual %", "class": "lagging",
          "why": "Feeds pay claims, indexation and pricing", "unit": "pp"}, monthly(2.4, -0.01, 0.22, 36), "monthly", "Eurostat"),
        ({"key": "hicp_NL", "label": "Netherlands - HICP inflation, annual %", "class": "lagging",
          "why": "Feeds pay claims, indexation and pricing", "unit": "pp"}, monthly(3.1, -0.01, 0.25, 36), "monthly", "Eurostat"),
        ({"key": "unemp_BE", "label": "Belgium - Unemployment rate, %", "class": "lagging",
          "why": "Labour cost & availability", "unit": "pp"}, monthly(5.6, 0.0, 0.09, 36), "monthly", "Eurostat"),
        ({"key": "uk_cpih", "label": "UK CPIH inflation, annual %", "class": "lagging",
          "why": "Drives UK pay settlements and thresholds", "unit": "pp"}, monthly(3.2, -0.02, 0.2, 36), "monthly", "ONS (UK)"),
    ]
    series = [_summarise(s, data, freq, src) for s, data, freq, src in specs]
    indicators = {
        "leading": [s for s in series if s["class"] == "leading"],
        "lagging": [s for s in series if s["class"] == "lagging"],
        "all": series,
        "movers": sorted([s for s in series
                          if s["unit"] == "pct" and s["change_pct"] is not None],
                         key=lambda s: -abs(s["change_pct"]))[:6],
        "rate_movers": sorted([s for s in series
                               if s["unit"] == "pp" and s["change"] is not None],
                              key=lambda s: -abs(s["change"]))[:6],
        "available": len(series), "total": len(series),
    }

    now = dt.datetime.now(dt.timezone.utc)
    def item(title, source, hours, official=False, url="https://example.invalid/sample"):
        when = now - dt.timedelta(hours=hours)
        return {"title": f"[SAMPLE] {title}", "url": url, "summary": "",
                "published": when.isoformat(),
                "published_display": when.strftime("%d %b %Y, %H:%M UTC"),
                "age_hours": hours, "source": source, "official": official,
                "country": "IE", "score": 20}

    news = {"themes": [
        {"key": "tax_ie", "title": "Ireland - Business tax, reliefs & Budget", "country": "IE",
         "widened": False, "count": 2,
         "items": [item("Revenue publishes updated R&D tax credit guidance", "Revenue.ie", 5, True),
                   item("Budget package to include capital allowances change", "Irish Times", 11)]},
        {"key": "employment_uk", "title": "UK - Employment law & employment taxes", "country": "UK",
         "widened": False, "count": 2,
         "items": [item("Employment Rights Bill: commencement dates confirmed", "GOV.UK", 8, True),
                   item("Employer NIC threshold change lands in April", "Financial Times", 20)]},
        {"key": "fire_safety_ma", "title": "Fire safety - M&A and acquisitions (UK & Europe)",
         "country": "EU", "widened": True, "count": 2,
         "items": [item("PE-backed group acquires regional fire protection installer", "Insider Media", 40),
                   item("Sprinkler maintenance business sold to European buyer", "Fire Safety Matters", 62)]},
    ], "top": [], "total_unique": 6, "total_shown": 6}

    chart_files = charts_mod.build_all(fx, freight, indicators, assets)
    view = render.build_view(fx, freight, indicators, news, chart_files)
    view["site_title"] += "  [SAMPLE DATA PREVIEW]"
    render.render_site(view, out)
    subject, html_body, text_body = render.render_email(view)
    (out / "email-preview.html").write_text(html_body, encoding="utf-8")
    (out / "email-preview.txt").write_text(text_body, encoding="utf-8")
    print("subject:", subject)
    print("wrote:", out / "index.html", "and", out / "email-preview.html")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/newsflow-preview")
