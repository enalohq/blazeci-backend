from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class UserToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    github_user_id: str = Field(unique=True, index=True)  # Unique per GitHub user
    github_login: str
    encrypted_token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user_repos: List["UserRepo"] = Relationship(back_populates="user")


class Repo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    github_repo_id: int = Field(unique=True, index=True)  # Unique per GitHub repo
    name: str
    owner_login: str
    full_name: str  # owner/repo format
    private: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user_repos: List["UserRepo"] = Relationship(back_populates="repo")
    webhooks: List["Webhook"] = Relationship(back_populates="repo")
    label: Optional["Label"] = Relationship(back_populates="repo", sa_relationship_kwargs={"uselist": False})


class UserRepo(SQLModel, table=True):
    """Many-to-many relationship between users and repos"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="usertoken.id")
    repo_id: int = Field(foreign_key="repo.id")
    selected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional[UserToken] = Relationship(back_populates="user_repos")
    repo: Optional[Repo] = Relationship(back_populates="user_repos")


class Webhook(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    repo_id: int = Field(foreign_key="repo.id")
    webhook_id: Optional[int] = None
    secret: Optional[str] = None
    url: Optional[str] = None
    active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    repo: Optional[Repo] = Relationship(back_populates="webhooks")


class Label(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    repo_id: int = Field(foreign_key="repo.id", unique=True, index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    repo: Optional[Repo] = Relationship(back_populates="label")


