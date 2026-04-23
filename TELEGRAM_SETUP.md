# Telegram Bot Setup

## 1. Utwórz bota

1. Otwórz Telegram i znajdź **@BotFather**
2. Wyślij `/newbot`
3. Podaj nazwę bota (np. "AutoScout US Bot")
4. Podaj username (np. "autoscout_us_bot")
5. BotFather da Ci **token** - skopiuj go

Przykład tokena: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## 2. Znajdź swój Chat ID

1. Wyślij wiadomość do swojego bota (dowolną)
2. Otwórz w przeglądarce:
   ```
   https://api.telegram.org/bot<TWÓJ_TOKEN>/getUpdates
   ```
3. Znajdź `"chat":{"id":123456789}` - to Twój Chat ID

## 3. Dodaj do .env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

## 4. Test

```bash
cd /Users/dawidslabicki/Documents/Claude/app_usa
source .venv/bin/activate
python -c "
from backend.services.telegram_bot import notify_new_inquiry
import asyncio
asyncio.run(notify_new_inquiry(1))
"
```

Powinieneś dostać wiadomość na Telegramie.
