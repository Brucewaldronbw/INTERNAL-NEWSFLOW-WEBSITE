"""Static PNG charts for the email (email clients cannot run Chart.js).

Palette, mark specs and the one-axis rule follow the house data-viz method:
  * categorical hues assigned in fixed slot order, never cycled
  * one y-axis per chart - series with different units get their own chart
  * 2px lines, recessive gridlines, no chart junk
  * every series carries a direct end-label as well as a legend, which is the
    required relief for the light-surface contrast warning on slots 3-5
"""
from __future__ import annotations

import datetime as dt
import logging
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates          # noqa: E402
import matplotlib.pyplot as plt            # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

LOG = logging.getLogger("newsflow.charts")

# --- house tokens (light surface - email is rendered light) -------------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
UP_GOOD = "#006300"
DOWN = "#e34948"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": ["DejaVu Sans"],
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": AXIS,
})


def _style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=6)


def _date_axis(ax, span_days: int) -> None:
    if span_days > 400:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    elif span_days > 120:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))


def _save(fig, out_dir: pathlib.Path, name: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, dpi=144, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    LOG.info("chart written: %s", path.name)
    return path.name


# ------------------------------------------------------------------ FX ------
def fx_chart(pair: dict, out_dir: pathlib.Path) -> str | None:
    """Single-series line - the title names the series, so no legend box."""
    points = pair.get("points") or []
    if len(points) < 2:
        return None
    dates = [p[0] for p in points]
    values = [p[1] for p in points]
    span = (dates[-1] - dates[0]).days or 1

    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ax.plot(dates, values, color=SERIES[0], linewidth=2.0, solid_capstyle="round", zorder=3)
    ax.fill_between(dates, values, min(values), color=SERIES[0], alpha=0.07, zorder=2)

    # direct label on the latest value
    ax.scatter([dates[-1]], [values[-1]], s=42, color=SERIES[0],
               edgecolor=SURFACE, linewidth=2, zorder=4)
    ax.annotate(f"{values[-1]:,.4f}", (dates[-1], values[-1]),
                textcoords="offset points", xytext=(8, 6),
                fontsize=11, fontweight="bold", color=INK)

    _style(ax)
    _date_axis(ax, span)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.3f}"))
    span_label = (f"{span / 365:.1f} year" if span >= 365 else f"{max(span // 30, 1)} month")
    ax.set_title(f"{pair['label']}  -  {span_label} history "
                 f"(ECB reference rate, to {pair['as_of']})",
                 loc="left", fontsize=12, fontweight="bold", color=INK, pad=12)
    ax.margins(x=0.02)
    return _save(fig, out_dir, f"fx_{pair['key'].lower()}")


# -------------------------------------------------------------- freight -----
def freight_chart(lanes: list[dict], out_dir: pathlib.Path, *, name: str,
                  title: str, unit: str) -> str | None:
    plotted = [l for l in lanes if len(l.get("points") or []) >= 2]
    if not plotted:
        return None

    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    span = 1
    ends = []
    for i, lane in enumerate(plotted[:len(SERIES)]):
        points = lane["points"]
        dates = [p[0] for p in points]
        values = [p[1] for p in points]
        span = max(span, (dates[-1] - dates[0]).days or 1)
        colour = SERIES[i]
        ax.plot(dates, values, color=colour, linewidth=2.0,
                solid_capstyle="round", zorder=3, label=lane["label"])
        ax.scatter([dates[-1]], [values[-1]], s=36, color=colour,
                   edgecolor=SURFACE, linewidth=2, zorder=4)
        ends.append((dates[-1], values[-1]))

    _style(ax)
    _date_axis(ax, span)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel(unit, fontsize=9, color=INK_2)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=12)
    if len(plotted) > 1:
        ax.legend(frameon=False, fontsize=9, loc="upper left",
                  bbox_to_anchor=(0, -0.16), ncol=2, labelcolor=INK_2)
    ax.margins(x=0.04)
    _label_ends(fig, ax, ends)
    return _save(fig, out_dir, name)


def _label_ends(fig, ax, ends: list[tuple], min_gap_px: float = 13.0) -> None:
    """Direct end-labels are the relief for the light-surface contrast warning,
    so they have to stay readable - nudge them apart when lines finish close
    together instead of letting the numbers overprint each other."""
    if not ends:
        return
    fig.canvas.draw()  # transforms are only valid once the figure has a renderer
    placed = []
    for x, y in ends:
        _, py = ax.transData.transform((mdates.date2num(x), y))
        placed.append([py, 0.0, x, y])
    placed.sort(key=lambda row: row[0])
    for i in range(1, len(placed)):
        gap = (placed[i][0] + placed[i][1]) - (placed[i - 1][0] + placed[i - 1][1])
        if gap < min_gap_px:
            placed[i][1] += min_gap_px - gap
    for _, offset, x, y in placed:
        ax.annotate(f"{y:,.0f}", (x, y), textcoords="offset points",
                    xytext=(7, offset - 3), fontsize=9, fontweight="bold",
                    color=INK, annotation_clip=False, zorder=5)


# ------------------------------------------------------------ indicators ----
def movers_chart(movers: list[dict], out_dir: pathlib.Path) -> str | None:
    """Diverging bars: polarity (rose vs fell) is the encoded dimension.

    Only per-cent-change series reach here - rate series move in percentage
    points and would not share this axis honestly."""
    movers = [m for m in movers if m.get("change_pct") is not None][:8]
    if not movers:
        return None
    movers = list(reversed(movers))
    labels = [m["label"][:46] for m in movers]
    values = [m["change_pct"] for m in movers]
    colours = [SERIES[0] if v >= 0 else DOWN for v in values]

    fig, ax = plt.subplots(figsize=(8.4, 0.46 * len(movers) + 1.5))
    bars = ax.barh(labels, values, color=colours, height=0.62, zorder=3)
    for bar, value in zip(bars, values):
        offset = 6 if value >= 0 else -6
        ax.annotate(f"{value:+.2f}%", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    textcoords="offset points", xytext=(offset, 0),
                    va="center", ha="left" if value >= 0 else "right",
                    fontsize=9, fontweight="bold", color=INK)

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=6)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_title("Biggest market moves vs previous close",
                 loc="left", fontsize=12, fontweight="bold", color=INK, pad=12)
    limit = max(abs(v) for v in values) * 1.35 or 1
    ax.set_xlim(-limit, limit)
    return _save(fig, out_dir, "indicator_movers")


def build_all(fx: dict, freight: dict, indicators: dict, out_dir: pathlib.Path) -> dict[str, str]:
    charts: dict[str, str] = {}
    for pair in fx.get("pairs", []):
        name = fx_chart(pair, out_dir)
        if name:
            charts[f"fx_{pair['key']}"] = name

    usd_lanes = [l for l in freight.get("lanes", []) if l["key"] != "SCFI"]
    index_lanes = [l for l in freight.get("lanes", []) if l["key"] == "SCFI"]
    name = freight_chart(usd_lanes, out_dir, name="freight_usd",
                         title="China / Far East → Europe container spot rates",
                         unit="USD per 40ft container")
    if name:
        charts["freight_usd"] = name
    name = freight_chart(index_lanes, out_dir, name="freight_index",
                         title="Shanghai Containerized Freight Index (SCFI)",
                         unit="index level")
    if name:
        charts["freight_index"] = name

    name = movers_chart(indicators.get("movers", []), out_dir)
    if name:
        charts["movers"] = name
    return charts
