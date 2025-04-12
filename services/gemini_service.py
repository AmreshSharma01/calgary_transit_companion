"""
Gemini AI service for generating transit suggestions based on weather
"""
from google import genai
import requests

# Configuration
OPENWEATHER_API_KEY = "88ce1e9d33a3a8e789ac2d43a9847a1a"
CITY_NAME = "Calgary"
COUNTRY_CODE = "CA"
GEMINI_API_KEY = "AIzaSyBfaoqr3dIY81EtJTsX7I0nIJ30pQJ8tRY"

def get_weather(city, country_code, api_key):
    """
    Get current weather data from OpenWeather API
    
    Args:
        city: City name
        country_code: Country code (e.g., 'CA' for Canada)
        api_key: OpenWeather API key
        
    Returns:
        Weather data JSON
    """
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city},{country_code}&appid={api_key}&units=metric"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def generate_transit_suggestion(weather_data):
    """
    Generate a transit suggestion using Gemini AI based on current weather conditions
    
    Args:
        weather_data: Weather data dictionary from OpenWeather API
        
    Returns:
        String with the suggestion
    """
    try:
        temperature = weather_data['main']['temp']
        description = weather_data['weather'][0]['description']
        wind_speed = weather_data['wind']['speed']

        prompt = (
            f"The current weather in Calgary is {temperature}°C with {description}. "
            f"Wind speed is {wind_speed} m/s. Based on this weather, provide a structured transit suggestion with the following format:\n\n"
            f"Quick Summary: [One short sentence]\n"
            f"What to Wear: [Concise clothing recommendation]\n"
            f"Transit Tips: [1-2 practical transit tips]\n"
            f"Additional Advice: [Optional brief extra advice if needed]\n\n"
            f"Be brief and practical. Format as plain text with clear line breaks."
        )

        # Initialize the Gemini API client
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Use Gemini API to generate content based on the prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # Specify the model
            contents=[prompt]
        )

        # Return the response text
        return response.text
    
    except Exception as e:
        print(f"Error generating transit suggestion with Gemini: {e}")
        return "Unable to generate transit suggestion at this time." 