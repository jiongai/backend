# DramaFlow Backend 🎭

AI 驱动的沉浸式多角色有声剧（AI Audio Drama）全自动生产、后期混音与字幕生成后端微服务。

---

## 🌟 核心特性

- 🎙️ **多云混合 TTS 智能路由 (Hybrid TTS Routing)**：
  - **Basic (免费/标准)**：采用 **Google Cloud TTS**（丰富角色音色池）与 **Azure Speech**（月度 50 万字符配额监控与自动降级保障）。
  - **Advance (VIP/高保真)**：采用 **ElevenLabs**（拟真音色 + 细粒度情感参数动态注入）与 **OpenAI TTS**（高质感旁白）。
- 🎭 **确定性角色音色绑定 (Deterministic Voice Mapping)**：
  - 基于角色名哈希映射算法，确保同一角色在全剧任意章节的音色严格一致，避免配音跳戏。
- 📖 **旁白强一致性与语种自适应 (Narrator Invariance)**：
  - 自动检测剧本文本语言（中文/英文），独立锁定旁白声音，彻底剥离上下文角色性别属性对旁白音色的干扰。
- 🎛️ **广播剧级数字音频后期 (Post-Production Engine)**：
  - **停顿控制**：自动在对话与旁白片段间插入 300ms 黄金戏剧静音间隙（`silence_gap`）。
  - **语速调节**：支持 0.25x - 4.0x 变速率不失真采样处理（`pacing`）。
  - **高保真输出**：统一输出 192kbps 广播级 MP3 音轨。
- 📝 **毫秒级精确对齐字幕 (Synchronized SRT & Timeline)**：
  - 合成过程中实时计算每一句台词的精确起止时间戳，同步产出标准 `.srt` 字幕文件与前端高亮播放所需的 `timeline` 时间轴索引。
- ☁️ **云端对象存储与生命周期管理 (Storage & Lifecycle Engine)**：
  - 原生集成 **Cloudflare R2**（S3 兼容协议），实现 `temp`（临时预览）与 `saved`（正式归档）状态隔离流转，采用 Copy-on-Write 重新分发 UUID 防并发污染。
- 🛡️ **生产级可观测性与安全防御**：
  - 集成 `CorrelationIdMiddleware` + `structlog` 全链路请求追踪，支持 `X-Access-Secret` 访问安全鉴权与 Serverless / 容器化环境下的 ffmpeg 自动探测。

---

## 🚀 快速开始

### 1. 环境准备与虚拟环境

```bash
# 克隆仓库
cd DramaFlow

# 创建 Python 3.10+ 虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS / Linux
# 或 Windows: venv\Scripts\activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> **环境说明**：系统依赖 `ffmpeg` 进行音频合成与格式转换。请确保运行环境中已安装 ffmpeg（如 macOS 执行 `brew install ffmpeg`，Ubuntu 执行 `apt-get install ffmpeg`）。对于 Railway/Lambda 部署，系统已内置路径探测。

### 3. 配置环境变量

从模版复制配置文件并填入相应 API Key：

```bash
cp env.template .env
```

核心配置项包括：
- `DARMAFLOW_API_ACCESS_SECRET`：API 访问访问鉴权密钥
- `ELEVENLABS_API_KEY`：ElevenLabs 语音合成密钥
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` 或 `GOOGLE_APPLICATION_CREDENTIALS`：Google TTS 服务账号凭证
- `AZURE_SPEECH_KEY` 与 `AZURE_SPEECH_REGION`：Azure 语音服务
- `OPENAI_API_KEY`：OpenAI 语音服务
- `R2_*`：Cloudflare R2 存储桶连接参数

### 4. 启动服务

```bash
# 本地开发模式（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用启动脚本
./run.sh
```

服务就绪后，可在浏览器访问：`http://localhost:8000/docs` 查看交互式 Swagger API 文档。

---

## 📡 核心 API 端点概览

详细请求参数与返回结构请参考 [API_DOCS.md](file:///Users/baojiong/My%20Projects/AIAudioDrarm/DramaFlow/API_DOCS.md)。

| 方法 | 路径 | 描述 | 鉴权要求 |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | 服务健康检查与 API Key 就绪状态 | 无 |
| `GET` | `/voices` | 获取当前支持的全部声音目录、情感参数与试听样本（支持语言过滤） | `X-Access-Secret` |
| `POST` | `/assign_voices` | 根据角色名与语种自动为结构化剧本分配声音 ID（前端 Magic Fill） | `X-Access-Secret` |
| `POST` | `/synthesize` | **核心**：根据剧本结构并发合成音频剧，输出 MP3/SRT 并上传 R2 | `X-Access-Secret` |
| `POST` | `/review` | 单条台词声音试听与参数预览（返回实时 MP3 音频流） | `X-Access-Secret` |
| `POST` | `/save_files` | 将生成的文件从 `temp` 正式保存/移动至 `saved` 归档目录 | `X-Access-Secret` |
| `POST` | `/move_files_to_temp` | 将已归档的文件移回 `temp` 临时目录（重新受制于过期策略） | `X-Access-Secret` |
| `POST` | `/del_files` | 从云存储中物理删除指定的音频与字幕文件 | `X-Access-Secret` |

---

## 🛠️ 项目架构

```
DramaFlow/
├── app/
│   ├── main.py                  # FastAPI 主应用、路由网关、中间件与安全鉴权
│   ├── config/
│   │   ├── voices.json          # 声音池配置、多语言映射与情感超参数字典
│   │   └── avatar_map.json      # 声音对应的头像静态映射
│   ├── core/
│   │   └── logging.py           # structlog 结构化日志配置与 Request ID 追踪
│   └── services/
│       ├── synthesizer.py       # 剧本级业务编排器（并发度控制、全阶段流水线调度）
│       ├── audio_engine.py      # TTS 路由决策、配额降级监控与哈希选角引擎
│       ├── tts_providers.py     # 多供应商抽象适配器 (Azure, Google, OpenAI, ElevenLabs)
│       ├── post_production.py   # 数字音频拼接、pacing 调控、静音缝隙与 SRT 运算
│       └── storage.py           # Cloudflare R2 对象存储生命周期与 Copy-on-Write 管理
├── env.template                 # 环境变量模板
├── requirements.txt             # 项目依赖清单
├── test_api.py                  # API 自动化回归测试套件
└── test_narrator_consistency.py # 旁白声音一致性验证脚本
```

---

## ⚙️ 进阶配置与声音扩展

若需扩展音色库、添加新语种或调整情感参数，请直接编辑 [`app/config/voices.json`](file:///Users/baojiong/My%20Projects/AIAudioDrarm/DramaFlow/app/config/voices.json)，无需改动业务代码：
- `VOICE_MAP`：维护各供应商（Google / ElevenLabs / Azure / OpenAI）的音色池与默认发音人。
- `EMOTION_SETTINGS`：配置不同情感（如 happy, angry, sad, whispering 等）的 stability、similarity_boost 和 style 参数。
- `VOICE_LABELS`：配置在前端展示的友好名称。

声音映射详情请查阅 [VOICES.md](file:///Users/baojiong/My%20Projects/AIAudioDrarm/DramaFlow/VOICES.md)。

---

## 📄 开源许可

本项目遵循 MIT 协议。
