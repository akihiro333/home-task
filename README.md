# TaskManager - Multi-tenant SaaS Task Management

A production-ready multi-tenant task management application built with FastAPI, PostgreSQL, Redis, Celery on the backend and Next.js 15 with TypeScript and Tailwind CSS on the frontend.

## Features

- **Multi-tenant Architecture**: Single database with row-level isolation via org_id
- **Authentication**: JWT tokens with OTP verification and Google OAuth support
- **Real-time Updates**: WebSocket connections with Redis pub/sub for live task updates
- **Background Jobs**: Celery-powered CSV export functionality
- **Role-based Access Control**: Admin and member roles with proper authorization
- **Modern Frontend**: Next.js 15 App Router with TypeScript and Tailwind CSS
- **Production Ready**: Docker containers, health checks, and CI/CD pipeline

## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd home-task

# Start all services
docker compose up

# Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

The application will automatically:
1. Set up the PostgreSQL database
2. Run database migrations
3. Create seed data with demo organizations and users
4. Start all services with health checks

## Demo Accounts

### Acme Corporation (acme.example.local)
- **Admin**: admin@acme.com / admin123
- **Member**: member@acme.com / member123

### Beta Industries (beta.example.local)
- **Admin**: admin@beta.com / admin123
- **Member**: member@beta.com / member123

## Architecture Overview

### Multi-tenancy Design

The application uses a **single database with row-level isolation** approach:

- All data tables include an `org_id` column for tenant isolation
- Tenant resolution happens via subdomain (e.g., `acme.example.local`) or JWT claims
- Middleware automatically injects the current organization context
- All database queries are automatically filtered by `org_id`

**Why single database?**
- Simpler deployment and maintenance
- Cost-effective for moderate scale
- Easier cross-tenant analytics and reporting
- Simplified backup and disaster recovery

**Trade-offs considered:**
- Less isolation than separate databases
- Potential for data leakage if queries miss org_id filter
- Scaling limitations at very high tenant counts

### Authentication Flow

1. **Registration**: Creates organization, admin user, and membership
2. **Login**: Validates credentials and generates 6-digit OTP
3. **OTP Verification**: Validates code and issues JWT tokens
4. **Token Refresh**: Automatic refresh with rotation for security
5. **Google OAuth**: Alternative login method (mock mode for development)

**Security features:**
- Rate limiting on login attempts
- OTP codes expire after 10 minutes
- JWT tokens are short-lived (15 minutes) with refresh rotation
- Passwords hashed with bcrypt
- RBAC enforced server-side

### Real-time Updates

WebSocket connections provide live updates using Redis pub/sub:

1. Client connects to `/ws/{org_id}` with JWT authentication
2. Server subscribes to org-specific Redis channels
3. Task changes publish messages to Redis
4. Messages broadcast only to clients in the same organization
5. Automatic reconnection and heartbeat handling

### Background Jobs

Celery handles asynchronous tasks:

- **CSV Export**: Generates task exports for organizations
- **Redis Broker**: Reliable message queuing
- **Job Status Tracking**: Monitor export progress
- **Scalable Workers**: Easy horizontal scaling

## API Endpoints

### Authentication
```bash
# Register new organization
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "My Company",
    "subdomain": "mycompany",
    "email": "admin@mycompany.com",
    "password": "secure123"
  }'

# Login (triggers OTP)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@acme.com",
    "password": "admin123"
  }'

# Verify OTP
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@acme.com",
    "code": "123456"
  }'

# Google OAuth (mock mode)
curl -X POST http://localhost:8000/auth/login/google \
  -H "Content-Type: application/json" \
  -d '{"id_token": "MOCK_ID_TOKEN"}'

# Refresh token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your-refresh-token"}'

# Logout
curl -X POST http://localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your-refresh-token"}'
```

### Task Management
```bash
# Get tasks with filters and pagination
curl -X GET "http://localhost:8000/organizations/1/tasks?status=todo&limit=10" \
  -H "Authorization: Bearer your-access-token"

# Create task
curl -X POST http://localhost:8000/organizations/1/tasks \
  -H "Authorization: Bearer your-access-token" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New Task",
    "description": "Task description",
    "status": "todo",
    "assignee_id": 2,
    "due_date": "2024-12-31"
  }'

# Update task
curl -X PUT http://localhost:8000/tasks/1 \
  -H "Authorization: Bearer your-access-token" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "doing",
    "assignee_id": 3
  }'

# Delete task
curl -X DELETE http://localhost:8000/tasks/1 \
  -H "Authorization: Bearer your-access-token"
```

### Background Jobs
```bash
# Export tasks to CSV
curl -X POST http://localhost:8000/tasks/1/export \
  -H "Authorization: Bearer your-access-token"

# Check job status
curl -X GET http://localhost:8000/jobs/job-uuid \
  -H "Authorization: Bearer your-access-token"
```

### WebSocket Connection
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/1?token=your-access-token');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};

// Send heartbeat
ws.send(JSON.stringify({ type: 'ping' }));
```

### Health Check
```bash
curl -X GET http://localhost:8000/health
```

## Environment Variables

### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/taskmanager

# Redis
REDIS_URL=redis://localhost:6379

# JWT Configuration
JWT_SECRET=your-secret-key-change-in-production
JWT_ISSUER=taskmanager
ACCESS_TTL_MIN=15
REFRESH_TTL_DAYS=7
OTP_TTL_MIN=10

# OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id

# Application
PUBLIC_URL=http://localhost:8000
TENANT_SUBDOMAIN_BASE=example.local
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id
```

## Development

### Backend Development
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest -v

# Run linting
ruff check .
mypy app/
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run type checking
npm run type-check

# Run linting
npm run lint
```

### Running Tests

```bash
# Backend tests (with coverage)
cd backend
pytest -v --cov=app

# Frontend type checking
cd frontend
npm run type-check
```

## Security Considerations

### Implemented Security Measures
- **Authentication**: JWT with short expiration and refresh rotation
- **Authorization**: Role-based access control enforced server-side
- **Rate Limiting**: Login attempt throttling via Redis
- **Input Validation**: Pydantic models for request validation
- **SQL Injection**: SQLAlchemy ORM with parameterized queries
- **CORS**: Configured for specific origins
- **Password Security**: bcrypt hashing with salt

### Production Security Recommendations
- Use HTTPS in production
- Set secure, random JWT secrets
- Configure proper CORS origins
- Enable database connection encryption
- Implement request rate limiting
- Add API key authentication for service-to-service calls
- Regular security audits and dependency updates
- Monitor for suspicious activity

## Scaling Considerations

### Current Architecture Limits
- Single database instance
- In-memory session storage
- Single Redis instance

### Scaling Strategies
1. **Database**: Read replicas, connection pooling, query optimization
2. **Application**: Horizontal scaling with load balancer
3. **Redis**: Redis Cluster for high availability
4. **Background Jobs**: Multiple Celery workers
5. **Frontend**: CDN for static assets, edge caching

### Migration Path for Large Scale
- Consider database sharding by tenant
- Implement distributed caching
- Move to microservices architecture
- Add monitoring and observability

## Deployment

### Docker Production
```bash
# Build and run in production mode
docker compose -f docker-compose.prod.yml up -d
```

### Cloud Run (Google Cloud)
The CI pipeline includes commented deployment steps for Google Cloud Run:

1. Configure project ID and region in `.github/workflows/ci.yml`
2. Set up service account with Cloud Run permissions
3. Add secrets: `GCP_SA_KEY`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`
4. Uncomment and customize the deploy job

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues:
1. Check the API documentation at `/docs`
2. Review the test files for usage examples
3. Open an issue on GitHub

---

Built with ❤️ using FastAPI, Next.js, PostgreSQL, Redis, and Docker.