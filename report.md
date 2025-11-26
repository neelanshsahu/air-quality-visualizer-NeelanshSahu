# Air Quality Data Visualizer – Analytical Report

## Introduction
The Delhi National Capital Region regularly records hazardous concentrations of fine particulate matter, making continuous monitoring essential for public health. This project ingests hourly readings from the [Open-Meteo Air Quality API](https://open-meteo.com/) for 1 January–31 March 2024 and turns them into actionable insights. The cleaned dataset (`cleaned_air_quality.csv`) tracks PM2.5, PM10, NO₂, SO₂, CO, and the supplied U.S. AQI reference; we additionally compute India-style AQI scores using CPCB breakpoints so that peaks can be compared across pollutants.

## Methodology
1. **Acquisition** – Pulled hourly pollutant concentrations (latitude 28.6139, longitude 77.2090) via the Open-Meteo API. Saved the untouched payload to `data/raw/open_meteo_delhi_q1_2024_hourly.csv` to document provenance.
2. **Cleaning & Processing** – Converted timestamps to local dates, resampled to daily means, interpolated occasional gaps, and converted CO from µg/m³ to mg/m³ to match CPCB limits.
3. **Statistical Analysis** – Used NumPy/Pandas to compute daily & monthly averages, AQI min/max/std, and pollution peaks (see `reports/*.csv` and `reports/metrics.json`).
4. **Visualization** – Generated required Matplotlib plots stored inside `plots/`.
5. **Export** – Saved the cleaned day-level dataset plus summary tables for LMS submission/GitHub.

## Graphs & Observations
- `plots/daily_aqi_trend.png`: AQI oscillates between 60 and 340; the steep drop after 8 February highlights a temporary reprieve before levels rise again late March.
- `plots/monthly_average_pm25.png`: Monthly PM2.5 averages fall from **123 µg/m³ in January** to **59 µg/m³ in February** and **49 µg/m³ in March**, mirroring the seasonal shift away from winter inversions.
- `plots/pm25_vs_pm10.png`: PM2.5 and PM10 show a **0.92 correlation**, indicating that coarse and fine particulates are driven by the same emission sources on most days.
- `plots/pm_trends_subplots.png`: Daily PM2.5 and PM10 curves move almost in lockstep; however, PM10 exhibits larger spikes during dust events in late March.

## Key Findings
- **Worst day:** 19 January 2024 reached an AQI of **342** with PM2.5 topping 174 µg/m³ – dangerous for all population groups.
- **Best day:** 8 February 2024 delivered the cleanest air (AQI ≈ **62**), roughly one-fifth of the January peak.
- **Seasonal averages:** Winter (Jan–Feb) maintained an AQI of **199**, nearly double the early-summer (March) average of **110**, underscoring the effect of stagnant winter air.
- **Pollution peaks:** PM2.5 exceeded 150 µg/m³ on 11 separate days; these peaks always coincided with PM10 surges above 220 µg/m³.
- **Overall means:** Average AQI across the quarter was **169**, with mean PM2.5 **78 µg/m³** and mean PM10 **131 µg/m³**, all exceeding national standards.

## Conclusion
Delhi’s winter-to-spring transition shows meaningful improvements, yet the quarter still spends most days in the “Unhealthy” band. The synchronized behavior of PM2.5 and PM10 suggests that interventions targeting combustion (vehicle exhaust, biomass burning) will yield broad benefits. The automated pipeline can be rerun for future months or additional cities by changing the Open-Meteo coordinates, enabling timely dashboards for campaigns or coursework submissions.

