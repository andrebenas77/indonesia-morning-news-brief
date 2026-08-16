# Bare-box recovery — Biznet web console

Recovering a **rebuilt** Biznet VPS (`103.197.190.92`, Ubuntu 24.04) from nothing: no SSH key,
no users, no repos, no secrets. Restores the screener first, then the morning brief.

> **Why the console at all.** SSH is publickey-only and `authorized_keys` is empty, so SSH cannot
> bootstrap itself. The screener's `deploy/setup.sh` step 1 installs the key — that one step has to
> happen somewhere else, and the browser console is the only door left.

**Typing in a VNC console is miserable. Phase A is deliberately four commands; everything else
waits for real SSH in Phase B.**

---

## Before you start — on your PC

| Value | How to get it |
|---|---|
| `SECTORS_API_KEY` | `[Environment]::GetEnvironmentVariable('SECTORS_API_KEY','User')` |
| `DEEPSEEK_API_KEY` | `[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')` |
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` → copy the `sk-ant-oat01-…`. **Must be regenerated — it is not stored anywhere recoverable.** |
| Telegram bot token + chat id | Already in `idx-telegram-screener/secrets/.env` on your PC |

You do **not** need to retype these in the console. They go in over SSH in Phase B.

---

## Phase A — Biznet web console (ONE line)

The console is noVNC and **does not accept clipboard paste**, so this is deliberately one short
line to type by hand. Nothing else happens here.

Biznet panel → your instance → **Console**. Log in as `root` (or the default user, then `sudo -i`).

### A1. Type exactly this

```bash
curl -sL andrebenas77.github.io/idx-telegram-screener/k.sh|bash
```

No `https://` needed — curl upgrades it and `-L` follows the redirect. 62 characters.

It creates the `screener` user, installs your public key, grants passwordless sudo, and — the step
that matters most — **installs `openssh-server` if the image shipped without it**. A minimal image
can, and "Connection refused" then looks exactly like an auth problem with the console already
closed. It also asserts `PubkeyAuthentication yes` before declaring success.

It deliberately does **not** run `setup.sh`. That means ~5 minutes of apt/pip output in a window you
cannot scroll or copy from. It runs over SSH in B0 instead.

Success looks like a `CONSOLE WORK IS DONE` banner. Safe to re-run; every step is guarded.

> **Why the user must exist first.** `deploy/setup.sh` installs the key for *whoever runs it* and
> never creates users, while every systemd unit hardcodes `User=screener` and `/home/screener/...`.
> Run setup.sh as root and the repo lands in `/root` while the timers look in `/home/screener` — a
> mismatch you would only discover after everything else was done.

### A2. Prove SSH works — **from your PC, not the console**

```bash
ssh -i "$HOME/.ssh/id_ed25519_idxvps3" screener@103.197.190.92 "hostname; date"
```

Once this answers, **close the console.** Everything below is normal SSH.

> If it still refuses: `cat ~/.ssh/authorized_keys` in the console should show a line ending
> `idx-screener-3`, and `~/.ssh` must be `700` with `authorized_keys` `600`.

---

## Phase B — over SSH

> **Never run `run_daily.sh` or `run_brief.sh` under `sudo`.** Both take `/tmp/idx-screener.lock`.
> One sudo run leaves a root-owned lock the `screener` user can never open again; `exec 9>` on it
> then fails immediately under `set -e`, *after* preflight, so no Telegram alert fires and the
> failure is silent. Recovery: `sudo rm /tmp/idx-screener.lock`.

### B0. Run the heavy bootstrap (now that output is scrollable)

```bash
ssh -i "$HOME/.ssh/id_ed25519_idxvps3" screener@103.197.190.92
```

```bash
curl -sL https://raw.githubusercontent.com/andrebenas77/idx-telegram-screener/main/deploy/setup.sh | bash
```

Asia/Jakarta, python3/git/jq/curl, Telethon, the 4 GB swapfile, Claude Code, and the screener clone.
Its step 1/7 re-installs the SSH key — a `grep -qF`-guarded no-op, since A1 already did it.

Note it installs **telethon only, not `requests`**. `requests` arrives with the brief's setup in C1,
so a screener-only box cannot run `sectors_client.py`. If you stop after Phase B, add it:
`pip3 install --user --break-system-packages requests`.

### B1. Push the two files git deliberately does not carry

`secrets/.env` and `reference/channels.txt` are gitignored (`.gitignore:10` and `:14`), so a clone is
not runnable without them. From **PowerShell on your PC**:

```bash
scp -i "$HOME/.ssh/id_ed25519_idxvps3" "$HOME/.claude/skills/idx-telegram-screener/secrets/.env" screener@103.197.190.92:~/idx-telegram-screener/secrets/.env
```

```bash
scp -i "$HOME/.ssh/id_ed25519_idxvps3" "$HOME/.claude/skills/idx-telegram-screener/reference/channels.txt" screener@103.197.190.92:~/idx-telegram-screener/reference/channels.txt
```

Also copy `secrets/trade.env` if you still run the trade-plan timers.

**Do not copy `screener.session`.** B2 makes a fresh one — a session appearing on a new IP is more
likely to trip Telegram's checks than a clean login.

`scp` without `-p` creates files at the remote umask default (644). `trade.env` holds live
credentials, so lock both down:

```bash
ssh -i "$HOME/.ssh/id_ed25519_idxvps3" screener@103.197.190.92 "chmod 600 ~/idx-telegram-screener/secrets/*.env && chmod +x ~/idx-telegram-screener/scripts/run_daily.sh && ls -l ~/idx-telegram-screener/secrets/"
```

Every `.env` must read `-rw-------`.

### B2. Telegram login — **interactive, cannot be scripted**

```bash
cd ~/idx-telegram-screener && python3 scripts/tg_login.py
```

You will be asked for the login code Telegram sends you, plus 2FA if enabled. You will also get a
"new login" security alert — that one is you. Then `chmod 600 secrets/screener.session`.

### B3. Secrets file (root-owned, 600)

```bash
sudo tee /etc/idx-screener.env >/dev/null <<'EOF'
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-REPLACE
SECTORS_API_KEY=REPLACE
TELEGRAM_BOT_TOKEN=REPLACE
TELEGRAM_CHAT_ID=REPLACE
SECTORS_CACHE_DIR=/home/screener/.sectors-cache
EOF
sudo chmod 600 /etc/idx-screener.env
```

`SECTORS_API_KEY` **must** live here, not in `secrets/.env` — `sectors_client.py` reads it from the
process environment and a systemd job starts with a near-empty one. Miss it and the Foreign column
silently renders "–" with no error anywhere.

`SECTORS_CACHE_DIR` is new: it makes the screener and the brief share one Sectors day-cache. Without
it they each pay full credits.

### B4. Screener units

```bash
sudo cp ~/idx-telegram-screener/deploy/idx-screener.{service,timer} ~/idx-telegram-screener/deploy/idx-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now idx-screener.timer idx-bot.service && systemctl list-timers idx-screener.timer
```

**At this point the screener is restored.** Verify before moving on:

```bash
cd ~/idx-telegram-screener && ./scripts/run_daily.sh --trigger manual
```

Watch memory in a second SSH session — this is the check that decides whether 2 GB was the right
call. Swap climbing steadily or a run past ~10 min means resize to NEO Lite MS 4.4.

```bash
watch -n2 free -m
```

---

## Phase C — the morning brief

### C1. Bootstrap

```bash
curl -sL https://raw.githubusercontent.com/andrebenas77/indonesia-morning-news-brief/main/deploy/setup.sh | bash
```

Detects the existing screener and skips timezone/swap/Claude Code. Installs `requests`, clones the
repo, and symlinks it into `~/.claude/skills/` — that symlink is what makes the
`/indonesia-morning-news-brief` skill resolvable. Its absence is why the screener's first VPS run
once exited 0 having done nothing.

### C2. Brief env file

```bash
sudo tee /etc/idx-brief.env >/dev/null <<'EOF'
DEEPSEEK_API_KEY=REPLACE
SECTORS_CACHE_DIR=/home/screener/.sectors-cache
IDX_SCREENER_DIR=/home/screener/idx-telegram-screener
EOF
sudo chmod 600 /etc/idx-brief.env
```

`IDX_SCREENER_DIR` replaces three hard-coded Windows paths. Without it the ticker universe and the
radar chatter buckets both go silently empty — warnings only, no error.

### C3. Deploy key for pushing

A repo-scoped deploy key beats a PAT on a box that also holds a logged-in Telegram *user* session.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_brief_deploy -N "" -C "brief-deploy@vps" && cat ~/.ssh/id_ed25519_brief_deploy.pub
```

Add that public key at **github.com/andrebenas77/indonesia-morning-news-brief → Settings → Deploy
keys → Add**, tick **Allow write access**. Then:

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/id_ed25519_brief_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config && cd ~/indonesia-morning-news-brief && git remote set-url origin git@github.com:andrebenas77/indonesia-morning-news-brief.git && ssh -T git@github.com
```

`ssh -T` answering "successfully authenticated" (it still says shell access is denied — that's
correct) means pushes will work.

### C4. Dry run before any timer

```bash
cd ~/indonesia-morning-news-brief && ./scripts/run_brief.sh --trigger manual --dry-run
```

Runs everything including Claude, skips commit/push and skips the store commit, prints the
FATAL/WARN lists it *would* have raised, and sends a `[DRY RUN]`-prefixed Telegram so the
notification path is proven too.

> **On a weekend this proves nothing.** `run_brief.sh` has a weekday guard and exits in about one
> second on Sat/Sun. That is correct behaviour, not a failure — but it also means Claude, the
> fetchers and the publish path were never exercised. To genuinely test on a weekend, pass an
> explicit weekday date, which bypasses the guard:
>
> ```bash
> cd ~/indonesia-morning-news-brief && ./scripts/run_brief.sh --trigger manual --dry-run --date $(date -d 'last friday' +%F)
> ```
>
> The same applies to `check_published.py`, which returns early when `now.weekday() > 4`.
>
> `run_daily.sh` (screener) has **no** weekday guard, so a manual weekend run appends a weekend row
> to `data/history.csv` and pushes it. Harmless — the recency weighting absorbs it — but expect the
> commit.

### C5. Install the timers

```bash
sudo cp ~/indonesia-morning-news-brief/deploy/idx-brief.{service,timer} ~/indonesia-morning-news-brief/deploy/idx-brief-watchdog.{service,timer} /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now idx-brief.timer idx-brief-watchdog.timer && systemctl list-timers 'idx-*'
```

Expect three timers: screener 07:00, brief 07:45, watchdog 09:30 — all Mon–Fri Asia/Jakarta.

The 07:45 slot is deliberate: after the screener, so the Sectors day-cache is warm and
`history.csv` is fresh, and before the 09:00 open. Both runs take `/tmp/idx-screener.lock`, so a
delayed screener makes the brief wait rather than the two thrashing 2 GB of RAM together.

---

## Verify, then cut over

The units are `Type=oneshot` with a long `TimeoutStartSec`, so a plain `systemctl start` **blocks
your terminal for the whole run** (minutes, silently). Use `--no-block` and follow the log instead:

```bash
sudo systemctl start --no-block idx-brief.service && journalctl -u idx-brief -f
```

- `https://andrebenas77.github.io/indonesia-morning-news-brief/` shows today's date
- `git -C ~/indonesia-morning-news-brief status` is clean and `git rev-list --count origin/main..HEAD` is 0
- Deliberately overlap the brief with the 07:00 screener once, to prove `flock` serialises them

**Let both timers fire unattended on two consecutive weekdays before disabling the Windows scheduled
task.** Until then the PC remains the fallback.

## Idempotency

| Step | Safe to re-run? |
|---|---|
| A1 `adduser` | Yes — errors harmlessly if the user exists |
| A3 / C1 `setup.sh` | Yes — every step checks before acting |
| B3 / C2 `tee` env files | Yes, but **overwrites** — re-paste all keys |
| B4 / C5 unit install | Yes |
| B2 `tg_login.py` | Yes, creates a fresh session |
| C3 `ssh-keygen` | **No** — prompts to overwrite; the old deploy key stops working |
