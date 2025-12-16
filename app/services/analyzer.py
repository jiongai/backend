"""
Audio Drama Analyzer Service
Converts novel text into structured audio drama scripts using Claude 3.5 Sonnet via OpenRouter.
"""

import httpx
import dirtyjson
import asyncio
from typing import Dict, Any, List
import re
import json
import os
from .audio_engine import tts_manager
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None



SYSTEM_PROMPT = """You are an expert Audio Drama Director. Convert novel text into a structured JSON script. Output strictly a JSON object with a key script containing a list of segments.

Segment format:
{
    "type": "narration" | "dialogue",
    "text": "content without quotes (keep original language)",
    "character": "name or Narrator",
    "gender": "male" | "female",
    "emotion": "neutral" | "happy" | "sad" | "angry" | "fearful" | "surprised" | "whispering" | "shouting",
    "pacing": 1.0, (float, 0.8=slow, 1.2=fast),
    "voice_id": "pending" // Placeholder: AI sets this, backend will replace it with actual voice ID
}


Rules:
- Split long narration (>30 words) for better pacing.
- Infer speakers from context.
Rules:
- Split long narration (>30 words) for better pacing.
- Infer speakers from context.
- IMPORTANT: Maintain the original language of the input text. Do NOT translate.
- JSON FORMATTING: CRITICAL! The "text" field content often contains quotes. To avoid syntax errors, you MUST enclose the text value in TRIPLE ANGLE BRACKETS `<<< >>>` instead of quotes.
  Example: { "text": <<<He said "Hello" and she cried "Wow!">>> }
- CRITICAL: You must convert the ENTIRE text given. Do not summarize.
- Output a valid JSON object (with the exception of the angle brackets which will be post-processed)."""



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
            
            # Post-processing: Convert <<<...>>> to valid JSON strings (quoted)
            # Find <<< content >>> and replace with "escaped content"
            def replace_brackets(match):
                text_content = match.group(1)
                # Ensure the text is properly JSON escaped and quoted
                return json.dumps(text_content)
            
            # Regex to find <<< content >>> (tolerant of 2 or 3 closing brackets)
            fixed_content = re.sub(r'<<<(.*?)>{2,3}', replace_brackets, content, flags=re.DOTALL)
            
            parsed = dirtyjson.loads(fixed_content)
            
            if "script" not in parsed or not isinstance(parsed["script"], list):
                if attempt == max_retries:
                    print(f"❌ Chunk {chunk_index} failed validation")
                    return []
                continue
                
            return parsed["script"]
            
        except Exception as e:
            if attempt == max_retries:
                print(f"❌ Chunk {chunk_index} error: {e}")
                
                # Debug: Print the problematic content for inspection
                try:
                    print(f"--- FAILED CONTENT CHUNK {chunk_index} ---")
                    # If 'fixed_content' exists in local scope, print it, else raw content
                    if 'fixed_content' in locals():
                        print(fixed_content[:1000] + "..." if len(fixed_content) > 1000 else fixed_content)
                    elif 'content' in locals():
                         print(content[:1000] + "..." if len(content) > 1000 else content)
                    print("--- END FAILED CONTENT ---")
                except:
                    pass
                    
                return []
            await asyncio.sleep(1) # Backoff
            
    return []


async def analyze_text(text: str, api_key: str, user_tier: str = "free") -> Dict[str, Any]:
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
        # Enforce default voice_id="pending" if missing
        # "pending" is a temporary placeholder indicating the voice has not been assigned yet.
        # It will be replaced by a concrete ID (e.g. "cmn-TW-Wavenet-B") in assign_voices_to_script.
        for segment in chunk_script:
            if "voice_id" not in segment:
                segment["voice_id"] = "pending"
        full_script.extend(chunk_script)

        
    if not full_script:
        raise ValueError("Failed to generate any script segments")
        
    full_script = tts_manager.assign_voices_to_script(full_script, user_tier)
    return {"script": full_script}


async def _analyze_chunk_doubao(client: AsyncOpenAI, chunk_text: str, chunk_index: int) -> List[Dict[str, Any]]:
    """Analyze a single chunk using Doubao (via OpenAI SDK)."""
    
    chunk_prompt = f"Part {chunk_index + 1} of a story. {SYSTEM_PROMPT}"
    
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model="doubao-seed-1-6-lite-251015",
                messages=[
                    {
                        "role": "system",
                        "content": chunk_prompt
                    },
                    {
                        "role": "user",
                        "content": chunk_text
                    }
                ],
                reasoning_effort="medium"
            )
            
            content = response.choices[0].message.content
            
            # Post-processing: Convert <<<...>>> to valid JSON strings (quoted)
            def replace_brackets(match):
                text_content = match.group(1)
                return json.dumps(text_content)
            
            fixed_content = re.sub(r'<<<(.*?)>{2,3}', replace_brackets, content, flags=re.DOTALL)
            parsed = dirtyjson.loads(fixed_content)
            
            if "script" not in parsed or not isinstance(parsed["script"], list):
                if attempt == max_retries:
                    print(f"❌ [Doubao] Chunk {chunk_index} failed validation")
                    return []
                continue
                
            return parsed["script"]
            
        except Exception as e:
            if attempt == max_retries:
                print(f"❌ [Doubao] Chunk {chunk_index} error: {e}")
                return []
            await asyncio.sleep(1)

    return []


async def analyze_text_doubao(text: str, ark_api_key: str, user_tier: str = "free") -> Dict[str, Any]:
    """
    Analyze novel text using Doubao Lite model.
    """
    if not AsyncOpenAI:
        raise ImportError("openai package is required for Doubao analysis")

    client = AsyncOpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=ark_api_key
    )

    # 1. Chunking
    chunks = _chunk_text(text)
    
    # 2. Parallel Analysis
    tasks = [
        _analyze_chunk_doubao(client, chunk, i) 
        for i, chunk in enumerate(chunks)
    ]
    
    results = await asyncio.gather(*tasks)
        
    # 3. Merge Results
    full_script = []
    for chunk_script in results:
        # Enforce default voice_id="pending" if missing
        for segment in chunk_script:
            if "voice_id" not in segment:
                segment["voice_id"] = "pending"
        full_script.extend(chunk_script)
        
    if not full_script:
        raise ValueError("Failed to generate any script segments with Doubao")
        
    full_script = tts_manager.assign_voices_to_script(full_script, user_tier)
    return {"script": full_script}
