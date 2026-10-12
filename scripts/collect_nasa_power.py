"""
Collect real daily meteorological data for Mumbai from NASA POWER.

Source:
https://power.larc.nasa.gov/

Important:
These are gridded meteorological estimates, not direct measurements
from a weather station in Mumbai.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# Project folders
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Approximate coordinates for central Mumbai
LATITUDE = 19.0760
LONGITUDE = 72.8777

# A short historical sample for our first test
START_DATE = "20250101"
END_DATE = "20250131"

# • T2M: Temperature at 2 Meters (typically the average or current hourly temperature)
# • T2M_MAX: Maximum Temperature at 2 Meters (the daily high)
# • T2M_MIN: Minimum Temperature at 2 Meters (the daily low)
# • RH2M: Relative Humidity at 2 Meters
PARAMETERS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M"]

API_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)

params = {
    "parameters": ",".join(PARAMETERS),
    "community": "SB",  # Sustainable Buildings community
    "longitude": LONGITUDE,
    "latitude": LATITUDE,
    "start": START_DATE,
    "end": END_DATE,
    "format": "JSON",
    "time-standard": "UTC",
}

def main():
    print("Requesting daily meteorological data from NASA POWER...")
    print(f"Coordinates: {LATITUDE}, {LONGITUDE}")
    print(f"Date range: {START_DATE} to {END_DATE}")

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()

    except requests.RequestException as error:
        print(f"API request failed: {error}")
        return

    except ValueError as error:
        print(f"Could not parse the API response as JSON: {error}")
        return 

    # Save the original response for provenance and debugging.
    raw_path = RAW_DIR / "nasa_power_mumbai_202501.json"   
    with raw_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    print(f"Raw API response saved to: {raw_path}")

    # Safely extract data structure
    properties = payload.get("properties", {})
    parameter_data = properties.get("parameter", {})

    if not parameter_data:
        print("The API response did not contain the expected 'parameter' data.")
        print("Available keys in properties:", list(properties.keys()))
        print(json.dumps(payload, indent=2)[:3000])
        return

    # Each parameter contains daily values keyed by YYYYMMDD.
    records = {}

    for parameter in PARAMETERS:
        daily_values = parameter_data.get(parameter)

        if not isinstance(daily_values, dict):
            print(f"Warning: parameter {parameter} is unavailable.")
            continue

        for date_string, value in daily_values.items():
            record = records.setdefault(date_string, {})
            record[parameter] = value

    if not records:
        print("No daily records were returned. Check the raw JSON file.")
        return

    df = pd.DataFrame.from_dict(records, orient="index")

    df.index.name = "date"
    df = df.reset_index()

    # Convert YYYYMMDD into a proper date.
    df["date"] = pd.to_datetime(
        df["date"],
        format="%Y%m%d",
        errors="coerce",
    )

    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Attach source and spatial metadata to each row.
    df["latitude"] = LATITUDE
    df["longitude"] = LONGITUDE
    df["source"] = "NASA POWER Daily API"
    df["retrieved_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    output_path = (
        PROCESSED_DIR / "mumbai_weather_daily_202501.csv"
    )

    df.to_csv(output_path, index=False)

    print("\nCollection finished.")
    print(f"Rows collected: {len(df)}")
    print(f"CSV saved to: {output_path}")
    print("\nReturned columns:")
    print(df.columns.tolist())
    print("\nFirst five rows:")
    print(df.head().to_string(index=False))
    print("\nMissing values by column:")
    print(df.isna().sum().to_string())


if __name__ == "__main__":
    main()