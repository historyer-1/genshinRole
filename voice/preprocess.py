"""
语音素材预处理脚本。

扫描声音素材目录中的 MP3 文件，清洗文件名后：
1. 转换为完整时长 WAV，保存到 voice/wav/{角色名}.wav
2. 从中间截取 60 秒参考音频，保存到 voice/ref/{角色名}_ref.wav

使用方式:
    python -m voice.preprocess
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

from config import SOUND_DIR, TTS_REF_DURATION

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# 输出目录
VOICE_DIR = Path(__file__).resolve().parent
WAV_DIR = VOICE_DIR / "wav"
REF_DIR = VOICE_DIR / "ref"


def _extract_char_name(filename: str) -> str | None:
    """
    从声音文件名中提取角色名。

    文件名格式: {序号}.{角色名}({版本标注})(Av...,P{序号}).mp3
    """
    stem = Path(filename).stem
    m = re.match(r"\d+\.(.+?)\(", stem)
    if m:
        return m.group(1).strip()
    return None


def _get_duration(mp3_path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）。"""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {r.stderr}")
    return float(r.stdout.strip())


def _convert_to_wav(mp3_path: Path, wav_path: Path) -> None:
    """将 MP3 转换为 WAV（24kHz, mono, 16bit）。"""
    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-ar", "24000", "-ac", "1", "-sample_fmt", "s16",
        str(wav_path),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 转换失败: {r.stderr.decode(errors='replace')}")


def _extract_ref_clip(mp3_path: Path, ref_path: Path, duration: float) -> None:
    """从 MP3 中间截取指定时长的 WAV 片段。"""
    clip_len = min(TTS_REF_DURATION, duration)
    start = max(0, (duration - clip_len) / 2)
    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-ss", str(start), "-t", str(clip_len),
        "-ar", "24000", "-ac", "1", "-sample_fmt", "s16",
        str(ref_path),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 截取失败: {r.stderr.decode(errors='replace')}")


def preprocess_all() -> None:
    """扫描所有 MP3 文件，转换 WAV 并截取参考音频。"""
    WAV_DIR.mkdir(exist_ok=True)
    REF_DIR.mkdir(exist_ok=True)

    sound_dir = Path(SOUND_DIR)
    if not sound_dir.exists():
        logger.error("声音素材目录不存在: %s", sound_dir)
        sys.exit(1)

    mp3_files = sorted(sound_dir.rglob("*.mp3"))
    logger.info("找到 %d 个 MP3 文件", len(mp3_files))

    success, skip, fail = 0, 0, 0
    for mp3 in mp3_files:
        char_name = _extract_char_name(mp3.name)
        if not char_name:
            logger.info("跳过（无法提取角色名）: %s", mp3.name)
            skip += 1
            continue

        wav_path = WAV_DIR / f"{char_name}.wav"
        ref_path = REF_DIR / f"{char_name}_ref.wav"

        # 同名文件已存在则跳过（支持增量处理）
        if wav_path.exists() and ref_path.exists():
            logger.info("已存在，跳过: %s", char_name)
            skip += 1
            continue

        try:
            duration = _get_duration(mp3)
            logger.info("处理: %s (%.1f秒) → %s", char_name, duration, mp3.name)

            if not wav_path.exists():
                _convert_to_wav(mp3, wav_path)
            if not ref_path.exists():
                _extract_ref_clip(mp3, ref_path, duration)

            success += 1
        except Exception as e:
            logger.error("失败 [%s]: %s", char_name, e)
            fail += 1

    logger.info("预处理完成: 成功 %d, 跳过 %d, 失败 %d", success, skip, fail)


if __name__ == "__main__":
    preprocess_all()
