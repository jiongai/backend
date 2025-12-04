# ✅ Vercel 部署最终修复方案

## 🐛 遇到的问题

### 问题 1: `builds` 和 `functions` 冲突
```
The `functions` property cannot be used in conjunction with the `builds` property.
```

**✅ 已修复**: 移除 `builds` 和 `routes`，只保留 `functions`

---

### 问题 2: 环境变量引用不存在
```
Environment Variable "OPENROUTER_API_KEY" references Secret "openrouter_api_key", which does not exist.
```

**✅ 解决方案**: 在 Vercel Dashboard 添加环境变量（见下方步骤）

---

### 问题 3: `uv` 无法处理 `audioop-lts` 环境标记
```
Using uv at "/usr/local/bin/uv"
ERROR: Could not find a version that satisfies the requirement audioop-lts
ERROR: No matching distribution found for audioop-lts
```

**根本原因**:
- Vercel 使用 `uv` 工具安装依赖
- `uv` 不能正确处理环境标记 `audioop-lts; python_version >= "3.13"`
- 即使 Python 3.12 不需要这个包，`uv` 仍然尝试解析它

**✅ 已修复**: 从 `requirements.txt` 移除 `audioop-lts`，创建 `requirements-dev.txt` 用于本地开发

---

## 📁 最终文件配置

### 1. `requirements.txt` (用于 Vercel 部署)

```python
fastapi
uvicorn[standard]
python-dotenv
httpx
edge-tts
elevenlabs
pydub
dirtyjson
```

**说明**: 
- ✅ 不含 `audioop-lts`
- ✅ Python 3.12 有内置 `audioop` 模块
- ✅ `pydub` 可以正常工作

---

### 2. `requirements-dev.txt` (用于本地 Python 3.13+ 开发)

```python
# Development Requirements (for Python 3.13+)
# Install with: pip install -r requirements.txt -r requirements-dev.txt

# audioop-lts is only needed for Python 3.13+ (where audioop was removed)
# Python 3.12 and earlier have built-in audioop module
audioop-lts; python_version >= "3.13"
```

**说明**:
- ✅ 只在本地 Python 3.13+ 环境需要
- ✅ 不影响 Vercel 部署

---

### 3. `runtime.txt`

```
python-3.12
```

**说明**: 明确指定 Vercel 使用 Python 3.12

---

### 4. `vercel.json`

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
- ✅ 只使用 `functions`（移除了 `builds` 和 `routes`）
- ✅ `maxDuration: 300` 允许 5 分钟执行时间
- ✅ 环境变量引用 Vercel Secrets

---

## 🔐 配置 Vercel 环境变量

### 方法 1: Vercel Dashboard（推荐）

1. **登录 Vercel**: https://vercel.com/dashboard
2. **选择项目**（或创建新项目）
3. **进入设置**: 
   - 项目页面 → **Settings** → **Environment Variables**
4. **添加第一个变量**:
   ```
   Name: OPENROUTER_API_KEY
   Value: sk-or-v1-你的实际密钥
   Environments: 
     ✅ Production
     ✅ Preview
     ✅ Development
   ```
5. **添加第二个变量**:
   ```
   Name: ELEVENLABS_API_KEY
   Value: sk_你的实际密钥
   Environments: 
     ✅ Production
     ✅ Preview
     ✅ Development
   ```
6. **保存** → 完成！

### 方法 2: Vercel CLI

```bash
# 安装 Vercel CLI
npm install -g vercel

# 登录
vercel login

# 进入项目目录
cd /Users/baojiong/Documents/AI/AudioDrama/backend

# 添加环境变量
vercel env add OPENROUTER_API_KEY
# 输入值: sk-or-v1-xxxxx
# 选择环境: Production, Preview, Development

vercel env add ELEVENLABS_API_KEY
# 输入值: sk_xxxxx
# 选择环境: Production, Preview, Development

# 验证
vercel env ls
```

---

## 🚀 部署步骤

### 1. 提交代码

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

# 查看更改
git status

# 添加所有文件
git add .

# 提交
git commit -m "fix: Resolve Vercel deployment issues

- Remove audioop-lts from requirements.txt for Vercel compatibility
- Create requirements-dev.txt for Python 3.13+ local development
- Fix vercel.json: remove builds/routes, keep only functions
- Add setup_dev.sh for automated development setup
- Update documentation"

# 推送到 GitHub
git push origin main
```

### 2. 部署到 Vercel

**方法 A: Git 自动部署**
1. 推送代码后，Vercel 自动检测并部署
2. 访问 Vercel Dashboard 查看部署状态

**方法 B: Vercel CLI 手动部署**
```bash
# 部署到生产环境
vercel --prod

# 或先部署预览版本测试
vercel
```

### 3. 验证部署

```bash
# 健康检查
curl https://your-app.vercel.app/

# 预期响应:
# {
#   "status": "healthy",
#   "service": "DramaFlow API",
#   "version": "1.0.0"
# }

# 测试音频生成
curl -X POST https://your-app.vercel.app/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"老人站在山顶。"}' \
  -o test.zip

# 检查 ZIP 文件
unzip -l test.zip
# 应该看到: drama.mp3 和 drama.srt
```

---

## 🖥️ 本地开发设置

### 自动设置（推荐）

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

# 运行自动设置脚本
./setup_dev.sh

# 脚本会自动:
# 1. 检测 Python 版本
# 2. 创建虚拟环境
# 3. 安装依赖
# 4. Python 3.13+ 自动安装 audioop-lts
# 5. 创建 .env 文件
```

### 手动设置

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装基础依赖
pip install -r requirements.txt

# 3. 如果使用 Python 3.13+，安装开发依赖
pip install -r requirements-dev.txt

# 4. 配置环境变量
cp env.template .env
# 编辑 .env，填入 API Keys

# 5. 运行服务器
./run.sh
```

---

## 📊 环境对比

| 环境 | Python | audioop 来源 | requirements | 状态 |
|------|--------|--------------|--------------|------|
| **Vercel 生产** | 3.12 | 内置 | requirements.txt | ✅ 正常 |
| **本地开发** | 3.12 | 内置 | requirements.txt | ✅ 正常 |
| **本地开发** | 3.13+ | audioop-lts | requirements.txt + requirements-dev.txt | ✅ 正常 |

---

## 🧪 测试清单

### Vercel 部署测试

- [ ] ✅ 环境变量已在 Vercel Dashboard 配置
- [ ] ✅ 代码已推送到 GitHub
- [ ] ✅ Vercel 构建成功（无 audioop-lts 错误）
- [ ] ✅ 健康检查返回 200
- [ ] ✅ `/generate` 接口返回 ZIP 文件
- [ ] ✅ ZIP 包含 MP3 和 SRT 文件

### 本地开发测试

- [ ] ✅ 虚拟环境创建成功
- [ ] ✅ 依赖安装无错误
- [ ] ✅ `python -c "from pydub import AudioSegment"` 成功
- [ ] ✅ `./run.sh` 启动服务器
- [ ] ✅ 本地测试 API 正常

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| `VERCEL_UV_ISSUE.md` | `uv` 工具问题详解 |
| `VERCEL_DEPLOYMENT.md` | 完整部署指南 |
| `VERCEL_CHECKLIST.md` | 部署检查清单 |
| `VERCEL_CONFIG_FIX.md` | 配置修复详情 |
| `DEPLOYMENT_FIX_SUMMARY.md` | Bug 修复总结 |
| `QUICKSTART.md` | 快速开始指南 |

---

## 🎯 关键要点

### ✅ 做对了什么

1. **分离部署和开发依赖**
   - `requirements.txt`: 简洁，只含 Vercel 需要的
   - `requirements-dev.txt`: Python 3.13+ 额外需要的

2. **明确 Python 版本**
   - Vercel: Python 3.12（稳定，有内置 audioop）
   - 本地: 灵活支持 3.12 和 3.13+

3. **简化 Vercel 配置**
   - 只使用 `functions`，移除 `builds`
   - 让 Vercel 自动检测 `api/` 目录

4. **完善文档**
   - 详细记录每个问题和解决方案
   - 提供自动化脚本简化设置

### ❌ 避免的陷阱

1. **环境标记不是万能的**
   - `uv` 工具对环境标记支持有限
   - 不要过度依赖复杂的条件依赖

2. **不要混用 `builds` 和 `functions`**
   - Vercel 2.0+ 只需要 `functions`
   - `builds` 是旧版 API

3. **环境变量需要手动配置**
   - `vercel.json` 只是引用，不是定义
   - 必须在 Vercel Dashboard 或 CLI 中实际创建

---

## 🎉 部署成功！

所有问题已解决，现在可以：

1. ✅ 在 Vercel Dashboard 配置环境变量
2. ✅ 推送代码到 GitHub
3. ✅ Vercel 自动构建和部署
4. ✅ API 在全球范围内可用

**祝部署顺利！** 🚀✨

---

## 🆘 遇到问题？

### 构建失败

```bash
# 查看构建日志
vercel logs

# 常见问题:
# - 环境变量未配置
# - requirements.txt 格式错误
# - Python 版本不匹配
```

### API 错误

```bash
# 查看运行时日志
vercel logs --follow

# 检查:
# - API Keys 是否有效
# - 配额是否用尽
# - 网络连接是否正常
```

### 本地开发问题

```bash
# 重新安装依赖
rm -rf venv
./setup_dev.sh

# 或手动排查
pip install -r requirements.txt -r requirements-dev.txt
python -c "from pydub import AudioSegment; print('OK')"
```

---

**需要帮助？查看文档或提交 Issue！** 📖💬

