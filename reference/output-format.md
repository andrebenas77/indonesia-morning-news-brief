# Output format

The brief has six sections in this order: **Where to Look Today**, **Net Foreign Flow**,
**Top News**, **Corporate / Emiten**, **Bank Indonesia Watch**, **Global Markets**.
You produce `build/data.json`; `scripts/build_html.py` renders it. Do not hand-write HTML.

## The two flow sections are NOT in data.json

`Where to Look Today` and `Net Foreign Flow` render from **`build/radar-<date>.json`**, which
`scripts/build_radar.py` generates by joining flow + news + Telegram chatter. `build_html.py` loads
it automatically — it looks for `radar-<date>.json` first and otherwise falls back to the newest
radar file, because the radar is keyed to the **trading session**, which lags the run date on
Mondays and after holidays.

You never hand-write these sections. If the radar file is missing, both sections render a muted
placeholder and the rest of the brief is unaffected.

### Accuracy rule for the flow board
The board publishes **only exactly-measured tickers** (`/v2/foreign-flow/`). Names that appear in
the broker-derived candidate ranking but were not measured are listed separately as *unverified
candidates* and must never be presented as measured flow. This is not pedantry: on 2026-07-24 the
derived value for BBCA was −76.7bn (outflow) while the exact value was +26.7bn (inflow) — the
opposite direction. Five of twelve measured tickers flipped sign that session.

## data.json schema

```json
{
  "date": "2026-07-22",
  "date_display": "Wednesday, 22 July 2026",
  "generated_at": "08:20 WIB",
  "sources_scanned": [
    {"outlet": "Kontan", "status": "ok"},
    {"outlet": "CNBC Indonesia", "status": "ok"},
    {"outlet": "Emitennews", "status": "ok"},
    {"outlet": "Bloomberg Technoz", "status": "ok"},
    {"outlet": "Bank Indonesia", "status": "ok"}
  ],
  "top_news": [
    {
      "rank": 1,
      "headline": "English display headline",
      "headline_original": "Original Bahasa headline (optional)",
      "summary": "One-line English factual summary of what happened.",
      "outlet": "Kontan",
      "time": "09:11",
      "url": "https://www.kontan.co.id/news/...",
      "tags": ["popular", "market"]
    }
  ],
  "corporate": [ { "headline": "...", "summary": "...", "outlet": "Emitennews", "time": "08:40", "url": "https://...", "tags": ["AMMN"] } ],
  "bank_indonesia": [ { "headline": "...", "summary": "...", "date": "22 July 2026", "url": "https://www.bi.go.id/en/..." } ],
  "global": [ { "headline": "...", "summary": "...", "outlet": "Reuters", "url": "https://...", "tags": ["fed"] } ]
}
```

### Field rules
- `date` — ISO `YYYY-MM-DD`, Asia/Jakarta. Used for the archive filename. **Required.**
- `date_display` — human string for the header. Optional (script derives one if omitted).
- `generated_at` — short local time string (e.g. `08:20 WIB`). Optional.
- `sources_scanned[]` — one entry per outlet attempted, `status` = `ok` | `failed`. Failed sources
  render as a muted "unavailable today" note (transparency; never hide a failure).
- `top_news[]` — up to 10, each with `rank` (1-based). `headline`, `summary`, `outlet`, `url`
  required; `time`, `headline_original`, `tags` optional.
- `corporate[]`, `global[]` — same item shape, no `rank`.
- `bank_indonesia[]` — item shape uses `date` instead of `time`; `outlet` defaults to
  "Bank Indonesia".
- Every `url` must be an absolute link actually fetched this run. `tags[]` are short lowercase
  labels (e.g. `popular`, `flows`, `fed`, `bbri`) shown as small chips.

## radar-<date>.json (generated — reference only)

```json
{
  "date": "2026-07-24",
  "available": true,
  "inputs": {"flows": true, "news": true, "chatter": true, "chatter_sessions": 1},
  "buckets": [
    {"key": "flow_confirms_news", "title": "Flow confirms the news", "desc": "...",
     "count": 9,
     "rows": [{"symbol": "BBRI", "net_idr": 173600000000, "net_display": "+173.6bn",
               "run_sessions": 8, "run_direction": "in", "news_count": 5,
               "chatter_rank": 7, "inst_net": null, "note": "5 stories · foreign +173.6bn"}]}
  ],
  "market": {
    "top_inflow": [], "top_outflow": [],
    "method": "Candidates derived from the top 8 foreign brokers ... measured exactly ...",
    "unverified_candidates": [{"symbol": "INDY", "derived_net_idr": 13400000000}],
    "sign_flips": [{"symbol": "BBCA", "derived": -76678127500, "exact": 26678230000}]
  },
  "warnings": ["Only 1 session(s) of Telegram history — chatter buckets are provisional..."]
}
```

The four buckets are always emitted in this order, even when empty:
`flow_confirms_news`, `flow_contradicts_news`, `crowded_distributed`, `quiet_accumulation`.

## Rendering rules (handled by the script)
- Missing/empty section → renders a muted "No items today." placeholder, never a crash.
- Headlines link out (`target="_blank" rel="noopener"`).
- `rank` shown as a number badge in Top News.
- Footer carries the methodology line and the disclaimer:
  *"Compiled from public sources for internal research use; not investment advice. Ranking is a
  transparent heuristic (most-read rails + cross-outlet coverage + Bank Indonesia priority), not
  view counts."*
