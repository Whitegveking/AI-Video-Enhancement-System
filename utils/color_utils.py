"""
色彩空间转换工具
处理 BGR <-> RGB 及 Tensor 转换
"""
import cv2
import numpy as np
import torch


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """
    BGR -> RGB 转换（OpenCV 默认 BGR，模型需要 RGB）

    Args:
        frame: BGR 格式 numpy 数组 (H, W, 3)

    Returns:
        RGB 格式 numpy 数组
    """
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(frame: np.ndarray) -> np.ndarray:
    """
    RGB -> BGR 转换（模型输出 RGB，写入视频需要 BGR）

    Args:
        frame: RGB 格式 numpy 数组 (H, W, 3)

    Returns:
        BGR 格式 numpy 数组
    """
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


def frame_to_tensor(frame: np.ndarray, device: str = "cuda") -> torch.Tensor:
    """
    将 RGB uint8 帧转换为模型输入 Tensor

    Args:
        frame: RGB 格式 numpy 数组 (H, W, 3), dtype=uint8
        device: 目标设备 ('cuda' 或 'cpu')

    Returns:
        Float Tensor (1, 3, H, W), 值域 [0, 1]
    """
    # uint8 [0,255] -> float32 [0,1]
    tensor = torch.from_numpy(frame.copy()).float() / 255.0
    # (H, W, 3) -> (3, H, W) -> (1, 3, H, W)
    tensor = tensor.permute(2, 0, 1).unsqueeze(0)
    return tensor.to(device)


def tensor_to_frame(tensor: torch.Tensor) -> np.ndarray:
    """
    将模型输出 Tensor 转换回 RGB uint8 帧

    Args:
        tensor: Float Tensor (1, 3, H, W) 或 (3, H, W), 值域 [0, 1]

    Returns:
        RGB 格式 numpy 数组 (H, W, 3), dtype=uint8
    """
    if tensor.dim() == 4:
        tensor = tensor.squeeze(0)

    # (3, H, W) -> (H, W, 3)
    frame = tensor.detach().cpu().clamp(0, 1).permute(1, 2, 0).numpy()
    # float32 [0,1] -> uint8 [0,255]
    frame = (frame * 255.0).round().astype(np.uint8)
    return frame
