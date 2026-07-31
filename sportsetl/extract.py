"""
Extract layer: one function per data source.

Each extractor returns a tidy ``pandas.DataFrame`` keyed by team abbreviation so
the pipeline can merge them regardless of league. Network-dependent extractors
(age scrape, weather API) are written to run for real, but the whole layer is
designed so any single source can be swapped for a cached CSV in offline / CI
runs (see ``pipeline.ETLPipeline`` and ``load_cached_aggregate``).
"""

from __future__ import annotations

import io
import re
import time
from typing import Callable, Optional

import pandas as pd
import requests

from .config import LeagueConfig, Team

USER_AGENT = "sports-etl/1.0 (+https://github.com/ybgandhi/ETL-Project)"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def parse_currency(value) -> float:
    """Turn a money string like ``"$1,234,567"`` or ``"$12.5M"`` into a float.

    Handles ``$``, thousands commas, parentheses for negatives, and ``K``/``M``/
    ``B`` magnitude suffixes. Returns ``NaN`` when nothing numeric is present.
    """
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return float("nan")
    negative = text.startswith("(") and text.endswith(")")
    mult = 1.0
    suffix = text[-1:].upper()
    if suffix in {"K", "M", "B"}:
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}[suffix]
        text = text[:-1]
    cleaned = re.sub(r"[^0-9.]", "", text)
    if cleaned in {"", "."}:
        return float("nan")
    num = float(cleaned) * mult
    return -num if negative else num


def build_team_resolver(teams: tuple[Team, ...]) -> Callable[[object], Optional[Team]]:
    """Resolve a scraped team token to a config ``Team``.

    Matches, in order: exact "City Name", nickname, the token's last word as a
    nickname, then city. Nickname is preferred over city so shared markets
    (both LA / both NY teams) resolve correctly. Returns ``None`` if unmatched.
    """
    full = {f"{t.city} {t.name}".lower(): t for t in teams}
    nick = {t.name.lower(): t for t in teams}
    city: dict[str, Team] = {}
    for t in teams:
        city.setdefault(t.city.lower(), t)

    def resolve(token) -> Optional[Team]:
        tok = str(token).strip().lower()
        if not tok:
            return None
        if tok in full:
            return full[tok]
        if tok in nick:
            return nick[tok]
        last = tok.split()[-1]
        if last in nick:
            return nick[last]
        return city.get(tok)

    return resolve


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
# Salary  (web scrape, e.g. spotrac.com -> mean salary per team)
# --------------------------------------------------------------------------- #
TEAM_HEADER_KEYWORDS = ("team", "club", "tm")
SALARY_HEADER_KEYWORDS = (
    "salary", "cap hit", "cap", "total value", "total", "value",
    "avg", "aav", "cash", "apy", "amount",
)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a MultiIndex header (grouped columns) into single strings."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " ".join(str(p) for p in tup if str(p) and "Unnamed" not in str(p)).strip()
            for tup in df.columns
        ]
    return df


def _pick_column(columns, keywords, override: Optional[str]) -> Optional[str]:
    if override is not None:
        return override if override in columns else None
    lowered = {str(c).lower(): c for c in columns}
    for c_lower, c in lowered.items():
        if any(k in c_lower for k in keywords):
            return c
    return None


def parse_salary_table(
    tables: list[pd.DataFrame],
    teams: tuple[Team, ...],
    *,
    team_col: Optional[str] = None,
    salary_col: Optional[str] = None,
) -> pd.DataFrame:
    """Turn a list of parsed HTML tables into ``team_full`` / ``avg_salary``.

    Split out from the network fetch so it is unit-testable against a fixture.
    Auto-detects the team and salary columns by header keyword unless overridden,
    parses currency strings, resolves team tokens to the league's config, and
    averages to the team level. Prints any team tokens it could not resolve so a
    site-specific alias is easy to spot and add.
    """
    resolve = build_team_resolver(teams)
    best: Optional[tuple[pd.DataFrame, str, str]] = None
    for raw in tables:
        df = _flatten_columns(raw)
        t_col = _pick_column(df.columns, TEAM_HEADER_KEYWORDS, team_col)
        s_col = _pick_column(df.columns, SALARY_HEADER_KEYWORDS, salary_col)
        if t_col is None or s_col is None:
            continue
        if best is None or len(df) > len(best[0]):
            best = (df, t_col, s_col)

    if best is None:
        raise ValueError(
            "No table with detectable team + salary columns. "
            "Pass team_col/salary_col explicitly."
        )

    df, t_col, s_col = best
    work = pd.DataFrame(
        {
            "team_obj": df[t_col].map(resolve),
            "salary": df[s_col].map(parse_currency),
        }
    )
    unresolved = sorted(
        {str(tok) for tok, obj in zip(df[t_col], work["team_obj"]) if obj is None}
    )
    if unresolved:
        print(f"[salary_from_web] unresolved team tokens (dropped): {unresolved}")

    work = work.dropna(subset=["team_obj", "salary"])
    work["team_full"] = work["team_obj"].map(lambda t: f"{t.city} {t.name}")
    grouped = (
        work.groupby("team_full", as_index=False)["salary"]
        .mean()
        .rename(columns={"salary": "avg_salary"})
    )
    return grouped


def salary_from_web(
    url: str,
    teams: tuple[Team, ...],
    *,
    team_col: Optional[str] = None,
    salary_col: Optional[str] = None,
) -> pd.DataFrame:
    """Scrape a player-level salary table (e.g. spotrac.com) to team means.

    Fetches ``url`` and delegates parsing to :func:`parse_salary_table`. Column
    detection is automatic but can be pinned via ``team_col`` / ``salary_col``
    once you have confirmed the live page's exact headers.
    """
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    return parse_salary_table(
        tables, teams, team_col=team_col, salary_col=salary_col
    )


# --------------------------------------------------------------------------- #
# Age  (web scrape -> mean age per team)
# --------------------------------------------------------------------------- #
def _fetch_tables(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    # pandas parses every <table> on the page from the fetched HTML.
    return pd.read_html(io.StringIO(resp.text))


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


def salary_for_league(
    league: LeagueConfig, season: str, season_end_year: int
) -> pd.DataFrame:
    """Dispatch to the league's configured salary source (``csv`` or ``web``)."""
    if league.salary_source == "web":
        if not league.salary_url_template:
            raise ValueError(f"{league.code} salary_source=web but no URL template")
        return salary_from_web(
            league.salary_url(season_end_year),
            league.teams,
            team_col=league.team_col,
            salary_col=league.salary_col,
        )
    return salary_from_csv(league.salary_csv(season, season_end_year))


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
