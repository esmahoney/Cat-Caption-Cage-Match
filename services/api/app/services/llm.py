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

Your job is to rate each caption on TWO dimensions (each 0-10):
- HUMOUR (0-10): How funny is it? Does it make you laugh out loud?
- RELEVANCE (0-10): How well does it fit as a cat meme caption? Is it clever and on-theme?

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
            "humour": 7,
            "relevance": 6,
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
        humour = max(0, min(10, int(r.get("humour", 5))))
        relevance = max(0, min(10, int(r.get("relevance", 5))))
        cleaned.append({
            "player_name": r.get("player_name", "Unknown"),
            "caption": r.get("caption", ""),
            "humour": humour,
            "relevance": relevance,
            "total": humour + relevance,
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
        player_id = caption_data.get("player_id", "")  # Preserve for reliable matching
        
        # Deterministic scores based on caption hash
        h = hashlib.md5(caption.encode()).hexdigest()
        
        # Use different parts of hash for each dimension
        humour_base = int(h[:2], 16) % 11
        relevance_base = int(h[2:4], 16) % 11
        
        # Adjust humour for length (short captions less funny)
        words = len(caption.split())
        if words < 3:
            humour_base = max(0, humour_base - 2)
        elif words > 12:
            humour_base = max(0, humour_base - 1)
        
        humour = max(0, min(10, humour_base))
        relevance = max(0, min(10, relevance_base))
        total = humour + relevance
        
        # Pick roast based on total score
        if total >= 14:
            pool = roast_comments[-3:]
        elif total >= 8:
            pool = roast_comments[5:10]
        else:
            pool = roast_comments[:5]
        
        comment_idx = int(h[4:6], 16) % len(pool)
        
        results.append({
            "player_id": player_id,
            "player_name": player_name,
            "caption": caption,
            "humour": humour,
            "relevance": relevance,
            "total": total,
            "roast_comment": pool[comment_idx],
        })
    
    return results


def _normalize_caption(text: str) -> str:
    """Normalize caption text for fuzzy matching."""
    import re
    # Lowercase, strip whitespace, remove punctuation
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    return text


def _merge_player_ids(llm_results: list[dict], original_captions: list[dict]) -> list[dict]:
    """
    Merge player_id from original captions into LLM results.
    
    LLM only sees player_name, but we need player_id for reliable matching.
    
    Matching strategy (in order of preference):
    1. Positional: If LLM returns captions in same order, match by index
    2. Exact: Match by (player_name, caption) tuple
    3. Fuzzy: Match by player_name and normalized caption text
    4. Name-only: Match by player_name alone (risky if names duplicate)
    """
    if not llm_results or not original_captions:
        return llm_results
    
    # Build lookup dicts for fallback matching
    exact_lookup = {
        (c.get("player_name", ""), c.get("caption", "")): c.get("player_id", "")
        for c in original_captions
    }
    fuzzy_lookup = {
        (c.get("player_name", ""), _normalize_caption(c.get("caption", ""))): c.get("player_id", "")
        for c in original_captions
    }
    name_lookup = {
        c.get("player_name", ""): c.get("player_id", "")
        for c in original_captions
    }
    
    # Track which original captions have been matched (for positional matching)
    matched_indices = set()
    
    for i, result in enumerate(llm_results):
        player_name = result.get("player_name", "")
        caption = result.get("caption", "")
        player_id = ""
        
        # Strategy 1: Positional matching (if index is valid and order preserved)
        if i < len(original_captions):
            orig = original_captions[i]
            # Verify player_name matches to confirm order is preserved
            if orig.get("player_name", "") == player_name:
                player_id = orig.get("player_id", "")
                matched_indices.add(i)
        
        # Strategy 2: Exact match fallback
        if not player_id:
            exact_key = (player_name, caption)
            player_id = exact_lookup.get(exact_key, "")
        
        # Strategy 3: Fuzzy match fallback (normalized caption)
        if not player_id:
            fuzzy_key = (player_name, _normalize_caption(caption))
            player_id = fuzzy_lookup.get(fuzzy_key, "")
        
        # Strategy 4: Name-only fallback (last resort)
        if not player_id:
            player_id = name_lookup.get(player_name, "")
        
        result["player_id"] = player_id
    
    return llm_results


async def score_captions(
    image_url: str,
    captions: list[dict],
) -> list[dict]:
    """
    Score captions using LLM.
    
    Args:
        image_url: URL of the cat image
        captions: List of {"player_id": str, "player_name": str, "caption": str}
    
    Returns:
        List of {"player_id", "player_name", "caption", "humour", "relevance", "total", "roast_comment"}
        - player_id: Unique identifier for reliable matching
        - humour: 0-10 score for how funny the caption is
        - relevance: 0-10 score for how well it fits as a cat meme caption
        - total: sum of humour + relevance (0-20)
    """
    if not captions:
        return []
    
    settings = get_settings()
    
    # Use fake mode if configured or no API keys
    # Fake mode has access to player_id directly
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
                results = _parse_response(response.choices[0].message.content)
                # Merge player_id back into results
                return _merge_player_ids(results, captions)
        
        elif settings.llm_provider == "gemini":
            model = _get_gemini_model()
            if model:
                response = model.generate_content(prompt)
                results = _parse_response(response.text)
                # Merge player_id back into results
                return _merge_player_ids(results, captions)
    
    except Exception as e:
        print(f"LLM scoring error: {e}")
    
    # Fallback to fake scoring (has access to player_id)
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

