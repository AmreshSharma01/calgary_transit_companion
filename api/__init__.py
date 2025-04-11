"""
API Blueprint initialization module
"""
from flask import Blueprint

# Create the blueprint with the correct URL prefix
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import routes to register with the blueprint
from . import routes, auth