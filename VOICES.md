# 🎤 DramaFlow 音色与情感配置指南

DramaFlow 采用分级多云混合 TTS 架构（Hybrid Routing Strategy），支持从高性价比的标准音色到高拟真、富有表现力的电影级音色。

---

## 1. 声音分级与供应商架构

| 梯队 | 适用群体 | 供应商 | 典型场景 | 特性 |
| :--- | :--- | :--- | :--- | :--- |
| **Basic (标准)** | 免费用户 / 标准角色 | **Google Cloud TTS** & **Azure Speech** | 旁白、大体量配角对白 | 成本极低、延迟极低、发音清晰标准，支持 Neural2 与 Wavenet 深度神经网络 |
| **Advance (高级)** | VIP 用户 / 核心主角 | **ElevenLabs** & **OpenAI TTS** | 核心男女主角深度对白、重要情绪高潮段落 | 声音自然生动、极具戏剧感染力，支持细粒度情绪（Stability/Style）注入 |

---

## 2. 默认音色对照表

### 旁白 (Narration)
系统会在合成前自动检测文本语种，锁定统一旁白音色，保证全剧声音连贯：

| 语种 | 默认发音人 | 供应商 | Voice ID | 音色特点 |
| :--- | :--- | :--- | :--- | :--- |
| **中文** | 云希 (故事) | Azure / Google | `azure:zh-CN-YunxiNeural` | 沉稳大气、富有叙事张力，专业有声书演播质感 |
| **英文** | Brian (Narrator) | Azure / Google | `azure:en-US-BrianNeural` | 磁性英朗、纯正叙事腔调 |
| **VIP 旁白** | Onyx / Alloy | OpenAI | `openai:onyx` / `openai:alloy` | 现代播客级质感、声音细腻温润 |

### 对白角色 (Dialogue)

#### Basic (Google Cloud TTS)
- **中文发音人池**：
  - 女声：`cmn-CN-Wavenet-A` (小燕 - 甜美), `cmn-CN-Wavenet-D` (晓晓 - 亲切), `cmn-TW-Wavenet-A` (台湾女声)
  - 男声：`cmn-CN-Wavenet-C` (云希 - 故事), `cmn-CN-Wavenet-B` (云扬 - 播音), `cmn-TW-Wavenet-B/C` (台湾男声)
- **英文发音人池**：
  - 女声：`en-US-Neural2-F` (Jennifer - 温暖), `en-US-Neural2-C` (Sarah - 明亮), `en-US-Neural2-E` (Emily - 柔和), `en-GB-Neural2-A` (英音女声) 等
  - 男声：`en-US-Neural2-J` (Michael - 活力), `en-US-Neural2-A` (Steven - 经典), `en-US-Neural2-D` (Robert - 深沉), `en-GB-Neural2-B` (英音男声) 等

#### Advance (ElevenLabs 精选库)
- **男声精选**：
  - `pNInz6obpgDQGcFmaJgB`：**Adam (Deep)** - 成熟低沉、磁性霸道
  - `ErXwobaYiN019PkySvjV`：**Antoni (Young)** - 阳光少年、富有活力
  - `VR6AewLTigWG4xSOukaG`：**Arnold (Strong)** - 强壮威严、战士首领
  - `N2lVS1w4EtoT3dr4eOWO`：**Callum (Calm)** - 儒雅平静、专业内敛
  - `yoZ06aMxZJJ28mfd3POQ`：**Sam (Lively)** - 机灵敏捷、幽默风趣
- **女声精选**：
  - `21m00Tcm4TlvDq8ikWAM`：**Rachel (Warm)** - 温暖治愈、知性从容
  - `MF3mGyEYCl7XYWbV9V6O`：**Elli (Lively)** - 活泼俏皮、元气少女
  - `EXAVITQu4vr4xnSDxMaL`：**Bella (Soft)** - 柔弱温婉、邻家女孩
  - `XB0fDUnXU5powFXDhCwa`：**Charlotte (Elegant)** - 优雅贵气、高岭之花
  - `ThT5KcBeYPX3keUQqHPh`：**Dorothy (Wise)** - 慈祥睿智、长者智囊

---

## 3. 情绪参数矩阵 (Emotion Settings)

针对 ElevenLabs，系统内建了 8 种戏剧化情感调节参数，在合成时自动注入发音引擎：

| 情感分类 | Stability (稳定性) | Similarity Boost (相似度提升) | Style (风格化夸张度) | 适用戏剧场景 |
| :--- | :--- | :--- | :--- | :--- |
| `neutral` | 0.60 | 0.75 | 0.0 | 日常叙事、平稳交谈 |
| `happy` | 0.45 | 0.80 | 0.3 | 喜悦、兴奋、庆贺 |
| `sad` | 0.40 | 0.70 | 0.2 | 悲伤、低落、抽泣 |
| `angry` | 0.30 | 0.80 | 0.6 | 愤怒、争吵、怒斥 |
| `fearful` | 0.30 | 0.65 | 0.5 | 恐惧、战栗、惊恐 |
| `surprised`| 0.35 | 0.75 | 0.4 | 诧异、不可置信 |
| `whispering`| 0.50 | 0.50 | 0.0 | 窃窃私语、密谋、耳语 |
| `shouting` | 0.25 | 0.80 | 0.7 | 呐喊、呼救、战场咆哮 |

---

## 4. 如何配置与扩展新音色

> [!IMPORTANT]
> **切勿修改代码中的硬编码！** 全部音色池、发音人映射和情绪参数均统一收口在 [`app/config/voices.json`](file:///Users/baojiong/My%20Projects/AIAudioDrarm/DramaFlow/app/config/voices.json)。

### 步骤一：在 `voices.json` 中登记
1. 在 `VOICE_MAP` 中将新 Voice ID 追加至对应的供应商音色池（如 `elevenlabs.pool.male` 或 `google.pool.zh.female`）。
2. 在 `VOICE_LABELS` 中添加展示名称映射，例如：
   ```json
   "VOICE_LABELS": {
       "my-custom-voice-id": "发音人名称 (性格特征)"
   }
   ```

### 步骤二：绑定头像（可选）
在 [`app/config/avatar_map.json`](file:///Users/baojiong/My%20Projects/AIAudioDrarm/DramaFlow/app/config/avatar_map.json) 中为新 Voice ID 绑定展示头像的 CDN URL，前端在调用 `/voices` 时将自动附带该头像链接：
```json
{
  "my-custom-voice-id": "r2.yourdomain.com/voice-avatars/my-custom-voice-id.png"
}
```
修改完成后，重启或热重载服务即可全量生效。
