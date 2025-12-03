"""FastAPI application module"""
from .routes import router
from .app import app

__all__ = ['router', 'app']

