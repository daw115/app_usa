# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoScout US — lokalna aplikacja do automatyzacji sprzedaży aut z amerykańskich giełd (Copart/IAAI/Amerpol) polskim klientom. Klient wypełnia formularz → scraper szuka aut → Claude Sonnet 4.6 analizuje zdjęcia szkód i wycenia naprawę → Claude Opus 4.7 generuje raport-ofertę → Janek (dealer) zatwierdza w dashboardzie i wysyła draftem Gmaila.

**Stack:** FastAPI + SQLModel (SQLite) + Jinja2 + Tailwind CDN + Playwright (scrapery) + Anthropic SDK

## Development Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Configuration
cp .env.example .env
# Wypełnij: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Login do giełd (zapisuje sesję Playwright)
python -m backend.services.scrapers.login_helper amerpol
python -m backend.services.scrapers.login_helper copart
python -m backend.services.scrapers.login_helper iaai

# Gmail OAuth setup
# Pobierz gmail_client_secret.json z Google Cloud (OAuth 2.0 Client ID → Desktop app)
# Pierwsze uruchomienie "Utwórz draft" otworzy consent w przeglądarce

# Run server
uvicorn backend.main:app --reload

# Publiczny URL dla klientów (cloudflared tunnel)
cloudflared tunnel --url http://localhost:8000
# Skopiuj URL *.trycloudflare.com/form

# Tests
pytest tests/ -q
pytest tests/test_pricing.py -v  # single test file
```

## Architecture

### Data Flow Pipeline (backend/tasks.py)

`run_search_pipeline(inquiry_id)` — główna orkiestracja:
1. **Scraping** — równolegle wywołuje `amerpol.search()`, `copart.search()`, `iaai.search()` z `SearchCriteria`
2. **Persist** — zapisuje `ScrapedListing` → `Listing` (SQLModel) z `photos_json`
3. **Analysis** — dla każdego listingu z photos: `analyzer.analyze_listing()` (Claude Sonnet 4.6 + prompt caching) → zwraca JSON z `damage_score`, `repair_estimate_usd`, `ai_notes`
4. **Pricing** — `pricing.calculate()` (czysta funkcja) → `total_cost_pln` (aukcja + agent + transport + cło + akcyza + VAT + naprawa + marża)
5. **Ranking** — `_rank()` sortuje po `(damage_score, total_cost_pln)`, top 5 dostaje `recommended_rank`, reszta `excluded=True`
6. **Status update** — `inquiry.status = InquiryStatus.ready`

`generate_report(inquiry_id)` — generacja raportu:
1. Pobiera top 5 ranked listings
2. `synthesizer.synthesize_report()` (Claude Opus 4.7) → HTML email body (po polsku, tabela + komentarze + rekomendacja)
3. Zapisuje `Report` z `html_body`, `subject`, `selected_listing_ids`

### AI Integration

**Analyzer** (`backend/services/analyzer.py`):
- Model: `claude-sonnet-4-6`
- Input: listing metadata + max 6 zdjęć (base64)
- System prompt z **prompt caching** (`cache_control: ephemeral`) — oszczędza tokeny przy wielu analizach
- Output: JSON z `damage_score` (1-10), `repair_estimate_usd` (low/high), `ai_notes`, `red_flags`
- Konserwatywne wyceny (lepiej przeszacować niż zaskoczyć klienta)

**Synthesizer** (`backend/services/synthesizer.py`):
- Model: `claude-opus-4-7`
- Input: `Inquiry` + top 5 `Listing` (JSON payload)
- System prompt: "senior car import advisor", ton profesjonalny/ciepły, **bez wzmianek o AI**
- Output: HTML email (bez `<html>/<head>`, tylko inner content) — tabela + akapity + CTA

### Scrapers (`backend/services/scrapers/`)

**Wspólna baza** (`base.py`):
- `SearchCriteria` — make, model, year_from/to, budget_pln, mileage_max, damage_tolerance
- `ScrapedListing` — source, source_url, title, year, make, model, mileage, damage_primary/secondary, photos[], current_bid_usd, buy_now_usd
- `storage_state_path(source)` → `playwright_profiles/{source}.json` (zapisana sesja logowania)
- `jitter()` — random delay 1.5-4s (ochrona przed banem)

**Implementacje** (`copart.py`, `iaai.py`, `amerpol.py`):
- Playwright headless=False (dla debugowania)
- Ładują `storage_state` zamiast logowania przy każdym uruchomieniu
- Selektory CSS **szkieletowe** — wymagają kalibracji na żywej stronie (giełdy zmieniają layout co kilka miesięcy)
- `copart_scraperapi.py` — fallback przez ScraperAPI proxy (jeśli Copart blokuje)

**Znane problemy:**
- Copart: selektory zdjęć często zwracają 0 zdjęć → priorytet CRITICAL w DEVELOPMENT_PLAN.md
- IAAI: brak implementacji pobierania zdjęć
- Max ~30 zapytań/dzień per konto (bezpieczeństwo)

### Pricing (`backend/services/pricing.py`)

Czysta funkcja `calculate(auction_usd, repair_low_usd, repair_high_usd, settings)`:
```
repair_usd = midpoint(low, high) * (1 + safety_pct)
usd_subtotal = auction + agent_fee + transport
pln_before_taxes = usd_subtotal * usd_pln_rate
customs_pln = auction * usd_pln_rate * customs_pct
excise_pln = (customs_base + customs) * excise_pct
vat_pln = (customs_base + customs + excise) * vat_pct
total_pln = pln_before_taxes + customs + excise + vat + repair_pln + margin_pln
```

`fetch_nbp_usd_rate()` — pobiera kurs USD z NBP API (auto-refresh przed każdym wyszukiwaniem jeśli `settings.auto_usd_rate=True`)

### Routes

**Public** (`backend/routes/public.py`):
- `GET /form` — formularz klienta (Jinja2 template)
- `POST /inquiry` — zapisuje `Inquiry`, wysyła Telegram notification

**Dashboard** (`backend/routes/dashboard.py`):
- `GET /` — lista inquiries (filtr po status)
- `GET /inquiry/{id}` — szczegóły + listings + reports
- `POST /inquiry/{id}/search` — trigger `run_search_pipeline` (background task)
- `POST /inquiry/{id}/add_manual_url` — ręczne dodanie listingu (fallback gdy scraper nie działa)
- `POST /listing/{id}/analyze` — pojedyncza analiza AI (jeśli dodano ręcznie)
- `POST /listing/{id}/toggle` — ukryj/pokaż listing
- `POST /inquiry/{id}/generate_report` — trigger `generate_report`
- `GET /report/{id}/edit` — edytor raportu (WYSIWYG textarea)
- `POST /report/{id}/save` — zapisz edytowany raport
- `POST /report/{id}/draft_to_gmail` — utwórz draft w Gmailu (OAuth)
- `POST /report/{id}/mark_sent` — oznacz jako wysłane
- `GET /settings` + `POST /settings` — konfiguracja stawek/marży

### Database (`backend/models.py`)

SQLModel (SQLite default, PostgreSQL opcjonalnie przez `DATABASE_URL`):
- `Inquiry` — zapytanie klienta (client_name, client_email, make, model, budget_pln, damage_tolerance, status)
- `Listing` — znalezione auto (inquiry_id FK, source, source_url, vin, photos_json, ai_damage_score, ai_repair_estimate_usd_low/high, total_cost_pln, recommended_rank, excluded)
- `Report` — wygenerowany raport (inquiry_id FK, html_body, subject, selected_listing_ids, status, gmail_draft_id)
- `Settings` — singleton (id=1) z konfiguracją (transport_usd, agent_fee_usd, customs_pct, excise_pct, vat_pct, margin_pln, repair_safety_pct, usd_pln_rate, auto_usd_rate)

### Frontend (`frontend/`)

Jinja2 templates + Tailwind CDN + zero JavaScript (tylko HTML forms):
- `form.html` — publiczny formularz klienta
- `dashboard/index.html` — lista inquiries
- `dashboard/inquiry_detail.html` — szczegóły zapytania + listings grid + reports
- `dashboard/report_editor.html` — edytor HTML raportu (textarea)
- `dashboard/settings.html` — konfiguracja stawek

## Development Guidelines

### Scrapery
- **Zawsze testuj na żywej stronie** — selektory CSS są szkieletowe i wymagają aktualizacji
- Używaj `storage_state` zamiast logowania przy każdym uruchomieniu
- Dodaj `jitter()` między requestami (1.5-4s)
- Jeśli scraper zwraca 0 zdjęć → debug selektorów w `debug_copart_selectors.py`
- Fallback: pole "Dodaj URL ręcznie" w dashboardzie

### AI Prompts
- **Analyzer**: konserwatywne wyceny, `confidence: low` jeśli zdjęcia niewystarczające
- **Synthesizer**: ton ciepły/profesjonalny, **nigdy nie wspominaj "AI" ani "automatycznie wygenerowane"**
- Używaj prompt caching w analyzer (system prompt z `cache_control: ephemeral`)

### Pricing
- Funkcja `calculate()` jest czysta → łatwo testowalna (patrz `tests/test_pricing.py`)
- Wszystkie stawki konfigurowalne w `/settings`
- Kurs USD auto-refresh z NBP przed każdym wyszukiwaniem (jeśli `auto_usd_rate=True`)

### Background Tasks
- FastAPI `BackgroundTasks` dla długich operacji (scraping, AI analysis)
- `_run_async()` helper w `dashboard.py` — workaround dla asyncio w background tasks
- Telegram notifications: nowe zapytanie, raport gotowy, błędy

### Gmail Integration
- OAuth 2.0 (Desktop app) — `gmail_client_secret.json` z Google Cloud
- Pierwsze uruchomienie otwiera consent w przeglądarce → zapisuje `gmail_token.json`
- Tylko **drafty** (nigdy auto-send) — Janek zawsze zatwierdza przed wysyłką

### Testing
- `pytest tests/ -q` — wszystkie testy
- `tests/test_pricing.py` — unit testy dla `calculate()` (czysta funkcja, łatwo testowalna)
- Brak testów dla scraperów (wymagają żywej strony + logowania)

## Known Limitations (MVP)

- **Bez auto-wysyłki maili** — zawsze draft do zatwierdzenia
- **Bez monitorowania skrzynki Gmail** — zapytania mailowe Janek przepisuje ręcznie
- **Bez transkrypcji rozmów** — Janek odbiera telefony, klienci mogą wypełnić formularz z linka SMS
- **Scrapery szkieletowe** — selektory wymagają kalibracji na żywej stronie każdej giełdy
- **Copart zdjęcia** — obecnie 0 zdjęć (CRITICAL priority w DEVELOPMENT_PLAN.md)

## Next Steps (DEVELOPMENT_PLAN.md)

1. **Scraper improvements** (CRITICAL) — debug selektorów zdjęć Copart/IAAI
2. **Email integration** — SMTP dla ATT Mail lub Gmail OAuth
3. **Dashboard enhancements** — filtry, sortowanie, porównywanie aut
4. **Analytics** — statystyki dla Janka (zapytania/dzień, conversion rate, top modele)
5. **Automatyzacja** — cron job: auto-search dla nowych zapytań co 30 min
6. **Klient portal** — publiczny URL `/track/{inquiry_id}/{token}` do śledzenia statusu

## Deployment

Railway (patrz `RAILWAY_DEPLOYMENT.md`):
- `railway.json` — konfiguracja buildu
- `Dockerfile` — Python 3.9 + Playwright
- PostgreSQL addon (opcjonalnie, domyślnie SQLite)
- Zmienne środowiskowe: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`
