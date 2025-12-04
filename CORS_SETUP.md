# CORS 配置指南

## 什么是 CORS？

CORS (Cross-Origin Resource Sharing) 是浏览器的安全机制，用于控制跨域请求。

**为什么需要？**
- 前端: `http://localhost:3000` (Next.js)
- 后端: `http://127.0.0.1:8000` (Python)
- 不同端口 = 跨域 = 浏览器默认阻止

## Python 后端配置示例

### FastAPI (推荐)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI()

# 🔧 CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📡 API 端点示例
@app.post("/api/generate")
async def generate_audio(text: str, api_key: str):
    # 1. 使用 API key 调用 AI 服务
    # 2. 生成音频文件
    # 3. 返回音频文件
    
    audio_file_path = "generated_audio.mp3"
    
    return FileResponse(
        audio_file_path,
        media_type="audio/mpeg",
        filename="audio-drama.mp3"
    )
```

### Flask

```python
from flask import Flask, request, send_file
from flask_cors import CORS

app = Flask(__name__)

# 🔧 CORS 配置
CORS(app, origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000"
])

# 📡 API 端点示例
@app.route("/api/generate", methods=["POST"])
def generate_audio():
    data = request.get_json()
    text = data.get("text")
    api_key = data.get("api_key")
    
    # 生成音频逻辑...
    audio_file_path = "generated_audio.mp3"
    
    return send_file(
        audio_file_path,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="audio-drama.mp3"
    )
```

## 完整的 FastAPI 示例（带音频生成）

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from pathlib import Path

app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class GenerateRequest(BaseModel):
    text: str
    api_key: str

@app.post("/api/generate")
async def generate_audio(request: GenerateRequest):
    try:
        # 验证输入
        if not request.text or not request.api_key:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # TODO: 这里添加你的音频生成逻辑
        # 例如：调用 OpenAI TTS、ElevenLabs、Azure TTS 等
        
        # 示例：假设生成了音频文件
        audio_path = "output/generated_audio.mp3"
        
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail="Audio generation failed")
        
        # 返回音频文件
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=audio-drama-{int(time.time())}.mp3"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## 安装依赖

```bash
# FastAPI
pip install fastapi uvicorn python-multipart

# 或 Flask
pip install flask flask-cors
```

## 运行后端服务器

```bash
# FastAPI
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Flask
python app.py
```

## 测试 CORS

### 1. 启动后端
```bash
python main.py
```

### 2. 启动前端
```bash
cd /path/to/my-audio-drama
npm run dev
```

### 3. 检查浏览器控制台
- ✅ 正常：API 请求成功，无 CORS 错误
- ❌ 错误：看到 "CORS policy" 错误消息

## 常见错误排查

### 错误 1: "Access-Control-Allow-Origin" 缺失
```
❌ Access to fetch at 'http://127.0.0.1:8000/api/generate' 
   from origin 'http://localhost:3000' has been blocked by CORS policy
```

**解决**: 确保后端已添加 CORS 中间件

### 错误 2: 预检请求失败
```
❌ Response to preflight request doesn't pass access control check
```

**解决**: 确保 `allow_methods` 包含 "POST"

### 错误 3: 凭证问题
```
❌ Credentials flag is 'true', but the 'Access-Control-Allow-Credentials' header is ''
```

**解决**: 设置 `allow_credentials=True`

## 配置参数说明

| 参数 | 说明 | 开发环境 | 生产环境 |
|------|------|----------|----------|
| `allow_origins` | 允许的前端域名 | `["*"]` 或 `["http://localhost:3000"]` | `["https://yourdomain.com"]` |
| `allow_methods` | 允许的 HTTP 方法 | `["*"]` | `["GET", "POST"]` |
| `allow_headers` | 允许的请求头 | `["*"]` | `["Content-Type", "Authorization"]` |
| `allow_credentials` | 允许携带 cookies | `True` (如需认证) | `True` |

## 安全提示

⚠️ **开发环境**: 可以使用 `allow_origins=["*"]` 方便测试

🔒 **生产环境**: 必须指定具体的域名，不要使用 `["*"]`

```python
# ❌ 生产环境不要这样做
allow_origins=["*"]

# ✅ 生产环境应该这样做
allow_origins=[
    "https://your-production-domain.com",
    "https://www.your-production-domain.com"
]
```

## Next.js 前端代码（已实现）

前端代码已经在 `/studio` 页面中实现，使用 axios 发送请求：

```typescript
const response = await axios.post(
  "http://127.0.0.1:8000/api/generate",
  {
    text: novelText,
    api_key: apiKey,
  },
  {
    responseType: "blob",
    headers: {
      "Content-Type": "application/json",
    },
  }
);
```

## 完整流程

1. ✅ 前端发送 POST 请求到 `http://127.0.0.1:8000/api/generate`
2. ✅ 浏览器发送预检请求 (OPTIONS)
3. ✅ 后端 CORS 中间件允许该请求
4. ✅ 后端处理请求，生成音频
5. ✅ 返回音频文件 (Blob)
6. ✅ 前端接收并播放音频

现在你只需要在 Python 后端添加 CORS 配置即可！

