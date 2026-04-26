#!/usr/bin/env python3
"""
AutoScout US - Configuration Verification Script
Sprawdza czy wszystkie wymagane komponenty są poprawnie skonfigurowane
"""

import os
import sys
from pathlib import Path


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_check(name, status, message=""):
    symbol = "✓" if status else "✗"
    color = "\033[92m" if status else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {name}")
    if message:
        print(f"  → {message}")


def check_env_file():
    """Sprawdź czy .env istnieje"""
    env_path = Path(".env")
    if not env_path.exists():
        return False, "Plik .env nie istnieje. Uruchom: cp .env.example .env"
    return True, "Plik .env znaleziony"


def load_env():
    """Załaduj zmienne z .env"""
    env_path = Path(".env")
    env_vars = {}

    if not env_path.exists():
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def check_anthropic_api(api_key):
    """Sprawdź połączenie z Anthropic API"""
    if not api_key:
        return False, "ANTHROPIC_API_KEY nie jest ustawiony w .env"

    if not api_key.startswith("sk-ant-"):
        return False, "ANTHROPIC_API_KEY ma nieprawidłowy format (powinien zaczynać się od 'sk-ant-')"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Test API call
        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )

        return True, f"Połączenie OK (model: {response.model})"
    except ImportError:
        return False, "Pakiet 'anthropic' nie jest zainstalowany. Uruchom: pip install -r requirements.txt"
    except Exception as e:
        return False, f"Błąd API: {str(e)}"


def check_telegram_bot(bot_token, chat_id):
    """Sprawdź Telegram bot"""
    if not bot_token:
        return False, "TELEGRAM_BOT_TOKEN nie jest ustawiony (opcjonalne)"

    if not chat_id:
        return False, "TELEGRAM_CHAT_ID nie jest ustawiony (opcjonalne)"

    try:
        import httpx

        # Test bot token
        response = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=10.0
        )

        if response.status_code != 200:
            return False, f"Nieprawidłowy bot token (status: {response.status_code})"

        bot_data = response.json()
        if not bot_data.get("ok"):
            return False, "Bot token nie jest prawidłowy"

        bot_name = bot_data["result"]["username"]
        return True, f"Bot OK (@{bot_name})"

    except ImportError:
        return False, "Pakiet 'httpx' nie jest zainstalowany"
    except Exception as e:
        return False, f"Błąd: {str(e)}"


def check_database(db_path, database_url):
    """Sprawdź dostęp do bazy danych"""
    if database_url:
        # PostgreSQL
        try:
            import sqlmodel
            from sqlalchemy import create_engine

            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(sqlmodel.text("SELECT 1"))

            return True, "PostgreSQL połączenie OK"
        except ImportError:
            return False, "Pakiet 'sqlmodel' nie jest zainstalowany"
        except Exception as e:
            return False, f"Błąd PostgreSQL: {str(e)}"

    elif db_path:
        # SQLite
        db_file = Path(db_path)
        if not db_file.exists():
            return False, f"Baza SQLite nie istnieje: {db_path}. Uruchom: alembic upgrade head"

        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()

            if not tables:
                return False, "Baza jest pusta. Uruchom: alembic upgrade head"

            return True, f"SQLite OK ({len(tables)} tabel)"
        except Exception as e:
            return False, f"Błąd SQLite: {str(e)}"

    return False, "Ani DB_PATH ani DATABASE_URL nie są ustawione"


def check_email_config(env_vars):
    """Sprawdź konfigurację email"""
    provider = env_vars.get("EMAIL_PROVIDER", "gmail")

    if provider == "gmail":
        client_secrets = env_vars.get("GMAIL_CLIENT_SECRETS", "./gmail_client_secret.json")
        secrets_path = Path(client_secrets)

        if not secrets_path.exists():
            return False, f"Gmail client_secret.json nie istnieje: {client_secrets}"

        return True, "Gmail OAuth skonfigurowany (token zostanie utworzony przy pierwszym użyciu)"

    elif provider == "smtp":
        required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]
        missing = [key for key in required if not env_vars.get(key)]

        if missing:
            return False, f"Brakujące zmienne SMTP: {', '.join(missing)}"

        return True, f"SMTP skonfigurowany ({env_vars.get('SMTP_HOST')})"

    return False, f"Nieznany EMAIL_PROVIDER: {provider}"


def check_scrapers(env_vars):
    """Sprawdź credentials scraperów"""
    scrapers = {
        "Copart": ("COPART_USERNAME", "COPART_PASSWORD"),
        "IAAI": ("IAAI_USERNAME", "IAAI_PASSWORD"),
        "Amerpol": ("AMERPOL_USERNAME", "AMERPOL_PASSWORD"),
    }

    configured = []
    missing = []

    for name, (user_key, pass_key) in scrapers.items():
        if env_vars.get(user_key) and env_vars.get(pass_key):
            configured.append(name)
        else:
            missing.append(name)

    if not configured:
        return False, "Żaden scraper nie jest skonfigurowany (opcjonalne)"

    message = f"Skonfigurowane: {', '.join(configured)}"
    if missing:
        message += f" | Brakujące: {', '.join(missing)}"

    return True, message


def check_playwright():
    """Sprawdź czy Playwright jest zainstalowany"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Sprawdź czy chromium jest zainstalowany
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return True, "Playwright + Chromium zainstalowane"
            except Exception:
                return False, "Chromium nie jest zainstalowany. Uruchom: playwright install chromium"

    except ImportError:
        return False, "Pakiet 'playwright' nie jest zainstalowany"
    except Exception as e:
        return False, f"Błąd: {str(e)}"


def main():
    print_header("AutoScout US - Weryfikacja Konfiguracji")

    # Check .env
    status, message = check_env_file()
    print_check(".env file", status, message)

    if not status:
        print("\nUtwórz plik .env przed kontynuacją:")
        print("  cp .env.example .env")
        sys.exit(1)

    # Load environment variables
    env_vars = load_env()

    print("\n--- WYMAGANE KOMPONENTY ---")

    # Anthropic API
    status, message = check_anthropic_api(env_vars.get("ANTHROPIC_API_KEY"))
    print_check("Anthropic API", status, message)

    # Database
    status, message = check_database(
        env_vars.get("DB_PATH"),
        env_vars.get("DATABASE_URL")
    )
    print_check("Database", status, message)

    # Playwright
    status, message = check_playwright()
    print_check("Playwright", status, message)

    print("\n--- OPCJONALNE KOMPONENTY ---")

    # Telegram
    status, message = check_telegram_bot(
        env_vars.get("TELEGRAM_BOT_TOKEN"),
        env_vars.get("TELEGRAM_CHAT_ID")
    )
    print_check("Telegram Bot", status, message)

    # Email
    status, message = check_email_config(env_vars)
    print_check("Email Provider", status, message)

    # Scrapers
    status, message = check_scrapers(env_vars)
    print_check("Scrapers", status, message)

    print("\n" + "="*60)
    print("\nNastępne kroki:")
    print("1. Napraw błędy oznaczone ✗")
    print("2. Zaloguj się do giełd: python -m backend.services.scrapers.login_helper <scraper>")
    print("3. Uruchom backend: uvicorn backend.main:app --reload")
    print("4. Otwórz dashboard: http://localhost:8000")
    print()


if __name__ == "__main__":
    main()
