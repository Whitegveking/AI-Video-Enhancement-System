"""
图像分块处理 (Tiling) 算法
将高分辨率图像切割为小块分别推理，防止显存溢出(OOM)
支持重叠填充(Padding)以消除拼接接缝伪影
"""
import numpy as np
import torch
from typing import Callable, Tuple


def tile_process(
    img_tensor: torch.Tensor,
    model_forward: Callable[[torch.Tensor], torch.Tensor],
    tile_size: int = 512,
    tile_pad: int = 32,
    scale: int = 4,
) -> torch.Tensor:
    """
    对输入图像 Tensor 进行分块推理，然后拼接回完整图像

    核心流程：
    1. 计算分块网格 (行数 x 列数)
    2. 对每个块加上 padding 后送入模型推理
    3. 裁掉 padding 区域，将有效部分拼回输出画布

    Args:
        img_tensor: 输入图像 Tensor, shape (1, C, H, W)
        model_forward: 模型前向推理函数, 接收 (1, C, h, w) 返回 (1, C, h*scale, w*scale)
        tile_size: 分块大小（像素）
        tile_pad: 重叠填充大小（像素）
        scale: 放大倍率

    Returns:
        输出图像 Tensor, shape (1, C, H*scale, W*scale)
    """
    batch, channel, height, width = img_tensor.shape
    assert batch == 1, "分块处理仅支持 batch_size=1"

    # 计算输出尺寸
    out_h = height * scale
    out_w = width * scale

    # 创建输出画布
    output = img_tensor.new_zeros((batch, channel, out_h, out_w))

    # 计算分块网格
    tiles_x = max(1, (width + tile_size - 1) // tile_size)
    tiles_y = max(1, (height + tile_size - 1) // tile_size)

    for y in range(tiles_y):
        for x in range(tiles_x):
            # ---- 计算当前块在输入图像中的位置 ----
            # 有效区域（不含 padding）
            input_start_x = x * tile_size
            input_start_y = y * tile_size
            input_end_x = min(input_start_x + tile_size, width)
            input_end_y = min(input_start_y + tile_size, height)

            # 加上 padding 的区域（可能超出边界，需裁剪）
            input_start_x_pad = max(input_start_x - tile_pad, 0)
            input_start_y_pad = max(input_start_y - tile_pad, 0)
            input_end_x_pad = min(input_end_x + tile_pad, width)
            input_end_y_pad = min(input_end_y + tile_pad, height)

            # 提取带 padding 的输入块
            input_tile = img_tensor[
                :, :,
                input_start_y_pad:input_end_y_pad,
                input_start_x_pad:input_end_x_pad
            ]

            # ---- 模型推理 ----
            with torch.no_grad():
                output_tile = model_forward(input_tile)

            # ---- 计算输出中有效区域（去掉 padding 对应的放大部分）----
            # padding 在左/上的实际像素数
            pad_left = input_start_x - input_start_x_pad
            pad_top = input_start_y - input_start_y_pad

            # 有效区域的宽高
            valid_w = input_end_x - input_start_x
            valid_h = input_end_y - input_start_y

            # 从输出 tile 中裁出有效部分
            output_start_x = pad_left * scale
            output_start_y = pad_top * scale
            output_valid = output_tile[
                :, :,
                output_start_y: output_start_y + valid_h * scale,
                output_start_x: output_start_x + valid_w * scale
            ]

            # ---- 写入输出画布 ----
            output[
                :, :,
                input_start_y * scale: input_end_y * scale,
                input_start_x * scale: input_end_x * scale
            ] = output_valid

    return output


def estimate_tile_size(
    height: int,
    width: int,
    scale: int = 4,
    gpu_memory_gb: float = 8.0,
    safety_factor: float = 0.6,
) -> int:
    """
    根据 GPU 显存大小估算合适的分块尺寸

    Args:
        height: 输入图像高度
        width: 输入图像宽度
        scale: 放大倍率
        gpu_memory_gb: GPU 显存大小 (GB)
        safety_factor: 显存安全系数 (预留给模型本身的开销)

    Returns:
        推荐的分块大小
    """
    available_memory = gpu_memory_gb * safety_factor * (1024 ** 3)  # 转为字节

    # 估算模型处理一个 tile 所需显存:
    # 输入: tile_size^2 * 3 * 4 bytes (float32)
    # 输出: (tile_size*scale)^2 * 3 * 4 bytes
    # 中间特征: 约为输入的 10~20 倍（经验值）
    # 总计约: tile_size^2 * 3 * 4 * (1 + scale^2 + 15) ≈ tile_size^2 * overhead
    overhead_per_pixel = 3 * 4 * (1 + scale ** 2 + 15)

    max_tile_size = int((available_memory / overhead_per_pixel) ** 0.5)

    # 对齐到 32 的倍数（对 GPU 计算更友好）
    max_tile_size = (max_tile_size // 32) * 32
    max_tile_size = max(128, min(max_tile_size, 1024))

    return max_tile_size
