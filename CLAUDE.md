# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DramaFlow** is an AI-powered audio drama generation system that converts novel text into immersive audio dramas with synchronized subtitles. It uses Claude 3.5 Sonnet for script analysis, Edge TTS for narration, and ElevenLabs for character dialogue.

## Development Commands

### Setup and Installation
```bash
# Create virtual environment
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For development (optional)
pip install -r requirements-dev.txt
```

### Running the Server
```bash
# Using the startup script (recommended)
./run.sh

# Directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode (no auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run API tests
python test_api.py

# Test narrator voice consistency
python test_narrator_consistency.py

# Verify requirements compatibility
python verify_requirements.py
```

### Deployment
```bash
# Railway deployment (recommended for audio processing)
# See RAILWAY_DEPLOYMENT.md for detailed instructions

# Railway deployment (recommended for audio processing)
# See RAILWAY_DEPLOYMENT.md for detailed instructions
```

## Architecture Overview

### Core Pipeline
1. **Text Analysis** (`app/services/analyzer.py`)
   - Uses Claude 3.5 Sonnet via OpenRouter
   - Converts novel text to structured JSON script
   - Segments: `narration` (旁白) and `dialogue` (对话)
   - Attributes: character, gender, emotion, pacing

2. **Audio Generation** (`app/services/audio_engine.py`)
   - **Narration**: Edge TTS (free) with consistent voice per language
   - **Dialogue**: ElevenLabs (paid) with gender-based voice selection
   - Key concept: Narrator voice is determined once per script for consistency

3. **Post-Production** (`app/services/post_production.py`)
   - Merges audio segments with 300ms silence gaps
   - Applies pacing adjustments (0.8-1.2x speed)
   - Generates SRT subtitles with character labels
   - Uses pydub + ffmpeg for audio processing

### Key Design Patterns

#### Voice Consistency System
- **Language Detection**: Automatically detects Chinese vs English text
- **Fixed Narrator Voice**: All narration uses same voice throughout drama
- **Gender Ignored for Narration**: `segment.gender` is ignored for narration segments
- **Dialogue Voices**: Selected based on `segment.gender` (male/female)

#### API Key Management
- **Priority**: HTTP headers > Environment variables > .env file
- **Required Keys**: `OPENROUTER_API_KEY`, `ELEVENLABS_API_KEY`
- **Header Names**: `X-OpenRouter-API-Key`, `X-ElevenLabs-API-Key`

#### Concurrency Control
- **Semaphore**: Limits concurrent ElevenLabs API calls (max 3)
- **Parallel Generation**: Audio segments generated concurrently
- **Background Cleanup**: Temporary files cleaned after response

### File Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI application with CORS and error handling
│   ├── services/
│   │   ├── analyzer.py      # Claude API integration for script analysis
│   │   ├── audio_engine.py  # Edge TTS + ElevenLabs voice generation
│   │   └── post_production.py # Audio merging + SRT generation
│   └── __init__.py
├── api/vendor/              # ffmpeg binaries for serverless deployment
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── nixpacks.toml           # Build configuration for Railway
├── railway.toml            # Railway deployment config

└── Procfile                # Process definition
```

## Configuration

### Environment Variables
```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...
ELEVENLABS_API_KEY=sk_...

# Optional
PORT=8000                    # Server port
FFMPEG_BINARY=/path/to/ffmpeg # Override ffmpeg location
```

### Voice Configuration
- **Narration Voices**: Set in `audio_engine.py` lines 17-18
  - English: `en-US-BrianNeural` (male), `en-GB-SoniaNeural` (female)
  - Chinese: `zh-CN-YunxiNeural` (male), `zh-CN-XiaoxiaoNeural` (female)
- **Dialogue Voices**: Set in `audio_engine.py` lines 23-26
  - Male: `pNInz6obpgDQGcFmaJgB` (Adam)
  - Female: `21m00Tcm4TlvDq8ikWAM` (Rachel)

### Deployment Notes

#### Railway (Recommended)
- No execution time limits
- Automatic ffmpeg installation via nixpacks
- Persistent processes (no cold starts)
- See `RAILWAY_DEPLOYMENT.md` for full guide



## API Endpoints

### `POST /generate`
Main endpoint for audio drama generation:
- Returns ZIP file with `drama.mp3` and `drama.srt`
- Headers: `X-Segments-Count`, `X-Package-Contents`
- Timeout: 5 minutes recommended

### `POST /analyze`
Preview script without audio generation:
- Returns structured JSON script
- Useful for debugging and preview

### `GET /health`
Health check with API key validation.

## Important Constraints

1. **Text Length**: Max 10,000 characters per request
2. **Concurrency**: Max 3 concurrent ElevenLabs API calls
3. **Audio Duration**: No hard limit, but long texts may timeout
4. **Language Support**: Chinese and English (auto-detected)
5. **Voice Consistency**: Critical for user experience - never break this

## Common Development Tasks

### Adding New Voices
1. Update `DIALOGUE_VOICES` in `audio_engine.py`
2. Test with `python test_api.py`
3. Verify narrator consistency with `python test_narrator_consistency.py`

### Modifying Script Analysis
1. Edit system prompt in `analyzer.py` lines 27-94
2. Maintain JSON output format
3. Test with various text inputs

### Debugging Audio Issues
1. Check ffmpeg configuration in `main.py` lines 14-46
2. Verify API keys are valid
3. Check temporary file permissions
4. Review logs for `AudioSegment.converter` path

## Testing Strategy

- **Unit Tests**: Focus on voice consistency and language detection
- **Integration Tests**: Use `test_api.py` for end-to-end testing
- **Manual Testing**: Always test with both Chinese and English texts
- **Performance Testing**: Monitor ElevenLabs API rate limits

## Notes for Future Development

- **Never** modify the narrator voice consistency logic without thorough testing
- **Always** maintain backward compatibility with existing API endpoints
- **Consider** ElevenLabs API costs when testing audio generation

- **Use** Railway for production deployments with audio processing