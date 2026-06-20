"""Turn the weekly metrics blob into a punchy, emoji-rich Telegram review.

The numbers and chart are deterministic; the voice is not. This calls the Anthropic
API with the coach persona + standing orders + the computed stats and asks for a
short, Telegram-formatted review that reads the athlete's notes and RPE the way the
coach would. If ANTHROPIC_API_KEY is missing or the call fails, it falls back to a
deterministic templated message so the Saturday job still ships something useful.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from ..hevy.block_report import REPO_ROOT
from .weekly_metrics import PRIMARIES, fmt_load

MODEL = "claude-opus-4-8"
MAX_TOKENS = 1600

# Status emoji from the RPE-vs-plan flag the metrics layer computed.
FLAG_EMOJI = {"on": "🟢", "warm": "🟡", "hot": "🔴", "none": "⚪"}

SYSTEM = """You are the athlete's long-time strength coach (the persona in CLAUDE.md):
direct, dry, no corporate fluff, a colleague not a cheerleader. You program the Big 5 —
Squat, Competition Bench, Sumo Deadlift, Weighted Pull-up, Weighted Dip — and treat all
five as primary competition lifts. Bench is the priority lift; always call it out.

You are writing the athlete's WEEKLY check-in, delivered to Telegram. It must:
- Be punchy and scannable. Emojis and arrows (⬆️⬇️➡️) to catch the eye. Short lines.
- Use status emoji per lift: 🟢 on-plan/under cap · 🟡 drifting · 🔴 over cap / needs attention.
- Read the RPE and the athlete's notes like a coach — praise discipline, flag cap breaches
  by name, never scold.
- Cover: data readiness, each Big-5 lift (top set vs plan + trend), an RPE watch, a one-line
  accessory note, this-block and long-term (cross-block) progress, and one sharp directive
  for next week.
- Telegram HTML only: <b>…</b> and <i>…</i> for emphasis. No markdown headers, no tables,
  no code fences. Keep it under ~3500 characters.
Explain the WHY briefly where it teaches something. Be honest about flat or down weeks."""


def _read(rel: str) -> str:
    p = REPO_ROOT / rel
    return p.read_text() if p.exists() else ""


def gather_context() -> str:
    """Coaching context the narrative should respect: standing orders, the block
    plan, open injuries, and prior-block verdicts (for the cross-block read)."""
    parts = [
        ("CURRENT BLOCK (plan, standing orders, where-we-are)", _read("brain/current-block.md")),
        ("ACTIVE ISSUES (injuries / restrictions)", _read("brain/active-issues.md")),
        ("PRIOR BLOCK REVIEWS (index + verdicts)", _read("reviews/README.md")),
    ]
    return "\n\n".join(f"## {title}\n{body.strip()}" for title, body in parts if body.strip())


def build_user_prompt(stats: dict, context: str) -> str:
    return (
        "Here is the coaching context:\n\n"
        f"{context}\n\n"
        "------\n\n"
        "Here are this week's computed numbers (Hevy log = source of truth). "
        "`rpe_flag` is on/warm/hot from actual-vs-plan RPE; `actual: null` means the "
        "lift wasn't logged this week (e.g. the day hasn't happened yet):\n\n"
        f"{json.dumps(stats, indent=2)}\n\n"
        "------\n\n"
        "Write the weekly Telegram review now. Lead with a one-line header "
        "(block / week / data-readiness). Then the Big 5, the RPE watch, accessories, "
        "progress (this block + long-term), and the next-week directive."
    )


def narrate(stats: dict, context: str | None = None, model: str = MODEL) -> str:
    """Generate the review via the Anthropic API. Raises on missing key / API error
    so the caller can decide whether to fall back."""
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_user_prompt(stats, context or gather_context())}],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()


def _fmt_set(s: dict | None) -> str:
    if not s:
        return "—"
    rpe = f"@{s['rpe']}" if s.get("rpe") is not None else "@—"
    base = f"{fmt_load(s['added_lb'], s['is_bw'])}×{s['reps']} {rpe}"
    return f"{base} (e1RM {s['e1rm']:g})" if s.get("e1rm") is not None else base


def render_fallback(stats: dict) -> str:
    """Deterministic, no-API message. Less punchy, but always ships."""
    geo = stats["geometry"]
    rd = stats["readiness"]
    ready = "✅ all days logged" if rd["all_in"] else f"⚠️ missing {', '.join(rd['missing'])}"
    lines = [
        f"🏋️ <b>{geo['block_id']} · Week {geo['week_no']}/{geo['weeks']}</b> — weekly review",
        f"Data: {ready}",
        "",
        "<b>Big 5</b>",
    ]
    for lift in stats["big5"]:
        emoji = FLAG_EMOJI.get(lift["rpe_flag"], "⚪")
        tag = " 🏆" if lift["key"] == "bench" else ""
        lines.append(f"{emoji} <b>{lift['name']}</b>{tag}: {_fmt_set(lift['actual'])}")
        if lift["plan"]:
            lines.append(f"   plan {_fmt_set(lift['plan'])}")
    logged = [a["name"] for a in stats["accessories"] if a["logged"]]
    lines += ["", f"<b>Accessories</b>: {len(logged)}/{len(stats['accessories'])} logged."]
    if rd["rpe_gaps"]:
        lines.append(f"⚠️ Top sets missing RPE: {', '.join(rd['rpe_gaps'])}.")
    return "\n".join(lines)


def main() -> None:
    import argparse
    from datetime import date as date_cls

    from .weekly_metrics import build_stats

    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--fallback", action="store_true", help="Skip the API, print template")
    args = ap.parse_args()
    today = date_cls.fromisoformat(args.date) if args.date else None
    stats = build_stats(today)
    print(render_fallback(stats) if args.fallback else narrate(stats))


if __name__ == "__main__":
    main()
