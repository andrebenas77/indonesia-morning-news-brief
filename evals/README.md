# Evals

Scenario tests for the `indonesia-morning-news-brief` skill. There is no built-in runner —
run each scenario by invoking the skill with the given prompt/conditions and grade the result
against the rubric below (and the scenario's own `expected_behavior`).

## Contents
- How to run
- Shared grading rubric
- Scenarios

## How to run
1. Start a fresh session with the skill available.
2. Give it the scenario's `query` (simulate any stated conditions, e.g. a downed source).
3. Inspect `build/data.json`, the console output of `scripts/build_html.py`, and the rendered
   `docs/index.html`.
4. Grade against the shared rubric + the scenario's `expected_behavior`. Any "no" is a fail.

## Shared grading rubric (applies to every run)
- [ ] **No fabrication** — every headline, URL, outlet, and timestamp was actually fetched this run.
- [ ] **Links resolve** — spot-check 3 links; each opens a real article on the stated outlet.
- [ ] **Links absolute** — every `url` starts with `http(s)://`.
- [ ] **English** — display headlines and summaries are English; aggregator voice (no opinions).
- [ ] **Bank Indonesia present** — if BI had any recent release, it appears (Watch, and Top News if market-moving).
- [ ] **Ranking follows rubric** — Top News reflects popularity + cross-outlet + BI + market-impact.
- [ ] **Structure** — four sections in order; Top News ≤ 10 and numbered.
- [ ] **Transparency** — every attempted outlet is in `sources_scanned` with ok/failed.
- [ ] **Build valid** — `build_html.py` exits 0; writes `docs/index.html`, dated archive, `docs/archive.html`.
- [ ] **Renders** — page opens with all sections visible; archive link works.

## Scenarios
- [eval-01-standard-weekday.md](eval-01-standard-weekday.md)
- [eval-02-bi-rate-decision.md](eval-02-bi-rate-decision.md)
- [eval-03-source-failure.md](eval-03-source-failure.md)
- [eval-04-fomc-overnight.md](eval-04-fomc-overnight.md)
