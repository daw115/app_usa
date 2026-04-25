# AutoScout US - Setup Checklist

Quick reference dla konfiguracji aplikacji.

## Pre-Installation

- [ ] Python 3.9+ zainstalowany (`python3 --version`)
- [ ] Git zainstalowany (`git --version`)
- [ ] ~500MB wolnego miejsca na dysku
- [ ] Połączenie internetowe

## Installation

- [ ] Sklonowano repo: `git clone https://github.com/daw115/app_usa.git`
- [ ] Utworzono venv: `python3 -m venv .venv`
- [ ] Aktywowano venv: `source .venv/bin/activate`
- [ ] Zainstalowano dependencies: `pip install -r requirements.txt`
- [ ] Zainstalowano Playwright: `playwright install chromium`

## Configuration

### Wymagane

- [ ] Skopiowano `.env.example` → `.env`
- [ ] **Anthropic API Key** dodany do `.env`
  - Zarejestrowano na https://console.anthropic.com
  - Utworzono API key
  - Dodano `ANTHROPIC_API_KEY=sk-ant-...`

### Opcjonalne (ale zalecane)

- [ ] **Telegram Bot** skonfigurowany
  - Utworzono bota przez @BotFather
  - Uzyskano Chat ID przez @userinfobot
  - Dodano `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID`

- [ ] **Email Provider** wybrany i skonfigurowany
  - **Opcja A: Gmail OAuth**
    - [ ] Utworzono projekt w Google Cloud Console
    - [ ] Włączono Gmail API
    - [ ] Pobrано `gmail_client_secret.json`
    - [ ] Ustawiono `EMAIL_PROVIDER=gmail`
  - **Opcja B: SMTP**
    - [ ] Ustawiono `EMAIL_PROVIDER=smtp`
    - [ ] Dodano `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`

- [ ] **Scrapers Credentials** dodane
  - [ ] Zarejestrowano na Copart.com
  - [ ] Zarejestrowano na IAAI.com
  - [ ] Zarejestrowano na Amerpol.com
  - [ ] Dodano credentials do `.env`

## Database Setup

- [ ] Uruchomiono migracje: `alembic upgrade head`
- [ ] Plik `app.db` utworzony w głównym katalogu

## Scrapers Login

- [ ] Zapisano sesję Copart: `python -m backend.services.scrapers.login_helper copart`
- [ ] Zapisano sesję IAAI: `python -m backend.services.scrapers.login_helper iaai`
- [ ] Zapisano sesję Amerpol: `python -m backend.services.scrapers.login_helper amerpol`

## Verification

- [ ] Uruchomiono weryfikację: `python verify_config.py`
- [ ] Wszystkie wymagane komponenty ✓
- [ ] Opcjonalne komponenty skonfigurowane według potrzeb

## First Run

- [ ] Backend uruchomiony: `uvicorn backend.main:app --reload`
- [ ] Dashboard otwarty: http://localhost:8000
- [ ] Utworzono testowe zapytanie
- [ ] Wyszukiwanie działa
- [ ] AI analysis działa
- [ ] Raport generuje się poprawnie

## Production (opcjonalnie)

- [ ] Cloudflared zainstalowany (dla publicznego URL)
- [ ] Tunnel uruchomiony: `cloudflared tunnel --url http://localhost:8000`
- [ ] URL publiczny skopiowany i przetestowany
- [ ] Formularz klienta działa: `https://xxx.trycloudflare.com/form`

## Troubleshooting

Jeśli coś nie działa:

1. Sprawdź logi w terminalu gdzie uruchomiony jest uvicorn
2. Uruchom `python verify_config.py` aby zdiagnozować problem
3. Zobacz SETUP.md sekcja "Troubleshooting"
4. Sprawdź czy venv jest aktywowany: `which python`

## Maintenance

- [ ] Sesje scraperów odświeżane co ~30 dni
- [ ] Gmail token odświeżany co ~6 miesięcy (automatycznie)
- [ ] Selektory CSS scraperów aktualizowane gdy giełdy zmieniają strony
- [ ] Backup bazy danych regularnie (jeśli używasz SQLite)

## Next Steps

Po zakończeniu setup:

1. Przeczytaj README.md dla szczegółów użytkowania
2. Zobacz SETUP.md dla zaawansowanej konfiguracji
3. Przetestuj cały workflow z testowym zapytaniem
4. Skonfiguruj auto-search scheduler jeśli potrzebny
5. Dostosuj ustawienia pricing w `/settings`

---

**Szybki start:** `python3 setup.py` przeprowadzi przez większość tych kroków automatycznie.
