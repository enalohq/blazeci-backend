import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_backend_dir / ".env", override=False)


class Settings:
    # GitHub OAuth settings
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    
    # GitHub App settings
    GITHUB_APP_ID: str = os.getenv("GITHUB_APP_ID", "")
    GITHUB_APP_PRIVATE_KEY: str = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    GITHUB_APP_PRIVATE_KEY_PATH: str = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
    GITHUB_APP_PRIVATE_KEY_SECRET_NAME: str = os.getenv("GITHUB_APP_PRIVATE_KEY_SECRET_NAME", "")
    
    # Application URLs
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    
    # Backend origin for local development
    BACKEND_ORIGIN: str = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")
    
    # Construct OAuth redirect URI from backend origin
    @property
    def GITHUB_OAUTH_REDIRECT_URI(self) -> str:
        return f"{self.BACKEND_ORIGIN}/auth/callback"
    
    # Construct webhook URL from backend origin
    @property 
    def WEBHOOK_URL(self) -> str:
        return f"{self.BACKEND_ORIGIN}/webhooks/github"
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Security settings
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "dev-secret")
    
    # AWS / ECS settings for ephemeral runner
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    ECS_CLUSTER: str = os.getenv("ECS_CLUSTER", "ECS-ECR-STAGING-API")
    ECS_TASK_DEFINITION: str = os.getenv("ECS_TASK_DEFINITION", "github-runner-task")
    ECS_CONTAINER_NAME: str = os.getenv("ECS_CONTAINER_NAME", "github-runner")
    ECS_SUBNET_IDS: str = os.getenv("ECS_SUBNET_IDS", "subnet-0f00f5030e91c0b42,subnet-0d9d4d75b11eba35b,subnet-0c0645a7f4174cf28")  # comma-separated
    ECS_SECURITY_GROUP_IDS: str = os.getenv("ECS_SECURITY_GROUP_IDS", "sg-0c753eb8d5992cabd")  # comma-separated
    ECS_ASSIGN_PUBLIC_IP: str = os.getenv("ECS_ASSIGN_PUBLIC_IP", "ENABLED")
    
    # ECS service settings
    ECS_SERVICE_NAME: str = os.getenv("ECS_SERVICE_NAME", "github-runner-task-service-7ub1dmt0")
    ECS_SERVICE_DESIRED_COUNT_ON_PUSH: int = int(os.getenv("ECS_SERVICE_DESIRED_COUNT_ON_PUSH", "1"))
    
    # GitHub self-hosted runner settings
    # GITHUB_RUNNER_PAT removed - now using GitHub App authentication
    RUNNER_LABELS: str = os.getenv("RUNNER_LABELS", "blazeci-small")


settings = Settings()


