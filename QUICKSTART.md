# 🚀 Quick Start Guide

Get your DramaFlow backend running in 3 minutes!

## Prerequisites

- Python 3.8+
- OpenRouter API key ([Get one here](https://openrouter.ai/))
- ElevenLabs API key ([Get one here](https://elevenlabs.io/))

## Setup Steps

### 1️⃣ Install Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2️⃣ Configure API Keys

```bash
# Copy the template
cp env.template .env

# Edit .env and add your keys
nano .env  # or use your preferred editor
```

Your `.env` file should look like:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
ELEVENLABS_API_KEY=xxxxxxxxxxxxx
```

### 3️⃣ Start the Server

**Option A: Using the run script (recommended)**
```bash
./run.sh
```

**Option B: Using Python directly**
```bash
python app/main.py
```

**Option C: Using uvicorn**
```bash
uvicorn app.main:app --reload
```

The API will be available at: **http://localhost:8000**

## 🧪 Test Your Setup

### Quick Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "openrouter_configured": true,
  "elevenlabs_configured": true
}
```

### Run Full Test Suite
```bash
python test_api.py
```

### Try the Interactive API Docs

Open your browser and go to: **http://localhost:8000/docs**

This provides a beautiful Swagger UI where you can test all endpoints!

## 📝 Your First Audio Drama

### Example 1: Analyze Text (Fast, free preview)

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The old mansion stood on the hill. \"Who goes there?\" called Sarah nervously."
  }'
```

### Example 2: Generate Audio Drama (Takes 1-2 mins)

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The old mansion stood on the hill. \"Who goes there?\" called Sarah nervously. The wind whispered through the trees. \"I am here,\" replied a deep voice from the shadows."
  }' \
  -o my_first_drama.mp3
```

Then play the audio:
```bash
# macOS
open my_first_drama.mp3

# Linux
xdg-open my_first_drama.mp3

# Windows
start my_first_drama.mp3
```

## 🎯 API Endpoints Summary

| Endpoint | Method | Purpose | Speed |
|----------|--------|---------|-------|
| `/health` | GET | Check server status | Instant |
| `/analyze` | POST | Preview script structure | ~5 sec |
| `/generate` | POST | Generate full audio drama | ~1-2 min |

## 🎨 Project Structure

```
backend/
├── app/
│   ├── main.py                    # 🚀 FastAPI app
│   └── services/
│       ├── analyzer.py            # 🤖 AI script analysis
│       ├── audio_engine.py        # 🎙️ TTS generation
│       └── post_production.py     # 🎵 Audio merging
├── requirements.txt               # 📦 Dependencies
├── env.template                   # 🔑 Config template
├── run.sh                         # ▶️  Startup script
└── test_api.py                    # 🧪 Test suite
```

## 💡 Tips

1. **Start with `/analyze`** - It's fast and free. Use it to preview the script before generating audio.

2. **Save API credits** - Test with short texts (50-100 words) first.

3. **Monitor logs** - The terminal shows progress as it generates audio.

4. **Check the docs** - http://localhost:8000/docs has interactive API testing built-in!

## ❓ Troubleshooting

### Server won't start?
- Check virtual environment is activated: `which python` should show `venv/bin/python`
- Verify dependencies: `pip list | grep fastapi`

### API keys not working?
- Ensure no extra spaces in `.env` file
- Verify keys at OpenRouter and ElevenLabs dashboards
- Try passing keys via headers instead (see README.md)

### Audio generation fails?
- Check you have both API keys configured
- Verify ElevenLabs account has credits
- Try a shorter text sample first

## 🎓 Next Steps

1. Read the full [README.md](README.md) for advanced features
2. Customize voices in `app/services/audio_engine.py`
3. Adjust audio quality in `app/services/post_production.py`
4. Build a frontend to make it user-friendly!

## 🆘 Need Help?

- Check logs in the terminal where the server is running
- Test with `python test_api.py`
- Verify API keys are valid and have credits

---

**You're all set! 🎉 Start creating amazing audio dramas!**

