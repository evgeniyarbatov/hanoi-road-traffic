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
def get_collection_interval(current_time, num_coordinates):
    """
    Return collection interval in minutes based on time of day.
    Optimized to stay under 2500 total API calls per 24 hours.
    
    With smart intervals:
    - Peak hours (9pm-12am, 5am-8am): every 15 minutes = 24 collections
    - Off-peak hours: every 75 minutes = 14.4 collections
    - Total: ~38.4 collections * num_coordinates ≈ 2300 API calls (for 60 coords)
    """
    hour = current_time.hour
    
    # High resolution periods: 21-23 (9pm-12am) and 5-7 (5am-8am)
    if (21 <= hour <= 23) or (5 <= hour <= 7):
        return 15   # 4 calls per hour during peak
    else:
        return 75   # 0.8 calls per hour during off-peak

def collect_for_24_hours_variable(coordinates):
    """
    Collect traffic data for 24 hours with variable intervals.
    Optimized to stay under 2500 API calls total.
    Higher frequency during peak hours: 9pm-12am and 5am-8am
    """
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
    
    # Calculate expected API calls
    expected_collections = calculate_expected_collections(len(coordinates))
    
    print(f"Starting 24-hour variable interval collection at {start_time}")
    print(f"Will end at {end_time}")
    print(f"Total coordinates per collection: {len(coordinates)}")
    print(f"Expected total API calls: {expected_collections}")
    print("Collection schedule:")
    print("  • High resolution (every 15 min): 9pm-12am and 5am-8am")
    print("  • Standard resolution (every 75 min): all other times")
    
    collection_count = 0
    total_api_calls = 0
    
    while datetime.now() < end_time:
        collection_start = time.time()
        collection_count += 1
        current_time = datetime.now()
        
        # Get appropriate interval for current time
        interval_minutes = get_collection_interval(current_time, len(coordinates))
        
        print(f"\n=== Collection #{collection_count} at {current_time} ===")
        print(f"Current interval: {interval_minutes} minutes")
        
        # Collect data for all coordinates
        for i, (lat, lon) in enumerate(coordinates, 1):
            percent = round((i / len(coordinates)) * 100, 2)
            print(f"Processing coordinate {i} of {len(coordinates)} ({percent}%): {lat}, {lon}")
            
            response = call_tomtom_api(lat, lon)
            if response:
                save_to_postgis(response, lat, lon, current_time)
            
            total_api_calls += 1
            
            # Safety check for API limit
            if total_api_calls >= 2500:
                print(f"\nAPI limit reached! Stopping at {total_api_calls} calls.")
                return
            
            # Small delay between API calls to be respectful
            time.sleep(0.1)
        
        collection_end = time.time()
        collection_duration = collection_end - collection_start
        print(f"Collection #{collection_count} completed in {time.strftime('%H:%M:%S', time.gmtime(collection_duration))}")
        print(f"Total API calls so far: {total_api_calls}")
        
        # Calculate time until next collection
        next_collection_time = current_time + timedelta(minutes=interval_minutes)
        remaining_time = end_time - datetime.now()
        
        if remaining_time.total_seconds() <= 0:
            break
            
        if next_collection_time < end_time:
            sleep_seconds = (next_collection_time - datetime.now()).total_seconds()
            if sleep_seconds > 0:
                print(f"Waiting {sleep_seconds/60:.1f} minutes until next collection...")
                print(f"Next collection at: {next_collection_time}")
                time.sleep(sleep_seconds)
        else:
            break
    
    print(f"\n24-hour variable interval collection completed!")
    print(f"Total collections: {collection_count}")
    print(f"Total API calls used: {total_api_calls}")
    print(f"API calls remaining: {2500 - total_api_calls}")

def calculate_expected_collections(num_coordinates):
    """Calculate expected number of API calls for the 24-hour period"""
    # Peak hours: 6 hours total (21-23 and 5-7) at 15-minute intervals = 24 collections
    # Off-peak: 18 hours at 75-minute intervals = 14.4 collections
    # Total: ~38.4 collections
    
    peak_hours = 6
    off_peak_hours = 18
    
    peak_collections = (peak_hours * 60) / 15  # 24 collections
    off_peak_collections = (off_peak_hours * 60) / 75  # 14.4 collections
    
    total_collections = peak_collections + off_peak_collections
    total_api_calls = total_collections * num_coordinates
    
    return int(total_api_calls)

def preview_collection_schedule(num_coordinates=60):
    """
    Preview the collection schedule for the next 24 hours
    """
    start_time = datetime.now()
    current_time = start_time
    end_time = start_time + timedelta(hours=24)
    
    collections = []
    collection_count = 0
    
    print("Collection Schedule Preview:")
    print("=" * 50)
    
    while current_time < end_time:
        collection_count += 1
        interval = get_collection_interval(current_time, num_coordinates)
        
        collections.append({
            'number': collection_count,
            'time': current_time,
            'interval': interval
        })
        
        # Show first few and transition points
        if collection_count <= 5 or interval != get_collection_interval(current_time + timedelta(minutes=interval), num_coordinates):
            print(f"Collection #{collection_count:2d}: {current_time.strftime('%H:%M:%S')} (next in {interval:4.1f} min)")
        
        current_time = current_time + timedelta(minutes=interval)
    
    # Summary statistics
    high_res_collections = sum(1 for c in collections if c['interval'] < 30)
    standard_collections = len(collections) - high_res_collections
    total_api_calls = len(collections) * num_coordinates
    
    print("=" * 50)
    print(f"Total collections planned: {len(collections)}")
    print(f"High resolution periods: {high_res_collections} collections (every 15 min)")
    print(f"Standard resolution periods: {standard_collections} collections (every 75 min)")
    print(f"Coordinates per collection: {num_coordinates}")
    print(f"Total API calls: {total_api_calls}")
    print(f"API calls per hour (avg): {total_api_calls/24:.1f}")
    print(f"Remaining API budget: {2500 - total_api_calls}")
    
    if total_api_calls > 2500:
        print("⚠️  WARNING: This schedule exceeds 2500 API calls!")
    else:
        print("✅ This schedule stays within the 2500 API call limit.")

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
    
    args = parser.parse_args()
    
    # Read coordinates from CSV
    coordinates = read_csv_coordinates(args.csv_file)
    
    preview_collection_schedule()
    
    if not coordinates:
        print("No valid coordinates found. Exiting.")
        return
    
    if args.continuous:
        collect_for_24_hours_variable(coordinates)
    else:
        collect_once(coordinates)

if __name__ == "__main__":
    main()