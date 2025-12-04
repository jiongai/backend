#!/bin/bash
# Setup ffmpeg for Vercel deployment

set -e

echo "🎬 Setting up ffmpeg for Vercel..."
echo ""

# Create vendor directory
echo "📁 Creating vendor directory..."
mkdir -p vendor

# Download ffmpeg (Linux x86_64 for Vercel)
echo "📥 Downloading ffmpeg (Linux x86_64)..."
curl -L https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/ffmpeg-linux-x64 -o vendor/ffmpeg

# Set executable permission
chmod +x vendor/ffmpeg

# Verify download
if [ -f "vendor/ffmpeg" ]; then
    echo "✅ ffmpeg downloaded successfully"
    echo "   Size: $(du -h vendor/ffmpeg | cut -f1)"
    echo "   Path: $(pwd)/vendor/ffmpeg"
else
    echo "❌ Failed to download ffmpeg"
    exit 1
fi

# Add ffmpeg-python to requirements.txt if not already there
echo ""
echo "📝 Updating requirements.txt..."
if ! grep -q "ffmpeg-python" requirements.txt; then
    echo "ffmpeg-python" >> requirements.txt
    echo "✅ Added ffmpeg-python to requirements.txt"
else
    echo "ℹ️  ffmpeg-python already in requirements.txt"
fi

# Test ffmpeg (optional, might not work on macOS)
echo ""
echo "🧪 Testing ffmpeg..."
if ./vendor/ffmpeg -version > /dev/null 2>&1; then
    echo "✅ ffmpeg is executable"
else
    echo "⚠️  Cannot test ffmpeg on this system (may work on Linux/Vercel)"
fi

echo ""
echo "================================"
echo "✅ Setup complete!"
echo "================================"
echo ""
echo "📋 Next steps:"
echo ""
echo "  1. ✅ ffmpeg binary is ready in vendor/"
echo "  2. ✅ requirements.txt updated"
echo ""
echo "  3. 🔧 Update app/main.py (see VERCEL_FFMPEG.md)"
echo "     Add ffmpeg configuration at the top"
echo ""
echo "  4. 📤 Commit and push:"
echo "     git add vendor/ requirements.txt app/main.py"
echo "     git commit -m \"feat: Add ffmpeg support for Vercel\""
echo "     git push origin main"
echo ""
echo "📖 See VERCEL_FFMPEG.md for detailed instructions"
echo ""

