import datetime
import numpy as np
from database.db_setup import db_session
from database.models import Trip, StopTime, Route

"""
Note: In a real-world application, we would:
1. Train ML models with historical transit data
2. Deploy the models in production
3. Use the models to make real predictions

For this demo, we'll simulate these predictions with simplified logic.
These could be replaced with actual ML models in production.
"""

def predict_arrival_times(trip_id, stop_id, scheduled_minutes):
    """
    Predict arrival time adjustments based on historical patterns.
    
    Args:
        trip_id: The trip ID
        stop_id: The stop ID
        scheduled_minutes: The scheduled travel time in minutes
        
    Returns:
        Dictionary with predicted arrival time information
    """
    # Get current hour (for time-of-day effects)
    current_hour = datetime.datetime.now().hour
    
    # Factors that might affect transit time:
    # 1. Time of day (rush hour vs. non-rush hour)
    # 2. Day of week
    # 3. Weather (not implemented here)
    # 4. Special events (not implemented here)
    
    # Simple rush-hour simulation
    is_rush_hour = (current_hour >= 7 and current_hour <= 9) or (current_hour >= 16 and current_hour <= 18)
    
    # Base delay is a percentage of the scheduled time
    base_delay = 0
    
    if is_rush_hour:
        # During rush hour, add 10-20% to the scheduled time
        delay_factor = np.random.uniform(0.1, 0.2)
    else:
        # Outside rush hour, add 0-5% to the scheduled time
        delay_factor = np.random.uniform(0, 0.05)
    
    # Some routes/trips have specific patterns
    # In a real model, these would be learned from historical data
    if trip_id.startswith('1-') or trip_id.startswith('2-'):
        # Routes 1 and 2 tend to be more reliable
        delay_factor *= 0.8
    elif trip_id.startswith('3-') or trip_id.startswith('4-'):
        # Routes 3 and 4 tend to have more delays
        delay_factor *= 1.2
    
    # Calculate the predicted delay in minutes
    delay_minutes = int(scheduled_minutes * delay_factor)
    
    # Get the current time
    now = datetime.datetime.now()
    
    # Calculate scheduled and predicted arrival times
    scheduled_arrival = now + datetime.timedelta(minutes=scheduled_minutes)
    predicted_arrival = scheduled_arrival + datetime.timedelta(minutes=delay_minutes)
    
    return {
        "scheduled_arrival": scheduled_arrival.strftime('%H:%M'),
        "predicted_arrival": predicted_arrival.strftime('%H:%M'),
        "delay_minutes": delay_minutes,
        "confidence": 0.85  # In a real model, this would be the model's confidence score
    }

def predict_crowding(trip_id, route_id, current_hour):
    """
    Predict crowding levels on a specific trip.
    
    Args:
        trip_id: The trip ID
        route_id: The route ID
        current_hour: Current hour of the day
        
    Returns:
        String indicating the predicted crowding level
    """
    # Get day of week (0 = Monday, 6 = Sunday)
    day_of_week = datetime.datetime.now().weekday()
    
    # Base crowding levels
    # 0: Empty, 1: Low, 2: Medium, 3: High, 4: Very High
    base_crowding = 1
    
    # Adjust for rush hour
    if (current_hour >= 7 and current_hour <= 9) or (current_hour >= 16 and current_hour <= 18):
        if day_of_week < 5:  # Weekday
            base_crowding += 2
        else:  # Weekend
            base_crowding += 1
    
    # Adjust for route popularity
    # In a real model, this would be based on historical ridership data
    popular_routes = ['1-20760', '2-20760', '3-20760']  # Example popular routes
    if route_id in popular_routes:
        base_crowding += 1
    
    # Some randomness to simulate variance
    random_adjustment = np.random.choice([-1, 0, 1], p=[0.2, 0.6, 0.2])
    crowding_level = max(0, min(4, base_crowding + random_adjustment))
    
    # Map numeric level to descriptive text
    crowding_descriptions = {
        0: "Empty",
        1: "Low",
        2: "Medium",
        3: "High",
        4: "Very High"
    }
    
    return crowding_descriptions[crowding_level]

def predict_optimal_departure_time(start_stop_id, end_stop_id, desired_arrival_time):
    """
    Predict the optimal departure time to arrive at the destination by the desired time.
    
    Args:
        start_stop_id: Starting stop ID
        end_stop_id: Ending stop ID
        desired_arrival_time: Desired arrival time (datetime object)
        
    Returns:
        Dictionary with optimal departure information
    """
    # In a real application, this would use machine learning to analyze:
    # 1. Historical travel times between these stops
    # 2. Time of day effects
    # 3. Day of week effects
    # 4. Weather impacts
    
    # For this demo, we'll use a simplified approach
    
    # Get all stop times for the end stop
    end_stop_times = StopTime.query.filter_by(stop_id=end_stop_id).all()
    
    best_trip = None
    best_time_diff = float('inf')
    
    # Convert desired arrival time to minutes since midnight
    desired_hour, desired_minute = desired_arrival_time.hour, desired_arrival_time.minute
    desired_minutes = desired_hour * 60 + desired_minute
    
    for end_st in end_stop_times:
        # Get the trip
        trip = Trip.query.filter_by(trip_id=end_st.trip_id).first()
        if not trip:
            continue
            
        # Check if this trip also stops at the start stop
        start_st = StopTime.query.filter_by(
            trip_id=trip.trip_id,
            stop_id=start_stop_id
        ).first()
        
        if not start_st or start_st.stop_sequence >= end_st.stop_sequence:
            continue
            
        # Calculate arrival time in minutes since midnight
        arrival_hour, arrival_minute = map(int, end_st.arrival_time.split(':')[:2])
        arrival_minutes = arrival_hour * 60 + arrival_minute
        
        # Calculate time difference
        time_diff = abs(arrival_minutes - desired_minutes)
        
        # Update best trip if this one is closer to desired arrival time
        if time_diff < best_time_diff:
            best_time_diff = time_diff
            best_trip = {
                'trip_id': trip.trip_id,
                'route_id': trip.route_id,
                'departure_time': start_st.departure_time,
                'arrival_time': end_st.arrival_time,
                'time_diff_minutes': time_diff
            }
    
    if best_trip:
        # Get route information
        route = Route.query.filter_by(route_id=best_trip['route_id']).first()
        if route:
            best_trip['route_name'] = f"{route.route_short_name} - {route.route_long_name}"
        
        # Add buffer time (extra minutes to ensure on-time arrival)
        current_hour = datetime.datetime.now().hour
        is_rush_hour = (current_hour >= 7 and current_hour <= 9) or (current_hour >= 16 and current_hour <= 18)
        
        if is_rush_hour:
            buffer_minutes = 15
        else:
            buffer_minutes = 10
            
        best_trip['recommended_buffer'] = buffer_minutes
        
        # Calculate recommended departure time
        departure_hour, departure_minute = map(int, best_trip['departure_time'].split(':')[:2])
        recommended_departure = datetime.datetime.now().replace(
            hour=departure_hour, 
            minute=departure_minute
        ) - datetime.timedelta(minutes=buffer_minutes)
        
        best_trip['recommended_departure'] = recommended_departure.strftime('%H:%M')
        
    return best_trip or {"error": "No suitable trips found"}