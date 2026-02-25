"""
视频预览与对比控件
支持左右分栏对比（原始 vs 增强）、滑块拖动对比
"""
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QSlider, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap


def numpy_to_qpixmap(rgb_array: np.ndarray, max_width: int = 0, max_height: int = 0) -> QPixmap:
    """
    将 RGB numpy 数组转换为 QPixmap

    Args:
        rgb_array: RGB uint8 数组 (H, W, 3)
        max_width: 最大显示宽度（0=不限制）
        max_height: 最大显示高度（0=不限制）

    Returns:
        QPixmap 对象
    """
    h, w, ch = rgb_array.shape
    bytes_per_line = ch * w
    q_image = QImage(rgb_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(q_image)

    if max_width > 0 or max_height > 0:
        target_w = max_width if max_width > 0 else pixmap.width()
        target_h = max_height if max_height > 0 else pixmap.height()
        pixmap = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    return pixmap


class VideoPreviewWidget(QWidget):
    """
    视频预览控件
    左侧显示原始帧，右侧显示增强后帧
    """

    frame_slider_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ---- 预览区域 ----
        preview_layout = QHBoxLayout()

        # 左侧：原始视频
        left_container = QVBoxLayout()
        self.original_label_title = QLabel("原始画面")
        self.original_label_title.setAlignment(Qt.AlignCenter)
        self.original_label_title.setStyleSheet(
            "color: #aaa; font-size: 12px; padding: 2px;"
        )
        self.original_display = QLabel()
        self.original_display.setAlignment(Qt.AlignCenter)
        self.original_display.setMinimumSize(320, 240)
        self.original_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.original_display.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;"
        )
        self.original_display.setText("拖拽视频到此处\n或点击「导入视频」")
        self.original_display.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; "
            "border-radius: 4px; color: #666; font-size: 14px;"
        )
        left_container.addWidget(self.original_label_title)
        left_container.addWidget(self.original_display)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #555;")

        # 右侧：增强后视频
        right_container = QVBoxLayout()
        self.enhanced_label_title = QLabel("增强效果")
        self.enhanced_label_title.setAlignment(Qt.AlignCenter)
        self.enhanced_label_title.setStyleSheet(
            "color: #aaa; font-size: 12px; padding: 2px;"
        )
        self.enhanced_display = QLabel()
        self.enhanced_display.setAlignment(Qt.AlignCenter)
        self.enhanced_display.setMinimumSize(320, 240)
        self.enhanced_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.enhanced_display.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; "
            "border-radius: 4px; color: #666; font-size: 14px;"
        )
        self.enhanced_display.setText("增强效果将在此显示")
        right_container.addWidget(self.enhanced_label_title)
        right_container.addWidget(self.enhanced_display)

        preview_layout.addLayout(left_container)
        preview_layout.addWidget(separator)
        preview_layout.addLayout(right_container)

        layout.addLayout(preview_layout)

        # ---- 帧滑块 ----
        slider_layout = QHBoxLayout()
        self.frame_label = QLabel("帧: 0 / 0")
        self.frame_label.setStyleSheet("color: #ccc; font-size: 11px;")
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.setValue(0)
        self.frame_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #444;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 3px;
            }
        """)
        self.frame_slider.valueChanged.connect(self._on_slider_changed)

        slider_layout.addWidget(self.frame_label)
        slider_layout.addWidget(self.frame_slider)
        layout.addLayout(slider_layout)

    def set_total_frames(self, total: int):
        """设置总帧数（更新滑块范围）"""
        self.frame_slider.setMaximum(max(0, total - 1))
        self.frame_label.setText(f"帧: 0 / {total}")

    def update_original(self, rgb_frame: np.ndarray):
        """更新原始画面"""
        display_size = self.original_display.size()
        pixmap = numpy_to_qpixmap(rgb_frame, display_size.width(), display_size.height())
        self.original_display.setPixmap(pixmap)

    def update_enhanced(self, rgb_frame: np.ndarray):
        """更新增强画面"""
        display_size = self.enhanced_display.size()
        pixmap = numpy_to_qpixmap(rgb_frame, display_size.width(), display_size.height())
        self.enhanced_display.setPixmap(pixmap)

    def clear_displays(self):
        """清空预览"""
        self.original_display.clear()
        self.original_display.setText("拖拽视频到此处\n或点击「导入视频」")
        self.enhanced_display.clear()
        self.enhanced_display.setText("增强效果将在此显示")
        self.frame_slider.setValue(0)
        self.frame_slider.setMaximum(0)

    def _on_slider_changed(self, value: int):
        total = self.frame_slider.maximum() + 1
        self.frame_label.setText(f"帧: {value} / {total}")
        self.frame_slider_changed.emit(value)
