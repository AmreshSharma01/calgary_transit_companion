import requests
import datetime
from google.transit import gtfs_realtime_pb2

def unix_to_time(ts):
    """Convert Unix timestamp to datetime string"""
    try:
        if ts <= 0:
            return "N/A"
        return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, OverflowError, TypeError):
        return "N/A"

def fetch_vehicle_positions(vehicle_url):
    """
    Fetch real-time vehicle positions from GTFS-RT feed
    
    Args:
        vehicle_url: URL for the vehicle positions feed
        
    Returns:
        Dictionary of vehicle data keyed by trip_id
    """
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(vehicle_url)
        feed.ParseFromString(response.content)
        
        vehicle_data = {}
        for entity in feed.entity:
            if entity.HasField("vehicle"):
                v = entity.vehicle
                if v.HasField("trip"):
                    vehicle_data[v.trip.trip_id] = {
                        "trip_id": v.trip.trip_id,
                        "latitude": float(v.position.latitude) if v.HasField("position") else None,
                        "longitude": float(v.position.longitude) if v.HasField("position") else None,
                        "bearing": float(v.position.bearing) if v.HasField("position") and v.position.HasField("bearing") else None,
                        "speed": float(v.position.speed) if v.HasField("position") and v.position.HasField("speed") else None,
                        "vehicle_id": v.vehicle.id if v.HasField("vehicle") else "unknown",
                        "timestamp": unix_to_time(v.timestamp) if v.HasField("timestamp") else "N/A",
                        "occupancy_status": v.occupancy_status if v.HasField("occupancy_status") else None,
                        "congestion_level": v.congestion_level if v.HasField("congestion_level") else None
                    }
        return vehicle_data
    except Exception as e:
        print(f"Error fetching vehicle positions: {e}")
        return {}

def fetch_trip_updates(trip_update_url):
    """
    Fetch real-time trip updates from GTFS-RT feed
    
    Args:
        trip_update_url: URL for the trip updates feed
        
    Returns:
        Dictionary of trip update data keyed by trip_id
    """
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(trip_update_url)
        feed.ParseFromString(response.content)
        
        trip_data = {}
        for entity in feed.entity:
            if entity.HasField("trip_update"):
                t = entity.trip_update
                if t.HasField("trip"):
                    updates = []
                    for stop in t.stop_time_update:
                        update = {
                            "stop_sequence": stop.stop_sequence,
                            "stop_id": stop.stop_id
                        }
                        
                        if stop.HasField("arrival"):
                            update["arrival"] = unix_to_time(stop.arrival.time)
                            update["arrival_delay"] = stop.arrival.delay if stop.arrival.HasField("delay") else None
                        else:
                            update["arrival"] = "N/A"
                            update["arrival_delay"] = None
                        
                        if stop.HasField("departure"):
                            update["departure"] = unix_to_time(stop.departure.time)
                            update["departure_delay"] = stop.departure.delay if stop.departure.HasField("delay") else None
                        else:
                            update["departure"] = "N/A"
                            update["departure_delay"] = None
                        
                        updates.append(update)
                    
                    trip_data[t.trip.trip_id] = {
                        "trip_id": t.trip.trip_id,
                        "route_id": t.trip.route_id if t.trip.HasField("route_id") else "N/A",
                        "schedule_relationship": t.trip.schedule_relationship if t.trip.HasField("schedule_relationship") else "SCHEDULED",
                        "vehicle_id": t.vehicle.id if t.HasField("vehicle") else "unknown",
                        "timestamp": unix_to_time(t.timestamp) if t.HasField("timestamp") else "N/A",
                        "stops": updates
                    }
        return trip_data
    except Exception as e:
        print(f"Error fetching trip updates: {e}")
        return {}