# Railway Deployment Setup Guide

This guide walks you through deploying the Mission AI Possible Challenge Analytics Tool on Railway.

## Architecture

Railway deployment consists of two services:
- **Backend Service**: FastAPI application
- **Frontend Service**: Next.js application

## Prerequisites

1. Railway account
2. GitHub repository connected to Railway
3. Railway CLI (optional, for local testing)

## Service Configuration

### Backend Service

#### Root Directory
Set the **Root Directory** to: `backend`

#### Build Configuration
- **Builder**: Dockerfile
- **Dockerfile Path**: `backend/Dockerfile`

#### Start Command
```bash
bash start.sh
```

#### Environment Variables

**Required:**
```bash
# Port (Railway provides this automatically)
# PORT=8000  # Managed by Railway

# CORS Configuration - CRITICAL!
# Replace with your actual frontend Railway URL
CORS_ALLOW_ORIGINS=https://your-frontend-domain.up.railway.app

# OpenWebUI Integration
OPEN_WEBUI_HOSTNAME=https://your-openwebui-instance.com
OPEN_WEBUI_API_KEY=sk-your-api-key-here

# Session Security
SESSION_SECRET=your-secure-random-string-here
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAME_SITE=lax
```

**Optional:**
```bash
# Database (use Railway Postgres for production)
DB_ENGINE=postgres  # or sqlite for testing
DB_HOST=${PGHOST}  # From Railway Postgres service
DB_PORT=${PGPORT}
DB_NAME=${PGDATABASE}
DB_USER=${PGUSER}
DB_PASSWORD=${PGPASSWORD}

# Or use the connection string directly:
SQLALCHEMY_DATABASE_URI=${DATABASE_URL}

# Auth Mode
AUTH_MODE=DEFAULT  # or HYBRID, OAUTH

# For Microsoft OAuth (if using HYBRID or OAUTH mode)
OAUTH_TENANT_ID=your-tenant-id
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_REDIRECT_URL=https://your-frontend-domain.up.railway.app/auth/oauth/callback

# Feature Flags
FEATURE_ROLE_USER_ENABLED=false

# Logging
BACKEND_LOG_LEVEL=INFO
```

---

### Frontend Service

#### Root Directory
Set the **Root Directory** to: `frontend`

#### Build Configuration
- **Builder**: Dockerfile
- **Dockerfile Path**: `frontend/Dockerfile`

#### Start Command
```bash
bash start.sh
```

#### Environment Variables

**Required:**
```bash
# Port (Railway provides this automatically)
# PORT=3000  # Managed by Railway

# Browser-side API calls (use backend's PUBLIC Railway URL)
NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain.up.railway.app

# Server-side API calls (can use internal networking for better performance)
# Option 1: Use internal networking (faster, no egress costs)
API_BASE_URL=http://backend.railway.internal

# Option 2: Use public URL (if internal networking doesn't work)
# API_BASE_URL=https://your-backend-domain.up.railway.app

# Auth Mode (must match backend)
AUTH_MODE=DEFAULT
NEXT_PUBLIC_AUTH_MODE=DEFAULT
```

**Optional:**
```bash
# Node Environment
NODE_ENV=production
```

---

## Step-by-Step Deployment

### 1. Deploy Backend Service

1. Create a new service in Railway
2. Connect your GitHub repository
3. Set **Root Directory** to `backend`
4. Add all required environment variables (see above)
5. **IMPORTANT**: Leave `CORS_ALLOW_ORIGINS` blank initially (we'll add it after frontend deployment)
6. Deploy the service
7. Note the public URL: `https://backend-production-xxxx.up.railway.app`

### 2. Deploy Frontend Service

1. Create a new service in Railway
2. Connect the same GitHub repository
3. Set **Root Directory** to `frontend`
4. Add environment variables:
   ```bash
   NEXT_PUBLIC_API_BASE_URL=https://backend-production-xxxx.up.railway.app
   API_BASE_URL=http://backend.railway.internal
   AUTH_MODE=DEFAULT
   NEXT_PUBLIC_AUTH_MODE=DEFAULT
   ```
5. Deploy the service
6. Note the public URL: `https://frontend-production-yyyy.up.railway.app`

### 3. Update Backend CORS Configuration

**This is the critical step!**

1. Go back to your **backend service** in Railway
2. Add/Update the `CORS_ALLOW_ORIGINS` environment variable:
   ```bash
   CORS_ALLOW_ORIGINS=https://frontend-production-yyyy.up.railway.app
   ```
   Replace with your actual frontend URL from step 2.
3. Railway will automatically redeploy the backend

### 4. Test the Health Check

1. Visit: `https://your-frontend-domain.up.railway.app/status/health`
2. Check that both Frontend and Backend services show ✓ OK
3. The page will display the exact CORS configuration you need if there's still an error

---

## Common Issues

### "Failed to fetch" Error

**Symptom**: Backend shows ✗ ERROR with "Failed to fetch" message

**Cause**: CORS is blocking requests from the frontend origin

**Solution**:
1. Visit `/status/health` on your deployed frontend
2. Look for the yellow warning box that says "IMPORTANT FOR RAILWAY"
3. Copy the exact `CORS_ALLOW_ORIGINS` value shown
4. Add it to your backend service environment variables
5. Wait for Railway to redeploy

### Internal Networking Not Working

**Symptom**: Frontend cannot connect to `http://backend.railway.internal`

**Solution**: Use the public backend URL instead:
```bash
API_BASE_URL=https://backend-production-xxxx.up.railway.app
```

Note: This will count against egress, but it will work.

### Redirecting to Login Instead of Setup

**Symptom**: Fresh deployment with no users redirects to `/auth/login` instead of `/setup`

**Cause**: The frontend middleware cannot reach the backend to check if setup is needed. When the health check times out, older versions assumed setup was complete.

**Solution**:
1. Check Railway logs for the frontend service to see middleware errors
2. Verify `API_BASE_URL` is set correctly (try both internal and public URLs)
3. Ensure backend service is fully started before frontend starts checking
4. The latest middleware code now handles this gracefully by redirecting to `/setup` when unable to determine status

**Debug Steps**:
```bash
# Check frontend logs
railway logs --service frontend

# Look for these log messages:
# "[Middleware] Checking setup status at: ..."
# "[Middleware] Setup status response: ..."
```

### Database Connection Issues

**For SQLite (development/testing):**
```bash
DB_ENGINE=sqlite
# No other DB variables needed
```

**For Postgres (production):**
1. Add a Postgres service in Railway
2. Use Railway's provided connection variables:
   ```bash
   DB_ENGINE=postgres
   SQLALCHEMY_DATABASE_URI=${DATABASE_URL}
   ```

### Session/Auth Issues

Make sure these match between frontend and backend:
```bash
# Backend
AUTH_MODE=DEFAULT
SESSION_SECRET=your-secret-here

# Frontend
AUTH_MODE=DEFAULT
NEXT_PUBLIC_AUTH_MODE=DEFAULT
```

---

## Custom Domains

If you're using custom domains:

1. Add your custom domain in Railway's service settings
2. Update environment variables:
   ```bash
   # Backend
   CORS_ALLOW_ORIGINS=https://your-custom-frontend-domain.com

   # Frontend
   NEXT_PUBLIC_API_BASE_URL=https://your-custom-backend-domain.com
   ```

---

## Environment Variable Quick Reference

### Backend Must Have:
- `CORS_ALLOW_ORIGINS` ← Frontend's public URL
- `OPEN_WEBUI_HOSTNAME`
- `OPEN_WEBUI_API_KEY`
- `SESSION_SECRET`

### Frontend Must Have:
- `NEXT_PUBLIC_API_BASE_URL` ← Backend's public URL
- `API_BASE_URL` ← Backend's internal or public URL
- `AUTH_MODE`
- `NEXT_PUBLIC_AUTH_MODE`

---

## Troubleshooting Tools

### Health Check Page
Visit: `https://your-frontend-domain.up.railway.app/status/health`

This page shows:
- Frontend status
- Backend connectivity
- Exact CORS configuration needed
- Response times
- Error messages

### Railway Logs
```bash
# View backend logs
railway logs --service backend

# View frontend logs
railway logs --service frontend
```

### Test Backend Directly
```bash
curl https://your-backend-domain.up.railway.app/health
```

Should return: `{"status":"ok"}`

---

## Security Checklist

Before going to production:

- [ ] Change `SESSION_SECRET` to a secure random string
- [ ] Set `SESSION_COOKIE_SECURE=true`
- [ ] Use Postgres instead of SQLite
- [ ] Only allow specific origins in `CORS_ALLOW_ORIGINS` (no wildcards)
- [ ] Rotate `OPEN_WEBUI_API_KEY` regularly
- [ ] Set up OAuth if needed (`AUTH_MODE=OAUTH` or `HYBRID`)
- [ ] Review Railway service logs for any security warnings

---

## Performance Tips

1. **Use internal networking**: Set `API_BASE_URL=http://backend.railway.internal` to avoid egress charges
2. **Add caching**: Consider adding Redis for session storage
3. **Database**: Use Railway Postgres with connection pooling
4. **CDN**: Put a CDN in front of your frontend for static assets

---

## Support

If you encounter issues:
1. Check the `/status/health` page first
2. Review Railway service logs
3. Verify all environment variables are set correctly
4. Check that CORS configuration matches exactly
5. Test backend `/health` endpoint directly with curl

For more help, see:
- [Railway Documentation](https://docs.railway.app)
- [FastAPI CORS Guide](https://fastapi.tiangolo.com/tutorial/cors/)
- [Next.js Environment Variables](https://nextjs.org/docs/basic-features/environment-variables)
