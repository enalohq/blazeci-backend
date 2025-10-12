import httpx
from .config import settings


async def exchange_code_for_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        headers = {"Accept": "application/json"}
        payload = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": settings.github_redirect_uri,
        }
        resp = await client.post("https://github.com/login/oauth/access_token", data=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"Failed to obtain access token: {data}")
        return data["access_token"]


async def get_authenticated_user(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        resp = await client.get("https://api.github.com/user", headers=headers)
        resp.raise_for_status()
        return resp.json()


async def list_user_repos(token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        # Default: public and private, affiliations of the authenticated user
        resp = await client.get("https://api.github.com/user/repos?per_page=100", headers=headers)
        resp.raise_for_status()
        return resp.json()

async def list_user_orgs(token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        url = "https://api.github.com/user/orgs?per_page=100"
        print(f"DEBUG: Making request to {url}")
        resp = await client.get(url, headers=headers)
        print(f"DEBUG: Response status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"DEBUG: Response body: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        print(f"DEBUG: Organizations response: {data}")
        return data

async def list_org_repos(token: str, org_login: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/orgs/{org_login}/repos?per_page=100&type=all"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def create_repo_webhook(token: str, owner_login: str, repo_name: str, callback_url: str, secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "name": "web",
            "active": True,
            "events": ["push", "issues", "issue_comment", "pull_request"],
            "config": {
                "url": callback_url,
                "content_type": "json",
                "insecure_ssl": "0",
                "secret": secret,
            },
        }
        url = f"https://api.github.com/repos/{owner_login}/{repo_name}/hooks"
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # include response details for debugging
            return {"ok": False, "status": resp.status_code, "error": resp.text}
        data = resp.json()
        data["ok"] = True
        return data


async def list_repo_webhooks(token: str, owner_login: str, repo_name: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"https://api.github.com/repos/{owner_login}/{repo_name}/hooks"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def update_repo_webhook(token: str, owner_login: str, repo_name: str, hook_id: int, callback_url: str, secret: str) -> dict:
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "active": True,
            "config": {
                "url": callback_url,
                "content_type": "json",
                "insecure_ssl": "0",
                "secret": secret,
            },
        }
        url = f"https://api.github.com/repos/{owner_login}/{repo_name}/hooks/{hook_id}"
        resp = await client.patch(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        data["ok"] = True
        return data


async def get_repo(token: str, owner_login: str, repo_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{owner_login}/{repo_name}"
        resp = await client.get(url, headers=headers)
        return {"status": resp.status_code, "body": resp.json(), "ok": resp.status_code == 200}


async def get_oauth_scopes(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        resp = await client.get("https://api.github.com/user", headers=headers)
        scopes = resp.headers.get("x-oauth-scopes", "")
        return {"status": resp.status_code, "scopes": [s.strip() for s in scopes.split(",") if s.strip()]}


