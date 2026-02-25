"""验证所有模块导入"""
import sys
sys.path.insert(0, '.')

from config import MODELS, WEIGHTS_DIR, TEMP_DIR, OUTPUT_DIR
print('config OK, models:', list(MODELS.keys()))

from utils.ffmpeg_utils import get_video_info, extract_audio, merge_audio_video
print('ffmpeg_utils OK')

from utils.video_io import read_video_frames, VideoWriter, get_video_properties
print('video_io OK')

from utils.color_utils import bgr_to_rgb, rgb_to_bgr, frame_to_tensor, tensor_to_frame
print('color_utils OK')

from core.tiling import tile_process, estimate_tile_size
print('tiling OK')

from core.memory_manager import MemoryManager
mm = MemoryManager()
info = mm.get_gpu_memory_info()
print(f'memory_manager OK, GPU: {info["device_name"]}, {info["total_mb"]:.0f}MB')

from core.video_processor import VideoProcessor
print('video_processor OK')

from core.worker_thread import VideoWorkerThread, PreviewWorkerThread
print('worker_thread OK')

from models.base_enhancer import BaseEnhancer
print('base_enhancer OK')

from models.realesrgan_enhancer import RealESRGANEnhancer
print('realesrgan_enhancer OK')

from models.gfpgan_enhancer import GFPGANEnhancer
print('gfpgan_enhancer OK')

# 测试 Tiling 算法
import torch
print(f'\nTiling 推荐块大小 (16GB显存): {estimate_tile_size(1080, 1920, scale=4, gpu_memory_gb=16)}px')

print('\n=== 所有模块导入成功! ===')
