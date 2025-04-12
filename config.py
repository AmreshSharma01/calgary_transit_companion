import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Application settings
DEBUG = os.getenv('DEBUG', 'True') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY', 'development-key-change-in-production')

# API URLs
VEHICLE_URL = os.getenv('VEHICLE_URL', "https://data.calgary.ca/download/am7c-qe3u/application%2Foctet-stream")
TRIP_UPDATE_URL = os.getenv('TRIP_UPDATE_URL', "https://data.calgary.ca/download/gs4m-mdc2/application%2Foctet-stream")
ALERT_URL = os.getenv('ALERT_URL', "https://data.calgary.ca/download/jhgn-ynqj/application%2Foctet-stream")

# Database settings
DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///transit.db')

# GTFS data settings
GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'gtfs')

# Map settings
DEFAULT_LAT = 51.0447
DEFAULT_LON = -114.0719
DEFAULT_ZOOM = 13

# Weather API settings
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')

# GTFS Realtime feeds 
GTFS_RT_VEHICLE_POSITIONS = VEHICLE_URL
GTFS_RT_TRIP_UPDATES = TRIP_UPDATE_URL
GTFS_RT_SERVICE_ALERTS = ALERT_URL