# Sources

## Contents
- Sectors API (primary for corporate news)
- Indonesia outlets (fallback only)
- Bank Indonesia (always, WebFetch)
- Global scan (always, WebSearch)
- Fetch notes & fallbacks

## Sectors API (primary for corporate news)

```bash
py scripts/fetch_sectors_news.py --days 1
```

Writes `build/sectors-news-<date>.json` from `/v2/news/`, `/v2/filings/` and `/v2/suspensions/`.
Sectors already aggregates and **summarizes the Indonesian outlets in English**, attaching
`symbols[]`, `sector`, `sub_sector[]`, normalized `tags[]` and an 8-axis `dimension` vector — so it
replaces the per-outlet scrape for corporate news at ~3 credits a run.

What it gives you that scraping did not:
- **`filings`** — insider and institutional transactions with holder name, before/after holdings and
  the individual fills. `holder_type` `institution` and `insider` both work; `corporate-investor`
  returns nothing and should not be used.
- **`suspensions`** — trading halts with the official reason and the IDX PDF.
- **`tickers`** — the ticker union that feeds `fetch_flows.py --tickers`.

**Scope limit — this is why the scrape below still exists.** Sectors carries **no Bank Indonesia
releases and no global macro**. Those two scans stay on WebFetch/WebSearch every single run.

## Indonesia outlets (always — fetched by script, not WebFetch)

```bash
py scripts/fetch_outlets.py --hours 30
```

Runs **every morning alongside Sectors**, not as a fallback. Sectors aggregates each story
into one article, which is precisely what destroys `cross_outlet_count` — on the Sectors-only
path it was always 1. The raw feeds restore that signal and add the most-read rails, which
Sectors does not carry at all.

All six endpoints verified live 2026-08-16:

| Outlet | Method | Endpoint | Gives |
|---|---|---|---|
| Kontan | RSS | `https://investasi.kontan.co.id/rss` | Latest market (~25) |
| Kontan | HTML | `https://www.kontan.co.id/` → `#berita-terpopuler` | **Terpopuler rail** (ranked most-read) |
| CNBC Indonesia | RSS | `https://www.cnbcindonesia.com/market/rss` | Latest market (~100) |
| CNBC Indonesia | JSON | `https://www.cnbcindonesia.com/widget/wp_terpopuler?param=10` | Most-Popular rail |
| Emitennews | HTML | `https://emitennews.com/` | Latest + trending (`data-label="home_*_tap"`) |
| Bloomberg Technoz | RSS | `https://www.bloombergtechnoz.com/rss` | Latest market/economy (~100) |

**Traps, all found the hard way:**

- `www.kontan.co.id/rss` returns an HTML feed-directory page, not XML. Use the `investasi.`
  subdomain.
- Kontan emits **two** elements with `id="berita-terpopuler"`. The first is *Terpopuler*
  (real most-read); the second is *Jangan Lewatkan* — editorial picks that restart numbering
  at 1 and carry non-market content (a live sample had an esports result at rank 1). The
  parser matches on the heading text for this reason.
- Emitennews `/feed` and `/rss` both return **HTTP 500** — no RSS exists. The homepage is
  parsed instead.
- Bloomberg Technoz `/feed` and `/ekonomi/rss` return the HTML page, not XML. Only `/rss` works.
- CNBC's Most-Popular rail is JS-rendered on the page, but the widget endpoint above returns
  it as JSON. It is **undocumented** and may vanish without notice — treat it as best-effort.

**The two rails are not equivalent.** Kontan's Terpopuler is genuinely market-relevant; CNBC's
Most Popular is site-wide (a live sample: flag ceremony, toll road, train tickets, a death, an
earthquake — 0/5 market). A CNBC rail hit therefore only earns a `rail_rank` when the story
also appears in CNBC's `/market` feed. See `ranking-rubric.md`.

WebFetch on these outlets is no longer part of the workflow. Bank Indonesia and the global
scan below still use WebFetch/WebSearch every run — Sectors carries neither.

## Bank Indonesia (always)

- News releases (EN): `https://www.bi.go.id/en/publikasi/ruang-media/news-release/default.aspx`
- News releases (ID): `https://www.bi.go.id/id/publikasi/ruang-media/news-release/default.aspx`

Always fetch and capture the latest releases (title, date, link). A fresh, market-moving BI item
(rate decision, rupiah measures, macroprudential) is also eligible for **Top News**, not just the
Bank Indonesia Watch section.

## Global scan (search terms)

Use WebSearch, last ~24h, prefer Reuters / Bloomberg / CNBC / Trading Economics. Keep 3–6 items
with real links for **Global Markets**:

- `FOMC decision` / `Fed rate` / `Fed officials speech`
- `DXY dollar index today`
- `Trump tariffs` / `Trump policy markets`
- `US 10-year Treasury yield today`

These four themes are the fixed global watchlist (per the PM's scope). Commodities and China are
intentionally **not** always-checks — include only if they surface as a top global market story.

## Fetch notes & fallbacks

- WebFetch returns readable text/markdown; JS-only rails (e.g. CNBC "Most Popular") often show
  "Loading…" — don't treat that as data. Use cross-outlet frequency to rank instead.
- If an outlet returns a cross-host redirect, re-fetch the redirect URL.
- If a primary outlet is down/403/timeout: note it in `sources_scanned` as failed and continue.
  Optional secondary fallbacks (only if a primary is unavailable): IDX `https://www.idx.co.id/`,
  Bisnis `https://www.bisnis.com/`, Investor Daily `https://investor.id/`.
- Optional deep fetch: for a shortlisted Top-News item you may WebFetch the article page itself to
  confirm the link is live and refine the one-line summary — but never invent detail not on the page.
