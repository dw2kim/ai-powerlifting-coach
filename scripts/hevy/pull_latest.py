"""Fetch the N most recent workouts and print as JSON to stdout.

Used by the `reviewing-session` skill: `python -m scripts.hevy.pull_latest --count 1`
"""
from __future__ import annotations

import argparse
import json

from .client import HevyClient


def fetch_latest(count: int = 1) -> list[dict]:
    client = HevyClient()
    data = client.get("/workouts", page=1, pageSize=max(count, 1))
    workouts = data.get("workouts", [])
    return workouts[:count]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    json.dump(fetch_latest(args.count), indent=2, fp=__import__("sys").stdout)


if __name__ == "__main__":
    main()
