"""
LLM scoring service for caption judging.

Supports Groq (preferred) and Gemini as providers, with a fake mode for testing.
"""
import json
import hashlib
import os
from typing import Optional

from ..config import get_settings

# Try to import LLM clients
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


# Model configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-1.5-flash"

# Cached clients
_groq_client = None
_gemini_model = None


def _get_groq_client():
    """Get or create Groq client."""
    global _groq_client
    if _groq_client is None and GROQ_AVAILABLE:
        settings = get_settings()
        if settings.groq_api_key:
            _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


def _get_gemini_model():
    """Get or create Gemini model."""
    global _gemini_model
    if _gemini_model is None and GENAI_AVAILABLE:
        settings = get_settings()
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    return _gemini_model


def _build_prompt(captions: list[dict]) -> str:
    """Build the scoring prompt."""
    caption_list = "\n".join([
        f'{i+1}. Player: "{c["player_name"]}" - Caption: "{c["caption"]}"'
        for i, c in enumerate(captions)
    ])
    
    return f"""You are "Cat Meme Gordon Ramsay" - a brutally honest but hilarious judge of cat meme captions.

Your job is to rate each caption on a scale of 0-10 based on:
- HUMOR (0-10): How funny is it? Does it make you laugh?
- CREATIVITY (0-10): How clever or original is it as a cat meme caption?

The final score is the average of humor and creativity, rounded to the nearest integer.

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


def _parse_response(response_text: str) -> list[dict]:
    """Parse LLM response JSON."""
    # Clean up common issues
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    data = json.loads(text)
    results = data.get("results", [])
    
    # Validate and clean
    cleaned = []
    for r in results:
        cleaned.append({
            "player_name": r.get("player_name", "Unknown"),
            "caption": r.get("caption", ""),
            "score": max(0, min(10, int(r.get("score", 5)))),
            "roast_comment": r.get("roast_comment", "No comment."),
        })
    
    return cleaned


def _fake_score(captions: list[dict]) -> list[dict]:
    """Generate deterministic fake scores for testing."""
    roast_comments = [
        "This is what happens when you let interns write memes.",
        "I've seen better captions on a milk carton.",
        "Did you write this with your eyes closed?",
        "My grandmother's cat could do better.",
        "This is so bad it's almost impressive. Almost.",
        "Were you trying to be funny, or was that an accident?",
        "I've had more laughs at a funeral.",
        "This caption is the human equivalent of a participation trophy.",
        "Somewhere, a comedy writer just felt a disturbance.",
        "If mediocrity was a caption, this would be it.",
        "Actually not terrible. I'm as surprised as you are.",
        "Finally, someone who understands cats!",
        "This made me snort. Well done, you legend.",
    ]
    
    results = []
    for caption_data in captions:
        caption = caption_data.get("caption", "")
        player_name = caption_data.get("player_name", "Unknown")
        
        # Deterministic score based on caption hash
        h = hashlib.md5(caption.encode()).hexdigest()
        base_score = int(h[:2], 16) % 11
        
        # Adjust for length
        words = len(caption.split())
        if words < 3:
            base_score = max(0, base_score - 2)
        elif words > 12:
            base_score = max(0, base_score - 1)
        
        final_score = max(0, min(10, base_score))
        
        # Pick roast based on score
        if final_score >= 8:
            pool = roast_comments[-3:]
        elif final_score >= 5:
            pool = roast_comments[5:10]
        else:
            pool = roast_comments[:5]
        
        comment_idx = int(h[2:4], 16) % len(pool)
        
        results.append({
            "player_name": player_name,
            "caption": caption,
            "score": final_score,
            "roast_comment": pool[comment_idx],
        })
    
    return results


async def score_captions(
    image_url: str,
    captions: list[dict],
) -> list[dict]:
    """
    Score captions using LLM.
    
    Args:
        image_url: URL of the cat image
        captions: List of {"player_name": str, "caption": str}
    
    Returns:
        List of {"player_name", "caption", "score", "roast_comment"}
    """
    if not captions:
        return []
    
    settings = get_settings()
    
    # Use fake mode if configured or no API keys
    if settings.llm_provider == "fake":
        return _fake_score(captions)
    
    prompt = _build_prompt(captions)
    
    try:
        if settings.llm_provider == "groq":
            client = _get_groq_client()
            if client:
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    temperature=0.7,
                )
                return _parse_response(response.choices[0].message.content)
        
        elif settings.llm_provider == "gemini":
            model = _get_gemini_model()
            if model:
                response = model.generate_content(prompt)
                return _parse_response(response.text)
    
    except Exception as e:
        print(f"LLM scoring error: {e}")
    
    # Fallback to fake scoring
    return _fake_score(captions)


async def test_llm_connection() -> tuple[bool, str]:
    """Test if LLM is working."""
    settings = get_settings()
    
    if settings.llm_provider == "fake":
        return True, "Fake LLM mode enabled"
    
    try:
        if settings.llm_provider == "groq":
            client = _get_groq_client()
            if not client:
                return False, "Groq API key not configured"
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": "Say meow"}],
                max_tokens=10,
            )
            return True, f"Groq working: {response.choices[0].message.content[:30]}"
        
        elif settings.llm_provider == "gemini":
            model = _get_gemini_model()
            if not model:
                return False, "Gemini API key not configured"
            response = model.generate_content("Say meow")
            return True, f"Gemini working: {response.text[:30]}"
    
    except Exception as e:
        return False, f"LLM error: {e}"
    
    return False, "No LLM provider configured"

