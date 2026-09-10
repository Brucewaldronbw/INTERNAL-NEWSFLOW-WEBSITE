# Moyne Roberts — Daily Business Newsflow

A self-updating dashboard and a 09:00 (Europe/Dublin) email covering:

| Section | What it shows | Where it comes from |
|---|---|---|
| **EUR/CNY** | spot rate, 1d/1w/1m/3m/1y change, 52-week range, 2-year chart | ECB euro reference rates → Frankfurter → open.er-api |
| **EUR/GBP** | same | same |
| **China → Europe freight** | FBX11, FBX13, Drewry WCI lanes (Shanghai→Rotterdam / Genoa), WCI composite, SCFI, with history | Freightos FBX → Drewry WCI → SSE/SCFI |
| **Tax & policy newsflow** | Ireland, UK, Netherlands, Belgium — business tax, reliefs, employment law, employment taxes | 18 official government/regulator feeds + targeted Google News sweeps |
| **Fire safety M&A** | acquisitions, mergers and PE activity in fire safety / fire protection across the UK and Europe | targeted Google News sweeps |
| **Leading & lagging indicators** | Brent, copper, Euro Stoxx 50, FTSE 100, Bund and Gilt yields; HICP inflation, unemployment and economic sentiment for IE/NL/BE/euro area; UK CPIH, unemployment and GDP | Stooq, Eurostat, ONS |

Every source is free and needs no API key.

---

## Go-live checklist

The code, the schedule and the website are all in this repository. Two things
need a human with repository-admin rights, because they involve credentials and
settings that cannot be set from code:

### 1. Give it a mailbox to send from  *(required — nothing is emailed until this is done)*

Pick **one** transport and add its values under
**Settings → Secrets and variables → Actions → Secrets**:

**Option A — Microsoft 365 / Outlook SMTP** (simplest if the sending mailbox already exists)

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | the sending mailbox, e.g. `newsflow@moyneroberts.com` |
| `SMTP_PASS` | that mailbox's app password |
| `MAIL_FROM` | the same address |

Microsoft 365 requires SMTP AUTH to be enabled on that mailbox and an app
password (basic auth with the normal password is disabled on most tenants).

**Option B — Microsoft Graph** (no password; a one-off app registration, best for a locked-down tenant)

| Secret | Value |
|---|---|
| `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` | from the Entra ID app registration |
| `MAIL_FROM` | the mailbox the app is permitted to send as |

Grant the app the **Mail.Send** application permission, then restrict it to the
one mailbox with an ApplicationAccessPolicy.

**Option C — Resend / SendGrid** (fastest if you would rather not touch the tenant)

| Secret | Value |
|---|---|
| `RESEND_API_KEY` | API key |
| `MAIL_FROM` | a verified sending address |

### 2. Turn the website on

**Settings → Pages → Build and deployment → Deploy from a branch**, branch =
your default branch, folder = `/ (root)`. The workflow commits a freshly built
`index.html` every morning, so Pages republishes it automatically.

*(If you would rather Pages was driven by the workflow itself, set the repository
variable `PAGES_VIA_ACTIONS` to `true` and change the Pages source to
"GitHub Actions" — the workflow already contains that path.)*

### 3. Optional settings

Under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Default | Purpose |
|---|---|---|
| `BRIEF_RECIPIENTS` | `bruce.waldron@moyneroberts.com` | comma-separated distribution list |
| `SITE_URL` | *(none)* | your Pages URL — adds an "Open the live dashboard" button to the email |
| `MAIL_FROM_NAME` | `Moyne Roberts Newsflow` | sender display name |
| `PAGES_VIA_ACTIONS` | *(none)* | set to `true` only for the Actions-driven Pages option |

### 4. Send a test

**Actions → Daily newsflow brief → Run workflow**, tick **force_send**. Use the
`recipients` box to send the first one only to yourself.

---

## The schedule

`.github/workflows/daily-brief.yml` runs at **08:00, 09:00 and 10:00 UTC** daily.
`pipeline/run.py` then sends only when it is **09:00 or later in Europe/Dublin**
and nothing has been sent yet that day, with the result recorded in
`data/state.json`.

That combination handles the three things that otherwise break a "9am email":

* **Daylight saving** — 09:00 Dublin is 08:00 UTC in summer and 09:00 UTC in winter.
* **GitHub's scheduler running late** — it is best-effort and can be 5–30 minutes behind.
* **Duplicates** — the day's state file means the extra runs only refresh the
  website; they never send a second email.

---

## Resilience

Every source is wrapped so that one bad morning cannot stop the brief:

* HTTP calls retry with backoff and then return "no data" rather than raising.
* FX and freight readings are merged into `data/*.json` and committed back, so
  each chart keeps its history — and the freight chart deepens daily — even
  through a source outage.
* Sections with no data render an explicit "did not respond" notice; they never
  show a stale number as if it were today's.
* If email delivery fails, the dashboard is still rebuilt and committed, and the
  workflow run is marked failed so the problem is visible in Actions.

Freight is the fragile one: there is no free, stable public API for container
spot rates, so the collector scrapes three public publishers in turn. If they
all change their markup at once that section will report no reading until the
selectors in `pipeline/fetchers/freight.py` are updated.

---

## Working on it locally

```bash
pip install -r requirements.txt

python -m unittest discover -s tests        # 37 unit tests
python -m pipeline.run --offline --no-email --out /tmp/site   # every source "down"
python scripts/preview_with_sample_data.py /tmp/preview       # site + email from fake data
python -m pipeline.run --no-email --out /tmp/site             # real data, no email
python -m pipeline.run --force --to you@example.com           # real data, send to yourself
```

`scripts/preview_with_sample_data.py` generates **random** numbers so layout can
be checked without a network. It labels its output `[SAMPLE DATA PREVIEW]` and
writes to a scratch directory — it never touches the published site.

### Layout

```
pipeline/
  config.py            sources, feeds, search queries, indicator definitions
  util.py              retrying HTTP, the JSON history store, formatting
  fetchers/fx.py       ECB / Frankfurter / open.er-api
  fetchers/freight.py  Freightos FBX / Drewry WCI / SCFI
  fetchers/news.py     official feeds + Google News sweeps, scoring and dedupe
  fetchers/indicators.py  Stooq / Eurostat JSON-stat / ONS
  charts.py            matplotlib PNGs for the email
  render.py            view model, website and email bodies
  mailer.py            SMTP / Microsoft Graph / Resend
  run.py               orchestrator and the send guard
templates/             site.html.j2, email.html.j2
assets/vendor/         Chart.js, vendored so the site needs no CDN
data/                  accumulated history + last-sent state (committed by the workflow)
```

To add a country, a topic or an indicator, edit `pipeline/config.py` — the
fetchers and templates pick it up without further changes.

---

## Notes

* The figures are collected from public sources for internal information only.
  They are not financial, tax or legal advice — confirm against the primary
  source before relying on anything here.
* Rates are shown in the unit that makes sense for them: an index or a price
  moves in **per cent**, an inflation or unemployment rate moves in
  **percentage points**.
