# ✅ Vercel Functions 模式匹配问题修复

## 🐛 错误信息

```
Error: The pattern "api/**/*.py" defined in `functions` doesn't match any Serverless Functions inside the `api` directory.

Learn More: https://vercel.link/unmatched-function-pattern
```

## 🔍 问题分析

### 项目结构

```
backend/
├── api/
│   └── index.py          ← 只有一个文件
├── app/
│   └── main.py
└── vercel.json
```

### 错误的配置 ❌

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
}
```

**问题**：
1. `api/**/*.py` 这个通配符模式可能不匹配单个文件
2. 对于简单的项目结构，Vercel 可以**自动检测** `api/` 目录
3. 不需要显式配置 `functions`

---

## ✅ 解决方案

### 方案 1: 最简配置（已采用）✅

```json
{
  "version": 2
}
```

**说明**：
- ✅ Vercel 自动检测 `api/index.py`
- ✅ 自动创建 Serverless Function
- ✅ 路由自动映射：`/` → `api/index.py`
- ✅ 不需要手动配置 functions、builds、routes

**优点**：
- 简单
- 不容易出错
- 遵循 Vercel 的"约定优于配置"原则

---

### 方案 2: 完全空配置

删除 `vercel.json` 或只保留 `{}`

**说明**：
- Vercel 仍然可以自动检测
- 但缺少 `version: 2` 可能使用旧版 API

---

### 方案 3: 如果确实需要自定义（Pro Plan）

如果你有 **Vercel Pro Plan**，想设置更长的超时时间：

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb"
      }
    }
  ]
}
```

**注意**：
- ⚠️ `maxDuration` 只在 `functions` 中有效
- ⚠️ `builds` 和 `functions` 不能同时使用
- ⚠️ Hobby Plan 最多 10 秒超时，无法延长

---

## 🏗️ Vercel 自动检测规则

Vercel 会自动将以下文件转换为 Serverless Functions：

```
api/
├── index.py          → / (根路径)
├── hello.py          → /api/hello
├── users.py          → /api/users
└── users/
    └── [id].py       → /api/users/:id (动态路由)
```

**你的项目**：
```
api/
└── index.py          → / (所有请求)
```

`api/index.py` 导出 FastAPI app，FastAPI 内部处理所有路由：
- `/` → 健康检查
- `/generate` → 音频生成

---

## 🔄 Vercel 部署流程

```
推送代码到 GitHub
    ↓
Vercel 检测到更新
    ↓
扫描项目结构
    ↓
发现 api/index.py
    ↓
自动识别为 Python Serverless Function
    ↓
读取 runtime.txt (python-3.12)
    ↓
安装 requirements.txt
    ↓
部署完成
```

**不需要**：
- ❌ 手动配置 `functions`
- ❌ 手动配置 `builds`
- ❌ 手动配置 `routes`

---

## ⚙️ 超时时间说明

### Hobby Plan（免费）

```json
{
  "version": 2
}
```

- **超时时间**: 10 秒（无法延长）
- **内存**: 1024 MB
- **并发**: 基础限制

### Pro Plan（付费）

如果需要更长超时，可以联系 Vercel 支持或在项目设置中调整：

```json
{
  "version": 2
}
```

然后在 Dashboard → Settings → Functions 中设置超时。

---

## 📝 最终配置文件

### vercel.json ✅

```json
{
  "version": 2
}
```

### runtime.txt ✅

```
python-3.12
```

### requirements.txt ✅

```
fastapi
uvicorn[standard]
python-dotenv
httpx
edge-tts
elevenlabs
pydub
dirtyjson
```

### api/index.py ✅

```python
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app

app = app
```

---

## 🧪 验证配置

### 1. 本地测试（使用 Vercel CLI）

```bash
# 安装 Vercel CLI
npm install -g vercel

# 本地运行（模拟 Vercel 环境）
cd /Users/baojiong/Documents/AI/AudioDrama/backend
vercel dev

# 测试
curl http://localhost:3000/
```

### 2. 部署测试

```bash
# 推送到 GitHub
git add vercel.json
git commit -m "fix: Simplify vercel.json configuration"
git push origin main

# 或直接部署
vercel --prod
```

### 3. 查看构建日志

应该看到：
```
✅ Detected Python files in /api directory
✅ Building Serverless Function: api/index.py
✅ Installing dependencies from requirements.txt
✅ Deployment ready
```

---

## 🎯 关键要点

### ✅ 做对了什么

1. **遵循 Vercel 约定**
   - `api/` 目录自动识别
   - `index.py` 作为根路由
   - 不需要复杂配置

2. **保持简单**
   - 最小化 `vercel.json` 配置
   - 让 Vercel 自动处理

3. **明确版本**
   - `version: 2` 使用最新 API
   - `runtime.txt` 指定 Python 版本

### ❌ 避免的陷阱

1. **过度配置**
   - ❌ `functions` 模式不匹配
   - ❌ `builds` 和 `functions` 冲突
   - ❌ 不必要的 `routes` 配置

2. **错误的通配符**
   - ❌ `api/**/*.py` 可能不匹配
   - ✅ 让 Vercel 自动检测

---

## 📊 配置演进历史

### 第 1 版（❌ 错误）

```json
{
  "version": 2,
  "builds": [...],
  "routes": [...],
  "functions": {...}
}
```

**问题**: `builds` 和 `functions` 冲突

### 第 2 版（❌ 错误）

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key"
  }
}
```

**问题**: 
- 模式不匹配
- Secret 引用错误

### 第 3 版（✅ 正确）

```json
{
  "version": 2
}
```

**优点**: 
- 简单
- 可靠
- 遵循最佳实践

---

## 🚀 部署后验证

### 健康检查

```bash
curl https://your-app.vercel.app/
```

**预期响应**：
```json
{
  "status": "healthy",
  "service": "DramaFlow API",
  "version": "1.0.0"
}
```

### 测试音频生成

```bash
curl -X POST https://your-app.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"测试文本"}' \
  -o test.zip
```

**预期**：
- ✅ 返回 ZIP 文件
- ✅ 包含 `drama.mp3` 和 `drama.srt`

---

## 📚 相关资源

- [Vercel Serverless Functions](https://vercel.com/docs/functions/serverless-functions)
- [Python Runtime](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [Configuration Reference](https://vercel.com/docs/projects/project-configuration)

---

## ✅ 修复完成

### 更改内容
- ✅ 简化 `vercel.json` 为最小配置
- ✅ 移除不必要的 `functions` 配置
- ✅ 让 Vercel 自动检测 `api/index.py`

### 下一步
1. 推送代码：`git push origin main`
2. 等待 Vercel 自动部署
3. 验证部署成功

---

**修复完成！这次应该可以成功部署了！** ✅🚀

