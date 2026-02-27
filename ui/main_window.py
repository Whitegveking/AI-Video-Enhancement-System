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
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SUPPORTED_VIDEO_FORMATS, MODELS, WEIGHTS_DIR
from ui.video_preview import VideoPreviewWidget
from ui.parameter_panel import ParameterPanel
from ui.video_compare_dialog import VideoCompareDialog
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
        self._realtime_preview_on = False
        self._cached_model_key = None  # 记录已加载的模型key，避免重复加载
        self._output_path = ""  # 最近一次处理的输出文件路径
        self._auto_resolved_key = None  # 自动模式检测缓存，每个视频只检测一次
        self._auto_resolved_for = ""  # 记录上次自动检测对应的视频路径

        # 防抖定时器：滑块拖动时延迟200ms再触发预览
        self._preview_debounce_timer = QTimer(self)
        self._preview_debounce_timer.setSingleShot(True)
        self._preview_debounce_timer.setInterval(200)
        self._preview_debounce_timer.timeout.connect(self._on_debounced_preview)
        self._pending_preview_frame = 0

        self._init_window()
        self._init_menu()
        self._init_ui()
        self._connect_signals()

    def _init_window(self):
        """初始化窗口属性"""
        self.setWindowTitle("AI 视频增强系统 v1.0")
        self.setMinimumSize(1100, 700)
        self.resize(1600, 1000)
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
        self.param_panel.preview_toggled.connect(self._on_realtime_preview_toggled)
        self.param_panel.compare_requested.connect(self._on_compare_videos)

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
            # 清除自动模型检测缓存（新视频需重新检测）
            self._auto_resolved_key = None
            self._auto_resolved_for = ""
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

        # 实时预览模式：用防抖定时器延迟触发增强预览
        if self._realtime_preview_on:
            self._pending_preview_frame = frame_index
            self._preview_debounce_timer.start()  # 重新计时

    def _on_realtime_preview_toggled(self, checked: bool):
        """实时预览开关状态变化"""
        self._realtime_preview_on = checked
        if checked:
            if not self._input_path:
                QMessageBox.information(self, "提示", "请先导入视频")
                self.param_panel.btn_realtime_preview.setChecked(False)
                return
            # 开启时加载模型
            if not self._load_enhancer():
                self.param_panel.btn_realtime_preview.setChecked(False)
                return
            self.statusBar().showMessage("实时预览已开启 - 拖动帧滑块查看增强效果")
            self.param_panel.append_log("🟢 实时预览已开启")
            # 立即预览当前帧
            self._pending_preview_frame = self.preview_widget.frame_slider.value()
            self._on_debounced_preview()
        else:
            self._preview_debounce_timer.stop()
            self.statusBar().showMessage("实时预览已关闭")
            self.param_panel.append_log("🔴 实时预览已关闭")

    def _on_debounced_preview(self):
        """防抖后触发的实时预览（滑块停止拖动300ms后执行）"""
        if not self._realtime_preview_on or not self._input_path:
            return
        if not self._enhancer or not self._enhancer.is_loaded:
            return
        # 如果上一个预览线程还在跑，跳过（等下次触发）
        if self._preview_thread and self._preview_thread.isRunning():
            return

        params = self.param_panel.get_parameters()
        frame_index = self._pending_preview_frame

        self._preview_thread = PreviewWorkerThread(self)
        self._preview_thread.setup(
            enhancer=self._enhancer,
            input_path=self._input_path,
            frame_index=frame_index,
            use_tiling=params["use_tiling"],
            tile_size=params["tile_size"],
            tile_pad=params["tile_pad"],
            denoise_strength=params["denoise"],
            outscale=params["scale"],
        )
        self._preview_thread.result_signal.connect(self._on_preview_result)
        self._preview_thread.error_signal.connect(self._on_preview_error)
        self._preview_thread.start()

    def _resolve_model_key(self) -> str:
        """
        解析实际使用的模型 key。
        如果用户选择了 "Auto"，则自动分析视频的第一帧来选择模型：
        - 检测到人脸 → GFPGAN
        - 否则 → RealESRGAN_x4
        同一视频只检测一次，结果缓存。
        """
        params = self.param_panel.get_parameters()
        model_key = params["model_key"]

        if model_key != "Auto":
            return model_key

        if not self._input_path:
            return "RealESRGAN_x4"

        # 缓存：同一视频只检测一次
        if (self._auto_resolved_key
                and self._auto_resolved_for == self._input_path):
            return self._auto_resolved_key

        self.param_panel.append_log("🔍 正在分析视频内容...")

        try:
            import cv2
            frame = read_single_frame(self._input_path, 0)
            if frame is None:
                self.param_panel.append_log("  无法读取帧，默认使用通用超分")
                chosen = "RealESRGAN_x4"
            else:
                # OpenCV 的 CascadeClassifier 不支持中文路径，
                # 用 Python 读取 XML 后写到系统临时目录（纯 ASCII 路径）
                import shutil
                import tempfile
                cascade_src = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "weights", "haarcascade_frontalface_default.xml"
                )
                tmp_dir = os.path.join(tempfile.gettempdir(), "aivideo_cache")
                os.makedirs(tmp_dir, exist_ok=True)
                cascade_tmp = os.path.join(tmp_dir, "haarcascade_frontalface_default.xml")
                if not os.path.exists(cascade_tmp):
                    shutil.copy2(cascade_src, cascade_tmp)

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                face_cascade = cv2.CascadeClassifier(cascade_tmp)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )

                if len(faces) > 0:
                    chosen = "GFPGAN_v1.4"
                    self.param_panel.append_log(f"  检测到 {len(faces)} 张人脸 → 使用人像修复模式")
                else:
                    chosen = "RealESRGAN_x4"
                    self.param_panel.append_log("  未检测到人脸 → 使用通用超分模式")

            # 缓存结果
            self._auto_resolved_key = chosen
            self._auto_resolved_for = self._input_path

            # 更新 UI 的放大倍率显示
            self.param_panel.spin_scale.setValue(MODELS[chosen]["scale"])
            return chosen

        except Exception as e:
            self.param_panel.append_log(f"  自动检测出错: {e}，默认使用通用超分")
            return "RealESRGAN_x4"

    def _load_enhancer(self) -> bool:
        """加载 AI 模型（已加载相同模型时跳过，避免重复加载）"""
        model_key = self._resolve_model_key()
        model_config = MODELS[model_key]
        params = self.param_panel.get_parameters()

        # 如果已经加载了相同的模型，直接返回
        if (self._enhancer and self._enhancer.is_loaded
                and self._cached_model_key == model_key):
            return True

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
            display = f"{model_config['icon']} {model_config['display_name']}"
            self.param_panel.append_log(f"正在加载模型: {display}...")

            if "GFPGAN" in model_key:
                from models.gfpgan_enhancer import GFPGANEnhancer
                self._enhancer = GFPGANEnhancer()
                self._enhancer.load_model(
                    weight_path=weight_path,
                    upscale=model_config["scale"],
                )
            else:
                from models.realesrgan_enhancer import RealESRGANEnhancer
                self._enhancer = RealESRGANEnhancer()
                self._enhancer.load_model(
                    weight_path=weight_path,
                    model_key=model_key,
                    half=params["half"],
                )

            self._cached_model_key = model_key
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
            denoise_strength=params["denoise"],
            outscale=params["scale"],
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
            denoise_strength=params["denoise"],
            outscale=params["scale"],
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
        self._output_path = output_path
        self.param_panel.set_processing_state(False)
        self.param_panel.progress_bar.setValue(100)
        self.param_panel.lbl_status.setText("处理完成！")
        self.param_panel.append_log(f"✓ 处理完成: {output_path}")
        self.statusBar().showMessage(f"输出: {output_path}")

        # 启用对比播放按钮
        self.param_panel.btn_compare.setEnabled(True)

        QMessageBox.information(
            self, "处理完成",
            f"视频增强完成！\n\n输出路径:\n{output_path}\n\n"
            f"点击「🎬 对比播放」可同步对比原始与增强视频"
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

        # 取消处理后恢复 UI 状态
        if "已取消" in message:
            self.param_panel.set_processing_state(False)
            self.param_panel.lbl_status.setText("已取消")
            self.param_panel.append_log("⏹ 处理已取消，可重新操作")

    def _on_compare_videos(self):
        """打开视频对比播放窗口"""
        if not self._input_path or not self._output_path:
            QMessageBox.information(self, "提示", "请先处理视频后再进行对比播放")
            return
        if not os.path.exists(self._output_path):
            QMessageBox.warning(self, "文件不存在",
                                f"增强视频文件不存在:\n{self._output_path}")
            return

        self.param_panel.append_log("🎬 打开视频对比播放...")
        dlg = VideoCompareDialog(self._input_path, self._output_path, parent=self)
        dlg.exec_()

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
