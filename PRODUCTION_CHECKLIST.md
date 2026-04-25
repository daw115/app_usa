# Production Readiness Checklist

Stan: **2026-04-25**, branch `claude/sweet-allen-41aca0`. Cel: deployment Railway.

## ⚠️ Najpierw: rotacja sekretów (BLOCKER)

Sekrety wyciekły do gita w commicie `1a746ad` (pliki `RAILWAY_DEPLOYMENT_STATUS.md`, `RAILWAY_QUICK_START.md`). Wycieki w aktualnym HEAD są usunięte, **ale nadal są w historii**.

### Akcja Janka/Dawida (wymagana ręcznie)

1. **Zrotować klucze:**
   - `ANTHROPIC_API_KEY` w panelu Anthropic / proxy (`api.quatarly.cloud`)
   - `TELEGRAM_BOT_TOKEN` w @BotFather → `/revoke` → `/newtoken`
2. **Wyczyścić git history** (jedna z opcji):
   ```bash
   # Opcja A: BFG (najszybsza)
   bfg --replace-text passwords.txt   # plik z mapowaniem stary→***REMOVED***
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   git push --force-with-lease

   # Opcja B: git-filter-repo
   git filter-repo --replace-text passwords.txt
   git push --force-with-lease
   ```
3. **Wpisać nowe klucze tylko w Railway → Variables**, nigdy do repo.
4. **(Opcjonalnie) Powiadomić Anthropic / proxy provider** o wycieku starego klucza.

---

## Environment Variables

### Wymagane
- [x] `ANTHROPIC_API_KEY` — walidowane na startupie (RuntimeError jeśli puste)
- [x] `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- [x] `DATABASE_URL` — Railway PostgreSQL addon (auto)

### Email
- [x] `EMAIL_PROVIDER=gmail` lub `smtp` (dispatcher w `backend/services/gmail.py:send_email`)
- [ ] Gmail OAuth: `GMAIL_CLIENT_SECRETS`, `GMAIL_TOKEN_PATH` (musisz wgrać `gmail_client_secret.json` na Railway)
- [x] SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

### Observability
- [x] `SENTRY_DSN` — opcjonalny, jeśli pusty → Sentry pominięty
- [x] `ENVIRONMENT=production`
- [x] `LOG_FORMAT=json` na Railway, `text` lokalnie

### Resource limits (mają sensowne defaulty)
- [x] `PLAYWRIGHT_TIMEOUT=30000`, `SCRAPER_PAGE_TIMEOUT=15000`
- [x] `AI_TIMEOUT_SECONDS=60`, `AI_MAX_PHOTOS=6`
- [x] `SCRAPER_DAILY_LIMIT=30`

### Scraper auth (opcjonalne — sesje z `playwright_profiles/`)
- [ ] `COPART_USERNAME/PASSWORD`, `IAAI_*`, `AMERPOL_*`
- [ ] `SCRAPERAPI_KEY` (fallback dla Copart)

---

## Database Migrations

```bash
# Lokalnie (SQLite)
DATABASE_URL=sqlite:///./app.db alembic upgrade head

# Produkcja: entrypoint.sh wywołuje `alembic upgrade head` przed startem uvicorna.
```

**Migracje (3):**
1. `395befaef905_initial_schema.py` — schemat bazowy, **dialect-aware** (PG + SQLite).
2. `2a9c1f3b8d44_add_missing_indexes.py` — indeksy zgodne z modelami + UNIQUE constraints.
3. `3b7e2a4f9c11_add_scraper_run.py` — tabela rate-limitowania scraperów.

---

## Security

### Rate Limiting
- [x] `/inquiry` endpoint: 10 req/h per IP (slowapi)
- [x] **Scraper rate limiting**: 30 wyszukiwań/dzień per source (ScraperRun + `services/rate_limit.py`)

### Sekrety
- [x] `.env` w `.gitignore`
- [x] `.env.example` z placeholderami (NIE z prawdziwymi wartościami)
- [ ] Sekrety zrotowane i historia git wyczyszczona — **patrz wyżej**

---

## Error Handling & Health

- [x] Startup validation: `ANTHROPIC_API_KEY` required
- [x] Per-scraper try/catch + `asyncio.wait_for` (90s timeout)
- [x] AI analyzer: per-listing timeout (`config.ai_timeout_seconds`)
- [x] Telegram errors logowane, nie blokują flow
- [x] **Sentry** (jeśli `SENTRY_DSN` ustawione) — wszystkie 5xx + nieobsłużone wyjątki

### Health check
- [x] `/health` zwraca **HTTP 503** przy błędzie DB/API (Railway poprawnie wykryje fail)
- [x] Railway healthcheck: `path=/health`, `timeout=300s`

---

## Logging

- [x] Format JSON na Railway (`LOG_FORMAT=json` + `python-json-logger`)
- [x] Format tekstowy lokalnie
- [x] `request_id` w każdym logu (middleware + factory)
- [x] Request ID w response header `X-Request-ID`

---

## Performance

- [x] PostgreSQL na produkcji (Railway addon), SQLite lokalnie
- [x] Indeksy na FK + częstych filtrach (z migracji 2)
- [x] Prompt caching dla analyzera (system prompt z `cache_control: ephemeral`)
- [x] Równoległe scraping (`asyncio.gather` 3 źródeł)
- [x] Równoległa analiza AI (`asyncio.gather` po listingach)
- [x] Per-call timeouty: 90s scraper, 60s AI
- [x] In-memory cache dla AI analizy (TTL 24h, klucz: VIN+photos hash)

---

## Deployment (Railway)

### Konfiguracja
- [x] `railway.json` — builder DOCKERFILE, healthcheckPath `/health`, restart on failure
- [x] `Dockerfile` — Python 3.9-slim + Playwright + entrypoint
- [x] `entrypoint.sh` — chmod +x w git, fallback `PORT=8000`, runs `alembic upgrade head` + uvicorn
- [x] `nixpacks.toml` **usunięty** (kolizja z Dockerfile)

### Pre-deploy
- [x] `pytest tests/ backend/tests/` → 27 passed
- [x] `alembic upgrade head` smoke test na SQLite ✅
- [ ] Railway Variables ustawione (rotowane klucze!)
- [ ] PostgreSQL addon podłączony

### Post-deploy
- [ ] `curl https://<app>.up.railway.app/health` → `{"ok":true,...}`
- [ ] Submit test inquiry przez `/form`
- [ ] Trigger search w dashboardzie → sprawdzić czy `scraper_run` rośnie
- [ ] Sprawdzić Sentry dashboard (jeśli skonfigurowane)
- [ ] Telegram: powiadomienie o nowym inquiry

---

## Outstanding Work (post-launch)

1. **Scraper selektory** — Copart/IAAI mogą wymagać kalibracji na żywej stronie (test_copart_photos.py)
2. **Backup PostgreSQL** — Railway robi automatyczne snapshoty, ale warto eksportować weekly do osobnego storage
3. **Klient portal** `/track/{id}/{token}` — endpoint i template (jest tracking_token w modelu)
4. **Dashboard enhancements** — filtry/sortowanie, porównywanie aut
5. **Analytics** — `/analytics` dla Janka

---

## Rollback

```bash
# Railway: rollback do poprzedniego deploymentu w dashboardzie

# Lokalnie:
alembic downgrade -1   # cofa ostatnią migrację
```
