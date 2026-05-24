#!/usr/bin/env python3
"""
Audio transcription script using SiliconFlow API (硅基流动, 国内直连).

Usage:
    python3 transcribe.py <SILICONFLOW_API_KEY> /path/to/audio.wav

Requires: ffmpeg for format conversion (auto-detected)
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import requests

# 硅基流动 API (国内直连)
API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "FunAudioLLM/SenseVoiceSmall"

FFMPEG = "ffmpeg"


def _get_proxies():
    for env_key in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(env_key)
        if val:
            return {"https": val, "http": val}
    return None


PROXIES = _get_proxies()


def convert_to_wav_if_needed(input_path, output_path="/tmp/transcribe_temp.wav"):
    if str(input_path).lower().endswith('.wav'):
        return input_path

    try:
        subprocess.run(
            [FFMPEG, "-y", "-i", str(input_path),
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
             str(output_path)],
            capture_output=True, check=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting audio: {e.stderr.decode()}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("ffmpeg not available, uploading original file", file=sys.stderr)
        return input_path


def transcribe_with_siliconflow(audio_path, api_key):
    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": audio_file},
                data={"model": MODEL, "response_format": "text"},
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


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files using SiliconFlow API"
    )
    parser.add_argument("api_key", help="SiliconFlow API key")
    parser.add_argument("audio_file", help="Path to audio file (ogg, mp3, wav, m4a, etc.)")
    args = parser.parse_args()

    input_path = Path(args.audio_file)
    if not input_path.exists():
        print(f"Error: File not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    # Check ffmpeg
    try:
        subprocess.run([FFMPEG, "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: ffmpeg not found, only WAV files supported", file=sys.stderr)

    # Convert to WAV if needed
    audio_path = convert_to_wav_if_needed(input_path)
    if not audio_path:
        sys.exit(1)

    # Transcribe
    print(f"Using SiliconFlow API ({MODEL})...", file=sys.stderr)
    text, error = transcribe_with_siliconflow(audio_path, args.api_key)

    # Cleanup temp file
    temp_file = "/tmp/transcribe_temp.wav"
    if audio_path != str(input_path) and os.path.exists(temp_file):
        os.remove(temp_file)

    if text:
        print("✓ SiliconFlow API succeeded", file=sys.stderr)
        print(text)
    else:
        print(f"✗ SiliconFlow API failed: {error}", file=sys.stderr)
        print("[No transcription detected]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
