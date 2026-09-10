"""Orchestrator: collect -> chart -> render site -> email.

Typical use (from the GitHub Actions workflow):
    python -m pipeline.run                 # build site, email if 09:00 local & not sent
    python -m pipeline.run --force         # build and email regardless of clock
    python -m pipeline.run --no-email      # rebuild the site only
    python -m pipeline.run --offline       # no network, exercise the pipeline
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

from . import charts as charts_mod
from . import config, mailer, render, util
from .fetchers import freight as freight_mod
from .fetchers import fx as fx_mod
from .fetchers import indicators as indicators_mod
from .fetchers import news as news_mod

LOG = logging.getLogger("newsflow")

ROOT = util.ROOT
ASSET_DIR = ROOT / "assets" / "charts"
STATE_PATH = util.DATA_DIR / "state.json"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict) -> None:
    util.DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1, sort_keys=True))


def should_send(state: dict, *, force: bool) -> tuple[bool, str]:
    """The workflow fires twice (08:00 and 09:00 UTC) so that 09:00 local is hit
    in both GMT and IST, and GitHub's scheduler is allowed to run late. This
    guard turns those runs into exactly one send per day."""
    if force:
        return True, "forced"
    now_local = dt.datetime.now(ZoneInfo(config.LOCAL_TZ))
    today = now_local.date().isoformat()
    if state.get("last_sent_date") == today:
        return False, f"already sent today ({today})"
    if now_local.hour < config.SEND_HOUR_LOCAL:
        return False, (f"local time {now_local:%H:%M} {config.LOCAL_TZ} is before "
                       f"{config.SEND_HOUR_LOCAL:02d}:00")
    return True, f"due at {now_local:%H:%M} {config.LOCAL_TZ}"


def collect() -> dict:
    LOG.info("collecting FX ...")
    fx = fx_mod.fetch()
    LOG.info("collecting freight ...")
    freight = freight_mod.fetch()
    LOG.info("collecting economic indicators ...")
    indicators = indicators_mod.fetch()
    LOG.info("collecting newsflow ...")
    news = news_mod.fetch()
    return {"fx": fx, "freight": freight, "indicators": indicators, "news": news}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and send the morning newsflow brief.")
    parser.add_argument("--force", action="store_true", help="send regardless of local time")
    parser.add_argument("--no-email", action="store_true", help="build the site only")
    parser.add_argument("--offline", action="store_true", help="skip all network calls")
    parser.add_argument("--to", help="override recipients (comma separated)")
    parser.add_argument("--out", default=str(ROOT), help="site output directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.offline:
        os.environ["NEWSFLOW_OFFLINE"] = "1"
        util.OFFLINE = True
    _setup_logging(args.verbose)
    LOG.info("newsflow run starting (offline=%s)", util.OFFLINE)

    data = collect()
    chart_files = charts_mod.build_all(data["fx"], data["freight"], data["indicators"], ASSET_DIR)
    view = render.build_view(data["fx"], data["freight"], data["indicators"],
                             data["news"], chart_files)

    site_path = render.render_site(view, pathlib.Path(args.out))
    LOG.info("site built at %s", site_path)

    state = _load_state()
    state["last_run_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    state["last_run_sources"] = {
        "fx_pairs_with_data": sum(1 for p in data["fx"]["pairs"] if p["value"] is not None),
        "freight_series_with_data": len(data["freight"]["available"]),
        "indicators_with_data": data["indicators"]["available"],
        "news_items": data["news"]["total_shown"],
    }

    if args.no_email:
        LOG.info("--no-email: skipping delivery")
        _save_state(state)
        return 0

    send, reason = should_send(state, force=args.force)
    if not send:
        LOG.info("not sending: %s", reason)
        _save_state(state)
        return 0
    LOG.info("sending: %s", reason)

    subject, html_body, text_body = render.render_email(view)
    images = {key: ASSET_DIR / name for key, name in chart_files.items()}
    recipients = [e.strip() for e in args.to.split(",")] if args.to else config.RECIPIENTS

    try:
        transport = mailer.send(subject, html_body, text_body, images, recipients)
    except mailer.MailNotConfigured as exc:
        LOG.error("EMAIL NOT SENT - %s", exc)
        _save_state(state)
        return 2
    except Exception as exc:  # noqa: BLE001 - surface any transport error to CI
        LOG.exception("EMAIL FAILED: %s", exc)
        _save_state(state)
        return 3

    state["last_sent_date"] = dt.datetime.now(ZoneInfo(config.LOCAL_TZ)).date().isoformat()
    state["last_sent_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    state["last_transport"] = transport
    _save_state(state)
    LOG.info("brief delivered to %s via %s", ", ".join(recipients), transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
