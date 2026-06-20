"""Render the weekly progress chart (PNG) from the metrics blob.

Two panels, dark theme, large fonts so it reads on a phone:
  - left : block-to-date e1RM per Big-5, week by week (this block's trend)
  - right: long-term best e1RM per Big-5, month by month (cross-block progress)

Headless (Agg backend), so it runs fine on a CI runner with no display.
"""
from __future__ import annotations

import argparse
from datetime import date as date_cls
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .weekly_metrics import PRIMARIES, build_stats  # noqa: E402

# One stable colour per lift, plus a phone-readable display label.
STYLE = {
    "squat": ("#ff6b6b", "Squat"),
    "bench": ("#ffd93d", "Bench"),
    "sumo": ("#6bcB77", "Sumo"),
    "wpu": ("#4d96ff", "Pull-up"),
    "dip": ("#c780fa", "Dip"),
}
BG = "#0f1115"
FG = "#e6e6e6"
GRID = "#2a2f3a"
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(ym: str) -> str:
    """'2026-06' -> 'Jun '26'."""
    y, m = ym.split("-")
    return f"{MONTHS[int(m)]} '{y[2:]}"


def _style_axes(ax) -> None:
    ax.set_facecolor(BG)
    ax.tick_params(colors=FG, labelsize=12)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.7)
    ax.title.set_color(FG)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)


def render(stats: dict, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    # Week keys may be ints (in-memory) or strings (JSON round-trip) — normalize.
    block_to_date = {int(k): v for k, v in stats["block_to_date"].items()}
    longterm = stats["longterm"]
    geo = stats["geometry"]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13.0, 6.0))
    fig.patch.set_facecolor(BG)

    # --- Panel A: this block, e1RM by week ---
    weeks = sorted(block_to_date)
    for key, _name, _tid, _bw in PRIMARIES:
        color, label = STYLE[key]
        xs = [w for w in weeks if block_to_date[w][key] is not None]
        ys = [block_to_date[w][key] for w in xs]
        if not ys:
            continue
        axL.plot(xs, ys, marker="o", markersize=8, linewidth=2.6,
                 color=color, label=label)
        axL.annotate(f"{ys[-1]:g}", (xs[-1], ys[-1]), color=color,
                     fontsize=11, fontweight="bold",
                     xytext=(6, 4), textcoords="offset points")
    axL.set_title(f"{geo['block_id']} · e1RM by week", fontsize=15, fontweight="bold")
    axL.set_xlabel("Week")
    axL.set_ylabel("Estimated 1RM (lb)")
    axL.set_xticks(weeks)
    _style_axes(axL)

    # --- Panel B: long-term, monthly best e1RM ---
    all_months: list[str] = sorted({pt["month"] for s in longterm.values() for pt in s})
    idx = {m: i for i, m in enumerate(all_months)}
    for key, _name, _tid, _bw in PRIMARIES:
        color, label = STYLE[key]
        series = longterm.get(key, [])
        if not series:
            continue
        xs = [idx[pt["month"]] for pt in series]
        ys = [pt["e1rm"] for pt in series]
        axR.plot(xs, ys, marker="o", markersize=6, linewidth=2.4,
                 color=color, label=label)
    axR.set_title("Long-term · best e1RM by month", fontsize=15, fontweight="bold")
    axR.set_xlabel("Month")
    axR.set_xticks(range(len(all_months)))
    axR.set_xticklabels([_month_label(m) for m in all_months], rotation=45, ha="right")
    _style_axes(axR)

    # Shared legend across the top.
    handles, labels = axL.get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc="upper center", ncol=5,
                     frameon=False, fontsize=12.5, bbox_to_anchor=(0.5, 1.02))
    for text in leg.get_texts():
        text.set_color(FG)

    fig.suptitle("")  # legend sits in the top margin
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=130, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Override 'today' (YYYY-MM-DD)")
    ap.add_argument("--out", default="weekly_review_chart.png")
    args = ap.parse_args()
    today = date_cls.fromisoformat(args.date) if args.date else None
    path = render(build_stats(today), args.out)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
