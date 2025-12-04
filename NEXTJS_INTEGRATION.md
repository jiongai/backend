# 🚀 Next.js 完整集成指南

## 📦 安装依赖

```bash
npm install jszip
# 或
pnpm add jszip
# 或
yarn add jszip
```

---

## 🎯 方案 1: App Router（推荐）

### 1. 创建 Studio 页面

**文件**: `app/studio/page.tsx`

```typescript
'use client';

import { useState, useRef } from 'react';
import JSZip from 'jszip';

export default function StudioPage() {
  const [novelText, setNovelText] = useState('');
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<string>('');
  const [error, setError] = useState<string>('');
  const audioRef = useRef<HTMLAudioElement>(null);

  const handleGenerate = async () => {
    if (!novelText.trim()) {
      alert('请输入小说文本');
      return;
    }

    setLoading(true);
    setError('');
    setAudioUrl(null);

    try {
      // 调用后端 API
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: novelText,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '生成失败');
      }

      // 获取 ZIP 文件
      const zipBlob = await response.blob();
      
      // 解压 ZIP
      const zip = await JSZip.loadAsync(zipBlob);
      
      // 提取 MP3
      const mp3File = zip.file('drama.mp3');
      if (!mp3File) {
        throw new Error('ZIP 中未找到音频文件');
      }
      const mp3Blob = await mp3File.async('blob');
      const url = URL.createObjectURL(mp3Blob);
      setAudioUrl(url);
      
      // 提取 SRT 字幕（可选）
      const srtFile = zip.file('drama.srt');
      if (srtFile) {
        const srtText = await srtFile.async('text');
        setSubtitles(srtText);
      }

      // 自动播放
      setTimeout(() => {
        audioRef.current?.play();
      }, 100);
      
    } catch (err) {
      console.error('生成失败:', err);
      setError(err instanceof Error ? err.message : '生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">🎭 DramaFlow Studio</h1>
      
      {/* 输入区域 */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">
          输入小说文本
        </label>
        <textarea
          value={novelText}
          onChange={(e) => setNovelText(e.target.value)}
          placeholder="请输入你的小说文本...

例如：
老旧的庄园矗立在山顶。「这里有人吗？」莎拉紧张地低声问道。风在树林间呼啸而过。「我在这里。」一个低沉的声音从阴影中传来。"
          className="w-full h-48 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="text-sm text-gray-500 mt-2">
          提示：包含对话、情节和动作描写效果更好
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          ❌ {error}
        </div>
      )}

      {/* 生成按钮 */}
      <button
        onClick={handleGenerate}
        disabled={loading || !novelText.trim()}
        className={`w-full py-3 rounded-lg text-white font-medium transition-colors ${
          loading || !novelText.trim()
            ? 'bg-gray-400 cursor-not-allowed' 
            : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        {loading ? '🎬 生成中... (可能需要1-2分钟)' : '🎵 生成音频剧'}
      </button>

      {/* 加载动画 */}
      {loading && (
        <div className="mt-6 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">正在分析文本并生成音频...</p>
          <p className="text-sm text-gray-500 mt-2">这可能需要一些时间，请耐心等待</p>
        </div>
      )}

      {/* 播放器 */}
      {audioUrl && (
        <div className="mt-8 border border-gray-200 rounded-lg p-6 bg-white shadow-sm">
          <h2 className="text-xl font-bold mb-4 text-green-600">
            ✅ 生成完成！
          </h2>
          
          {/* 音频播放器 */}
          <div className="mb-4">
            <audio
              ref={audioRef}
              src={audioUrl}
              controls
              className="w-full"
            />
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 mb-4">
            <a
              href={audioUrl}
              download="drama.mp3"
              className="flex-1 bg-green-600 text-white px-4 py-2 rounded text-center hover:bg-green-700 transition-colors"
            >
              📥 下载音频
            </a>
            
            {subtitles && (
              <button
                onClick={() => {
                  const blob = new Blob([subtitles], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'drama.srt';
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="flex-1 bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 transition-colors"
              >
                📄 下载字幕
              </button>
            )}
          </div>

          {/* 字幕显示 */}
          {subtitles && (
            <details className="mt-4">
              <summary className="cursor-pointer font-medium text-gray-700 hover:text-gray-900">
                📝 查看字幕
              </summary>
              <pre className="mt-2 p-4 bg-gray-50 rounded text-sm overflow-auto max-h-64 whitespace-pre-wrap">
                {subtitles}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 方案 2: 使用自定义 Hook

**文件**: `hooks/useAudioDrama.ts`

```typescript
import { useState } from 'react';
import JSZip from 'jszip';

interface AudioDramaResult {
  audioUrl: string;
  subtitles: string;
}

export function useAudioDrama() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AudioDramaResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generate = async (text: string) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '生成失败');
      }

      // 解压 ZIP
      const zipBlob = await response.blob();
      const zip = await JSZip.loadAsync(zipBlob);
      
      // 提取文件
      const mp3Blob = await zip.file('drama.mp3')!.async('blob');
      const audioUrl = URL.createObjectURL(mp3Blob);
      
      const srtFile = zip.file('drama.srt');
      const subtitles = srtFile ? await srtFile.async('text') : '';
      
      setResult({ audioUrl, subtitles });
      return { audioUrl, subtitles };
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '未知错误';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { loading, result, error, generate };
}
```

**使用 Hook 的页面**:

```typescript
'use client';

import { useState } from 'react';
import { useAudioDrama } from '@/hooks/useAudioDrama';

export default function StudioPage() {
  const [text, setText] = useState('');
  const { loading, result, error, generate } = useAudioDrama();

  return (
    <div className="container mx-auto p-6">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full h-48 p-4 border rounded"
      />
      
      <button
        onClick={() => generate(text)}
        disabled={loading}
        className="mt-4 px-6 py-2 bg-blue-600 text-white rounded"
      >
        {loading ? '生成中...' : '生成音频剧'}
      </button>

      {error && <div className="text-red-500 mt-4">{error}</div>}

      {result && (
        <audio src={result.audioUrl} controls className="w-full mt-4" />
      )}
    </div>
  );
}
```

---

## 🎯 方案 3: 使用 API Route（代理模式）

如果你想隐藏后端 URL 或处理认证，可以通过 Next.js API Route 代理。

**文件**: `app/api/generate/route.ts`

```typescript
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // 转发到 Python 后端
    const response = await fetch('http://localhost:8000/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Generation failed' },
        { status: response.status }
      );
    }

    // 获取 ZIP 数据
    const zipBlob = await response.blob();
    
    // 返回 ZIP 文件
    return new NextResponse(zipBlob, {
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename=drama_package.zip',
      },
    });
    
  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

**前端调用**:

```typescript
// 现在调用你自己的 API
const response = await fetch('/api/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text }),
});
```

---

## 🎯 方案 4: 环境变量配置

**文件**: `.env.local`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**使用环境变量**:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const response = await fetch(`${API_URL}/generate`, {
  method: 'POST',
  // ...
});
```

---

## 🎨 完整的 UI 组件库集成

### 使用 Tailwind CSS

```typescript
export default function AudioDramaGenerator() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 py-12">
      <div className="container mx-auto px-4 max-w-4xl">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h1 className="text-4xl font-bold text-center mb-8 bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
            🎭 DramaFlow Studio
          </h1>
          
          {/* 你的组件内容 */}
        </div>
      </div>
    </div>
  );
}
```

### 使用 shadcn/ui

```bash
npx shadcn-ui@latest add button textarea
```

```typescript
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function StudioPage() {
  return (
    <div className="container mx-auto p-6">
      <Textarea
        placeholder="输入小说文本..."
        className="min-h-[200px]"
      />
      
      <Button onClick={handleGenerate} className="mt-4">
        生成音频剧
      </Button>
    </div>
  );
}
```

---

## 🚀 Next.js 部署注意事项

### 1. Vercel 部署

如果后端也部署了，更新环境变量：

```bash
# Vercel 环境变量
NEXT_PUBLIC_API_URL=https://your-backend-url.com
```

### 2. CORS 配置

确保 Python 后端允许你的前端域名：

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-frontend-url.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. 超时配置

对于较长的生成时间，配置 Next.js API 超时：

```typescript
// app/api/generate/route.ts
export const maxDuration = 300; // 5分钟
```

---

## 📱 响应式设计

```typescript
export default function StudioPage() {
  return (
    <div className="container mx-auto p-4 sm:p-6 lg:p-8">
      {/* 移动端优化 */}
      <textarea
        className="w-full h-32 sm:h-48 md:h-64 p-4 border rounded"
      />
      
      <button
        className="w-full sm:w-auto px-6 py-3 mt-4"
      >
        生成音频剧
      </button>
    </div>
  );
}
```

---

## 🧪 测试 Next.js 集成

### 1. 启动后端
```bash
cd backend
./run.sh
```

### 2. 启动前端
```bash
cd my-audio-drama  # 你的 Next.js 项目
npm run dev
```

### 3. 访问
```
http://localhost:3000/studio
```

---

## 📊 完整项目结构

```
my-audio-drama/
├── app/
│   ├── studio/
│   │   └── page.tsx          # Studio 页面
│   ├── api/
│   │   └── generate/
│   │       └── route.ts      # API 代理（可选）
│   └── layout.tsx
├── hooks/
│   └── useAudioDrama.ts      # 自定义 Hook
├── components/
│   └── AudioPlayer.tsx       # 音频播放器组件
├── .env.local                # 环境变量
├── package.json
└── next.config.js
```

---

## 💡 开发提示

### 1. 开发时跨域问题

Next.js 开发服务器配置代理：

```javascript
// next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },
};
```

### 2. TypeScript 类型

```typescript
// types/audio-drama.ts
export interface AudioDramaRequest {
  text: string;
}

export interface AudioDramaResponse {
  audioUrl: string;
  subtitles: string;
}
```

---

**现在你可以在 Next.js 项目中完美集成 DramaFlow 了！** 🚀

推荐使用**方案 1（App Router）**，最简单直接！

