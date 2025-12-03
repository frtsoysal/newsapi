"""
Configuration
=============

Load environment variables and config settings.
"""

import os
from pathlib import Path

# Try to load .env file
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY', '9269b16560454b61af6508052e53e4a1')

# API Settings
NEWSAPI_BASE_URL = "https://newsapi.org/v2"
GAMMA_API_BASE_URL = "https://gamma-api.polymarket.com"

# Defaults
DEFAULT_LANGUAGE = 'en'
MAX_ARTICLES_PER_EVENT = 5
DEFAULT_DAYS_BACK = 7

