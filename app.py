from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
from nhl_data import get_available_players, get_next_game, get_team_links_for_research, TEAM_INFO
import logging
from twilio.rest import Client
import shutil
import json
from sqlalchemy import text
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('app')

# Initialize APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Shutdown the scheduler when the app is shutting down
atexit.register(lambda: scheduler.shutdown())

# Initialize Twilio client for SMS notifications
try:
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_from_number = os.environ.get('TWILIO_FROM_NUMBER')
    twilio_client = Client(account_sid, auth_token) if account_sid and auth_token else None
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Twilio client: {str(e)}")
    twilio_client = None

app = Flask(__name__)

# Set up database path - Use persistent disk on Render
db_path = os.environ.get('DATABASE_PATH', 'pool.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
logger.info(f"Using SQLite database at {db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key

# Session configuration - keep users logged in longer
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 day session lifetime
app.config['SESSION_TYPE'] = 'filesystem'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_REFRESH_EACH_REQUEST'] = True

# Create session directory if it doesn't exist
session_dir = os.path.join(app.root_path, 'flask_session')
os.makedirs(session_dir, exist_ok=True)
app.config['SESSION_FILE_DIR'] = session_dir

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('EMAIL_USER')

# Initialize the database
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)
sess = Session(app)  # Initialize Flask-Session

# Create a DatabaseInitMiddleware to initialize the database on startup
def init_db():
    """Initialize the database if not already done."""
    try:
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f"Tables in database: {tables}")
        
        # Create all tables if they don't exist
        db.create_all()
        
        # Check if the User table exists and has data
        user_table_exists = 'user' in tables
        if user_table_exists:
            try:
                # Use raw SQL instead of User.query.count() to avoid model dependency
                result = db.session.execute(text('SELECT COUNT(*) FROM "user"'))
                user_count = result.scalar()
                logger.info(f"User table successfully created")
            except Exception as e:
                logger.error(f"Error querying User table: {str(e)}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

# Database initialization middleware 
class DatabaseInitMiddleware:
    def __init__(self, app):
        self.app = app
        self.db_initialized = False

    def __call__(self, environ, start_response):
        if not self.db_initialized:
            try:
                with app.app_context():
                    success = init_db()
                    if success:
                        logger.info("Database initialized successfully")
                    else:
                        logger.error("Failed to initialize database")
                    self.db_initialized = True
            except Exception as e:
                logger.error(f"Error initializing database at startup: {str(e)}")
        
        return self.app(environ, start_response)

# Apply the middleware
app.wsgi_app = DatabaseInitMiddleware(app.wsgi_app)

# Initialize database at startup
try:
    with app.app_context():
        init_db()
except Exception as e:
    logger.error(f"Error initializing database at startup: {str(e)}")

# Models
class OfflinePlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    total_points = db.Column(db.Integer, default=0)
    past_picks = db.Column(db.JSON)  # Store past picks as JSON
    past_game_points = db.Column(db.JSON)  # Store points for each past game
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    draft_position = db.Column(db.Integer, unique=True)  # Add draft position for offline players

    def update_points_for_game(self, game_date, points):
        """Update points for a specific game"""
        if self.past_game_points is None:
            self.past_game_points = {}
        
        game_key = game_date.strftime('%Y-%m-%d')
        self.past_game_points[game_key] = points
        # Don't update total_points here as it's set separately

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))  # Add phone number field
    notification_preference = db.Column(db.String(10), default='sms')  # Now defaults to 'sms'
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    picks = db.relationship('Pick', backref='user', lazy=True)
    draft_position = db.Column(db.Integer, unique=True)
    offline_player_id = db.Column(db.Integer, unique=True)

    @property
    def total_points(self):
        """Calculate total points for all picks"""
        base_points = sum(pick.points for pick in self.picks)
        # Add points from linked offline player if exists
        if self.offline_player_id:
            offline_player = OfflinePlayer.query.get(self.offline_player_id)
            if offline_player:
                base_points += offline_player.total_points
        return base_points

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Pick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    player_name = db.Column(db.String(80), nullable=False)
    player_team = db.Column(db.String(80), nullable=False)
    game_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    points = db.Column(db.Integer, default=0)  # Track points for this pick
    pick_number = db.Column(db.Integer)  # New field to track pick order for each game

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    
    @classmethod
    def get(cls, key, default=None):
        """Get a setting value by key with optional default"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            return setting.value
        return default
    
    @classmethod
    def set(cls, key, value):
        """Set a setting value by key"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = cls(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
        return setting