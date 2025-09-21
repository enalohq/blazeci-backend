from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..config import settings
from ..db import get_session
from ..models import UserToken
from datetime import datetime
from ..security import encrypt_token, create_session_cookie, read_session_cookie
from ..github import exchange_code_for_token, get_authenticated_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/")
def hello():
    print("API RUNNING FINE")
    return {"message": "Auth API is running"}

@router.get("/login")
def login():
    print(f"DEBUG: Initiating OAuth login, redirecting to GitHub...")
    print(settings.FRONTEND_ORIGIN)
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Missing GITHUB_CLIENT_ID")
    scopes = ["repo", "admin:repo_hook", "read:org"]
    scope_param = "+".join(scopes)
    url = (
        f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_OAUTH_REDIRECT_URI}&scope={scope_param}"
    )
    return RedirectResponse(url)


@router.get("/callback")
async def callback(code: str, response: Response, session: Session = Depends(get_session)):
    try:
        print(f"DEBUG: Starting OAuth callback with code: {code[:10]}...")
        print(f"DEBUG: Client ID set: {bool(settings.GITHUB_CLIENT_ID)}")
        print(f"DEBUG: Client Secret set: {bool(settings.GITHUB_CLIENT_SECRET)}")
        print(f"DEBUG: Redirect URI: {settings.GITHUB_OAUTH_REDIRECT_URI}")
        
        token = await exchange_code_for_token(code)
        print(f"DEBUG: Token obtained successfully")
        
        user = await get_authenticated_user(token)
        print(f"DEBUG: User info obtained: {user.get('login')} (ID: {user.get('id')})")
        
        github_user_id = str(user["id"])  # string for portability
        github_login = user.get("login", "")

        # upsert user token
        existing = session.exec(select(UserToken).where(UserToken.github_user_id == github_user_id)).first()
        if existing:
            print(f"DEBUG: Updating existing user {github_login}")
            existing.github_login = github_login
            existing.encrypted_token = encrypt_token(token)
            existing.updated_at = datetime.utcnow()
        else:
            print(f"DEBUG: Creating new user {github_login}")
            existing = UserToken(github_user_id=github_user_id, github_login=github_login, encrypted_token=encrypt_token(token))
            session.add(existing)
        session.commit()
        session.refresh(existing)
        print(f"DEBUG: User saved to DB with ID: {existing.id}")

        cookie = create_session_cookie(existing.id)
        print(f"DEBUG: Created session cookie: {cookie[:20]}...")
        print(f"DEBUG: Cookie length: {len(cookie)}")
        response = RedirectResponse(url=f"{settings.FRONTEND_ORIGIN}/repos")
        
        # Set the session cookie
        response.set_cookie(
            key="session",
            value=cookie,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=86400,  # 24 hours
        )
        print(f"DEBUG: Cookie set in response headers")
        print(f"DEBUG: Response headers: {dict(response.headers)}")
        print(f"DEBUG: Redirecting to {settings.FRONTEND_ORIGIN}/repos with new session for user {github_login} (DB ID: {existing.id})")
        return response
        
    except Exception as e:
        print(f"ERROR in OAuth callback: {e}")
        # Redirect to login page with error
        return RedirectResponse(url=f"{settings.FRONTEND_ORIGIN}/login?error=oauth_failed")


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie to log out the user"""
    response = RedirectResponse(url=f"{settings.FRONTEND_ORIGIN}/login")
    response.delete_cookie(
        key="session",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/debug/session")
def debug_session(request: Request, session_db: Session = Depends(get_session)):
    """Debug endpoint to check current session state"""
    cookie = request.cookies.get("session")
    if not cookie:
        return {"error": "No session cookie found"}
    
    user_id = read_session_cookie(cookie)
    if not user_id:
        return {"error": "Invalid session cookie"}
    
    user = session_db.get(UserToken, user_id)
    if not user:
        return {"error": f"User with ID {user_id} not found in database"}
    
    return {
        "session_cookie": cookie[:20] + "...",  # Truncated for security
        "user_id": user_id,
        "github_user_id": user.github_user_id,
        "github_login": user.github_login,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat()
    }


