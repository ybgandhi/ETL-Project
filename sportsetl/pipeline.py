"""
Transform + Load layer.

``ETLPipeline`` builds one tidy row per team for a given (league, season) and
stitches the three sources together. ``aggregate`` runs any number of
(league, season) pairs and concatenates them into a single long DataFrame with
``League`` and ``Season`` columns -- the shape you want for cross-league,
cross-season analysis (correlations, group-bys, etc.).

The canonical output columns are:

    League | Season | Team City | Team Name | Avg Team Salary
          | Avg Team Age | Avg Temp of City

which matches the original notebook so existing consumers keep working.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from . import extract
from .config import LeagueConfig, get_league, season_end_year

OUTPUT_COLUMNS = [
    "League",
    "Season",
    "Team City",
    "Team Name",
    "Avg Team Salary",
    "Avg Team Age",
    "Avg Temp of City",
]


@dataclass
class ETLPipeline:
    """Runs Extract -> Transform for one league and one season."""

    league: LeagueConfig
    season: str
    weather_api_key: Optional[str] = None

    def run(self) -> pd.DataFrame:
        end_year = season_end_year(self.season)

        salary = extract.salary_for_league(self.league, self.season, end_year)
        age = extract.age_for_league(self.league, end_year)

        # Build the team spine from config so every league lines up on age_abbr.
        spine = pd.DataFrame(
            [
                {
                    "age_abbr": t.age_abbr,
                    "Team City": t.city,
                    "Team Name": t.name,
                    "team_full": f"{t.city} {t.name}",
                }
                for t in self.league.teams
            ]
        )

        df = spine.merge(age, on="age_abbr", how="left")
        df = df.merge(salary, on="team_full", how="left")

        if self.weather_api_key:
            weather = extract.weather_for_teams(self.league.teams, self.weather_api_key)
            df = df.merge(weather, on="age_abbr", how="left")
        else:
            df["avg_temp"] = pd.NA  # weather is optional; leave blank when no key

        df["League"] = self.league.code
        df["Season"] = self.season
        df = df.rename(
            columns={
                "avg_salary": "Avg Team Salary",
                "avg_age": "Avg Team Age",
                "avg_temp": "Avg Temp of City",
            }
        )
        return df[OUTPUT_COLUMNS]


def aggregate(
    specs: Iterable[tuple[str, str]],
    *,
    weather_api_key: Optional[str] = None,
) -> pd.DataFrame:
    """Run many (league_code, season) pairs and stack them into one frame.

    Example::

        aggregate([("NBA", "2017-18"), ("NBA", "2018-19"), ("NFL", "2021")])
    """
    frames = []
    for league_code, season in specs:
        pipe = ETLPipeline(get_league(league_code), season, weather_api_key)
        frames.append(pipe.run())
    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def load_cached_aggregate(*csv_paths: str) -> pd.DataFrame:
    """Concatenate previously-saved aggregated CSVs (offline / demo path)."""
    frames = [pd.read_csv(p) for p in csv_paths]
    return pd.concat(frames, ignore_index=True)


METRIC_COLUMNS = {
    "Avg Team Salary": "Salary",
    "Avg Team Age": "Age",
    "Avg Temp of City": "Temp",
}


def correlation_matrix(
    df: pd.DataFrame,
    *,
    by: Optional[str] = None,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Correlation matrix of the three metrics.

    ``by=None``      -> one matrix over all rows.
    ``by="League"``  -> a dict of matrices, one per league.
    ``by="Season"``  -> a dict of matrices, one per season.

    Salary is z-scored within each (League, Season) before a pooled correlation
    so that leagues on wildly different pay scales (NBA vs NFL) can be combined
    without the bigger-money league dominating the result.
    """
    metrics = [c for c in METRIC_COLUMNS if c in df.columns]
    work = df.copy()
    # Normalize salary within each league+season so scales are comparable.
    work["Avg Team Salary"] = work.groupby(["League", "Season"])[
        "Avg Team Salary"
    ].transform(lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else s * 0)

    def _corr(frame: pd.DataFrame) -> pd.DataFrame:
        return (
            frame[metrics]
            .rename(columns=METRIC_COLUMNS)
            .astype(float)
            .corr()
        )

    if by is None:
        return _corr(work)
    return {key: _corr(g) for key, g in work.groupby(by)}
