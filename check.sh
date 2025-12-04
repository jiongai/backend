#!/bin/bash

# DramaFlow 配置检查脚本

echo "🔍 DramaFlow 配置检查"
echo "===================="
echo ""

# 颜色代码
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查计数
passed=0
failed=0

# 1. 检查当前目录
echo "1️⃣  检查当前目录..."
if [[ $(pwd) == */AudioDrama/backend ]]; then
    echo -e "   ${GREEN}✅ 在正确的目录${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ 不在项目根目录${NC}"
    echo "      请运行: cd /Users/baojiong/Documents/AI/AudioDrama/backend"
    ((failed++))
fi
echo ""

# 2. 检查虚拟环境
echo "2️⃣  检查虚拟环境..."
if [ -d "venv" ]; then
    echo -e "   ${GREEN}✅ venv/ 目录存在${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ venv/ 不存在${NC}"
    echo "      请运行: python3 -m venv venv"
    ((failed++))
fi
echo ""

# 3. 检查 .env 文件
echo "3️⃣  检查 .env 文件..."
if [ -f ".env" ]; then
    echo -e "   ${GREEN}✅ .env 文件存在${NC}"
    
    # 检查 API 密钥
    if grep -q "OPENROUTER_API_KEY=sk-or-v1-" .env 2>/dev/null; then
        echo -e "   ${GREEN}✅ OpenRouter API 密钥已配置${NC}"
        ((passed++))
    elif grep -q "OPENROUTER_API_KEY=$" .env 2>/dev/null || grep -q "OPENROUTER_API_KEY=$" .env 2>/dev/null; then
        echo -e "   ${YELLOW}⚠️  OpenRouter API 密钥为空${NC}"
        echo "      请在 .env 文件中添加密钥"
        ((failed++))
    else
        echo -e "   ${YELLOW}⚠️  OpenRouter API 密钥可能无效${NC}"
        echo "      密钥应该以 sk-or-v1- 开头"
    fi
    
    if grep -q "ELEVENLABS_API_KEY=..*" .env 2>/dev/null; then
        echo -e "   ${GREEN}✅ ElevenLabs API 密钥已配置${NC}"
        ((passed++))
    else
        echo -e "   ${YELLOW}⚠️  ElevenLabs API 密钥未配置${NC}"
        ((failed++))
    fi
else
    echo -e "   ${RED}❌ .env 文件不存在${NC}"
    echo "      请运行: cp env.template .env"
    echo "      然后编辑 .env 添加 API 密钥"
    ((failed++))
fi
echo ""

# 4. 检查 Python 依赖
echo "4️⃣  检查 Python 依赖..."
if ./venv/bin/python -c "import fastapi" 2>/dev/null; then
    echo -e "   ${GREEN}✅ fastapi 已安装${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ fastapi 未安装${NC}"
    echo "      请运行: source venv/bin/activate && pip install -r requirements.txt"
    ((failed++))
fi

if ./venv/bin/python -c "import uvicorn" 2>/dev/null; then
    echo -e "   ${GREEN}✅ uvicorn 已安装${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ uvicorn 未安装${NC}"
    ((failed++))
fi

if ./venv/bin/python -c "import pydub" 2>/dev/null; then
    echo -e "   ${GREEN}✅ pydub 已安装${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ pydub 未安装${NC}"
    ((failed++))
fi

if ./venv/bin/python -c "import edge_tts" 2>/dev/null; then
    echo -e "   ${GREEN}✅ edge-tts 已安装${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ edge-tts 未安装${NC}"
    ((failed++))
fi
echo ""

# 5. 检查代码文件
echo "5️⃣  检查代码文件..."
if [ -f "app/main.py" ]; then
    echo -e "   ${GREEN}✅ app/main.py 存在${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ app/main.py 不存在${NC}"
    ((failed++))
fi

if [ -f "app/services/analyzer.py" ]; then
    echo -e "   ${GREEN}✅ analyzer.py 存在${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ analyzer.py 不存在${NC}"
    ((failed++))
fi
echo ""

# 6. 测试模块导入
echo "6️⃣  测试模块导入..."
if ./venv/bin/python -c "from app.main import app" 2>/dev/null; then
    echo -e "   ${GREEN}✅ 可以导入 FastAPI 应用${NC}"
    ((passed++))
else
    echo -e "   ${RED}❌ 无法导入 FastAPI 应用${NC}"
    echo "      可能存在代码语法错误"
    ((failed++))
fi
echo ""

# 总结
echo "===================="
echo "📊 检查结果"
echo "===================="
echo -e "通过: ${GREEN}${passed}${NC}"
echo -e "失败: ${RED}${failed}${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 所有检查通过！项目可以启动！${NC}"
    echo ""
    echo "启动命令:"
    echo "  ./run.sh"
    echo ""
    echo "或者:"
    echo "  source venv/bin/activate"
    echo "  uvicorn app.main:app --reload"
    exit 0
else
    echo -e "${RED}⚠️  发现 ${failed} 个问题，请修复后再启动${NC}"
    echo ""
    echo "查看详细故障排除指南:"
    echo "  cat TROUBLESHOOTING.md"
    exit 1
fi

