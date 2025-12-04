# 🔧 DramaFlow 故障排除指南

## 问题 1: `ModuleNotFoundError: No module named 'app'`

### 症状
```
Traceback (most recent call last):
  File "/Users/baojiong/Documents/AI/AudioDrama/backend/app/main.py", line 19, in <module>
    from app.services import (
ModuleNotFoundError: No module named 'app'
```

### ❌ 错误的启动方式
```bash
python app/main.py          # ❌ 不要这样做
cd app && python main.py    # ❌ 不要这样做
```

### ✅ 正确的启动方式

#### 方式 1: 使用启动脚本（最简单）
```bash
./run.sh
```

#### 方式 2: 使用 uvicorn（推荐）
```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 方式 3: 使用 Python 模块
```bash
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

### 原因
FastAPI 应用必须通过 `uvicorn` 以模块方式启动，而不是直接运行 Python 文件。

---

## 问题 2: `401 Unauthorized` - OpenRouter API

### 症状
```
Error generating audio drama: Client error '401 Unauthorized' 
for url 'https://openrouter.ai/api/v1/chat/completions'
```

### 原因
- API 密钥未配置
- API 密钥无效或过期
- API 密钥格式错误

### ✅ 解决方案

#### 1. 检查 .env 文件
```bash
cat .env
```

应该看到：
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxx
ELEVENLABS_API_KEY=xxxxxxxxxx
```

#### 2. 验证 API 密钥格式

**OpenRouter API 密钥**应该：
- 以 `sk-or-v1-` 开头
- 后面跟随一长串字符
- 例如: `sk-or-v1-1234567890abcdef...`

**获取密钥**: https://openrouter.ai/keys

#### 3. 测试 API 密钥
```bash
# 测试 OpenRouter
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer YOUR_KEY_HERE"

# 应该返回模型列表，而不是 401 错误
```

#### 4. 重新启动服务器
修改 `.env` 后，必须重启服务器：
```bash
# 按 Ctrl+C 停止服务器
# 然后重新启动
./run.sh
```

---

## 问题 3: `No module named 'fastapi'`

### 症状
```
ModuleNotFoundError: No module named 'fastapi'
```

### ✅ 解决方案
```bash
# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证安装
pip list | grep fastapi
```

---

## 问题 4: `audioop` 或 `pydub` 错误

### 症状
```
ModuleNotFoundError: No module named 'audioop'
```

### ✅ 解决方案
```bash
source venv/bin/activate
pip install audioop-lts
```

这个包已经包含在 `requirements.txt` 中，如果遇到问题：
```bash
pip install -r requirements.txt --force-reinstall
```

---

## 问题 5: 端口已被占用

### 症状
```
ERROR: [Errno 48] Address already in use
```

### ✅ 解决方案

#### 查找占用端口的进程
```bash
lsof -i :8000
```

#### 杀死该进程
```bash
kill -9 <PID>
```

#### 或使用不同端口
```bash
uvicorn app.main:app --reload --port 8001
```

---

## 问题 6: 虚拟环境未激活

### 症状
命令行提示符没有 `(venv)` 前缀

### ✅ 解决方案
```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# 验证激活
which python  # 应该指向 venv/bin/python
```

---

## 🔍 诊断检查清单

运行以下命令诊断问题：

```bash
# 1. 确认在项目根目录
pwd
# 应该显示: /Users/baojiong/Documents/AI/AudioDrama/backend

# 2. 检查目录结构
ls -la
# 应该看到: app/ venv/ requirements.txt .env

# 3. 检查虚拟环境
which python
# 应该显示: .../backend/venv/bin/python

# 4. 检查依赖
pip list | grep -E "fastapi|uvicorn|pydub"
# 应该看到这些包

# 5. 测试导入
python -c "from app.main import app; print('OK')"
# 应该输出: OK

# 6. 检查 .env 文件
ls -la .env
# 应该存在且不为空
```

---

## 🆘 快速修复脚本

如果一切都不工作，运行这个完整重置：

```bash
#!/bin/bash
# 保存为 reset.sh 并运行

# 1. 重新创建虚拟环境
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 3. 检查 .env
if [ ! -f .env ]; then
    cp env.template .env
    echo "请编辑 .env 文件并添加 API 密钥"
    exit 1
fi

# 4. 启动服务器
uvicorn app.main:app --reload
```

---

## 💡 最佳实践

1. **总是从项目根目录运行命令**
2. **总是激活虚拟环境**
3. **使用 uvicorn 而不是 python 直接运行**
4. **修改 .env 后重启服务器**
5. **查看终端日志了解错误详情**

---

## 📞 获取帮助

如果问题仍未解决：

1. 检查终端完整错误信息
2. 确认 Python 版本: `python --version` (应该是 3.8+)
3. 确认在正确目录: `pwd`
4. 检查文件权限: `ls -la run.sh` (应该有 x 权限)

---

*最后更新: 2024年12月3日*

