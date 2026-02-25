"""
端到端测试 - 使用 Real-ESRGAN 处理测试视频
输入: 320x240 → 输出: 1280x960 (4x)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.realesrgan_enhancer import RealESRGANEnhancer
from core.video_processor import VideoProcessor

def main():
    input_path = "test_input.mp4"
    if not os.path.exists(input_path):
        print("测试视频不存在，请先生成 test_input.mp4")
        return

    # 1. 加载模型
    print("=" * 50)
    print("加载 Real-ESRGAN x4 模型...")
    enhancer = RealESRGANEnhancer()
    enhancer.load_model(model_key="RealESRGAN_x4", half=True)

    # 2. 处理视频
    print("=" * 50)
    processor = VideoProcessor(enhancer)
    output = processor.process_video(
        input_path=input_path,
        use_tiling=True,
        tile_size=512,
        tile_pad=32,
        progress_callback=lambda cur, total, fps: print(
            f"\r  进度: {cur}/{total} ({cur*100//total}%) | {fps:.1f} fps", end="", flush=True
        ),
    )

    print()
    print("=" * 50)
    if output and os.path.exists(output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"测试通过! 输出: {output} ({size_mb:.1f} MB)")

        # 验证输出视频属性
        from utils.video_io import get_video_properties
        props = get_video_properties(output)
        print(f"输出分辨率: {props['width']}x{props['height']}")
        print(f"帧率: {props['fps']}, 帧数: {props['total_frames']}")
    else:
        print("测试失败!")

    # 3. 释放模型
    enhancer.release()

if __name__ == "__main__":
    main()
