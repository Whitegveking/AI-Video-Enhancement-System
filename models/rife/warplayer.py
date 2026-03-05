"""
光流后向扭曲模块 (Backward Warping)
基于光流场使用 grid_sample 对图像进行扭曲变形
用于 RIFE 模型的帧合成
"""
import torch
import torch.nn.functional as F

# 缓存不同分辨率的采样网格，避免重复创建
_backwarp_grid_cache = {}


def warp(tenInput: torch.Tensor, tenFlow: torch.Tensor) -> torch.Tensor:
    """
    使用光流场对输入图像进行后向扭曲

    Args:
        tenInput: 输入图像张量 (B, C, H, W)
        tenFlow: 光流场 (B, 2, H, W), 其中 flow[:,0] 为水平分量, flow[:,1] 为垂直分量

    Returns:
        扭曲后的图像 (B, C, H, W)
    """
    k = (tenFlow.shape[2], tenFlow.shape[3])

    if k not in _backwarp_grid_cache:
        H, W = k
        # 创建归一化坐标网格 [-1, 1]
        tenHorizontal = (
            torch.linspace(-1.0, 1.0, W, device=tenFlow.device)
            .view(1, 1, 1, W)
            .expand(1, -1, H, -1)
        )
        tenVertical = (
            torch.linspace(-1.0, 1.0, H, device=tenFlow.device)
            .view(1, 1, H, 1)
            .expand(1, -1, -1, W)
        )
        _backwarp_grid_cache[k] = torch.cat([tenHorizontal, tenVertical], dim=1)

    # 将光流从像素坐标转换为归一化坐标 [-1, 1]
    tenFlow_norm = torch.cat([
        tenFlow[:, 0:1, :, :] / ((tenInput.shape[3] - 1.0) / 2.0),
        tenFlow[:, 1:2, :, :] / ((tenInput.shape[2] - 1.0) / 2.0),
    ], dim=1)

    # 基础网格 + 光流偏移 → 采样坐标
    grid = _backwarp_grid_cache[k].to(device=tenFlow.device, dtype=tenFlow.dtype)
    grid = (grid.expand(tenFlow.shape[0], -1, -1, -1) + tenFlow_norm).permute(0, 2, 3, 1)

    return F.grid_sample(
        input=tenInput,
        grid=grid,
        mode="bilinear",
        padding_mode="border",
        align_corners=True,
    )
