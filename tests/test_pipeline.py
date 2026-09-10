"""Unit tests for the parts of the pipeline where a silent bug would be
invisible in the output: the send guard, the data parsers, and the
unit-correct handling of rates vs levels."""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault("NEWSFLOW_OFFLINE", "1")

from pipeline import config, render, util                    # noqa: E402
from pipeline.fetchers.freight import _build_lane, _to_iso, _walk_for_series  # noqa: E402
from pipeline.fetchers.fx import _build_card                 # noqa: E402
from pipeline.fetchers.indicators import (                   # noqa: E402
    _display, _normalise_period, _ons_date, _parse_jsonstat, _summarise)
from pipeline.fetchers.news import _norm_key, _score, _split_google_title  # noqa: E402
from pipeline.run import should_send                         # noqa: E402


def days_ago(n: int) -> str:
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


class SendGuardTests(unittest.TestCase):
    """Three cron runs a day must produce exactly one email."""

    def _at(self, hour: int, state: dict):
        local = dt.datetime(2026, 6, 15, hour, 0, tzinfo=dt.timezone.utc)
        with mock.patch("pipeline.run.dt") as fake:
            fake.datetime.now.return_value = local
            fake.timezone = dt.timezone
            return should_send(state, force=False)

    def test_blocked_before_nine(self):
        send, reason = self._at(7, {})
        self.assertFalse(send)
        self.assertIn("before", reason)

    def test_sends_at_nine(self):
        self.assertTrue(self._at(9, {})[0])

    def test_sends_when_the_schedule_runs_late(self):
        self.assertTrue(self._at(11, {})[0])

    def test_only_once_per_day(self):
        state = {"last_sent_date": "2026-06-15"}
        send, reason = self._at(10, state)
        self.assertFalse(send)
        self.assertIn("already sent", reason)

    def test_force_overrides_everything(self):
        self.assertTrue(should_send({"last_sent_date": dt.date.today().isoformat()},
                                    force=True)[0])


class JsonStatTests(unittest.TestCase):
    def test_single_selection_cube(self):
        cube = {"id": ["geo", "time"], "size": [1, 3],
                "dimension": {"time": {"category": {"index": {
                    "2026-05": 0, "2026-06": 1, "2026-07": 2}}}},
                "value": {"0": 1.5, "1": 1.8, "2": 2.1}}
        self.assertEqual(_parse_jsonstat(cube),
                         {"2026-05-01": 1.5, "2026-06-01": 1.8, "2026-07-01": 2.1})

    def test_time_is_not_the_last_dimension(self):
        # size [2, 1] -> the time axis has a stride of 1 here, but the parser
        # must compute it rather than assume time comes last.
        cube = {"id": ["time", "unit"], "size": [2, 1],
                "dimension": {"time": {"category": {"index": {"2026-06": 0, "2026-07": 1}}}},
                "value": {"0": 4.0, "1": 4.4}}
        self.assertEqual(_parse_jsonstat(cube), {"2026-06-01": 4.0, "2026-07-01": 4.4})

    def test_missing_observations_are_dropped(self):
        cube = {"id": ["time"], "size": [3],
                "dimension": {"time": {"category": {"index": {
                    "2026-05": 0, "2026-06": 1, "2026-07": 2}}}},
                "value": {"0": 1.0, "2": 3.0}}
        self.assertEqual(_parse_jsonstat(cube), {"2026-05-01": 1.0, "2026-07-01": 3.0})

    def test_rubbish_returns_empty_not_an_exception(self):
        self.assertEqual(_parse_jsonstat({"nonsense": True}), {})

    def test_period_normalisation(self):
        self.assertEqual(_normalise_period("2026Q3"), "2026-07-01")
        self.assertEqual(_normalise_period("2026-07"), "2026-07-01")
        self.assertEqual(_normalise_period("2026"), "2026-01-01")

    def test_ons_dates(self):
        self.assertEqual(_ons_date({"year": "2026", "month": "August"}, "months"), "2026-08-01")
        self.assertEqual(_ons_date({"year": "2026", "quarter": "Q2"}, "quarters"), "2026-04-01")
        self.assertIsNone(_ons_date({"month": "August"}, "months"))


class UnitTests(unittest.TestCase):
    """A rate moves in percentage points; a level moves in per cent."""

    def test_rate_change_is_shown_in_points(self):
        self.assertEqual(_display(0.15, 150.0, "pp"), "+0.15 pp")

    def test_level_change_is_shown_in_percent(self):
        self.assertEqual(_display(75.0, 1.5, "pct"), "+1.50%")

    def test_summarise_labels_a_rate_series_in_points(self):
        series = {"2026-06-01": 0.10, "2026-07-01": 0.25}
        out = _summarise({"key": "hicp", "label": "HICP", "class": "lagging",
                          "why": "", "unit": "pp"}, series, "monthly", "Eurostat")
        self.assertEqual(out["change_display"], "+0.15 pp")
        self.assertAlmostEqual(out["change"], 0.15)

    def test_render_signal_uses_points_for_a_rate(self):
        self.assertEqual(render._signal({"unit": "pp", "change": 0.2, "change_pct": 999}), 0.2)
        self.assertEqual(render._signal({"unit": "pct", "change": 0.2, "change_pct": 1.5}), 1.5)


class FxCardTests(unittest.TestCase):
    def setUp(self):
        self.series = {days_ago(n): 8.0 + n * 0.01 for n in range(0, 400)}

    def test_latest_observation_wins(self):
        card = _build_card(config.FX_PAIRS[0], self.series)
        self.assertEqual(card["value"], 8.0)
        self.assertEqual(card["as_of"], days_ago(0))

    def test_change_windows_are_populated(self):
        card = _build_card(config.FX_PAIRS[0], self.series)
        for window in ("1d", "1w", "1m", "3m", "1y"):
            self.assertIsNotNone(card["changes"][window], window)
        # the series falls as it approaches today, so every change is negative
        self.assertLess(card["changes"]["1m"], 0)

    def test_gap_in_the_series_falls_back_to_the_prior_observation(self):
        sparse = {days_ago(0): 8.0, days_ago(40): 9.0}
        card = _build_card(config.FX_PAIRS[0], sparse)
        self.assertIsNotNone(card["changes"]["1m"])  # resolves to the 40-day-old point

    def test_empty_series_is_marked_stale_not_crashed(self):
        card = _build_card(config.FX_PAIRS[0], {})
        self.assertIsNone(card["value"])
        self.assertTrue(card["stale"])


class FreightTests(unittest.TestCase):
    def test_harvests_date_value_pairs_from_a_nested_payload(self):
        payload = {"data": {"series": [{"date": "2026-07-01", "value": 2100},
                                       {"date": "2026-07-08", "value": 2250}]}}
        out: dict[str, float] = {}
        _walk_for_series(payload, out)
        self.assertEqual(out, {"2026-07-01": 2100.0, "2026-07-08": 2250.0})

    def test_epoch_milliseconds_are_understood(self):
        self.assertEqual(_to_iso(1750000000000), "2025-06-15")

    def test_lane_without_data_renders_a_dash_not_an_error(self):
        lane = _build_lane(config.FREIGHT_LANES[0], {}, None)
        self.assertIsNone(lane["value"])
        self.assertEqual(lane["points"], [])


class NewsTests(unittest.TestCase):
    def test_publisher_is_split_off_a_google_news_title(self):
        title, publisher = _split_google_title("HMRC updates R&D guidance - Accountancy Daily")
        self.assertEqual(title, "HMRC updates R&D guidance")
        self.assertEqual(publisher, "Accountancy Daily")

    def test_title_without_a_publisher_is_left_alone(self):
        title, publisher = _split_google_title("Budget 2027 in full")
        self.assertEqual(title, "Budget 2027 in full")
        self.assertIsNone(publisher)

    def test_official_sources_outrank_a_sweeper_hit(self):
        official = {"title": "Corporation tax relief change", "summary": "",
                    "official": True, "age_hours": 5}
        sweeper = {"title": "Corporation tax relief change", "summary": "",
                   "official": False, "age_hours": 5}
        self.assertGreater(_score(official), _score(sweeper))

    def test_stale_items_score_below_fresh_ones(self):
        fresh = {"title": "Tax relief", "summary": "", "official": False, "age_hours": 6}
        stale = {"title": "Tax relief", "summary": "", "official": False, "age_hours": 24 * 30}
        self.assertGreater(_score(fresh), _score(stale))

    def test_dedupe_key_ignores_punctuation_and_case(self):
        self.assertEqual(_norm_key("Budget 2027: what it means!"),
                         _norm_key("budget 2027 - What it means"))


class RenderTests(unittest.TestCase):
    def _view(self):
        fx = {"pairs": [_build_card(p, {days_ago(n): 8.0 + n * 0.01 for n in range(200)})
                        for p in config.FX_PAIRS]}
        lanes = [_build_lane(l, {days_ago(n): 2000.0 + n for n in range(200)}, "test")
                 for l in config.FREIGHT_LANES]
        freight = {"lanes": lanes, "available": lanes, "any_data": True, "headline": lanes[0]}
        indicators = {"leading": [], "lagging": [], "all": [], "movers": [],
                      "rate_movers": [], "available": 0, "total": 0}
        news = {"themes": [], "top": [], "total_unique": 0, "total_shown": 0}
        return render.build_view(fx, freight, indicators, news, {})

    def test_email_freight_columns_match_their_headers(self):
        """The email table is headed Latest / 1w / 1m / 1y - the cells must be
        those windows, not 1w / 1m / 3m."""
        view = self._view()
        row = view["freight"]["rows"][0]
        full = [c["text"] for c in row["cells_full"]]     # 1w, 1m, 3m, 1y
        shown = [c["text"] for c in row["cells"]]         # what the email prints
        self.assertEqual(shown, [full[0], full[1], full[3]])
        self.assertEqual(len(shown), 3)

    def test_site_renders_with_no_data_at_all(self):
        empty_fx = {"pairs": [_build_card(p, {}) for p in config.FX_PAIRS]}
        empty_freight = {"lanes": [_build_lane(l, {}, None) for l in config.FREIGHT_LANES],
                         "available": [], "any_data": False, "headline": None}
        view = render.build_view(
            empty_fx, empty_freight,
            {"leading": [], "lagging": [], "all": [], "movers": [], "rate_movers": [],
             "available": 0, "total": 0},
            {"themes": [], "top": [], "total_unique": 0, "total_shown": 0}, {})
        self.assertTrue(view["degraded"])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = render.render_site(view, pathlib.Path(tmp))
            self.assertIn("Moyne Roberts", path.read_text())

    def test_embedded_chart_json_is_parseable_not_html_escaped(self):
        import json
        view = self._view()
        payload = render._chart_payload(view)
        parsed = json.loads(payload)
        self.assertTrue(parsed["charts"])
        self.assertNotIn("&quot;", payload)

    def test_email_body_and_plain_text_are_produced(self):
        subject, html_body, text_body = render.render_email(self._view())
        self.assertIn("Morning Newsflow", subject)
        self.assertIn("Moyne Roberts", html_body)
        self.assertIn("CHINA -> EUROPE FREIGHT", text_body)


class MailerTests(unittest.TestCase):
    def test_cid_placeholders_are_replaced_with_real_message_ids(self):
        import tempfile
        from pipeline import mailer
        with tempfile.TemporaryDirectory() as tmp:
            png = pathlib.Path(tmp) / "chart.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
            msg, cids = mailer.build_message(
                "Subject", '<img src="cid:movers">', "text",
                {"movers": png}, ["a@example.com"], "from@example.com")
            self.assertIn("movers", cids)
            body = msg.get_payload()[-1].get_payload()[0].get_payload()
            self.assertIn(f"cid:{cids['movers']}", body)
            self.assertNotIn("cid:movers", body)

    def test_no_transport_configured_raises_a_clear_error(self):
        from pipeline import mailer
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(mailer.MailNotConfigured):
                mailer.send("s", "<p>h</p>", "t", {}, ["a@example.com"])


class UtilTests(unittest.TestCase):
    def test_merge_keeps_history_and_prefers_new_values(self):
        merged = util.merge_series({"2026-01-01": 1.0, "2026-01-02": 2.0},
                                   {"2026-01-02": 2.5, "2026-01-03": 3.0})
        self.assertEqual(merged, {"2026-01-01": 1.0, "2026-01-02": 2.5, "2026-01-03": 3.0})

    def test_trim_drops_old_points(self):
        series = {days_ago(500): 1.0, days_ago(10): 2.0}
        self.assertEqual(list(util.trim_series(series, 365)), [days_ago(10)])

    def test_nearest_on_or_before_never_looks_forward(self):
        series = {"2026-01-01": 1.0, "2026-02-01": 2.0}
        self.assertEqual(util.nearest_on_or_before(series, dt.date(2026, 1, 20)), 1.0)
        self.assertIsNone(util.nearest_on_or_before(series, dt.date(2025, 12, 1)))

    def test_pct_change_handles_a_zero_base(self):
        self.assertIsNone(util.pct_change(5.0, 0.0))
        self.assertIsNone(util.pct_change(None, 1.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
