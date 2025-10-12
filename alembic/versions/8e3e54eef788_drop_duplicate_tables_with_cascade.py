"""Drop duplicate tables with CASCADE

Revision ID: 8e3e54eef788
Revises: f909172dbee7
Create Date: 2025-09-30 23:58:04.906675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8e3e54eef788'
down_revision: Union[str, None] = 'f909172dbee7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop duplicate tables with CASCADE to handle foreign key constraints
    # These are duplicate tables that should be removed in favor of singular versions
    op.execute("DROP TABLE IF EXISTS user_repos CASCADE")
    op.execute("DROP TABLE IF EXISTS user_tokens CASCADE") 
    op.execute("DROP TABLE IF EXISTS repos CASCADE")
    op.execute("DROP TABLE IF EXISTS webhooks CASCADE")
    op.execute("DROP TABLE IF EXISTS labels CASCADE")


def downgrade() -> None:
    # Note: This migration removes duplicate tables
    # Downgrade would recreate them, but we don't want that
    # If you need to rollback, you should restore from database backup
    print("WARNING: This migration removes duplicate tables.")
    print("Rollback would recreate duplicate tables which is not recommended.")
    print("If you need to rollback, restore from database backup instead.")
    pass
