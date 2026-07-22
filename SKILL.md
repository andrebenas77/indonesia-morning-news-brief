---
name: indonesia-morning-news-brief
description: Screens Indonesian financial-market morning news and publishes a ranked HTML brief. Use for a daily Jakarta Stock Exchange (JCI/IHSG) news screen — scans Kontan, CNBC Indonesia, Emitennews, Bloomberg Technoz and Bank Indonesia for the top ~10 stories worth reading, plus global signals (Fed, DXY, Trump, US rates/UST yields), and outputs a modern-dark HTML page for GitHub Pages. Triggers on requests like "Indonesia market news", "morning brief", "IHSG/JCI news", "Jakarta stock exchange news", "Bank Indonesia news".
---

# Indonesia Morning News Brief

Produce a daily, ranked, English-language HTML news brief for an Indonesia-focused
portfolio manager. Scan reputable Indonesian outlets + Bank Indonesia, rank the top ~10
stories "worth reading," add a lean global-macro scan, render a modern-dark HTML page, and
publish it to GitHub Pages with a dated archive.

**This is a pure aggregator.** Ranked headlines + a one-line factual English summary + a
working link. No opinions, no recommendations, no analytical commentary.

## Absolute rules (MUST)

1. **Never fabricate.** Only include headlines, URLs, outlets, and timestamps you actually
   retrieved this run via WebFetch/WebSearch. Never invent or guess a headline or a link.
   Every link must resolve to an article you fetched. If unsure a link is real, drop the item.
2. **If a source fails to load, note it and continue.** Do not fabricate items to reach 10.
   Fewer real stories beats padded fake ones. Record failed sources in `sources_scanned`.
3. **Bank Indonesia is always included** if BI has any recent release (rate, rupiah,
   macroprudential, surveys). It is the standing benchmark for "worth reading."
4. **English output.** Translate/summarize Bahasa headlines into concise English. Keep proper
   nouns and tickers as-is (e.g. IHSG, BBRI, AMMN).
5. **Aggregator voice only.** The summary states what happened in one line — no "this matters
   because", no buy/sell views.

## Morning workflow

Copy this checklist into your reply and check items off as you go:

```
Indonesia Morning Brief — progress
- [ ] 1. Set date (Asia/Jakarta) and read reference files
- [ ] 2. Scan Indonesia outlets (Kontan Terpopuler + market, CNBC, Emitennews, Bloomberg Technoz)
- [ ] 3. Fetch Bank Indonesia latest releases (always)
- [ ] 4. Global scan (Fed/FOMC, DXY, Trump/tariffs, UST 10Y) — last ~24h
- [ ] 5. Score & rank -> Top 10; bucket Corporate/Emiten, BI Watch, Global
- [ ] 6. Translate/summarize each to a 1-line English summary
- [ ] 7. Write build/data.json; run scripts/build_html.py
- [ ] 8. Verify docs/index.html in the browser preview
- [ ] 9. Commit & push (ask first); confirm Pages URL
```

### Step 1 — Setup
Determine today's date in Asia/Jakarta (WIB, UTC+7). Read [reference/sources.md](reference/sources.md),
[reference/ranking-rubric.md](reference/ranking-rubric.md), and
[reference/output-format.md](reference/output-format.md).

### Step 2 — Scan Indonesia outlets
WebFetch each source in `reference/sources.md`. For each candidate story collect:
`headline`, `url` (absolute), `outlet`, `time` (as shown on the page, else omit),
`category`, and — where available — its **Terpopuler/most-read rail position**.

- **Kontan** — read the **Terpopuler** rail (ranked most-read) *and* the latest market items.
  The Terpopuler ordinal is your strongest popularity signal.
- **CNBC Indonesia** — its "Most Popular" rail is JS-rendered and usually invisible to WebFetch;
  take the latest `/market` headlines instead and rely on cross-outlet frequency for ranking.
  (Optional: use the browser MCP to render the popular rail — only if needed.)
- **Emitennews** — emiten/corporate-action focused; good for the Corporate/Emiten bucket.
- **Bloomberg Technoz** — market/economy headlines.

### Step 3 — Bank Indonesia (always)
WebFetch the BI news-release page in `reference/sources.md`. Capture the latest releases with
titles, dates, and links. These feed the **Bank Indonesia Watch** section; a fresh, market-moving
BI item (e.g. a rate decision) should also be scored into **Top News**.

### Step 4 — Global scan
WebSearch for the last ~24h on: Fed / FOMC / Fed speakers; DXY / US dollar; Trump / tariffs /
US policy affecting markets; US 10-year Treasury yield. Prefer Reuters / Bloomberg / CNBC.
Keep 3–6 items with real links for the **Global Markets** section.

### Step 5 — Score & rank
Apply [reference/ranking-rubric.md](reference/ranking-rubric.md). Take the **Top 10** for Top News.
Route stock/corporate items to Corporate/Emiten, BI items to Bank Indonesia Watch, and global
items to Global Markets. De-duplicate the same story across outlets (keep the best source; the
duplication itself raises its rank).

### Step 6 — Summarize
Write a **one-line English factual summary** for every item. Translate Bahasa headlines to English
for the display headline; you may keep the original in `headline_original` if useful.

### Step 7 — Build
Write `build/data.json` following the schema in [reference/output-format.md](reference/output-format.md),
then run:

```bash
python scripts/build_html.py
```

This renders `docs/index.html` (today) + `docs/archive/YYYY-MM-DD.html` and regenerates
`docs/archive.html`. On Windows, if `python` is not found use the full path:
`C:/Users/ASUS/AppData/Local/Python/bin/python.exe scripts/build_html.py`.

### Step 8 — Verify
Open `docs/index.html` in the browser preview. Confirm: 4 sections render; Top News is numbered
and ≤10; Bank Indonesia Watch is populated; Global Markets has real items; dark theme looks right;
Archive link works. Spot-check 2–3 links open to genuine articles.

### Step 9 — Publish
Show the user a short summary (counts per section + the top 3 headlines). **Ask before pushing.**
Then commit and push; confirm the live Pages URL. See [README.md](README.md) for the git/Pages setup
(the repo and Pages toggle are created once, manually, because `gh` CLI is not installed).

## Output format

Strict template — always these four sections in this order: **Top News**, **Corporate / Emiten**,
**Bank Indonesia Watch**, **Global Markets**. Full spec and the `data.json` schema live in
[reference/output-format.md](reference/output-format.md). Do not hand-write HTML — always render via
`scripts/build_html.py` so the layout stays consistent.

## Examples & evals

- What good looks like: [examples/good-output.html](examples/good-output.html) (built from
  [examples/good-data.json](examples/good-data.json)).
- What to avoid: [examples/bad-output.md](examples/bad-output.md).
- Test scenarios and grading rubric: [evals/README.md](evals/README.md).
