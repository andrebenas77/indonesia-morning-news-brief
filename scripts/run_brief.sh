#!/usr/bin/env bash
#
# Unattended morning-brief run (VPS). Invoked by idx-brief.timer at 07:45 WIB on
# weekdays, or by hand:
#
#   ./run_brief.sh [--trigger timer|manual] [--dry-run]
#
# Structure, and why:
#
#   * The deterministic fetch/dedup scripts run HERE, in the shell, not inside
#     Claude. One DATE is computed once and passed to every one of them, which
#     removes the whole class of timezone-skew bugs (a run on 2026-08-14 had
#     `export TZ=Asia/Jakarta; date` print GMT under Git Bash and silently build
#     the wrong day). It also means a Claude failure does not cost us the fetches.
#   * Claude is then handed the editorial work only: rank, summarise, render,
#     publish.
#   * Nothing is trusted until it is verified. A zero exit from claude is not
#     evidence that anything happened — see the verification block.
#
# Secrets come from the systemd EnvironmentFiles, never from this file.

set -euo pipefail

TRIGGER="manual"
DRYRUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --trigger) TRIGGER="${2:-manual}"; shift 2 ;;
        --dry-run) DRYRUN=true; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="/tmp/idx-screener.lock"
LOGDIR="${HOME}/logs"
STATE="${ROOT}/build/last_run.json"
SITE="https://andrebenas77.github.io/indonesia-morning-news-brief/"

mkdir -p "$LOGDIR" "${ROOT}/build" "${ROOT}/data"

# THE date for this run. Every script is given it explicitly; none re-derives it.
DATE="$(date +%F)"
LOG="${LOGDIR}/brief-${DATE}.log"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

notify() {
    python3 "${ROOT}/scripts/notify_telegram.py" "$@" >>"$LOG" 2>&1 || \
        log "[!!] notify failed (see log) — the run itself may still have succeeded"
}

# --- weekday guard ---------------------------------------------------------
# The timer is Persistent=true so a run missed while the box was down still
# happens. Without this guard, a Saturday catch-up would overwrite docs/index.html
# with a weekend brief — a Sunday catch-up on 2026-08-16 came within seconds of
# doing exactly that.
if [[ "$(date +%u)" -gt 5 ]]; then
    log "weekend ($(date +%A)) — IDX is closed, skipping without publishing"
    exit 0
fi

# --- preflight -------------------------------------------------------------
# One distinct message per failure. A single generic "setup error" once sent a
# manual-run env problem chasing entirely the wrong fix on the sibling screener.
PRE=()
for v in CLAUDE_CODE_OAUTH_TOKEN SECTORS_API_KEY DEEPSEEK_API_KEY \
         TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
    [[ -n "${!v:-}" ]] || PRE+=("${v} is not set (systemd supplies it from /etc/idx-screener.env or /etc/idx-brief.env; a plain shell does NOT — export it first)")
done
python3 -c "import requests" 2>/dev/null || \
    PRE+=("python3 cannot import requests — pip3 install --user --break-system-packages requests")
[[ -e "${HOME}/.claude/skills/indonesia-morning-news-brief" ]] || \
    PRE+=("~/.claude/skills/indonesia-morning-news-brief is missing — the /indonesia-morning-news-brief skill will not resolve and claude will exit 0 having done nothing (this exact omission broke the screener's first VPS run)")

CLAUDE="$(command -v claude || true)"
[[ -z "$CLAUDE" && -x "${HOME}/.local/bin/claude" ]] && CLAUDE="${HOME}/.local/bin/claude"
[[ -n "$CLAUDE" ]] || PRE+=("claude binary not found (systemd PATH is minimal; the native installer puts it in ~/.local/bin)")

if [[ ${#PRE[@]} -gt 0 ]]; then
    for p in "${PRE[@]}"; do log "[!!] preflight: $p"; done
    notify --title "IDX brief FAILED — ${DATE}" \
           --text "Preflight failed, the run never started.

$(printf -- '- %s\n' "${PRE[@]}")

Log: ${LOG}"
    exit 1
fi

# --- lock ------------------------------------------------------------------
# WAIT for the screener rather than fail fast. Both runs launch Claude Code and
# this box has 2 GB; two at once swap-thrash and both fail. run_daily.sh takes the
# same lock with -n, so a delayed screener makes the brief wait, and the brief can
# never block the screener. Needs PrivateTmp=false in the unit.
exec 9>"$LOCK"
if ! flock -w 1200 9; then
    log "[!!] waited 20min for /tmp/idx-screener.lock and never got it — exiting"
    notify --title "IDX brief SKIPPED — ${DATE}" \
           --text "Another run held the lock for 20 minutes. No brief today."
    exit 1
fi

START=$(date +%s)
log "=== run start (trigger=${TRIGGER}, dry-run=${DRYRUN}, date=${DATE}) ==="
cd "$ROOT"

if ! git pull --rebase --autostash >>"$LOG" 2>&1; then
    log "[!!] git pull --rebase failed — continuing with the local checkout"
fi

# --- deterministic pipeline (steps 2-6) ------------------------------------
# Warn-not-fail individually; the verification block below decides whether what
# survived is publishable. A dead outlet costs one ranking signal, not the brief.
step() {
    local label="$1"; shift
    if "$@" >>"$LOG" 2>&1; then
        log "  ok   ${label}"
    else
        log "  FAIL ${label} (exit $?) — continuing"
        return 1
    fi
}

set +e
step "sectors news"  python3 scripts/fetch_sectors_news.py --days 1 --date "$DATE"
step "raw outlets"   python3 scripts/fetch_outlets.py --hours 30 --date "$DATE"
step "dedup/classify" python3 scripts/dedup_news.py --date "$DATE"

TICKERS="$(jq -r '(.tickers // [])[:25] | join(",")' "build/dedup-${DATE}.json" 2>/dev/null || true)"
if [[ -n "$TICKERS" ]]; then
    log "  tickers -> ${TICKERS}"
    step "foreign flow" python3 scripts/fetch_flows.py --tickers "$TICKERS"
else
    log "  [!] no tickers from dedup — skipping foreign flow"
fi
step "radar join"    python3 scripts/build_radar.py
set -e

DEDUP_ENGINE="$(jq -r '.engine // "none"' "build/dedup-${DATE}.json" 2>/dev/null || echo none)"
log "dedup engine: ${DEDUP_ENGINE}"

# --- Claude: rank, summarise, render, publish (steps 7-13) -----------------
read -r -d '' PROMPT <<EOF || true
/indonesia-morning-news-brief run

This is an UNATTENDED scheduled run for ${DATE}. No human is available, so do not
ask any questions and do not wait for confirmation at any step.

Steps 2-6 have ALREADY BEEN RUN for you by scripts/run_brief.sh. These files exist
and are current — do not re-run those scripts, it wastes Sectors credits:
  build/sectors-news-${DATE}.json
  build/outlets-${DATE}.json
  build/dedup-${DATE}.json      <- rank from this one
  build/flows-${DATE}.json      (may be absent if the fetch failed)
  build/radar-${DATE}.json      (may be absent if the fetch failed)

Start at step 7 (Bank Indonesia) and work through to step 13. Use ${DATE} as the
date everywhere; do not re-derive it.

You have standing authorization to commit and push (step 13) without asking. If an
individual step fails, record it in sources_scanned and continue rather than
aborting the whole run.

End your reply with the step-12 summary ONLY. It is forwarded verbatim to a phone
as a Telegram message, so: plain text, no markdown tables, no code fences, under
3000 characters. Lead with the date, then the top 3 headlines and section counts.
EOF

if $DRYRUN; then
    PROMPT="${PROMPT}

DRY RUN: build docs/index.html as normal but do NOT git commit and do NOT git push."
fi

export BRIEF_UNATTENDED=1
set +e
OUT="$("$CLAUDE" -p "$PROMPT" \
        --output-format json \
        --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" \
        2>>"$LOG")"
CODE=$?
set -e

END=$(date +%s); DUR=$((END - START))
log "claude exited ${CODE} after ${DUR}s"

SUMMARY="$(printf '%s' "$OUT" | jq -r '.result // empty' 2>/dev/null || true)"
COST="$(printf '%s' "$OUT" | jq -r '.total_cost_usd // empty' 2>/dev/null || true)"
[[ -z "$SUMMARY" ]] && SUMMARY="$(printf '%s' "$OUT" | tail -c 3000)"
[[ -n "$COST" ]] && log "cost: \$${COST}"

# --- verification ----------------------------------------------------------
# FATAL = there is no published brief today. WARN = it published but thinner than
# it should be. The duration check alone would have caught all twelve days of the
# August 2026 silent failure.
FATAL=()
WARN=()

MIN_DUR=90
[[ $DUR -lt $MIN_DUR ]] && FATAL+=("finished in ${DUR}s but a real run takes minutes — the skill likely never executed")

[[ -s "${ROOT}/build/sectors-news-${DATE}.json" ]] || \
    FATAL+=("build/sectors-news-${DATE}.json missing or empty")
# Match the brief-date meta tag, NOT a bare date. The visible date is human-formatted
# and the only other ISO date on the page is the flow board's, which is keyed to the
# trading session and lags the run date — grepping for "$DATE" alone would report a
# false FATAL every single day.
grep -q "name=\"brief-date\" content=\"${DATE}\"" "${ROOT}/docs/index.html" 2>/dev/null || \
    FATAL+=("docs/index.html does not carry brief-date=${DATE} — the brief was not rebuilt")
[[ -s "${ROOT}/docs/archive/${DATE}.html" ]] || \
    FATAL+=("docs/archive/${DATE}.html missing — the archive copy was not written")

if $DRYRUN; then
    log "[dry-run] skipping the push check"
elif git fetch -q origin main >>"$LOG" 2>&1; then
    UNPUSHED="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
    [[ "${UNPUSHED:-0}" -gt 0 ]] && \
        FATAL+=("${UNPUSHED} commit(s) never pushed — the published site was not updated")
else
    WARN+=("could not reach GitHub to confirm the brief was published")
fi

OUTLET_N="$(jq -r '.counts.items // 0' "build/outlets-${DATE}.json" 2>/dev/null || echo 0)"
[[ "${OUTLET_N:-0}" -lt 20 ]] && \
    WARN+=("only ${OUTLET_N} raw outlet headlines — cross-outlet signal is degraded")
OUTLET_FAILED="$(jq -r '[.sources[]? | select(.status=="failed") | .outlet] | unique | join(", ")' "build/outlets-${DATE}.json" 2>/dev/null || true)"
[[ -n "$OUTLET_FAILED" ]] && WARN+=("outlet fetch failed: ${OUTLET_FAILED}")

[[ "$DEDUP_ENGINE" == "lexical-fallback" ]] && \
    WARN+=("DeepSeek unavailable — clustering fell back to lexical only")
[[ "$DEDUP_ENGINE" == "deepseek-partial" ]] && \
    WARN+=("DeepSeek time budget exceeded — some clusters are lexical only")

[[ -s "${ROOT}/build/flows-${DATE}.json" ]] || WARN+=("no foreign-flow data for ${DATE}")
[[ -s "${ROOT}/build/radar-${DATE}.json" ]] || WARN+=("no radar file for ${DATE}")

TOPN="$(jq -r '(.top_news // []) | length' "${ROOT}/build/data.json" 2>/dev/null || echo 0)"
[[ "${TOPN:-0}" -lt 6 ]] && WARN+=("only ${TOPN} Top News items")

for w in ${WARN[@]+"${WARN[@]}"};  do log "[warn] $w"; done
for f in ${FATAL[@]+"${FATAL[@]}"}; do log "[!!] $f"; done

OK=true
[[ $CODE -ne 0 || ${#FATAL[@]} -gt 0 ]] && OK=false

# --- two-phase store commit ------------------------------------------------
# ONLY after the publish is verified. Committing the headline store at cluster
# time would mean a run that died before publishing still marks today's stories
# as "seen", so tomorrow suppresses as repeats stories that never actually
# shipped. That is precisely the failure mode this repo just lived through.
if $OK && ! $DRYRUN; then
    if python3 scripts/dedup_news.py --date "$DATE" --commit-store >>"$LOG" 2>&1; then
        if [[ -n "$(git status --porcelain data/headline-store.json)" ]]; then
            if git add data/headline-store.json \
               && git commit -q -m "Headline store ${DATE}" >>"$LOG" 2>&1 \
               && git push -q origin main >>"$LOG" 2>&1; then
                log "headline store committed and pushed"
            else
                WARN+=("headline store updated but NOT pushed — repeat detection may drift")
                log "[!] headline store not pushed"
            fi
        fi
    else
        WARN+=("headline store commit failed — repeat detection will miss today")
    fi
elif $DRYRUN; then
    log "[dry-run] skipping the headline-store commit"
fi

if [[ ${#FATAL[@]} -eq 0 ]]; then FATAL_JSON='[]'
else FATAL_JSON="$(printf '%s\n' "${FATAL[@]}" | jq -R . | jq -s -c .)"; fi
if [[ ${#WARN[@]} -eq 0 ]]; then WARN_JSON='[]'
else WARN_JSON="$(printf '%s\n' "${WARN[@]}" | jq -R . | jq -s -c .)"; fi

cat >"$STATE" <<JSON
{
  "finished_at": "$(date '+%F %T %Z')",
  "ok": ${OK},
  "exit_code": ${CODE},
  "duration_s": ${DUR},
  "trigger": "${TRIGGER}",
  "dry_run": ${DRYRUN},
  "date": "${DATE}",
  "dedup_engine": "${DEDUP_ENGINE}",
  "cost_usd": "${COST}",
  "problems": ${FATAL_JSON},
  "warnings": ${WARN_JSON}
}
JSON

WARNTEXT=""
if [[ ${#WARN[@]} -gt 0 ]]; then
    WARNTEXT="

Warnings:
$(printf -- '- %s\n' "${WARN[@]}")"
fi
PREFIX=""; $DRYRUN && PREFIX="[DRY RUN] "

if $OK; then
    notify --title "${PREFIX}IDX morning brief — ${DATE}" \
           --text "${SUMMARY}

Brief: ${SITE}${WARNTEXT}"
    log "=== run ok ==="
else
    REASON=""
    [[ $CODE -ne 0 ]] && REASON="- claude exited ${CODE}"$'\n'
    [[ ${#FATAL[@]} -gt 0 ]] && REASON="${REASON}$(printf -- '- %s\n' "${FATAL[@]}")"
    notify --title "${PREFIX}IDX brief FAILED — ${DATE}" \
           --text "The ${TRIGGER} run did not produce a published brief.

${REASON}
Ran ${DUR}s.

Last output:
$(printf '%s' "$SUMMARY" | tail -c 1200)

Log: ${LOG}"
    log "=== run FAILED ==="
    exit 1
fi
