"""
League / season configuration for the multi-sport ETL pipeline.

Everything that varies from one league (or season) to the next lives here as
data, so adding a new league or a new season is a config change -- not a code
change. The pipeline in ``pipeline.py`` reads these ``LeagueConfig`` objects and
does not hard-code any team, city, or URL itself.

Two leagues ship out of the box:
  * NBA  -- ages scraped from basketball-reference.com
  * NFL  -- ages scraped from pro-football-reference.com

Cities are used both to label the team and to look up weather via OpenWeather.
When a franchise's home city differs from the name people search weather by
(e.g. "Golden State" -> "San Francisco"), set ``weather_city``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Team:
    """A single franchise within a league."""

    name: str            # e.g. "Warriors"
    city: str            # home-market label, e.g. "Golden State"
    age_abbr: str        # abbreviation used by the age source, e.g. "GSW"
    weather_city: Optional[str] = None  # override for the weather lookup

    @property
    def weather_query(self) -> str:
        """City string to send to the weather API."""
        return self.weather_city or self.city


@dataclass(frozen=True)
class LeagueConfig:
    """Everything the pipeline needs to build one league for one season."""

    code: str                       # "NBA", "NFL"
    age_source: str                 # key into extract.AGE_SOURCES
    age_url_template: str           # {end_year} is substituted per season
    salary_csv_template: str        # {code}/{season}; {season_end} available too
    teams: tuple[Team, ...] = field(default_factory=tuple)

    def age_url(self, season_end_year: int) -> str:
        return self.age_url_template.format(end_year=season_end_year)

    def salary_csv(self, season: str, season_end_year: int) -> str:
        return self.salary_csv_template.format(
            code=self.code, season=season, season_end=season_end_year
        )

    def team_by_abbr(self, abbr: str) -> Optional[Team]:
        for t in self.teams:
            if t.age_abbr == abbr:
                return t
        return None


# --------------------------------------------------------------------------- #
# NBA
# --------------------------------------------------------------------------- #
NBA_TEAMS = (
    Team("Hawks", "Atlanta", "ATL"),
    Team("Celtics", "Boston", "BOS"),
    Team("Nets", "Brooklyn", "BRK"),
    Team("Hornets", "Charlotte", "CHO"),
    Team("Bulls", "Chicago", "CHI"),
    Team("Cavaliers", "Cleveland", "CLE"),
    Team("Mavericks", "Dallas", "DAL"),
    Team("Nuggets", "Denver", "DEN"),
    Team("Pistons", "Detroit", "DET"),
    Team("Warriors", "Golden State", "GSW", weather_city="San Francisco"),
    Team("Rockets", "Houston", "HOU"),
    Team("Pacers", "Indiana", "IND", weather_city="Indianapolis"),
    Team("Clippers", "Los Angeles", "LAC"),
    Team("Lakers", "Los Angeles", "LAL"),
    Team("Grizzlies", "Memphis", "MEM"),
    Team("Heat", "Miami", "MIA"),
    Team("Bucks", "Milwaukee", "MIL"),
    Team("Timberwolves", "Minnesota", "MIN", weather_city="Minneapolis"),
    Team("Pelicans", "New Orleans", "NOP"),
    Team("Knicks", "New York", "NYK"),
    Team("Thunder", "Oklahoma City", "OKC"),
    Team("Magic", "Orlando", "ORL"),
    Team("76ers", "Philadelphia", "PHI"),
    Team("Suns", "Phoenix", "PHO"),
    Team("Trail Blazers", "Portland", "POR"),
    Team("Kings", "Sacramento", "SAC"),
    Team("Spurs", "San Antonio", "SAS"),
    Team("Raptors", "Toronto", "TOR"),
    Team("Jazz", "Utah", "UTA", weather_city="Salt Lake City"),
    Team("Wizards", "Washington", "WAS", weather_city="Washington D.C."),
)

NBA = LeagueConfig(
    code="NBA",
    age_source="basketball_reference",
    age_url_template=(
        "https://www.basketball-reference.com/leagues/NBA_{end_year}_per_minute.html"
    ),
    salary_csv_template="Resources/{code}_{season}_salary.csv",
    teams=NBA_TEAMS,
)


# --------------------------------------------------------------------------- #
# NFL
# --------------------------------------------------------------------------- #
NFL_TEAMS = (
    Team("Cardinals", "Arizona", "crd", weather_city="Glendale"),
    Team("Falcons", "Atlanta", "atl"),
    Team("Ravens", "Baltimore", "rav"),
    Team("Bills", "Buffalo", "buf", weather_city="Orchard Park"),
    Team("Panthers", "Carolina", "car", weather_city="Charlotte"),
    Team("Bears", "Chicago", "chi"),
    Team("Bengals", "Cincinnati", "cin"),
    Team("Browns", "Cleveland", "cle"),
    Team("Cowboys", "Dallas", "dal", weather_city="Arlington"),
    Team("Broncos", "Denver", "den"),
    Team("Lions", "Detroit", "det"),
    Team("Packers", "Green Bay", "gnb"),
    Team("Texans", "Houston", "htx"),
    Team("Colts", "Indianapolis", "clt"),
    Team("Jaguars", "Jacksonville", "jax"),
    Team("Chiefs", "Kansas City", "kan"),
    Team("Raiders", "Las Vegas", "rai"),
    Team("Chargers", "Los Angeles", "sdg", weather_city="Inglewood"),
    Team("Rams", "Los Angeles", "ram", weather_city="Inglewood"),
    Team("Dolphins", "Miami", "mia", weather_city="Miami Gardens"),
    Team("Vikings", "Minnesota", "min", weather_city="Minneapolis"),
    Team("Patriots", "New England", "nwe", weather_city="Foxborough"),
    Team("Saints", "New Orleans", "nor"),
    Team("Giants", "New York", "nyg", weather_city="East Rutherford"),
    Team("Jets", "New York", "nyj", weather_city="East Rutherford"),
    Team("Eagles", "Philadelphia", "phi"),
    Team("Steelers", "Pittsburgh", "pit"),
    Team("49ers", "San Francisco", "sfo", weather_city="Santa Clara"),
    Team("Seahawks", "Seattle", "sea"),
    Team("Buccaneers", "Tampa Bay", "tam", weather_city="Tampa"),
    Team("Titans", "Tennessee", "oti", weather_city="Nashville"),
    Team("Commanders", "Washington", "was", weather_city="Landover"),
)

NFL = LeagueConfig(
    code="NFL",
    age_source="pro_football_reference",
    # PFR keys rosters by the season's starting year (single year, not span).
    age_url_template="https://www.pro-football-reference.com/years/{end_year}/",
    salary_csv_template="Resources/{code}_{season}_salary.csv",
    teams=NFL_TEAMS,
)


LEAGUES: dict[str, LeagueConfig] = {NBA.code: NBA, NFL.code: NFL}


def get_league(code: str) -> LeagueConfig:
    try:
        return LEAGUES[code.upper()]
    except KeyError as exc:
        raise KeyError(
            f"Unknown league {code!r}. Known leagues: {sorted(LEAGUES)}"
        ) from exc


def season_end_year(season: str) -> int:
    """Turn a season label into the year the age/roster source keys on.

    Accepts both ``"2017-18"`` (NBA-style span) and ``"2021"`` (single year).
    For a span, returns the ending year (2018); for a single year, returns it.
    """
    season = season.strip()
    if "-" in season:
        start, end = season.split("-", 1)
        start = start.strip()
        end = end.strip()
        # Expand two-digit end ("2017-18" -> 2018), else use as-is.
        if len(end) == 2:
            return int(start[:2] + end)
        return int(end)
    return int(season)
