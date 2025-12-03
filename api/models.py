"""
Pydantic models for API responses
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ArticleResponse(BaseModel):
    """News article response"""
    source_name: str
    title: str
    description: Optional[str]
    url: str
    image_url: Optional[str]
    published_at: Optional[datetime]
    relevance_score: float


class MarketResponse(BaseModel):
    """Market (outcome) response"""
    id: str
    question: str
    outcomes: list[str]
    prices: list[float]


class EventSummaryResponse(BaseModel):
    """AI-generated summary response"""
    summary: str
    key_points: list[str]
    sentiment: str
    confidence: str
    sources_used: int


class EventWithNewsResponse(BaseModel):
    """Full event with news and summary"""
    id: str
    slug: str
    title: str
    description: str
    category: Optional[str]
    tags: list[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    volume: float
    active: bool
    closed: bool
    markets: list[MarketResponse]
    articles: list[ArticleResponse]
    summary: Optional[EventSummaryResponse]


class EventListResponse(BaseModel):
    """List of events response"""
    events: list[EventWithNewsResponse]
    total: int
    page: int
    limit: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    services: dict[str, bool]

