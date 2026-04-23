# AutoScout US

Lokalna aplikacja do automatyzacji sprzedaży aut z amerykańskich giełd
(Copart / IAAI / Amerpol) polskim klientom. Klient wypełnia formularz →
scraper szuka aut → Claude analizuje zdjęcia szkód i wycenia naprawę →
synthesizer generuje raport-ofertę → Janek zatwierdza w dashboardzie i
wysyła draftem Gmaila.

## Szybki start

```bash
# 1. Venv + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Konfiguracja
cp .env.example .env
# wpisz ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# 3. Zaloguj się ręcznie do giełd (otworzy się okno przeglądarki)
python -m backend.services.scrapers.login_helper amerpol
python -m backend.services.scrapers.login_helper copart
python -m backend.services.scrapers.login_helper iaai

# 4. OAuth do Gmaila — pobierz gmail_client_secret.json z Google Cloud
#    (OAuth 2.0 Client ID → Desktop app), umieść w katalogu projektu.
#    Pierwsze uruchomienie "Utwórz draft" otworzy konsent w przeglądarce.

# 5. Start
uvicorn backend.main:app --reload

# 6. Publiczny URL dla klientów
cloudflared tunnel --url http://localhost:8000
# skopiuj URL *.trycloudflare.com/form — to wysyłasz klientowi
```

Dashboard dla Janka: <http://localhost:8000/>
Formularz klienta: `<publiczny-url>/form`

## Przepływ pracy

1. Klient dzwoni. Janek mówi "wysyłam formularz", SMS-uje link.
2. Klient wypełnia formularz → Telegram ping do Janka.
3. Janek klika **🔍 Szukaj na giełdach** w dashboardzie.
4. Pipeline: scrape → analyze (Claude Sonnet 4.6 z prompt cachingiem) →
   ranking w oparciu o score szkody i koszt całkowity w PLN.
5. Janek przegląda kandydatów, opcjonalnie **Ukryj** niepasujące.
6. Klika **📝 Generuj raport** → Claude Opus 4.7 pisze email (tabela +
   komentarze + rekomendacja).
7. Edytuje w panelu, klika **📧 Utwórz draft w Gmailu**.
8. Otwiera swoją skrzynkę Gmail, sprawdza draft i klika Wyślij.
9. Klika **✅ Oznacz jako wysłane**.

## Kalkulacja kosztu (`/settings`)

`total_pln = (auction + agent + transport) * kurs + cło + akcyza + VAT +
naprawa_z_zapasem + marża`

Wszystkie stawki są konfigurowalne. Domyślnie kurs USD pobierany
automatycznie z NBP przed każdym wyszukiwaniem.

## Scrapery

Selektory CSS dla Copart/IAAI/Amerpol są szkieletem — strony giełd
zmieniają się co kilka miesięcy. Po pierwszym uruchomieniu sprawdź, czy
`backend.services.scrapers.*` zwracają dane; jeśli nie, zaktualizuj
selektory w plikach `copart.py`, `iaai.py`, `amerpol.py`.

**Bezpieczeństwo kont:** max ~30 zapytań/dzień, jitter 1.5-4s między
requestami. Używamy **zapisanych sesji logowania** (Playwright
`storage_state`) zamiast ponownego logowania przy każdym uruchomieniu.

Awaryjnie — w szczegółach zapytania jest pole **Dodaj URL ręcznie**;
można wkleić link do aukcji i pominąć scraper.

## Testy

```bash
pytest tests/ -q
```

## Struktura

- `backend/main.py` — FastAPI entrypoint
- `backend/models.py` — Inquiry / Listing / Report / Settings (SQLModel)
- `backend/routes/public.py` — publiczny formularz
- `backend/routes/dashboard.py` — panel Janka
- `backend/services/analyzer.py` — Claude Sonnet 4.6, prompt caching
- `backend/services/synthesizer.py` — Claude Opus 4.7, finalny raport
- `backend/services/pricing.py` — kalkulator PLN (czysta funkcja,
  testowalna)
- `backend/services/telegram_bot.py` — push powiadomień
- `backend/services/gmail.py` — OAuth + drafts
- `backend/services/scrapers/` — Copart / IAAI / Amerpol (Playwright)
- `backend/tasks.py` — orkiestracja: search → analyze → rank →
  synthesize → draft
- `frontend/` — formularz + dashboard (Jinja + Tailwind CDN + HTMX)

## Znane ograniczenia MVP

- **Bez auto-wysyłki maili** — zawsze draft do zatwierdzenia.
- **Bez monitorowania skrzynki Gmail** (zapytania mailowe Janek
  przepisuje ręcznie do formularza w panelu).
- **Bez transkrypcji rozmów** — Janek dalej odbiera telefony; klienci
  mogą jednak wypełnić formularz samodzielnie z linka SMS.
- **Scrapery szkieletowe** — selektory wymagają kalibracji na żywej
  stronie każdej giełdy.
