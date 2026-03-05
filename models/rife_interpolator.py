"""
RIFE 补帧模型封装器
将 RIFE v4 (IFNet HD v3) 封装为统一的高层接口

功能:
- 加载预训练权重 (支持多种权重格式)
- 对任意两帧进行中间帧插值
- 自动处理图像填充 (对齐到 64 的倍数)
- 支持 FP16 半精度推理

使用方式:
    rife = RIFEInterpolator()
    rife.load_model("weights/flownet.pkl")
    mid_frame = rife.interpolate(frame0_rgb, frame1_rgb, timestep=0.5)
"""
import numpy as np
import torch
import torch.nn.functional as F
from typing import Optional

from models.rife.IFNet_HDv3 import IFNet


class RIFEInterpolator:
    """
    RIFE 补帧模型接口

    核心原理:
    给定连续两帧 img0 (t=0) 和 img1 (t=1)，
    RIFE 通过多尺度光流估计生成任意时刻 t ∈ (0,1) 的中间帧
    """

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.flownet = IFNet()
        self._loaded = False
        self._half = False
        self.model_name = "RIFE_v4"

    def load_model(self, weight_path: str, device: Optional[str] = None, half: bool = False):
        """
        加载 RIFE 预训练权重

        Args:
            weight_path: 权重文件路径 (flownet.pkl / .pth)
            device: 目标设备 ('cuda' / 'cpu')
            half: 是否使用 FP16 半精度
        """
        if device:
            self.device = torch.device(device)

        # 加载权重 (兼容多种保存格式)
        state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)

        # 处理不同格式的 state_dict
        new_dict = {}
        for k, v in state_dict.items():
            # 格式1: 'flownet.block0...' → 去掉 'flownet.' 前缀
            if k.startswith("flownet."):
                new_dict[k[8:]] = v
            # 格式2: 'module.flownet.block0...' (DataParallel)
            elif k.startswith("module.flownet."):
                new_dict[k[15:]] = v
            # 格式3: 'module.block0...' (DataParallel without flownet wrapper)
            elif k.startswith("module."):
                new_dict[k[7:]] = v
            else:
                # 格式4: 直接就是 IFNet 的 state_dict
                new_dict[k] = v

        self.flownet.load_state_dict(new_dict, strict=False)
        self.flownet.eval()
        self.flownet.to(self.device)

        # FP16 半精度
        self._half = half and self.device.type == "cuda"
        if self._half:
            self.flownet.half()

        self._loaded = True
        print(f"[RIFE] 模型已加载: {weight_path}")
        print(f"[RIFE] 设备: {self.device}, 半精度: {self._half}")

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._loaded

    @torch.no_grad()
    def interpolate(
        self,
        frame0_rgb: np.ndarray,
        frame1_rgb: np.ndarray,
        timestep: float = 0.5,
    ) -> np.ndarray:
        """
        在两帧之间插值生成中间帧

        Args:
            frame0_rgb: 第一帧 RGB 图像 (H, W, 3) uint8
            frame1_rgb: 第二帧 RGB 图像 (H, W, 3) uint8
            timestep: 时间步 (0.0~1.0)
                      0.5 = 精确中间帧
                      0.25 / 0.75 = 四分之一/四分之三位置

        Returns:
            插值后的 RGB 帧 (H, W, 3) uint8
        """
        h, w, _ = frame0_rgb.shape

        # numpy → tensor, [0,255] → [0,1]
        img0 = torch.from_numpy(frame0_rgb.copy()).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        img1 = torch.from_numpy(frame1_rgb.copy()).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        img0 = img0.to(self.device)
        img1 = img1.to(self.device)

        if self._half:
            img0 = img0.half()
            img1 = img1.half()

        # 填充到 64 的倍数 (IFNet 要求)
        ph = ((h - 1) // 64 + 1) * 64
        pw = ((w - 1) // 64 + 1) * 64
        padding = (0, pw - w, 0, ph - h)
        img0 = F.pad(img0, padding)
        img1 = F.pad(img1, padding)

        # 拼接两帧并推理
        x = torch.cat((img0, img1), dim=1)

        # 根据分辨率决定处理尺度 (官方默认 scale=1.0)
        inference_scale = self._get_inference_scale(h, w)
        scale_list = [8 / inference_scale, 4 / inference_scale,
                      2 / inference_scale, 1 / inference_scale]
        flow_list, mask, merged = self.flownet(x, timestep, scale_list)

        # merged[3] 是最终融合帧，裁剪回原始尺寸
        result = merged[3][:, :, :h, :w]

        # tensor → numpy
        result = result.squeeze(0).float().clamp(0, 1).permute(1, 2, 0).cpu().numpy()
        result = (result * 255.0).round().astype(np.uint8)

        return result

    def _get_inference_scale(self, h: int, w: int) -> float:
        """
        根据图像分辨率自动选择推理缩放因子

        高分辨率使用较小的 scale (如 0.5) 减少显存占用
        scale 越小 → scale_list 中的值越大 → 下采样更多
        """
        max_dim = max(h, w)

        if max_dim > 2160:   # 4K+
            return 0.5
        elif max_dim > 1080:  # 2K / 1080p+
            return 1.0
        elif max_dim > 480:   # 720p / 标清+
            return 2.0
        else:                 # 小分辨率
            return 4.0

    def release(self):
        """释放模型资源"""
        if self.flownet is not None:
            del self.flownet
            self.flownet = None
        self._loaded = False
        torch.cuda.empty_cache()
