# Eval 04 — FOMC / big global move overnight

```json
{
  "skill": "indonesia-morning-news-brief",
  "query": "Run my Indonesia market morning brief for today.",
  "conditions": "The Fed announced a decision overnight (US time) and global markets moved; DXY and UST 10Y repriced.",
  "expected_behavior": [
    "Global Markets leads with the Fed outcome and includes DXY and US 10Y context, each with a real link (Reuters/Bloomberg/CNBC/Trading Economics).",
    "The global figures (rate level, DXY level, yield) match what was actually fetched — no invented numbers.",
    "If Indonesian outlets published a local read-through (rupiah/IHSG reaction to the Fed), it is captured in Top News.",
    "Indonesia coverage is still the core of the brief; global is the supporting section, not the whole page.",
    "Trump/policy item included if relevant that day; otherwise the three other global themes suffice.",
    "Summaries are factual, no macro forecasting or positioning advice."
  ]
}
```

Tests that the global scan adds real, sourced context without hijacking the Indonesia focus.
