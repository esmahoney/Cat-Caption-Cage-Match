"""
llm.py - LLM scoring and roast mode for Cat Caption Cage Match

Handles all interactions with Google Gemini for caption scoring.
Includes a fake_llm mode for testing without an API key.
"""

import os
import json
import random
import hashlib
from typing import Optional
from PIL import Image

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


# Model configuration
MODEL_NAME = "gemini-2.5-pro-preview-06-05"
VISION_MODEL_NAME = "gemini-2.0-flash"

# Cached model instance
_model = None
_configured = False


def configure_api() -> bool:
    """Configure the Gemini API with the API key from environment."""
    global _configured
    
    if not GENAI_AVAILABLE:
        print("Warning: google-generativeai not installed")
        return False
    
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("Warning: GOOGLE_API_KEY not set")
        return False
    
    try:
        genai.configure(api_key=api_key)
        _configured = True
        return True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return False


def get_model():
    """Get the Gemini model instance."""
    global _model
    
    if not _configured:
        configure_api()
    
    if _model is None and _configured:
        _model = genai.GenerativeModel(VISION_MODEL_NAME)
    
    return _model


def is_fake_mode() -> bool:
    """Check if fake LLM mode is enabled."""
    return os.environ.get("FAKE_LLM_MODE", "").lower() == "true"


def score_captions(
    image: Image.Image,
    captions: list[dict],
    image_description: Optional[str] = None
) -> list[dict]:
    """
    Score all captions for a round using the LLM.
    
    Args:
        image: The cat image for this round
        captions: List of {'player_name': str, 'caption': str}
        image_description: Optional description of the image
    
    Returns:
        List of {'player_name': str, 'caption': str, 'score': int, 'roast_comment': str}
    """
    if not captions:
        return []
    
    # Use fake mode if enabled or if API not available
    if is_fake_mode() or not _configured:
        return _fake_score_captions(captions)
    
    try:
        return _llm_score_captions(image, captions, image_description)
    except Exception as e:
        print(f"LLM scoring failed: {e}")
        # Fall back to fake scoring
        return _fake_score_captions(captions)


def _llm_score_captions(
    image: Image.Image,
    captions: list[dict],
    image_description: Optional[str] = None
) -> list[dict]:
    """Score captions using the actual Gemini LLM."""
    model = get_model()
    if model is None:
        return _fake_score_captions(captions)
    
    # Build the caption list for the prompt
    caption_list = "\n".join([
        f"{i+1}. Player: \"{c['player_name']}\" - Caption: \"{c['caption']}\""
        for i, c in enumerate(captions)
    ])
    
    prompt = f"""You are "Cat Meme Gordon Ramsay" - a brutally honest but hilarious judge of cat meme captions.

Your job is to rate each caption on a scale of 0-10 based on:
- HUMOR (0-10): How funny is it? Does it make you laugh?
- RELEVANCE (0-10): How well does it relate to the cat image?

The final score is the average of humor and relevance, rounded to the nearest integer.

BE RUTHLESS. Be honest. Avoid ties when possible - there should be clear winners and losers.
Add a short, snarky roast comment for each caption in your Gordon Ramsay style (1-2 sentences max).

Here are the captions to judge:

{caption_list}

Respond with ONLY valid JSON in this exact format (no markdown, no extra text):
{{
    "results": [
        {{
            "player_name": "player name exactly as given",
            "caption": "the caption exactly as given",
            "score": 7,
            "roast_comment": "Your snarky comment here"
        }}
    ]
}}

Make sure to include ALL captions in your response, in the same order as given."""

    try:
        # Call the model with image and prompt
        response = model.generate_content([image, prompt])
        
        # Parse the JSON response
        response_text = response.text.strip()
        
        # Clean up common JSON issues
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        results = data.get("results", [])
        
        # Validate and clean up results
        scored_results = []
        for result in results:
            scored_results.append({
                'player_name': result.get('player_name', 'Unknown'),
                'caption': result.get('caption', ''),
                'score': max(0, min(10, int(result.get('score', 5)))),
                'roast_comment': result.get('roast_comment', 'No comment.')
            })
        
        return scored_results
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response as JSON: {e}")
        return _fake_score_captions(captions)
    except Exception as e:
        print(f"LLM scoring error: {e}")
        return _fake_score_captions(captions)


def _fake_score_captions(captions: list[dict]) -> list[dict]:
    """
    Generate fake scores for testing without an API key.
    
    Uses deterministic scoring based on caption content so results
    are reproducible but still varied.
    """
    results = []
    
    # Pre-defined roast comments for fake mode
    roast_comments = [
        "This is what happens when you let interns write memes.",
        "I've seen better captions on a milk carton.",
        "Did you write this with your eyes closed?",
        "My grandmother's cat could do better, and she's been dead for years.",
        "This is so bad it's almost impressive. Almost.",
        "Were you trying to be funny, or was that an accident?",
        "I've had more laughs at a funeral.",
        "This caption is the human equivalent of a participation trophy.",
        "Somewhere, a comedy writer just felt a disturbance in the force.",
        "If mediocrity was a caption, this would be it.",
        "Actually not terrible. I'm as surprised as you are.",
        "Finally, someone who understands cats!",
        "This made me snort. Well done, you absolute legend.",
    ]
    
    for caption_data in captions:
        caption = caption_data.get('caption', '')
        player_name = caption_data.get('player_name', 'Unknown')
        
        # Generate deterministic score based on caption content
        caption_hash = hashlib.md5(caption.encode()).hexdigest()
        base_score = int(caption_hash[:2], 16) % 11  # 0-10
        
        # Add some variation based on word count and length
        word_count = len(caption.split())
        length_bonus = min(2, word_count // 3)  # Bonus for longer captions
        
        # Penalize very short or very long captions
        if word_count < 3:
            base_score = max(0, base_score - 2)
        elif word_count > 12:
            base_score = max(0, base_score - 1)
        
        final_score = max(0, min(10, base_score + length_bonus))
        
        # Pick a roast comment based on score
        if final_score >= 8:
            comment_pool = roast_comments[-3:]  # Positive-ish
        elif final_score >= 5:
            comment_pool = roast_comments[5:10]  # Neutral
        else:
            comment_pool = roast_comments[:5]  # Harsh
        
        # Deterministic comment selection
        comment_idx = int(caption_hash[2:4], 16) % len(comment_pool)
        
        results.append({
            'player_name': player_name,
            'caption': caption,
            'score': final_score,
            'roast_comment': comment_pool[comment_idx]
        })
    
    return results


def test_api_connection() -> tuple[bool, str]:
    """Test if the Gemini API is working."""
    if is_fake_mode():
        return True, "Fake LLM mode enabled (no API call made)"
    
    if not GENAI_AVAILABLE:
        return False, "google-generativeai package not installed"
    
    if not configure_api():
        return False, "Failed to configure API (check GOOGLE_API_KEY)"
    
    try:
        model = get_model()
        if model is None:
            return False, "Could not create model instance"
        
        # Simple test prompt
        response = model.generate_content("Say 'meow' if you can hear me.")
        if response and response.text:
            return True, f"API working! Response: {response.text[:50]}..."
        return False, "API returned empty response"
        
    except Exception as e:
        return False, f"API test failed: {e}"
