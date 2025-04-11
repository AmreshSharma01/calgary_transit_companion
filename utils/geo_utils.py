import math
import numpy as np

def haversine_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371
    return c * r

def find_nearest_stops(stop_list, lat, lon, max_distance=0.5):
    nearby_stops = []
    
    for stop in stop_list:
        try:
            stop_lat = float(stop.stop_lat)
            stop_lon = float(stop.stop_lon)
            distance = haversine_distance(lat, lon, stop_lat, stop_lon)
            
            if distance <= max_distance:
                nearby_stops.append({
                    'stop': stop,
                    'distance': distance
                })
        except (ValueError, TypeError, AttributeError):
            continue

    nearby_stops.sort(key=lambda x: x['distance'])
    
    return nearby_stops

def calculate_bearing(lat1, lon1, lat2, lon2):

    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    bearing = math.atan2(y, x)
    
    bearing_degrees = (math.degrees(bearing) + 360) % 360
    
    return bearing_degrees

def simplify_shape(shape_points, tolerance=0.0001):
    if len(shape_points) <= 2:
        return shape_points
    
    sorted_points = sorted(shape_points, key=lambda p: p.shape_pt_sequence)
    
    simplified = [sorted_points[0]]
    
    last_point = sorted_points[0]
    
    for point in sorted_points[1:]:
        dist = np.sqrt(
            (float(point.shape_pt_lat) - float(last_point.shape_pt_lat))**2 + 
            (float(point.shape_pt_lon) - float(last_point.shape_pt_lon))**2
        )
        
        if dist >= tolerance:
            simplified.append(point)
            last_point = point
    
    if simplified[-1] != sorted_points[-1]:
        simplified.append(sorted_points[-1])
    
    return simplified