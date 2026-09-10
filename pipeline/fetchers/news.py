"""Policy, tax, employment-law and M&A newsflow.

Two tiers:
  * OFFICIAL_FEEDS - government / statistics-office / regulator feeds. These
    are authoritative and always sort above sweeper results.
  * NEWS_THEMES    - Google News RSS sweeps per topic and jurisdiction.

Items are de-duplicated across sources, scored for business relevance, and
grouped into the themes rendered on the site and in the email.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import urllib.parse

import feedparser

from .. import config, util

LOG = logging.getLogger("newsflow.news")

FRESH_HOURS = 36          # what counts as "this morning's news"
FALLBACK_HOURS = 24 * 7   # widen if a theme comes back empty
MAX_PER_THEME = 8

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# Official feeds are matched into themes by keyword so they appear in context.
OFFICIAL_THEME_HINTS = {
    "employment_ie": ["employment", "wrc", "wage", "prsi", "pension", "leave", "worker"],
    "employment_uk": ["employment", "wage", "national insurance", "worker", "payroll"],
    "tax_ie": ["tax", "revenue", "budget", "vat", "duty", "relief", "finance"],
    "tax_uk": ["tax", "hmrc", "treasury", "budget", "vat", "duty", "relief", "business rates"],
    "tax_nl": ["belasting", "tax", "financien", "financiën", "loonheffing", "arbeid"],
    "tax_be": ["tax", "finance", "belasting", "wage", "social"],
    "macro_eu": ["inflation", "gdp", "rate", "economy", "trade", "customs", "statistics"],
}


def _clean(text: str | None) -> str:
    return _WS.sub(" ", _TAG.sub(" ", text or "")).strip()


def _entry_time(entry) -> dt.datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        stamp = getattr(entry, attr, None)
        if stamp:
            try:
                return dt.datetime(*stamp[:6], tzinfo=dt.timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _split_google_title(title: str) -> tuple[str, str | None]:
    """Google News titles are 'Headline - Publisher'."""
    if " - " in title:
        head, _, publisher = title.rpartition(" - ")
        if head and len(publisher) < 60:
            return head.strip(), publisher.strip()
    return title, None


def _score(item: dict) -> int:
    haystack = f"{item['title']} {item['summary']}".lower()
    score = 12 if item["official"] else 0
    for weight, words in config.RELEVANCE_BOOST.items():
        for word in words:
            if word in haystack:
                score += weight
    age_h = item.get("age_hours")
    if age_h is not None:
        if age_h <= 24:
            score += 6
        elif age_h <= 48:
            score += 3
        elif age_h > 24 * 14:
            score -= 4
    return score


def _norm_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:70]


def _parse_feed(url: str, *, official: bool, source: str | None,
                country: str | None) -> list[dict]:
    resp = util.get(url, retries=2)
    if resp is None:
        return []
    try:
        parsed = feedparser.parse(resp.content)
    except Exception as exc:  # feedparser is tolerant, but never trust a feed
        LOG.warning("feed parse failed %s: %s", url, exc)
        return []

    now = dt.datetime.now(dt.timezone.utc)
    items = []
    for entry in parsed.entries[:40]:
        title = _clean(getattr(entry, "title", ""))
        if not title:
            continue
        publisher = source
        if not official:
            title, detected = _split_google_title(title)
            publisher = detected or _clean(getattr(getattr(entry, "source", None), "title", "")) or "News"
        published = _entry_time(entry)
        age_hours = (now - published).total_seconds() / 3600 if published else None
        items.append({
            "title": title,
            "url": getattr(entry, "link", ""),
            "summary": _clean(getattr(entry, "summary", ""))[:400],
            "published": published.isoformat() if published else None,
            "published_display": published.strftime("%d %b %Y, %H:%M UTC") if published else "date not stated",
            "age_hours": age_hours,
            "source": publisher,
            "official": official,
            "country": country,
        })
    return items


def fetch() -> dict:
    all_items: list[dict] = []

    # ---- tier 1: official feeds
    for feed in config.OFFICIAL_FEEDS:
        items = _parse_feed(feed["url"], official=True, source=feed["source"],
                            country=feed["country"])
        LOG.info("official feed %s -> %s items", feed["source"], len(items))
        all_items.extend(items)

    # ---- tier 1b: site-scoped sweeps of publishers with no working feed
    for sweep in config.OFFICIAL_SITE_SWEEPS:
        query = f'site:{sweep["site"]} ({sweep["terms"]})'
        url = config.GOOGLE_NEWS.format(q=urllib.parse.quote(query))
        items = _parse_feed(url, official=True, source=sweep["source"],
                            country=sweep["country"])
        LOG.info("official sweep %s -> %s items", sweep["source"], len(items))
        all_items.extend(items)

    # ---- tier 2: themed Google News sweeps
    theme_hits: dict[str, list[dict]] = {t["key"]: [] for t in config.NEWS_THEMES}
    for theme in config.NEWS_THEMES:
        for query in theme["queries"]:
            url = config.GOOGLE_NEWS.format(q=urllib.parse.quote(query))
            items = _parse_feed(url, official=False, source=None, country=theme["country"])
            for item in items:
                item["theme"] = theme["key"]
            theme_hits[theme["key"]].extend(items)
        LOG.info("theme %s -> %s raw items", theme["key"], len(theme_hits[theme["key"]]))
        all_items.extend(theme_hits[theme["key"]])

    # ---- assign official items to themes by country + keyword hint
    for item in all_items:
        if item.get("theme"):
            continue
        item["theme"] = _guess_theme(item)

    # ---- score, dedupe (best-scoring copy of a story wins)
    for item in all_items:
        item["score"] = _score(item)
    best: dict[str, dict] = {}
    for item in sorted(all_items, key=lambda i: -i["score"]):
        key = _norm_key(item["title"])
        if key and key not in best:
            best[key] = item

    deduped = list(best.values())
    themes = []
    for theme in config.NEWS_THEMES:
        pool = [i for i in deduped if i.get("theme") == theme["key"]]
        fresh = [i for i in pool if (i["age_hours"] or 1e9) <= FRESH_HOURS]
        chosen = fresh or [i for i in pool if (i["age_hours"] or 1e9) <= FALLBACK_HOURS]
        chosen = sorted(chosen, key=lambda i: (-i["score"], i["age_hours"] or 1e9))[:MAX_PER_THEME]
        themes.append({
            "key": theme["key"],
            "title": theme["title"],
            "country": theme["country"],
            "items": chosen,
            "widened": not fresh and bool(chosen),
            "count": len(chosen),
        })

    top = sorted(
        [i for i in deduped if (i["age_hours"] or 1e9) <= FRESH_HOURS],
        key=lambda i: -i["score"],
    )[:6]

    LOG.info("news: %s raw, %s unique, %s in top picks", len(all_items), len(deduped), len(top))
    return {
        "themes": themes,
        "top": top,
        "total_unique": len(deduped),
        "total_shown": sum(t["count"] for t in themes),
    }


def _guess_theme(item: dict) -> str:
    country = item.get("country")
    haystack = f"{item['title']} {item['summary']}".lower()
    candidates = [t for t in config.NEWS_THEMES if t["country"] == country] or config.NEWS_THEMES
    best_key, best_hits = candidates[0]["key"], -1
    for theme in candidates:
        hints = OFFICIAL_THEME_HINTS.get(theme["key"], [])
        hits = sum(1 for h in hints if h in haystack)
        if hits > best_hits:
            best_key, best_hits = theme["key"], hits
    return best_key
