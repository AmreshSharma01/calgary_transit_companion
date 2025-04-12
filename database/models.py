from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from database.db_setup import Base
from flask_login import UserMixin

class Route(Base):
    __tablename__ = 'routes'
    
    route_id = Column(String(50), primary_key=True)
    route_short_name = Column(String(50), nullable=True)
    route_long_name = Column(String(255), nullable=True)
    route_type = Column(Integer, nullable=True)
    route_url = Column(String(255), nullable=True)
    route_color = Column(String(10), nullable=True)
    route_text_color = Column(String(10), nullable=True)
    
    # Relationships
    trips = relationship("Trip", back_populates="route")
    
    def __repr__(self):
        return f"<Route {self.route_short_name}: {self.route_long_name}>"

class Stop(Base):
    __tablename__ = 'stops'
    
    stop_id = Column(String(50), primary_key=True)
    stop_code = Column(String(50), nullable=True)
    stop_name = Column(String(255), nullable=False)
    stop_desc = Column(String(255), nullable=True)
    stop_lat = Column(String(20), nullable=False)
    stop_lon = Column(String(20), nullable=False)
    zone_id = Column(String(50), nullable=True)
    stop_url = Column(String(255), nullable=True)
    location_type = Column(Integer, default=0, nullable=True)
    
    # Relationships
    stop_times = relationship("StopTime", back_populates="stop")
    
    def __repr__(self):
        return f"<Stop {self.stop_id}: {self.stop_name}>"

class Trip(Base):
    __tablename__ = 'trips'
    
    trip_id = Column(String(50), primary_key=True)
    route_id = Column(String(50), ForeignKey('routes.route_id'), nullable=False)
    service_id = Column(String(50), nullable=False)
    trip_headsign = Column(String(255), nullable=True)
    direction_id = Column(Integer, nullable=True)
    block_id = Column(String(50), nullable=True)
    shape_id = Column(String(50), nullable=True)
    
    # Relationships
    route = relationship("Route", back_populates="trips")
    stop_times = relationship("StopTime", back_populates="trip", order_by="StopTime.stop_sequence")
    
    def __repr__(self):
        return f"<Trip {self.trip_id}: {self.trip_headsign}>"

class StopTime(Base):
    __tablename__ = 'stop_times'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String(50), ForeignKey('trips.trip_id'), nullable=False)
    arrival_time = Column(String(10), nullable=True)
    departure_time = Column(String(10), nullable=True)
    stop_id = Column(String(50), ForeignKey('stops.stop_id'), nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    pickup_type = Column(Integer, default=0, nullable=True)
    drop_off_type = Column(Integer, default=0, nullable=True)
    shape_dist_traveled = Column(Float, nullable=True)
    
    # Relationships
    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")
    
    def __repr__(self):
        return f"<StopTime {self.trip_id} at {self.stop_id}: {self.arrival_time}>"

class Shape(Base):
    __tablename__ = 'shapes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shape_id = Column(String(50), nullable=False, index=True)
    shape_pt_lat = Column(String(20), nullable=False)
    shape_pt_lon = Column(String(20), nullable=False)
    shape_pt_sequence = Column(Integer, nullable=False)
    shape_dist_traveled = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<Shape {self.shape_id} #{self.shape_pt_sequence}>"

class User(UserMixin, Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=True)
    
    # Relationships
    favorite_routes = relationship("UserFavoriteRoute", back_populates="user")
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return True
        
    def __repr__(self):
        return f"<User {self.username}>"

class UserFavoriteRoute(Base):
    __tablename__ = 'user_favorite_routes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    route_id = Column(String(50), ForeignKey('routes.route_id'), nullable=False)
    added_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="favorite_routes")
    route = relationship("Route")
    
    def __repr__(self):
        return f"<UserFavoriteRoute {self.user_id}: {self.route_id}>"