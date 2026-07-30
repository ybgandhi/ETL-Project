#!/usr/bin/env python3
"""
Generate a drop-in salary CSV template for any configured league/season.

The pipeline merges salary on the full team label ("City Name"), so this script
emits the exact `TEAM` strings the pipeline expects -- fill in real player rows
and a live run works with no code changes.

Usage:
    python scripts/make_salary_template.py NFL 2021
    python scripts/make_salary_template.py NBA 2018-19 --rows 3
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sportsetl.config import get_league  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("league", help="league code, e.g. NFL or NBA")
    ap.add_argument("season", help="season label, e.g. 2021 or 2018-19")
    ap.add_argument(
        "--rows", type=int, default=1,
        help="placeholder player rows per team (default 1)",
    )
    args = ap.parse_args()

    league = get_league(args.league)
    out_path = f"Resources/{league.code}_{args.season}_salary.csv"

    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["NAME", "POSITION", "TEAM", "SALARY"])
        for team in league.teams:
            full = f"{team.city} {team.name}"
            for i in range(args.rows):
                # SALARY intentionally blank -- replace with real player data.
                w.writerow([f"<player {i + 1}>", "", full, ""])

    print(f"Wrote template -> {out_path} ({len(league.teams)} teams)")
    print("Fill the SALARY column with real player salaries, then run:")
    print(f"    python run_analysis.py --live {league.code}:{args.season}")


if __name__ == "__main__":
    main()
