# 🎵 前端集成指南 - 直接播放 MP3

## 📦 安装依赖

```bash
npm install jszip
# 或
pnpm add jszip
```

---

## 🎯 最简单的播放示例

### React/Next.js 完整组件

```typescript
'use client';

import { useState } from 'react';
import JSZip from 'jszip';

export default function AudioDramaPlayer() {
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<string>('');
  const [error, setError] = useState<string>('');

  const generateAndPlay = async (text: string) => {
    setLoading(true);
    setError('');
    
    try {
      // 1. 调用后端 API
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error('生成失败');
      }

      // 2. 获取 ZIP 文件（Blob）
      const zipBlob = await response.blob();
      
      // 3. 解压 ZIP
      const zip = await JSZip.loadAsync(zipBlob);
      
      // 4. 提取 MP3 文件
      const mp3File = zip.file('drama.mp3');
      if (!mp3File) {
        throw new Error('ZIP 中未找到 MP3 文件');
      }
      
      const mp3Blob = await mp3File.async('blob');
      
      // 5. 创建音频 URL（关键！）
      const url = URL.createObjectURL(mp3Blob);
      setAudioUrl(url);
      
      // 6. 可选：提取字幕
      const srtFile = zip.file('drama.srt');
      if (srtFile) {
        const srtText = await srtFile.async('text');
        setSubtitles(srtText);
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">音频剧播放器</h1>
      
      <button
        onClick={() => generateAndPlay('小说文本内容...')}
        disabled={loading}
        className="bg-blue-500 text-white px-4 py-2 rounded"
      >
        {loading ? '生成中...' : '生成并播放'}
      </button>

      {error && (
        <div className="text-red-500 mt-2">{error}</div>
      )}

      {audioUrl && (
        <div className="mt-4">
          <audio 
            src={audioUrl} 
            controls 
            autoPlay  {/* 自动播放 */}
            className="w-full"
          />
          
          {subtitles && (
            <div className="mt-4 p-4 bg-gray-100 rounded">
              <h3 className="font-bold mb-2">字幕:</h3>
              <pre className="text-sm whitespace-pre-wrap">{subtitles}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## ⚡ 核心代码片段

### 1. 基础播放（最简化）

```typescript
async function generateAndPlay(text: string) {
  // 调用 API
  const response = await fetch('http://localhost:8000/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  // 解压 ZIP
  const zipBlob = await response.blob();
  const zip = await JSZip.loadAsync(zipBlob);
  const mp3Blob = await zip.file('drama.mp3')!.async('blob');
  
  // 创建 URL 并播放
  const audioUrl = URL.createObjectURL(mp3Blob);
  const audio = new Audio(audioUrl);
  audio.play();
}
```

### 2. 带加载状态的版本

```typescript
const [isPlaying, setIsPlaying] = useState(false);

async function playDrama(text: string) {
  setIsPlaying(true);
  
  try {
    const response = await fetch('http://localhost:8000/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });

    const zipBlob = await response.blob();
    const zip = await JSZip.loadAsync(zipBlob);
    const mp3Blob = await zip.file('drama.mp3')!.async('blob');
    const url = URL.createObjectURL(mp3Blob);
    
    // 使用 Audio 元素播放
    const audio = new Audio(url);
    audio.play();
    
    // 监听播放结束
    audio.onended = () => {
      setIsPlaying(false);
      URL.revokeObjectURL(url); // 清理资源
    };
    
  } catch (error) {
    console.error('播放失败:', error);
    setIsPlaying(false);
  }
}
```

### 3. 使用 HTML Audio 标签（推荐）

```typescript
export default function AudioPlayer() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async (text: string) => {
    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      const zipBlob = await response.blob();
      const zip = await JSZip.loadAsync(zipBlob);
      const mp3Blob = await zip.file('drama.mp3')!.async('blob');
      const url = URL.createObjectURL(mp3Blob);
      
      // 设置音频源
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.load();
        audioRef.current.play();
      }
      
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={() => handleGenerate('文本...')}>
        {loading ? '生成中...' : '生成音频剧'}
      </button>
      
      <audio 
        ref={audioRef} 
        controls 
        className="w-full mt-4"
      />
    </div>
  );
}
```

---

## 🎨 完整的 Studio 页面示例

```typescript
'use client';

import { useState, useRef } from 'react';
import JSZip from 'jszip';

interface GenerateResponse {
  audioUrl: string;
  subtitles: string;
}

export default function StudioPage() {
  const [novelText, setNovelText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const handleGenerate = async () => {
    if (!novelText.trim()) {
      alert('请输入小说文本');
      return;
    }

    setLoading(true);

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
        throw new Error(`生成失败: ${response.status}`);
      }

      // 获取 ZIP 文件
      const zipBlob = await response.blob();
      
      // 解压
      const zip = await JSZip.loadAsync(zipBlob);
      
      // 提取 MP3
      const mp3File = zip.file('drama.mp3');
      if (!mp3File) throw new Error('未找到音频文件');
      const mp3Blob = await mp3File.async('blob');
      const audioUrl = URL.createObjectURL(mp3Blob);
      
      // 提取 SRT（可选）
      const srtFile = zip.file('drama.srt');
      const subtitles = srtFile ? await srtFile.async('text') : '';
      
      // 保存结果
      setResult({ audioUrl, subtitles });
      
      // 自动播放
      setTimeout(() => {
        audioRef.current?.play();
      }, 100);
      
    } catch (error) {
      console.error('生成失败:', error);
      alert(error instanceof Error ? error.message : '生成失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">DramaFlow Studio</h1>
      
      {/* 输入区域 */}
      <div className="mb-6">
        <label className="block text-sm font-medium mb-2">
          输入小说文本
        </label>
        <textarea
          value={novelText}
          onChange={(e) => setNovelText(e.target.value)}
          placeholder="输入你的小说文本..."
          className="w-full h-48 p-4 border rounded-lg"
        />
      </div>

      {/* 生成按钮 */}
      <button
        onClick={handleGenerate}
        disabled={loading}
        className={`w-full py-3 rounded-lg text-white font-medium ${
          loading 
            ? 'bg-gray-400 cursor-not-allowed' 
            : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        {loading ? '生成中... (可能需要1-2分钟)' : '生成音频剧'}
      </button>

      {/* 播放器 */}
      {result && (
        <div className="mt-8 border rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">🎵 生成完成！</h2>
          
          {/* 音频播放器 */}
          <audio
            ref={audioRef}
            src={result.audioUrl}
            controls
            className="w-full mb-4"
          />

          {/* 下载按钮 */}
          <div className="flex gap-2 mb-4">
            <a
              href={result.audioUrl}
              download="drama.mp3"
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
            >
              下载音频
            </a>
            
            {result.subtitles && (
              <button
                onClick={() => {
                  const blob = new Blob([result.subtitles], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'drama.srt';
                  a.click();
                }}
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
              >
                下载字幕
              </button>
            )}
          </div>

          {/* 字幕显示 */}
          {result.subtitles && (
            <details className="mt-4">
              <summary className="cursor-pointer font-medium">
                查看字幕
              </summary>
              <pre className="mt-2 p-4 bg-gray-100 rounded text-sm overflow-auto max-h-64">
                {result.subtitles}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* 加载动画 */}
      {loading && (
        <div className="mt-4 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">正在生成音频剧...</p>
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 关键要点

### 1. **必须解压 ZIP**
```typescript
const zip = await JSZip.loadAsync(zipBlob);
const mp3Blob = await zip.file('drama.mp3')!.async('blob');
```

### 2. **创建 Object URL**
```typescript
const audioUrl = URL.createObjectURL(mp3Blob);
```

### 3. **使用 Audio 元素播放**
```typescript
<audio src={audioUrl} controls autoPlay />
// 或
const audio = new Audio(audioUrl);
audio.play();
```

### 4. **清理资源（重要！）**
```typescript
// 当不再需要时
URL.revokeObjectURL(audioUrl);
```

---

## 🚀 快速测试

### 在浏览器控制台测试

```javascript
// 1. 生成音频剧
fetch('http://localhost:8000/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Test text' })
})
.then(res => res.blob())
.then(zipBlob => JSZip.loadAsync(zipBlob))
.then(zip => zip.file('drama.mp3').async('blob'))
.then(mp3Blob => {
  const url = URL.createObjectURL(mp3Blob);
  const audio = new Audio(url);
  audio.play();
  console.log('正在播放！');
});
```

---

## 💡 最佳实践

### 1. 加载进度提示
```typescript
const [progress, setProgress] = useState(0);

// 使用 axios 获取进度
import axios from 'axios';

const response = await axios.post('http://localhost:8000/generate', 
  { text },
  {
    responseType: 'blob',
    onDownloadProgress: (progressEvent) => {
      const percentCompleted = Math.round(
        (progressEvent.loaded * 100) / progressEvent.total
      );
      setProgress(percentCompleted);
    }
  }
);
```

### 2. 缓存音频
```typescript
// 保存到 localStorage
const saveAudio = async (mp3Blob: Blob) => {
  const reader = new FileReader();
  reader.readAsDataURL(mp3Blob);
  reader.onloadend = () => {
    localStorage.setItem('lastAudio', reader.result as string);
  };
};

// 读取缓存
const loadCachedAudio = () => {
  const cached = localStorage.getItem('lastAudio');
  if (cached) {
    setAudioUrl(cached);
  }
};
```

### 3. 错误处理
```typescript
try {
  const response = await fetch('http://localhost:8000/generate', {...});
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '生成失败');
  }
  
  // ... 处理响应
} catch (error) {
  if (error instanceof TypeError) {
    console.error('网络错误:', error);
  } else {
    console.error('生成错误:', error);
  }
}
```

---

## 📱 移动端适配

```typescript
// 检测移动设备
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

// 移动端可能需要用户手势触发播放
if (isMobile) {
  // 显示播放按钮，不自动播放
  <audio src={audioUrl} controls />
} else {
  // 桌面端可以自动播放
  <audio src={audioUrl} controls autoPlay />
}
```

---

**现在你可以在前端直接播放生成的音频了！** 🎉🎵

