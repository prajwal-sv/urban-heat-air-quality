"""Collect daily PM2.5 and PM10 data from OpenAQ API v3 for January 2025."""

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("OPENAQ_API_KEY")
BASE_URL = "https://api.openaq.org/v3"

SENSORS_PER_POLLUTANT = 3

# Target January 2025 to match your NASA POWER dataset
START_DATETIME = "2025-01-01T00:00:00Z"
END_DATETIME = "2025-01-31T23:59:59Z"

HEADERS = {
    "X-API-Key": API_KEY or "",
    "Accept": "application/json",
}


def main():
    if not API_KEY:
        raise RuntimeError(
            "OPENAQ_API_KEY is missing. Check the .env file."
        )

    sensor_file = PROCESSED_DIR / "openaq_mumbai_sensors.csv"
    if not sensor_file.exists():
        raise FileNotFoundError(
            f"Sensor file not found: {sensor_file}. "
            "Run collect_openaq.py first."
        )

    sensors = pd.read_csv(sensor_file)
    sensors["parameter_name"] = (
        sensors["parameter_name"].astype(str).str.lower()
    )

    selected = []

    for pollutant in ["pm25", "pm10"]:
        candidates = sensors[
            sensors["parameter_name"] == pollutant
        ].dropna(subset=["sensor_id", "location_id"])

        # Prefer different locations for each pollutant.
        candidates = candidates.drop_duplicates(
            subset=["location_id"]
        ).head(SENSORS_PER_POLLUTANT)

        selected.extend(candidates.to_dict("records"))

    if not selected:
        raise RuntimeError(
            "No PM2.5 or PM10 sensors found in the sensor CSV."
        )

    print(f"Date range: {START_DATETIME} through {END_DATETIME}")
    print(f"Sensor requests planned: {len(selected)}")

    all_measurements = []
    raw_responses = []
    failed_requests = []

    for sensor in selected:
        sensor_id = int(sensor["sensor_id"])
        location_id = int(sensor["location_id"])
        pollutant = sensor["parameter_name"]

        url = f"{BASE_URL}/sensors/{sensor_id}/days"
        params = {
            "datetime_from": START_DATETIME,
            "datetime_to": END_DATETIME,
            "limit": 1000,
            "page": 1,
        }

        print(
            f"Requesting {pollutant} sensor {sensor_id} "
            f"at {sensor.get('location_name', 'unknown location')}..."
        )

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()

        except requests.RequestException as error:
            message = str(error)
            if getattr(error, "response", None) is not None:
                message += (
                    f" | HTTP response: "
                    f"{error.response.text[:1000]}"
                )

            print(f"Request failed for sensor {sensor_id}: {message}")
            failed_requests.append({
                "sensor_id": sensor_id,
                "parameter_name": pollutant,
                "error": message,
            })
            time.sleep(0.2)
            continue

        raw_responses.append({
            "sensor_id": sensor_id,
            "location_id": location_id,
            "parameter_name": pollutant,
            "response": payload,
        })

        results = payload.get("results", [])
        print(f"  Daily records returned: {len(results)}")

        for item in results:
            period = item.get("period") or {}
            datetime_from = period.get("datetimeFrom") or {}
            datetime_to = period.get("datetimeTo") or {}
            parameter = item.get("parameter") or {}

            all_measurements.append({
                "sensor_id": sensor_id,
                "location_id": location_id,
                "location_name": sensor.get("location_name"),
                "parameter_name": parameter.get("name", pollutant),
                "value": item.get("value"),
                "unit": parameter.get("units", sensor.get("unit")),
                "period_start_utc": datetime_from.get("utc"),
                "period_start_local": datetime_from.get("local"),
                "period_end_utc": datetime_to.get("utc"),
                "period_end_local": datetime_to.get("local"),
                "latitude": sensor.get("latitude"),
                "longitude": sensor.get("longitude"),
            })

        time.sleep(0.2)

    raw_path = RAW_DIR / "openaq_mumbai_daily_measurements.json"
    with raw_path.open("w", encoding="utf-8") as file:
        json.dump(raw_responses, file, indent=2, ensure_ascii=False)

    output_path = (
        PROCESSED_DIR / "openaq_mumbai_daily_measurements.csv"
    )
    
    if all_measurements:
        df = pd.DataFrame(all_measurements)
    else:
        df = pd.DataFrame(columns=[
            "sensor_id", "location_id", "location_name", "parameter_name",
            "value", "unit", "period_start_utc", "period_start_local",
            "period_end_utc", "period_end_local", "latitude", "longitude"
        ])

    df.to_csv(output_path, index=False)

    failures_path = RAW_DIR / "openaq_measurement_errors.json"
    with failures_path.open("w", encoding="utf-8") as file:
        json.dump(failed_requests, file, indent=2, ensure_ascii=False)

    print("\nCollection finished.")
    print(f"Measurement rows: {len(df)}")
    print(f"CSV saved: {output_path}")
    print(f"Raw responses saved: {raw_path}")
    print(f"Request error log: {failures_path}")

    if not df.empty:
        print("\nRows by pollutant:")
        print(df["parameter_name"].value_counts().to_string())

        print("\nSample measurements:")
        print(df.head(10).to_string(index=False))
    else:
        print(
            "\nNo measurement rows were returned. Check the raw response "
            "and error log before changing the query."
        )

    if failed_requests:
        print(f"\nRequests with errors: {len(failed_requests)}")


if __name__ == "__main__":
    main()
    