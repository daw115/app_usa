# Testing Guide

## Automated Tests

### Unit Tests
```bash
# All tests
pytest tests/ -v

# Specific test files
pytest tests/test_pricing.py -v
pytest tests/test_analyzer.py -v
pytest tests/test_synthesizer.py -v

# Quick run (no verbose)
pytest tests/ -q
```

### Integration Tests
```bash
pytest tests/test_integration.py -v
```

**Coverage:**
- Full pipeline: inquiry → scraping → AI analysis → pricing → ranking → report generation
- Error handling: scraper failures don't crash pipeline
- Database operations: CRUD for Inquiry, Listing, Report
- AI mocking: Anthropic API responses for analyzer and synthesizer

## Manual End-to-End Test

### Prerequisites
```bash
# Start server
uvicorn backend.main:app --reload

# In another terminal, create public tunnel (optional)
cloudflared tunnel --url http://localhost:8000
```

### Test Steps

**1. Submit inquiry via public form**
- Navigate to: http://localhost:8000/form
- Fill form:
  - Name: Jan Kowalski
  - Email: jan@example.com
  - Make: BMW
  - Model: X5
  - Year: 2015-2017
  - Budget: 80000 PLN
  - Damage tolerance: Light
- Submit → should see "Dziękujemy!" confirmation

**2. Verify Telegram notification**
- Check configured Telegram chat for new inquiry notification
- Should contain: client name, make/model, budget

**3. Trigger search in dashboard**
- Navigate to: http://localhost:8000/
- Click on new inquiry
- Click "🔍 Szukaj na giełdach" button
- Wait 30-60 seconds for pipeline to complete

**4. Verify listings**
- Check listings table shows results from Copart/IAAI/Amerpol
- Each listing should have:
  - ✅ Photos (at least 1-2 per listing)
  - ✅ VIN
  - ✅ AI damage_score (1-10)
  - ✅ AI repair estimate (low/high USD)
  - ✅ Total cost PLN
  - ✅ Recommended rank (1-5 for top listings)

**5. Generate report**
- Click "📝 Generuj raport" button
- Wait 10-15 seconds
- Click "Edytuj raport" link

**6. Verify report content**
- Subject line contains: "Oferta aut z USA — [year] [make] [model]"
- HTML body contains:
  - ✅ Polish greeting with client name
  - ✅ Table with top 3-5 cars
  - ✅ Columns: Rok/Model, Przebieg, Szkoda, Koszt (PLN), Link
  - ✅ Commentary paragraphs for each car
  - ✅ Final recommendation
  - ✅ CTA (call to action)

**7. Create Gmail draft**
- Click "📧 Utwórz draft w Gmailu" button
- If first time: browser opens for OAuth consent
- Should redirect back with success message

**8. Verify Gmail draft**
- Open Gmail in browser
- Check Drafts folder
- Draft should contain:
  - ✅ Correct recipient (client email)
  - ✅ Subject line
  - ✅ HTML formatted body (table renders correctly)

**9. Mark as sent**
- Back in dashboard, click "✅ Oznacz jako wysłane"
- Inquiry status should change to "sent"

## Expected Results

### Scraper Output
- **Copart**: 3-8 listings with photos
- **IAAI**: 2-5 listings with photos
- **Amerpol**: 0-3 listings (depends on inventory)

### AI Analysis
- **Damage score**: 1-10 (lower is better)
- **Repair estimate**: $500-$15,000 range typical
- **Confidence**: high/medium/low
- **Processing time**: ~5-10 seconds per listing

### Pricing Calculation
- **Formula**: (auction + agent + transport) × USD_rate + customs + excise + VAT + repair + margin
- **Typical range**: 50,000-150,000 PLN for mid-range cars
- **Margin**: 5,000 PLN default (configurable in /settings)

### Report Generation
- **Processing time**: 10-15 seconds
- **Length**: 500-1000 words typical
- **Tone**: Professional, warm, concrete (no AI mentions)

## Known Issues

### Scrapers
- **Copart photos**: Selectors may need updating if site layout changes
- **IAAI photos**: Limited coverage, may return 0 photos for some listings
- **Rate limiting**: Max ~30 searches/day per source to avoid bans

### AI Analysis
- **No photos**: If listing has 0 photos, AI analysis skipped (ai_damage_score = None)
- **Parsing failures**: Rare cases where Claude returns invalid JSON → fallback response used

### Gmail OAuth
- **First run**: Requires browser consent flow
- **Token expiry**: Refresh token valid for 6 months, then re-auth needed

## Troubleshooting

### Pipeline stuck in "searching" status
```bash
# Check logs
tail -f backend/logs/app.log

# Common causes:
# - Scraper timeout (>30s)
# - No storage_state for giełda (run login_helper)
# - Network issues
```

### No photos in listings
```bash
# Debug Copart selectors
python debug_copart_selectors.py

# Check screenshot
open /tmp/copart_page.png
```

### AI analysis fails
```bash
# Check Anthropic API key
echo $ANTHROPIC_API_KEY

# Test API directly
python -c "from backend.services.analyzer import _anthropic; print(_anthropic())"
```

### Gmail draft creation fails
```bash
# Check OAuth credentials
ls -la gmail_client_secret.json gmail_token.json

# Re-authenticate
rm gmail_token.json
# Next draft creation will trigger OAuth flow
```

## Performance Benchmarks

### Full Pipeline (1 inquiry, 10 listings)
- Scraping: 20-40 seconds
- AI analysis: 50-100 seconds (10 listings × 5-10s each)
- Ranking: <1 second
- Report generation: 10-15 seconds
- **Total**: ~90-150 seconds

### Optimization Tips
- Use prompt caching for analyzer (saves ~70% tokens on repeated analyses)
- Parallel scraping (already implemented)
- Limit max_results in SearchCriteria (default: 8 per source)
