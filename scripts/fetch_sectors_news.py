#!/usr/bin/env python3
"""Pull IDX news, insider/institutional filings and suspensions from the Sectors API.

Replaces the Kontan/CNBC/Emitennews/Technoz WebFetch scrape for *corporate* news —
Sectors already summarizes those outlets in English and attaches tickers, sectors and
tags. It carries no Bank Indonesia releases and no global macro, so those two scans
stay on WebFetch (see reference/sources.md).

Writes build/sectors-news-<date>.json, including the union of tickers mentioned — that
list is what feeds `fetch_flows.py --tickers`.

Usage:
    py scripts/fetch_sectors_news.py
    py scripts/fetch_sectors_news.py --days 2 --pages 3
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sectors_client import SectorsClient, normalize_tag, strip_jk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
WIB = timezone(timedelta(hours=7))

# The screener already curates the IDX ticker universe; reuse it for fallback matching
# rather than maintaining a second list. Optional — absent means no fallback.
#
# The two skills live in different places on the dev box and on the VPS, so the path is
# env-overridable. Getting this wrong is silent: load_universe() just returns {} and
# ticker matching quietly stops working.
SCREENER_DIR = Path(os.environ.get(
    "IDX_SCREENER_DIR",
    r"C:\Users\ASUS\.claude\skills\idx-telegram-screener" if sys.platform == "win32"
    else str(Path.home() / "idx-telegram-screener")))
SCREENER_TICKERS = SCREENER_DIR / "reference" / "tickers.csv"

PAGE_LIMIT = 30  # API max


def load_universe() -> dict[str, str]:
    """{TICKER: company name} from the screener's curated list, if available."""
    out: dict[str, str] = {}
    try:
        if SCREENER_TICKERS.exists():
            with open(SCREENER_TICKERS, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    t = (r.get("ticker") or "").strip().upper()
                    if t:
                        out[t] = (r.get("company") or "").strip()
    except Exception as e:
        print(f"[news] ticker universe unavailable ({e}) — fallback matching off",
              file=sys.stderr)
    return out


def dim_score(dimension: dict | None) -> int:
    """Sum of the 8-axis relevance vector Sectors attaches to each article.

    Used as a ranking prior, not a verdict — a high score means the article touches many
    analytical dimensions (valuation, financials, ownership...), not that it is bullish.
    """
    if not isinstance(dimension, dict):
        return 0
    return sum(int(v or 0) for v in dimension.values() if isinstance(v, (int, float)))


def extract_symbols(item: dict, universe: dict[str, str]) -> list[str]:
    """Tickers for an article. `symbols[]` is authoritative but sometimes empty, so fall
    back to scanning the title for a known ticker code or company name."""
    syms = [strip_jk(s) for s in (item.get("symbols") or []) if s]
    syms = [s for s in syms if s]
    if syms:
        return sorted(set(syms))
    if not universe:
        return []
    title = (item.get("title") or "")
    found = set()
    for tok in re.findall(r"\b[A-Z]{4}\b", title):
        if tok in universe:
            found.add(tok)
    low = title.lower()
    for tk, company in universe.items():
        if company and len(company) >= 6 and company.lower() in low:
            found.add(tk)
    return sorted(found)


def norm_tags(tags) -> list[str]:
    seen, out = set(), []
    for t in tags or []:
        n = normalize_tag(t)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def fetch_news(c: SectorsClient, start: str, pages: int, universe) -> list[dict]:
    items, offset = [], 0
    for _ in range(pages):
        page = c.news(start=start, limit=PAGE_LIMIT, offset=offset)
        if not page:
            break
        for it in page.get("results") or []:
            items.append({
                "title": it.get("title"),
                "summary": it.get("body"),
                "url": it.get("source"),
                "thumbnail": it.get("thumbnail"),
                "timestamp": it.get("timestamp"),
                "sector": it.get("sector"),
                "sub_sector": it.get("sub_sector") or [],
                "tags": norm_tags(it.get("tags")),
                "symbols": extract_symbols(it, universe),
                "dimension": it.get("dimension") or {},
                "dim_score": dim_score(it.get("dimension")),
            })
        pg = page.get("pagination") or {}
        if not pg.get("has_next"):
            break
        offset = pg.get("next_offset") or (offset + PAGE_LIMIT)
    return items


def fetch_filings(c: SectorsClient, start: str) -> list[dict]:
    """Insider + institutional transactions.

    Direction comes from `transaction_type` and `amount_transaction` only.
    `share_percentage_transaction` is a naive before-minus-after subtraction that inverts
    across dilution events (observed: a 60m-share BUY rendering as 30% -> 16.99%), so it
    is deliberately not read here.
    """
    out = []
    for holder in ("institution", "insider"):
        page = c.filings(start=start, holder_type=holder, limit=PAGE_LIMIT)
        if not page:
            continue
        for it in page.get("results") or []:
            out.append({
                "title": it.get("title"),
                "summary": it.get("body"),
                "url": it.get("source"),
                "timestamp": it.get("timestamp"),
                "symbol": strip_jk(it.get("symbol")),
                "sector": it.get("sector"),
                "sub_sector": it.get("sub_sector"),
                "tags": norm_tags(it.get("tags")),
                "holder_type": it.get("holder_type"),
                "holder_name": it.get("holder_name"),
                "transaction_type": it.get("transaction_type"),
                "amount_transaction": it.get("amount_transaction"),
                "transaction_value": it.get("transaction_value"),
                "price": it.get("price"),
                "fills": it.get("price_transaction") or [],
            })
    out.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return out


def fetch_suspensions(c: SectorsClient, start: str) -> list[dict]:
    page = c.suspensions(start=start, limit=10)
    if not page:
        return []
    return [{
        "symbol": strip_jk(it.get("symbol")),
        "date": it.get("suspension_date") or it.get("date"),
        "reason": it.get("reason") or it.get("title"),
        "url": it.get("source") or it.get("url"),
    } for it in (page.get("results") or [])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="run date YYYY-MM-DD (default: today, Asia/Jakarta)")
    ap.add_argument("--days", type=int, default=1, help="lookback window in days")
    ap.add_argument("--pages", type=int, default=3, help="news pages (30 items each)")
    ap.add_argument("--out")
    args = ap.parse_args()

    today = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    start = (datetime.strptime(today, "%Y-%m-%d")
             - timedelta(days=args.days)).strftime("%Y-%m-%d")

    c = SectorsClient(date=today)
    out = {
        "date": today, "window_start": start,
        "generated_at": datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"),
        "available": False, "news": [], "filings": [], "suspensions": [],
        "tickers": [], "ticker_counts": {}, "errors": [],
    }

    if not c.enabled:
        out["errors"].append("SECTORS_API_KEY not set — Sectors news unavailable")
        return write(out, args, c)

    universe = load_universe()
    out["news"] = fetch_news(c, start, args.pages, universe)
    out["filings"] = fetch_filings(c, start)
    out["suspensions"] = fetch_suspensions(c, start)

    counts: Counter = Counter()
    for it in out["news"]:
        counts.update(it["symbols"])
    for f in out["filings"]:
        if f.get("symbol"):
            counts[f["symbol"]] += 1
    out["ticker_counts"] = dict(counts.most_common())
    out["tickers"] = [t for t, _ in counts.most_common()]
    out["counts"] = {"news": len(out["news"]), "filings": len(out["filings"]),
                     "suspensions": len(out["suspensions"]),
                     "tickers": len(out["tickers"])}
    out["available"] = bool(out["news"] or out["filings"])
    return write(out, args, c)


def write(out: dict, args, c: SectorsClient) -> int:
    out["credits_used"] = c.credits
    out["cache_hits"] = c.cache_hits
    out["errors"].extend(c.errors)
    BUILD.mkdir(parents=True, exist_ok=True)
    path = Path(args.out) if args.out else BUILD / f"sectors-news-{out['date']}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[news] wrote {path}")
    print(f"[news] {out.get('counts')} available={out['available']} "
          f"credits={c.credits} cache_hits={c.cache_hits}")
    if out["tickers"]:
        print(f"[news] tickers: {','.join(out['tickers'][:20])}")
    if out["errors"]:
        print(f"[news] errors: {out['errors'][:3]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
