from flask import Flask, render_template
from database.db_setup import init_db, db_session
from database.models import Route, Stop, Trip, StopTime, Shape, User, UserFavoriteRoute
from services.gtfs_service import load_static_gtfs_data
import os

app = Flask(__name__)

GTFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'gtfs')

def setup(force_reload=False):
    init_db()
    try:
        if force_reload or Route.query.count() == 0:
            print("Loading GTFS data into database...")
            load_static_gtfs_data(GTFS_DIR)
    except Exception as e:
        print(f"Error during setup: {e}")

with app.app_context():
    setup()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)