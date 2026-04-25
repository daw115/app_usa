# AutoScout US - Przewodnik Konfiguracji

Kompleksowy przewodnik setup aplikacji od zera do działającego systemu.

## Wymagania Systemowe

- **Python 3.9+** (sprawdź: `python3 --version`)
- **Git** (sprawdź: `git --version`)
- **~500MB** wolnego miejsca (dependencies + Playwright browser)
- **Połączenie internetowe** (instalacja, API calls)

## Szybki Start

```bash
# Uruchom interaktywny setup
python3 setup.py
```

Setup script przeprowadzi przez:
1. Sprawdzenie wersji Pythona
2. Utworzenie venv
3. Instalację dependencies
4. Konfigurację .env
5. Inicjalizację bazy danych

## Ręczna Konfiguracja (Krok po Kroku)

### 1. Środowisko Python

```bash
# Utwórz venv
python3 -m venv .venv

# Aktywuj venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Zainstaluj dependencies
pip install -r requirements.txt

# Zainstaluj Playwright browser
playwright install chromium
```

### 2. Konfiguracja .env

```bash
# Skopiuj template
cp .env.example .env

# Edytuj .env w swoim edytorze
nano .env  # lub vim, code, etc.
```

### 3. Anthropic API (WYMAGANE)

**Uzyskanie klucza:**
1. Zarejestruj się na https://console.anthropic.com
2. Przejdź do Settings → API Keys
3. Kliknij "Create Key"
4. Skopiuj klucz (zaczyna się od `sk-ant-`)

**W .env:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxx...
```

**Pricing (styczeń 2026):**
- Claude Sonnet 4.6: $3/$15 per 1M tokens (input/output)
- Claude Opus 4.7: $15/$75 per 1M tokens
- Prompt caching: 90% taniej dla cached content

**Szacowany koszt:**
- Analiza 1 auta (6 zdjęć): ~$0.15-0.30
- Raport dla 5 aut: ~$1-2
- Miesięcznie (50 zapytań): ~$50-100

### 4. Telegram Bot (OPCJONALNE)

**Tworzenie bota:**
1. Otwórz Telegram, znajdź @BotFather
2. Wyślij `/newbot`
3. Podaj nazwę (np. "AutoScout US Bot")
4. Podaj username (np. "autoscout_us_bot")
5. Skopiuj token (format: `123456:ABC-DEF...`)

**Uzyskanie Chat ID:**
1. Znajdź @userinfobot w Telegram
2. Wyślij `/start`
3. Bot zwróci twój Chat ID (liczba, np. `123456789`)

**W .env:**
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

**Test:**
```bash
# Po uruchomieniu aplikacji
curl -X POST http://localhost:8000/api/test-telegram
```

### 5. Email - Opcja A: Gmail OAuth (ZALECANE)

**Setup w Google Cloud Console:**

1. Przejdź do https://console.cloud.google.com
2. Utwórz nowy projekt lub wybierz istniejący
3. Włącz Gmail API:
   - APIs & Services → Library
   - Szukaj "Gmail API"
   - Kliknij Enable

4. Utwórz OAuth credentials:
   - APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Name: "AutoScout US"
   - Download JSON

5. Zapisz pobrany plik jako `gmail_client_secret.json` w głównym katalogu projektu

**W .env:**
```bash
EMAIL_PROVIDER=gmail
GMAIL_CLIENT_SECRETS=./gmail_client_secret.json
GMAIL_TOKEN_PATH=./gmail_token.json
```

**Pierwsze użycie:**
- Przy pierwszym tworzeniu draftu otworzy się przeglądarka
- Zaloguj się na konto Gmail
- Zatwierdź uprawnienia
- Token zostanie zapisany w `gmail_token.json` (ważny 6 miesięcy)

**Uwaga:** Gmail tworzy DRAFTY (nie wysyła automatycznie)

### 5. Email - Opcja B: SMTP

**Dla popularnych providerów:**

**Gmail SMTP:**
```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # NIE zwykłe hasło!
SMTP_FROM=your-email@gmail.com
```

Uwaga: Wymaga "App Password" z Google Account settings

**ATT Mail:**
```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=outbound.att.net
SMTP_PORT=465
SMTP_USER=your-email@att.net
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@att.net
```

**Outlook/Office365:**
```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
```

**Uwaga:** SMTP wysyła BEZPOŚREDNIO (bez draftu)

### 6. Scrapers - Credentials Giełd

**Copart (https://copart.com):**
1. Zarejestruj się jako "Member" (darmowe)
2. Potwierdź email
3. Zaloguj się i sprawdź że działa

**IAAI (https://iaai.com):**
1. Zarejestruj się jako "Guest Buyer"
2. Potwierdź email
3. Zaloguj się i sprawdź że działa

**Amerpol (https://amerpol.com):**
1. Zarejestruj konto
2. Potwierdź email
3. Zaloguj się i sprawdź że działa

**W .env:**
```bash
COPART_USERNAME=your-email@example.com
COPART_PASSWORD=your-password
IAAI_USERNAME=your-email@example.com
IAAI_PASSWORD=your-password
AMERPOL_USERNAME=your-email@example.com
AMERPOL_PASSWORD=your-password
```

**ScraperAPI (opcjonalnie):**
- Dla Copart przez proxy (jeśli blokuje)
- Zarejestruj się na https://scraperapi.com
- Darmowy tier: 1000 requests/miesiąc

```bash
SCRAPERAPI_KEY=your-key
```

### 7. Zapisanie Sesji Logowania

Po skonfigurowaniu credentials, zapisz sesje:

```bash
# Aktywuj venv jeśli nie jest aktywowany
source .venv/bin/activate

# Zaloguj się do każdej giełdy (otworzy przeglądarkę)
python -m backend.services.scrapers.login_helper copart
python -m backend.services.scrapers.login_helper iaai
python -m backend.services.scrapers.login_helper amerpol
```

Każdy helper:
1. Otworzy przeglądarkę Playwright
2. Przejdzie do strony logowania
3. Poczekaj aż się zalogujesz ręcznie
4. Zamknij przeglądarkę
5. Sesja zostanie zapisana w `backend/services/scrapers/sessions/`

**Ważność sesji:** ~30 dni (potem powtórz login_helper)

### 8. Inicjalizacja Bazy Danych

```bash
# Uruchom migracje
alembic upgrade head
```

Utworzy `app.db` (SQLite) w głównym katalogu.

**Dla PostgreSQL:**
```bash
# W .env ustaw DATABASE_URL zamiast DB_PATH
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

## Uruchomienie

### Backend

```bash
# Aktywuj venv
source .venv/bin/activate

# Uruchom serwer
uvicorn backend.main:app --reload
```

Serwer dostępny na: http://localhost:8000

### Frontend (opcjonalnie, dla development)

Frontend jest renderowany przez backend (Jinja templates).
Dla development z hot-reload:

```bash
cd frontend
npm install
npm run dev
```

## Weryfikacja Konfiguracji

```bash
# Uruchom skrypt weryfikacji
python verify_config.py
```

Sprawdzi:
- ✓ Połączenie z Anthropic API
- ✓ Telegram bot token i chat_id
- ✓ Dostęp do bazy danych
- ✓ Scrapers credentials (opcjonalnie)

## Publiczny URL (dla klientów)

Aby klienci mogli wypełniać formularz z telefonu:

```bash
# Zainstaluj cloudflared
brew install cloudflare/cloudflare/cloudflared  # macOS
# lub pobierz z https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

# Uruchom tunnel
cloudflared tunnel --url http://localhost:8000
```

Skopiuj URL (format: `https://xxx.trycloudflare.com`) i wyślij klientowi:
```
https://xxx.trycloudflare.com/form
```

**Uwaga:** URL zmienia się przy każdym uruchomieniu cloudflared

## Troubleshooting

### "ModuleNotFoundError: No module named 'anthropic'"
```bash
# Sprawdź czy venv jest aktywowany
which python  # powinno pokazać .venv/bin/python

# Jeśli nie, aktywuj
source .venv/bin/activate

# Reinstaluj dependencies
pip install -r requirements.txt
```

### "playwright._impl._errors.Error: Executable doesn't exist"
```bash
# Zainstaluj Playwright browsers
playwright install chromium
```

### "anthropic.AuthenticationError: Invalid API key"
- Sprawdź czy klucz w .env zaczyna się od `sk-ant-`
- Sprawdź czy nie ma spacji przed/po kluczu
- Wygeneruj nowy klucz w console.anthropic.com

### "Telegram bot not responding"
```bash
# Test bota przez curl
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Powinno zwrócić JSON z danymi bota
```

### "Gmail OAuth nie działa"
- Sprawdź czy `gmail_client_secret.json` istnieje
- Sprawdź czy Gmail API jest włączone w Google Cloud Console
- Usuń `gmail_token.json` i spróbuj ponownie (wymusi re-auth)

### "Scrapers zwracają puste wyniki"
- Selektory CSS mogą być nieaktualne (giełdy zmieniają strony)
- Sprawdź `backend/services/scrapers/copart.py` (i inne)
- Zaktualizuj selektory patrząc na HTML strony
- Alternatywnie: dodaj URL ręcznie w dashboardzie

### "Database locked"
- SQLite nie obsługuje wielu jednoczesnych zapisów
- Dla production użyj PostgreSQL:
  ```bash
  DATABASE_URL=postgresql://user:pass@localhost/dbname
  ```

## Bezpieczeństwo

### Rate Limiting
- Max ~30 zapytań/dzień na giełdę
- Jitter 1.5-4s między requestami
- Używamy zapisanych sesji (nie logujemy się za każdym razem)

### Credentials
- **NIGDY** nie commituj `.env` do git
- `.env` jest w `.gitignore`
- Dla production użyj secrets managera (AWS Secrets, Vault, etc.)

### API Keys
- Anthropic: ustaw spending limits w console
- Telegram: bot token daje pełny dostęp do bota
- Gmail: OAuth token ma ograniczone uprawnienia (tylko drafts)

## Następne Kroki

1. Otwórz dashboard: http://localhost:8000
2. Kliknij "Nowe zapytanie" i wypełnij formularz
3. Kliknij "🔍 Szukaj na giełdach"
4. Poczekaj na wyniki (2-5 minut)
5. Przejrzyj kandydatów
6. Kliknij "📝 Generuj raport"
7. Edytuj raport
8. Kliknij "📧 Utwórz draft w Gmailu"
9. Sprawdź draft w Gmail i wyślij
10. Oznacz jako wysłane

## Wsparcie

- Dokumentacja: README.md
- Issues: https://github.com/daw115/app_usa/issues
- Logi: sprawdź terminal gdzie uruchomiony jest uvicorn
