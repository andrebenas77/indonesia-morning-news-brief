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
- [ ] 2. Sectors news:   py scripts/fetch_sectors_news.py --days 1
- [ ] 3. Foreign flow:   py scripts/fetch_flows.py --tickers <tickers from step 2>
- [ ] 4. Radar join:     py scripts/build_radar.py
- [ ] 5. Fetch Bank Indonesia latest releases (always, WebFetch)
- [ ] 6. Global scan (Fed/FOMC, DXY, Trump/tariffs, UST 10Y) — last ~24h
- [ ] 7. Score & rank -> Top 10; bucket Corporate/Emiten, BI Watch, Global
- [ ] 8. Translate/summarize each to a 1-line English summary
- [ ] 9. Write build/data.json; run scripts/build_html.py
- [ ] 10. Verify docs/index.html in the browser preview
- [ ] 11. Commit & push (ask first); confirm Pages URL
```

### Step 1 — Setup
Determine today's date in Asia/Jakarta (WIB, UTC+7). Read [reference/sources.md](reference/sources.md),
[reference/ranking-rubric.md](reference/ranking-rubric.md), and
[reference/output-format.md](reference/output-format.md).

### Step 2 — Sectors news (primary for corporate news)
```bash
py scripts/fetch_sectors_news.py --days 1
```
Writes `build/sectors-news-<date>.json` — English summaries of the Indonesian outlets with
`symbols[]`, normalized `tags[]`, and an 8-axis `dimension` vector, plus insider/institutional
filings and any suspensions. The script prints the ticker union; **copy it for step 3**.

Only fall back to the per-outlet WebFetch scrape in `reference/sources.md` if this fails or returns
very few items — and record that in `sources_scanned`.

### Step 3 — Foreign flow
```bash
py scripts/fetch_flows.py --tickers BBCA,BMRI,ASII        # tickers from step 2
```
Ranks foreign brokers, derives candidate tickers, then **measures the shortlist exactly** via
`/v2/foreign-flow/` and pulls the retail/institutional cohort split on the top names. ~50 credits at
the default `standard` tier; `--tier lean` (~32) or `--tier deep` (~91) if you need to trade cost
for breadth. Calls are cached per trading session and **shared with the Telegram screener**, so
whichever runs second pays only for tickers the first did not fetch.

> Only exactly-measured tickers reach the published board. The broker-derived ranking is a
> *candidate generator* — on 2026-07-24 it pointed the wrong way on 5 of 12 measured names.

### Step 4 — Radar join
```bash
py scripts/build_radar.py
```
Joins flow + news + the screener's `data/history.csv` (if it has run) into
`build/radar-<date>.json` — the four "Where to Look Today" buckets plus the flow board. Missing
inputs degrade to warnings on the page, never a crash.

### Step 5 — Bank Indonesia (always)
WebFetch the BI news-release page in `reference/sources.md`. Capture the latest releases with
titles, dates, and links. These feed the **Bank Indonesia Watch** section; a fresh, market-moving
BI item (e.g. a rate decision) should also be scored into **Top News**.

### Step 6 — Global scan
WebSearch for the last ~24h on: Fed / FOMC / Fed speakers; DXY / US dollar; Trump / tariffs /
US policy affecting markets; US 10-year Treasury yield. Prefer Reuters / Bloomberg / CNBC.
Keep 3–6 items with real links for the **Global Markets** section.

### Step 7 — Score & rank
Apply [reference/ranking-rubric.md](reference/ranking-rubric.md). Take the **Top 10** for Top News.
Route stock/corporate items to Corporate/Emiten, BI items to Bank Indonesia Watch, and global
items to Global Markets. De-duplicate the same story across outlets (keep the best source; the
duplication itself raises its rank). Tickers surfacing in the radar buckets get a ranking boost —
see the rubric.

### Step 8 — Summarize
Write a **one-line English factual summary** for every item. Sectors items already arrive
summarized in English; condense to one line rather than rewriting. Keep the original Bahasa
headline in `headline_original` if useful.

### Step 9 — Build
Write `build/data.json` following the schema in [reference/output-format.md](reference/output-format.md),
then run:

```bash
python scripts/build_html.py
```

This renders `docs/index.html` (today) + `docs/archive/YYYY-MM-DD.html` and regenerates
`docs/archive.html`. On Windows, if `python` is not found use the full path:
`C:/Users/ASUS/AppData/Local/Python/bin/python.exe scripts/build_html.py`.

### Step 10 — Verify
Open `docs/index.html` in the browser preview. Confirm: **6** sections render; Where to Look Today
shows its four buckets; the flow board carries its method note; Top News is numbered and ≤10; Bank
Indonesia Watch is populated; Global Markets has real items; dark theme looks right; Archive link
works. Spot-check 2–3 links open to genuine articles.

### Step 11 — Publish
Show the user a short summary (counts per section + the top 3 headlines). **Ask before pushing.**
Then commit and push; confirm the live Pages URL. See [README.md](README.md) for the git/Pages setup
(the repo and Pages toggle are created once, manually, because `gh` CLI is not installed).

## Output format

Strict template — always these six sections in this order: **Where to Look Today**,
**Net Foreign Flow**, **Top News**, **Corporate / Emiten**, **Bank Indonesia Watch**,
**Global Markets**. Full spec and the `data.json` schema live in
[reference/output-format.md](reference/output-format.md). Do not hand-write HTML — always render via
`scripts/build_html.py` so the layout stays consistent.

The first two sections are rendered from `build/radar-<date>.json`, **not** from `data.json` —
you never author them by hand. If flow data is missing they degrade to a placeholder and the rest
of the brief is unaffected.

## Examples & evals

- What good looks like: [examples/good-output.html](examples/good-output.html) (built from
  [examples/good-data.json](examples/good-data.json)).
- What to avoid: [examples/bad-output.md](examples/bad-output.md).
- Test scenarios and grading rubric: [evals/README.md](evals/README.md).
