"""
Audio Drama Analyzer Service
Converts novel text into structured audio drama scripts using Claude 3.5 Sonnet via OpenRouter.
"""

import httpx
import dirtyjson
import asyncio
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



def _chunk_text(text: str, max_chunk_size: int = 1200) -> List[str]:
    """
    Split text into chunks aiming for max_chunk_size, preserving paragraph boundaries.
    """
    if len(text) <= max_chunk_size:
        return [text]
        
    chunks = []
    current_chunk = []
    current_size = 0
    
    # Split by actual paragraphs first
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        # If adding this paragraph exceeds limit (and we have content)
        if current_size + len(paragraph) > max_chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [paragraph]
            current_size = len(paragraph)
        else:
            current_chunk.append(paragraph)
            current_size += len(paragraph) + 1 # +1 for newline
            
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
        
    return chunks


async def _analyze_chunk(client: httpx.AsyncClient, chunk_text: str, api_key: str, chunk_index: int) -> List[Dict[str, Any]]:
    """Analyze a single chunk of text."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Context prompt for chunks
    chunk_prompt = f"Part {chunk_index + 1} of a story. {SYSTEM_PROMPT}"
    
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "max_tokens": 8192,
        "messages": [
            {
                "role": "system",
                "content": chunk_prompt
            },
            {
                "role": "user",
                "content": chunk_text
            }
        ]
    }
    
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=120.0)
            response.raise_for_status()
            
            content = response.json()["choices"][0]["message"]["content"]
            parsed = dirtyjson.loads(content)
            
            if "script" not in parsed or not isinstance(parsed["script"], list):
                if attempt == max_retries:
                    print(f"❌ Chunk {chunk_index} failed validation")
                    return []
                continue
                
            return parsed["script"]
            
        except Exception as e:
            if attempt == max_retries:
                print(f"❌ Chunk {chunk_index} error: {e}")
                return []
            await asyncio.sleep(1) # Backoff
            
    return []


async def analyze_text(text: str, api_key: str) -> Dict[str, Any]:
    """
    Analyze novel text converting it to audio drama script format.
    Handles long text by chunking.
    """
    # 1. Chunking
    chunks = _chunk_text(text)
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        # 2. Parallel Analysis
        tasks = [
            _analyze_chunk(client, chunk, api_key, i) 
            for i, chunk in enumerate(chunks)
        ]
        
        results = await asyncio.gather(*tasks)
        
    # 3. Merge Results
    full_script = []
    for chunk_script in results:
        full_script.extend(chunk_script)
        
    if not full_script:
        raise ValueError("Failed to generate any script segments")
        
    return {"script": full_script}

