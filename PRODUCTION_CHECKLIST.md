# Production Readiness Checklist

## Environment Variables

### Required
- [x] `ANTHROPIC_API_KEY` - Claude API key (validated on startup)
- [x] `TELEGRAM_BOT_TOKEN` - Telegram bot for notifications
- [x] `TELEGRAM_CHAT_ID` - Telegram chat ID for Janek
- [ ] `DATABASE_URL` - PostgreSQL connection string (Railway addon)

### Email Configuration
- [x] `EMAIL_PROVIDER` - "gmail" or "smtp"
- [ ] Gmail OAuth: `GMAIL_CLIENT_SECRETS`, `GMAIL_TOKEN_PATH`
- [ ] SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

### Optional
- [ ] `ANTHROPIC_BASE_URL` - Custom API endpoint (if using proxy)
- [ ] `SCRAPERAPI_KEY` - ScraperAPI for Copart fallback
- [ ] Scraper credentials: `COPART_USERNAME`, `COPART_PASSWORD`, etc.

## Database Migrations

```bash
# Generate migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Security

### Rate Limiting
- [x] `/inquiry` endpoint: 10 requests/hour per IP (slowapi)
- [ ] Scraper rate limiting: max 30 searches/day per source (TODO: implement)

### Input Validation
- [x] Form inputs sanitized (FastAPI Form validation)
- [x] Email validation (pydantic EmailStr)
- [ ] SQL injection protection (SQLModel parameterized queries)
- [ ] XSS protection (Jinja2 auto-escaping enabled)

### Secrets Management
- [x] `.env` file not committed (in .gitignore)
- [x] `.env.example` provided for reference
- [ ] Railway environment variables configured

## Error Handling

### Application Level
- [x] Startup validation (ANTHROPIC_API_KEY required)
- [x] Scraper failures don't crash pipeline (try/catch in tasks.py)
- [x] Telegram notification errors logged (don't block main flow)
- [ ] Sentry integration (optional, for production monitoring)

### Health Checks
- [x] `/health` endpoint returns DB + API status
- [x] Railway health check configured (checks `/health`)

## Logging

### Current Setup
- [x] Python logging configured (INFO level)
- [x] Format: `%(asctime)s %(levelname)s %(name)s — %(message)s`
- [ ] Structured JSON logging for Railway (TODO: add python-json-logger)

### Log Levels
- Production: INFO
- Development: DEBUG
- Critical errors: ERROR with stack traces

## Performance

### Database
- [x] SQLite for development
- [ ] PostgreSQL for production (Railway addon)
- [ ] Connection pooling (SQLAlchemy default)
- [ ] Indexes on foreign keys (SQLModel auto-creates)

### AI API
- [x] Prompt caching enabled (analyzer system prompt)
- [x] Parallel scraping (asyncio.gather)
- [ ] Request timeout: 30s for scrapers, 60s for AI

### Caching
- [ ] Redis for session storage (optional, future enhancement)
- [ ] CDN for static assets (optional, Tailwind CDN already used)

## Monitoring

### Metrics to Track
- [ ] Request rate (/inquiry submissions per hour)
- [ ] Pipeline success rate (inquiries → reports sent)
- [ ] AI API latency (analyzer + synthesizer)
- [ ] Scraper success rate (per source)
- [ ] Error rate (5xx responses)

### Alerting
- [x] Telegram notifications for critical errors
- [ ] Email alerts for pipeline failures (optional)
- [ ] Sentry for exception tracking (optional)

## Deployment

### Pre-Deploy Checklist
- [x] All tests passing (`pytest tests/ -q`)
- [x] Migrations generated (`alembic revision --autogenerate`)
- [ ] Environment variables set in Railway
- [ ] Database backup (if migrating from SQLite)
- [ ] Gmail OAuth credentials uploaded (if using Gmail)

### Railway Configuration
```bash
# Build command (railway.json)
pip install -r requirements.txt && playwright install chromium

# Start command
alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT

# Health check
GET /health (expect {"ok": true})
```

### Post-Deploy Verification
- [ ] `/health` returns 200 OK
- [ ] Submit test inquiry via `/form`
- [ ] Trigger search in dashboard
- [ ] Verify listings have photos
- [ ] Generate test report
- [ ] Create Gmail draft (or send via SMTP)
- [ ] Check Telegram notifications

## Rollback Plan

### If deployment fails:
1. Check Railway logs for errors
2. Verify environment variables
3. Roll back to previous deployment (Railway UI)
4. If DB migration failed: `alembic downgrade -1`

### If production issues:
1. Check `/health` endpoint
2. Review Railway logs
3. Verify Anthropic API status
4. Check scraper storage_state files
5. Test Gmail/SMTP connectivity

## Maintenance

### Weekly
- [ ] Review error logs
- [ ] Check scraper success rates
- [ ] Monitor AI API costs (Anthropic dashboard)

### Monthly
- [ ] Update dependencies (`pip list --outdated`)
- [ ] Review and archive old inquiries
- [ ] Backup database
- [ ] Rotate API keys (if policy requires)

### As Needed
- [ ] Update scraper selectors (when giełdy change layout)
- [ ] Refresh Gmail OAuth token (expires after 6 months)
- [ ] Update Playwright browsers (`playwright install chromium`)

## Security Audit

### Before Production
- [ ] Review all environment variables
- [ ] Audit third-party dependencies (`pip-audit`)
- [ ] Check for exposed secrets in git history
- [ ] Verify HTTPS enabled (Railway default)
- [ ] Test rate limiting effectiveness
- [ ] Review CORS settings (if adding frontend API)

## Documentation

### Updated Files
- [x] README.md - Setup and configuration
- [x] TESTING.md - Test procedures
- [x] CLAUDE.md - Architecture and guidelines
- [x] RAILWAY_DEPLOYMENT.md - Deployment guide
- [x] PRODUCTION_CHECKLIST.md - This file

### Missing Documentation
- [ ] API documentation (if exposing public API)
- [ ] Runbook for common issues
- [ ] Disaster recovery procedures
