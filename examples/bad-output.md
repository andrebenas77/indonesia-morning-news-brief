# Anti-patterns — what a bad brief looks like

Each item is a real failure mode to avoid. Compare against `good-output.html` /
`good-data.json`.

## 1. Fabricated headline or link (the worst failure)
> ❌ `{"headline": "IHSG jumps 3% on foreign buying", "url": "https://www.kontan.co.id/news/ihsg-jumps-3-percent"}`

The URL was guessed to look plausible; it 404s and the headline was never fetched. **Only ever
include items actually retrieved this run.** If you didn't fetch it, it doesn't exist. When in
doubt about a link, drop the item.

## 2. Padding to hit 10 with filler
> ❌ Two sources failed to load, so five generic "prediksi IHSG hari ini" clickbait items were added
> to reach a Top-10.

Fewer real, high-signal stories beats a padded list. Note failed sources in `sources_scanned` and
ship what you actually have.

## 3. Missing Bank Indonesia
> ❌ BI published a rate decision this morning, but the brief has no Bank Indonesia Watch items.

Bank Indonesia is the standing benchmark. If BI has any recent release, it MUST appear (and a
market-moving BI item also belongs in Top News).

## 4. Editorializing (this is a pure aggregator)
> ❌ `"summary": "BI's hold is a dovish signal — banks look attractive here; accumulate BBRI on dips."`

No views, no recommendations, no "this matters because." State what happened in one factual line:
> ✅ `"summary": "Bank Indonesia kept its policy rate unchanged at 5.75%."`

## 5. Bahasa left untranslated
> ❌ `"headline": "IHSG Melemah 0,39% ke 6.315 pada Sesi I"`

Display headlines are English. Keep the original in `headline_original` if useful, but the shown
headline must be English:
> ✅ `"headline": "IHSG falls 0.39% to 6,315 in the morning session"`

## 6. Lifestyle / off-topic clutter
> ❌ Top News includes "10 richest crazy-rich Indonesians in 2026" or a football transfer story.

Exclude lifestyle, sport, celebrity, and non-market politics. See the exclude list in
`reference/ranking-rubric.md`.

## 7. Relative or broken links
> ❌ `"url": "/market/2026072200-17-999/"` (relative) or `"url": "kontan.co.id/news/..."` (no scheme)

Links must be absolute and start with `http://` or `https://`. The renderer drops the hyperlink for
anything else, leaving a dead headline.

## 8. Hand-writing HTML instead of using the script
> ❌ Editing `docs/index.html` directly, or writing bespoke `<div>`s per story.

Always produce `build/data.json` and run `scripts/build_html.py`. Hand-edited HTML drifts from the
template, breaks the archive manifest, and won't match past days.

## 9. Wrong or missing date
> ❌ `data.json` has no `date`, or `date: "22/07/2026"`.

`date` is required and must be ISO `YYYY-MM-DD` (Asia/Jakarta) — it names the archive file. The
build script exits with an error otherwise.

## 10. Silent source failure
> ❌ Bloomberg Technoz timed out and was simply omitted with no trace.

Record every attempted outlet in `sources_scanned` with `status: "ok"` or `"failed"`. Transparency
about coverage is part of the product.
