import pandas as pd
import numpy as np
import sys
import argparse
import os
import folium
import plotly.express as px

def load_data(file_path):
    """
    Load road data from CSV file with error handling
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        DataFrame with road data
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        df = pd.read_csv(file_path)
        print(f"Successfully loaded data from: {file_path}")
        print(f"Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns")
        
        # Validate required columns
        required_columns = ['way_id', 'name', 'lat', 'lon', 'distance']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        return df
    
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

def filter_by_distance(df, max_distance=30000):
    """
    Filter ways by maximum distance
    
    Args:
        df: DataFrame with road data
        max_distance: Maximum distance threshold (default: 30000m)
        
    Returns:
        Filtered DataFrame
    """
    print(f"Original dataset size: {len(df)} rows")
    df_filtered = df[df['distance'] <= max_distance].copy()
    print(f"After filtering by distance (<= {max_distance}m): {len(df_filtered)} rows")
    return df_filtered

def calculate_complex_importance_score(df):
    """
    Calculate complex importance score for roads based on multiple factors
    
    Args:
        df: DataFrame with road data
        
    Returns:
        DataFrame with added importance scores
    """
    df = df.copy()
    
    # Initialize scores
    df['length_score'] = 0
    df['intersection_score'] = 0
    df['highway_score'] = 0
    df['connectivity_score'] = 0
    df['traffic_score'] = 0
    df['final_importance_score'] = 0
    
    # 1. Length Score (normalized distance)
    if 'distance' in df.columns:
        df['length_score'] = (df['distance'] - df['distance'].min()) / (df['distance'].max() - df['distance'].min()) * 100
    
    # 2. Intersection Score (combination of total and major intersections)
    if 'total_intersections' in df.columns and 'major_intersections' in df.columns:
        # Normalize intersection counts
        total_int_norm = df['total_intersections'] / df['total_intersections'].max() * 50 if df['total_intersections'].max() > 0 else 0
        major_int_norm = df['major_intersections'] / df['major_intersections'].max() * 50 if df['major_intersections'].max() > 0 else 0
        df['intersection_score'] = total_int_norm + (major_int_norm * 2)  # Weight major intersections more
    elif 'total_intersections' in df.columns:
        df['intersection_score'] = df['total_intersections'] / df['total_intersections'].max() * 100 if df['total_intersections'].max() > 0 else 0
    
    # 3. Highway Type Score (based on road hierarchy)
    highway_weights = {
        'motorway': 100,
        'trunk': 90,
        'primary': 80,
        'secondary': 60,
        'tertiary': 40,
        'unclassified': 30,
        'residential': 20,
        'service': 10,
        'track': 5,
        'path': 2,
        'footway': 1,
        'unknown': 15
    }
    
    df['highway_score'] = df['highway_type'].map(highway_weights).fillna(15)
    
    # 4. Connectivity Score (based on node degree and intersection density)
    if 'avg_node_degree' in df.columns and 'intersection_density' in df.columns:
        # Handle potential string values with ** markers
        df['avg_node_degree_clean'] = pd.to_numeric(df['avg_node_degree'].astype(str).str.replace('**', ''), errors='coerce')
        df['intersection_density_clean'] = pd.to_numeric(df['intersection_density'].astype(str).str.replace('**', ''), errors='coerce')
        
        avg_degree_norm = df['avg_node_degree_clean'] / df['avg_node_degree_clean'].max() * 50 if df['avg_node_degree_clean'].max() > 0 else 0
        int_density_norm = df['intersection_density_clean'] / df['intersection_density_clean'].max() * 50 if df['intersection_density_clean'].max() > 0 else 0
        df['connectivity_score'] = avg_degree_norm + int_density_norm
    elif 'max_node_degree' in df.columns:
        df['connectivity_score'] = df['max_node_degree'] / df['max_node_degree'].max() * 100 if df['max_node_degree'].max() > 0 else 0
    
    # 5. Traffic Score (based on lanes and speed limits)
    traffic_score = 0
    if 'lanes' in df.columns:
        lanes_clean = pd.to_numeric(df['lanes'], errors='coerce').fillna(1)
        traffic_score += (lanes_clean / lanes_clean.max() * 30) if lanes_clean.max() > 0 else 0
    
    if 'maxspeed' in df.columns:
        speed_clean = pd.to_numeric(df['maxspeed'], errors='coerce').fillna(30)  # Default 30 km/h
        traffic_score += (speed_clean / speed_clean.max() * 30) if speed_clean.max() > 0 else 0
    
    if 'running_score' in df.columns:
        running_norm = df['running_score'] / df['running_score'].max() * 40 if df['running_score'].max() > 0 else 0
        traffic_score += running_norm
    
    df['traffic_score'] = traffic_score
    
    # Calculate final weighted importance score
    weights = {
        'length': 0.25,      # 25% - road length importance
        'intersection': 0.25, # 25% - intersection connectivity
        'highway': 0.20,     # 20% - road hierarchy/type
        'connectivity': 0.15, # 15% - network connectivity
        'traffic': 0.15      # 15% - traffic capacity/usage
    }
    
    df['final_importance_score'] = (
        df['length_score'] * weights['length'] +
        df['intersection_score'] * weights['intersection'] +
        df['highway_score'] * weights['highway'] +
        df['connectivity_score'] * weights['connectivity'] +
        df['traffic_score'] * weights['traffic']
    )
    
    return df

def get_top_important_roads(df, top_n=100):
    """
    Get top N most important roads based on complex scoring
    
    Args:
        df: DataFrame with importance scores
        top_n: Number of top roads to return
        
    Returns:
        DataFrame with top roads sorted by importance
    """
    # Sort by final importance score
    top_roads = df.nlargest(top_n, 'final_importance_score').copy()
    
    # Add ranking
    top_roads['importance_rank'] = range(1, len(top_roads) + 1)
    
    return top_roads

def analyze_top_roads(df, filter_unnamed=True, max_distance=30000, top_n=100):
    """
    Analyze individual road segments (ways) without name grouping
    
    Args:
        df: DataFrame with road data
        filter_unnamed: Whether to filter out unnamed roads
        max_distance: Maximum distance threshold
        top_n: Number of top important roads to focus on
        
    Returns:
        DataFrame with top important individual road segments
    """
    
    # Filter by distance first
    df = filter_by_distance(df, max_distance)
    
    # Filter unnamed roads if requested
    if filter_unnamed:
        print(f"Dataset size before unnamed filter: {len(df)} rows")
        df_filtered = df[~df['name'].str.contains('unnamed', case=False, na=False)]
        print(f"After removing unnamed roads: {len(df_filtered)} rows")
    else:
        df_filtered = df.copy()
    
    # Remove rows with invalid coordinates
    df_filtered = df_filtered.dropna(subset=['lat', 'lon'])
    print(f"After removing invalid coordinates: {len(df_filtered)} rows")
    
    # Calculate complex importance scores
    print("Calculating complex importance scores...")
    df_scored = calculate_complex_importance_score(df_filtered)
    
    # Get top important roads (individual ways only)
    top_important_roads = get_top_important_roads(df_scored, top_n)
    print(f"Identified top {len(top_important_roads)} most important road segments")
    
    # Prepare the final dataset with all relevant information
    road_segments = []
    for _, row in top_important_roads.iterrows():
        road_segments.append({
            'way_id': row['way_id'],
            'name': row['name'],
            'lat': row['lat'],
            'lon': row['lon'],
            'highway_type': row.get('highway_type', 'unknown'),
            'distance': row.get('distance', 0),
            'importance_rank': row['importance_rank'],
            'importance_score': row['final_importance_score'],
            'length_score': row['length_score'],
            'intersection_score': row['intersection_score'],
            'highway_score': row['highway_score'],
            'connectivity_score': row['connectivity_score'],
            'traffic_score': row['traffic_score'],
            'total_intersections': row.get('total_intersections', 0),
            'major_intersections': row.get('major_intersections', 0),
            'lanes': row.get('lanes', ''),
            'maxspeed': row.get('maxspeed', '')
        })
    
    # Convert to DataFrame
    road_segments_df = pd.DataFrame(road_segments)
    
    return road_segments_df, top_important_roads

def save_analysis_to_csv(road_segments_df, top_important_roads, prefix='road_analysis'):
    """
    Save road analysis to CSV files
    
    Args:
        road_segments_df: DataFrame with top road segments
        top_important_roads: DataFrame with detailed importance scores
        prefix: Prefix for output files
    """
    
    # Save top road segments
    segments_file = f'data/{prefix}_top_road_segments.csv'
    road_segments_df.to_csv(segments_file, index=False)
    print(f"Saved {len(road_segments_df)} top road segments to {segments_file}")
    
    # Save detailed importance analysis
    importance_file = f'{prefix}_detailed_analysis.csv'
    # top_important_roads.to_csv(importance_file, index=False)
    # print(f"Saved {len(top_important_roads)} roads with detailed importance scores to {importance_file}")
    
    # Save a ranking summary file by different criteria
    summary_file = f'{prefix}_ranking_summary.csv'
    summary_data = []
    
    # Add top roads by different criteria
    criteria = [
        ('final_importance', 'final_importance_score'),
        ('length', 'length_score'),
        ('intersections', 'intersection_score'),
        ('highway_type', 'highway_score'),
        ('connectivity', 'connectivity_score'),
        ('traffic', 'traffic_score')
    ]
    
    for criterion, score_col in criteria:
        top_by_criterion = top_important_roads.nlargest(20, score_col)
        for rank, (_, row) in enumerate(top_by_criterion.iterrows(), 1):
            summary_data.append({
                'ranking_type': f'top_{criterion}',
                'rank': rank,
                'way_id': row['way_id'],
                'name': row['name'],
                'lat': row['lat'],
                'lon': row['lon'],
                'highway_type': row['highway_type'],
                'distance': row['distance'],
                'score_value': row[score_col],
                'final_importance_score': row['final_importance_score'],
                'importance_rank': row['importance_rank']
            })
    
    summary_df = pd.DataFrame(summary_data)
    # summary_df.to_csv(summary_file, index=False)
    # print(f"Saved ranking summary to {summary_file}")

def create_plotly_map(road_segments_df, map_file):
    """
    Create an interactive map using Plotly with importance visualization
    """
    
    # Create the plotly map with importance-based sizing and coloring
    fig = px.scatter_mapbox(
        road_segments_df,
        lat='lat',
        lon='lon',
        color='importance_score',
        size='importance_score',
        hover_name='name',
        hover_data={
            'way_id': True,
            'importance_rank': True,
            'highway_type': True,
            'distance': ':,.0f',
            'total_intersections': True,
            'major_intersections': True,
            'importance_score': ':.1f',
            'lat': ':.6f',
            'lon': ':.6f'
        },
        title="Top Important Road Segments (Distance ≤ 30km)",
        mapbox_style='open-street-map',
        zoom=11,
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        mapbox=dict(
            center=dict(
                lat=road_segments_df['lat'].mean(),
                lon=road_segments_df['lon'].mean()
            )
        ),
        height=700,
        title_x=0.5,
        coloraxis_colorbar=dict(title="Importance Score")
    )
    
    # Save the map
    fig.write_html(map_file)
    print(f"Plotly interactive map saved to {map_file}")
    
    return fig

def main():
    """
    Main function to handle command line arguments and execute road segments analysis
    """
    parser = argparse.ArgumentParser(
        description='Road Segments Analysis - Complex ranking of individual road segments within distance limit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python road_analysis.py data.csv
  python road_analysis.py data.csv --max-distance 25000 --top-n 50
  python road_analysis.py data.csv --include-unnamed --map-type both
  python road_analysis.py data.csv --output-prefix hanoi_road_segments
        """
    )
    
    # Required arguments
    parser.add_argument('file', help='Path to the CSV file containing road data')
    
    # Optional arguments
    parser.add_argument('--output-prefix', type=str, default='road_segments',
                       help='Prefix for output files (default: road_segments)')
    
    parser.add_argument('--max-distance', type=int, default=5000,
                       help='Maximum distance threshold in meters (default: 5000)')
    
    parser.add_argument('--top-n', type=int, default=100,
                       help='Number of top important road segments to analyze (default: 100)')
    
    parser.add_argument('--include-unnamed', action='store_true',
                       help='Include unnamed roads in analysis')
    
    args = parser.parse_args()
    
    # Load data
    df = load_data(args.file)
    
    # Analyze top road segments
    print(f"\nAnalyzing top {args.top_n} most important road segments within {args.max_distance}m...")
    road_segments_df, top_important_roads = analyze_top_roads(
        df, 
        filter_unnamed=not args.include_unnamed,
        max_distance=args.max_distance,
        top_n=args.top_n
    )
    
    # Save to CSV
    print("\nSaving analysis to CSV files...")
    save_analysis_to_csv(road_segments_df, top_important_roads, args.output_prefix)
    
    # Create maps if requested
    print("\nCreating maps...")
    try:
        plotly_file = f'data/{args.output_prefix}_plotly_map.html'
        create_plotly_map(road_segments_df, plotly_file)
    except ImportError:
        print("Plotly not installed. Install with: pip install plotly")
    
    print(f"\nRoad segments analysis complete!")
    print(f"Files saved with prefix '{args.output_prefix}'")
    print(f"Top {len(road_segments_df)} most important road segments analyzed (≤{args.max_distance}m)")

if __name__ == "__main__":
    main()