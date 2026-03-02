"""Database configuration for Floosball application."""

# Set to True to use database storage, False to use JSON files
USE_DATABASE = True

# Database connection string (can be changed for different databases)
DATABASE_URL = "sqlite:///data/floosball.db"

# Whether to clear database on fresh start (set to False once data is permanent)
CLEAR_ON_START = True
