# News API + Polymarket Pipeline

Polymarket eventlerini News API haberleriyle eşleştirip AI summary üreten pipeline.

## Dosya Yapısı

```
backend/
├── polymarket/              # Polymarket Gamma API client
│   ├── __init__.py
│   └── client.py            # Event, Market modelleri ve PolymarketClient
│
├── newsapi/                 # News API client
│   ├── __init__.py
│   ├── client.py            # Article modeli ve NewsAPIClient
│   ├── newsapidocs.txt      # API dokümantasyonu
│   └── poly.txt             # Polymarket API şeması
│
├── pipeline/                # Event-News eşleştirme
│   ├── __init__.py
│   └── matching.py          # Query builder, scorer, matcher
│
├── ai/                      # AI summarizer
│   ├── __init__.py
│   └── summarizer.py        # OpenAI entegrasyonu, EventSummary
│
├── api/                     # FastAPI endpoints
│   ├── __init__.py
│   ├── app.py               # FastAPI application
│   ├── routes.py            # API endpoints
│   └── models.py            # Pydantic response modelleri
│
├── config.py                # Environment config (.env loader)
├── requirements.txt         # Python dependencies
├── .env                     # API keys (gitignore'd)
└── venv/                    # Python virtual environment
```

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/v1/health` | Servis durumu |
| GET | `/api/v1/events` | Event listesi + haberler + AI summary |
| GET | `/api/v1/events/{slug}` | Tek event detayı |
| GET | `/api/v1/events/{slug}/news` | Sadece ilgili haberler |
| GET | `/api/v1/search?q=xxx` | Event arama |

## Query Parametreleri

### `/api/v1/events`
- `limit` (int, 1-50): Kaç event dönsün (default: 10)
- `page` (int): Sayfa numarası (default: 1)
- `active` (bool): Aktif eventler (default: true)
- `closed` (bool): Kapanmış eventler (default: false)
- `include_news` (bool): Haberler dahil mi (default: true)
- `include_summary` (bool): AI summary dahil mi (default: true)
- `max_articles` (int, 1-10): Event başına max haber (default: 5)

## Kurulum

```bash
cd backend

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install fastapi uvicorn pydantic

# Environment variables (.env dosyası oluştur)
echo 'OPENAI_API_KEY=sk-xxx' > .env
echo 'NEWSAPI_KEY=xxx' >> .env
```

## Çalıştırma

```bash
cd backend
source venv/bin/activate
PYTHONPATH=. uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Docs: http://localhost:8000/docs

## Pipeline Akışı

```
1. Polymarket Event
       ↓
2. build_news_query(event)  → "Fed rate December Jerome Powell"
       ↓
3. get_time_window(event)   → (2025-11-03, 2025-12-04)
       ↓
4. NewsAPI.search_everything(query, from, to)
       ↓
5. score_article(article, event)  → relevance score
       ↓
6. Top 5 articles selected
       ↓
7. AISummarizer.summarize_event(event, articles)
       ↓
8. EventSummary {summary, key_points, sentiment, confidence}
```

## Modüller

### `polymarket/client.py`
- `Event`: id, slug, title, description, tags, markets, dates, volume
- `Market`: id, question, outcomes, outcome_prices
- `PolymarketClient.get_events()`: Event listesi çek
- `PolymarketClient.get_event_by_slug()`: Tek event çek
- `PolymarketClient.search_events()`: Keyword ile ara

### `newsapi/client.py`
- `Article`: source, title, description, url, published_at, content
- `NewsAPIClient.search_everything()`: Tüm makalelerde ara
- `NewsAPIClient.get_top_headlines()`: Güncel başlıklar
- `NewsAPIClient.search_for_event()`: Event için haber ara

### `pipeline/matching.py`
- `build_news_query(event)`: Event'ten News API query oluştur
- `get_time_window(event)`: Tarih aralığı hesapla
- `score_article(article, event)`: Haber relevance skoru
- `match_news_to_event(event)`: Full pipeline - haberler + skorlama

### `ai/summarizer.py`
- `EventSummary`: summary, key_points, sentiment, confidence
- `AISummarizer.summarize_event()`: OpenAI ile özet üret
- Fallback: API key yoksa basit headline listesi

## Maliyet

GPT-4o-mini ile event başına ~$0.0002 (~0.02 cent)

| Kullanım | Aylık Maliyet |
|----------|---------------|
| 100/gün | $0.68 |
| 1000/gün | $6.75 |
| 5000/gün | $33.75 |

## Environment Variables

| Değişken | Açıklama |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI API key (AI summary için) |
| `NEWSAPI_KEY` | News API key |

