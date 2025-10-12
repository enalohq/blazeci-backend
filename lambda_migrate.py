"""
Lambda Database Migration Utility
Handles database migrations in AWS Lambda environment
"""
import os
import sys
from pathlib import Path
from sqlmodel import create_engine
import subprocess


def migrate_lambda_db():
    """
    Run database migrations in Lambda environment
    This function can be called from Lambda to ensure schema is up to date
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    try:
        # In Lambda, we need to ensure migrations are applied
        print(f"🔄 Running database migrations for: {database_url}")
        
        # Create engine to test connection
        engine = create_engine(database_url, echo=False)
        
        # Try to run alembic upgrade
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print("✅ Lambda database migrations completed successfully")
            return True
        else:
            print(f"⚠️ Alembic migration failed in Lambda: {result.stderr}")
            # In Lambda, we might need to fall back to create_all
            from sqlmodel import SQLModel
            from app.models import *  # Import all models
            
            SQLModel.metadata.create_all(engine)
            print("✅ Fallback table creation completed")
            return True
            
    except Exception as e:
        print(f"❌ Lambda migration error: {e}")
        return False


def check_migration_status():
    """Check current migration status"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "alembic", "current"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            current_rev = result.stdout.strip()
            print(f"📊 Current migration: {current_rev}")
            return current_rev
        else:
            print("❌ Could not determine current migration status")
            return None
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return None


if __name__ == "__main__":
    # Can be run standalone for testing
    print("🗃️ Lambda Database Migration Utility")
    migrate_lambda_db()
    check_migration_status()