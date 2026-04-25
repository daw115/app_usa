#!/usr/bin/env python3
"""
AutoScout US - Interactive Setup Script
Przeprowadza przez konfigurację aplikacji krok po kroku
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(number, text):
    print(f"\n[{number}] {text}")


def print_success(text):
    print(f"✓ {text}")


def print_error(text):
    print(f"✗ {text}")


def check_python_version():
    """Sprawdź wersję Pythona"""
    print_step(1, "Sprawdzanie wersji Pythona...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error(f"Python {version.major}.{version.minor} jest za stary")
        print("Wymagany Python 3.9 lub nowszy")
        return False

    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True


def setup_venv():
    """Utwórz i aktywuj venv"""
    print_step(2, "Konfiguracja środowiska wirtualnego...")

    venv_path = Path(".venv")

    if venv_path.exists():
        print_success("Venv już istnieje")
        return True

    try:
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print_success("Utworzono .venv")
        print("\nAktywuj venv:")
        print("  macOS/Linux: source .venv/bin/activate")
        print("  Windows: .venv\\Scripts\\activate")
        return True
    except subprocess.CalledProcessError:
        print_error("Nie udało się utworzyć venv")
        return False


def install_dependencies():
    """Zainstaluj dependencies"""
    print_step(3, "Instalacja dependencies...")

    pip_cmd = ".venv/bin/pip" if os.name != "nt" else ".venv\\Scripts\\pip"

    if not Path(pip_cmd).exists():
        print_error("Venv nie jest aktywowany")
        print("Uruchom ponownie po aktywacji venv")
        return False

    try:
        print("Instalacja pakietów Python...")
        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
        print_success("Zainstalowano pakiety Python")

        print("\nInstalacja Playwright browsers...")
        playwright_cmd = ".venv/bin/playwright" if os.name != "nt" else ".venv\\Scripts\\playwright"
        subprocess.run([playwright_cmd, "install", "chromium"], check=True)
        print_success("Zainstalowano Playwright chromium")

        return True
    except subprocess.CalledProcessError:
        print_error("Błąd instalacji")
        return False


def prompt_input(prompt_text, default="", required=True):
    """Pobierz input od użytkownika"""
    if default:
        prompt_text = f"{prompt_text} [{default}]"

    while True:
        value = input(f"{prompt_text}: ").strip()

        if not value and default:
            return default

        if not value and required:
            print("To pole jest wymagane")
            continue

        return value


def configure_env():
    """Interaktywna konfiguracja .env"""
    print_step(4, "Konfiguracja .env")

    env_path = Path(".env")

    if env_path.exists():
        overwrite = input("\n.env już istnieje. Nadpisać? (t/N): ").strip().lower()
        if overwrite != "t":
            print("Pomijam konfigurację .env")
            return True

    config = {}

    # Database
    print("\n--- BAZA DANYCH ---")
    config["DB_PATH"] = prompt_input("Ścieżka do bazy SQLite", "./app.db", required=False)
    config["DATABASE_URL"] = prompt_input("PostgreSQL URL (opcjonalnie)", "", required=False)

    # Anthropic
    print("\n--- ANTHROPIC API ---")
    print("Uzyskaj klucz: https://console.anthropic.com/settings/keys")
    config["ANTHROPIC_API_KEY"] = prompt_input("Anthropic API Key", required=True)
    config["ANTHROPIC_BASE_URL"] = prompt_input("Base URL (opcjonalnie)", "", required=False)

    # Telegram
    print("\n--- TELEGRAM BOT (opcjonalnie) ---")
    print("1. Utwórz bota: https://t.me/BotFather")
    print("2. Uzyskaj chat_id: https://t.me/userinfobot")
    config["TELEGRAM_BOT_TOKEN"] = prompt_input("Bot Token", "", required=False)
    config["TELEGRAM_CHAT_ID"] = prompt_input("Chat ID", "", required=False)

    # Email
    print("\n--- EMAIL ---")
    print("Wybierz provider:")
    print("1. Gmail OAuth (drafts)")
    print("2. SMTP (direct send)")
    email_choice = prompt_input("Wybór (1/2)", "1")

    if email_choice == "1":
        config["EMAIL_PROVIDER"] = "gmail"
        print("\nPobierz credentials z Google Cloud Console:")
        print("https://console.cloud.google.com/apis/credentials")
        config["GMAIL_CLIENT_SECRETS"] = prompt_input("Ścieżka do client_secret.json", "./gmail_client_secret.json")
        config["GMAIL_TOKEN_PATH"] = prompt_input("Ścieżka do token.json", "./gmail_token.json")
    else:
        config["EMAIL_PROVIDER"] = "smtp"
        config["SMTP_HOST"] = prompt_input("SMTP Host", required=True)
        config["SMTP_PORT"] = prompt_input("SMTP Port", "465")
        config["SMTP_USER"] = prompt_input("SMTP User", required=True)
        config["SMTP_PASSWORD"] = prompt_input("SMTP Password", required=True)
        config["SMTP_FROM"] = prompt_input("From Email", config.get("SMTP_USER", ""))

    # Scrapers
    print("\n--- SCRAPERS ---")
    print("Credentials do giełd (opcjonalnie, możesz dodać później)")
    config["COPART_USERNAME"] = prompt_input("Copart Username", "", required=False)
    config["COPART_PASSWORD"] = prompt_input("Copart Password", "", required=False)
    config["IAAI_USERNAME"] = prompt_input("IAAI Username", "", required=False)
    config["IAAI_PASSWORD"] = prompt_input("IAAI Password", "", required=False)
    config["AMERPOL_USERNAME"] = prompt_input("Amerpol Username", "", required=False)
    config["AMERPOL_PASSWORD"] = prompt_input("Amerpol Password", "", required=False)
    config["SCRAPERAPI_KEY"] = prompt_input("ScraperAPI Key (opcjonalnie)", "", required=False)

    # Public form URL
    config["PUBLIC_FORM_BASE_URL"] = prompt_input("Public form base URL", "http://localhost:8000")

    # Zapisz .env
    with open(".env", "w") as f:
        for key, value in config.items():
            if value:
                f.write(f"{key}={value}\n")

    print_success("Zapisano .env")
    return True


def run_migrations():
    """Uruchom migracje bazy danych"""
    print_step(5, "Inicjalizacja bazy danych...")

    alembic_cmd = ".venv/bin/alembic" if os.name != "nt" else ".venv\\Scripts\\alembic"

    if not Path(alembic_cmd).exists():
        print_error("Alembic nie znaleziony - czy venv jest aktywowany?")
        return False

    try:
        subprocess.run([alembic_cmd, "upgrade", "head"], check=True)
        print_success("Baza danych zainicjalizowana")
        return True
    except subprocess.CalledProcessError:
        print_error("Błąd migracji")
        return False


def print_next_steps():
    """Wyświetl następne kroki"""
    print_header("SETUP ZAKOŃCZONY")

    print("Następne kroki:\n")
    print("1. Aktywuj venv (jeśli jeszcze nie):")
    print("   source .venv/bin/activate")
    print()
    print("2. Zaloguj się do giełd (zapisuje sesje):")
    print("   python -m backend.services.scrapers.login_helper copart")
    print("   python -m backend.services.scrapers.login_helper iaai")
    print("   python -m backend.services.scrapers.login_helper amerpol")
    print()
    print("3. Uruchom backend:")
    print("   uvicorn backend.main:app --reload")
    print()
    print("4. Otwórz dashboard:")
    print("   http://localhost:8000")
    print()
    print("5. (Opcjonalnie) Weryfikuj konfigurację:")
    print("   python verify_config.py")
    print()
    print("Dokumentacja: README.md, SETUP.md")
    print()


def main():
    print_header("AutoScout US - Setup")

    if not check_python_version():
        sys.exit(1)

    if not setup_venv():
        sys.exit(1)

    print("\n⚠️  UWAGA: Aktywuj venv przed kontynuacją:")
    print("   source .venv/bin/activate")
    print()

    continue_setup = input("Kontynuować setup? (T/n): ").strip().lower()
    if continue_setup == "n":
        print("\nSetup przerwany. Uruchom ponownie po aktywacji venv.")
        sys.exit(0)

    if not install_dependencies():
        sys.exit(1)

    if not configure_env():
        sys.exit(1)

    if not run_migrations():
        print("\n⚠️  Migracje nie powiodły się, ale możesz spróbować ręcznie:")
        print("   alembic upgrade head")

    print_next_steps()


if __name__ == "__main__":
    main()
