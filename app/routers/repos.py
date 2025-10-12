from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from ..db import get_session
from ..models import Users, UserTokens, Repos, Webhooks, UserRepos
from ..security import decrypt_token, read_session_cookie
from ..github import list_user_repos, list_user_orgs, list_org_repos, get_authenticated_user

router = APIRouter(prefix="/api", tags=["repos"])


def get_current_user_id(request: Request, session_db: Session) -> int:
    cookie = request.cookies.get("session")
    print(f"DEBUG: API request from {request.client.host if request.client else 'unknown'}")
    print(f"DEBUG: Request headers: {dict(request.headers)}")
    print(f"DEBUG: All cookies: {request.cookies}")
    print(f"DEBUG: Session cookie received: {cookie[:20] + '...' if cookie else 'None'}")
    print(f"DEBUG: Origin header: {request.headers.get('origin')}")
    print(f"DEBUG: Referer header: {request.headers.get('referer')}")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = read_session_cookie(cookie)
    print(f"DEBUG: Decoded user_id: {user_id}")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Debug: Get user info to verify correct user
    user = session_db.get(Users, user_id)
    if user:
        print(f"DEBUG: Session resolved to user {user.github_login} (GitHub ID: {user.github_user_id}, DB ID: {user_id})")
    else:
        print(f"DEBUG: Session cookie points to non-existent user ID: {user_id}")
    
    return user_id


@router.get("/repos")
async def get_repos(request: Request, session_db: Session = Depends(get_session)) -> List[dict]:
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Get user's token
    token_record = session_db.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="User token not found")
    token = decrypt_token(token_record.encrypted_token)
    repos = await list_user_repos(token)
    # Minimal projection for frontend
    return [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "private": r.get("private"),
            "owner_login": r.get("owner", {}).get("login"),
        }
        for r in repos
    ]


@router.get("/account")
async def account_info(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Get user's token
    token_record = session_db.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="User token not found")
    token = decrypt_token(token_record.encrypted_token)
    me = await get_authenticated_user(token)
    print(f"DEBUG: Getting organizations for user {me.get('login')}")
    orgs = await list_user_orgs(token)
    print(f"DEBUG: Found {len(orgs)} organizations: {[o.get('login') for o in orgs]}")
    return {
        "login": me.get("login"),
        "type": me.get("type"),  # "User" or "Organization" (for PATs acting as org)
        "orgs": [{"login": o.get("login"), "id": o.get("id"), "avatar_url": o.get("avatar_url")} for o in orgs],
    }


@router.get("/repos/by-owner")
async def repos_by_owner(owner_login: str, request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Get user's token
    token_record = session_db.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="User token not found")
    token = decrypt_token(token_record.encrypted_token)
    repos = await list_org_repos(token, owner_login)
    return [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "private": r.get("private"),
            "owner_login": r.get("owner", {}).get("login"),
        }
        for r in repos
    ]


@router.post("/repos/select")
async def select_repo(payload: dict, request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    github_repo_id = int(payload.get("id"))
    name = payload.get("name")
    owner_login = payload.get("owner_login")
    full_name = payload.get("full_name", f"{owner_login}/{name}")
    private = payload.get("private", False)
    
    if not (github_repo_id and name and owner_login):
        raise HTTPException(status_code=400, detail="Missing repo fields")
    
    # Find or create repo
    repo = session_db.exec(select(Repos).where(Repos.github_repo_id == github_repo_id)).first()
    if not repo:
        repo = Repos(
            github_repo_id=github_repo_id,
            name=name,
            owner_login=owner_login,
            full_name=full_name,
            private=private
        )
        session_db.add(repo)
        session_db.commit()
        session_db.refresh(repo)
    
    # Check if user already selected this repo
    existing_user_repo = session_db.exec(
        select(UserRepos).where(UserRepos.user_id == user_id, UserRepos.github_repo_id == repo.github_repo_id)
    ).first()
    
    if not existing_user_repo:
        # Create user-repo relationship
        user_repo = UserRepos(user_id=user_id, github_repo_id=repo.github_repo_id)
        session_db.add(user_repo)
        session_db.commit()
        session_db.refresh(user_repo)
    
    return {"ok": True, "repo_id": repo.id, "name": repo.name, "owner_login": repo.owner_login}


@router.get("/repos/selected")
def list_selected(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    # Join UserRepos and Repos to get user's selected repos
    user_repos = session_db.exec(
        select(Repos, UserRepos).join(UserRepos, Repos.github_repo_id == UserRepos.github_repo_id).where(UserRepos.user_id == user_id)
    ).all()
    return [
        {
            "id": repo.id,
            "github_repo_id": repo.github_repo_id,
            "name": repo.name,
            "owner_login": repo.owner_login,
            "full_name": repo.full_name,
            "private": repo.private,
            "selected_at": user_repo.selected_at.isoformat() if user_repo else None,
        }
        for repo, user_repo in user_repos
    ]


# Label functionality removed - labels table was eliminated in schema refactor


# list_labels function removed - labels table was eliminated in schema refactor


@router.get("/overview")
def overview(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(Users, user_id)
    
    # Check if user has token
    token_record = session_db.exec(select(UserTokens).where(UserTokens.user_id == user_id)).first()
    token_present = bool(user and token_record and token_record.encrypted_token)
    
    # Get user's repos via many-to-many relationship
    user_repos = session_db.exec(
        select(Repos, UserRepos).join(UserRepos, Repos.github_repo_id == UserRepos.github_repo_id).where(UserRepos.user_id == user_id)
    ).all()
    
    repo_ids = [repo.id for repo, _ in user_repos]
    webhooks_by_repo = {w.repo_id: w for w in (session_db.exec(select(Webhooks).where(Webhooks.repo_id.in_(repo_ids))).all() if repo_ids else [])}
    
    return [
        {
            "repo": {
                "db_id": repo.id,
                "github_repo_id": repo.github_repo_id,
                "name": repo.name,
                "owner": repo.owner_login,
                "full_name": repo.full_name,
                "private": repo.private,
            },
            "token_present": token_present,
            "webhook": (
                {
                    "id": webhooks_by_repo[repo.id].github_webhook_id,
                    "url": webhooks_by_repo[repo.id].url,
                    "active": webhooks_by_repo[repo.id].active,
                }
                if repo.id in webhooks_by_repo
                else None
            ),
        }
        for repo, user_repo in user_repos
    ]


@router.get("/user")
def user_info(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(Users, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user has token
    token_record = session_db.exec(select(UserTokens).where(UserTokens.user_id == user_id)).first()
    token_present = bool(token_record and token_record.encrypted_token)
    
    return {
        "id": user.id, 
        "github_user_id": user.github_user_id, 
        "github_login": user.github_login,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "token_present": token_present
    }


