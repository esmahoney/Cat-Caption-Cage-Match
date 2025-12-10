"""
llm.py - LLM scoring and roast mode for Cat Caption Cage Match

Handles all interactions with LLMs (Groq or Google Gemini) for caption scoring.
Includes a fake_llm mode for testing without an API key.
"""

import os
import json
import random
import hashlib
import base64
import io
from typing import Optional
from PIL import Image

# Try to import Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


# Model configuration
# Using llama-3.3-70b for text scoring (vision models have access issues)
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-1.5-flash"

# Cached instances
_groq_client = None
_gemini_model = None
_configured_provider = None  # 'groq', 'gemini', or None


def configure_api() -> bool:
    """Configure the LLM API. Tries Groq first, then Gemini."""
    global _configured_provider, _groq_client, _gemini_model
    
    # Try Groq first
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key and GROQ_AVAILABLE:
        try:
            _groq_client = Groq(api_key=groq_key)
            _configured_provider = 'groq'
            return True
        except Exception as e:
            print(f"Groq configuration failed: {e}")
    
    # Fall back to Gemini
    gemini_key = os.environ.get("GOOGLE_API_KEY", "")
    if gemini_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=gemini_key)
            _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            _configured_provider = 'gemini'
            return True
        except Exception as e:
            print(f"Gemini configuration failed: {e}")
    
    if not GROQ_AVAILABLE and not GENAI_AVAILABLE:
        print("Warning: Neither groq nor google-generativeai packages installed")
    elif not groq_key and not gemini_key:
        print("Warning: Neither GROQ_API_KEY nor GOOGLE_API_KEY set")
    
    return False


def is_fake_mode() -> bool:
    """Check if fake LLM mode is enabled."""
    return os.environ.get("FAKE_LLM_MODE", "").lower() == "true"


def _image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


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
    
    # Use fake mode if enabled or if no API configured
    if is_fake_mode() or _configured_provider is None:
        return _fake_score_captions(captions)
    
    try:
        if _configured_provider == 'groq':
            return _groq_score_captions(image, captions)
        elif _configured_provider == 'gemini':
            return _gemini_score_captions(image, captions)
        else:
            return _fake_score_captions(captions)
    except Exception as e:
        print(f"LLM scoring failed: {e}")
        # Fall back to fake scoring
        return _fake_score_captions(captions)


def _build_prompt(captions: list[dict], has_image: bool = False) -> str:
    """Build the scoring prompt."""
    caption_list = "\n".join([
        f"{i+1}. Player: \"{c['player_name']}\" - Caption: \"{c['caption']}\""
        for i, c in enumerate(captions)
    ])
    
    if has_image:
        criteria = """Your job is to rate each caption on a scale of 0-10 based on:
- HUMOR (0-10): How funny is it? Does it make you laugh?
- RELEVANCE (0-10): How well does it relate to the cat image?

The final score is the average of humor and relevance, rounded to the nearest integer."""
    else:
        criteria = """Your job is to rate each caption on a scale of 0-10 based on:
- HUMOR (0-10): How funny is it? Does it make you laugh?
- CREATIVITY (0-10): How clever or original is it as a cat meme caption?

The final score is the average of humor and creativity, rounded to the nearest integer."""
    
    return f"""You are "Cat Meme Gordon Ramsay" - a brutally honest but hilarious judge of cat meme captions.

{criteria}

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


def _parse_llm_response(response_text: str, captions: list[dict]) -> list[dict]:
    """Parse and validate LLM response."""
    # Clean up common JSON issues
    response_text = response_text.strip()
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


def _groq_score_captions(image: Image.Image, captions: list[dict]) -> list[dict]:
    """Score captions using Groq API (text-only mode for now)."""
    if _groq_client is None:
        return _fake_score_captions(captions)
    
    prompt = _build_prompt(captions, has_image=False)
    
    try:
        # Using text model - captions are judged on humor/creativity alone
        response = _groq_client.chat.completions.create(
            model=GROQ_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1024,
            temperature=0.7
        )
        
        response_text = response.choices[0].message.content
        return _parse_llm_response(response_text, captions)
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse Groq response as JSON: {e}")
        return _fake_score_captions(captions)
    except Exception as e:
        print(f"Groq scoring error: {e}")
        return _fake_score_captions(captions)


def _gemini_score_captions(image: Image.Image, captions: list[dict]) -> list[dict]:
    """Score captions using Gemini API."""
    if _gemini_model is None:
        return _fake_score_captions(captions)
    
    prompt = _build_prompt(captions, has_image=True)
    
    try:
        response = _gemini_model.generate_content([image, prompt])
        response_text = response.text
        return _parse_llm_response(response_text, captions)
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response as JSON: {e}")
        return _fake_score_captions(captions)
    except Exception as e:
        print(f"Gemini scoring error: {e}")
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
    """Test if the LLM API is working."""
    if is_fake_mode():
        return True, "Fake LLM mode enabled (no API call made)"
    
    if not configure_api():
        providers = []
        if GROQ_AVAILABLE:
            providers.append("GROQ_API_KEY")
        if GENAI_AVAILABLE:
            providers.append("GOOGLE_API_KEY")
        
        if not providers:
            return False, "No LLM packages installed (try: pip install groq)"
        return False, f"No API key set. Set one of: {', '.join(providers)}"
    
    try:
        if _configured_provider == 'groq':
            # Simple test with Groq
            response = _groq_client.chat.completions.create(
                model=GROQ_TEXT_MODEL,
                messages=[{"role": "user", "content": "Say 'meow' if you can hear me."}],
                max_tokens=10
            )
            text = response.choices[0].message.content
            return True, f"Groq API working! Response: {text[:50]}..."
        
        elif _configured_provider == 'gemini':
            response = _gemini_model.generate_content("Say 'meow' if you can hear me.")
            if response and response.text:
                return True, f"Gemini API working! Response: {response.text[:50]}..."
            return False, "Gemini API returned empty response"
        
        return False, "No provider configured"
        
    except Exception as e:
        return False, f"API test failed: {e}"
