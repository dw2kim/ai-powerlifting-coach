#!/usr/bin/env python3
"""Regenerate the Skills table in README.md from .claude/skills/*/SKILL.md frontmatter.

Idempotent. Run by the PostToolUse hook whenever a SKILL.md is created/edited, or by
hand: `python3 scripts/gen_skills_readme.py`. Stdlib only — no venv needed, so the hook
works in any shell.

The table is written between the SKILLS:START / SKILLS:END markers in README.md. If the
markers are absent, the section is appended. Each row = skill name, its trigger ("parameter"
equivalent — these skills are invoked conversationally, not with CLI args), and a quick
description (the part of the frontmatter description before its "Triggers" clause).
"""
from __future__ import annotations

import glob
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
README = REPO / "README.md"
START = "<!-- SKILLS:START -->"
END = "<!-- SKILLS:END -->"


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    fm: dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def split_desc(desc: str) -> tuple[str, str]:
    """Split a description into (what-it-does, trigger clause)."""
    parts = re.split(r"\bTriggers?\b", desc, maxsplit=1, flags=re.I)
    what = parts[0].strip().rstrip(".").strip()
    trig = ("Triggers" + parts[1]).strip() if len(parts) > 1 else "—"
    return what, trig


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def build_block() -> str:
    rows = []
    for p in sorted(glob.glob(str(REPO / ".claude" / "skills" / "*" / "SKILL.md"))):
        fm = frontmatter(pathlib.Path(p).read_text())
        name = fm.get("name") or pathlib.Path(p).parent.name
        what, trig = split_desc(fm.get("description", ""))
        rows.append((name, trig, what))

    lines = [
        START,
        "",
        "## Skills",
        "",
        "_Auto-generated from `.claude/skills/*/SKILL.md` by `scripts/gen_skills_readme.py` "
        "(via a PostToolUse hook). Do not edit this table by hand — edit the SKILL.md frontmatter._",
        "",
        "| Skill | Trigger | What it does |",
        "|---|---|---|",
    ]
    for name, trig, what in rows:
        lines.append(f"| `{cell(name)}` | {cell(trig)} | {cell(what)} |")
    lines += ["", END]
    return "\n".join(lines)


def main() -> None:
    block = build_block()
    text = README.read_text()
    i, j = text.find(START), text.find(END)
    if i != -1 and j != -1:
        new = text[:i] + block + text[j + len(END):]
    else:
        new = text.rstrip() + "\n\n" + block + "\n"
    if new != text:
        README.write_text(new)
        print(f"Updated {README} Skills table")
    else:
        print("Skills table already current")


if __name__ == "__main__":
    main()
