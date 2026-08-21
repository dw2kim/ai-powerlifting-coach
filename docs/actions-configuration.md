# GitHub Actions configuration

Every key the workflows read, where it goes, and what breaks without it. Set them under
**Settings → Secrets and variables → Actions**.

`SHEETS_SPREADSHEET_ID` is the only one that is not a credential — it's the id in the
spreadsheet's URL — so it works as either a Secret or a Variable. Everything else is a
credential and belongs in **Secrets**.

## What each workflow needs

| Key | Kind | Export block | Sync movement library | Push block to Hevy | Weekly review |
|---|---|---|---|---|---|
| `HEVY_API_KEY` | secret | — | — | required | required |
| `TELEGRAM_BOT_TOKEN` | secret | — | — | — | required |
| `TELEGRAM_CHAT_ID` | secret | — | — | — | required |
| `ANTHROPIC_API_KEY` | secret | — | — | — | required |
| `GOOGLE_SA_JSON` | secret | required | required | — | optional¹ |
| `SHEETS_SPREADSHEET_ID` | secret **or** variable | required | required | — | optional¹ |

¹ The weekly review degrades on purpose: without the Google keys the review still ships to
Telegram and the block JSON is still corrected, and only the Sheet push is skipped with a
warning in the job log. It has run 17 times and that push has been skipped every time.

`SHEETS_DRIVE_FOLDER_ID` and `GOOGLE_SHARE_EMAIL` are read by `export_block.py` only, for its
create-a-new-sheet mode on a Shared Drive. Unused when `SHEETS_SPREADSHEET_ID` is set.

## GOOGLE_SA_JSON

A Google **service-account** key. Either the key JSON itself (what a GitHub secret holds) or a
path to the key file (local `.env`). A value starting with `{` is read as inline JSON.

The account needs no Drive quota and cannot create files — share the target spreadsheet with
the service account's email as **Editor** and that is its entire reach. `export_movement_library`
requests the `spreadsheets` scope only; `export_block` also requests `drive`, which its
folder mode needs.

## Never commit these

Secrets live in GitHub's encrypted store, not in the repository. **This repository is public** —
a credential committed here is a credential published, and rotating it is the only fix. There is
no way to add a secret through a pull request; the Settings UI or the API is the only path.
