"""
AI Summarizer
=============

Polymarket eventleri ve ilgili haberler için AI özet üretir.
OpenAI API kullanır.
"""

import sys
sys.path.insert(0, '/Users/ibrahimfiratsoysal/Bloomberg for prediction markets/backend')

import json
import urllib.request
import ssl
from dataclasses import dataclass
from typing import Optional

# Load config (includes .env loading)
from config import OPENAI_API_KEY

# SSL verification bypass for development
ssl._create_default_https_context = ssl._create_unverified_context

# OpenAI API config
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class EventSummary:
    """AI-generated summary for an event"""
    event_title: str
    summary: str
    key_points: list[str]
    sentiment: str  # bullish, bearish, neutral
    confidence: str  # high, medium, low
    sources_used: int


# System prompt for summarization
SYSTEM_PROMPT = """You are a financial analyst assistant that summarizes news for prediction market events.

Your task:
1. Analyze the provided news articles related to a prediction market event
2. Generate a concise, objective summary
3. Extract key points that might influence the market
4. Assess the overall sentiment (bullish = event likely to happen, bearish = unlikely, neutral = unclear)
5. Rate your confidence based on news quality and relevance

IMPORTANT:
- Be objective, don't predict outcomes
- Focus on facts from the news
- Note any conflicting information
- Keep summary under 150 words
- Return JSON format only"""


USER_PROMPT_TEMPLATE = """Prediction Market Event:
Title: {event_title}
Description: {event_description}
Current Market Price: {market_price}

Related News Articles:
{articles_text}

Generate a summary in this JSON format:
{{
    "summary": "Brief 2-3 sentence overview of the situation",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "sentiment": "bullish|bearish|neutral",
    "confidence": "high|medium|low"
}}"""


class AISummarizer:
    """AI-powered event summarizer using OpenAI"""
    
    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model
        
        if not self.api_key:
            print("⚠️  Warning: OPENAI_API_KEY not set. AI summaries will be disabled.")
    
    def _call_openai(self, messages: list[dict]) -> str:
        """Make request to OpenAI API"""
        if not self.api_key:
            return None
        
        url = f"{OPENAI_API_BASE}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }
        
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {self.api_key}')
        
        with urllib.request.urlopen(req, data=data, timeout=30) as response:
            result = json.loads(response.read().decode())
        
        return result['choices'][0]['message']['content']
    
    def summarize_event(
        self,
        event_title: str,
        event_description: str,
        articles: list,  # List of Article or ScoredArticle
        market_price: float = None,
    ) -> Optional[EventSummary]:
        """
        Generate AI summary for event with related news
        
        Args:
            event_title: Event title
            event_description: Event description
            articles: List of relevant articles
            market_price: Current Yes price (0-1)
            
        Returns:
            EventSummary object or None if failed
        """
        if not self.api_key:
            return self._fallback_summary(event_title, articles)
        
        if not articles:
            return EventSummary(
                event_title=event_title,
                summary="No relevant news articles found for this event.",
                key_points=["No recent news coverage"],
                sentiment="neutral",
                confidence="low",
                sources_used=0,
            )
        
        # Build articles text
        articles_text = ""
        for i, article in enumerate(articles[:5], 1):
            # Handle both Article and ScoredArticle
            if hasattr(article, 'article'):
                a = article.article
            else:
                a = article
            
            articles_text += f"\n{i}. [{a.source_name}] {a.title}\n"
            if a.description:
                articles_text += f"   {a.description[:200]}...\n"
        
        # Format market price
        price_str = f"{market_price*100:.0f}% Yes" if market_price else "N/A"
        
        # Build prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            event_title=event_title,
            event_description=event_description[:300] if event_description else "N/A",
            market_price=price_str,
            articles_text=articles_text,
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            response = self._call_openai(messages)
            
            # Parse JSON response
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            data = json.loads(response.strip())
            
            return EventSummary(
                event_title=event_title,
                summary=data.get('summary', ''),
                key_points=data.get('key_points', []),
                sentiment=data.get('sentiment', 'neutral'),
                confidence=data.get('confidence', 'medium'),
                sources_used=len(articles),
            )
            
        except Exception as e:
            print(f"AI summarization error: {e}")
            return self._fallback_summary(event_title, articles)
    
    def _fallback_summary(
        self,
        event_title: str,
        articles: list,
    ) -> EventSummary:
        """Generate fallback summary without AI"""
        if not articles:
            return EventSummary(
                event_title=event_title,
                summary="No news articles found.",
                key_points=[],
                sentiment="neutral",
                confidence="low",
                sources_used=0,
            )
        
        # Extract headlines as key points
        key_points = []
        for article in articles[:3]:
            if hasattr(article, 'article'):
                a = article.article
            else:
                a = article
            key_points.append(f"[{a.source_name}] {a.title[:80]}")
        
        return EventSummary(
            event_title=event_title,
            summary=f"Found {len(articles)} relevant news articles. AI summary unavailable (set OPENAI_API_KEY).",
            key_points=key_points,
            sentiment="neutral",
            confidence="low",
            sources_used=len(articles),
        )


# Convenience function
def summarize_event_news(
    event_title: str,
    event_description: str,
    articles: list,
    market_price: float = None,
) -> Optional[EventSummary]:
    """Quick summary generation"""
    summarizer = AISummarizer()
    return summarizer.summarize_event(
        event_title=event_title,
        event_description=event_description,
        articles=articles,
        market_price=market_price,
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/ibrahimfiratsoysal/Bloomberg for prediction markets/backend')
    
    from polymarket.client import PolymarketClient
    from pipeline.matching import match_news_to_event
    
    print("Testing AI Summarizer")
    print("=" * 60)
    
    # Get an event
    poly_client = PolymarketClient()
    events = poly_client.get_events(limit=1)
    
    if events:
        event = events[0]
        print(f"\n📌 Event: {event.title}")
        
        # Match news
        scored_articles = match_news_to_event(event, max_articles=5)
        print(f"   Found {len(scored_articles)} articles")
        
        # Get market price
        market_price = None
        if event.markets:
            prices = event.markets[0].outcome_prices
            if prices:
                market_price = prices[0]
        
        # Generate summary
        print("\n🤖 Generating AI summary...")
        summarizer = AISummarizer()
        summary = summarizer.summarize_event(
            event_title=event.title,
            event_description=event.description,
            articles=scored_articles,
            market_price=market_price,
        )
        
        if summary:
            print(f"\n📝 Summary:\n{summary.summary}")
            print(f"\n📋 Key Points:")
            for point in summary.key_points:
                print(f"   • {point}")
            print(f"\n📊 Sentiment: {summary.sentiment}")
            print(f"🎯 Confidence: {summary.confidence}")
            print(f"📰 Sources: {summary.sources_used}")
    
    print("\n✅ Test completed!")

