# Eval 03 — A source fails to load

```json
{
  "skill": "indonesia-morning-news-brief",
  "query": "Run my Indonesia market morning brief for today.",
  "conditions": "One primary outlet is unreachable (e.g. Bloomberg Technoz returns ECONNRESET/403/timeout on every attempt).",
  "expected_behavior": [
    "The skill retries the failing source at most once, then marks it status: failed in sources_scanned.",
    "The brief is still produced from the remaining reachable outlets.",
    "NO headlines are fabricated to compensate for the missing source; the Top-News count may be < 10 if needed.",
    "The failed outlet is visibly flagged (a muted 'unavailable today' chip), never silently dropped.",
    "Bank Indonesia is still fetched and present (it is a different host from the failed outlet).",
    "build_html.py still exits 0 and renders a valid page."
  ]
}
```

Tests graceful degradation and the anti-fabrication rule under partial data. The verification run on
2026-07-22 exercised this for real (Bloomberg Technoz threw ECONNRESET, then recovered on retry).
