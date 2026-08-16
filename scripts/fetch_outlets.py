#!/usr/bin/env python3
"""Fetch raw headlines direct from the Indonesian outlets, including the most-read rails.

This is *complementary* to fetch_sectors_news.py, not a fallback for it. Sectors gives
English summaries, symbols[] and the dimension vector, but it aggregates each story into
a single article — so on the Sectors path alone the ranking rubric's "cross-outlet
frequency" signal has no input and always reads 1. This script supplies the raw,
un-aggregated stream those two signals need:

  * cross-outlet frequency — the same story seen at Kontan AND CNBC AND Technoz
  * most-read rail position — which stories Indonesian readers actually opened

Deliberately standard-library only. sectors_client.py needs `requests`; keeping this
script free of it means a broken requests install cannot take down both news paths at
once.

Usage:
    py scripts/fetch_outlets.py
    py scripts/fetch_outlets.py --hours 30 --date 2026-08-16
    py scripts/fetch_outlets.py --only Kontan          # single outlet, for testing
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
WIB = timezone(timedelta(hours=7))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
TIMEOUT = 15
RETRIES = 2

# Ticker matching is a nice-to-have here; the dedup step re-derives it anyway. The
# guarded import keeps a missing `requests` (pulled in transitively by sectors_client)
# from taking this script down with it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from fetch_sectors_news import extract_symbols, load_universe
except Exception as _e:  # pragma: no cover - exercised only when requests is broken
    print(f"[outlets] ticker universe unavailable ({_e}) — symbols off", file=sys.stderr)

    def load_universe() -> dict:
        return {}

    def extract_symbols(item: dict, universe: dict) -> list:
        return []


# --- sources ---------------------------------------------------------------
#
# Every endpoint below was probed live on 2026-08-16. Two notes worth keeping:
#   * www.kontan.co.id/rss returns an HTML feed-directory page, not XML. The real
#     feed is on the investasi. subdomain.
#   * emitennews.com/feed and /rss both return HTTP 500 — no RSS exists at all, so
#     the homepage is parsed instead.
SOURCES = [
    {"outlet": "Kontan", "method": "rss", "rail": "latest",
     "url": "https://investasi.kontan.co.id/rss"},
    {"outlet": "Kontan", "method": "kontan_popular", "rail": "popular",
     "url": "https://www.kontan.co.id/"},
    {"outlet": "CNBC Indonesia", "method": "rss", "rail": "latest",
     "url": "https://www.cnbcindonesia.com/market/rss"},
    {"outlet": "CNBC Indonesia", "method": "cnbc_widget", "rail": "popular",
     "url": "https://www.cnbcindonesia.com/widget/wp_terpopuler?param=10"},
    {"outlet": "Emitennews", "method": "emiten_html", "rail": "latest",
     "url": "https://emitennews.com/"},
    {"outlet": "Bloomberg Technoz", "method": "rss", "rail": "latest",
     "url": "https://www.bloombergtechnoz.com/rss"},
]

# Kontan's Terpopuler is a genuine market signal — a live sample ranked foreign net-buy
# in BBRI/BBCA, 2027 tax policy and the rupiah in its top four. CNBC's rail is site-wide
# and the same sample was a flag ceremony, a toll road, train tickets and an earthquake:
# 0 of 5 market-relevant. So a CNBC rail hit only earns a rail_rank when the story also
# appears in CNBC's /market feed. Without that guard the brief's top story becomes a
# flag ceremony. See reference/ranking-rubric.md.
MARKET_SCOPED_RAIL = {"Kontan": True, "CNBC Indonesia": False, "Emitennews": True}


def http_get(url: str) -> bytes:
    """GET with a browser UA. Retries twice on transient failure.

    Accept-Encoding: identity is deliberate — it costs a little bandwidth and saves
    carrying a gzip branch that would only ever be exercised in production.
    """
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept-Encoding": "identity",
                "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:
            last = e
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def canon_url(u: str) -> str:
    """Merge key: host+path, lowercased, query and trailing slash removed.

    Kontan serves the same article from the RSS and the Terpopuler rail with a
    ?source=home_popular marker, and Sectors links to the original article URL — so
    this one function collapses both the intra-outlet and the Sectors<->outlet dupes
    before any model is involved.
    """
    u = (u or "").strip()
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = u.split("?")[0].split("#")[0]
    return u.rstrip("/").lower()


def mk_id(outlet: str, cu: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", outlet.lower())[:8]
    return f"{slug}-{hashlib.sha256(cu.encode('utf-8')).hexdigest()[:8]}"


def parse_ts(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WIB)
        return dt.astimezone(WIB).isoformat()
    except Exception:
        return None


# --- parsers ---------------------------------------------------------------

def parse_rss(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        title = strip_html((it.findtext("title") or ""))
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        out.append({
            "title": title,
            "url": link,
            "summary": strip_html(it.findtext("description") or "")[:400],
            "timestamp": parse_ts(it.findtext("pubDate")),
            "rail_rank": None,
        })
    return out


KONTAN_RE = re.compile(
    r'<div class="nomer[^"]*"[^>]*>\s*(\d+)\s*</div>.*?<a href="([^"]+)"[^>]*>(.*?)</a>',
    re.S)
KONTAN_HEAD_RE = re.compile(r'<div class="hed-kanan">\s*([^<]+?)\s*</div>')


def parse_kontan_popular(raw: bytes) -> list[dict]:
    """Kontan's most-read rail.

    Careful: the homepage emits *two* elements with id="berita-terpopuler" and
    identical markup. The first is "Terpopuler" (genuine most-read); the second is
    "Jangan Lewatkan" — editorial picks, which restart numbering at 1 and carry
    non-market content (a live sample had an esports result at rank 1). Matching on
    the heading rather than position means a reorder fails loudly instead of quietly
    ranking editorial picks as most-read.
    """
    text = raw.decode("utf-8", "replace")
    block = None
    for m in re.finditer(r'id="berita-terpopuler"', text):
        seg = text[m.start():m.start() + 25000]
        head = KONTAN_HEAD_RE.search(seg)
        if head and head.group(1).strip().lower() == "terpopuler":
            end = seg.find("</ul>")          # one widget only, never the next
            block = seg[:end] if end != -1 else seg
            break
    if block is None:
        raise ValueError("Kontan 'Terpopuler' widget not found — page structure changed")
    out = []
    for rank, url, title in KONTAN_RE.findall(block):
        t = strip_html(title)
        if not t or not url.startswith("http"):
            continue
        out.append({"title": t, "url": url, "summary": "",
                    "timestamp": None, "rail_rank": int(rank)})
    if not out:
        raise ValueError("Kontan Terpopuler matched 0 items — page structure changed")
    return out


CNBC_ITEM_RE = re.compile(r'<a\b[^>]*?\bdtr-idx="(\d+)"[^>]*?>', re.S)
ATTR_RE = re.compile(r'\b(href|dtr-ttl)="([^"]*)"')


def parse_cnbc_widget(raw: bytes) -> list[dict]:
    """The widget returns {"content": "<html fragment>"} — this is what makes CNBC's
    otherwise JS-rendered Most Popular rail reachable from a headless box."""
    payload = json.loads(raw.decode("utf-8", "replace"))
    frag = payload.get("content") or ""
    out = []
    for m in CNBC_ITEM_RE.finditer(frag):
        attrs = dict(ATTR_RE.findall(m.group(0)))
        url, title = attrs.get("href", ""), strip_html(attrs.get("dtr-ttl", ""))
        if not url.startswith("http") or not title:
            continue
        out.append({"title": title, "url": url, "summary": "",
                    "timestamp": None, "rail_rank": int(m.group(1))})
    if not out:
        raise ValueError("CNBC widget matched 0 items — undocumented endpoint changed")
    return out


EMITEN_RE = re.compile(
    r'data-label="home_(updates|trending)_tap"\s+data-attr="[^"]*?\'news_title\':\s*'
    r'\'(.*?)\'\s*\}"\s+href="([^"]+)"', re.S)


def parse_emiten(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", "replace")
    out, rank = [], 0
    for kind, title, url in EMITEN_RE.findall(text):
        t = strip_html(title)
        if not t or not url.startswith("http"):
            continue
        r = None
        if kind == "trending":
            rank += 1
            r = rank
        out.append({"title": t, "url": url, "summary": "",
                    "timestamp": None, "rail_rank": r})
    if not out:
        raise ValueError("Emitennews matched 0 items — page structure changed")
    return out


PARSERS = {
    "rss": parse_rss,
    "kontan_popular": parse_kontan_popular,
    "cnbc_widget": parse_cnbc_widget,
    "emiten_html": parse_emiten,
}


# --- main ------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="run date YYYY-MM-DD (default: today, Asia/Jakarta)")
    ap.add_argument("--hours", type=int, default=30, help="freshness window")
    ap.add_argument("--only", help="restrict to one outlet, for testing")
    ap.add_argument("--out")
    args = ap.parse_args()

    today = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    cutoff = datetime.now(WIB) - timedelta(hours=args.hours)

    out = {
        "date": today,
        "window_start": cutoff.isoformat(),
        "generated_at": datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"),
        "available": False, "sources": [], "items": [],
        "counts": {}, "errors": [],
    }

    universe = load_universe()
    by_canon: dict[str, dict] = {}
    # Populated from CNBC's /market feed, then used to decide whether a CNBC
    # most-popular hit is market news or site-wide noise.
    market_urls: dict[str, set] = {}

    sources = [s for s in SOURCES
               if not args.only or s["outlet"].lower() == args.only.lower()]
    # Latest feeds before popularity rails, so market_urls is populated when the
    # rails are scored. SOURCES is already ordered that way; enforce it anyway.
    sources.sort(key=lambda s: 0 if s["rail"] == "latest" else 1)

    for src in sources:
        rec = {"outlet": src["outlet"], "method": src["method"], "url": src["url"],
               "rail": src["rail"], "status": "ok", "count": 0, "error": None}
        try:
            rows = PARSERS[src["method"]](http_get(src["url"]))
            kept = 0
            for row in rows:
                cu = canon_url(row["url"])
                if not cu:
                    continue

                # Freshness: only judge items that carry a timestamp. Rail items
                # never do, and dropping them would discard the whole signal.
                ts = row.get("timestamp")
                if ts:
                    try:
                        if datetime.fromisoformat(ts) < cutoff:
                            continue
                    except Exception:
                        pass

                rank = row.get("rail_rank")
                if rank is not None and not MARKET_SCOPED_RAIL.get(src["outlet"], True):
                    # Site-wide rail: only counts if the story is also in this
                    # outlet's market feed. Otherwise keep the item but score it null.
                    if cu not in market_urls.get(src["outlet"], set()):
                        rank = None

                if cu in by_canon:
                    # Same article from this outlet's other rail — merge, don't duplicate.
                    prev = by_canon[cu]
                    if rank is not None and (prev.get("rail_rank") is None
                                             or rank < prev["rail_rank"]):
                        prev["rail_rank"] = rank
                        prev["rail"] = src["rail"]
                    if not prev.get("summary") and row.get("summary"):
                        prev["summary"] = row["summary"]
                    if not prev.get("timestamp") and row.get("timestamp"):
                        prev["timestamp"] = row["timestamp"]
                    continue

                item = {
                    "id": mk_id(src["outlet"], cu),
                    "outlet": src["outlet"],
                    "title": row["title"],
                    "url": row["url"],
                    "canon_url": cu,
                    "summary": row.get("summary") or "",
                    "timestamp": ts,
                    "time_confidence": "pubdate" if ts else "listing-order",
                    "rail": src["rail"] if rank is not None else "latest",
                    "rail_rank": rank,
                    "rail_scope": ("market" if MARKET_SCOPED_RAIL.get(src["outlet"], True)
                                   else "site-wide"),
                    "symbols": extract_symbols({"title": row["title"]}, universe),
                    "method": src["method"],
                }
                by_canon[cu] = item
                if src["rail"] == "latest":
                    market_urls.setdefault(src["outlet"], set()).add(cu)
                kept += 1
            rec["count"] = kept
        except Exception as e:
            rec["status"] = "failed"
            rec["error"] = f"{type(e).__name__}: {e}"
            out["errors"].append(f"{src['outlet']}/{src['method']}: {rec['error']}")
        out["sources"].append(rec)

    items = list(by_canon.values())
    items.sort(key=lambda r: (r.get("rail_rank") or 99, r.get("timestamp") or ""),
               reverse=False)
    out["items"] = items

    by_outlet = Counter(i["outlet"] for i in items)
    out["counts"] = {
        "items": len(items),
        "by_outlet": dict(by_outlet),
        "with_rail_rank": sum(1 for i in items if i.get("rail_rank") is not None),
        "sources_ok": sum(1 for s in out["sources"] if s["status"] == "ok"),
        "sources_failed": sum(1 for s in out["sources"] if s["status"] == "failed"),
    }
    out["available"] = len(items) > 0

    BUILD.mkdir(parents=True, exist_ok=True)
    path = Path(args.out) if args.out else BUILD / f"outlets-{today}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[outlets] wrote {path}")
    print(f"[outlets] {out['counts']} available={out['available']}")
    for s in out["sources"]:
        flag = "ok " if s["status"] == "ok" else "FAIL"
        print(f"[outlets]   {flag} {s['outlet']:<18} {s['method']:<15} n={s['count']}"
              + (f"  {s['error']}" if s["error"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
