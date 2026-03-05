"""
视频补帧处理流水线
完整流程: 提取音频 → 逐帧读取 → 相邻帧插值 → 写入高帧率视频 → 合并音频

补帧原理:
原始视频: F0, F1, F2, F3, ...  (N 帧, FPS_orig)

2x 补帧后: F0, I(0,1,0.5), F1, I(1,2,0.5), F2, ...
→ 输出 2N-1 帧, 帧率 = FPS_orig × 2

4x 补帧后: F0, I(0,1,0.25), I(0,1,0.5), I(0,1,0.75), F1, ...
→ 输出 4N-3 帧, 帧率 = FPS_orig × 4

视频总时长不变，音频无需变速直接合并。
"""
import os
import time
from typing import Optional, Callable

from config import TEMP_DIR, OUTPUT_DIR
from utils.ffmpeg_utils import extract_audio, merge_audio_video, get_video_info, cleanup_temp_files
from utils.video_io import read_video_frames, get_video_properties, VideoWriter
from utils.color_utils import bgr_to_rgb, rgb_to_bgr
from core.memory_manager import MemoryManager
from models.rife_interpolator import RIFEInterpolator


class FrameInterpolationProcessor:
    """
    视频补帧处理流水线
    串联所有处理步骤，支持进度回调和取消操作
    """

    def __init__(self, interpolator: RIFEInterpolator):
        """
        Args:
            interpolator: RIFE 补帧模型实例 (需已调用 load_model)
        """
        self.interpolator = interpolator
        self.memory_manager = MemoryManager(gc_interval=30)
        self._cancelled = False

    def cancel(self):
        """取消处理"""
        self._cancelled = True

    def interpolate_video(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        multiplier: int = 2,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        preview_callback: Optional[Callable] = None,
    ) -> str:
        """
        对视频进行补帧处理

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径 (默认自动生成)
            multiplier: 补帧倍率 (2 = 双倍帧率, 4 = 四倍帧率)
            progress_callback: 进度回调 (current_frame, total_frames, fps)
            preview_callback: 预览帧回调 (rgb_frame)

        Returns:
            输出视频路径，取消时返回空字符串
        """
        self._cancelled = False
        self.memory_manager.reset()

        if not self.interpolator.is_loaded:
            raise RuntimeError("RIFE 模型尚未加载")

        # ========== 1. 获取视频信息 ==========
        video_info = get_video_info(input_path)
        props = get_video_properties(input_path)
        total_frames = props["total_frames"]
        fps = props["fps"]
        w, h = props["width"], props["height"]

        new_fps = fps * multiplier
        # 预估输出总帧数: (N-1) * multiplier + 1
        estimated_output = (total_frames - 1) * multiplier + 1

        print(f"[补帧] 输入: {w}×{h} @ {fps:.2f}fps, 共 {total_frames} 帧")
        print(f"[补帧] 输出: {w}×{h} @ {new_fps:.2f}fps, 约 {estimated_output} 帧 ({multiplier}x)")

        # ========== 2. 提取音频 ==========
        audio_path = None
        if video_info["has_audio"]:
            print("[补帧] 正在提取音频...")
            audio_path = extract_audio(input_path)
            print(f"[补帧] 音频已提取: {audio_path}")

        # ========== 3. 准备输出路径 ==========
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                OUTPUT_DIR,
                f"{base_name}_interp_{multiplier}x_{int(new_fps)}fps.mp4"
            )

        temp_video_path = os.path.join(
            TEMP_DIR,
            f"temp_interp_{os.path.basename(output_path)}"
        )

        # ========== 4. 逐帧处理 ==========
        print("[补帧] 开始逐帧处理...")
        start_time = time.time()
        frame_count = 0   # 已读取的原始帧数
        written = 0        # 已写入的帧数

        with VideoWriter(temp_video_path, new_fps, w, h) as writer:
            prev_bgr = None

            for bgr_frame in read_video_frames(input_path):
                if self._cancelled:
                    print("[补帧] 处理已取消")
                    writer.release()
                    cleanup_temp_files(temp_video_path, audio_path)
                    return ""

                frame_count += 1

                if prev_bgr is None:
                    # 第一帧: 直接写入
                    writer.write_frame(bgr_frame)
                    written += 1
                    prev_bgr = bgr_frame
                    continue

                # BGR → RGB (模型需要 RGB 输入)
                prev_rgb = bgr_to_rgb(prev_bgr)
                curr_rgb = bgr_to_rgb(bgr_frame)

                # 在相邻两帧之间插入 (multiplier - 1) 个中间帧
                for j in range(1, multiplier):
                    if self._cancelled:
                        writer.release()
                        cleanup_temp_files(temp_video_path, audio_path)
                        return ""

                    t = j / multiplier
                    interp_rgb = self.interpolator.interpolate(
                        prev_rgb, curr_rgb, timestep=t
                    )
                    interp_bgr = rgb_to_bgr(interp_rgb)
                    writer.write_frame(interp_bgr)
                    written += 1

                # 写入当前原始帧
                writer.write_frame(bgr_frame)
                written += 1

                prev_bgr = bgr_frame

                # 流式内存管理
                self.memory_manager.step()

                # 进度回调
                elapsed = time.time() - start_time
                current_fps = written / elapsed if elapsed > 0 else 0
                if progress_callback:
                    progress_callback(frame_count, total_frames, current_fps)

                # 预览回调 (每 10 对帧发送一次)
                if preview_callback and (frame_count - 1) % 10 == 0:
                    preview_callback(curr_rgb)

        # ========== 5. 合并音频 ==========
        if audio_path and os.path.exists(audio_path):
            print("[补帧] 正在合并音频...")
            merge_audio_video(temp_video_path, audio_path, output_path)
            cleanup_temp_files(temp_video_path, audio_path)
        else:
            # 没有音频，直接重命名
            os.replace(temp_video_path, output_path)

        # ========== 6. 最终清理 ==========
        self.memory_manager.force_cleanup()
        elapsed_total = time.time() - start_time
        avg_fps = written / elapsed_total if elapsed_total > 0 else 0

        print(f"[补帧] 处理完成！")
        print(f"  输出: {output_path}")
        print(f"  写入帧数: {written}, 总耗时: {elapsed_total:.1f}s, 平均: {avg_fps:.2f} fps")

        return output_path
