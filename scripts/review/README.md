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

---

# End-of-W4 next-block draft → Google Sheet

At the **end of Week 4** (the Sunday before the W5 deload) a scheduled Claude Code routine
drafts the *next* block and drops it into a Google Sheet, so it can be reviewed during the
deload and finalized before the new block starts. W5 is a deload — it produces no
design-relevant data, so W1–W4 actuals are the inputs and drafting at end-of-W4 is correct.
The draft is **provisional**: never auto-applied to `current-block.*`, never pushed to Hevy.

## Why a routine, not a pure cron

The drafting itself is the `designing-training-block` skill (LLM work — retrospect,
theme, wave, accessories, log-grounded loads). So a **Claude Code routine** runs the skill;
`draft_next_block.py` owns only the deterministic bookends around it.

## Pipeline

The routine, fired weekly **Sunday 13:00 America/Toronto**, runs:

1. `python -m scripts.review.draft_next_block check` — **guard**: is today the Sunday of the
   block's penultimate week (W4 for a 5-week block)? Reuses `weekly_metrics.geometry`. Exit
   `0` = proceed (and sync the Hevy log), exit `3` = skip. The routine stops on `3`, so most
   Sundays are a clean no-op.
2. `designing-training-block` **in draft mode** (see the skill's "Draft mode" section): writes
   `brain/next-block-draft.{md,json}` with a PROVISIONAL banner; skips the review gate, the
   archive/overwrite, and the Hevy push. Obeys all binding rules — including
   `primary-backoff-volume` (squat/sumo backoff) and the `accessory-rotation` expansion
   clause (1–2 new movements).
3. `python -m scripts.review.draft_next_block notify` — render the draft to a Google Sheet
   (`scripts.sheets.export_block`, two colour-coded tabs: "&lt;Block N&gt; Overview" + "&lt;Block N&gt; Plan"), push a Telegram
   heads-up with the Sheet URL + a W1→peak glance, and commit the draft to the
   `draft/next-block` branch (never master).

**Finalization (after W5, athlete-driven):** run `reviewing-block` for the now-complete
block, reconcile its lessons + any Sheet edits against the draft, then promote it into
`brain/current-block.{md,json}`, archive the prior block, and push to Hevy.

## Local testing

```bash
# Guard only, across dates (exit 0 = proceed, 3 = skip); --no-sync avoids the Hevy API:
.venv/bin/python -m scripts.review.draft_next_block check --date 2026-06-28 --no-sync  # W4 Sun → proceed
.venv/bin/python -m scripts.review.draft_next_block check --date 2026-06-21 --no-sync  # W3 Sun → skip

# Sheet layout preview (no Google calls, no creds) — diff against the live B3 sheet:
.venv/bin/python -m scripts.sheets.export_block brain/current-block.json --dry-run

# Notify preview (needs a brain/next-block-draft.json present): prints Sheet grid + Telegram text
.venv/bin/python -m scripts.review.draft_next_block notify --dry-run
```

## One-time setup (Google Sheets)

The Sheet is created by a Google **service account** (so the routine needs no interactive login):

1. **GCP project** → enable the **Google Sheets API** and **Google Drive API**.
2. Create a **service account**, add a **JSON key**, download it → `GOOGLE_SA_JSON` path
   (keep the file outside the repo, e.g. `~/.gcp/`).
3. **Pre-make one spreadsheet** in your Drive (e.g. "Block Drafts") and **share it with the
   service account's email** (Editor). Its id (from `docs.google.com/spreadsheets/d/<ID>/edit`)
   is `SHEETS_SPREADSHEET_ID`. The SA rewrites its tabs each draft.
   > Why a pre-made sheet, not a folder: a service account has **no Drive storage quota**, so
   > it can't *create* files in a personal (`@gmail.com`) Drive — it can only edit a file
   > you've shared with it. (On Google **Workspace**, you can instead set
   > `SHEETS_DRIVE_FOLDER_ID` to a **Shared Drive** folder and get a new Sheet per block.)
4. Provision the env vars (`HEVY_API_KEY`, `TELEGRAM_*`, `GOOGLE_SA_JSON`,
   `SHEETS_SPREADSHEET_ID`) wherever the routine runs.

`gspread` + `google-auth` are declared in `pyproject.toml` — `pip install -e .` picks them up.

> **Where this runs:** the draft job lives in the **local Claude app scheduler** (the
> `next-block-draft` task), not GitHub Actions — step 2 runs the `designing-training-block`
> *skill*, which needs Claude. So `GOOGLE_SA_JSON` as a **local file path** is correct; the
> key file stays on your Mac and never goes in git.
>
> If you ever run any of this in **GitHub Actions** instead, a local path is meaningless on
> the runner. Store the **JSON content** (not a path) as a GitHub secret and pass it through:
> `env: GOOGLE_SA_JSON: ${{ secrets.GOOGLE_SA_JSON }}`. `export_block.py` detects a value
> starting with `{` and loads it as inline credentials — same var, both environments. Never
> commit the key file or a populated `.env`.
