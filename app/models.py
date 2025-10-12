from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from datetime import datetime


class GitHubInstallations(SQLModel, table=True):
    """GitHub App installations for organizations/users"""
    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(index=True)  # GitHub installation ID
    account_id: int = Field(index=True)  # GitHub account ID (user or org)
    account_login: str = Field(index=True)  # GitHub account login name
    account_type: str = Field(index=True)  # "User" or "Organization"
    # dropped target_type (redundant with account_type)
    permissions: Optional[str] = Field(default=None)  # JSON string of permissions
    events: Optional[str] = Field(default=None)  # JSON string of subscribed events
    suspended_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("installation_id", "account_id"),
    )


class Users(SQLModel, table=True):
    """User information from GitHub OAuth"""
    id: Optional[int] = Field(default=None, primary_key=True)
    github_user_id: int = Field(unique=True, index=True)  # GitHub's numeric user ID
    github_login: str = Field(index=True)  # GitHub username (not unique, renames possible)
    email: Optional[str] = Field(default=None, index=True)
    name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    tokens: List["UserTokens"] = Relationship(back_populates="user")
    user_repos: List["UserRepos"] = Relationship(back_populates="user")


class UserTokens(SQLModel, table=True):
    """OAuth tokens for users - separate table for security"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    encrypted_token: str  # The actual OAuth token, encrypted (use Text/LargeBinary in real DB)
    token_type: str = Field(default="oauth")  # oauth, pat, etc.
    scopes: Optional[str] = Field(default=None)  # Comma-separated OAuth scopes
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional[Users] = Relationship(back_populates="tokens")


class Repos(SQLModel, table=True):
    """Repository information from GitHub"""
    id: Optional[int] = Field(default=None, primary_key=True)
    github_repo_id: int = Field(unique=True, index=True)
    name: str = Field(index=True)
    owner_login: str = Field(index=True)
    full_name: str = Field(index=True)  # owner/repo format
    description: Optional[str] = Field(default=None)
    private: bool = Field(default=False)
    default_branch: str = Field(default="main")
    language: Optional[str] = Field(default=None)
    stars_count: int = Field(default=0)
    forks_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user_repos: List["UserRepos"] = Relationship(back_populates="repo")
    webhooks: List["Webhooks"] = Relationship(back_populates="repo")

    __table_args__ = (
        UniqueConstraint("owner_login", "name"),
    )


class UserRepos(SQLModel, table=True):
    """Many-to-many relationship: which users have access to which repos"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    github_repo_id: int = Field(foreign_key="repos.github_repo_id", index=True)  # matches database schema
    permission: str = Field(default="read")  # read, write, admin
    selected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional[Users] = Relationship(back_populates="user_repos")
    repo: Optional[Repos] = Relationship(back_populates="user_repos")
    
    __table_args__ = (
        UniqueConstraint("user_id", "github_repo_id"),
    )


class Webhooks(SQLModel, table=True):
    """GitHub webhooks for repositories"""
    id: Optional[int] = Field(default=None, primary_key=True)
    repo_id: int = Field(foreign_key="repos.id", index=True)
    github_webhook_id: Optional[int] = Field(default=None)
    secret: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    events: str = Field(default="push")
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    repo: Optional[Repos] = Relationship(back_populates="webhooks")

    __table_args__ = (
        UniqueConstraint("repo_id", "github_webhook_id"),
    )
