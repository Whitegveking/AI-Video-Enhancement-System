"""
GFPGAN 模型适配器
专用于人脸修复与增强
"""
import os
import numpy as np
import torch
from typing import Optional

from models.base_enhancer import BaseEnhancer
from config import WEIGHTS_DIR, MODELS


class GFPGANEnhancer(BaseEnhancer):
    """
    GFPGAN 增强器
    利用人脸先验信息进行面部细节修复
    适合包含人脸的视频内容
    """

    def __init__(self):
        super().__init__()
        self.model_name = "GFPGAN"
        self.scale = 2  # GFPGAN 默认2倍
        self._restorer = None  # GFPGANer 实例

    def load_model(
        self,
        weight_path: Optional[str] = None,
        device: Optional[str] = None,
        upscale: int = 2,
        bg_upsampler=None,
        **kwargs
    ):
        """
        加载 GFPGAN 模型

        Args:
            weight_path: 权重文件路径
            device: 目标设备
            upscale: 放大倍率
            bg_upsampler: 背景上采样器（可选，传入 RealESRGANer 实例用于增强背景）
        """
        from gfpgan import GFPGANer

        if device:
            self.device = device
        self.scale = upscale

        model_config = MODELS.get("GFPGAN_v1.4")

        if weight_path is None:
            weight_path = os.path.join(WEIGHTS_DIR, model_config["weight_file"])

        if not os.path.exists(weight_path):
            raise FileNotFoundError(
                f"模型权重文件不存在: {weight_path}\n"
                f"请下载: {model_config['weight_url']}\n"
                f"并放置到: {WEIGHTS_DIR}"
            )

        self._restorer = GFPGANer(
            model_path=weight_path,
            upscale=self.scale,
            arch="clean",     # GFPGANv1.4 使用 clean 架构
            channel_multiplier=2,
            bg_upsampler=bg_upsampler,
        )

        self._loaded = True
        print(f"[GFPGAN] 模型加载完成 (scale={self.scale}, device={self.device})")

    def enhance_frame(self, rgb_frame: np.ndarray) -> np.ndarray:
        """
        增强单帧（自动检测人脸并修复）

        Args:
            rgb_frame: RGB uint8 帧 (H, W, 3)

        Returns:
            RGB uint8 增强帧
        """
        if not self._loaded:
            raise RuntimeError("模型尚未加载，请先调用 load_model()")

        import cv2
        # GFPGANer.enhance() 接受 BGR 输入
        bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

        # 返回: cropped_faces（裁切的人脸）, restored_faces（修复的人脸）, restored_img（完整图像）
        _, _, output_bgr = self._restorer.enhance(
            bgr_frame,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,  # 将修复的人脸贴回原图
        )

        output_rgb = cv2.cvtColor(output_bgr, cv2.COLOR_BGR2RGB)
        return output_rgb

    def _model_forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """
        GFPGAN 不支持纯 Tensor 前向（内部有人脸检测逻辑），
        此处通过 numpy 中转实现
        """
        from utils.color_utils import tensor_to_frame, frame_to_tensor

        # Tensor -> numpy RGB
        rgb_frame = tensor_to_frame(input_tensor)
        # 增强
        enhanced = self.enhance_frame(rgb_frame)
        # numpy RGB -> Tensor
        return frame_to_tensor(enhanced, self.device)

    def release(self):
        """释放模型"""
        self._restorer = None
        super().release()
