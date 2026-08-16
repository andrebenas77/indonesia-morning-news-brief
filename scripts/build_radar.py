#!/usr/bin/env python3
"""Join news + foreign flow + Telegram chatter into the "Where to Look Today" radar.

Reads (all optional — missing inputs degrade, never crash):
    build/flows-<date>.json          from fetch_flows.py
    build/sectors-news-<date>.json   from fetch_sectors_news.py
    <screener>/data/history.csv      from the Telegram screener, if it has run

Writes build/radar-<date>.json, which scripts/build_html.py renders.

On "chatter": this deliberately does NOT recompute the screener's crowd score. That
scoring (decay, heat-z, theme age) is the screener's own framework and lives there; two
competing definitions of "crowded" across two pages would be worse than one simple,
clearly-labelled proxy. Here chatter is just recency-weighted post/channel counts.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # cp1252 consoles choke on Indonesian text
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
WIB = timezone(timedelta(hours=7))

# Env-overridable: the screener sits elsewhere on the VPS. A wrong path here is
# silent — load_chatter() returns {} and the crowded/quiet radar buckets are simply
# always empty.
SCREENER_DIR = Path(os.environ.get(
    "IDX_SCREENER_DIR",
    r"C:\Users\ASUS\.claude\skills\idx-telegram-screener" if sys.platform == "win32"
    else str(Path.home() / "idx-telegram-screener")))
SCREENER_HISTORY = SCREENER_DIR / "data" / "history.csv"

# Thresholds
CHATTER_WINDOW = 5      # sessions of history to weigh
CHATTER_HALFLIFE = 4.0  # matches the screener's decay_halflife_days default
CHATTER_TOP_N = 15      # rank <= this counts as "crowded"
QUIET_MAX_POSTS = 1     # decayed posts at/below this counts as "quiet"
RUN_MIN = 3             # consecutive sessions for a "sustained" flow run
ROWS_PER_BUCKET = 6


def fmt_idr(v) -> str:
    if v is None:
        return "-"
    a = abs(v)
    sign = "+" if v > 0 else ("-" if v < 0 else "")
    if a >= 1e12:
        return f"{sign}{a/1e12:,.2f}T"
    if a >= 1e9:
        return f"{sign}{a/1e9:,.1f}bn"
    if a >= 1e6:
        return f"{sign}{a/1e6:,.0f}m"
    return f"{sign}{a:,.0f}"


def load_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[radar] could not read {path.name}: {e}", file=sys.stderr)
    return None


def load_chatter():
    """Recency-weighted posts/channels per ticker from the screener's raw history."""
    if not SCREENER_HISTORY.exists():
        return {}, 0
    try:
        rows = list(csv.DictReader(open(SCREENER_HISTORY, encoding="utf-8")))
    except Exception as e:
        print(f"[radar] chatter unavailable: {e}", file=sys.stderr)
        return {}, 0
    dates = sorted({r["date"] for r in rows})[-CHATTER_WINDOW:]
    if not dates:
        return {}, 0
    age = {d: (len(dates) - 1 - i) for i, d in enumerate(dates)}
    acc = defaultdict(lambda: {"posts": 0.0, "raw_posts": 0, "channels": 0})
    for r in rows:
        if r["date"] not in age:
            continue
        try:
            posts, chans = int(r["posts"]), int(r["channels"])
        except (ValueError, KeyError):
            continue
        w = 0.5 ** (age[r["date"]] / CHATTER_HALFLIFE)
        t = r["ticker"].strip().upper()
        acc[t]["posts"] += posts * w
        acc[t]["raw_posts"] += posts
        acc[t]["channels"] = max(acc[t]["channels"], chans)
    ranked = sorted(acc.items(), key=lambda kv: kv[1]["posts"], reverse=True)
    for rank, (t, v) in enumerate(ranked, start=1):
        v["rank"] = rank
        v["posts"] = round(v["posts"], 2)
    return dict(ranked), len(dates)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="session/run date YYYY-MM-DD")
    ap.add_argument("--flows", help="explicit path to flows json")
    ap.add_argument("--news", help="explicit path to sectors-news json")
    args = ap.parse_args()

    today = args.date or datetime.now(WIB).strftime("%Y-%m-%d")

    flows = load_json(Path(args.flows)) if args.flows else None
    if flows is None:
        # The flow file is named for the trading session, which may lag the run date.
        cands = sorted(BUILD.glob("flows-*.json"), reverse=True)
        flows = load_json(cands[0]) if cands else None

    news = load_json(Path(args.news)) if args.news else load_json(
        BUILD / f"sectors-news-{today}.json")
    chatter, chatter_sessions = load_chatter()

    out = {
        "date": (flows or {}).get("date") or today,
        "run_date": today,
        "generated_at": datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"),
        "available": False,
        "inputs": {
            "flows": bool(flows and flows.get("available")),
            "news": bool(news and news.get("available")),
            "chatter": bool(chatter),
            "chatter_sessions": chatter_sessions,
        },
        "buckets": [], "market": {}, "warnings": [],
    }

    if not (flows and flows.get("available")):
        out["warnings"].append(
            "Foreign-flow data unavailable — radar cannot be built. "
            "Run scripts/fetch_flows.py, or check SECTORS_API_KEY.")
        return write(out, today)

    def decorate(rows):
        for r in rows:
            r["net_display"] = fmt_idr(r.get("net_idr"))
            r["sum_3_display"] = fmt_idr(r.get("sum_3"))
        return rows

    out["market"] = {
        "top_inflow": decorate(flows["market"].get("top_inflow", [])),
        "top_outflow": decorate(flows["market"].get("top_outflow", [])),
        "method": flows["market"].get("method", ""),
        "brokers_used": flows["market"].get("brokers_used", []),
        "unverified_candidates": flows["market"].get("unverified_candidates", []),
        "notes": flows.get("notes", []),
        "sign_flips": flows.get("sign_flips", []),
    }
    if not news or not news.get("available"):
        out["warnings"].append("Sectors news unavailable — news-linked buckets are empty.")
    if chatter_sessions and chatter_sessions < 3:
        out["warnings"].append(
            f"Only {chatter_sessions} session(s) of Telegram history — chatter buckets "
            f"are provisional until ~1 week of runs accrue.")
    if not chatter:
        out["warnings"].append(
            "No Telegram history found — chatter buckets are empty. Run the screener first.")

    news_counts = (news or {}).get("ticker_counts", {}) or {}
    tickers = flows.get("tickers", {}) or {}

    def row(sym: str, note_bits: list[str]) -> dict:
        e = tickers.get(sym, {})
        ch = chatter.get(sym, {})
        return {
            "symbol": sym,
            "net_idr": e.get("latest_net"),
            "net_display": fmt_idr(e.get("latest_net")),
            "run_sessions": e.get("run_sessions"),
            "run_direction": e.get("run_direction"),
            "sum_3": e.get("sum_3"),
            "sum_3_display": fmt_idr(e.get("sum_3")),
            "inst_net": e.get("inst_net"),
            "inst_display": fmt_idr(e.get("inst_net")) if e.get("inst_net") is not None else None,
            "retail_net": e.get("retail_net"),
            "retail_display": fmt_idr(e.get("retail_net")) if e.get("retail_net") is not None else None,
            "news_count": news_counts.get(sym, 0),
            "chatter_posts": ch.get("posts"),
            "chatter_rank": ch.get("rank"),
            "note": " · ".join(b for b in note_bits if b),
        }

    def sustained(e, direction):
        return (e.get("run_direction") == direction
                and (e.get("run_sessions") or 0) >= RUN_MIN)

    confirms, contradicts, distributed, quiet = [], [], [], []

    for sym, e in tickers.items():
        net = e.get("latest_net")
        if net is None:
            continue
        nc = news_counts.get(sym, 0)
        ch = chatter.get(sym, {})
        crowded = bool(ch.get("rank") and ch["rank"] <= CHATTER_TOP_N)
        is_quiet = (not ch) or (ch.get("posts", 0) <= QUIET_MAX_POSTS)

        if nc and net > 0:
            confirms.append(row(sym, [
                f"{nc} stor{'y' if nc == 1 else 'ies'}",
                f"foreign {fmt_idr(net)}",
                f"{e['run_sessions']} sessions in" if sustained(e, "in") else "",
            ]))
        if nc and net < 0:
            contradicts.append(row(sym, [
                f"{nc} stor{'y' if nc == 1 else 'ies'} but foreign {fmt_idr(net)}",
                f"{e['run_sessions']} sessions out" if sustained(e, "out") else "",
            ]))
        if crowded and (net < 0 or sustained(e, "out")):
            bits = [f"chatter #{ch['rank']}", f"foreign {fmt_idr(net)}"]
            if e.get("inst_net") is not None:
                bits.append(f"inst {fmt_idr(e['inst_net'])}")
            if e.get("retail_net") is not None:
                bits.append(f"retail {fmt_idr(e['retail_net'])}")
            distributed.append(row(sym, bits))
        if is_quiet and sustained(e, "in"):
            quiet.append(row(sym, [
                f"{e['run_sessions']} sessions of inflow",
                f"3-session {fmt_idr(e.get('sum_3'))}",
                "no chatter" if not ch else f"chatter #{ch.get('rank')}",
            ]))

    def pack(key, title, desc, rows, reverse):
        rows.sort(key=lambda r: abs(r["net_idr"] or 0), reverse=reverse)
        return {"key": key, "title": title, "desc": desc,
                "rows": rows[:ROWS_PER_BUCKET], "count": len(rows)}

    out["buckets"] = [
        pack("flow_confirms_news", "Flow confirms the news",
             "In the news and foreign money moving in the same direction.",
             confirms, True),
        pack("flow_contradicts_news", "Flow contradicts the news",
             "In the news but foreigners net sellers — possible sell-the-news fade.",
             contradicts, True),
        pack("crowded_distributed", "Crowded but being distributed",
             "Loud on Telegram while foreign/institutional money exits.",
             distributed, True),
        pack("quiet_accumulation", "Quiet accumulation",
             "Sustained foreign buying with little or no chatter — contrarian watchlist.",
             quiet, True),
    ]
    out["available"] = any(b["rows"] for b in out["buckets"]) or bool(
        out["market"].get("top_inflow"))
    return write(out, today)


def write(out: dict, today: str) -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD / f"radar-{out['date']}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[radar] wrote {path}")
    print(f"[radar] available={out['available']} inputs={out['inputs']}")
    for b in out["buckets"]:
        print(f"[radar]   {b['key']}: {b['count']} (showing {len(b['rows'])})")
    for w in out["warnings"]:
        print(f"[radar] WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
