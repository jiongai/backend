"""
Audio Drama Analyzer Service
Converts novel text into structured audio drama scripts using Claude 3.5 Sonnet via OpenRouter.
"""

import httpx
import dirtyjson
from typing import Dict, Any, List


SYSTEM_PROMPT = """You are an expert Audio Drama Director. Convert novel text into a structured JSON script. Output strictly a JSON object with a key script containing a list of segments.

Segment format:
{
    "type": "narration" | "dialogue",
    "text": "content without quotes (keep original language)",
    "character": "name or Narrator",
    "gender": "male" | "female",
    "emotion": "neutral" | "happy" | "sad" | "angry" | "fearful" | "surprised" | "whispering" | "shouting",
    "pacing": 1.0 (float, 0.8=slow, 1.2=fast)
}

Rules:
- Split long narration (>30 words) for better pacing.
- Infer speakers from context.
Rules:
- Split long narration (>30 words) for better pacing.
- Infer speakers from context.
- IMPORTANT: Maintain the original language of the input text. Do NOT translate.
- JSON FORMATTING: In the "text" field, replace any internal double quotes with single quotes. Do not use unescaped double quotes inside strings.
- CRITICAL: You must convert the ENTIRE text given. Do not summarize.
- Output strictly valid JSON."""


async def analyze_text(text: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze novel text and convert it to audio drama script format.
    
    Args:
        text: The novel text to convert
        api_key: OpenRouter API key
        
    Returns:
        Dict containing the script with segments
        
    Raises:
        httpx.HTTPError: If the API request fails
        ValueError: If JSON parsing fails after retries
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "max_tokens": 8192,  # Ensure enough tokens for long scripts
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": text
            }
        ]
    }
    
    max_retries = 2
    last_error = None
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(max_retries + 1):
            try:
                # Make API request
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                # Extract the response content
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]
                
                # Parse the JSON using dirtyjson for robust parsing
                parsed_result = dirtyjson.loads(content)
                
                # Validate the result has the expected structure
                if "script" not in parsed_result:
                    raise ValueError("Response does not contain 'script' key")
                
                if not isinstance(parsed_result["script"], list):
                    raise ValueError("'script' must be a list")
                
                return parsed_result
                
            except (dirtyjson.Error, ValueError, KeyError) as e:
                last_error = e
                if attempt < max_retries:
                    # Retry on parsing errors
                    continue
                else:
                    # Final attempt failed
                    raise ValueError(
                        f"Failed to parse response after {max_retries + 1} attempts: {str(e)}"
                    ) from e
            
            except httpx.HTTPError as e:
                # Don't retry on HTTP errors, raise immediately
                raise
    
    # This should not be reached, but just in case
    raise ValueError(f"Failed to analyze text: {last_error}")

