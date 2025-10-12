import os
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..config import settings
from ..db import get_session
from ..models import Users, UserTokens
from datetime import datetime
from ..security import encrypt_token, create_session_cookie, read_session_cookie
from ..github import exchange_code_for_token, get_authenticated_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/")
def hello():
    print("API RUNNING FINE")
    return {"message": "Auth API is running"}

@router.get("/login")
def login(request: Request):
    print(f"DEBUG: Initiating OAuth login, redirecting to GitHub...")
    print(f"DEBUG: FRONTEND_ORIGIN = {settings.FRONTEND_ORIGIN}")
    print(f"DEBUG: BACKEND_ORIGIN = {settings.BACKEND_ORIGIN}")
    print(f"DEBUG: GITHUB_OAUTH_REDIRECT_URI = {settings.GITHUB_OAUTH_REDIRECT_URI}")
    
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Missing GITHUB_CLIENT_ID")
    
    # Generate a secure state parameter for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    
    scopes = ["repo", "user:email", "admin:repo_hook"]
    scope_param = "%20".join(scopes)  # URL encode spaces
    
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_OAUTH_REDIRECT_URI}"
        f"&scope={scope_param}"
        f"&state={state}"
        f"&allow_signup=true"
    )
    
    print(f"DEBUG: Final OAuth URL = {url}")
    
    # Check if this is a Lambda/API Gateway environment by looking for AWS Lambda headers
    user_agent = request.headers.get("user-agent", "")
    if "Amazon CloudFront" in request.headers.get("via", "") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        # In Lambda environment, return JSON response for frontend to handle redirect
        return {
            "login_url": url,
            "state": state,
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scopes": scopes,
            "message": "Redirect user to login_url for GitHub OAuth authentication"
        }
    else:
        # In local development, use direct redirect
        return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, code: str = None, response: Response = None, session: Session = Depends(get_session)):
    if not code:
        return {"error": "Missing authorization code", "message": "This endpoint should be called by GitHub OAuth. Use /auth/login to start the OAuth flow."}
    try:
        print(f"DEBUG: Starting OAuth callback with code: {code[:10]}...")
        print(f"DEBUG: Client ID set: {bool(settings.GITHUB_CLIENT_ID)}")
        print(f"DEBUG: Client Secret set: {bool(settings.GITHUB_CLIENT_SECRET)}")
        print(f"DEBUG: Redirect URI: {settings.GITHUB_OAUTH_REDIRECT_URI}")
        
        token = await exchange_code_for_token(code)
        print(f"DEBUG: Token obtained successfully")
        
        user = await get_authenticated_user(token)
        print(f"DEBUG: User info obtained: {user.get('login')} (ID: {user.get('id')})")
        
        github_user_id = str(user["id"])  # Convert to string to match VARCHAR database column
        github_login = user.get("login", "")
        email = user.get("email")
        name = user.get("name")
        avatar_url = user.get("avatar_url")
        
        print(f"DEBUG: Email from GitHub: {email}")  # Debug email

        # Upsert user (github_user_id is stored as VARCHAR in database)
        existing_user = session.exec(select(Users).where(Users.github_user_id == github_user_id)).first()
        if existing_user:
            print(f"DEBUG: Updating existing user {github_login}")
            existing_user.github_login = github_login
            existing_user.email = email
            existing_user.name = name
            existing_user.avatar_url = avatar_url
            existing_user.updated_at = datetime.utcnow()
        else:
            print(f"DEBUG: Creating new user {github_login}")
            existing_user = Users(
                github_user_id=github_user_id,
                github_login=github_login,
                email=email,
                name=name,
                avatar_url=avatar_url
            )
            session.add(existing_user)
        
        session.commit()
        session.refresh(existing_user)
        
        # Upsert user token (separate table)
        existing_token = session.exec(select(UserTokens).where(UserTokens.user_id == existing_user.id)).first()
        if existing_token:
            existing_token.encrypted_token = encrypt_token(token)
            existing_token.updated_at = datetime.utcnow()
        else:
            existing_token = UserTokens(
                user_id=existing_user.id,
                encrypted_token=encrypt_token(token)
            )
            session.add(existing_token)
        
        session.commit()
        session.commit()
        session.refresh(existing_token)
        print(f"DEBUG: User saved to DB with ID: {existing_user.id}")

        cookie = create_session_cookie(existing_user.id)
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
        print(f"DEBUG: Redirecting to {settings.FRONTEND_ORIGIN}/repos with new session for user {github_login} (DB ID: {existing_user.id})")
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
    
    user = session_db.get(Users, user_id)
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


