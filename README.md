# AI 视频增强系统 (AI Video Enhancement System)

基于 **PyTorch + PyQt5** 的毕业设计项目，提供视频超分、补帧、实时预览与对比播放能力，面向低清视频到高清视频的工程化增强流程。

---

## 1. 当前已实现能力

### 1.1 视频超分与增强
- 多模型支持：
  - `RealESRGAN_x4`（通用 4x）
  - `RealESRGAN_x2`（通用 2x）
  - `RealESRGAN_x4_Anime`（动漫优化）
  - `GFPGAN_v1.4`（人像修复）
- 自动模式 `Auto`：基于人脸检测自动在 GFPGAN 与 Real-ESRGAN 间切换。
- 支持自定义倍率、降噪强度、分块参数（tile size / tile pad）。

### 1.2 视频补帧
- 集成 `RIFE v4`（`flownet.pkl`）
- 支持 `2x / 4x` 帧率提升
- 保持时长不变，处理后自动合并原音轨

### 1.3 联合处理
- 一键模式：**超分 + 补帧**（先超分后补帧）

### 1.4 GUI 与交互
- 拖拽导入视频
- 实时预览（带防抖）
- 处理日志、进度条、可取消任务
- 对比播放窗口：已改为**按时间同步**（适配补帧后帧率变化场景）

### 1.5 工程稳定性
- 全流程后台线程（`QThread`），避免 UI 卡死
- 流式逐帧处理，避免整视频载入内存
- 分块推理 + 显存清理，降低 OOM 风险

---

## 2. 技术栈

- **Python / PyTorch**：模型推理
- **Real-ESRGAN / GFPGAN / RIFE**：超分与补帧
- **OpenCV**：逐帧读取与图像处理
- **FFmpeg**：音频提取与音画复用
- **PyQt5**：桌面 GUI

---

## 3. 项目结构

```text
AI-Video-Enhancement-System/
├── main.py
├── config.py
├── requirements.txt
├── core/
│   ├── video_processor.py
│   ├── frame_interpolator.py
│   ├── worker_thread.py
│   ├── tiling.py
│   └── memory_manager.py
├── models/
│   ├── base_enhancer.py
│   ├── realesrgan_enhancer.py
│   ├── gfpgan_enhancer.py
│   ├── rife_interpolator.py
│   └── rife/
│       ├── IFNet_HDv3.py
│       └── warplayer.py
├── ui/
│   ├── main_window.py
│   ├── parameter_panel.py
│   ├── video_preview.py
│   └── video_compare_dialog.py
├── utils/
│   ├── ffmpeg_utils.py
│   ├── video_io.py
│   └── color_utils.py
├── tests/
│   ├── test_imports.py
│   └── test_e2e.py
├── output/
├── temp/
└── weights/
```

---

## 4. 环境与依赖

### 4.1 系统依赖
- Python 3.10+
- FFmpeg（需已加入系统 PATH）
- NVIDIA GPU（推荐，支持 CUDA）

### 4.2 Python 依赖安装

先安装 PyTorch（CUDA 12.4 示例）：

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

再安装项目依赖：

```bash
pip install -r requirements.txt
```

---

## 5. 模型权重准备

将以下文件放入 `weights/`：

- `RealESRGAN_x4plus.pth`
- `RealESRGAN_x2plus.pth`
- `RealESRGAN_x4plus_anime_6B.pth`
- `GFPGANv1.4.pth`
- `flownet.pkl`（RIFE）
- `haarcascade_frontalface_default.xml`（自动模式人脸检测）

参考下载地址（部分）：

- Real-ESRGAN: <https://github.com/xinntao/Real-ESRGAN/releases>
- GFPGAN: <https://github.com/TencentARC/GFPGAN/releases>
- RIFE: <https://github.com/hzwer/Practical-RIFE>

---

## 6. 运行

```bash
python main.py
```

推荐流程：
1. 导入视频
2. 选择增强模式/倍率/降噪/分块参数
3. 选择处理方式：超分 / 补帧 / 超分+补帧
4. 处理完成后打开“对比播放”查看效果

---

## 7. 核心流水线

### 7.1 超分流水线

```text
提取音频(FFmpeg)
→ 逐帧读取(OpenCV)
→ BGR→RGB
→ 分块推理(Tiling, PyTorch)
→ RGB→BGR
→ 写入临时视频
→ 合并音频(FFmpeg)
```

### 7.2 补帧流水线

```text
提取音频(FFmpeg)
→ 逐帧读取(OpenCV)
→ 相邻帧插值(RIFE)
→ 写入高帧率视频
→ 合并音频(FFmpeg)
```

---

## 8. 测试

### 8.1 导入与模块检查

```bash
python tests/test_imports.py
```

### 8.2 端到端测试

```bash
python tests/test_e2e.py
```

> `test_e2e.py` 需要在项目根目录准备 `test_input.mp4`。

### 8.3 CI（持续集成）

项目已提供 GitHub Actions 工作流：

- 配置文件：`.github/workflows/ci.yml`
- 触发时机：`push` / `pull_request` 到 `main` 或 `master`
- 当前检查项：
	1. 依赖安装（含 CPU 版 PyTorch）
	2. Python 语法编译检查（`compileall`）
	3. 冒烟测试（`python tests/test_imports.py`）

该 CI 设计为“轻量门禁”：优先快速发现导入错误、语法错误和基础依赖问题。

---

## 9. 结合论文目标的改进建议（按优先级）

以下建议基于当前代码实现与项目说明（分层架构、音画同步、显存控制、QThread 响应性）整理。

### P0（建议优先完成，能明显提升工程质量）

1. **统一自动化测试框架（pytest 化）**
	- 现状：有 `test_imports.py` 和 `test_e2e.py`，但偏脚本化。
	- 建议：迁移为 `pytest` 测试用例，加入 CI（GitHub Actions）自动跑基础测试。

2. **权重自动检查与下载引导**
	- 现状：缺权重时弹窗提示。
	- 建议：增加“检测权重状态”页和一键下载脚本（可选镜像源）。

3. **README 与参数说明完善（可复现实验）**
	- 明确不同显存档位下的推荐 `tile_size`、FP16 开关建议。
	- 补充典型输入输出命名规则和结果目录规范。

### P1（中期优化，提升性能与扩展性）

4. **推理后端抽象（PyTorch / ONNX / TensorRT）**
	- 与论文中的“可导出与加速”方向一致。
	- 目标：同一接口切换后端，便于性能对比实验。

5. **批处理队列模式**
	- 支持多视频排队处理、失败重试、任务日志归档。

6. **更细粒度日志与可观测性**
	- 增加每阶段耗时（解码/推理/编码/合并）统计。
	- 输出到日志文件，便于毕业论文实验数据复现。

### P2（长期规划，提升论文深度）

7. **时序超分模型接入（如 BasicVSR++）**
	- 目前项目已具备良好的分层与线程结构，可继续扩展模型适配器。

8. **客观指标评估模块**
	- 增加 PSNR/SSIM/LPIPS 的离线评估脚本，支持论文量化对比。

9. **CLI 模式与无界面批处理**
	- 便于服务器/实验室环境跑大规模对比实验。

---

## 10. 已知注意事项

- 首次加载模型耗时较长，属正常现象。
- 4K/高倍率建议开启分块与 FP16。
- Windows 中文路径下 OpenCV 某些模型加载存在兼容性问题，项目已对关键场景做路径规避处理。

---

## 11. 致谢

本项目用于毕业设计实践，感谢 Real-ESRGAN、GFPGAN、RIFE、OpenCV、FFmpeg、PyQt5 等开源社区。