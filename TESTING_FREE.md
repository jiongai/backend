# 🆓 免费测试模式 - 仅使用 Edge TTS

如果你的 ElevenLabs API 密钥有问题，或者想先测试系统，可以使用完全免费的 Edge TTS 版本。

## 🎯 临时切换到免费模式

### 方法 1: 修改 main.py（临时测试）

编辑 `app/main.py`，找到第 19-23 行的导入语句：

```python
from app.services import (
    analyze_text,
    generate_segment_audio,
    merge_audio_and_generate_srt
)
```

改为：

```python
from app.services import (
    analyze_text,
    merge_audio_and_generate_srt
)
from app.services.audio_engine_free import generate_segment_audio
```

保存后重启服务器：
```bash
# Ctrl+C 停止
./run.sh  # 重新启动
```

### 方法 2: 创建测试端点

或者保持原代码不变，我可以创建一个专门的测试端点。

---

## 🎭 免费版本的声音配置

**旁白 (Narration)**:
- 男性: `en-US-BrianNeural` (专业、深沉)
- 女性: `en-GB-SoniaNeural` (英式、优雅)

**对话 (Dialogue)**:
- 男性: `en-US-GuyNeural` (友好、清晰)
- 女性: `en-US-JennyNeural` (活泼、自然)

通过使用不同的声音，仍然可以区分旁白和对话！

---

## ✅ 优点

1. **完全免费** - 无需 API 密钥或订阅
2. **无配额限制** - 可以无限制测试
3. **快速测试** - 验证整个系统流程
4. **高质量** - Edge TTS 质量很好

## ⚠️ 限制

1. 声音选择较少
2. 无法微调情绪和语调
3. 对中文支持需要额外配置

---

## 🔄 切换回付费版本

完成测试后，要使用 ElevenLabs：

1. 恢复 `app/main.py` 的原始导入
2. 配置有效的 ElevenLabs API 密钥
3. 重启服务器

---

## 🧪 快速测试

```bash
# 启动服务器
./run.sh

# 在另一个终端测试
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The old mansion stood alone. \"Who is there?\" Sarah whispered nervously."
  }' \
  -o test_drama_free.mp3

# 播放测试
open test_drama_free.mp3
```

---

*这个免费版本非常适合开发和测试！*

