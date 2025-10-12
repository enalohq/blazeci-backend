"""
GitHub App Router
Handles GitHub App installation, authentication, and runner management
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlmodel import Session, select
from typing import List, Dict, Any

from ..db import get_session
from ..models import GitHubInstallations, Users, UserRepos
from ..github_app import github_app, runner_manager
from ..security import read_session_cookie

router = APIRouter(prefix="/github-app", tags=["github-app"])


def get_current_user_id(request: Request, session_db: Session) -> int:
    """Get current user ID from session cookie"""
    cookie = request.cookies.get("session")
    print(f"🍪 DEBUG: Session cookie present: {bool(cookie)}")
    print(f"🍪 DEBUG: Session cookie value: {cookie[:20] if cookie else 'None'}...")
    
    if not cookie:
        print("❌ DEBUG: No session cookie found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    user_id = read_session_cookie(cookie)
    print(f"👤 DEBUG: Decoded user_id from session: {user_id}")
    
    if not user_id:
        print("❌ DEBUG: Invalid session cookie")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    # Verify user exists in database
    from ..models import Users
    user = session_db.get(Users, user_id)
    if not user:
        print(f"❌ DEBUG: User {user_id} not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    print(f"✅ DEBUG: User authenticated: {user.github_login}")
    return user_id


@router.get("/installations")
async def list_installations(
    request: Request,
    session: Session = Depends(get_session)
):
    """List all GitHub App installations - requires user authentication"""
    # Require user authentication
    user_id = get_current_user_id(request, session)
    print(f"🔥 DEBUG: GitHub App /installations called by user {user_id}")
    
    try:
        print("🔥 DEBUG: Calling github_app.get_installations()")
        installations = await github_app.get_installations()
        print(f"🔥 DEBUG: Got {len(installations)} installations")
        
        # Optional: Filter installations by user's GitHub account
        # This would require linking installations to users in your database
        
        return {"installations": installations}
    except Exception as e:
        print(f"🔥 DEBUG: ERROR in GitHub App installations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch installations: {str(e)}"
        )


@router.post("/installations/{installation_id}/sync")
async def sync_installation(
    installation_id: int,
    session: Session = Depends(get_session)
):
    """Sync installation data with database"""
    try:
        # Get installation details from GitHub
        installations = await github_app.get_installations()
        target_installation = None
        
        for installation in installations:
            if installation["id"] == installation_id:
                target_installation = installation
                break
        
        if not target_installation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Installation not found"
            )
        
        # Check if installation exists in database
        statement = select(GitHubInstallations).where(
            GitHubInstallations.installation_id == installation_id
        )
        existing = session.exec(statement).first()
        
        if existing:
            # Update existing installation
            existing.account_id = target_installation["account"]["id"]
            existing.account_login = target_installation["account"]["login"]
            existing.account_type = target_installation["account"]["type"]
            existing.suspended_at = target_installation.get("suspended_at")
            session.add(existing)
        else:
            # Create new installation record
            new_installation = GitHubInstallations(
                installation_id=installation_id,
                account_id=target_installation["account"]["id"],
                account_login=target_installation["account"]["login"],
                account_type=target_installation["account"]["type"],
                suspended_at=target_installation.get("suspended_at")
            )
            session.add(new_installation)
        
        session.commit()
        return {"message": "Installation synced successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync installation: {str(e)}"
        )


@router.get("/installations/{installation_id}/repositories")
async def get_installation_repos(installation_id: int):
    """Get repositories accessible to a GitHub App installation"""
    try:
        repos = await github_app.get_installation_repos(installation_id)
        return {"repositories": repos}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch installation repositories: {str(e)}"
        )


@router.post("/runners/{installation_id}/{owner}/{repo}/registration-token")
async def get_runner_registration_token(
    installation_id: int,
    owner: str,
    repo: str,
    request: Request,
    session_db: Session = Depends(get_session)
):
    """Get runner registration token for a repository"""
    user_id = get_current_user_id(request, session_db)
    try:
        token = await runner_manager.get_runner_registration_token(
            installation_id, owner, repo
        )
        return {"token": token}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get runner registration token: {str(e)}"
        )


@router.post("/runners/{installation_id}/{owner}/{repo}/removal-token")
async def get_runner_removal_token(
    installation_id: int,
    owner: str,
    repo: str,
    request: Request,
    session_db: Session = Depends(get_session)
):
    """Get runner removal token for a repository"""
    user_id = get_current_user_id(request, session_db)
    try:
        token = await runner_manager.get_runner_removal_token(
            installation_id, owner, repo
        )
        return {"token": token}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get runner removal token: {str(e)}"
        )


@router.get("/runners/{installation_id}/{owner}/{repo}")
async def list_repo_runners(
    installation_id: int,
    owner: str,
    repo: str,
    request: Request,
    session_db: Session = Depends(get_session)
):
    """List all runners for a repository"""
    user_id = get_current_user_id(request, session_db)
    try:
        runners = await runner_manager.list_runners(installation_id, owner, repo)
        return {"runners": runners}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list runners: {str(e)}"
        )


@router.delete("/runners/{installation_id}/{owner}/{repo}/{runner_id}")
async def remove_runner(
    installation_id: int,
    owner: str,
    repo: str,
    runner_id: int,
    request: Request,
    session_db: Session = Depends(get_session)
):
    """Remove a specific runner from a repository"""
    user_id = get_current_user_id(request, session_db)
    try:
        success = await runner_manager.remove_runner(
            installation_id, owner, repo, runner_id
        )
        if success:
            return {"message": "Runner removed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove runner"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove runner: {str(e)}"
        )


@router.get("/installations/db")
async def list_db_installations(session: Session = Depends(get_session)):
    """List GitHub App installations stored in database"""
    statement = select(GitHubInstallations)
    installations = session.exec(statement).all()
    return {"installations": installations}