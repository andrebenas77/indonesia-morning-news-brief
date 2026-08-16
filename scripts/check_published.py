#!/usr/bin/env python3
"""External watchdog: did today's brief actually reach the live site?

This is the only check that can catch "the timer never fired at all" — which is
exactly the failure this repo suffered for twelve weekdays in August 2026, when the
desktop scheduler silently stopped running and nothing anywhere noticed. An in-run
verification block cannot detect a run that never happened, by construction. So this
runs as its OWN systemd unit at 09:30 and asks the published page, not the server.

    python3 scripts/check_published.py            # print verdict, exit 0/1
    python3 scripts/check_published.py --notify   # also Telegram on failure

Standard library only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIB = timezone(timedelta(hours=7))
SITE = "https://andrebenas77.github.io/indonesia-morning-news-brief/"
UA = "idx-brief-watchdog/1.0"


def fetch(url: str, timeout: int = 30) -> str:
    # Pages caches aggressively; bust it so we are not reassured by a stale copy.
    bust = f"{url}?cb={datetime.now(WIB).strftime('%Y%m%d%H%M%S')}"
    req = urllib.request.Request(bust, headers={
        "User-Agent": UA, "Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="date to expect (default: today, Asia/Jakarta)")
    ap.add_argument("--url", default=SITE)
    ap.add_argument("--notify", action="store_true",
                    help="send a Telegram alert when the check fails")
    args = ap.parse_args()

    now = datetime.now(WIB)
    date = args.date or now.strftime("%Y-%m-%d")

    if not args.date and now.weekday() > 4:
        print(f"[watchdog] {now.strftime('%A')} — IDX closed, nothing expected")
        return 0

    problem = None
    try:
        html = fetch(args.url)
        # Read the brief-date meta tag specifically. A bare date search would match
        # the flow board's ISO date, which is keyed to the trading session and
        # legitimately lags the run date — that would alert every single day.
        import re
        m = re.search(r'name=["\']brief-date["\']\s+content=["\'](\d{4}-\d{2}-\d{2})["\']',
                      html)
        if not m:
            problem = ("the live page has no brief-date meta tag — it predates the "
                       "2026-08 rebuild, or the template was not applied")
        elif m.group(1) != date:
            problem = (f"the live brief is dated {m.group(1)}, expected {date}")
        else:
            print(f"[watchdog] ok — {args.url} is serving {date}")
    except urllib.error.HTTPError as e:
        problem = f"HTTP {e.code} fetching {args.url}"
    except Exception as e:
        problem = f"{type(e).__name__} fetching {args.url}: {e}"

    if not problem:
        return 0

    print(f"[watchdog] FAIL: {problem}", file=sys.stderr)
    if args.notify:
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "notify_telegram.py"),
                 "--title", f"IDX brief MISSING — {date}",
                 "--text", f"The 07:45 run did not publish.\n\n{problem}\n\n"
                           f"Check:  systemctl status idx-brief.service\n"
                           f"Log:    ~/logs/brief-{date}.log"],
                check=False, timeout=60)
        except Exception as e:
            print(f"[watchdog] notify failed: {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
