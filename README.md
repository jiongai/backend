# DramaFlow Backend

DramaFlow 是一个将**结构化剧本**转换为多角色有声剧的 FastAPI 后端。它负责音色分配、多云 TTS 调度、音频拼接、SRT 字幕与时间轴生成，以及 Cloudflare R2 文件生命周期管理。

> 当前服务不负责把小说原文分析成剧本；调用方需要提供由 `narration` 和 `dialogue` 片段组成的结构化 JSON。

## 核心能力

- 多供应商 TTS：Google Cloud TTS、Azure Speech、OpenAI TTS、ElevenLabs。
- 分层路由：免费对白默认使用 Google，VIP 对白默认使用 ElevenLabs；旁白根据用户等级、供应商可用性与 Azure 月度额度选择。
- 自动补齐音色：`/synthesize` 可以直接接收空 `voice_id`，后端会在合成前完成分配。
- 旁白强一致性：整份剧本只使用一个旁白声音，并统一旁白的角色名和性别字段。
- 确定性角色选角：根据角色名哈希选择声音，同一角色在相同音色池中保持一致。
- 供应商原生语速：`pacing` 范围为 `0.25`～`4.0`，只在 TTS 阶段处理，不在后期重复变速。
- 音频后期：片段间插入 300ms 静音，最终输出 192kbps MP3、SRT 和毫秒级 `timeline`。
- R2 生命周期：生成文件先进入 `temp`，随后可保存到 `saved`、移回 `temp` 或永久删除。
- 安全与可观测性：共享密钥鉴权、请求 ID、结构化日志、凭证脱敏、生产环境安全失败策略。

## 处理流程

```text
结构化剧本
    ↓
校验片段字段并补齐 voice_id
    ↓
按 voice_id 检查实际需要的供应商凭证
    ↓
并发生成旁白和对白 MP3
    ↓
拼接音频 + 300ms 间隔 + SRT + timeline
    ↓
上传到 Cloudflare R2 的 temp 目录
    ↓
返回 audio_url、srt_url 和 timeline
```

## 快速开始

### 1. 准备环境

建议使用 Python 3.12，并确保系统已安装 ffmpeg。

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

macOS 可通过 `brew install ffmpeg` 安装 ffmpeg。Railway 部署会根据 `nixpacks.toml` 自动安装 Python 3.12 和 ffmpeg。

### 2. 配置环境变量

```bash
cp env.template .env
```

本地开发至少需要配置准备使用的 TTS 供应商。完整合成还需要配置 Cloudflare R2：

```dotenv
ENVIRONMENT=development
PORT=8000
DARMAFLOW_API_ACCESS_SECRET=replace-with-a-random-secret
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# 至少配置实际使用的 TTS 供应商
GOOGLE_APPLICATION_CREDENTIALS_JSON={...}
# AZURE_SPEECH_KEY=...
# AZURE_SPEECH_REGION=eastus
# OPENAI_API_KEY=...
# ELEVENLABS_API_KEY=...

R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=dramaflow
R2_PUBLIC_DOMAIN=https://cdn.example.com
R2_PROJECT_ID=DramaFlowProduction
```

生产环境必须设置：

```dotenv
ENVIRONMENT=production
DARMAFLOW_API_ACCESS_SECRET=<strong-random-secret>
CORS_ALLOWED_ORIGINS=https://app.example.com
LOG_FORMAT=json
LOG_LEVEL=INFO
```

生产环境缺少有效访问密钥时，受保护接口返回 `503 authentication_not_configured`，不会自动开放访问。

### 3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

也可以运行：

```bash
./run.sh
```

启动后可访问：

- Swagger UI：`http://localhost:8000/docs`
- OpenAPI JSON：`http://localhost:8000/openapi.json`
- 健康检查：`http://localhost:8000/health`

### 4. 运行测试

```bash
python -m unittest discover -v
```

单元测试使用临时文件和 mock 客户端，不会调用真实 TTS 或 R2 服务。目前覆盖请求校验、旁白一致性、供应商凭证检查、原生语速、MP3 格式、时间轴、鉴权、日志脱敏和存储 URL 安全等行为。

`test_api.py` 是针对已启动服务的连通性脚本，其中 `/review` 会调用真实 TTS；使用前请确认凭证和调用成本。

## API 概览

除 `/` 和 `/health` 外，所有业务接口都需要 `X-Access-Secret`。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/` | 服务元数据 |
| `GET` | `/health` | 进程存活与部分配置状态 |
| `GET` | `/voices` | 获取音色目录、情绪参数和试听样例 |
| `POST` | `/assign_voices` | 预先为剧本分配音色，供前端展示和修改 |
| `POST` | `/synthesize` | 自动准备剧本、生成 MP3/SRT 并上传 R2 |
| `POST` | `/review` | 返回单句 MP3 试听流 |
| `POST` | `/save_files` | 将 `temp` 文件移动到 `saved` |
| `POST` | `/move_files_to_temp` | 将 `saved` 文件移回 `temp` |
| `POST` | `/del_files` | 永久删除一个或一对文件 |

详细请求结构、状态码和示例见 [API_DOCS.md](API_DOCS.md)。Railway 上线说明见 [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)。

## TTS 路由规则

| 内容 | `free` | `vip` |
| --- | --- | --- |
| 对白 | Google | ElevenLabs |
| 旁白 | Azure（已配置且额度允许）→ Google → OpenAI | OpenAI → Azure → Google |

显式提供的 `voice_id` 优先于自动路由。请求只检查最终剧本实际引用的供应商，因此纯 Google 请求不需要 ElevenLabs Key。

`X-User-Tier` 当前是受信任的调用方 Header。生产环境应由后端网关或可信服务设置，不应允许普通客户端任意伪造。

## 剧本片段约束

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

- `type`：`narration` 或 `dialogue`。
- `text`：1～5000 字符。
- `character`：1～100 字符；旁白在准备阶段统一为 `Narrator`。
- `gender`：`male`、`female` 或 `neutral`。
- `emotion`：`neutral`、`happy`、`sad`、`angry`、`fearful`、`surprised`、`whispering`、`shouting`。
- `pacing`：`0.25`～`4.0`。
- `voice_id`：推荐使用 `provider:voice` 格式；空字符串表示自动分配。

每个请求最多包含 1000 个片段。若旁白片段提供多个不同的手动声音，接口返回 422。

## 项目结构

```text
app/
├── main.py                  # 应用工厂、中间件和路由装配
├── api/
│   ├── dependencies.py      # 鉴权与语言规范化
│   ├── errors.py            # 稳定错误响应
│   ├── schemas.py           # API 请求/响应模型
│   └── routes/              # system、voices、synthesis、storage
├── models/script.py         # 严格的剧本片段模型
├── core/
│   ├── settings.py          # 集中式环境配置
│   ├── runtime.py           # ffmpeg 初始化
│   └── logging.py           # 结构化日志与脱敏
├── config/
│   ├── voices.json          # 音色池、标签、情绪参数
│   └── avatar_map.json      # 音色头像映射
└── services/
    ├── audio_engine.py      # 音色分配、供应商路由和凭证检查
    ├── synthesizer.py       # 合成流水线编排
    ├── post_production.py   # 拼接、MP3、SRT、timeline
    ├── storage.py           # R2 URL 校验和文件生命周期
    └── tts/                 # 四个 TTS 供应商适配器与注册表
```

## 音色扩展

编辑 [app/config/voices.json](app/config/voices.json) 可以扩展音色池、展示名称和 ElevenLabs 情绪参数；编辑 [app/config/avatar_map.json](app/config/avatar_map.json) 可以绑定头像。更多说明见 [VOICES.md](VOICES.md) 和 [VOICE_FLOW.txt](VOICE_FLOW.txt)。

## 当前边界

- 不包含小说原文分析或自动生成结构化剧本的接口。
- `/health` 是存活探针，不会主动连接所有外部供应商或 R2。
- 合成是同步 HTTP 请求；长剧本应由调用方设置合理超时。
- `audio_duration_ms` 当前保留在响应模型中，但尚未填充。
