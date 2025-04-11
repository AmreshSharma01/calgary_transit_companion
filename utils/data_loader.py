import os
import csv
import sys
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_setup import Base
from database.models import Route, Stop, Trip, StopTime, Shape
from services.gtfs_service import load_static_gtfs_data

def setup_database(db_path, gtfs_dir):
    """
    Set up the database and load GTFS data
    
    Args:
        db_path: Path to the SQLite database file
        gtfs_dir: Directory containing GTFS text files
    """
    # Create database engine
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if data already exists
        route_count = session.query(Route).count()
        if route_count > 0:
            print(f"Database already contains {route_count} routes.")
            overwrite = input("Do you want to overwrite the existing data? (y/n): ")
            if overwrite.lower() != 'y':
                print("Exiting without changes.")
                return
            
            # Clear existing data
            print("Clearing existing data...")
            session.query(StopTime).delete()
            session.query(Trip).delete()
            session.query(Stop).delete()
            session.query(Shape).delete()
            session.query(Route).delete()
            session.commit()
        
        # Load GTFS data
        print(f"Loading GTFS data from {gtfs_dir}...")
        load_static_gtfs_data(gtfs_dir, session)
        
        # Commit changes
        session.commit()
        print("Data loading complete!")
        
        # Print stats
        route_count = session.query(Route).count()
        stop_count = session.query(Stop).count()
        trip_count = session.query(Trip).count()
        stoptime_count = session.query(StopTime).count()
        shape_count = session.query(Shape).count()
        
        print(f"\nDatabase Statistics:")
        print(f"- Routes: {route_count}")
        print(f"- Stops: {stop_count}")
        print(f"- Trips: {trip_count}")
        print(f"- Stop Times: {stoptime_count}")
        print(f"- Shape Points: {shape_count}")
        
    except Exception as e:
        session.rollback()
        print(f"Error loading data: {e}")
    finally:
        session.close()

def main():
    """Command line interface for the data loader"""
    parser = argparse.ArgumentParser(description='Load GTFS data into the database')
    parser.add_argument('--db', default='transit.db', help='Path to the SQLite database file')
    parser.add_argument('--gtfs', default='static/gtfs', help='Directory containing GTFS text files')
    args = parser.parse_args()
    
    # Convert relative paths to absolute
    db_path = os.path.abspath(args.db)
    gtfs_dir = os.path.abspath(args.gtfs)
    
    # Check if GTFS directory exists
    if not os.path.isdir(gtfs_dir):
        print(f"Error: GTFS directory {gtfs_dir} does not exist.")
        return
    
    # Check if GTFS files exist
    required_files = ['routes.txt', 'stops.txt', 'trips.txt', 'stop_times.txt']
    missing_files = [f for f in required_files if not os.path.exists(os.path.join(gtfs_dir, f))]
    
    if missing_files:
        print(f"Error: Missing required GTFS files: {', '.join(missing_files)}")
        return
    
    # Set up database
    setup_database(db_path, gtfs_dir)

if __name__ == '__main__':
    main()