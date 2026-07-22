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

| Signal | Why | Points |
|---|---|---|
| **Popularity** — in an outlet's Terpopuler/most-read rail | Reader demand proxy | +5 if rail position 1–3; +3 if 4–10; +1 if 11+ |
| **Cross-outlet frequency** — same story on ≥2 tracked outlets | Editorial importance proxy | +3 per additional outlet (cap +6) |
| **Bank Indonesia** — BI release or BI-policy story | Standing benchmark | +6 (and always include, see below) |
| **Market impact category** (see list) | Direct relevance to positioning | +4 |
| **Freshness** — published today / overnight | Morning brief is about what's new | +1 |

**Market impact categories:** index/IHSG moves, foreign fund flows, major emiten corporate action
(M&A, rights issue, delisting, tender, buyback, earnings surprise, dividend), regulator action
(OJK / IDX / BEI), macro data prints (CPI, GDP, trade balance, FX reserves, PMI), sovereign
rating/yield moves, large IPOs.

`score = popularity + cross_outlet + bank_indonesia + market_impact + freshness`

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
- Duplicate of a story already selected (merge; the duplication boosts the kept item's score).

## Bucketing (after ranking)

- **Top News** — the 10 highest-scoring stories across everything (Indonesia-weighted).
- **Corporate / Emiten** — single-stock / corporate-action stories (Emitennews, CNBC, Kontan) not
  already in Top News. Up to ~8.
- **Bank Indonesia Watch** — the latest BI releases (rate, rupiah, surveys, macroprudential),
  regardless of whether one also appears in Top News. Up to ~6.
- **Global Markets** — Fed, DXY, Trump/policy, US rates/UST 10Y. 3–6 items.

A story may appear in both Top News and its themed bucket (e.g. a BI rate decision in Top News and
Bank Indonesia Watch) — that repetition is intentional and expected.
