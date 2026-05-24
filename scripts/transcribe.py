#!/usr/bin/env python3
"""
Audio transcription script using Groq API or SiliconFlow (国内可访问).

Requires: GROQ_API_KEY or SILICONFLOW_API_KEY environment variable
Optional: ffmpeg for format conversion (auto-detected)

Usage:
    export GROQ_API_KEY="your-key"           # Groq API (需要翻墙)
    export SILICONFLOW_API_KEY="your-key"    # 硅基流动 API (国内直连)
    python3 transcribe.py /path/to/audio.ogg

Output: Transcribed text to stdout

API Priority:
    1. SILICONFLOW_API_KEY (priority, works in China)
    2. GROQ_API_KEY (fallback, needs VPN)
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import requests

# Groq API (需要翻墙)
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"

# 硅基流动 API (国内直连)
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_MODEL = "FunAudioLLM/SenseVoiceSmall"  # 硅基流动推荐的中文语音模型

FFMPEG = "ffmpeg"


# Proxy support: only use proxy if explicitly set via environment variables
def _get_proxies():
    """Only use proxy if user explicitly set HTTPS_PROXY/HTTP_PROXY env vars."""
    for env_key in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(env_key)
        if val:
            return {"https": val, "http": val}
    return None


PROXIES = _get_proxies()


def check_dependencies():
    """Check if required tools and API keys are available."""
    groq_key = os.environ.get("GROQ_API_KEY")
    siliconflow_key = os.environ.get("SILICONFLOW_API_KEY")

    if not groq_key and not siliconflow_key:
        print("Error: No API key found", file=sys.stderr)
        print("Set one of:", file=sys.stderr)
        print("  export GROQ_API_KEY='your-key'           # Groq API (需要翻墙)", file=sys.stderr)
        print("  export SILICONFLOW_API_KEY='your-key'    # 硅基流动 API (国内直连)", file=sys.stderr)
        print("", file=sys.stderr)
        print("获取 API Key:", file=sys.stderr)
        print("  Groq: https://console.groq.com", file=sys.stderr)
        print("  硅基流动: https://cloud.siliconflow.cn", file=sys.stderr)
        return False

    # Check for ffmpeg (optional but recommended for format conversion)
    try:
        subprocess.run([FFMPEG, "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: ffmpeg not found", file=sys.stderr)
        print("Install with: brew install ffmpeg", file=sys.stderr)
        print("Without ffmpeg, only WAV files are supported", file=sys.stderr)

    return True


def convert_to_wav_if_needed(input_path, output_path="/tmp/transcribe_temp.wav"):
    """Convert audio file to WAV format if needed (for ffmpeg support)."""
    # If already WAV, return as-is
    if str(input_path).lower().endswith('.wav'):
        return input_path

    # Try ffmpeg conversion
    try:
        subprocess.run(
            [
                FFMPEG, "-y", "-i", str(input_path),
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(output_path)
            ],
            capture_output=True,
            check=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting audio: {e.stderr.decode()}", file=sys.stderr)
        return None
    except FileNotFoundError:
        # No ffmpeg available - try direct upload
        print("ffmpeg not available, uploading original file", file=sys.stderr)
        return input_path


def transcribe_with_groq(audio_path):
    """Transcribe audio file using Groq API."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None, "GROQ_API_KEY not set"

    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}"
                },
                files={
                    "file": audio_file
                },
                data={
                    "model": GROQ_MODEL,
                    "response_format": "text",
                    "language": "zh"
                },
                proxies=PROXIES,
                timeout=30
            )

        response.raise_for_status()
        return response.text.strip(), None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response:
            error_msg = f"{e} - API response: {e.response.text}"
        return None, f"Groq API error: {error_msg}"


def transcribe_with_siliconflow(audio_path):
    """Transcribe audio file using SiliconFlow API (国内直连)."""
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        return None, "SILICONFLOW_API_KEY not set"

    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                SILICONFLOW_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}"
                },
                files={
                    "file": audio_file
                },
                data={
                    "model": SILICONFLOW_MODEL,
                    "response_format": "text"
                },
                proxies=PROXIES,
                timeout=60
            )

        response.raise_for_status()
        return response.text.strip(), None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response:
            error_msg = f"{e} - API response: {e.response.text}"
        return None, f"SiliconFlow API error: {error_msg}"


def transcribe(audio_path):
    """Transcribe audio file, trying SiliconFlow first, then Groq as fallback."""
    # Try SiliconFlow first (国内直连, 优先)
    siliconflow_key = os.environ.get("SILICONFLOW_API_KEY")
    if siliconflow_key:
        print("Using SiliconFlow API...", file=sys.stderr)
        text, error = transcribe_with_siliconflow(audio_path)
        if text:
            print("✓ SiliconFlow API succeeded", file=sys.stderr)
            return text
        print(f"✗ SiliconFlow API failed: {error}", file=sys.stderr)
        print("Falling back to Groq...", file=sys.stderr)

    # Try Groq (fallback)
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        print("Trying Groq API...", file=sys.stderr)
        text, error = transcribe_with_groq(audio_path)
        if text:
            print("✓ Groq API succeeded", file=sys.stderr)
            return text
        print(f"✗ Groq API failed: {error}", file=sys.stderr)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using Groq or SiliconFlow API"
    )
    parser.add_argument("audio_file", help="Path to audio file (ogg, mp3, wav, m4a, etc.)")
    args = parser.parse_args()

    if not check_dependencies():
        sys.exit(1)

    input_path = Path(args.audio_file)
    if not input_path.exists():
        print(f"Error: File not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    # Convert to WAV if needed (for ffmpeg support)
    audio_path = convert_to_wav_if_needed(input_path)
    if not audio_path:
        sys.exit(1)

    # Transcribe using available API
    text = transcribe(audio_path)

    # Cleanup temp file if we created one
    temp_file = "/tmp/transcribe_temp.wav"
    if audio_path != str(input_path) and os.path.exists(temp_file):
        os.remove(temp_file)

    if text:
        print(text)
    else:
        print("[No transcription detected]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
