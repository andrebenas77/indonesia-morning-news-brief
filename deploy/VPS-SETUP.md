# VPS setup — Indonesia Morning News Brief

Runs the brief unattended at **07:45 WIB, Mon–Fri**, on the same Biznet box as the
Telegram screener.

## Why the VPS at all

The Claude Code desktop scheduler only executes while the app is open. Between
2026-08-04 and 2026-08-16 the task fired seven times — at 05:21, 05:52, 06:39, 07:38,
never at its 08:30 cron — because each was a *catch-up run at app launch*. Every one
died mid-tool-call when the app closed. No error, no log, no notification, and twelve
weekdays with no published brief. systemd does not have that failure mode, and the
watchdog below catches the ones it might.

## Prerequisites

The screener's `deploy/setup.sh` must have run first. It provides the SSH key,
Asia/Jakarta clock, 4 GB swap, `python3`/`git`/`jq`, and Claude Code. This setup
detects and skips all of that.

## Install

```bash
curl -sL https://raw.githubusercontent.com/andrebenas77/indonesia-morning-news-brief/main/deploy/setup.sh | bash
```

Then the three manual steps it prints: deploy key, `/etc/idx-brief.env`, timers.

## Schedule and the shared lock

| Unit | When | Persistent |
|---|---|---|
| `idx-screener.timer` | 07:00 WIB Mon–Fri | true |
| (trade plan) | 07:15 | — |
| `idx-brief.timer` | **07:45 WIB Mon–Fri** | true |
| `idx-brief-watchdog.timer` | 09:30 WIB Mon–Fri | **false** |

07:45 is chosen so the Sectors day-cache is already warm from the 07:00 screener run
(the news and flow fetches then cost almost nothing) and the screener's
`data/history.csv` is fresh, so `build_radar.py`'s chatter buckets populate.

**The lock is load-bearing.** This box has 2 GB of RAM and both runs launch Claude
Code. `run_brief.sh` takes `/tmp/idx-screener.lock` with `flock -w 1200` (wait up to
20 min); `run_daily.sh` already takes the same lock with `flock -n` (fail fast). So a
delayed screener makes the brief wait, and the brief can never block the screener.
This requires `PrivateTmp=false` in the unit — with a private `/tmp` each service gets
its own lock file and the coordination silently does nothing.

`Persistent=true` on the brief timer is safe **only** because `run_brief.sh` exits
early when `date +%u > 5`. Without that guard a Saturday catch-up would overwrite
`docs/index.html` with a weekend brief. A Sunday catch-up on 2026-08-16 came within
seconds of doing exactly that.

## Environment

`/etc/idx-screener.env` (existing, root:root 600) — shared:

```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…
SECTORS_API_KEY=…
TELEGRAM_BOT_TOKEN=…
TELEGRAM_CHAT_ID=…
SECTORS_CACHE_DIR=/home/screener/.cache/sectors     # add this
```

`/etc/idx-brief.env` (new, root:root 600):

```
DEEPSEEK_API_KEY=sk-…
SECTORS_CACHE_DIR=/home/screener/.cache/sectors
IDX_SCREENER_DIR=/home/screener/idx-telegram-screener
```

Both are listed as `EnvironmentFile=` without a `-` prefix, so a missing file fails the
unit loudly rather than starting a run that cannot work.

`IDX_SCREENER_DIR` and `SECTORS_CACHE_DIR` are not optional niceties. Their three
call-sites (`sectors_client.py`, `fetch_sectors_news.py`, `build_radar.py`) all fail
**silently** on Linux if left at their Windows defaults: a garbage cache directory in
the repo, ticker matching quietly off, and permanently empty radar buckets.

Claude Code authenticates from `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token` on your
PC, valid ~1 year). Its expiry looks like `claude` exiting within seconds — caught by
the `DUR < 90s` FATAL check and reported to Telegram.

## Verify before trusting the timer

```bash
cd ~/indonesia-morning-news-brief
```

**1. Dry run** — everything including Claude, but no commit, no push, no store commit:

```bash
./scripts/run_brief.sh --trigger manual --dry-run
```

Expect a `[DRY RUN]`-prefixed Telegram message, which also proves the notify path.

**2. Memory under load** — the decisive test on a 2 GB box. In a second SSH session run
`watch -n2 free -m` while the brief runs. Healthy: headroom remains, swap near idle.
Unhealthy: swap climbing steadily, run past ~20 min, or an OOM kill in `journalctl -k`
→ resize the box.

**3. Prove the lock serialises**, rather than assuming it:

```bash
sudo systemctl start idx-screener.service      # then immediately:
./scripts/run_brief.sh --trigger manual --dry-run
```

The brief should log that it is waiting, then proceed once the screener finishes — not
run concurrently.

**4. Live run**:

```bash
sudo systemctl start idx-brief.service
journalctl -u idx-brief -n 50 --no-pager
tail -n 40 ~/logs/brief-$(date +%F).log
curl -s https://andrebenas77.github.io/indonesia-morning-news-brief/ | grep -o "$(date +%F)" | head -1
git status --porcelain && git rev-list --count origin/main..HEAD    # expect empty, 0
```

**5. Watchdog** — prove it fires on a day the brief has not run:

```bash
sudo systemctl start idx-brief-watchdog.service
```

**Let the timer run unattended for two consecutive weekdays before disabling the
Windows scheduled task.**

## Reading a failure

`run_brief.sh` distinguishes two classes and Telegrams both:

- **FATAL** — no brief today. Duration under 90s (this alone would have caught all
  twelve failed August days), missing `sectors-news-<date>.json`, `docs/index.html`
  without today's date, missing archive copy, or commits that were never pushed.
- **WARN** — it published, but thinner. Fewer than 20 raw outlet headlines, a failed
  outlet, `engine: lexical-fallback` (DeepSeek down), missing flow/radar, fewer than 6
  Top News items.

Machine-readable state lands in `build/last_run.json`.

## The headline store

`data/headline-store.json` is tracked in git (not in `docs/`, so Pages never serves it)
and holds the rolling 7-day memory behind `repeat_days`.

It is written **only** by `dedup_news.py --commit-store`, which `run_brief.sh` runs
*after* the publish verification passes. That ordering is the point: committing at
cluster time would mean a run that died before publishing still marks today's stories
as seen, so tomorrow suppresses as "repeats" stories that never actually shipped —
precisely the failure this repo just lived through.

## Rolling back to the PC

The Windows scheduled task is *disabled*, not deleted, so it can be re-enabled during a
VPS outage. Its prompt is stale — it describes the old pure-WebFetch pipeline and never
mentions `fetch_sectors_news.py`, `fetch_outlets.py` or `dedup_news.py` — and must be
rewritten before any re-enable. See the banner at the top of
`~/.claude/scheduled-tasks/idx-morning-news-brief/SKILL.md`.

Ad-hoc PC runs stay fine: leave `BRIEF_UNATTENDED` unset so "ask before pushing" still
applies, and `git pull --rebase` first — the VPS is the sole regular writer.
