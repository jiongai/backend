# DramaFlow Backend 🎭

Convert novel text into immersive audio dramas with AI-powered voice synthesis and intelligent script analysis.

## Features

- 🤖 **AI Script Analysis**: Uses Claude 3.5 Sonnet to convert novel text into structured audio drama scripts
- 🎙️ **Dual TTS System**: 
  - Edge TTS (free) for narration
  - ElevenLabs (paid) for character dialogue
- 🎵 **Audio Post-Production**: Automatic merging, pacing control, and silence gaps
- 📝 **SRT Subtitles**: Synchronized subtitle generation
- ⚡ **Parallel Processing**: Concurrent audio generation for faster results
- 🧹 **Automatic Cleanup**: Background task cleanup of temporary files

## Setup

### 1. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy the template
cp env.template .env

# Edit .env and add your API keys
nano .env
```

Add your API keys to `.env`:
```
OPENROUTER_API_KEY=your_openrouter_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
```

### 4. Run the Server

```bash
# Development mode with auto-reload
python app/main.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### 1. Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "openrouter_configured": true,
  "elevenlabs_configured": true
}
```

### 2. Analyze Text (Preview Script)

```bash
POST /analyze
Content-Type: application/json

{
  "text": "Your novel text here..."
}
```

**Response:**
```json
{
  "script": [
    {
      "type": "narration",
      "text": "The sun rose over the misty mountains.",
      "character": "Narrator",
      "gender": "male",
      "emotion": "neutral",
      "pacing": 1.0
    },
    {
      "type": "dialogue",
      "text": "Where are we going?",
      "character": "Sarah",
      "gender": "female",
      "emotion": "surprised",
      "pacing": 1.1
    }
  ],
  "metadata": {
    "segments_count": 2,
    "narration_count": 1,
    "dialogue_count": 1,
    "characters": ["Narrator", "Sarah"]
  }
}
```

### 3. Generate Audio Drama

```bash
POST /generate
Content-Type: application/json

{
  "text": "Your novel text here..."
}
```

**Response:** Downloads `drama.mp3` file

**Headers:**
- `X-Segments-Count`: Number of segments in the script
- `X-SRT-Available`: Whether subtitles were generated

## Example Usage

### Using cURL

```bash
# Analyze text only
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "The old mansion stood on the hill. \"Who goes there?\" called a voice from within."}'

# Generate full audio drama
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "The old mansion stood on the hill. \"Who goes there?\" called a voice from within."}' \
  -o drama.mp3
```

### Using Python

```python
import requests

# Analyze text
response = requests.post(
    "http://localhost:8000/analyze",
    json={"text": "Your novel text here..."}
)
script = response.json()
print(f"Generated {len(script['script'])} segments")

# Generate audio drama
response = requests.post(
    "http://localhost:8000/generate",
    json={"text": "Your novel text here..."}
)

with open("drama.mp3", "wb") as f:
    f.write(response.content)

print("Audio drama saved to drama.mp3")
```

## API Key Configuration

You can provide API keys in three ways:

1. **Environment Variables** (recommended):
   ```bash
   export OPENROUTER_API_KEY="your_key"
   export ELEVENLABS_API_KEY="your_key"
   ```

2. **`.env` File**:
   ```
   OPENROUTER_API_KEY=your_key
   ELEVENLABS_API_KEY=your_key
   ```

3. **HTTP Headers**:
   ```bash
   curl -X POST http://localhost:8000/generate \
     -H "X-OpenRouter-API-Key: your_key" \
     -H "X-ElevenLabs-API-Key: your_key" \
     -H "Content-Type: application/json" \
     -d '{"text": "..."}'
   ```

## Voice Configuration

### Narration (Edge TTS - Free)
- **Male**: `en-US-BrianNeural` (professional, human-like)
- **Female**: `en-GB-SoniaNeural` (professional UK accent)

### Dialogue (ElevenLabs - Paid)
- **Male**: `Adam`
- **Female**: `Rachel`

To customize voices, edit `app/services/audio_engine.py`:
```python
NARRATION_VOICES = {
    "male": "en-US-BrianNeural",
    "female": "en-GB-SoniaNeural"
}

DIALOGUE_VOICES = {
    "male": "Adam",
    "female": "Rachel"
}
```

## Architecture

```
DramaFlow Backend
├── app/
│   ├── main.py              # FastAPI application
│   ├── services/
│   │   ├── analyzer.py      # Text → Script conversion (Claude)
│   │   ├── audio_engine.py  # Audio generation (Edge TTS + ElevenLabs)
│   │   └── post_production.py  # Audio merging + SRT generation
│   └── __init__.py
├── requirements.txt
├── env.template
└── README.md
```

## Development

### Project Structure

- **analyzer.py**: Converts novel text to structured JSON script using Claude 3.5 Sonnet
- **audio_engine.py**: Generates audio for each segment using appropriate TTS service
- **post_production.py**: Merges audio segments, applies pacing, generates SRT subtitles
- **main.py**: FastAPI application orchestrating the entire pipeline

### Adding New Features

1. **Custom Voices**: Edit voice mappings in `audio_engine.py`
2. **Background Music**: Use `add_background_music()` in `post_production.py`
3. **New Emotions**: Extend the emotion mapping in the system prompt
4. **Output Formats**: Add new export formats in `post_production.py`

## Troubleshooting

### Common Issues

1. **"OpenRouter API key is required"**
   - Ensure `.env` file exists with valid `OPENROUTER_API_KEY`
   - Or pass the key via `X-OpenRouter-API-Key` header

2. **"ElevenLabs API key is required"**
   - Ensure `.env` file exists with valid `ELEVENLABS_API_KEY`
   - Or pass the key via `X-ElevenLabs-API-Key` header

3. **Audio quality issues**
   - Adjust bitrate in `post_production.py` (default: 192kbps)
   - Try different voice models in `audio_engine.py`

4. **Slow generation**
   - Audio is generated in parallel for speed
   - Consider reducing text length or splitting into batches

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

