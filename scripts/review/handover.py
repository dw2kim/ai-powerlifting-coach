"""Block handover readiness — does the next block exist yet, and did this one get reviewed?

Why this module exists
----------------------
B7 was due to start on Mon 2026-11-02 and the athlete had to ask for it. Nothing in the repo
had noticed, and two separate things were wrong:

1. The `draft_next_block` routine lives in a **local** scheduler that was not running, so it
   had never produced a commit in its life.
2. Its guard could only ever fire on **one** day — the W4 Sunday. `weekly_metrics.geometry`
   clamps `week_no` to the block length, so from the W5 Sunday onward `week_no` can never
   equal the target again and the guard skips *forever*. One missed firing was permanent.

So the fix is not "find a better scheduler". It is: **the job that reliably runs must be the
one that notices.** That job is the Saturday weekly review, which runs in GitHub Actions with
the repo's own secrets and has shipped every week for months.

This module is deterministic, has no network calls and no LLM, and answers two questions:

  - Is the **next block** drafted and current? (not the stale draft of a long-archived block)
  - Once the block has **ended**, does `reviews/<block-id>.md` exist? That review is the
    documented gate on designing the next block, and B6 reached its final Saturday without one.

It stays quiet until the penultimate week, then escalates.
"""
from __future__ import annotations

import json
from datetime import date as date_cls, timedelta
from pathlib import Path

from ..hevy.block_report import REPO_ROOT
from .weekly_metrics import DAY_WEEKDAY

BRAIN = REPO_ROOT / "brain"
CURRENT_BLOCK = BRAIN / "current-block.json"
DRAFT_JSON = BRAIN / "next-block-draft.json"
REVIEWS = REPO_ROOT / "reviews"
ARCHIVE = REPO_ROOT / "data" / "block-archive"


def block_end(block: dict) -> date_cls:
    """The last prescribed training day of the block.

    start_date is W1 Monday; the final week's latest prescribed day sets the end. A deload or
    travel week that drops D3/D4 must not report an end date later than it actually trains.
    """
    start = date_cls.fromisoformat(block["start_date"])
    weeks = int(block.get("weeks", 5))
    final = [p.get("day") for p in block.get("prescriptions", []) if p.get("week") == weeks]
    offsets = [DAY_WEEKDAY[d] for d in final if d in DAY_WEEKDAY] or list(DAY_WEEKDAY.values())
    return start + timedelta(days=(weeks - 1) * 7 + max(offsets))


def _archived_ids() -> set[str]:
    return {p.stem for p in ARCHIVE.glob("*.json")}


def draft_status(block_id: str) -> tuple[str, str | None]:
    """(status, draft_block_id) — 'current', 'stale' or 'missing'.

    A draft is STALE rather than current when it describes the running block or a block that
    has already been archived. The real case: `next-block-draft.json` sat on 2026-Q3-B04 from
    July through November, four blocks out of date, and nothing read it as anything but present.
    """
    if not DRAFT_JSON.exists():
        return "missing", None
    try:
        did = json.loads(DRAFT_JSON.read_text()).get("block_id")
    except (json.JSONDecodeError, OSError):
        return "stale", None
    if not did or did == block_id or did in _archived_ids():
        return "stale", did
    return "current", did


def state(block: dict, today: date_cls) -> dict:
    """Handover readiness for the running block as of `today`."""
    block_id = block.get("block_id")
    end = block_end(block)
    weeks = int(block.get("weeks", 5))
    start = date_cls.fromisoformat(block["start_date"])
    # Unclamped, unlike geometry(): after the block ends this keeps counting, which is the
    # whole point — a handover warning has to survive the end of the block.
    week_no = (today - start).days // 7 + 1
    status, draft_id = draft_status(block_id)
    return {
        "block_id": block_id,
        "weeks": weeks,
        "week_no": week_no,
        "end_date": end.isoformat(),
        "days_to_end": (end - today).days,
        "ended": today > end,
        "draft_status": status,
        "draft_block_id": draft_id,
        "review_present": (REVIEWS / f"{block_id}.md").exists(),
        # Quiet until the penultimate week; the draft is due on the W4 Sunday.
        "active": week_no >= weeks - 1,
    }


def blocking(st: dict) -> list[str]:
    """Reasons the handover is overdue, i.e. worth failing the job over.

    Only once the block has actually ended — before that the draft is merely due, and a due
    item should nag, not go red.
    """
    if not st["ended"]:
        return []
    out = []
    if not st["review_present"]:
        out.append(f"{st['block_id']} has ended ({st['end_date']}) and has no review in reviews/")
    if st["draft_status"] != "current":
        out.append(f"{st['block_id']} has ended and the next block is not drafted "
                   f"(next-block-draft.json is {st['draft_status']})")
    return out


def render(st: dict) -> str:
    """Telegram/markdown warning, or '' when there is nothing to say."""
    if not st["active"]:
        return ""
    lines: list[str] = []
    if st["ended"]:
        lines.append(f"<b>🔴 Block handover overdue — {st['block_id']} ended "
                     f"{st['end_date']}.</b>")
    else:
        lines.append(f"<b>📋 Block handover — {st['block_id']} ends {st['end_date']} "
                     f"({st['days_to_end']} days).</b>")

    if st["review_present"]:
        lines.append(f"✅ Block review written (<code>reviews/{st['block_id']}.md</code>).")
    elif st["ended"]:
        lines.append("🔴 <b>No block review.</b> It is the gate on designing the next block — "
                     "run <code>reviewing-block</code> before anything else.")
    else:
        lines.append("⬜ Block review not written yet — due once the last session is logged.")

    if st["draft_status"] == "current":
        lines.append(f"✅ Next block drafted: <b>{st['draft_block_id']}</b>.")
    elif st["draft_status"] == "stale":
        lines.append(f"🔴 <b>next-block-draft.json is STALE</b> — it still describes "
                     f"<b>{st['draft_block_id'] or 'an unreadable block'}</b>. Treat it as absent.")
    else:
        lines.append("🔴 <b>No next-block draft.</b>")

    if st["ended"]:
        lines.append("<i>The next block was due to start the Monday after the block ended. "
                     "Say the word and I'll review and design it now.</i>")
    elif st["draft_status"] != "current":
        lines.append("<i>Draft is due this Sunday (end of the penultimate week), so it can be "
                     "reviewed during the deload.</i>")
    return "\n".join(lines)
