"""
Event-News Matching Pipeline
============================

Polymarket eventlerini News API haberleriyle eşleştirir.
- Query oluşturma
- Tarih aralığı hesaplama
- Article skorlama ve sıralama
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from polymarket.client import Event
from newsapi.client import Article, NewsAPIClient


# Common words to exclude from queries
STOP_WORDS = {
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'is', 
    'are', 'was', 'were', 'be', 'been', 'being', 'will', 'would', 'could', 
    'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'it',
    'its', 'by', 'from', 'with', 'as', 'but', 'if', 'then', 'than', 'so',
    'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how', 'all',
    'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'not', 'only', 'own', 'same', 'too', 'very', 'just', 'before',
    'after', 'during', 'while', 'market', 'resolve', 'yes', 'no',
}

# Generic tags to skip
GENERIC_TAGS = {
    'business', 'politics', 'news', 'world', 'us', 'usa', 'america',
    'global', 'international', 'economy', 'economic', 'predictions',
    '2024', '2025', '2026',
}


@dataclass
class ScoredArticle:
    """Article with relevance score"""
    article: Article
    score: float
    match_reasons: list[str]


def extract_key_terms(text: str) -> list[str]:
    """Extract important terms from text"""
    # Clean and tokenize
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    
    # Filter stop words and short words
    terms = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    
    return terms


def build_news_query(event: Event, max_terms: int = 8) -> str:
    """
    Build News API query from event data
    
    Strategy:
    1. Extract key terms from title
    2. Add specific tags (non-generic)
    3. Optionally add terms from description
    
    Args:
        event: Polymarket Event object
        max_terms: Maximum query terms
        
    Returns:
        Query string for News API
    """
    terms = []
    
    # 1. Extract from title (most important)
    title_terms = extract_key_terms(event.title)
    terms.extend(title_terms[:5])
    
    # 2. Add specific tags
    for tag in event.tags:
        tag_lower = tag.lower()
        if tag_lower not in GENERIC_TAGS and tag_lower not in [t.lower() for t in terms]:
            terms.append(tag)
            if len(terms) >= max_terms:
                break
    
    # 3. Look for named entities in title (capitalized words, names, etc.)
    # These are often important: company names, people, etc.
    named_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', event.title)
    for entity in named_entities:
        if entity.lower() not in STOP_WORDS and entity not in terms:
            terms.insert(0, f'"{entity}"')  # Exact match for names
            if len(terms) >= max_terms:
                break
    
    # Build query - use OR for broader search
    query = ' '.join(terms[:max_terms])
    
    return query


def get_time_window(
    event: Event,
    default_days_back: int = 7,
    buffer_days: int = 2,
) -> tuple[datetime, datetime]:
    """
    Calculate search time window based on event dates
    
    Args:
        event: Polymarket Event object
        default_days_back: Default days to look back if no event dates
        buffer_days: Extra days before start_date
        
    Returns:
        Tuple of (from_date, to_date)
    """
    now = datetime.now()
    
    # Helper to make datetime naive for comparison
    def to_naive(dt: datetime) -> datetime:
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    
    # End date: use event end_date if in future, else now
    if event.end_date:
        end_naive = to_naive(event.end_date)
        if end_naive > now:
            to_date = min(end_naive, now + timedelta(days=1))
        else:
            to_date = now
    else:
        to_date = now
    
    # Start date: use event start_date with buffer, or default
    if event.start_date:
        start_naive = to_naive(event.start_date)
        from_date = start_naive - timedelta(days=buffer_days)
        # Don't go too far back
        min_date = now - timedelta(days=30)
        from_date = max(from_date, min_date)
    else:
        from_date = now - timedelta(days=default_days_back)
    
    return from_date, to_date


def score_article(
    article: Article,
    event: Event,
    query_terms: list[str],
) -> ScoredArticle:
    """
    Score article relevance to event
    
    Scoring factors:
    - Title keyword matches (highest weight)
    - Description keyword matches
    - Source reliability
    - Recency
    
    Args:
        article: News article
        event: Polymarket event
        query_terms: Terms used in search query
        
    Returns:
        ScoredArticle with score and match reasons
    """
    score = 0.0
    reasons = []
    
    # Prepare text for matching
    article_title = (article.title or '').lower()
    article_desc = (article.description or '').lower()
    event_title = event.title.lower()
    
    # 1. Title matches (weight: 3)
    title_matches = 0
    for term in query_terms:
        term_clean = term.strip('"').lower()
        if term_clean in article_title:
            title_matches += 1
    
    if title_matches > 0:
        score += title_matches * 3
        reasons.append(f"title_match:{title_matches}")
    
    # 2. Description matches (weight: 1)
    desc_matches = 0
    for term in query_terms:
        term_clean = term.strip('"').lower()
        if term_clean in article_desc:
            desc_matches += 1
    
    if desc_matches > 0:
        score += desc_matches * 1
        reasons.append(f"desc_match:{desc_matches}")
    
    # 3. Named entity exact match (weight: 5)
    # Check if key names from event appear in article
    named_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', event.title)
    for entity in named_entities:
        if entity.lower() in article_title:
            score += 5
            reasons.append(f"entity:{entity}")
    
    # 4. Recency bonus (weight: 0-2)
    if article.published_at:
        pub_date = article.published_at
        if pub_date.tzinfo is not None:
            pub_date = pub_date.replace(tzinfo=None)
        days_old = (datetime.now() - pub_date).days
        if days_old <= 1:
            score += 2
            reasons.append("very_recent")
        elif days_old <= 3:
            score += 1
            reasons.append("recent")
    
    # 5. Source quality bonus (weight: 1)
    quality_sources = {
        'reuters', 'bloomberg', 'associated press', 'bbc', 'cnn', 
        'wall street journal', 'new york times', 'washington post',
        'financial times', 'the economist', 'politico', 'axios'
    }
    source_lower = (article.source_name or '').lower()
    if any(qs in source_lower for qs in quality_sources):
        score += 1
        reasons.append("quality_source")
    
    return ScoredArticle(article=article, score=score, match_reasons=reasons)


def match_news_to_event(
    event: Event,
    max_articles: int = 5,
    min_score: float = 2.0,
) -> list[ScoredArticle]:
    """
    Full pipeline: find and score news articles for an event
    
    Args:
        event: Polymarket event
        max_articles: Maximum articles to return
        min_score: Minimum relevance score
        
    Returns:
        List of scored articles, sorted by score (descending)
    """
    # 1. Build query
    query = build_news_query(event)
    query_terms = query.split()
    
    # 2. Get time window
    from_date, to_date = get_time_window(event)
    
    # 3. Fetch articles
    client = NewsAPIClient()
    try:
        articles, _ = client.search_everything(
            query=query,
            from_date=from_date,
            to_date=to_date,
            sort_by='relevancy',
            page_size=20,  # Fetch more for scoring
        )
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []
    
    # 4. Score articles
    scored = [score_article(a, event, query_terms) for a in articles]
    
    # 5. Filter and sort
    scored = [s for s in scored if s.score >= min_score]
    scored.sort(key=lambda x: x.score, reverse=True)
    
    return scored[:max_articles]


if __name__ == "__main__":
    # Test the matching pipeline
    from polymarket.client import PolymarketClient
    
    print("Testing Event-News Matching Pipeline")
    print("=" * 60)
    
    # Get an event
    poly_client = PolymarketClient()
    events = poly_client.get_events(limit=3)
    
    for event in events:
        print(f"\n📌 Event: {event.title}")
        print(f"   Tags: {event.tags[:3]}")
        
        # Build query
        query = build_news_query(event)
        print(f"   Query: {query}")
        
        # Get time window
        from_date, to_date = get_time_window(event)
        print(f"   Time window: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
        
        # Match news
        print("\n   📰 Matching news articles...")
        scored_articles = match_news_to_event(event, max_articles=3)
        
        if scored_articles:
            for sa in scored_articles:
                print(f"\n   [{sa.score:.1f}] {sa.article.title[:60]}...")
                print(f"        Source: {sa.article.source_name}")
                print(f"        Reasons: {sa.match_reasons}")
        else:
            print("   No matching articles found")
        
        print("\n" + "-" * 60)
    
    print("\n✅ Pipeline test completed!")

