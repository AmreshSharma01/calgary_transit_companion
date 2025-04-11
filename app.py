from flask import Flask, render_template
from database.db_setup import init_db, db_session
from database.models import Route, Stop, Trip, StopTime, Shape, User, UserFavoriteRoute

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)