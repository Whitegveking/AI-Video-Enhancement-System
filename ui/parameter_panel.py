"""
参数配置面板
提供模型选择、放大倍率、降噪程度、Tiling 参数等控件
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QPushButton, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from config import MODELS, DEFAULT_TILE_SIZE, DEFAULT_TILE_PAD, DEFAULT_SCALE


class ParameterPanel(QWidget):
    """
    右侧参数配置面板
    包含模型选择、处理参数、操作按钮和日志输出
    """

    # 信号
    start_processing = pyqtSignal()
    cancel_processing = pyqtSignal()
    preview_requested = pyqtSignal()
    import_video = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ========== 导入按钮 ==========
        self.btn_import = QPushButton("📂 导入视频")
        self.btn_import.setMinimumHeight(40)
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1a8ae8; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        self.btn_import.clicked.connect(self.import_video.emit)
        layout.addWidget(self.btn_import)

        # ========== 视频信息 ==========
        info_group = QGroupBox("视频信息")
        info_group.setStyleSheet(self._group_style())
        info_layout = QVBoxLayout()
        self.lbl_video_info = QLabel("未导入视频")
        self.lbl_video_info.setWordWrap(True)
        self.lbl_video_info.setStyleSheet("color: #bbb; font-size: 12px;")
        info_layout.addWidget(self.lbl_video_info)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # ========== 模型设置 ==========
        model_group = QGroupBox("AI 模型设置")
        model_group.setStyleSheet(self._group_style())
        model_layout = QVBoxLayout()

        # 模型选择
        model_layout.addWidget(QLabel("模型:"))
        self.combo_model = QComboBox()
        for key, cfg in MODELS.items():
            self.combo_model.addItem(f"{cfg['name']} - {cfg['description']}", key)
        self.combo_model.setStyleSheet(self._combo_style())
        model_layout.addWidget(self.combo_model)

        # 放大倍率
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("放大倍率:"))
        self.spin_scale = QSpinBox()
        self.spin_scale.setRange(1, 4)
        self.spin_scale.setValue(DEFAULT_SCALE)
        self.spin_scale.setStyleSheet(self._spin_style())
        scale_layout.addWidget(self.spin_scale)
        scale_layout.addWidget(QLabel("x"))
        model_layout.addLayout(scale_layout)

        # 降噪强度
        denoise_layout = QHBoxLayout()
        denoise_layout.addWidget(QLabel("降噪强度:"))
        self.spin_denoise = QDoubleSpinBox()
        self.spin_denoise.setRange(0.0, 1.0)
        self.spin_denoise.setSingleStep(0.1)
        self.spin_denoise.setValue(0.5)
        self.spin_denoise.setStyleSheet(self._spin_style())
        denoise_layout.addWidget(self.spin_denoise)
        model_layout.addLayout(denoise_layout)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # ========== 高级设置 ==========
        adv_group = QGroupBox("高级设置")
        adv_group.setStyleSheet(self._group_style())
        adv_layout = QVBoxLayout()

        # Tiling 开关
        self.chk_tiling = QCheckBox("启用分块处理 (防止显存溢出)")
        self.chk_tiling.setChecked(True)
        self.chk_tiling.setStyleSheet("color: #ccc;")
        adv_layout.addWidget(self.chk_tiling)

        # 分块大小
        tile_layout = QHBoxLayout()
        tile_layout.addWidget(QLabel("分块大小:"))
        self.spin_tile_size = QSpinBox()
        self.spin_tile_size.setRange(128, 1024)
        self.spin_tile_size.setSingleStep(64)
        self.spin_tile_size.setValue(DEFAULT_TILE_SIZE)
        self.spin_tile_size.setStyleSheet(self._spin_style())
        tile_layout.addWidget(self.spin_tile_size)
        tile_layout.addWidget(QLabel("px"))
        adv_layout.addLayout(tile_layout)

        # 重叠填充
        pad_layout = QHBoxLayout()
        pad_layout.addWidget(QLabel("重叠填充:"))
        self.spin_tile_pad = QSpinBox()
        self.spin_tile_pad.setRange(0, 128)
        self.spin_tile_pad.setSingleStep(8)
        self.spin_tile_pad.setValue(DEFAULT_TILE_PAD)
        self.spin_tile_pad.setStyleSheet(self._spin_style())
        pad_layout.addWidget(self.spin_tile_pad)
        pad_layout.addWidget(QLabel("px"))
        adv_layout.addLayout(pad_layout)

        # FP16 半精度
        self.chk_half = QCheckBox("FP16 半精度 (降低显存占用)")
        self.chk_half.setChecked(True)
        self.chk_half.setStyleSheet("color: #ccc;")
        adv_layout.addWidget(self.chk_half)

        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # ========== 操作按钮 ==========
        self.btn_preview = QPushButton("👁 预览当前帧")
        self.btn_preview.setMinimumHeight(36)
        self.btn_preview.setStyleSheet(self._btn_secondary_style())
        self.btn_preview.clicked.connect(self.preview_requested.emit)
        layout.addWidget(self.btn_preview)

        self.btn_start = QPushButton("🚀 开始处理")
        self.btn_start.setMinimumHeight(44)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1a9c1a; }
            QPushButton:pressed { background-color: #0c5e0c; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_start.clicked.connect(self.start_processing.emit)
        layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("⏹ 取消处理")
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #d13438;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_cancel.clicked.connect(self.cancel_processing.emit)
        layout.addWidget(self.btn_cancel)

        # ========== 进度条 ==========
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #333;
                text-align: center;
                color: white;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # ========== 日志输出 ==========
        log_group = QGroupBox("处理日志")
        log_group.setStyleSheet(self._group_style())
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet(
            "background-color: #1a1a1a; color: #0f0; "
            "border: 1px solid #444; font-family: Consolas; font-size: 11px;"
        )
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

    # ========== 公共方法 ==========

    def get_model_key(self) -> str:
        """获取选中的模型配置键名"""
        return self.combo_model.currentData()

    def get_parameters(self) -> dict:
        """获取当前所有参数设置"""
        return {
            "model_key": self.get_model_key(),
            "scale": self.spin_scale.value(),
            "denoise": self.spin_denoise.value(),
            "use_tiling": self.chk_tiling.isChecked(),
            "tile_size": self.spin_tile_size.value(),
            "tile_pad": self.spin_tile_pad.value(),
            "half": self.chk_half.isChecked(),
        }

    def update_video_info(self, info: dict):
        """更新视频信息显示"""
        text = (
            f"文件: {info.get('filename', 'N/A')}\n"
            f"分辨率: {info.get('width', 0)}×{info.get('height', 0)}\n"
            f"帧率: {info.get('fps', 0):.2f} fps\n"
            f"帧数: {info.get('total_frames', 0)}\n"
            f"时长: {info.get('duration', 0):.1f}s\n"
            f"编码: {info.get('video_codec', 'N/A')}\n"
            f"音频: {'有' if info.get('has_audio') else '无'}"
        )
        self.lbl_video_info.setText(text)

    def set_processing_state(self, processing: bool):
        """设置处理状态（禁用/启用控件）"""
        self.btn_start.setEnabled(not processing)
        self.btn_cancel.setEnabled(processing)
        self.btn_import.setEnabled(not processing)
        self.btn_preview.setEnabled(not processing)
        self.combo_model.setEnabled(not processing)

    def update_progress(self, current: int, total: int, fps: float):
        """更新进度条"""
        if total > 0:
            percent = int(current / total * 100)
            self.progress_bar.setValue(percent)
            remaining = (total - current) / fps if fps > 0 else 0
            self.lbl_status.setText(
                f"处理中: {current}/{total} 帧 | {fps:.2f} fps | 预计剩余: {remaining:.0f}s"
            )

    def append_log(self, message: str):
        """追加日志"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ========== 样式 ==========

    @staticmethod
    def _group_style() -> str:
        return """
            QGroupBox {
                color: #ddd;
                border: 1px solid #555;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel { color: #ccc; font-size: 12px; }
        """

    @staticmethod
    def _combo_style() -> str:
        return """
            QComboBox {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3c3c3c;
                color: #eee;
                selection-background-color: #0078d4;
            }
        """

    @staticmethod
    def _spin_style() -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """

    @staticmethod
    def _btn_secondary_style() -> str:
        return """
            QPushButton {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #0078d4; }
            QPushButton:pressed { background-color: #333; }
            QPushButton:disabled { background-color: #2a2a2a; color: #666; }
        """
