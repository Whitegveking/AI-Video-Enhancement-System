"""
Real-ESRGAN 模型适配器
支持通用场景超分辨率 (x2/x4) 及动漫专用模型
"""
import os
import numpy as np
import torch
from typing import Optional

from models.base_enhancer import BaseEnhancer
from config import WEIGHTS_DIR, MODELS


class RealESRGANEnhancer(BaseEnhancer):
    """
    Real-ESRGAN 增强器
    基于 RRDB 网络结构，适用于通用画质增强与超分辨率
    """

    def __init__(self):
        super().__init__()
        self.model_name = "Real-ESRGAN"
        self._upsampler = None  # RealESRGANer 实例

    def load_model(
        self,
        weight_path: Optional[str] = None,
        device: Optional[str] = None,
        model_key: str = "RealESRGAN_x4",
        half: bool = True,
        **kwargs
    ):
        """
        加载 Real-ESRGAN 模型

        Args:
            weight_path: 权重文件路径，为 None 时自动使用默认路径
            device: 目标设备
            model_key: 模型配置键名（RealESRGAN_x4, RealESRGAN_x2, RealESRGAN_x4_Anime）
            half: 是否使用 FP16 半精度（减少显存占用）
        """
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        if device:
            self.device = device

        model_config = MODELS.get(model_key, MODELS["RealESRGAN_x4"])
        self.scale = model_config["scale"]

        # 根据模型类型构建不同的网络结构
        if "anime" in model_key.lower():
            # 动漫模型：6 个 RRDB 块
            model = RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64,
                num_block=6, num_grow_ch=32, scale=self.scale
            )
        else:
            # 通用模型：23 个 RRDB 块
            model = RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64,
                num_block=23, num_grow_ch=32, scale=self.scale
            )

        # 确定权重文件路径
        if weight_path is None:
            weight_path = os.path.join(WEIGHTS_DIR, model_config["weight_file"])

        # 如果权重不存在，提示需要下载
        if not os.path.exists(weight_path):
            raise FileNotFoundError(
                f"模型权重文件不存在: {weight_path}\n"
                f"请下载: {model_config['weight_url']}\n"
                f"并放置到: {WEIGHTS_DIR}"
            )

        # 使用 FP16 仅在 CUDA 下
        use_half = half and self.device == "cuda"

        # 创建 RealESRGANer 上采样器
        self._upsampler = RealESRGANer(
            scale=self.scale,
            model_path=weight_path,
            model=model,
            tile=0,          # 我们自己管理 tiling
            tile_pad=0,
            pre_pad=10,      # 预填充防止边缘伪影
            half=use_half,
            device=self.device,
        )

        self._loaded = True
        print(f"[Real-ESRGAN] 模型加载完成: {model_config['name']} (scale={self.scale}, device={self.device})")

    def enhance_frame(self, rgb_frame: np.ndarray) -> np.ndarray:
        """
        增强单帧（使用 Real-ESRGAN 官方接口）

        Args:
            rgb_frame: RGB uint8 帧 (H, W, 3)

        Returns:
            RGB uint8 增强帧
        """
        if not self._loaded:
            raise RuntimeError("模型尚未加载，请先调用 load_model()")

        import cv2
        # RealESRGANer.enhance() 接受 BGR 输入，返回 BGR 输出
        bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
        output_bgr, _ = self._upsampler.enhance(bgr_frame, outscale=self.scale)
        output_rgb = cv2.cvtColor(output_bgr, cv2.COLOR_BGR2RGB)

        return output_rgb

    def _model_forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """
        模型前向推理（供 Tiling 分块调用）

        Args:
            input_tensor: (1, 3, H, W) float32 tensor

        Returns:
            (1, 3, H*scale, W*scale) float32 tensor
        """
        if not self._loaded:
            raise RuntimeError("模型尚未加载")

        model = self._upsampler.model
        if hasattr(self._upsampler, 'half') and self._upsampler.half:
            input_tensor = input_tensor.half()

        with torch.no_grad():
            output = model(input_tensor)

        return output.float()

    def release(self):
        """释放模型及显存"""
        self._upsampler = None
        super().release()
