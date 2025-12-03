"""
FastAPI Routes
==============

API endpoints for Polymarket events with news summaries.
"""

import sys
sys.path.insert(0, '/Users/ibrahimfiratsoysal/Bloomberg for prediction markets/backend')

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from polymarket.client import PolymarketClient, Event
from newsapi.client import NewsAPIClient
from pipeline.matching import match_news_to_event, ScoredArticle
from ai.summarizer import AISummarizer

from .models import (
    EventWithNewsResponse,
    EventListResponse,
    ArticleResponse,
    MarketResponse,
    EventSummaryResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api/v1", tags=["events"])


def event_to_response(
    event: Event,
    articles: list[ScoredArticle],
    summary: Optional[dict] = None,
) -> EventWithNewsResponse:
    """Convert internal models to API response"""
    
    # Convert markets
    markets = []
    for m in event.markets:
        markets.append(MarketResponse(
            id=m.id,
            question=m.question,
            outcomes=m.outcomes,
            prices=m.outcome_prices,
        ))
    
    # Convert articles
    article_responses = []
    for sa in articles:
        a = sa.article
        article_responses.append(ArticleResponse(
            source_name=a.source_name,
            title=a.title,
            description=a.description,
            url=a.url,
            image_url=a.image_url,
            published_at=a.published_at,
            relevance_score=sa.score,
        ))
    
    # Convert summary
    summary_response = None
    if summary:
        summary_response = EventSummaryResponse(
            summary=summary.summary,
            key_points=summary.key_points,
            sentiment=summary.sentiment,
            confidence=summary.confidence,
            sources_used=summary.sources_used,
        )
    
    return EventWithNewsResponse(
        id=event.id,
        slug=event.slug,
        title=event.title,
        description=event.description,
        category=event.category,
        tags=event.tags,
        start_date=event.start_date,
        end_date=event.end_date,
        volume=event.volume,
        active=event.active,
        closed=event.closed,
        markets=markets,
        articles=article_responses,
        summary=summary_response,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    # Test services
    poly_ok = False
    news_ok = False
    
    try:
        client = PolymarketClient()
        events = client.get_events(limit=1)
        poly_ok = len(events) > 0
    except:
        pass
    
    try:
        client = NewsAPIClient()
        articles, _ = client.get_top_headlines(country='us', page_size=1)
        news_ok = len(articles) > 0
    except:
        pass
    
    return HealthResponse(
        status="ok" if (poly_ok and news_ok) else "degraded",
        version="1.0.0",
        services={
            "polymarket": poly_ok,
            "newsapi": news_ok,
        }
    )


@router.get("/events", response_model=EventListResponse)
async def get_events_with_news(
    limit: int = Query(default=10, ge=1, le=50, description="Number of events to return"),
    page: int = Query(default=1, ge=1, description="Page number"),
    active: bool = Query(default=True, description="Filter by active events"),
    closed: bool = Query(default=False, description="Include closed events"),
    include_news: bool = Query(default=True, description="Include news articles"),
    include_summary: bool = Query(default=True, description="Include AI summary"),
    max_articles: int = Query(default=5, ge=1, le=10, description="Max articles per event"),
):
    """
    Get Polymarket events with related news and AI summaries
    
    Returns paginated list of events with:
    - Event metadata (title, description, markets)
    - Related news articles (scored by relevance)
    - AI-generated summary (if enabled)
    """
    try:
        # Fetch events
        poly_client = PolymarketClient()
        offset = (page - 1) * limit
        events = poly_client.get_events(
            limit=limit,
            offset=offset,
            active=active,
            closed=closed,
        )
        
        # Process each event
        summarizer = AISummarizer() if include_summary else None
        results = []
        
        for event in events:
            # Match news
            articles = []
            if include_news:
                articles = match_news_to_event(event, max_articles=max_articles)
            
            # Generate summary
            summary = None
            if include_summary and summarizer and articles:
                market_price = None
                if event.markets and event.markets[0].outcome_prices:
                    market_price = event.markets[0].outcome_prices[0]
                
                summary = summarizer.summarize_event(
                    event_title=event.title,
                    event_description=event.description,
                    articles=articles,
                    market_price=market_price,
                )
            
            results.append(event_to_response(event, articles, summary))
        
        return EventListResponse(
            events=results,
            total=len(results),  # Could get actual total from API pagination
            page=page,
            limit=limit,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_slug}", response_model=EventWithNewsResponse)
async def get_event_with_news(
    event_slug: str,
    max_articles: int = Query(default=5, ge=1, le=10, description="Max articles"),
    include_summary: bool = Query(default=True, description="Include AI summary"),
):
    """
    Get single event by slug with related news and AI summary
    """
    try:
        # Fetch event
        poly_client = PolymarketClient()
        event = poly_client.get_event_by_slug(event_slug)
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event '{event_slug}' not found")
        
        # Match news
        articles = match_news_to_event(event, max_articles=max_articles)
        
        # Generate summary
        summary = None
        if include_summary and articles:
            summarizer = AISummarizer()
            market_price = None
            if event.markets and event.markets[0].outcome_prices:
                market_price = event.markets[0].outcome_prices[0]
            
            summary = summarizer.summarize_event(
                event_title=event.title,
                event_description=event.description,
                articles=articles,
                market_price=market_price,
            )
        
        return event_to_response(event, articles, summary)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_slug}/news", response_model=list[ArticleResponse])
async def get_event_news(
    event_slug: str,
    max_articles: int = Query(default=10, ge=1, le=20, description="Max articles"),
):
    """
    Get only news articles for an event (without summary)
    """
    try:
        # Fetch event
        poly_client = PolymarketClient()
        event = poly_client.get_event_by_slug(event_slug)
        
        if not event:
            raise HTTPException(status_code=404, detail=f"Event '{event_slug}' not found")
        
        # Match news
        articles = match_news_to_event(event, max_articles=max_articles)
        
        # Convert to response
        return [
            ArticleResponse(
                source_name=sa.article.source_name,
                title=sa.article.title,
                description=sa.article.description,
                url=sa.article.url,
                image_url=sa.article.image_url,
                published_at=sa.article.published_at,
                relevance_score=sa.score,
            )
            for sa in articles
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_events(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=10, ge=1, le=20, description="Max results"),
    include_news: bool = Query(default=False, description="Include news for each result"),
):
    """
    Search events by keyword
    """
    try:
        poly_client = PolymarketClient()
        events = poly_client.search_events(query=q, limit=limit)
        
        results = []
        for event in events:
            articles = []
            if include_news:
                articles = match_news_to_event(event, max_articles=3)
            
            results.append(event_to_response(event, articles, None))
        
        return {
            "query": q,
            "results": results,
            "count": len(results),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

