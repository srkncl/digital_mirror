#!/usr/bin/env python3
"""
Digital Mirror - A camera mirror app for Apple platforms
Uses PySide6 (Qt) for UI and OpenCV for camera access
Works on macOS and iOS
"""

VERSION = "1.1.0"

import sys
import platform
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QComboBox, QFrame,
    QStyledItemDelegate, QListView, QSlider, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QSize, QSettings, Signal
from PySide6.QtGui import QImage, QPixmap, QIcon, QAction, QKeySequence, QNativeGestureEvent


def is_ios():
    """Check if running on iOS."""
    # On iOS via Pythonista or similar, platform.system() returns 'Darwin'
    # but platform.machine() returns 'iPhone' or 'iPad'
    machine = platform.machine().lower()
    return 'iphone' in machine or 'ipad' in machine


def get_camera_devices():
    """Get list of available camera devices with their names.

    Returns:
        List of tuples: (index, device_name)
    """
    cameras = []

    # macOS and iOS use AVFoundation
    try:
        import AVFoundation
        devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
            AVFoundation.AVMediaTypeVideo
        )
        for i, device in enumerate(devices):
            cameras.append((i, device.localizedName()))
    except ImportError:
        # Fallback if AVFoundation not available via PyObjC
        pass

    # Fallback: probe camera indices with OpenCV
    if not cameras:
        # On iOS, typically 0 = back camera, 1 = front camera
        camera_names = ["Back Camera", "Front Camera"] if is_ios() else ["Camera 0", "Camera 1"]
        for i in range(2 if is_ios() else 5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                name = camera_names[i] if i < len(camera_names) else f"Camera {i}"
                cameras.append((i, name))
                cap.release()

    return cameras


class StyledComboBox(QComboBox):
    """ComboBox with dark-themed popup."""

    def showPopup(self):
        super().showPopup()
        # Style the popup container when it appears
        popup = self.findChild(QFrame)
        if popup:
            popup.setStyleSheet("background-color: #3a3a3a; border: 1px solid #4a4a4a;")
        # Also style the view's parent container
        if self.view() and self.view().window():
            self.view().window().setStyleSheet("background-color: #3a3a3a; border: 1px solid #4a4a4a;")


class CameraWidget(QLabel):
    """Widget that displays the camera feed."""

    # Signal emitted when zoom changes via pinch gesture
    zoom_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        self.is_frozen = False
        self.frozen_locked = False  # True when frozen via double-tap
        self.last_raw_frame = None  # Store raw frame for re-rendering when frozen
        self.last_mirrored = True
        self.pan_offset_x = 0.0  # Pan offset as fraction of frame width
        self.pan_offset_y = 0.0  # Pan offset as fraction of frame height
        self.drag_start_pos = None  # For mouse drag panning
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Enable keyboard focus
        self.setStyleSheet("background-color: #1a1a1a; border-radius: 8px;")
        self.setText("Initializing camera...")
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #888;
                font-size: 18px;
                border-radius: 8px;
            }
        """)

    def event(self, event):
        """Handle events including gestures."""
        if event.type() == event.Type.Gesture:
            return self._handle_gesture(event)
        elif event.type() == event.Type.NativeGesture:
            return self._handle_native_gesture(event)
        return super().event(event)

    def _handle_gesture(self, event):
        """Handle pinch gesture for zoom."""
        from PySide6.QtWidgets import QGestureEvent, QPinchGesture
        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if pinch:
            scale_factor = pinch.scaleFactor()
            if scale_factor != 1.0:
                # Emit signal with delta (scale factor relative to 1.0)
                self.zoom_changed.emit(scale_factor)
        return True

    def _handle_native_gesture(self, event):
        """Handle native gesture events (macOS trackpad)."""
        gesture_type = event.gestureType()
        if gesture_type == Qt.NativeGestureType.ZoomNativeGesture:
            # Value is the zoom delta
            delta = event.value()
            # Convert to scale factor (1.0 + delta)
            self.zoom_changed.emit(1.0 + delta)
            return True
        return False

    def wheelEvent(self, event):
        """Handle scroll wheel/trackpad scroll for panning when frozen."""
        if self.is_frozen and hasattr(self, '_last_zoom') and self._last_zoom > 1.0:
            # Get scroll delta (pixelDelta for trackpad, angleDelta for mouse wheel)
            pixel_delta = event.pixelDelta()
            if not pixel_delta.isNull():
                # Trackpad scroll - use pixel delta directly
                dx = pixel_delta.x()
                dy = pixel_delta.y()
            else:
                # Mouse wheel - convert angle to pixels
                angle_delta = event.angleDelta()
                dx = angle_delta.x() / 8
                dy = angle_delta.y() / 8

            if self.last_raw_frame is not None:
                h, w = self.last_raw_frame.shape[:2]
                self.pan_offset_x += dx / w * 4
                self.pan_offset_y += dy / h * 4
                self._clamp_pan_offset()
                self._request_rerender()
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        """Freeze the frame when mouse is pressed (unless locked frozen)."""
        if self.frozen_locked:
            # Start drag for panning when locked frozen
            self.drag_start_pos = event.position()
        else:
            self.is_frozen = True
            self._show_frozen_overlay("Release to unfreeze")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse drag for panning when frozen."""
        if self.frozen_locked and self.drag_start_pos is not None:
            delta = event.position() - self.drag_start_pos
            self.drag_start_pos = event.position()
            # Convert pixel delta to frame fraction (invert for natural drag)
            if self.last_raw_frame is not None:
                h, w = self.last_raw_frame.shape[:2]
                self.pan_offset_x += delta.x() / w * 2
                self.pan_offset_y += delta.y() / h * 2
                self._clamp_pan_offset()
                self._request_rerender()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Unfreeze the frame when mouse is released (unless locked frozen)."""
        self.drag_start_pos = None
        if not self.frozen_locked:
            self.is_frozen = False
            self._hide_frozen_overlay()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Toggle freeze lock on double-tap."""
        if self.frozen_locked:
            # Unfreeze and reset pan
            self.frozen_locked = False
            self.is_frozen = False
            self.pan_offset_x = 0.0
            self.pan_offset_y = 0.0
            self._hide_frozen_overlay()
        else:
            # Lock frozen
            self.frozen_locked = True
            self.is_frozen = True
            self._show_frozen_overlay("Double-tap to unfreeze")
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Handle arrow keys for panning when frozen."""
        if self.is_frozen:
            pan_step = 0.05  # 5% of frame per key press
            if event.key() == Qt.Key.Key_Left:
                self.pan_offset_x += pan_step
                self._clamp_pan_offset()
                self._request_rerender()
                return
            elif event.key() == Qt.Key.Key_Right:
                self.pan_offset_x -= pan_step
                self._clamp_pan_offset()
                self._request_rerender()
                return
            elif event.key() == Qt.Key.Key_Up:
                self.pan_offset_y += pan_step
                self._clamp_pan_offset()
                self._request_rerender()
                return
            elif event.key() == Qt.Key.Key_Down:
                self.pan_offset_y -= pan_step
                self._clamp_pan_offset()
                self._request_rerender()
                return
        super().keyPressEvent(event)

    def _clamp_pan_offset(self):
        """Clamp pan offset to valid range based on zoom level."""
        # Maximum pan is limited by how much extra frame is visible at current zoom
        # At zoom 1.0, no panning allowed. At zoom 3.0, can pan up to 2/3 of frame.
        if hasattr(self, '_last_zoom'):
            max_pan = max(0, 1 - 1 / self._last_zoom)
        else:
            max_pan = 0.5
        self.pan_offset_x = max(-max_pan, min(max_pan, self.pan_offset_x))
        self.pan_offset_y = max(-max_pan, min(max_pan, self.pan_offset_y))

    def _request_rerender(self):
        """Request parent to re-render the frozen frame."""
        # Find the parent app and trigger re-render
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_rerender_frozen'):
                parent._rerender_frozen()
                break
            parent = parent.parent()

    def _show_frozen_overlay(self, message):
        """Show the frozen indicator text."""
        if not hasattr(self, 'frozen_label'):
            self.frozen_label = QLabel(self)
            self.frozen_label.setStyleSheet("""
                QLabel {
                    color: white;
                    background-color: rgba(0, 0, 0, 0.6);
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 13px;
                }
            """)
        self.frozen_label.setText(message)
        self.frozen_label.adjustSize()
        self.frozen_label.move(10, self.height() - self.frozen_label.height() - 10)
        self.frozen_label.show()
        self.frozen_label.raise_()

    def _hide_frozen_overlay(self):
        """Hide the frozen indicator text."""
        if hasattr(self, 'frozen_label'):
            self.frozen_label.hide()
    
    def update_frame(self, frame: np.ndarray, mirrored: bool = True, zoom: float = 1.0,
                     brightness: int = 0):
        """Update the display with a new frame."""
        if frame is None:
            return

        # Store raw frame for re-rendering when frozen
        self.last_raw_frame = frame.copy()
        self.last_mirrored = mirrored

        self._render_frame(frame, mirrored, zoom, brightness)

    def _render_frame(self, frame: np.ndarray, mirrored: bool, zoom: float, brightness: int):
        """Render a frame with the given settings."""
        # Store zoom for pan clamping
        self._last_zoom = zoom

        # Mirror the frame horizontally if enabled
        if mirrored:
            frame = cv2.flip(frame, 1)

        # Apply zoom by cropping the frame with pan offset
        if zoom > 1.0:
            h, w = frame.shape[:2]
            crop_w = int(w / zoom)
            crop_h = int(h / zoom)
            # Apply pan offset (convert from -1..1 range to pixel offset)
            pan_x = int(self.pan_offset_x * w / 2)
            pan_y = int(self.pan_offset_y * h / 2)
            # Center position with pan offset
            x1 = (w - crop_w) // 2 - pan_x
            y1 = (h - crop_h) // 2 - pan_y
            # Clamp to frame bounds
            x1 = max(0, min(w - crop_w, x1))
            y1 = max(0, min(h - crop_h, y1))
            frame = frame[y1:y1+crop_h, x1:x1+crop_w]

        # Apply brightness adjustment
        if brightness != 0:
            frame = cv2.convertScaleAbs(frame, alpha=1.0, beta=brightness)

        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Get dimensions
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w

        # Create QImage
        q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Scale to fit widget while maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(q_image).scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)

    def rerender_frozen_frame(self, zoom: float, brightness: int):
        """Re-render the frozen frame with new zoom/brightness settings."""
        if self.last_raw_frame is not None:
            self._render_frame(self.last_raw_frame.copy(), self.last_mirrored, zoom, brightness)


class DigitalMirrorApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Mirror")
        self.setMinimumSize(800, 600)

        # Settings
        self.settings = QSettings("DigitalMirror", "DigitalMirror")

        # State
        self.camera = None
        self.camera_index = 0
        self.is_mirrored = True
        self.is_running = False
        self.zoom_level = 1.0
        self.brightness = 0

        # Setup UI
        self._setup_ui()
        self._setup_shortcuts()

        # Load saved settings
        self._load_settings()

        # Setup timer for frame updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)

        # Start camera
        self._start_camera()
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Camera view
        self.camera_widget = CameraWidget()
        self.camera_widget.zoom_changed.connect(self._on_pinch_zoom)
        layout.addWidget(self.camera_widget, 1)
        
        # Controls bar
        controls = QFrame()
        controls.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 8, 12, 8)
        
        # Camera selector
        self.camera_combo = StyledComboBox()
        self.camera_combo.setMinimumWidth(150)
        # Force styled rendering instead of native macOS popup
        self.camera_combo.setItemDelegate(QStyledItemDelegate(self.camera_combo))
        list_view = QListView()
        list_view.setStyleSheet("""
            QListView {
                background-color: #3a3a3a;
                border: none;
                outline: none;
                color: white;
            }
            QListView::item {
                padding: 6px 12px;
                min-height: 24px;
            }
            QListView::item:hover {
                background-color: #4a4a4a;
            }
            QListView::item:selected {
                background-color: #0066cc;
            }
        """)
        self.camera_combo.setView(list_view)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self._populate_cameras()
        controls_layout.addWidget(QLabel("Camera:"))
        controls_layout.addWidget(self.camera_combo)
        
        controls_layout.addStretch()

        # Zoom slider
        controls_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(100)
        self.zoom_slider.setMaximum(500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self.zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background-color: #4a4a4a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background-color: #0066cc;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #0077ee;
            }
        """)
        controls_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("1.0x")
        self.zoom_label.setFixedWidth(35)
        controls_layout.addWidget(self.zoom_label)

        # Brightness slider
        controls_layout.addWidget(QLabel("Brightness:"))
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(-50)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setFixedWidth(100)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        self.brightness_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background-color: #4a4a4a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background-color: #0066cc;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #0077ee;
            }
        """)
        controls_layout.addWidget(self.brightness_slider)
        self.brightness_label = QLabel("0")
        self.brightness_label.setFixedWidth(25)
        controls_layout.addWidget(self.brightness_label)

        controls_layout.addStretch()

        # Mirror toggle button
        self.mirror_btn = QPushButton("🪞 Mirror: ON")
        self.mirror_btn.setCheckable(True)
        self.mirror_btn.setChecked(True)
        self.mirror_btn.clicked.connect(self._toggle_mirror)
        self.mirror_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:checked {
                background-color: #0066cc;
            }
        """)
        controls_layout.addWidget(self.mirror_btn)
        
        # Fullscreen button
        fullscreen_btn = QPushButton("⛶ Fullscreen")
        fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        controls_layout.addWidget(fullscreen_btn)

        # About button
        about_btn = QPushButton("ℹ️ About")
        about_btn.clicked.connect(self._show_about)
        about_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
        """)
        controls_layout.addWidget(about_btn)

        layout.addWidget(controls)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #ccc;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: white;
                selection-background-color: #0066cc;
                border: 1px solid #4a4a4a;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                background-color: #3a3a3a;
                padding: 6px 12px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #4a4a4a;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0066cc;
            }
        """)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Escape to exit fullscreen
        self.shortcut_esc = QAction(self)
        self.shortcut_esc.setShortcut(QKeySequence(Qt.Key_Escape))
        self.shortcut_esc.triggered.connect(self._exit_fullscreen)
        self.addAction(self.shortcut_esc)
        
        # F for fullscreen toggle
        self.shortcut_f = QAction(self)
        self.shortcut_f.setShortcut(QKeySequence(Qt.Key_F))
        self.shortcut_f.triggered.connect(self._toggle_fullscreen)
        self.addAction(self.shortcut_f)
        
        # M for mirror toggle
        self.shortcut_m = QAction(self)
        self.shortcut_m.setShortcut(QKeySequence(Qt.Key_M))
        self.shortcut_m.triggered.connect(self._toggle_mirror)
        self.addAction(self.shortcut_m)
        
        # Q to quit
        self.shortcut_q = QAction(self)
        self.shortcut_q.setShortcut(QKeySequence(Qt.Key_Q))
        self.shortcut_q.triggered.connect(self.close)
        self.addAction(self.shortcut_q)
    
    def _populate_cameras(self):
        """Find available cameras and populate the dropdown."""
        self.camera_combo.clear()

        available_cameras = get_camera_devices()

        if not available_cameras:
            self.camera_combo.addItem("No cameras found")
            return

        for idx, name in available_cameras:
            self.camera_combo.addItem(name, idx)
    
    def _start_camera(self):
        """Start the camera capture."""
        if self.camera is not None:
            self.camera.release()
        
        # Get selected camera index
        idx = self.camera_combo.currentData()
        if idx is None:
            idx = 0
        
        self.camera = cv2.VideoCapture(idx)
        
        if not self.camera.isOpened():
            self.camera_widget.setText("❌ Could not open camera\n\nPlease check camera permissions")
            return
        
        # Set camera properties for better quality
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        
        self.is_running = True
        self.timer.start(33)  # ~30 FPS
    
    def _stop_camera(self):
        """Stop the camera capture."""
        self.is_running = False
        self.timer.stop()
        if self.camera is not None:
            self.camera.release()
            self.camera = None
    
    def _update_frame(self):
        """Capture and display a new frame."""
        if self.camera is None or not self.camera.isOpened():
            return

        # Skip frame update if frozen (user is holding click)
        if self.camera_widget.is_frozen:
            return

        ret, frame = self.camera.read()
        if ret:
            # Reset pan offset when not frozen
            self.camera_widget.pan_offset_x = 0.0
            self.camera_widget.pan_offset_y = 0.0
            self.camera_widget.update_frame(frame, self.is_mirrored, self.zoom_level,
                                            self.brightness)

    def _rerender_frozen(self):
        """Re-render the frozen frame (called by CameraWidget for pan updates)."""
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness)

    def _on_camera_changed(self, index):
        """Handle camera selection change."""
        if self.is_running:
            self._stop_camera()
            self._start_camera()

    def _on_zoom_changed(self, value):
        """Handle zoom slider change."""
        self.zoom_level = value / 100.0
        self.zoom_label.setText(f"{self.zoom_level:.1f}x")
        # Re-render if frozen
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness)

    def _on_pinch_zoom(self, scale_factor):
        """Handle pinch-to-zoom gesture."""
        # Apply scale factor to current zoom level
        new_zoom = self.zoom_level * scale_factor
        # Clamp to valid range (1.0 to 5.0)
        new_zoom = max(1.0, min(5.0, new_zoom))
        self.zoom_level = new_zoom
        # Update slider and label
        self.zoom_slider.setValue(int(new_zoom * 100))
        self.zoom_label.setText(f"{new_zoom:.1f}x")
        # Re-render if frozen
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness)

    def _on_brightness_changed(self, value):
        """Handle brightness slider change."""
        self.brightness = value
        self.brightness_label.setText(str(value))
        # Re-render if frozen
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness)

    def _toggle_mirror(self):
        """Toggle mirror mode."""
        self.is_mirrored = not self.is_mirrored
        self.mirror_btn.setChecked(self.is_mirrored)
        self.mirror_btn.setText(f"🪞 Mirror: {'ON' if self.is_mirrored else 'OFF'}")
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()

    def _show_about(self):
        """Show the About dialog."""
        about_text = f"""<h2>Digital Mirror</h2>
<p>Version {VERSION}</p>
<p>A camera mirror app for Apple platforms.</p>
<p><b>Features:</b></p>
<ul>
<li>Real-time camera preview</li>
<li>Mirror mode (horizontal flip)</li>
<li>Zoom up to 5x with pinch gesture</li>
<li>Brightness adjustment</li>
<li>Freeze frame with pan support</li>
<li>Fullscreen mode</li>
</ul>
<p>Built with Python, PySide6, and OpenCV.</p>
"""
        QMessageBox.about(self, "About Digital Mirror", about_text)

    def _load_settings(self):
        """Load saved settings."""
        # Camera
        saved_camera = str(self.settings.value("camera_name", ""))
        if saved_camera:
            idx = self.camera_combo.findText(saved_camera)
            if idx >= 0:
                self.camera_combo.setCurrentIndex(idx)

        # Mirror
        mirrored_val = self.settings.value("mirrored", True)
        self.is_mirrored = mirrored_val in (True, "true", "True", 1)
        self.mirror_btn.setChecked(self.is_mirrored)
        self.mirror_btn.setText(f"🪞 Mirror: {'ON' if self.is_mirrored else 'OFF'}")

        # Zoom
        zoom_val = self.settings.value("zoom", 1.0)
        try:
            self.zoom_level = float(str(zoom_val))
        except (ValueError, TypeError):
            self.zoom_level = 1.0
        self.zoom_slider.setValue(int(self.zoom_level * 100))
        self.zoom_label.setText(f"{self.zoom_level:.1f}x")

        # Brightness
        brightness_val = self.settings.value("brightness", 0)
        try:
            self.brightness = int(str(brightness_val))
        except (ValueError, TypeError):
            self.brightness = 0
        self.brightness_slider.setValue(self.brightness)
        self.brightness_label.setText(str(self.brightness))

        # Window geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_settings(self):
        """Save current settings."""
        self.settings.setValue("camera_name", self.camera_combo.currentText())
        self.settings.setValue("mirrored", self.is_mirrored)
        self.settings.setValue("zoom", self.zoom_level)
        self.settings.setValue("brightness", self.brightness)
        self.settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Clean up when closing the app."""
        self._save_settings()
        self._stop_camera()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Digital Mirror")
    
    # Set app-wide style
    app.setStyle("Fusion")
    
    window = DigitalMirrorApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
