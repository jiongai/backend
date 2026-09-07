"""
DramaFlow API 自动化回归与连通性测试套件
验证当前服务的全部活跃端点：/health, /voices, /assign_voices, /review, /synthesize
"""

import os
import sys
import requests
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv(override=True)

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("DARMAFLOW_API_ACCESS_SECRET", "")

HEADERS = {
    "Content-Type": "application/json"
}
if SECRET_KEY:
    HEADERS["X-Access-Secret"] = SECRET_KEY

# 模拟测试剧本
SAMPLE_SCRIPT = [
    {
        "type": "narration",
        "text": "The wind howled softly across the old empty hills.",
        "character": "Narrator",
        "gender": "neutral",
        "emotion": "neutral",
        "pacing": 1.0,
        "voice_id": ""
    },
    {
        "type": "dialogue",
        "text": "Is anyone still out there?",
        "character": "Sarah",
        "gender": "female",
        "emotion": "fearful",
        "pacing": 1.0,
        "voice_id": ""
    },
    {
        "type": "dialogue",
        "text": "Don't worry, I'm right behind you.",
        "character": "John",
        "gender": "male",
        "emotion": "neutral",
        "pacing": 1.0,
        "voice_id": ""
    }
]


def test_health():
    """测试 1: 健康检查端点"""
    print("\n🔍 [1/5] 测试 GET /health ...")
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ 健康检查通过: status={data.get('status')}")
            print(f"   ElevenLabs 就绪: {data.get('elevenlabs_configured')}")
            return True
        else:
            print(f"❌ 健康检查失败: HTTP {res.status_code} - {res.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 无法访问 {BASE_URL}，请确保服务已启动 (uvicorn app.main:app)")
        return False


def test_voices():
    """测试 2: 获取音色目录 (支持语言过滤)"""
    print("\n🔍 [2/5] 测试 GET /voices ...")
    res = requests.get(f"{BASE_URL}/voices?languages=en&languages=zh", headers=HEADERS, timeout=10)
    if res.status_code == 200:
        data = res.json()
        voice_map = data.get("voice_map", {})
        has_basic = "Basic" in voice_map
        has_advance = "Advance" in voice_map
        print(f"✅ 音色列表获取成功 (Basic: {has_basic}, Advance: {has_advance})")
        print(f"   支持的情感配置项数量: {len(data.get('emotion_settings', {}))}")
        return True
    else:
        print(f"❌ 获取音色失败: HTTP {res.status_code} - {res.text}")
        return False


def test_assign_voices():
    """测试 3: 智能音色分配 (Magic Fill)"""
    print("\n🔍 [3/5] 测试 POST /assign_voices ...")
    payload = {
        "script": SAMPLE_SCRIPT
    }
    res = requests.post(f"{BASE_URL}/assign_voices?languages=en", json=payload, headers=HEADERS, timeout=15)
    if res.status_code == 200:
        data = res.json()
        enriched_script = data.get("script", [])
        print(f"✅ 音色分配成功，共处理 {len(enriched_script)} 个片段")
        for seg in enriched_script:
            print(f"   • [{seg.get('character')}] -> {seg.get('voice_id')}")
        return enriched_script
    else:
        print(f"❌ 音色分配失败: HTTP {res.status_code} - {res.text}")
        return None


def test_review():
    """测试 4: 单句快速试听 (返回二进制音频流)"""
    print("\n🔍 [4/5] 测试 POST /review ...")
    payload = {
        "text": "Hello, testing DramaFlow review.",
        "voice_id": "google:en-US-Neural2-J",
        "pacing": 1.0,
        "emotion": "neutral"
    }
    try:
        res = requests.post(f"{BASE_URL}/review", json=payload, headers=HEADERS, timeout=20)
        if res.status_code == 200 and "audio" in res.headers.get("Content-Type", ""):
            audio_size = len(res.content)
            print(f"✅ 试听音频生成成功: {audio_size} bytes (audio/mpeg)")
            return True
        else:
            print(f"⚠️ 试听接口返回: HTTP {res.status_code} (可能未配置对应 TTS 凭证或网络波动: {res.text[:100]})")
            return False
    except Exception as e:
        print(f"⚠️ 试听接口异常: {e}")
        return False


def test_synthesize_dry_run():
    """测试 5: 合成流水线探测 (limit=0 探测管道)"""
    print("\n🔍 [5/5] 测试 POST /synthesize (Dry Run: limit=0) ...")
    payload = {
        "script": SAMPLE_SCRIPT,
        "limit": 0
    }
    res = requests.post(f"{BASE_URL}/synthesize", json=payload, headers=HEADERS, timeout=15)
    if res.status_code == 200:
        data = res.json()
        print(f"✅ 合成流水线校验成功: {data.get('message')}")
        return True
    else:
        print(f"❌ 合成流水线请求失败: HTTP {res.status_code} - {res.text}")
        return False


def main():
    print("=" * 60)
    print("🎭 DramaFlow API 自动化回归验证套件")
    print(f"目标地址: {BASE_URL}")
    print(f"安全密钥配置状态: {'已配置' if SECRET_KEY else '未配置 (请确认服务端是否放行)'}")
    print("=" * 60)

    if not test_health():
        print("\n❌ 服务未启动或健康检查未通过，测试终止。")
        sys.exit(1)

    voices_ok = test_voices()
    assign_ok = bool(test_assign_voices())
    synth_ok = test_synthesize_dry_run()
    review_ok = test_review()

    print("\n" + "=" * 60)
    print("📊 测试执行汇总:")
    print(f"  • GET /health         : ✅ 通过")
    print(f"  • GET /voices         : {'✅ 通过' if voices_ok else '❌ 失败'}")
    print(f"  • POST /assign_voices : {'✅ 通过' if assign_ok else '❌ 失败'}")
    print(f"  • POST /synthesize    : {'✅ 通过' if synth_ok else '❌ 失败'}")
    print(f"  • POST /review        : {'✅ 通过' if review_ok else '⚠️ 跳过/依赖TTS凭证'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
