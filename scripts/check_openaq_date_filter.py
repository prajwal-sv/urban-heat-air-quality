
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

api_key = os.getenv("OPENAQ_API_KEY")
if not api_key:
    raise RuntimeError("OPENAQ_API_KEY is missing from .env")

sensor_id = 5404
url = f"https://api.openaq.org/v3/sensors/{sensor_id}/days"

params = {
    "date_from": "2025-01-01",
    "date_to": "2025-01-31",
    "limit": 5,
    "page": 1,
}

response = requests.get(
    url,
    headers={"X-API-Key": api_key, "Accept": "application/json"},
    params=params,
    timeout=30,
)

print("HTTP status:", response.status_code)
print("Request URL:", response.url)
print("Response preview:", response.text[:1500])
response.raise_for_status()

payload = response.json()
print("\nAPI metadata:", payload.get("meta"))
results = payload.get("results", [])
print("Records returned:", len(results))

for row in results:
    period = row.get("period") or {}
    start = period.get("datetimeFrom") or {}
    end = period.get("datetimeTo") or {}
    print(
        "Start:", start.get("local"),
        "| End:", end.get("local"),
        "| Value:", row.get("value"),
    )
