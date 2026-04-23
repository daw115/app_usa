# Railway Deployment Guide

## Przygotowanie

1. **Utwórz konto na Railway.app**
   - Zaloguj się przez GitHub

2. **Utwórz nowy projekt**
   - New Project → Deploy from GitHub repo
   - Wybierz ten repository

3. **Dodaj PostgreSQL**
   - Add Service → Database → PostgreSQL
   - Railway automatycznie ustawi zmienną `DATABASE_URL`

## Zmienne środowiskowe

W Railway Dashboard → Variables dodaj:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
PUBLIC_FORM_BASE_URL=https://twoja-domena.railway.app
```

**Opcjonalne (Gmail):**
```
GMAIL_CLIENT_SECRETS=<zawartość gmail_client_secret.json jako string>
GMAIL_TOKEN_PATH=/tmp/gmail_token.json
```

## Ograniczenia na Railway

### ❌ Scrapery NIE BĘDĄ DZIAŁAĆ
- Playwright wymaga GUI/Chrome
- Railway nie ma wsparcia dla headless browsers bez dodatkowej konfiguracji
- **Rozwiązanie:** Używaj funkcji "Dodaj aukcję ręcznie" w dashboardzie

### ✅ Co BĘDZIE działać:
- Dashboard (przeglądanie zapytań)
- Formularz klienta
- Ręczne dodawanie aukcji z URL
- Analiza AI (Claude Sonnet 4.6)
- Generowanie raportów (Claude Opus 4.7)
- Gmail drafts
- Telegram notifications
- PostgreSQL database (persistent)

## Deploy

Railway automatycznie:
1. Wykryje Python
2. Zainstaluje dependencies z `requirements.txt`
3. Uruchomi `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

## Po deploy

1. Otwórz URL Railway (np. `https://app-usa-production.up.railway.app`)
2. Dashboard: `https://twoja-domena.railway.app/`
3. Formularz: `https://twoja-domena.railway.app/form`

## Alternatywa: Lokalne uruchomienie + Cloudflare Tunnel

Jeśli potrzebujesz scraperów:

```bash
# Terminal 1: Uruchom aplikację lokalnie
source .venv/bin/activate
uvicorn backend.main:app --reload

# Terminal 2: Expose przez Cloudflare
cloudflared tunnel --url http://localhost:8000
```

Cloudflare da Ci publiczny URL (np. `https://abc-def.trycloudflare.com`) który możesz wysłać klientom.

**Zalety:**
- Wszystko działa (scrapery, sesje logowania, SQLite)
- Darmowe
- Nie wymaga zmian w kodzie

**Wady:**
- Musisz mieć komputer włączony
- URL zmienia się przy każdym restarcie (chyba że kupisz stały tunel)
