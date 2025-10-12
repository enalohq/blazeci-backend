from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from .config import settings
import subprocess
import sys
from pathlib import Path


engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db() -> None:
    """Initialize database with Alembic migrations"""
    try:
        # Run Alembic upgrade to head
        backend_dir = Path(__file__).parent.parent
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], cwd=backend_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Database migrations applied successfully")
        else:
            print(f"⚠️ Alembic migration failed: {result.stderr}")
            # Fallback to basic table creation
            print("🔄 Falling back to basic table creation...")
            SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        # Fallback to basic table creation
        print("🔄 Falling back to basic table creation...")
        SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session



@contextmanager
def session_scope():
    """Context manager for DB sessions outside FastAPI dependency system."""
    with Session(engine) as session:
        yield session

