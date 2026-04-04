# TEDIHT - Smart Document Inspection and Archival System

## Overview

Alt_F4_Bureaucracy is a comprehensive document management system designed to streamline document inspection, processing, and archival. It combines multiple technologies to provide intelligent document handling, full-text search capabilities, and automated task processing.

## Architecture

The system is built with the following components:

- **FastAPI Backend**: RESTful API for document management and operations
- **Streamlit Frontend**: User-friendly dashboard for document visualization and interaction
- **PostgreSQL**: Primary relational database for structured data
- **Neo4j**: Graph database for relationship and document flow tracking
- **Celery**: Distributed task queue for asynchronous processing
- **Redis**: Message broker and caching layer
- **Meilisearch**: Full-text search engine for fast document retrieval
- **MinIO**: S3-compatible object storage for document files

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** installed on your system
- Sufficient disk space for database volumes
- Ports 5432, 6379, 7687, 7474, 7700, 9000, 9001, 8000, and 8501 available

### Installation & Running

1. **Clone or navigate to the project directory**:

   ```bash
   cd /path/to/Alt_F4_Bureaucracy
   ```

2. **Create a `.env` file** (optional - uses defaults if not provided):

   ```bash
   # Database Configuration
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=alt_db
   POSTGRES_PORT=5432

   # Neo4j Configuration
   NEO4J_AUTH=neo4j/password
   NEO4J_AUTH_USER=neo4j
   NEO4J_AUTH_PASSWORD=password
   NEO4J_PORT=7687
   NEO4J_BROWSER_PORT=7474

   # Redis Configuration
   REDIS_PASSWORD=redis_password
   REDIS_PORT=6379

   # Meilisearch Configuration
   MEILI_MASTER_KEY=super_secret_key
   MEILI_ENV=development
   MEILISEARCH_PORT=7700

   # MinIO Configuration
   MINIO_ROOT_USER=minioadmin
   MINIO_ROOT_PASSWORD=minioadmin
   MINIO_PORT=9000
   MINIO_CONSOLE_PORT=9001

   # FastAPI Configuration
   FASTAPI_PORT=8000

   # Streamlit Configuration
   STREAMLIT_PORT=8501
   ```

3. **Start all services with Docker Compose**:

   ```bash
   docker-compose up -d
   ```

   For verbose output and debugging:

   ```bash
   docker-compose up
   ```

4. **Wait for services to be ready** (health checks run automatically):

   ```bash
   docker-compose ps
   ```

   All services should show `healthy` status before proceeding.

### Accessing the Application

Once all services are running:

- **FastAPI API**: http://localhost:8000
  - API Documentation (Swagger UI): http://localhost:8000/docs
  - Alternative API Docs (ReDoc): http://localhost:8000/redoc
  - Health Check: http://localhost:8000/health

- **Streamlit Dashboard**: http://localhost:8501

- **Neo4j Browser**: http://localhost:7474
  - Default username: `neo4j`
  - Default password: `password`

- **MinIO Console**: http://localhost:9001
  - Default username: `minioadmin`
  - Default password: `minioadmin`

- **Meilisearch**: http://localhost:7700

- **PostgreSQL**: `localhost:5432`
  - Default username: `postgres`
  - Default password: `postgres`
  - Database: `alt_db`

- **Redis**: `localhost:6379`

## Project Structure

```
Alt_F4_Bureaucracy/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── celery_app.py          # Celery configuration
│   ├── schemas.py             # Pydantic models
│   ├── db/
│   │   ├── database.py        # Database connection config
│   │   ├── init_db.py         # Database initialization
│   │   └── __init__.py
│   └── models/
│       ├── user.py            # User model
│       ├── document.py        # Document model
│       ├── alert.py           # Alert model
│       ├── audit.py           # Audit log model
│       ├── archive.py         # Archive model
│       ├── role.py            # Role/permission model
│       └── __init__.py
├── streamlit_app/
│   └── main.py                # Streamlit frontend
├── alembic/
│   ├── env.py                 # Alembic configuration
│   └── versions/              # Migration scripts
├── docker-compose.yml         # Service orchestration
├── Dockerfile.fastapi         # FastAPI container
├── Dockerfile.celery          # Celery worker/beat container
├── Dockerfile.streamlit       # Streamlit container
├── requirements.txt           # Python dependencies
└── alembic.ini               # Alembic config file
```

## Common Commands

### Start Services

```bash
# Start all services in background
docker-compose up -d

# Start specific service(s)
docker-compose up -d fastapi
docker-compose up -d streamlit
```

### View Logs

```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f fastapi
docker-compose logs -f celery-worker
docker-compose logs -f streamlit
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (careful - data will be deleted)
docker-compose down -v
```

### Rebuild Services

```bash
# Rebuild all services
docker-compose up -d --build

# Rebuild specific service
docker-compose up -d --build fastapi
```

### Access Service Shells

```bash
# FastAPI container
docker exec -it alt-fastapi bash

# Celery worker
docker exec -it alt-celery-worker bash

# PostgreSQL
docker exec -it alt-postgres psql -U postgres -d alt_db
```

## Services Overview

| Service       | Port        | Purpose                     | Healthcheck      |
| ------------- | ----------- | --------------------------- | ---------------- |
| PostgreSQL    | 5432        | Primary relational database | `pg_isready`     |
| Neo4j         | 7687 / 7474 | Graph database & browser UI | HTTP GET         |
| Redis         | 6379        | Cache & message broker      | Redis PING       |
| Meilisearch   | 7700        | Full-text search engine     | HTTP GET /health |
| MinIO         | 9000 / 9001 | Object storage & console    | HTTP GET /health |
| FastAPI       | 8000        | REST API backend            | Implicit         |
| Celery Worker | -           | Async task processing       | -                |
| Celery Beat   | -           | Task scheduling             | -                |
| Streamlit     | 8501        | Web dashboard               | -                |

## Development Notes

- **Database Migrations**: Use Alembic for schema changes

  ```bash
  # Create a new migration
  docker-compose exec fastapi alembic revision --autogenerate -m "message"

  # Apply migrations
  docker-compose exec fastapi alembic upgrade head
  ```

- **Environment Variables**: All services read configuration from environment variables (defined in `.env` or `docker-compose.yml`)

- **Hot Reload**: FastAPI and Streamlit services have volume mounts and reload enabled for development

- **Celery Tasks**: Check `app/celery_app.py` for task definitions

## Troubleshooting

### Services fail to start

- Check Docker is running: `docker ps`
- Review logs: `docker-compose logs`
- Ensure ports are not already in use: `netstat -an | grep LISTEN`

### Database connection errors

- Verify PostgreSQL is healthy: `docker-compose ps postgres`
- Check connection string in environment variables
- Reset database: `docker-compose down -v && docker-compose up -d`

### Memory issues with Neo4j

- Edit `docker-compose.yml` Neo4j section to adjust heap sizes
- Default is 512MB initial, 1024MB max

## Auth and RBAC Manual Test Cases

Use this section as a checklist for manual testing in Swagger (`/docs`) or with `curl`.

### Role Mapping (current implementation)

- `admin`, `system` -> `ADMIN`
- `archivist`, `inspector`, `operator` -> `OPERATOR`
- `viewer`, `auditor` -> `AUDITOR`

### Authentication Endpoints

| Endpoint                                                    | Expected Response                        |
| ----------------------------------------------------------- | ---------------------------------------- |
| `POST /auth/register` with new username/email               | `200` + created user info                |
| `POST /auth/register` with duplicate username/email         | `409`                                    |
| `POST /auth/login` with valid credentials                   | `200` + `access_token` + `refresh_token` |
| `POST /auth/login` with invalid credentials                 | `401`                                    |
| `GET /auth/me` with valid access token                      | `200` + current user profile             |
| `GET /auth/me` without token                                | `403` with `Not authenticated`           |
| `POST /auth/refresh` with valid refresh token               | `200` + new token pair                   |
| `POST /auth/refresh` with revoked/expired/old refresh token | `401`                                    |
| `POST /auth/logout` with valid refresh token                | `200` + `Refresh token revoked`          |

### RBAC Authorization Matrix

#### Document endpoints

| Endpoint                      | ADMIN                          | OPERATOR                       | AUDITOR                          |
| ----------------------------- | ------------------------------ | ------------------------------ | -------------------------------- |
| `POST /upload`                | `200` or `409` duplicate       | `200` or `409` duplicate       | `403` `Insufficient permissions` |
| `POST /upload-pdf`            | `200` (or processing response) | `200` (or processing response) | `403` `Insufficient permissions` |
| `POST /{document_id}/process` | `200`                          | `200`                          | `403` `Insufficient permissions` |
| `GET /task-status/{task_id}`  | `200`                          | `200`                          | `200`                            |

#### Invoice endpoints

| Endpoint                              | ADMIN   | OPERATOR | AUDITOR |
| ------------------------------------- | ------- | -------- | ------- |
| `POST /api/v1/invoices/extract`       | allowed | allowed  | `403`   |
| `POST /api/v1/invoices/extract-url`   | allowed | allowed  | `403`   |
| `POST /api/v1/invoices/validate-full` | allowed | allowed  | `403`   |
| `POST /api/v1/invoices/batch-extract` | allowed | allowed  | `403`   |
| `GET /api/v1/invoices/validate`       | allowed | allowed  | allowed |

#### Nomenclator endpoints

| Endpoint                                 | ADMIN   | OPERATOR | AUDITOR |
| ---------------------------------------- | ------- | -------- | ------- |
| `POST /api/v1/nomenclator/suggest`       | allowed | allowed  | `403`   |
| `POST /api/v1/nomenclator/suggest-batch` | allowed | allowed  | `403`   |
| `GET /api/v1/nomenclator/standards`      | allowed | allowed  | allowed |

### Notes for Swagger (`/docs`)

- Endpoints are visible to all users in Swagger; authorization is enforced only on `Execute`.
- If response is `403` with `Not authenticated`, token header was not sent.
- If response is `403` with `Insufficient permissions`, token is valid but role is not allowed.
- In Swagger generated `curl`, confirm the `Authorization: Bearer ...` header exists before executing.

## Team Collaboration

- Pull changes and rebuild: `docker-compose down && git pull && docker-compose up -d --build`
- Share environment variables via `.env.example` (without secrets)
- Document schema changes in `DATABASE_SCHEMA.md` and `MIGRATIONS.md`
- Use Alembic migrations for all database changes

---

For more information, see `DATABASE_SCHEMA.md`, `DB_SCHEMA.md`, and `MIGRATIONS.md`
