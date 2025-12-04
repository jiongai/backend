# 🔄 API 响应更新 - 现在包含 SRT 字幕！

## ✅ 更新内容

`/generate` 端点现在返回一个 **ZIP 文件**，包含：
1. ✅ `drama.mp3` - 完整的音频剧
2. ✅ `drama.srt` - 同步字幕文件

---

## 📦 新的响应格式

### 之前（只有 MP3）
```
Content-Type: audio/mpeg
Content-Disposition: attachment; filename="drama.mp3"
```

### 现在（ZIP 包含 MP3 + SRT）
```
Content-Type: application/zip
Content-Disposition: attachment; filename="drama_package.zip"
X-Package-Contents: drama.mp3,drama.srt
X-Segments-Count: 3
```

---

## 🔧 前端代码更新

### 方法 1: 下载 ZIP 文件（推荐）

```typescript
async function generateAudioDrama(text: string) {
  const response = await fetch('http://localhost:8000/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error('Generation failed');
  }

  // 获取 ZIP 文件
  const blob = await response.blob();
  
  // 下载 ZIP 文件
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'drama_package.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

### 方法 2: 解压 ZIP 并使用文件

```typescript
import JSZip from 'jszip';

async function generateAndExtractAudioDrama(text: string) {
  const response = await fetch('http://localhost:8000/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });

  const blob = await response.blob();
  
  // 解压 ZIP
  const zip = await JSZip.loadAsync(blob);
  
  // 提取 MP3
  const mp3Blob = await zip.file('drama.mp3')?.async('blob');
  if (mp3Blob) {
    const audioUrl = URL.createObjectURL(mp3Blob);
    // 使用 audioUrl 播放音频
    const audio = new Audio(audioUrl);
    audio.play();
  }
  
  // 提取 SRT
  const srtText = await zip.file('drama.srt')?.async('text');
  if (srtText) {
    console.log('Subtitles:', srtText);
    // 使用 SRT 显示字幕
    displaySubtitles(srtText);
  }
}
```

### 方法 3: React 组件示例

```typescript
'use client';

import { useState } from 'react';
import JSZip from 'jszip';

export default function AudioDramaGenerator() {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const generateDrama = async (text: string) => {
    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      const blob = await response.blob();
      const zip = await JSZip.loadAsync(blob);
      
      // 提取 MP3
      const mp3Blob = await zip.file('drama.mp3')?.async('blob');
      if (mp3Blob) {
        const url = URL.createObjectURL(mp3Blob);
        setAudioUrl(url);
      }
      
      // 提取 SRT
      const srtText = await zip.file('drama.srt')?.async('text');
      if (srtText) {
        setSubtitles(srtText);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading && <p>Generating...</p>}
      
      {audioUrl && (
        <div>
          <audio src={audioUrl} controls />
          <pre>{subtitles}</pre>
        </div>
      )}
    </div>
  );
}
```

---

## 📥 安装 JSZip

如果使用方法 2 或 3，需要安装 jszip：

```bash
npm install jszip
# 或
yarn add jszip
# 或
pnpm add jszip
```

---

## 🎯 SRT 字幕格式说明

生成的 `drama.srt` 文件格式如下：

```srt
1
00:00:00,000 --> 00:00:03,500
The old mansion stood alone on the hill.

2
00:00:03,800 --> 00:00:07,200
[Sarah] Who is there?

3
00:00:07,500 --> 00:00:10,800
The wind howled through the trees.
```

**格式说明**:
- 对话会标注角色名称：`[Character Name] text`
- 旁白直接显示文本
- 时间戳精确到毫秒
- 300ms 的静音间隙在片段之间

---

## 🎨 显示字幕示例

```typescript
function parseSubtitles(srtText: string) {
  const subtitles: Array<{
    index: number;
    start: number;
    end: number;
    text: string;
  }> = [];

  const blocks = srtText.trim().split('\n\n');
  
  blocks.forEach(block => {
    const lines = block.split('\n');
    if (lines.length >= 3) {
      const index = parseInt(lines[0]);
      const [start, end] = lines[1].split(' --> ');
      const text = lines.slice(2).join('\n');
      
      subtitles.push({
        index,
        start: timeToSeconds(start),
        end: timeToSeconds(end),
        text,
      });
    }
  });

  return subtitles;
}

function timeToSeconds(timeStr: string): number {
  const [hours, minutes, seconds] = timeStr.split(':');
  const [secs, ms] = seconds.split(',');
  return (
    parseInt(hours) * 3600 +
    parseInt(minutes) * 60 +
    parseInt(secs) +
    parseInt(ms) / 1000
  );
}

// 使用示例
function displaySubtitlesWithAudio(audioElement: HTMLAudioElement, srtText: string) {
  const subtitles = parseSubtitles(srtText);
  const subtitleElement = document.getElementById('subtitle-display');
  
  audioElement.addEventListener('timeupdate', () => {
    const currentTime = audioElement.currentTime;
    const currentSubtitle = subtitles.find(
      sub => currentTime >= sub.start && currentTime <= sub.end
    );
    
    if (subtitleElement && currentSubtitle) {
      subtitleElement.textContent = currentSubtitle.text;
    } else if (subtitleElement) {
      subtitleElement.textContent = '';
    }
  });
}
```

---

## 🔄 迁移指南

### 如果你之前的代码直接处理 MP3

#### 之前:
```typescript
const response = await fetch('http://localhost:8000/generate', {...});
const audioBlob = await response.blob();
const audioUrl = URL.createObjectURL(audioBlob);
```

#### 现在:
```typescript
const response = await fetch('http://localhost:8000/generate', {...});
const zipBlob = await response.blob();

// 需要解压 ZIP
const zip = await JSZip.loadAsync(zipBlob);
const audioBlob = await zip.file('drama.mp3')?.async('blob');
const audioUrl = URL.createObjectURL(audioBlob!);
```

---

## 📊 响应头信息

新的响应包含有用的元数据：

```typescript
const headers = response.headers;
const segmentsCount = headers.get('X-Segments-Count');  // "3"
const contents = headers.get('X-Package-Contents');     // "drama.mp3,drama.srt"
```

---

## 💡 最佳实践

### 1. 缓存字幕
```typescript
// 下载后保存字幕
const srtText = await zip.file('drama.srt')?.async('text');
localStorage.setItem('lastSubtitles', srtText);
```

### 2. 提供下载选项
```typescript
// 让用户可以下载完整的 ZIP
<button onClick={() => downloadZip(zipBlob)}>
  下载完整包 (音频 + 字幕)
</button>

// 或分别下载
<button onClick={() => downloadFile(audioBlob, 'drama.mp3')}>
  下载音频
</button>
<button onClick={() => downloadFile(srtBlob, 'drama.srt')}>
  下载字幕
</button>
```

### 3. 字幕显示组件
```typescript
<div className="audio-player">
  <audio src={audioUrl} controls />
  <div className="subtitles">{currentSubtitle}</div>
</div>
```

---

## 🧪 测试新功能

```bash
# 测试端点
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Test text"}' \
  -o test_package.zip

# 解压查看
unzip -l test_package.zip
# 应该看到:
#   drama.mp3
#   drama.srt

# 查看字幕
unzip -p test_package.zip drama.srt
```

---

## ✅ 优势

1. **一次请求获取所有内容** - 不需要额外的 API 调用
2. **同步保证** - MP3 和 SRT 总是匹配的
3. **易于下载** - 用户可以下载完整包
4. **向后兼容** - 仍然可以单独提取和使用 MP3

---

*现在你的音频剧包含完整的字幕支持了！* 🎉

