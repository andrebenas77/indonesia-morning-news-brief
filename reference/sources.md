# Sources

## Contents
- Indonesia outlets (primary)
- Bank Indonesia (always)
- Global scan (search terms)
- Fetch notes & fallbacks

## Indonesia outlets (primary)

Fetch these every run. Prefer each site's most-read/popular rail plus its latest market items.

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
