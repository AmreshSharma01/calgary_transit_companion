#!/usr/bin/env python3
import os
import argparse
import sys
from application import app, setup  # Make sure this matches your actual filename
from config import DEBUG

def main():
    """Run the Flask application with command-line arguments"""
    parser = argparse.ArgumentParser(description='Run the Transit App')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--load-gtfs', action='store_true', help='Force reload GTFS data')
    
    args = parser.parse_args()
    
    # Handle GTFS data loading if requested
    if args.load_gtfs:
        print("Loading GTFS data...")
        # Call setup with app context
        with app.app_context():
            setup(force_reload=True)
        print("GTFS data loading complete.")
    
    # Set debug mode
    debug_mode = args.debug if args.debug else DEBUG
    
    # Run the app
    app.run(
        host=args.host,
        port=args.port,
        debug=debug_mode
    )

if __name__ == '__main__':
    main()