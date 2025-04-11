from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from database.db_setup import init_db, db_session
from database.models import Route, Stop, Trip, StopTime, Shape, User, UserFavoriteRoute
from services.gtfs_service import load_static_gtfs_data
import os
from services.realtime_service import fetch_vehicle_positions, fetch_trip_updates

app = Flask(__name__)

GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'gtfs')
VEHICLE_URL = "https://data.calgary.ca/download/am7c-qe3u/application%2Foctet-stream"
TRIP_UPDATE_URL = "https://data.calgary.ca/download/gs4m-mdc2/application%2Foctet-stream"

def setup(force_reload=False):
    init_db()
    try:
        if force_reload or Route.query.count() == 0:
            print("Loading GTFS data into database...")
            load_static_gtfs_data(GTFS_DIR)
    except Exception as e:
        print(f"Error during setup: {e}")

with app.app_context():
    setup()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vehicles')
def get_vehicles():
    vehicles = fetch_vehicle_positions(VEHICLE_URL)
    print(f"Fetched {len(vehicles)} vehicles from real-time feed")
    
    for trip_id, vehicle in vehicles.items():
        try:
            trip = Trip.query.filter_by(trip_id=trip_id).first()
            if trip:
                vehicle['route_id'] = trip.route_id
                print(f"Found route_id {trip.route_id} for trip {trip_id}")
            else:
                vehicle['route_id'] = 'unknown'
                print(f"No route found for trip {trip_id}, setting to 'unknown'")
            
            vehicle['lat'] = vehicle.pop('latitude')
            vehicle['lon'] = vehicle.pop('longitude')
        except Exception as e:
            print(f"Error enhancing vehicle data: {e}")
            vehicle['route_id'] = 'unknown'

    return jsonify(vehicles)

@app.route('/api/trips')
def get_trips():
    trips = fetch_trip_updates(TRIP_UPDATE_URL)
    return jsonify(trips)


if __name__ == '__main__':
    app.run(debug=True)