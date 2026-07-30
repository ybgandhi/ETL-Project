#!/usr/bin/env python3
"""
Entrypoint: build (or load) the aggregated dataset and emit the correlation
matrix + heatmap.

Two modes:

  Live ETL (needs network + an OpenWeather key in api_keys.weather_api_key)::

      python run_analysis.py --live NBA:2017-18 NBA:2018-19 NFL:2021

  Offline / demo (default) -- reads cached aggregated CSVs from Resources/ so
  it runs anywhere, including CI::

      python run_analysis.py

Outputs land in ./output/ : the combined dataset, the correlation matrix CSV,
and a PNG heatmap.
"""

from __future__ import annotations

import argparse
import os

from sportsetl import aggregate, correlation_matrix, load_cached_aggregate
from sportsetl.plots import plot_correlation_heatmap

OUTPUT_DIR = "output"
DEFAULT_CACHED = ["Resources/nba_2017-18_aggregated.csv"]


def _slug(value: str) -> str:
    """Filesystem-safe token for a league code or season label."""
    return "".join(c if c.isalnum() else "-" for c in str(value)).strip("-")


def parse_specs(items: list[str]) -> list[tuple[str, str]]:
    specs = []
    for item in items:
        league, season = item.split(":", 1)
        specs.append((league.strip().upper(), season.strip()))
    return specs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "specs",
        nargs="*",
        help="league:season pairs, e.g. NBA:2017-18 NFL:2021 (live mode)",
    )
    ap.add_argument("--live", action="store_true", help="run the real ETL pipeline")
    args = ap.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.live:
        try:
            from api_keys import weather_api_key
        except ImportError:
            weather_api_key = os.environ.get("OPENWEATHER_API_KEY")
        specs = parse_specs(args.specs) or [("NBA", "2017-18")]
        print(f"Running live ETL for: {specs}")
        df = aggregate(specs, weather_api_key=weather_api_key)
    else:
        print(f"Loading cached aggregate: {DEFAULT_CACHED}")
        df = load_cached_aggregate(*DEFAULT_CACHED)

    combined_path = os.path.join(OUTPUT_DIR, "aggregated.csv")
    df.to_csv(combined_path, index=False)
    print(f"\nAggregated dataset ({len(df)} rows) -> {combined_path}")
    print(df.head(10).to_string(index=False))

    leagues = ", ".join(sorted(df["League"].unique()))

    # ---- overall matrix + heatmap ----------------------------------------- #
    corr = correlation_matrix(df)
    corr_path = os.path.join(OUTPUT_DIR, "correlation_matrix.csv")
    corr.to_csv(corr_path)
    print("\nCorrelation matrix (salary z-scored within league+season):")
    print(corr.round(3).to_string())
    png = plot_correlation_heatmap(
        corr,
        os.path.join(OUTPUT_DIR, "correlation_matrix.png"),
        title=f"Salary / Age / Temp correlation -- {leagues}",
    )
    print(f"\nHeatmap -> {png}")

    # ---- per-league / per-season breakdowns ------------------------------- #
    # Only emitted when the data actually spans more than one group, so a
    # single-league single-season run stays clean.
    for dim in ("League", "Season"):
        groups = df[dim].nunique()
        if groups < 2:
            continue
        print(f"\nPer-{dim.lower()} breakdown ({groups} groups):")
        for key, sub_corr in correlation_matrix(df, by=dim).items():
            print(f"\n[{dim} = {key}]")
            print(sub_corr.round(3).to_string())
            out = os.path.join(
                OUTPUT_DIR, f"correlation_{dim.lower()}_{_slug(key)}.png"
            )
            plot_correlation_heatmap(
                sub_corr, out, title=f"Salary / Age / Temp -- {dim} {key}"
            )
            print(f"  heatmap -> {out}")


if __name__ == "__main__":
    main()
