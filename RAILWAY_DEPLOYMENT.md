# Railway Deployment Guide

This project is structured as a monorepo with separate backend and frontend services. Follow these instructions for proper Railway deployment.

## Service Configuration

You need to create **two separate services** in Railway, one for backend and one for frontend.

### Backend Service Configuration

1. **Create a new service** in your Railway project
2. **Connect to this repository**
3. Configure the following settings in Service Settings:

#### Root Directory
```
backend
```

#### Environment Variables
```bash
SERVICE_ROLE=backend
BACKEND_PORT=${PORT}

# Database (use Railway Postgres or external)
DB_ENGINE=postgres
DB_HOST=<your-postgres-host>
DB_PORT=5432
DB_NAME=<your-db-name>
DB_USER=<your-db-user>
DB_PASSWORD=<your-db-password>

# Session & Auth
SESSION_SECRET=<generate-a-secure-random-string>
AUTH_MODE=DEFAULT

# OpenWebUI Integration
OPEN_WEBUI_HOSTNAME=<your-openwebui-hostname>
OPEN_WEBUI_API_KEY=<your-api-key>

# Optional: Session cookie settings
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAME_SITE=strict
```

#### Custom Start Command
```bash
bash ../start.sh
```

#### Watch Paths (Optional - prevents unnecessary rebuilds)
```
backend/**
start.sh
```

### Frontend Service Configuration

1. **Create another service** in your Railway project
2. **Connect to this repository**
3. Configure the following settings in Service Settings:

#### Root Directory
```
frontend
```

#### Environment Variables
```bash
SERVICE_ROLE=frontend
FRONTEND_PORT=${PORT}

# API Configuration (use your backend service URL)
NEXT_PUBLIC_API_BASE_URL=https://<your-backend-service>.up.railway.app
API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

# Node/Next.js settings
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1

# Auth mode (must match backend)
AUTH_MODE=DEFAULT
NEXT_PUBLIC_AUTH_MODE=DEFAULT
```

#### Custom Start Command
```bash
bash ../start.sh
```

#### Watch Paths (Optional - prevents unnecessary rebuilds)
```
frontend/**
start.sh
```

## How It Works

### Root Directory Setting

By setting the Root Directory to `backend` or `frontend`, Railway:
- Changes the working directory for all build and deploy commands
- Auto-detects dependencies (`requirements.txt` for Python, `package.json` for Node)
- Runs Railpack from that subdirectory

### Automatic Detection

**Backend:**
- Railpack detects `requirements.txt` in `/backend`
- Automatically installs Python 3.11 (or version specified in `runtime.txt`)
- Runs `pip install -r requirements.txt`
- Executes the start command

**Frontend:**
- Railpack detects `package.json` in `/frontend`
- Automatically installs Node.js dependencies
- Runs `npm run build` (production build)
- Executes the start command

### Start Script

The `../start.sh` script:
1. Checks the `SERVICE_ROLE` environment variable
2. Routes to either `start_backend()` or `start_frontend()`
3. Runs Alembic migrations (backend only)
4. Starts Uvicorn (backend) or Next.js production server (frontend)

## Watch Paths

Watch paths prevent code changes in one service from triggering rebuilds of the other service. Without watch paths:
- A change in `frontend/` would redeploy both frontend AND backend
- With watch paths, only the relevant service redeploys

## Troubleshooting

### "python interpreter not found"
- Ensure Root Directory is set to `backend`
- Check that `requirements.txt` exists in `/backend` directory

### "node_modules missing" or ".next missing"
- Ensure Root Directory is set to `frontend`
- Check that `package.json` exists in `/frontend` directory
- Verify `npm run build` completed successfully in build logs

### "Service role not set" warning
- Add `SERVICE_ROLE=backend` or `SERVICE_ROLE=frontend` to environment variables

### Database connection errors
- Verify all `DB_*` environment variables are set correctly
- If using Railway Postgres, use the connection variables from the database service
- Check that Alembic migrations ran successfully in logs

## Alternative: Direct Database URI

Instead of individual `DB_*` variables, you can use a direct connection string:

```bash
SQLALCHEMY_DATABASE_URI=postgresql://user:password@host:port/database
```

This is especially useful with Railway's Postgres service, which provides a `DATABASE_URL` variable.
