"""
主窗口
整合所有 UI 组件，协调 UI 层与业务逻辑层的交互
"""
import os
import sys
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QAction, QMenuBar, QStatusBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SUPPORTED_VIDEO_FORMATS, MODELS, WEIGHTS_DIR
from ui.video_preview import VideoPreviewWidget
from ui.parameter_panel import ParameterPanel
from utils.ffmpeg_utils import get_video_info
from utils.video_io import get_video_properties, read_single_frame
from utils.color_utils import bgr_to_rgb
from core.worker_thread import VideoWorkerThread, PreviewWorkerThread


class MainWindow(QMainWindow):
    """
    AI视频增强系统 - 主窗口
    布局: 左侧预览区 + 右侧控制面板
    """

    def __init__(self):
        super().__init__()
        self._input_path = ""
        self._enhancer = None
        self._worker_thread = None
        self._preview_thread = None

        self._init_window()
        self._init_menu()
        self._init_ui()
        self._connect_signals()

    def _init_window(self):
        """初始化窗口属性"""
        self.setWindowTitle("AI 视频增强系统 v1.0")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: #eee;")

        # 启用拖拽
        self.setAcceptDrops(True)

    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet(
            "QMenuBar { background-color: #333; color: #eee; }"
            "QMenuBar::item:selected { background-color: #0078d4; }"
            "QMenu { background-color: #3c3c3c; color: #eee; }"
            "QMenu::item:selected { background-color: #0078d4; }"
        )

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        import_action = QAction("导入视频(&I)", self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self._on_import_video)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_ui(self):
        """初始化界面布局"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 左侧：视频预览区
        self.preview_widget = VideoPreviewWidget()
        main_layout.addWidget(self.preview_widget, stretch=1)

        # 右侧：参数控制面板
        self.param_panel = ParameterPanel()
        main_layout.addWidget(self.param_panel)

        # 状态栏
        self.statusBar().showMessage("就绪 - 请导入视频文件")
        self.statusBar().setStyleSheet("color: #aaa; font-size: 11px;")

    def _connect_signals(self):
        """连接信号与槽"""
        # 参数面板按钮
        self.param_panel.import_video.connect(self._on_import_video)
        self.param_panel.start_processing.connect(self._on_start_processing)
        self.param_panel.cancel_processing.connect(self._on_cancel_processing)
        self.param_panel.preview_requested.connect(self._on_preview_frame)

        # 帧滑块
        self.preview_widget.frame_slider_changed.connect(self._on_frame_slider_changed)

    # =====================================================
    # 事件处理
    # =====================================================

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if any(url.toLocalFile().lower().endswith(ext)
                       for ext in SUPPORTED_VIDEO_FORMATS):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if any(file_path.lower().endswith(ext) for ext in SUPPORTED_VIDEO_FORMATS):
                self._load_video(file_path)
                return

    # =====================================================
    # 槽函数
    # =====================================================

    def _on_import_video(self):
        """导入视频文件"""
        ext_filter = "视频文件 (" + " ".join(
            f"*{ext}" for ext in SUPPORTED_VIDEO_FORMATS
        ) + ")"

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "", ext_filter
        )
        if file_path:
            self._load_video(file_path)

    def _load_video(self, file_path: str):
        """加载视频文件并更新UI"""
        try:
            self._input_path = file_path
            info = get_video_info(file_path)
            props = get_video_properties(file_path)

            # 更新参数面板
            self.param_panel.update_video_info(info)

            # 更新预览区
            self.preview_widget.set_total_frames(props["total_frames"])

            # 显示第一帧
            first_frame = read_single_frame(file_path, 0)
            if first_frame is not None:
                rgb_frame = bgr_to_rgb(first_frame)
                self.preview_widget.update_original(rgb_frame)

            self.statusBar().showMessage(f"已加载: {os.path.basename(file_path)}")
            self.param_panel.append_log(f"✓ 导入视频: {os.path.basename(file_path)}")
            self.param_panel.append_log(
                f"  分辨率: {info['width']}×{info['height']}, "
                f"帧率: {info['fps']:.2f}, 帧数: {info['total_frames']}"
            )

        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法读取视频文件:\n{str(e)}")

    def _on_frame_slider_changed(self, frame_index: int):
        """帧滑块变化时更新预览"""
        if not self._input_path:
            return
        frame = read_single_frame(self._input_path, frame_index)
        if frame is not None:
            rgb_frame = bgr_to_rgb(frame)
            self.preview_widget.update_original(rgb_frame)

    def _load_enhancer(self) -> bool:
        """加载 AI 模型"""
        params = self.param_panel.get_parameters()
        model_key = params["model_key"]
        model_config = MODELS[model_key]

        # 检查权重文件
        weight_path = os.path.join(WEIGHTS_DIR, model_config["weight_file"])
        if not os.path.exists(weight_path):
            QMessageBox.warning(
                self, "缺少模型权重",
                f"模型权重文件不存在:\n{weight_path}\n\n"
                f"请下载:\n{model_config['weight_url']}\n\n"
                f"并放到:\n{WEIGHTS_DIR}"
            )
            return False

        try:
            self.param_panel.append_log(f"正在加载模型: {model_config['name']}...")

            if "GFPGAN" in model_key:
                from models.gfpgan_enhancer import GFPGANEnhancer
                self._enhancer = GFPGANEnhancer()
                self._enhancer.load_model(
                    weight_path=weight_path,
                    upscale=params["scale"],
                )
            else:
                from models.realesrgan_enhancer import RealESRGANEnhancer
                self._enhancer = RealESRGANEnhancer()
                self._enhancer.load_model(
                    weight_path=weight_path,
                    model_key=model_key,
                    half=params["half"],
                )

            self.param_panel.append_log(f"✓ 模型加载完成")
            return True

        except Exception as e:
            QMessageBox.critical(self, "模型加载失败", str(e))
            self.param_panel.append_log(f"✗ 模型加载失败: {str(e)}")
            return False

    def _on_preview_frame(self):
        """预览当前帧的增强效果"""
        if not self._input_path:
            QMessageBox.information(self, "提示", "请先导入视频")
            return

        if not self._load_enhancer():
            return

        params = self.param_panel.get_parameters()
        frame_index = self.preview_widget.frame_slider.value()

        self.param_panel.append_log(f"正在预览第 {frame_index} 帧...")
        self.statusBar().showMessage("正在生成预览...")

        self._preview_thread = PreviewWorkerThread(self)
        self._preview_thread.setup(
            enhancer=self._enhancer,
            input_path=self._input_path,
            frame_index=frame_index,
            use_tiling=params["use_tiling"],
            tile_size=params["tile_size"],
            tile_pad=params["tile_pad"],
        )
        self._preview_thread.result_signal.connect(self._on_preview_result)
        self._preview_thread.error_signal.connect(self._on_preview_error)
        self._preview_thread.start()

    def _on_preview_result(self, original: np.ndarray, enhanced: np.ndarray):
        """预览结果"""
        self.preview_widget.update_original(original)
        self.preview_widget.update_enhanced(enhanced)
        self.statusBar().showMessage("预览完成")
        self.param_panel.append_log("✓ 预览生成完成")

    def _on_preview_error(self, error_msg: str):
        """预览出错"""
        QMessageBox.critical(self, "预览失败", error_msg)
        self.statusBar().showMessage("预览失败")

    def _on_start_processing(self):
        """开始视频处理"""
        if not self._input_path:
            QMessageBox.information(self, "提示", "请先导入视频")
            return

        if not self._load_enhancer():
            return

        params = self.param_panel.get_parameters()

        # 切换UI为处理状态
        self.param_panel.set_processing_state(True)
        self.param_panel.progress_bar.setValue(0)
        self.param_panel.append_log("="*40)
        self.param_panel.append_log("🚀 开始视频处理")

        # 创建并启动工作线程
        self._worker_thread = VideoWorkerThread(self)
        self._worker_thread.setup(
            enhancer=self._enhancer,
            input_path=self._input_path,
            use_tiling=params["use_tiling"],
            tile_size=params["tile_size"],
            tile_pad=params["tile_pad"],
        )

        # 连接信号
        self._worker_thread.progress_signal.connect(self._on_processing_progress)
        self._worker_thread.preview_signal.connect(self._on_processing_preview)
        self._worker_thread.finished_signal.connect(self._on_processing_finished)
        self._worker_thread.error_signal.connect(self._on_processing_error)
        self._worker_thread.status_signal.connect(self._on_processing_status)

        self._worker_thread.start()

    def _on_cancel_processing(self):
        """取消处理"""
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.cancel()
            self.param_panel.append_log("⏹ 正在取消...")

    def _on_processing_progress(self, current: int, total: int, fps: float):
        """处理进度更新"""
        self.param_panel.update_progress(current, total, fps)

    def _on_processing_preview(self, rgb_frame: np.ndarray):
        """处理中的预览帧"""
        self.preview_widget.update_enhanced(rgb_frame)

    def _on_processing_finished(self, output_path: str):
        """处理完成"""
        self.param_panel.set_processing_state(False)
        self.param_panel.progress_bar.setValue(100)
        self.param_panel.lbl_status.setText("处理完成！")
        self.param_panel.append_log(f"✓ 处理完成: {output_path}")
        self.statusBar().showMessage(f"输出: {output_path}")

        QMessageBox.information(
            self, "处理完成",
            f"视频增强完成！\n\n输出路径:\n{output_path}"
        )

    def _on_processing_error(self, error_msg: str):
        """处理出错"""
        self.param_panel.set_processing_state(False)
        self.param_panel.append_log(f"✗ 错误: {error_msg}")
        self.statusBar().showMessage("处理失败")
        QMessageBox.critical(self, "处理失败", error_msg)

    def _on_processing_status(self, message: str):
        """处理状态更新"""
        self.statusBar().showMessage(message)
        self.param_panel.append_log(message)

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "AI 视频增强系统 v1.0\n\n"
            "基于深度学习的视频超分辨率与画质增强\n\n"
            "技术栈: PyTorch + OpenCV + FFmpeg + PyQt5\n"
            "模型: Real-ESRGAN / GFPGAN\n\n"
            "毕业设计作品"
        )

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self._worker_thread and self._worker_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "视频正在处理中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self._worker_thread.cancel()
            self._worker_thread.wait(3000)

        # 释放模型
        if self._enhancer:
            self._enhancer.release()

        event.accept()
