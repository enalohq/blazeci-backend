-- Database initialization script for Docker Compose
-- This script runs when the PostgreSQL container starts for the first time

-- Create the database (already created by POSTGRES_DB env var)
-- CREATE DATABASE github_auth_app;

-- Grant permissions to app_user
GRANT ALL PRIVILEGES ON DATABASE github_auth_app TO app_user;

-- Connect to the database
\c github_auth_app;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The tables will be created by Alembic migrations
-- This script just ensures the database and user are set up correctly
