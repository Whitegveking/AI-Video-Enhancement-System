"""
OpenCV 视频读写封装
提供逐帧读取生成器与视频写入器
"""
import cv2
import numpy as np
from typing import Generator, Tuple, Optional, Dict, Any


def read_video_frames(video_path: str) -> Generator[np.ndarray, None, None]:
    """
    逐帧读取视频的生成器（流式处理，不占用大量内存）
    输出 BGR 格式帧（OpenCV 默认）

    Args:
        video_path: 视频文件路径

    Yields:
        BGR 格式的帧 (np.ndarray, shape: H x W x 3, dtype: uint8)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            yield frame
    finally:
        cap.release()


def get_video_properties(video_path: str) -> Dict[str, Any]:
    """
    通过 OpenCV 获取视频属性

    Args:
        video_path: 视频文件路径

    Returns:
        视频属性字典
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    props = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fourcc": int(cap.get(cv2.CAP_PROP_FOURCC)),
    }
    cap.release()
    return props


def read_single_frame(video_path: str, frame_index: int = 0) -> Optional[np.ndarray]:
    """
    读取视频中指定帧（用于预览）

    Args:
        video_path: 视频文件路径
        frame_index: 帧索引（从0开始）

    Returns:
        BGR 格式帧，读取失败返回 None
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ret, frame = cap.read()
    cap.release()

    return frame if ret else None


class VideoWriter:
    """
    视频写入器封装
    支持逐帧写入，资源自动释放
    """

    def __init__(
        self,
        output_path: str,
        fps: float,
        width: int,
        height: int,
        fourcc: str = "mp4v"
    ):
        """
        Args:
            output_path: 输出视频路径
            fps: 帧率
            width: 帧宽度
            height: 帧高度
            fourcc: 编码器 FourCC 代码
        """
        self.output_path = output_path
        self.fourcc_code = cv2.VideoWriter_fourcc(*fourcc)
        self.writer = cv2.VideoWriter(
            output_path, self.fourcc_code, fps, (width, height)
        )
        if not self.writer.isOpened():
            raise RuntimeError(f"无法创建视频写入器: {output_path}")

        self._frame_count = 0

    def write_frame(self, frame: np.ndarray):
        """
        写入一帧（BGR 格式）

        Args:
            frame: BGR 格式帧
        """
        self.writer.write(frame)
        self._frame_count += 1

    @property
    def frame_count(self) -> int:
        """已写入的帧数"""
        return self._frame_count

    def release(self):
        """释放写入器资源"""
        if self.writer is not None:
            self.writer.release()
            self.writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
