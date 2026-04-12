"""
独立批处理队列窗口
支持：批量导入、队列执行、单任务独立参数编辑
"""
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from config import MODELS, SUPPORTED_VIDEO_FORMATS


class BatchQueueDialog(QDialog):
    """批处理队列独立窗口"""

    EMOJI_FONT = QFont("Segoe UI Emoji", 10)

    import_tasks = pyqtSignal(object, str, object, int)   # file_paths, mode, params, multiplier
    start_queue = pyqtSignal()
    clear_queue = pyqtSignal()
    remove_task = pyqtSignal(int)
    retry_task = pyqtSignal(int)
    compare_task = pyqtSignal(int)
    save_task_config = pyqtSignal(int, str, object, int)  # task_id, mode, params, multiplier

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_map = {}
        self._updating_form = False
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("批处理队列管理器")
        self.resize(1200, 760)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(self._dialog_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        # 左侧：任务列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 顶部操作区（并入左侧，减少整窗顶部空白）
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.btn_import = QPushButton("📚 批量导入视频")
        self.btn_import.setMinimumHeight(36)
        self.btn_import.setStyleSheet(self._btn_secondary_style())
        self.btn_import.clicked.connect(self._on_import_clicked)
        top_row.addWidget(self.btn_import)

        self.btn_start = QPushButton("▶ 开始队列")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.setStyleSheet(self._btn_secondary_style())
        self.btn_start.clicked.connect(self.start_queue.emit)
        top_row.addWidget(self.btn_start)

        self.btn_clear = QPushButton("🧹 清空队列")
        self.btn_clear.setMinimumHeight(36)
        self.btn_clear.setStyleSheet(self._btn_secondary_style())
        self.btn_clear.clicked.connect(self.clear_queue.emit)
        top_row.addWidget(self.btn_clear)

        top_row.addStretch()
        self.lbl_summary = QLabel("队列: 0 条")
        self.lbl_summary.setStyleSheet("color: #999;")
        top_row.addWidget(self.lbl_summary)
        left_layout.addLayout(top_row)

        self.table_tasks = QTableWidget(0, 6)
        self.table_tasks.setHorizontalHeaderLabels(["ID", "文件", "模式", "状态", "进度", "输出"])
        self.table_tasks.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_tasks.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_tasks.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_tasks.verticalHeader().setVisible(False)
        self.table_tasks.setAlternatingRowColors(True)
        self.table_tasks.setStyleSheet(self._table_style())
        self.table_tasks.itemSelectionChanged.connect(self._on_task_selected)

        header = self.table_tasks.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.table_tasks.setColumnHidden(0, True)

        left_layout.addWidget(self.table_tasks, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 4, 0, 0)
        action_row.setSpacing(10)
        self.btn_remove = QPushButton("➖ 移除")
        self.btn_remove.setMinimumHeight(36)
        self.btn_remove.setStyleSheet(self._btn_secondary_style())
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        action_row.addWidget(self.btn_remove)

        self.btn_retry = QPushButton("🔁 重试失败")
        self.btn_retry.setMinimumHeight(36)
        self.btn_retry.setStyleSheet(self._btn_secondary_style())
        self.btn_retry.clicked.connect(self._on_retry_clicked)
        action_row.addWidget(self.btn_retry)

        self.btn_compare = QPushButton("🎬 对比选中")
        self.btn_compare.setMinimumHeight(36)
        self.btn_compare.setStyleSheet(self._btn_secondary_style())
        self.btn_compare.clicked.connect(self._on_compare_clicked)
        action_row.addWidget(self.btn_compare)

        left_layout.addLayout(action_row)

        splitter.addWidget(left_widget)

        # 右侧：选中任务参数
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        group = QGroupBox("选中任务独立参数")
        group.setStyleSheet(self._group_style())
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        form = QFormLayout(group)

        self.lbl_selected = QLabel("未选中任务")
        self.lbl_selected.setStyleSheet("color: #999;")
        form.addRow("当前任务:", self.lbl_selected)

        self.combo_mode = QComboBox()
        self.combo_mode.setStyleSheet(self._combo_style())
        self.combo_mode.setFont(self.EMOJI_FONT)
        self.combo_mode.addItem("超分", "sr")
        self.combo_mode.addItem("补帧", "interp")
        self.combo_mode.addItem("超分 + 补帧", "combined")
        form.addRow("任务模式:", self.combo_mode)

        self.combo_model = QComboBox()
        self.combo_model.setStyleSheet(self._combo_style())
        self.combo_model.setFont(self.EMOJI_FONT)
        for key, cfg in MODELS.items():
            icon = cfg.get("icon", "")
            display = cfg.get("display_name", cfg.get("name", key))
            self.combo_model.addItem(f"{icon} {display}", key)
        form.addRow("增强模型:", self.combo_model)

        self.spin_scale = QSpinBox()
        self.spin_scale.setStyleSheet(self._spin_style())
        self.spin_scale.setRange(1, 4)
        self.spin_scale.setValue(4)
        form.addRow("放大倍率:", self.spin_scale)

        self.spin_denoise = QDoubleSpinBox()
        self.spin_denoise.setStyleSheet(self._spin_style())
        self.spin_denoise.setRange(0.0, 1.0)
        self.spin_denoise.setSingleStep(0.1)
        self.spin_denoise.setDecimals(1)
        self.spin_denoise.setValue(0.0)
        form.addRow("降噪强度:", self.spin_denoise)

        self.chk_tiling = QCheckBox("启用分块")
        self.chk_tiling.setStyleSheet(self._checkbox_style())
        self.chk_tiling.setChecked(True)
        form.addRow("分块处理:", self.chk_tiling)

        self.spin_tile_size = QSpinBox()
        self.spin_tile_size.setStyleSheet(self._spin_style())
        self.spin_tile_size.setRange(128, 1024)
        self.spin_tile_size.setSingleStep(64)
        self.spin_tile_size.setValue(512)
        form.addRow("分块大小:", self.spin_tile_size)

        self.spin_tile_pad = QSpinBox()
        self.spin_tile_pad.setStyleSheet(self._spin_style())
        self.spin_tile_pad.setRange(0, 128)
        self.spin_tile_pad.setSingleStep(8)
        self.spin_tile_pad.setValue(32)
        form.addRow("重叠填充:", self.spin_tile_pad)

        self.chk_half = QCheckBox("FP16 半精度")
        self.chk_half.setStyleSheet(self._checkbox_style())
        self.chk_half.setChecked(True)
        form.addRow("推理精度:", self.chk_half)

        self.combo_interp_multi = QComboBox()
        self.combo_interp_multi.setStyleSheet(self._combo_style())
        self.combo_interp_multi.addItem("2x", 2)
        self.combo_interp_multi.addItem("4x", 4)
        form.addRow("补帧倍率:", self.combo_interp_multi)

        right_layout.addWidget(group, 0, Qt.AlignTop)

        self.btn_save = QPushButton("💾 保存到选中任务")
        self.btn_save.setMinimumHeight(36)
        self.btn_save.setStyleSheet(self._btn_secondary_style())
        self.btn_save.clicked.connect(self._on_save_clicked)
        right_layout.addWidget(self.btn_save, 0, Qt.AlignTop)

        right_layout.addStretch(1)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 5)

        root.addWidget(splitter, 1)

    def _status_text(self, status: str) -> str:
        return {
            "pending": "等待中",
            "running": "处理中",
            "done": "已完成",
            "failed": "失败",
            "cancelled": "已取消",
        }.get(status, status)

    def _mode_text(self, mode: str) -> str:
        return {
            "sr": "超分",
            "interp": "补帧",
            "combined": "超分+补帧",
        }.get(mode, mode)

    def _collect_form_params(self) -> dict:
        return {
            "model_key": self.combo_model.currentData(),
            "scale": self.spin_scale.value(),
            "denoise": self.spin_denoise.value(),
            "use_tiling": self.chk_tiling.isChecked(),
            "tile_size": self.spin_tile_size.value(),
            "tile_pad": self.spin_tile_pad.value(),
            "half": self.chk_half.isChecked(),
        }

    def _set_form_from_task(self, task):
        self._updating_form = True
        try:
            params = task.params or {}

            idx_mode = self.combo_mode.findData(task.mode)
            if idx_mode >= 0:
                self.combo_mode.setCurrentIndex(idx_mode)

            idx_model = self.combo_model.findData(params.get("model_key", "RealESRGAN_x4"))
            if idx_model >= 0:
                self.combo_model.setCurrentIndex(idx_model)

            self.spin_scale.setValue(int(params.get("scale", 4)))
            self.spin_denoise.setValue(float(params.get("denoise", 0.0)))
            self.chk_tiling.setChecked(bool(params.get("use_tiling", True)))
            self.spin_tile_size.setValue(int(params.get("tile_size", 512)))
            self.spin_tile_pad.setValue(int(params.get("tile_pad", 32)))
            self.chk_half.setChecked(bool(params.get("half", True)))

            idx_multi = self.combo_interp_multi.findData(task.multiplier)
            if idx_multi >= 0:
                self.combo_interp_multi.setCurrentIndex(idx_multi)

            self.lbl_selected.setText(
                f"#{task.task_id} - {os.path.basename(task.input_path)} ({self._status_text(task.status)})"
            )
        finally:
            self._updating_form = False

    def _selected_task_id(self) -> int:
        rows = self.table_tasks.selectionModel().selectedRows()
        if not rows:
            return -1
        item = self.table_tasks.item(rows[0].row(), 0)
        if not item:
            return -1
        try:
            return int(item.text())
        except Exception:
            return -1

    def _find_row(self, task_id: int) -> int:
        for row in range(self.table_tasks.rowCount()):
            item = self.table_tasks.item(row, 0)
            if item and item.text() == str(task_id):
                return row
        return -1

    def refresh_tasks(self, tasks):
        selected_tid = self._selected_task_id()
        self._task_map = {t.task_id: t for t in tasks}

        self.table_tasks.setRowCount(0)
        for task in tasks:
            row = self.table_tasks.rowCount()
            self.table_tasks.insertRow(row)

            self.table_tasks.setItem(row, 0, QTableWidgetItem(str(task.task_id)))
            self.table_tasks.setItem(row, 1, QTableWidgetItem(os.path.basename(task.input_path)))
            self.table_tasks.setItem(row, 2, QTableWidgetItem(self._mode_text(task.mode)))
            self.table_tasks.setItem(row, 3, QTableWidgetItem(self._status_text(task.status)))
            self.table_tasks.setItem(row, 4, QTableWidgetItem(f"{int(task.progress)}%"))
            self.table_tasks.setItem(row, 5, QTableWidgetItem(task.output_path or "-"))

        if selected_tid > 0:
            row = self._find_row(selected_tid)
            if row >= 0:
                self.table_tasks.selectRow(row)
        self.lbl_summary.setText(f"队列: {len(tasks)} 条")

    def update_task_item(self, task):
        row = self._find_row(task.task_id)
        if row < 0:
            return
        self.table_tasks.setItem(row, 2, QTableWidgetItem(self._mode_text(task.mode)))
        self.table_tasks.setItem(row, 3, QTableWidgetItem(self._status_text(task.status)))
        self.table_tasks.setItem(row, 4, QTableWidgetItem(f"{int(task.progress)}%"))
        self.table_tasks.setItem(row, 5, QTableWidgetItem(task.output_path or "-"))
        self._task_map[task.task_id] = task

    def set_running_state(self, running: bool):
        self.btn_import.setEnabled(not running)
        self.btn_start.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
        self.btn_remove.setEnabled(not running)
        self.btn_retry.setEnabled(not running)

    def _on_import_clicked(self):
        ext_filter = "视频文件 (" + " ".join(f"*{ext}" for ext in SUPPORTED_VIDEO_FORMATS) + ")"
        file_paths, _ = QFileDialog.getOpenFileNames(self, "批量选择视频文件", "", ext_filter)
        if not file_paths:
            return
        self.import_tasks.emit(
            file_paths,
            self.combo_mode.currentData(),
            self._collect_form_params(),
            self.combo_interp_multi.currentData(),
        )

    def _on_task_selected(self):
        tid = self._selected_task_id()
        if tid <= 0:
            self.lbl_selected.setText("未选中任务")
            return
        task = self._task_map.get(tid)
        if task:
            self._set_form_from_task(task)

    def _on_save_clicked(self):
        tid = self._selected_task_id()
        if tid <= 0:
            QMessageBox.information(self, "提示", "请先选中一个任务")
            return
        self.save_task_config.emit(
            tid,
            self.combo_mode.currentData(),
            self._collect_form_params(),
            self.combo_interp_multi.currentData(),
        )

    def _on_remove_clicked(self):
        tid = self._selected_task_id()
        if tid > 0:
            self.remove_task.emit(tid)

    def _on_retry_clicked(self):
        tid = self._selected_task_id()
        if tid > 0:
            self.retry_task.emit(tid)

    def _on_compare_clicked(self):
        tid = self._selected_task_id()
        if tid > 0:
            self.compare_task.emit(tid)

    @staticmethod
    def _dialog_style() -> str:
        return """
            QDialog {
                background-color: #2b2b2b;
                color: #eee;
            }
            QLabel {
                color: #ccc;
                font-size: 12px;
            }
            QSplitter::handle {
                background-color: #3a3a3a;
                width: 1px;
            }
        """

    @staticmethod
    def _group_style() -> str:
        return """
            QGroupBox {
                color: #ddd;
                border: 1px solid #555;
                border-radius: 8px;
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
        """

    @staticmethod
    def _combo_style() -> str:
        return """
            QComboBox {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 6px;
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
                border-radius: 6px;
                padding: 4px 6px;
                min-height: 22px;
            }
        """

    @staticmethod
    def _checkbox_style() -> str:
        return """
            QCheckBox {
                color: #ddd;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 4px;
                border: 1px solid #666;
                background: #2f2f2f;
            }
            QCheckBox::indicator:checked {
                background: #0078d4;
                border: 1px solid #0078d4;
            }
        """

    @staticmethod
    def _btn_secondary_style() -> str:
        return """
            QPushButton {
                background-color: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #0078d4; }
            QPushButton:pressed { background-color: #333; }
            QPushButton:disabled { background-color: #2a2a2a; color: #666; }
        """

    @staticmethod
    def _table_style() -> str:
        return """
            QTableWidget {
                background-color: #1f1f1f;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 8px;
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
        """
