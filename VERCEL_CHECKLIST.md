# ✅ Vercel 部署检查清单

## 📋 部署前检查

### 1. 文件结构 ✅

```
backend/
├── api/
│   └── index.py              ✅ Vercel 入口文件
├── app/
│   ├── __init__.py
│   ├── main.py               ✅ FastAPI 应用
│   └── services/
│       ├── __init__.py
│       ├── analyzer.py       ✅ AI 分析服务
│       ├── audio_engine.py   ✅ 音频生成服务
│       └── post_production.py ✅ 后期处理服务
├── requirements.txt          ✅ 依赖（带环境标记）
├── runtime.txt               ✅ Python 3.12
├── vercel.json               ✅ Vercel 配置
└── .vercelignore             ✅ 忽略文件
```

### 2. 依赖配置 ✅

**requirements.txt**:
```python
fastapi
uvicorn[standard]
python-dotenv
httpx
edge-tts
elevenlabs
pydub
dirtyjson
audioop-lts; python_version >= "3.13"  # ✅ 环境标记
```

**验证结果**:
- ✅ Python 3.13 (本地): audioop-lts 已安装
- ✅ Python 3.12 (Vercel): audioop-lts 会被跳过
- ✅ pydub 在两种环境都正常工作

### 3. Vercel 配置 ✅

**vercel.json**:
```json
{
  "version": 2,
  "builds": [{"src": "api/index.py", "use": "@vercel/python"}],
  "routes": [{"src": "/(.*)", "dest": "api/index.py"}],
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key",
    "ELEVENLABS_API_KEY": "@elevenlabs_api_key"
  },
  "functions": {
    "api/index.py": {
      "maxDuration": 300  // ✅ 5 分钟超时
    }
  }
}
```

### 4. 环境变量 ⚠️ 需要配置

在 Vercel Dashboard 中添加：

| 变量名 | 值 | 状态 |
|--------|-----|------|
| `OPENROUTER_API_KEY` | `sk-or-v1-xxxxx` | ⚠️ 待配置 |
| `ELEVENLABS_API_KEY` | `sk_xxxxx` | ⚠️ 待配置 |

**配置步骤**:
1. 访问 [Vercel Dashboard](https://vercel.com/dashboard)
2. 选择项目 → Settings → Environment Variables
3. 添加上述两个变量
4. 选择环境: Production, Preview, Development

---

## 🚀 部署步骤

### 方法 1: Git 自动部署（推荐）

```bash
# 1. 确保所有文件已提交
git add .
git commit -m "feat: Add Vercel deployment configuration"

# 2. 推送到 GitHub
git push origin main

# 3. 在 Vercel 导入项目
# 访问 https://vercel.com/new
# 选择 GitHub 仓库
# Root Directory: backend
# 点击 Deploy
```

### 方法 2: Vercel CLI

```bash
# 1. 安装 Vercel CLI
npm install -g vercel

# 2. 登录
vercel login

# 3. 部署
cd backend
vercel --prod

# 按提示配置环境变量
```

---

## 🧪 部署后验证

### 1. 健康检查

```bash
curl https://your-app.vercel.app/
```

**预期响应**:
```json
{
  "status": "healthy",
  "service": "DramaFlow API",
  "version": "1.0.0"
}
```

### 2. 测试音频生成（短文本）

```bash
curl -X POST https://your-app.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"老人站在山顶。"}' \
  -o test.zip
```

**预期**:
- ✅ 返回 ZIP 文件
- ✅ 包含 `drama.mp3` 和 `drama.srt`

### 3. 检查构建日志

```bash
vercel logs
```

**应该看到**:
```
✅ Installing dependencies from requirements.txt
✅ audioop-lts skipped (python_version < 3.13)
✅ pydub successfully installed
✅ Build completed
```

---

## 🔍 常见问题排查

### 问题 1: 依赖安装失败

**症状**:
```
ERROR: Could not find a version that satisfies the requirement audioop-lts
```

**检查**:
- ✅ requirements.txt 是否有环境标记: `audioop-lts; python_version >= "3.13"`
- ✅ runtime.txt 是否指定 `python-3.12`

**解决**: 已修复 ✅

---

### 问题 2: 500 Internal Server Error

**检查**:
1. Vercel 日志: `vercel logs`
2. 环境变量是否配置
3. API Keys 是否有效

**常见原因**:
- ❌ 环境变量未配置
- ❌ API Key 无效或过期
- ❌ API 配额用尽

---

### 问题 3: 请求超时

**症状**:
```
Function execution timed out
```

**检查**:
- ✅ vercel.json 的 `maxDuration` 是否设置
- ⚠️ 文本是否太长（建议 < 1000 字）

**解决**:
- 已设置 `maxDuration: 300` (5 分钟) ✅
- 如需更长时间，需要 Pro Plan

---

### 问题 4: CORS 错误

**症状**:
```
Access to fetch at 'https://...' from origin '...' has been blocked by CORS
```

**检查**:
- ✅ app/main.py 的 CORS 配置

**当前配置**: ✅ 允许所有来源
```python
allow_origins=["*"]
```

**生产环境建议**:
```python
allow_origins=[
    "https://your-frontend.vercel.app",
    "http://localhost:3000"  # 开发环境
]
```

---

## 📊 性能监控

### Vercel Analytics

```bash
# 启用 Analytics
vercel analytics

# 查看性能数据
# Dashboard → Analytics
```

### 关键指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 冷启动时间 | < 5s | 待测试 |
| 平均响应时间 | < 30s | 待测试 |
| 成功率 | > 95% | 待测试 |
| 并发请求 | 根据套餐 | 待测试 |

---

## 🎯 优化建议

### 1. 缓存策略

```python
# 在 main.py 添加缓存头
return FileResponse(
    path=zip_path,
    headers={
        "Cache-Control": "public, max-age=3600",
        "X-Package-Contents": "drama.mp3,drama.srt"
    }
)
```

### 2. 错误处理

```python
# 添加更详细的错误日志
import logging
logging.basicConfig(level=logging.INFO)
```

### 3. 请求限制

```python
# 限制文本长度
if len(request.text) > 5000:
    raise HTTPException(
        status_code=400,
        detail="Text too long. Maximum 5000 characters."
    )
```

---

## 📚 相关文档

- [VERCEL_DEPLOYMENT.md](./VERCEL_DEPLOYMENT.md) - 完整部署指南
- [DEPLOYMENT_FIX_SUMMARY.md](./DEPLOYMENT_FIX_SUMMARY.md) - Bug 修复详情
- [PROJECT_STATUS.md](./PROJECT_STATUS.md) - 项目状态
- [QUICKSTART.md](./QUICKSTART.md) - 快速开始

---

## ✅ 最终检查清单

部署前确认：

- [x] ✅ requirements.txt 包含环境标记
- [x] ✅ runtime.txt 指定 Python 3.12
- [x] ✅ vercel.json 配置正确
- [x] ✅ api/index.py 入口文件存在
- [x] ✅ .vercelignore 配置正确
- [ ] ⚠️ 环境变量已在 Vercel 配置
- [x] ✅ 本地测试通过
- [x] ✅ 依赖验证通过
- [ ] ⚠️ 代码已推送到 Git 仓库

---

## 🎉 准备就绪！

所有技术准备工作已完成！

**下一步**:
1. 配置 Vercel 环境变量
2. 推送代码到 GitHub
3. 在 Vercel 导入项目
4. 部署并测试

**预期结果**:
- ✅ 构建成功
- ✅ 部署成功
- ✅ API 正常响应
- ✅ 音频生成功能正常

---

*祝部署顺利！* 🚀✨


