"""
News API Client
===============

NewsAPI.org'dan haber çekmek için client.
Endpoints:
  - /v2/everything - Tüm makaleler
  - /v2/top-headlines - Güncel başlıklar
"""

import urllib.request
import urllib.parse
import json
import os
import ssl
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

# SSL verification bypass for development
ssl._create_default_https_context = ssl._create_unverified_context

NEWSAPI_BASE = "https://newsapi.org/v2"

# API key from environment or default (for testing)
DEFAULT_API_KEY = os.environ.get('NEWSAPI_KEY', '9269b16560454b61af6508052e53e4a1')


@dataclass
class Article:
    """News article model"""
    source_id: Optional[str]
    source_name: str
    author: Optional[str]
    title: str
    description: Optional[str]
    url: str
    image_url: Optional[str]
    published_at: Optional[datetime]
    content: Optional[str]
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Article':
        """Parse API response into Article object"""
        source = data.get('source', {})
        
        published_at = None
        if data.get('publishedAt'):
            try:
                published_at = datetime.fromisoformat(data['publishedAt'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        return cls(
            source_id=source.get('id'),
            source_name=source.get('name', 'Unknown'),
            author=data.get('author'),
            title=data.get('title', ''),
            description=data.get('description'),
            url=data.get('url', ''),
            image_url=data.get('urlToImage'),
            published_at=published_at,
            content=data.get('content'),
        )


class NewsAPIClient:
    """News API client for fetching news articles"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = NEWSAPI_BASE
    
    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make HTTP request to News API"""
        params = params or {}
        params['apiKey'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        if data.get('status') != 'ok':
            error_msg = data.get('message', 'Unknown error')
            raise Exception(f"News API error: {error_msg}")
        
        return data
    
    def search_everything(
        self,
        query: str,
        from_date: datetime | str = None,
        to_date: datetime | str = None,
        language: str = 'en',
        sort_by: str = 'relevancy',
        page: int = 1,
        page_size: int = 20,
        domains: str = None,
        exclude_domains: str = None,
    ) -> tuple[list[Article], int]:
        """
        Search all articles using /everything endpoint
        
        Args:
            query: Search keywords (supports AND/OR/NOT, quotes for exact match)
            from_date: Oldest article date (datetime or ISO string)
            to_date: Newest article date
            language: 2-letter ISO code (en, de, fr, etc.)
            sort_by: relevancy, popularity, or publishedAt
            page: Page number (1-based)
            page_size: Results per page (max 100)
            domains: Comma-separated domains to include
            exclude_domains: Comma-separated domains to exclude
            
        Returns:
            Tuple of (articles list, total results count)
        """
        params = {
            'q': query,
            'language': language,
            'sortBy': sort_by,
            'page': page,
            'pageSize': min(page_size, 100),
        }
        
        # Format dates
        if from_date:
            if isinstance(from_date, datetime):
                from_date = from_date.strftime('%Y-%m-%d')
            params['from'] = from_date
        
        if to_date:
            if isinstance(to_date, datetime):
                to_date = to_date.strftime('%Y-%m-%d')
            params['to'] = to_date
        
        if domains:
            params['domains'] = domains
        
        if exclude_domains:
            params['excludeDomains'] = exclude_domains
        
        data = self._request('/everything', params)
        
        articles = [Article.from_api_response(a) for a in data.get('articles', [])]
        total = data.get('totalResults', 0)
        
        return articles, total
    
    def get_top_headlines(
        self,
        country: str = None,
        category: str = None,
        sources: str = None,
        query: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Article], int]:
        """
        Get top headlines using /top-headlines endpoint
        
        Args:
            country: 2-letter ISO country code (us, gb, etc.)
            category: business, entertainment, general, health, science, sports, technology
            sources: Comma-separated source IDs (can't mix with country/category)
            query: Search keywords
            page: Page number
            page_size: Results per page (max 100)
            
        Returns:
            Tuple of (articles list, total results count)
        """
        params = {
            'page': page,
            'pageSize': min(page_size, 100),
        }
        
        if country:
            params['country'] = country
        if category:
            params['category'] = category
        if sources:
            params['sources'] = sources
        if query:
            params['q'] = query
        
        # At least one filter required
        if not any([country, category, sources, query]):
            params['country'] = 'us'  # Default to US
        
        data = self._request('/top-headlines', params)
        
        articles = [Article.from_api_response(a) for a in data.get('articles', [])]
        total = data.get('totalResults', 0)
        
        return articles, total
    
    def search_for_event(
        self,
        event_title: str,
        event_description: str = '',
        event_tags: list[str] = None,
        days_back: int = 7,
        max_articles: int = 10,
    ) -> list[Article]:
        """
        Search for articles related to a Polymarket event
        
        Args:
            event_title: Event title to search
            event_description: Optional description for context
            event_tags: Optional tags for better matching
            days_back: How many days back to search
            max_articles: Maximum articles to return
            
        Returns:
            List of relevant articles
        """
        # Build query from title (use title as main query)
        # Extract key terms, remove common words
        query = event_title
        
        # Add top tags if available
        if event_tags:
            # Add first 2 tags that aren't too generic
            generic = {'business', 'politics', 'news', 'world', 'us', 'usa'}
            specific_tags = [t for t in event_tags if t.lower() not in generic][:2]
            if specific_tags:
                query = f"{query} {' '.join(specific_tags)}"
        
        # Date range
        from_date = datetime.now() - timedelta(days=days_back)
        to_date = datetime.now()
        
        articles, _ = self.search_everything(
            query=query,
            from_date=from_date,
            to_date=to_date,
            sort_by='relevancy',
            page_size=max_articles,
        )
        
        return articles


# Convenience functions
def search_news(query: str, days_back: int = 7) -> list[Article]:
    """Quick news search"""
    client = NewsAPIClient()
    from_date = datetime.now() - timedelta(days=days_back)
    articles, _ = client.search_everything(query, from_date=from_date)
    return articles


def get_headlines(country: str = 'us') -> list[Article]:
    """Quick headlines fetch"""
    client = NewsAPIClient()
    articles, _ = client.get_top_headlines(country=country)
    return articles


if __name__ == "__main__":
    # Test the client
    print("Testing NewsAPIClient...")
    
    client = NewsAPIClient()
    
    # Test 1: Search everything
    print("\n📰 Testing /everything endpoint:")
    articles, total = client.search_everything(
        query="Federal Reserve",
        page_size=3
    )
    print(f"   Found {total} articles, showing {len(articles)}:")
    for a in articles:
        print(f"   - [{a.source_name}] {a.title[:50]}...")
    
    # Test 2: Top headlines
    print("\n📰 Testing /top-headlines endpoint:")
    articles, total = client.get_top_headlines(country='us', page_size=3)
    print(f"   Found {total} headlines, showing {len(articles)}:")
    for a in articles:
        print(f"   - [{a.source_name}] {a.title[:50]}...")
    
    print("\n✅ All tests passed!")

