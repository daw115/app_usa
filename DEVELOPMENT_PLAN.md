# Plan rozwoju AutoScout US

## 1. Scraper improvements ⏳
**Cel:** Pobieranie zdjęć z Copart/IAAI dla analizy AI

**Zadania:**
- [ ] Debug selektorów zdjęć Copart (obecnie 0 zdjęć)
- [ ] Dodać fallback selektory dla różnych layoutów
- [ ] Test na 5 różnych aukcjach
- [ ] IAAI scraper - dodać pobieranie zdjęć

**Priorytet:** CRITICAL - bez zdjęć AI nie działa

## 2. Email integration ⏳
**Cel:** Wysyłka raportów przez email

**Opcje:**
- SMTP dla ATT Mail (outbound.att.net:465)
- Gmail OAuth (wymaga Google Cloud setup)

**Zadania:**
- [ ] Dodać SMTP backend do `backend/services/email.py`
- [ ] Konfiguracja w .env (SMTP_HOST, SMTP_USER, SMTP_PASS)
- [ ] Przycisk "Wyślij email" w raporcie
- [ ] Test wysyłki

## 3. Automatyzacja ⏳
**Cel:** Auto-search dla nowych zapytań

**Zadania:**
- [ ] Cron job: co 30 min sprawdź nowe zapytania (status=new)
- [ ] Auto-trigger search pipeline
- [ ] Telegram notification po zakończeniu
- [ ] Opcja wyłączenia auto-search w settings

## 4. Dashboard enhancements ⏳
**Cel:** Lepsze UX dla Janka

**Zadania:**
- [ ] Filtry: źródło (Copart/IAAI/etc), szkoda (1-10), cena
- [ ] Sortowanie: cena, szkoda, data aukcji
- [ ] Porównywanie: checkbox + modal z 2-3 autami obok siebie
- [ ] Bulk actions: ukryj zaznaczone, analizuj zaznaczone

## 5. Klient portal ⏳
**Cel:** Klient może śledzić status zapytania

**Zadania:**
- [ ] Publiczny URL: `/track/{inquiry_id}/{token}`
- [ ] Widok: status, znalezione auta (bez cen), ETA raportu
- [ ] Email z linkiem tracking po złożeniu formularza
- [ ] Opcja: klient zatwierdza wybrane auta przed raportem

## 6. Analytics ⏳
**Cel:** Statystyki dla Janka

**Zadania:**
- [ ] Dashboard `/analytics`:
  - Zapytania: dzisiaj/tydzień/miesiąc
  - Conversion rate: zapytanie → wysłany raport
  - Średni koszt auta (PLN)
  - Top 5 modeli
  - Źródła: Copart vs IAAI vs Amerpol
- [ ] Wykresy: Chart.js lub Recharts
- [ ] Export CSV

## Kolejność implementacji:
1. **Scraper improvements** (bez tego AI nie działa)
2. **Email integration** (kluczowe dla workflow)
3. **Dashboard enhancements** (daily UX)
4. **Analytics** (insights)
5. **Automatyzacja** (nice-to-have)
6. **Klient portal** (future)
