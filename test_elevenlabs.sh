#!/bin/bash

# ElevenLabs API 快速诊断脚本

echo "🔍 ElevenLabs API 诊断工具"
echo "============================="
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ .env 文件不存在"
    echo "   请先创建: cp env.template .env"
    exit 1
fi

# 读取 API 密钥
source .env
API_KEY=$ELEVENLABS_API_KEY

if [ -z "$API_KEY" ]; then
    echo "❌ .env 中未找到 ELEVENLABS_API_KEY"
    echo "   请在 .env 文件中添加你的密钥"
    exit 1
fi

echo "✅ API 密钥已加载"
echo "   长度: ${#API_KEY} 字符"
echo "   前缀: ${API_KEY:0:8}..."
echo ""

# 测试 1: 获取可用声音列表
echo "🧪 测试 1: 获取声音列表..."
response=$(curl -s -w "\n%{http_code}" -X GET "https://api.elevenlabs.io/v1/voices" \
  -H "xi-api-key: $API_KEY" 2>&1)

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "✅ 成功! API 密钥有效"
    voice_count=$(echo "$body" | grep -o '"voice_id"' | wc -l | tr -d ' ')
    echo "   可用声音数: $voice_count"
    echo ""
    
    # 显示一些声音信息
    echo "📋 部分可用声音:"
    echo "$body" | grep -o '"name":"[^"]*"' | head -5 | sed 's/"name":"/   - /g' | sed 's/"//g'
    echo ""
    
    # 测试 2: 尝试生成简短音频
    echo "🧪 测试 2: 生成测试音频..."
    test_response=$(curl -s -w "\n%{http_code}" -X POST \
      "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" \
      -H "xi-api-key: $API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"text":"Test","model_id":"eleven_monolingual_v1"}' \
      --output test_output.mp3 2>&1)
    
    test_code=$(echo "$test_response" | tail -n1)
    
    if [ "$test_code" = "200" ]; then
        echo "✅ 成功生成测试音频!"
        echo "   文件: test_output.mp3"
        
        if [ -f "test_output.mp3" ]; then
            file_size=$(ls -lh test_output.mp3 | awk '{print $5}')
            echo "   大小: $file_size"
            echo ""
            echo "🎵 播放测试音频..."
            open test_output.mp3 2>/dev/null || echo "   请手动播放: test_output.mp3"
        fi
        
        echo ""
        echo "============================="
        echo "🎉 所有测试通过!"
        echo "============================="
        echo ""
        echo "你的 ElevenLabs API 配置正确！"
        echo "现在可以启动 DramaFlow 了:"
        echo "  ./run.sh"
        exit 0
    else
        echo "⚠️  音频生成失败"
        echo "   HTTP 状态码: $test_code"
        test_body=$(echo "$test_response" | sed '$d')
        echo "   响应: $test_body"
    fi
    
elif [ "$http_code" = "401" ]; then
    echo "❌ 认证失败 (401 Unauthorized)"
    echo ""
    echo "可能的原因:"
    echo "  1. API 密钥无效或已过期"
    echo "  2. 密钥格式错误（检查是否有多余空格）"
    echo "  3. 密钥已被撤销"
    echo ""
    echo "解决方案:"
    echo "  1. 访问: https://elevenlabs.io/app/settings/api-keys"
    echo "  2. 创建新的 API 密钥"
    echo "  3. 更新 .env 文件中的密钥"
    echo "  4. 重新运行此脚本"
    
elif [ "$http_code" = "403" ]; then
    echo "❌ 权限不足 (403 Forbidden)"
    echo ""
    echo "错误详情:"
    echo "$body" | grep -o '"message":"[^"]*"' | sed 's/"message":"//g' | sed 's/"//g'
    echo ""
    echo "可能的原因:"
    echo "  1. 账户没有活跃订阅"
    echo "  2. 免费配额已用完"
    echo "  3. API 密钥权限不足"
    echo ""
    echo "解决方案:"
    echo "  1. 检查订阅状态: https://elevenlabs.io/app/settings/subscription"
    echo "  2. 查看配额使用情况"
    echo "  3. 考虑升级计划或等待配额重置"
    
else
    echo "❌ API 连接失败"
    echo "   HTTP 状态码: $http_code"
    echo ""
    echo "响应内容:"
    echo "$body"
    echo ""
    echo "可能的原因:"
    echo "  1. 网络连接问题"
    echo "  2. ElevenLabs 服务暂时不可用"
    echo "  3. 防火墙阻止了连接"
    echo ""
    echo "解决方案:"
    echo "  1. 检查网络连接"
    echo "  2. 稍后重试"
    echo "  3. 检查 https://status.elevenlabs.io/"
fi

echo ""
echo "============================="
echo "需要更多帮助？"
echo "============================="
echo "查看详细配置指南: cat ELEVENLABS_SETUP.md"
echo "联系支持: support@elevenlabs.io"
echo ""

exit 1

