"""merge_github_app_migrations

Revision ID: 2f96ffc9837e
Revises: 008a19ff5e36, github_app_simple
Create Date: 2025-10-01 16:37:43.672127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f96ffc9837e'
down_revision: Union[str, None] = ('008a19ff5e36', 'github_app_simple')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
