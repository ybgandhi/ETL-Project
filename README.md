# ETL-Project

# The Goal of this ETL was to compare NBA Team average salaries, age, and the temeprature of the city they play for.

# Data sources:
Salary data was pulled from a csv file found on Kaggle
Temperature data was pulled from OpenWeather API
Age data was pulled via webscraping basketballreference.com

## Web data source notes
The exact endpoints used in the notebooks (`Database.ipynb` / `Database 106.ipynb`):

- **Age (web scrape)** — `https://www.basketball-reference.com/leagues/NBA_2018_per_minute.html`
  - Scraped with `requests` + `BeautifulSoup`, and the table parsed via `pandas.read_html`.
  - This is the **2017-18 NBA "Per Minute" stats** table; only player name, team, and age were kept.
- **Temperature (API)** — `http://api.openweathermap.org/data/2.5/weather?q=<city>&units=imperial&appid=<key>`
  - Note: the code uses the **current-weather** endpoint (`/data/2.5/weather`), not the historical endpoint mentioned in the narrative; "Golden State" is remapped to "San Francisco" for the lookup.
- **Salary (local CSV)** — `Resources/nba_2017_salary.csv` (originally sourced from Kaggle, 2017-18 season). Not scraped; read locally with pandas.


# Importing Libraries
The below are the libraries used in the analysis
- numpy
- api_key
- requests

# Base Dataframe
- created a list of all NBA team names
- created a list of all the locations associated with the respective NBA team
- created a list of all the cities associated with the locations (will be used for API weather pull)

# Team Salary Data
- The csv file contained players salary for the 2017-18 NBA Season
- enables Pandas to read the csv file and created a dataframe
- used a numpy function to groupby the team names and mean of the salaries

# Team Age Data
- leveraged basketballreference.com to get 2017-18 player per minute stats
- the per minute stats table included team of the players and their respective age as well
- inspected the web url to get the HTML tags and id's from the table to pull the data
- after establishing a base url, ran function requests to get the data from the table based on the html tags
- only needed player name, team name, and age from the web page table
- created a dataframe and inspected it
- ran syntax to remove all duplicate player names so their age only shows up once
- the table pulled in had repeating headers for each new team. the syntax above removed all of them except the one indexed in row 20
- wrote syntax to remove the respective row column
- used a numpy function to groupby the team names and mean age of all the players on the team

# City Weather API
- leverged OpenWeather Historical API to get the average temp of the respective city
- baed on OpenWeather.com API instructions, pulled in city using the list created earlier
- wrote a for loop to collect the city name and the temp of the city 
- stored both values as a row in a dataframe

# Combining DataBases
- used Pandas left join to merge the dataframes
- dropped columns to show only location of the city assoicated with the team, team name, average salary, average age, and average city temp

# Turn into JSON
- create connection using Mongo module
- copy df into the collection variable
- insert data for each row into the df
- for loop will print each 'document'

---

# `sportsetl` — generalized multi-league / multi-season pipeline

The original notebook is NBA-only and single-season. The `sportsetl/` package
refactors that same Extract → Transform → Load flow into reusable, config-driven
code so it can incorporate **other leagues (NFL included out of the box)** and
**aggregate across any number of seasons**.

### Layout
- `sportsetl/config.py` — `LeagueConfig` + `Team` definitions. Adding a league or
  season is a **data change here**, not a code change. Ships with full NBA (30)
  and NFL (32) team → city maps, including weather-city overrides
  (e.g. Warriors → San Francisco, Bills → Orchard Park).
- `sportsetl/extract.py` — one function per source: salary from CSV, age via
  `basketball_reference` **or** `pro_football_reference` scrapers, temperature via
  the OpenWeather API. Sources are pluggable via the `AGE_SOURCES` registry.
- `sportsetl/pipeline.py` — `ETLPipeline` builds one (league, season); `aggregate()`
  stacks many into a single long DataFrame with `League` / `Season` columns;
  `correlation_matrix()` computes the salary/age/temp correlations.
- `sportsetl/plots.py` — renders a labelled correlation heatmap (matplotlib).
- `run_analysis.py` — entrypoint (offline demo mode + `--live` ETL mode).

### Run it
```bash
# Offline demo — uses the cached aggregated CSV, no network/keys needed
python run_analysis.py

# Live ETL across leagues and seasons (needs network + OpenWeather key)
python run_analysis.py --live NBA:2017-18 NBA:2018-19 NFL:2021
```
Outputs (`output/`): `aggregated.csv`, `correlation_matrix.csv`,
`correlation_matrix.png`. When the run spans **more than one league or season**,
it also emits a per-group heatmap for each
(`correlation_league_<CODE>.png`, `correlation_season_<LABEL>.png`) so you can
compare, e.g., NBA vs NFL side by side. A single-league single-season run skips
these and stays clean.

### Salary sources — CSV **or** web scrape
Each league declares its salary source in `config.py`:
- **NBA** → `csv` (the Kaggle file, averaged to team level).
- **NFL** → `web`, scraped from spotrac's player-level contracts table
  (`https://www.spotrac.com/nfl/contracts`).

The web scraper (`extract.salary_from_web`) auto-detects the team and salary
columns by header keyword, parses currency strings (`$1,234,567`, `$12.5M`),
resolves each scraped team token to the config via full name / nickname / city,
and averages to the team level. Any token it can't resolve is printed (and
dropped) so a site-specific alias is easy to spot. Column detection can be
pinned with `team_col` / `salary_col` once you've confirmed the live headers.

```bash
python run_analysis.py --live NFL:2021    # scrapes salaries + ages, no CSV needed
```

> **Note:** scraping spotrac requires outbound access to `spotrac.com`. Some
> managed/CI environments block it at the egress policy (HTTP 403 on CONNECT);
> run from a network that permits it, or fall back to the CSV path below.

### Fallback — supply salaries as a CSV instead
If you'd rather not scrape (or the host is blocked), scaffold a correctly-shaped
CSV straight from the config (team names line up automatically), fill it, and
switch that league's `salary_source` back to `"csv"`:
```bash
python scripts/make_salary_template.py NFL 2021
# -> Resources/NFL_2021_salary.csv  (fill in the SALARY column)
```

### Tests
`tests/test_salary_web.py` drives the scraper's parsing/aggregation against a
local HTML fixture (currency parsing, team resolution, team-level means) — no
network required. Run with `python tests/test_salary_web.py` (or `pytest tests/`).

### Cross-league aggregation note
Salaries are **z-scored within each (league, season)** before pooling, so leagues
on very different pay scales (NBA vs NFL) can be combined without the
bigger-money league dominating the correlation. Per-league / per-season matrices
are available via `correlation_matrix(df, by="League")` / `by="Season"`.

### Salary / Age / Temp correlation — NBA 2017-18
|        | Salary | Age  | Temp |
|--------|--------|------|------|
| Salary | 1.00   | 0.65 | 0.01 |
| Age    | 0.65   | 1.00 | 0.11 |
| Temp   | 0.01   | 0.11 | 1.00 |

Salary and roster age are **moderately correlated (0.65)** — older, veteran teams
cost more. City temperature is **uncorrelated** with both (~0.01 / 0.11): where a
team plays has no bearing on how it's paid or aged.