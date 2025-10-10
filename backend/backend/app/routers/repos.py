from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from ..db import get_session
from ..models import UserToken, Repo, Label, Webhook, UserRepo
from ..security import decrypt_token, read_session_cookie
from ..github import list_user_repos, list_user_orgs, list_org_repos, get_authenticated_user

router = APIRouter(prefix="/api", tags=["repos"])


def get_current_user_id(request: Request, session_db: Session) -> int:
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = read_session_cookie(cookie)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Debug: Get user info to verify correct user
    user = session_db.get(UserToken, user_id)
    if user:
        print(f"DEBUG: Session resolved to user {user.github_login} (GitHub ID: {user.github_user_id}, DB ID: {user_id})")
    else:
        print(f"DEBUG: Session cookie points to non-existent user ID: {user_id}")
    
    return user_id


@router.get("/repos")
async def get_repos(request: Request, session_db: Session = Depends(get_session)) -> List[dict]:
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(UserToken, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    token = decrypt_token(user.encrypted_token)
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
    user = session_db.get(UserToken, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    token = decrypt_token(user.encrypted_token)
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
    user = session_db.get(UserToken, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    token = decrypt_token(user.encrypted_token)
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
    repo = session_db.exec(select(Repo).where(Repo.github_repo_id == github_repo_id)).first()
    if not repo:
        repo = Repo(
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
        select(UserRepo).where(UserRepo.user_id == user_id, UserRepo.repo_id == repo.id)
    ).first()
    
    if not existing_user_repo:
        # Create user-repo relationship
        user_repo = UserRepo(user_id=user_id, repo_id=repo.id)
        session_db.add(user_repo)
        session_db.commit()
        session_db.refresh(user_repo)
    
    return {"ok": True, "repo_id": repo.id, "name": repo.name, "owner_login": repo.owner_login}


@router.get("/repos/selected")
def list_selected(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    # Join UserRepo and Repo to get user's selected repos
    user_repos = session_db.exec(
        select(Repo, UserRepo).join(UserRepo).where(UserRepo.user_id == user_id)
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


@router.post("/repos/label")
def set_label(payload: dict, request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    repo_id = int(payload.get("repo_id", 0))
    name = (payload.get("name") or "").strip()
    if not repo_id or not name:
        raise HTTPException(status_code=400, detail="repo_id and name are required")
    
    # Check if user has access to this repo
    user_repo = session_db.exec(
        select(UserRepo).where(UserRepo.user_id == user_id, UserRepo.repo_id == repo_id)
    ).first()
    if not user_repo:
        raise HTTPException(status_code=404, detail="Repo not found for user")
    
    # upsert label per repo
    existing = session_db.exec(select(Label).where(Label.repo_id == repo_id)).first()
    if existing:
        existing.name = name
    else:
        existing = Label(repo_id=repo_id, name=name)
        session_db.add(existing)
    session_db.commit()
    session_db.refresh(existing)
    return {"ok": True, "label_id": existing.id, "name": existing.name}


@router.get("/repos/labels")
def list_labels(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    # Get labels for repos the user has access to
    user_repos = session_db.exec(
        select(UserRepo).where(UserRepo.user_id == user_id)
    ).all()
    repo_ids = [ur.repo_id for ur in user_repos]
    
    if repo_ids:
        labels = session_db.exec(select(Label).where(Label.repo_id.in_(repo_ids))).all()
    else:
        labels = []
    return [{"id": l.id, "repo_id": l.repo_id, "name": l.name} for l in labels]


@router.get("/overview")
def overview(request: Request, session_db: Session = Depends(get_session)):
    user_id = get_current_user_id(request, session_db)
    user = session_db.get(UserToken, user_id)
    token_present = bool(user and user.encrypted_token)
    
    # Get user's repos via many-to-many relationship
    user_repos = session_db.exec(
        select(Repo, UserRepo).join(UserRepo).where(UserRepo.user_id == user_id)
    ).all()
    
    repo_ids = [repo.id for repo, _ in user_repos]
    labels_by_repo = {l.repo_id: l for l in (session_db.exec(select(Label).where(Label.repo_id.in_(repo_ids))).all() if repo_ids else [])}
    webhooks_by_repo = {w.repo_id: w for w in (session_db.exec(select(Webhook).where(Webhook.repo_id.in_(repo_ids))).all() if repo_ids else [])}
    
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
            "label": ({"id": labels_by_repo[repo.id].id, "name": labels_by_repo[repo.id].name} if repo.id in labels_by_repo else None),
            "webhook": (
                {
                    "id": webhooks_by_repo[repo.id].webhook_id,
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
    user = session_db.get(UserToken, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "github_user_id": user.github_user_id, "github_login": user.github_login, "token_present": True}


