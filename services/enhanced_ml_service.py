"""
Enhanced ML Service with Weather Integration and Real-time Data Analysis

In a production system:
1. Train ML models with historical transit data, weather impacts, and real-time conditions
2. Deploy the models in a scalable infrastructure
3. Use the models to make real predictions with high accuracy

This version integrates weather data, simulates advanced ML predictions, and provides
comprehensive transit insights to improve the user experience.
"""

import requests
import random
import datetime
import numpy as np
import logging
import math
from services.weather_service import get_current_weather, get_transit_weather_impact, get_weather_forecast, process_5day_forecast

# Set up logging
logger = logging.getLogger(__name__)

# Weather condition impact factors for transit (synthetic for demo)
WEATHER_IMPACTS = {
    'Clear': 0.0,       # No delay
    'Clouds': 0.05,     # 5% delay
    'Rain': 0.15,       # 15% delay
    'Drizzle': 0.1,     # 10% delay
    'Snow': 0.25,       # 25% delay
    'Thunderstorm': 0.3, # 30% delay
    'Fog': 0.2,         # 20% delay
    'Mist': 0.1,        # 10% delay
}

def get_current_weather_for_location(lat, lon):
    """
    Get current weather for a specific location
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Weather data dictionary or None if not available
    """
    # In a real app, you would use your API key from settings or environment
    api_key = None
    
    try:
        # Try to get the OpenWeather API key from environment
        from config import OPENWEATHER_API_KEY
        api_key = OPENWEATHER_API_KEY
    except (ImportError, AttributeError):
        pass
        
    if not api_key:
        logger.warning("No OpenWeather API key available for weather data")
        return None
        
    try:
        weather_data = get_current_weather(lat, lon, api_key)
        return weather_data
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return None

def predict_arrival_times(trip_id, stop_id, scheduled_minutes, weather_data=None):
    """
    Predict arrival time adjustments based on historical patterns and current weather conditions.
    
    Args:
        trip_id: The trip ID
        stop_id: The stop ID
        scheduled_minutes: The scheduled travel time in minutes
        weather_data: Current weather data if available
        
    Returns:
        Dictionary with predicted arrival time information
    """
    # Base prediction uses historical patterns
    # In a real model, this would use trained models on historical data
    
    # Use a normal distribution to simulate prediction variability
    # Standard deviation increases with scheduled time to represent growing uncertainty
    std_dev = max(1, scheduled_minutes * 0.05)  # 5% of scheduled time, minimum 1 minute
    
    # In a real system, we'd use historical data based on:
    # - Time of day (peak vs. off-peak)
    # - Day of week (weekday vs. weekend)
    # - Historical performance for this specific trip
    
    # Base variation - tends to be slightly late (1-3 minute delay on average)
    base_variation = np.random.normal(2, std_dev)
    
    # Weather adjustment
    weather_adjustment = 0
    weather_factor = 0
    
    if weather_data:
        try:
            # Get weather condition and apply appropriate factor
            condition = weather_data['weather'][0]['main']
            
            # Get the impact factor for this weather condition
            weather_factor = WEATHER_IMPACTS.get(condition, 0.0)
            
            # Apply the weather factor to scheduled time
            # More impact on longer trips
            weather_adjustment = scheduled_minutes * weather_factor
            
            logger.info(f"Weather condition {condition} adds {weather_adjustment:.1f}min delay factor")
        except Exception as e:
            logger.error(f"Error calculating weather adjustment: {e}")
    
    # Calculate predicted minutes with all factors
    predicted_minutes = scheduled_minutes + base_variation + weather_adjustment
    
    # Ensure prediction is not negative
    predicted_minutes = max(predicted_minutes, scheduled_minutes * 0.8)
    
    # Calculate prediction confidence (higher for shorter trips and better weather)
    # Scale from 0.5 to 0.95
    base_confidence = 0.95 - (0.01 * min(scheduled_minutes, 45))  # Longer trips = lower confidence
    weather_confidence_penalty = weather_factor * 0.3  # Weather reduces confidence
    confidence = max(0.5, min(0.95, base_confidence - weather_confidence_penalty))
    
    # Generate a prediction explanation
    explanation = []
    if abs(base_variation) > 1:
        if base_variation > 0:
            explanation.append(f"Historical data suggests {round(base_variation)}min delay on this route")
        else:
            explanation.append(f"Historical data suggests arrival {abs(round(base_variation))}min earlier than scheduled")
            
    if weather_adjustment > 1:
        explanation.append(f"Current {condition} conditions may add {round(weather_adjustment)}min delay")
    
    if not explanation:
        explanation.append("On-time arrival expected")
    
    # Format the result
    result = {
        'scheduled_time': scheduled_minutes,
        'predicted_time': round(predicted_minutes, 1),
        'delay': round(predicted_minutes - scheduled_minutes, 1),
        'confidence': round(confidence, 2),
        'explanation': explanation,
        'factors': {
            'historical_pattern': round(base_variation, 1),
            'weather_impact': round(weather_adjustment, 1)
        }
    }
    
    return result

def predict_crowding(trip_id, route_id, current_hour=None, weather_data=None):
    """
    Predict crowding levels on a specific trip considering weather and time factors.
    
    Args:
        trip_id: The trip ID
        route_id: The route ID
        current_hour: Current hour of the day (defaults to current time)
        weather_data: Current weather data if available
        
    Returns:
        Dictionary with crowding prediction information
    """
    if current_hour is None:
        current_hour = datetime.datetime.now().hour
        
    # Peak hours have more crowding (7-9am and 4-6pm)
    is_morning_peak = 7 <= current_hour <= 9
    is_evening_peak = 16 <= current_hour <= 18
    is_peak_hour = is_morning_peak or is_evening_peak
    
    # Base crowding score (0-100)
    if is_peak_hour:
        base_crowding = random.randint(70, 90)  # More crowded during peak
    elif 10 <= current_hour <= 15:  # Midday
        base_crowding = random.randint(40, 65)  # Medium crowding
    else:  # Early morning or late evening
        base_crowding = random.randint(20, 40)  # Less crowded
    
    # Weather factor - people tend to use transit more in bad weather
    weather_factor = 0
    
    if weather_data:
        try:
            # Get weather condition
            condition = weather_data['weather'][0]['main']
            
            # Rainy or snowy conditions increase transit use
            if condition in ['Rain', 'Snow', 'Thunderstorm']:
                weather_factor = random.randint(10, 20)  # 10-20% more crowded
            elif condition in ['Drizzle', 'Fog', 'Mist']:
                weather_factor = random.randint(5, 10)   # 5-10% more crowded
        except Exception as e:
            logger.error(f"Error calculating weather factor for crowding: {e}")
    
    # Calculate final crowding score
    crowding_score = min(100, base_crowding + weather_factor)
    
    # Map to descriptive levels
    if crowding_score < 30:
        level = "Empty"
        description = "Many seats available"
    elif crowding_score < 50:
        level = "Light"
        description = "Several seats available"
    elif crowding_score < 70:
        level = "Moderate"
        description = "Some seats may be available"
    elif crowding_score < 85:
        level = "Crowded"
        description = "Standing room only"
    else:
        level = "Very Crowded"
        description = "Limited standing room"
    
    # Format the result
    result = {
        'level': level,
        'description': description,
        'score': crowding_score,
        'is_peak_hour': is_peak_hour,
        'factors': {
            'time_of_day': 'Peak hour' if is_peak_hour else 'Off-peak',
            'weather_impact': weather_factor
        }
    }
    
    return result

def predict_optimal_departure_time(start_stop_id, end_stop_id, desired_arrival_time, weather_data=None):
    """
    Predict the optimal departure time to arrive at the destination by the desired time,
    considering weather and traffic conditions.
    
    Args:
        start_stop_id: Starting stop ID
        end_stop_id: Ending stop ID
        desired_arrival_time: Desired arrival time (datetime object)
        weather_data: Current weather data if available
        
    Returns:
        Dictionary with optimal departure information
    """
    # In a real system, this would use:
    # - Historical travel time data between these stops
    # - Current real-time conditions
    # - Weather impact models
    
    # For demo, we'll simulate this with reasonable values
    # Base travel time (minutes) - would come from historical data or routing engine
    base_travel_time = random.randint(15, 45)
    
    # Buffer for transfers and waiting (minutes)
    buffer_time = random.randint(5, 15)
    
    # Weather adjustment
    weather_adjustment = 0
    weather_condition = "Unknown"
    
    if weather_data:
        try:
            # Get weather condition
            weather_condition = weather_data['weather'][0]['main']
            
            # Get the impact factor for this weather condition
            weather_factor = WEATHER_IMPACTS.get(weather_condition, 0.0)
            
            # Apply the weather factor to travel time
            weather_adjustment = base_travel_time * weather_factor
            
            logger.info(f"Weather condition {weather_condition} adds {weather_adjustment:.1f}min to optimal departure")
        except Exception as e:
            logger.error(f"Error calculating weather adjustment for optimal departure: {e}")
    
    # Total travel time estimate
    total_minutes = base_travel_time + buffer_time + weather_adjustment
    
    # Calculate the optimal departure time
    optimal_departure = desired_arrival_time - datetime.timedelta(minutes=total_minutes)
    
    # Format the result
    result = {
        'desired_arrival_time': desired_arrival_time.strftime('%H:%M'),
        'optimal_departure_time': optimal_departure.strftime('%H:%M'),
        'travel_time_minutes': round(base_travel_time + weather_adjustment),
        'buffer_minutes': buffer_time,
        'total_minutes': round(total_minutes),
        'factors': {
            'weather_condition': weather_condition,
            'weather_impact_minutes': round(weather_adjustment),
            'confidence': 'medium'  # In a real system, we would calculate this
        }
    }
    
    return result

def predict_transit_conditions(lat, lon, route_id=None):
    """
    Predict overall transit conditions based on weather, time, and route
    
    Args:
        lat: Latitude
        lon: Longitude
        route_id: Optional route ID to get route-specific predictions
        
    Returns:
        Dictionary with transit condition predictions
    """
    # Get current weather for contextual predictions
    weather_data = get_current_weather_for_location(lat, lon)
    
    # Current time factors
    now = datetime.datetime.now()
    current_hour = now.hour
    is_weekend = now.weekday() >= 5
    is_peak_hour = (7 <= current_hour <= 9) or (16 <= current_hour <= 18)
    
    # Prepare response structure
    conditions = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'location': {
            'lat': lat,
            'lon': lon
        }
    }
    
    # Weather-based transit impact (if available)
    if weather_data:
        # Get weather impact assessment
        weather_impact = get_transit_weather_impact(weather_data)
        conditions['weather'] = {
            'condition': weather_data['weather'][0]['main'],
            'description': weather_data['weather'][0]['description'],
            'temperature': round(weather_data['main']['temp']),
            'icon': weather_data['weather'][0]['icon']
        }
        conditions['transit_impact'] = weather_impact
    else:
        # Default impact if no weather data
        conditions['weather'] = {
            'condition': 'Unknown',
            'description': 'Weather data unavailable',
            'temperature': None,
            'icon': '01d'  # default icon
        }
        conditions['transit_impact'] = {
            'impact_level': 'unknown',
            'delay_factor': 1.0,
            'risks': ['Weather data unavailable'],
            'recommendations': ['Check transit agency website for current conditions']
        }
    
    # Time-based predictions
    time_factor = 'peak_hour' if is_peak_hour else 'off_peak'
    day_factor = 'weekend' if is_weekend else 'weekday'
    
    # Overall status prediction
    if conditions['transit_impact']['impact_level'] == 'high':
        overall_status = 'Significant delays likely'
    elif conditions['transit_impact']['impact_level'] == 'medium':
        overall_status = 'Minor delays possible' if is_peak_hour else 'Normal service with some delays'
    else:
        overall_status = 'Busy conditions' if is_peak_hour else 'Good service expected'
    
    # Compile recommendations
    recommendations = conditions['transit_impact']['recommendations'].copy()
    
    if is_peak_hour and not is_weekend:
        recommendations.append('Expect crowded conditions due to peak hour travel')
    
    if route_id:
        recommendations.append(f'Check route {route_id} for specific service alerts')
    
    # Complete the response
    conditions['overall_status'] = overall_status
    conditions['factors'] = [
        f"Time: {time_factor}",
        f"Day: {day_factor}",
        f"Weather: {conditions['weather']['description']}"
    ]
    conditions['recommendations'] = recommendations
    
    return conditions
    
def get_forecast_transit_conditions(lat, lon, days=5):
    """
    Get transit condition forecasts for multiple days based on weather forecasts
    
    Args:
        lat: Latitude
        lon: Longitude
        days: Number of days to forecast (default 5, max 5)
        
    Returns:
        Dictionary with daily transit condition forecasts
    """
    try:
        # Get OpenWeather API key from config
        try:
            from config import OPENWEATHER_API_KEY
            api_key = OPENWEATHER_API_KEY
            if not api_key:
                logger.warning("No OpenWeather API key available for forecast")
                return {
                    'forecast_available': False,
                    'error': 'No weather API key available',
                    'forecasts': []
                }
        except (ImportError, AttributeError):
            logger.warning("No OpenWeather API key available for forecast")
            return {
                'forecast_available': False,
                'error': 'No weather API key available',
                'forecasts': []
            }
            
        # Get weather forecast data
        forecast_data = get_weather_forecast(lat, lon, api_key)
        
        if not forecast_data:
            return {
                'forecast_available': False,
                'error': 'Unable to retrieve weather forecast',
                'forecasts': []
            }
        
        # Process forecast data into daily summaries
        daily_forecasts = process_5day_forecast(forecast_data)
        
        # Limit to requested number of days
        daily_forecasts = daily_forecasts[:min(days, 5)]
        
        # Get real-time alerts if available
        alerts = []
        try:
            from services.alert_service import fetch_service_alerts, get_active_alerts
            from config import GTFS_RT_SERVICE_ALERTS
            if GTFS_RT_SERVICE_ALERTS:
                all_alerts = fetch_service_alerts(GTFS_RT_SERVICE_ALERTS)
                if all_alerts:
                    alerts = get_active_alerts(all_alerts)
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            
        # Add current alerts count to first day
        if daily_forecasts and alerts:
            daily_forecasts[0]['alerts_count'] = len(alerts)
            
        # Enrich forecasts with time-based factors and additional transit insights
        now = datetime.datetime.now()
        
        for forecast in daily_forecasts:
            # Parse date to determine day of week
            forecast_date = datetime.datetime.strptime(forecast['date'], '%Y-%m-%d')
            day_of_week = forecast_date.strftime('%A')
            
            # If it's a weekday, add commute time factors
            if day_of_week in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                forecast['weekday'] = True
                forecast['commute_impact'] = 'medium'
                
                # Add specific commute time recommendations
                am_peak_status = "Morning commute (7-9 AM): "
                pm_peak_status = "Evening commute (4-6 PM): "
                
                # Base on weather impact
                transit_impact = forecast.get('transit_impact', {})
                impact_level = transit_impact.get('impact_level', 'low')
                
                if impact_level == 'high':
                    am_peak_status += "Significant delays likely"
                    pm_peak_status += "Significant delays likely"
                elif impact_level == 'medium':
                    am_peak_status += "Moderate delays possible"
                    pm_peak_status += "Moderate delays possible"
                else:
                    am_peak_status += "Normal conditions expected"
                    pm_peak_status += "Normal conditions expected"
                
                forecast['commute_times'] = {
                    'morning': am_peak_status,
                    'evening': pm_peak_status
                }
            else:
                forecast['weekday'] = False
                forecast['commute_impact'] = 'low'
                
            # Add overall transit status based on weather impact
            transit_impact = forecast.get('transit_impact', {})
            impact_level = transit_impact.get('impact_level', 'low')
            
            if impact_level == 'high':
                forecast['overall_status'] = "Poor transit conditions expected"
            elif impact_level == 'medium':
                forecast['overall_status'] = "Moderate transit conditions expected"
            else:
                forecast['overall_status'] = "Good transit conditions expected"
                
            # Add alerts count for future days (we don't have this data, so default to 0)
            if 'alerts_count' not in forecast:
                forecast['alerts_count'] = 0
                
        # Return complete forecast
        return {
            'forecast_available': True,
            'location': forecast_data.get('city', {}).get('name', 'Unknown Location'),
            'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'forecasts': daily_forecasts
        }
        
    except Exception as e:
        logger.error(f"Error in get_forecast_transit_conditions: {e}")
        return {
            'forecast_available': False,
            'error': str(e),
            'forecasts': []
        }