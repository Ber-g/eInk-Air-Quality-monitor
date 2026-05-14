#!/usr/bin/env python3
from __future__ import annotations
"""
Fetches air quality data from RSQA (Ville de Montréal official network).
Returns None on failure — never returns fake/random data.
"""
import time as _time
import requests
from datetime import datetime, timedelta

# RSQA always uses HNE (UTC-5). During EDT (summer) we add +1h for local time.
_DST_OFFSET = timedelta(hours=1)

RSQA_API      = "https://donnees.montreal.ca/api/3/action/datastore_search"
RESOURCE_ID   = "f4eca3bf-5ded-4d3c-a8dc-ed42486498f3"
TIMEOUT       = 15
MISSING_VALUE = "-9999"

# All RSQA stations on the island — Id matches the API field "Id"
STATIONS = {
    "rosemont":    {"id": "1",  "name": "Rosemont",          "address": "2580 Saint-Joseph Est"},
    "centre_sud":  {"id": "11", "name": "Centre-Sud",         "address": "75 Ontario Est"},
    "ndg":         {"id": "10", "name": "NDG / Décarie",       "address": "1540 de Roberval"},
    "ahuntsic":    {"id": "9",  "name": "Ahuntsic",            "address": "4240 Charleroi"},
    "st_laurent":  {"id": "8",  "name": "Saint-Laurent",       "address": "1050-A St-Jean-Baptiste"},
    "laval_n":     {"id": "7",  "name": "Nord (Chateauneuf)",  "address": "76540 Chateauneuf"},
    "ste_marie":   {"id": "2",  "name": "Sainte-Marie",        "address": "20965 Ch. Ste-Marie"},
    "verdun":      {"id": "5",  "name": "Verdun / Wilfrid",    "address": "12400 Wilfrid-Oullette"},
}


def fetch(station_key: str) -> dict | None:
    """
    Fetch latest hourly data for a station.

    Returns a dict on success:
        {
            "station": str,
            "address": str,
            "timestamp": datetime,
            "pollutants": {
                "PM2.5": float | None,   # µg/m³, None = sensor offline
                "PM10":  float | None,
                "NO2":   float | None,
                "O3":    float | None,
                "SO2":   float | None,
                "CO":    float | None,
            }
        }
    Returns None if the API call fails entirely.
    """
    station = STATIONS.get(station_key)
    if station is None:
        raise ValueError(f"Unknown station '{station_key}'. Valid: {list(STATIONS)}")

    for attempt in range(2):
        try:
            r = requests.get(RSQA_API, params={
                "resource_id": RESOURCE_ID,
                "limit": 500,
                "sort": "_id desc",
            }, timeout=TIMEOUT)
            r.raise_for_status()
            records = r.json()["result"]["records"]
            return _parse(records, station)
        except Exception as e:
            if attempt == 0:
                continue  # one silent retry
            print(f"[fetcher] RSQA unreachable after 2 attempts: {e}")
            return None



def _parse(records: list, station: dict) -> dict | None:
    """Extract latest-hour data for one station from the full record list."""
    sid = station["id"]

    # Find the latest hour that has data for this station
    station_records = [r for r in records if r.get("Id") == sid]
    if not station_records:
        return None

    # Find the most recent record by (date, hour) — avoids midnight rollover bug
    latest = max(station_records, key=lambda r: (r["date"], int(r["heure"])))
    latest_hour = int(latest["heure"])
    latest_date = latest["date"]

    pollutants = {}
    for r in station_records:
        if int(r["heure"]) == latest_hour:
            val = r["valeur"]
            if val == MISSING_VALUE:
                pollutants[r["pollutant"]] = None
            else:
                fval = float(val)
                # RSQA reports CO in mg/m³, all others in µg/m³ — normalise to µg/m³
                pollutants[r["pollutant"]] = fval * 1000 if r["pollutant"] == "CO" else fval

    ts = datetime.strptime(f"{latest_date} {latest_hour:02d}:00", "%Y-%m-%d %H:%M")
    if _time.localtime().tm_isdst == 1:
        ts += _DST_OFFSET

    return {
        "station":    station["name"],
        "address":    station["address"],
        "timestamp":  ts,
        "pollutants": pollutants,
    }


if __name__ == "__main__":
    print("Testing RSQA fetcher...\n")
    for key in ("rosemont", "centre_sud", "ndg"):
        result = fetch(key)
        if result is None:
            print(f"{key:15} → FAILED")
        else:
            age = datetime.now() - result["timestamp"]
            print(f"{key:15} → {result['station']} | {result['timestamp'].strftime('%H:%M')} ({int(age.total_seconds()/60)}min ago)")
            for pol, val in result["pollutants"].items():
                status = f"{val} µg/m³" if val is not None else "offline"
                print(f"  {pol:8} {status}")
        print()
