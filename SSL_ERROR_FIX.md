# 🔧 SSL 错误修复指南

## ❌ 错误信息

```
Error generating audio drama: [SSL: UNEXPECTED_EOF_WHILE_READING] 
EOF occurred in violation of protocol (_ssl.c:1032)
```

---

## ✅ 已修复！

### 修复内容

**自动重试机制**已添加到 ElevenLabs API 调用中：
- ✅ 最多重试 3 次
- ✅ 指数退避策略（2秒、4秒、6秒）
- ✅ 只对网络/SSL 错误重试
- ✅ 详细的错误日志

### 代码位置
`app/services/audio_engine.py` - `_generate_with_elevenlabs()` 函数

---

## 🔄 自动重试工作原理

```python
尝试 1: 失败 (SSL 错误) → 等待 2 秒
尝试 2: 失败 (SSL 错误) → 等待 4 秒
尝试 3: 成功 ✅
```

**日志输出示例**:
```
⚠️  ElevenLabs API error (attempt 1/3): SSL error
   Retrying in 2 seconds...
⚠️  ElevenLabs API error (attempt 2/3): SSL error
   Retrying in 4 seconds...
✅ ElevenLabs API succeeded after 3 attempts
```

---

## 🚀 重启服务器

修复已应用，重启服务器生效：

```bash
# 停止服务器
pkill -f "uvicorn app.main:app"

# 重新启动
cd /Users/baojiong/Documents/AI/AudioDrama/backend
./run.sh
```

或者，如果使用 `--reload`，代码会自动重新加载！

---

## 🔍 错误原因分析

### 为什么会出现 SSL 错误？

1. **网络不稳定**
   - 临时网络波动
   - DNS 解析问题
   - 路由问题

2. **API 端点问题**
   - ElevenLabs 服务器临时过载
   - SSL 握手超时
   - 连接被意外关闭

3. **并发请求**
   - 多个音频同时生成
   - TCP 连接池耗尽

4. **防火墙/代理**
   - 企业防火墙干扰
   - VPN 连接不稳定

---

## 🛠️ 其他解决方案

### 方案 1: 检查网络连接

```bash
# 测试 ElevenLabs API 连通性
curl -v https://api.elevenlabs.io/v1/voices \
  -H "xi-api-key: $(grep ELEVENLABS_API_KEY .env | cut -d= -f2)"
```

### 方案 2: 使用 VPN

如果在某些地区，可能需要 VPN 访问 ElevenLabs：

```bash
# 连接 VPN
# 然后重启服务器
```

### 方案 3: 增加超时时间

如果重试仍然失败，可以增加超时：

```python
# app/services/audio_engine.py
client = ElevenLabs(
    api_key=api_key,
    timeout=60.0  # 增加到 60 秒
)
```

### 方案 4: 临时使用免费 Edge TTS

如果 ElevenLabs 持续问题，临时切换到免费版本：

```python
# app/main.py - 临时修改导入
from app.services.audio_engine_free import generate_segment_audio
```

---

## 📊 监控和日志

### 查看实时日志

```bash
# 查看服务器日志
tail -f /Users/baojiong/.cursor/projects/Users-baojiong-Documents-AI-AudioDrama-backend/terminals/4.txt
```

### 检查重试是否生效

正常日志应该显示：
```
Generating audio for segments...
⚠️  ElevenLabs API error (attempt 1/3): SSL...
   Retrying in 2 seconds...
✅ ElevenLabs API succeeded after 2 attempts
Generated 3 audio files
```

---

## 🎯 预防措施

### 1. 稳定的网络环境
- 使用有线网络
- 避免使用不稳定的 WiFi

### 2. 适当的并发控制
```python
# 当前已实现：并发生成音频
# 如果需要限制并发数，可以使用 Semaphore
```

### 3. 监控 ElevenLabs 状态
访问: https://status.elevenlabs.io/

### 4. 备用方案
保留 `audio_engine_free.py` 作为备份

---

## 🧪 测试修复

### 测试 1: 简单请求

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world"}' \
  -o test.zip
```

### 测试 2: 较长文本

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"The mansion stood alone. \"Who goes there?\" Sarah whispered."}' \
  -o test2.zip
```

### 测试 3: 多次请求

```bash
for i in {1..3}; do
  echo "Request $i"
  curl -X POST http://localhost:8000/generate \
    -H "Content-Type: application/json" \
    -d '{"text":"Test '$i'"}' \
    -o test$i.zip
done
```

---

## 📈 性能优化建议

### 1. 使用连接池

```python
# 如果需要，可以配置 httpx 客户端
import httpx

client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10
    )
)
```

### 2. 缓存常用音频

对于常见的文本片段，可以缓存生成的音频。

### 3. 批量处理

如果生成大量音频，考虑分批处理。

---

## 🆘 如果问题持续

### 1. 检查 ElevenLabs 配额

```bash
# 访问 ElevenLabs 控制台
open https://elevenlabs.io/app/settings/subscription
```

### 2. 联系 ElevenLabs 支持

如果问题持续，可能是 API 端问题：
- Email: support@elevenlabs.io
- Discord: https://discord.gg/elevenlabs

### 3. 使用免费替代方案

临时切换到 Edge TTS（完全免费）：

```python
# app/main.py
# 将导入改为：
from app.services.audio_engine_free import generate_segment_audio
```

---

## ✅ 修复验证清单

- [x] 添加重试机制
- [x] 添加指数退避
- [x] 添加详细日志
- [x] 代码无语法错误
- [ ] 重启服务器
- [ ] 测试生成音频
- [ ] 验证重试是否工作

---

## 💡 关键要点

1. **自动重试** - 大多数 SSL 错误会自动恢复
2. **耐心等待** - 重试需要时间（最多 12 秒）
3. **查看日志** - 了解重试过程
4. **备用方案** - Edge TTS 随时可用

---

**修复已完成！现在重启服务器测试。** 🚀

大多数情况下，SSL 错误会在 1-2 次重试后自动恢复！

