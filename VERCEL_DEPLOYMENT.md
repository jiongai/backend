# 🚀 Vercel 部署指南

## ✅ 已修复的问题

### 问题：`audioop-lts` 包与 Vercel Python 3.12 不兼容

**错误信息**:
```
ERROR: Could not find a version that satisfies the requirement audioop-lts
ERROR: Ignored the following versions that require a different python version: 
  0.1.0 Requires-Python >=3.13
```

**原因**:
- `audioop-lts` 包只支持 Python 3.13+
- Vercel 使用 Python 3.12
- 但 `pydub` 需要 `audioop` 模块

**解决方案**: ✅ 使用环境标记条件性安装

```python
# requirements.txt
audioop-lts; python_version >= "3.13"
```

这样：
- **Python 3.12** (Vercel): 使用内置的 `audioop` 模块 ✅
- **Python 3.13+** (本地开发): 自动安装 `audioop-lts` ✅

---

## 📁 项目结构

```
backend/
├── api/
│   └── index.py          # Vercel 入口文件
├── app/
│   ├── main.py           # FastAPI 应用
│   └── services/
│       ├── analyzer.py
│       ├── audio_engine.py
│       └── post_production.py
├── requirements.txt       # 依赖（带环境标记）
├── runtime.txt            # Python 版本
└── vercel.json            # Vercel 配置
```

---

## ⚙️ 配置文件

### 1. `vercel.json`

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key",
    "ELEVENLABS_API_KEY": "@elevenlabs_api_key"
  }
}
```

**说明**:
- `maxDuration: 300` - 音频生成可能需要较长时间（最多 5 分钟）
- `api/**/*.py` - 匹配所有 API 目录下的 Python 文件
- 环境变量使用 Vercel Secrets（需要在 Vercel 控制台配置）
- Vercel 自动检测 `api/` 目录并创建 serverless functions
- 移除了 `builds` 和 `routes`（与 `functions` 冲突）

### 2. `runtime.txt`

```
python-3.12
```

**说明**: 指定 Python 3.12（Vercel 当前支持的版本）

### 3. `api/index.py`

```python
"""
Vercel entry point for DramaFlow API
"""
import sys
from pathlib import Path

# Add the parent directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app

# Export for Vercel
app = app
```

**说明**: Vercel 需要 `api/` 目录下的入口文件

---

## 🔐 配置环境变量

### 方法 1: Vercel CLI

```bash
# 安装 Vercel CLI
npm install -g vercel

# 登录
vercel login

# 设置环境变量
vercel env add OPENROUTER_API_KEY
vercel env add ELEVENLABS_API_KEY
```

### 方法 2: Vercel 控制台

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. 选择你的项目
3. 进入 **Settings** → **Environment Variables**
4. 添加变量：
   - `OPENROUTER_API_KEY`: 你的 OpenRouter API Key
   - `ELEVENLABS_API_KEY`: 你的 ElevenLabs API Key

---

## 📦 部署步骤

### 首次部署

```bash
# 1. 初始化 Git（如果还没有）
git init
git add .
git commit -m "Initial commit for Vercel deployment"

# 2. 推送到 GitHub
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main

# 3. 连接到 Vercel
vercel

# 按提示操作：
# - 选择项目路径: ./backend
# - 链接到已有项目或创建新项目
# - 选择 Python 框架
```

### 方法 2: 通过 Vercel 控制台

1. 访问 [Vercel Import](https://vercel.com/new)
2. 导入 Git 仓库
3. 设置：
   - **Root Directory**: `backend`
   - **Framework Preset**: `Other`
4. 添加环境变量（见上方）
5. 点击 **Deploy**

---

## 🧪 部署后测试

### 1. 检查健康状态

```bash
curl https://your-project.vercel.app/
```

**预期响应**:
```json
{
  "status": "healthy",
  "service": "DramaFlow API",
  "version": "1.0.0"
}
```

### 2. 测试生成接口

```bash
curl -X POST https://your-project.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "老人站在山顶。「你是谁？」少女问道。"
  }' \
  -o test_drama.zip
```

---

## ⚠️ 注意事项

### 1. 超时限制

**问题**: Vercel Serverless Functions 有执行时间限制
- **Hobby Plan**: 10 秒
- **Pro Plan**: 60 秒
- **Enterprise**: 最多 900 秒

**解决方案**:
- 在 `vercel.json` 中设置 `maxDuration`
- 如果文本很长，考虑分批处理或使用异步处理

### 2. 文件系统限制

**问题**: Vercel 的文件系统是只读的（除了 `/tmp`）

**当前实现**: ✅ 已使用 `tempfile` 模块处理临时文件

```python
# app/main.py
temp_dir = tempfile.mkdtemp(prefix="drama_")
```

### 3. 并发请求限制

**ElevenLabs API 限制**:
- Free Tier: 最多 3-4 个并发请求

**当前实现**: ✅ 已使用 `asyncio.Semaphore(3)` 限制并发

### 4. 内存限制

**Vercel 限制**:
- Hobby: 1024 MB
- Pro: 3008 MB

**优化建议**:
- 长文本分段处理
- 及时清理临时文件
- 使用流式处理音频

---

## 🔍 常见问题

### Q1: 部署后 500 错误

**检查**:
1. Vercel 日志: `vercel logs`
2. 环境变量是否正确配置
3. API Keys 是否有效

### Q2: 依赖安装失败

**检查**:
1. `requirements.txt` 格式是否正确
2. 所有包是否兼容 Python 3.12
3. 查看构建日志

### Q3: 请求超时

**解决**:
1. 检查 `vercel.json` 的 `maxDuration` 设置
2. 升级到 Pro Plan（如果需要更长执行时间）
3. 考虑异步处理架构

---

## 📊 兼容性矩阵

| 环境 | Python 版本 | audioop 来源 | 状态 |
|------|-------------|--------------|------|
| **Vercel** | 3.12 | 内置 | ✅ 正常工作 |
| **本地开发** | 3.13+ | audioop-lts | ✅ 自动安装 |
| **本地开发** | 3.12 及以下 | 内置 | ✅ 正常工作 |

---

## 🔄 持续部署

### 自动部署

Vercel 会自动监听 Git 仓库的变化：
- **main 分支**: 推送后自动部署到生产环境
- **其他分支**: 自动创建预览部署

### 手动部署

```bash
# 部署到生产环境
vercel --prod

# 部署预览版本
vercel
```

---

## 🎯 性能优化建议

### 1. 启用缓存

```python
# 在 main.py 中添加缓存头
return FileResponse(
    path=zip_path,
    headers={
        "Cache-Control": "public, max-age=3600"
    }
)
```

### 2. 使用 CDN

Vercel 自动提供全球 CDN，无需额外配置。

### 3. 监控性能

使用 Vercel Analytics:
```bash
vercel analytics
```

---

## 📚 相关资源

- [Vercel Python 文档](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)

---

## ✅ 部署清单

部署前确认：

- [ ] `requirements.txt` 包含所有依赖（带环境标记）
- [ ] `runtime.txt` 指定 Python 3.12
- [ ] `vercel.json` 配置正确
- [ ] `api/index.py` 入口文件存在
- [ ] 环境变量已在 Vercel 配置
- [ ] API Keys 有效且有足够配额
- [ ] 代码已推送到 Git 仓库
- [ ] 测试本地运行正常

---

**部署完成后，你的 DramaFlow API 将在全球范围内高速可用！** 🚀✨

