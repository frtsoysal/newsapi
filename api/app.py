"""
FastAPI Application
===================

Main FastAPI application for Polymarket News API.
"""

import sys
sys.path.insert(0, '/Users/ibrahimfiratsoysal/Bloomberg for prediction markets/backend')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

# Create FastAPI app
app = FastAPI(
    title="Polymarket News API",
    description="""
    API for fetching Polymarket prediction market events with related news articles and AI-generated summaries.
    
    ## Features
    
    - **Events**: Fetch active/closed prediction market events from Polymarket
    - **News Matching**: Automatically find relevant news articles for each event
    - **AI Summaries**: Generate context summaries using OpenAI (requires API key)
    
    ## Environment Variables
    
    - `NEWSAPI_KEY`: News API key (required for news fetching)
    - `OPENAI_API_KEY`: OpenAI API key (optional, for AI summaries)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Polymarket News API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

