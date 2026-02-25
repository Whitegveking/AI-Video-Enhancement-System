"""
全局配置文件
定义路径、默认参数、模型配置等
"""
import os

# ===================== 路径配置 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 确保目录存在
for _dir in [WEIGHTS_DIR, TEMP_DIR, OUTPUT_DIR]:
    os.makedirs(_dir, exist_ok=True)

# ===================== FFmpeg 配置 =====================
FFMPEG_BIN = "ffmpeg"  # 系统 PATH 中的 ffmpeg

# ===================== 模型配置 =====================
MODELS = {
    "RealESRGAN_x4": {
        "name": "RealESRGAN_x4plus",
        "scale": 4,
        "weight_file": "RealESRGAN_x4plus.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "description": "通用场景4倍超分辨率",
    },
    "RealESRGAN_x2": {
        "name": "RealESRGAN_x2plus",
        "scale": 2,
        "weight_file": "RealESRGAN_x2plus.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "description": "通用场景2倍超分辨率",
    },
    "RealESRGAN_x4_Anime": {
        "name": "RealESRGAN_x4plus_anime_6B",
        "scale": 4,
        "weight_file": "RealESRGAN_x4plus_anime_6B.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "description": "动漫场景4倍超分辨率",
    },
    "GFPGAN_v1.4": {
        "name": "GFPGANv1.4",
        "scale": 2,
        "weight_file": "GFPGANv1.4.pth",
        "weight_url": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        "description": "人脸修复与增强",
    },
}

# ===================== 处理参数默认值 =====================
DEFAULT_TILE_SIZE = 512       # 分块大小
DEFAULT_TILE_PAD = 32         # 分块重叠填充
DEFAULT_SCALE = 4             # 默认放大倍率
DEFAULT_DENOISE = 0.5         # 默认降噪强度 (0~1)
DEFAULT_MODEL = "RealESRGAN_x4"

# ===================== 支持的视频格式 =====================
SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mkv", ".flv", ".mov", ".wmv", ".webm"]

# ===================== 视频编码配置 =====================
VIDEO_CODEC = "libx264"       # 输出视频编码器
VIDEO_CRF = "18"              # 质量因子 (越低质量越高, 0=无损)
VIDEO_PRESET = "medium"       # 编码速度预设
