import time
import json
import os
import psycopg2
import requests
import argparse
import pandas as pd
from shapely.geometry import LineString
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

# === API CALL ===
def call_tomtom_api(lat, lon):
    """Call TomTom API for a given lat,lon coordinate"""
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
def save_to_postgis(data, lat, lon, timestamp=None):
    """Save API response data to PostGIS database"""
    try:
        coord_list = data.get('flowSegmentData', {}).get('coordinates', {}).get('coordinate', [])
        if not coord_list:
            print("No coordinates found in API response.")
            return
        
        linestring = LineString([(pt['longitude'], pt['latitude']) for pt in coord_list])
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Include timestamp if provided
        if timestamp:
            cur.execute("""
                INSERT INTO traffic (lat, lon, data, queryPoint, segment, timestamp)
                VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_SetSRID(ST_GeomFromText(%s), 4326), %s);
            """, (
                lat,
                lon,
                json.dumps(data),
                lon,
                lat,
                linestring.wkt,
                timestamp
            ))
        else:
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

# === READ CSV FILE ===
def read_csv_coordinates(csv_file):
    """Read lat,lon coordinates from CSV file"""
    try:
        df = pd.read_csv(csv_file)
        
        # Check if required columns exist (case insensitive)
        lat_col = None
        lon_col = None
        
        for col in df.columns:
            if col.lower() in ['lat', 'latitude']:
                lat_col = col
            elif col.lower() in ['lon', 'lng', 'longitude']:
                lon_col = col
        
        if not lat_col or not lon_col:
            raise Exception(f"Required columns not found. Available columns: {list(df.columns)}")
        
        print(f"Found {len(df)} coordinates in CSV file")
        print(f"Using columns: {lat_col}, {lon_col}")
        
        # Return list of (lat, lon) tuples
        coordinates = [(row[lat_col], row[lon_col]) for _, row in df.iterrows()]
        return coordinates
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []

# === CONTINUOUS COLLECTION FOR 24 HOURS ===
def collect_for_24_hours(coordinates, interval_minutes=60):
    """Collect traffic data for 24 hours at specified intervals"""
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
    
    print(f"Starting 24-hour collection at {start_time}")
    print(f"Will end at {end_time}")
    print(f"Collection interval: {interval_minutes} minutes")
    print(f"Total coordinates per collection: {len(coordinates)}")
    
    collection_count = 0
    
    while datetime.now() < end_time:
        collection_start = time.time()
        collection_count += 1
        current_time = datetime.now()
        
        print(f"\n=== Collection #{collection_count} at {current_time} ===")
        
        for i, (lat, lon) in enumerate(coordinates, 1):
            percent = round((i / len(coordinates)) * 100, 2)
            print(f"Processing coordinate {i} of {len(coordinates)} ({percent}%): {lat}, {lon}")
            
            response = call_tomtom_api(lat, lon)
            if response:
                save_to_postgis(response, lat, lon, current_time)
            
            # Small delay between API calls to be respectful
            time.sleep(0.1)
        
        collection_end = time.time()
        collection_duration = collection_end - collection_start
        print(f"Collection #{collection_count} completed in {time.strftime('%H:%M:%S', time.gmtime(collection_duration))}")
        
        # Calculate time until next collection
        next_collection_time = current_time + timedelta(minutes=interval_minutes)
        remaining_time = end_time - datetime.now()
        
        if remaining_time.total_seconds() <= 0:
            break
            
        if next_collection_time < end_time:
            sleep_seconds = (next_collection_time - datetime.now()).total_seconds()
            if sleep_seconds > 0:
                print(f"Waiting {sleep_seconds/60:.1f} minutes until next collection...")
                time.sleep(sleep_seconds)
        else:
            break
    
    print(f"\n24-hour collection completed! Total collections: {collection_count}")

# === SINGLE COLLECTION ===
def collect_once(coordinates):
    """Collect traffic data once for all coordinates"""
    start_time = time.time()
    total_coords = len(coordinates)
    print(f"Total coordinates found: {total_coords}")
    
    for i, (lat, lon) in enumerate(coordinates, 1):
        percent = round((i / total_coords) * 100, 2)
        print(f"Processing coordinate {i} of {total_coords} ({percent}%): {lat}, {lon}")
        
        response = call_tomtom_api(lat, lon)
        if response:
            save_to_postgis(response, lat, lon)
        
        # Small delay between API calls
        time.sleep(0.1)
    
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"Total processing time: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

# === MAIN FUNCTION ===
def main():
    parser = argparse.ArgumentParser(description='Collect traffic data from TomTom API using CSV coordinates')
    parser.add_argument('csv_file', help='Path to CSV file containing lat,lon coordinates')
    parser.add_argument('--continuous', '-c', action='store_true', 
                       help='Run continuously for 24 hours')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Collection interval in minutes (default: 60)')
    
    args = parser.parse_args()
    
    # Read coordinates from CSV
    coordinates = read_csv_coordinates(args.csv_file)
    
    if not coordinates:
        print("No valid coordinates found. Exiting.")
        return
    
    if args.continuous:
        collect_for_24_hours(coordinates, args.interval)
    else:
        collect_once(coordinates)

if __name__ == "__main__":
    main()