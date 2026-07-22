#!/usr/bin/env python3
"""Render build/data.json into the Indonesia Morning Brief HTML site.

Reads:   build/data.json            (assembled by Claude each morning)
         assets/template.html       (modern-dark page shell with {{PLACEHOLDERS}})
Writes:  docs/index.html            (always = the run's date)
         docs/archive/<date>.html   (dated copy)
         docs/archive/manifest.json (index of all archived days)
         docs/archive.html          (browsable archive, regenerated from the manifest)

Pure standard library. Run from anywhere:
    python scripts/build_html.py [path/to/data.json]
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DEFAULT = ROOT / "build" / "data.json"
TEMPLATE = ROOT / "assets" / "template.html"
DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive"
MANIFEST = ARCHIVE / "manifest.json"

DISCLAIMER = (
    "Compiled from public sources for internal research use; not investment advice. "
    "Ranking is a transparent heuristic (most-read rails + cross-outlet coverage + "
    "Bank Indonesia priority), not view counts. Headlines link to the original publishers."
)


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def safe_url(u) -> str | None:
    """Return an escaped absolute http(s) URL, or None if it isn't one."""
    if not u:
        return None
    u = str(u).strip()
    if not re.match(r"^https?://", u, re.I):
        return None
    return esc(u)


def die(msg: str) -> None:
    print(f"[build_html] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------- rendering ----------

def render_tags(tags) -> str:
    if not tags:
        return ""
    return "".join(f'<span class="tag">{esc(t)}</span>' for t in tags)


def render_headline(item) -> str:
    hl = esc(item.get("headline", "Untitled"))
    url = safe_url(item.get("url"))
    if url:
        return f'<a href="{url}" target="_blank" rel="noopener">{hl}</a>'
    return hl  # no valid link -> render as plain text (do not fabricate one)


def render_story(item, rank=None) -> str:
    # meta line: outlet · time/date · tags
    bits = []
    outlet = item.get("outlet")
    if outlet:
        bits.append(f'<span class="outlet">{esc(outlet)}</span>')
    when = item.get("time") or item.get("date")
    if when:
        bits.append(esc(when))
    meta = ' <span aria-hidden="true">·</span> '.join(bits)
    tags = render_tags(item.get("tags"))
    foot = ""
    if meta or tags:
        foot = f'<div class="foot">{meta}{tags}</div>'
    summary = item.get("summary")
    sum_html = f'<div class="sum">{esc(summary)}</div>' if summary else ""
    rank_html = f'<div class="rank">{esc(rank)}</div>' if rank is not None else ""
    return (
        f'<article class="story">{rank_html}'
        f'<div class="body"><div class="hl">{render_headline(item)}</div>'
        f'{sum_html}{foot}</div></article>'
    )


def render_section(items, ranked=False) -> str:
    if not items:
        return '<div class="empty">No items today.</div>'
    rows = []
    for i, it in enumerate(items, start=1):
        rank = it.get("rank", i) if ranked else None
        rows.append(render_story(it, rank=rank))
    return f'<div class="stories">{"".join(rows)}</div>'


def render_sources(sources) -> str:
    if not sources:
        return ""
    chips = []
    for s in sources:
        outlet = esc(s.get("outlet", "?"))
        status = (s.get("status") or "ok").lower()
        if status == "failed":
            chips.append(f'<span class="chip dim"><span class="s-failed">&#10005;</span> {outlet}</span>')
        else:
            chips.append(f'<span class="chip"><span class="s-ok">&#9679;</span> {outlet}</span>')
    return "".join(chips)


def display_date(data) -> str:
    if data.get("date_display"):
        return esc(data["date_display"])
    try:
        d = datetime.strptime(data["date"], "%Y-%m-%d").date()
        return d.strftime("%A, %d %B %Y")
    except Exception:
        return esc(data.get("date", ""))


def fill(template: str, mapping: dict) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def build_page(data, template, home_href, archive_href) -> str:
    top = data.get("top_news") or []
    corp = data.get("corporate") or []
    bi = data.get("bank_indonesia") or []
    glob = data.get("global") or []
    return fill(template, {
        "DATE_DISPLAY": display_date(data),
        "GENERATED_AT": esc(data.get("generated_at", "")),
        "SOURCES_SCANNED": render_sources(data.get("sources_scanned")),
        "TOP_NEWS": render_section(top, ranked=True),
        "CORPORATE": render_section(corp),
        "BANK_INDONESIA": render_section(bi),
        "GLOBAL": render_section(glob),
        "TOP_NEWS_COUNT": str(len(top)),
        "CORPORATE_COUNT": str(len(corp)),
        "BANK_INDONESIA_COUNT": str(len(bi)),
        "GLOBAL_COUNT": str(len(glob)),
        "DISCLAIMER": esc(DISCLAIMER),
        "HOME_HREF": home_href,
        "ARCHIVE_HREF": archive_href,
    })


def extract_style(template: str) -> str:
    m = re.search(r"<style>.*?</style>", template, re.S)
    return m.group(0) if m else ""


def update_manifest(data) -> list:
    entry = {
        "date": data["date"],
        "date_display": display_date(data),
        "generated_at": data.get("generated_at", ""),
        "top_headline": (data.get("top_news") or [{}])[0].get("headline", ""),
        "counts": {
            "top": len(data.get("top_news") or []),
            "corporate": len(data.get("corporate") or []),
            "bank_indonesia": len(data.get("bank_indonesia") or []),
            "global": len(data.get("global") or []),
        },
    }
    items = []
    if MANIFEST.exists():
        try:
            items = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            items = []
    items = [x for x in items if x.get("date") != entry["date"]]  # upsert
    items.append(entry)
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    MANIFEST.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return items


def render_archive_html(items, style) -> str:
    rows = []
    for e in items:
        d = esc(e.get("date_display", e.get("date", "")))
        hl = esc(e.get("top_headline", ""))
        c = e.get("counts", {})
        counts = f"{c.get('top',0)} top · {c.get('corporate',0)} corp · {c.get('bank_indonesia',0)} BI · {c.get('global',0)} global"
        href = esc(f"archive/{e.get('date','')}.html")
        lead = f'<div class="sum">{hl}</div>' if hl else ""
        rows.append(
            f'<a class="story" href="{href}" style="text-decoration:none">'
            f'<div class="body"><div class="hl">{d}</div>{lead}'
            f'<div class="foot">{esc(counts)}</div></div></a>'
        )
    body = f'<div class="stories">{"".join(rows)}</div>' if rows else '<div class="empty">No archived briefs yet.</div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archive — Indonesia Market Morning Brief</title>
{style}
</head>
<body>
<header class="topbar"><div class="wrap">
  <a class="brand" href="index.html"><span class="dot"></span>IDX Morning Brief <small>· Jakarta markets</small></a>
  <nav class="nav"><a href="index.html">Today</a><a href="archive.html">Archive</a></nav>
</div></header>
<div class="wrap">
  <div class="masthead"><h1>Archive</h1><div class="sub">All past morning briefs, newest first.</div></div>
  <main><section class="block"><h2>Briefs <span class="count">{len(items)}</span></h2>{body}</section></main>
  <footer><div class="disc">{esc(DISCLAIMER)}</div></footer>
</div>
</body>
</html>
"""


def main() -> None:
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DEFAULT
    if not data_path.exists():
        die(f"data file not found: {data_path}. Create build/data.json first "
            f"(see reference/output-format.md).")
    if not TEMPLATE.exists():
        die(f"template not found: {TEMPLATE}")

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"data.json is not valid JSON: {e}")

    if not data.get("date"):
        die("data.json is missing required field 'date' (YYYY-MM-DD).")
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        die(f"'date' must be YYYY-MM-DD, got: {data['date']!r}")

    template = TEMPLATE.read_text(encoding="utf-8")
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    # dated archive page (lives in docs/archive/, so links go up one level)
    dated_html = build_page(data, template, home_href="../index.html", archive_href="../archive.html")
    dated_file = ARCHIVE / f"{data['date']}.html"
    dated_file.write_text(dated_html, encoding="utf-8")

    # today's index (lives in docs/)
    index_html = build_page(data, template, home_href="index.html", archive_href="archive.html")
    (DOCS / "index.html").write_text(index_html, encoding="utf-8")

    # archive index
    items = update_manifest(data)
    (DOCS / "archive.html").write_text(render_archive_html(items, extract_style(template)), encoding="utf-8")

    print(f"[build_html] OK  date={data['date']}  "
          f"top={len(data.get('top_news') or [])} "
          f"corp={len(data.get('corporate') or [])} "
          f"bi={len(data.get('bank_indonesia') or [])} "
          f"global={len(data.get('global') or [])}")
    print(f"[build_html] wrote: docs/index.html, {dated_file.relative_to(ROOT)}, docs/archive.html")


if __name__ == "__main__":
    main()
