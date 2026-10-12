"""
Discover real air-quality monitoring locations near Mumbai using OpenAQ API v3.

This first step collects station and sensor metadata.
It does not assume that every station measures PM2.5 or PM10.
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("OPENAQ_API_KEY")

BASE_URL = "https://api.openaq.org/v3"
LATITUDE = 19.0760
LONGITUDE = 72.8777
RADIUS_METERS = 25000
LOCATION_LIMIT = 100

HEADERS = {
    "X-API-Key": API_KEY or "",
    "Accept": "application/json",
}

def get_json(url, params=None):
    """Request JSON from OpenAQ and report useful HTTP errors."""
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def main():
    if not API_KEY or API_KEY == "your_actual_key_here":
        print("ERROR: OpenAQ API key is missing.")
        print("Check the OPENAQ_API_KEY line in your project .env file.")
        return

    print("Searching for OpenAQ monitoring locations near Mumbai...")
    print(f"Centre: {LATITUDE}, {LONGITUDE}")
    print(f"Search radius: {RADIUS_METERS} metres")
    locations_url = f"{BASE_URL}/locations"

    try:
        payload = get_json(
            locations_url,
            params={
                "coordinates": f"{LATITUDE},{LONGITUDE}",
                "radius": RADIUS_METERS,
                "limit": LOCATION_LIMIT,
                "page": 1,
            },
        )
    except requests.RequestException as error:
        print(f"OpenAQ location request failed: {error}")
        if getattr(error, "response", None) is not None:
            print("Response details:", error.response.text[:1500])
        return

    # Preserve the original API response.
    raw_locations_path = RAW_DIR / "openaq_mumbai_locations.json"
    with raw_locations_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

    locations = payload.get("results", [])
    print(f"Locations returned by API: {len(locations)}")

    if not locations:
        print("No locations returned. Check the saved JSON and API response.")
        return

    location_rows = []
    sensor_rows = []
    raw_sensor_responses = []

    for location in locations:
        coordinates = location.get("coordinates") or {}
        country = location.get("country") or {}

        location_id = location.get("id")

        location_rows.append({
            "location_id": location_id,
            "location_name": location.get("name"),
            "locality": location.get("locality"),
            "country_code": country.get("code"),
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "timezone": location.get("timezone"),
            "is_mobile": location.get("isMobile"),
            "is_monitor": location.get("isMonitor"),
        })

        if location_id is None:
            continue

        sensors_url = f"{BASE_URL}/locations/{location_id}/sensors"

        try:
            sensor_payload = get_json(
                sensors_url,
                params={"limit": 100, "page": 1},
            )
        except requests.RequestException as error:
            print(
                f"Could not retrieve sensors for location "
                f"{location_id}: {error}"
            )
            continue

        raw_sensor_responses.append({
            "location_id": location_id,
            "response": sensor_payload,
        })

        for sensor in sensor_payload.get("results", []):
            parameter = sensor.get("parameter") or {}

            sensor_rows.append({
                "location_id": location_id,
                "location_name": location.get("name"),
                "sensor_id": sensor.get("id"),
                "sensor_name": sensor.get("name"),
                "parameter_id": parameter.get("id"),
                "parameter_name": parameter.get("name"),
                "parameter_display_name": parameter.get("displayName"),
                "unit": parameter.get("units"),
                "latitude": coordinates.get("latitude"),
                "longitude": coordinates.get("longitude"),
            })

        # Be polite to the API between location requests.
        time.sleep(0.15)

    raw_sensors_path = RAW_DIR / "openaq_mumbai_sensors.json"
    with raw_sensors_path.open("w", encoding="utf-8") as file:
        json.dump(
            raw_sensor_responses,
            file,
            indent=2,
            ensure_ascii=False,
        )

    locations_df = pd.DataFrame(location_rows)
    sensors_df = pd.DataFrame(sensor_rows)

    locations_path = PROCESSED_DIR / "openaq_mumbai_locations.csv"
    sensors_path = PROCESSED_DIR / "openaq_mumbai_sensors.csv"

    locations_df.to_csv(locations_path, index=False)
    sensors_df.to_csv(sensors_path, index=False)

    print("\nDiscovery finished.")
    print(f"Locations saved: {locations_path}")
    print(f"Sensors saved: {sensors_path}")
    print(f"Raw location response: {raw_locations_path}")
    print(f"Raw sensor responses: {raw_sensors_path}")
    print(f"Location rows: {len(locations_df)}")
    print(f"Sensor rows: {len(sensors_df)}")

    if not sensors_df.empty:
        print("\nAvailable pollutant/parameter counts:")
        print(
            sensors_df["parameter_name"]
            .fillna("unknown")
            .value_counts()
            .to_string()
        )

        print("\nFirst 10 sensors:")
        print(sensors_df.head(10).to_string(index=False))
    else:
        print(
            "\nNo sensor rows were returned. This is not proof that "
            "Mumbai has no air-quality sensors; inspect the API responses."
        )

if __name__ == "__main__":
    main()