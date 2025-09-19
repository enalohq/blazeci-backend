import hmac
import hashlib
import secrets
import boto3
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ..config import settings
from ..db import get_session
from ..models import UserToken, Repo, Webhook, UserRepo
from ..security import decrypt_token
from ..github import create_repo_webhook, get_repo, get_oauth_scopes, list_repo_webhooks, update_repo_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)


class RegisterWebhookPayload(BaseModel):
    repo_id: int


@router.post("/register")
async def register_webhook(payload: RegisterWebhookPayload, request: Request, session: Session = Depends(get_session)):
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Resolve user and token
    from ..security import read_session_cookie

    user_id = read_session_cookie(cookie)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")
    repo_id = int(payload.repo_id)
    repo = session.get(Repo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
    
    # Check if user has access to this repo
    user_repo = session.exec(
        select(UserRepo).where(UserRepo.user_id == user_id, UserRepo.repo_id == repo_id)
    ).first()
    if not user_repo:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = session.get(UserToken, user_id)
    token = decrypt_token(user.encrypted_token)

    # Diagnostics: verify access and scopes
    repo_info = await get_repo(token, repo.owner_login, repo.name)
    scopes_info = await get_oauth_scopes(token)
    if not repo_info.get("ok"):
        raise HTTPException(status_code=404, detail={"reason": "repo_not_found_or_no_access", "repo_status": repo_info.get("status"), "body": repo_info.get("body")})
    if "admin:repo_hook" not in scopes_info.get("scopes", []) and "repo" not in scopes_info.get("scopes", []):
        raise HTTPException(status_code=403, detail={"reason": "insufficient_scopes", "scopes": scopes_info.get("scopes")})

    # Create secret and webhook
    secret_value = secrets.token_hex(16)
    callback_url = settings.webhook_url  # Use public URL instead of localhost
    # Idempotent: reuse existing hook with same URL if present; otherwise create
    existing_hooks = await list_repo_webhooks(token, repo.owner_login, repo.name)
    matched = next((h for h in existing_hooks if (h.get("config") or {}).get("url") == callback_url), None)
    if matched:
        wh = await update_repo_webhook(token, repo.owner_login, repo.name, matched.get("id"), callback_url, secret_value)
    else:
        wh = await create_repo_webhook(token, repo.owner_login, repo.name, callback_url, secret_value)
    if not wh.get("ok"):
        raise HTTPException(status_code=502, detail=f"GitHub webhook create failed: {wh.get('status')} {wh.get('error')}")


    # Persist webhook info
    # Upsert local record for the webhook
    existing_local = session.exec(select(Webhook).where(Webhook.repo_id == repo.id)).first()
    if existing_local:
        existing_local.webhook_id = wh.get("id")
        existing_local.secret = secret_value
        existing_local.url = wh.get("config", {}).get("url")
        existing_local.active = True
        webhook = existing_local
    else:
        webhook = Webhook(repo_id=repo.id, webhook_id=wh.get("id"), secret=secret_value, url=wh.get("config", {}).get("url"), active=True)
    session.add(webhook)
    session.commit()
    return {"ok": True, "webhook_id": webhook.webhook_id}


@router.post("/github")
async def receive_github(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    session: Session = Depends(get_session),
):
    body = await request.body()
    # print(f"Received GitHub event: {x_github_event}")
    # print(body)
    # Find matching secret: naive lookup by iterating known secrets; in prod: map per repo
    secrets_list = session.exec(select(Webhook).where(Webhook.active == True)).all()

    verified = False
    matched_webhook: Webhook | None = None
    for wh in secrets_list:
        if wh.secret and verify_signature(wh.secret, body, x_hub_signature_256 or ""):
            verified = True
            matched_webhook = wh
            break
    if not verified:
        print("Webhook signature verification failed for event:", x_github_event)
        raise HTTPException(status_code=401, detail="Invalid signature")
    # Parse payload
    payload = await request.json()
    # On push events, ensure an ECS service is running (create or update)
    if x_github_event == "push" and matched_webhook is not None:
        try:
            print("Received push event. Preparing to launch runner task for repo id:", matched_webhook.repo_id)
            ecs = boto3.client("ecs", region_name=settings.aws_region)
            logs = boto3.client("logs", region_name=settings.aws_region)
            # Best effort: ensure log group exists
            try:
                logs.create_log_group(logGroupName="/ecs/github-runner")
                print("Created CloudWatch Logs group /ecs/github-runner")
            except Exception as e:
                # Ignore AlreadyExists or lack of permissions; ECS may still log if group pre-created
                print("Log group creation attempt result:", str(e))
            subnets = [s for s in (settings.ecs_subnet_ids or "").split(",") if s]
            security_groups = [s for s in (settings.ecs_security_group_ids or "").split(",") if s]

            # Resolve repo details used for the runner
            repo = session.get(Repo, matched_webhook.repo_id)
            if not repo:
                raise Exception("Matched webhook repo not found")

            # Pick a user associated with this repo to supply a GitHub token
            user_repo = session.exec(select(UserRepo).where(UserRepo.repo_id == repo.id)).first()
            if not user_repo:
                raise Exception("No user associated with repo to provide GH token")
            user = session.get(UserToken, user_repo.user_id)
            if not user:
                raise Exception("User token not found for repo association")
            gh_token = decrypt_token(user.encrypted_token)

            awsvpc_conf: Dict[str, object] = {
                "subnets": subnets,
                "assignPublicIp": settings.ecs_assign_public_ip,
            }
            if security_groups:
                awsvpc_conf["securityGroups"] = security_groups

            # Prefer configured runner PAT if provided; fall back to user's token
            effective_token = settings.runner_pat or gh_token
            env_vars = [
                {"name": "GH_OWNER", "value": repo.owner_login},
                {"name": "GH_REPO", "value": repo.name},
                {"name": "GH_TOKEN", "value": effective_token},
                {"name": "RUNNER_LABELS", "value": settings.runner_labels},
            ]

            response = ecs.run_task(
                cluster=settings.ecs_cluster,
                launchType="FARGATE",
                taskDefinition=settings.ecs_task_definition,
                networkConfiguration={
                    "awsvpcConfiguration": awsvpc_conf,
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": settings.ecs_container_name,
                            "environment": env_vars,
                        }
                    ]
                },
            )
            print("ECS run_task response:", response)
        except Exception as e:
            # Don't fail the webhook; log and continue
            print(f"ECS service ensure error: {e}")

    return {"ok": True, "event": x_github_event}


