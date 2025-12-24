# DramaFlow API 文档

本文档详细描述了 DramaFlow 后端提供的所有 API 接口。

## 目录

1. [通用说明](#1-通用说明)
2. [核心功能](#2-核心功能)
    - [POST /synthesize](#22-post-synthesize) (合成音频)
3. [配置与辅助](#3-配置与辅助)
    - [POST /del_files](#24-post-del_files) (删除文件)
    - [GET /voices](#31-get-voices) (获取声音配置)
    - [POST /review](#32-post-review) (声音试听)
    - [GET /health](#33-get-health) (健康检查)


---

## 1. 通用说明

- **Base URL**: `http://localhost:8000` (本地) 或部署地址
- **鉴权**: 部分接口需要 API Key，通过 Request Headers 传递。如果服务器端配置了 `.env` 环境变量，则 Header 中的 Key 可选（作为覆盖使用）。

### 公共 Headers

| Header 名 | 说明 | 示例 |
| :--- | :--- | :--- |
| `X-OpenRouter-API-Key` | OpenRouter API Key (如有需要) | `sk-or-v1-...` |
| `X-ElevenLabs-API-Key` | ElevenLabs API Key (付费语音合成) | `xi-...` |
| `X-User-Tier` | 用户等级，影响路由策略 | `free` (默认) 或 `vip` |
| `X-Request-ID` | 请求追踪 ID (可选) | `123e4567-e89b...` |

---

## 2. 核心功能



### 2.2 POST `/assign_voices` (New)

为剧本中的角色分配声音 ID (Voice ID)。前端在生成/编辑完剧本后，调用此接口获取系统的声音分配建议。

- **URL**: `/assign_voices`
- **Body**: JSON (SynthesizeRequest)

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `script` | array | 是 | 剧本片段数组。其中 `voice_id` 可以为空字符串。 |

#### 响应
- **Content-Type**: `application/json`

```json
{
  "message": "Voices assigned successfully",
  "script": [
    {
       "type": "dialogue",
       "text": "Hello",
       "character": "Harry",
       "voice_id": "elevenlabs:Adam", 
       "voice_name": "Adam (Deep)"
       ...
    }
  ],
  "metadata": ...
}
```

---

### 2.2 POST `/synthesize`

将结构化的脚本（JSON 格式）合成为完整的音频剧。通常配合前端编辑后的脚本使用。

- **URL**: `/synthesize`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `script` | array | 是 | 结构化的脚本数组。**手动指定 Voice (Manual Override)**: <br>如果脚本中的某个段落包含 `voice_id` 字段且值不是 "", 系统将**强制使用**该 Voice ID (例如 "en-US-Neural2-J") 进行合成，而忽略自动分配逻辑。<br>支持对话角色 (`dialogue`) 和旁白 (`narration`)。 |
| `limit` | int | 否 | - | 生成片段数限制。<br>`1`: 只生成前 1 段<br>`5`: 生成前 5 段<br>`0`: 不生成音频<br>不传: 生成全部 |


#### 响应
- **Content-Type**: `application/json`
- **内容**: 返回音频和字幕的下载链接。

```json
{
  "message": "Synthesis successful",
  "segments_count": 5,
  "audio_url": "https://pub-xxxx.r2.dev/projects/demos/temp/uuid.mp3",
  "srt_url": "https://pub-xxxx.r2.dev/projects/demos/temp/uuid.srt",
  "timeline": [
    { "index": 1, "start": 0, "end": 5000 },
    { "index": 2, "start": 5000, "end": 12000 }
  ]
}
```

- **Headers**:
    - `X-Segments-Count`: 处理的片段数量

---

### 2.3 POST `/save_files` (New)

- **Temp 来源**: 原文件会被**移动**（复制并删除）。适用于首次保存。
- **Saved 来源**: 原文件会被**复制**（保留原文件）。适用于另存为/版本管理。
系统中总是会生成一个新的 UUID。

- **URL**: `/save_files`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `audio_url` | string | 是 | 源音频文件的 URL (可以是 temp, 也可以是 saved) |
| `srt_url` | string | 是 | 源字幕文件的 URL (可以是 temp, 也可以是 saved) |

#### 响应
- **Content-Type**: `application/json`

```json
{
  "audio_url": "https://pub-xxxx.r2.dev/projects/Demos/saved/uuid.mp3",
  "srt_url": "https://pub-xxxx.r2.dev/projects/Demos/saved/uuid.srt"
}
```

---



---

### 2.4 POST `/del_files` (New)

直接从云存储中删除指定的文件的接口。小心使用，删除后不可恢复。

- **URL**: `/del_files`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `audio_url` | string | 否 | 要删除的音频文件 URL |
| `srt_url` | string | 否 | 要删除的字幕文件 URL |

*至少提供一个参数*

#### 响应
- **Content-Type**: `application/json`

```json
{
  "message": "Files deletion processed",
  "details": {
    "audio": true,
    "srt": true
  }
}
```

---


## 3. 配置与辅助

### 3.1 GET `/voices`

获取当前系统支持的所有声音配置及情感参数。前端可用此数据构建声音选择器。

- **URL**: `/voices`
- **响应**: JSON

#### 响应结构 (JSON)

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `voice_map` | object | 包含声音配置，分为 `Basic` (Google) 和 `Advance` (ElevenLabs) 两组。 |


| `emotion_settings` | object | 不同情感对应的语音参数 (稳定性, 相似度等) |
| `samples` | object | 声音试听 URL (如 OpenAI 的静态样本) |

#### 响应示例片段

```json
{
  "voice_map": {
    "Basic": { 
      "en": { 
        "male": { "id": "google:en-US-Neural2-J", "name": "Male J (Neural2)", "avatar_url": "https://pub.r2.dev/voice-avatars/en-US-Neural2-J.jpeg" }
      },
      "pool": { ... }
    },
    "Advance": {
      "male": { "id": "elevenlabs:pNInz6obpgDQGcFmaJgB", "name": "Adam (Deep)", "avatar_url": "https://pub.r2.dev/voice-avatars/pNInz6obpgDQGcFmaJgB.jpeg" },
      "pool": { ... }
    }
  },
  "emotion_settings": {
    "happy": { "stability": 0.45, "style": 0.3 }
  },
  "samples": {
    "openai": {
      "onyx": "https://cdn.openai.com/API/docs/audio/onyx.wav",
      "alloy": "https://cdn.openai.com/API/docs/audio/alloy.wav"
    }
  }
}
```


---


### 3.2 POST `/review`

生成一段试听音频。用于前端用户在调整 `voice` 参数时，实时预览该声音的效果。

- **URL**: `/review`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 限制 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | 是 | Max 100 字符 | 试听文本内容。**注意：系统实际只会合成前 30 个字符。** |
| `voice_id` | string | 是 | - | 目标 Voice ID (如 "google:en-US-Neural2-J") |
| `pacing` | float | 否 | 0.25-4.0 | 语速 (默认 1.0) |
| `emotion` | string | 否 | - | 情感样式 (默认 "neutral") |


#### 响应
- **Content-Type**: `audio/mpeg`
- **内容**: 生成的 MP3 音频文件流。


### 3.3 GET `/health`


详细健康检查，确认 API Key 是否配置。

- **URL**: `/health`
- **响应**: JSON

```json
{
  "status": "healthy",
  "openrouter_configured": true,
  "elevenlabs_configured": true
}
```
