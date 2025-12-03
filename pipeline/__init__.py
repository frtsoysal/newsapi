"""Event-News matching pipeline module"""
from .matching import (
    build_news_query,
    get_time_window,
    score_article,
    match_news_to_event,
    ScoredArticle,
)

__all__ = [
    'build_news_query',
    'get_time_window', 
    'score_article',
    'match_news_to_event',
    'ScoredArticle',
]

