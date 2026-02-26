"""
FFmpeg 音视频处理工具封装
负责音频提取、视频合并、格式转换等操作
"""
import os
import subprocess
import json
from typing import Optional, Dict, Any

from config import FFMPEG_BIN, TEMP_DIR


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    获取视频文件的详细信息（分辨率、帧率、时长、编码格式等）

    Args:
        video_path: 视频文件路径

    Returns:
        包含视频信息的字典
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        probe_data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"无法读取视频信息: {e}")

    info = {
        "path": video_path,
        "filename": os.path.basename(video_path),
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "total_frames": 0,
        "duration": 0.0,
        "video_codec": "",
        "audio_codec": "",
        "has_audio": False,
        "file_size": os.path.getsize(video_path),
    }

    # 解析视频流
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = int(stream.get("width", 0))
            info["height"] = int(stream.get("height", 0))
            info["video_codec"] = stream.get("codec_name", "")
            # 解析帧率 (如 "30000/1001")
            fps_str = stream.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                info["fps"] = float(num) / float(den) if float(den) != 0 else 0.0
            else:
                info["fps"] = float(fps_str)
            info["total_frames"] = int(stream.get("nb_frames", 0))
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
            info["audio_codec"] = stream.get("codec_name", "")

    # 解析时长
    fmt = probe_data.get("format", {})
    info["duration"] = float(fmt.get("duration", 0.0))

    # 如果 nb_frames 没拿到，用时长*帧率估算
    if info["total_frames"] == 0 and info["fps"] > 0 and info["duration"] > 0:
        info["total_frames"] = int(info["fps"] * info["duration"])

    return info


def extract_audio(video_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    从视频中提取音频流（无损提取，不重新编码）

    Args:
        video_path: 源视频路径
        output_path: 音频输出路径，默认存到 temp 目录

    Returns:
        音频文件路径，如果视频无音频返回 None
    """
    # 检查是否有音频
    info = get_video_info(video_path)
    if not info["has_audio"]:
        return None

    if output_path is None:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(TEMP_DIR, f"{base_name}_audio.aac")

    cmd = [
        FFMPEG_BIN,
        "-y",                   # 覆盖输出文件
        "-i", video_path,
        "-vn",                  # 不处理视频流
        "-acodec", "copy",      # 无损复制音频流
        output_path
    ]

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"音频提取失败: {e.stderr}")

    return output_path


def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str
) -> str:
    """
    将无声视频与音频无损合并

    Args:
        video_path: 无声视频文件路径
        audio_path: 音频文件路径
        output_path: 输出文件路径

    Returns:
        输出文件路径
    """
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",         # 视频流直接复制（不重新编码）
        "-c:a", "copy",         # 音频流直接复制
        "-shortest",            # 以较短的流为准
        output_path
    ]

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"音视频合并失败: {e.stderr}")

    return output_path


def encode_video_from_frames(
    frames_dir: str,
    output_path: str,
    fps: float,
    crf: str = "18",
    preset: str = "medium",
    codec: str = "libx264",
) -> str:
    """
    将一系列帧图片编码为视频（备用方案，主流程使用 OpenCV VideoWriter）

    Args:
        frames_dir: 帧图片目录（按序号命名: 00001.png, 00002.png, ...）
        output_path: 输出视频路径
        fps: 帧率
        crf: 质量因子
        preset: 编码速度预设
        codec: 视频编码器

    Returns:
        输出视频路径
    """
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "%05d.png"),
        "-c:v", codec,
        "-crf", crf,
        "-preset", preset,
        "-pix_fmt", "yuv420p",  # 兼容性最好的像素格式
        output_path
    ]

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"视频编码失败: {e.stderr}")

    return output_path


def cleanup_temp_files(*file_paths: str):
    """清理临时文件"""
    for fp in file_paths:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
