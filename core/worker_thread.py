"""
QThread 后台工作线程
将耗时的 AI 推理任务放到后台线程执行，通过信号与槽更新 UI
"""
import traceback
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from core.video_processor import VideoProcessor
from models.base_enhancer import BaseEnhancer
from config import DEFAULT_TILE_SIZE, DEFAULT_TILE_PAD


class VideoWorkerThread(QThread):
    """
    视频处理后台工作线程
    通过 Signal 向主线程发送进度、预览帧、完成/错误信号
    """

    # ========== 信号定义 ==========
    # 进度信号: (当前帧, 总帧数, 当前fps)
    progress_signal = pyqtSignal(int, int, float)
    # 预览帧信号: (RGB numpy array)
    preview_signal = pyqtSignal(np.ndarray)
    # 处理完成信号: (输出文件路径)
    finished_signal = pyqtSignal(str)
    # 错误信号: (错误信息)
    error_signal = pyqtSignal(str)
    # 状态信息信号: (消息文本)
    status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processor = None
        self._input_path = ""
        self._output_path = ""
        self._enhancer = None
        self._use_tiling = True
        self._tile_size = DEFAULT_TILE_SIZE
        self._tile_pad = DEFAULT_TILE_PAD
        self._denoise_strength = 0.0
        self._outscale = 0

    def setup(
        self,
        enhancer: BaseEnhancer,
        input_path: str,
        output_path: str = "",
        use_tiling: bool = True,
        tile_size: int = DEFAULT_TILE_SIZE,
        tile_pad: int = DEFAULT_TILE_PAD,
        denoise_strength: float = 0.0,
        outscale: int = 0,
    ):
        """
        配置工作线程参数（在 start() 之前调用）

        Args:
            enhancer: 已加载的增强模型
            input_path: 输入视频路径
            output_path: 输出视频路径（空字符串=自动生成）
            use_tiling: 是否使用分块
            tile_size: 分块大小
            tile_pad: 分块填充
            denoise_strength: 降噪强度 (0.0~1.0)
            outscale: 输出放大倍率 (0=使用模型原生)
        """
        self._enhancer = enhancer
        self._input_path = input_path
        self._output_path = output_path or None
        self._use_tiling = use_tiling
        self._tile_size = tile_size
        self._tile_pad = tile_pad
        self._denoise_strength = denoise_strength
        self._outscale = outscale

    def run(self):
        """线程主体 —— 执行视频处理"""
        try:
            self.status_signal.emit("正在初始化处理流水线...")

            self._processor = VideoProcessor(self._enhancer)

            self.status_signal.emit("正在处理视频...")

            output_path = self._processor.process_video(
                input_path=self._input_path,
                output_path=self._output_path,
                use_tiling=self._use_tiling,
                tile_size=self._tile_size,
                tile_pad=self._tile_pad,
                denoise_strength=self._denoise_strength,
                outscale=self._outscale,
                progress_callback=self._on_progress,
                preview_callback=self._on_preview,
            )

            if output_path:
                self.finished_signal.emit(output_path)
            else:
                self.status_signal.emit("处理已取消")

        except Exception as e:
            error_msg = f"处理出错: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)

    def cancel(self):
        """请求取消处理"""
        if self._processor:
            self._processor.cancel()

    def _on_progress(self, current: int, total: int, fps: float):
        """进度回调 → 发射信号"""
        self.progress_signal.emit(current, total, fps)

    def _on_preview(self, rgb_frame: np.ndarray):
        """预览回调 → 发射信号"""
        self.preview_signal.emit(rgb_frame.copy())


class PreviewWorkerThread(QThread):
    """
    单帧预览后台线程
    用于"预览增强效果"功能
    """

    # (原始RGB帧, 增强RGB帧)
    result_signal = pyqtSignal(np.ndarray, np.ndarray)
    error_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enhancer = None
        self._input_path = ""
        self._frame_index = 0
        self._use_tiling = True
        self._tile_size = DEFAULT_TILE_SIZE
        self._tile_pad = DEFAULT_TILE_PAD
        self._denoise_strength = 0.0
        self._outscale = 0

    def setup(
        self,
        enhancer: BaseEnhancer,
        input_path: str,
        frame_index: int = 0,
        use_tiling: bool = True,
        tile_size: int = DEFAULT_TILE_SIZE,
        tile_pad: int = DEFAULT_TILE_PAD,
        denoise_strength: float = 0.0,
        outscale: int = 0,
    ):
        self._enhancer = enhancer
        self._input_path = input_path
        self._frame_index = frame_index
        self._use_tiling = use_tiling
        self._tile_size = tile_size
        self._tile_pad = tile_pad
        self._denoise_strength = denoise_strength
        self._outscale = outscale

    def run(self):
        try:
            processor = VideoProcessor(self._enhancer)
            original, enhanced = processor.process_single_frame(
                self._input_path,
                self._frame_index,
                self._use_tiling,
                self._tile_size,
                self._tile_pad,
                self._denoise_strength,
                self._outscale,
            )
            self.result_signal.emit(original, enhanced)
        except Exception as e:
            self.error_signal.emit(f"预览出错: {str(e)}")
