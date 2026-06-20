# Weekly training review → Telegram

Every **Saturday 11:00 a.m. US Eastern** a GitHub Action reviews the training week and
the block-to-date progress on the Big 5 (+ accessories) and pushes a punchy, emoji-rich
summary plus a progress chart to Telegram. The Hevy log is the source of truth.

## Pipeline (`weekly_review.py`)

1. **Time guard** — only proceeds at Sat 11:00 America/New_York (DST-safe; see schedule below).
2. **Sync** — `scripts.hevy.sync_archive` pulls the latest Hevy workouts so yesterday's
   session is present. Best-effort: a sync failure degrades to last-known data with a
   ⚠️ readiness caveat rather than skipping the review.
3. **Metrics** (`weekly_metrics.py`) — block/week geometry, data-readiness, this week's
   Big-5 top sets vs plan + RPE-cap flags, accessories, block-to-date e1RM, long-term trend.
4. **Chart** (`render_chart.py`) — two-panel PNG (this block by week + long-term by month).
5. **Narrative** (`narrate.py`) — Anthropic API (`claude-opus-4-8`) writes the coach-voice
   text from the stats + standing orders + notes. Falls back to a deterministic template
   if `ANTHROPIC_API_KEY` is unset or the call fails.
6. **Deliver** — `scripts.notifications.telegram` sends the chart (photo) + narrative.
7. **Archive** — snapshot to `reviews/weekly/<ISO-week>.md`, then commit the synced data +
   snapshot (also keeps the scheduled workflow alive past GitHub's 60-day idle disable).

## Schedule (DST-safe)

GitHub cron is UTC with no DST, so the workflow runs at **both** `15:00` and `16:00` UTC on
Saturday and the in-script Eastern guard passes exactly one: 15:00 UTC = 11:00 EDT (summer),
16:00 UTC = 11:00 EST (winter). Manual runs: **Actions → Weekly training review → Run
workflow** (defaults to bypassing the guard).

## Local testing

```bash
# Preview message + chart, no Telegram, no commit, no network:
.venv/bin/python -m scripts.review.weekly_review --force --dry-run --skip-sync

# Just the numbers / the chart / the template message:
.venv/bin/python -m scripts.review.weekly_metrics --date 2026-06-20
.venv/bin/python -m scripts.review.render_chart  --date 2026-06-20 --out /tmp/chart.png
.venv/bin/python -m scripts.review.narrate       --date 2026-06-20 --fallback

# Real Telegram send (needs .env keys), but don't commit:
.venv/bin/python -m scripts.review.weekly_review --force --no-commit
```

## One-time setup

1. **Telegram bot** — talk to [@BotFather](https://t.me/BotFather) → `/newbot` →
   `TELEGRAM_BOT_TOKEN`. Send your new bot any message, then
   `curl https://api.telegram.org/bot<TOKEN>/getUpdates` and read `result[].message.chat.id`
   → `TELEGRAM_CHAT_ID`.
2. **GitHub secrets** — repo **Settings → Secrets and variables → Actions**, add:
   `HEVY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`.
3. **Local** (optional, for testing) — copy the same keys into `.env` (see `.env.example`).

> ⚠️ Security: `.env` with a live `HEVY_API_KEY` is currently tracked in git. Consider
> `git rm --cached .env`, rotating the key, and relying on the GitHub secrets above.
