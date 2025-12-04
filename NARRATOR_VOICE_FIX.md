# 🎙️ 旁白声音一致性修复

## ✅ 已修复

### 问题
之前的实现会根据 `segment['gender']` 字段切换旁白声音，导致同一个旁白者在不同段落使用不同的声音，破坏了叙事的连贯性。

### 修复方案
现在所有旁白（narration）片段使用**单一固定的声音**，无论 AI 分析的性别是什么。

---

## 🔧 修改内容

### 1. 声音配置

**之前**（会切换）:
```python
NARRATION_VOICES = {
    "male": "en-US-BrianNeural",
    "female": "en-GB-SoniaNeural"
}
```

**现在**（固定单一声音）:
```python
# 旁白：使用单一一致的声音
NARRATION_VOICE_EN = "en-US-BrianNeural"  # 英文旁白
NARRATION_VOICE_ZH = "zh-CN-YunxiNeural"  # 中文旁白
```

### 2. 生成逻辑

**关键变化**:
```python
if segment_type == "narration":
    # ✅ 忽略 gender 字段，传入 None
    await _generate_with_edge_tts(text, None, str(output_file))
elif segment_type == "dialogue":
    # ✅ 对话仍然使用 gender 选择声音
    await _generate_with_elevenlabs(text, gender, str(output_file), ...)
```

### 3. 自动语言检测

```python
# 自动检测中文
has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
voice = NARRATION_VOICE_ZH if has_chinese else NARRATION_VOICE_EN
```

---

## 🎭 效果对比

### 之前的行为
```
旁白片段 1 (gender: male)   → 使用 Brian 声音
旁白片段 2 (gender: female) → 使用 Sonia 声音  ❌ 切换了！
旁白片段 3 (gender: male)   → 使用 Brian 声音  ❌ 又切换了！
```

### 现在的行为
```
旁白片段 1 (gender: male)   → 使用 Brian 声音
旁白片段 2 (gender: female) → 使用 Brian 声音  ✅ 保持一致
旁白片段 3 (gender: male)   → 使用 Brian 声音  ✅ 保持一致
```

**结果**: 整个音频剧的旁白保持同一个声音，专业且连贯！

---

## 🌍 语言支持

### 英文文本
```
自动使用: en-US-BrianNeural
特点: 专业、深沉、适合叙事
```

### 中文文本
```
自动使用: zh-CN-YunxiNeural (男声)
特点: 成熟、稳重、专业播音
```

### 切换中文女声旁白

如果想用女声旁白，修改 `audio_engine.py` 第 18 行：

```python
# 修改前
NARRATION_VOICE_ZH = "zh-CN-YunxiNeural"  # 男声

# 修改为
NARRATION_VOICE_ZH = "zh-CN-XiaoxiaoNeural"  # 女声
```

---

## 📋 可用的中文旁白声音

### 推荐选项

| Voice ID | 性别 | 特点 | 适合场景 |
|----------|------|------|----------|
| **zh-CN-YunxiNeural** | 男 | 成熟、专业、播音腔 | ✅ 严肃文学、历史 |
| **zh-CN-XiaoxiaoNeural** | 女 | 温柔、清晰、亲切 | ✅ 言情、温馨故事 |
| zh-CN-YunyangNeural | 男 | 年轻、活力 | 青春、轻松 |
| zh-CN-XiaochenNeural | 女 | 甜美、可爱 | 儿童故事 |
| zh-CN-YunhaoNeural | 男 | 沉稳、权威 | 纪实、新闻 |

### 测试不同声音

```python
# 测试命令
import edge_tts
import asyncio

async def test_voice():
    text = "这是一个测试文本"
    communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
    await communicate.save("test_voice.mp3")

asyncio.run(test_voice())
```

---

## 🎨 角色配置建议

### 方案 1: 男声旁白 + 多角色对话（当前默认）
```python
NARRATION_VOICE_ZH = "zh-CN-YunxiNeural"  # 男声旁白
# 对话：使用 ElevenLabs 的不同声音
```

**适合**: 大多数小说、传统叙事

### 方案 2: 女声旁白 + 多角色对话
```python
NARRATION_VOICE_ZH = "zh-CN-XiaoxiaoNeural"  # 女声旁白
# 对话：使用 ElevenLabs 的不同声音
```

**适合**: 女性视角、言情小说

### 方案 3: 年轻男声旁白
```python
NARRATION_VOICE_ZH = "zh-CN-YunyangNeural"  # 年轻男声
```

**适合**: 青春校园、轻小说

---

## 🔄 自动重载

如果服务器使用 `--reload` 启动，代码修改会自动生效：

```bash
# 应该看到
INFO: WatchFiles detected changes in 'app/services/audio_engine.py'
INFO: Reloading...
```

无需手动重启！

---

## 🧪 测试修复

### 测试用例

```json
{
  "text": "老人站在山顶。「你是谁？」年轻人问道。风吹过树林。「我是守护者。」老人回答。"
}
```

**预期结果**:
- ✅ 旁白1（"老人站在山顶"）: zh-CN-YunxiNeural
- ✅ 对话1（年轻人）: ElevenLabs 男声
- ✅ 旁白2（"风吹过树林"）: zh-CN-YunxiNeural ⭐ **相同声音！**
- ✅ 对话2（老人）: ElevenLabs 男声

---

## 📊 技术细节

### 语言检测逻辑

```python
import re
has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
```

**检测范围**: Unicode 中日韩统一表意文字 (CJK Unified Ideographs)
- U+4E00 到 U+9FFF
- 覆盖常用中文字符

### 混合语言文本

```
"The old man stood. 老人站在山顶。"
```

**处理**: 只要包含中文字符，就使用中文声音

---

## 💡 最佳实践

### 1. 选择旁白声音的原则

- **一致性优先**: 整个作品使用同一个旁白声音
- **匹配内容**: 严肃内容用成熟声音，轻松内容用年轻声音
- **避免性别刻板**: 男女声都可以讲任何故事

### 2. 旁白 vs 对话

| 类型 | 声音策略 | 原因 |
|------|----------|------|
| **旁白** | 固定单一 | 保持叙事连贯性 |
| **对话** | 根据角色变化 | 区分不同角色 |

### 3. 测试建议

生成音频后：
1. 听完整作品，检查旁白声音是否一致
2. 确认对话和旁白有明显区分
3. 验证语言检测准确（中英文混合时）

---

## 🔧 自定义配置

### 使用环境变量（高级）

```bash
# .env
NARRATION_VOICE_EN=en-US-BrianNeural
NARRATION_VOICE_ZH=zh-CN-YunxiNeural
```

```python
# audio_engine.py
NARRATION_VOICE_EN = os.getenv("NARRATION_VOICE_EN", "en-US-BrianNeural")
NARRATION_VOICE_ZH = os.getenv("NARRATION_VOICE_ZH", "zh-CN-YunxiNeural")
```

---

## ✅ 验证清单

修复后确认：

- [x] 旁白声音配置改为单一常量
- [x] generate_segment_audio 传入 None 给旁白
- [x] _generate_with_edge_tts 处理 None 参数
- [x] 添加语言自动检测
- [x] 代码无语法错误
- [ ] 服务器已重载
- [ ] 测试生成音频
- [ ] 验证旁白声音一致

---

## 🎊 总结

**核心改进**:
1. ✅ 旁白声音保持一致
2. ✅ 自动检测语言
3. ✅ 支持中英文
4. ✅ 易于切换旁白声音
5. ✅ 对话声音仍然多样

**结果**: 更专业、更连贯的音频剧体验！🎭✨

---

*修复完成！你的旁白现在会保持一致的声音了！*

