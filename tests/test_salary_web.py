"""
Unit tests for the web salary scraper's parsing/aggregation logic.

These exercise the exact code path a live spotrac fetch would hit
(``parse_salary_table``), but drive it from a local HTML fixture so they run
offline / in CI with no network. Run with:  python -m pytest tests/ -q
"""

import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sportsetl.config import NFL
from sportsetl.extract import (
    build_team_resolver,
    parse_currency,
    parse_salary_table,
)

# A spotrac-style player-level table: money as "$#,###,###", team as nickname.
FIXTURE_HTML = """
<table>
  <thead><tr><th>Player</th><th>Pos</th><th>Team</th><th>Total Value</th></tr></thead>
  <tbody>
    <tr><td>Player A</td><td>QB</td><td>Cardinals</td><td>$10,000,000</td></tr>
    <tr><td>Player B</td><td>WR</td><td>Cardinals</td><td>$6,000,000</td></tr>
    <tr><td>Player C</td><td>QB</td><td>Kansas City Chiefs</td><td>$40,000,000</td></tr>
    <tr><td>Player D</td><td>DE</td><td>Chiefs</td><td>$20,000,000</td></tr>
    <tr><td>Player E</td><td>RB</td><td>49ers</td><td>$5,500,000</td></tr>
  </tbody>
</table>
"""


def test_parse_currency():
    assert parse_currency("$1,234,567") == 1234567.0
    assert parse_currency("$12.5M") == 12_500_000.0
    assert parse_currency("$2B") == 2_000_000_000.0
    assert parse_currency("(500)") == -500.0
    assert parse_currency("") != parse_currency("")  # NaN != NaN
    assert parse_currency(4200000) == 4200000.0


def test_team_resolver_full_nickname_city():
    resolve = build_team_resolver(NFL.teams)
    assert resolve("Kansas City Chiefs").name == "Chiefs"   # full
    assert resolve("Chiefs").name == "Chiefs"               # nickname
    assert resolve("49ers").name == "49ers"                 # numeric nickname
    assert resolve("Arizona").name == "Cardinals"           # city
    assert resolve("Cardinals").city == "Arizona"
    assert resolve("Nonexistent FC") is None


def test_parse_salary_table_aggregates_to_team_mean():
    tables = pd.read_html(io.StringIO(FIXTURE_HTML))
    out = parse_salary_table(tables, NFL.teams)
    by = dict(zip(out["team_full"], out["avg_salary"]))
    assert by["Arizona Cardinals"] == 8_000_000.0      # (10M + 6M) / 2
    assert by["Kansas City Chiefs"] == 30_000_000.0    # (40M + 20M) / 2
    assert by["San Francisco 49ers"] == 5_500_000.0
    assert set(out.columns) == {"team_full", "avg_salary"}


def test_parse_salary_table_column_override():
    tables = pd.read_html(io.StringIO(FIXTURE_HTML))
    out = parse_salary_table(
        tables, NFL.teams, team_col="Team", salary_col="Total Value"
    )
    assert len(out) == 3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
