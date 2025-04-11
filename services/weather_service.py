"""
services/weather_service.py - Weather data integration for transit predictions
"""

import requests
import logging
from datetime import datetime, timezone
import math
import json

# Create a logger
logger = logging.getLogger(__name__)

def get_coordinates_from_address(address, api_key):
    """
    Get geographic coordinates from a text address using OpenWeather's Geocoding API
    
    Args:
        address: Text address or city name
        api_key: OpenWeather API key
        
    Returns:
        Tuple of (latitude, longitude, location_name) or (None, None, None) if not found
    """
    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        'q': address,
        'limit': 1,
        'appid': api_key
    }
    
    try:
        response = requests.get(geo_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]['lat'], data[0]['lon'], data[0]['name']
            else:
                logger.warning(f"No coordinates found for address: {address}")
                return None, None, None
        else:
            logger.error(f"Geocoding error: {response.status_code} - {response.text}")
            return None, None, None
    except Exception as e:
        logger.error(f"Exception in get_coordinates_from_address: {e}")
        return None, None, None

def get_current_weather(lat, lon, api_key):
    """
    Get current weather conditions for the given coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        api_key: OpenWeather API key
        
    Returns:
        Dictionary with weather data or None if error
    """
    base_url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'
    }
    
    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Weather data retrieved for {lat}, {lon}: {data['weather'][0]['description']}")
            return data
        else:
            logger.error(f"Failed to fetch current weather: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception in get_current_weather: {e}")
        return None

def get_weather_forecast(lat, lon, api_key):
    """
    Get 5-day weather forecast for the given coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        api_key: OpenWeather API key
        
    Returns:
        Dictionary with forecast data or None if error
    """
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'
    }
    
    try:
        response = requests.get(forecast_url, params=params)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Failed to fetch forecast: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception in get_weather_forecast: {e}")
        return None

def process_5day_forecast(forecast_data):
    """
    Process the 5-day forecast data into a daily summary format
    
    Args:
        forecast_data: Raw forecast data from OpenWeather API
        
    Returns:
        List of daily forecast summaries
    """
    if not forecast_data:
        return []
        
    try:
        daily_forecasts = {}
        
        # Group forecasts by day
        for item in forecast_data['list']:
            # Extract date (without time)
            dt = datetime.fromtimestamp(item['dt'])
            date_key = dt.strftime('%Y-%m-%d')
            
            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {
                    'date': date_key,
                    'day_name': dt.strftime('%A'),
                    'temps': [],
                    'conditions': [],
                    'wind_speeds': [],
                    'precipitations': [],
                    'humidities': [],
                    'timestamps': []
                }
                
            # Add data points
            daily_forecasts[date_key]['temps'].append(item['main']['temp'])
            daily_forecasts[date_key]['conditions'].append(item['weather'][0]['main'])
            daily_forecasts[date_key]['wind_speeds'].append(item['wind']['speed'])
            daily_forecasts[date_key]['humidities'].append(item['main']['humidity'])
            daily_forecasts[date_key]['timestamps'].append(dt.strftime('%H:%M'))
            
            # Add precipitation if available (rain or snow)
            precip = 0
            if 'rain' in item and '3h' in item['rain']:
                precip += item['rain']['3h']
            if 'snow' in item and '3h' in item['snow']:
                precip += item['snow']['3h']
            daily_forecasts[date_key]['precipitations'].append(precip)
        
        # Process each day's data into a summary
        result = []
        for date_key in sorted(daily_forecasts.keys()):
            day_data = daily_forecasts[date_key]
            
            # Calculate averages and most common conditions
            avg_temp = sum(day_data['temps']) / len(day_data['temps'])
            avg_wind = sum(day_data['wind_speeds']) / len(day_data['wind_speeds'])
            avg_humidity = sum(day_data['humidities']) / len(day_data['humidities'])
            total_precip = sum(day_data['precipitations'])
            
            # Find most common weather condition for the day
            from collections import Counter
            conditions_count = Counter(day_data['conditions'])
            primary_condition = conditions_count.most_common(1)[0][0]
            
            # Get min/max temperatures
            min_temp = min(day_data['temps'])
            max_temp = max(day_data['temps'])
            
            # Create summary
            summary = {
                'date': day_data['date'],
                'day_name': day_data['day_name'],
                'avg_temp': round(avg_temp, 1),
                'min_temp': round(min_temp, 1),
                'max_temp': round(max_temp, 1),
                'condition': primary_condition,
                'wind_speed': round(avg_wind, 1),
                'humidity': round(avg_humidity),
                'precipitation': round(total_precip, 1),
                'timestamps': day_data['timestamps']
            }
            
            # Add transit impact assessment
            transit_impact = assess_forecast_transit_impact(summary)
            summary['transit_impact'] = transit_impact
            
            result.append(summary)
            
        return result
    except Exception as e:
        logger.error(f"Error processing 5-day forecast: {e}")
        return []

def assess_forecast_transit_impact(forecast_day):
    """
    Assess the transit impact for a forecast day
    
    Args:
        forecast_day: Processed daily forecast data
        
    Returns:
        Dictionary with transit impact assessment
    """
    # Base impact levels
    impact_level = 'low'
    delay_factor = 1.0
    risks = []
    recommendations = []
    
    # Assess based on conditions
    condition = forecast_day['condition']
    
    # Precipitation-based impacts
    if forecast_day['precipitation'] > 10:
        impact_level = 'high'
        delay_factor = 1.5
        risks.append(f"Heavy precipitation ({forecast_day['precipitation']}mm) may cause significant transit delays")
        recommendations.append("Consider postponing non-essential travel if possible")
    elif forecast_day['precipitation'] > 5:
        impact_level = 'medium'
        delay_factor = 1.3
        risks.append(f"Moderate precipitation ({forecast_day['precipitation']}mm) may slow transit speeds")
        recommendations.append("Allow extra travel time")
    elif forecast_day['precipitation'] > 0:
        delay_factor = max(delay_factor, 1.1)
        risks.append(f"Light precipitation ({forecast_day['precipitation']}mm) possible")
    
    # Temperature-based impacts
    if forecast_day['min_temp'] < -15:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.2)
        risks.append(f"Very cold temperatures (down to {forecast_day['min_temp']}°C)")
        recommendations.append("Dress warmly and prepare for possible transit delays")
    elif forecast_day['max_temp'] > 30:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.1)
        risks.append(f"Very hot temperatures (up to {forecast_day['max_temp']}°C)")
        recommendations.append("Carry water while traveling")
    
    # Wind-based impacts
    if forecast_day['wind_speed'] > 10:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.2)
        risks.append(f"Strong winds ({forecast_day['wind_speed']} m/s)")
        recommendations.append("Check transit alerts before traveling")
    
    # Condition-based impacts
    if condition in ['Thunderstorm', 'Snow']:
        impact_level = max(impact_level, 'high')
        delay_factor = max(delay_factor, 1.4)
        risks.append(f"{condition} conditions forecast")
        recommendations.append("Prepare for significant transit delays")
    elif condition in ['Rain', 'Drizzle']:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.2)
        risks.append(f"{condition} conditions forecast")
        recommendations.append("Allow extra travel time")
    elif condition in ['Fog', 'Mist']:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.15)
        risks.append(f"Reduced visibility due to {condition}")
        recommendations.append("Allow extra travel time")
    
    # If no specific risks identified
    if not risks:
        risks.append("No significant weather impacts expected")
        recommendations.append("Normal transit operations likely")
    
    return {
        'impact_level': impact_level,
        'delay_factor': round(delay_factor, 2),
        'risks': risks,
        'recommendations': recommendations
    }

def get_transit_weather_impact(weather_data):
    """
    Analyze weather conditions to determine impact on transit
    
    Args:
        weather_data: Weather data from OpenWeather API
        
    Returns:
        Dictionary with impact assessments
    """
    if not weather_data:
        return {
            'impact_level': 'unknown',
            'delay_factor': 1.0,
            'risks': ['No weather data available'],
            'recommendations': ['Proceed with normal transit plans']
        }
    
    # Initialize impact factors
    weather_id = weather_data['weather'][0]['id']
    main_condition = weather_data['weather'][0]['main']
    description = weather_data['weather'][0]['description']
    temperature = weather_data['main']['temp']
    wind_speed = weather_data['wind'].get('speed', 0)
    
    # Calculate impact level
    impact_level = 'low'  # Default
    delay_factor = 1.0    # Multiplier for transit times (1.0 = no delay)
    risks = []
    recommendations = []
    
    # Assess based on condition categories
    # Thunderstorm (2xx)
    if 200 <= weather_id < 300:
        impact_level = 'high'
        delay_factor = 1.5
        risks.append('Thunderstorms may cause significant transit delays')
        recommendations.append('Consider postponing non-essential travel')
    
    # Drizzle/Rain (3xx, 5xx)
    elif (300 <= weather_id < 400) or (500 <= weather_id < 600):
        if weather_id in [302, 312, 314, 502, 503, 504, 522]:  # Heavy rain codes
            impact_level = 'medium'
            delay_factor = 1.3
            risks.append('Heavy rain may cause slower transit speeds and minor delays')
            recommendations.append('Allow extra travel time')
        else:
            impact_level = 'low'
            delay_factor = 1.1
            risks.append('Light rain may cause slightly slower transit speeds')
            recommendations.append('Normal transit operations expected with minor delays')
    
    # Snow (6xx)
    elif 600 <= weather_id < 700:
        if weather_id in [602, 622]:  # Heavy snow codes
            impact_level = 'high'
            delay_factor = 1.7
            risks.append('Heavy snow may cause significant transit delays or cancellations')
            recommendations.append('Check transit alerts before traveling')
        else:
            impact_level = 'medium'
            delay_factor = 1.4
            risks.append('Snow may cause transit delays')
            recommendations.append('Allow significant extra travel time')
    
    # Atmosphere conditions (fog, mist, etc.) (7xx)
    elif 700 <= weather_id < 800:
        impact_level = 'medium'
        delay_factor = 1.2
        risks.append('Reduced visibility may cause transit delays')
        recommendations.append('Allow extra travel time')
    
    # Clear/Clouds (800, 8xx)
    elif weather_id >= 800:
        impact_level = 'low'
        delay_factor = 1.0
        risks.append('No significant weather impacts expected')
        recommendations.append('Normal transit operations expected')
    
    # Temperature considerations
    if temperature < -15:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.2)
        risks.append('Extreme cold may cause equipment issues')
        recommendations.append('Dress warmly and prepare for possible delays')
    elif temperature > 30:
        impact_level = max(impact_level, 'medium') 
        delay_factor = max(delay_factor, 1.1)
        risks.append('Extreme heat may cause equipment issues')
        recommendations.append('Carry water while traveling')
    
    # Wind considerations
    if wind_speed > 15:
        impact_level = max(impact_level, 'medium')
        delay_factor = max(delay_factor, 1.2)
        risks.append('High winds may cause transit delays')
        recommendations.append('Check transit alerts before traveling')
    
    return {
        'impact_level': impact_level,
        'delay_factor': round(delay_factor, 2),
        'risks': risks,
        'recommendations': recommendations,
        'condition': main_condition,
        'description': description
    }

def format_weather_for_display(weather_data):
    """
    Format weather data for user-friendly display
    
    Args:
        weather_data: Weather data from OpenWeather API
        
    Returns:
        Dictionary with formatted weather information
    """
    if not weather_data:
        return {
            'available': False,
            'error': 'Weather data unavailable'
        }
    
    try:
        # Format basic weather info
        formatted = {
            'available': True,
            'location': f"{weather_data['name']}, {weather_data['sys']['country']}",
            'temperature': {
                'current': round(weather_data['main']['temp']),
                'feels_like': round(weather_data['main']['feels_like']),
                'min': round(weather_data['main']['temp_min']),
                'max': round(weather_data['main']['temp_max']),
                'unit': '°C'
            },
            'condition': {
                'main': weather_data['weather'][0]['main'],
                'description': weather_data['weather'][0]['description'].capitalize(),
                'icon': weather_data['weather'][0]['icon']
            },
            'details': {
                'humidity': weather_data['main']['humidity'],
                'pressure': weather_data['main']['pressure'],
                'wind_speed': round(weather_data['wind']['speed'] * 3.6, 1),  # m/s to km/h
                'wind_direction': weather_data['wind'].get('deg', 0)
            },
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sunrise': datetime.fromtimestamp(weather_data['sys']['sunrise']).strftime('%H:%M'),
            'sunset': datetime.fromtimestamp(weather_data['sys']['sunset']).strftime('%H:%M')
        }
        
        # Add weather impact assessment
        impact = get_transit_weather_impact(weather_data)
        formatted['transit_impact'] = impact
        
        return formatted
    except Exception as e:
        logger.error(f"Error formatting weather data: {e}")
        return {
            'available': False,
            'error': f'Error formatting weather data: {str(e)}'
        }