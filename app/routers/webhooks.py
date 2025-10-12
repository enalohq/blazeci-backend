import hmac
import hashlib
import secrets
import boto3
from typing import Dict
from datetime import datetime, timedelta
import time
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..config import settings
from ..db import get_session
from ..models import Users, UserTokens, Repos, Webhooks, UserRepos, GitHubInstallations
from ..security import decrypt_token
from ..github import create_repo_webhook, get_repo, get_oauth_scopes, list_repo_webhooks, update_repo_webhook
from ..github_app import GitHubApp

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Global deduplication cache to prevent race conditions
recent_task_requests = {}  # {repo_id: timestamp}


async def handle_github_app_event(event_type: str, payload: dict, session: Session) -> dict:
    """Handle GitHub App installation and repository events"""
    try:
        if event_type == "installation":
            action = payload.get("action")
            installation = payload.get("installation", {})
            
            if action == "created":
                # New installation
                print(f"🆕 GitHub App installed: {installation.get('account', {}).get('login')}")
                
                # Save installation to database
                new_installation = GitHubInstallations(
                    installation_id=installation.get("id"),
                    account_id=installation.get("account", {}).get("id"),
                    account_login=installation.get("account", {}).get("login"),
                    account_type=installation.get("account", {}).get("type"),
                    permissions=str(installation.get("permissions", {})),
                    events=str(installation.get("events", []))
                )
                session.add(new_installation)
                session.commit()
                
            elif action == "deleted":
                # Installation removed
                print(f"🗑️  GitHub App uninstalled: {installation.get('account', {}).get('login')}")
                
                # Remove from database
                stmt = select(GitHubInstallations).where(
                    GitHubInstallations.installation_id == installation.get("id")
                )
                existing = session.exec(stmt).first()
                if existing:
                    session.delete(existing)
                    session.commit()
            
        elif event_type == "installation_repositories":
            action = payload.get("action")
            installation = payload.get("installation", {})
            
            if action == "added":
                repos_added = payload.get("repositories_added", [])
                print(f"📁 Repositories added to installation: {len(repos_added)} repos")
                
            elif action == "removed":
                repos_removed = payload.get("repositories_removed", [])
                print(f"🗑️  Repositories removed from installation: {len(repos_removed)} repos")
        
        return {"ok": True, "event": event_type, "message": "GitHub App event processed"}
        
    except Exception as e:
        print(f"❌ Error handling GitHub App event: {e}")
        return {"ok": False, "event": event_type, "error": str(e)}


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)


class RegisterWebhookPayload(BaseModel):
    repo_id: int


@router.post("/register")
async def register_webhook(payload: RegisterWebhookPayload, request: Request, session: Session = Depends(get_session)):
    try:
        cookie = request.cookies.get("session")
        if not cookie:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Resolve user and token
        from ..security import read_session_cookie

        user_id = read_session_cookie(cookie)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid session")
        repo_id = int(payload.repo_id)
        repo = session.get(Repos, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")
        
        # Check if user has access to this repo
        user_repo = session.exec(
            select(UserRepos).where(UserRepos.user_id == user_id, UserRepos.github_repo_id == repo.github_repo_id)
        ).first()
        if not user_repo:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        user = session.get(Users, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Get user's token
        token_record = session.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
        if not token_record:
            raise HTTPException(status_code=401, detail="User token not found")
        token = decrypt_token(token_record.encrypted_token)

        # Check if webhook already exists for this repo
        existing_webhook = session.exec(
            select(Webhooks).where(Webhooks.repo_id == repo_id, Webhooks.active == True)
        ).first()
        
        if existing_webhook:
            return {"ok": True, "webhook_id": existing_webhook.webhook_id, "message": "Webhook already exists"}

        # Generate a secure webhook secret
        webhook_secret = secrets.token_urlsafe(32)
        
        # Create webhook URL
        webhook_url = f"{settings.BACKEND_ORIGIN}/webhooks/github"
        
        # Check if we're in local development (localhost)
        is_local_dev = "localhost" in webhook_url or "127.0.0.1" in webhook_url
        
        # Use GitHub App installation token if available, otherwise use user token
        github_app = GitHubApp()
        installation_id = None
        
        # Try to find GitHub App installation for this repo
        stmt = select(GitHubInstallations).where(
            GitHubInstallations.account_login == repo.owner_login
        )
        installation = session.exec(stmt).first()
        if installation:
            installation_id = installation.installation_id
        
        if installation_id:
            effective_token = await github_app.get_installation_token(installation_id)
            print(f"🔑 Using GitHub App installation token for {repo.owner_login}")
        else:
            effective_token = token
            print(f"🔑 Using user token for {repo.owner_login}")
            
        # Check token scopes for debugging
        try:
            scopes_info = await get_oauth_scopes(effective_token)
            print(f"📋 Token scopes: {scopes_info}")
        except Exception as e:
            print(f"⚠️  Could not check token scopes: {e}")
        
        # Handle local development vs production
        if is_local_dev:
            print(f"🏠 Local development detected - creating mock webhook")
            print(f"💡 For testing webhooks locally, use ngrok or deploy to a public URL")
            
            # Create a mock webhook ID for local development
            webhook_id = f"local-dev-webhook-{repo_id}-{int(time.time())}"
            
            # Store mock webhook in database for local testing
            new_webhook = Webhooks(
                repo_id=repo_id,
                webhook_id=webhook_id,
                secret=webhook_secret,
                url=webhook_url,
                active=True
            )
            session.add(new_webhook)
            session.commit()
            
            return {
                "ok": True, 
                "webhook_id": webhook_id, 
                "message": "Mock webhook created for local development. Use ngrok for real webhook testing."
            }
        
        # Production: Create actual webhook via GitHub API
        webhook_response = await create_repo_webhook(
            effective_token,
            repo.owner_login, 
            repo.name, 
            webhook_url,
            webhook_secret
        )
        
        if not webhook_response or "id" not in webhook_response:
            error_msg = "Failed to create webhook on GitHub"
            if webhook_response and "error" in webhook_response:
                error_msg += f": {webhook_response.get('error', 'Unknown error')}"
            print(f"❌ Webhook creation failed: {webhook_response}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        webhook_id = webhook_response["id"]
        
        # Store webhook in database
        new_webhook = Webhooks(
            repo_id=repo_id,
            webhook_id=str(webhook_id),
            secret=webhook_secret,
            url=webhook_url,
            active=True
        )
        session.add(new_webhook)
        session.commit()
        
        return {
            "ok": True, 
            "webhook_id": str(webhook_id), 
            "message": "Webhook created successfully"
        }
        
    except Exception as e:
        print(f"Webhook registration error: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook registration failed: {str(e)}")


@router.post("/github")
async def receive_github(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    session: Session = Depends(get_session),
):
    body = await request.body()
    print(f"=== WEBHOOK: {x_github_event} ===")
    print(f"Body Length: {len(body)}")
    # Find matching secret: naive lookup by iterating known secrets; in prod: map per repo
    secrets_list = session.exec(select(Webhooks).where(Webhooks.active == True)).all()

    verified = False
    matched_webhook: Webhooks | None = None
    for wh in secrets_list:
        if wh.secret and verify_signature(wh.secret, body, x_hub_signature_256 or ""):
            verified = True
            matched_webhook = wh
            break
    if not verified:
        print(f"❌ Webhook signature verification failed: {x_github_event}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    # Parse payload
    payload = await request.json()
    print(f"✅ Verified {x_github_event} for repo {matched_webhook.repo_id if matched_webhook else 'unknown'}")
    
    # Handle ping events (sent when webhook is created/updated) - don't launch runners
    if x_github_event == "ping":
        print(f"🏓 Ping event - webhook setup confirmed")
        return {"ok": True, "event": x_github_event, "message": "Ping received"}
    
    # Handle GitHub App installation events
    if x_github_event in ["installation", "installation_repositories"]:
        print(f"📱 GitHub App {x_github_event} event received")
        return await handle_github_app_event(x_github_event, payload, session)
    
    # Only launch runners for specific actionable events - PRIORITIZE workflow_job over others
    if x_github_event in ["push","workflow_run","workflow_job"] and matched_webhook is not None:
        # Additional filtering: only on push events with actual commits
        if x_github_event == "push":
            commits = payload.get("commits", [])
            if not commits:
                print(f"📝 Push without commits - skipping")
                return {"ok": True, "event": x_github_event, "message": "No commits to process"}
        
        action = payload.get('action', 'N/A')
        print(f"🔄 Processing {x_github_event}({action})")
        
        # Event filtering by priority
        if x_github_event == "workflow_job":
            action = payload.get("action")
            if action != "queued":
                print(f"⏭️  Ignoring workflow_job({action}) - only 'queued' triggers runners")
                return {"ok": True, "event": x_github_event, "message": f"Ignored action: {action}"}
        
        elif x_github_event == "workflow_run":
            action = payload.get("action")
            if action not in ["requested"]:
                print(f"⏭️  Ignoring workflow_run({action}) - only 'requested' triggers runners")
                return {"ok": True, "event": x_github_event, "message": f"Ignored action: {action}"}
        
        elif x_github_event == "push":
            print(f"📤 Push event - creating runner")
        
        print(f"🔍 Checking existing runners...")
        
        # CRITICAL: Check for recent task creation requests to prevent race conditions
        repo_id = matched_webhook.repo_id
        current_time = time.time()
        
        # Clean up old entries (older than 60 seconds)
        global recent_task_requests
        recent_task_requests = {k: v for k, v in recent_task_requests.items() if current_time - v < 60}
        
        # Check if we recently created a task for this repo (within last 15 seconds)
        if repo_id in recent_task_requests:
            time_since_last = current_time - recent_task_requests[repo_id]
            if time_since_last < 15:  # 15 second cooldown
                print(f"⏸️  Cooldown active - task created {time_since_last:.1f}s ago, skipping duplicate")
                return {"ok": True, "event": x_github_event, "message": f"Recent task created {time_since_last:.1f}s ago"}
        
        try:
            ecs = boto3.client("ecs", region_name=settings.AWS_REGION)
            
            # Check for existing running tasks for this repository
            existing_tasks = ecs.list_tasks(
                cluster=settings.ECS_CLUSTER,
                family=settings.ECS_TASK_DEFINITION,
                desiredStatus='RUNNING'
            )
            
            running_task_count = len(existing_tasks.get('taskArns', []))
            
            # Also check for recently started tasks (PENDING/PROVISIONING)
            pending_tasks = ecs.list_tasks(
                cluster=settings.ECS_CLUSTER,
                family=settings.ECS_TASK_DEFINITION,
                desiredStatus='PENDING'
            )
            pending_task_count = len(pending_tasks.get('taskArns', []))
            total_active_tasks = running_task_count + pending_task_count
            
            print(f"📊 Active tasks: {total_active_tasks} (running: {running_task_count}, pending: {pending_task_count})")
            
            # CRITICAL: If we already have active tasks, be very selective about creating more
            if total_active_tasks >= 2:
                if x_github_event != "workflow_job":
                    print(f"🚫 Too many active tasks ({total_active_tasks}) - skipping {x_github_event}")
                    return {"ok": True, "event": x_github_event, "message": f"Too many active tasks ({total_active_tasks})"}
                else:
                    print(f"⚠️  Allowing workflow_job despite {total_active_tasks} active tasks")
            
            # Check queued jobs in GitHub to determine if we need more runners
            repo = session.get(Repos, matched_webhook.repo_id)
            if total_active_tasks > 0 and x_github_event == "workflow_job":
                try:
                    # Get GitHub App installation token for API calls
                    github_app = GitHubApp()
                    # Get installation ID from the payload (if available) or find it for this repo
                    installation_id = payload.get('installation', {}).get('id')
                    if not installation_id:
                        # Find installation for this repository
                        stmt = select(GitHubInstallations).where(
                            GitHubInstallations.account_login == repo.owner_login
                        )
                        installation = session.exec(stmt).first()
                        installation_id = installation.installation_id if installation else None
                    
                    if installation_id:
                        effective_token = await github_app.get_installation_token(installation_id)
                    else:
                        # Fallback to user token if no installation found
                        user_repo = session.exec(select(UserRepos).where(UserRepos.github_repo_id == repo.github_repo_id)).first()
                        user = session.get(Users, user_repo.user_id)
                        token_record = session.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
                        effective_token = decrypt_token(token_record.encrypted_token)
                    
                    # Check queued jobs
                    import httpx
                    headers = {"Authorization": f"Bearer {effective_token}", "Accept": "application/vnd.github+json"}
                    async with httpx.AsyncClient() as client:
                        jobs_resp = await client.get(
                            f"https://api.github.com/repos/{repo.owner_login}/{repo.name}/actions/runs/{payload.get('workflow_job', {}).get('run_id', 0)}/jobs",
                            headers=headers
                        )
                        
                        if jobs_resp.status_code == 200:
                            jobs_data = jobs_resp.json()
                            queued_jobs = [job for job in jobs_data.get('jobs', []) if job.get('status') == 'queued']
                            in_progress_jobs = [job for job in jobs_data.get('jobs', []) if job.get('status') == 'in_progress']
                            
                            # If we have enough active tasks for the workload, skip
                            if total_active_tasks >= len(queued_jobs):
                                print(f"✋ Sufficient runners ({total_active_tasks}) for queued jobs ({len(queued_jobs)})")
                                return {"ok": True, "event": x_github_event, "message": "Sufficient runners available"}
                                
                except Exception as e:
                    print(f"⚠️  Could not check GitHub job queue: {e}")
                    # If we can't check the queue, be conservative and don't launch if we have any active tasks
                    if total_active_tasks > 0:
                        print(f"🔒 Conservative mode - {total_active_tasks} active tasks, skipping")
                        return {"ok": True, "event": x_github_event, "message": "Active runners present"}
            
            # For other events, avoid duplicates if we have active tasks
            elif total_active_tasks > 0 and x_github_event in ["workflow_run", "push"]:
                print(f"⏭️  Skipping {x_github_event} - {total_active_tasks} active tasks handling workflow")
                return {"ok": True, "event": x_github_event, "message": "Active runners handling workflow"}
            
            trigger_info = f"{x_github_event}({payload.get('action', 'N/A')})"
            print(f"🚀 Creating runner task - {trigger_info}")
            
            # Record this task creation to prevent race conditions
            recent_task_requests[repo_id] = current_time
            

            
            logs = boto3.client("logs", region_name=settings.AWS_REGION)
            subnets = [s for s in (settings.ECS_SUBNET_IDS or "").split(",") if s]
            security_groups = [s for s in (settings.ECS_SECURITY_GROUP_IDS or "").split(",") if s]

            # Resolve repo details used for the runner
            repo = session.get(Repos, matched_webhook.repo_id)
            if not repo:
                raise Exception("Matched webhook repo not found")

            # Pick a user associated with this repo to supply a GitHub token
            user_repo = session.exec(select(UserRepos).where(UserRepos.github_repo_id == repo.github_repo_id)).first()
            if not user_repo:
                raise Exception("No user associated with repo to provide GH token")
            user = session.get(Users, user_repo.user_id)
            if not user:
                raise Exception("User not found for repo association")
            # Get user's token
            token_record = session.exec(select(UserTokens).where(UserTokens.user_id == user.id)).first()
            if not token_record:
                raise Exception("User token not found for repo association")
            gh_token = decrypt_token(token_record.encrypted_token)

            awsvpc_conf: Dict[str, object] = {
                "subnets": subnets,
                "assignPublicIp": settings.ECS_ASSIGN_PUBLIC_IP,
            }
            if security_groups:
                awsvpc_conf["securityGroups"] = security_groups

            # Use GitHub App installation token for runner registration
            github_app = GitHubApp()
            # Get installation ID from webhook payload or find it for this repo
            installation_id = payload.get('installation', {}).get('id')
            if not installation_id:
                # Find installation for this repository
                stmt = select(GitHubInstallations).where(
                    GitHubInstallations.account_login == repo.owner_login
                )
                installation = session.exec(stmt).first()
                installation_id = installation.installation_id if installation else None
            
            if installation_id:
                effective_token = await github_app.get_installation_token(installation_id)
            else:
                # Fallback to user token if no installation found
                effective_token = gh_token
            
            # Quick token validation
            try:
                import httpx
                headers = {"Authorization": f"Bearer {effective_token}", "Accept": "application/vnd.github+json"}
                async with httpx.AsyncClient() as client:
                    # Test runner registration permissions
                    reg_token_resp = await client.post(
                        f"https://api.github.com/repos/{repo.owner_login}/{repo.name}/actions/runners/registration-token",
                        headers=headers
                    )
                    
                    if reg_token_resp.status_code != 201:
                        print(f"❌ Token lacks runner permissions ({reg_token_resp.status_code}) - skipping")
                        return {"ok": True, "event": x_github_event, "message": "Skipped - insufficient permissions"}
                    
                    print(f"✅ Token validated for runner registration")
                        
            except Exception as e:
                print(f"⚠️  Token validation error: {e}")
                return {"ok": True, "event": x_github_event, "message": "Skipped - permission check error"}
                
            # Add context about what triggered this runner
            trigger_info = ""
            if x_github_event == "workflow_job":
                job_name = payload.get("workflow_job", {}).get("name", "unknown")
                trigger_info = f"job-{job_name}"
            elif x_github_event == "workflow_run":
                workflow_name = payload.get("workflow_run", {}).get("name", "unknown")
                trigger_info = f"workflow-{workflow_name}"
            elif x_github_event == "push":
                branch = payload.get("ref", "").replace("refs/heads/", "")
                trigger_info = f"push-{branch}"
            
            env_vars = [
                {"name": "GH_OWNER", "value": repo.owner_login},
                {"name": "GH_REPO", "value": repo.name},
                {"name": "GITHUB_TOKEN", "value": effective_token},
                {"name": "RUNNER_TRIGGER", "value": f"{x_github_event}-{trigger_info}"}
            ]

            response = ecs.run_task(
                cluster=settings.ECS_CLUSTER,
                taskDefinition=settings.ECS_TASK_DEFINITION,
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": awsvpc_conf,
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": settings.ECS_CONTAINER_NAME,
                            "environment": env_vars,
                        }
                    ]
                },
            )
            task_arn = response.get('tasks', [{}])[0].get('taskArn', 'unknown')
            task_id = task_arn.split('/')[-1] if task_arn != 'unknown' else 'unknown'
            print(f"✅ ECS task created: {task_id} for {repo.owner_login}/{repo.name}")
        except Exception as e:
            # Don't fail the webhook; log and continue
            print(f"❌ ECS task creation failed: {e}")

    return {"ok": True, "event": x_github_event}


