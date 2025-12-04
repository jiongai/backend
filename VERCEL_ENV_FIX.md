# ✅ Vercel 环境变量配置问题修复

## 🐛 问题描述

### 错误信息
```
Environment Variable "OPENROUTER_API_KEY" references Secret "openrouter_api_key", which does not exist.
```

### 你已经做的
✅ 在 Vercel Dashboard 中设置了环境变量

### 为什么还报错？

**根本原因**：`vercel.json` 中的 `env` 配置方式不对！

---

## 📖 Vercel 环境变量的两种方式

### 方式 1: 在 vercel.json 中引用 Secret（❌ 复杂，容易出错）

```json
{
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key"
  }
}
```

**问题**：
- `@` 前缀表示引用一个名为 `openrouter_api_key` 的 **Secret**
- Secret 和普通环境变量是**不同的东西**
- Secret 需要通过 CLI 创建：`vercel secrets add openrouter_api_key "value"`
- 在 Dashboard 添加的是**环境变量**，不是 Secret

**这就是为什么报错！**

---

### 方式 2: 只在 Dashboard 配置（✅ 推荐，简单）

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
  // 不需要 env 配置！
}
```

**优点**：
- ✅ 简单直接
- ✅ 只需要在 Dashboard 配置一次
- ✅ 不需要 `vercel.json` 中的 `env` 配置
- ✅ Vercel 自动注入环境变量到运行时

---

## ✅ 解决方案

### 已修复：移除 `vercel.json` 中的 `env` 配置

**修改前** ❌：
```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "@openrouter_api_key",  // ❌ 引用不存在的 Secret
    "ELEVENLABS_API_KEY": "@elevenlabs_api_key"   // ❌ 引用不存在的 Secret
  }
}
```

**修改后** ✅：
```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
}
```

---

## 🔐 正确的环境变量配置流程

### 1. 在 Vercel Dashboard 配置（你已经做了 ✅）

1. 登录 https://vercel.com/dashboard
2. 选择项目
3. Settings → Environment Variables
4. 添加变量：

```
Name: OPENROUTER_API_KEY
Value: sk-or-v1-你的密钥
Environments: ✅ Production, ✅ Preview, ✅ Development
```

```
Name: ELEVENLABS_API_KEY
Value: sk_你的密钥
Environments: ✅ Production, ✅ Preview, ✅ Development
```

### 2. 在代码中使用（无需修改）

```python
# app/main.py
import os
from dotenv import load_dotenv

load_dotenv()

openrouter_key = os.getenv("OPENROUTER_API_KEY")  # ✅ 自动读取
elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")  # ✅ 自动读取
```

**Vercel 会自动注入这些环境变量！**

---

## 🔍 Secret vs 环境变量对比

| 特性 | Secret | 环境变量 |
|------|--------|----------|
| **创建方式** | CLI: `vercel secrets add` | Dashboard 或 CLI |
| **引用方式** | `"KEY": "@secret_name"` | 自动注入 |
| **可见性** | 加密，不可见 | Dashboard 可见 |
| **使用场景** | 多项目共享密钥 | 单项目配置 |
| **推荐度** | ❌ 复杂 | ✅ 简单 |

**对于你的项目**：使用普通环境变量就够了，不需要 Secret！

---

## 🧪 验证配置

### 检查 Dashboard 环境变量

1. 访问：https://vercel.com/dashboard
2. 选择项目 → Settings → Environment Variables
3. 确认看到：
   ```
   OPENROUTER_API_KEY    [Hidden]    Production, Preview, Development
   ELEVENLABS_API_KEY    [Hidden]    Production, Preview, Development
   ```

### 检查 vercel.json

```bash
cat vercel.json
```

**应该看到**：
```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
}
```

**不应该有 `env` 字段！**

---

## 🚀 重新部署

修改 `vercel.json` 后，需要重新部署：

### 方法 1: Git 推送（推荐）

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

git add vercel.json
git commit -m "fix: Remove env config from vercel.json"
git push origin main
```

Vercel 会自动检测并重新部署。

### 方法 2: Vercel CLI 手动部署

```bash
vercel --prod
```

### 方法 3: Vercel Dashboard 手动触发

1. 访问项目页面
2. Deployments → 最新部署 → "..." → Redeploy

---

## 📊 部署后验证

### 1. 查看构建日志

```
✅ Installing dependencies...
✅ Building...
✅ No "Secret not found" error  ← 关键！
✅ Deployment ready
```

### 2. 测试 API

```bash
# 健康检查
curl https://your-app.vercel.app/

# 测试生成（会使用环境变量中的 API Keys）
curl -X POST https://your-app.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"测试"}' \
  -o test.zip
```

如果成功返回 ZIP 文件，说明环境变量配置正确！✅

---

## ⚠️ 如果还是报错

### 错误 1: API Key 无效

```
401 Unauthorized
```

**检查**：
- Dashboard 中的 API Key 是否正确
- 是否有多余的空格
- 是否选择了所有环境（Production, Preview, Development）

**解决**：
1. 删除旧的环境变量
2. 重新添加，仔细检查值
3. 重新部署

### 错误 2: 环境变量未生效

```python
# 在代码中添加调试
print(f"OPENROUTER_API_KEY: {os.getenv('OPENROUTER_API_KEY')[:10]}...")
```

**检查 Vercel 日志**：
- Deployments → 点击部署 → Function Logs
- 查看是否打印了 API Key 的前几位

### 错误 3: 环境变量名称不匹配

**确保一致**：
- Dashboard: `OPENROUTER_API_KEY`（大写）
- 代码: `os.getenv("OPENROUTER_API_KEY")`（大写）

---

## 💡 最佳实践

### ✅ 推荐做法

1. **在 Dashboard 配置环境变量**
   - 简单直观
   - 可以随时修改
   - 支持多环境

2. **不在 vercel.json 中配置 env**
   - 避免 Secret 引用问题
   - 减少配置复杂度

3. **使用 .env 文件本地开发**
   ```bash
   # .env (本地)
   OPENROUTER_API_KEY=sk-or-v1-xxxxx
   ELEVENLABS_API_KEY=sk_xxxxx
   ```

4. **不要提交 .env 到 Git**
   ```bash
   # .gitignore
   .env
   .env.local
   ```

### ❌ 避免的做法

1. **不要在 vercel.json 中硬编码密钥**
   ```json
   {
     "env": {
       "OPENROUTER_API_KEY": "sk-or-v1-xxxxx"  // ❌ 不安全！
     }
   }
   ```

2. **不要混用 Secret 和环境变量**
   - 除非你真的需要多项目共享密钥
   - 否则只用环境变量就够了

---

## 📚 相关文档

- [Vercel Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)
- [Vercel Secrets](https://vercel.com/docs/cli/secrets)
- [Python Dotenv](https://pypi.org/project/python-dotenv/)

---

## ✅ 修复总结

### 问题根源
- `vercel.json` 中使用 `@` 引用 Secret
- 但你在 Dashboard 添加的是环境变量，不是 Secret
- 两者是不同的东西！

### 解决方案
- ✅ 移除 `vercel.json` 中的 `env` 配置
- ✅ 只在 Dashboard 配置环境变量
- ✅ Vercel 自动注入，代码直接使用

### 下一步
1. 推送修改后的 `vercel.json`
2. 等待 Vercel 重新部署
3. 测试 API 是否正常工作

---

**修复完成！现在应该可以正常部署了！** ✅🚀

