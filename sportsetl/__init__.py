"""
sportsetl -- a configurable, multi-league / multi-season ETL pipeline.

Generalizes the original NBA-only notebook so the same code path can extract,
merge, and analyze salary / age / city-temperature for the NBA, the NFL, or any
league you add to ``config.LEAGUES`` -- across as many seasons as you like.

Quick start::

    from sportsetl import aggregate, correlation_matrix
    df = aggregate([("NBA", "2017-18"), ("NFL", "2021")], weather_api_key=KEY)
    print(correlation_matrix(df, by="League"))
"""

from .config import LEAGUES, LeagueConfig, Team, get_league, season_end_year
from .pipeline import (
    ETLPipeline,
    aggregate,
    correlation_matrix,
    load_cached_aggregate,
)

__all__ = [
    "LEAGUES",
    "LeagueConfig",
    "Team",
    "get_league",
    "season_end_year",
    "ETLPipeline",
    "aggregate",
    "correlation_matrix",
    "load_cached_aggregate",
]
