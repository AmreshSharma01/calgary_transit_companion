import os
from dotenv import load_dotenv

load_dotenv()

DEBUG = os.getenv('DEBUG', 'True') == 'True'

DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///transit.db')

GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'gtfs')