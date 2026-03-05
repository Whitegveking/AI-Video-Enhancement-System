"""
IFNet (Intermediate Flow Network) - RIFE v4.15 核心网络架构
多尺度光流估计网络，逐级细化中间帧的光流和融合掩码

架构说明 (与 Practical-RIFE v4.15 完全一致):
- Head 模块: 浅层特征提取 (3ch → 8ch)
- 4 个 IFBlock 分别在不同分辨率上估计光流
- IFBlock 使用 ResConv (带可学习 beta 的残差卷积)
- PixelShuffle 上采样代替简单反卷积
- 仅在最终尺度进行帧融合
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

from models.rife.warplayer import warp


def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
    """带 LeakyReLU 激活的卷积层"""
    return nn.Sequential(
        nn.Conv2d(
            in_planes, out_planes,
            kernel_size=kernel_size, stride=stride,
            padding=padding, dilation=dilation, bias=True,
        ),
        nn.LeakyReLU(0.2, True),
    )


class Head(nn.Module):
    """
    浅层特征提取头
    3ch → 32ch (下采样) → 32ch × 2 → 8ch (上采样回原分辨率)
    """

    def __init__(self):
        super().__init__()
        self.cnn0 = nn.Conv2d(3, 32, 3, 2, 1)
        self.cnn1 = nn.Conv2d(32, 32, 3, 1, 1)
        self.cnn2 = nn.Conv2d(32, 32, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(32, 8, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x, feat=False):
        x0 = self.cnn0(x)
        x = self.relu(x0)
        x1 = self.cnn1(x)
        x = self.relu(x1)
        x2 = self.cnn2(x)
        x = self.relu(x2)
        x3 = self.cnn3(x)
        if feat:
            return [x0, x1, x2, x3]
        return x3


class ResConv(nn.Module):
    """
    带可学习缩放因子的残差卷积块
    output = LeakyReLU(conv(x) * beta + x)
    """

    def __init__(self, c, dilation=1):
        super().__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, dilation, dilation=dilation, groups=1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    """
    中间流估计块 (Intermediate Flow Block)
    在特定分辨率上估计光流增量和融合掩码

    输出通道: 6ch (flow 4ch + mask 1ch + 1ch unused)
    使用 ConvTranspose2d + PixelShuffle(2) 实现高质量上采样
    """

    def __init__(self, in_planes, c=64):
        super().__init__()
        self.conv0 = nn.Sequential(
            conv(in_planes, c // 2, 3, 2, 1),
            conv(c // 2, c, 3, 2, 1),
        )
        # 8 层 ResConv 残差块 (每层自带残差连接)
        self.convblock = nn.Sequential(
            ResConv(c), ResConv(c),
            ResConv(c), ResConv(c),
            ResConv(c), ResConv(c),
            ResConv(c), ResConv(c),
        )
        # 反卷积 + PixelShuffle 上采样: c → 24 → 6ch (4x空间放大)
        self.lastconv = nn.Sequential(
            nn.ConvTranspose2d(c, 4 * 6, 4, 2, 1),
            nn.PixelShuffle(2),
        )

    def forward(self, x, flow=None, scale=1):
        """
        Args:
            x: 拼接后的输入特征
            flow: 上一级累积光流 (B, 4, H, W)，首次为 None
            scale: 当前尺度因子 (8/4/2/1)
        Returns:
            flow: 光流增量 (B, 4, H, W)
            mask: 融合掩码增量 (B, 1, H, W)
        """
        x = F.interpolate(
            x, scale_factor=1.0 / scale, mode="bilinear", align_corners=False,
        )
        if flow is not None:
            flow = (
                F.interpolate(
                    flow, scale_factor=1.0 / scale, mode="bilinear",
                    align_corners=False,
                )
                * (1.0 / scale)
            )
            x = torch.cat((x, flow), dim=1)

        feat = self.conv0(x)
        feat = self.convblock(feat)
        tmp = self.lastconv(feat)

        # 上采样回原始分辨率
        tmp = F.interpolate(
            tmp, scale_factor=scale, mode="bilinear", align_corners=False,
        )
        flow = tmp[:, :4] * scale
        mask = tmp[:, 4:5]
        return flow, mask


class IFNet(nn.Module):
    """
    RIFE v4.15 的中间流估计网络 (IFNet HD v3)

    多尺度架构：
    - block0: 1/8 分辨率初估光流 (c=192)
    - block1: 1/4 分辨率细化 (c=128)
    - block2: 1/2 分辨率细化 (c=96)
    - block3: 原始分辨率精修 (c=64)

    输入通道分析:
    - Head 输出 8ch 特征
    - block0: img0(3) + img1(3) + f0(8) + f1(8) + timestep(1) = 23 = 7+16
    - block1-3: warped_img0(3) + warped_img1(3) + wf0(8) + wf1(8)
                + timestep(1) + mask(1) = 24
                + flow(4) 在 IFBlock 内部拼接 → 28 = 8+4+16
    """

    def __init__(self):
        super().__init__()
        self.block0 = IFBlock(7 + 16, c=192)       # 23 通道
        self.block1 = IFBlock(8 + 4 + 16, c=128)   # 24 + 4(flow) = 28
        self.block2 = IFBlock(8 + 4 + 16, c=96)
        self.block3 = IFBlock(8 + 4 + 16, c=64)

        # 浅层特征提取头: 3ch → 8ch
        self.encode = Head()

    def forward(self, x, timestep=0.5, scale_list=[8, 4, 2, 1]):
        """
        前向推理

        Args:
            x: 拼接的两帧图像 (B, 6, H, W), 值域 [0,1]
            timestep: 插值时间步 (0~1), 0.5 表示中间帧
            scale_list: 各级处理的缩放因子列表

        Returns:
            flow_list: 各级累积光流列表
            mask: 最终融合掩码 (经过 sigmoid)
            merged: 各级结果列表, merged[3] 为最终融合帧
        """
        channel = x.shape[1] // 2
        img0 = x[:, :channel]
        img1 = x[:, channel:]

        # 构建时间步特征图 (与空间维度相同)
        if not torch.is_tensor(timestep):
            timestep = (x[:, :1].clone() * 0 + 1) * timestep
        else:
            timestep = timestep.repeat(1, 1, img0.shape[2], img0.shape[3])

        # 提取浅层特征 (8ch)
        f0 = self.encode(img0[:, :3])
        f1 = self.encode(img1[:, :3])

        flow_list = []
        merged = []
        mask_list = []
        warped_img0 = img0
        warped_img1 = img1
        flow = None
        mask = None
        block = [self.block0, self.block1, self.block2, self.block3]

        for i in range(4):
            if flow is None:
                # 首级: 无先验光流
                flow, mask = block[i](
                    torch.cat((img0[:, :3], img1[:, :3], f0, f1, timestep), dim=1),
                    None,
                    scale=scale_list[i],
                )
            else:
                # 后续级: 使用上一级光流扭曲特征
                wf0 = warp(f0, flow[:, :2])
                wf1 = warp(f1, flow[:, 2:4])
                fd, mask = block[i](
                    torch.cat((
                        warped_img0[:, :3], warped_img1[:, :3],
                        wf0, wf1, timestep, mask,
                    ), dim=1),
                    flow,
                    scale=scale_list[i],
                )
                flow = flow + fd

            mask_list.append(mask)
            flow_list.append(flow)
            warped_img0 = warp(img0, flow[:, :2])
            warped_img1 = warp(img1, flow[:, 2:4])
            merged.append((warped_img0, warped_img1))

        # 最终融合: sigmoid 掩码加权混合
        mask = torch.sigmoid(mask)
        merged[3] = warped_img0 * mask + warped_img1 * (1 - mask)

        return flow_list, mask_list[3], merged

