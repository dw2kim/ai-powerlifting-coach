"""Send messages and photos to Telegram via the Bot API.

Auth: a bot token from @BotFather plus the target chat id. Same env pattern as
scripts/hevy/client.py — `load_dotenv()` then read from the environment:

  TELEGRAM_BOT_TOKEN   the bot token (123456:ABC...)
  TELEGRAM_CHAT_ID     the chat to deliver to

Used by the weekly review job to push the chart (sendPhoto) + the coach narrative
(sendMessage). Plain `requests` — no extra dependency.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

API_BASE = "https://api.telegram.org"
# Telegram hard limits: 4096 chars per message, 1024 per photo caption.
MAX_MESSAGE = 4096
MAX_CAPTION = 1024


class TelegramError(RuntimeError):
    pass


def _creds(token: str | None, chat_id: str | None) -> tuple[str, str]:
    load_dotenv()
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise TelegramError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set. Add them to .env "
            "(local) or the GitHub Actions secrets (CI)."
        )
    return token, chat_id


def _split(text: str, limit: int) -> list[str]:
    """Split a long message under `limit`, preferring paragraph/line breaks."""
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 2:
            cut = window.rfind("\n")
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def send_message(
    text: str,
    parse_mode: str | None = "HTML",
    token: str | None = None,
    chat_id: str | None = None,
    timeout: float = 30.0,
) -> None:
    """Send text, splitting at the 4096-char limit. If a parse_mode is given and
    Telegram rejects the markup (400), retry the chunk as plain text so a stray
    tag never costs us the whole message."""
    token, chat_id = _creds(token, chat_id)
    url = f"{API_BASE}/bot{token}/sendMessage"
    for chunk in _split(text, MAX_MESSAGE):
        payload = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(url, data=payload, timeout=timeout)
        if resp.status_code == 400 and parse_mode:
            payload.pop("parse_mode", None)
            resp = requests.post(url, data=payload, timeout=timeout)
        if not resp.ok:
            raise TelegramError(f"sendMessage -> {resp.status_code}: {resp.text}")


def send_photo(
    photo_path: str | Path,
    caption: str = "",
    parse_mode: str | None = "HTML",
    token: str | None = None,
    chat_id: str | None = None,
    timeout: float = 60.0,
) -> None:
    """Upload a local image with an optional caption (truncated to 1024 chars)."""
    token, chat_id = _creds(token, chat_id)
    url = f"{API_BASE}/bot{token}/sendPhoto"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:MAX_CAPTION]
        if parse_mode:
            data["parse_mode"] = parse_mode
    with open(photo_path, "rb") as fh:
        resp = requests.post(url, data=data, files={"photo": fh}, timeout=timeout)
    if resp.status_code == 400 and parse_mode and caption:
        data.pop("parse_mode", None)
        with open(photo_path, "rb") as fh:
            resp = requests.post(url, data=data, files={"photo": fh}, timeout=timeout)
    if not resp.ok:
        raise TelegramError(f"sendPhoto -> {resp.status_code}: {resp.text}")
