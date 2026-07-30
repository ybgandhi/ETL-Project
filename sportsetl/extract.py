"""
Extract layer: one function per data source.

Each extractor returns a tidy ``pandas.DataFrame`` keyed by team abbreviation so
the pipeline can merge them regardless of league. Network-dependent extractors
(age scrape, weather API) are written to run for real, but the whole layer is
designed so any single source can be swapped for a cached CSV in offline / CI
runs (see ``pipeline.ETLPipeline`` and ``load_cached_aggregate``).
"""

from __future__ import annotations

import time
from typing import Callable

import pandas as pd
import requests

from .config import LeagueConfig, Team

USER_AGENT = "sports-etl/1.0 (+https://github.com/ybgandhi/ETL-Project)"


# --------------------------------------------------------------------------- #
# Salary  (local CSV -> mean salary per team)
# --------------------------------------------------------------------------- #
def salary_from_csv(
    csv_path: str,
    *,
    team_col: str = "TEAM",
    salary_col: str = "SALARY",
) -> pd.DataFrame:
    """Read a player-level salary CSV and average it up to the team level.

    The CSV only needs a team column and a numeric salary column; column names
    are configurable so the same loader works across leagues and vendors.
    """
    df = pd.read_csv(csv_path)
    df = df[[team_col, salary_col]].dropna()
    df[salary_col] = pd.to_numeric(df[salary_col], errors="coerce")
    grouped = (
        df.groupby(team_col, as_index=False)[salary_col]
        .mean()
        .rename(columns={team_col: "team_full", salary_col: "avg_salary"})
    )
    return grouped


# --------------------------------------------------------------------------- #
# Age  (web scrape -> mean age per team)
# --------------------------------------------------------------------------- #
def _fetch_tables(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    # pandas parses every <table> on the page from the fetched HTML.
    return pd.read_html(resp.text)


def age_from_basketball_reference(url: str, teams: tuple[Team, ...]) -> pd.DataFrame:
    """Mean player age per team from a basketball-reference per-minute table.

    Mirrors the original notebook: drop repeated header rows, de-dupe players
    (a traded player appears once per team plus a "TOT" row), then group by team.
    """
    tables = _fetch_tables(url)
    df = tables[0]
    df = df[df["Tm"] != "Tm"]                 # strip repeated header rows
    df = df[df["Tm"] != "TOT"]                # drop combined-season rows
    df = df.drop_duplicates(subset="Player")  # one row per player
    df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    grouped = (
        df.groupby("Tm", as_index=False)["Age"]
        .mean()
        .rename(columns={"Tm": "age_abbr", "Age": "avg_age"})
    )
    return grouped


def age_from_pro_football_reference(url: str, teams: tuple[Team, ...]) -> pd.DataFrame:
    """Mean player age per team for an NFL season.

    PFR does not expose a single league-wide age table, so we read each team's
    roster page (``/teams/{abbr}/{year}_roster.htm``) and average its ``Age``
    column. ``url`` is the season index page; the ending year is parsed from it.
    """
    season_year = "".join(ch for ch in url if ch.isdigit())[-4:]
    base = "https://www.pro-football-reference.com/teams/{abbr}/{year}_roster.htm"
    rows = []
    for team in teams:
        roster_url = base.format(abbr=team.age_abbr, year=season_year)
        try:
            tables = _fetch_tables(roster_url)
        except Exception:  # noqa: BLE001 - one bad team shouldn't sink the run
            continue
        roster = next((t for t in tables if "Age" in t.columns), None)
        if roster is None:
            continue
        ages = pd.to_numeric(roster["Age"], errors="coerce").dropna()
        if len(ages):
            rows.append({"age_abbr": team.age_abbr, "avg_age": ages.mean()})
        time.sleep(1)  # be polite to the source
    return pd.DataFrame(rows)


AGE_SOURCES: dict[str, Callable[[str, tuple[Team, ...]], pd.DataFrame]] = {
    "basketball_reference": age_from_basketball_reference,
    "pro_football_reference": age_from_pro_football_reference,
}


def age_for_league(league: LeagueConfig, season_end_year: int) -> pd.DataFrame:
    scraper = AGE_SOURCES[league.age_source]
    return scraper(league.age_url(season_end_year), league.teams)


# --------------------------------------------------------------------------- #
# Weather  (OpenWeather current-weather API -> temp per city)
# --------------------------------------------------------------------------- #
OPENWEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"


def weather_for_teams(
    teams: tuple[Team, ...],
    api_key: str,
    *,
    units: str = "imperial",
) -> pd.DataFrame:
    """Current temperature for each team's home city.

    Deduplicates by city so shared markets (e.g. both LA teams) cost one call.
    """
    rows = []
    cache: dict[str, float] = {}
    for team in teams:
        city = team.weather_query
        if city not in cache:
            try:
                resp = requests.get(
                    OPENWEATHER_URL,
                    params={"q": city, "units": units, "appid": api_key},
                    timeout=30,
                ).json()
                cache[city] = resp["main"]["temp"]
            except (KeyError, IndexError, requests.RequestException):
                print(f"{city} not found")
                cache[city] = float("nan")
        rows.append({"age_abbr": team.age_abbr, "avg_temp": cache[city]})
    return pd.DataFrame(rows)
