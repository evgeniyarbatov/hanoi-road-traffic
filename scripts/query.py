import time
import osmium
import datetime
import json
import os
import psycopg2
import requests
import argparse
from shapely.geometry import LineString
from dotenv import load_dotenv

# === Load ENVIRONMENT VARIABLES ===
load_dotenv()
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')
if not TOMTOM_API_KEY:
    raise Exception("TOMTOM_API_KEY not found in .env file")

# === DATABASE CONFIG ===
DB_CONFIG = {
    'dbname': 'traffic',
    'user': 'root',
    'password': 'DKW9b9agY23e',
    'host': 'localhost',
    'port': 5432
}
MAX_CALLS_PER_DAY = 50000
API_URL = 'https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json'

# === OSM HANDLER ===
class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.ways = []

    def way(self, w):
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
            if len(coords) >= 2:
                self.ways.append(coords)
        except Exception as e:
            print("Error processing way:", e)

# === CACHE ===
def load_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
            today = datetime.date.today().isoformat()
            if data.get("date") == today:
                return data
    return {"date": datetime.date.today().isoformat(), "calls": 0, "data": {}}

def save_cache(cache, cache_file):
    with open(cache_file, 'w') as f:
        json.dump(cache, f)

# === API CALL ===
def call_tomtom_api(lat, lon, cache):
    key = f"{round(lat, 5)}_{round(lon, 5)}"
    if key in cache['data']:
        return cache['data'][key]

    if cache['calls'] >= MAX_CALLS_PER_DAY:
        print("API call limit reached")
        return None

    params = {
        'point': f'{lat},{lon}',
        'unit': 'KMPH',
        'key': TOMTOM_API_KEY
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()
        cache['data'][key] = data
        cache['calls'] += 1
        return data
    except Exception as e:
        print(f"API error for {lat},{lon}: {e}")
        return None

# === SAVE TO POSTGIS ===
def save_to_postgis(data, lat, lon):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO traffic (lat, lon, data, geom)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
        """, (lat, lon, json.dumps(data), lon, lat))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Database error:", e)

# === MAIN FUNCTION ===
def main():
    parser = argparse.ArgumentParser(description="Process OSM file and call TomTom API")
    parser.add_argument("--osm", required=True, help="Path to the OSM file")
    parser.add_argument("--cache", required=True, help="Path to the cache file")
    args = parser.parse_args()

    osm_file = args.osm
    cache_file = args.cache

    start_time = time.time()  # ⏱ Start timer

    # Load OSM ways
    handler = WayHandler()
    print("Parsing OSM file...")
    handler.apply_file(osm_file, locations=True)

    total_ways = len(handler.ways)
    print(f"Total ways found: {total_ways}")

    # Load cache
    cache = load_cache(cache_file)

    for i, coords in enumerate(handler.ways, 1):
        line = LineString(coords)
        midpoint = line.interpolate(0.5, normalized=True)
        lat, lon = midpoint.y, midpoint.x

        response = call_tomtom_api(lat, lon, cache)
        if response:
            save_to_postgis(response, lat, lon)

        # Display progress every 100 ways or on last one
        if i % 100 == 0 or i == total_ways:
            percent = round((i / total_ways) * 100, 2)
            print(f"Processing way {i} of {total_ways} ({percent}%)")

    # Save updated cache
    save_cache(cache, cache_file)

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"Total processing time: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

    # Save updated cache
    save_cache(cache, cache_file)

if __name__ == "__main__":
    main()
