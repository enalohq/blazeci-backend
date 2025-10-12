"""Create new plural tables schema

Revision ID: custom_schema_refactor
Revises: 8e3e54eef788
Create Date: 2025-10-01 08:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'custom_schema_refactor'
down_revision: Union[str, None] = '8e3e54eef788'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_user_id', sa.String(255), nullable=False),
        sa.Column('github_login', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('github_user_id')
    )
    op.create_index('ix_users_github_user_id', 'users', ['github_user_id'])
    op.create_index('ix_users_github_login', 'users', ['github_login'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Create new UserTokens table
    op.create_table('user_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('encrypted_token', sa.Text(), nullable=False),
        sa.Column('token_type', sa.String(50), nullable=False, server_default='oauth'),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index('ix_user_tokens_user_id', 'user_tokens', ['user_id'])

    # Create new Repos table (plural)
    op.create_table('repos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_repo_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_login', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('private', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('default_branch', sa.String(100), nullable=False, server_default='main'),
        sa.Column('language', sa.String(100), nullable=True),
        sa.Column('stars_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('forks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('github_repo_id')
    )
    op.create_index('ix_repos_github_repo_id', 'repos', ['github_repo_id'])
    op.create_index('ix_repos_name', 'repos', ['name'])
    op.create_index('ix_repos_owner_login', 'repos', ['owner_login'])
    op.create_index('ix_repos_full_name', 'repos', ['full_name'])

    # Create new UserRepos table (plural)
    op.create_table('user_repos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('github_repo_id', sa.Integer(), nullable=False),
        sa.Column('permission', sa.String(50), nullable=False, server_default='read'),
        sa.Column('selected_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['github_repo_id'], ['repos.github_repo_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'github_repo_id')
    )
    op.create_index('ix_user_repos_user_id', 'user_repos', ['user_id'])
    op.create_index('ix_user_repos_github_repo_id', 'user_repos', ['github_repo_id'])

    # Create new Webhooks table (plural)
    op.create_table('webhooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('github_webhook_id', sa.Integer(), nullable=True),
        sa.Column('secret', sa.String(255), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('events', sa.String(500), nullable=False, server_default='push'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE')
    )
    op.create_index('ix_webhooks_repo_id', 'webhooks', ['repo_id'])

    # Migrate data from old tables to new tables
    op.execute("""
        -- Migrate usertoken to users and user_tokens
        INSERT INTO users (github_user_id, github_login, created_at, updated_at)
        SELECT github_user_id, github_login, created_at, updated_at
        FROM usertoken;
        
        INSERT INTO user_tokens (user_id, encrypted_token, created_at, updated_at)
        SELECT u.id, ut.encrypted_token, ut.created_at, ut.updated_at
        FROM usertoken ut
        JOIN users u ON u.github_user_id = ut.github_user_id;
        
        -- Migrate repo to repos
        INSERT INTO repos (github_repo_id, name, owner_login, full_name, private, created_at, updated_at)
        SELECT github_repo_id, name, owner_login, full_name, private, created_at, 
               COALESCE(created_at, CURRENT_TIMESTAMP) as updated_at
        FROM repo;
        
        -- Migrate userrepo to user_repos
        INSERT INTO user_repos (user_id, github_repo_id, selected_at)
        SELECT u.id, r.github_repo_id, ur.selected_at
        FROM userrepo ur
        JOIN usertoken ut ON ut.id = ur.user_id
        JOIN users u ON u.github_user_id = ut.github_user_id
        JOIN repo r ON r.id = ur.repo_id;
        
        -- Migrate webhook to webhooks
        INSERT INTO webhooks (repo_id, github_webhook_id, secret, url, active, created_at, updated_at)
        SELECT r_new.id, w.webhook_id, w.secret, w.url, w.active, w.created_at,
               COALESCE(w.created_at, CURRENT_TIMESTAMP) as updated_at
        FROM webhook w
        JOIN repo r_old ON r_old.id = w.repo_id
        JOIN repos r_new ON r_new.github_repo_id = r_old.github_repo_id;
    """)

    # Drop old tables with CASCADE to handle foreign keys
    op.execute("DROP TABLE IF EXISTS userrepo CASCADE")
    op.execute("DROP TABLE IF EXISTS webhook CASCADE") 
    op.execute("DROP TABLE IF EXISTS usertoken CASCADE")
    op.execute("DROP TABLE IF EXISTS repo CASCADE")
    op.execute("DROP TABLE IF EXISTS label CASCADE")  # Remove labels table as requested


def downgrade() -> None:
    # This is a major schema change - backup and restore from backup instead
    print("WARNING: This migration completely restructures the schema.")
    print("Rollback requires restoring from database backup.")
    pass