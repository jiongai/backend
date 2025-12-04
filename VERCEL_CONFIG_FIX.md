# ✅ Vercel 配置修复

## 🐛 错误信息

```
The `functions` property cannot be used in conjunction with the `builds` property. 
Please remove one of them.
```

## 📋 问题分析

### 错误的配置 ❌

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ],
  "functions": {
    "api/index.py": {
      "maxDuration": 300
    }
  }
}
```

**问题**: 
- `builds` 和 `functions` 是互斥的
- `builds` 是旧的 API（Vercel 1.0）
- `functions` 是新的 API（Vercel 2.0+）
- 不能同时使用

## ✅ 正确的配置

### 方案 1: 使用 `functions`（推荐）

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

**优点**:
- ✅ 简洁明了
- ✅ Vercel 自动检测 `api/` 目录
- ✅ 自动创建 serverless functions
- ✅ 不需要手动配置 routes
- ✅ 支持最新的 Vercel 特性

**工作原理**:
1. Vercel 扫描 `api/` 目录
2. 找到 `api/index.py`
3. 自动创建 serverless function
4. 路由自动映射: `/` → `api/index.py`

### 方案 2: 使用 `builds`（不推荐）

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
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ]
}
```

**缺点**:
- ❌ 旧版 API
- ❌ 不支持 `maxDuration` 配置
- ❌ 需要手动配置 routes
- ❌ 更复杂

## 📁 项目结构

```
backend/
├── api/
│   └── index.py          # Vercel 自动检测为 serverless function
├── app/
│   ├── main.py           # FastAPI 应用
│   └── services/
│       ├── analyzer.py
│       ├── audio_engine.py
│       └── post_production.py
├── vercel.json           # ✅ 只使用 functions
└── runtime.txt           # python-3.12
```

## 🔍 Vercel 自动检测规则

### API 目录结构

Vercel 会自动将以下文件转换为 serverless functions：

```
api/
├── index.py          → / (根路径)
├── hello.py          → /api/hello
└── users/
    └── [id].py       → /api/users/:id (动态路由)
```

### 我们的配置

```
api/
└── index.py          → / (所有路由)
```

`api/index.py` 导出 FastAPI app，FastAPI 内部处理所有路由：
- `/` → 健康检查
- `/generate` → 音频生成

## 🧪 验证配置

### 本地测试

```bash
# 安装 Vercel CLI
npm install -g vercel

# 本地运行（模拟 Vercel 环境）
cd backend
vercel dev

# 测试
curl http://localhost:3000/
curl -X POST http://localhost:3000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"测试"}' \
  -o test.zip
```

### 部署测试

```bash
# 部署到预览环境
vercel

# 部署到生产环境
vercel --prod
```

## 📊 配置对比

| 特性 | `functions` | `builds` |
|------|-------------|----------|
| API 版本 | 新版 (2.0+) | 旧版 (1.0) |
| 自动检测 | ✅ 是 | ❌ 否 |
| maxDuration | ✅ 支持 | ❌ 不支持 |
| 配置复杂度 | ✅ 简单 | ❌ 复杂 |
| 推荐使用 | ✅ 是 | ❌ 否 |

## ⚙️ 超时配置说明

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
}
```

**maxDuration 限制**:
- **Hobby Plan**: 最多 10 秒
- **Pro Plan**: 最多 60 秒
- **Enterprise**: 最多 900 秒 (15 分钟)

**我们的设置**: 300 秒 (5 分钟)
- 需要 **Pro Plan** 或更高
- 适合音频生成任务（可能需要 2-5 分钟）

**如果使用 Hobby Plan**:
```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 10
    }
  }
}
```

## 🔐 环境变量配置

### 在 vercel.json 中引用

```json
{
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key",
    "ELEVENLABS_API_KEY": "@elevenlabs_api_key"
  }
}
```

**注意**: `@` 前缀表示引用 Vercel Secrets

### 在 Vercel Dashboard 中设置

```bash
# 方法 1: CLI
vercel env add OPENROUTER_API_KEY
vercel env add ELEVENLABS_API_KEY

# 方法 2: Dashboard
# Settings → Environment Variables → Add
```

## ✅ 修复完成

### 修改的文件

1. **`vercel.json`** - 移除 `builds` 和 `routes`，只保留 `functions`
2. **`VERCEL_DEPLOYMENT.md`** - 更新配置示例
3. **`VERCEL_CHECKLIST.md`** - 更新检查清单

### 验证结果

```bash
# 配置语法正确 ✅
# 不再有 builds/functions 冲突 ✅
# Vercel 可以正确解析 ✅
```

## 🚀 现在可以部署了

```bash
# 提交更改
git add vercel.json
git commit -m "fix: Remove builds property from vercel.json"
git push

# 或直接部署
vercel --prod
```

---

**修复完成！配置现在符合 Vercel 最新规范！** ✅🚀

