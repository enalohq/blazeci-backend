"""
GitHub App Authentication Module
Handles GitHub App JWT generation and installation token management
"""
import time
import jwt
import httpx
from typing import Optional, Dict, Any
from .config import settings


class GitHubApp:
    """GitHub App authentication and API client"""
    
    def __init__(self):
        self.app_id = settings.GITHUB_APP_ID
        # Priority order: 1) Secrets Manager, 2) File path, 3) Environment variable
        self.private_key = self._get_private_key()
    
    def _get_private_key(self) -> str:
        """Get private key from various sources in priority order"""
        # 1. Try AWS Secrets Manager first (best for production)
        if hasattr(settings, 'GITHUB_APP_PRIVATE_KEY_SECRET_NAME') and settings.GITHUB_APP_PRIVATE_KEY_SECRET_NAME:
            try:
                import boto3
                import json
                secrets_client = boto3.client('secretsmanager', region_name=settings.AWS_REGION)
                response = secrets_client.get_secret_value(SecretId=settings.GITHUB_APP_PRIVATE_KEY_SECRET_NAME)
                # Secret can be stored as plain text or JSON
                if response['SecretString'].startswith('{'):
                    secret_data = json.loads(response['SecretString'])
                    return secret_data.get('private_key', '')
                else:
                    return response['SecretString']  # Plain text
            except Exception as e:
                print(f"⚠️  Could not fetch from Secrets Manager: {e}")
        
        # 2. Try file path (good for local development)
        if hasattr(settings, 'GITHUB_APP_PRIVATE_KEY_PATH') and settings.GITHUB_APP_PRIVATE_KEY_PATH:
            try:
                from pathlib import Path
                key_path = Path(__file__).parent.parent / settings.GITHUB_APP_PRIVATE_KEY_PATH
                with open(key_path, 'r') as f:
                    return f.read()
            except (FileNotFoundError, IOError) as e:
                print(f"⚠️  Could not read private key file: {e}")
        
        # 3. Fallback to environment variable
        return settings.GITHUB_APP_PRIVATE_KEY
        
    def generate_jwt(self) -> str:
        """Generate JWT for GitHub App authentication"""
        try:
            # Debug the private key format
            print(f"🔑 DEBUG: Private key length: {len(self.private_key)}")
            print(f"🔑 DEBUG: Private key starts with: {self.private_key[:50]}...")
            print(f"🔑 DEBUG: Private key ends with: ...{self.private_key[-50:]}")
            
            # Ensure proper PEM formatting for Lambda environment
            private_key = self.private_key
            if not private_key.startswith('-----BEGIN'):
                # If the key doesn't have proper headers, it might be base64 or escaped
                if '\\n' in private_key:
                    # Replace escaped newlines with actual newlines
                    private_key = private_key.replace('\\n', '\n')
                    print(f"🔑 DEBUG: Fixed escaped newlines in private key")
            
            # Convert RSA PRIVATE KEY format to PRIVATE KEY format if needed
            if 'BEGIN RSA PRIVATE KEY' in private_key:
                print(f"🔑 DEBUG: Converting RSA PRIVATE KEY to PRIVATE KEY format")
                
                # First, ensure proper PEM formatting with newlines
                # The key might be stored as a single line in environment variables
                if '\n' not in private_key:
                    # Reconstruct proper PEM format
                    lines = []
                    header = '-----BEGIN RSA PRIVATE KEY-----'
                    footer = '-----END RSA PRIVATE KEY-----'
                    
                    # Extract the base64 content between headers
                    content = private_key.replace(header, '').replace(footer, '').replace(' ', '')
                    
                    # Add header
                    lines.append(header)
                    
                    # Split base64 content into 64-character lines
                    for i in range(0, len(content), 64):
                        lines.append(content[i:i+64])
                    
                    # Add footer
                    lines.append(footer)
                    
                    private_key = '\n'.join(lines)
                    print(f"🔑 DEBUG: Reconstructed PEM format with proper newlines")
                
                # Load the RSA private key and convert to PKCS#8 format
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.serialization import load_pem_private_key
                
                try:
                    # Load the RSA private key
                    rsa_key = load_pem_private_key(private_key.encode(), password=None)
                    
                    # Convert to PKCS#8 format (what PyJWT expects)
                    private_key = rsa_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ).decode()
                    
                    print(f"🔑 DEBUG: Converted key starts with: {private_key[:50]}...")
                except Exception as e:
                    print(f"🔑 DEBUG: Error loading private key: {e}")
                    print(f"🔑 DEBUG: Key format: {repr(private_key[:100])}")
                    raise
            
            print(f"🔑 DEBUG: Final private key starts with: {private_key[:50]}...")
            
            import datetime
            
            # Get current UTC time to ensure correct timestamps
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            now_timestamp = int(now_utc.timestamp())
            
            # Use actual system time - GitHub accepts current timestamps
            print(f"🔑 DEBUG: Using system timestamp: {now_timestamp}")
            
            payload = {
                "iat": now_timestamp - 60,  # Issued at (60 seconds ago to account for clock skew)
                "exp": now_timestamp + (10 * 60),  # Expires in 10 minutes
                "iss": self.app_id  # Issuer is the GitHub App ID
            }
            
            print(f"🔑 DEBUG: UTC time: {now_utc}")
            print(f"🔑 DEBUG: Corrected timestamp: {now_timestamp}")
            print(f"🔑 DEBUG: JWT payload: {payload}")
            
            # Basic timestamp sanity check (not too restrictive)
            min_timestamp = 1577836800  # 2020-01-01 (reasonable minimum)
            max_timestamp = 2147483647  # 2038-01-01 (Unix timestamp max)
            
            if payload["iat"] < min_timestamp or payload["iat"] > max_timestamp:
                print(f"🔑 ERROR: Invalid timestamp range. iat={payload['iat']}")
                raise ValueError(f"Invalid JWT timestamp: {payload['iat']}")
                
            print(f"🔑 DEBUG: Valid timestamp: {payload['iat']}")
            
            return jwt.encode(payload, private_key, algorithm="RS256")
        except Exception as e:
            print(f"🔑 DEBUG: JWT encoding error: {e}")
            raise
    
    async def get_installation_token(self, installation_id: int) -> str:
        """Get installation access token for a specific installation"""
        jwt_token = self.generate_jwt()
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            return data["token"]
    
    async def get_installations(self) -> list[dict]:
        """Get all installations of this GitHub App"""
        jwt_token = self.generate_jwt()
        
        print(f"🔑 DEBUG: Generated JWT token (first 50 chars): {jwt_token[:50]}...")
        print(f"🔑 DEBUG: App ID being used: {self.app_id}")
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            print(f"🔑 DEBUG: Making request to GitHub API with headers: {headers}")
            
            resp = await client.get("https://api.github.com/app/installations", headers=headers)
            
            print(f"🔑 DEBUG: GitHub API response status: {resp.status_code}")
            print(f"🔑 DEBUG: GitHub API response headers: {dict(resp.headers)}")
            
            if resp.status_code != 200:
                print(f"🔑 DEBUG: GitHub API error response: {resp.text}")
            
            resp.raise_for_status()
            return resp.json()
    
    async def get_installation_repos(self, installation_id: int) -> list[dict]:
        """Get repositories accessible to a specific installation"""
        installation_token = await self.get_installation_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/installation/repositories"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            return data.get("repositories", [])


class GitHubRunnerManager:
    """Manages GitHub self-hosted runners using GitHub App authentication"""
    
    def __init__(self, github_app: GitHubApp):
        self.github_app = github_app
    
    async def get_runner_registration_token(self, installation_id: int, owner: str, repo: str) -> str:
        """Get runner registration token for a repository"""
        installation_token = await self.github_app.get_installation_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token"
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            return data["token"]
    
    async def get_runner_removal_token(self, installation_id: int, owner: str, repo: str) -> str:
        """Get runner removal token for a repository"""
        installation_token = await self.github_app.get_installation_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners/remove-token"
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            return data["token"]
    
    async def list_runners(self, installation_id: int, owner: str, repo: str) -> list[dict]:
        """List all runners for a repository"""
        installation_token = await self.github_app.get_installation_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            return data.get("runners", [])
    
    async def remove_runner(self, installation_id: int, owner: str, repo: str, runner_id: int) -> bool:
        """Remove a specific runner from a repository"""
        installation_token = await self.github_app.get_installation_token(installation_id)
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners/{runner_id}"
            resp = await client.delete(url, headers=headers)
            
            return resp.status_code == 204


# Initialize GitHub App instance
github_app = GitHubApp()
runner_manager = GitHubRunnerManager(github_app)


# Enhanced GitHub API functions using GitHub App authentication
async def create_repo_webhook_with_app(installation_id: int, owner_login: str, repo_name: str, 
                                     callback_url: str, secret: str) -> dict:
    """Create webhook using GitHub App authentication"""
    installation_token = await github_app.get_installation_token(installation_id)
    
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        payload = {
            "name": "web",
            "active": True,
            "events": ["push", "issues", "issue_comment", "pull_request", "workflow_job", "workflow_run"],
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
            return {"ok": False, "status": resp.status_code, "error": resp.text}
        
        data = resp.json()
        data["ok"] = True
        return data


async def get_repo_with_app(installation_id: int, owner_login: str, repo_name: str) -> dict:
    """Get repository information using GitHub App authentication"""
    installation_token = await github_app.get_installation_token(installation_id)
    
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {installation_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        url = f"https://api.github.com/repos/{owner_login}/{repo_name}"
        resp = await client.get(url, headers=headers)
        return {"status": resp.status_code, "body": resp.json(), "ok": resp.status_code == 200}