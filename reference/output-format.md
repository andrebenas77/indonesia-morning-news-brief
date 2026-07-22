# Output format

The brief always has four sections in this order: **Top News**, **Corporate / Emiten**,
**Bank Indonesia Watch**, **Global Markets**. You produce `build/data.json`; `scripts/build_html.py`
renders it. Do not hand-write HTML.

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

## Rendering rules (handled by the script)
- Missing/empty section → renders a muted "No items today." placeholder, never a crash.
- Headlines link out (`target="_blank" rel="noopener"`).
- `rank` shown as a number badge in Top News.
- Footer carries the methodology line and the disclaimer:
  *"Compiled from public sources for internal research use; not investment advice. Ranking is a
  transparent heuristic (most-read rails + cross-outlet coverage + Bank Indonesia priority), not
  view counts."*
