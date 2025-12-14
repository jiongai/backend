# DramaFlow API 文档

本文档详细描述了 DramaFlow 后端提供的所有 API 接口。

## 目录

1. [通用说明](#1-通用说明)
2. [核心功能](#2-核心功能)
    - [POST /analyze](#21-post-analyze) (解析文本)
    - [POST /synthesize](#22-post-synthesize) (合成音频)
    - [POST /generate](#23-post-generate) (全流程生成)
3. [配置与辅助](#3-配置与辅助)
    - [GET /voices](#31-get-voices) (获取声音配置)
    - [GET /health](#32-get-health) (健康检查)

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

---

## 2. 核心功能

### 2.1 POST `/analyze`

解析小说文本，将其转换为结构化的音频剧脚本。此接口**不生成音频**，仅用于预览。

- **URL**: `/analyze`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 限制 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | 是 | 10-10000 字符 | 小说文本内容 |

#### 响应示例

```json
{
  "script": [
    {
      "type": "narration",
      "text": "The wind howled.",
      "character": "Narrator",
      "gender": "male",
      "emotion": "fearful",
      "character": "Narrator",
      "gender": "male",
      "emotion": "fearful",
      "pacing": 1.0,
      "voice": "待定"
    }

  ],
  "metadata": {
    "segments_count": 1,
    "narration_count": 1,
    "dialogue_count": 0,
    "characters": ["Narrator"]
  }
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
| `script` | array | 是 | 结构化的脚本数组。**支持手动指定 Voice**: 若片段包含 `voice` 字段且值不是 "待定", 则强制使用该 Voice ID (如 "en-US-Neural2-J")。 |


#### 响应
- **Content-Type**: `application/zip`
- **内容**: ZIP 包，解压后包含：
    1. `drama.mp3`: 音频文件
    2. `drama.srt`: 字幕文件
    3. `roles.json`: 角色配音表 (包含角色名、Voice ID、Voice Name)

- **Headers**:
    - `X-Segments-Count`: 处理的片段数量

---

### 2.3 POST `/generate`

全流程接口：输入文本 -> 自动分析 -> 自动合成 -> 返回音频包。

- **URL**: `/generate`
- **Body**: JSON

#### 请求参数 (Body)

| 参数名 | 类型 | 必填 | 限制 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | 是 | 10-10000 字符 | 小说文本内容 |

#### 响应
- **Content-Type**: `application/zip`
- **内容**: 包含 `drama.mp3`, `drama.srt` 和 `roles.json` 的 ZIP 包。


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
        "male": { "id": "en-US-Neural2-J", "name": "Male J (Neural2)" }
      },
      "pool": { ... }
    },
    "Advance": {
      "male": { "id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Deep)" },
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

### 3.2 GET `/health`

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
