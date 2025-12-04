"""
Simple test script for the DramaFlow API
"""

import requests
import json
import os
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000"

# Sample text for testing
SAMPLE_TEXT = """
The old mansion stood alone on the hill, its windows dark and empty. 
Sarah approached the creaking gate. "Hello?" she called out nervously. 
"Is anyone there?" The wind whispered through the trees, carrying an eerie silence. 
A door slammed somewhere inside. "I'm here," came a deep voice from the shadows. 
Sarah's heart raced as she took a step back.
"""


def test_health_check():
    """Test the health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Health check passed")
        print(f"   OpenRouter configured: {data['openrouter_configured']}")
        print(f"   ElevenLabs configured: {data['elevenlabs_configured']}")
        return True
    else:
        print(f"❌ Health check failed: {response.status_code}")
        return False


def test_analyze():
    """Test the analyze endpoint."""
    print("\nTesting text analysis...")
    
    response = requests.post(
        f"{BASE_URL}/analyze",
        json={"text": SAMPLE_TEXT}
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Analysis successful")
        
        if "script" in data:
            print(f"   Segments generated: {len(data['script'])}")
            
            if "metadata" in data:
                meta = data["metadata"]
                print(f"   Narration segments: {meta.get('narration_count', 0)}")
                print(f"   Dialogue segments: {meta.get('dialogue_count', 0)}")
                print(f"   Characters: {', '.join(meta.get('characters', []))}")
            
            # Print first few segments
            print("\n   Sample segments:")
            for i, segment in enumerate(data['script'][:3], 1):
                print(f"   {i}. [{segment['type']}] {segment['character']}: {segment['text'][:50]}...")
        
        return data
    else:
        print(f"❌ Analysis failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return None


def test_generate():
    """Test the audio generation endpoint."""
    print("\nTesting audio generation...")
    print("⏳ This may take 1-2 minutes...")
    
    response = requests.post(
        f"{BASE_URL}/generate",
        json={"text": SAMPLE_TEXT},
        timeout=300  # 5 minute timeout
    )
    
    if response.status_code == 200:
        # Save the audio file
        output_file = "test_drama.mp3"
        with open(output_file, "wb") as f:
            f.write(response.content)
        
        print("✅ Audio generation successful")
        print(f"   Saved to: {output_file}")
        print(f"   File size: {len(response.content) / 1024:.2f} KB")
        
        # Check headers
        if "X-Segments-Count" in response.headers:
            print(f"   Segments: {response.headers['X-Segments-Count']}")
        
        return True
    else:
        print(f"❌ Generation failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("DramaFlow API Test Suite")
    print("=" * 60)
    
    # Test 1: Health check
    if not test_health_check():
        print("\n⚠️  Server is not healthy. Please check:")
        print("   1. Server is running (python app/main.py)")
        print("   2. API keys are configured in .env file")
        return
    
    # Test 2: Analyze text
    analysis_result = test_analyze()
    if not analysis_result:
        print("\n⚠️  Analysis failed. Check OpenRouter API key.")
        return
    
    # Test 3: Generate audio (optional, as it takes time and costs money)
    print("\n" + "=" * 60)
    user_input = input("Do you want to test audio generation? This will use API credits. (y/N): ")
    
    if user_input.lower() in ['y', 'yes']:
        test_generate()
    else:
        print("Skipping audio generation test.")
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

