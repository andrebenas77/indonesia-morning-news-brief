# Eval 01 — Standard weekday

```json
{
  "skill": "indonesia-morning-news-brief",
  "query": "Run my Indonesia market morning brief for today.",
  "conditions": "Normal trading weekday. All sources reachable.",
  "expected_behavior": [
    "Scans all five sources (Kontan, CNBC Indonesia, Emitennews, Bloomberg Technoz, Bank Indonesia); each appears in sources_scanned as ok.",
    "Top News has up to 10 ranked items, numbered 1..N, ordered by the ranking rubric.",
    "Bank Indonesia Watch is populated from the latest BI releases.",
    "Global Markets has 3-6 items covering Fed, DXY, Trump/policy, and US 10Y — each with a real link.",
    "Corporate/Emiten holds single-stock items not already in Top News.",
    "Every headline is English with a one-line factual summary and an absolute link that resolves.",
    "build/data.json is written, scripts/build_html.py exits 0, and docs/index.html + docs/archive/<date>.html + docs/archive.html are produced.",
    "No fabricated headlines or links; nothing padded to force a count."
  ]
}
```

Grade against this list plus the shared rubric in `README.md`. `examples/good-output.html` is a
passing reference for this scenario.
