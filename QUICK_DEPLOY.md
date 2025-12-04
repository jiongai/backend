# 🚀 快速部署到 Vercel

## ⚡ 3 步完成部署

### 步骤 1: 配置环境变量 🔐

访问 [Vercel Dashboard](https://vercel.com/dashboard) → 选择项目 → Settings → Environment Variables

添加两个变量：

| Name | Value | Environments |
|------|-------|--------------|
| `OPENROUTER_API_KEY` | `sk-or-v1-你的密钥` | ✅ Production, Preview, Development |
| `ELEVENLABS_API_KEY` | `sk_你的密钥` | ✅ Production, Preview, Development |

---

### 步骤 2: 推送代码 📤

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

git add .
git commit -m "fix: Resolve Vercel deployment issues"
git push origin main
```

---

### 步骤 3: 等待部署完成 ⏳

Vercel 会自动：
1. 检测到代码推送
2. 使用 Python 3.12 构建
3. 安装 `requirements.txt` 中的依赖
4. 部署到全球 CDN

**构建时间**: 约 2-3 分钟

---

## ✅ 验证部署

```bash
# 健康检查
curl https://your-app.vercel.app/

# 测试生成
curl -X POST https://your-app.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"测试文本"}' \
  -o drama.zip
```

---

## 🖥️ 本地开发（可选）

```bash
# 自动设置
./setup_dev.sh

# 或手动设置
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Python 3.13+ 需要额外安装
pip install -r requirements-dev.txt

# 配置环境变量
cp env.template .env
# 编辑 .env 文件

# 运行
./run.sh
```

---

## 📋 文件检查清单

- [x] ✅ `requirements.txt` - 不含 `audioop-lts`
- [x] ✅ `requirements-dev.txt` - Python 3.13+ 开发依赖
- [x] ✅ `runtime.txt` - `python-3.12`
- [x] ✅ `vercel.json` - 只有 `functions`，无 `builds`
- [x] ✅ `api/index.py` - Vercel 入口文件
- [ ] ⚠️ 环境变量 - 需要在 Vercel Dashboard 配置

---

## 🆘 常见问题

### Q: 构建失败，提示找不到 `audioop-lts`？
**A**: 确保 `requirements.txt` 中**没有** `audioop-lts`。已修复 ✅

### Q: 环境变量错误？
**A**: 在 Vercel Dashboard 添加 `OPENROUTER_API_KEY` 和 `ELEVENLABS_API_KEY`

### Q: 本地 Python 3.13 报错？
**A**: 安装开发依赖：`pip install -r requirements-dev.txt`

---

## 📚 详细文档

- **完整指南**: `FINAL_VERCEL_FIX.md`
- **问题详解**: `VERCEL_UV_ISSUE.md`
- **配置说明**: `VERCEL_DEPLOYMENT.md`

---

**就是这么简单！** 🎉✨

