# Gmail OAuth Setup

## 1. Google Cloud Console

1. Otwórz https://console.cloud.google.com
2. Utwórz nowy projekt lub wybierz istniejący
3. Włącz Gmail API:
   - APIs & Services → Library
   - Szukaj "Gmail API" → Enable

## 2. OAuth Credentials

1. APIs & Services → Credentials → Create Credentials → OAuth client ID
2. Application type: **Desktop app**
3. Name: "AutoScout US"
4. Download JSON → zapisz jako `gmail_client_secret.json` w katalogu projektu

## 3. OAuth Consent Screen

1. APIs & Services → OAuth consent screen
2. User Type: **External**
3. App name: "AutoScout US"
4. User support email: usacarsbitches@proton.me
5. Developer contact: usacarsbitches@proton.me
6. Scopes → Add: `gmail.compose`, `gmail.send`
7. Test users → Add: usacarsbitches@proton.me

## 4. Pierwsze uruchomienie

```bash
cd /Users/dawidslabicki/Documents/Claude/app_usa
source .venv/bin/activate
uvicorn backend.main:app --reload
```

Otwórz http://localhost:8000/inquiry/1 → wygeneruj raport → kliknij "Utwórz draft w Gmailu"

Otworzy się przeglądarka z OAuth consent → zaloguj się na usacarsbitches@proton.me → Allow

Token zostanie zapisany w `gmail_token.json` i będzie działać przez ~7 dni.
