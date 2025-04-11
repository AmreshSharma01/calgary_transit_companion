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
