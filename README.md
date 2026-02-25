# AI 视频增强系统 (AI Video Enhancement System)

基于深度学习的视频超分辨率与画质增强系统。

## 技术栈
- **PyTorch** - 深度学习推理引擎
- **Real-ESRGAN** - 通用场景超分辨率
- **GFPGAN** - 人脸修复增强
- **OpenCV** - 视频帧读写
- **FFmpeg** - 音视频分离与合并
- **PyQt5** - GUI 界面

## 项目结构
```
├── main.py                 # 程序入口
├── config.py               # 全局配置
├── requirements.txt        # 依赖清单
├── ui/                     # 表现层 (PyQt5)
│   ├── main_window.py      # 主窗口
│   ├── video_preview.py    # 视频预览对比控件
│   └── parameter_panel.py  # 参数配置面板
├── core/                   # 业务逻辑层
│   ├── video_processor.py  # 视频处理流水线
│   ├── worker_thread.py    # QThread 后台工作线程
│   ├── tiling.py           # 图像分块算法
│   └── memory_manager.py   # 内存管理
├── models/                 # AI 模型集成层
│   ├── base_enhancer.py    # 统一 Enhancer 基类
│   ├── realesrgan_enhancer.py
│   └── gfpgan_enhancer.py
├── utils/                  # 工具层
│   ├── ffmpeg_utils.py     # FFmpeg 封装
│   ├── video_io.py         # OpenCV 视频IO
│   └── color_utils.py      # 色彩空间转换
└── weights/                # 模型权重 (需手动下载)
```

## 快速开始

### 1. 安装依赖
```bash
# PyTorch (CUDA 12.4)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

# 其他依赖
pip install opencv-python numpy PyQt5 basicsr realesrgan gfpgan
```

### 2. 下载模型权重
将权重文件放入 `weights/` 目录:
- [RealESRGAN_x4plus.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth)
- [RealESRGAN_x2plus.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth)
- [GFPGANv1.4.pth](https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth)

### 3. 运行
```bash
python main.py
```

## 核心处理流程
```
提取音频(FFmpeg) → 逐帧读取(OpenCV) → BGR→RGB → Tiling分块 
→ AI推理(PyTorch) → 拼接还原 → RGB→BGR → 写帧 → 合并音频(FFmpeg)
```