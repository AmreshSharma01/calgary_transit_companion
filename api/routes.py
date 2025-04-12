"""
API Routes module - Contains all API endpoints for the transit application
"""
import datetime
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    # Fallback implementation if werkzeug is not available
    import hashlib
    def generate_password_hash(password):
        return hashlib.sha256(password.encode()).hexdigest()

from . import api_bp
from database.db_setup import db_session
from database.models import Route, Stop, Trip, StopTime, User, UserFavoriteRoute

# Public API endpoints
@api_bp.route('/routes', methods=['GET'])
def get_routes():
    """Get all routes or filter by type"""
    route_type = request.args.get('route_type', type=int)
    
    query = Route.query
    
    # Apply filters if specified
    if route_type is not None:
        query = query.filter_by(route_type=route_type)
        
    # Apply pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Ensure reasonable limits
    per_page = min(per_page, 100)
    
    # Execute query with pagination
    routes = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Format response
    result = []
    for route in routes:
        result.append({
            'route_id': route.route_id,
            'route_short_name': route.route_short_name,
            'route_long_name': route.route_long_name,
            'route_type': route.route_type,
            'route_color': route.route_color,
            'route_text_color': route.route_text_color,
            'route_url': route.route_url
        })
    
    return jsonify(result)

@api_bp.route('/routes/<route_id>', methods=['GET'])
def get_route(route_id):
    """Get a specific route by ID"""
    route = Route.query.get(route_id)
    
    if not route:
        return jsonify({'error': 'Route not found'}), 404
    
    # Get all trips for this route
    trips = Trip.query.filter_by(route_id=route_id).all()
    trip_ids = [trip.trip_id for trip in trips]
    
    # Format response
    result = {
        'route_id': route.route_id,
        'route_short_name': route.route_short_name,
        'route_long_name': route.route_long_name,
        'route_type': route.route_type,
        'route_color': route.route_color,
        'route_text_color': route.route_text_color,
        'route_url': route.route_url,
        'trips_count': len(trips),
        'trip_ids': trip_ids[:10]  # Only include first 10 trips to limit response size
    }
    
    return jsonify(result)

@api_bp.route('/stops', methods=['GET'])
def get_stops():
    """Get all stops or filter by location or zone"""
    zone_id = request.args.get('zone_id')
    
    query = Stop.query
    
    # Apply filters if specified
    if zone_id:
        query = query.filter_by(zone_id=zone_id)
        
    # Apply pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Ensure reasonable limits
    per_page = min(per_page, 100)
    
    # Execute query with pagination
    stops = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Format response
    result = []
    for stop in stops:
        result.append({
            'stop_id': stop.stop_id,
            'stop_code': stop.stop_code,
            'stop_name': stop.stop_name,
            'stop_desc': stop.stop_desc,
            'stop_lat': stop.stop_lat,
            'stop_lon': stop.stop_lon,
            'zone_id': stop.zone_id,
            'stop_url': stop.stop_url,
            'location_type': stop.location_type
        })
    
    return jsonify(result)

@api_bp.route('/stops/nearby', methods=['GET'])
def get_nearby_stops():
    """Get stops near specified coordinates"""
    # Get query parameters
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', 0.5))  # Default 500m (0.5km)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinates or radius. Please provide lat, lon and optional radius'}), 400
    
    # Limit radius to reasonable value (5km max)
    radius = min(radius, 5.0)
    
    # Find nearby stops
    # Note: This is a simplified calculation that works for small distances
    # For more accuracy, use a geospatial database or proper distance calculation
    lat_range = radius / 111.32  # 1 degree latitude is approximately 111.32 km
    lon_range = radius / (111.32 * abs(float(lat) / 90))  # Adjust for longitude based on latitude
    
    stops = Stop.query.filter(
        func.abs(func.cast(Stop.stop_lat, func.float) - lat) <= lat_range,
        func.abs(func.cast(Stop.stop_lon, func.float) - lon) <= lon_range
    ).all()
    
    # Calculate approximate distance and sort by distance
    result = []
    for stop in stops:
        # Simple distance calculation (approximate)
        distance = (
            (float(stop.stop_lat) - lat) ** 2 + 
            (float(stop.stop_lon) - lon) ** 2
        ) ** 0.5 * 111.32
        
        # Only include stops within the radius
        if distance <= radius:
            result.append({
                'stop_id': stop.stop_id,
                'stop_name': stop.stop_name,
                'stop_lat': stop.stop_lat,
                'stop_lon': stop.stop_lon,
                'distance': round(distance, 3)  # Distance in km, rounded to 3 decimal places
            })
    
    # Sort by distance
    result.sort(key=lambda x: x['distance'])
    
    return jsonify(result)

@api_bp.route('/search', methods=['GET'])
def search_routes():
    """
    Search for routes between two points
    
    Query parameters:
    - start_lat: Starting latitude
    - start_lon: Starting longitude
    - end_lat: Ending latitude
    - end_lon: Ending longitude
    """
    try:
        start_lat = float(request.args.get('start_lat'))
        start_lon = float(request.args.get('start_lon'))
        end_lat = float(request.args.get('end_lat'))
        end_lon = float(request.args.get('end_lon'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid coordinates. Please provide start_lat, start_lon, end_lat, end_lon'}), 400
    
    # Find nearby stops for start and end points (using 500m radius)
    radius = 0.5  # 500m in km
    
    # Calculate the degree ranges for latitude and longitude
    start_lat_range = radius / 111.32
    start_lon_range = radius / (111.32 * abs(start_lat / 90))
    end_lat_range = radius / 111.32
    end_lon_range = radius / (111.32 * abs(end_lat / 90))
    
    # Find stops near start point
    start_stops = Stop.query.filter(
        func.abs(func.cast(Stop.stop_lat, func.float) - start_lat) <= start_lat_range,
        func.abs(func.cast(Stop.stop_lon, func.float) - start_lon) <= start_lon_range
    ).all()
    
    # Find stops near end point
    end_stops = Stop.query.filter(
        func.abs(func.cast(Stop.stop_lat, func.float) - end_lat) <= end_lat_range,
        func.abs(func.cast(Stop.stop_lon, func.float) - end_lon) <= end_lon_range
    ).all()
    
    # Find routes that connect these stops
    routes = []
    
    # Get all trips that stop at any start stop
    start_stop_ids = [stop.stop_id for stop in start_stops]
    end_stop_ids = [stop.stop_id for stop in end_stops]
    
    # Find all stop times for start stops
    start_stop_times = StopTime.query.filter(StopTime.stop_id.in_(start_stop_ids)).all()
    start_trip_ids = [st.trip_id for st in start_stop_times]
    
    # Find all stop times for end stops where trip_id is in start_trip_ids
    end_stop_times = StopTime.query.filter(
        StopTime.stop_id.in_(end_stop_ids),
        StopTime.trip_id.in_(start_trip_ids)
    ).all()
    
    # Map trips to their routes
    trip_route_map = {}
    for trip_id in set([st.trip_id for st in end_stop_times]):
        trip = Trip.query.get(trip_id)
        if trip:
            trip_route_map[trip_id] = trip.route_id
    
    # Only include direct routes
    direct_routes = set(trip_route_map.values())
    
    # Get route details
    route_details = []
    for route_id in direct_routes:
        route = Route.query.get(route_id)
        if route:
            route_details.append({
                'route_id': route.route_id,
                'route_short_name': route.route_short_name,
                'route_long_name': route.route_long_name,
                'route_type': route.route_type,
                'route_color': route.route_color
            })
    
    return jsonify({
        'start_stops': [{
            'stop_id': stop.stop_id,
            'stop_name': stop.stop_name,
            'stop_lat': stop.stop_lat,
            'stop_lon': stop.stop_lon
        } for stop in start_stops],
        'end_stops': [{
            'stop_id': stop.stop_id,
            'stop_name': stop.stop_name,
            'stop_lat': stop.stop_lat,
            'stop_lon': stop.stop_lon
        } for stop in end_stops],
        'routes': route_details
    })

# Protected API endpoints (require authentication)
@api_bp.route('/users/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    """Get the current user's profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'created_at': user.created_at.isoformat() if user.created_at else None
    })

@api_bp.route('/users/profile', methods=['PUT'])
@jwt_required()
def update_user_profile():
    """Update the current user's profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    # Update allowed fields
    if data.get('email'):
        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({'error': 'Email already in use'}), 409
        user.email = data['email']
    
    # Update password if provided
    if data.get('password'):
        user.password_hash = generate_password_hash(data['password'])
    
    db_session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    })

@api_bp.route('/users/favorites', methods=['GET'])
@jwt_required()
def get_favorite_routes():
    """Get the current user's favorite routes"""
    user_id = get_jwt_identity()
    
    favorites = UserFavoriteRoute.query.filter_by(user_id=user_id).all()
    
    result = []
    for favorite in favorites:
        route = Route.query.get(favorite.route_id)
        if route:
            result.append({
                'id': favorite.id,
                'route_id': route.route_id,
                'route_short_name': route.route_short_name,
                'route_long_name': route.route_long_name,
                'route_type': route.route_type,
                'route_color': route.route_color,
                'added_at': favorite.added_at.isoformat() if favorite.added_at else None
            })
    
    return jsonify(result)

@api_bp.route('/users/favorites', methods=['POST'])
@jwt_required()
def add_favorite_route():
    """Add a route to user's favorites"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'route_id' not in data:
        return jsonify({'error': 'Missing route_id'}), 400
    
    # Check if route exists
    route = Route.query.get(data['route_id'])
    if not route:
        return jsonify({'error': 'Route not found'}), 404
    
    # Check if already favorited
    existing = UserFavoriteRoute.query.filter_by(
        user_id=user_id, 
        route_id=data['route_id']
    ).first()
    
    if existing:
        return jsonify({'message': 'Route already in favorites'}), 200
    
    # Add to favorites
    favorite = UserFavoriteRoute(
        user_id=user_id,
        route_id=data['route_id'],
        added_at=datetime.datetime.now()
    )
    
    db_session.add(favorite)
    db_session.commit()
    
    return jsonify({
        'message': 'Route added to favorites',
        'favorite': {
            'id': favorite.id,
            'route_id': route.route_id,
            'route_short_name': route.route_short_name,
            'route_long_name': route.route_long_name
        }
    }), 201

@api_bp.route('/users/favorites/<int:favorite_id>', methods=['DELETE'])
@jwt_required()
def remove_favorite_route(favorite_id):
    """Remove a route from user's favorites"""
    user_id = get_jwt_identity()
    
    favorite = UserFavoriteRoute.query.filter_by(id=favorite_id, user_id=user_id).first()
    if not favorite:
        return jsonify({'error': 'Favorite not found or not owned by user'}), 404
    
    db_session.delete(favorite)
    db_session.commit()
    
    return jsonify({'message': 'Route removed from favorites'})