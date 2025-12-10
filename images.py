"""
images.py - Cat image fetching for Cat Caption Cage Match

Handles fetching random cat images from TheCatAPI with a local fallback
for offline/dev mode.
"""

import os
import io
import random
import requests
from pathlib import Path
from PIL import Image
from typing import Optional, Tuple


# TheCatAPI endpoint
CAT_API_URL = "https://api.thecatapi.com/v1/images/search"

# Local fallback directory
LOCAL_CATS_DIR = Path(__file__).parent / "static" / "cats"

# Cache for the last fetched image (to avoid re-fetching)
_last_image: Optional[Image.Image] = None
_last_image_url: Optional[str] = None


def fetch_random_cat() -> Tuple[Image.Image, str]:
    """
    Fetch a random cat image.
    
    Returns:
        Tuple of (PIL.Image, image_url)
    
    First tries TheCatAPI, falls back to local images if API fails.
    """
    global _last_image, _last_image_url
    
    # Try TheCatAPI first
    image, url = _fetch_from_api()
    
    if image is None:
        # Fall back to local images
        image, url = _fetch_from_local()
    
    if image is None:
        # Ultimate fallback: generate a placeholder
        image, url = _generate_placeholder()
    
    _last_image = image
    _last_image_url = url
    
    return image, url


def _fetch_from_api() -> Tuple[Optional[Image.Image], Optional[str]]:
    """Fetch a cat image from TheCatAPI."""
    try:
        api_key = os.environ.get("THECATAPI_KEY", "")
        headers = {"x-api-key": api_key} if api_key else {}
        
        params = {
            "size": "med",
            "mime_types": "jpg,png",
            "limit": 1
        }
        
        response = requests.get(
            CAT_API_URL,
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if not data:
            return None, None
        
        image_url = data[0]["url"]
        
        # Download the image
        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()
        
        image = Image.open(io.BytesIO(img_response.content))
        
        # Convert to RGB if necessary (some PNGs have alpha channel)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        return image, image_url
        
    except Exception as e:
        print(f"TheCatAPI error: {e}")
        return None, None


def _fetch_from_local() -> Tuple[Optional[Image.Image], Optional[str]]:
    """Fetch a random cat image from local directory."""
    try:
        if not LOCAL_CATS_DIR.exists():
            return None, None
        
        # Find all image files
        image_files = list(LOCAL_CATS_DIR.glob("*.jpg")) + \
                      list(LOCAL_CATS_DIR.glob("*.jpeg")) + \
                      list(LOCAL_CATS_DIR.glob("*.png"))
        
        if not image_files:
            return None, None
        
        # Pick a random image
        image_path = random.choice(image_files)
        image = Image.open(image_path)
        
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        return image, f"local:{image_path.name}"
        
    except Exception as e:
        print(f"Local image error: {e}")
        return None, None


def _generate_placeholder() -> Tuple[Image.Image, str]:
    """Generate a placeholder image when no cats are available."""
    # Create a simple colored placeholder with text
    from PIL import ImageDraw, ImageFont
    
    width, height = 400, 300
    
    # Random pastel color
    r = random.randint(180, 255)
    g = random.randint(180, 255)
    b = random.randint(180, 255)
    
    image = Image.new('RGB', (width, height), (r, g, b))
    draw = ImageDraw.Draw(image)
    
    # Draw a simple cat face
    # Ears
    draw.polygon([(80, 100), (120, 40), (160, 100)], fill=(100, 100, 100))
    draw.polygon([(240, 100), (280, 40), (320, 100)], fill=(100, 100, 100))
    
    # Face
    draw.ellipse([(100, 80), (300, 250)], fill=(150, 150, 150))
    
    # Eyes
    draw.ellipse([(140, 130), (180, 170)], fill=(255, 255, 255))
    draw.ellipse([(220, 130), (260, 170)], fill=(255, 255, 255))
    draw.ellipse([(150, 140), (170, 160)], fill=(50, 50, 50))
    draw.ellipse([(230, 140), (250, 160)], fill=(50, 50, 50))
    
    # Nose
    draw.polygon([(190, 180), (210, 180), (200, 195)], fill=(255, 150, 150))
    
    # Whiskers
    for y_offset in [-10, 0, 10]:
        draw.line([(100, 190 + y_offset), (150, 185 + y_offset)], fill=(80, 80, 80), width=1)
        draw.line([(250, 185 + y_offset), (300, 190 + y_offset)], fill=(80, 80, 80), width=1)
    
    return image, "placeholder:generated"


def image_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    image.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def get_last_image() -> Tuple[Optional[Image.Image], Optional[str]]:
    """Get the last fetched image (useful for sharing same image to all players)."""
    return _last_image, _last_image_url


def describe_image_for_llm(image: Image.Image) -> str:
    """
    Generate a basic description of the image for the LLM.
    
    For now, just returns basic metadata. Could be enhanced with
    actual image description via vision model.
    """
    width, height = image.size
    aspect = "landscape" if width > height else "portrait" if height > width else "square"
    
    return f"A {aspect} cat photo ({width}x{height} pixels)"


def ensure_local_cats_dir() -> None:
    """Ensure the local cats directory exists."""
    LOCAL_CATS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create a .gitkeep file
    gitkeep = LOCAL_CATS_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
