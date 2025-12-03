"""
Polymarket Gamma API Client
===========================

Gamma API'den event ve market verilerini çeker.
Endpoint: https://gamma-api.polymarket.com
"""

import urllib.request
import urllib.parse
import json
import ssl
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

# SSL verification bypass for development
ssl._create_default_https_context = ssl._create_unverified_context

GAMMA_API_BASE = "https://gamma-api.polymarket.com"


@dataclass
class Market:
    """Polymarket market (outcome) model"""
    id: str
    question: str
    slug: str
    outcomes: list[str]
    outcome_prices: list[float]
    volume: float
    active: bool
    closed: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class Event:
    """Polymarket event model"""
    id: str
    slug: str
    title: str
    description: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    category: Optional[str]
    tags: list[str]
    active: bool
    closed: bool
    volume: float
    markets: list[Market] = field(default_factory=list)
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Event':
        """Parse API response into Event object"""
        # Parse dates
        start_date = None
        end_date = None
        
        if data.get('startDate'):
            try:
                start_date = datetime.fromisoformat(data['startDate'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        if data.get('endDate'):
            try:
                end_date = datetime.fromisoformat(data['endDate'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        # Parse tags
        tags = []
        for tag in data.get('tags', []):
            if isinstance(tag, dict) and tag.get('label'):
                tags.append(tag['label'])
            elif isinstance(tag, str):
                tags.append(tag)
        
        # Parse markets
        markets = []
        for m in data.get('markets', []):
            try:
                # Parse outcomes
                outcomes = m.get('outcomes', '[]')
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                
                # Parse outcome prices
                prices = m.get('outcomePrices', '[]')
                if isinstance(prices, str):
                    prices = json.loads(prices)
                prices = [float(p) for p in prices]
                
                market = Market(
                    id=str(m.get('id', '')),
                    question=m.get('question', ''),
                    slug=m.get('slug', ''),
                    outcomes=outcomes,
                    outcome_prices=prices,
                    volume=float(m.get('volumeNum', 0) or m.get('volume', 0) or 0),
                    active=m.get('active', False),
                    closed=m.get('closed', False),
                )
                markets.append(market)
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        
        return cls(
            id=str(data.get('id', '')),
            slug=data.get('slug', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            start_date=start_date,
            end_date=end_date,
            category=data.get('category'),
            tags=tags,
            active=data.get('active', False),
            closed=data.get('closed', False),
            volume=float(data.get('volume', 0) or 0),
            markets=markets,
        )


class PolymarketClient:
    """Gamma API client for fetching Polymarket events"""
    
    def __init__(self, base_url: str = GAMMA_API_BASE):
        self.base_url = base_url
    
    def _request(self, endpoint: str, params: dict = None) -> dict | list:
        """Make HTTP request to Gamma API"""
        url = f"{self.base_url}{endpoint}"
        
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    
    def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = 'volume',
        ascending: bool = False,
    ) -> list[Event]:
        """
        Fetch events from Gamma API
        
        Args:
            limit: Max events to return (default 50)
            offset: Pagination offset
            active: Filter by active status
            closed: Filter by closed status
            order: Sort field (volume, startDate, endDate)
            ascending: Sort direction
            
        Returns:
            List of Event objects
        """
        params = {
            'limit': limit,
            'offset': offset,
            'active': str(active).lower(),
            'closed': str(closed).lower(),
            'order': order,
            'ascending': str(ascending).lower(),
        }
        
        data = self._request('/events', params)
        
        # Handle both array and object responses
        if isinstance(data, list):
            events_data = data
        else:
            events_data = data.get('events', data.get('data', []))
        
        return [Event.from_api_response(e) for e in events_data]
    
    def get_event_by_slug(self, slug: str) -> Optional[Event]:
        """
        Fetch single event by slug
        
        Args:
            slug: Event slug (e.g. 'fed-rate-hike-in-2025')
            
        Returns:
            Event object or None if not found
        """
        try:
            # Gamma API uses query param for slug lookup
            data = self._request('/events', {'slug': slug})
            
            # Handle both array and object responses
            if isinstance(data, list):
                events_data = data
            else:
                events_data = data.get('events', data.get('data', []))
            
            if events_data:
                return Event.from_api_response(events_data[0])
            return None
        except urllib.error.HTTPError as e:
            if e.code in (404, 422):
                return None
            raise
    
    def search_events(
        self,
        query: str,
        limit: int = 20,
        active: bool = True,
    ) -> list[Event]:
        """
        Search events by title/description (client-side filtering)
        
        Args:
            query: Search term
            limit: Max results
            active: Filter by active status
            
        Returns:
            List of matching Event objects
        """
        # Fetch more events for filtering
        events = self.get_events(limit=100, active=active)
        
        query_lower = query.lower()
        matches = []
        
        for event in events:
            # Check title, description, and tags
            searchable = f"{event.title} {event.description} {' '.join(event.tags)}".lower()
            if query_lower in searchable:
                matches.append(event)
                if len(matches) >= limit:
                    break
        
        return matches


# Convenience function
def get_active_events(limit: int = 50) -> list[Event]:
    """Quick access to active events sorted by volume"""
    client = PolymarketClient()
    return client.get_events(limit=limit, active=True, closed=False, order='volume')


if __name__ == "__main__":
    # Test the client
    print("Testing PolymarketClient...")
    
    client = PolymarketClient()
    events = client.get_events(limit=5)
    
    print(f"\nFetched {len(events)} events:\n")
    
    for event in events:
        print(f"📌 {event.title}")
        print(f"   ID: {event.id} | Slug: {event.slug}")
        print(f"   Volume: ${event.volume:,.0f}")
        print(f"   Tags: {event.tags[:3]}")
        print(f"   Markets: {len(event.markets)}")
        if event.markets:
            m = event.markets[0]
            print(f"     → {m.question[:50]}...")
            print(f"       Prices: {m.outcome_prices}")
        print()

