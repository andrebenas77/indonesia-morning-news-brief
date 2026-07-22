# Eval 02 — Bank Indonesia rate-decision day

```json
{
  "skill": "indonesia-morning-news-brief",
  "query": "Run my Indonesia market morning brief for today.",
  "conditions": "Bank Indonesia announced a Board of Governors rate decision yesterday/this morning. Multiple outlets are covering it.",
  "expected_behavior": [
    "The BI rate decision is scored into Top News (not only Bank Indonesia Watch), and typically ranks in the top 3 given BI flag + cross-outlet coverage + market impact.",
    "The BI news release itself appears in Bank Indonesia Watch with its date and bi.go.id link.",
    "The rupiah / rate read-through (e.g. an FX or IHSG reaction story) is captured if outlets published one.",
    "The same story appearing in both Top News and BI Watch is acceptable and expected.",
    "Summaries state the decision factually (level and direction) with no rate-path opinion or trade recommendation.",
    "All BI and outlet links are absolute and resolve."
  ]
}
```

This is the scenario that most directly tests the "Bank Indonesia is the benchmark" rule.
