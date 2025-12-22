"""
Cat image fetching service.

Fetches random cat images from TheCatAPI with fallbacks.
"""
import os
import random
from pathlib import Path

import httpx

from ..config import get_settings


# TheCatAPI endpoint
CAT_API_URL = "https://api.thecatapi.com/v1/images/search"

# Fallback placeholder images (when API is unavailable)
PLACEHOLDER_CATS = [
    "https://placekitten.com/600/400",
    "https://placekitten.com/500/400",
    "https://placekitten.com/600/500",
    "https://placekitten.com/550/450",
]


async def fetch_random_cat_url() -> str:
    """
    Fetch a random cat image URL.
    
    Tries TheCatAPI first, falls back to placeholder images.
    """
    settings = get_settings()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.thecatapi_key:
                headers["x-api-key"] = settings.thecatapi_key
            
            response = await client.get(
                CAT_API_URL,
                headers=headers,
                params={
                    "size": "med",
                    "mime_types": "jpg,png",
                    "limit": 1,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                return data[0]["url"]
    
    except Exception as e:
        print(f"TheCatAPI error: {e}")
    
    # Fallback to placeholder
    return random.choice(PLACEHOLDER_CATS)


async def fetch_cat_image_bytes(url: str) -> bytes:
    """
    Fetch image bytes from a URL.
    
    Useful if you need the actual image data (e.g., for LLM vision).
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

