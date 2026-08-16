#!/usr/bin/env bash
#
# VPS setup for the Indonesia Morning News Brief.
#
#   curl -sL https://raw.githubusercontent.com/andrebenas77/indonesia-morning-news-brief/main/deploy/setup.sh | bash
#
# Assumes the box has ALREADY been provisioned by the screener's deploy/setup.sh —
# SSH key, Asia/Jakarta clock, 4 GB swap, python3/git/jq and Claude Code are all
# installed there. This script detects that and skips those steps rather than
# redoing them. Safe to re-run: every step checks before acting.

set -euo pipefail

REPO="https://github.com/andrebenas77/indonesia-morning-news-brief.git"
DEST="$HOME/indonesia-morning-news-brief"
SKILLS="$HOME/.claude/skills"
SCREENER="$HOME/idx-telegram-screener"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '    \033[1;33m[!!]\033[0m %s\n' "$*"; }

say "Indonesia Morning Brief — VPS setup"
echo "    user: $(whoami)   host: $(hostname)   time: $(date)"

# --- 1. prerequisites already provided by the screener ---------------------
say "1/6  Checking the shared prerequisites"
MISSING=0
for c in python3 git jq; do
    command -v "$c" >/dev/null 2>&1 && ok "$c" || { warn "$c missing"; MISSING=1; }
done
if command -v claude >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/claude" ]]; then
    ok "claude $("$HOME/.local/bin/claude" --version 2>/dev/null || echo installed)"
else
    warn "claude not installed — run the screener's deploy/setup.sh first"
    MISSING=1
fi
[[ -d "$SCREENER" ]] && ok "screener repo present (ticker universe + chatter history)" \
                     || warn "screener repo not at ${SCREENER} — radar chatter buckets will be empty"
if [[ $MISSING -eq 1 ]]; then
    warn "Install the screener first:"
    warn "  curl -sL https://raw.githubusercontent.com/andrebenas77/idx-telegram-screener/main/deploy/setup.sh | bash"
    exit 1
fi
[[ "$(date +%Z)" == "WIB" ]] && ok "timezone $(date +%Z)" || warn "timezone is $(date +%Z), expected WIB"

# --- 2. python dependency --------------------------------------------------
# Only sectors_client.py needs it; fetch_outlets.py and dedup_news.py are stdlib
# only, deliberately, so a broken requests cannot take down every news path at once.
say "2/6  Installing requests"
if python3 -c "import requests" 2>/dev/null; then
    ok "already present"
else
    pip3 install --user --quiet --break-system-packages requests 2>/dev/null \
        || pip3 install --user --quiet requests
    python3 -c "import requests" && ok "installed"
fi

# --- 3. the repo -----------------------------------------------------------
say "3/6  Fetching the brief"
if [[ -d "$DEST/.git" ]]; then
    git -C "$DEST" pull --rebase --quiet || warn "pull failed; keeping existing copy"
    ok "updated $DEST"
else
    git clone --quiet "$REPO" "$DEST"
    ok "cloned to $DEST"
fi
chmod +x "$DEST/scripts/run_brief.sh" 2>/dev/null || true
mkdir -p "$DEST/build" "$DEST/data" "$HOME/logs" "$HOME/.cache/sectors"
ok "build/ data/ ~/logs ~/.cache/sectors"

# --- 4. skill symlink ------------------------------------------------------
# Without this the /indonesia-morning-news-brief skill does not resolve, and claude
# exits 0 within seconds having produced nothing — which reads exactly like a good
# run. This is the single most common way a VPS install silently does nothing.
say "4/6  Registering the skill"
mkdir -p "$SKILLS"
ln -sfn "$DEST" "$SKILLS/indonesia-morning-news-brief"
[[ -e "$SKILLS/indonesia-morning-news-brief/SKILL.md" ]] \
    && ok "$SKILLS/indonesia-morning-news-brief -> $DEST" \
    || { warn "symlink did not resolve"; exit 1; }

# --- 5. env file template --------------------------------------------------
say "5/6  Environment"
if [[ -r /etc/idx-brief.env ]]; then
    ok "/etc/idx-brief.env exists"
else
    warn "/etc/idx-brief.env is missing — create it as root (see step 2 below)"
fi
if [[ -r /etc/idx-screener.env ]]; then
    grep -q '^SECTORS_CACHE_DIR=' /etc/idx-screener.env 2>/dev/null \
        && ok "screener env exports SECTORS_CACHE_DIR (shared day-cache)" \
        || warn "add SECTORS_CACHE_DIR to /etc/idx-screener.env too, or the two skills will not share the Sectors cache and you pay double credits"
else
    warn "/etc/idx-screener.env not readable by $(whoami) — that is expected (root:root 600); systemd reads it, you do not"
fi

# --- 6. smoke test ---------------------------------------------------------
say "6/6  Smoke test (no API keys needed)"
cd "$DEST"
if python3 scripts/fetch_outlets.py --hours 30 --out /tmp/outlets-smoke.json >/dev/null 2>&1; then
    N="$(jq -r '.counts.items' /tmp/outlets-smoke.json)"
    OKN="$(jq -r '.counts.sources_ok' /tmp/outlets-smoke.json)"
    ok "outlet fetch works: ${N} headlines from ${OKN}/6 sources"
    rm -f /tmp/outlets-smoke.json
else
    warn "outlet fetch failed — check network/DNS"
fi

cat <<'BANNER'

============================================================
  SETUP COMPLETE — three things still need you
============================================================

  1. Deploy key, so the box can push:

       ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_brief_deploy -N ""
       cat ~/.ssh/id_ed25519_brief_deploy.pub

     Add that key at:
       github.com/andrebenas77/indonesia-morning-news-brief
         -> Settings -> Deploy keys -> Add, TICK "Allow write access"

     Then:
       cd ~/indonesia-morning-news-brief
       git remote set-url origin git@github.com:andrebenas77/indonesia-morning-news-brief.git
       printf 'Host github.com\n  IdentityFile ~/.ssh/id_ed25519_brief_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
       ssh -T git@github.com        # expect "successfully authenticated"

  2. Environment file (as root):

       sudo tee /etc/idx-brief.env >/dev/null <<'ENV'
       DEEPSEEK_API_KEY=sk-...
       SECTORS_CACHE_DIR=/home/screener/.cache/sectors
       IDX_SCREENER_DIR=/home/screener/idx-telegram-screener
       ENV
       sudo chmod 600 /etc/idx-brief.env

     And append SECTORS_CACHE_DIR=/home/screener/.cache/sectors to
     /etc/idx-screener.env so both skills share one Sectors day-cache.

  3. Install the timers:

       sudo cp ~/indonesia-morning-news-brief/deploy/idx-brief*.service /etc/systemd/system/
       sudo cp ~/indonesia-morning-news-brief/deploy/idx-brief*.timer   /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable --now idx-brief.timer idx-brief-watchdog.timer
       systemctl list-timers 'idx-*'

  Then dry-run it before trusting the timer:

       ./scripts/run_brief.sh --trigger manual --dry-run

  Full detail, including the memory test: deploy/VPS-SETUP.md

============================================================

BANNER
