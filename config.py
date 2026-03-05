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
    "Auto": {
        "name": "Auto",
        "icon": "✨",
        "display_name": "智能自动选择",
        "scale": 4,
        "weight_file": "",
        "weight_url": "",
        "description": "根据视频内容自动选择最佳模型",
    },
    "RealESRGAN_x4": {
        "name": "RealESRGAN_x4plus",
        "icon": "🌄",
        "display_name": "通用超分 (4x)",
        "scale": 4,
        "weight_file": "RealESRGAN_x4plus.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "description": "风景/建筑/自然场景等通用画质增强",
    },
    "RealESRGAN_x2": {
        "name": "RealESRGAN_x2plus",
        "icon": "🖼️",
        "display_name": "轻度超分 (2x)",
        "scale": 2,
        "weight_file": "RealESRGAN_x2plus.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "description": "轻度放大，保留更多原始细节",
    },
    "RealESRGAN_x4_Anime": {
        "name": "RealESRGAN_x4plus_anime_6B",
        "icon": "🎬",
        "display_name": "动漫超分 (4x)",
        "scale": 4,
        "weight_file": "RealESRGAN_x4plus_anime_6B.pth",
        "weight_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "description": "专为动漫/卡通风格优化",
    },
    "GFPGAN_v1.4": {
        "name": "GFPGANv1.4",
        "icon": "👤",
        "display_name": "人像修复",
        "scale": 2,
        "weight_file": "GFPGANv1.4.pth",
        "weight_url": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        "description": "人脸修复与美化，还原五官细节",
    },
}

# ===================== 处理参数默认值 =====================
DEFAULT_TILE_SIZE = 512       # 分块大小
DEFAULT_TILE_PAD = 32         # 分块重叠填充
DEFAULT_SCALE = 4             # 默认放大倍率
DEFAULT_DENOISE = 0.5         # 默认降噪强度 (0~1)
DEFAULT_MODEL = "RealESRGAN_x4"

# ===================== 补帧配置 =====================
RIFE_MODEL = {
    "name": "RIFE_v4",
    "icon": "🎞️",
    "display_name": "RIFE v4 补帧",
    "weight_file": "flownet.pkl",
    "weight_url": "https://github.com/hzwer/Practical-RIFE",
    "description": "基于 RIFE 光流估计的实时视频补帧",
}
DEFAULT_INTERP_MULTI = 2      # 默认补帧倍率 (2x / 4x)

# ===================== 支持的视频格式 =====================
SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mkv", ".flv", ".mov", ".wmv", ".webm"]

# ===================== 视频编码配置 =====================
VIDEO_CODEC = "libx264"       # 输出视频编码器
VIDEO_CRF = "18"              # 质量因子 (越低质量越高, 0=无损)
VIDEO_PRESET = "medium"       # 编码速度预设
