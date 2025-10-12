"""merge_heads_resolve_conflict

Revision ID: 34ddbead2b87
Revises: 374535b40c04, custom_schema_refactor
Create Date: 2025-10-01 11:13:35.305580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34ddbead2b87'
down_revision: Union[str, None] = ('374535b40c04', 'custom_schema_refactor')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
