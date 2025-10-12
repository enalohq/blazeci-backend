#!/usr/bin/env python3
"""
Database Migration Management Script
Provides easy commands for managing Alembic migrations
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print the result"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} failed")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_migration(message):
    """Create a new migration"""
    if not message:
        message = input("Enter migration message: ")
    
    cmd = f"alembic revision --autogenerate -m \"{message}\""
    return run_command(cmd, f"Creating migration: {message}")

def upgrade_database(revision="head"):
    """Upgrade database to specific revision"""
    cmd = f"alembic upgrade {revision}"
    return run_command(cmd, f"Upgrading database to {revision}")

def downgrade_database(revision):
    """Downgrade database to specific revision"""
    if not revision:
        revision = input("Enter revision to downgrade to: ")
    
    cmd = f"alembic downgrade {revision}"
    return run_command(cmd, f"Downgrading database to {revision}")

def show_history():
    """Show migration history"""
    cmd = "alembic history"
    return run_command(cmd, "Showing migration history")

def show_current():
    """Show current migration"""
    cmd = "alembic current"
    return run_command(cmd, "Showing current migration")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("""
🗃️  Database Migration Manager

Usage:
    python migrate.py <command> [args]

Commands:
    create <message>     Create a new migration
    upgrade [revision]   Upgrade to revision (default: head)
    downgrade <revision> Downgrade to revision
    history             Show migration history
    current             Show current migration
    status              Show current status

Examples:
    python migrate.py create "Add user table"
    python migrate.py upgrade
    python migrate.py upgrade +1
    python migrate.py downgrade -1
    python migrate.py history
        """)
        return

    command = sys.argv[1].lower()
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    if command == "create":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        create_migration(message)
    
    elif command == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        upgrade_database(revision)
    
    elif command == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else None
        downgrade_database(revision)
    
    elif command == "history":
        show_history()
    
    elif command == "current":
        show_current()
    
    elif command == "status":
        print("📊 Current Migration Status:")
        show_current()
        print("\n📚 Migration History:")
        show_history()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Run 'python migrate.py' for help")

if __name__ == "__main__":
    main()