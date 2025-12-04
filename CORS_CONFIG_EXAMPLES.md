# 🔒 DramaFlow CORS 配置示例

## 当前配置（开发环境）

```python
# app/main.py - 当前配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ 开发环境：允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**适用**: 开发、测试
**优点**: 方便快速测试，无需配置
**缺点**: 不安全，不适合生产

---

## 生产环境配置建议

### 选项 1: 指定前端域名（推荐）

```python
# 🔒 生产环境配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-domain.com",           # 生产域名
        "https://www.your-domain.com",       # www 版本
        "http://localhost:3000",             # 本地开发
        "http://127.0.0.1:3000",             # 本地开发备用
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # 只允许需要的方法
    allow_headers=["Content-Type", "Authorization"],  # 只允许需要的头
)
```

### 选项 2: 使用环境变量（最灵活）

```python
import os

# 从环境变量读取允许的源
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

然后在 `.env` 文件中：
```
# 开发环境
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# 生产环境
ALLOWED_ORIGINS=https://your-production-domain.com,https://www.your-production-domain.com
```

### 选项 3: 根据环境自动切换

```python
import os

# 检测环境
ENV = os.getenv("ENVIRONMENT", "development")

if ENV == "production":
    # 🔒 生产环境：严格配置
    CORS_ORIGINS = [
        "https://your-domain.com",
        "https://www.your-domain.com"
    ]
else:
    # 🛠️ 开发环境：宽松配置
    CORS_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"] if ENV != "production" else ["GET", "POST", "OPTIONS"],
    allow_headers=["*"] if ENV != "production" else ["Content-Type", "Authorization"],
)
```

---

## 🧪 测试 CORS 配置

### 测试 1: 使用 curl

```bash
# 测试预检请求
curl -X OPTIONS http://localhost:8000/generate \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v

# 应该看到响应头：
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Methods: ...
```

### 测试 2: 使用浏览器控制台

```javascript
// 在浏览器控制台运行
fetch('http://localhost:8000/health', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
})
.then(res => res.json())
.then(data => console.log('✅ CORS 正常:', data))
.catch(err => console.error('❌ CORS 错误:', err));
```

### 测试 3: 使用前端应用

启动你的前端应用，检查浏览器开发者工具的 Network 标签：

✅ **正常**: 
- 请求状态: 200 OK
- 响应头包含 `Access-Control-Allow-Origin`
- 无 CORS 错误

❌ **错误**:
- 控制台显示 CORS policy 错误
- 请求被阻止

---

## 🐛 常见问题排查

### 问题 1: "CORS policy" 错误

```
Access to fetch at 'http://localhost:8000/generate' from origin 
'http://localhost:3000' has been blocked by CORS policy
```

**检查**:
- ✅ 后端是否启动？
- ✅ CORS 中间件是否添加？
- ✅ `allow_origins` 是否包含前端地址？

**解决**: 
```python
# 临时调试：使用通配符
allow_origins=["*"]
```

### 问题 2: 预检请求失败

```
Response to preflight request doesn't pass access control check
```

**原因**: OPTIONS 请求被拒绝

**解决**:
```python
allow_methods=["*"]  # 或明确包含 "OPTIONS"
```

### 问题 3: 凭证错误

```
Credentials flag is 'true', but the 'Access-Control-Allow-Credentials' header is ''
```

**解决**:
```python
allow_credentials=True  # 确保设置为 True
```

### 问题 4: 文件下载 CORS 错误

如果返回 `FileResponse` 遇到 CORS 问题：

```python
return FileResponse(
    path=audio_file,
    media_type="audio/mpeg",
    filename="drama.mp3",
    headers={
        "Access-Control-Expose-Headers": "Content-Disposition",  # 允许访问这个头
    }
)
```

---

## 📱 前端配置（Next.js/React）

### axios 配置

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',  // 或你的后端地址
  withCredentials: true,  // 如果需要发送 cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// 使用
const response = await api.post('/generate', {
  text: 'Your text here...'
});
```

### fetch 配置

```typescript
const response = await fetch('http://localhost:8000/generate', {
  method: 'POST',
  credentials: 'include',  // 如果需要发送 cookies
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    text: 'Your text here...'
  }),
});
```

---

## 🔐 安全最佳实践

### ✅ 应该做的

1. **生产环境指定域名**
   ```python
   allow_origins=["https://yourdomain.com"]  # 不要用 "*"
   ```

2. **限制方法**
   ```python
   allow_methods=["GET", "POST"]  # 只允许需要的
   ```

3. **限制头部**
   ```python
   allow_headers=["Content-Type", "Authorization"]
   ```

4. **使用 HTTPS**
   ```python
   allow_origins=["https://yourdomain.com"]  # 生产用 https
   ```

### ❌ 不应该做的

1. **生产环境用通配符**
   ```python
   allow_origins=["*"]  # ❌ 生产环境危险
   ```

2. **过度开放**
   ```python
   allow_methods=["*"]  # ❌ 生产环境应限制
   allow_headers=["*"]  # ❌ 生产环境应限制
   ```

3. **混合 HTTP/HTTPS**
   ```python
   allow_origins=[
       "https://secure.com",
       "http://insecure.com"  # ❌ 避免混合
   ]
   ```

---

## 🚀 快速修改指南

### 现在就要连接前端？

**不需要修改** - 当前配置 `allow_origins=["*"]` 已经支持所有前端！

### 准备部署到生产？

1. 打开 `app/main.py`
2. 找到第 36-42 行
3. 修改为：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-production-domain.com",  # 替换为你的域名
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
```

4. 重启服务器

---

## 📚 相关文档

- [FastAPI CORS 文档](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS 指南](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

---

*当前 DramaFlow 的 CORS 配置已经可以正常工作！*

