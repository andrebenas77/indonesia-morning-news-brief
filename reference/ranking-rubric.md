# Ranking rubric — "worth reading"

No Indonesian outlet exposes literal view counts, so "worth reading" is a **transparent
heuristic**, not a number. A story is a Top-News candidate if it meets **≥1 signal** below,
then candidates are ordered by total score. Take the **Top 10**.

## Contents
- Signals & scoring
- Tie-breakers
- Include / exclude rules
- Bucketing

## Signals & scoring

All of these are **pre-computed** in `build/dedup-<date>.json`. Read them off the cluster;
do not re-derive them by eye.

| Signal | Why | Points |
|---|---|---|
| **Popularity** — `best_rail_rank` on the cluster | Reader demand proxy | +5 if 1–3; +3 if 4–10; +1 if 11+ |
| **Cross-outlet frequency** — `cross_outlet_count` | Editorial importance proxy | +3 per additional outlet (cap +6) |
| **Bank Indonesia** — BI release or BI-policy story | Standing benchmark | +6 (and always include, see below) |
| **Market impact category** (see list) | Direct relevance to positioning | +4 |
| **Freshness** — published today / overnight | Morning brief is about what's new | +1 |
| **Dimension breadth** — Sectors' 8-axis `dimension` vector on the article | Touches many analytical angles (valuation, financials, ownership…) | +2 if `dim_score` ≥ 4; +1 if 2–3 |
| **Flow confirmation** — a ticker in the story appears in today's `radar-<date>.json` buckets | Money actually moved on it | +3 if in **Flow contradicts the news**; +2 if in **Flow confirms the news** |
| **Day-over-day repeat** — `repeat_days` | Third-morning churn is not news | **−4** if `repeat_days == 1`; **−6** if ≥ 2 |

**On `cross_outlet_count`:** until August 2026 this signal had no input at all. The Sectors
API returns one pre-aggregated article per story, so the count was always 1 and the rule
below was dead. `scripts/fetch_outlets.py` now fetches the outlets raw alongside Sectors and
`scripts/dedup_news.py` clusters them, so the number is real. A count of 4 means four
distinct newsrooms independently thought the story was worth running.

**On `best_rail_rank` — the rails are not equivalent, and this matters.** Kontan's
*Terpopuler* is genuine most-read and is market-relevant in practice. CNBC Indonesia's
*Most Popular* is **site-wide**: a live sample ranked a flag ceremony, a toll road, train
tickets, a death and an earthquake in its top five — zero market stories. So a CNBC rail
hit only earns a `rail_rank` when the story also appears in CNBC's `/market` feed;
otherwise `fetch_outlets.py` records `rail_rank: null`. Two consequences:
- `null` means *"no rail carried it"*, **not** *"readers ignored it"*. Never score it as
  unpopular. Check `sources[].status` in `build/outlets-<date>.json` — a `failed` rail
  means the signal is missing, not negative.
- Do not restore CNBC's rail as a direct input without re-checking what is actually in it.

**On the repeat penalty:** it is a *penalty a human overrides*, never a filter. Ordinary
"IHSG naik" churn deserves suppression; a policy story on its third morning is often the
opposite — that is the story developing. `dedup_news.py` exempts
`category == "bank_indonesia"` from the penalty entirely. If you find yourself wanting to
drop repeats outright, don't.

**On `dimension`:** it is a *relevance breadth* score, not a direction. A high `dim_score` means the
article touches several analytical axes — never read it as bullish or bearish.

**On flow confirmation:** *contradicts* scores higher than *confirms* on purpose. A stock rising on
good press while foreigners sell is more decision-relevant than one where price, story and flow all
agree.

**Market impact categories:** index/IHSG moves, foreign fund flows, major emiten corporate action
(M&A, rights issue, delisting, tender, buyback, earnings surprise, dividend), regulator action
(OJK / IDX / BEI), macro data prints (CPI, GDP, trade balance, FX reserves, PMI), sovereign
rating/yield moves, large IPOs.

```
score = popularity + cross_outlet + bank_indonesia + market_impact
      + freshness + dimension + flow − repeat_penalty
```

## Tie-breakers
1. Bank Indonesia / macro-policy over single-stock news.
2. Higher Terpopuler rail position.
3. Broader index/market impact over narrow single-name impact.
4. More recent timestamp.

## Include / exclude rules

**Always include** (if present this run): any Bank Indonesia release or BI-policy story.

**Exclude from Top News:**
- Lifestyle, sport, celebrity, entertainment, horoscopes, tech-gadget reviews.
- Non-market politics (unless it's concrete policy affecting markets — fiscal, tax, trade, SOE).
- Advertorials / sponsored content.
- Generic daily clickbait like "rekomendasi saham hari ini" / "prediksi IHSG hari ini" — unless it
  carries genuinely notable, specific news (then keep, ranked on merit).
- Any cluster with `category == "noise"` in `build/dedup-<date>.json`. That bucket is the
  dedup pass's own read of the exclusions above (lifestyle, sport, crime, human interest,
  disasters without a named market impact, advertorial, generic clickbait). It is advisory
  and occasionally wrong in the safe direction — if a `noise` item is obviously a real
  market story, overrule it and say so.
- Duplicates are already merged into one cluster by `dedup_news.py`; you should not be
  seeing the same story twice. If you do, the clustering missed it — merge by hand and
  add the extra outlet to the count.

## Bucketing (after ranking)

- **Top News** — the 10 highest-scoring stories across everything (Indonesia-weighted).
- **Corporate / Emiten** — single-stock / corporate-action stories (Emitennews, CNBC, Kontan) not
  already in Top News. Up to ~8.
- **Bank Indonesia Watch** — the latest BI releases (rate, rupiah, surveys, macroprudential),
  regardless of whether one also appears in Top News. Up to ~6.
- **Global Markets** — Fed, DXY, Trump/policy, US rates/UST 10Y. 3–6 items.

A story may appear in both Top News and its themed bucket (e.g. a BI rate decision in Top News and
Bank Indonesia Watch) — that repetition is intentional and expected.
