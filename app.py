from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from google.transit import gtfs_realtime_pb2
import datetime
import json
import os
import traceback
from database.db_setup import init_db, db_session
from database.models import Route, Stop, Trip, StopTime, Shape, User, UserFavoriteRoute
from services.gtfs_service import load_static_gtfs_data
from services.realtime_service import fetch_vehicle_positions, fetch_trip_updates
from services.enhanced_ml_service import predict_arrival_times, predict_crowding, predict_transit_conditions
from services.weather_service import get_current_weather
from services.alert_service import fetch_service_alerts, filter_alerts_by_route, get_active_alerts
import numpy as np
from forms import LoginForm, RegistrationForm, ProfileForm
from flask_wtf.csrf import CSRFProtect

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Access environment variables
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

app = Flask(__name__)

# Configure CSRF protection
csrf = CSRFProtect(app)

# Import and register the API blueprint
from api import api_bp
app.register_blueprint(api_bp)

# Set up login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Configuration
app.secret_key = os.environ.get("SESSION_SECRET", "calgary-transit-secret-key")
VEHICLE_URL = "https://data.calgary.ca/download/am7c-qe3u/application%2Foctet-stream"
TRIP_UPDATE_URL = "https://data.calgary.ca/download/gs4m-mdc2/application%2Foctet-stream"
ALERT_URL = "https://data.calgary.ca/download/jhgn-ynqj/application%2Foctet-stream"
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'gtfs')

def setup(force_reload=False):
    init_db()
    try:
        if force_reload or Route.query.count() == 0:
            print("Loading GTFS data into database...")
            load_static_gtfs_data(GTFS_DIR)
    except Exception as e:
        print(f"Error during setup: {e}")
        # We have the transit.db file with data already, so we can continue

# Execute setup with app context
with app.app_context():
    setup()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route('/')
def index():
    routes = Route.query.all()
    return render_template('index.html', routes=routes)

@app.route('/api/docs')
def api_documentation():
    """Display API documentation page"""
    return render_template('api_docs.html')
    
@app.route('/conditions')
def transit_conditions_dashboard():
    """Display the transit conditions dashboard with weather and alerts"""
    return render_template('conditions.html')

@app.route('/api/vehicles')
def get_vehicles():
    """API endpoint to get real-time vehicle positions"""
    # Get vehicle positions from real-time feed
    vehicles = fetch_vehicle_positions(VEHICLE_URL)
    print(f"Fetched {len(vehicles)} vehicles from real-time feed")
    
    # Enhance vehicle data with route information
    for trip_id, vehicle in vehicles.items():
        try:
            # Get the trip to find its route_id
            trip = Trip.query.filter_by(trip_id=trip_id).first()
            if trip:
                vehicle['route_id'] = trip.route_id
                print(f"Found route_id {trip.route_id} for trip {trip_id}")
            else:
                vehicle['route_id'] = 'unknown'
                print(f"No route found for trip {trip_id}, setting to 'unknown'")
            
            # Rename coordinates to match our frontend
            vehicle['lat'] = vehicle.pop('latitude')
            vehicle['lon'] = vehicle.pop('longitude')
        except Exception as e:
            print(f"Error enhancing vehicle data: {e}")
            vehicle['route_id'] = 'unknown'
    
    # For demo purposes, let's ensure we have at least some vehicles to show
    # This prevents the demo from being empty if no real-time data is available
    if not vehicles:
        print("No real vehicles found, adding demo vehicles")
        # Add a demo vehicle for some common routes
        demo_routes = ['1-20760', '2-20760', '3-20760', '10-20760']
        for i, route_id in enumerate(demo_routes):
            vehicle_id = f"demo-{i+1}"
            # Use Calgary's coordinates with slight offsets
            lat = 51.0447 + (i * 0.005) 
            lon = -114.0719 + (i * 0.005)
            vehicles[vehicle_id] = {
                'route_id': route_id,
                'lat': lat,
                'lon': lon,
                'vehicle_id': vehicle_id,
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'trip_id': f"demo-trip-{i+1}"
            }
    
    return jsonify(vehicles)

@app.route('/api/trips')
def get_trips():
    """API endpoint to get real-time trip updates"""
    trips = fetch_trip_updates(TRIP_UPDATE_URL)
    return jsonify(trips)

@app.route('/api/alerts')
def get_alerts():
    """API endpoint to get service alerts"""
    try:
        # Get alerts from GTFS-RT feed
        alerts = fetch_service_alerts(ALERT_URL)
        
        # Filter by route_id if provided
        route_id = request.args.get('route_id')
        if route_id:
            alerts = filter_alerts_by_route(alerts, route_id)
            
        # Only return active alerts by default
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        if not include_inactive:
            alerts = get_active_alerts(alerts)
            
        return jsonify(alerts)
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return jsonify([])

@app.route('/api/weather')
def get_weather_data():
    """API endpoint to get weather information for a location"""
    try:
        # Get coordinates from request
        lat = float(request.args.get('lat', 51.0447))  # Default to Calgary
        lon = float(request.args.get('lon', -114.0719))
        
        # Check if we have an API key
        if not OPENWEATHER_API_KEY:
            return jsonify({
                "error": "Weather API key not configured",
                "weather_available": False
            })
            
        # Get current weather
        weather_data = get_current_weather(lat, lon, OPENWEATHER_API_KEY)
        
        if not weather_data:
            return jsonify({
                "error": "Could not fetch weather data",
                "weather_available": False
            })
            
        # Format the response
        response = {
            "weather_available": True,
            "location": f"{weather_data['name']}, {weather_data['sys']['country']}",
            "temperature": round(weather_data['main']['temp'], 1),
            "condition": weather_data['weather'][0]['description'],
            "icon": weather_data['weather'][0]['icon'],
            "humidity": weather_data['main']['humidity'],
            "wind_speed": weather_data['wind']['speed'],
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
            
        return jsonify(response)
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return jsonify({
            "error": str(e),
            "weather_available": False
        })

@app.route('/api/transit-conditions')
def get_transit_conditions():
    """API endpoint to get current transit conditions including weather impacts"""
    try:
        # Get coordinates from request
        lat = float(request.args.get('lat', 51.0447))  # Default to Calgary
        lon = float(request.args.get('lon', -114.0719))
        route_id = request.args.get('route_id')
        
        # Get transit conditions prediction
        conditions = predict_transit_conditions(lat, lon, route_id)
        
        # Get weather data for Gemini AI suggestion
        weather_data = None
        if OPENWEATHER_API_KEY:
            try:
                weather_data = get_current_weather(lat, lon, OPENWEATHER_API_KEY)
            except Exception as e:
                print(f"Error fetching weather data for Gemini: {e}")
        
        # Get Gemini AI suggestion if weather data is available
        if weather_data:
            try:
                from services.gemini_service import generate_transit_suggestion
                ai_suggestion = generate_transit_suggestion(weather_data)
                conditions['ai_suggestion'] = ai_suggestion
            except Exception as e:
                print(f"Error generating Gemini AI suggestion: {e}")
                conditions['ai_suggestion'] = "Unable to provide AI transit suggestion at this time."
        else:
            conditions['ai_suggestion'] = "Weather data unavailable for AI suggestion."
        
        # Get active alerts
        try:
            alerts = fetch_service_alerts(ALERT_URL)
            active_alerts = get_active_alerts(alerts)
            
            # Filter by route if provided
            if route_id:
                active_alerts = filter_alerts_by_route(active_alerts, route_id)
                
            conditions['alerts'] = active_alerts[:5]  # Limit to 5 alerts
            conditions['alerts_count'] = len(active_alerts)
        except Exception as e:
            print(f"Error getting alerts for transit conditions: {e}")
            conditions['alerts'] = []
            conditions['alerts_count'] = 0
            
        return jsonify(conditions)
    except Exception as e:
        print(f"Error generating transit conditions: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "overall_status": "Unknown",
            "factors": ["Error retrieving transit conditions"],
            "recommendations": ["Try again later"],
            "ai_suggestion": "Unable to provide AI transit suggestion at this time."
        })

@app.route('/api/transit-forecast')
def get_transit_forecast():
    """API endpoint to get 5-day transit condition forecasts based on weather"""
    try:
        # Get coordinates from request
        lat = float(request.args.get('lat', 51.0447))  # Default to Calgary
        lon = float(request.args.get('lon', -114.0719))
        days = int(request.args.get('days', 5))
        
        # Import the forecast function from enhanced ML service
        from services.enhanced_ml_service import get_forecast_transit_conditions
        
        # Get transit forecast
        forecast = get_forecast_transit_conditions(lat, lon, days)
        
        return jsonify(forecast)
    except Exception as e:
        print(f"Error generating transit forecast: {e}")
        return jsonify({
            "error": str(e),
            "forecast_available": False,
            "generated_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "forecasts": []
        })

@app.route('/api/nearby_stops')
def get_nearby_stops():
    """Find stops near the user's location"""
    lat = float(request.args.get('lat', 0))
    lon = float(request.args.get('lon', 0))
    radius = float(request.args.get('radius', 0.5))  # in kilometers
    
    nearby = find_nearby_stops(lat, lon, radius)
    return jsonify(nearby)

@app.route('/api/route/<route_id>')
def get_route_details(route_id):
    """Simple API that just returns the route shape"""
    try:
        route = Route.query.filter_by(route_id=route_id).first()
        if not route:
            return jsonify({"error": "Route not found"}), 404
        
        # Find a trip with a shape
        trip = Trip.query.filter_by(route_id=route_id).first()
        if not trip or not trip.shape_id:
            # Try to find any trip with a shape
            trip = Trip.query.filter(Trip.shape_id.isnot(None)).first()
        
        shapes_data = {}
        if trip and trip.shape_id:
            # Get shape points - with manual sampling for guaranteed performance
            shape_points = []
            all_points = Shape.query.filter_by(shape_id=trip.shape_id).order_by(Shape.shape_pt_sequence).all()
            
            # Always add first point
            if len(all_points) > 0:
                shape_points.append(all_points[0])
            
            # Sample the middle points
            if len(all_points) > 20:
                step = len(all_points) // 20  # Get about 20 points
                for i in range(step, len(all_points), step):
                    shape_points.append(all_points[i])
            else:
                # If few points, add all of them
                shape_points.extend(all_points[1:])
            
            # Always add last point
            if len(all_points) > 1:
                shape_points.append(all_points[-1])
            
            # Convert points to the expected format
            shapes_data[trip.shape_id] = []
            for point in shape_points:
                try:
                    lat = float(point.shape_pt_lat)
                    lng = float(point.shape_pt_lon)
                    shapes_data[trip.shape_id].append({
                        'lat': lat,
                        'lng': lng,
                        'sequence': point.shape_pt_sequence
                    })
                except (ValueError, TypeError):
                    # Skip invalid points
                    continue
        
        # Return simplified response
        return jsonify({
            'route': {
                'route_id': route.route_id,
                'route_short_name': route.route_short_name,
                'route_long_name': route.route_long_name
            },
            'shapes': shapes_data
        })
        
    except Exception as e:
        print(f"Error in get_route_details: {e}")
        # Even if there's an error, return a valid response structure
        return jsonify({
            'route': {
                'route_id': route_id,
                'route_short_name': 'Route',
                'route_long_name': 'Information Unavailable'
            },
            'shapes': {}
        })

@app.route('/api/route/<route_id>/trips')
def get_route_trips(route_id):
    """Get all trip IDs for a specific route"""
    try:
        # Find all trips for the given route
        trips = Trip.query.filter_by(route_id=route_id).all()
        trip_ids = [trip.trip_id for trip in trips]
        
        return jsonify({
            'route_id': route_id,
            'trips': trip_ids
        })
    except Exception as e:
        print(f"Error in get_route_trips: {e}")
        return jsonify({
            'route_id': route_id,
            'trips': []
        })

@app.route('/search')
def search_routes():
    """Find nearby stations within 500m and show connecting routes"""
    try:
        # Parse coordinates safely
        try:
            start_lat = float(request.args.get('start_lat', 0) or 0)
            start_lon = float(request.args.get('start_lon', 0) or 0)
            end_lat = float(request.args.get('end_lat', 0) or 0)
            end_lon = float(request.args.get('end_lon', 0) or 0)
            
            # Validate coordinates
            if start_lat == 0 and start_lon == 0 and end_lat == 0 and end_lon == 0:
                return render_template('error.html', 
                                    message="Please select origin and destination locations."), 400
                
        except (ValueError, TypeError) as e:
            print(f"Error parsing coordinates: {e}")
            return render_template('error.html', 
                                message="Invalid coordinates. Please enter valid locations or use the map."), 400
            
        # Find nearby stops - with robust error handling
        try:
            # Set search radius
            radius = 0.5  # in kilometers
            
            start_stops = find_nearby_stops(start_lat, start_lon, radius)
            end_stops = find_nearby_stops(end_lat, end_lon, radius)
            
            # Sort by distance and limit to prevent too many stops
            if start_stops:
                start_stops.sort(key=lambda x: x['distance'])
                start_stops = start_stops[:5]  # Limit to top 5 closest
            
            if end_stops:
                end_stops.sort(key=lambda x: x['distance'])
                end_stops = end_stops[:5]  # Limit to top 5 closest
            
            # Log for debugging
            print(f"Found {len(start_stops)} start stops and {len(end_stops)} end stops")
                
            # If no stops found, return early with informative message
            if not start_stops and not end_stops:
                return render_template('error.html', 
                                  message="No transit stops found near your locations. Try different locations."), 404
            
            # Find routes that connect origin and destination areas
            routes_data = find_connecting_routes(start_stops, end_stops)
            
            # Return template with nearby stops and route data
            return render_template('search.html', 
                                  start_stops=start_stops, 
                                  end_stops=end_stops, 
                                  routes_data=routes_data,
                                  start_lat=start_lat,
                                  start_lon=start_lon,
                                  end_lat=end_lat,
                                  end_lon=end_lon)
                              
        except Exception as e:
            print(f"Error finding nearby stops: {e}")
            return render_template('error.html', 
                              message="Error finding transit stops. Please try again later."), 500
                              
    except Exception as e:
        print(f"Unexpected error in search_routes: {e}")
        return render_template('error.html', 
                          message="An unexpected error occurred. Please try again later."), 500


def find_connecting_routes(start_stops, end_stops):
    """Find routes that connect nearby stations in origin and destination"""
    connecting_routes = []
    
    # First, look for real-time routes using current time (now that departure time is gone)
    now = datetime.datetime.now()
    
    # Get real-time direct routes
    direct_routes = find_direct_routes(start_stops, end_stops)
    
    # Get routes with transfers
    transfer_routes = find_routes_with_transfers(start_stops, end_stops)
    
    try:
        # Get stop IDs
        start_stop_ids = [s['stop_id'] for s in start_stops]
        end_stop_ids = [s['stop_id'] for s in end_stops]
        
        # First, find routes serving the start stops
        start_routes = {}
        for stop_id in start_stop_ids:
            # Find stop times for this stop
            stop_times = StopTime.query.filter_by(stop_id=stop_id).limit(20).all()
            for st in stop_times:
                trip = Trip.query.filter_by(trip_id=st.trip_id).first()
                if trip:
                    route = Route.query.filter_by(route_id=trip.route_id).first()
                    if route:
                        if route.route_id not in start_routes:
                            start_routes[route.route_id] = {
                                'route': route,
                                'stops': [stop_id],
                                'shape_id': trip.shape_id,
                                'stop_sequence': st.stop_sequence  # Keep track of stop sequence
                            }
                        else:
                            if stop_id not in start_routes[route.route_id]['stops']:
                                start_routes[route.route_id]['stops'].append(stop_id)
                                
                                # If no shape_id yet, add it
                                if not start_routes[route.route_id]['shape_id'] and trip.shape_id:
                                    start_routes[route.route_id]['shape_id'] = trip.shape_id
        
        # Find routes serving the end stops
        end_routes = {}
        for stop_id in end_stop_ids:
            # Find stop times for this stop
            stop_times = StopTime.query.filter_by(stop_id=stop_id).limit(20).all()
            for st in stop_times:
                trip = Trip.query.filter_by(trip_id=st.trip_id).first()
                if trip:
                    route = Route.query.filter_by(route_id=trip.route_id).first()
                    if route:
                        if route.route_id not in end_routes:
                            end_routes[route.route_id] = {
                                'route': route,
                                'stops': [stop_id],
                                'shape_id': trip.shape_id,
                                'stop_sequence': st.stop_sequence  # Keep track of stop sequence
                            }
                        else:
                            if stop_id not in end_routes[route.route_id]['stops']:
                                end_routes[route.route_id]['stops'].append(stop_id)
                                
                                # If no shape_id yet, add it
                                if not end_routes[route.route_id]['shape_id'] and trip.shape_id:
                                    end_routes[route.route_id]['shape_id'] = trip.shape_id
        
        # Check for direct routes (routes that serve both origin and destination)
        direct_routes = []
        processed_routes = set()  # Track processed routes to avoid duplicates
        
        # Process direct routes
        for route_id in start_routes:
            if route_id in end_routes and route_id not in processed_routes:
                processed_routes.add(route_id)
                
                # Get the shape_id - try start route first, then end route
                shape_id = start_routes[route_id]['shape_id'] or end_routes[route_id]['shape_id']
                
                # If no shape_id, try to find one
                if not shape_id:
                    # Find any trip for this route that has a shape_id
                    trip = Trip.query.filter(Trip.route_id == route_id, Trip.shape_id.isnot(None)).first()
                    if trip:
                        shape_id = trip.shape_id
                
                # Use trip headsign to determine direction
                trips = Trip.query.filter_by(route_id=route_id).limit(5).all()
                headsign = trips[0].trip_headsign if trips else "Unknown"
                
                direct_routes.append({
                    'type': 'direct',
                    'route_id': route_id,
                    'route_name': f"{start_routes[route_id]['route'].route_short_name} - {headsign}",
                    'shape_id': shape_id,
                    'direction': 'outbound'  # Default direction
                })
        
        # Find possible transfers between routes
        transfer_routes = []
        processed_transfers = set()  # Track processed transfer combinations
        
        for start_route_id, start_route_data in start_routes.items():
            for end_route_id, end_route_data in end_routes.items():
                # Skip if same route or if we've already processed this combo
                transfer_key = f"{start_route_id}_{end_route_id}"
                reverse_key = f"{end_route_id}_{start_route_id}"
                
                if (start_route_id == end_route_id or 
                    transfer_key in processed_transfers or 
                    reverse_key in processed_transfers):
                    continue
                
                # Look for common stops as potential transfer points
                # Get all stops for start route
                start_route_all_stops = set()
                trips = Trip.query.filter_by(route_id=start_route_id).limit(5).all()
                for trip in trips:
                    stop_times = StopTime.query.filter_by(trip_id=trip.trip_id).all()
                    for st in stop_times:
                        start_route_all_stops.add(st.stop_id)
                
                # Get all stops for end route
                end_route_all_stops = set()
                trips = Trip.query.filter_by(route_id=end_route_id).limit(5).all()
                for trip in trips:
                    stop_times = StopTime.query.filter_by(trip_id=trip.trip_id).all()
                    for st in stop_times:
                        end_route_all_stops.add(st.stop_id)
                
                # Find common stops (transfer points)
                transfer_stops = start_route_all_stops.intersection(end_route_all_stops)
                
                if transfer_stops:
                    # Only process the first transfer point to reduce duplicates
                    transfer_stop_id = list(transfer_stops)[0]
                    transfer_stop = Stop.query.filter_by(stop_id=transfer_stop_id).first()
                    
                    if transfer_stop:
                        processed_transfers.add(transfer_key)
                        
                        # Get headsigns for better route names
                        start_trips = Trip.query.filter_by(route_id=start_route_id).limit(1).all()
                        end_trips = Trip.query.filter_by(route_id=end_route_id).limit(1).all()
                        
                        start_headsign = start_trips[0].trip_headsign if start_trips else ""
                        end_headsign = end_trips[0].trip_headsign if end_trips else ""
                        
                        # Create a more informative route name
                        start_route_name = f"Route {start_route_data['route'].route_short_name} - {start_headsign}"
                        end_route_name = f"Route {end_route_data['route'].route_short_name} - {end_headsign}"
                        
                        transfer_routes.append({
                            'type': 'transfer',
                            'start_route_id': start_route_id,
                            'start_route_name': start_route_name,
                            'end_route_id': end_route_id,
                            'end_route_name': end_route_name,
                            'transfer_stop_id': transfer_stop_id,
                            'transfer_stop_name': transfer_stop.stop_name,
                            'transfer_stop_lat': float(transfer_stop.stop_lat),
                            'transfer_stop_lon': float(transfer_stop.stop_lon),
                            'start_shape_id': start_route_data['shape_id'],
                            'end_shape_id': end_route_data['shape_id']
                        })
        
        # Prepare the shape data for routes
        all_routes = direct_routes + transfer_routes
        shape_data = {}
        
        for route in all_routes:
            if route['type'] == 'direct' and route['shape_id']:
                shape_points = get_shape_points(route['shape_id'])
                if shape_points:
                    shape_data[route['route_id']] = shape_points
                else:
                    # If no shape points, create a simple straight line between the first stops
                    start_stop = start_routes[route['route_id']]['stops'][0] if start_routes[route['route_id']]['stops'] else None
                    end_stop = end_routes[route['route_id']]['stops'][0] if end_routes[route['route_id']]['stops'] else None
                    
                    if start_stop and end_stop:
                        start_stop_obj = Stop.query.filter_by(stop_id=start_stop).first()
                        end_stop_obj = Stop.query.filter_by(stop_id=end_stop).first()
                        
                        if start_stop_obj and end_stop_obj:
                            # Create a line between the two stops
                            shape_data[route['route_id']] = [
                                {
                                    'lat': float(start_stop_obj.stop_lat),
                                    'lng': float(start_stop_obj.stop_lon),
                                    'sequence': 1
                                },
                                {
                                    'lat': float(end_stop_obj.stop_lat),
                                    'lng': float(end_stop_obj.stop_lon),
                                    'sequence': 2
                                }
                            ]
            elif route['type'] == 'transfer':
                # Add shapes for both legs of the journey
                if route['start_shape_id']:
                    shape_points = get_shape_points(route['start_shape_id'])
                    if shape_points:
                        shape_data[f"{route['start_route_id']}_1"] = shape_points
                
                if route['end_shape_id']:
                    shape_points = get_shape_points(route['end_shape_id'])
                    if shape_points:
                        shape_data[f"{route['end_route_id']}_2"] = shape_points
        
        # Limit number of routes to reduce clutter
        # Prioritize direct routes, then limit transfer routes
        if len(direct_routes) > 3:
            direct_routes = direct_routes[:3]
            
        if len(transfer_routes) > 5:
            transfer_routes = transfer_routes[:5]
            
        # Print some debug info
        print(f"Direct routes: {len(direct_routes)}")
        print(f"Transfer routes: {len(transfer_routes)}")
        print(f"Shape data entries: {len(shape_data)}")
        
        return {
            'direct_routes': direct_routes,
            'transfer_routes': transfer_routes,
            'shape_data': shape_data
        }
    
    except Exception as e:
        print(f"Error finding connecting routes: {e}")
        traceback.print_exc()
        return {
            'direct_routes': [],
            'transfer_routes': [],
            'shape_data': {}
        }


def get_shape_points(shape_id):
    """Get shape points for a specific shape_id with simplified geometry"""
    try:
        # Get shape points
        all_points = Shape.query.filter_by(shape_id=shape_id).order_by(Shape.shape_pt_sequence).all()
        
        # Sample points to reduce data size
        shape_points = []
        
        # Always add first point
        if len(all_points) > 0:
            shape_points.append(all_points[0])
        
        # Sample the middle points
        if len(all_points) > 20:
            step = len(all_points) // 20  # Get about 20 points
            for i in range(step, len(all_points), step):
                shape_points.append(all_points[i])
        else:
            # If few points, add all of them
            shape_points.extend(all_points[1:])
        
        # Always add last point
        if len(all_points) > 1:
            shape_points.append(all_points[-1])
        
        # Convert to list of lat/lng objects
        result = []
        for point in shape_points:
            try:
                lat = float(point.shape_pt_lat)
                lng = float(point.shape_pt_lon)
                result.append({
                    'lat': lat,
                    'lng': lng,
                    'sequence': point.shape_pt_sequence
                })
            except (ValueError, TypeError):
                # Skip invalid points
                continue
        
        return result
    except Exception as e:
        print(f"Error getting shape points: {e}")
        return None

def find_nearby_stops(lat, lon, radius):
    """Find stops near the given coordinates with improved performance"""
    nearby = []
    
    # Use spatial indexing if available (simplifying for now)
    stops = Stop.query.all()
    
    for stop in stops:
        try:
            stop_lat = float(stop.stop_lat)
            stop_lon = float(stop.stop_lon)
            
            # Calculate distance 
            dist = np.sqrt((stop_lat - lat)**2 + (stop_lon - lon)**2) * 111
            if dist <= radius:
                nearby.append({
                    'stop_id': stop.stop_id,
                    'stop_name': stop.stop_name,
                    'stop_lat': stop_lat,
                    'stop_lon': stop_lon,
                    'distance': round(dist, 2)
                })
        except (ValueError, TypeError):
            # Skip stops with invalid coordinates
            continue
    
    return nearby

def find_direct_routes(start_stops, end_stops, departure_time=None):
    """Find direct routes between start and end stops within 500m radius"""
    direct_routes = []
    
    try:
        # Get stop IDs
        start_stop_ids = [s['stop_id'] for s in start_stops]
        end_stop_ids = [s['stop_id'] for s in end_stops]
        
        if not start_stop_ids or not end_stop_ids:
            print("No stops found within radius")
            return []
        
        # Always use current time if not provided
        if departure_time is None:
            departure_time = datetime.datetime.now()
            
        # Convert departure_time to minutes since midnight for comparison
        def to_minutes(dt):
            return dt.hour * 60 + dt.minute
        
        departure_minutes = to_minutes(departure_time)
        
        # Limit the number of stops to check to improve performance
        start_stop_ids = start_stop_ids[:5]  # Limit to 5 closest stops
        end_stop_ids = end_stop_ids[:5]      # Limit to 5 closest stops
        
        # Find trips that connect start and end stops directly
        for start_id in start_stop_ids:
            try:
                # Get stop times at starting stop - limit results
                start_stop_times = StopTime.query.filter(StopTime.stop_id == start_id).limit(100).all()
                
                for start_time in start_stop_times:
                    # Skip past departures (more than 5 min ago)
                    try:
                        st_time = start_time.departure_time.split(':')
                        st_minutes = int(st_time[0]) * 60 + int(st_time[1])
                        
                        # Allow for overnight routes (after midnight)
                        if st_minutes < 240 and departure_minutes > 1200:  # 4am cutoff
                            st_minutes += 1440  # Add 24 hours
                        
                        # Skip if departure time is more than 5 min in the past
                        if st_minutes < departure_minutes - 5:
                            continue
                            
                        # Skip if departure is too far in the future (over 2 hours)
                        if st_minutes > departure_minutes + 120:
                            continue
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing time: {e}")
                        continue
                        
                    try:
                        trip = Trip.query.filter_by(trip_id=start_time.trip_id).first()
                        if not trip:
                            continue
                    except Exception as e:
                        print(f"Error finding trip: {e}")
                        continue
                        
                    try:
                        # Check if this trip also goes through an end stop
                        end_stop_time = StopTime.query.filter(
                            StopTime.trip_id == trip.trip_id,
                            StopTime.stop_id.in_(end_stop_ids),
                            StopTime.stop_sequence > start_time.stop_sequence
                        ).first()
                        
                        if not end_stop_time:
                            continue
                            
                        route = Route.query.filter_by(route_id=trip.route_id).first()
                        if not route:
                            continue
                    except Exception as e:
                        print(f"Error finding end stop time or route: {e}")
                        continue
                        
                    # Calculate travel time
                    try:
                        start_mins = to_minutes_from_str(start_time.departure_time)
                        end_mins = to_minutes_from_str(end_stop_time.arrival_time)
                        
                        # Handle overnight routes
                        if end_mins < start_mins:
                            end_mins += 1440  # Add 24 hours
                            
                        travel_time = end_mins - start_mins
                    except (ValueError, IndexError) as e:
                        print(f"Error calculating travel time: {e}")
                        travel_time = 0
                    
                    try:
                        # Get start and end stop details
                        start_stop = Stop.query.filter_by(stop_id=start_id).first()
                        end_stop = Stop.query.filter_by(stop_id=end_stop_time.stop_id).first()
                        
                        if not (start_stop and end_stop):
                            continue
                            
                        # Apply ML prediction for better arrival time estimates
                        try:
                            predicted_arrival = predict_arrival_times(
                                trip.trip_id, 
                                end_stop_time.stop_id, 
                                travel_time
                            )
                        except Exception as e:
                            print(f"Error predicting arrival time: {e}")
                            predicted_arrival = {"predicted_arrival": end_stop_time.arrival_time}
                        
                        # Predict crowding level
                        try:
                            current_hour = datetime.datetime.now().hour
                            crowding = predict_crowding(trip.trip_id, trip.route_id, current_hour)
                        except Exception as e:
                            print(f"Error predicting crowding: {e}")
                            crowding = "Unknown"
                        
                        # Add to results
                        direct_routes.append({
                            'type': 'direct',
                            'route_id': route.route_id,
                            'route_name': f"{route.route_short_name} - {route.route_long_name}",
                            'trip_id': trip.trip_id,
                            'start_stop': {
                                'id': start_stop.stop_id,
                                'name': start_stop.stop_name,
                                'lat': float(start_stop.stop_lat),
                                'lon': float(start_stop.stop_lon),
                                'time': start_time.departure_time
                            },
                            'end_stop': {
                                'id': end_stop.stop_id,
                                'name': end_stop.stop_name,
                                'lat': float(end_stop.stop_lat),
                                'lon': float(end_stop.stop_lon),
                                'time': end_stop_time.arrival_time,
                                'predicted_time': predicted_arrival
                            },
                            'travel_time': travel_time,
                            'crowding': crowding
                        })
                    except Exception as e:
                        print(f"Error creating route data: {e}")
                        continue
            except Exception as e:
                print(f"Error processing start stop {start_id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in find_direct_routes: {e}")
        
    return direct_routes

def find_routes_with_transfers(start_stops, end_stops, departure_time=None, max_transfers=1):
    """Find routes with one transfer between start and end stops"""
    # Always use current time if not provided
    if departure_time is None:
        departure_time = datetime.datetime.now()
    try:
        if max_transfers <= 0:
            return []
            
        # If we don't have enough stops to search, return early
        if not start_stops or not end_stops:
            print("No stops provided to find_routes_with_transfers")
            return []
            
        # This implementation focuses on finding routes with exactly one transfer
        transfer_routes = []
        
        # Get stop IDs
        start_stop_ids = [s['stop_id'] for s in start_stops]
        end_stop_ids = [s['stop_id'] for s in end_stops]
        
        # Limit the number of stops to search to reduce database load
        start_stop_ids = start_stop_ids[:3]  # Limit to 3 stops max
        end_stop_ids = end_stop_ids[:3]      # Limit to 3 stops max
        
        # Find direct routes first (these are the fastest)
        direct_routes = find_direct_routes(start_stops, end_stops, departure_time)
        if len(direct_routes) >= 5:
            # If we already have at least 5 direct routes, no need for transfers
            return []
            
        # Since transfers are more complex, if there's heavy load we can skip them
        # For this example we'll continue with transfers
        
        try:
            # Find potential transfer stops - limit the queries to reduce database load
            # Get routes serving start stops
            start_trips = Trip.query.join(StopTime).filter(StopTime.stop_id.in_(start_stop_ids)).limit(50).all()
            start_route_ids = {trip.route_id for trip in start_trips}
            
            # Limit the number of routes to check
            route_limit = 5  # Only check 5 routes max
            start_routes_limited = list(start_route_ids)[:route_limit]
            
            # Get routes serving end stops
            end_trips = Trip.query.join(StopTime).filter(StopTime.stop_id.in_(end_stop_ids)).limit(50).all()
            end_route_ids = {trip.route_id for trip in end_trips}
            end_routes_limited = list(end_route_ids)[:route_limit]
            
            # If we don't have any routes to check, return early
            if not start_routes_limited or not end_routes_limited:
                return []
                
            # Get candidate transfer stops - use very small sample for each trip to reduce DB load
            potential_transfer_stops = set()
            for route_id in start_routes_limited:
                # Get a sample trip for this route
                sample_trip = Trip.query.filter_by(route_id=route_id).first()
                if sample_trip:
                    # Get a small sample of stop times for this trip
                    sample_stop_times = StopTime.query.filter_by(trip_id=sample_trip.trip_id).limit(20).all()
                    for st in sample_stop_times:
                        potential_transfer_stops.add(st.stop_id)
            
            # Same for end routes
            end_transfer_stops = set()
            for route_id in end_routes_limited:
                sample_trip = Trip.query.filter_by(route_id=route_id).first()
                if sample_trip:
                    sample_stop_times = StopTime.query.filter_by(trip_id=sample_trip.trip_id).limit(20).all()
                    for st in sample_stop_times:
                        end_transfer_stops.add(st.stop_id)
            
            # Find common stops that could serve as transfer points
            transfer_stops = potential_transfer_stops.intersection(end_transfer_stops)
            
            # Limit to a reasonable number
            transfer_stops_list = list(transfer_stops)[:10]  # Limit to 10 stops max
            
            # If we don't have any transfer stops, return early
            if not transfer_stops_list:
                return []
                
            # For each start stop, find a route to a transfer stop
            # Then for each transfer stop, find a route to an end stop
            for start_id in start_stop_ids:
                try:
                    routes_to_transfer = find_trips_between_stops([start_id], transfer_stops_list, departure_time)
                    
                    for route1 in routes_to_transfer:
                        try:
                            # Find routes from this transfer stop to end stops
                            transfer_stop_id = route1['end_stop']['id']
                            transfer_time = to_minutes_from_str(route1['end_stop']['time']) + 5  # Add 5 minutes for transfer
                            
                            # Convert to datetime for the next search
                            transfer_hour = transfer_time // 60
                            transfer_minute = transfer_time % 60
                            transfer_datetime = departure_time.replace(hour=transfer_hour % 24, minute=transfer_minute)
                            
                            routes_to_end = find_trips_between_stops([transfer_stop_id], end_stop_ids, transfer_datetime)
                            
                            for route2 in routes_to_end:
                                # Calculate the total journey details
                                try:
                                    # Calculate total travel time
                                    total_time = route1['travel_time'] + 5 + route2['travel_time']  # 5 min for transfer
                                    
                                    # Get detailed stops
                                    start_stop = Stop.query.filter_by(stop_id=start_id).first()
                                    transfer_stop = Stop.query.filter_by(stop_id=transfer_stop_id).first()
                                    end_stop = Stop.query.filter_by(stop_id=route2['end_stop']['id']).first()
                                    
                                    if not (start_stop and transfer_stop and end_stop):
                                        continue
                                        
                                    # Create the combined route
                                    transfer_route = {
                                        'type': 'transfer',
                                        'route_id': f"{route1['route_id']}+{route2['route_id']}",
                                        'route_name': f"{route1['route_name']} + {route2['route_name']}",
                                        'start_stop': {
                                            'id': start_stop.stop_id,
                                            'name': start_stop.stop_name,
                                            'lat': float(start_stop.stop_lat),
                                            'lon': float(start_stop.stop_lon),
                                            'time': route1['start_stop']['time']
                                        },
                                        'end_stop': {
                                            'id': end_stop.stop_id,
                                            'name': end_stop.stop_name,
                                            'lat': float(end_stop.stop_lat),
                                            'lon': float(end_stop.stop_lon),
                                            'time': route2['end_stop']['time']
                                        },
                                        'transfer_stop': {
                                            'id': transfer_stop.stop_id,
                                            'name': transfer_stop.stop_name,
                                            'lat': float(transfer_stop.stop_lat),
                                            'lon': float(transfer_stop.stop_lon),
                                            'arrival_time': route1['end_stop']['time'],
                                            'departure_time': route2['start_stop']['time']
                                        },
                                        'legs': [
                                            {
                                                'route_id': route1['route_id'],
                                                'route_name': route1['route_name'],
                                                'trip_id': route1['trip_id'],
                                                'start_stop': {
                                                    'id': start_stop.stop_id,
                                                    'name': start_stop.stop_name,
                                                    'time': route1['start_stop']['time']
                                                },
                                                'end_stop': {
                                                    'id': transfer_stop.stop_id,
                                                    'name': transfer_stop.stop_name,
                                                    'time': route1['end_stop']['time']
                                                },
                                                'travel_time': route1['travel_time']
                                            },
                                            {
                                                'route_id': route2['route_id'],
                                                'route_name': route2['route_name'],
                                                'trip_id': route2['trip_id'],
                                                'start_stop': {
                                                    'id': transfer_stop.stop_id,
                                                    'name': transfer_stop.stop_name,
                                                    'time': route2['start_stop']['time']
                                                },
                                                'end_stop': {
                                                    'id': end_stop.stop_id,
                                                    'name': end_stop.stop_name,
                                                    'time': route2['end_stop']['time']
                                                },
                                                'travel_time': route2['travel_time']
                                            }
                                        ],
                                        'travel_time': total_time,
                                        'transfers': 1
                                    }
                                    
                                    transfer_routes.append(transfer_route)
                                    
                                    # Limit the number of transfers we find to avoid overloading
                                    if len(transfer_routes) >= 10:
                                        return transfer_routes
                                        
                                except Exception as e:
                                    print(f"Error processing transfer route: {e}")
                                    continue
                        except Exception as e:
                            print(f"Error processing route to transfer: {e}")
                            continue
                except Exception as e:
                    print(f"Error finding routes from start stop {start_id}: {e}")
                    continue
        except Exception as e:
            print(f"Error finding transfer stops: {e}")
            return []
            
        return transfer_routes
    except Exception as e:
        print(f"Error in find_routes_with_transfers: {e}")
        return []

def find_trips_between_stops(start_stop_ids, end_stop_ids, departure_time=None):
    """Find trips that connect the given start and end stops"""
    # Always use current time if not provided
    if departure_time is None:
        departure_time = datetime.datetime.now()
    direct_routes = []
    
    try:
        if not start_stop_ids or not end_stop_ids:
            print("No stops provided to find_trips_between_stops")
            return []
            
        # Limit the number of stops to check
        start_stop_ids = start_stop_ids[:3]  # Just take top 3 stops
        end_stop_ids = end_stop_ids[:3]      # Just take top 3 stops
        
        # Convert departure_time to minutes since midnight for comparison
        def to_minutes(dt):
            return dt.hour * 60 + dt.minute
        
        departure_minutes = to_minutes(departure_time)
        
        # Find trips that connect start and end stops directly
        for start_id in start_stop_ids:
            try:
                # Get stop times at starting stop - limit to reduce database load
                start_stop_times = StopTime.query.filter(StopTime.stop_id == start_id).limit(50).all()
                
                for start_time in start_stop_times:
                    # Skip past departures (more than 5 min ago)
                    try:
                        st_time = start_time.departure_time.split(':')
                        st_minutes = int(st_time[0]) * 60 + int(st_time[1])
                        
                        # Allow for overnight routes (after midnight)
                        if st_minutes < 240 and departure_minutes > 1200:  # 4am cutoff
                            st_minutes += 1440  # Add 24 hours
                        
                        # Skip if departure time is more than 5 min in the past
                        if st_minutes < departure_minutes - 5:
                            continue
                            
                        # Skip if departure is too far in the future (over 2 hours)
                        if st_minutes > departure_minutes + 120:  # 2 hours
                            continue
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing time: {e}")
                        continue
                    
                    try:    
                        trip = Trip.query.filter_by(trip_id=start_time.trip_id).first()
                        if not trip:
                            continue
                    except Exception as e:
                        print(f"Error getting trip: {e}")
                        continue
                    
                    try:
                        # Check if this trip also goes through an end stop
                        end_stop_time = StopTime.query.filter(
                            StopTime.trip_id == trip.trip_id,
                            StopTime.stop_id.in_(end_stop_ids),
                            StopTime.stop_sequence > start_time.stop_sequence
                        ).first()
                        
                        if not end_stop_time:
                            continue
                            
                        route = Route.query.filter_by(route_id=trip.route_id).first()
                        if not route:
                            continue
                    except Exception as e:
                        print(f"Error finding end stop or route: {e}")
                        continue
                        
                    # Calculate travel time
                    try:
                        start_mins = to_minutes_from_str(start_time.departure_time)
                        end_mins = to_minutes_from_str(end_stop_time.arrival_time)
                        
                        # Handle overnight routes
                        if end_mins < start_mins:
                            end_mins += 1440  # Add 24 hours
                            
                        travel_time = end_mins - start_mins
                        
                        # Skip unreasonable travel times (over 3 hours)
                        if travel_time > 180:
                            continue
                    except (ValueError, IndexError) as e:
                        print(f"Error calculating travel time: {e}")
                        continue
                    
                    # Add to results
                    direct_routes.append({
                        'route_id': route.route_id,
                        'route_name': f"{route.route_short_name} - {route.route_long_name}",
                        'trip_id': trip.trip_id,
                        'start_stop': {
                            'id': start_id,
                            'time': start_time.departure_time
                        },
                        'end_stop': {
                            'id': end_stop_time.stop_id,
                            'time': end_stop_time.arrival_time
                        },
                        'travel_time': travel_time
                    })
            except Exception as e:
                print(f"Error processing start stop {start_id}: {e}")
                continue
    except Exception as e:
        print(f"Error in find_trips_between_stops: {e}")
    
    return direct_routes

def to_minutes_from_str(time_str):
    """Convert time string (HH:MM:SS) to minutes since midnight"""
    try:
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError):
        return 0

def deduplicate_routes(routes):
    """Remove duplicate routes based on trip_id"""
    unique_routes = {}
    for route in routes:
        # Create a signature for deduplication
        if 'legs' in route:
            # For routes with transfers, use both trip IDs
            signature = '+'.join([leg.get('trip_id', '') for leg in route['legs']])
        else:
            # For direct routes, use the trip ID
            signature = route.get('trip_id', '')
            
        # Only keep the route with the lowest travel time
        if signature not in unique_routes or route['travel_time'] < unique_routes[signature]['travel_time']:
            unique_routes[signature] = route
            
    return list(unique_routes.values())

def sort_routes_by_relevance(routes):
    """Sort routes by a combination of factors: travel time, departure time, transfers"""
    def route_score(route):
        # Lower is better
        travel_time = route.get('travel_time', 0)
        transfers = route.get('transfers', 0)
        
        # Penalize transfers
        transfer_penalty = transfers * 15  # 15 minutes per transfer
        
        # Calculate how soon the route leaves
        now = datetime.datetime.now()
        current_minutes = now.hour * 60 + now.minute
        
        departure_time = route.get('start_stop', {}).get('time', '00:00:00')
        try:
            parts = departure_time.split(':')
            departure_minutes = int(parts[0]) * 60 + int(parts[1])
            
            # Handle overnight routes
            if departure_minutes < 240 and current_minutes > 1200:  # 4am cutoff
                departure_minutes += 1440  # Add 24 hours
                
            wait_time = max(0, departure_minutes - current_minutes)
        except (ValueError, IndexError):
            wait_time = 0
            
        # Balance between travel time (70%), wait time (20%), and transfers (10%)
        score = (travel_time * 0.7) + (wait_time * 0.2) + (transfer_penalty * 0.1)
        return score
        
    # Sort by score (lower is better)
    return sorted(routes, key=route_score)

def get_predictions(trip_id, stop_id):
    """Get predicted arrival time for a specific trip at a specific stop"""
    # Use the ML service to predict arrival times
    # This is a simplified implementation that could be expanded
    
    # Get the stop time first
    stop_time = StopTime.query.filter_by(trip_id=trip_id, stop_id=stop_id).first()
    if not stop_time:
        return {"error": "Stop time not found"}
    
    # Convert time to minutes
    time_parts = stop_time.arrival_time.split(':')
    minutes = int(time_parts[0]) * 60 + int(time_parts[1])
    
    # Get the prediction
    prediction = predict_arrival_times(trip_id, stop_id, minutes)
    
    # Add crowding prediction
    trip = Trip.query.get(trip_id)
    if trip:
        current_hour = datetime.datetime.now().hour
        prediction["crowding"] = predict_crowding(trip_id, trip.route_id, current_hour)
    
    return prediction

def get_trip_stops(trip_id, start_sequence, end_sequence):
    """Get all stops for a trip between the start and end sequences"""
    stops = []
    stop_times = StopTime.query.filter(
        StopTime.trip_id == trip_id,
        StopTime.stop_sequence >= start_sequence,
        StopTime.stop_sequence <= end_sequence
    ).order_by(StopTime.stop_sequence).all()
    
    for stop_time in stop_times:
        stop = Stop.query.filter_by(stop_id=stop_time.stop_id).first()
        if stop:
            stops.append({
                'stop_id': stop.stop_id,
                'stop_name': stop.stop_name,
                'stop_lat': float(stop.stop_lat),
                'stop_lon': float(stop.stop_lon),
                'arrival_time': stop_time.arrival_time,
                'departure_time': stop_time.departure_time,
                'sequence': stop_time.stop_sequence
            })
    
    return stops

@app.route('/route/<route_id>')
def route_details(route_id):
    """Display details for a specific route"""
    route = Route.query.filter_by(route_id=route_id).first()
    if not route:
        return render_template('error.html', message="Route not found"), 404
    trips = Trip.query.filter_by(route_id=route_id).all()
    
    # Get shape data for the route
    shape_data = {}
    if trips and trips[0].shape_id:
        shapes = Shape.query.filter_by(shape_id=trips[0].shape_id).order_by(Shape.shape_pt_sequence).all()
        points = []
        for shape in shapes:
            try:
                points.append({
                    'lat': float(shape.shape_pt_lat),
                    'lng': float(shape.shape_pt_lon)
                })
            except (ValueError, TypeError):
                continue
        shape_data = points
    
    # Get stops for this route
    stops = []
    if trips:
        stop_times = StopTime.query.filter_by(trip_id=trips[0].trip_id).order_by(StopTime.stop_sequence).all()
        for stop_time in stop_times:
            stop = Stop.query.filter_by(stop_id=stop_time.stop_id).first()
            if stop:
                stops.append({
                    'stop_id': stop.stop_id,
                    'stop_name': stop.stop_name,
                    'stop_lat': float(stop.stop_lat),
                    'stop_lon': float(stop.stop_lon),
                    'arrival_time': stop_time.arrival_time,
                    'departure_time': stop_time.departure_time
                })
    
    return render_template('route_details.html', 
                          route=route, 
                          trips=trips[:10],  # Limit to 10 trips
                          shape=shape_data,
                          stops=stops)
# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Login failed. Please check your username and password.', 'danger')
            return render_template('auth/login.html', form=LoginForm(), error='Invalid username or password')
    
    return render_template('auth/login.html', form=LoginForm())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Basic validation
        error = None
        if not username or len(username) < 3 or len(username) > 20:
            error = 'Username must be between 3 and 20 characters.'
        elif not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif not password or len(password) < 8:
            error = 'Password must be at least 8 characters long.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already taken. Please choose a different one.'
        elif User.query.filter_by(email=email).first():
            error = 'Email already registered. Please use a different one or login.'
        
        if error:
            flash(error, 'danger')
            return render_template('auth/register.html', form=RegistrationForm(), error=error)
        
        # If no errors, create user
        hashed_password = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            created_at=datetime.datetime.now()
        )
        
        db_session.add(user)
        db_session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', form=RegistrationForm())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    # Get user's favorite routes
    favorite_routes = UserFavoriteRoute.query.filter_by(user_id=current_user.id).all()
    form = ProfileForm(original_email=current_user.email)
    
    return render_template('auth/profile.html', 
                          current_user=current_user, 
                          favorite_routes=favorite_routes,
                          form=form)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(original_email=current_user.email)
    
    if form.validate_on_submit():
        current_user.email = form.email.data
        
        # Only update password if a new one was provided
        if form.password.data:
            current_user.password_hash = generate_password_hash(form.password.data)
        
        db_session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.email.data = current_user.email
    
    return render_template('auth/edit_profile.html', form=form)

@app.route('/favorites')
@login_required
def favorites():
    favorite_routes = UserFavoriteRoute.query.filter_by(user_id=current_user.id).all()
    return render_template('auth/favorites.html', favorite_routes=favorite_routes)

@app.route('/add_favorite/<route_id>', methods=['POST'])
@login_required
def add_favorite(route_id):
    # Check if route exists
    route = Route.query.get(route_id)
    if not route:
        flash('Route not found.', 'danger')
        return redirect(url_for('index'))
    
    # Check if already in favorites
    existing = UserFavoriteRoute.query.filter_by(user_id=current_user.id, route_id=route_id).first()
    if existing:
        flash('This route is already in your favorites.', 'info')
        return redirect(url_for('route_details', route_id=route_id))
    
    # Add to favorites
    favorite = UserFavoriteRoute(
        user_id=current_user.id,
        route_id=route_id,
        added_at=datetime.datetime.now()
    )
    
    db_session.add(favorite)
    db_session.commit()
    
    flash('Route added to favorites!', 'success')
    return redirect(url_for('route_details', route_id=route_id))

@app.route('/remove_favorite/<int:favorite_id>', methods=['POST'])
@login_required
def remove_favorite(favorite_id):
    favorite = UserFavoriteRoute.query.filter_by(id=favorite_id, user_id=current_user.id).first()
    
    if not favorite:
        flash('Favorite not found.', 'danger')
        return redirect(url_for('favorites'))
    
    db_session.delete(favorite)
    db_session.commit()
    
    flash('Route removed from favorites.', 'success')
    return redirect(url_for('favorites'))
