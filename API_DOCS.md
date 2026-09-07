# DramaFlow API 接口文档

本文档详细规范了 DramaFlow 后端微服务提供的所有 RESTful API 接口。

---

## 目录

1. [通用说明与鉴权规范](#1-通用说明与鉴权规范)
2. [核心合成与剧本编排](#2-核心合成与剧本编排)
   - [2.1 POST /assign_voices (智能分配声音)](#21-post-assign_voices-智能分配声音)
   - [2.2 POST /synthesize (完整音频剧合成)](#22-post-synthesize-完整音频剧合成)
3. [文件存储与生命周期管理 (Cloudflare R2)](#3-文件存储与生命周期管理-cloudflare-r2)
   - [3.1 POST /save_files (固化保存文件)](#31-post-save_files-固化保存文件)
   - [3.2 POST /move_files_to_temp (移回临时存储)](#32-post-move_files_to_temp-移回临时存储)
   - [3.3 POST /del_files (物理删除文件)](#33-post-del_files-物理删除文件)
4. [声音配置与辅助调试](#4-声音配置与辅助调试)
   - [4.1 GET /voices (获取声音目录与情感配置)](#41-get-voices-获取声音目录与情感配置)
   - [4.2 POST /review (单句音色快速试听)](#42-post-review-单句音色快速试听)
   - [4.3 GET /health (服务健康与密钥检查)](#43-get-health-服务健康与密钥检查)
   - [4.4 GET / (基础运行状态)](#44-get--基础运行状态)

---

## 1. 通用说明与鉴权规范

- **Base URL**: `http://localhost:8000` (本地开发) 或生产部署地址
- **响应格式**: `application/json` (部分试听流为 `audio/mpeg`)

### 公共 Request Headers

| Header 名 | 类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `X-Access-Secret` | string | 条件必填 | 后端全局安全访问密钥。当服务端环境变量配置了 `DARMAFLOW_API_ACCESS_SECRET` 时必须携带。 | `Bao32db04...` |
| `X-User-Tier` | string | 否 | 用户等级。`free` (默认) 或 `vip`。直接决定 TTS 混合路由策略。 | `free` / `vip` |
| `X-ElevenLabs-API-Key` | string | 否 | ElevenLabs API Key。可用于覆盖服务器默认配置（按请求计费归属）。 | `xi-...` |
| `X-OpenRouter-API-Key` | string | 否 | OpenRouter API Key（保留供扩展使用）。 | `sk-or-v1-...` |
| `X-Correlation-ID` | string | 否 | 请求链路追踪 ID。未提供时系统自动生成 UUID。 | `b8e4f1a2-...` |

---

## 2. 核心合成与剧本编排

### 2.1 POST `/assign_voices` (智能分配声音)

根据角色名、性别与语言，利用确定性哈希算法为结构化剧本中的各个片段预分配合适的 Voice ID。前端通常在“智能配音/Magic Fill”功能中调用此接口，获取声音建议后再允许用户微调。

- **URL**: `/assign_voices`
- **Method**: `POST`
- **Query Parameters**:
  - `languages` (可选，可多次传递): 限制声音分配的语种范围（如 `?languages=en&languages=zh`）。不传时默认限制为 `en`。

#### 请求体 (Body - JSON)

```json
{
  "script": [
    {
      "type": "narration",
      "text": "清晨的微风穿过树林，带来了一丝凉意。",
      "character": "Narrator",
      "gender": "neutral",
      "emotion": "neutral",
      "pacing": 1.0,
      "voice_id": ""
    },
    {
      "type": "dialogue",
      "text": "我们真的要走这条路吗？",
      "character": "艾米丽",
      "gender": "female",
      "emotion": "fearful",
      "pacing": 1.0,
      "voice_id": ""
    }
  ]
}
```

#### 响应体 (Response - JSON)

```json
{
  "message": "Voices assigned successfully",
  "script": [
    {
      "type": "narration",
      "text": "清晨的微风穿过树林，带来了一丝凉意。",
      "character": "Narrator",
      "gender": "neutral",
      "emotion": "neutral",
      "pacing": 1.0,
      "voice_id": "azure:zh-CN-YunxiNeural"
    },
    {
      "type": "dialogue",
      "text": "我们真的要走这条路吗？",
      "character": "艾米丽",
      "gender": "female",
      "emotion": "fearful",
      "pacing": 1.0,
      "voice_id": "google:cmn-CN-Wavenet-A"
    }
  ],
  "metadata": {
    "segments_count": 2,
    "characters": ["Narrator", "艾米丽"]
  }
}
```

---

### 2.2 POST `/synthesize` (完整音频剧合成)

核心业务接口。根据输入的结构化剧本并发调用各 TTS 引擎生成语音，并在后台流水线中执行**语速微调 (Pacing) -> 插入 300ms 黄金静音间隙 -> 音轨混音导出 -> 生成标准 SRT 字幕与 Timeline 时间轴 -> 上传至 Cloudflare R2**。

- **URL**: `/synthesize`
- **Method**: `POST`

#### 请求参数 (Body - JSON)

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `script` | array[object] | 是 | 结构化剧本片段列表。若片段包含有效的 `voice_id`（如 `"google:en-US-Neural2-J"` 或 `"elevenlabs:pNInz6obpgDQGcFmaJgB"`），系统将**强制使用指定的音色**；支持旁白与角色独立定制。 |
| `limit` | integer | 否 | 合成片段数量限制。<br>• `null`/不填: 合成全部片段<br>• `>0`: 截取前 N 个片段合成（用于快速试听测试）<br>• `0`: 跳过合成直接返回 |

#### 请求体示例

```json
{
  "script": [
    {
      "type": "narration",
      "text": "The wind howled outside the cabin.",
      "character": "Narrator",
      "gender": "neutral",
      "emotion": "neutral",
      "pacing": 1.0,
      "voice_id": "google:en-US-Neural2-J"
    },
    {
      "type": "dialogue",
      "text": "Did you hear that noise?",
      "character": "David",
      "gender": "male",
      "emotion": "fearful",
      "pacing": 1.1,
      "voice_id": "elevenlabs:pNInz6obpgDQGcFmaJgB"
    }
  ],
  "limit": null
}
```

#### 响应体 (Response - JSON)

```json
{
  "message": "Synthesis successful",
  "segments_count": 2,
  "audio_duration_ms": null,
  "audio_url": "https://pub-xxx.r2.dev/projects/DramaFlow/temp/3a4b9c1d-8e7f-4a0b-bcde-1234567890ab.mp3",
  "srt_url": "https://pub-xxx.r2.dev/projects/DramaFlow/temp/3a4b9c1d-8e7f-4a0b-bcde-1234567890ab.srt",
  "timeline": [
    {
      "index": 1,
      "start": 0,
      "end": 3200
    },
    {
      "index": 2,
      "start": 3500,
      "end": 5800
    }
  ]
}
```

> [!NOTE]
> `audio_url` 与 `srt_url` 初始生成在 `temp/` 临时目录下。若需要长久保存，请调用 `/save_files` 固化归档。

---

## 3. 文件存储与生命周期管理 (Cloudflare R2)

### 3.1 POST `/save_files` (固化保存文件)

将生成的音频和字幕文件转正保存：
- **来源为 `temp`**: 执行 Copy-on-Write 分配全新独立 UUID 并删除临时源文件，移入 `saved/` 目录。
- **来源已在 `saved`**: 复制生成新的独立快照副本（用于版本管理或另存为）。

- **URL**: `/save_files`
- **Method**: `POST`

#### 请求参数 (Body - JSON)

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `audio_url` | string | 是 | 当前音频文件完整 URL（支持 temp 或 saved） |
| `srt_url` | string | 是 | 当前字幕文件完整 URL（支持 temp 或 saved） |

#### 响应体 (Response - JSON)

```json
{
  "audio_url": "https://pub-xxx.r2.dev/projects/DramaFlow/saved/8f6e4d2c-1b0a-4c9d-8e7f-9876543210fe.mp3",
  "srt_url": "https://pub-xxx.r2.dev/projects/DramaFlow/saved/8f6e4d2c-1b0a-4c9d-8e7f-9876543210fe.srt"
}
```

---

### 3.2 POST `/move_files_to_temp` (移回临时存储)

将已归档在 `saved/` 目录下的文件移回 `temp/` 临时目录（生成全新 UUID 并删除旧文件），使其重新受制于临时文件的生命周期清理规则。

- **URL**: `/move_files_to_temp`
- **Method**: `POST`

#### 请求体 (Body - JSON)

```json
{
  "audio_url": "https://pub-xxx.r2.dev/projects/DramaFlow/saved/xxx.mp3",
  "srt_url": "https://pub-xxx.r2.dev/projects/DramaFlow/saved/xxx.srt"
}
```

#### 响应体 (Response - JSON)

```json
{
  "audio_url": "https://pub-xxx.r2.dev/projects/DramaFlow/temp/new_uuid.mp3",
  "srt_url": "https://pub-xxx.r2.dev/projects/DramaFlow/temp/new_uuid.srt"
}
```

---

### 3.3 POST `/del_files` (物理删除文件)

从云存储桶中永久删除指定的一个或多个音频/字幕文件。

- **URL**: `/del_files`
- **Method**: `POST`

#### 请求参数 (Body - JSON)

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `audio_url` | string | 否 | 要删除的音频 URL |
| `srt_url` | string | 否 | 要删除的字幕 URL |

*(至少提供其中一个参数)*

#### 响应体 (Response - JSON)

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

## 4. 声音配置与辅助调试

### 4.1 GET `/voices` (获取声音目录与情感配置)

获取系统当前收录的全部音色池（区分 Basic 与 Advance 梯队）、各情感对应的合成超参数，以及试听样例 URL。前端可据此渲染音色选择下拉菜单。

- **URL**: `/voices`
- **Method**: `GET`
- **Query Parameters**:
  - `languages` (可选，可多次传递): 语种筛选（如 `?languages=en&languages=zh`）。不传时默认返回英文 (`en`) 音色。

#### 响应体 (Response - JSON) 片段示例

```json
{
  "voice_map": {
    "Basic": {
      "en": {
        "male": {
          "id": "google:en-US-Neural2-J",
          "name": "Michael (Energetic)",
          "avatar_url": "https://r2.fictalk.com/voice-avatars/en-US-Neural2-J.png"
        },
        "female": {
          "id": "google:en-US-Neural2-F",
          "name": "Jennifer (Warm)",
          "avatar_url": "https://r2.fictalk.com/voice-avatars/en-US-Neural2-F.png"
        }
      },
      "pool": { ... }
    },
    "Advance": {
      "male": {
        "id": "elevenlabs:pNInz6obpgDQGcFmaJgB",
        "name": "Adam (Deep)",
        "avatar_url": "https://r2.fictalk.com/voice-avatars/pNInz6obpgDQGcFmaJgB.png"
      },
      "pool": { ... }
    }
  },
  "emotion_settings": {
    "neutral": { "stability": 0.6, "similarity_boost": 0.75, "style": 0.0 },
    "happy": { "stability": 0.45, "similarity_boost": 0.8, "style": 0.3 },
    "angry": { "stability": 0.3, "similarity_boost": 0.8, "style": 0.6 }
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

### 4.2 POST `/review` (单句音色快速试听)

为前端用户在选择声音或调节配速/情感时提供单句实时试听。

- **URL**: `/review`
- **Method**: `POST`
- **限制说明**: 输入文本最大限制 100 字符，服务端出于性能考虑会截取前 30 个字符进行实时合成。

#### 请求参数 (Body - JSON)

| 字段名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | 是 | - | 试听台词内容（建议短句） |
| `voice_id` | string | 是 | - | 音色唯一标识，例如 `"google:en-US-Neural2-J"` 或 `"elevenlabs:pNInz6obpgDQGcFmaJgB"` |
| `pacing` | float | 否 | `1.0` | 语速倍率（范围 0.25 - 4.0） |
| `emotion` | string | 否 | `"neutral"` | 情绪类型（如 happy, angry, sad, whispering 等） |

#### 响应

- **Content-Type**: `audio/mpeg`
- **Body**: 二进制音频流（MP3 格式）。

---

### 4.3 GET `/health` (服务健康与密钥检查)

用于负载均衡健康探针与配置状态诊断。

- **URL**: `/health`
- **Method**: `GET`
- **鉴权要求**: 无

#### 响应体 (Response - JSON)

```json
{
  "status": "healthy",
  "openrouter_configured": false,
  "elevenlabs_configured": true
}
```

---

### 4.4 GET `/` (基础运行状态)

- **URL**: `/`
- **Method**: `GET`
- **响应体**:
  ```json
  {
    "service": "DramaFlow API",
    "status": "running",
    "version": "1.0.0"
  }
  ```
