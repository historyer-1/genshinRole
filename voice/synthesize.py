"""
角色语音合成模块。

使用 MiMo-V2.5-TTS-VoiceClone 模型，基于角色原声音频素材克隆语音。
派蒙智能体不使用此模块。

依赖预处理产物 voice/ref/ 目录下的参考音频文件。
运行 `python -m voice.preprocess` 生成。
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv

from config import TTS_MAX_TEXT_LENGTH, TTS_STYLE_PROMPT, TTS_TIMEOUT

load_dotenv()

logger = logging.getLogger(__name__)

# ── API 配置（从 .env 加载） ──
_TTS_MODEL = os.getenv("tts_model", "mimo-v2.5-tts-voiceclone")
_TTS_API_KEY = os.getenv("tts_api_key", "")
_TTS_BASE_URL = os.getenv("tts_base_url", "https://token-plan-cn.xiaomimimo.com/v1")

# ── 预处理产物目录 ──
_REF_DIR = Path(__file__).resolve().parent / "ref"

# ── 模块级状态 ──
_ref_cache: dict[str, str] = {}  # 角色名 → base64 编码的参考音频 data URI


def init_voice_map() -> list[str]:
    """
    加载预处理好的参考音频文件。

    Returns:
        可用语音的角色名列表。
    """
    global _ref_cache
    _ref_cache = {}

    if not _REF_DIR.exists():
        logger.warning("参考音频目录不存在: %s，请先运行 python -m voice.preprocess", _REF_DIR)
        return []

    for wav_file in sorted(_REF_DIR.glob("*_ref.wav")):
        role_name = wav_file.stem.removesuffix("_ref")
        try:
            b64 = base64.b64encode(wav_file.read_bytes()).decode("utf-8")
            _ref_cache[role_name] = f"data:audio/wav;base64,{b64}"
        except Exception as e:
            logger.warning("加载参考音频失败 [%s]: %s", role_name, e)

    available = list(_ref_cache.keys())
    logger.info("语音合成初始化完成，可用角色 %d 个", len(available))
    return available


def has_voice(role_name: str) -> bool:
    """检查角色是否有可用的参考音频。"""
    return role_name in _ref_cache


def get_available_roles() -> list[str]:
    """返回有可用语音的角色名列表。"""
    return list(_ref_cache.keys())


def _split_text(text: str, max_len: int = TTS_MAX_TEXT_LENGTH) -> list[str]:
    """
    将长文本按句子边界分段。

    Args:
        text: 待分段文本。
        max_len: 单段最大字符数。
    """
    if len(text) <= max_len:
        return [text]

    segments: list[str] = []
    current = ""
    for part in re.split(r"([。！？…]+)", text):
        if len(current) + len(part) > max_len and current:
            segments.append(current)
            current = ""
        current += part
    if current:
        segments.append(current)
    return segments


async def _call_tts(text: str, ref_audio: str, role_name: str) -> bytes:
    """
    调用 MiMo TTS API 合成语音。

    Args:
        text: 待合成文本。
        ref_audio: 参考音频 data URI。
        role_name: 角色名称，用于生成风格提示词。

    Returns:
        WAV 格式的合成音频字节。
    """
    url = f"{_TTS_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "api-key": _TTS_API_KEY,
    }
    payload = {
        "model": _TTS_MODEL,
        "messages": [
            {"role": "user", "content": TTS_STYLE_PROMPT.format(role_name=role_name)},
            {"role": "assistant", "content": text},
        ],
        "audio": {
            "format": "wav",
            "voice": ref_audio,
        },
    }

    async with httpx.AsyncClient(timeout=TTS_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    audio_b64 = data["choices"][0]["message"]["audio"]["data"]
    return base64.b64decode(audio_b64)


def _concat_wav(wav_parts: list[bytes]) -> bytes:
    """
    拼接多个 WAV 音频（假设格式一致：24kHz, mono, 16bit）。

    Args:
        wav_parts: WAV 音频字节列表。
    """
    if len(wav_parts) == 1:
        return wav_parts[0]

    with wave.open(io.BytesIO(wav_parts[0]), "rb") as w:
        params = w.getparams()

    output = io.BytesIO()
    with wave.open(output, "wb") as out:
        out.setparams(params)
        for part in wav_parts:
            with wave.open(io.BytesIO(part), "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))

    return output.getvalue()


async def synthesize_voice(text: str, role_name: str) -> bytes:
    """
    为指定角色合成语音。

    Args:
        text: 待合成的文本内容。
        role_name: 角色名称（中文）。

    Returns:
        WAV 格式的合成音频字节。

    Raises:
        ValueError: 角色无可用参考音频。
        RuntimeError: TTS API 调用失败。
    """
    if role_name not in _ref_cache:
        raise ValueError(f"角色 [{role_name}] 无可用的参考音频")

    ref_audio = _ref_cache[role_name]
    segments = _split_text(text)

    if len(segments) == 1:
        return await _call_tts(segments[0], ref_audio, role_name)

    wav_parts = [await _call_tts(seg, ref_audio, role_name) for seg in segments]
    return _concat_wav(wav_parts)
