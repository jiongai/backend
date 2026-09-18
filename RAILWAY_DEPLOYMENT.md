# Railway 部署指南

本文档说明如何把当前 DramaFlow FastAPI 服务部署到 Railway。项目已经包含：

- `railway.toml`：使用 Nixpacks 构建并启动 uvicorn。
- `nixpacks.toml`：安装 Python 3.12、pip、ffmpeg 和 util-linux。
- `.python-version`：为 Nixpacks 和 Railpack 声明 Python 3.12；平台的 Python 版本环境变量可能覆盖此文件。
- `Procfile`：备用启动声明。

当前服务接收结构化剧本并返回 R2 上的 MP3/SRT URL；不存在旧版 `/generate` 接口，也不会返回 ZIP 文件。

## 1. 部署前准备

### 1.1 外部服务

完整合成至少需要：

1. 一个可用的 TTS 供应商。
2. 一个 Cloudflare R2 Bucket。
3. R2 API Token，具备对象读取、写入和删除权限。
4. R2 公共开发域名或自定义域名，用于返回公开音频/字幕 URL。

最简单的基础部署可以只配置 Google Cloud TTS。若需要其他路由，再增加：

- Azure Speech：免费旁白优先选项。
- OpenAI：VIP 旁白或基础供应商不可用时的后备。
- ElevenLabs：VIP 对白。

### 1.2 本地验证

推送代码前建议运行：

```bash
python -m unittest discover -v
```

测试不访问真实 TTS 或 R2。另请确认本地能够启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. 创建 Railway 服务

1. 将代码推送到 GitHub。
2. 在 Railway 选择 **New Project → Deploy from GitHub repo**。
3. 选择当前后端仓库。
4. Railway 会读取 `railway.toml` 和 `nixpacks.toml`。
5. 在服务的 **Settings → Networking** 中生成 Railway 域名。

实际启动命令为：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway 自动提供 `PORT`，通常不需要手动设置。

## 3. 配置环境变量

在 Railway 服务的 **Variables** 页面添加环境变量。不要上传本地 `.env` 或 Google 凭据文件。

### 3.1 运行与安全

```dotenv
ENVIRONMENT=production
DARMAFLOW_API_ACCESS_SECRET=<strong-random-secret>
CORS_ALLOWED_ORIGINS=https://app.example.com
LOG_FORMAT=json
LOG_LEVEL=INFO
LOG_INCLUDE_STACKTRACES=false
```

说明：

- `DARMAFLOW_API_ACCESS_SECRET` 必须替换为随机强密钥，不能保留 `your_api_access_secret_here`、`changeme` 等占位值。
- 生产环境未配置有效密钥时，`/voices`、`/synthesize` 等受保护接口返回 `503 authentication_not_configured`。
- 多个 CORS 来源使用逗号分隔，不要添加多余路径：

```dotenv
CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
```

- 生产环境默认使用 JSON 日志并隐藏异常堆栈；上面的日志变量是显式推荐值。

生成随机密钥的一个示例：

```bash
openssl rand -hex 32
```

### 3.2 Google Cloud TTS

Railway 推荐直接保存完整 Service Account JSON：

```dotenv
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account","project_id":"...",...}
```

请在 Railway Variables 中粘贴完整单行 JSON。不要把 Service Account JSON 提交到 Git。

`GOOGLE_APPLICATION_CREDENTIALS=/path/to/file.json` 只适合该文件确实存在于部署容器或挂载卷时使用。

### 3.3 可选 TTS 供应商

```dotenv
# Azure Speech
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=eastus

# OpenAI TTS
OPENAI_API_KEY=...

# ElevenLabs
ELEVENLABS_API_KEY=...
```

凭证按请求最终使用的音色检查：

- 纯 Google 请求不需要 ElevenLabs Key。
- 使用 `elevenlabs:...` 音色时必须配置 ElevenLabs Key，或由可信调用方通过 `X-ElevenLabs-API-Key` 提供。
- `X-User-Tier: vip` 的自动路由通常需要 OpenAI 和 ElevenLabs。

`OPENROUTER_API_KEY` 不是当前结构化剧本合成流程的必需项。它只作为旧配置兼容字段保留，并由 `/health` 展示是否存在。

### 3.4 Cloudflare R2

```dotenv
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=dramaflow
R2_PUBLIC_DOMAIN=https://cdn.example.com
R2_PROJECT_ID=DramaFlowProduction
```

注意：

- `R2_ENDPOINT_URL` 是 S3 兼容 API 地址。
- `R2_PUBLIC_DOMAIN` 是用户访问 MP3/SRT 的 HTTP(S) 公共域名，两者不是同一个地址。
- `R2_PUBLIC_DOMAIN` 推荐填写完整的 `https://` 地址；合法的裸域名（如 `r2.fictalk.com`）会自动补为 `https://r2.fictalk.com`。末尾斜杠会自动去除，不允许包含登录凭据、查询参数或 fragment。
- `R2_PROJECT_ID` 只能使用字母、数字、点、下划线和连字符，并决定对象路径：

```text
projects/{R2_PROJECT_ID}/temp/{uuid}.mp3
projects/{R2_PROJECT_ID}/temp/{uuid}.srt
```

建议在 R2 配置生命周期规则，自动清理 `projects/{R2_PROJECT_ID}/temp/` 下的过期临时文件；`saved/` 不应使用相同的短期清理规则。

## 4. 部署配置说明

### `railway.toml`

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### `nixpacks.toml`

```toml
[phases.setup]
nixPkgs = ["python312", "python312Packages.pip", "ffmpeg", "util-linux"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Nixpacks 会根据 `requirements.txt` 识别并安装 Python 依赖。

### `Procfile`

```text
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`railway.toml` 中的 `startCommand` 是当前主要启动配置，Procfile 只作为兼容备用。

## 5. 健康检查

在 Railway 服务设置中将 Healthcheck Path 配置为：

```text
/health
```

验证：

```bash
export DRAMAFLOW_URL="https://your-service.up.railway.app"
curl "$DRAMAFLOW_URL/health"
```

期望响应：

```json
{
  "status": "healthy",
  "openrouter_configured": false,
  "elevenlabs_configured": true
}
```

`/health` 是进程存活探针，不会主动验证 Google、Azure、OpenAI、ElevenLabs、ffmpeg 或 R2 的网络连通性。

## 6. 部署后验证

### 6.1 验证鉴权和音色目录

```bash
export DRAMAFLOW_SECRET="<DARMAFLOW_API_ACCESS_SECRET>"

curl "$DRAMAFLOW_URL/voices?languages=en" \
  -H "X-Access-Secret: $DRAMAFLOW_SECRET"
```

缺少密钥应返回 401，错误密钥应返回 403。

### 6.2 无成本验证合成路由

`limit=0` 不调用 TTS、ffmpeg 或 R2，可用于检查请求模型、鉴权和路由：

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

期望响应：

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

### 6.3 完整 Google 合成验证

以下请求会产生真实 Google TTS 和 R2 调用：

```bash
curl -X POST "$DRAMAFLOW_URL/synthesize" \
  -H "Content-Type: application/json" \
  -H "X-Access-Secret: $DRAMAFLOW_SECRET" \
  -H "X-User-Tier: free" \
  -d '{
    "script": [{
      "type": "narration",
      "text": "The story begins on a quiet winter night.",
      "character": "Narrator",
      "gender": "neutral",
      "emotion": "neutral",
      "pacing": 1.0,
      "voice_id": "google:en-US-Neural2-J"
    }]
  }'
```

成功响应包含：

```json
{
  "message": "Synthesis successful",
  "segments_count": 1,
  "audio_url": "https://cdn.example.com/projects/DramaFlowProduction/temp/....mp3",
  "srt_url": "https://cdn.example.com/projects/DramaFlowProduction/temp/....srt",
  "timeline": [
    {"index": 1, "start": 0, "end": 2400}
  ]
}
```

继续验证返回的 `audio_url` 和 `srt_url` 能通过公网访问。

## 7. 日志与监控

Railway 的 **Deployments → Logs** 可以查看实时日志。生产环境默认输出 JSON，并包含请求 ID：

```json
{
  "event": "Synthesize request received",
  "request_id": "...",
  "script_segments": 2,
  "providers": ["google"],
  "level": "info"
}
```

日志处理器会对常见密钥字段和已知凭证值进行脱敏，也会限制长字符串和集合的长度。不要主动把完整请求 Header 或凭证写入自定义日志。

建议监控：

- HTTP 5xx 和 503 比例。
- TTS 供应商错误与延迟。
- 合成请求耗时。
- Railway CPU、内存和重启次数。
- R2 存储量及 `temp` 生命周期清理情况。

## 8. 故障排除

### 合成时报 `R2_PUBLIC_DOMAIN must be an absolute HTTP(S) URL`

这表示运行中的公共域名配置未通过校验。旧版代码要求包含协议，裸域名会在生成返回链接时失败；当前版本会为合法裸域名自动补上 `https://`，需部署包含此修复的代码才能生效。

推荐在 Railway 中设置 `R2_PUBLIC_DOMAIN=https://r2.fictalk.com`（替换为自己的 R2 公共域名），核对待应用变更中的新值并点击 Deploy。紫色变量表示仍有待应用修改。若仍报错，在运行容器中执行以下命令，只检查这一项实际值：

```bash
python -c 'import os; print(repr(os.environ.get("R2_PUBLIC_DOMAIN")))'
```

空值、`https:r2.fictalk.com` 等错误格式仍会被拒绝。本地 `.env` 的修改不会自动更新 Railway Variables。

### 启动时报 `No module named 'pyaudioop'`

如果日志路径包含 `python3.13`，且堆栈在 `pydub/utils.py` 的 `import pyaudioop as audioop` 处退出，原因是 Python 3.13 移除了标准库 `audioop`，而 pydub 的备用导入也不可用。这发生在应用导入阶段。

项目的 `requirements.txt` 已包含兼容依赖：

```text
audioop-lts; python_version >= "3.13"
```

Python 3.13 及以上会安装该包，Python 3.12 使用标准库模块。参考 [Python 官方说明](https://docs.python.org/3/library/audioop.html) 和 [audioop-lts 安装说明](https://pypi.org/project/audioop-lts/)。

处理步骤：

1. 将更新后的 `requirements.txt` 和 `.python-version` 推送到 Railway 关联的仓库分支，并触发包含依赖安装的重新构建；仅重启旧容器不会安装新依赖。
2. 检查构建日志中的构建器和 Python 版本。若实际使用 Railpack，`nixpacks.toml` 不控制其 Python 版本；[Railpack 会读取 `.python-version`](https://railpack.com/languages/python)。如 Variables 已设置 `RAILPACK_PYTHON_VERSION`，应改为 `3.12` 或移除覆盖值；Nixpacks 对应变量为 `NIXPACKS_PYTHON_VERSION`。
3. 在部署容器中运行 `python -c "import audioop; from pydub import AudioSegment; print('audio dependencies OK')"`，然后确认 `/health` 返回成功。

### 受保护接口返回 503

若响应为：

```json
{"detail":{"code":"authentication_not_configured"}}
```

检查：

- `ENVIRONMENT=production`。
- `DARMAFLOW_API_ACCESS_SECRET` 已设置且不是模板占位值。
- 修改 Variables 后已经重新部署。

若响应为：

```json
{
  "detail": {
    "code": "tts_provider_not_configured",
    "providers": ["google"]
  }
}
```

说明最终剧本引用了未配置的供应商。检查对应凭证，或显式换成已配置的 `voice_id`。

### ffmpeg 错误

`nixpacks.toml` 会安装 ffmpeg。正常启动日志应包含：

```text
Running locally or on Railway, using system ffmpeg
Using system ffmpeg binary
```

如果后期导出失败：

1. 确认部署实际使用 Nixpacks。
2. 检查构建日志中是否安装了 ffmpeg。
3. 在 Railway Shell 中运行 `ffmpeg -version`。

### R2 Client is not configured

检查以下变量是否全部存在：

```text
R2_ENDPOINT_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_DOMAIN
```

若返回 R2 URL 校验错误，还要确认请求 URL 的协议、域名、目录和扩展名与当前配置完全一致。

### 422 请求校验错误

常见原因：

- 剧本为空。
- 缺少 `character` 或 `gender`。
- 使用未支持的 emotion。
- `pacing` 超出 0.25～4.0。
- `voice_id` 的供应商前缀不受支持。
- 不同旁白片段指定了多个不同声音。

### 请求耗时较长

合成在一个 HTTP 请求内完成。片段越多，TTS 和后期耗时越长。建议：

- 调用端设置足够的超时。
- 使用 `limit` 先进行短片段验证。
- 关注供应商速率限制。
- 为 Railway 服务配置足够的内存和 CPU。

## 9. 上线检查清单

- [ ] 单元测试全部通过。
- [ ] Railway 使用 Python 3.12 和 ffmpeg 构建成功。
- [ ] `ENVIRONMENT=production`。
- [ ] 配置随机且非占位的 `DARMAFLOW_API_ACCESS_SECRET`。
- [ ] CORS 只包含正式前端域名。
- [ ] 日志格式为 JSON，生产环境堆栈关闭。
- [ ] 至少一个 TTS 供应商配置完成。
- [ ] R2 API Token 具备所需权限。
- [ ] R2 公共域名能够访问生成文件。
- [ ] `/health` 通过。
- [ ] `/voices` 的鉴权行为正确。
- [ ] `limit=0` 验证通过。
- [ ] 完整 MP3/SRT 合成验证通过。
- [ ] R2 `temp` 生命周期清理规则已配置。
