# 🎙️ ElevenLabs API 配置指南

## 📋 问题诊断

当前错误：
```
The API key you used is missing the permission text_to_speech to execute this operation.
```

这意味着：
- ❌ API 密钥缺少 `text_to_speech` 权限
- ❌ 或者账户没有有效订阅
- ❌ 或者密钥已过期/被撤销

---

## 🔧 解决步骤

### 步骤 1: 登录 ElevenLabs

访问：https://elevenlabs.io/

使用你的账户登录

---

### 步骤 2: 检查订阅状态

1. 进入 **Settings** (设置)
2. 查看 **Subscription** (订阅) 标签
3. 确认：
   - ✅ 有活跃的订阅（Starter, Creator, Pro, 或 Enterprise）
   - ✅ 或者有免费配额（每月 10,000 字符）

**重要**: 即使是免费账户也应该有基本的 text-to-speech 权限！

---

### 步骤 3: 获取/创建 API 密钥

#### 访问 API 密钥页面
https://elevenlabs.io/app/settings/api-keys

或者：
1. 点击右上角的头像
2. 选择 **Settings**
3. 点击 **API Keys** 标签

#### 创建新的 API 密钥

1. 点击 **"+ Create"** 或 **"Create API Key"**
2. 给密钥命名（例如：DramaFlow）
3. 点击创建
4. **立即复制密钥** - 它只会显示一次！

**密钥格式**: 通常是一串类似 `sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx` 的字符

---

### 步骤 4: 验证 API 密钥

在创建/复制密钥后，用这个命令测试：

```bash
# 替换 YOUR_API_KEY 为你的实际密钥
curl -X GET https://api.elevenlabs.io/v1/voices \
  -H "xi-api-key: YOUR_API_KEY"
```

**成功响应**: 应该返回可用声音列表（JSON 格式）

**失败响应**: 如果返回 401 或权限错误，说明密钥无效

---

### 步骤 5: 更新 .env 文件

```bash
# 编辑 .env 文件
nano .env
```

更新为新的密钥：
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
ELEVENLABS_API_KEY=你的新ElevenLabs密钥
```

保存文件（nano: Ctrl+O, Enter, Ctrl+X）

---

### 步骤 6: 重启服务器

```bash
# 在运行服务器的终端按 Ctrl+C 停止

# 重新启动
./run.sh
```

---

## 🧪 测试 API

### 方式 1: 使用 curl 直接测试 ElevenLabs

```bash
# 替换为你的密钥
API_KEY="你的ElevenLabs密钥"

# 测试生成语音
curl -X POST https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM \
  -H "xi-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test.",
    "model_id": "eleven_monolingual_v1"
  }' \
  --output test_elevenlabs.mp3

# 播放测试音频
open test_elevenlabs.mp3
```

### 方式 2: 使用项目的测试脚本

```bash
# 确保服务器正在运行
python test_api.py
```

---

## 🎭 可用的声音 ID

ElevenLabs 预设声音：

| 名称 | Voice ID | 性别 | 风格 |
|------|----------|------|------|
| **Adam** | `pNInz6obpgDQGcFmaJgB` | 男 | 深沉、成熟 |
| **Rachel** | `21m00Tcm4TlvDq8ikWAM` | 女 | 温暖、友好 |
| Antoni | `ErXwobaYiN019PkySvjV` | 男 | 年轻、活力 |
| Bella | `EXAVITQu4vr4xnSDxMaL` | 女 | 柔和、叙事 |
| Elli | `MF3mGyEYCl7XYWbV9V6O` | 女 | 年轻、活泼 |
| Josh | `TxGEqnHWrfWFTfGW9XjX` | 男 | 专业、清晰 |

当前项目配置：
- 男性对话: **Adam** (`pNInz6obpgDQGcFmaJgB`)
- 女性对话: **Rachel** (`21m00Tcm4TlvDq8ikWAM`)

---

## 🔍 常见问题排查

### 问题 1: "Missing permissions" 错误

**可能原因**:
- 使用了旧的/已撤销的密钥
- 账户订阅已过期
- 密钥创建时出错

**解决方案**:
1. 删除旧密钥（在 ElevenLabs 网站上）
2. 创建全新的密钥
3. 确认订阅状态有效

---

### 问题 2: "Invalid API key" 错误

**检查**:
- ✅ 密钥格式正确（没有多余空格）
- ✅ `.env` 文件中密钥前后没有引号
- ✅ 密钥完整（没有被截断）

正确格式：
```
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

错误格式：
```
ELEVENLABS_API_KEY="sk_xxxx"    # ❌ 不要引号
ELEVENLABS_API_KEY= sk_xxxx     # ❌ 不要空格
```

---

### 问题 3: "Quota exceeded" 错误

**解决方案**:
1. 检查账户配额：https://elevenlabs.io/app/settings/subscription
2. 等待配额重置（每月1号）
3. 或升级订阅计划

---

### 问题 4: 网络连接问题

**测试连接**:
```bash
curl https://api.elevenlabs.io/v1/voices
```

如果无法连接：
- 检查网络连接
- 检查防火墙设置
- 尝试使用 VPN（如果在受限地区）

---

## 💡 订阅计划建议

| 计划 | 价格 | 字符数/月 | 适合 |
|------|------|-----------|------|
| **Free** | $0 | 10,000 | 测试、小项目 |
| **Starter** | $5 | 30,000 | 个人使用 |
| **Creator** | $22 | 100,000 | 创作者 |
| **Pro** | $99 | 500,000 | 专业用途 |

对于 DramaFlow：
- **测试阶段**: Free 计划足够（约 10-20 个短音频剧）
- **生产使用**: 建议 Starter 或以上

---

## ✅ 验证清单

完成配置后，确认：

- [ ] ElevenLabs 账户有活跃订阅或免费配额
- [ ] 创建了新的 API 密钥
- [ ] API 密钥已复制并保存
- [ ] 使用 curl 测试密钥有效
- [ ] `.env` 文件已更新
- [ ] 服务器已重启
- [ ] 可以成功生成音频

---

## 🆘 仍然无法工作？

### 快速诊断脚本

创建并运行此脚本：

```bash
#!/bin/bash
# 保存为 test_elevenlabs.sh

echo "🔍 ElevenLabs API 诊断"
echo "====================="
echo ""

# 读取 API 密钥
source .env
API_KEY=$ELEVENLABS_API_KEY

if [ -z "$API_KEY" ]; then
    echo "❌ .env 中未找到 ELEVENLABS_API_KEY"
    exit 1
fi

echo "✅ API 密钥已加载 (长度: ${#API_KEY} 字符)"
echo ""

# 测试 API
echo "🧪 测试 API 连接..."
response=$(curl -s -w "\n%{http_code}" -X GET https://api.elevenlabs.io/v1/voices \
  -H "xi-api-key: $API_KEY")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" -eq 200 ]; then
    echo "✅ API 连接成功！"
    echo "可用声音数: $(echo "$body" | grep -o '"voice_id"' | wc -l)"
else
    echo "❌ API 连接失败"
    echo "HTTP 状态码: $http_code"
    echo "响应: $body"
fi
```

```bash
chmod +x test_elevenlabs.sh
./test_elevenlabs.sh
```

---

## 📞 获取帮助

如果问题持续：

1. **ElevenLabs 支持**: support@elevenlabs.io
2. **查看文档**: https://docs.elevenlabs.io/
3. **社区论坛**: https://discord.gg/elevenlabs

---

*配置完成后，你的 DramaFlow 将使用高质量的 ElevenLabs 语音！*

