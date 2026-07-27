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

## Indonesia outlets (fallback only)

Only fetch these when `fetch_sectors_news.py` fails or returns very few items (note it in
`sources_scanned`). Prefer each site's most-read/popular rail plus its latest market items.

| Outlet | URL(s) | Read this | Best for |
|---|---|---|---|
| Kontan | `https://www.kontan.co.id/` · `https://investasi.kontan.co.id/` | **Terpopuler** rail (ranked most-read) + latest market | Market, macro, popularity ranking |
| CNBC Indonesia | `https://www.cnbcindonesia.com/market` | Latest `/market` headlines (Most-Popular rail is JS-rendered, usually not in static HTML) | Market, macro, flows |
| Emitennews | `https://emitennews.com/` | Latest headlines | Emiten / corporate actions |
| Bloomberg Technoz | `https://www.bloombergtechnoz.com/` · `https://www.bloombergtechnoz.com/ekonomi` | Latest market/economy headlines | Market, economy |

Capture per story: `headline`, absolute `url`, `outlet`, `time` (if shown), `category`,
and the **Terpopuler rail position** when present (1 = most read).

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
