# Railway Deployment Status

## Current Issue
Railway deployment fails with 502 error. Root cause: Railway is using cached build that has incorrect PORT variable expansion.

**CRITICAL**: Railway's build cache is extremely aggressive and ignores ALL code changes:
- ✅ Fixed Dockerfile with entrypoint.sh (proper PORT expansion)
- ✅ Fixed Alembic migration with IF NOT EXISTS for enum types
- ✅ Switched to Nixpacks builder
- ✅ Multiple git pushes (15+ commits)
- ❌ Railway STILL uses old cached build from days ago

Railway logs show: `Error: Invalid value for '--port': '$PORT' is not a valid integer`
This proves Railway is NOT using the new code with entrypoint.sh.

**SOLUTION**: User MUST manually clear build cache in Railway dashboard.

## What Was Tried
1. ✅ Set all environment variables via Railway API (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, etc.)
2. ✅ Fixed Dockerfile CMD to use shell expansion: `CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]`
3. ✅ Created entrypoint.sh script with proper PORT expansion
4. ✅ Added nixpacks.toml configuration
5. ✅ Added railway.json with Nixpacks builder
6. ❌ Railway still uses old cached Docker image despite multiple git pushes and `railway up` commands

## Current Configuration

### Environment Variables (Set via Railway API)

Wszystkie wartości w Railway → Variables. **Nigdy nie commituj sekretów do repo.**

- `ANTHROPIC_API_KEY` — z console.anthropic.com (lub proxy z `ANTHROPIC_BASE_URL`)
- `ANTHROPIC_BASE_URL` — opcjonalnie, jeśli używasz proxy
- `TELEGRAM_BOT_TOKEN` — z @BotFather
- `TELEGRAM_CHAT_ID` — chat ID Janka
- `EMAIL_PROVIDER` — `gmail` lub `smtp`
- `PORT` — ustawia Railway (nie nadpisuj)
- `PUBLIC_FORM_BASE_URL` — np. `https://app-usa-production.up.railway.app`
- `DATABASE_URL` — auto-set przez Railway PostgreSQL addon

### Files
- `Dockerfile`: Uses entrypoint.sh with proper shell expansion
- `entrypoint.sh`: Shell script that runs migrations and starts uvicorn with ${PORT}
- `nixpacks.toml`: Nixpacks configuration for Railway
- `railway.json`: Specifies Nixpacks builder with health check

## Next Steps (Manual)
1. Open Railway dashboard: https://railway.app/project/42e7551e-a5fb-4b80-8970-aabe11b34d50
2. Go to app-usa service settings
3. Click "Clear Build Cache" or "Redeploy" with cache clearing option
4. Wait for new deployment to complete
5. Verify health endpoint: https://app-usa-production.up.railway.app/health

## Alternative: Local Docker Test
```bash
# Build and test locally
docker build -t app-usa .
docker run -e PORT=8000 -e DATABASE_URL=sqlite:///./test.db -p 8000:8000 app-usa

# Test health endpoint
curl http://localhost:8000/health
```

## Railway Service IDs

Project / Service / Environment IDs trzymaj poza repo (np. w `.env.local` lub w prywatnym notesie). IDs nie są tak wrażliwe jak tokeny, ale ułatwiają reconnaissance — lepiej ich nie publikować.
