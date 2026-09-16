# DramaFlow API 接口文档

DramaFlow API 接收结构化剧本，完成音色准备、TTS 合成、音频后期、字幕生成和 Cloudflare R2 文件管理。

本地 Base URL：

```text
http://localhost:8000
```

交互式文档：

```text
GET /docs
GET /openapi.json
```

## 1. 通用约定

### 1.1 鉴权

除 `GET /` 和 `GET /health` 外，所有接口都需要：

```http
X-Access-Secret: <DARMAFLOW_API_ACCESS_SECRET>
```

鉴权结果：

| 状态码 | 含义 |
| --- | --- |
| `401` | 服务端已配置密钥，但请求未提供 `X-Access-Secret` |
| `403` | 请求密钥不正确 |
| `503` | 生产环境未配置有效的服务端访问密钥 |

非生产环境允许不配置访问密钥。生产环境设置 `ENVIRONMENT=production` 后会采用安全失败策略。

### 1.2 公共 Header

| Header | 是否必需 | 说明 |
| --- | --- | --- |
| `X-Access-Secret` | 受保护接口必需 | 共享 API 访问密钥 |
| `X-User-Tier` | 否 | `free` 或 `vip`，默认 `free` |
| `X-ElevenLabs-API-Key` | 否 | 仅 `/synthesize` 和 `/review` 使用，可覆盖服务端 ElevenLabs Key |
| `X-Request-ID` | 否 | UUID4 请求 ID；缺失或无效时由中间件生成 |

`X-User-Tier` 应由可信网关或服务端调用方设置。它直接影响自动音色路由和供应商成本。

### 1.3 剧本片段模型

`/assign_voices` 和 `/synthesize` 使用同一套严格模型：

```json
{
  "type": "dialogue",
  "text": "Did you hear that?",
  "character": "Alice",
  "gender": "female",
  "emotion": "fearful",
  "pacing": 1.1,
  "voice_id": "google:en-US-Neural2-F"
}
```

| 字段 | 类型 | 必需 | 约束 |
| --- | --- | --- | --- |
| `type` | string | 是 | `narration` 或 `dialogue` |
| `text` | string | 是 | 去除首尾空白后长度为 1～5000 |
| `character` | string | 是 | 长度为 1～100；旁白准备后统一为 `Narrator` |
| `gender` | string | 是 | `male`、`female`、`neutral` |
| `emotion` | string | 否 | 默认 `neutral`；支持 8 种情绪 |
| `pacing` | number | 否 | 默认 `1.0`，范围 `0.25`～`4.0` |
| `voice_id` | string | 否 | 默认空字符串；最大 128 字符 |
| `provider` | string/null | 否 | 仅用于兼容旧客户端的原始 voice ID |

支持的情绪：

```text
neutral, happy, sad, angry, fearful, surprised, whispering, shouting
```

推荐始终使用命名空间音色：

```text
google:en-US-Neural2-F
azure:zh-CN-YunxiNeural
openai:onyx
elevenlabs:pNInz6obpgDQGcFmaJgB
```

旧客户端仍可传原始 ID，后端会通过 `provider` 或 ID 特征推断供应商；新客户端不应依赖该推断。

### 1.4 通用错误

请求模型校验失败时返回 FastAPI 标准 `422`。业务内部错误使用稳定结构，不会暴露供应商响应、堆栈、凭证或本地路径：

```json
{
  "detail": {
    "code": "synthesis_failed",
    "message": "The request could not be completed",
    "request_id": "4b36c90c..."
  }
}
```

常见状态码：

| 状态码 | 场景 |
| --- | --- |
| `400` | R2 URL、文件组合或生命周期状态不合法 |
| `401` / `403` | 访问密钥缺失或错误 |
| `422` | 请求字段不合法、音色无法解析或旁白音色冲突 |
| `503` | 鉴权未配置或实际需要的 TTS 供应商未配置 |
| `500` | TTS、后期、上传或其他内部错误 |

## 2. 系统接口

### 2.1 `GET /`

无需鉴权。返回服务元数据：

```json
{
  "service": "DramaFlow API",
  "status": "running",
  "version": "1.0.0"
}
```

### 2.2 `GET /health`

无需鉴权。用于 Railway 或负载均衡器的存活探针：

```json
{
  "status": "healthy",
  "openrouter_configured": false,
  "elevenlabs_configured": true
}
```

该接口只表示应用进程能够响应，并展示两个兼容性配置标志；它不会主动连接 TTS 供应商、ffmpeg 或 R2。

## 3. 音色接口

### 3.1 `GET /voices`

返回前端可展示的 Basic/Advance 音色、情绪参数和试听样例。

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `languages` | string[] | 可重复传入；支持 `en`、`zh` 及 `en-US`、`zh-CN`、`zh-TW`、`cn` 等别名 |

未传入时默认返回英文音色：

```http
GET /voices?languages=en&languages=zh
```

响应结构：

```json
{
  "voice_map": {
    "Basic": {
      "en": {
        "male": {
          "id": "google:en-US-Neural2-J",
          "name": "Michael (Energetic)",
          "avatar_url": "r2.fictalk.com/voice-avatars/en-US-Neural2-J.jpeg"
        },
        "female": {
          "id": "google:en-US-Neural2-F",
          "name": "Jennifer (Warm)",
          "avatar_url": "r2.fictalk.com/voice-avatars/en-US-Neural2-F.png"
        }
      },
      "pool": {}
    },
    "Advance": {
      "male": {
        "id": "elevenlabs:pNInz6obpgDQGcFmaJgB",
        "name": "Adam (Deep)",
        "avatar_url": "r2.fictalk.com/voice-avatars/pNInz6obpgDQGcFmaJgB.png"
      },
      "pool": {}
    }
  },
  "emotion_settings": {
    "neutral": {
      "stability": 0.6,
      "similarity_boost": 0.75,
      "style": 0.0
    }
  },
  "samples": {
    "openai": {
      "onyx": "https://cdn.openai.com/API/docs/audio/onyx.wav"
    }
  }
}
```

### 3.2 `POST /assign_voices`

在不生成音频的情况下，为空 `voice_id` 自动分配音色。常用于前端 Magic Fill。

```http
POST /assign_voices?languages=en&languages=zh
X-Access-Secret: ...
X-User-Tier: free
Content-Type: application/json
```

请求：

```json
{
  "script": [
    {
      "type": "narration",
      "text": "清晨的微风穿过树林。",
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

响应示例中的具体音色取决于用户等级、供应商配置和音色池：

```json
{
  "message": "Voices assigned successfully",
  "script": [
    {
      "type": "narration",
      "text": "清晨的微风穿过树林。",
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

行为说明：

- 所有旁白共用一个声音，并统一为 `character=Narrator`、`gender=neutral`。
- 一个旁白片段提供手动 `voice_id` 时，该声音传播到全部旁白。
- 多个旁白片段提供不同手动声音时返回 `422`。
- 对白的手动 `voice_id` 会被保留。
- 同名对白角色通过确定性哈希获得稳定声音。

### 3.3 `POST /review`

生成一条短试听并直接返回 MP3 文件流。

请求：

```json
{
  "text": "Hello, this is a preview.",
  "voice_id": "google:en-US-Neural2-J",
  "pacing": 1.0,
  "emotion": "neutral"
}
```

限制：

- `text` 接受 1～100 字符，实际只合成前 30 个字符。
- `voice_id` 必须能够解析到受支持的供应商。
- `pacing` 范围为 `0.25`～`4.0`。
- 引用了未配置的供应商时返回 `503 tts_provider_not_configured`。

成功响应：

```http
Content-Type: audio/mpeg
Content-Disposition: attachment; filename="preview.mp3"
```

## 4. 合成接口

### 4.1 `POST /synthesize`

合成完整有声剧。该接口会先自动准备剧本，因此不要求调用方提前调用 `/assign_voices`。

请求：

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
      "voice_id": ""
    },
    {
      "type": "dialogue",
      "text": "Did you hear that?",
      "character": "David",
      "gender": "male",
      "emotion": "fearful",
      "pacing": 1.1,
      "voice_id": "google:en-US-Neural2-J"
    }
  ],
  "limit": null
}
```

顶层字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `script` | array | 是 | 1～1000 个严格校验的剧本片段 |
| `limit` | integer/null | 否 | `null` 合成全部，正整数合成前 N 段，`0` 只做跳过响应 |

处理规则：

1. 截取 `limit` 指定的片段。
2. 补齐空音色，并保证旁白全剧一致。
3. 根据最终 `voice_id` 计算实际需要的供应商。
4. 只检查这些供应商的凭证；纯 Google 请求不需要 ElevenLabs Key。
5. 并发生成旁白和对白；对白并发上限为 3。
6. 按原剧本顺序拼接，每段之间插入 300ms 静音。
7. 输出 192kbps MP3、SRT 和 `timeline`。
8. 将 MP3/SRT 上传至 R2 的 `temp` 目录。

响应：

```json
{
  "message": "Synthesis successful",
  "segments_count": 2,
  "audio_duration_ms": null,
  "audio_url": "https://cdn.example.com/projects/DramaFlow/temp/3a4b9c1d.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/temp/3a4b9c1d.srt",
  "timeline": [
    {"index": 1, "start": 0, "end": 3200},
    {"index": 2, "start": 3500, "end": 5800}
  ]
}
```

`audio_duration_ms` 当前为保留字段，尚未填充。音频总时长可以从最后一个 timeline 项的 `end` 推导。

`limit=0` 时仍会校验请求模型，但不会检查供应商凭证、调用 TTS、执行后期或访问 R2：

```json
{
  "message": "Synthesis skipped (limit=0)",
  "segments_count": 0,
  "audio_duration_ms": null,
  "audio_url": null,
  "srt_url": null,
  "timeline": null
}
```

## 5. R2 文件生命周期

所有文件接口只接受 `R2_PUBLIC_DOMAIN` 下的规范 URL：

```text
projects/{project_id}/{temp|saved}/{filename}.{mp3|srt}
```

以下 URL 会在访问 R2 前被拒绝：

- 外部域名或不同协议。
- 包含用户名、密码、查询参数或 URL fragment。
- URL 编码路径、反斜线或非规范路径。
- `temp` / `saved` 以外的目录。
- MP3/SRT 扩展名错误。
- 音频和字幕来自不同项目或不同目录。

### 5.1 `POST /save_files`

将文件保存到 `saved`：

- 来源为 `temp`：分别复制到新的 `saved` UUID，然后删除临时源文件。
- 来源为 `saved`：幂等返回原 URL，不创建副本。

请求：

```json
{
  "audio_url": "https://cdn.example.com/projects/DramaFlow/temp/source.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/temp/source.srt"
}
```

响应：

```json
{
  "audio_url": "https://cdn.example.com/projects/DramaFlow/saved/audio-uuid.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/saved/srt-uuid.srt"
}
```

### 5.2 `POST /move_files_to_temp`

将一对 `saved` 文件分别移动到新的 `temp` UUID，并删除原文件。

```json
{
  "audio_url": "https://cdn.example.com/projects/DramaFlow/saved/audio-id.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/saved/srt-id.srt"
}
```

响应：

```json
{
  "audio_url": "https://cdn.example.com/projects/DramaFlow/temp/new-audio-id.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/temp/new-srt-id.srt"
}
```

### 5.3 `POST /del_files`

永久删除音频、字幕或两者。至少提供一个 URL。

```json
{
  "audio_url": "https://cdn.example.com/projects/DramaFlow/temp/source.mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlow/temp/source.srt"
}
```

响应：

```json
{
  "message": "Files deletion processed",
  "details": {
    "audio": true,
    "srt": true
  }
}
```

## 6. curl 示例

设置地址和访问密钥：

```bash
export DRAMAFLOW_URL="http://localhost:8000"
export DRAMAFLOW_SECRET="replace-with-your-secret"
```

查询音色：

```bash
curl "$DRAMAFLOW_URL/voices?languages=en" \
  -H "X-Access-Secret: $DRAMAFLOW_SECRET"
```

验证合成路由但不调用外部服务：

```bash
curl -X POST "$DRAMAFLOW_URL/synthesize" \
  -H "Content-Type: application/json" \
  -H "X-Access-Secret: $DRAMAFLOW_SECRET" \
  -d '{
    "script": [{
      "type": "narration",
      "text": "A quiet night.",
      "character": "Narrator",
      "gender": "neutral",
      "emotion": "neutral",
      "pacing": 1.0,
      "voice_id": ""
    }],
    "limit": 0
  }'
```
