import sys
import os
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QFileDialog, QRadioButton,
    QButtonGroup, QTextEdit, QTabWidget, QGroupBox, QScrollArea,
    QProgressBar, QMessageBox, QSplitter, QFrame, QSlider, QComboBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QSpinBox, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QGraphicsOpacityEffect, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# Get the project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add parent directory to path to import main module
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from main import process_video

# Import manual tracking module
try:
    from frontend.manual_tracking import ManualTrackingData, TrackingEvent
except ImportError:
    # If import fails, create dummy classes
    class ManualTrackingData:
        def __init__(self):
            self.events = []
    class TrackingEvent:
        pass
from frontend.manual_tracking import ManualTrackingData, TrackingEvent
from frontend.translations import get_translation_manager, t


class VideoProcessingThread(QThread):
    """Thread for processing video without freezing UI"""
    finished = pyqtSignal(bool, str)  # (success, output_path)
    progress = pyqtSignal(str)
    
    def __init__(self, video_path: str, classes: list, verbose: bool = True):
        super().__init__()
        self.video_path = video_path
        self.classes = classes
        self.verbose = verbose
        self.tracks = None  # Store tracks data for heat maps
        self.frames = None  # Store video frames for field size
        self.fps = 30  # Store fps for movement analysis
    
    def run(self):
        try:
            from frontend.translations import t
            self.progress.emit(t("กำลังประมวลผลวิดีโอ...", "กำลังประมวลผลวิดีโอ..."))
            # Reset logs before processing
            self.reset_logs()
            # Read video frames first to get dimensions
            from utils import read_video
            self.frames, self.fps, _, _ = read_video(self.video_path, self.verbose)
            output_path, self.tracks = process_video(self.video_path, self.classes, self.verbose, return_tracks=True)
            self.progress.emit(t("ประมวลผลเสร็จสิ้น!", "ประมวลผลเสร็จสิ้น!"))
            self.finished.emit(True, output_path)
        except Exception as e:
            from frontend.translations import t
            self.progress.emit(f"{t('เกิดข้อผิดพลาด:', 'เกิดข้อผิดพลาด:')} {str(e)}")
            self.finished.emit(False, "")
    
    def reset_logs(self):
        """Clear log files"""
        log_files = [
            os.path.join(PROJECT_ROOT, "logs", "tracking.log"),
            os.path.join(PROJECT_ROOT, "logs", "camera_movement.log"),
            os.path.join(PROJECT_ROOT, "logs", "memory_access.log")
        ]
        for log_file in log_files:
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'w') as f:
                        f.write("")  # Clear log file
            except Exception:
                pass


class VideoPlayerWidget(QWidget):
    """Custom video player widget with controls"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video display
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)
        
        # Controls panel - single line, minimal height
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                padding: 2px 8px;
            }
        """)
        controls_frame.setFixedHeight(32)
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setSpacing(6)
        controls_layout.setContentsMargins(3, 2, 3, 2)
        
        # Play/Pause button - smaller
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                border: none;
                padding: 2px 10px;
                border-radius: 3px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
        """)
        self.play_pause_btn.setFixedWidth(50)
        self.play_pause_btn.setFixedHeight(26)
        
        # Time label - smaller
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #e0e0e0; font-size: 8pt;")
        self.time_label.setFixedWidth(90)
        
        # Seek slider - thinner
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 3px;
                background: #3a3a3a;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: #c41e3a;
                border: 1px solid #c41e3a;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #d63347;
            }
            QSlider::sub-page:horizontal {
                background: #c41e3a;
                border-radius: 1px;
            }
        """)
        self.seek_slider.setRange(0, 0)
        
        # Speed control - smaller
        from frontend.translations import t
        speed_label_text = t("ความเร็ว:", "Speed:")
        self.speed_label = QLabel(speed_label_text)
        self.speed_label.setStyleSheet("color: #e0e0e0; font-size: 8pt;")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentIndex(3)  # Default 1.0x
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px 4px;
                min-width: 65px;
                max-width: 65px;
            }
            QComboBox:hover {
                border-color: #c41e3a;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #e0e0e0;
                selection-background-color: #c41e3a;
            }
        """)
        self.speed_combo.setFixedHeight(26)
        
        # Add all controls to single line
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addWidget(self.time_label)
        controls_layout.addWidget(self.seek_slider, 1)
        controls_layout.addWidget(self.speed_label)
        controls_layout.addWidget(self.speed_combo)
        
        layout.addWidget(controls_frame)
    
    def setup_connections(self):
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.seek_slider.sliderMoved.connect(self.set_position)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.playbackStateChanged.connect(self.state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.speed_combo.currentTextChanged.connect(self.change_speed)
    
    def on_media_status_changed(self, status):
        """Handle media status changes"""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Video loaded, ensure widget is visible
            self.video_widget.show()
            self.video_widget.update()
            # Try to show first frame
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                # Pause to show first frame
                self.media_player.pause()
    
    def load_video(self, video_path: str):
        if os.path.exists(video_path):
            url = QUrl.fromLocalFile(video_path)
            # Ensure video widget is visible before loading
            self.video_widget.show()
            self.video_widget.setVisible(True)
            
            # Set source
            self.media_player.setSource(url)
            self.play_pause_btn.setText("▶")
            
            # Force widget update
            self.video_widget.update()
            
            # Small delay to ensure media is loaded, then try to show first frame
            QTimer.singleShot(100, lambda: self.show_first_frame())
    
    def show_first_frame(self):
        """Try to show the first frame of the video"""
        try:
            # Set position to 0 to show first frame
            self.media_player.setPosition(0)
            # Pause to show frame
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.pause()
            # Force update
            self.video_widget.update()
        except:
            pass
    
    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("▶")
        else:
            self.media_player.play()
            self.play_pause_btn.setText("⏸")
    
    def set_position(self, position):
        self.media_player.setPosition(position)
    
    def position_changed(self, position):
        self.seek_slider.setValue(position)
        self.update_time_label()
    
    def duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.update_time_label()
    
    def state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setText("⏸")
        else:
            self.play_pause_btn.setText("▶")
    
    def change_speed(self, speed_text):
        speed = float(speed_text.replace("x", ""))
        self.media_player.setPlaybackRate(speed)
    
    def update_time_label(self):
        duration = self.media_player.duration()
        position = self.media_player.position()
        
        duration_str = self.format_time(duration)
        position_str = self.format_time(position)
        
        self.time_label.setText(f"{position_str} / {duration_str}")
    
    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class PreviewVideoWidget(QWidget):
    """Preview video widget with controls"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.0)  # Mute preview audio
        self.media_player.setAudioOutput(self.audio_output)
        self.is_seeking = False
        
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Container frame
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #555;
                border-radius: 6px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Video display
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 4px;")
        self.media_player.setVideoOutput(self.video_widget)
        container_layout.addWidget(self.video_widget)
        
        # Controls panel - single line, minimal height (same as VideoPlayerWidget)
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                padding: 2px 8px;
            }
        """)
        controls_frame.setFixedHeight(32)
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setSpacing(6)
        controls_layout.setContentsMargins(3, 2, 3, 2)
        
        # Play/Pause button - smaller (reduced size slightly)
        self.play_btn = QPushButton("▶")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
        """)
        self.play_btn.setFixedWidth(44)
        self.play_btn.setFixedHeight(24)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        controls_layout.addWidget(self.play_btn)
        
        # Time label - smaller (same as VideoPlayerWidget)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #e0e0e0; font-size: 8pt;")
        self.time_label.setFixedWidth(90)
        controls_layout.addWidget(self.time_label)
        
        # Seek slider - thinner (same as VideoPlayerWidget)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 3px;
                background: #3a3a3a;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: #c41e3a;
                border: 1px solid #c41e3a;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #d63347;
            }
            QSlider::sub-page:horizontal {
                background: #c41e3a;
                border-radius: 1px;
            }
        """)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(0)
        controls_layout.addWidget(self.seek_slider, 1)  # Stretch to fill space
        
        container_layout.addWidget(controls_frame)
        layout.addWidget(container)
    
    def setup_connections(self):
        self.play_btn.clicked.connect(self.toggle_play_pause)
        self.media_player.playbackStateChanged.connect(self.state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.seek_slider.sliderPressed.connect(self.slider_pressed)
        self.seek_slider.sliderReleased.connect(self.slider_released)
        self.seek_slider.valueChanged.connect(self.slider_value_changed)
    
    def load_video(self, video_path: str):
        if os.path.exists(video_path):
            url = QUrl.fromLocalFile(video_path)
            self.media_player.setSource(url)
            self.play_btn.setText("▶")
            self.time_label.setText("00:00 / 00:00")
    
    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶")
        else:
            self.media_player.play()
            self.play_btn.setText("⏸")
    
    def state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")
    
    def position_changed(self, position):
        if not self.is_seeking:
            self.seek_slider.setValue(position)
        self.update_time_label()
    
    def duration_changed(self, duration):
        self.seek_slider.setMaximum(duration)
        self.update_time_label()
    
    def slider_pressed(self):
        self.is_seeking = True
    
    def slider_released(self):
        self.is_seeking = False
        self.media_player.setPosition(self.seek_slider.value())
    
    def slider_value_changed(self, value):
        if self.is_seeking:
            self.media_player.setPosition(value)
            self.update_time_label()
    
    def update_time_label(self):
        position = self.media_player.position()
        duration = self.media_player.duration()
        
        pos_sec = position // 1000
        dur_sec = duration // 1000 if duration > 0 else 0
        
        pos_min = pos_sec // 60
        pos_sec = pos_sec % 60
        dur_min = dur_sec // 60
        dur_sec = dur_sec % 60
        
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")
    
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            pass


class FreeFootballAnalysisApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.demo_video: Optional[str] = None
        self.processed = False
        self.processing_thread: Optional[VideoProcessingThread] = None
        self.current_output_path: Optional[str] = None
        self.current_mode = "AI"  # "AI" or "Manual"
        self.tracks: Optional[Dict] = None  # Store tracking data for heat maps
        self.video_frames: Optional[List] = None  # Store video frames for field size
        self.video_fps: int = 30  # Store fps for movement analysis
        self.current_heat_map_title: Optional[str] = None  # Store current heat map title
        self.current_heat_map_type: Optional[str] = None  # Store current heat map type
        self.heat_map_generator: Optional = None  # Store generator reference
        self.original_field_size: tuple = (1920, 1080)  # Store original field size for full res saving
        
        # Initialize tracking data
        try:
            self.manual_tracking_data = ManualTrackingData()
        except:
            self.manual_tracking_data = None
        
        # Store team players
        self.team1_players: List[Dict[str, str]] = []
        self.team2_players: List[Dict[str, str]] = []
        
        # Professional football analysis event types with outcomes
        # Format: (action_name, color, [outcomes])
        # 
        # คำอธิบาย Outcome:
        # - "ประตู" = ได้ประตู (Goal)
        # - "ยิงเข้า" = ยิงเข้าเป้าแต่ไม่ได้ประตู (Shot on Target)
        # - "ยิงออก" = ยิงออกนอกเป้า (Shot off Target)
        # - "แอสซิสต์" = ส่งบอลแล้วได้ประตู (Assist - ส่งแล้วได้ประตู)
        # - "คีย์พาส" = ส่งบอลที่สร้างโอกาสยิง (Key Pass - ส่งแล้วมีโอกาสยิงแต่ไม่ได้ประตู)
        # - "สำเร็จ" = การกระทำสำเร็จ (Success)
        # - "ไม่สำเร็จ" = การกระทำไม่สำเร็จ (Failed)
        #
        self.default_event_types = [
            # Attacking Actions
            ("ยิง", "#FF9800", ["ประตู", "ยิงเข้า", "ยิงออก", "บล็อก", "ถูกเซฟ"]),
            # หมายเหตุ: "ประตู" = ได้ประตู, "ยิงเข้า" = ยิงเข้าเป้าแต่ไม่ได้ประตู
            
            ("ส่งบอล", "#2196F3", ["สำเร็จ", "ไม่สำเร็จ", "แอสซิสต์", "คีย์พาส"]),
            # หมายเหตุ: "แอสซิสต์" = ส่งแล้วได้ประตู, "คีย์พาส" = ส่งแล้วมีโอกาสยิง
            
            ("ข้ามบอล", "#E91E63", ["สำเร็จ", "ไม่สำเร็จ", "แอสซิสต์", "คีย์พาส"]),
            ("ผ่านบอล", "#9C27B0", ["สำเร็จ", "ไม่สำเร็จ", "แอสซิสต์", "คีย์พาส"]),
            ("ส่งบอลยาว", "#795548", ["สำเร็จ", "ไม่สำเร็จ", "แอสซิสต์", "คีย์พาส"]),
            ("ส่งบอลสั้น", "#607D8B", ["สำเร็จ", "ไม่สำเร็จ"]),
            ("ส่งบอลในเขตโทษ", "#FF5722", ["สำเร็จ", "ไม่สำเร็จ", "แอสซิสต์", "คีย์พาส"]),
            
            # Set Pieces
            ("เตะมุม", "#00BCD4", ["ประตู", "ยิงเข้า", "ยิงออก", "แอสซิสต์", "คีย์พาส", "เคลียร์"]),
            ("ฟรีคิก", "#FFC107", ["ประตู", "ยิงเข้า", "ยิงออก", "แอสซิสต์", "คีย์พาส", "เคลียร์"]),
            ("ลูกโทษ", "#F44336", ["ประตู", "ไม่ประตู", "ถูกเซฟ"]),
            ("ทุ่มบอล", "#607D8B", ["สำเร็จ", "ไม่สำเร็จ"]),
            
            # Defensive Actions
            ("แย่งบอล", "#9C27B0", ["สำเร็จ", "ไม่สำเร็จ", "ฟาวล์"]),
            ("สกัดบอล", "#9C27B0", ["สำเร็จ", "ไม่สำเร็จ"]),
            ("เคลียร์บอล", "#795548", ["สำเร็จ", "ไม่สำเร็จ", "อันตราย"]),
            ("บล็อก", "#FF5722", ["บล็อก", "บล็อกยิง"]),
            ("เซฟ", "#00BCD4", ["เซฟ", "ไม่เซฟ", "เซฟสำคัญ"]),
            
            # Disciplinary
            ("ฟาวล์", "#F44336", ["ฟาวล์", "ใบเหลือง", "ใบแดง"]),
            ("ใบเหลือง", "#FFEB3B", ["ใบเหลือง"]),
            ("ใบแดง", "#E91E63", ["ใบแดง"]),
            
            # Other Events
            ("ออฟไซด์", "#9E9E9E", ["ออฟไซด์"]),
            ("บอลออก", "#607D8B", ["บอลออก"]),
            ("เปลี่ยนตัว", "#795548", ["เปลี่ยนตัวเข้า", "เปลี่ยนตัวออก"]),
            ("บาดเจ็บ", "#FF9800", ["บาดเจ็บ"]),
            ("เสียบอล", "#F44336", ["เสียบอล"]),
            ("ครองบอล", "#4CAF50", ["ครองบอล"]),
        ]
        
        # Initialize enabled events (empty by default - user must configure first)
        self.enabled_events = set()
        
        # Auto-refresh timer for logs (refresh every 500ms like terminal)
        self.log_refresh_timer = QTimer()
        self.log_refresh_timer.timeout.connect(self.auto_refresh_logs)
        self.current_log_path = None  # Track currently displayed log file
        
        # Initialize translation manager
        self.translation_manager = get_translation_manager()
        
        # Store UI elements for translation refresh
        self.ui_elements_to_translate = {}
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle(t("FREE - Football Analysis", "FREE - Football Analysis"))
        # Make window responsive - use percentage-based sizing
        self.setMinimumSize(1000, 600)
        
        # Central widget - just tabs, no sidebar
        main_area = self.create_main_area()
        main_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(main_area)
        
        # Apply dark theme
        self.apply_dark_theme()
    
    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Scroll area for sidebar content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c41e3a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #d63347;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # Options group
        options_group = QGroupBox("Options")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        options_layout = QVBoxLayout()
        options_layout.setSpacing(10)
        
        self.checkbox_players = QCheckBox("Highlight Players")
        self.checkbox_players.setChecked(True)
        options_layout.addWidget(self.checkbox_players)
        
        self.checkbox_goalkeepers = QCheckBox("Highlight Goalkeepers")
        self.checkbox_goalkeepers.setChecked(True)
        options_layout.addWidget(self.checkbox_goalkeepers)
        
        self.checkbox_referees = QCheckBox("Highlight Referees")
        self.checkbox_referees.setChecked(True)
        options_layout.addWidget(self.checkbox_referees)
        
        self.checkbox_ball = QCheckBox("Highlight Ball")
        self.checkbox_ball.setChecked(True)
        options_layout.addWidget(self.checkbox_ball)
        
        self.checkbox_stats = QCheckBox("Show Statistics")
        self.checkbox_stats.setChecked(True)
        options_layout.addWidget(self.checkbox_stats)
        
        options_group.setLayout(options_layout)
        scroll_layout.addWidget(options_group)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Separator
        line3 = QFrame()
        line3.setFrameShape(QFrame.Shape.HLine)
        line3.setFrameShadow(QFrame.Shadow.Sunken)
        line3.setStyleSheet("color: #555;")
        layout.addWidget(line3)
        
        # Start Analysis button
        start_text = t("เริ่มวิเคราะห์ (Start Analysis)", "เริ่มวิเคราะห์ (Start Analysis)")
        self.btn_start = QPushButton(start_text)
        self.btn_start.clicked.connect(self.start_analysis)
        self.btn_start.setEnabled(False)
        self.ui_elements_to_translate[self.btn_start] = "เริ่มวิเคราะห์ (Start Analysis)"
        layout.addWidget(self.btn_start)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        return sidebar
    
    def create_main_area(self):
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #b0b0b0;
                padding: 12px 24px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #c41e3a;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #333;
            }
        """)
        
        # Mode selection
        mode_tab = self.create_mode_selection_tab()
        tabs.addTab(mode_tab, t("Info", "Info"))
        
        # AI YOLO Mode tabs
        usage_tab = self.create_usage_tab()
        tabs.addTab(usage_tab, t("AI - Tracking", "AI - Tracking"))
        
        results_tab = self.create_results_tab()
        tabs.addTab(results_tab, t("Video Preview", "Video Preview"))
        
        # AI Results tab (Heat Maps)
        ai_results_tab = self.create_ai_results_tab()
        tabs.addTab(ai_results_tab, t("AI - Results", "AI - Results"))
        
        # Manual Tracking tab
        manual_tracking_tab = self.create_manual_tracking_tab()
        tabs.addTab(manual_tracking_tab, t("Manual Tracking", "Manual Tracking"))
        
        # Logs tab
        logs_tab = self.create_logs_tab()
        tabs.addTab(logs_tab, t("Logs", "Logs"))
        
        self.tabs = tabs
        return tabs
    
    def create_usage_tab(self):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)
        
        # Top row: Options and Video Source side by side
        top_row = QHBoxLayout()
        top_row.setSpacing(20)
        
        # Options group - left side
        options_group_text = t("ตัวเลือกการแสดงผล", "Display Options")
        options_group = QGroupBox(options_group_text)
        self.ui_elements_to_translate[options_group] = "ตัวเลือกการแสดงผล"
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13pt;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                padding-bottom: 12px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #c41e3a;
                font-size: 13pt;
            }
        """)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(15, 10, 15, 10)
        options_layout.setSpacing(12)
        
        checkbox_style = """
            QCheckBox {
                font-size: 11pt;
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #666;
                background-color: #2b2b2b;
            }
            QCheckBox::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
            QCheckBox::indicator:hover {
                border-color: #c41e3a;
            }
        """
        
        checkbox_players_text = t("Track ผู้เล่น", "Track Players")
        self.checkbox_players = QCheckBox(checkbox_players_text)
        self.checkbox_players.setChecked(True)
        self.checkbox_players.setStyleSheet(checkbox_style)
        self.ui_elements_to_translate[self.checkbox_players] = "Track ผู้เล่น"
        options_layout.addWidget(self.checkbox_players)
        
        checkbox_goalkeepers_text = t("Track ผู้รักษาประตู", "Track Goalkeepers")
        self.checkbox_goalkeepers = QCheckBox(checkbox_goalkeepers_text)
        self.checkbox_goalkeepers.setChecked(True)
        self.checkbox_goalkeepers.setStyleSheet(checkbox_style)
        self.ui_elements_to_translate[self.checkbox_goalkeepers] = "Track ผู้รักษาประตู"
        options_layout.addWidget(self.checkbox_goalkeepers)
        
        checkbox_referees_text = t("Track ผู้ตัดสิน", "Track Referees")
        self.checkbox_referees = QCheckBox(checkbox_referees_text)
        self.checkbox_referees.setChecked(True)
        self.checkbox_referees.setStyleSheet(checkbox_style)
        self.ui_elements_to_translate[self.checkbox_referees] = "Track ผู้ตัดสิน"
        options_layout.addWidget(self.checkbox_referees)
        
        checkbox_ball_text = t("Track ลูกบอล", "Track Ball")
        self.checkbox_ball = QCheckBox(checkbox_ball_text)
        self.checkbox_ball.setChecked(True)
        self.checkbox_ball.setStyleSheet(checkbox_style)
        self.ui_elements_to_translate[self.checkbox_ball] = "Track ลูกบอล"
        options_layout.addWidget(self.checkbox_ball)
        
        checkbox_stats_text = t("แสดงสถิติ", "Show Statistics")
        self.checkbox_stats = QCheckBox(checkbox_stats_text)
        self.checkbox_stats.setChecked(True)
        self.checkbox_stats.setStyleSheet(checkbox_style)
        self.ui_elements_to_translate[self.checkbox_stats] = "แสดงสถิติ"
        options_layout.addWidget(self.checkbox_stats)
        
        # Add warning/info label
        info_label_text = t("💡 หมายเหตุ: ตัวเลือกข้างต้นใช้สำหรับการแสดงผลในวิดีโอเท่านั้น ไม่ส่งผลต่อการวิเคราะห์ผลด้าน ImageProcessing ของ AI", "💡 Note: The above options are for video display only and do not affect AI ImageProcessing analysis results")
        info_label = QLabel(info_label_text)
        self.ui_elements_to_translate[info_label] = "💡 หมายเหตุ: ตัวเลือกข้างต้นใช้สำหรับการแสดงผลในวิดีโอเท่านั้น ไม่ส่งผลต่อการวิเคราะห์ผลด้าน ImageProcessing ของ AI"
        info_label.setStyleSheet("""
            QLabel {
                font-size: 9.5pt;
                color: #b8b8b8;
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-left: 3px solid #c41e3a;
                border-radius: 4px;
                padding: 8px 10px;
                margin-top: 2px;
            }
        """)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        info_label.setContentsMargins(0, 0, 0, 0)
        options_layout.addWidget(info_label)
        
        options_group.setLayout(options_layout)
        top_row.addWidget(options_group, 1)  # Stretch factor 1
        
        # Video Source section - right side
        source_group_text = t("แหล่งวิดีโอ", "Video Source")
        source_group = QGroupBox(source_group_text)
        self.ui_elements_to_translate[source_group] = "แหล่งวิดีโอ"
        source_group.setStyleSheet(options_group.styleSheet())
        source_layout = QVBoxLayout()
        source_layout.setContentsMargins(15, 10, 15, 10)
        source_layout.setSpacing(14)
        
        # Demo section
        demo_text = t("ตัวอย่าง", "Demo")
        demo_label = QLabel(demo_text)
        demo_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #c41e3a; margin-top: 5px;")
        self.ui_elements_to_translate[demo_label] = "ตัวอย่าง"
        source_layout.addWidget(demo_label)
        
        demo_inst_text = t("เลือกวิดีโอตัวอย่างจาก 2 วิดีโอ", "Select demo video from 2 videos")
        demo_instruction = QLabel(demo_inst_text)
        self.ui_elements_to_translate[demo_instruction] = "เลือกวิดีโอตัวอย่างจาก 2 วิดีโอ"
        demo_instruction.setStyleSheet("color: #b0b0b0; font-size: 10pt; margin-bottom: 8px;")
        source_layout.addWidget(demo_instruction)
        
        self.demo_button_group = QButtonGroup()
        radio_style = """
            QRadioButton {
                font-size: 11pt;
                color: #e0e0e0;
                spacing: 8px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #666;
                background-color: #2b2b2b;
            }
            QRadioButton::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
            QRadioButton::indicator:hover {
                border-color: #c41e3a;
            }
        """
        demo1_text = t("ตัวอย่าง 1", "Demo 1")
        self.radio_demo1 = QRadioButton(demo1_text)
        self.ui_elements_to_translate[self.radio_demo1] = "ตัวอย่าง 1"
        self.radio_demo1.setStyleSheet(radio_style)
        demo2_text = t("ตัวอย่าง 2", "Demo 2")
        self.radio_demo2 = QRadioButton(demo2_text)
        self.ui_elements_to_translate[self.radio_demo2] = "ตัวอย่าง 2"
        self.radio_demo2.setStyleSheet(radio_style)
        self.radio_demo1.setChecked(False)
        self.radio_demo2.setChecked(False)
        self.demo_button_group.addButton(self.radio_demo1, 0)
        self.demo_button_group.addButton(self.radio_demo2, 1)
        
        demo_radio_layout = QHBoxLayout()
        demo_radio_layout.setSpacing(20)
        demo_radio_layout.addWidget(self.radio_demo1)
        demo_radio_layout.addWidget(self.radio_demo2)
        demo_radio_layout.addStretch()
        source_layout.addLayout(demo_radio_layout)
        
        self.radio_demo1.toggled.connect(self.on_demo_selected)
        self.radio_demo2.toggled.connect(self.on_demo_selected)
        
        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("color: #555; margin: 12px 0;")
        source_layout.addWidget(line2)
        
        # Upload section
        upload_text = t("อัปโหลดวิดีโอ", "Upload Video")
        upload_label = QLabel(upload_text)
        upload_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #c41e3a; margin-top: 5px;")
        self.ui_elements_to_translate[upload_label] = "อัปโหลดวิดีโอ"
        source_layout.addWidget(upload_label)
        
        browse_text = t("เลือกไฟล์วิดีโอ", "Select Video File")
        self.btn_browse = QPushButton(browse_text)
        self.ui_elements_to_translate[self.btn_browse] = "เลือกไฟล์วิดีโอ"
        self.btn_browse.clicked.connect(self.browse_video)
        self.btn_browse.setMinimumHeight(40)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #555;
            }
            QPushButton:hover {
                background-color: #333;
                border-color: #c41e3a;
                color: #c41e3a;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """)
        source_layout.addWidget(self.btn_browse)
        
        self.selected_video_label = QLabel("")
        self.selected_video_label.setWordWrap(True)
        self.selected_video_label.setStyleSheet("color: #b0b0b0; font-size: 10pt; margin-top: 5px; padding: 5px;")
        source_layout.addWidget(self.selected_video_label)
        
        source_group.setLayout(source_layout)
        top_row.addWidget(source_group, 1)  # Stretch factor 1
        
        layout.addLayout(top_row)
        
        # Video preview widget - larger, in the middle
        self.preview_video = PreviewVideoWidget()
        self.preview_video.setMinimumHeight(420)
        self.preview_video.setMaximumHeight(550)
        layout.addWidget(self.preview_video, 1)  # Stretch factor 1 to take available space
        
        # Add spacing before start button
        layout.addSpacing(10)
        
        # Start Analysis button - moved from sidebar
        start_text2 = t("เริ่มวิเคราะห์", "Start Analysis")
        self.btn_start = QPushButton(start_text2)
        self.ui_elements_to_translate[self.btn_start] = "เริ่มวิเคราะห์"
        self.btn_start.clicked.connect(self.start_analysis)
        self.btn_start.setEnabled(False)
        self.btn_start.setMinimumHeight(55)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 16px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13pt;
                border: none;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        layout.addWidget(self.btn_start)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                font-size: 10pt;
                color: #e0e0e0;
                background-color: #2b2b2b;
            }
            QProgressBar::chunk {
                background-color: #c41e3a;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #c41e3a; font-weight: bold; font-size: 11pt; padding: 8px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        return widget
    
    def create_results_tab(self):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_text = t("Video Preview", "Video Preview")
        title = QLabel(title_text)
        self.ui_elements_to_translate[title] = "Video Preview"
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Video player widget
        self.result_video_player = VideoPlayerWidget()
        self.result_video_player.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Store reference to speed label for translation
        if hasattr(self.result_video_player, 'speed_label'):
            self.ui_elements_to_translate[self.result_video_player.speed_label] = "ความเร็ว:"
        layout.addWidget(self.result_video_player, 1)
        
        # Buttons for video control
        button_layout = QHBoxLayout()
        
        open_video_text = t("เปิดวีดีโอ", "Open Video")
        self.btn_open_output = QPushButton(open_video_text)
        # Store with Thai text as key, but we'll use the default parameter in translate
        self.ui_elements_to_translate[self.btn_open_output] = ("เปิดวีดีโอ", "Open Video")
        self.btn_open_output.clicked.connect(self.open_video_file)
        button_layout.addWidget(self.btn_open_output)
        
        open_folder_text = t("เปิดโฟลเดอร์ผลลัพธ์", "Open Output Folder")
        self.btn_open_folder = QPushButton(open_folder_text)
        # Store with Thai text as key, but we'll use the default parameter in translate
        self.ui_elements_to_translate[self.btn_open_folder] = ("เปิดโฟลเดอร์ผลลัพธ์", "Open Output Folder")
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        button_layout.addWidget(self.btn_open_folder)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def create_ai_results_tab(self):
        """Create AI Results tab with sub-tabs for different analysis types"""
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        # Create sub-tabs widget
        sub_tabs = QTabWidget()
        sub_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #b0b0b0;
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #c41e3a;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #333;
            }
        """)
        
        # Heat Map tab (existing functionality)
        heat_map_tab = self.create_heat_map_subtab()
        heat_map_tab_name = t("Heat Map", "Heat Map")
        sub_tabs.addTab(heat_map_tab, heat_map_tab_name)
        if not hasattr(self, 'ai_results_subtabs'):
            self.ai_results_subtabs = {}
        self.ai_results_subtabs[0] = ("Heat Map", heat_map_tab_name)
        
        # Statistics tab (new - coming soon)
        statistics_tab = self.create_statistics_subtab()
        statistics_tab_name = t("Statistics", "Statistics")
        sub_tabs.addTab(statistics_tab, statistics_tab_name)
        self.ai_results_subtabs[1] = ("Statistics", statistics_tab_name)
        
        # Movement Analysis tab (new - coming soon)
        movement_tab = self.create_movement_analysis_subtab()
        movement_tab_name = t("Movement Analysis", "Movement Analysis")
        sub_tabs.addTab(movement_tab, movement_tab_name)
        self.ai_results_subtabs[2] = ("Movement Analysis", movement_tab_name)
        
        # Pass Analysis tab (new - coming soon)
        pass_analysis_tab = self.create_pass_analysis_subtab()
        pass_analysis_tab_name = t("Pass Analysis", "Pass Analysis")
        sub_tabs.addTab(pass_analysis_tab, pass_analysis_tab_name)
        self.ai_results_subtabs[3] = ("Pass Analysis", pass_analysis_tab_name)
        
        # Zone Analysis tab (new - coming soon)
        zone_analysis_tab = self.create_zone_analysis_subtab()
        zone_analysis_tab_name = t("Zone Analysis", "Zone Analysis")
        sub_tabs.addTab(zone_analysis_tab, zone_analysis_tab_name)
        self.ai_results_subtabs[4] = ("Zone Analysis", zone_analysis_tab_name)
        
        # Store sub_tabs reference for refresh
        self.ai_results_subtabs_widget = sub_tabs
        
        layout.addWidget(sub_tabs)
        
        return widget
    
    def create_heat_map_subtab(self):
        """Create Heat Map sub-tab"""
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Info label
        heat_maps_info_text = t("Heat Maps จะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Heat Maps will be displayed after analyzing video")
        info_label = QLabel(heat_maps_info_text)
        self.ui_elements_to_translate[info_label] = ("Heat Maps จะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Heat Maps will be displayed after analyzing video")
        info_label.setStyleSheet("color: #b0b0b0; font-size: 11pt; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Heat map type selector
        heat_map_group_text = t("เลือกประเภท Heat Map", "Select Heat Map Type")
        heat_map_group = QGroupBox(heat_map_group_text)
        self.ui_elements_to_translate[heat_map_group] = ("เลือกประเภท Heat Map", "Select Heat Map Type")
        heat_map_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        heat_map_layout = QHBoxLayout()
        
        self.heat_map_radio_group = QButtonGroup()
        all_players_text = t("ผู้เล่นทั้งหมด", "All Players")
        self.radio_all_players = QRadioButton(all_players_text)
        self.ui_elements_to_translate[self.radio_all_players] = "ผู้เล่นทั้งหมด"
        team1_text = t("ทีม 1", "Team 1")
        self.radio_team1 = QRadioButton(team1_text)
        self.ui_elements_to_translate[self.radio_team1] = "ทีม 1"
        team2_text = t("ทีม 2", "Team 2")
        self.radio_team2 = QRadioButton(team2_text)
        self.ui_elements_to_translate[self.radio_team2] = "ทีม 2"
        ball_text = t("ลูกบอล", "Ball")
        self.radio_ball = QRadioButton(ball_text)
        self.ui_elements_to_translate[self.radio_ball] = "ลูกบอล"
        
        self.heat_map_radio_group.addButton(self.radio_all_players, 0)
        self.heat_map_radio_group.addButton(self.radio_team1, 1)
        self.heat_map_radio_group.addButton(self.radio_team2, 2)
        self.heat_map_radio_group.addButton(self.radio_ball, 3)
        
        radio_style = """
            QRadioButton {
                font-size: 11pt;
                color: #e0e0e0;
                spacing: 8px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #666;
                background-color: #2b2b2b;
            }
            QRadioButton::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
        """
        self.radio_all_players.setStyleSheet(radio_style)
        self.radio_team1.setStyleSheet(radio_style)
        self.radio_team2.setStyleSheet(radio_style)
        self.radio_ball.setStyleSheet(radio_style)
        self.radio_all_players.setChecked(True)
        
        heat_map_layout.addWidget(self.radio_all_players)
        heat_map_layout.addWidget(self.radio_team1)
        heat_map_layout.addWidget(self.radio_team2)
        heat_map_layout.addWidget(self.radio_ball)
        heat_map_layout.addStretch()
        
        # Connect radio buttons to update heat map
        self.radio_all_players.toggled.connect(lambda: self.update_heat_map_display())
        self.radio_team1.toggled.connect(lambda: self.update_heat_map_display())
        self.radio_team2.toggled.connect(lambda: self.update_heat_map_display())
        self.radio_ball.toggled.connect(lambda: self.update_heat_map_display())
        
        heat_map_group.setLayout(heat_map_layout)
        layout.addWidget(heat_map_group)
        
        # Heat map display area
        heat_map_display = QFrame()
        heat_map_display.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #555;
                border-radius: 6px;
            }
        """)
        heat_map_display_layout = QVBoxLayout(heat_map_display)
        heat_map_display_layout.setContentsMargins(10, 10, 10, 10)
        
        # Label for heat map image
        self.heat_map_label = QLabel()
        self.heat_map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heat_map_label.setMinimumHeight(400)
        self.heat_map_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        no_heat_map_text_th = "ยังไม่มีข้อมูล Heat Map\nกรุณากดวิเคราะห์วิดีโอก่อน"
        no_heat_map_text_en = "No Heat Map data yet\nPlease analyze video first"
        current_lang = self.translation_manager.get_language()
        no_heat_map_text = no_heat_map_text_en if current_lang == "EN" else no_heat_map_text_th
        self.heat_map_label.setText(no_heat_map_text)
        if not hasattr(self, 'heat_map_label_text'):
            self.heat_map_label_text = (no_heat_map_text_th, no_heat_map_text_en)
        # Store for translation refresh
        if hasattr(self, 'ui_elements_to_translate'):
            self.ui_elements_to_translate[self.heat_map_label] = self.heat_map_label_text
        self.heat_map_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                color: #888;
                font-size: 12pt;
            }
        """)
        heat_map_display_layout.addWidget(self.heat_map_label)
        
        layout.addWidget(heat_map_display, 1)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_heat_map_text = t("บันทึก Heat Map เป็น PNG", "Save Heat Map as PNG")
        self.btn_save_heat_map = QPushButton(save_heat_map_text)
        self.ui_elements_to_translate[self.btn_save_heat_map] = ("บันทึก Heat Map เป็น PNG", "Save Heat Map as PNG")
        self.btn_save_heat_map.clicked.connect(self.save_heat_map)
        self.btn_save_heat_map.setEnabled(False)  # Disabled until heat map is generated
        self.btn_save_heat_map.setMinimumHeight(40)
        self.btn_save_heat_map.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11pt;
                border: none;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        button_layout.addWidget(self.btn_save_heat_map)
        
        layout.addLayout(button_layout)
        
        return widget
    
    def create_statistics_subtab(self):
        """Create Statistics sub-tab with real statistics"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title_text = t("Statistics", "Statistics")
        title = QLabel(title_text)
        self.ui_elements_to_translate[title] = ("Statistics", "Statistics")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Info label
        stats_info_text = t("สถิติจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Statistics will be displayed after analyzing video")
        info_label = QLabel(stats_info_text)
        self.ui_elements_to_translate[info_label] = ("สถิติจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Statistics will be displayed after analyzing video")
        info_label.setStyleSheet("color: #b0b0b0; font-size: 11pt; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Scroll area for statistics
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c41e3a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #d63347;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # Team statistics section
        team_stats_text = t("Team Statistics", "Team Statistics")
        self.team_stats_group = QGroupBox(team_stats_text)
        self.ui_elements_to_translate[self.team_stats_group] = ("Team Statistics", "Team Statistics")
        self.team_stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        team_stats_layout = QVBoxLayout()
        self.team_stats_layout = team_stats_layout
        self.team_stats_group.setLayout(team_stats_layout)
        scroll_layout.addWidget(self.team_stats_group)
        
        # Placeholder when no data
        no_stats_text = t("ยังไม่มีข้อมูลสถิติ\nกรุณากดวิเคราะห์วิดีโอก่อน", "No statistics data yet\nPlease analyze video first")
        self.stats_placeholder = QLabel(no_stats_text)
        if not hasattr(self, 'stats_placeholder_text'):
            self.stats_placeholder_text = ("ยังไม่มีข้อมูลสถิติ\nกรุณากดวิเคราะห์วิดีโอก่อน", "No statistics data yet\nPlease analyze video first")
        # Store for translation refresh
        if hasattr(self, 'ui_elements_to_translate'):
            self.ui_elements_to_translate[self.stats_placeholder] = self.stats_placeholder_text
        self.stats_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_placeholder.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 14pt;
                padding: 40px;
            }
        """)
        scroll_layout.addWidget(self.stats_placeholder)
        
        # Initially hide team stats group and show placeholder
        self.team_stats_group.setVisible(False)
        self.stats_placeholder.setVisible(True)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def update_statistics(self):
        """Update statistics display when tracking data is available"""
        print(f"[DEBUG] update_statistics called. Has tracks: {self.tracks is not None}")
        
        if not self.tracks:
            # Show placeholder if no tracks
            print("[DEBUG] No tracks available")
            if hasattr(self, 'stats_placeholder'):
                self.stats_placeholder.setVisible(True)
            if hasattr(self, 'team_stats_group'):
                self.team_stats_group.setVisible(False)
            return
        
        # Check if tracks have data
        players_data = self.tracks.get("players", [])
        print(f"[DEBUG] Players data length: {len(players_data)}")
        
        if not players_data or len(players_data) == 0:
            print("[DEBUG] No players data")
            if hasattr(self, 'stats_placeholder'):
                self.stats_placeholder.setText(t("ยังไม่มีข้อมูลผู้เล่น\nกรุณากดวิเคราะห์วิดีโอก่อน", "No player data yet\nPlease analyze video first"))
                self.stats_placeholder.setVisible(True)
            if hasattr(self, 'team_stats_group'):
                self.team_stats_group.setVisible(False)
            return
        
        try:
            from analytics.statistics_calculator import StatisticsCalculator
            
            # Get field dimensions
            field_width = 1920
            field_height = 1080
            if self.video_frames and len(self.video_frames) > 0:
                field_height, field_width = self.video_frames[0].shape[:2]
            
            # Get FPS (default to 30 if not available)
            fps = 30  # You might want to store this from video processing
            
            print(f"[DEBUG] Calculating statistics with {len(players_data)} frames")
            
            # Calculate statistics
            calculator = StatisticsCalculator(fps=fps)
            stats = calculator.calculate_player_statistics(self.tracks, field_width, field_height)
            print(f"[DEBUG] Statistics calculated: {stats}")
            
            summary = calculator.get_summary_statistics(stats)
            print(f"[DEBUG] Summary: {summary}")
            
            # Clear previous statistics
            self.clear_statistics_display()
            
            # Display team statistics (includes overall stats)
            summary["overall"] = stats["overall"]
            self.display_team_statistics(summary)
            
            # Hide placeholder and show team stats
            if hasattr(self, 'stats_placeholder'):
                self.stats_placeholder.setVisible(False)
            if hasattr(self, 'team_stats_group'):
                self.team_stats_group.setVisible(True)
            
            print("[DEBUG] Statistics displayed successfully")
            
        except Exception as e:
            import traceback
            error_msg = f"เกิดข้อผิดพลาด: {str(e)}"
            print(f"[ERROR] Error updating statistics: {error_msg}")
            print(traceback.format_exc())
            # Show error message with more details
            if hasattr(self, 'stats_placeholder'):
                detailed_error = f"{error_msg}\n\nกรุณาตรวจสอบ console สำหรับรายละเอียด"
                self.stats_placeholder.setText(detailed_error)
                self.stats_placeholder.setVisible(True)
            if hasattr(self, 'team_stats_group'):
                self.team_stats_group.setVisible(False)
    
    def clear_statistics_display(self):
        """Clear all statistics widgets"""
        # Clear team statistics
        while self.team_stats_layout.count():
            child = self.team_stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def get_most_common_team_colour(self, team_id: int) -> Optional[tuple]:
        """
        Find the most common team colour for a team by counting players
        Goalkeepers usually have different colours, so the most common colour = regular players
        """
        if not self.tracks:
            return None
        
        from collections import Counter
        
        # Count team colours for this team across all frames
        team_colours = []
        
        for frame_num, frame_players in enumerate(self.tracks.get("players", [])):
            if not isinstance(frame_players, dict):
                continue
            
            for pid, player in frame_players.items():
                if not isinstance(player, dict):
                    continue
                
                if player.get("team") == team_id and "team_colour" in player:
                    team_colour = player.get("team_colour")
                    # Convert to tuple for hashing (if it's numpy array or list)
                    if isinstance(team_colour, np.ndarray):
                        team_colour = tuple(team_colour.tolist())
                    elif isinstance(team_colour, list):
                        team_colour = tuple(team_colour)
                    elif isinstance(team_colour, tuple):
                        pass
                    else:
                        continue
                    
                    # Round to nearest 10 to group similar colours together
                    # This helps account for slight variations in lighting
                    rounded_colour = tuple(int(round(c / 10.0) * 10) for c in team_colour)
                    team_colours.append(rounded_colour)
        
        if not team_colours:
            return None
        
        # Find most common colour
        colour_counter = Counter(team_colours)
        most_common_colour, count = colour_counter.most_common(1)[0]
        
        print(f"[DEBUG] Team {team_id} most common colour: {most_common_colour} (appears {count} times out of {len(team_colours)} total)")
        
        return most_common_colour
    
    def colours_similar(self, colour1: tuple, colour2: tuple, tolerance: int = 30) -> bool:
        """
        Check if two colours are similar within tolerance
        """
        if len(colour1) != 3 or len(colour2) != 3:
            return False
        
        # Calculate total difference
        diff = sum(abs(a - b) for a, b in zip(colour1, colour2))
        return diff <= tolerance
    
    def is_likely_goalkeeper(self, player: Dict, frame_width: int, frame_height: int) -> bool:
        """
        Check if a player is likely a goalkeeper based on position
        Goalkeepers are usually near the edges of the field (near goals)
        """
        if "bbox" not in player:
            return False
        
        bbox = player["bbox"]
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        
        # Calculate center position
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Goalkeepers are usually near the left or right edges (within 15% of field width)
        edge_threshold = frame_width * 0.15
        
        # Check if player is near left or right edge
        is_near_left_edge = center_x < edge_threshold
        is_near_right_edge = center_x > (frame_width - edge_threshold)
        
        # Also check if player is in lower part of field (goalkeepers are usually in goal area)
        is_in_lower_field = center_y > frame_height * 0.6
        
        # Likely goalkeeper if near edge AND in lower part of field
        return (is_near_left_edge or is_near_right_edge) and is_in_lower_field
    
    def analyze_player_positions(self, player_id: int, team_id: int, frame_width: int, frame_height: int) -> Dict:
        """
        Analyze a player's positions across all frames to determine if they're likely a goalkeeper
        Returns a dictionary with analysis results
        """
        if not self.tracks:
            return {"is_goalkeeper": False, "edge_ratio": 0.0, "center_ratio": 0.0}
        
        edge_threshold = frame_width * 0.15
        center_threshold_x = frame_width * 0.3  # Middle 60% of field width
        center_threshold_y = frame_height * 0.3  # Middle 40% of field height
        
        edge_frames = 0
        center_frames = 0
        total_frames = 0
        
        for frame_num, frame_players in enumerate(self.tracks.get("players", [])):
            if not isinstance(frame_players, dict):
                continue
            
            if player_id not in frame_players:
                continue
            
            player = frame_players[player_id]
            if not isinstance(player, dict) or player.get("team") != team_id:
                continue
            
            if "bbox" not in player:
                continue
            
            bbox = player["bbox"]
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            total_frames += 1
            
            # Check if near edge
            is_near_left = center_x < edge_threshold
            is_near_right = center_x > (frame_width - edge_threshold)
            is_near_edge = is_near_left or is_near_right
            
            if is_near_edge:
                edge_frames += 1
            
            # Check if in center area
            is_in_center_x = center_x >= center_threshold_x and center_x <= (frame_width - center_threshold_x)
            is_in_center_y = center_y >= center_threshold_y and center_y <= (frame_height - center_threshold_y)
            is_in_center = is_in_center_x and is_in_center_y
            
            if is_in_center:
                center_frames += 1
        
        if total_frames == 0:
            return {"is_goalkeeper": False, "edge_ratio": 0.0, "center_ratio": 0.0}
        
        edge_ratio = edge_frames / total_frames
        center_ratio = center_frames / total_frames
        
        # Goalkeeper if: spends >60% of time near edges AND spends <20% of time in center
        is_goalkeeper = edge_ratio > 0.6 and center_ratio < 0.2
        
        return {
            "is_goalkeeper": is_goalkeeper,
            "edge_ratio": edge_ratio,
            "center_ratio": center_ratio,
            "total_frames": total_frames
        }
    
    def get_player_image(self, team_id: int, max_size: int = 180) -> Optional[QPixmap]:
        """Extract player image from first frame for the team (using most common team colour, avoiding goalkeepers and referees)"""
        if not self.tracks or not self.video_frames:
            return None
        
        try:
            # Import referee filter for additional checks
            from referee_filter import RefereeFilter
            referee_filter = RefereeFilter(iou_threshold=0.3, color_tolerance=40)
            
            # Get frame dimensions for goalkeeper detection
            frame_height, frame_width = self.video_frames[0].shape[:2] if self.video_frames else (1080, 1920)
            
            # Get the most common team colour (should be regular players, not goalkeeper)
            most_common_colour = self.get_most_common_team_colour(team_id)
            
            # Collect all players with their analysis
            player_candidates = {}  # key: (player_id, frame_num), value: (player, analysis, color_match_score)
            
            # First pass: Collect all players and analyze them
            for frame_num, frame_players in enumerate(self.tracks.get("players", [])):
                if not isinstance(frame_players, dict):
                    continue
                
                for pid, player in frame_players.items():
                    if not isinstance(player, dict):
                        continue
                    
                    if player.get("team") != team_id or "bbox" not in player:
                        continue
                    
                    # Check if player might be a referee by color analysis
                    is_referee = False
                    player_colour = player.get("team_colour")
                    
                    # Convert to tuple for comparison
                    if player_colour is not None:
                        if isinstance(player_colour, np.ndarray):
                            player_colour = tuple(player_colour.tolist())
                        elif isinstance(player_colour, list):
                            player_colour = tuple(player_colour)
                        
                        if isinstance(player_colour, tuple) and len(player_colour) == 3:
                            # Check if color matches referee colors
                            if referee_filter.is_referee_color(player_colour):
                                is_referee = True  # Skip referee-like colors
                    
                    # Check for overlap with detected referees
                    if not is_referee and frame_num < len(self.tracks.get("referees", [])):
                        frame_referees = self.tracks["referees"][frame_num]
                        if isinstance(frame_referees, dict):
                            player_bbox = player["bbox"]
                            for referee_id, referee in frame_referees.items():
                                if "bbox" in referee:
                                    iou = referee_filter.calculate_iou(player_bbox, referee["bbox"])
                                    if iou > 0.3:  # Significant overlap
                                        is_referee = True  # Skip this player (likely a referee)
                                        break
                    
                    # Skip if identified as referee
                    if is_referee:
                        continue
                    
                    # Check if player_colour is valid
                    if player_colour is None or not isinstance(player_colour, tuple) or len(player_colour) != 3:
                        continue
                    
                    # Analyze player position across all frames
                    analysis = self.analyze_player_positions(pid, team_id, frame_width, frame_height)
                    
                    # Skip if clearly a goalkeeper
                    if analysis["is_goalkeeper"]:
                        continue
                    
                    # Calculate color match score
                    color_match_score = 0
                    if most_common_colour is not None:
                        rounded_colour = tuple(int(round(c / 10.0) * 10) for c in player_colour)
                        if rounded_colour == most_common_colour:
                            color_match_score = 2  # Perfect match
                        elif self.colours_similar(player_colour, most_common_colour, tolerance=50):
                            color_match_score = 1  # Similar color
                    else:
                        color_match_score = 1  # No common color, accept any
                    
                    if color_match_score > 0:
                        key = (pid, frame_num)
                        if key not in player_candidates:
                            player_candidates[key] = (player, analysis, color_match_score)
            
            # Sort candidates by: 1) color match score (higher better), 2) center ratio (higher better = more in center)
            # 3) lower edge ratio (lower better = less time near edges)
            sorted_candidates = sorted(
                player_candidates.items(),
                key=lambda x: (
                    -x[1][2],  # color_match_score (negative for descending)
                    -x[1][1]["center_ratio"],  # center_ratio (negative for descending)
                    x[1][1]["edge_ratio"]  # edge_ratio (ascending)
                )
            )
            
            # Use the best candidate
            if sorted_candidates:
                (pid, frame_num), (player, analysis, color_score) = sorted_candidates[0]
                print(f"[DEBUG] Team {team_id}: Selected player {pid} from frame {frame_num}")
                print(f"[DEBUG]   - Color match score: {color_score}")
                print(f"[DEBUG]   - Edge ratio: {analysis['edge_ratio']:.2f}, Center ratio: {analysis['center_ratio']:.2f}")
                print(f"[DEBUG]   - Total candidates: {len(sorted_candidates)}")
                return self._extract_player_image(frame_num, player, max_size)
            
            # Fallback: Try with less strict filtering (allow goalkeepers if no other option)
            print(f"[DEBUG] No non-goalkeeper candidates found for team {team_id}, trying with all players")
            for frame_num, frame_players in enumerate(self.tracks.get("players", [])):
                if not isinstance(frame_players, dict):
                    continue
                
                for pid, player in frame_players.items():
                    if not isinstance(player, dict):
                        continue
                    
                    if player.get("team") == team_id and "bbox" in player:
                        # Still prefer players with matching color
                        player_colour = player.get("team_colour")
                        if player_colour is not None:
                            if isinstance(player_colour, np.ndarray):
                                player_colour = tuple(player_colour.tolist())
                            elif isinstance(player_colour, list):
                                player_colour = tuple(player_colour)
                            
                            if isinstance(player_colour, tuple) and len(player_colour) == 3:
                                if most_common_colour is None or self.colours_similar(player_colour, most_common_colour, tolerance=80):
                                    return self._extract_player_image(frame_num, player, max_size)
            
            # Final fallback: any player
            for frame_num, frame_players in enumerate(self.tracks.get("players", [])):
                if not isinstance(frame_players, dict):
                    continue
                
                for pid, player in frame_players.items():
                    if not isinstance(player, dict):
                        continue
                    
                    if player.get("team") == team_id and "bbox" in player:
                        return self._extract_player_image(frame_num, player, max_size)
            
        except Exception as e:
            print(f"Error extracting player image: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return None
    
    def _extract_player_image(self, frame_num: int, player: Dict, max_size: int = 180) -> Optional[QPixmap]:
        """Extract and process player image from frame"""
        try:
            if frame_num >= len(self.video_frames):
                return None
            
            frame = self.video_frames[frame_num]
            
            # Extract player image from bbox with padding (zoom out)
            bbox = player["bbox"]
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            
            # Calculate padding to zoom out (add 30% on each side)
            bbox_width = x2 - x1
            bbox_height = y2 - y1
            padding_x = int(bbox_width * 0.3)  # 30% padding on left and right
            padding_y = int(bbox_height * 0.4)  # 40% padding on top and bottom (more for head)
            
            # Apply padding
            x1 = x1 - padding_x
            y1 = y1 - padding_y
            x2 = x2 + padding_x
            y2 = y2 + padding_y
            
            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 > x1 and y2 > y1:
                player_image = frame[y1:y2, x1:x2].copy()  # Make a copy to ensure contiguous array
                
                # Resize to larger size for display
                h_img, w_img = player_image.shape[:2]
                if h_img > max_size or w_img > max_size:
                    scale = max_size / max(h_img, w_img)
                    new_w = int(w_img * scale)
                    new_h = int(h_img * scale)
                    import cv2
                    player_image = cv2.resize(player_image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                
                # Convert to QPixmap
                # Ensure array is contiguous and convert to bytes
                import cv2
                height, width, channel = player_image.shape
                bytes_per_line = 3 * width
                
                # Convert numpy array to bytes
                if not player_image.flags['C_CONTIGUOUS']:
                    player_image = np.ascontiguousarray(player_image)
                
                # Convert to bytes
                image_bytes = player_image.tobytes()
                
                q_image = QImage(image_bytes, width, height, bytes_per_line, QImage.Format.Format_BGR888)
                pixmap = QPixmap.fromImage(q_image)
                return pixmap
                
        except Exception as e:
            print(f"Error in _extract_player_image: {str(e)}")
        
        return None
    
    def display_team_statistics(self, summary: Dict):
        """Display team statistics (only accurate values)"""
        # summary structure: {"teams": {1: {...}, 2: {...}}, "overall": {...}}
        team_stats = summary.get("teams", {})
        
        for team_id in [1, 2]:
            if team_id not in team_stats:
                continue
            team_data = team_stats[team_id]
            
            team_frame = QFrame()
            team_frame.setStyleSheet("""
                QFrame {
                    background-color: #2b2b2b;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 5px;
                }
            """)
            team_layout = QHBoxLayout(team_frame)  # Changed to HBoxLayout for side-by-side layout
            
            # Left side: Player image
            image_container = QFrame()
            image_container.setFixedWidth(200)  # Increased from 140 to 200
            image_container.setFixedHeight(250)  # Set fixed height for better layout
            image_container.setStyleSheet("""
                QFrame {
                    background-color: #1a1a1a;
                    border: 2px solid #555;
                    border-radius: 6px;
                }
            """)
            image_layout = QVBoxLayout(image_container)
            image_layout.setContentsMargins(5, 5, 5, 5)
            image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Get player image
            player_pixmap = self.get_player_image(team_id, max_size=180)  # Increased max size
            if player_pixmap:
                player_label = QLabel()
                # Scale pixmap to fit container while maintaining aspect ratio
                scaled_pixmap = player_pixmap.scaled(
                    190, 240,  # Container size minus padding
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                player_label.setPixmap(scaled_pixmap)
                player_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                player_label.setStyleSheet("""
                    QLabel {
                        border: none;
                        background-color: transparent;
                    }
                """)
                image_layout.addWidget(player_label)
            else:
                # Placeholder if no image
                no_image_text = t("ไม่มีรูปภาพ", "No Image")
                placeholder_label = QLabel(no_image_text)
                placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder_label.setStyleSheet("""
                    QLabel {
                        color: #888;
                        font-size: 10pt;
                        background-color: transparent;
                    }
                """)
                image_layout.addWidget(placeholder_label)
            
            team_layout.addWidget(image_container)
            
            # Right side: Statistics
            stats_container = QWidget()
            stats_layout = QVBoxLayout(stats_container)
            
            # Team title
            team_title_text = t(f"ทีม {team_id}", f"Team {team_id}")
            team_title = QLabel(team_title_text)
            team_title.setStyleSheet("""
                QLabel {
                    color: #c41e3a;
                    font-size: 16pt;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
            """)
            stats_layout.addWidget(team_title)
            
            # Ball Possession (main stat)
            possession_text = t("ครองบอล:", "Ball Possession:")
            possession_label = QLabel(f"{possession_text} {team_data['ball_possession_percent']:.1f}%")
            possession_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-size: 18pt;
                    font-weight: bold;
                    padding: 10px;
                    background-color: #1a1a1a;
                    border-radius: 4px;
                    margin-bottom: 5px;
                }
            """)
            team_layout.addWidget(possession_label)
            
            # Other statistics
            possession_time_text = t("เวลาครองบอล:", "Possession Time:")
            possession_frames_text = t("เฟรมครองบอล:", "Possession Frames:")
            total_touches_text = t("การสัมผัสบอลทั้งหมด:", "Total Touches:")
            players_detected_text = t("จำนวนผู้เล่นที่ตรวจจับได้:", "Players Detected:")
            active_frames_text = t("เฟรมที่ใช้งาน:", "Active Frames:")
            minutes_text = t("นาที", "minutes")
            frames_text = t("เฟรม", "frames")
            stats_text = (
                f"{possession_time_text} {team_data['ball_possession_time_minutes']:.1f} {minutes_text}\n"
                f"{possession_frames_text} {team_data['ball_possession_frames']} {frames_text}\n"
                f"{total_touches_text} {team_data['total_touches']}\n"
                f"{players_detected_text} {team_data['total_players']}\n"
                f"{active_frames_text} {team_data['active_frames']}"
            )
            
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("""
                QLabel {
                    color: #e0e0e0;
                    font-size: 11pt;
                    padding: 5px;
                }
            """)
            stats_layout.addWidget(stats_label)
            
            stats_layout.addStretch()
            team_layout.addWidget(stats_container, 1)  # Stretch factor 1
            
            self.team_stats_layout.addWidget(team_frame)
        
        # Overall statistics
        overall_data = team_stats.get("overall", {})
        if overall_data:
            overall_frame = QFrame()
            overall_frame.setStyleSheet("""
                QFrame {
                    background-color: #1a1a1a;
                    border: 2px solid #555;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 10px 5px;
                }
            """)
            overall_layout = QVBoxLayout(overall_frame)
            
            overall_title_text = t("สถิติรวม", "Overall Statistics")
            overall_title = QLabel(overall_title_text)
            overall_title.setStyleSheet("""
                QLabel {
                    color: #c41e3a;
                    font-size: 14pt;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
            """)
            overall_layout.addWidget(overall_title)
            
            total_frames_text = t("เฟรมทั้งหมด:", "Total Frames:")
            video_duration_text = t("ระยะเวลาวิดีโอ:", "Video Duration:")
            team_players_text = t("ผู้เล่น", "Players")
            total_possession_frames_text = t("เฟรมครองบอลทั้งหมด:", "Total Possession Frames:")
            overall_text = (
                f"{total_frames_text} {overall_data.get('total_frames', 0)}\n"
                f"{video_duration_text} {overall_data.get('video_duration_minutes', 0):.1f} {minutes_text}\n"
                f"{t('ทีม 1', 'Team 1')} {team_players_text}: {overall_data.get('total_players_team1', 0)}\n"
                f"{t('ทีม 2', 'Team 2')} {team_players_text}: {overall_data.get('total_players_team2', 0)}\n"
                f"{total_possession_frames_text} {overall_data.get('total_ball_possession_frames', 0)}"
            )
            
            overall_label = QLabel(overall_text)
            overall_label.setStyleSheet("""
                QLabel {
                    color: #b0b0b0;
                    font-size: 11pt;
                    padding: 5px;
                }
            """)
            overall_layout.addWidget(overall_label)
            
            self.team_stats_layout.addWidget(overall_frame)
    
    def display_top_players(self, top_players: Dict):
        """Display top players statistics - removed as we only show team stats now"""
        # Top players section removed - only showing team statistics
        pass
    
    def create_movement_analysis_subtab(self):
        """Create Movement Analysis sub-tab with movement analysis features"""
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Info label
        movement_info_text = t("วิเคราะห์การเคลื่อนไหวจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Movement analysis will be displayed after analyzing video")
        info_label = QLabel(movement_info_text)
        self.ui_elements_to_translate[info_label] = ("วิเคราะห์การเคลื่อนไหวจะแสดงผลหลังจากกดวิเคราะห์วิดีโอ", "Movement analysis will be displayed after analyzing video")
        info_label.setStyleSheet("color: #b0b0b0; font-size: 11pt; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Warning/Info box about accuracy
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a1a;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 10px;
            }
        """)
        warning_layout = QVBoxLayout(warning_frame)
        # Define warning text in both languages
        warning_full_text_th = (
            "⚠️ หมายเหตุเกี่ยวกับความแม่นยำ:\n• หน่วย px/s = pixels per second (พิกเซลต่อวินาที)\n• ไม่สามารถแปลงเป็น m/s ได้โดยไม่มี field calibration\n• ข้อมูลนี้มาจาก AI tracking ซึ่งมีความแม่นยำประมาณ 90-95%\n• ความเร็วและระยะทางเป็นค่าสัมพัทธ์สำหรับเปรียบเทียบ\n• ใช้สำหรับวิเคราะห์รูปแบบการเล่นและการเปรียบเทียบระหว่างผู้เล่น"
        )
        warning_full_text_en = (
            "⚠️ Note about accuracy:\n• Unit px/s = pixels per second\n• Cannot convert to m/s without field calibration\n• This data comes from AI tracking with approximately 90-95% accuracy\n• Speed and distance are relative values for comparison\n• Used for analyzing playing patterns and comparing between players"
        )
        # Use current language to set initial text - check language directly
        current_lang = self.translation_manager.get_language()
        if current_lang == "EN":
            warning_text = warning_full_text_en
        else:
            warning_text = warning_full_text_th
        warning_label = QLabel(warning_text)
        # Store both languages for refresh
        self.ui_elements_to_translate[warning_label] = (warning_full_text_th, warning_full_text_en)
        warning_label.setStyleSheet("color: #ffcc00; font-size: 9pt;")
        warning_label.setWordWrap(True)
        warning_layout.addWidget(warning_label)
        layout.addWidget(warning_frame)
        
        # Controls section
        controls_layout = QHBoxLayout()
        
        # Analysis type selector
        analysis_group_text = t("ประเภทการวิเคราะห์", "Analysis Type")
        analysis_group = QGroupBox(analysis_group_text)
        self.ui_elements_to_translate[analysis_group] = ("ประเภทการวิเคราะห์", "Analysis Type")
        analysis_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        analysis_layout = QVBoxLayout()
        
        self.movement_analysis_radio_group = QButtonGroup()
        movement_paths_text = t("เส้นทางการเคลื่อนที่", "Movement Paths")
        self.radio_movement_paths = QRadioButton(movement_paths_text)
        self.ui_elements_to_translate[self.radio_movement_paths] = ("เส้นทางการเคลื่อนที่", "Movement Paths")
        speed_zones_text = t("Speed Zones (พื้นที่ความเร็วสูง)", "Speed Zones (High Speed Areas)")
        self.radio_speed_zones = QRadioButton(speed_zones_text)
        self.ui_elements_to_translate[self.radio_speed_zones] = ("Speed Zones (พื้นที่ความเร็วสูง)", "Speed Zones (High Speed Areas)")
        speed_chart_text = t("กราฟความเร็ว", "Speed Chart")
        self.radio_speed_chart = QRadioButton(speed_chart_text)
        self.ui_elements_to_translate[self.radio_speed_chart] = ("กราฟความเร็ว", "Speed Chart")
        movement_stats_text = t("สถิติการเคลื่อนไหว", "Movement Statistics")
        self.radio_movement_stats = QRadioButton(movement_stats_text)
        self.ui_elements_to_translate[self.radio_movement_stats] = ("สถิติการเคลื่อนไหว", "Movement Statistics")
        
        self.movement_analysis_radio_group.addButton(self.radio_movement_paths, 0)
        self.movement_analysis_radio_group.addButton(self.radio_speed_zones, 1)
        self.movement_analysis_radio_group.addButton(self.radio_speed_chart, 2)
        self.movement_analysis_radio_group.addButton(self.radio_movement_stats, 3)
        
        radio_style = """
            QRadioButton {
                font-size: 10pt;
                color: #e0e0e0;
                spacing: 8px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #666;
                background-color: #2b2b2b;
            }
            QRadioButton::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
        """
        self.radio_movement_paths.setStyleSheet(radio_style)
        self.radio_speed_zones.setStyleSheet(radio_style)
        self.radio_speed_chart.setStyleSheet(radio_style)
        self.radio_movement_stats.setStyleSheet(radio_style)
        self.radio_movement_paths.setChecked(True)
        
        analysis_layout.addWidget(self.radio_movement_paths)
        analysis_layout.addWidget(self.radio_speed_zones)
        analysis_layout.addWidget(self.radio_speed_chart)
        analysis_layout.addWidget(self.radio_movement_stats)
        analysis_group.setLayout(analysis_layout)
        
        # Team/Player selector
        selector_group_text = t("เลือกทีม/ผู้เล่น", "Select Team/Player")
        selector_group = QGroupBox(selector_group_text)
        self.ui_elements_to_translate[selector_group] = ("เลือกทีม/ผู้เล่น", "Select Team/Player")
        selector_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        selector_layout = QVBoxLayout()
        
        self.movement_team_radio_group = QButtonGroup()
        movement_all_text = t("ผู้เล่นทั้งหมด", "All Players")
        self.radio_movement_all = QRadioButton(movement_all_text)
        self.ui_elements_to_translate[self.radio_movement_all] = ("ผู้เล่นทั้งหมด", "All Players")
        movement_team1_text = t("ทีม 1", "Team 1")
        self.radio_movement_team1 = QRadioButton(movement_team1_text)
        self.ui_elements_to_translate[self.radio_movement_team1] = ("ทีม 1", "Team 1")
        movement_team2_text = t("ทีม 2", "Team 2")
        self.radio_movement_team2 = QRadioButton(movement_team2_text)
        self.ui_elements_to_translate[self.radio_movement_team2] = ("ทีม 2", "Team 2")
        self.radio_movement_all.setChecked(True)
        
        self.movement_team_radio_group.addButton(self.radio_movement_all, 0)
        self.movement_team_radio_group.addButton(self.radio_movement_team1, 1)
        self.movement_team_radio_group.addButton(self.radio_movement_team2, 2)
        
        self.radio_movement_all.setStyleSheet(radio_style)
        self.radio_movement_team1.setStyleSheet(radio_style)
        self.radio_movement_team2.setStyleSheet(radio_style)
        
        selector_layout.addWidget(self.radio_movement_all)
        selector_layout.addWidget(self.radio_movement_team1)
        selector_layout.addWidget(self.radio_movement_team2)
        
        # Speed threshold for speed zones
        speed_threshold_layout = QHBoxLayout()
        speed_threshold_text = t("Speed Threshold:", "Speed Threshold:")
        speed_threshold_label = QLabel(speed_threshold_text)
        self.ui_elements_to_translate[speed_threshold_label] = ("Speed Threshold:", "Speed Threshold:")
        speed_threshold_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        self.speed_threshold_spin = QSpinBox()
        self.speed_threshold_spin.setMinimum(0)
        self.speed_threshold_spin.setMaximum(10000)
        self.speed_threshold_spin.setValue(100)
        self.speed_threshold_spin.setSuffix(" px/s")
        self.speed_threshold_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                font-size: 10pt;
            }
        """)
        speed_threshold_layout.addWidget(speed_threshold_label)
        speed_threshold_layout.addWidget(self.speed_threshold_spin)
        speed_threshold_layout.addStretch()
        selector_layout.addLayout(speed_threshold_layout)
        
        selector_group.setLayout(selector_layout)
        
        controls_layout.addWidget(analysis_group)
        controls_layout.addWidget(selector_group)
        layout.addLayout(controls_layout)
        
        # Connect signals
        self.radio_movement_paths.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_speed_zones.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_speed_chart.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_movement_stats.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_movement_all.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_movement_team1.toggled.connect(lambda: self.update_movement_analysis())
        self.radio_movement_team2.toggled.connect(lambda: self.update_movement_analysis())
        self.speed_threshold_spin.valueChanged.connect(lambda: self.update_movement_analysis())
        
        # Display area
        display_frame = QFrame()
        display_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #555;
                border-radius: 6px;
            }
        """)
        display_layout = QVBoxLayout(display_frame)
        display_layout.setContentsMargins(10, 10, 10, 10)
        
        # Image/chart label
        self.movement_analysis_label = QLabel()
        self.movement_analysis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.movement_analysis_label.setMinimumHeight(400)
        no_movement_data_text = t("ยังไม่มีข้อมูลการวิเคราะห์การเคลื่อนไหว\nกรุณากดวิเคราะห์วิดีโอก่อน", "No movement analysis data yet\nPlease analyze video first")
        self.movement_analysis_label.setText(no_movement_data_text)
        if not hasattr(self, 'movement_analysis_label_text'):
            self.movement_analysis_label_text = ("ยังไม่มีข้อมูลการวิเคราะห์การเคลื่อนไหว\nกรุณากดวิเคราะห์วิดีโอก่อน", "No movement analysis data yet\nPlease analyze video first")
        # Store for translation refresh
        if hasattr(self, 'ui_elements_to_translate'):
            self.ui_elements_to_translate[self.movement_analysis_label] = self.movement_analysis_label_text
        self.movement_analysis_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                color: #888;
                font-size: 12pt;
            }
        """)
        display_layout.addWidget(self.movement_analysis_label)
        
        # Statistics text area (for movement stats)
        self.movement_stats_text = QTextEdit()
        self.movement_stats_text.setReadOnly(True)
        self.movement_stats_text.setVisible(False)
        self.movement_stats_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 10pt;
                font-family: 'Courier New', monospace;
            }
        """)
        display_layout.addWidget(self.movement_stats_text)
        
        layout.addWidget(display_frame, 1)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_movement_text = t("บันทึกภาพวิเคราะห์", "Save Analysis Image")
        self.btn_save_movement = QPushButton(save_movement_text)
        self.ui_elements_to_translate[self.btn_save_movement] = ("บันทึกภาพวิเคราะห์", "Save Analysis Image")
        self.btn_save_movement.clicked.connect(self.save_movement_analysis)
        self.btn_save_movement.setEnabled(False)
        self.btn_save_movement.setMinimumHeight(40)
        self.btn_save_movement.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11pt;
                border: none;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        button_layout.addWidget(self.btn_save_movement)
        layout.addLayout(button_layout)
        
        return widget
    
    def create_pass_analysis_subtab(self):
        """Create Pass Analysis sub-tab (Coming Soon)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Coming soon message
        pass_coming_soon_text_th = "การวิเคราะห์การส่งบอล\nเร็วๆ นี้"
        pass_coming_soon_text_en = "Pass Analysis\nComing Soon"
        current_lang = self.translation_manager.get_language()
        pass_coming_soon_text = pass_coming_soon_text_en if current_lang == "EN" else pass_coming_soon_text_th
        coming_soon_label = QLabel(pass_coming_soon_text)
        self.ui_elements_to_translate[coming_soon_label] = (pass_coming_soon_text_th, pass_coming_soon_text_en)
        coming_soon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coming_soon_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 24pt;
                font-weight: bold;
                padding: 40px;
            }
        """)
        layout.addWidget(coming_soon_label)
        
        # Description
        pass_desc_text_th = (
            "แท็บนี้จะแสดง:\n• อัตราความสำเร็จในการส่งบอล\n• การวิเคราะห์ระยะทางการส่งบอล\n• Heat Map ทิศทางการส่งบอล\n• การระบุการส่งบอลสำคัญ\n• ห่วงโซ่การส่งบอล\n• และอื่นๆ..."
        )
        pass_desc_text_en = (
            "This tab will show:\n• Pass success rate\n• Pass distance analysis\n• Pass direction heat map\n• Key passes identification\n• Pass chains\n• And more..."
        )
        pass_desc_text = pass_desc_text_en if current_lang == "EN" else pass_desc_text_th
        desc_label = QLabel(pass_desc_text)
        self.ui_elements_to_translate[desc_label] = (pass_desc_text_th, pass_desc_text_en)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 12pt;
                padding: 20px;
            }
        """)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        return widget
    
    def create_zone_analysis_subtab(self):
        """Create Zone Analysis sub-tab (Coming Soon)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Coming soon message
        zone_coming_soon_text_th = "การวิเคราะห์โซน\nเร็วๆ นี้"
        zone_coming_soon_text_en = "Zone Analysis\nComing Soon"
        current_lang = self.translation_manager.get_language()
        zone_coming_soon_text = zone_coming_soon_text_en if current_lang == "EN" else zone_coming_soon_text_th
        coming_soon_label = QLabel(zone_coming_soon_text)
        self.ui_elements_to_translate[coming_soon_label] = (zone_coming_soon_text_th, zone_coming_soon_text_en)
        coming_soon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coming_soon_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 24pt;
                font-weight: bold;
                padding: 40px;
            }
        """)
        layout.addWidget(coming_soon_label)
        
        # Description
        zone_desc_text_th = (
            "แท็บนี้จะแสดง:\n• กิจกรรมตามโซนสนาม\n• การวิเคราะห์โซนป้องกัน\n• การวิเคราะห์โซนกลาง\n• การวิเคราะห์โซนบุก\n• สถิติตามโซน\n• และอื่นๆ..."
        )
        zone_desc_text_en = (
            "This tab will show:\n• Activity by field zones\n• Defensive third analysis\n• Middle third analysis\n• Attacking third analysis\n• Zone-based statistics\n• And more..."
        )
        zone_desc_text = zone_desc_text_en if current_lang == "EN" else zone_desc_text_th
        desc_label = QLabel(zone_desc_text)
        self.ui_elements_to_translate[desc_label] = (zone_desc_text_th, zone_desc_text_en)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 12pt;
                padding: 20px;
            }
        """)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        return widget
    
    def update_heat_maps(self):
        """Update heat maps when tracking data is available"""
        if not self.tracks:
            return
        
        self.update_heat_map_display()
    
    def update_heat_map_display(self):
        """
        Update the displayed heat map based on selected radio button
        Optimized for memory efficiency:
        - Clears old images before creating new ones
        - Uses display-optimized size instead of full resolution
        - Only stores full resolution when saving
        """
        if not self.tracks:
            self.heat_map_label.setText(t("ยังไม่มีข้อมูล Heat Map\nกรุณากดวิเคราะห์วิดีโอก่อน", "No Heat Map data yet\nPlease analyze video first"))
            if not hasattr(self, 'heat_map_label_text'):
                self.heat_map_label_text = "ยังไม่มีข้อมูล Heat Map\nกรุณากดวิเคราะห์วิดีโอก่อน"
            self.btn_save_heat_map.setEnabled(False)
            return
        
        try:
            # Clear old images to free memory
            if hasattr(self, 'current_heat_map_image'):
                del self.current_heat_map_image
            self.current_heat_map_image = None
            
            # Import heat map generator
            from analytics import HeatMapGenerator
            
            # Get display size (smaller for display, saves memory)
            label_size = self.heat_map_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                # Use display size for rendering (max 1280x720 for memory efficiency)
                display_width = min(label_size.width() - 20, 1280)
                display_height = min(label_size.height() - 20, 720)
            else:
                # Default display size
                display_width = 1280
                display_height = 720
            
            # Get original field dimensions for full resolution (only when saving)
            original_field_width = 1920
            original_field_height = 1080
            if self.video_frames and len(self.video_frames) > 0:
                original_field_height, original_field_width = self.video_frames[0].shape[:2]
            
            # Use smaller size for display to save memory
            generator = HeatMapGenerator(field_width=display_width, field_height=display_height)
            
            # Generate heat map based on selection (at display resolution)
            if self.radio_all_players.isChecked():
                heat_map = generator.generate_player_heat_map(self.tracks, sigma=35.0)
                title = "Heat Map - All Players"
                self.current_heat_map_type = "all_players"
            elif self.radio_team1.isChecked():
                heat_map = generator.generate_team_heat_map(self.tracks, team_id=1, sigma=35.0)
                title = "Heat Map - Team 1"
                self.current_heat_map_type = "team_1"
            elif self.radio_team2.isChecked():
                heat_map = generator.generate_team_heat_map(self.tracks, team_id=2, sigma=35.0)
                title = "Heat Map - Team 2"
                self.current_heat_map_type = "team_2"
            elif self.radio_ball.isChecked():
                heat_map = generator.generate_ball_heat_map(self.tracks, sigma=25.0)
                title = "Heat Map - Ball"
                self.current_heat_map_type = "ball"
            else:
                heat_map = generator.generate_player_heat_map(self.tracks, sigma=35.0)
                title = "Heat Map - All Players"
                self.current_heat_map_type = "all_players"
            
            # Create field background (at display resolution)
            field_bg = generator.create_field_background()
            
            # Overlay heat map on field with title (at display resolution)
            result_image = generator.overlay_heat_map(field_bg, heat_map, title=title)
            
            # Convert to QPixmap and display (no need to store full res for display)
            height, width, channel = result_image.shape
            bytes_per_line = 3 * width
            q_image = QImage(result_image.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(q_image)
            
            # Scale to fit label (already at display size, just fit to label)
            if label_size.width() > 0 and label_size.height() > 0:
                scaled_pixmap = pixmap.scaled(
                    label_size.width() - 20, 
                    label_size.height() - 20,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.heat_map_label.setPixmap(scaled_pixmap)
            else:
                self.heat_map_label.setPixmap(pixmap)
            
            # Clear intermediate variables to free memory
            del heat_map, field_bg, result_image, q_image, pixmap
            if 'scaled_pixmap' in locals():
                del scaled_pixmap
            
            # Store generator and tracks for full resolution generation when saving
            self.heat_map_generator = generator
            self.original_field_size = (original_field_width, original_field_height)
            self.current_heat_map_title = title
            
            # Enable save button
            self.btn_save_heat_map.setEnabled(True)
                
        except Exception as e:
            self.heat_map_label.setText(f"{t('เกิดข้อผิดพลาด:', 'Error occurred:')} {str(e)}")
            self.btn_save_heat_map.setEnabled(False)
            import traceback
            print(traceback.format_exc())
    
    def save_heat_map(self):
        """
        Save current heat map as PNG file
        Generates full resolution image only when saving (memory efficient)
        Opens file dialog first, then processes and saves
        """
        if not self.tracks:
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), t("ไม่มี Heat Map ที่จะบันทึก", "No Heat Map to save"))
            return
        
        try:
            from datetime import datetime
            
            # Get save location from user first
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create default filename
            type_name_map = {
                "all_players": "AllPlayers",
                "team_1": "Team1",
                "team_2": "Team2",
                "ball": "Ball"
            }
            type_name = type_name_map.get(self.current_heat_map_type, "heatmap")
            default_filename = f"heatmap_{type_name}_{timestamp}.png"
            
            # Open file dialog immediately
            save_heat_map_title = t("บันทึก Heat Map", "Save Heat Map")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                save_heat_map_title,
                os.path.join(PROJECT_ROOT, "output", default_filename),
                "PNG Files (*.png);;All Files (*)"
            )
            
            # Only process if user selected a file
            if file_path:
                # Generate full resolution heat map only when saving
                from analytics import HeatMapGenerator
                
                # Get original field dimensions
                field_width, field_height = self.original_field_size
                
                # Create generator with full resolution
                generator = HeatMapGenerator(field_width=field_width, field_height=field_height)
                
                # Generate heat map at full resolution
                if self.current_heat_map_type == "all_players":
                    heat_map = generator.generate_player_heat_map(self.tracks, sigma=35.0)
                    title = "Heat Map - All Players"
                elif self.current_heat_map_type == "team_1":
                    heat_map = generator.generate_team_heat_map(self.tracks, team_id=1, sigma=35.0)
                    title = "Heat Map - Team 1"
                elif self.current_heat_map_type == "team_2":
                    heat_map = generator.generate_team_heat_map(self.tracks, team_id=2, sigma=35.0)
                    title = "Heat Map - Team 2"
                elif self.current_heat_map_type == "ball":
                    heat_map = generator.generate_ball_heat_map(self.tracks, sigma=25.0)
                    title = "Heat Map - Ball"
                else:
                    heat_map = generator.generate_player_heat_map(self.tracks, sigma=35.0)
                    title = "Heat Map - All Players"
                
                # Create field background at full resolution
                field_bg = generator.create_field_background()
                
                # Overlay heat map with title at full resolution
                full_res_image = generator.overlay_heat_map(field_bg, heat_map, title=title)
                
                # Save full resolution image
                import cv2
                cv2.imwrite(file_path, full_res_image)
                
                # Clear full resolution image from memory
                del full_res_image, heat_map, field_bg
                
                QMessageBox.information(
                    self, 
                    "สำเร็จ", 
                    f"บันทึก Heat Map เรียบร้อยแล้ว\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "ข้อผิดพลาด", 
                f"เกิดข้อผิดพลาดในการบันทึกไฟล์:\n{str(e)}"
            )
            import traceback
            print(traceback.format_exc())
    
    def update_movement_analysis(self):
        """Update movement analysis display based on selected options"""
        if not self.tracks:
            self.movement_analysis_label.setText(t("ยังไม่มีข้อมูลการวิเคราะห์การเคลื่อนไหว\nกรุณากดวิเคราะห์วิดีโอก่อน", "No movement analysis data yet\nPlease analyze video first"))
            if not hasattr(self, 'movement_analysis_label_text'):
                self.movement_analysis_label_text = "ยังไม่มีข้อมูลการวิเคราะห์การเคลื่อนไหว\nกรุณากดวิเคราะห์วิดีโอก่อน"
            self.movement_analysis_label.setVisible(True)
            self.movement_stats_text.setVisible(False)
            self.btn_save_movement.setEnabled(False)
            return
        
        try:
            from analytics import MovementAnalyzer, HeatMapGenerator
            
            # Get field dimensions
            field_width = 1920
            field_height = 1080
            if self.video_frames and len(self.video_frames) > 0:
                field_height, field_width = self.video_frames[0].shape[:2]
            
            # Get team filter
            team_id = None
            if self.radio_movement_team1.isChecked():
                team_id = 1
            elif self.radio_movement_team2.isChecked():
                team_id = 2
            
            # Initialize analyzer
            analyzer = MovementAnalyzer(
                fps=self.video_fps,
                field_width=field_width,
                field_height=field_height
            )
            
            # Get display size
            label_size = self.movement_analysis_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                display_width = min(label_size.width() - 20, 1280)
                display_height = min(label_size.height() - 20, 720)
            else:
                display_width = 1280
                display_height = 720
            
            # Scale field dimensions for display
            scale_x = display_width / field_width
            scale_y = display_height / field_height
            scale = min(scale_x, scale_y)
            display_field_width = int(field_width * scale)
            display_field_height = int(field_height * scale)
            
            analyzer.field_width = display_field_width
            analyzer.field_height = display_field_height
            
            # Generate visualization based on selection
            if self.radio_movement_paths.isChecked():
                # Show movement paths
                self.movement_analysis_label.setVisible(True)
                self.movement_stats_text.setVisible(False)
                
                # Create field background
                generator = HeatMapGenerator(field_width=display_field_width, field_height=display_field_height)
                field_bg = generator.create_field_background()
                
                # Draw paths for all players in selected team
                player_positions = analyzer.get_player_positions_over_time(self.tracks, team_id=team_id)
                
                # Use different colors for different players
                colors = [
                    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0),
                    (255, 192, 203), (0, 128, 128), (128, 128, 0), (128, 0, 0)
                ]
                
                result_image = field_bg.copy()
                for idx, (pid, positions) in enumerate(player_positions.items()):
                    color = colors[idx % len(colors)]
                    result_image = analyzer.draw_movement_path(positions, result_image, color, thickness=2)
                
                # Convert to QPixmap
                height, width, channel = result_image.shape
                bytes_per_line = 3 * width
                q_image = QImage(result_image.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
                pixmap = QPixmap.fromImage(q_image)
                pixmap = pixmap.scaled(
                    display_width, display_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.movement_analysis_label.setPixmap(pixmap)
                self.current_movement_analysis_image = result_image
                self.btn_save_movement.setEnabled(True)
                
            elif self.radio_speed_zones.isChecked():
                # Show speed zones heat map
                self.movement_analysis_label.setVisible(True)
                self.movement_stats_text.setVisible(False)
                
                speed_threshold = self.speed_threshold_spin.value()
                
                # Use original field dimensions for analysis
                full_analyzer = MovementAnalyzer(
                    fps=self.video_fps,
                    field_width=field_width,
                    field_height=field_height
                )
                
                # Generate speed zones heat map at original resolution
                heat_map = full_analyzer.generate_speed_zones_heat_map(
                    self.tracks,
                    speed_threshold=speed_threshold,
                    team_id=team_id,
                    sigma=35.0
                )
                
                # Check if heat map is valid
                if heat_map is None or heat_map.size == 0:
                    self.movement_analysis_label.setText(t(f"ไม่มีข้อมูลความเร็วสูงกว่า {speed_threshold} px/s", f"No data with speed higher than {speed_threshold} px/s"))
                    self.btn_save_movement.setEnabled(False)
                    return
                
                # Resize heat map to display size
                heat_map_resized = cv2.resize(heat_map, (display_field_width, display_field_height))
                
                # Create field background at display size
                generator = HeatMapGenerator(field_width=display_field_width, field_height=display_field_height)
                field_bg = generator.create_field_background()
                
                # Blend heat map with field
                result_image = cv2.addWeighted(field_bg, 0.5, heat_map_resized, 0.7, 0)
                
                # Add title
                speed_zones_label = t("Speed Zones", "Speed Zones")
                team_label = t("Team", "Team")
                title_text = f"{speed_zones_label} (>{speed_threshold} px/s)"
                if team_id:
                    title_text += f" - {team_label} {team_id}"
                cv2.putText(result_image, title_text, (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
                
                # Convert to QPixmap
                height, width, channel = result_image.shape
                bytes_per_line = 3 * width
                q_image = QImage(result_image.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
                pixmap = QPixmap.fromImage(q_image)
                pixmap = pixmap.scaled(
                    display_width, display_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.movement_analysis_label.setPixmap(pixmap)
                self.current_movement_analysis_image = result_image
                self.btn_save_movement.setEnabled(True)
                
            elif self.radio_speed_chart.isChecked():
                # Show speed chart
                self.movement_analysis_label.setVisible(True)
                self.movement_stats_text.setVisible(False)
                
                # Get first player's speed data (or average of all players)
                analysis = analyzer.analyze_player_movement(self.tracks, team_id=team_id)
                
                if analysis:
                    # Combine speeds from all players
                    all_speeds = []
                    for pid, data in analysis.items():
                        all_speeds.extend(data["speeds"])
                    
                    if all_speeds:
                        # Group by frame and average
                        speeds_by_frame = {}
                        for speed, frame in all_speeds:
                            if frame not in speeds_by_frame:
                                speeds_by_frame[frame] = []
                            speeds_by_frame[frame].append(speed)
                        
                        avg_speeds = [(np.mean(speeds_by_frame[frame]), frame) 
                                     for frame in sorted(speeds_by_frame.keys())]
                        
                        # Create chart
                        chart_title = t("Average Speed Over Time", "Average Speed Over Time")
                        if team_id:
                            team_label = t("Team", "Team")
                            chart_title += f" - {team_label} {team_id}"
                        
                        chart_image = analyzer.create_speed_chart(avg_speeds, title=chart_title)
                        
                        # Convert to QPixmap
                        height, width, channel = chart_image.shape
                        bytes_per_line = 3 * width
                        q_image = QImage(chart_image.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
                        pixmap = QPixmap.fromImage(q_image)
                        pixmap = pixmap.scaled(
                            display_width, min(display_height, 400),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.movement_analysis_label.setPixmap(pixmap)
                        self.current_movement_analysis_image = chart_image
                        self.btn_save_movement.setEnabled(True)
                    else:
                        self.movement_analysis_label.setText(t("ไม่มีข้อมูลความเร็ว", "No speed data"))
                        self.btn_save_movement.setEnabled(False)
                else:
                    self.movement_analysis_label.setText(t("ไม่มีข้อมูลผู้เล่น", "No player data"))
                    self.btn_save_movement.setEnabled(False)
                    
            elif self.radio_movement_stats.isChecked():
                # Show movement statistics
                self.movement_analysis_label.setVisible(False)
                self.movement_stats_text.setVisible(True)
                
                analysis = analyzer.analyze_player_movement(self.tracks, team_id=team_id)
                
                movement_stats_title = t("=== สถิติการเคลื่อนไหว ===", "=== Movement Statistics ===")
                stats_text = f"{movement_stats_title}\n\n"
                if team_id:
                    team_label = t("ทีม:", "Team:")
                    stats_text += f"{team_label} {team_id}\n\n"
                else:
                    all_players_label = t("ผู้เล่นทั้งหมด", "All Players")
                    stats_text += f"{all_players_label}\n\n"
                
                if analysis:
                    # Calculate team averages
                    total_distance = 0.0
                    total_avg_speed = 0.0
                    max_speed = 0.0
                    player_count = 0
                    
                    for pid, data in analysis.items():
                        total_distance += data["total_distance"]
                        total_avg_speed += data["avg_speed"]
                        max_speed = max(max_speed, data["max_speed"])
                        player_count += 1
                    
                    if player_count > 0:
                        num_players_label = t("จำนวนผู้เล่น:", "Number of Players:")
                        avg_total_distance_label = t("ระยะทางรวมเฉลี่ย:", "Average Total Distance:")
                        avg_speed_label = t("ความเร็วเฉลี่ย:", "Average Speed:")
                        max_speed_label = t("ความเร็วสูงสุด:", "Maximum Speed:")
                        stats_text += f"{num_players_label} {player_count}\n"
                        stats_text += f"{avg_total_distance_label} {total_distance/player_count:.1f} pixels\n"
                        stats_text += f"{avg_speed_label} {total_avg_speed/player_count:.1f} px/s\n"
                        stats_text += f"{max_speed_label} {max_speed:.1f} px/s\n\n"
                    
                    player_details_label = t("--- รายละเอียดผู้เล่น ---", "--- Player Details ---")
                    unit_note_label = t("⚠️ หน่วย: px = pixels (พิกเซล), px/s = pixels per second", "⚠️ Units: px = pixels, px/s = pixels per second")
                    relative_note_label = t("   ข้อมูลนี้เป็นค่าสัมพัทธ์ ใช้สำหรับเปรียบเทียบเท่านั้น", "   This data is relative and for comparison only")
                    stats_text += f"{player_details_label}\n"
                    stats_text += f"{unit_note_label}\n"
                    stats_text += f"{relative_note_label}\n\n"
                    
                    player_id_label = t("Player ID", "Player ID")
                    total_distance_label = t("ระยะทางรวม:", "Total Distance:")
                    avg_speed_label = t("ความเร็วเฉลี่ย:", "Average Speed:")
                    max_speed_label = t("ความเร็วสูงสุด:", "Maximum Speed:")
                    min_speed_label = t("ความเร็วต่ำสุด:", "Minimum Speed:")
                    play_time_label = t("เวลาเล่น:", "Play Time:")
                    seconds_label = t("วินาที", "seconds")
                    num_frames_label = t("จำนวนเฟรม:", "Number of Frames:")
                    for pid, data in analysis.items():
                        stats_text += f"{player_id_label} {pid}:\n"
                        stats_text += f"  {total_distance_label} {data['total_distance']:.1f} px\n"
                        stats_text += f"  {avg_speed_label} {data['avg_speed']:.1f} px/s\n"
                        stats_text += f"  {max_speed_label} {data['max_speed']:.1f} px/s\n"
                        stats_text += f"  {min_speed_label} {data['min_speed']:.1f} px/s\n"
                        stats_text += f"  {play_time_label} {data['total_time']:.1f} {seconds_label}\n"
                        stats_text += f"  {num_frames_label} {data['num_frames']}\n\n"
                else:
                    no_movement_data_label = t("ไม่มีข้อมูลการเคลื่อนไหว", "No movement data")
                    stats_text += no_movement_data_label
                
                self.movement_stats_text.setPlainText(stats_text)
                self.btn_save_movement.setEnabled(False)  # Can't save text as image
            else:
                self.movement_analysis_label.setVisible(True)
                self.movement_stats_text.setVisible(False)
                
        except Exception as e:
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), f"{t('เกิดข้อผิดพลาดในการวิเคราะห์การเคลื่อนไหว:', 'Error occurred during movement analysis:')}\n{str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def save_movement_analysis(self):
        """Save current movement analysis visualization as PNG"""
        if not hasattr(self, 'current_movement_analysis_image'):
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), t("ไม่มีภาพที่จะบันทึก", "No image to save"))
            return
        
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Determine file type
            if self.radio_movement_paths.isChecked():
                file_type = "movement_paths"
            elif self.radio_speed_zones.isChecked():
                file_type = "speed_zones"
            elif self.radio_speed_chart.isChecked():
                file_type = "speed_chart"
            else:
                file_type = "movement_analysis"
            
            default_filename = f"movement_{file_type}_{timestamp}.png"
            
            save_movement_title = t("บันทึกภาพวิเคราะห์การเคลื่อนไหว", "Save Movement Analysis Image")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                save_movement_title,
                os.path.join(PROJECT_ROOT, "output", default_filename),
                "PNG Files (*.png);;All Files (*)"
            )
            
            if file_path:
                cv2.imwrite(file_path, self.current_movement_analysis_image)
                QMessageBox.information(
                    self,
                    "สำเร็จ",
                    f"บันทึกภาพเรียบร้อยแล้ว\n{file_path}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "ข้อผิดพลาด",
                f"เกิดข้อผิดพลาดในการบันทึกไฟล์:\n{str(e)}"
            )
            import traceback
            print(traceback.format_exc())
    
    def create_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        logs_title_text = t("Logs", "Logs")
        title = QLabel(logs_title_text)
        self.ui_elements_to_translate[title] = "Logs"
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Log file selector
        log_label_text = t("เลือกไฟล์ Log:", "Select Log File:")
        log_label = QLabel(log_label_text)
        self.ui_elements_to_translate[log_label] = "เลือกไฟล์ Log:"
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px; color: #e0e0e0;")
        layout.addWidget(log_label)
        
        log_button_layout = QHBoxLayout()
        self.log_buttons = QButtonGroup()
        
        log_files = [
            (os.path.join(PROJECT_ROOT, "logs", "tracking.log"), t("Tracking Log", "Tracking Log")),
            (os.path.join(PROJECT_ROOT, "logs", "camera_movement.log"), t("Camera Movement Log", "Camera Movement Log")),
            (os.path.join(PROJECT_ROOT, "logs", "memory_access.log"), t("Memory Access Log", "Memory Access Log"))
        ]
        
        self.log_radio_buttons = {}
        self.log_radio_buttons_translation = {}
        for log_path, log_name in log_files:
            radio = QRadioButton(log_name)
            radio.log_path = log_path
            # Store original English name for translation
            original_name = "Tracking Log" if "tracking.log" in log_path else ("Camera Movement Log" if "camera_movement.log" in log_path else "Memory Access Log")
            self.log_radio_buttons_translation[radio] = original_name
            self.log_buttons.addButton(radio)
            log_button_layout.addWidget(radio)
            self.log_radio_buttons[log_path] = radio
        
        for radio in self.log_radio_buttons.values():
            radio.toggled.connect(lambda checked, r=radio: self.load_log_file(r.log_path) if checked else None)
        
        layout.addLayout(log_button_layout)
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 15px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Refresh button (optional - kept for manual refresh if needed)
        refresh_text = t("รีเฟรช (Refresh)", "Refresh")
        refresh_btn = QPushButton(refresh_text)
        self.ui_elements_to_translate[refresh_btn] = "รีเฟรช (Refresh)"
        refresh_btn.clicked.connect(self.refresh_logs)
        layout.addWidget(refresh_btn)
        
        # Load initial log file after log_text is created
        if self.log_radio_buttons:
            first_button = list(self.log_radio_buttons.values())[0]
            first_button.setChecked(True)
            QTimer.singleShot(0, lambda: self.load_log_file(first_button.log_path))
        
        # Start auto-refresh timer (refresh every 500ms like terminal)
        self.log_refresh_timer.start(500)
        
        return widget
    
    def apply_dark_theme(self):
        """Apply dark mode + dark red theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QFrame {
                background-color: #2b2b2b;
                border-radius: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
            QCheckBox, QRadioButton {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555;
                border-radius: 3px;
                background-color: #2b2b2b;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {
                border-color: #c41e3a;
            }
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
            QPushButton:pressed {
                background-color: #a01a2e;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #c41e3a;
                border-radius: 3px;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
    
    def on_demo_selected(self, checked):
        if checked:
            sender = self.sender()
            if sender == self.radio_demo1:
                self.demo_video = os.path.join(PROJECT_ROOT, "demos", "demo1.mp4")
                self.video_path = None
            elif sender == self.radio_demo2:
                self.demo_video = os.path.join(PROJECT_ROOT, "demos", "demo2.mp4")
                self.video_path = None
            
            if os.path.exists(self.demo_video):
                self.selected_video_label.setText("")
                self.preview_video.load_video(self.demo_video)
                self.btn_start.setEnabled(True)
            else:
                self.selected_video_label.setText(t("ไม่พบไฟล์วิดีโอ", "Video file not found"))
                self.btn_start.setEnabled(False)
    
    def browse_video(self):
        select_video_title = t("เลือกไฟล์วิดีโอ", "Select Video File")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            select_video_title,
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.m4v *.3gp);;All Files (*)"
        )
        
        if file_path:
            self.video_path = file_path
            self.demo_video = None
            self.radio_demo1.setChecked(False)
            self.radio_demo2.setChecked(False)
            
            self.selected_video_label.setText(f"{t('ไฟล์ที่เลือก:', 'Selected file:')} {os.path.basename(file_path)}")
            self.preview_video.load_video(file_path)
            self.btn_start.setEnabled(True)
    
    def get_selected_classes(self):
        """Get list of class IDs based on selected checkboxes"""
        classes = []
        # ball: 0, goalkeeper: 1, player: 2, referee: 3, stats: 4
        if self.checkbox_ball.isChecked():
            classes.append(0)
        if self.checkbox_goalkeepers.isChecked():
            classes.append(1)
        if self.checkbox_players.isChecked():
            classes.append(2)
        if self.checkbox_referees.isChecked():
            classes.append(3)
        if self.checkbox_stats.isChecked():
            classes.append(4)
        return classes
    
    def start_analysis(self):
        # Get video path
        video_to_process = self.video_path if self.video_path else self.demo_video
        
        if not video_to_process or not os.path.exists(video_to_process):
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), t("กรุณาเลือกวิดีโอก่อนเริ่มวิเคราะห์", "Please select video before starting analysis"))
            return
        
        classes = self.get_selected_classes()
        if not classes:
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), t("กรุณาเลือกอย่างน้อย 1 ตัวเลือกการแสดงผล", "Please select at least 1 display option"))
            return
        
        # Disable button and show progress
        self.btn_start.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(t("กำลังประมวลผล...", "Processing..."))
        self.status_label.setStyleSheet("color: #c41e3a; font-weight: bold;")
        
        # Start processing in separate thread
        self.processing_thread = VideoProcessingThread(video_to_process, classes, verbose=True)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.progress.connect(self.update_status)
        self.processing_thread.start()
    
    def update_status(self, message):
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #c41e3a; font-weight: bold;")
    
    def on_processing_finished(self, success, output_path):
        self.progress_bar.setVisible(False)
        self.btn_start.setEnabled(True)
        
        if success:
            self.processed = True
            self.status_label.setText("✓ ประมวลผลเสร็จสิ้น!")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # Store tracking data from processing thread
            if self.processing_thread and self.processing_thread.tracks:
                self.tracks = self.processing_thread.tracks
                self.video_frames = self.processing_thread.frames
                self.video_fps = self.processing_thread.fps if hasattr(self.processing_thread, 'fps') else 30
                # Update heat maps in AI Results tab
                self.update_heat_maps()
                # Update statistics in AI Results tab
                self.update_statistics()
                # Update movement analysis in AI Results tab
                self.update_movement_analysis()
            
            # Update results tab with actual output path
            if output_path and os.path.exists(output_path):
                self.result_video_player.load_video(output_path)
                self.btn_open_output.setEnabled(True)
                self.current_output_path = output_path
                # Switch to results tab
                self.tabs.setCurrentIndex(2)  # Video Preview tab
            else:
                # Fallback to old path
                output_path = os.path.join(PROJECT_ROOT, "output", "output.mp4")
                if os.path.exists(output_path):
                    self.result_video_player.load_video(output_path)
                    self.btn_open_output.setEnabled(True)
                    self.current_output_path = output_path
            
            QMessageBox.information(self, t("สำเร็จ", "Success"), t("การประมวลผลวิดีโอเสร็จสิ้นแล้ว!\nกรุณาไปที่แท็บ Video Preview หรือ AI Results เพื่อดูผลลัพธ์", "Video processing completed!\nPlease go to Video Preview or AI Results tab to view results"))
        else:
            self.status_label.setText("✗ เกิดข้อผิดพลาดในการประมวลผล")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            QMessageBox.critical(self, t("ข้อผิดพลาด", "Error"), t("เกิดข้อผิดพลาดในการประมวลผลวิดีโอ\nกรุณาลองใหม่อีกครั้ง", "Error occurred during video processing\nPlease try again"))
    
    def open_video_file(self):
        """Open video file dialog and load selected video in player"""
        output_folder = os.path.join(PROJECT_ROOT, "output")
        
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)
        
        # Video file filter - support common video formats
        video_filter = (
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.mpeg *.mpg *.m4v *.3gp);;"
            "MP4 Files (*.mp4);;"
            "AVI Files (*.avi);;"
            "MOV Files (*.mov);;"
            "MKV Files (*.mkv);;"
            "WebM Files (*.webm);;"
            "All Files (*.*)"
        )
        
        select_video_title = t("เลือกไฟล์วิดีโอ", "Select Video File")
        video_path, _ = QFileDialog.getOpenFileName(
            self,
            select_video_title,
            output_folder,
            video_filter
        )
        
        if video_path and os.path.exists(video_path):
            # Load video in the result video player
            self.result_video_player.load_video(video_path)
            self.current_output_path = video_path
        elif video_path:
            QMessageBox.warning(self, t("ไม่พบไฟล์", "File Not Found"), f"{t('ไม่พบไฟล์วิดีโอ:', 'Video file not found:')} {video_path}")
    
    def open_output_folder(self):
        output_folder = os.path.join(PROJECT_ROOT, "output")
        if os.path.exists(output_folder):
            if sys.platform == "win32":
                os.startfile(output_folder)
            elif sys.platform == "darwin":
                os.system(f"open {output_folder}")
            else:
                os.system(f"xdg-open {output_folder}")
        else:
            QMessageBox.warning(self, t("ไม่พบโฟลเดอร์", "Folder Not Found"), t("ไม่พบโฟลเดอร์ผลลัพธ์", "Output folder not found"))
    
    def load_log_file(self, log_path):
        try:
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.log_text.setPlainText(content)
                # Scroll to bottom
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.log_text.setTextCursor(cursor)
                # Store current log path for auto-refresh
                self.current_log_path = log_path
            else:
                self.log_text.setPlainText(f"ไม่พบไฟล์: {log_path}")
                self.current_log_path = log_path
        except Exception as e:
            self.log_text.setPlainText(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {str(e)}")
            self.current_log_path = log_path
    
    def refresh_logs(self):
        for radio in self.log_radio_buttons.values():
            if radio.isChecked():
                self.load_log_file(radio.log_path)
                break
    
    def auto_refresh_logs(self):
        """Auto-refresh the currently displayed log file (called by timer)"""
        if self.current_log_path:
            try:
                if os.path.exists(self.current_log_path):
                    with open(self.current_log_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Only update if content changed to avoid unnecessary UI updates
                    current_content = self.log_text.toPlainText()
                    if content != current_content:
                        self.log_text.setPlainText(content)
                        # Scroll to bottom
                        cursor = self.log_text.textCursor()
                        cursor.movePosition(cursor.MoveOperation.End)
                        self.log_text.setTextCursor(cursor)
            except Exception:
                pass  # Silently ignore errors during auto-refresh
    
    def create_mode_selection_tab(self):
        """Create beautiful landing page with logo and animated welcome message"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        
        # Get DPI scaling factor for responsive sizing
        app = QApplication.instance()
        dpi_scale = 1.0
        if app:
            try:
                # Get device pixel ratio (handles 100%, 125%, 150% scaling)
                dpi_scale = app.devicePixelRatio()
                # Normalize to reasonable scale (1.0, 1.25, 1.5)
                if dpi_scale > 1.5:
                    dpi_scale = 1.5
                elif dpi_scale > 1.25:
                    dpi_scale = 1.25
                else:
                    dpi_scale = 1.0
            except:
                dpi_scale = 1.0
        
        # Base sizes (for 100% scaling)
        base_logo_size = int(700 * dpi_scale)  # Increased from 500 to 700
        base_font_info = int(10 * dpi_scale)
        
        # Main layout
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(int(40 * dpi_scale), int(30 * dpi_scale), 
                                       int(40 * dpi_scale), int(30 * dpi_scale))
        main_layout.setSpacing(int(30 * dpi_scale))
        
        # ========== LOGO SECTION (Top) - Main Brand Identity ==========
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        logo_label = QLabel()
        
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Scale logo larger - using as main brand identity
            pixmap = pixmap.scaled(base_logo_size, base_logo_size, 
                                  Qt.AspectRatioMode.KeepAspectRatio, 
                                  Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        else:
            # Fallback if logo not found
            logo_label.setText("FREE Football Analysis")
            logo_label.setStyleSheet(f"color: #ffffff; font-size: {int(72 * dpi_scale)}pt; font-weight: bold;")
        
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                padding: {int(20 * dpi_scale)}px;
            }}
        """)
        main_layout.addWidget(logo_label)
        
        # ========== INFORMATION SECTION ==========
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(139, 21, 56, 0.1);
                border: 1px solid rgba(139, 21, 56, 0.3);
                border-radius: {int(12 * dpi_scale)}px;
                padding: {int(20 * dpi_scale)}px;
            }}
        """)
        # Set size policy to not expand
        info_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(int(25 * dpi_scale), int(20 * dpi_scale), 
                                      int(25 * dpi_scale), int(20 * dpi_scale))
        info_layout.setSpacing(int(15 * dpi_scale))
        
        # Version Information
        version_section = QHBoxLayout()
        version_label_text = t("เวอร์ชัน:", "Version:")
        version_label = QLabel(version_label_text)
        version_label.setStyleSheet(f"color: #8b1538; font-size: {base_font_info}pt; font-weight: bold; min-width: {int(80 * dpi_scale)}px;")
        self.ui_elements_to_translate[version_label] = ("เวอร์ชัน:", "Version:")
        version_section.addWidget(version_label)
        
        version_value = QLabel("1.0.0")
        version_value.setStyleSheet(f"color: #ffffff; font-size: {base_font_info}pt;")
        version_section.addWidget(version_value)
        
        # Language toggle button - placed between version and build
        current_lang = self.translation_manager.get_language()
        # Create language button with clear label and globe icon
        lang_label_th = "ภาษา:"
        lang_label_en = "Language:"
        lang_label = t(lang_label_th, lang_label_en)
        lang_display = "ไทย" if current_lang == "TH" else "English"
        self.language_btn = QPushButton(f"🌐 {lang_label} {lang_display}")
        self.language_btn.setCheckable(True)
        self.language_btn.setChecked(current_lang == "TH")
        
        # Add tooltip to explain the button
        tooltip_th = "คลิกเพื่อเปลี่ยนภาษา (Click to change language)"
        tooltip_en = "Click to change language (คลิกเพื่อเปลี่ยนภาษา)"
        tooltip_text = t(tooltip_th, tooltip_en)
        self.language_btn.setToolTip(tooltip_text)
        
        self.language_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #8b1538;
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.2);
                padding: {int(6 * dpi_scale)}px {int(16 * dpi_scale)}px;
                border-radius: {int(6 * dpi_scale)}px;
                font-size: {base_font_info}pt;
                font-weight: bold;
                min-width: {int(120 * dpi_scale)}px;
            }}
            QPushButton:hover {{
                background-color: #a01a42;
                border: 2px solid rgba(255, 255, 255, 0.4);
                transform: scale(1.05);
            }}
            QPushButton:checked {{
                background-color: #c41e3a;
                border: 2px solid rgba(255, 255, 255, 0.6);
            }}
        """)
        self.language_btn.clicked.connect(self.toggle_language)
        version_section.addWidget(self.language_btn)
        
        version_section.addStretch()
        
        build_label_text = t("Build:", "Build:")
        build_label = QLabel(build_label_text)
        build_label.setStyleSheet(f"color: #8b1538; font-size: {base_font_info}pt; font-weight: bold; min-width: {int(60 * dpi_scale)}px;")
        self.ui_elements_to_translate[build_label] = ("Build:", "Build:")
        version_section.addWidget(build_label)
        
        build_value = QLabel("2025.12")
        build_value.setStyleSheet(f"color: #ffffff; font-size: {base_font_info}pt;")
        version_section.addWidget(build_value)
        
        info_layout.addLayout(version_section)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setStyleSheet("background-color: rgba(139, 21, 56, 0.3); max-height: 1px;")
        info_layout.addWidget(separator1)
        
        # Developer Information - All in one line with beautiful styling
        developer_section = QHBoxLayout()
        developer_section.setSpacing(int(10 * dpi_scale))
        
        developer_label_text = t("ผู้พัฒนา:", "Developer:")
        developer_label = QLabel(developer_label_text)
        developer_label.setStyleSheet(f"color: #8b1538; font-size: {base_font_info}pt; font-weight: bold; min-width: {int(80 * dpi_scale)}px;")
        self.ui_elements_to_translate[developer_label] = ("ผู้พัฒนา:", "Developer:")
        developer_section.addWidget(developer_label)
        
        # Developer Name
        developer_name_text = t("นายพัชระ อัลอุมารี", "Mr.Patchara Al-umaree")
        developer_name = QLabel(developer_name_text)
        developer_name.setStyleSheet(f"color: #ffffff; font-size: {base_font_info}pt;")
        self.ui_elements_to_translate[developer_name] = ("นายพัชระ อัลอุมารี", "Mr.Patchara Al-umaree")
        developer_section.addWidget(developer_name)
        
        # Separator
        separator_dev = QLabel("|")
        separator_dev.setStyleSheet(f"color: rgba(139, 21, 56, 0.5); font-size: {base_font_info}pt; padding: 0 {int(10 * dpi_scale)}px;")
        developer_section.addWidget(separator_dev)
        
        # Email - styled beautifully
        email_value = QLabel("Email : Patcharaalumaree@gmail.com")
        email_value.setStyleSheet(f"""
            color: #ffffff; 
            font-size: {base_font_info}pt;
            padding: {int(2 * dpi_scale)}px {int(8 * dpi_scale)}px;
            background-color: rgba(139, 21, 56, 0.15);
            border-radius: {int(4 * dpi_scale)}px;
        """)
        developer_section.addWidget(email_value)
        
        # Separator
        separator_email = QLabel("|")
        separator_email.setStyleSheet(f"color: rgba(139, 21, 56, 0.5); font-size: {base_font_info}pt; padding: 0 {int(10 * dpi_scale)}px;")
        developer_section.addWidget(separator_email)
        
        # GitHub Link - styled beautifully
        github_link = QLabel('<a href="https://github.com/MrPatchara" style="color: #8b1538; text-decoration: none; font-weight: bold;">GitHub</a>')
        github_link.setStyleSheet(f"""
            color: #8b1538; 
            font-size: {base_font_info}pt;
            padding: {int(2 * dpi_scale)}px {int(8 * dpi_scale)}px;
            background-color: rgba(139, 21, 56, 0.15);
            border-radius: {int(4 * dpi_scale)}px;
        """)
        github_link.setOpenExternalLinks(True)
        github_link.setTextFormat(Qt.TextFormat.RichText)
        developer_section.addWidget(github_link)
        
        developer_section.addStretch()
        info_layout.addLayout(developer_section)
        
        # Center the info frame
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addStretch()
        center_layout.addWidget(info_frame)
        center_layout.addStretch()
        
        main_layout.addWidget(center_container)
        
        main_layout.addStretch()
        
        return widget
    
    def toggle_language(self):
        """Toggle between TH and EN languages"""
        current_lang = self.translation_manager.get_language()
        new_lang = "EN" if current_lang == "TH" else "TH"
        self.translation_manager.set_language(new_lang)
        
        # Update button text with language label and display name
        lang_label_th = "ภาษา:"
        lang_label_en = "Language:"
        lang_label = t(lang_label_th, lang_label_en)
        lang_display = "ไทย" if new_lang == "TH" else "English"
        self.language_btn.setText(f"🌐 {lang_label} {lang_display}")
        self.language_btn.setChecked(new_lang == "TH")
        
        # Update tooltip
        tooltip_th = "คลิกเพื่อเปลี่ยนภาษา (Click to change language)"
        tooltip_en = "Click to change language (คลิกเพื่อเปลี่ยนภาษา)"
        tooltip_text = t(tooltip_th, tooltip_en)
        self.language_btn.setToolTip(tooltip_text)
        
        # Refresh all UI text
        self.refresh_ui_text()
    
    def refresh_ui_text(self):
        """Refresh all UI text with current language"""
        # Update window title
        self.setWindowTitle(t("FREE - Football Analysis", "FREE - Football Analysis"))
        
        # Update tab names
        if hasattr(self, 'tabs'):
            tab_map = {
                "Info": t("Info", "Info"),
                "AI - Tracking": t("AI - Tracking", "AI - Tracking"),
                "Video Preview": t("Video Preview", "Video Preview"),
                "AI - Results": t("AI - Results", "AI - Results"),
                "Manual Tracking": t("Manual Tracking", "Manual Tracking"),
                "Logs": t("Logs", "Logs")
            }
            # Reverse map for finding original
            reverse_map = {v: k for k, v in tab_map.items()}
            for i in range(self.tabs.count()):
                current = self.tabs.tabText(i)
                # Check if current is already translated, find original
                if current in reverse_map:
                    orig = reverse_map[current]
                    self.tabs.setTabText(i, tab_map[orig])
                elif current in tab_map:
                    self.tabs.setTabText(i, tab_map[current])
        
        # Update all stored UI elements
        if hasattr(self, 'ui_elements_to_translate'):
            for element, original_text in self.ui_elements_to_translate.items():
                if element:
                    try:
                        # Handle tuple (thai_text, english_text) or string
                        if isinstance(original_text, tuple):
                            thai_text, english_text = original_text
                            # Get current language to determine which text to use
                            current_lang = self.translation_manager.get_language()
                            if current_lang == "EN":
                                translated = english_text
                            else:
                                translated = thai_text
                        else:
                            # Get the correct translation - use original_text as key
                            translated = t(original_text, original_text)
                        
                        # Apply translation based on element type
                        if hasattr(element, 'setText'):
                            element.setText(translated)
                        if hasattr(element, 'setTitle'):
                            element.setTitle(translated)
                        if hasattr(element, 'setPlaceholderText'):
                            element.setPlaceholderText(translated)
                        if hasattr(element, 'setToolTip'):
                            element.setToolTip(translated)
                    except Exception as e:
                        print(f"Error updating UI element {element}: {e}")
                        pass
        
        # Update event buttons
        if hasattr(self, 'event_buttons_translation'):
            for btn, event_name in self.event_buttons_translation.items():
                if btn and hasattr(btn, 'setText'):
                    translated = t(event_name, event_name)
                    btn.setText(translated)
        
        # Update table headers
        if hasattr(self, 'events_table'):
            headers = [
                t("เวลา", "Time"), t("เหตุการณ์", "Event"), t("ผลลัพธ์", "Outcome"),
                t("ทีม", "Team"), t("ครึ่ง", "Half"), t("ผู้เล่น", "Player"), t("การจัดการ", "Management")
            ]
            self.events_table.setHorizontalHeaderLabels(headers)
        
        # Update combo boxes
        if hasattr(self, 'half_combo'):
            self.half_combo.clear()
            self.half_combo.addItems([
                t("ครึ่งแรก", "First Half"), t("ครึ่งหลัง", "Second Half"),
                t("ต่อเวลาครึ่งแรก", "Extra Time First Half"), t("ต่อเวลาครึ่งหลัง", "Extra Time Second Half")
            ])
        
        if hasattr(self, 'team_combo'):
            # Get current team names from inputs if available, otherwise use defaults
            if hasattr(self, 'team1_input') and hasattr(self, 'team2_input'):
                team1_name = self.team1_input.text() if self.team1_input.text() else t("ทีม 1", "Team 1")
                team2_name = self.team2_input.text() if self.team2_input.text() else t("ทีม 2", "Team 2")
            else:
                team1_name = t("ทีม 1", "Team 1")
                team2_name = t("ทีม 2", "Team 2")
            current_index = self.team_combo.currentIndex()
            self.team_combo.clear()
            self.team_combo.addItems([team1_name, team2_name])
            # Restore selection if valid
            if 0 <= current_index < 2:
                self.team_combo.setCurrentIndex(current_index)
        
        # Update placeholder texts
        if hasattr(self, 'team1_input'):
            if hasattr(self, 'team1_input_placeholder_text'):
                placeholder = t(self.team1_input_placeholder_text[0], self.team1_input_placeholder_text[1])
                self.team1_input.setPlaceholderText(placeholder)
        if hasattr(self, 'team2_input'):
            if hasattr(self, 'team2_input_placeholder_text'):
                placeholder = t(self.team2_input_placeholder_text[0], self.team2_input_placeholder_text[1])
                self.team2_input.setPlaceholderText(placeholder)
        
        # Update AI Results sub-tabs
        if hasattr(self, 'ai_results_subtabs_widget') and hasattr(self, 'ai_results_subtabs'):
            sub_tabs = self.ai_results_subtabs_widget
            for idx, (orig_name, _) in self.ai_results_subtabs.items():
                if idx < sub_tabs.count():
                    translated_name = t(orig_name, orig_name)
                    sub_tabs.setTabText(idx, translated_name)
        
        # Update heat map radio buttons
        if hasattr(self, 'radio_all_players'):
            self.radio_all_players.setText(t("ผู้เล่นทั้งหมด", "All Players"))
        if hasattr(self, 'radio_team1'):
            self.radio_team1.setText(t("ทีม 1", "Team 1"))
        if hasattr(self, 'radio_team2'):
            self.radio_team2.setText(t("ทีม 2", "Team 2"))
        if hasattr(self, 'radio_ball'):
            self.radio_ball.setText(t("ลูกบอล", "Ball"))
        
        # Update movement analysis radio buttons
        if hasattr(self, 'radio_movement_paths'):
            self.radio_movement_paths.setText(t("เส้นทางการเคลื่อนที่", "Movement Paths"))
        if hasattr(self, 'radio_speed_zones'):
            self.radio_speed_zones.setText(t("Speed Zones (พื้นที่ความเร็วสูง)", "Speed Zones (High Speed Areas)"))
        if hasattr(self, 'radio_speed_chart'):
            self.radio_speed_chart.setText(t("กราฟความเร็ว", "Speed Chart"))
        if hasattr(self, 'radio_movement_stats'):
            self.radio_movement_stats.setText(t("สถิติการเคลื่อนไหว", "Movement Statistics"))
        if hasattr(self, 'radio_movement_all'):
            self.radio_movement_all.setText(t("ผู้เล่นทั้งหมด", "All Players"))
        if hasattr(self, 'radio_movement_team1'):
            self.radio_movement_team1.setText(t("ทีม 1", "Team 1"))
        if hasattr(self, 'radio_movement_team2'):
            self.radio_movement_team2.setText(t("ทีม 2", "Team 2"))
        
        # Update log radio buttons
        if hasattr(self, 'log_radio_buttons_translation'):
            for radio, original_name in self.log_radio_buttons_translation.items():
                if radio:
                    translated = t(original_name, original_name)
                    radio.setText(translated)
        
        # Update manual help button tooltip
        if hasattr(self, 'manual_help_btn') and hasattr(self, 'manual_help_btn_tooltip_text'):
            tooltip = t(self.manual_help_btn_tooltip_text[0], self.manual_help_btn_tooltip_text[1])
            self.manual_help_btn.setToolTip(tooltip)
    
    def switch_mode(self, mode: str):
        """Switch between AI and Manual mode"""
        self.current_mode = mode
        if mode == "AI":
            # Switch to AI Usage tab
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "AI - Usage":
                    self.tabs.setCurrentIndex(i)
                    break
        else:
            # Switch to Manual Tracking tab
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Manual Tracking":
                    self.tabs.setCurrentIndex(i)
                    break
    
    def create_manual_tracking_tab(self):
        """Create manual tracking tab (Manual Tracking)"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Top section: Video player and Event Tracking side by side
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setChildrenCollapsible(False)
        
        # Left side: Video player
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # Video load section
        video_load_layout = QHBoxLayout()
        # Get current language to set initial text
        current_lang = self.translation_manager.get_language()
        add_video_text_th = "เพิ่มวิดีโอ"
        add_video_text_en = "Add Video"
        add_video_text = add_video_text_en if current_lang == "EN" else add_video_text_th
        self.manual_load_video_btn = QPushButton(add_video_text)
        self.ui_elements_to_translate[self.manual_load_video_btn] = (add_video_text_th, add_video_text_en)
        self.manual_load_video_btn.clicked.connect(self.load_video_for_manual_tracking)
        video_load_layout.addWidget(self.manual_load_video_btn)
        
        # Help button
        help_text_th = "วิธีใช้งาน"
        help_text_en = "How to Use"
        help_tooltip_text_th = "เปิดหน้าต่างช่วยเหลือ"
        help_tooltip_text_en = "Open help window"
        # Get current language to set initial text
        current_lang = self.translation_manager.get_language()
        help_text = help_text_en if current_lang == "EN" else help_text_th
        help_tooltip_text = help_tooltip_text_en if current_lang == "EN" else help_tooltip_text_th
        self.manual_help_btn = QPushButton(help_text)
        self.ui_elements_to_translate[self.manual_help_btn] = (help_text_th, help_text_en)
        self.manual_help_btn.setToolTip(help_tooltip_text)
        # Store tooltip for translation refresh
        if not hasattr(self, 'manual_help_btn_tooltip_text'):
            self.manual_help_btn_tooltip_text = (help_tooltip_text_th, help_tooltip_text_en)
        self.manual_help_btn.setFixedSize(110, 35)
        self.manual_help_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 10pt;
                font-weight: bold;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        self.manual_help_btn.clicked.connect(self.show_manual_tracking_help)
        video_load_layout.addWidget(self.manual_help_btn)
        
        video_load_layout.addStretch()
        left_layout.addLayout(video_load_layout)
        
        # Video player - responsive sizing
        self.manual_video_player = VideoPlayerWidget()
        self.manual_video_player.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Store reference to speed label for translation
        if hasattr(self.manual_video_player, 'speed_label'):
            self.ui_elements_to_translate[self.manual_video_player.speed_label] = ("ความเร็ว:", "Speed:")
        left_layout.addWidget(self.manual_video_player, 1)
        
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        top_splitter.addWidget(left_panel)
        
        # Right side: Event Tracking panel
        right_panel = QWidget()
        right_panel.setMinimumWidth(300)
        right_panel.setMaximumWidth(400)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Event buttons panel
        events_group_text_th = "Event Tracking"
        events_group_text_en = "Event Tracking"
        events_group_text = events_group_text_en if current_lang == "EN" else events_group_text_th
        events_group = QGroupBox(events_group_text)
        self.ui_elements_to_translate[events_group] = (events_group_text_th, events_group_text_en)
        events_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #c41e3a;
            }
        """)
        events_layout = QVBoxLayout()
        
        # Team selection - editable text fields
        team1_layout = QHBoxLayout()
        team1_label_text_th = "ทีม 1:"
        team1_label_text_en = "Team 1:"
        team1_label_text = team1_label_text_en if current_lang == "EN" else team1_label_text_th
        team1_label = QLabel(team1_label_text)
        self.ui_elements_to_translate[team1_label] = (team1_label_text_th, team1_label_text_en)
        team1_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.team1_input = QLineEdit()
        team1_placeholder_th = "กรอกชื่อทีม 1"
        team1_placeholder_en = "Enter Team 1 name"
        team1_placeholder = team1_placeholder_en if current_lang == "EN" else team1_placeholder_th
        self.team1_input.setPlaceholderText(team1_placeholder)
        team1_default_th = "ทีม 1"
        team1_default_en = "Team 1"
        team1_default = team1_default_en if current_lang == "EN" else team1_default_th
        self.team1_input.setText(team1_default)
        # Store placeholder for translation refresh
        if not hasattr(self, 'team1_input_placeholder_text'):
            self.team1_input_placeholder_text = (team1_placeholder_th, team1_placeholder_en)
        self.ui_elements_to_translate[self.team1_input] = self.team1_input_placeholder_text
        self.team1_input.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus {
                border-color: #c41e3a;
            }
        """)
        team1_layout.addWidget(team1_label)
        team1_layout.addWidget(self.team1_input)
        events_layout.addLayout(team1_layout)
        
        team2_layout = QHBoxLayout()
        team2_label_text_th = "ทีม 2:"
        team2_label_text_en = "Team 2:"
        team2_label_text = team2_label_text_en if current_lang == "EN" else team2_label_text_th
        team2_label = QLabel(team2_label_text)
        team2_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.ui_elements_to_translate[team2_label] = (team2_label_text_th, team2_label_text_en)
        self.team2_input = QLineEdit()
        team2_placeholder_th = "กรอกชื่อทีม 2"
        team2_placeholder_en = "Enter Team 2 name"
        team2_placeholder = team2_placeholder_en if current_lang == "EN" else team2_placeholder_th
        self.team2_input.setPlaceholderText(team2_placeholder)
        team2_default_th = "ทีม 2"
        team2_default_en = "Team 2"
        team2_default = team2_default_en if current_lang == "EN" else team2_default_th
        self.team2_input.setText(team2_default)
        # Store placeholder for translation refresh
        if not hasattr(self, 'team2_input_placeholder_text'):
            self.team2_input_placeholder_text = (team2_placeholder_th, team2_placeholder_en)
        self.ui_elements_to_translate[self.team2_input] = self.team2_input_placeholder_text
        self.team2_input.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus {
                border-color: #c41e3a;
            }
        """)
        team2_layout.addWidget(team2_label)
        team2_layout.addWidget(self.team2_input)
        events_layout.addLayout(team2_layout)
        
        # Player settings buttons
        players_settings_layout = QHBoxLayout()
        team1_players_text_th = "ตั้งค่ารายชื่อทีม 1"
        team1_players_text_en = "Set Team 1 Players"
        team1_players_text = team1_players_text_en if current_lang == "EN" else team1_players_text_th
        self.team1_players_btn = QPushButton(team1_players_text)
        self.ui_elements_to_translate[self.team1_players_btn] = (team1_players_text_th, team1_players_text_en)
        self.team1_players_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.team1_players_btn.clicked.connect(lambda: self.show_players_dialog(1))
        
        team2_players_text_th = "ตั้งค่ารายชื่อทีม 2"
        team2_players_text_en = "Set Team 2 Players"
        team2_players_text = team2_players_text_en if current_lang == "EN" else team2_players_text_th
        self.team2_players_btn = QPushButton(team2_players_text)
        self.ui_elements_to_translate[self.team2_players_btn] = (team2_players_text_th, team2_players_text_en)
        self.team2_players_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.team2_players_btn.clicked.connect(lambda: self.show_players_dialog(2))
        
        players_settings_layout.addWidget(self.team1_players_btn)
        players_settings_layout.addWidget(self.team2_players_btn)
        events_layout.addLayout(players_settings_layout)
        
        # Team and Half selection in one row
        team_half_layout = QHBoxLayout()
        
        # Team selection
        team_select_label_text_th = "เลือกทีม:"
        team_select_label_text_en = "Select Team:"
        team_select_label_text = team_select_label_text_en if current_lang == "EN" else team_select_label_text_th
        team_select_label = QLabel(team_select_label_text)
        self.ui_elements_to_translate[team_select_label] = (team_select_label_text_th, team_select_label_text_en)
        team_select_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.team_combo = QComboBox()
        team1_combo_th = "ทีม 1"
        team1_combo_en = "Team 1"
        team2_combo_th = "ทีม 2"
        team2_combo_en = "Team 2"
        team1_combo = team1_combo_en if current_lang == "EN" else team1_combo_th
        team2_combo = team2_combo_en if current_lang == "EN" else team2_combo_th
        self.team_combo.addItems([team1_combo, team2_combo])
        self.team_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox:hover {
                border-color: #c41e3a;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #e0e0e0;
                selection-background-color: #c41e3a;
            }
        """)
        # Update team combo when team names change
        self.team1_input.textChanged.connect(self.update_team_combo)
        self.team2_input.textChanged.connect(self.update_team_combo)
        
        # Half selection
        half_label_text_th = "ครึ่ง:"
        half_label_text_en = "Half:"
        half_label_text = half_label_text_en if current_lang == "EN" else half_label_text_th
        half_label = QLabel(half_label_text)
        self.ui_elements_to_translate[half_label] = (half_label_text_th, half_label_text_en)
        half_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        self.half_combo = QComboBox()
        half1_th = "ครึ่งแรก"
        half1_en = "First Half"
        half2_th = "ครึ่งหลัง"
        half2_en = "Second Half"
        half3_th = "ต่อเวลาครึ่งแรก"
        half3_en = "Extra Time First Half"
        half4_th = "ต่อเวลาครึ่งหลัง"
        half4_en = "Extra Time Second Half"
        half1 = half1_en if current_lang == "EN" else half1_th
        half2 = half2_en if current_lang == "EN" else half2_th
        half3 = half3_en if current_lang == "EN" else half3_th
        half4 = half4_en if current_lang == "EN" else half4_th
        self.half_combo.addItems([half1, half2, half3, half4])
        self.half_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #c41e3a;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #e0e0e0;
                selection-background-color: #c41e3a;
            }
        """)
        
        team_half_layout.addWidget(team_select_label)
        team_half_layout.addWidget(self.team_combo)
        team_half_layout.addSpacing(20)
        team_half_layout.addWidget(half_label)
        team_half_layout.addWidget(self.half_combo)
        team_half_layout.addStretch()
        events_layout.addLayout(team_half_layout)
        
        # Customize button
        customize_layout = QHBoxLayout()
        customize_text_th = "ปรับแต่งปุ่ม"
        customize_text_en = "Customize Buttons"
        customize_text = customize_text_en if current_lang == "EN" else customize_text_th
        self.customize_events_btn = QPushButton(customize_text)
        self.ui_elements_to_translate[self.customize_events_btn] = (customize_text_th, customize_text_en)
        self.customize_events_btn.clicked.connect(self.show_customize_events_dialog)
        customize_layout.addWidget(self.customize_events_btn)
        customize_layout.addStretch()
        events_layout.addLayout(customize_layout)
        
        # Event buttons grid - use grid layout for compact buttons
        events_grid = QWidget()
        grid_layout = QVBoxLayout(events_grid)
        grid_layout.setSpacing(5)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create button rows (2 columns)
        self.event_buttons = {}
        self.event_outcomes = {}  # Store outcomes for each event type
        row_layout = None
        for idx, event_data in enumerate(self.default_event_types):
            if len(event_data) == 3:
                event_name, color, outcomes = event_data
            else:
                # Backward compatibility
                event_name, color = event_data[:2]
                outcomes = []
            
            self.event_outcomes[event_name] = outcomes
            
            if idx % 2 == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(5)
                grid_layout.addLayout(row_layout)
            
            # Translate event name for button
            translated_event_name = t(event_name, event_name)
            btn = QPushButton(translated_event_name)
            btn.setMinimumSize(120, 40)
            btn.setMaximumSize(120, 40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 10pt;
                    border: 2px solid {color};
                }}
                QPushButton:hover {{
                    background-color: {color}dd;
                    border-color: white;
                }}
                QPushButton:pressed {{
                    background-color: {color}aa;
                }}
            """)
            btn.clicked.connect(lambda checked, e=event_name: self.on_event_button_clicked(e))
            btn.setVisible(event_name in self.enabled_events)
            row_layout.addWidget(btn)
            self.event_buttons[event_name] = btn
            # Store for translation refresh
            if not hasattr(self, 'event_buttons_translation'):
                self.event_buttons_translation = {}
            self.event_buttons_translation[btn] = event_name
        
        # Add stretch to fill remaining space
        grid_layout.addStretch()
        
        events_layout.addWidget(events_grid)
        events_group.setLayout(events_layout)
        right_layout.addWidget(events_group, 1)  # Make it expand
        
        top_splitter.addWidget(right_panel)
        
        # Set splitter sizes (70% video, 30% events)
        top_splitter.setSizes([700, 300])
        main_layout.addWidget(top_splitter, 1)  # Make top section expand
        
        # Bottom section: Event List (scrollable)
        events_list_text_th = "Event List"
        events_list_text_en = "Event List"
        events_list_text = events_list_text_en if current_lang == "EN" else events_list_text_th
        events_list_group = QGroupBox(events_list_text)
        self.ui_elements_to_translate[events_list_group] = (events_list_text_th, events_list_text_en)
        events_list_group.setStyleSheet(events_group.styleSheet())
        events_list_group.setFixedHeight(300)  # Fixed height to match with Event Tracking
        events_list_layout = QVBoxLayout()
        
        # Event table with scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c41e3a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #d63347;
            }
        """)
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(7)
        time_header_th = "เวลา"
        time_header_en = "Time"
        event_header_th = "เหตุการณ์"
        event_header_en = "Event"
        outcome_header_th = "ผลลัพธ์"
        outcome_header_en = "Outcome"
        team_header_th = "ทีม"
        team_header_en = "Team"
        half_header_th = "ครึ่ง"
        half_header_en = "Half"
        player_header_th = "ผู้เล่น"
        player_header_en = "Player"
        management_header_th = "การจัดการ"
        management_header_en = "Management"
        table_headers = [
            time_header_en if current_lang == "EN" else time_header_th,
            event_header_en if current_lang == "EN" else event_header_th,
            outcome_header_en if current_lang == "EN" else outcome_header_th,
            team_header_en if current_lang == "EN" else team_header_th,
            half_header_en if current_lang == "EN" else half_header_th,
            player_header_en if current_lang == "EN" else player_header_th,
            management_header_en if current_lang == "EN" else management_header_th
        ]
        self.events_table.setHorizontalHeaderLabels(table_headers)
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.events_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #555;
                gridline-color: #555;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #c41e3a;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #c41e3a;
                padding: 8px;
                border: 1px solid #555;
                font-weight: bold;
            }
        """)
        # Enable double-click to jump to timestamp
        self.events_table.itemDoubleClicked.connect(self.on_event_double_clicked)
        scroll_area.setWidget(self.events_table)
        events_list_layout.addWidget(scroll_area)
        
        # Buttons for event list
        event_buttons_layout = QHBoxLayout()
        delete_selected_text_th = "ลบที่เลือก"
        delete_selected_text_en = "Delete Selected"
        delete_selected_text = delete_selected_text_en if current_lang == "EN" else delete_selected_text_th
        self.delete_event_btn = QPushButton(delete_selected_text)
        self.ui_elements_to_translate[self.delete_event_btn] = (delete_selected_text_th, delete_selected_text_en)
        self.delete_event_btn.clicked.connect(self.delete_selected_event)
        event_buttons_layout.addWidget(self.delete_event_btn)
        
        clear_all_text_th = "ลบทั้งหมด"
        clear_all_text_en = "Clear All"
        clear_all_text = clear_all_text_en if current_lang == "EN" else clear_all_text_th
        self.clear_events_btn = QPushButton(clear_all_text)
        self.ui_elements_to_translate[self.clear_events_btn] = (clear_all_text_th, clear_all_text_en)
        self.clear_events_btn.clicked.connect(self.clear_all_events)
        event_buttons_layout.addWidget(self.clear_events_btn)
        
        export_csv_text_th = "ส่งออก CSV"
        export_csv_text_en = "Export CSV"
        export_csv_text = export_csv_text_en if current_lang == "EN" else export_csv_text_th
        self.export_btn = QPushButton(export_csv_text)
        self.ui_elements_to_translate[self.export_btn] = (export_csv_text_th, export_csv_text_en)
        self.export_btn.clicked.connect(self.export_tracking_to_csv)
        event_buttons_layout.addWidget(self.export_btn)
        
        events_list_layout.addLayout(event_buttons_layout)
        events_list_group.setLayout(events_list_layout)
        main_layout.addWidget(events_list_group, 1)
        
        return widget
    
    def update_team_combo(self):
        """Update team combo box with current team names"""
        current_selection = self.team_combo.currentText()
        team1_name = self.team1_input.text() if self.team1_input.text() else "ทีม 1"
        team2_name = self.team2_input.text() if self.team2_input.text() else "ทีม 2"
        
        # Update team names in manual_tracking_data
        if self.manual_tracking_data:
            self.manual_tracking_data.team_a_name = team1_name
            self.manual_tracking_data.team_b_name = team2_name
        
        self.team_combo.clear()
        self.team_combo.addItems([team1_name, team2_name])
        
        # Try to restore selection
        if current_selection in [team1_name, "ทีม 1", "Team 1"]:
            self.team_combo.setCurrentIndex(0)
        elif current_selection in [team2_name, "ทีม 2", "Team 2"]:
            self.team_combo.setCurrentIndex(1)
        else:
            # Default to first team if selection not found
            self.team_combo.setCurrentIndex(0)
    
    def on_event_button_clicked(self, event_type: str):
        """Handle event button click - show outcome dialog if needed"""
        outcomes = self.event_outcomes.get(event_type, [])
        
        # Pause video if playing to capture accurate timestamp
        was_playing = False
        if not self.manual_video_player.media_player.source().isEmpty():
            if self.manual_video_player.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                was_playing = True
                self.manual_video_player.media_player.pause()
        
        if len(outcomes) > 1:
            # Show outcome selection dialog
            self.show_outcome_dialog(event_type, outcomes, was_playing)
        else:
            # No outcome needed or only one option
            outcome = outcomes[0] if outcomes else None
            # If outcome is "ประตู", show goal dialog
            if outcome == "ประตู":
                self.show_goal_dialog(event_type, outcome, was_playing)
            else:
                self.add_tracking_event(event_type, outcome)
                # Resume video if it was playing
                if was_playing:
                    self.manual_video_player.media_player.play()
    
    def show_outcome_dialog(self, event_type: str, outcomes: list, was_playing: bool = False):
        """Show dialog to select outcome"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{t('เลือกผลลัพธ์ -', 'Select outcome for:')} {t(event_type, event_type)}")
        dialog.setMinimumSize(300, 200)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        title = QLabel(f"{t('เลือกผลลัพธ์สำหรับ:', 'Select outcome for:')} {t(event_type, event_type)}")
        title.setStyleSheet("font-weight: bold; font-size: 12pt; color: #c41e3a; margin-bottom: 15px;")
        layout.addWidget(title)
        
        # Create outcome buttons
        outcome_buttons = []
        for outcome in outcomes:
            btn = QPushButton(t(outcome, outcome))
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #e0e0e0;
                    border: 2px solid #555;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c41e3a;
                    border-color: #c41e3a;
                }
            """)
            btn.clicked.connect(lambda checked, o=outcome: self.on_outcome_selected(event_type, o, dialog, was_playing))
            layout.addWidget(btn)
            outcome_buttons.append(btn)
        
        # Cancel button
        cancel_btn = QPushButton(t("ยกเลิก", "Cancel"))
        cancel_btn.clicked.connect(lambda: self.on_outcome_cancelled(dialog, was_playing))
        layout.addWidget(cancel_btn)
        
        dialog.exec()
    
    def on_outcome_selected(self, event_type: str, outcome: str, dialog: QDialog, was_playing: bool = False):
        """Handle outcome selection"""
        dialog.accept()
        
        # If outcome is "ประตู", always show goal dialog
        if outcome == "ประตู":
            self.show_goal_dialog(event_type, outcome, was_playing)
        else:
            self.add_tracking_event(event_type, outcome)
            # Resume video if it was playing
            if was_playing:
                self.manual_video_player.media_player.play()
    
    def on_outcome_cancelled(self, dialog: QDialog, was_playing: bool = False):
        """Handle outcome dialog cancellation"""
        dialog.reject()
        # Resume video if it was playing
        if was_playing:
            self.manual_video_player.media_player.play()
    
    def show_players_dialog(self, team_num: int):
        """Show dialog to input players for a team with name, surname, and position"""
        dialog = QDialog(self)
        set_players_title = t(f"ตั้งค่ารายชื่อทีม {team_num}", f"Set Team {team_num} Players")
        dialog.setWindowTitle(set_players_title)
        dialog.setMinimumSize(600, 500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QTableWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                gridline-color: #444;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #c41e3a;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #e0e0e0;
                padding: 8px;
                border: 1px solid #555;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus {
                border-color: #c41e3a;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        title_text = t(f"กรอกรายชื่อนักเตะทีม {team_num}", f"Enter Team {team_num} Players")
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 14pt; color: #c41e3a; margin-bottom: 10px;")
        layout.addWidget(title)
        
        instruction_text = t("กรอกข้อมูลนักเตะ: ชื่อ, นามสกุล, ตำแหน่ง (สามารถเพิ่มแถวได้โดยกด Enter)", "Enter player information: Name, Surname, Position (Press Enter to add new row)")
        instruction = QLabel(instruction_text)
        instruction.setStyleSheet("color: #b0b0b0; margin-bottom: 10px;")
        layout.addWidget(instruction)
        
        # Create table for players
        players_table = QTableWidget()
        players_table.setColumnCount(3)
        table_headers = [t("ชื่อ", "Name"), t("นามสกุล", "Surname"), t("ตำแหน่ง", "Position")]
        players_table.setHorizontalHeaderLabels(table_headers)
        players_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        players_table.setRowCount(20)  # Start with 20 rows
        
        # Load existing players
        current_players = self.team1_players if team_num == 1 else self.team2_players
        for row, player in enumerate(current_players):
            if row >= 20:
                players_table.setRowCount(row + 1)
            if isinstance(player, dict):
                players_table.setItem(row, 0, QTableWidgetItem(player.get('name', '')))
                players_table.setItem(row, 1, QTableWidgetItem(player.get('surname', '')))
                players_table.setItem(row, 2, QTableWidgetItem(player.get('position', '')))
            else:
                # Backward compatibility: if it's a string, put it in name column
                players_table.setItem(row, 0, QTableWidgetItem(str(player)))
        
        layout.addWidget(players_table)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        add_row_btn = QPushButton(t("เพิ่มแถว", "Add Row"))
        add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_row_btn.clicked.connect(lambda: players_table.setRowCount(players_table.rowCount() + 1))
        buttons_layout.addWidget(add_row_btn)
        buttons_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
        """)
        buttons_layout.addWidget(button_box)
        layout.addLayout(buttons_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            players = []
            for row in range(players_table.rowCount()):
                name_item = players_table.item(row, 0)
                surname_item = players_table.item(row, 1)
                position_item = players_table.item(row, 2)
                
                name = name_item.text().strip() if name_item else ""
                surname = surname_item.text().strip() if surname_item else ""
                position = position_item.text().strip() if position_item else ""
                
                # Only add if at least name is provided
                if name or surname:
                    players.append({
                        'name': name,
                        'surname': surname,
                        'position': position,
                        'full_name': f"{name} {surname}".strip() if name or surname else ""
                    })
            
            if team_num == 1:
                self.team1_players = players
                if self.manual_tracking_data:
                    # Convert to list of full names for backward compatibility
                    self.manual_tracking_data.team_a_players = [p['full_name'] or p['name'] for p in players]
            else:
                self.team2_players = players
                if self.manual_tracking_data:
                    self.manual_tracking_data.team_b_players = [p['full_name'] or p['name'] for p in players]
    
    def show_goal_dialog(self, event_type: str, outcome: str, was_playing: bool = False):
        """Show goal dialog when outcome is 'ประตู' - always show for all goals"""
        if self.manual_video_player.media_player.source().isEmpty():
            QMessageBox.warning(self, t("ไม่มีวิดีโอ", "No Video"), t("กรุณาโหลดวิดีโอก่อนบันทึกประตู", "Please load video before saving goal"))
            if was_playing:
                self.manual_video_player.media_player.play()
            return
        
        # Ensure video is paused while dialog is open
        if was_playing:
            self.manual_video_player.media_player.pause()
        
        dialog = QDialog(self)
        dialog.setWindowTitle(t("บันทึกประตู", "Save Goal"))
        dialog.setMinimumSize(350, 200)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        title = QLabel(t("บันทึกประตู", "Save Goal"))
        title.setStyleSheet("font-weight: bold; font-size: 14pt; color: #c41e3a; margin-bottom: 15px;")
        layout.addWidget(title)
        
        # Team selection
        team_layout = QHBoxLayout()
        team_label = QLabel(t("ทีมที่ได้ประตู:", "Team that scored:"))
        team_label.setStyleSheet("font-weight: bold;")
        team_combo = QComboBox()
        team1_default = t("ทีม 1", "Team 1")
        team2_default = t("ทีม 2", "Team 2")
        team_combo.addItems([self.team1_input.text() or team1_default, self.team2_input.text() or team2_default])
        team_layout.addWidget(team_label)
        team_layout.addWidget(team_combo)
        layout.addLayout(team_layout)
        
        # Player selection (if players are available)
        player_layout = QHBoxLayout()
        player_label = QLabel(t("ผู้ยิงประตู:", "Goal Scorer:"))
        player_label.setStyleSheet("font-weight: bold;")
        player_combo = QComboBox()
        not_specified = t("ไม่ระบุ", "Not Specified")
        player_combo.addItem(not_specified)
        
        def update_player_list(team_index):
            player_combo.clear()
            player_combo.addItem(not_specified)
            players_list = self.team1_players if team_index == 0 else self.team2_players
            for player in players_list:
                if isinstance(player, dict):
                    display_name = player.get('full_name') or player.get('name', '')
                    if display_name:
                        player_combo.addItem(display_name)
                else:
                    # Backward compatibility
                    if player:
                        player_combo.addItem(str(player))
        
        team_combo.currentIndexChanged.connect(update_player_list)
        update_player_list(0)  # Initialize with team 1
        
        player_layout.addWidget(player_label)
        player_layout.addWidget(player_combo)
        layout.addLayout(player_layout)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
        """)
        layout.addWidget(button_box)
        
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            try:
                current_time = self.manual_video_player.media_player.position() / 1000.0
                team_index = team_combo.currentIndex()
                team_name = team_combo.currentText()
                
                half_text = self.half_combo.currentText()
                # Map half selection to numeric value - check both languages
                half_mapping_direct = {
                    "ครึ่งแรก": 1, "First Half": 1,
                    "ครึ่งหลัง": 2, "Second Half": 2,
                    "ต่อเวลาครึ่งแรก": 3, "Extra Time First Half": 3,
                    "ต่อเวลาครึ่งหลัง": 4, "Extra Time Second Half": 4
                }
                half = half_mapping_direct.get(half_text, 1)
                
                player_name = None
                # Check if not "ไม่ระบุ" / "Not Specified" (index 0 is always the "not specified" option)
                if player_combo.currentIndex() > 0:
                    player_name = player_combo.currentText()
                
                if self.manual_tracking_data:
                    event = TrackingEvent(
                        timestamp=current_time,
                        event_type=event_type,
                        team=team_name,
                        outcome=outcome,
                        half=half,
                        player_name=player_name
                    )
                    
                    self.manual_tracking_data.add_event(event)
                    self.update_events_table()
                    
                    # Show confirmation
                    player_info = f" โดย {player_name}" if player_name else ""
                    QMessageBox.information(
                        self, 
                        "บันทึกสำเร็จ", 
                        f"บันทึกประตูของ {team_name}{player_info}\nที่เวลา {int(current_time // 60)}:{int(current_time % 60):02d}"
                    )
            except Exception as e:
                QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), f"{t('ไม่สามารถบันทึกประตูได้:', 'Cannot save goal:')} {str(e)}")
        
        # Resume video if it was playing
        if was_playing:
            self.manual_video_player.media_player.play()
    
    def add_tracking_event(self, event_type: str, outcome: Optional[str] = None):
        """Add a tracking event at current video time"""
        # Check if video is loaded
        if self.manual_video_player.media_player.source().isEmpty():
            no_video_title = t("ไม่มีวิดีโอ", "No Video")
            no_video_msg = t("กรุณาโหลดวิดีโอก่อนเพิ่มเหตุการณ์", "Please load video before adding event")
            QMessageBox.warning(self, no_video_title, no_video_msg)
            return
        
        try:
            current_time = self.manual_video_player.media_player.position() / 1000.0  # Convert to seconds
            team_selection = self.team_combo.currentText()
            # Use the team name directly from combo box (already updated with real names)
            team = team_selection
            
            # Map half selection to numeric value - check both languages
            half_text = self.half_combo.currentText()
            half_mapping_th = {
                t("ครึ่งแรก", "First Half"): 1,
                t("ครึ่งหลัง", "Second Half"): 2,
                t("ต่อเวลาครึ่งแรก", "Extra Time First Half"): 3,
                t("ต่อเวลาครึ่งหลัง", "Extra Time Second Half"): 4
            }
            # Also check direct Thai/English values
            half_mapping_direct = {
                "ครึ่งแรก": 1, "First Half": 1,
                "ครึ่งหลัง": 2, "Second Half": 2,
                "ต่อเวลาครึ่งแรก": 3, "Extra Time First Half": 3,
                "ต่อเวลาครึ่งหลัง": 4, "Extra Time Second Half": 4
            }
            half = half_mapping_direct.get(half_text, half_mapping_th.get(half_text, 1))
            
            if self.manual_tracking_data:
                event = TrackingEvent(
                    timestamp=current_time,
                    event_type=event_type,
                    team=team,
                    outcome=outcome,
                    half=half
                )
                
                self.manual_tracking_data.add_event(event)
                self.update_events_table()
        except Exception as e:
            QMessageBox.warning(self, t("ข้อผิดพลาด", "Error"), f"{t('ไม่สามารถเพิ่มเหตุการณ์ได้:', 'Cannot add event:')} {str(e)}")
    
    def update_events_table(self):
        """Update the events table"""
        if not self.manual_tracking_data:
            return
        
        # Get current language for translation
        current_lang = self.translation_manager.get_language()
        
        self.events_table.setRowCount(len(self.manual_tracking_data.events))
        
        for row, event in enumerate(self.manual_tracking_data.events):
            # Time
            time_str = f"{int(event.timestamp // 60):02d}:{int(event.timestamp % 60):02d}"
            self.events_table.setItem(row, 0, QTableWidgetItem(time_str))
            
            # Event - translate event_type
            translated_event_type = t(event.event_type, event.event_type)
            self.events_table.setItem(row, 1, QTableWidgetItem(translated_event_type))
            
            # Outcome - translate outcome
            if event.outcome:
                translated_outcome = t(event.outcome, event.outcome)
            else:
                translated_outcome = "-"
            self.events_table.setItem(row, 2, QTableWidgetItem(translated_outcome))
            
            # Team - translate "กลาง" if needed, otherwise keep team name
            if event.team == "กลาง":
                translated_team = t("กลาง", "Neutral")
            else:
                translated_team = event.team
            self.events_table.setItem(row, 3, QTableWidgetItem(translated_team))
            
            # Half - convert numeric to text with translation
            half_mapping_th = {
                1: "ครึ่งแรก",
                2: "ครึ่งหลัง",
                3: "ต่อเวลาครึ่งแรก",
                4: "ต่อเวลาครึ่งหลัง"
            }
            half_mapping_en = {
                1: "First Half",
                2: "Second Half",
                3: "Extra Time First Half",
                4: "Extra Time Second Half"
            }
            if current_lang == "EN":
                half_text = half_mapping_en.get(event.half, f"Half {event.half}")
            else:
                half_text = half_mapping_th.get(event.half, f"ครึ่ง {event.half}")
            self.events_table.setItem(row, 4, QTableWidgetItem(half_text))
            
            # Player name
            player_name = event.player_name if event.player_name else "-"
            self.events_table.setItem(row, 5, QTableWidgetItem(player_name))
            
            # Delete button - translate
            delete_text = t("ลบ", "Delete")
            delete_btn = QPushButton(delete_text)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_event_by_index(r))
            self.events_table.setCellWidget(row, 6, delete_btn)
    
    def delete_selected_event(self):
        """Delete selected event from table"""
        current_row = self.events_table.currentRow()
        if current_row >= 0:
            self.delete_event_by_index(current_row)
    
    def delete_event_by_index(self, index: int):
        """Delete event by index"""
        self.manual_tracking_data.remove_event(index)
        self.update_events_table()
    
    def on_event_double_clicked(self, item):
        """Handle double-click on event to jump to video timestamp"""
        if not item:
            return
        
        row = item.row()
        if row < 0 or not self.manual_tracking_data or row >= len(self.manual_tracking_data.events):
            return
        
        # Get the event
        event = self.manual_tracking_data.events[row]
        
        # Check if video is loaded
        if self.manual_video_player.media_player.source().isEmpty():
            QMessageBox.warning(self, t("ไม่มีวิดีโอ", "ไม่มีวิดีโอ"), t("กรุณาโหลดวิดีโอก่อน", "กรุณาโหลดวิดีโอก่อน"))
            return
        
        # Convert timestamp (seconds) to milliseconds
        timestamp_ms = int(event.timestamp * 1000)
        
        # Jump to the timestamp
        self.manual_video_player.media_player.setPosition(timestamp_ms)
        
        # Pause the video to show the frame
        if self.manual_video_player.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.manual_video_player.media_player.pause()
        
        # Highlight the row briefly
        self.events_table.selectRow(row)
    
    def clear_all_events(self):
        """Clear all events"""
        reply = QMessageBox.question(
            self, t("ยืนยัน", "ยืนยัน"), t("คุณแน่ใจหรือไม่ว่าต้องการลบเหตุการณ์ทั้งหมด?", "คุณแน่ใจหรือไม่ว่าต้องการลบเหตุการณ์ทั้งหมด?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manual_tracking_data.events.clear()
            self.update_events_table()
    
    def export_tracking_to_csv(self):
        """Export tracking data to Excel with multiple sheets"""
        if not self.manual_tracking_data or not self.manual_tracking_data.events:
            QMessageBox.warning(self, t("ไม่มีข้อมูล", "ไม่มีข้อมูล"), t("ไม่มีเหตุการณ์ที่ติดตามเพื่อส่งออก", "ไม่มีเหตุการณ์ที่ติดตามเพื่อส่งออก"))
            return
        
        export_title = t("ส่งออกข้อมูลการติดตาม", "Export Tracking Data")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            export_title,
            "",
            "Excel Files (*.xlsx);;CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.xlsx'):
                    # Export to Excel with multiple sheets
                    # Check if there are 2 teams for comparison sheet
                    teams = sorted(set(e.team for e in self.manual_tracking_data.events if e.team != "กลาง"))
                    has_comparison = len(teams) == 2
                    
                    self.manual_tracking_data.export_to_excel(file_path)
                    
                    sheet_info = (
                        f"{t('ไฟล์ประกอบด้วย:', 'ไฟล์ประกอบด้วย:')}\n"
                        f"- Sheet 1: {t('ข้อมูลดิบ', 'ข้อมูลดิบ')}\n"
                        f"- Sheet 2: {t('สรุปผลรวม', 'สรุปผลรวม')} ({t('ไม่มีเปอร์เซ็นต์', 'ไม่มีเปอร์เซ็นต์')})\n"
                    )
                    if has_comparison:
                        sheet_info += f"- Sheet 3: {t('เปรียบเทียบทีม', 'เปรียบเทียบทีม')}\n"
                        sheet_info += f"- Sheet 4-7: {t('สรุปตามครึ่ง', 'สรุปตามครึ่ง')}"
                    else:
                        sheet_info += f"- Sheet 3-6: {t('สรุปตามครึ่ง', 'สรุปตามครึ่ง')}"
                    
                    QMessageBox.information(
                        self, 
                        t("สำเร็จ", "สำเร็จ"), 
                        f"{t('ส่งออกข้อมูลการติดตามไปยัง:', 'ส่งออกข้อมูลการติดตามไปยัง:')}\n{file_path}\n\n{sheet_info}"
                    )
                else:
                    # Fallback to CSV
                    self.manual_tracking_data.export_to_csv(file_path)
                    QMessageBox.information(self, t("สำเร็จ", "Success"), f"{t('ส่งออกข้อมูลการติดตามไปยัง:', 'Tracking data exported to:')}\n{file_path}")
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "ข้อผิดพลาด", 
                    f"ไม่สามารถส่งออกไฟล์ได้:\n{str(e)}\n\n"
                    "กรุณาตรวจสอบว่าติดตั้ง openpyxl แล้วหรือไม่:\n"
                    "pip install openpyxl"
                )
    
    def load_video_for_manual_tracking(self):
        """เพิ่มวิดีโอสำหรับติดตามด้วยมือ"""
        add_video_title = t("เพิ่มวิดีโอสำหรับติดตามด้วยมือ", "Add Video for Manual Tracking")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            add_video_title,
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        
        if file_path and os.path.exists(file_path):
            try:
                # Reset load attempts counter
                self._video_load_attempts = 0
                
                # Load video
                self.manual_video_player.load_video(file_path)
                
                # Store video path
                if self.manual_tracking_data:
                    self.manual_tracking_data.video_path = file_path
                
                # Wait a bit for media to load, then check status
                QTimer.singleShot(500, lambda: self.check_video_loaded(file_path))
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")
    
    def check_video_loaded(self, file_path: str):
        """Check if video loaded successfully"""
        try:
            media_status = self.manual_video_player.media_player.mediaStatus()
            # Check for loaded status
            if media_status in [QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia]:
                success_title = t("โหลดวิดีโอสำเร็จ", "Video Loaded Successfully")
                success_msg = t(
                    f"โหลดวิดีโอสำเร็จ:\n{os.path.basename(file_path)}\n\nคุณสามารถเล่นวิดีโอและเพิ่มเหตุการณ์ติดตามได้แล้ว",
                    f"Video loaded successfully:\n{os.path.basename(file_path)}\n\nYou can now play the video and add tracking events"
                )
                QMessageBox.information(self, success_title, success_msg)
            elif media_status == QMediaPlayer.MediaStatus.InvalidMedia:
                invalid_title = t("วิดีโอไม่ถูกต้อง", "Invalid Video")
                invalid_msg = t(
                    f"ไฟล์วิดีโออาจเสียหายหรือรูปแบบไม่รองรับ:\n{os.path.basename(file_path)}\n\nกรุณาลองใช้ไฟล์วิดีโออื่น",
                    f"Video file may be corrupted or format not supported:\n{os.path.basename(file_path)}\n\nPlease try another video file"
                )
                QMessageBox.warning(self, invalid_title, invalid_msg)
            else:
                # Still loading, wait a bit more (max 5 seconds)
                if not hasattr(self, '_video_load_attempts'):
                    self._video_load_attempts = 0
                self._video_load_attempts += 1
                if self._video_load_attempts < 5:
                    QTimer.singleShot(1000, lambda: self.check_video_loaded(file_path))
                else:
                    # Assume loaded after timeout
                    success_title = t("โหลดวิดีโอสำเร็จ", "Video Loaded Successfully")
                    success_msg = t(
                        f"โหลดวิดีโอ:\n{os.path.basename(file_path)}\n\nคุณสามารถเล่นวิดีโอและเพิ่มเหตุการณ์ติดตามได้แล้ว",
                        f"Video loaded:\n{os.path.basename(file_path)}\n\nYou can now play the video and add tracking events"
                    )
                    QMessageBox.information(self, success_title, success_msg)
                    self._video_load_attempts = 0
        except Exception as e:
            # If check fails, assume it's loaded
            success_title = t("โหลดวิดีโอสำเร็จ", "Video Loaded Successfully")
            success_msg = t(
                f"โหลดวิดีโอ:\n{os.path.basename(file_path)}\n\nคุณสามารถเล่นวิดีโอและเพิ่มเหตุการณ์ติดตามได้แล้ว",
                f"Video loaded:\n{os.path.basename(file_path)}\n\nYou can now play the video and add tracking events"
            )
            QMessageBox.information(self, success_title, success_msg)
    
    def show_customize_events_dialog(self):
        """Show dialog to customize which tracking events are visible"""
        # Get current language to set initial text
        current_lang = self.translation_manager.get_language()
        
        dialog = QDialog(self)
        dialog_title_th = "ปรับแต่งปุ่มติดตาม"
        dialog_title_en = "Customize Tracking Buttons"
        dialog.setWindowTitle(dialog_title_en if current_lang == "EN" else dialog_title_th)
        dialog.setMinimumSize(400, 500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555;
                border-radius: 3px;
                background-color: #2b2b2b;
            }
            QCheckBox::indicator:checked {
                background-color: #c41e3a;
                border-color: #c41e3a;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        title_text_th = "เลือกปุ่มที่ต้องการแสดง:"
        title_text_en = "Select buttons to display:"
        title_text = title_text_en if current_lang == "EN" else title_text_th
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 12pt; color: #c41e3a; margin-bottom: 10px;")
        layout.addWidget(title)
        
        instruction_text_th = "เลือกปุ่มที่ต้องการแสดงในแผงติดตาม:"
        instruction_text_en = "Select buttons to display in the tracking panel:"
        instruction_text = instruction_text_en if current_lang == "EN" else instruction_text_th
        instruction = QLabel(instruction_text)
        instruction.setStyleSheet("color: #b0b0b0; margin-bottom: 15px;")
        layout.addWidget(instruction)
        
        # Select All / Clear All buttons
        select_buttons_layout = QHBoxLayout()
        select_all_text_th = "เลือกทั้งหมด"
        select_all_text_en = "Select All"
        select_all_text = select_all_text_en if current_lang == "EN" else select_all_text_th
        select_all_btn = QPushButton(select_all_text)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        clear_all_text_th = "เอาออกทั้งหมด"
        clear_all_text_en = "Clear All"
        clear_all_text = clear_all_text_en if current_lang == "EN" else clear_all_text_th
        clear_all_btn = QPushButton(clear_all_text)
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(clear_all_btn)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)
        
        # Scroll area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(5)
        
        # Create checkboxes for each event type
        self.event_checkboxes = {}
        for event_data in self.default_event_types:
            if len(event_data) == 3:
                event_name, color, _ = event_data
            else:
                event_name, color = event_data
            # Translate event name for checkbox
            translated_event_name = t(event_name, event_name)
            checkbox = QCheckBox(translated_event_name)
            checkbox.setChecked(event_name in self.enabled_events)
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-weight: bold;
                }}
            """)
            scroll_layout.addWidget(checkbox)
            self.event_checkboxes[event_name] = checkbox
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Connect select all / clear all buttons
        def select_all():
            for checkbox in self.event_checkboxes.values():
                checkbox.setChecked(True)
        
        def clear_all():
            for checkbox in self.event_checkboxes.values():
                checkbox.setChecked(False)
        
        select_all_btn.clicked.connect(select_all)
        clear_all_btn.clicked.connect(clear_all)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_text_th = "ตกลง"
        ok_text_en = "OK"
        ok_text = ok_text_en if current_lang == "EN" else ok_text_th
        ok_btn = QPushButton(ok_text)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_text_th = "ยกเลิก"
        cancel_text_en = "Cancel"
        cancel_text = cancel_text_en if current_lang == "EN" else cancel_text_th
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update enabled events based on checkboxes
            self.enabled_events = {
                event_name for event_name, checkbox in self.event_checkboxes.items()
                if checkbox.isChecked()
            }
            
            # Update button visibility
            for event_name, btn in self.event_buttons.items():
                btn.setVisible(event_name in self.enabled_events)
    
    def show_manual_tracking_help(self):
        """Show comprehensive help dialog for manual tracking in Thai"""
        dialog = QDialog(self)
        dialog.setWindowTitle(t("คู่มือการใช้งาน Manual Tracking", "Manual Tracking User Guide"))
        dialog.setMinimumSize(900, 700)
        dialog.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #c41e3a;
                color: white;
                padding: 10px 25px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #d63347;
            }
            QScrollArea {
                background-color: rgba(30, 30, 46, 0.8);
                border: 2px solid #c41e3a;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel(t("📖 คู่มือการใช้งาน Manual Tracking", "📖 Manual Tracking User Guide"))
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 20pt;
            color: #FFD700;
            padding: 10px;
            background-color: rgba(196, 30, 58, 0.3);
            border-radius: 8px;
            margin-bottom: 10px;
        """)
        layout.addWidget(title)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(30, 30, 46, 0.5);
                border: 2px solid #c41e3a;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 14px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background-color: #c41e3a;
                border-radius: 7px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #d63347;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Section 1: Introduction
        intro_section = self.create_help_section(
            "🎯 ภาพรวมการใช้งาน",
            """
            <p style='font-size: 11pt; line-height: 1.6;'>
            <b>Manual Tracking</b> เป็นระบบติดตามเหตุการณ์การแข่งขันฟุตบอลแบบมืออาชีพ 
            ใช้ในการวิเคราะห์การแข่งขันฟุตบอล
            </p>
            <p style='font-size: 11pt; line-height: 1.6;'>
            <b>ขั้นตอนการใช้งาน:</b><br>
            1. กดปุ่ม <b style='color: #2196F3;'>เพิ่มวิดีโอ</b> เพื่อโหลดวิดีโอการแข่งขัน<br>
            2. ตั้งชื่อทีม 1 และทีม 2 (หรือใช้ชื่อเริ่มต้น)<br>
            3. ตั้งค่ารายชื่อผู้เล่น (ถ้าต้องการ)<br>
            4. เลือกทีมและครึ่งที่ต้องการติดตาม<br>
            5. เล่นวิดีโอและกดปุ่มเหตุการณ์ต่างๆ เมื่อเกิดเหตุการณ์<br>
            6. ส่งออกข้อมูลเป็น Excel หรือ CSV เมื่อเสร็จสิ้น
            </p>
            """,
            "#4CAF50"
        )
        content_layout.addWidget(intro_section)
        
        # Section 2: Attacking Actions
        attacking_section = self.create_help_section(
            "⚽ การโจมตี (Attacking Actions)",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>ปุ่มการโจมตี:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b style='color: #FF9800;'>ยิง</b> - บันทึกการยิงประตู
                <ul>
                <li><b>ประตู</b> - ยิงได้ประตู</li>
                <li><b>ยิงเข้า</b> - ยิงเข้าเป้าแต่ไม่ได้ประตู (นับเป็นสำเร็จ)</li>
                <li><b>ยิงออก</b> - ยิงออกนอกเป้า</li>
                <li><b>บล็อก</b> - ถูกบล็อก</li>
                <li><b>ถูกเซฟ</b> - ถูกผู้รักษาประตูเซฟ</li>
                </ul>
            </li>
            <li><b style='color: #2196F3;'>ส่งบอล</b> - บันทึกการส่งบอล
                <ul>
                <li><b>สำเร็จ</b> - ส่งบอลสำเร็จ</li>
                <li><b>ไม่สำเร็จ</b> - ส่งบอลไม่สำเร็จ</li>
                <li><b>แอสซิสต์</b> - ส่งบอลแล้วได้ประตู</li>
                <li><b>คีย์พาส</b> - ส่งบอลที่สร้างโอกาสยิง</li>
                </ul>
            </li>
            <li><b style='color: #E91E63;'>ข้ามบอล</b> - บันทึกการข้ามบอล (ผลลัพธ์เหมือนส่งบอล)</li>
            <li><b style='color: #9C27B0;'>ผ่านบอล</b> - บันทึกการผ่านบอล (ผลลัพธ์เหมือนส่งบอล)</li>
            <li><b style='color: #795548;'>ส่งบอลยาว</b> - บันทึกการส่งบอลยาว (ผลลัพธ์เหมือนส่งบอล)</li>
            <li><b style='color: #607D8B;'>ส่งบอลสั้น</b> - บันทึกการส่งบอลสั้น (สำเร็จ/ไม่สำเร็จ)</li>
            <li><b style='color: #FF5722;'>ส่งบอลในเขตโทษ</b> - บันทึกการส่งบอลในเขตโทษ (ผลลัพธ์เหมือนส่งบอล)</li>
            </ul>
            """,
            "#FF9800"
        )
        content_layout.addWidget(attacking_section)
        
        # Section 3: Set Pieces
        setpieces_section = self.create_help_section(
            "🎯 ลูกตั้งเตะ (Set Pieces)",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>ปุ่มลูกตั้งเตะ:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b style='color: #00BCD4;'>เตะมุม</b> - บันทึกการเตะมุม
                <ul>
                <li><b>ประตู</b> - เตะมุมแล้วได้ประตู</li>
                <li><b>ยิงเข้า</b> - เตะมุมแล้วยิงเข้าเป้า</li>
                <li><b>ยิงออก</b> - เตะมุมแล้วยิงออก</li>
                <li><b>แอสซิสต์</b> - เตะมุมแล้วได้ประตู</li>
                <li><b>คีย์พาส</b> - เตะมุมแล้วสร้างโอกาสยิง</li>
                <li><b>เคลียร์</b> - ถูกเคลียร์ออก</li>
                </ul>
            </li>
            <li><b style='color: #FFC107;'>ฟรีคิก</b> - บันทึกการเตะฟรีคิก (ผลลัพธ์เหมือนเตะมุม)</li>
            <li><b style='color: #F44336;'>ลูกโทษ</b> - บันทึกการเตะลูกโทษ
                <ul>
                <li><b>ประตู</b> - เตะลูกโทษได้ประตู</li>
                <li><b>ไม่ประตู</b> - เตะลูกโทษไม่ประตู</li>
                <li><b>ถูกเซฟ</b> - ถูกผู้รักษาประตูเซฟ</li>
                </ul>
            </li>
            <li><b style='color: #607D8B;'>ทุ่มบอล</b> - บันทึกการทุ่มบอล (สำเร็จ/ไม่สำเร็จ)</li>
            </ul>
            """,
            "#00BCD4"
        )
        content_layout.addWidget(setpieces_section)
        
        # Section 4: Defensive Actions
        defensive_section = self.create_help_section(
            "🛡️ การป้องกัน (Defensive Actions)",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>ปุ่มการป้องกัน:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b style='color: #9C27B0;'>แย่งบอล</b> - บันทึกการแย่งบอล
                <ul>
                <li><b>สำเร็จ</b> - แย่งบอลสำเร็จ</li>
                <li><b>ไม่สำเร็จ</b> - แย่งบอลไม่สำเร็จ</li>
                <li><b>ฟาวล์</b> - แย่งบอลแล้วทำฟาวล์</li>
                </ul>
            </li>
            <li><b style='color: #9C27B0;'>สกัดบอล</b> - บันทึกการสกัดบอล (สำเร็จ/ไม่สำเร็จ)</li>
            <li><b style='color: #795548;'>เคลียร์บอล</b> - บันทึกการเคลียร์บอล
                <ul>
                <li><b>สำเร็จ</b> - เคลียร์บอลสำเร็จ</li>
                <li><b>ไม่สำเร็จ</b> - เคลียร์บอลไม่สำเร็จ</li>
                <li><b>อันตราย</b> - เคลียร์บอลแบบอันตราย</li>
                </ul>
            </li>
            <li><b style='color: #FF5722;'>บล็อก</b> - บันทึกการบล็อก
                <ul>
                <li><b>บล็อก</b> - บล็อกสำเร็จ</li>
                <li><b>บล็อกยิง</b> - บล็อกการยิง</li>
                </ul>
            </li>
            <li><b style='color: #00BCD4;'>เซฟ</b> - บันทึกการเซฟของผู้รักษาประตู
                <ul>
                <li><b>เซฟ</b> - เซฟสำเร็จ</li>
                <li><b>ไม่เซฟ</b> - ไม่เซฟได้</li>
                <li><b>เซฟสำคัญ</b> - เซฟที่สำคัญ</li>
                </ul>
            </li>
            </ul>
            """,
            "#9C27B0"
        )
        content_layout.addWidget(defensive_section)
        
        # Section 5: Disciplinary
        disciplinary_section = self.create_help_section(
            "⚖️ การทำผิดกติกา (Disciplinary)",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>ปุ่มการทำผิดกติกา:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b style='color: #F44336;'>ฟาวล์</b> - บันทึกการทำฟาวล์
                <ul>
                <li><b>ฟาวล์</b> - ฟาวล์ธรรมดา</li>
                <li><b>ใบเหลือง</b> - ฟาวล์แล้วได้ใบเหลือง</li>
                <li><b>ใบแดง</b> - ฟาวล์แล้วได้ใบแดง</li>
                </ul>
            </li>
            <li><b style='color: #FFEB3B;'>ใบเหลือง</b> - บันทึกการได้ใบเหลือง</li>
            <li><b style='color: #E91E63;'>ใบแดง</b> - บันทึกการได้ใบแดง</li>
            </ul>
            """,
            "#F44336"
        )
        content_layout.addWidget(disciplinary_section)
        
        # Section 6: Other Events
        other_section = self.create_help_section(
            "📋 เหตุการณ์อื่นๆ (Other Events)",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>ปุ่มเหตุการณ์อื่นๆ:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b style='color: #9E9E9E;'>ออฟไซด์</b> - บันทึกการออฟไซด์</li>
            <li><b style='color: #607D8B;'>บอลออก</b> - บันทึกการที่บอลออกนอกสนาม</li>
            <li><b style='color: #795548;'>เปลี่ยนตัว</b> - บันทึกการเปลี่ยนตัวผู้เล่น
                <ul>
                <li><b>เปลี่ยนตัวเข้า</b> - ผู้เล่นเข้า</li>
                <li><b>เปลี่ยนตัวออก</b> - ผู้เล่นออก</li>
                </ul>
            </li>
            <li><b style='color: #FF9800;'>บาดเจ็บ</b> - บันทึกการบาดเจ็บ</li>
            <li><b style='color: #F44336;'>เสียบอล</b> - บันทึกการเสียบอล</li>
            <li><b style='color: #4CAF50;'>ครองบอล</b> - บันทึกการครองบอล</li>
            </ul>
            """,
            "#607D8B"
        )
        content_layout.addWidget(other_section)
        
        # Section 7: Tips and Best Practices
        tips_section = self.create_help_section(
            "💡 เคล็ดลับและแนวทางปฏิบัติ",
            """
            <p style='font-size: 11pt; line-height: 1.6;'><b>เคล็ดลับการใช้งาน:</b></p>
            <ul style='font-size: 10pt; line-height: 1.8;'>
            <li><b>การบันทึกเวลา:</b> วิดีโอจะหยุดอัตโนมัติเมื่อกดปุ่มเหตุการณ์ เพื่อให้บันทึกเวลาที่แม่นยำ</li>
            <li><b>การตั้งชื่อทีม:</b> สามารถเปลี่ยนชื่อทีมได้ตลอดเวลา และจะอัพเดทในรายการเหตุการณ์ทันที</li>
            <li><b>การตั้งค่ารายชื่อ:</b> ตั้งค่ารายชื่อผู้เล่นเพื่อให้สามารถบันทึกชื่อผู้เล่นได้เมื่อเกิดประตู</li>
            <li><b>การลบเหตุการณ์:</b> คลิกที่เหตุการณ์ในตารางแล้วกด "ลบที่เลือก" หรือดับเบิลคลิกเพื่อไปยังเวลานั้น</li>
            <li><b>การปรับแต่งปุ่ม:</b> ใช้ปุ่ม "ปรับแต่งปุ่ม" เพื่อเลือกปุ่มที่ต้องการแสดง</li>
            <li><b>การส่งออก:</b> ส่งออกเป็น Excel เพื่อดูสถิติแบบละเอียด หรือ CSV สำหรับการวิเคราะห์ต่อ</li>
            <li><b>การบันทึกประตู:</b> เมื่อเลือกผลลัพธ์ "ประตู" จะมีหน้าต่างให้กรอกชื่อผู้ยิงและรายละเอียดเพิ่มเติม</li>
            </ul>
            """,
            "#FFD700"
        )
        content_layout.addWidget(tips_section)
        
        # Credits section
        credits_section = QWidget()
        credits_section.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(196, 30, 58, 0.4), stop:1 rgba(33, 150, 243, 0.4));
                border: 2px solid #c41e3a;
                border-radius: 10px;
                padding: 20px;
            }
        """)
        credits_layout = QVBoxLayout(credits_section)
        credits_layout.setSpacing(15)
        credits_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title with better styling
        about_title = QLabel(t("👨‍💻 ผู้พัฒนา", "👨‍💻 Developer"))
        about_title.setStyleSheet("""
            font-weight: bold;
            font-size: 18pt;
            color: #FFD700;
            padding: 10px 0px;
            background-color: rgba(255, 215, 0, 0.1);
            border-radius: 5px;
            border-left: 4px solid #FFD700;
            padding-left: 10px;
        """)
        credits_layout.addWidget(about_title)
        
        # Developer info with better spacing
        developer_name = QLabel("นายพัชระ อัลอุมารี")
        developer_name.setStyleSheet("""
            font-size: 15pt;
            color: #FFFFFF;
            font-weight: bold;
            padding: 10px 0px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            padding-left: 10px;
        """)
        credits_layout.addWidget(developer_name)
        
        # Info container for better organization
        info_container = QWidget()
        info_container.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 46, 0.5);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        # Location
        location_label = QLabel("📍 <b>ที่อยู่:</b> กรุงเทพมหานคร, ประเทศไทย")
        location_label.setStyleSheet("""
            font-size: 11pt;
            color: #e0e0e0;
            padding: 8px;
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 5px;
        """)
        location_label.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(location_label)
        
        # Email
        email_label = QLabel('<a href="mailto:Patcharaalumaree@gmail.com" style="color: #2196F3; text-decoration: none;"><b>📧 อีเมล:</b> Patcharaalumaree@gmail.com</a>')
        email_label.setOpenExternalLinks(True)
        email_label.setTextFormat(Qt.TextFormat.RichText)
        email_label.setStyleSheet("""
            font-size: 11pt;
            color: #2196F3;
            padding: 8px;
            background-color: rgba(33, 150, 243, 0.1);
            border-radius: 5px;
        """)
        info_layout.addWidget(email_label)
        
        # GitHub link
        github_link = QLabel('<a href="https://github.com/MrPatchara" style="color: #2196F3; text-decoration: none; font-weight: bold;">🔗 <b>โปรไฟล์ GitHub</b></a>')
        github_link.setOpenExternalLinks(True)
        github_link.setTextFormat(Qt.TextFormat.RichText)
        github_link.setStyleSheet("""
            font-size: 12pt;
            color: #2196F3;
            padding: 10px;
            background-color: rgba(33, 150, 243, 0.15);
            border: 1px solid rgba(33, 150, 243, 0.3);
            border-radius: 5px;
        """)
        info_layout.addWidget(github_link)
        
        credits_layout.addWidget(info_container)
        
        content_layout.addWidget(credits_section)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Close button
        close_btn = QPushButton("ปิด")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def create_help_section(self, title: str, content: str, color: str) -> QWidget:
        """Create a styled help section"""
        section = QWidget()
        section.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(30, 30, 46, 0.6);
                border-left: 4px solid {color};
                border-radius: 5px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14pt;
            color: {color};
            padding-bottom: 5px;
        """)
        layout.addWidget(title_label)
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("""
            font-size: 10pt;
            color: #e0e0e0;
            line-height: 1.6;
        """)
        layout.addWidget(content_label)
        
        return section


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look
    
    window = FreeFootballAnalysisApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
