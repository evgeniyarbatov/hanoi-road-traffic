import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString

def analyze_running_routes_from_osm(osm_file_path, buffer_distance=50):
    """
    Analyze running opportunities along major roads using local OSM file
    
    Args:
        osm_file_path: Path to local OSM file (.osm, .osm.pbf, .osm.xml)
        buffer_distance: Distance in meters to search for pedestrian ways near roads
    
    Returns:
        GeoDataFrame with roads and their running suitability scores
    """
    
    print("Loading OSM data from local file...")
    
    # Load graphs from local OSM file
    try:
        # Load driving network (main roads)
        G_drive = ox.graph_from_xml(osm_file_path, simplify=True, retain_all=False)
        roads_gdf = ox.graph_to_gdfs(G_drive, nodes=False)
        
        # Load walking network (pedestrian ways)
        G_walk = ox.graph_from_xml(osm_file_path, simplify=True, retain_all=False)
        # Filter for pedestrian-accessible ways
        pedestrian_edges = []
        for u, v, data in G_walk.edges(data=True):
            if is_pedestrian_friendly(data):
                pedestrian_edges.append((u, v, data))
        
        # Create pedestrian GDF
        if pedestrian_edges:
            ped_data = []
            for u, v, data in pedestrian_edges:
                ped_data.append({
                    'u': u,
                    'v': v,
                    'geometry': data.get('geometry', LineString([(G_walk.nodes[u]['x'], G_walk.nodes[u]['y']),
                                                               (G_walk.nodes[v]['x'], G_walk.nodes[v]['y'])])),
                    'highway': data.get('highway', 'unknown'),
                    'surface': data.get('surface', 'unknown'),
                    'lit': data.get('lit', 'unknown')
                })
            peds_gdf = gpd.GeoDataFrame(ped_data, crs='EPSG:4326')
        else:
            print("No pedestrian ways found in the OSM file")
            peds_gdf = gpd.GeoDataFrame(columns=['geometry'], crs='EPSG:4326')
            
    except Exception as e:
        print(f"Error loading OSM file: {e}")
        return None
    
    print(f"Loaded {len(roads_gdf)} road segments and {len(peds_gdf)} pedestrian ways")
    
    # Filter for major roads suitable for monitoring traffic
    major_roads = roads_gdf[
        roads_gdf['highway'].isin(['primary', 'secondary', 'trunk', 'tertiary', 
                                  'primary_link', 'secondary_link', 'trunk_link'])
    ].copy()
    
    print(f"Found {len(major_roads)} major roads")
    
    if len(major_roads) == 0 or len(peds_gdf) == 0:
        print("Insufficient data for analysis")
        return major_roads if len(major_roads) > 0 else None
    
    # Project to local UTM for accurate distance calculations
    # Hanoi is approximately at lat 21.0285, lon 105.8542 (UTM Zone 48N)
    utm_crs = 'EPSG:32648'  # UTM Zone 48N
    major_roads_utm = major_roads.to_crs(utm_crs)
    peds_utm = peds_gdf.to_crs(utm_crs)
    
    # Find pedestrian ways near major roads
    print("Analyzing spatial relationships...")
    nearby_peds = gpd.sjoin_nearest(
        major_roads_utm, 
        peds_utm, 
        distance_col='ped_distance',
        max_distance=buffer_distance,
        lsuffix='_road',
        rsuffix='_ped'
    )
    
    # Calculate running suitability scores
    nearby_peds['running_score'] = nearby_peds.apply(calculate_running_score, axis=1)
    
    # Group by road to get best pedestrian option per road
    print(nearby_peds.columns)
    
    def normalize_osmid(val):
        if isinstance(val, list):
            return val[0]  # or `','.join(map(str, val))` if you want to keep all IDs
        return val

    nearby_peds['osmid'] = nearby_peds['osmid'].apply(normalize_osmid)
    
    best_running_roads = (nearby_peds
                         .sort_values('running_score', ascending=False)
                         .groupby('osmid')
                         .first()
                         .reset_index())
    
    best_running_roads = gpd.GeoDataFrame(
        best_running_roads,
        geometry='geometry',
        crs=utm_crs  # the UTM CRS you used earlier
    )

    # Convert back to WGS84 for output
    result = best_running_roads.to_crs('EPSG:4326')
    
    print(f"Found {len(result)} roads with nearby running opportunities")
    
    return result

def is_pedestrian_friendly(edge_data):
    """Check if an edge is suitable for pedestrians/runners"""
    highway = edge_data.get('highway', '')
    foot = edge_data.get('foot', '')
    access = edge_data.get('access', '')
    
    # Include dedicated pedestrian infrastructure
    if highway in ['footway', 'path', 'pedestrian', 'steps', 'track']:
        return True
    
    # Include roads where pedestrians are explicitly allowed
    if foot in ['yes', 'designated']:
        return True
        
    # Include low-traffic roads that are walkable
    if highway in ['residential', 'service', 'tertiary', 'unclassified']:
        return access != 'private'
    
    # Include cycleways (usually allow pedestrians)
    if highway == 'cycleway':
        return True
        
    return False

def calculate_running_score(row):
    """
    Calculate a running suitability score based on various factors
    Higher score = better for running
    """
    score = 0
    
    # Base score for having nearby pedestrian infrastructure
    score += 10
    
    # Distance penalty (closer is better)
    distance = row.get('ped_distance', 100)
    if distance < 5:
        score += 20  # Sidewalk directly adjacent
    elif distance < 15:
        score += 15  # Very close
    elif distance < 30:
        score += 10  # Close
    elif distance < 50:
        score += 5   # Moderate distance
    
    # Road type bonus (more important roads = more interesting traffic to monitor)
    highway = row.get('highway_road', '')
    if highway in ['trunk', 'primary']:
        score += 15
    elif highway in ['secondary']:
        score += 10
    elif highway in ['tertiary']:
        score += 5
    
    # Pedestrian way quality bonus
    ped_highway = row.get('highway_right', '')
    surface = row.get('surface', '')
    lit = row.get('lit', '')
    
    if ped_highway == 'footway':
        score += 10  # Dedicated sidewalk
    elif ped_highway == 'path':
        score += 8   # Dedicated path
    elif ped_highway in ['residential', 'service']:
        score += 5   # Quiet road
    
    if surface in ['asphalt', 'concrete', 'paved']:
        score += 5
    
    if lit in ['yes']:
        score += 3
    
    # Lane count consideration (more lanes = more traffic to observe)
    lanes = row.get('lanes', '')
    if lanes:
        try:
            lane_count = int(lanes)
            score += min(lane_count * 2, 10)  # Cap at 10 points
        except:
            pass
    
    return score

def export_results(results_gdf, output_file='hanoi_running_roads.geojson'):
    """Export results to GeoJSON for use in other tools"""
    if results_gdf is not None and len(results_gdf) > 0:
        # Select relevant columns
        export_cols = ['osmid', 'highway__road', 'name', 'ped_distance', 
                      'running_score', 'geometry']
        export_cols = [col for col in export_cols if col in results_gdf.columns]
        
        results_gdf[export_cols].to_file(output_file, driver='GeoJSON')
        print(f"Results exported to {output_file}")
        return True
    return False

def plot_results(results_gdf, top_n=20):
    """Plot the top running roads"""
    if results_gdf is None or len(results_gdf) == 0:
        print("No data to plot")
        return
    
    # Get top roads by running score
    top_roads = results_gdf.nlargest(top_n, 'running_score')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Map plot
    top_roads.plot(ax=ax1, color='red', linewidth=2, alpha=0.7)
    ax1.set_title(f'Top {top_n} Roads for Running & Traffic Monitoring')
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    
    # Score distribution
    results_gdf['running_score'].hist(ax=ax2, bins=20, alpha=0.7)
    ax2.set_title('Running Score Distribution')
    ax2.set_xlabel('Running Score')
    ax2.set_ylabel('Number of Roads')
    
    plt.tight_layout()
    plt.show()
    
    return top_roads

# Example usage
if __name__ == "__main__":
    # Usage example - replace with your OSM file path
    osm_file = "osm/hanoi.osm"  # or .osm, .osm.xml
    
    print("Starting running route analysis...")
    results = analyze_running_routes_from_osm(osm_file, buffer_distance=50)
    
    if results is not None:
        print(f"\nTop 10 roads by running score:")
        top_roads = results.nlargest(10, 'running_score')
        for idx, road in top_roads.iterrows():
            road_name = road.get('name_road', 'Unnamed')
            highway_type = road.get('highway_road', 'unknown')
            score = road.get('running_score', 0)
            distance = road.get('ped_distance', 0)
            print(f"- {road_name} ({highway_type}): Score {score:.1f}, "
                  f"Pedestrian way {distance:.1f}m away")
        
        # Export results
        export_results(results, 'data/hanoi_running_roads.geojson')
        
        # Plot results
        plot_results(results)
    
    else:
        print("Analysis failed - check your OSM file path and content")