"""
视频处理流水线 - 核心协调器
完整流程: 提取音频 → 逐帧读取 → BGR→RGB → AI推理(Tiling) → RGB→BGR → 写帧 → 合并音频
"""
import os
import time
from typing import Optional, Callable

from config import TEMP_DIR, OUTPUT_DIR, DEFAULT_TILE_SIZE, DEFAULT_TILE_PAD
from utils.ffmpeg_utils import extract_audio, merge_audio_video, get_video_info, cleanup_temp_files
from utils.video_io import read_video_frames, get_video_properties, VideoWriter
from utils.color_utils import bgr_to_rgb, rgb_to_bgr
from core.memory_manager import MemoryManager
from models.base_enhancer import BaseEnhancer


class VideoProcessor:
    """
    视频增强处理流水线
    串联所有处理步骤，支持进度回调和取消操作
    """

    def __init__(self, enhancer: BaseEnhancer):
        """
        Args:
            enhancer: AI 增强模型实例（需已调用 load_model）
        """
        self.enhancer = enhancer
        self.memory_manager = MemoryManager(gc_interval=30)
        self._cancelled = False

    def cancel(self):
        """取消处理"""
        self._cancelled = True

    def process_video(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        use_tiling: bool = True,
        tile_size: int = DEFAULT_TILE_SIZE,
        tile_pad: int = DEFAULT_TILE_PAD,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        preview_callback: Optional[Callable] = None,
    ) -> str:
        """
        处理完整视频

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径（默认自动生成）
            use_tiling: 是否使用分块处理
            tile_size: 分块大小
            tile_pad: 分块重叠填充
            progress_callback: 进度回调 (current_frame, total_frames, fps)
            preview_callback: 预览帧回调 (rgb_frame)

        Returns:
            输出视频路径
        """
        self._cancelled = False
        self.memory_manager.reset()

        if not self.enhancer.is_loaded:
            raise RuntimeError("模型尚未加载")

        # ========== 1. 获取视频信息 ==========
        video_info = get_video_info(input_path)
        props = get_video_properties(input_path)
        total_frames = props["total_frames"]
        fps = props["fps"]
        in_w, in_h = props["width"], props["height"]
        out_w = in_w * self.enhancer.scale
        out_h = in_h * self.enhancer.scale

        print(f"[流水线] 输入: {in_w}x{in_h} @ {fps:.2f}fps, 共 {total_frames} 帧")
        print(f"[流水线] 输出: {out_w}x{out_h}, 模型: {self.enhancer.model_name}, scale={self.enhancer.scale}")

        # ========== 2. 提取音频 ==========
        audio_path = None
        if video_info["has_audio"]:
            print("[流水线] 正在提取音频...")
            audio_path = extract_audio(input_path)
            print(f"[流水线] 音频已提取: {audio_path}")

        # ========== 3. 准备输出路径 ==========
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                OUTPUT_DIR,
                f"{base_name}_enhanced_{self.enhancer.scale}x.mp4"
            )

        # 临时无声视频路径
        temp_video_path = os.path.join(
            TEMP_DIR,
            f"temp_nosound_{os.path.basename(output_path)}"
        )

        # ========== 4. 逐帧处理 ==========
        print("[流水线] 开始逐帧处理...")
        start_time = time.time()
        processed = 0

        with VideoWriter(temp_video_path, fps, out_w, out_h) as writer:
            for bgr_frame in read_video_frames(input_path):
                if self._cancelled:
                    print("[流水线] 处理已取消")
                    writer.release()
                    cleanup_temp_files(temp_video_path, audio_path)
                    return ""

                # BGR -> RGB (模型需要 RGB 输入)
                rgb_frame = bgr_to_rgb(bgr_frame)

                # AI 推理
                if use_tiling:
                    enhanced_rgb = self.enhancer.enhance_with_tiling(
                        rgb_frame, tile_size, tile_pad
                    )
                else:
                    enhanced_rgb = self.enhancer.enhance_frame(rgb_frame)

                # RGB -> BGR (OpenCV 写入需要 BGR)
                enhanced_bgr = rgb_to_bgr(enhanced_rgb)

                # 写入帧
                writer.write_frame(enhanced_bgr)

                # 流式内存管理
                self.memory_manager.step()

                # 进度回调
                processed += 1
                elapsed = time.time() - start_time
                current_fps = processed / elapsed if elapsed > 0 else 0

                if progress_callback:
                    progress_callback(processed, total_frames, current_fps)

                # 预览回调（每20帧发送一次预览）
                if preview_callback and processed % 20 == 0:
                    preview_callback(enhanced_rgb)

        # ========== 5. 合并音频 ==========
        if audio_path and os.path.exists(audio_path):
            print("[流水线] 正在合并音频...")
            merge_audio_video(temp_video_path, audio_path, output_path)
            cleanup_temp_files(temp_video_path, audio_path)
        else:
            # 没有音频，直接用临时视频作为输出
            os.replace(temp_video_path, output_path)

        # ========== 6. 最终清理 ==========
        self.memory_manager.force_cleanup()
        elapsed_total = time.time() - start_time
        avg_fps = processed / elapsed_total if elapsed_total > 0 else 0

        print(f"[流水线] 处理完成！")
        print(f"  输出: {output_path}")
        print(f"  总帧数: {processed}, 总耗时: {elapsed_total:.1f}s, 平均: {avg_fps:.2f} fps")

        return output_path

    def process_single_frame(
        self,
        input_path: str,
        frame_index: int = 0,
        use_tiling: bool = True,
        tile_size: int = DEFAULT_TILE_SIZE,
        tile_pad: int = DEFAULT_TILE_PAD,
    ):
        """
        处理单帧（用于预览功能）

        Args:
            input_path: 视频路径
            frame_index: 帧索引
            use_tiling: 是否使用分块
            tile_size: 分块大小
            tile_pad: 分块填充

        Returns:
            (原始RGB帧, 增强RGB帧) 元组
        """
        from utils.video_io import read_single_frame

        bgr_frame = read_single_frame(input_path, frame_index)
        if bgr_frame is None:
            raise RuntimeError(f"无法读取第 {frame_index} 帧")

        rgb_frame = bgr_to_rgb(bgr_frame)

        if use_tiling:
            enhanced_rgb = self.enhancer.enhance_with_tiling(
                rgb_frame, tile_size, tile_pad
            )
        else:
            enhanced_rgb = self.enhancer.enhance_frame(rgb_frame)

        return rgb_frame, enhanced_rgb
