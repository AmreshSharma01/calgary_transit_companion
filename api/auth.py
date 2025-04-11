"""
Authentication module for the API
"""
import datetime
from flask import request, jsonify

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    # Fallback implementation if werkzeug is not available
    import hashlib
    def generate_password_hash(password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def check_password_hash(hash_value, password):
        return hash_value == generate_password_hash(password)
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity
)

from . import api_bp
from database.db_setup import db_session
from database.models import User

# Authentication routes
@api_bp.route('/auth/register', methods=['POST'])
def register():
    """
    Register a new user
    
    Request body:
    {
        "username": "username",
        "email": "email@example.com",
        "password": "password"
    }
    """
    data = request.get_json()
    
    # Validate input
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    # Create new user
    new_user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        created_at=datetime.datetime.now()
    )
    
    db_session.add(new_user)
    db_session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email
        }
    }), 201

@api_bp.route('/auth/login', methods=['POST'])
def login():
    """
    Authenticate a user and return JWT tokens
    
    Request body:
    {
        "username": "username",
        "password": "password"
    }
    """
    data = request.get_json()
    
    # Validate input
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
    
    # Find user
    user = User.query.filter_by(username=data['username']).first()
    
    # Verify user and password
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Create tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    }), 200

@api_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh the access token using a refresh token
    """
    current_user = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user)
    
    return jsonify({
        'access_token': new_access_token
    }), 200