"""Central configuration for the Moyne Roberts daily newsflow brief."""
from __future__ import annotations

import os

# ---------------------------------------------------------------- general ----
SITE_TITLE = "Moyne Roberts — Daily Business Newsflow"
SITE_TAGLINE = "FX - Freight - Tax & Policy - M&A - Economic Indicators"
LOCAL_TZ = "Europe/Dublin"
SEND_HOUR_LOCAL = int(os.environ.get("SEND_HOUR_LOCAL", "9"))
RECIPIENTS = [
    e.strip()
    for e in os.environ.get("BRIEF_RECIPIENTS", "bruce.waldron@moyneroberts.com").split(",")
    if e.strip()
]
SITE_URL = os.environ.get("SITE_URL", "")
HTTP_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 MoyneRobertsNewsflow/1.0"
)

# How much history to show on the charts
FX_HISTORY_DAYS = 365 * 2
FREIGHT_HISTORY_DAYS = 365 * 2

# -------------------------------------------------------------------- FX ----
# ECB reference rates are quoted as units of foreign currency per 1 EUR.
FX_PAIRS = [
    {"key": "EURCNY", "code": "CNY", "label": "EUR / CNY", "symbol": "CN¥",
     "blurb": "Chinese renminbi per euro - drives landed cost of China-sourced product."},
    {"key": "EURGBP", "code": "GBP", "label": "EUR / GBP", "symbol": "£",
     "blurb": "Sterling per euro - drives UK revenue translation and UK-sourced cost."},
]

# ---------------------------------------------------------------- freight ----
# Trade lanes we care about (China / Far East -> North Europe & Mediterranean).
FREIGHT_LANES = [
    {"key": "FBX11", "label": "China/East Asia → North Europe (FBX11)"},
    {"key": "FBX13", "label": "China/East Asia → Mediterranean (FBX13)"},
    {"key": "WCI_SHA_RTM", "label": "Shanghai → Rotterdam (Drewry WCI)"},
    {"key": "WCI_SHA_GOA", "label": "Shanghai → Genoa (Drewry WCI)"},
    {"key": "WCI_COMPOSITE", "label": "Drewry WCI Composite (global)"},
    {"key": "SCFI", "label": "Shanghai Containerized Freight Index (SCFI)"},
]

# ------------------------------------------------------------------- news ----
# Google News RSS is used as a broad sweeper; official feeds below are the
# authoritative sources and are always ranked above sweeper results.
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-IE&gl=IE&ceid=IE:en"

# Direct feeds, kept only where the publisher actually serves a working one.
# GOV.UK's Atom search is the gold standard here - it is stable and complete.
OFFICIAL_FEEDS = [
    {"country": "UK", "source": "HMRC (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=hm-revenue-customs"},
    {"country": "UK", "source": "HM Treasury (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=hm-treasury"},
    {"country": "UK", "source": "Dept for Business & Trade (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=department-for-business-and-trade"},
    {"country": "UK", "source": "Dept for Work & Pensions (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=department-for-work-pensions"},
    {"country": "UK", "source": "Companies House (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=companies-house"},
    {"country": "UK", "source": "Office for National Statistics",
     "url": "https://www.ons.gov.uk/releasecalendar?rss"},
]

# Ireland, the Netherlands, Belgium and the Commission either do not publish a
# public RSS feed any more or have moved it (every candidate returned 404 or an
# empty document when probed). Rather than ship dead feeds, those publishers are
# reached through site-scoped news queries, which return the same primary-source
# articles and are marked OFFICIAL in the brief. `scripts/source_report.py`
# re-checks all of this, so a feed that comes back can be promoted above.
OFFICIAL_SITE_SWEEPS = [
    {"country": "IE", "source": "Revenue.ie (Irish Revenue)", "site": "revenue.ie",
     "terms": "tax OR VAT OR relief OR employer OR compliance"},
    {"country": "IE", "source": "gov.ie (Irish Government)", "site": "gov.ie",
     "terms": "tax OR budget OR employment OR business OR enterprise"},
    {"country": "IE", "source": "Central Statistics Office (IE)", "site": "cso.ie",
     "terms": "inflation OR employment OR earnings OR economy"},
    {"country": "IE", "source": "Workplace Relations Commission", "site": "workplacerelations.ie",
     "terms": "employment OR wage OR employer OR dispute"},
    {"country": "NL", "source": "Rijksoverheid (NL Government)", "site": "rijksoverheid.nl",
     "terms": "belasting OR ondernemers OR arbeidsmarkt OR loon"},
    {"country": "NL", "source": "Belastingdienst", "site": "belastingdienst.nl",
     "terms": "belasting OR ondernemer OR loonheffing"},
    {"country": "NL", "source": "CBS (Statistics Netherlands)", "site": "cbs.nl",
     "terms": "inflatie OR werkloosheid OR economie OR lonen"},
    {"country": "BE", "source": "FPS Finance (Belgium)", "site": "finance.belgium.be",
     "terms": "tax OR belasting OR impot OR company"},
    {"country": "BE", "source": "Belgium.be", "site": "belgium.be",
     "terms": "tax OR employment OR business OR wage"},
    {"country": "BE", "source": "National Bank of Belgium", "site": "nbb.be",
     "terms": "economy OR inflation OR business OR credit"},
    {"country": "EU", "source": "European Commission - Taxation & Customs",
     "site": "taxation-customs.ec.europa.eu",
     "terms": "tax OR VAT OR customs OR directive"},
]

# Topical sweeps run through Google News. Each becomes a "theme" on the site.
NEWS_THEMES = [
    {
        "key": "tax_ie",
        "title": "Ireland - Business tax, reliefs & Budget",
        "country": "IE",
        "queries": [
            'Ireland ("corporation tax" OR "tax relief" OR "R&D tax credit" OR Budget) business',
            'Ireland Revenue ("tax" OR "VAT" OR "capital gains") business when:7d',
        ],
    },
    {
        "key": "employment_ie",
        "title": "Ireland - Employment law & employment taxes",
        "country": "IE",
        "queries": [
            'Ireland ("employment law" OR "minimum wage" OR "PRSI" OR "auto-enrolment" OR "sick leave") employers',
        ],
    },
    {
        "key": "tax_uk",
        "title": "UK - Business tax, reliefs & fiscal policy",
        "country": "UK",
        "queries": [
            'UK ("corporation tax" OR "business rates" OR "capital allowances" OR "R&D tax relief" OR Budget) business',
            'HMRC ("tax" OR "VAT" OR "compliance") business when:7d',
        ],
    },
    {
        "key": "employment_uk",
        "title": "UK - Employment law & employment taxes",
        "country": "UK",
        "queries": [
            'UK ("employment rights" OR "national insurance" OR "national living wage" OR "employment law") employers',
        ],
    },
    {
        "key": "tax_nl",
        "title": "Netherlands - Business tax & policy",
        "country": "NL",
        "queries": [
            'Netherlands ("corporate tax" OR "vennootschapsbelasting" OR "tax plan" OR Prinsjesdag) business',
            'Netherlands ("labour law" OR "arbeidsrecht" OR "payroll tax" OR "loonheffing") employers',
        ],
    },
    {
        "key": "tax_be",
        "title": "Belgium - Business tax & policy",
        "country": "BE",
        "queries": [
            'Belgium ("corporate tax" OR "vennootschapsbelasting" OR "tax reform" OR "wage subsidy") business',
            'Belgium ("labour law" OR "employment law" OR "wage indexation" OR "social security contributions") employers',
        ],
    },
    {
        "key": "fire_safety_ma",
        "title": "Fire safety - M&A and acquisitions (UK & Europe)",
        "country": "EU",
        "queries": [
            '("fire safety" OR "fire protection" OR "fire suppression" OR "passive fire protection" OR sprinkler OR "fire alarm" OR "fire detection") (acquisition OR acquires OR acquired OR merger OR "M&A" OR takeover OR "buys")',
            '("fire protection" OR "life safety") ("private equity" OR "bolt-on" OR "buy and build" OR "acquisition") UK Europe',
        ],
    },
    {
        "key": "macro_eu",
        "title": "Macro, trade & supply chain",
        "country": "EU",
        "queries": [
            '("container freight rates" OR "ocean freight" OR "Red Sea" OR "shipping rates") Europe Asia',
            '("European Central Bank" OR "Bank of England") ("interest rate" OR "rate decision" OR inflation)',
        ],
    },
]

# Words that lift an article's relevance score for a business audience.
RELEVANCE_BOOST = {
    3: ["corporation tax", "corporate tax", "vennootschapsbelasting", "tax relief",
        "tax credit", "capital allowances", "r&d tax", "vat rate", "employment rights",
        "employment law", "minimum wage", "national insurance", "prsi", "payroll tax",
        "auto-enrolment", "pension auto", "budget 20", "finance bill", "fire safety",
        "fire protection", "acquisition", "acquires", "merger"],
    2: ["tax", "levy", "duty", "relief", "grant", "subsidy", "employer", "employment",
        "wage", "salary", "redundancy", "tribunal", "compliance", "regulation",
        "freight", "tariff", "customs", "supply chain", "interest rate", "inflation"],
    1: ["business", "economy", "growth", "policy", "government", "eu", "consultation"],
}

# ------------------------------------------------------- economic indicators --
# Market-derived series. Yahoo's chart endpoint is the primary (Stooq refuses
# datacentre IPs, which is what CI and the scheduler run on); Stooq stays as a
# fallback for the days Yahoo rate-limits. Bond yields come from the ECB and
# the Bank of England, which publish them directly.
MARKET_SERIES = [
    {"key": "brent", "yahoo": "BZ=F", "stooq": "cb.f", "label": "Brent crude (USD/bbl)",
     "class": "leading", "why": "Input cost & freight surcharge pressure"},
    {"key": "copper", "yahoo": "HG=F", "stooq": "hg.f", "label": "Copper (USD/lb)",
     "class": "leading", "why": "Classic 'Dr Copper' global demand gauge"},
    {"key": "stoxx", "yahoo": "^STOXX50E", "stooq": "^stx50", "label": "Euro Stoxx 50",
     "class": "leading", "why": "Equity market discounts future earnings"},
    {"key": "ftse", "yahoo": "^FTSE", "stooq": "^ukx", "label": "FTSE 100",
     "class": "leading", "why": "UK-weighted forward-looking demand signal"},
    {"key": "eurusd", "yahoo": "EURUSD=X", "stooq": "eurusd", "label": "EUR / USD",
     "class": "leading", "why": "Sets the euro cost of USD-denominated freight and commodities"},
]

# Euro-area 10-year benchmark government yield, straight from the ECB yield
# curve (the same API that serves the FX rates, so it is already proven).
ECB_YIELD_SERIES = [
    {"key": "ea10y", "sdmx": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
     "label": "Euro area 10y benchmark yield (%)", "class": "leading", "unit": "pp",
     "why": "Euro-area growth & inflation expectations, and the cost of borrowing"},
]

# Bank of England published statistics (CSV, no key).
BOE_SERIES = [
    {"key": "uk10y", "code": "IUDMNZC", "label": "UK 10y gilt yield (%)",
     "class": "leading", "unit": "pp",
     "why": "UK borrowing cost & fiscal risk premium"},
    {"key": "uk_bank_rate", "code": "IUDBEDR", "label": "Bank of England Bank Rate (%)",
     "class": "lagging", "unit": "pp",
     "why": "Sets the floor under UK borrowing costs"},
]

# Eurostat (free, no key). Dataset -> filter. Monthly series.
EUROSTAT_SERIES = [
    {"key": "hicp", "dataset": "prc_hicp_manr", "label": "HICP inflation, annual %",
     "class": "lagging", "why": "Feeds pay claims, indexation and pricing", "unit": "pp",
     "params": {"coicop": "CP00", "unit": "RCH_A"},
     "geos": {"IE": "Ireland", "NL": "Netherlands", "BE": "Belgium", "EA": "Euro area"}},
    {"key": "unemp", "dataset": "une_rt_m", "label": "Unemployment rate, %",
     "class": "lagging", "why": "Labour cost & availability", "unit": "pp",
     "params": {"unit": "PC_ACT", "s_adj": "SA", "age": "TOTAL", "sex": "T"},
     "geos": {"IE": "Ireland", "NL": "Netherlands", "BE": "Belgium", "EA": "Euro area"}},
    {"key": "conf", "dataset": "ei_bsco_m_r2", "label": "Consumer confidence indicator",
     "class": "leading", "why": "Survey-based turning-point signal",
     "params": {"indic": "BS-CSMCI", "s_adj": "SA", "unit": "BAL"},
     "geos": {"IE": "Ireland", "NL": "Netherlands", "BE": "Belgium", "EA": "Euro area"}},
]

# ONS (UK) timeseries: (series id, dataset id)
ONS_SERIES = [
    {"key": "uk_cpih", "path": "economy/inflationandpriceindices/timeseries/l55o/mm23",
     "label": "UK CPIH inflation, annual %", "class": "lagging",
     "why": "Drives UK pay settlements and thresholds", "unit": "pp"},
    {"key": "uk_unemp",
     "path": "employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
     "label": "UK unemployment rate, %", "class": "lagging",
     "why": "UK labour market slack", "unit": "pp"},
    {"key": "uk_gdp", "path": "economy/grossdomesticproductgdp/timeseries/ihyq/qna",
     "label": "UK GDP, quarterly % change", "class": "lagging",
     "why": "Headline UK activity", "unit": "pp"},
    {"key": "uk_awe", "path": "employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/emp",
     "label": "UK average weekly earnings, annual %", "class": "lagging",
     "why": "The wage bill trend behind employment-cost planning", "unit": "pp"},
]
