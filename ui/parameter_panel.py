"""
参数配置面板
提供模型选择、放大倍率、降噪程度、Tiling 参数等控件
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QPushButton, QProgressBar, QTextEdit,
    QSlider, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from config import MODELS, DEFAULT_TILE_SIZE, DEFAULT_TILE_PAD, DEFAULT_SCALE, DEFAULT_INTERP_MULTI


class ParameterPanel(QWidget):
    """
    右侧参数配置面板
    包含模型选择、处理参数、补帧设置、操作按钮和日志输出
    """

    # 信号
    start_processing = pyqtSignal()
    cancel_processing = pyqtSignal()
    start_interpolation = pyqtSignal()     # 开始补帧
    start_combined = pyqtSignal()          # 超分 + 补帧联合处理
    import_batch_videos = pyqtSignal()     # 批量导入视频
    open_batch_manager = pyqtSignal()      # 打开完整队列管理界面
    start_batch_queue = pyqtSignal()       # 启动批处理队列
    clear_batch_queue = pyqtSignal()       # 清空批处理队列
    remove_batch_task = pyqtSignal(int)    # 移除指定任务
    retry_batch_task = pyqtSignal(int)     # 重试失败任务
    compare_batch_task = pyqtSignal(int)   # 对比指定任务
    preview_requested = pyqtSignal()
    preview_toggled = pyqtSignal(bool)     # 实时预览开关状态变化
    compare_requested = pyqtSignal()       # 视频对比播放
    import_video = pyqtSignal()

    # Windows 下支持 emoji 显示的字体
    EMOJI_FONT = QFont("Segoe UI Emoji", 10)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(340)
        self._init_ui()

    def _init_ui(self):
        # 使用 QScrollArea 包裹，防止控件过多时溢出
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

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
        model_layout.setSpacing(8)

        # 模型选择
        model_layout.addWidget(QLabel("增强模式:"))
        self.combo_model = QComboBox()
        self.combo_model.setFont(self.EMOJI_FONT)
        for key, cfg in MODELS.items():
            icon = cfg.get('icon', '')
            display = cfg.get('display_name', cfg['name'])
            self.combo_model.addItem(f"{icon} {display}", key)
        self.combo_model.setStyleSheet(self._combo_style())
        self.combo_model.setToolTip("选择适合视频内容的增强模式")
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.combo_model)

        # 模型说明
        self.lbl_model_desc = QLabel("")
        self.lbl_model_desc.setWordWrap(True)
        self.lbl_model_desc.setStyleSheet("color: #999; font-size: 11px; padding: 2px 4px;")
        model_layout.addWidget(self.lbl_model_desc)

        # 放大倍率 (可自定义，默认跟随模型)
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("放大倍率:"))
        self.spin_scale = QSpinBox()
        self.spin_scale.setRange(1, 4)
        self.spin_scale.setValue(DEFAULT_SCALE)
        self.spin_scale.setStyleSheet(self._spin_style())
        self.spin_scale.setToolTip("设置输出视频的放大倍率\n切换模型时自动同步，也可手动调整")
        scale_layout.addWidget(self.spin_scale)
        scale_layout.addWidget(QLabel("x"))
        model_layout.addLayout(scale_layout)

        # 降噪强度 (滑块 + 输入框 联动)
        denoise_layout = QVBoxLayout()
        denoise_header = QHBoxLayout()
        denoise_header.addWidget(QLabel("降噪强度:"))
        self.spin_denoise = QDoubleSpinBox()
        self.spin_denoise.setRange(0.0, 1.0)
        self.spin_denoise.setSingleStep(0.1)
        self.spin_denoise.setDecimals(1)
        self.spin_denoise.setValue(0.0)
        self.spin_denoise.setFixedWidth(65)
        self.spin_denoise.setStyleSheet(self._spin_style())
        self.spin_denoise.setToolTip("设为 0 关闭降噪\n数值越大降噪越强但细节会减少")
        self.spin_denoise.valueChanged.connect(self._on_denoise_spin_changed)
        denoise_header.addWidget(self.spin_denoise)
        denoise_header.addStretch()
        denoise_layout.addLayout(denoise_header)

        self.slider_denoise = QSlider(Qt.Horizontal)
        self.slider_denoise.setRange(0, 10)  # 0~10 对应 0.0~1.0
        self.slider_denoise.setValue(0)
        self.slider_denoise.setTickPosition(QSlider.TicksBelow)
        self.slider_denoise.setTickInterval(1)
        self.slider_denoise.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #444; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4; width: 14px; margin: -5px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4; border-radius: 2px;
            }
        """)
        self.slider_denoise.valueChanged.connect(self._on_denoise_slider_changed)
        denoise_layout.addWidget(self.slider_denoise)
        model_layout.addLayout(denoise_layout)

        # 初始化模型描述
        self._on_model_changed(0)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # ========== 高级设置 ==========
        adv_group = QGroupBox("高级设置")
        adv_group.setStyleSheet(self._group_style())
        adv_layout = QVBoxLayout()
        adv_layout.setSpacing(8)

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

        # ========== 补帧设置 ==========
        interp_group = QGroupBox("补帧设置 (RIFE)")
        interp_group.setStyleSheet(self._group_style())
        interp_layout = QVBoxLayout()
        interp_layout.setSpacing(8)

        # 补帧倍率
        multi_layout = QHBoxLayout()
        multi_layout.addWidget(QLabel("补帧倍率:"))
        self.combo_interp_multi = QComboBox()
        self.combo_interp_multi.addItem("2x (双倍帧率)", 2)
        self.combo_interp_multi.addItem("4x (四倍帧率)", 4)
        self.combo_interp_multi.setCurrentIndex(0 if DEFAULT_INTERP_MULTI == 2 else 1)
        self.combo_interp_multi.setStyleSheet(self._combo_style())
        self.combo_interp_multi.setToolTip("选择帧率提升倍数\n2x: 30fps → 60fps\n4x: 30fps → 120fps")
        multi_layout.addWidget(self.combo_interp_multi)
        interp_layout.addLayout(multi_layout)

        # 目标帧率提示
        self.lbl_interp_info = QLabel("📝 导入视频后显示目标帧率")
        self.lbl_interp_info.setWordWrap(True)
        self.lbl_interp_info.setStyleSheet("color: #999; font-size: 11px; padding: 2px 4px;")
        interp_layout.addWidget(self.lbl_interp_info)

        interp_group.setLayout(interp_layout)
        layout.addWidget(interp_group)

        # ========== 批处理队列 ==========
        batch_group = QGroupBox("批处理队列")
        batch_group.setStyleSheet(self._group_style())
        batch_layout = QVBoxLayout()
        batch_layout.setSpacing(8)

        # 队列模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("队列模式:"))
        self.combo_batch_mode = QComboBox()
        self.combo_batch_mode.addItem("超分", "sr")
        self.combo_batch_mode.addItem("补帧", "interp")
        self.combo_batch_mode.addItem("超分 + 补帧", "combined")
        self.combo_batch_mode.setStyleSheet(self._combo_style())
        mode_layout.addWidget(self.combo_batch_mode)
        batch_layout.addLayout(mode_layout)

        # 批处理主按钮
        batch_btn_row = QHBoxLayout()
        self.btn_import_batch = QPushButton("📚 批量导入")
        self.btn_import_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_import_batch.clicked.connect(self.import_batch_videos.emit)
        batch_btn_row.addWidget(self.btn_import_batch)

        self.btn_start_batch = QPushButton("▶ 开始队列")
        self.btn_start_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_start_batch.clicked.connect(self.start_batch_queue.emit)
        batch_btn_row.addWidget(self.btn_start_batch)

        self.btn_clear_batch = QPushButton("🧹 清空")
        self.btn_clear_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_clear_batch.clicked.connect(self.clear_batch_queue.emit)
        batch_btn_row.addWidget(self.btn_clear_batch)
        batch_layout.addLayout(batch_btn_row)

        self.btn_open_batch_manager = QPushButton("🗂 打开队列管理器")
        self.btn_open_batch_manager.setStyleSheet(self._btn_secondary_style())
        self.btn_open_batch_manager.clicked.connect(self.open_batch_manager.emit)
        batch_layout.addWidget(self.btn_open_batch_manager)

        # 队列表格
        self.table_batch = QTableWidget(0, 5)
        self.table_batch.setHorizontalHeaderLabels(["ID", "文件", "模式", "状态", "进度"])
        self.table_batch.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_batch.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_batch.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_batch.verticalHeader().setVisible(False)
        self.table_batch.setAlternatingRowColors(True)
        self.table_batch.setMaximumHeight(180)
        self.table_batch.setStyleSheet("""
            QTableWidget {
                background-color: #1f1f1f;
                color: #ddd;
                border: 1px solid #444;
                gridline-color: #444;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ddd;
                border: 1px solid #444;
                padding: 3px;
                font-size: 11px;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        header = self.table_batch.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_batch.setColumnHidden(0, True)  # 隐藏内部ID
        batch_layout.addWidget(self.table_batch)

        # 队列条目操作
        batch_item_row = QHBoxLayout()
        self.btn_remove_batch = QPushButton("➖ 移除")
        self.btn_remove_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_remove_batch.clicked.connect(self._emit_remove_batch_task)
        batch_item_row.addWidget(self.btn_remove_batch)

        self.btn_retry_batch = QPushButton("🔁 重试失败")
        self.btn_retry_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_retry_batch.clicked.connect(self._emit_retry_batch_task)
        batch_item_row.addWidget(self.btn_retry_batch)

        self.btn_compare_batch = QPushButton("🎬 对比选中")
        self.btn_compare_batch.setStyleSheet(self._btn_secondary_style())
        self.btn_compare_batch.clicked.connect(self._emit_compare_batch_task)
        batch_item_row.addWidget(self.btn_compare_batch)
        batch_layout.addLayout(batch_item_row)

        self.lbl_batch_info = QLabel("队列: 0 条")
        self.lbl_batch_info.setStyleSheet("color: #999; font-size: 11px;")
        batch_layout.addWidget(self.lbl_batch_info)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        # ========== 操作按钮 ==========
        # 实时预览开关
        preview_row = QHBoxLayout()
        self.btn_preview = QPushButton("👁 预览当前帧")
        self.btn_preview.setMinimumHeight(36)
        self.btn_preview.setStyleSheet(self._btn_secondary_style())
        self.btn_preview.clicked.connect(self.preview_requested.emit)
        preview_row.addWidget(self.btn_preview)

        self.btn_realtime_preview = QPushButton("🔴 实时预览")
        self.btn_realtime_preview.setMinimumHeight(36)
        self.btn_realtime_preview.setCheckable(True)
        self.btn_realtime_preview.setChecked(False)
        self.btn_realtime_preview.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #0078d4; }
            QPushButton:checked {
                background-color: #0078d4;
                color: white;
                border-color: #0078d4;
            }
            QPushButton:disabled { background-color: #2a2a2a; color: #666; }
        """)
        self.btn_realtime_preview.toggled.connect(self._on_realtime_toggled)
        preview_row.addWidget(self.btn_realtime_preview)
        layout.addLayout(preview_row)

        self.btn_start = QPushButton("🚀 开始超分")
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

        self.btn_interpolate = QPushButton("🎞️ 开始补帧")
        self.btn_interpolate.setMinimumHeight(44)
        self.btn_interpolate.setStyleSheet("""
            QPushButton {
                background-color: #6b3fa0;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7d4dbd; }
            QPushButton:pressed { background-color: #5a3590; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_interpolate.clicked.connect(self.start_interpolation.emit)
        layout.addWidget(self.btn_interpolate)

        self.btn_combined = QPushButton("超分 + 补帧")
        self.btn_combined.setMinimumHeight(44)
        self.btn_combined.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:pressed { background-color: #0a4f7d; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_combined.setToolTip("先超分再补帧，一键完成两项处理")
        self.btn_combined.clicked.connect(self.start_combined.emit)
        layout.addWidget(self.btn_combined)

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

        # 视频对比播放
        self.btn_compare = QPushButton("🎬 对比播放")
        self.btn_compare.setMinimumHeight(36)
        self.btn_compare.setEnabled(False)
        self.btn_compare.setStyleSheet(self._btn_secondary_style())
        self.btn_compare.setToolTip("处理完成后，同步播放原始与增强视频进行对比")
        self.btn_compare.clicked.connect(self.compare_requested.emit)
        layout.addWidget(self.btn_compare)

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

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

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

    def get_interp_multiplier(self) -> int:
        """获取当前补帧倍率"""
        return self.combo_interp_multi.currentData()

    def get_batch_mode(self) -> str:
        """获取批处理队列模式"""
        return self.combo_batch_mode.currentData()

    def add_batch_item(self, task_id: int, file_name: str, mode_text: str):
        """向批处理表格添加任务"""
        row = self.table_batch.rowCount()
        self.table_batch.insertRow(row)
        self.table_batch.setItem(row, 0, QTableWidgetItem(str(task_id)))
        self.table_batch.setItem(row, 1, QTableWidgetItem(file_name))
        self.table_batch.setItem(row, 2, QTableWidgetItem(mode_text))
        self.table_batch.setItem(row, 3, QTableWidgetItem("等待中"))
        self.table_batch.setItem(row, 4, QTableWidgetItem("0%"))
        self._update_batch_info()

    def update_batch_item(self, task_id: int, status: str = None, progress: str = None):
        """更新批处理任务状态/进度"""
        row = self._find_batch_row(task_id)
        if row < 0:
            return
        if status is not None:
            self.table_batch.setItem(row, 3, QTableWidgetItem(status))
        if progress is not None:
            self.table_batch.setItem(row, 4, QTableWidgetItem(progress))

    def remove_batch_item(self, task_id: int):
        """从批处理表格移除任务"""
        row = self._find_batch_row(task_id)
        if row >= 0:
            self.table_batch.removeRow(row)
            self._update_batch_info()

    def clear_batch_items(self):
        """清空批处理表格"""
        self.table_batch.setRowCount(0)
        self._update_batch_info()

    def set_batch_running_state(self, running: bool):
        """设置批处理队列运行状态"""
        self.btn_import_batch.setEnabled(not running)
        self.btn_start_batch.setEnabled(not running)
        self.btn_clear_batch.setEnabled(not running)
        self.btn_open_batch_manager.setEnabled(not running)
        self.btn_remove_batch.setEnabled(not running)
        self.btn_retry_batch.setEnabled(not running)

    def update_interp_info(self, original_fps: float):
        """根据原始帧率更新补帧信息提示"""
        multi = self.get_interp_multiplier()
        target_fps = original_fps * multi
        self.lbl_interp_info.setText(
            f"📝 {original_fps:.1f}fps → {target_fps:.0f}fps ({multi}x 补帧)"
        )

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
        self.btn_interpolate.setEnabled(not processing)
        self.btn_combined.setEnabled(not processing)
        self.btn_start_batch.setEnabled(not processing)
        self.btn_import_batch.setEnabled(not processing)
        self.btn_open_batch_manager.setEnabled(not processing)
        self.btn_cancel.setEnabled(processing)
        self.btn_import.setEnabled(not processing)
        self.btn_preview.setEnabled(not processing)
        self.btn_realtime_preview.setEnabled(not processing)
        self.combo_model.setEnabled(not processing)
        self.combo_interp_multi.setEnabled(not processing)
        # 处理中关闭实时预览
        if processing and self.btn_realtime_preview.isChecked():
            self.btn_realtime_preview.setChecked(False)

    def update_progress(self, current: int, total: int, fps: float):
        """更新进度条"""
        if total > 0:
            percent = int(current / total * 100)
            self.progress_bar.setValue(percent)
            remaining = (total - current) / fps if fps > 0 else 0
            self.lbl_status.setText(
                f"处理中: {current}/{total} 帧 | {fps:.2f} fps | 预计剩余: {remaining:.0f}s"
            )

    def is_realtime_preview_on(self) -> bool:
        """实时预览是否开启"""
        return self.btn_realtime_preview.isChecked()

    def _on_model_changed(self, index: int):
        """模型选择变化时更新说明和放大倍率"""
        model_key = self.combo_model.currentData()
        if model_key and model_key in MODELS:
            cfg = MODELS[model_key]
            self.lbl_model_desc.setText(f"📝 {cfg['description']}")
            self.spin_scale.setValue(cfg['scale'])

    def _on_denoise_spin_changed(self, value: float):
        """降噪输入框变化 → 同步滑块"""
        slider_val = int(round(value * 10))
        self.slider_denoise.blockSignals(True)
        self.slider_denoise.setValue(slider_val)
        self.slider_denoise.blockSignals(False)

    def _on_denoise_slider_changed(self, value: int):
        """降噪滑块变化 → 同步输入框"""
        spin_val = value / 10.0
        self.spin_denoise.blockSignals(True)
        self.spin_denoise.setValue(spin_val)
        self.spin_denoise.blockSignals(False)

    def _on_realtime_toggled(self, checked: bool):
        """实时预览开关切换"""
        if checked:
            self.btn_realtime_preview.setText("🟢 实时预览")
        else:
            self.btn_realtime_preview.setText("🔴 实时预览")
        self.preview_toggled.emit(checked)

    def append_log(self, message: str):
        """追加日志"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _selected_batch_task_id(self) -> int:
        rows = self.table_batch.selectionModel().selectedRows()
        if not rows:
            return -1
        row = rows[0].row()
        item = self.table_batch.item(row, 0)
        if not item:
            return -1
        try:
            return int(item.text())
        except Exception:
            return -1

    def _find_batch_row(self, task_id: int) -> int:
        for row in range(self.table_batch.rowCount()):
            item = self.table_batch.item(row, 0)
            if item and item.text() == str(task_id):
                return row
        return -1

    def _update_batch_info(self):
        self.lbl_batch_info.setText(f"队列: {self.table_batch.rowCount()} 条")

    def _emit_remove_batch_task(self):
        tid = self._selected_batch_task_id()
        if tid > 0:
            self.remove_batch_task.emit(tid)

    def _emit_retry_batch_task(self):
        tid = self._selected_batch_task_id()
        if tid > 0:
            self.retry_batch_task.emit(tid)

    def _emit_compare_batch_task(self):
        tid = self._selected_batch_task_id()
        if tid > 0:
            self.compare_batch_task.emit(tid)

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
                padding: 6px 10px;
                min-height: 24px;
                font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3c3c3c;
                color: #eee;
                selection-background-color: #0078d4;
                font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif;
                font-size: 13px;
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
                padding: 4px 6px;
                min-height: 22px;
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
