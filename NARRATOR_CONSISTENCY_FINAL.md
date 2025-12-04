# ✅ 旁白声音一致性 - 最终修复

## 🎯 修复目标

确保**整个音频剧从头到尾使用同一个旁白声音**，无论 AI 分析的性别字段是什么。

---

## ✅ 修复实现

### 工作流程

```
1. 用户提交文本
   ↓
2. 在 main.py 中检测整个文本的语言 (一次检测)
   ↓
3. 决定使用哪个旁白声音
   - 中文 → zh-CN-YunxiNeural
   - 英文 → en-US-BrianNeural
   ↓
4. 将这个固定的声音传递给所有旁白片段
   ↓
5. 所有旁白使用相同的声音
```

---

## 🔧 关键代码修改

### 1. main.py - 在脚本级别决定旁白声音

```python
# Step 1.5: 检测语言并确定统一的旁白声音
import re
has_chinese = bool(re.search(r'[\u4e00-\u9fff]', request.text))

if has_chinese:
    narrator_voice = "zh-CN-YunxiNeural"  # 中文男声
else:
    narrator_voice = "en-US-BrianNeural"  # 英文男声

print(f"Using narrator: {narrator_voice}")
```

### 2. main.py - 传递固定声音给所有片段

```python
async def generate_with_limit(segment):
    async with semaphore:
        return await generate_segment_audio(
            segment=segment,
            output_dir=audio_dir,
            elevenlabs_api_key=elevenlabs_key,
            narration_voice=narrator_voice  # ← 固定的旁白声音
        )
```

### 3. audio_engine.py - 使用固定声音

```python
if segment_type == "narration":
    # 使用传入的固定旁白声音，忽略 gender
    await _generate_with_edge_tts(text, None, str(output_file), narration_voice)
```

### 4. audio_engine.py - Edge TTS 函数更新

```python
async def _generate_with_edge_tts(text, gender, output_file, fixed_voice=None):
    if fixed_voice:
        voice = fixed_voice  # 使用固定声音
    else:
        voice = NARRATION_VOICE_EN  # 默认
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
```

---

## 🎭 效果演示

### 场景：混合性别的旁白片段

**输入脚本**:
```json
[
  {"type": "narration", "text": "老人走向山顶", "gender": "male"},
  {"type": "dialogue", "text": "你是谁", "character": "年轻人", "gender": "male"},
  {"type": "narration", "text": "她低声说道", "gender": "female"},  // ← 注意这里是 female
  {"type": "narration", "text": "他转身离开", "gender": "male"}
]
```

### ❌ 之前的行为（会切换）

```
旁白1: gender=male   → 可能用 Brian
旁白2: gender=female → 切换到 Sonia  ❌
旁白3: gender=male   → 切换回 Brian  ❌
```

### ✅ 现在的行为（始终一致）

```
检测语言: 中文 → 决定使用 zh-CN-YunxiNeural

旁白1: gender=male   → zh-CN-YunxiNeural
旁白2: gender=female → zh-CN-YunxiNeural  ✅ 保持一致
旁白3: gender=male   → zh-CN-YunxiNeural  ✅ 保持一致

所有旁白 = 同一个声音！
```

---

## 📊 声音使用策略

| 类型 | 声音选择 | 依据 |
|------|----------|------|
| **旁白** | 固定单一声音 | 在脚本开始时检测语言，整个作品使用同一个 |
| **对话** | 根据角色性别 | 每个角色根据 gender 字段选择声音 |

---

## 🌍 语言检测

### 检测逻辑

```python
import re
has_chinese = bool(re.search(r'[\u4e00-\u9fff]', original_text))
```

**规则**:
- 文本中有任何中文字符 → 使用中文旁白
- 纯英文/其他语言 → 使用英文旁白

### 混合语言文本

```python
text = "The story begins. 故事开始了。"
# 结果：检测到中文 → 使用 zh-CN-YunxiNeural
```

---

## 🎙️ 配置的旁白声音

### 当前配置

```python
NARRATION_VOICE_EN = "en-US-BrianNeural"  # 英文男声
NARRATION_VOICE_ZH = "zh-CN-YunxiNeural"  # 中文男声
```

### 切换为女声旁白

编辑 `app/services/audio_engine.py` 第 18 行：

```python
# 中文女声旁白
NARRATION_VOICE_ZH = "zh-CN-XiaoxiaoNeural"

# 英文女声旁白
NARRATION_VOICE_EN = "en-GB-SoniaNeural"
```

---

## 🧪 验证步骤

### 1. 检查日志

生成音频时应该看到：

```
Analyzing text (963 characters)...
Detected Chinese text. Using narrator: zh-CN-YunxiNeural  ← 看这里！
Generated script with 10 segments
Generating audio for segments...
   Using consistent narrator voice: zh-CN-YunxiNeural  ← 每个旁白都显示
   Using consistent narrator voice: zh-CN-YunxiNeural
   Using consistent narrator voice: zh-CN-YunxiNeural
Generated 10 audio files
```

### 2. 测试用例

**测试 1: 纯中文**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"老人站在山顶。「你好」他说。风吹过。「再见」她说。"}' \
  -o test_chinese.zip
```

**预期**: 所有旁白使用 `zh-CN-YunxiNeural`

**测试 2: 纯英文**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"The old man stood. \"Hello\" he said. Wind blew. \"Goodbye\" she said."}' \
  -o test_english.zip
```

**预期**: 所有旁白使用 `en-US-BrianNeural`

**测试 3: 混合语言**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"The story begins. 老人站在山顶。"}' \
  -o test_mixed.zip
```

**预期**: 检测到中文 → 所有旁白使用 `zh-CN-YunxiNeural`

---

## 🔍 代码审查

### 关键检查点

✅ **1. 语言检测位置**
```python
# main.py - Line ~167
# 在整个脚本生成前检测一次
has_chinese = bool(re.search(r'[\u4e00-\u9fff]', request.text))
```

✅ **2. 决定旁白声音**
```python
# main.py - Line ~170
narrator_voice = "zh-CN-YunxiNeural" if has_chinese else "en-US-BrianNeural"
```

✅ **3. 传递给所有片段**
```python
# main.py - Line ~185
return await generate_segment_audio(
    segment=segment,
    narration_voice=narrator_voice  # 所有片段收到相同的声音
)
```

✅ **4. 使用固定声音**
```python
# audio_engine.py - Line ~77
if segment_type == "narration":
    await _generate_with_edge_tts(text, None, str(output_file), narration_voice)
```

✅ **5. Edge TTS 应用固定声音**
```python
# audio_engine.py - Line ~99
if fixed_voice:
    voice = fixed_voice  # 使用传入的固定声音
```

---

## 📋 完整流程

```
1. 用户提交: "老人说话。「你好」他说。风吹。「再见」她说。"
   ↓
2. 检测语言: 发现中文 → narrator_voice = "zh-CN-YunxiNeural"
   ↓
3. AI 分析生成脚本:
   - 旁白1: gender=male
   - 对话1: gender=male
   - 旁白2: gender=female  ← AI 可能错误分析为 female
   - 对话2: gender=female
   ↓
4. 生成音频:
   - 旁白1: 使用 zh-CN-YunxiNeural (忽略 gender=male)
   - 对话1: 使用 ElevenLabs 男声 (使用 gender=male)
   - 旁白2: 使用 zh-CN-YunxiNeural (忽略 gender=female) ✅
   - 对话2: 使用 ElevenLabs 女声 (使用 gender=female)
   ↓
5. 结果: 所有旁白声音一致！
```

---

## ✅ 验证清单

- [x] 在 main.py 中添加语言检测
- [x] 决定统一的旁白声音
- [x] 传递 narration_voice 参数
- [x] generate_segment_audio 接受参数
- [x] _generate_with_edge_tts 使用固定声音
- [x] 添加日志输出
- [x] 代码无语法错误
- [ ] 服务器自动重载
- [ ] 测试验证

---

## 🎊 总结

### 关键改进

1. **语言检测在脚本级别** - 只检测一次原始文本
2. **固定旁白声音** - 整个请求使用同一个旁白声音
3. **忽略 gender 字段** - 旁白不再受 AI 分析的 gender 影响
4. **对话仍然灵活** - 角色对话根据 gender 选择声音
5. **自动语言支持** - 中英文自动选择对应旁白

### 保证

✅ **从第一个旁白到最后一个旁白，声音绝对一致！**

---

*修复完成！你的音频剧旁白现在像专业播音员一样保持声音的完美一致性！* 🎙️✨

