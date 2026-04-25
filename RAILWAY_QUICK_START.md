# Railway Deployment - Quick Start

## 1. Utwórz projekt Railway

1. Zaloguj się na https://railway.app
2. Kliknij "New Project" → "Deploy from GitHub repo"
3. Wybierz repository: `daw115/app_usa`
4. Railway automatycznie wykryje Python i zacznie deployment

## 2. Dodaj PostgreSQL Database

1. W Railway dashboard → "New" → "Database" → "Add PostgreSQL"
2. Railway automatycznie ustawi zmienną `DATABASE_URL`

## 3. Skonfiguruj zmienne środowiskowe

W Railway → Variables, dodaj:

```
ANTHROPIC_API_KEY=<REDACTED-ANTHROPIC-KEY>
ANTHROPIC_BASE_URL=https://api.quatarly.cloud/v1
TELEGRAM_BOT_TOKEN=<REDACTED-TELEGRAM-TOKEN>
TELEGRAM_CHAT_ID=<REDACTED-TELEGRAM-CHAT-ID>
EMAIL_PROVIDER=smtp
SMTP_HOST=outbound.att.net
SMTP_PORT=465
SMTP_USER=your-email@att.net
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@att.net
```

## 4. Skonfiguruj Build & Start Commands

W Railway → Settings:

**Build Command:**
```bash
pip install -r requirements.txt && playwright install chromium
```

**Start Command:**
```bash
alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## 5. Health Check

Railway → Settings → Health Check:
- Path: `/health`
- Timeout: 100s

## 6. Deploy

Railway automatycznie zdeployuje po pushu do `main`. Sprawdź:
- Logs: Railway → Deployments → View Logs
- URL: Railway wygeneruje publiczny URL (np. `app-usa-production.up.railway.app`)

## 7. Po deployment

1. Sprawdź health: `https://your-app.railway.app/health`
2. Otwórz dashboard: `https://your-app.railway.app/`
3. Formularz klienta: `https://your-app.railway.app/form`

## Troubleshooting

Jeśli deployment failuje:
1. Sprawdź Railway logs
2. Zweryfikuj zmienne środowiskowe
3. Upewnij się że PostgreSQL jest podłączony
4. Sprawdź czy migrations się wykonały (`alembic upgrade head`)
