"""
services/route_service.py - Complete implementation for optimized route finding
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from collections import defaultdict

from database.models import Route, Trip, StopTime, Stop
from services.ml_service import predict_arrival_times, predict_crowding

class RouteService:
    """Service to find and optimize transit routes between two locations."""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    def find_routes(self, start_lat, start_lon, end_lat, end_lon, departure_time=None, max_results=5):
        """
        Find optimized routes between origin and destination coordinates.
        
        Args:
            start_lat (float): Origin latitude
            start_lon (float): Origin longitude
            end_lat (float): Destination latitude
            end_lon (float): Destination longitude
            departure_time (datetime): Requested departure time (defaults to current time)
            max_results (int): Maximum number of routes to return (default: 5)
            
        Returns:
            list: List of optimized unique route options (limited to max_results)
        """
        # Set default departure time to current time if not specified
        if not departure_time:
            departure_time = datetime.now()
        
        # Find nearby stops for start and end points
        start_stops = self._find_nearby_stops(start_lat, start_lon)
        end_stops = self._find_nearby_stops(end_lat, end_lon)
        
        if not start_stops or not end_stops:
            return [], [], []
        
        # Find all possible routes - LIMIT to closest stops only for better performance
        all_routes = self._find_all_possible_routes_limited(start_stops[:3], end_stops[:3])
        
        # Filter routes based on departure time
        time_filtered_routes = self._filter_by_time(all_routes, departure_time)
        
        # Deduplicate routes to get unique options
        unique_routes = self._deduplicate_routes(time_filtered_routes)
        
        # Sort routes by relevance (travel time, transfers, etc.)
        sorted_routes = self._sort_routes_by_relevance(unique_routes)
        
        # Return only the top N results
        return sorted_routes[:max_results], start_stops, end_stops
    
    def _find_nearby_stops(self, lat, lon, radius=0.5):
        """Find stops near the given coordinates."""
        nearby = []
        stops = Stop.query.all()
        
        for stop in stops:
            # Approximate distance calculation
            dist = ((float(stop.stop_lat) - lat)**2 + (float(stop.stop_lon) - lon)**2) ** 0.5 * 111
            if dist <= radius:
                nearby.append({
                    'stop_id': stop.stop_id,
                    'stop_name': stop.stop_name,
                    'stop_lat': float(stop.stop_lat),
                    'stop_lon': float(stop.stop_lon),
                    'distance': round(dist, 2)
                })
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])
        return nearby
    
    def _find_all_possible_routes_limited(self, start_stops, end_stops, limit=10):
        """Find a limited set of possible routes between start and end stops."""
        possible_routes = []
        route_count = 0
        
        # Get stop IDs
        start_stop_ids = [s['stop_id'] for s in start_stops]
        end_stop_ids = [s['stop_id'] for s in end_stops]
        
        # Find trips that go through both start and end stops
        for start_id in start_stop_ids:
            # Early exit if we have enough routes
            if route_count >= limit:
                break
                
            # Get only a limited number of stop times per stop for better performance
            start_stop_times = StopTime.query.filter(StopTime.stop_id == start_id).limit(20).all()
            
            for stop_time in start_stop_times:
                # Early exit if we have enough routes
                if route_count >= limit:
                    break
                    
                trip = Trip.query.filter_by(trip_id=stop_time.trip_id).first()
                
                if trip:
                    # Check if this trip also goes through an end stop
                    end_stop_time = StopTime.query.filter(
                        StopTime.trip_id == trip.trip_id,
                        StopTime.stop_id.in_(end_stop_ids),
                        StopTime.stop_sequence > stop_time.stop_sequence
                    ).first()
                    
                    if end_stop_time:
                        route = Route.query.filter_by(route_id=trip.route_id).first()
                        if route:
                            # Get a limited set of stops for this trip
                            trip_stops = StopTime.query.filter_by(
                                trip_id=trip.trip_id
                            ).order_by(StopTime.stop_sequence).all()
                            
                            # Process stop details
                            stop_details = self._process_stop_details(trip_stops)
                            
                            # Calculate travel time
                            travel_time = self._calculate_travel_time(stop_time, end_stop_time)
                            
                            # Add to possible routes
                            possible_routes.append({
                                'route_id': route.route_id,
                                'route_name': f"{route.route_short_name} - {route.route_long_name}",
                                'route_short_name': route.route_short_name,
                                'trip_id': trip.trip_id,
                                'start_stop': {
                                    'stop_id': start_id,
                                    'stop_name': next((s['stop_name'] for s in start_stops if s['stop_id'] == start_id), ''),
                                    'stop_lat': next((s['stop_lat'] for s in start_stops if s['stop_id'] == start_id), 0),
                                    'stop_lon': next((s['stop_lon'] for s in start_stops if s['stop_id'] == start_id), 0),
                                    'departure_time': stop_time.departure_time
                                },
                                'end_stop': {
                                    'stop_id': end_stop_time.stop_id,
                                    'stop_name': next((s['stop_name'] for s in end_stops if s['stop_id'] == end_stop_time.stop_id), ''),
                                    'stop_lat': next((s['stop_lat'] for s in end_stops if s['stop_id'] == end_stop_time.stop_id), 0),
                                    'stop_lon': next((s['stop_lon'] for s in end_stops if s['stop_id'] == end_stop_time.stop_id), 0),
                                    'arrival_time': end_stop_time.arrival_time
                                },
                                'travel_time_minutes': travel_time,
                                'stops': stop_details,
                                'departure_hour': self._get_hour_from_time(stop_time.departure_time),
                                'sequence_signature': self._create_sequence_signature(trip_stops)
                            })
                            route_count += 1
        
        return possible_routes
    
    def _process_stop_details(self, trip_stops):
        """Process stop details for a trip."""
        stop_details = []
        for ts in trip_stops:
            s = Stop.query.filter_by(stop_id=ts.stop_id).first()
            if s:
                stop_details.append({
                    'stop_id': s.stop_id,
                    'stop_name': s.stop_name,
                    'arrival_time': ts.arrival_time,
                    'departure_time': ts.departure_time
                })
        return stop_details
    
    def _calculate_travel_time(self, start_stop_time, end_stop_time):
        """Calculate travel time between stops in minutes."""
        travel_time = 0
        if start_stop_time.departure_time and end_stop_time.arrival_time:
            # Convert times from HH:MM:SS format to minutes since midnight
            def time_to_minutes(time_str):
                h, m, s = map(int, time_str.split(':'))
                return h * 60 + m
            
            start_mins = time_to_minutes(start_stop_time.departure_time)
            end_mins = time_to_minutes(end_stop_time.arrival_time)
            travel_time = end_mins - start_mins
        
        return travel_time
    
    def _get_hour_from_time(self, time_str):
        """Extract hour from time string (HH:MM:SS)."""
        try:
            return int(time_str.split(':')[0])
        except:
            return 0
    
    def _create_sequence_signature(self, trip_stops):
        """Create a signature for route deduplication based on stop sequence."""
        return '-'.join([str(stop.stop_id) for stop in trip_stops])
    
    def _filter_by_time(self, routes, target_time):
        """
        Filter routes based on departure time.
        Returns routes departing within a reasonable window of the target time.
        """
        # Convert target_time to minutes since midnight
        target_hour = target_time.hour
        target_minute = target_time.minute
        target_minutes = target_hour * 60 + target_minute
        
        filtered_routes = []
        for route in routes:
            # Get departure time in minutes since midnight
            departure_time = route['start_stop']['departure_time']
            h, m, s = map(int, departure_time.split(':'))
            departure_minutes = h * 60 + m
            
            # Check if departure time is within window (e.g., 30 minutes before or 90 minutes after)
            time_diff = departure_minutes - target_minutes
            if -30 <= time_diff <= 90:
                route['departure_diff_minutes'] = time_diff
                filtered_routes.append(route)
        
        return filtered_routes
    
    def _deduplicate_routes(self, routes):
        """Deduplicate routes to show only unique options."""
        unique_routes = {}
        
        for route in routes:
            # Create a signature for this route
            # We consider routes unique if they:
            # 1. Have different route IDs, or
            # 2. Have same route ID but different path (sequence signature)
            route_signature = f"{route['route_id']}|{route['sequence_signature']}"
            
            # For same route+signature, keep only one route per hour
            hour_signature = f"{route_signature}|{route['departure_hour']}"
            
            # If this is a new unique signature, or it's better than existing one
            if (hour_signature not in unique_routes or 
                route['travel_time_minutes'] < unique_routes[hour_signature]['travel_time_minutes']):
                
                # Add predictions before storing
                self._add_predictions(route)
                unique_routes[hour_signature] = route
        
        return list(unique_routes.values())
    
    def _add_predictions(self, route):
        """Add ML predictions to the route."""
        # Add arrival time prediction
        predicted_arrival = predict_arrival_times(
            route['trip_id'], 
            route['end_stop']['stop_id'],
            route['travel_time_minutes']
        )
        
        # Add crowding prediction
        crowding_prediction = predict_crowding(
            route['trip_id'],
            route['route_id'],
            route['departure_hour']
        )
        
        route['predictions'] = {
            'estimated_arrival': predicted_arrival,
            'crowding_level': crowding_prediction
        }
    
    def _sort_routes_by_relevance(self, routes):
        """Sort routes by relevance (travel time, departure time diff, etc.)."""
        # First sort by travel time
        return sorted(routes, key=lambda x: (
            # Primary: travel time
            x['travel_time_minutes'],
            # Secondary: departure time difference (prefer times closer to requested)
            abs(x.get('departure_diff_minutes', 0))
        ))