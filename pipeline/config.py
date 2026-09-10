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

OFFICIAL_FEEDS = [
    # Ireland
    {"country": "IE", "source": "Revenue.ie (Irish Revenue)",
     "url": "https://www.revenue.ie/en/corporate/press-office/news/rss.xml"},
    {"country": "IE", "source": "Department of Finance (IE)",
     "url": "https://www.gov.ie/en/organisation-information/9e7062-department-of-finance-press-releases/rss.xml"},
    {"country": "IE", "source": "Department of Enterprise, Tourism & Employment (IE)",
     "url": "https://www.gov.ie/en/organisation-information/61d3a-department-of-enterprise-trade-and-employment-press-releases/rss.xml"},
    {"country": "IE", "source": "Workplace Relations Commission",
     "url": "https://www.workplacerelations.ie/en/news-media/rss.xml"},
    {"country": "IE", "source": "Central Statistics Office (IE)",
     "url": "https://www.cso.ie/en/statistics/rss.xml"},
    # United Kingdom
    {"country": "UK", "source": "HMRC (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=hm-revenue-customs"},
    {"country": "UK", "source": "HM Treasury (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=hm-treasury"},
    {"country": "UK", "source": "Dept for Business & Trade (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=department-for-business-and-trade"},
    {"country": "UK", "source": "Employment law & pay (GOV.UK)",
     "url": "https://www.gov.uk/search/news-and-communications.atom?topical_events%5B%5D=&keywords=employment+law"},
    {"country": "UK", "source": "Office for National Statistics",
     "url": "https://www.ons.gov.uk/releasecalendar?rss"},
    # Netherlands
    {"country": "NL", "source": "Rijksoverheid - Financiën",
     "url": "https://www.rijksoverheid.nl/ministeries/ministerie-van-financien/nieuws/rss"},
    {"country": "NL", "source": "Rijksoverheid - Sociale Zaken & Werkgelegenheid",
     "url": "https://www.rijksoverheid.nl/ministeries/ministerie-van-sociale-zaken-en-werkgelegenheid/nieuws/rss"},
    {"country": "NL", "source": "Belastingdienst / Rijksoverheid Belastingen",
     "url": "https://www.rijksoverheid.nl/onderwerpen/belastingen/nieuws/rss"},
    {"country": "NL", "source": "CBS (Statistics Netherlands)",
     "url": "https://www.cbs.nl/en-gb/rss"},
    # Belgium
    {"country": "BE", "source": "Belgium.be news",
     "url": "https://www.belgium.be/en/rss/news.xml"},
    {"country": "BE", "source": "FPS Finance (Belgium)",
     "url": "https://finance.belgium.be/en/rss.xml"},
    {"country": "BE", "source": "National Bank of Belgium",
     "url": "https://www.nbb.be/en/rss/press-releases"},
    # EU-wide
    {"country": "EU", "source": "European Commission - Taxation & Customs",
     "url": "https://taxation-customs.ec.europa.eu/rss_en"},
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
# Market-derived series (Stooq CSV, no API key required).
STOOQ_SERIES = [
    {"key": "brent", "symbol": "cb.f", "label": "Brent crude (USD/bbl)",
     "class": "leading", "why": "Input cost & freight surcharge pressure"},
    {"key": "copper", "symbol": "hg.f", "label": "Copper (USD/lb)",
     "class": "leading", "why": "Classic 'Dr Copper' global demand gauge"},
    {"key": "stoxx", "symbol": "^stx50", "label": "Euro Stoxx 50",
     "class": "leading", "why": "Equity market discounts future earnings"},
    {"key": "ftse", "symbol": "^ukx", "label": "FTSE 100",
     "class": "leading", "why": "UK-weighted forward-looking demand signal"},
    {"key": "de10y", "symbol": "10deuy.b", "label": "German 10y Bund yield (%)",
     "class": "leading", "why": "Euro-area growth & inflation expectations", "unit": "pp"},
    {"key": "uk10y", "symbol": "10ukuy.b", "label": "UK 10y Gilt yield (%)",
     "class": "leading", "why": "UK borrowing cost & fiscal risk premium", "unit": "pp"},
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
    {"key": "esi", "dataset": "ei_bssi_m_r2", "label": "Economic sentiment / confidence",
     "class": "leading", "why": "Survey-based turning-point signal",
     "params": {"indic": "BS-ESI-I", "s_adj": "SA", "unit": "I-BCI"},
     "geos": {"IE": "Ireland", "NL": "Netherlands", "BE": "Belgium", "EA": "Euro area"}},
]

# ONS (UK) timeseries: (series id, dataset id)
ONS_SERIES = [
    {"key": "uk_cpih", "series": "l55o", "dataset": "mm23",
     "label": "UK CPIH inflation, annual %", "class": "lagging",
     "why": "Drives UK pay settlements and thresholds", "unit": "pp"},
    {"key": "uk_unemp", "series": "mgsx", "dataset": "lms",
     "label": "UK unemployment rate, %", "class": "lagging",
     "why": "UK labour market slack", "unit": "pp"},
    {"key": "uk_gdp", "series": "ihyq", "dataset": "qna",
     "label": "UK GDP, quarterly % change", "class": "lagging",
     "why": "Headline UK activity", "unit": "pp"},
]
