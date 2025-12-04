#!/bin/bash
# Development Environment Setup Script
# Detects Python version and installs appropriate dependencies

set -e

echo "🚀 DramaFlow 开发环境设置"
echo "================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "📍 检测到 Python 版本: $PYTHON_VERSION"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
else
    echo "✅ 虚拟环境已存在"
fi
echo ""

# Activate virtual environment
echo "🔌 激活虚拟环境..."
source venv/bin/activate
echo ""

# Install base requirements
echo "📥 安装基础依赖..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ 基础依赖安装完成"
echo ""

# Check if Python 3.13+ and install audioop-lts
if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 13 ]; then
    echo "⚠️  检测到 Python 3.13+，需要安装 audioop-lts"
    if [ -f "requirements-dev.txt" ]; then
        echo "📥 安装开发依赖..."
        pip install -r requirements-dev.txt
        echo "✅ audioop-lts 安装完成"
    else
        echo "📥 直接安装 audioop-lts..."
        pip install audioop-lts
        echo "✅ audioop-lts 安装完成"
    fi
else
    echo "ℹ️  Python $PYTHON_VERSION 有内置 audioop 模块，无需额外安装"
fi
echo ""

# Verify installation
echo "🧪 验证安装..."
python -c "from pydub import AudioSegment; print('✅ pydub 正常')" || {
    echo "❌ pydub 验证失败"
    exit 1
}

python -c "import audioop; print('✅ audioop 正常')" || {
    echo "❌ audioop 验证失败"
    exit 1
}
echo ""

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "📝 创建 .env 文件..."
    cp env.template .env
    echo "⚠️  请编辑 .env 文件，填入你的 API Keys"
else
    echo "✅ .env 文件已存在"
fi
echo ""

echo "================================"
echo "✅ 开发环境设置完成！"
echo ""
echo "📚 下一步:"
echo "  1. 编辑 .env 文件，填入 API Keys"
echo "  2. 运行服务器: ./run.sh"
echo "  3. 测试 API: python test_api.py"
echo ""
echo "🔗 相关文档:"
echo "  - QUICKSTART.md"
echo "  - VERCEL_DEPLOYMENT.md"
echo "  - VERCEL_UV_ISSUE.md"
echo ""

