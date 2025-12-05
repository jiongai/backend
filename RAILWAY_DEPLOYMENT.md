# 🚂 Railway 部署指南

## 为什么选择 Railway？

Railway 比 Vercel 更适合这个音频处理项目：

| 特性 | Railway | Vercel |
|------|---------|--------|
| 执行时间 | ✅ 无限制 | ❌ 10秒限制 |
| ffmpeg | ✅ 自动安装 | ❌ 需要手动配置 |
| 冷启动 | ✅ 无（持久运行） | ❌ 有 |
| 适合音频处理 | ✅ 完美 | ❌ 不适合 |

---

## 📦 部署步骤

### 1. 准备 GitHub 仓库

确保代码已推送到 GitHub：

```bash
git add .
git commit -m "Add Railway deployment config"
git push origin main
```

### 2. 在 Railway 上创建项目

1. 访问 [railway.app](https://railway.app)
2. 点击 **"New Project"**
3. 选择 **"Deploy from GitHub repo"**
4. 授权 Railway 访问你的 GitHub
5. 选择 `AudioDrama/backend` 仓库

### 3. 配置环境变量

在 Railway 项目设置中添加：

```
OPENROUTER_API_KEY=sk-or-v1-xxxxx
ELEVENLABS_API_KEY=sk_xxxxx
```

**位置**：
- 进入项目 → 点击服务 → Settings → Variables

### 4. 部署配置

Railway 会自动检测到 `nixpacks.toml` 和 `railway.toml`：

- ✅ 自动安装 Python 3.12
- ✅ 自动安装 ffmpeg
- ✅ 自动安装 Python 依赖
- ✅ 自动启动 FastAPI 服务

### 5. 等待部署完成

部署通常需要 3-5 分钟：

1. 安装系统包（Python、ffmpeg）
2. 安装 Python 依赖
3. 启动服务

### 6. 获取部署 URL

部署完成后：

1. 进入项目 → Settings → Networking
2. 点击 **"Generate Domain"**
3. 获取类似 `https://your-project.up.railway.app` 的 URL

---

## 🧪 测试部署

### 1. 健康检查

```bash
curl https://your-project.up.railway.app/health
```

**期望输出**：
```json
{"status": "healthy"}
```

### 2. 生成音频剧

```bash
curl -X POST https://your-project.up.railway.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"老人站在山顶，望着远方的云海。"}' \
  -o test.zip
```

### 3. 检查结果

```bash
unzip -l test.zip
# 应该看到：
# drama.mp3
# drama.srt
```

---

## 📊 监控和日志

### 查看实时日志

1. 进入 Railway 项目
2. 点击你的服务
3. 选择 **"Deployments"** 标签
4. 点击最新的部署
5. 查看 **"Logs"** 部分

### 常见日志输出

**正常启动**：
```
✅ [main] Running locally, using system ffmpeg
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**音频处理**：
```
Analyzing text (XX characters)...
Generated script with X segments
Generating audio for segments...
🔍 Loading audio file: /tmp/...
✅ Loaded audio file: duration=XXXms
✅ Exported final audio successfully
```

---

## ⚙️ Railway 配置文件说明

### `railway.toml`

```toml
[build]
builder = "NIXPACKS"  # 使用 Nixpacks 构建系统

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "ON_FAILURE"  # 失败时自动重启
restartPolicyMaxRetries = 10
```

### `nixpacks.toml`

```toml
[phases.setup]
nixPkgs = ["python312", "ffmpeg"]  # 自动安装系统包

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

### `Procfile`（备用）

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## 🔧 故障排除

### 1. 部署失败

**检查日志**：
- Railway Dashboard → Deployments → 最新部署 → Logs

**常见问题**：
- ❌ 环境变量未设置
- ❌ requirements.txt 缺少依赖
- ❌ Python 版本不匹配

### 2. ffmpeg 未找到

Railway 应该会自动安装 ffmpeg（在 `nixpacks.toml` 中配置）。

**验证**：在日志中搜索 `ffmpeg`，应该看到：
```
INFO:     Running locally, using system ffmpeg
```

### 3. API 密钥错误

**症状**：
```
401 Unauthorized
OpenRouter API key is required
```

**解决**：
1. 检查 Railway Variables 中是否有 `OPENROUTER_API_KEY` 和 `ELEVENLABS_API_KEY`
2. 重新部署（修改环境变量后需要重新部署）

### 4. 超时错误

Railway 没有执行时间限制，但要注意：
- ElevenLabs 免费版有 API 速率限制
- 长文本可能需要较长时间处理

---

## 💡 优化建议

### 1. 启用健康检查

Railway 会定期检查 `/health` 端点：

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### 2. 设置环境变量

在 Railway Variables 中添加：

```
ENVIRONMENT=production
LOG_LEVEL=info
```

### 3. 监控资源使用

在 Railway Dashboard 中查看：
- CPU 使用率
- 内存使用率
- 网络流量

---

## 🆚 Railway vs Vercel 对比

| 功能 | Railway | Vercel |
|------|---------|--------|
| **执行时间** | ✅ 无限制 | ❌ 10秒 (Hobby) |
| **系统依赖** | ✅ 原生支持 | ❌ 需手动配置 |
| **冷启动** | ✅ 无 | ❌ 有 |
| **定价** | 💰 $5/月起 | 🆓 免费 Hobby 计划 |
| **适合场景** | 🎵 音频处理 | 🌐 静态网站/轻量 API |

---

## 📚 相关链接

- [Railway 文档](https://docs.railway.app)
- [Nixpacks 文档](https://nixpacks.com/docs)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)

---

## ✅ 检查清单

部署前确认：

- [ ] GitHub 仓库已更新
- [ ] `requirements.txt` 完整
- [ ] Railway 项目已创建
- [ ] 环境变量已配置（OPENROUTER_API_KEY, ELEVENLABS_API_KEY）
- [ ] 域名已生成
- [ ] 健康检查通过
- [ ] 音频生成测试通过

---

**部署完成后，你将拥有：**

✅ 无执行时间限制的音频处理服务  
✅ 自动安装的 ffmpeg  
✅ 持久运行的 FastAPI 应用  
✅ 实时日志和监控  

🎉 **享受你的 Railway 部署吧！**

