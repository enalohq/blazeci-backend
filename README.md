# BlazeCI Backend

FastAPI-based backend service for the BlazeCI GitHub Actions runner management platform.

## 🚀 Features

- **GitHub OAuth Integration**: Secure user authentication
- **GitHub App Support**: Repository access and management
- **Runner Management**: Create, manage, and monitor GitHub runners
- **Database Integration**: PostgreSQL with SQLAlchemy ORM
- **RESTful API**: Comprehensive API for frontend integration
- **Webhook Handling**: Process GitHub webhooks for runner events
- **AWS Integration**: ECS task management and SQS processing

## 🏗️ Architecture

### Technology Stack
- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL with SQLAlchemy
- **Authentication**: JWT tokens with GitHub OAuth
- **Deployment**: AWS Lambda or ECS containers
- **Queue**: AWS SQS for async processing

### API Endpoints
- `POST /auth/github` - GitHub OAuth authentication
- `GET /repos` - List user repositories
- `POST /repos/{repo_id}/runners` - Create runner for repository
- `DELETE /runners/{runner_id}` - Remove runner
- `GET /runners` - List active runners
- `POST /webhooks/github` - GitHub webhook handler

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL database
- GitHub OAuth App configured
- AWS credentials (for production)

### Local Development
```bash
# Clone the repository
git clone https://github.com/enalohq/blazeci-backend.git
cd blazeci-backend/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run directly
docker build -t blazeci-backend .
docker run -p 8000:8000 --env-file .env blazeci-backend
```

## 🔧 Configuration

### Environment Variables

#### Required
- `DATABASE_URL`: PostgreSQL connection string
- `GITHUB_CLIENT_ID`: GitHub OAuth App Client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth App Client Secret
- `ENCRYPTION_KEY`: Base64 encoded encryption key for tokens

#### Optional
- `GITHUB_APP_ID`: GitHub App ID (for app authentication)
- `GITHUB_APP_PRIVATE_KEY`: GitHub App private key
- `AWS_REGION`: AWS region for ECS/Lambda
- `ECS_CLUSTER`: ECS cluster name
- `ECS_TASK_DEFINITION`: ECS task definition name
- `SQS_QUEUE_URL`: SQS queue URL for async processing

### Database Schema
The application uses Alembic for database migrations. Key tables:
- `users`: User accounts and GitHub integration
- `repositories`: Connected GitHub repositories
- `runners`: Active runner instances
- `github_installations`: GitHub App installations

## 📚 API Documentation

### Authentication
The API uses JWT tokens for authentication. Obtain a token via the GitHub OAuth flow:

```bash
# Get authorization URL
curl -X GET "http://localhost:8000/auth/github/authorize"

# Exchange code for token
curl -X POST "http://localhost:8000/auth/github/callback" \
  -H "Content-Type: application/json" \
  -d '{"code": "github_oauth_code"}'
```

### Repository Management
```bash
# List user repositories
curl -X GET "http://localhost:8000/repos" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Create runner for repository
curl -X POST "http://localhost:8000/repos/123/runners" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"labels": ["blazeci-small"], "max_runners": 5}'
```

### Runner Management
```bash
# List active runners
curl -X GET "http://localhost:8000/runners" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Remove runner
curl -X DELETE "http://localhost:8000/runners/456" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🚀 Deployment

### AWS Lambda
```bash
# Build deployment package
pip install -r requirements.txt -t package/
cp -r app package/
cd package && zip -r ../blazeci-backend.zip .

# Deploy to Lambda
aws lambda create-function \
  --function-name blazeci-backend \
  --runtime python3.10 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler app.main.handler \
  --zip-file fileb://blazeci-backend.zip
```

### AWS ECS
```bash
# Build and push Docker image
docker build -t blazeci-backend .
docker tag blazeci-backend:latest YOUR_ECR_REPO/blazeci-backend:latest
docker push YOUR_ECR_REPO/blazeci-backend:latest

# Update ECS service
aws ecs update-service \
  --cluster YOUR_CLUSTER \
  --service blazeci-backend \
  --force-new-deployment
```

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## 📊 Monitoring

### Health Checks
- `GET /health` - Basic health check
- `GET /health/db` - Database connectivity check
- `GET /health/github` - GitHub API connectivity check

### Logging
The application uses structured logging with different levels:
- `INFO`: General application flow
- `WARNING`: Non-critical issues
- `ERROR`: Application errors
- `DEBUG`: Detailed debugging information

## 🔒 Security

### Authentication
- JWT tokens with configurable expiration
- GitHub OAuth 2.0 integration
- Secure token storage and encryption

### Data Protection
- All sensitive data encrypted at rest
- Secure database connections
- Input validation and sanitization

### API Security
- Rate limiting on all endpoints
- CORS configuration for frontend integration
- Request validation using Pydantic models

## 🛠️ Development

### Code Structure
```
app/
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── db.py                # Database connection
├── models.py            # SQLAlchemy models
├── security.py          # Authentication utilities
├── github.py            # GitHub API integration
├── routers/             # API route handlers
│   ├── auth.py
│   ├── repos.py
│   ├── webhooks.py
│   └── github_app.py
└── alembic/             # Database migrations
```

### Adding New Features
1. Create database migration if needed
2. Add new models in `models.py`
3. Create API routes in `routers/`
4. Add tests in `tests/`
5. Update documentation

## 📞 Support

For issues and questions:
- Create an issue in this repository
- Check the API documentation at `/docs` when running locally
- Review the infrastructure repository for deployment guidance

## 📄 License

This project is licensed under the MIT License.
