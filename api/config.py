"""
API configuration and middleware
"""
import os
from datetime import timedelta
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# JWT configuration
jwt = JWTManager()

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# CORS middleware
cors = CORS()

def configure_api(app):
    """Configure API extensions and middleware"""
    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'calgary-transit-jwt-secret')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    jwt.init_app(app)
    
    # Configure rate limiter
    limiter.init_app(app)
    
    # Configure CORS
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register API routes with rate limiting
    from . import api_bp
    
    # Apply rate limits to specific endpoints
    limiter.limit("3 per minute")(api_bp.route('/auth/register', methods=['POST']))
    limiter.limit("5 per minute")(api_bp.route('/auth/login', methods=['POST']))
    
    # Register blueprint
    app.register_blueprint(api_bp)
    
    return app