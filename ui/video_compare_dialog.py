"""
视频对比播放对话框
支持原始视频与增强后视频同步播放、逐帧对比
按时间同步：即使两个视频帧率不同（如补帧前后），也能正确同步
"""
import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QDialog, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QSlider, QComboBox, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap


def _frame_to_pixmap(bgr_frame: np.ndarray, max_w: int, max_h: int) -> QPixmap:
    """BGR numpy → QPixmap（缩放到指定区域）"""
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888)
    pm = QPixmap.fromImage(qimg)
    if max_w > 0 and max_h > 0:
        pm = pm.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


class VideoCompareDialog(QDialog):
    """
    双视频同步播放对比窗口

    左侧播放原始视频，右侧播放增强后视频，
    共享一个播放控制器（进度条、播放/暂停、倍速）。

    使用时间同步而非帧索引同步，以正确处理帧率不同的情况
    （例如超分前后分辨率不同但帧率相同，或补帧后帧率翻倍等）。
    """

    def __init__(self, original_path: str, enhanced_path: str, parent=None):
        super().__init__(parent)
        self._orig_path = original_path
        self._enh_path = enhanced_path

        # OpenCV captures
        self._cap_orig = None
        self._cap_enh = None

        # 各视频独立的属性
        self._fps_orig = 30.0
        self._fps_enh = 30.0
        self._total_frames_orig = 0
        self._total_frames_enh = 0

        # 时间控制（以毫秒为单位）
        self._duration_ms = 0       # 视频时长（取较短的）
        self._current_time_ms = 0   # 当前播放位置（毫秒）
        self._playing = False
        self._speed = 1.0

        # 播放定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        # 定时器基础间隔（毫秒），用原始视频帧间隔
        self._tick_interval_ms = 33.0  # 约30fps

        self._init_ui()
        self._open_videos()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("视频对比播放")
        self.setMinimumSize(1000, 600)
        self.resize(1280, 720)
        self.setStyleSheet("background-color: #2b2b2b; color: #eee;")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- 视频显示区 ----
        video_row = QHBoxLayout()

        # 左侧：原始
        left_box = QVBoxLayout()
        self.lbl_orig_title = QLabel("原始视频")
        self.lbl_orig_title.setAlignment(Qt.AlignCenter)
        self.lbl_orig_title.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold;")
        self.lbl_orig = QLabel()
        self.lbl_orig.setAlignment(Qt.AlignCenter)
        self.lbl_orig.setMinimumSize(480, 360)
        self.lbl_orig.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_orig.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;"
        )
        left_box.addWidget(self.lbl_orig_title)
        left_box.addWidget(self.lbl_orig)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #555;")

        # 右侧：增强
        right_box = QVBoxLayout()
        self.lbl_enh_title = QLabel("增强视频")
        self.lbl_enh_title.setAlignment(Qt.AlignCenter)
        self.lbl_enh_title.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold;")
        self.lbl_enh = QLabel()
        self.lbl_enh.setAlignment(Qt.AlignCenter)
        self.lbl_enh.setMinimumSize(480, 360)
        self.lbl_enh.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_enh.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;"
        )
        right_box.addWidget(self.lbl_enh_title)
        right_box.addWidget(self.lbl_enh)

        video_row.addLayout(left_box)
        video_row.addWidget(sep)
        video_row.addLayout(right_box)
        root.addLayout(video_row, stretch=1)

        # ---- 进度条 ----
        slider_row = QHBoxLayout()
        self.lbl_frame_info = QLabel("00:00.0 / 00:00.0")
        self.lbl_frame_info.setFixedWidth(160)
        self.lbl_frame_info.setStyleSheet("color: #ccc; font-size: 12px;")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #444; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4; width: 14px; margin: -4px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4; border-radius: 3px;
            }
        """)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.valueChanged.connect(self._on_slider_value_changed)

        self.lbl_time = QLabel("")
        self.lbl_time.setFixedWidth(200)
        self.lbl_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_time.setStyleSheet("color: #ccc; font-size: 12px;")

        slider_row.addWidget(self.lbl_frame_info)
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.lbl_time)
        root.addLayout(slider_row)

        # ---- 控制按钮 ----
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        btn_style = """
            QPushButton {
                background-color: #3c3c3c; color: #eee;
                border: 1px solid #555; border-radius: 6px;
                font-size: 14px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #0078d4; }
            QPushButton:pressed { background-color: #555; }
        """

        # 上一帧
        self.btn_prev = QPushButton("⏮ 上一帧")
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.clicked.connect(self._step_prev)
        ctrl_row.addWidget(self.btn_prev)

        # 播放 / 暂停
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setMinimumWidth(100)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold; padding: 6px 20px;
            }
            QPushButton:hover { background-color: #1a8ae8; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self.btn_play)

        # 下一帧
        self.btn_next = QPushButton("⏭ 下一帧")
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.clicked.connect(self._step_next)
        ctrl_row.addWidget(self.btn_next)

        # 停止
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setStyleSheet(btn_style)
        self.btn_stop.clicked.connect(self._stop)
        ctrl_row.addWidget(self.btn_stop)

        ctrl_row.addStretch()

        # 倍速选择
        ctrl_row.addWidget(QLabel("倍速:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1.0x", "1.5x", "2.0x"])
        self.combo_speed.setCurrentIndex(2)  # 默认 1.0x
        self.combo_speed.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c; color: #eee;
                border: 1px solid #555; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #3c3c3c; color: #eee;
                selection-background-color: #0078d4;
            }
        """)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        ctrl_row.addWidget(self.combo_speed)

        # 分辨率信息
        self.lbl_res = QLabel("")
        self.lbl_res.setStyleSheet("color: #888; font-size: 11px; margin-left: 12px;")
        ctrl_row.addWidget(self.lbl_res)

        root.addLayout(ctrl_row)

    # ------------------------------------------------------------------
    # 视频控制
    # ------------------------------------------------------------------
    def _open_videos(self):
        """打开两个视频文件，初始化时间同步参数"""
        self._cap_orig = cv2.VideoCapture(self._orig_path)
        self._cap_enh = cv2.VideoCapture(self._enh_path)

        if not self._cap_orig.isOpened() or not self._cap_enh.isOpened():
            self.lbl_orig.setText("无法打开视频")
            return

        # 各自的帧率和帧数
        self._fps_orig = self._cap_orig.get(cv2.CAP_PROP_FPS) or 30.0
        self._fps_enh = self._cap_enh.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames_orig = int(self._cap_orig.get(cv2.CAP_PROP_FRAME_COUNT))
        self._total_frames_enh = int(self._cap_enh.get(cv2.CAP_PROP_FRAME_COUNT))

        # 各自的时长（毫秒）
        dur_orig_ms = self._total_frames_orig / self._fps_orig * 1000.0
        dur_enh_ms = self._total_frames_enh / self._fps_enh * 1000.0
        # 取较短的时长，避免越界
        self._duration_ms = min(dur_orig_ms, dur_enh_ms)

        # slider 范围 = 0 ~ duration_ms（整数毫秒）
        self.slider.setMaximum(max(0, int(self._duration_ms)))
        self._current_time_ms = 0

        # 定时器间隔 = 原始视频帧间隔（用于逐帧推进时间）
        self._tick_interval_ms = 1000.0 / self._fps_orig if self._fps_orig > 0 else 33.0

        # 分辨率信息
        w_o = int(self._cap_orig.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_o = int(self._cap_orig.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w_e = int(self._cap_enh.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_e = int(self._cap_enh.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.lbl_res.setText(
            f"原始: {w_o}×{h_o} @ {self._fps_orig:.2f}fps  |  "
            f"增强: {w_e}×{h_e} @ {self._fps_enh:.2f}fps"
        )

        self.lbl_orig_title.setText(f"原始视频 ({w_o}×{h_o}, {self._fps_orig:.1f}fps)")
        self.lbl_enh_title.setText(f"增强视频 ({w_e}×{h_e}, {self._fps_enh:.1f}fps)")

        self._update_labels()
        self._show_at_time(0)

    def _time_to_frame(self, time_ms: float, fps: float, total_frames: int) -> int:
        """将时间位置（毫秒）转换为帧索引"""
        if fps <= 0:
            return 0
        frame_idx = int(time_ms / 1000.0 * fps)
        return max(0, min(frame_idx, total_frames - 1))

    def _show_at_time(self, time_ms: float):
        """按时间同步显示两个视频对应的帧"""
        if self._cap_orig is None or self._cap_enh is None:
            return

        time_ms = max(0, min(time_ms, self._duration_ms))
        self._current_time_ms = time_ms

        # 分别计算各自的帧索引
        idx_orig = self._time_to_frame(time_ms, self._fps_orig, self._total_frames_orig)
        idx_enh = self._time_to_frame(time_ms, self._fps_enh, self._total_frames_enh)

        # Seek & read 原始视频
        self._cap_orig.set(cv2.CAP_PROP_POS_FRAMES, idx_orig)
        ret1, frame_orig = self._cap_orig.read()

        # Seek & read 增强视频
        self._cap_enh.set(cv2.CAP_PROP_POS_FRAMES, idx_enh)
        ret2, frame_enh = self._cap_enh.read()

        if ret1:
            sz = self.lbl_orig.size()
            pm = _frame_to_pixmap(frame_orig, sz.width(), sz.height())
            self.lbl_orig.setPixmap(pm)
        if ret2:
            sz = self.lbl_enh.size()
            pm = _frame_to_pixmap(frame_enh, sz.width(), sz.height())
            self.lbl_enh.setPixmap(pm)

        self._update_labels()

    def _update_labels(self):
        """更新时间显示和进度条位置"""
        cur_sec = self._current_time_ms / 1000.0
        tot_sec = self._duration_ms / 1000.0

        # 时间显示
        self.lbl_frame_info.setText(
            f"{self._fmt_time(cur_sec)} / {self._fmt_time(tot_sec)}"
        )

        # slider 位置（不回触发信号）
        self.slider.blockSignals(True)
        self.slider.setValue(int(self._current_time_ms))
        self.slider.blockSignals(False)

        # 右侧显示帧号信息
        idx_orig = self._time_to_frame(
            self._current_time_ms, self._fps_orig, self._total_frames_orig
        )
        idx_enh = self._time_to_frame(
            self._current_time_ms, self._fps_enh, self._total_frames_enh
        )
        self.lbl_time.setText(
            f"原始帧: {idx_orig}/{self._total_frames_orig}  |  "
            f"增强帧: {idx_enh}/{self._total_frames_enh}"
        )

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        m = int(seconds) // 60
        s = seconds - m * 60
        return f"{m:02d}:{s:04.1f}"

    # ------------------------------------------------------------------
    # 播放定时器
    # ------------------------------------------------------------------
    def _timer_interval(self) -> int:
        """根据原始帧间隔和倍速计算定时器间隔 (ms)"""
        interval = self._tick_interval_ms / self._speed if self._speed > 0 else 33
        return max(1, int(interval))

    def _on_tick(self):
        """定时器回调：按时间推进播放"""
        # 每次推进一个原始帧的时间间隔
        advance_ms = self._tick_interval_ms
        new_time = self._current_time_ms + advance_ms

        if new_time >= self._duration_ms:
            self._current_time_ms = self._duration_ms
            self._update_labels()
            self._stop()
            return

        self._show_at_time(new_time)

    # ------------------------------------------------------------------
    # 按钮槽
    # ------------------------------------------------------------------
    def _toggle_play(self):
        if self._playing:
            self._pause()
        else:
            self._play()

    def _play(self):
        if self._duration_ms <= 0:
            return
        # 如果已到末尾，从头开始
        if self._current_time_ms >= self._duration_ms - 1:
            self._show_at_time(0)
        self._playing = True
        self.btn_play.setText("⏸ 暂停")
        self._timer.start(self._timer_interval())

    def _pause(self):
        self._playing = False
        self._timer.stop()
        self.btn_play.setText("▶ 播放")

    def _stop(self):
        self._pause()
        self._show_at_time(0)

    def _step_prev(self):
        """按原始帧间隔后退一帧"""
        self._pause()
        new_time = self._current_time_ms - self._tick_interval_ms
        self._show_at_time(max(0, new_time))

    def _step_next(self):
        """按原始帧间隔前进一帧"""
        self._pause()
        new_time = self._current_time_ms + self._tick_interval_ms
        self._show_at_time(min(self._duration_ms, new_time))

    def _on_speed_changed(self, index: int):
        speeds = [0.25, 0.5, 1.0, 1.5, 2.0]
        self._speed = speeds[index] if index < len(speeds) else 1.0
        if self._playing:
            self._timer.setInterval(self._timer_interval())

    # ------------------------------------------------------------------
    # 进度条交互
    # ------------------------------------------------------------------
    def _on_slider_pressed(self):
        """拖动开始时暂停播放"""
        if self._playing:
            self._timer.stop()

    def _on_slider_released(self):
        """拖动结束时跳转并可能恢复播放"""
        time_ms = self.slider.value()
        self._show_at_time(time_ms)
        if self._playing:
            self._timer.start(self._timer_interval())

    def _on_slider_value_changed(self, value: int):
        """拖动时实时更新显示（仅在拖动状态下）"""
        if self.slider.isSliderDown():
            self._show_at_time(value)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        """关闭时释放资源"""
        self._timer.stop()
        if self._cap_orig:
            self._cap_orig.release()
            self._cap_orig = None
        if self._cap_enh:
            self._cap_enh.release()
            self._cap_enh = None
        super().closeEvent(event)
