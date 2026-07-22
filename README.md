# Indonesia Morning News Brief

A repeatable [Claude Code Skill](https://platform.claude.com/docs/en/docs/agents-and-tools/agent-skills/overview)
that screens Indonesian financial-market news each morning and publishes a ranked, modern-dark
HTML brief for a Jakarta Stock Exchange (IHSG/JCI) portfolio manager — then commits it to
GitHub Pages so it's refreshed daily at one URL, with a dated archive.

**Live site:** `https://andrebenas77.github.io/indonesia-morning-news-brief/`
**Archive:** `https://andrebenas77.github.io/indonesia-morning-news-brief/archive.html`

## What it does
Every run it:
1. Scans Kontan, CNBC Indonesia, Emitennews, Bloomberg Technoz (+ Bank Indonesia) for Indonesian
   market news, and does a lean global scan (Fed, DXY, Trump/policy, US rates & UST 10Y).
2. Ranks the **top ~10 stories worth reading** with a transparent heuristic — most-read ("Terpopuler")
   rail position + cross-outlet coverage + a standing Bank Indonesia priority + market-impact category
   (no outlet exposes literal view counts, so this is the honest proxy).
3. Buckets the rest into **Corporate/Emiten**, **Bank Indonesia Watch**, and **Global Markets**.
4. Translates/summarizes each into one factual English line (pure aggregator — no opinions).
5. Renders the HTML and updates the archive.

## How to run
In Claude Code, just ask — e.g. *"Run my Indonesia market morning brief"* or `/indonesia-morning-news-brief`.
Claude fetches the news, writes `build/data.json`, runs the renderer, shows you a summary, and
(after you confirm) commits and pushes.

To re-render from an existing `build/data.json` without re-fetching:
```bash
python scripts/build_html.py
# Windows, if 'python' isn't on PATH:
# C:/Users/ASUS/AppData/Local/Python/bin/python.exe scripts/build_html.py
```

## How it works
Claude does the judgment (fetch → score → rank → translate → assemble `build/data.json`); a small
standard-library Python script does the deterministic rendering. This keeps the layout identical
day-to-day and cheap in tokens.

```
morning scan (WebFetch/WebSearch) -> build/data.json -> scripts/build_html.py
   -> docs/index.html + docs/archive/YYYY-MM-DD.html + docs/archive.html -> git push -> GitHub Pages
```

## Layout
```
SKILL.md            # instructions Claude follows (the workflow + rules)
README.md           # this file
reference/          # sources.md · ranking-rubric.md · output-format.md
assets/template.html# modern-dark, self-contained HTML shell with {{placeholders}}
scripts/build_html.py
examples/           # good-output.html + good-data.json, and bad-output.md (anti-patterns)
evals/              # 4 scenario tests + a shared grading rubric
docs/               # published site (GitHub Pages serves this folder)
build/              # working data.json (git-ignored)
```

## One-time GitHub setup
`gh` CLI is not installed, so the repo and Pages toggle are created once by hand:
1. On github.com create an **empty public** repo named `indonesia-morning-news-brief`
   (no README, no .gitignore, no license).
2. From this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Indonesia morning news brief skill"
   git branch -M main
   git remote add origin https://github.com/andrebenas77/indonesia-morning-news-brief.git
   git push -u origin main
   ```
3. Repo **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`** → Save.
   The site goes live at the URL above within a minute or two.

After that, each morning's run just commits the updated `docs/` and pushes.

## Notes
- Not investment advice — a public-source news screen. Ranking is a heuristic, not view counts.
- Editable knobs live in `reference/` (add outlets in `sources.md`, tune scoring in
  `ranking-rubric.md`); the look lives in `assets/template.html`.
