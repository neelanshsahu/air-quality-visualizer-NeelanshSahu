"""
Air Quality Data Visualizer pipeline.

This script downloads hourly pollutant concentrations for Delhi from the
Open-Meteo Air Quality API, converts them to daily aggregates, computes AQI,
and generates all assignment deliverables (CSV + plots + summary tables).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import json
import math
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "open_meteo_delhi_q1_2024_hourly.csv"
CLEAN_DATA_PATH = PROJECT_ROOT / "cleaned_air_quality.csv"
PLOTS_DIR = PROJECT_ROOT / "plots"
REPORTS_DIR = PROJECT_ROOT / "reports"

CITY = "Delhi"
LATITUDE = 28.6139
LONGITUDE = 77.209
START_DATE = "2024-01-01"
END_DATE = "2024-03-31"
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co"]
API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_hourly_data() -> pd.DataFrame:
    """Pull hourly air-quality readings for the configured city."""
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,us_aqi",
        "timeformat": "iso8601",
        "timezone": "auto",
    }
    print("Downloading hourly observations from Open-Meteo…")
    response = requests.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly")
    if not hourly:
        raise RuntimeError("Open-Meteo response did not include hourly data.")
    df = pd.DataFrame(hourly)
    df["datetime"] = pd.to_datetime(df["time"])
    df = df.drop(columns=["time"])
    df = df.rename(
        columns={
            "pm2_5": "pm25",
            "carbon_monoxide": "co",
            "nitrogen_dioxide": "no2",
            "sulphur_dioxide": "so2",
            "us_aqi": "aqi_reference",
        }
    )
    # Convert CO from µg/m³ (API default) to mg/m³ to align with CPCB breakpoints
    df["co"] = df["co"] / 1000.0
    df["city"] = CITY
    df["latitude"] = LATITUDE
    df["longitude"] = LONGITUDE
    return df


def preprocess(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly readings to daily averages and clean missing values."""
    hourly = raw_df.copy()
    hourly = hourly.set_index("datetime")
    daily = hourly.resample("D").mean(numeric_only=True).reset_index()
    daily["date"] = daily["datetime"].dt.date
    pollutant_cols = [col for col in POLLUTANTS if col in daily.columns]
    for col in pollutant_cols:
        daily[col] = daily[col].interpolate(limit_direction="both")
    daily["AQI_reference"] = daily.pop("aqi_reference")
    return daily.drop(columns=["datetime"])


Breakpoint = Tuple[float, float, int, int]


AQI_BREAKPOINTS: Dict[str, List[Breakpoint]] = {
    "pm25": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 500, 401, 500),
    ],
    "pm10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 600, 401, 500),
    ],
    "no2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 600, 401, 500),
    ],
    "so2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 2000, 401, 500),
    ],
    "co": [
        (0.0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, 50.0, 401, 500),
    ],
}


def compute_sub_index(value: float, breakpoints: List[Breakpoint]) -> float:
    """Compute the pollutant sub-index using CPCB-style breakpoints."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan
    for conc_lo, conc_hi, aqi_lo, aqi_hi in breakpoints:
        if value <= conc_hi:
            return ((aqi_hi - aqi_lo) / (conc_hi - conc_lo)) * (value - conc_lo) + aqi_lo
    # extend final segment when concentration exceeds final breakpoint
    conc_lo, conc_hi, aqi_lo, aqi_hi = breakpoints[-1]
    return ((aqi_hi - aqi_lo) / (conc_hi - conc_lo)) * (value - conc_lo) + aqi_lo


def add_aqi_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add AQI and dominant pollutant columns."""
    df = df.copy()
    sub_indices = {}
    for pollutant, breakpoints in AQI_BREAKPOINTS.items():
        if pollutant in df.columns:
            sub_indices[pollutant] = df[pollutant].apply(
                lambda value, bps=breakpoints: compute_sub_index(value, bps)
            )
    sub_df = pd.DataFrame(sub_indices)
    df["AQI"] = sub_df.max(axis=1)
    df["dominant_pollutant"] = sub_df.idxmax(axis=1)
    return df


def seasonal_label(month: int) -> str:
    """Map month numbers to Indian season names."""
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4):
        return "Summer"
    if month in (5, 6, 7):
        return "Monsoon"
    if month in (8, 9, 10):
        return "Post Monsoon"
    return "Late Autumn"


def summarize(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Produce daily, monthly, and seasonal summaries."""
    full = df.copy()
    full["date"] = pd.to_datetime(full["date"])
    full = full.sort_values("date")
    daily = full.set_index("date")
    monthly = daily.resample("ME").mean(numeric_only=True)
    monthly.index = monthly.index.to_period("M")
    seasonal = full.copy()
    seasonal["season"] = seasonal["date"].dt.month.apply(seasonal_label)
    seasonal_summary = (
        seasonal.groupby("season")[["AQI", "pm25", "pm10", "no2", "so2", "co"]]
        .mean(numeric_only=True)
        .reindex(["Winter", "Summer", "Monsoon", "Post Monsoon", "Late Autumn"])
        .dropna(how="all", subset=["AQI", "pm25", "pm10"])
    )
    return {
        "daily": daily,
        "monthly": monthly,
        "seasonal": seasonal_summary,
    }


def save_plots(daily: pd.DataFrame, monthly: pd.DataFrame) -> None:
    """Generate assignment-mandated visualizations."""
    PLOTS_DIR.mkdir(exist_ok=True, parents=True)

    # Line chart: Daily AQI trend
    plt.figure(figsize=(12, 5))
    plt.plot(daily.index, daily["AQI"], color="#d62728")
    plt.title("Daily AQI Trend – Delhi (Q1 2024)")
    plt.xlabel("Date")
    plt.ylabel("AQI")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "daily_aqi_trend.png", dpi=150)
    plt.close()

    # Bar chart: Monthly average PM2.5
    plt.figure(figsize=(8, 5))
    monthly_pm25 = monthly["pm25"]
    monthly_pm25.plot(kind="bar", color="#1f77b4")
    plt.title("Monthly Average PM2.5")
    plt.ylabel("µg/m³")
    plt.xlabel("Month")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "monthly_average_pm25.png", dpi=150)
    plt.close()

    # Scatter plot: PM2.5 vs PM10
    plt.figure(figsize=(6, 5))
    plt.scatter(daily["pm25"], daily["pm10"], alpha=0.7, c=daily["AQI"], cmap="plasma")
    plt.colorbar(label="AQI")
    plt.xlabel("PM2.5 (µg/m³)")
    plt.ylabel("PM10 (µg/m³)")
    plt.title("PM2.5 vs PM10 Concentration")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "pm25_vs_pm10.png", dpi=150)
    plt.close()

    # Subplots: comparative daily PM2.5 & PM10
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(daily.index, daily["pm25"], color="#2ca02c")
    axes[0].set_title("Daily PM2.5")
    axes[0].set_ylabel("µg/m³")
    axes[0].grid(alpha=0.2)
    axes[1].plot(daily.index, daily["pm10"], color="#ff7f0e")
    axes[1].set_title("Daily PM10")
    axes[1].set_ylabel("µg/m³")
    axes[1].grid(alpha=0.2)
    axes[1].set_xlabel("Date")
    fig.suptitle("Particulate Matter Trends – Delhi (Q1 2024)", y=0.95, fontsize=14)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "pm_trends_subplots.png", dpi=150)
    plt.close()


def persist_outputs(clean_df: pd.DataFrame, summaries: Dict[str, pd.DataFrame]) -> None:
    """Write cleaned CSV and summary tables."""
    clean_df.to_csv(CLEAN_DATA_PATH, index=False)
    summaries["daily"].reset_index().to_csv(REPORTS_DIR / "daily_summary.csv", index=False)
    summaries["monthly"].to_csv(REPORTS_DIR / "monthly_summary.csv")
    summaries["seasonal"].to_csv(REPORTS_DIR / "seasonal_summary.csv")


def export_metrics(clean_df: pd.DataFrame) -> None:
    """Store key metrics for the written report."""
    stats = {
        "aqi_min": float(np.nanmin(clean_df["AQI"])),
        "aqi_max": float(np.nanmax(clean_df["AQI"])),
        "aqi_std": float(np.nanstd(clean_df["AQI"])),
        "aqi_mean": float(np.nanmean(clean_df["AQI"])),
        "pm25_mean": float(np.nanmean(clean_df["pm25"])),
        "pm10_mean": float(np.nanmean(clean_df["pm10"])),
        "pm25_pm10_corr": float(clean_df["pm25"].corr(clean_df["pm10"])),
        "worst_day": clean_df.loc[clean_df["AQI"].idxmax(), "date"].isoformat(),
        "best_day": clean_df.loc[clean_df["AQI"].idxmin(), "date"].isoformat(),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


def main() -> None:
    REPORTS_DIR.mkdir(exist_ok=True, parents=True)
    RAW_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("Starting Open-Meteo pipeline…")
    raw_df = fetch_hourly_data()
    raw_df.to_csv(RAW_DATA_PATH, index=False)
    clean_df = preprocess(raw_df)
    clean_df = add_aqi_columns(clean_df)
    summaries = summarize(clean_df)
    save_plots(summaries["daily"], summaries["monthly"])
    persist_outputs(clean_df, summaries)
    export_metrics(clean_df)
    print(
        textwrap.dedent(
            f"""
            Pipeline complete:
              • Clean dataset -> {CLEAN_DATA_PATH}
              • Plots saved -> {PLOTS_DIR}
              • Summaries -> {REPORTS_DIR}
            """
        ).strip()
    )


if __name__ == "__main__":
    main()

