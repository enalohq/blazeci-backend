"""add_github_installations_table_simple

Revision ID: github_app_simple
Revises: 34ddbead2b87
Create Date: 2025-10-01 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'github_app_simple'
down_revision: Union[str, None] = '34ddbead2b87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create GitHubInstallations table
    op.create_table('githubinstallations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('installation_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('account_login', sa.String(), nullable=False),
    sa.Column('account_type', sa.String(), nullable=False),
    sa.Column('target_type', sa.String(), nullable=False),
    sa.Column('permissions', sa.String(), nullable=True),
    sa.Column('events', sa.String(), nullable=True),
    sa.Column('suspended_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_githubinstallations_account_id'), 'githubinstallations', ['account_id'], unique=False)
    op.create_index(op.f('ix_githubinstallations_account_login'), 'githubinstallations', ['account_login'], unique=False)
    op.create_index(op.f('ix_githubinstallations_account_type'), 'githubinstallations', ['account_type'], unique=False)
    op.create_index(op.f('ix_githubinstallations_installation_id'), 'githubinstallations', ['installation_id'], unique=True)
    op.create_index(op.f('ix_githubinstallations_target_type'), 'githubinstallations', ['target_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_githubinstallations_target_type'), table_name='githubinstallations')
    op.drop_index(op.f('ix_githubinstallations_installation_id'), table_name='githubinstallations')
    op.drop_index(op.f('ix_githubinstallations_account_type'), table_name='githubinstallations')
    op.drop_index(op.f('ix_githubinstallations_account_login'), table_name='githubinstallations')
    op.drop_index(op.f('ix_githubinstallations_account_id'), table_name='githubinstallations')
    op.drop_table('githubinstallations')