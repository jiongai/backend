# 🎤 可用声音配置

## 当前配置

### 旁白 (Narration) - Edge TTS (免费)
| 性别 | 声音名称 | Voice ID | 特点 |
|------|----------|----------|------|
| 男性 | Brian | `en-US-BrianNeural` | 专业、深沉、适合叙事 |
| 女性 | Sonia | `en-GB-SoniaNeural` | 英式口音、优雅、温暖 |

### 对话 (Dialogue) - ElevenLabs (付费)
| 性别 | 声音名称 | Voice ID | 特点 |
|------|----------|----------|------|
| 男性 | Adam | `pNInz6obpgDQGcFmaJgB` | 深沉、成熟、磁性 |
| 女性 | Rachel | `21m00Tcm4TlvDq8ikWAM` | 温暖、友好、清晰 |

---

## 更多 ElevenLabs 声音选项

如果想更换声音，可以从以下选项中选择：

### 男性声音

| 名称 | Voice ID | 特点 |
|------|----------|------|
| **Adam** ⭐ | `pNInz6obpgDQGcFmaJgB` | 深沉、成熟（当前使用）|
| Antoni | `ErXwobaYiN019PkySvjV` | 年轻、充满活力 |
| Arnold | `VR6AewLTigWG4xSOukaG` | 强壮、权威 |
| Callum | `N2lVS1w4EtoT3dr4eOWO` | 平静、专业 |
| Charlie | `IKne3meq5aSn9XLyUdCD` | 友好、随和 |
| Clyde | `2EiwWnXFnvU5JabPnv8n` | 中年、温暖 |
| Dave | `CYw3kZ02Hs0563khs1Fj` | 年轻、英式 |
| Fin | `D38z5RcWu1voky8WS1ja` | 爱尔兰口音 |
| George | `JBFqnCBsd6RMkjVDRZzb` | 英式、正式 |
| Josh | `TxGEqnHWrfWFTfGW9XjX` | 专业、新闻播音 |
| Patrick | `ODq5zmih8GrVes37Dizd` | 严肃、权威 |
| Sam | `yoZ06aMxZJJ28mfd3POQ` | 年轻、活泼 |
| Thomas | `GBv7mTt0atIp3Br8iCZE` | 温和、平静 |

### 女性声音

| 名称 | Voice ID | 特点 |
|------|----------|------|
| **Rachel** ⭐ | `21m00Tcm4TlvDq8ikWAM` | 温暖、友好（当前使用）|
| Bella | `EXAVITQu4vr4xnSDxMaL` | 柔和、叙事风格 |
| Charlotte | `XB0fDUnXU5powFXDhCwa` | 英式、优雅 |
| Domi | `AZnzlk1XvdvUeBnXmlld` | 自信、活力 |
| Dorothy | `ThT5KcBeYPX3keUQqHPh` | 年长、智慧 |
| Elli | `MF3mGyEYCl7XYWbV9V6O` | 年轻、活泼 |
| Emily | `LcfcDJNUP1GQjkzn1xUU` | 温柔、平静 |
| Freya | `jsCqWAovK2LkecY7zXl4` | 年轻、美式 |
| Gigi | `jBpfuIE2acCO8z3wKNLl` | 活泼、热情 |
| Glinda | `z9fAnlkpzviPz146aGWa` | 女巫般、神秘 |
| Grace | `oWAxZDx7w5VEj9dCyTzz` | 南方口音、温暖 |
| Jessica | `cgSgspJ2msm6clMCkdW9` | 专业、清晰 |
| Lily | `pFZP5JQG7iQjIQuC4Bku` | 英式、年轻 |
| Matilda | `XrExE9yKIg1WjnnlVkGX` | 温暖、叙事 |
| Nicole | `piTKgcLEGmPE4e6mEKli` | 活力、美式 |
| Sarah | `EXAVITQu4vr4xnSDxMaL` | 专业、新闻 |

---

## 🔧 如何更换声音

### 方法 1: 修改配置文件

编辑 `app/services/audio_engine.py`：

```python
DIALOGUE_VOICES = {
    "male": "TxGEqnHWrfWFTfGW9XjX",    # Josh - 专业播音
    "female": "MF3mGyEYCl7XYWbV9V6O"   # Elli - 年轻活泼
}
```

保存后重启服务器：
```bash
# Ctrl+C 停止
./run.sh
```

### 方法 2: 添加更多声音选项

如果想支持更多角色，可以扩展配置：

```python
DIALOGUE_VOICES = {
    "male": "pNInz6obpgDQGcFmaJgB",    # Adam - 默认男声
    "female": "21m00Tcm4TlvDq8ikWAM",  # Rachel - 默认女声
    "young_male": "ErXwobaYiN019PkySvjV",   # Antoni - 年轻男性
    "young_female": "MF3mGyEYCl7XYWbV9V6O",  # Elli - 年轻女性
    "old_male": "GBv7mTt0atIp3Br8iCZE",      # Thomas - 年长男性
    "old_female": "ThT5KcBeYPX3keUQqHPh"     # Dorothy - 年长女性
}
```

---

## 🧪 测试不同声音

想试听某个声音？使用这个命令：

```bash
# 替换 VOICE_ID 为上表中的任意 voice_id
curl -X POST https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID \
  -H "xi-api-key: $(grep ELEVENLABS_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, this is a test of this voice.","model_id":"eleven_monolingual_v1"}' \
  --output test_voice.mp3 && open test_voice.mp3
```

例如，测试 Josh 的声音：
```bash
curl -X POST https://api.elevenlabs.io/v1/text-to-speech/TxGEqnHWrfWFTfGW9XjX \
  -H "xi-api-key: $(grep ELEVENLABS_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, I am Josh. This is how I sound.","model_id":"eleven_monolingual_v1"}' \
  --output josh_test.mp3 && open josh_test.mp3
```

---

## 📋 获取最新声音列表

ElevenLabs 不断添加新声音。获取完整列表：

```bash
curl -X GET https://api.elevenlabs.io/v1/voices \
  -H "xi-api-key: $(grep ELEVENLABS_API_KEY .env | cut -d= -f2)" | \
  python -m json.tool | grep -A 2 '"name":'
```

---

## 💡 声音选择建议

### 小说转音频剧
- **旁白**: Brian (深沉、专业)
- **主角男性**: Adam (磁性、成熟)
- **主角女性**: Rachel (温暖、友好)
- **配角年轻**: Antoni / Elli
- **配角年长**: Thomas / Dorothy

### 新闻播报
- **男主播**: Josh
- **女主播**: Jessica

### 儿童故事
- **女声**: Elli (活泼)
- **男声**: Charlie (友好)

### 恐怖/悬疑
- **旁白**: Clyde (深沉)
- **神秘角色**: Glinda (神秘)

---

*选择合适的声音可以大大提升音频剧的质量！*

