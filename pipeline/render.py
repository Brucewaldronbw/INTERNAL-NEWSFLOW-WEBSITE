"""Turn fetched data into the view model, the website and the email body."""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import config, util

LOG = logging.getLogger("newsflow.render")

ROOT = util.ROOT
TEMPLATE_DIR = ROOT / "templates"
SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

WINDOW_LABELS = [("1d", "1 day"), ("1w", "1 week"), ("1m", "1 month"),
                 ("3m", "3 months"), ("1y", "1 year")]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True, lstrip_blocks=True,
    )


def _cls(value: float | None, *, higher_is_good: bool = True) -> str:
    if value is None or abs(value) < 0.02:
        return "flat"
    good = value > 0 if higher_is_good else value < 0
    return "up" if good else "down"


def _colour(cls: str) -> str:
    return {"up": "#006300", "down": "#e34948"}.get(cls, "#898781")


def _signal(series: dict) -> float | None:
    """The number whose sign and size we judge a series by: percentage points
    for a rate, per cent for a level."""
    return series["change"] if series.get("unit") == "pp" else series["change_pct"]


def _cell(value: float | None) -> dict:
    cls = "flat" if value is None or abs(value) < 0.02 else ("up" if value > 0 else "down")
    return {"text": util.fmt_pct(value), "cls": cls, "colour": _colour(cls)}


# --------------------------------------------------------------- view model --
def build_view(fx: dict, freight: dict, indicators: dict, news: dict,
               charts: dict[str, str]) -> dict:
    now = dt.datetime.now(dt.timezone.utc)

    # ---- FX view
    fx_pairs = []
    for pair in fx.get("pairs", []):
        change_row = [(label, _cell(pair["changes"].get(key)))
                      for key, label in WINDOW_LABELS]
        fx_pairs.append({
            **pair,
            "value_fmt": util.fmt_num(pair["value"], 4),
            "high_52w": util.fmt_num(pair["high_52w"], 4),
            "low_52w": util.fmt_num(pair["low_52w"], 4),
            "change_row": change_row,
        })

    # ---- freight view
    freight_rows = []
    colour_index = 0
    for lane in freight.get("lanes", []):
        has_data = lane["value"] is not None
        colour = None
        if has_data and lane["key"] != "SCFI":
            colour = SERIES_LIGHT[colour_index % len(SERIES_LIGHT)]
            colour_index += 1
        cells_full = [_cell(lane["changes"].get(k)) for k in ("1w", "1m", "3m", "1y")]
        freight_rows.append({
            "label": lane["label"],
            "value": (f"${lane['value']:,.0f}" if has_data and lane["key"] != "SCFI"
                      else (f"{lane['value']:,.0f}" if has_data else "—")),
            "as_of": lane["as_of"],
            "colour": colour,
            "cells": [cells_full[0], cells_full[1], cells_full[3]],  # 1w, 1m, 1y
            "cells_full": cells_full,
        })

    # ---- indicators view
    indicator_groups = []
    for key, title, blurb in (
        ("leading", "Leading indicators",
         "Fast-moving signals that tend to turn before activity does."),
        ("lagging", "Lagging indicators",
         "Confirm what has already happened - inflation, unemployment, output."),
    ):
        rows = []
        for series in indicators.get(key, []):
            if series["value"] is None:
                continue
            # For inflation and unemployment, a rise is not good news.
            higher_good = not any(w in series["label"].lower()
                                  for w in ("inflation", "unemployment"))
            signal = _signal(series)
            year_signal = (series["year_change"] if series["unit"] == "pp"
                           else series["year_change_pct"])
            cls = _cls(signal, higher_is_good=higher_good)
            year_cls = _cls(year_signal, higher_is_good=higher_good)
            rows.append({
                "label": series["label"],
                "why": series["why"],
                "value": util.fmt_num(series["value"], 2),
                "change": series["change_display"],
                "year_change": series["year_change_display"],
                "arrow": util.arrow(signal),
                "cls": cls, "year_cls": year_cls, "colour": _colour(cls),
                "as_of": series["as_of"], "source": series["source"],
            })
        if rows:
            indicator_groups.append({"title": title, "blurb": blurb, "rows": rows})

    glance = _build_glance(fx_pairs, freight, indicators)
    summary = _build_summary(fx_pairs, freight, indicators, news)

    degraded = _degraded_note(fx_pairs, freight, indicators, news)

    return {
        "site_title": config.SITE_TITLE,
        "site_tagline": config.SITE_TAGLINE,
        "site_url": config.SITE_URL,
        "date_long": dt.date.today().strftime("%A %-d %B %Y"),
        "generated_at": now.strftime("%d %b %Y %H:%M UTC"),
        "glance": glance,
        "summary_lines": summary,
        "fx": {"pairs": fx_pairs},
        "freight": {
            "any_data": freight.get("any_data", False),
            "rows": freight_rows,
            "charts": _freight_chart_specs(freight),
        },
        "indicator_groups": indicator_groups,
        "news": news,
        "charts": charts,
        "degraded": degraded,
        "sources": ["ECB reference rates", "Freightos FBX", "Drewry WCI", "SCFI",
                    "Eurostat", "ONS (UK)", "Stooq", "GOV.UK", "Revenue.ie",
                    "Rijksoverheid", "Belgium FPS Finance", "Google News"],
        "source_note": "ECB, Eurostat, ONS, Stooq, Freightos/Drewry/SCFI, "
                       "government press feeds and Google News",
    }


def _freight_chart_specs(freight: dict) -> list[dict]:
    usd = [l for l in freight.get("lanes", []) if l["key"] != "SCFI" and l["points"]]
    idx = [l for l in freight.get("lanes", []) if l["key"] == "SCFI" and l["points"]]
    specs = []
    if usd:
        specs.append({"id": "freight-usd", "title": "China / Far East → Europe spot rates",
                      "unit": "USD per 40ft container", "series": usd})
    if idx:
        specs.append({"id": "freight-index", "title": "Shanghai Containerized Freight Index",
                      "unit": "Index level", "series": idx})
    return specs


def _build_glance(fx_pairs: list[dict], freight: dict, indicators: dict) -> list[dict]:
    glance = []
    for pair in fx_pairs:
        change = pair["changes"].get("1w")
        cls = "flat" if change is None or abs(change) < 0.02 else ("up" if change > 0 else "down")
        glance.append({
            "label": pair["label"], "value": pair["value_fmt"],
            "change": f"{util.fmt_pct(change)} 1w", "arrow": util.arrow(change),
            "cls": cls, "colour": _colour(cls),
            "note": f"as at {pair['as_of']}" if pair["as_of"] else "no data yet",
        })

    headline = freight.get("headline")
    if headline:
        change = headline["changes"].get("1w")
        cls = "flat" if change is None or abs(change) < 0.02 else ("up" if change > 0 else "down")
        glance.append({
            "label": headline["label"],
            "value": f"${headline['value']:,.0f}" if headline["key"] != "SCFI" else f"{headline['value']:,.0f}",
            "change": f"{util.fmt_pct(change)} 1w", "arrow": util.arrow(change),
            "cls": cls, "colour": _colour(cls),
            "note": f"{headline['unit']} · {headline['as_of']}",
        })
    else:
        glance.append({"label": "China → Europe freight", "value": "—",
                       "change": "no reading", "arrow": "-", "cls": "flat",
                       "colour": "#898781", "note": "index sources unavailable this run"})

    spotlight = (indicators.get("movers", []) + indicators.get("rate_movers", []))[:3]
    for series in spotlight:
        higher_good = not any(w in series["label"].lower() for w in ("inflation", "unemployment"))
        signal = _signal(series)
        cls = _cls(signal, higher_is_good=higher_good)
        glance.append({
            "label": series["label"], "value": util.fmt_num(series["value"], 2),
            "change": f"{series['change_display']} vs prior",
            "arrow": util.arrow(signal), "cls": cls, "colour": _colour(cls),
            "note": f"{series['source']} · {series['as_of']}",
        })
    return glance


def _build_summary(fx_pairs: list[dict], freight: dict, indicators: dict,
                   news: dict) -> list[str]:
    lines = []
    for pair in fx_pairs:
        change = pair["changes"].get("1w")
        if change is None:
            continue
        direction = "stronger euro" if change > 0 else "weaker euro"
        lines.append(
            f"{pair['label']} at {pair['value_fmt']}, {util.fmt_pct(change)} over the week "
            f"({direction} against the {'renminbi' if pair['code'] == 'CNY' else 'pound'})."
        )

    headline = freight.get("headline")
    if headline and headline["changes"].get("1m") is not None:
        change = headline["changes"]["1m"]
        lines.append(
            f"{headline['label']} at {headline['value']:,.0f}, "
            f"{util.fmt_pct(change)} over the month."
        )

    for label, bucket in (("market", "movers"), ("rate/indicator", "rate_movers")):
        series = indicators.get(bucket, [])
        if series:
            top = series[0]
            lines.append(
                f"Largest {label} move: {top['label']} {top['change_display']} "
                f"vs the previous reading ({top['as_of']})."
            )

    official = [i for t in news.get("themes", []) for i in t["items"] if i.get("official")]
    if official:
        lines.append(f"{len(official)} official government/regulator releases picked up overnight.")
    return lines


def _degraded_note(fx_pairs, freight, indicators, news) -> str:
    problems = []
    if any(p["value"] is None for p in fx_pairs):
        problems.append("one or more FX sources")
    if not freight.get("any_data"):
        problems.append("all freight indices")
    if indicators.get("available", 0) == 0:
        problems.append("economic indicator feeds")
    if news.get("total_shown", 0) == 0:
        problems.append("news feeds")
    if not problems:
        return ""
    return ("Some sources did not respond on this run: " + ", ".join(problems) +
            ". Everything else below is current; the collector retries automatically "
            "on the next run.")


# ----------------------------------------------------------------- renderers --
def _chart_payload(view: dict) -> str:
    charts = []
    for pair in view["fx"]["pairs"]:
        if not pair["points"]:
            continue
        charts.append({
            "canvas": f"chart-fx-{pair['key']}", "prefix": "", "dp": 4, "unit": "month",
            "series": [{"label": pair["label"],
                        "points": [[d.isoformat(), round(v, 6)] for d, v in pair["points"]]}],
        })
    for spec in view["freight"]["charts"]:
        charts.append({
            "canvas": f"chart-{spec['id']}",
            "prefix": "$" if spec["id"] == "freight-usd" else "",
            "dp": 0, "unit": "month",
            "series": [{"label": lane["label"],
                        "points": [[d.isoformat(), round(v, 2)] for d, v in lane["points"]]}
                       for lane in spec["series"][:6]],
        })
    return json.dumps({"charts": charts}, separators=(",", ":"))


def render_site(view: dict, out_dir: pathlib.Path) -> pathlib.Path:
    # The payload sits in a <script type="application/json"> block, so the only
    # sequence that can break out is "</". Escape that, then mark it safe -
    # autoescaping would otherwise turn every quote into &quot; and the JSON
    # would not parse in the browser.
    payload = Markup(_chart_payload(view).replace("</", "<\\/"))
    html_out = _env().get_template("site.html.j2").render(**view, chart_data=payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(html_out, encoding="utf-8")
    LOG.info("site written: %s (%.0f KB)", path, path.stat().st_size / 1024)
    return path


def render_email(view: dict) -> tuple[str, str, str]:
    subject = _subject(view)
    body = _env().get_template("email.html.j2").render(
        **view, subject=subject, preheader=_preheader(view))
    return subject, body, _plain_text(view, subject)


def _subject(view: dict) -> str:
    bits = []
    for pair in view["fx"]["pairs"]:
        change = pair["changes"].get("1d") or pair["changes"].get("1w")
        if pair["value"] is not None:
            bits.append(f"{pair['key'][3:]} {pair['value_fmt']} {util.arrow(change)}")
    headline = view["freight"]["rows"][0] if view["freight"]["rows"] else None
    if headline and headline["value"] != "—":
        bits.append(f"Freight {headline['value']}")
    tail = " · ".join(bits) if bits else "daily brief"
    return f"Morning Newsflow — {dt.date.today().strftime('%d %b %Y')} — {tail}"


def _preheader(view: dict) -> str:
    return " ".join(view["summary_lines"])[:160] or "FX, freight, tax & policy newsflow."


def _plain_text(view: dict, subject: str) -> str:
    lines = [subject, "=" * min(len(subject), 78), ""]
    if view["summary_lines"]:
        lines.append("WHAT MOVED")
        lines += [f"  - {html.unescape(s)}" for s in view["summary_lines"]]
        lines.append("")
    lines.append("FX")
    for pair in view["fx"]["pairs"]:
        changes = ", ".join(f"{label} {value['text']}" for label, value in pair["change_row"])
        lines.append(f"  {pair['label']}: {pair['value_fmt']} ({changes})")
    lines.append("")
    lines.append("CHINA -> EUROPE FREIGHT")
    for row in view["freight"]["rows"]:
        lines.append(f"  {row['label']}: {row['value']}")
    lines.append("")
    for group in view["indicator_groups"]:
        lines.append(group["title"].upper())
        for row in group["rows"]:
            lines.append(f"  {row['label']}: {row['value']} ({row['change']} vs prior)")
        lines.append("")
    lines.append("NEWSFLOW")
    for theme in view["news"]["themes"]:
        if not theme["items"]:
            continue
        lines.append(f"  {theme['title']}")
        for item in theme["items"]:
            lines.append(f"    - {html.unescape(item['title'])} [{item['source']}]")
            lines.append(f"      {item['url']}")
        lines.append("")
    if view["site_url"]:
        lines.append(f"Dashboard: {view['site_url']}")
    lines.append(f"Generated {view['generated_at']}. Public data, internal information only.")
    return "\n".join(lines)
