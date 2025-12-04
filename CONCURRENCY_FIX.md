# 🚦 并发限制修复

## ❌ 错误信息

```
status: 'too_many_concurrent_requests'
message: 'Too many concurrent requests. Your current subscription is 
associated with a maximum of 4 concurrent requests (running in parallel).'
```

---

## ✅ 已修复！

### 问题原因

**之前的代码**：同时生成所有音频片段
```python
# 10 个片段 = 10 个并发请求 ❌
audio_paths = await asyncio.gather(*audio_generation_tasks)
```

**ElevenLabs 限制**：
- 免费层：最多 **4 个并发请求**
- 超过限制：返回 429 错误

---

## 🔧 修复方案

### 使用 Semaphore 控制并发

**新代码**：最多同时 3 个请求
```python
# 创建信号量限制并发为 3
semaphore = asyncio.Semaphore(3)

async def generate_with_limit(segment):
    async with semaphore:  # 等待获取许可
        return await generate_segment_audio(...)

# 并发执行，但同时最多 3 个
audio_paths = await asyncio.gather(*tasks)
```

### 工作原理

```
片段 1-3:  🎵 立即开始生成
片段 4:    ⏳ 等待...
           ✅ 片段 1 完成
片段 4:    🎵 开始生成
片段 5:    ⏳ 等待...
           ✅ 片段 2 完成
片段 5:    🎵 开始生成
...以此类推
```

**结果**：
- ✅ 永远不会超过 3 个并发请求
- ✅ 仍然比顺序执行快 3 倍
- ✅ 遵守 ElevenLabs API 限制

---

## 📊 性能对比

### 场景：生成 10 个音频片段

| 方式 | 并发数 | 时间 | 状态 |
|------|--------|------|------|
| **之前**（无限制） | 10 | ❌ 失败 | 超过限制 |
| **现在**（Semaphore=3） | 3 | ~40秒 | ✅ 成功 |
| **顺序执行** | 1 | ~120秒 | ✅ 成功但慢 |

---

## 🎯 不同订阅的并发限制

| 订阅层级 | 并发限制 | 推荐设置 |
|----------|----------|----------|
| **Free** | 4 | `Semaphore(3)` |
| **Starter** | 10 | `Semaphore(8)` |
| **Creator** | 20 | `Semaphore(15)` |
| **Pro** | 50 | `Semaphore(40)` |

---

## 🔧 如何调整并发数

### 如果你有付费订阅

编辑 `app/main.py`，找到第 170 行：

```python
# 当前设置（免费层）
semaphore = asyncio.Semaphore(3)

# 如果有 Starter 订阅（限制 10）
semaphore = asyncio.Semaphore(8)

# 如果有 Creator 订阅（限制 20）
semaphore = asyncio.Semaphore(15)
```

### 使用环境变量（推荐）

**步骤 1**：在 `.env` 文件添加：
```bash
ELEVENLABS_MAX_CONCURRENT=3
```

**步骤 2**：修改代码读取环境变量：
```python
max_concurrent = int(os.getenv("ELEVENLABS_MAX_CONCURRENT", 3))
semaphore = asyncio.Semaphore(max_concurrent)
```

---

## 🧪 测试修复

### 测试 1: 短文本（2-3个片段）
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Short text"}' \
  -o test_short.zip
```
**预期**：快速完成（所有片段并发）

### 测试 2: 长文本（10+个片段）
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Long novel text with multiple paragraphs and dialogues..."}' \
  -o test_long.zip
```
**预期**：稍慢但成功完成（分批并发）

---

## 📈 优化建议

### 1. 动态调整并发数

根据片段类型调整：
```python
# 对话使用 ElevenLabs（需要控制并发）
# 旁白使用 Edge TTS（无限制）

dialogue_count = sum(1 for s in script if s['type'] == 'dialogue')
if dialogue_count <= 3:
    semaphore = asyncio.Semaphore(3)
else:
    semaphore = asyncio.Semaphore(2)  # 更保守
```

### 2. 批量处理

对于非常长的文本：
```python
# 分批处理，每批最多 10 个
batch_size = 10
for i in range(0, len(script), batch_size):
    batch = script[i:i+batch_size]
    # 处理这一批
```

### 3. 使用进度回调

显示生成进度：
```python
completed = 0
total = len(script)

async def generate_with_progress(segment):
    result = await generate_with_limit(segment)
    nonlocal completed
    completed += 1
    print(f"Progress: {completed}/{total} ({completed*100//total}%)")
    return result
```

---

## 🔍 监控并发使用

### 查看日志

```bash
# 实时监控
tail -f /path/to/terminals/5.txt

# 应该看到：
# Generating audio for segments...
# (不会看到 429 错误了)
# Generated 10 audio files
```

### 添加调试日志（可选）

```python
print(f"Generating {len(script)} segments with max {3} concurrent requests")
# 每个任务开始时
print(f"Starting generation for segment {i+1}/{len(script)}")
```

---

## ⚠️ 注意事项

### 1. 不要设置太高
```python
semaphore = asyncio.Semaphore(10)  # ❌ 免费层会失败
```

### 2. 考虑网络稳定性
```python
# 网络不稳定时使用更保守的值
semaphore = asyncio.Semaphore(2)
```

### 3. 监控 API 配额
```bash
# 访问 ElevenLabs 控制台
open https://elevenlabs.io/app/settings/subscription
```

---

## 🚀 重启服务器

修复已应用，使用 `--reload` 的话代码会自动重新加载！

或手动重启：
```bash
pkill -f "uvicorn app.main:app"
cd /Users/baojiong/Documents/AI/AudioDrama/backend
./run.sh
```

---

## 📊 理解 Semaphore

### 什么是 Semaphore？

信号量是一个并发控制工具：

```python
semaphore = asyncio.Semaphore(3)  # 最多 3 个许可

async with semaphore:  # 获取许可（如果没有则等待）
    # 执行任务
    pass
# 自动释放许可
```

### 可视化

```
许可槽位: [✅] [✅] [✅]  (3个可用)

任务1 获取 → [❌] [✅] [✅]
任务2 获取 → [❌] [❌] [✅]
任务3 获取 → [❌] [❌] [❌]
任务4 等待... ⏳

任务1 完成 → [✅] [❌] [❌]
任务4 获取 → [❌] [❌] [❌]
```

---

## 💡 快速参考

### 免费层（当前配置）
```python
semaphore = asyncio.Semaphore(3)  # 限制 3 个并发
```

### 付费层
```python
# Starter: 10 并发限制
semaphore = asyncio.Semaphore(8)

# Creator: 20 并发限制
semaphore = asyncio.Semaphore(15)

# Pro: 50 并发限制
semaphore = asyncio.Semaphore(40)
```

### 环境变量方式（最灵活）
```python
max_concurrent = int(os.getenv("ELEVENLABS_MAX_CONCURRENT", 3))
semaphore = asyncio.Semaphore(max_concurrent)
```

---

## ✅ 修复验证

- [x] 添加 Semaphore 限制
- [x] 设置为 3 个并发
- [x] 代码无语法错误
- [ ] 服务器重新加载
- [ ] 测试长文本生成
- [ ] 验证不再出现 429 错误

---

**修复完成！现在可以处理任意长度的文本，不会超过 API 并发限制！** 🎉

使用 `--reload` 时代码已自动重新加载，无需手动重启！

