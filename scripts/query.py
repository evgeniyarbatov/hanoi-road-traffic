import time
import osmium
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
    'user': 'traffic',
    'password': 'DKW9b9agY23e',
    'host': 'localhost',
    'port': 5432
}
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

# === API CALL ===
def call_tomtom_api(lat, lon):
    key = f"{round(lat, 5)}_{round(lon, 5)}"

    params = {
        'point': f'{lat},{lon}',
        'unit': 'KMPH',
        'key': TOMTOM_API_KEY
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        print(f"API error for {lat},{lon}: {e}")
        return None

# === SAVE TO POSTGIS ===
def save_to_postgis(data, lat, lon):
    try:
        coord_list = data.get('flowSegmentData', {}).get('coordinates', {}).get('coordinate', [])

        if not coord_list:
            print("No coordinates found in API response.")
            return

        linestring = LineString([(pt['longitude'], pt['latitude']) for pt in coord_list])

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO traffic (lat, lon, data, queryPoint, segment)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_SetSRID(ST_GeomFromText(%s), 4326));
        """, (
            lat,
            lon,
            json.dumps(data),
            lon,
            lat,
            linestring.wkt
        ))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Database error:", e)
        
def point_exists_in_db(lat, lon):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM traffic
                WHERE ROUND(lat::numeric, 5) = ROUND(%s::numeric, 5)
                  AND ROUND(lon::numeric, 5) = ROUND(%s::numeric, 5)
            );
        """, (lat, lon))

        exists = cur.fetchone()[0]
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print("Database check error:", e)
        return False

# === MAIN FUNCTION ===
def main():
    parser = argparse.ArgumentParser(description="Process OSM file and call TomTom API")
    parser.add_argument("--osm", required=True, help="Path to the OSM file")
    args = parser.parse_args()

    osm_file = args.osm

    start_time = time.time()  # ⏱ Start timer

    # Load OSM ways
    handler = WayHandler()
    print("Parsing OSM file...")
    handler.apply_file(osm_file, locations=True)

    total_ways = len(handler.ways)
    print(f"Total ways found: {total_ways}")

    for i, coords in enumerate(handler.ways, 1):
        line = LineString(coords)
        midpoint = line.interpolate(0.5, normalized=True)
        lat, lon = float(midpoint.y), float(midpoint.x) 

        # Display progress every 100 ways or on last one
        if i % 100 == 0 or i == total_ways:
            percent = round((i / total_ways) * 100, 2)
            print(f"Processing way {i} of {total_ways} ({percent}%)")

        if point_exists_in_db(lat, lon):
            continue  # Skip if already exists

        response = call_tomtom_api(lat, lon)
        if response:
            save_to_postgis(response, lat, lon)

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"Total processing time: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

if __name__ == "__main__":
    main()
