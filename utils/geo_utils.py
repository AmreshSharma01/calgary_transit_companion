import math
import numpy as np

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    
    Returns distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def find_nearest_stops(stop_list, lat, lon, max_distance=0.5):
    """
    Find stops within a certain distance of a point
    
    Args:
        stop_list: List of stop objects with lat/lon attributes
        lat: Latitude of the point
        lon: Longitude of the point
        max_distance: Maximum distance in kilometers
        
    Returns:
        List of stops sorted by distance
    """
    nearby_stops = []
    
    for stop in stop_list:
        try:
            stop_lat = float(stop.stop_lat)
            stop_lon = float(stop.stop_lon)
            
            # Calculate distance
            distance = haversine_distance(lat, lon, stop_lat, stop_lon)
            
            if distance <= max_distance:
                nearby_stops.append({
                    'stop': stop,
                    'distance': distance
                })
        except (ValueError, TypeError, AttributeError):
            # Skip stops with invalid coordinates
            continue
    
    # Sort by distance
    nearby_stops.sort(key=lambda x: x['distance'])
    
    return nearby_stops

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the bearing between two points
    
    Returns bearing in degrees (0-360)
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Calculate bearing
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    bearing = math.atan2(y, x)
    
    # Convert to degrees and normalize
    bearing_degrees = (math.degrees(bearing) + 360) % 360
    
    return bearing_degrees

def simplify_shape(shape_points, tolerance=0.0001):
    """
    Simplify a shape by removing redundant points
    
    Args:
        shape_points: List of shape point objects with lat/lon/sequence attributes
        tolerance: Distance tolerance in degrees
        
    Returns:
        Simplified list of shape points
    """
    if len(shape_points) <= 2:
        return shape_points
    
    # Sort points by sequence
    sorted_points = sorted(shape_points, key=lambda p: p.shape_pt_sequence)
    
    # Start with the first point
    simplified = [sorted_points[0]]
    
    # Add points that are at least tolerance away from the last point
    last_point = sorted_points[0]
    
    for point in sorted_points[1:]:
        # Calculate distance in coordinate space (approximate)
        dist = np.sqrt(
            (float(point.shape_pt_lat) - float(last_point.shape_pt_lat))**2 + 
            (float(point.shape_pt_lon) - float(last_point.shape_pt_lon))**2
        )
        
        if dist >= tolerance:
            simplified.append(point)
            last_point = point
    
    # Always include the last point
    if simplified[-1] != sorted_points[-1]:
        simplified.append(sorted_points[-1])
    
    return simplified