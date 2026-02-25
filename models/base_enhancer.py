"""
AI 增强模型统一基类接口
所有模型适配器（Real-ESRGAN, GFPGAN, BasicVSR++ 等）必须继承此类
"""
import numpy as np
import torch
from abc import ABC, abstractmethod
from typing import Optional

from core.tiling import tile_process


class BaseEnhancer(ABC):
    """增强模型统一接口"""

    def __init__(self):
        self.model = None
        self.device: str = "cuda" if torch.cuda.is_available() else "cpu"
        self.scale: int = 4
        self.model_name: str = ""
        self._loaded: bool = False

    @abstractmethod
    def load_model(self, weight_path: str, device: Optional[str] = None, **kwargs):
        """
        加载模型权重到指定设备

        Args:
            weight_path: 权重文件路径 (.pth)
            device: 目标设备 ('cuda' / 'cpu')
        """
        pass

    @abstractmethod
    def enhance_frame(self, rgb_frame: np.ndarray) -> np.ndarray:
        """
        增强单帧图像（直接处理完整帧，可能导致 OOM）

        Args:
            rgb_frame: RGB 格式输入帧 (H, W, 3), dtype=uint8

        Returns:
            RGB 格式增强后帧 (H*scale, W*scale, 3), dtype=uint8
        """
        pass

    def enhance_with_tiling(
        self,
        rgb_frame: np.ndarray,
        tile_size: int = 512,
        tile_pad: int = 32,
    ) -> np.ndarray:
        """
        使用分块策略增强帧（防 OOM，通用实现）

        Args:
            rgb_frame: RGB 格式输入帧 (H, W, 3), dtype=uint8
            tile_size: 分块大小
            tile_pad: 重叠填充

        Returns:
            RGB 格式增强后帧, dtype=uint8
        """
        from utils.color_utils import frame_to_tensor, tensor_to_frame

        img_tensor = frame_to_tensor(rgb_frame, self.device)

        output_tensor = tile_process(
            img_tensor=img_tensor,
            model_forward=self._model_forward,
            tile_size=tile_size,
            tile_pad=tile_pad,
            scale=self.scale,
        )

        return tensor_to_frame(output_tensor)

    @abstractmethod
    def _model_forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """
        模型前向推理（供 Tiling 调用）

        Args:
            input_tensor: (1, C, H, W) float32 tensor, 值域 [0,1]

        Returns:
            (1, C, H*scale, W*scale) float32 tensor
        """
        pass

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._loaded

    def release(self):
        """释放模型资源"""
        self.model = None
        self._loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
