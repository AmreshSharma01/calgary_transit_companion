import os
import csv
from database.db_setup import db_session
from database.models import Route, Stop, Trip, StopTime, Shape

def load_static_gtfs_data(gtfs_dir):
    load_routes(os.path.join(gtfs_dir, 'routes.txt'))
    
    load_stops(os.path.join(gtfs_dir, 'stops.txt'))
    
    load_trips(os.path.join(gtfs_dir, 'trips.txt'))
    
    load_stop_times(os.path.join(gtfs_dir, 'stop_times.txt'))
    
    load_shapes(os.path.join(gtfs_dir, 'shapes.txt'))
    
    db_session.commit()

def load_routes(routes_file):

    if not os.path.exists(routes_file):
        print(f"Warning: {routes_file} not found")
        return
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            route = Route(
                route_id=row['route_id'],
                route_short_name=row['route_short_name'],
                route_long_name=row['route_long_name'],
                route_desc=row.get('route_desc', ''),
                route_type=int(row['route_type']),
                route_url=row.get('route_url', ''),
                route_color=row.get('route_color', ''),
                route_text_color=row.get('route_text_color', '')
            )
            db_session.add(route)

def load_stops(stops_file):
    if not os.path.exists(stops_file):
        print(f"Warning: {stops_file} not found")
        return
    
    with open(stops_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('stop_id') or not row.get('stop_lat') or not row.get('stop_lon'):
                continue
                
            stop = Stop(
                stop_id=row['stop_id'],
                stop_code=row.get('stop_code', ''),
                stop_name=row['stop_name'],
                stop_desc=row.get('stop_desc', ''),
                stop_lat=row['stop_lat'].strip(),
                stop_lon=row['stop_lon'].strip(),
                zone_id=row.get('zone_id', ''),
                stop_url=row.get('stop_url', ''),
                location_type=int(row['location_type']) if row.get('location_type', '') else None
            )
            db_session.add(stop)

def load_trips(trips_file):
    if not os.path.exists(trips_file):
        print(f"Warning: {trips_file} not found")
        return
    
    with open(trips_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('trip_id') or not row.get('route_id'):
                continue
                
            trip = Trip(
                trip_id=row['trip_id'],
                route_id=row['route_id'],
                service_id=row['service_id'],
                trip_headsign=row.get('trip_headsign', ''),
                direction_id=int(row['direction_id']) if row.get('direction_id', '') else None,
                block_id=row.get('block_id', ''),
                shape_id=row.get('shape_id', '')
            )
            db_session.add(trip)

def load_stop_times(stop_times_file):
    if not os.path.exists(stop_times_file):
        print(f"Warning: {stop_times_file} not found")
        return
    
    with open(stop_times_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('trip_id') or not row.get('stop_id'):
                continue
                
            stop_time = StopTime(
                trip_id=row['trip_id'],
                arrival_time=row['arrival_time'],
                departure_time=row['departure_time'],
                stop_id=row['stop_id'],
                stop_sequence=int(row['stop_sequence']),
                pickup_type=int(row['pickup_type']) if row.get('pickup_type', '') else None,
                drop_off_type=int(row['drop_off_type']) if row.get('drop_off_type', '') else None,
                shape_dist_traveled=float(row['shape_dist_traveled']) if row.get('shape_dist_traveled', '') else None,
                timepoint=int(row['timepoint']) if row.get('timepoint', '') else None
            )
            db_session.add(stop_time)

def load_shapes(shapes_file):
    if not os.path.exists(shapes_file):
        print(f"Warning: {shapes_file} not found")
        return
    
    with open(shapes_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('shape_id') or not row.get('shape_pt_lat') or not row.get('shape_pt_lon'):
                continue
                
            shape = Shape(
                shape_id=row['shape_id'],
                shape_pt_lat=row['shape_pt_lat'],
                shape_pt_lon=row['shape_pt_lon'],
                shape_pt_sequence=int(row['shape_pt_sequence']),
                shape_dist_traveled=float(row['shape_dist_traveled']) if row.get('shape_dist_traveled', '') else None
            )
            db_session.add(shape)