import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_backend_dir / ".env", override=False)


class Settings:
    github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
    github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    github_redirect_uri: str = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "https://wgu3ek-ip-27-123-241-218.tunnelmole.net/auth/callback")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")
    session_secret: str = os.getenv("SESSION_SECRET", "dev-secret")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    backend_origin: str = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")
    webhook_url: str = os.getenv("WEBHOOK_URL", "https://wgu3ek-ip-27-123-241-218.tunnelmole.net/webhooks/github")
    # AWS / ECS settings for ephemeral runner
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    ecs_cluster: str = os.getenv("ECS_CLUSTER", "ECS-ECR-STAGING-API")
    ecs_task_definition: str = os.getenv("ECS_TASK_DEFINITION", "github-runner-task")
    ecs_container_name: str = os.getenv("ECS_CONTAINER_NAME", "github-runner")
    ecs_subnet_ids: str = os.getenv("ECS_SUBNET_IDS", "subnet-0f00f5030e91c0b42,subnet-0d9d4d75b11eba35b,subnet-0c0645a7f4174cf28")  # comma-separated
    ecs_security_group_ids: str = os.getenv("ECS_SECURITY_GROUP_IDS", "sg-0c753eb8d5992cabd")  # comma-separated
    ecs_assign_public_ip: str = os.getenv("ECS_ASSIGN_PUBLIC_IP", "ENABLED")
    # ECS service settings
    ecs_service_name: str = os.getenv("ECS_SERVICE_NAME", "github-runner-task-service-7ub1dmt0")
    ecs_service_desired_count_on_push: int = int(os.getenv("ECS_SERVICE_DESIRED_COUNT_ON_PUSH", "1"))
    # GitHub self-hosted runner settings
    runner_pat: str = os.getenv("GITHUB_RUNNER_PAT", "")
    runner_labels: str = os.getenv("GITHUB_RUNNER_LABELS", "blazeci-small")


settings = Settings()


