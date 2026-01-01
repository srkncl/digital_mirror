#!/usr/bin/env python3
"""
Digital Mirror - A camera mirror app for Apple platforms
Uses PySide6 (Qt) for UI and OpenCV for camera access
Works on macOS and iOS
"""

VERSION = "1.2.0"

import sys
import platform
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QComboBox, QFrame,
    QStyledItemDelegate, QListView, QSlider, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QSize, QSettings, Signal
from PySide6.QtGui import QImage, QPixmap, QIcon, QAction, QKeySequence, QNativeGestureEvent, QPainter


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
        # Mask editing state
        self.mask_edit_mode = False  # True when in mask editing mode
        self.mask_add_mode = False  # True = add to mask, False = remove from mask (default: erase)
        self.user_mask_additions = None  # User-painted additions to mask
        self.user_mask_removals = None  # User-painted removals from mask
        self.last_paint_pos = None  # Last position for continuous painting
        self.brush_size = 20  # Brush size in pixels
        # Store the displayed image region for coordinate mapping
        self._display_crop = None  # (x1, y1, x2, y2) of displayed region in processed frame
        self._processed_frame_size = None  # (h, w) of frame after mirror/zoom but before face crop
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
        """Handle scroll wheel/trackpad scroll for panning when frozen, or brush size in edit mode."""
        if self.mask_edit_mode and self.frozen_locked:
            # In edit mode, scroll changes brush size
            angle_delta = event.angleDelta()
            if angle_delta.y() != 0:
                # Vertical scroll changes brush size
                delta = 5 if angle_delta.y() > 0 else -5
                self.brush_size = max(5, min(100, self.brush_size + delta))
                self._show_frozen_overlay(f"Brush: {self.brush_size}px  Left=Add  Right=Remove")
            event.accept()
            return
        elif self.is_frozen and hasattr(self, '_last_zoom') and self._last_zoom > 1.0:
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
        if self.mask_edit_mode and self.frozen_locked:
            # Start painting on mask
            # Right-click toggles to erase mode, left-click uses current mode
            if event.button() == Qt.MouseButton.RightButton:
                self.mask_add_mode = False
                mode = "ERASE"
            else:
                # Left click - use current mode (allows trackpad users to use A/E keys)
                mode = "ADD" if self.mask_add_mode else "ERASE"
            self._show_frozen_overlay(f"Mode: {mode}  Brush: {self.brush_size}px")
            self.last_paint_pos = event.position()
            self._paint_at_position(event.position(), self.mask_add_mode)
        elif self.frozen_locked:
            # Start drag for panning when locked frozen
            self.drag_start_pos = event.position()
        else:
            self.is_frozen = True
            self._show_frozen_overlay("Release to unfreeze")
            self._request_rerender()  # Apply bg removal on freeze
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse drag for panning when frozen."""
        if self.mask_edit_mode and self.frozen_locked and self.last_paint_pos is not None:
            # Continue painting
            self._paint_at_position(event.position(), self.mask_add_mode)
            self.last_paint_pos = event.position()
        elif self.frozen_locked and self.drag_start_pos is not None:
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
        self.last_paint_pos = None
        if not self.frozen_locked:
            self.is_frozen = False
            self._hide_frozen_overlay()
        super().mouseReleaseEvent(event)

    def _paint_at_position(self, pos, add_mode):
        """Paint on the user mask at the given widget position."""
        if self.last_raw_frame is None:
            return

        # Convert widget position to frame coordinates
        pixmap = self.pixmap()
        if pixmap is None:
            return

        # Get the actual display rect (centered in widget)
        widget_w, widget_h = self.width(), self.height()
        pixmap_w, pixmap_h = pixmap.width(), pixmap.height()
        offset_x = (widget_w - pixmap_w) // 2
        offset_y = (widget_h - pixmap_h) // 2

        # Convert to pixmap coordinates (0 to pixmap size)
        px = int(pos.x() - offset_x)
        py = int(pos.y() - offset_y)

        if px < 0 or py < 0 or px >= pixmap_w or py >= pixmap_h:
            return

        # Convert pixmap coords to normalized coords (0 to 1) within the displayed image
        norm_x = px / pixmap_w
        norm_y = py / pixmap_h

        # The displayed image may be a cropped face region from the processed frame
        # We need to map back through the crop to get processed frame coordinates
        if self._display_crop is not None and self._processed_frame_size is not None:
            # Display shows cropped face region
            crop_x1, crop_y1, crop_x2, crop_y2 = self._display_crop
            crop_w = crop_x2 - crop_x1
            crop_h = crop_y2 - crop_y1
            # Map to processed frame coords (after mirror/zoom, before face crop)
            fx = int(crop_x1 + norm_x * crop_w)
            fy = int(crop_y1 + norm_y * crop_h)
            proc_h, proc_w = self._processed_frame_size
        elif self._processed_frame_size is not None:
            # No face crop - display shows full processed frame
            proc_h, proc_w = self._processed_frame_size
            fx = int(norm_x * proc_w)
            fy = int(norm_y * proc_h)
        else:
            # Fallback - use raw frame size
            frame_h, frame_w = self.last_raw_frame.shape[:2]
            fx = int(norm_x * frame_w)
            fy = int(norm_y * frame_h)
            proc_h, proc_w = frame_h, frame_w

        # Clamp to processed frame bounds
        fx = max(0, min(proc_w - 1, fx))
        fy = max(0, min(proc_h - 1, fy))

        # Initialize user masks if needed (sized to match processed frame, which equals raw frame after mirror)
        # The mask is applied before the face crop, so it needs to match the processed frame size
        if self.user_mask_additions is None or self.user_mask_additions.shape != (proc_h, proc_w):
            self.user_mask_additions = np.zeros((proc_h, proc_w), dtype=np.uint8)
        if self.user_mask_removals is None or self.user_mask_removals.shape != (proc_h, proc_w):
            self.user_mask_removals = np.zeros((proc_h, proc_w), dtype=np.uint8)

        # Paint a circle at the position
        brush = self.brush_size
        if add_mode:
            cv2.circle(self.user_mask_additions, (fx, fy), brush, 1, -1)
            cv2.circle(self.user_mask_removals, (fx, fy), brush, 0, -1)
        else:
            cv2.circle(self.user_mask_removals, (fx, fy), brush, 1, -1)
            cv2.circle(self.user_mask_additions, (fx, fy), brush, 0, -1)

        # Re-render with updated mask
        self._request_rerender()

    def mouseDoubleClickEvent(self, event):
        """Toggle freeze lock on double-tap."""
        if self.frozen_locked:
            # Unfreeze and reset pan and masks
            self.frozen_locked = False
            self.is_frozen = False
            self.pan_offset_x = 0.0
            self.pan_offset_y = 0.0
            self.user_mask_additions = None
            self.user_mask_removals = None
            self.mask_edit_mode = False
            self._display_crop = None
            self._processed_frame_size = None
            self._hide_frozen_overlay()
        else:
            # Lock frozen
            self.frozen_locked = True
            self.is_frozen = True
            self._show_frozen_overlay("Double-tap to unfreeze")
            self._request_rerender()  # Apply bg removal on freeze
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for panning and mask editing."""
        # Mask edit mode shortcuts
        if self.mask_edit_mode and self.frozen_locked:
            if event.key() == Qt.Key.Key_A:
                # Switch to Add mode
                self.mask_add_mode = True
                self._show_frozen_overlay(f"Mode: ADD  Brush: {self.brush_size}px  (Press E to erase)")
                return
            elif event.key() == Qt.Key.Key_E:
                # Switch to Erase/Remove mode
                self.mask_add_mode = False
                self._show_frozen_overlay(f"Mode: ERASE  Brush: {self.brush_size}px  (Press A to add)")
                return
            elif event.key() == Qt.Key.Key_BracketLeft:
                # Decrease brush size
                self.brush_size = max(5, self.brush_size - 5)
                mode = "ADD" if self.mask_add_mode else "ERASE"
                self._show_frozen_overlay(f"Mode: {mode}  Brush: {self.brush_size}px")
                return
            elif event.key() == Qt.Key.Key_BracketRight:
                # Increase brush size
                self.brush_size = min(100, self.brush_size + 5)
                mode = "ADD" if self.mask_add_mode else "ERASE"
                self._show_frozen_overlay(f"Mode: {mode}  Brush: {self.brush_size}px")
                return

        # Pan with arrow keys when frozen
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
                     brightness: int = 0, bg_removal: bool = False, bg_session=None):
        """Update the display with a new frame."""
        if frame is None:
            return

        # Store raw frame for re-rendering when frozen
        self.last_raw_frame = frame.copy()
        self.last_mirrored = mirrored
        self.last_bg_removal = bg_removal
        self.last_bg_session = bg_session

        self._render_frame(frame, mirrored, zoom, brightness, bg_removal, bg_session)

    def _render_frame(self, frame: np.ndarray, mirrored: bool, zoom: float, brightness: int,
                      bg_removal: bool = False, bg_session=None):
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

        # Apply background removal if enabled (using MediaPipe)
        if bg_removal and bg_session is not None:
            try:
                import mediapipe as mp
                # MediaPipe expects RGB input
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                result = bg_session.segment(mp_image)

                # Get confidence mask (float 0-1, higher = more likely person)
                # Use first confidence mask which is the person mask
                if result.confidence_masks:
                    mask = result.confidence_masks[0].numpy_view()
                    # Remove extra dimension if present
                    if mask.ndim == 3:
                        mask = mask[:, :, 0]
                    # Convert to binary mask (threshold at 0.5)
                    mask_binary = (mask > 0.5).astype(np.uint8)
                else:
                    # Fallback: use category mask
                    mask = result.category_mask.numpy_view()
                    if mask.ndim == 3:
                        mask = mask[:, :, 0]
                    mask_binary = (mask > 0).astype(np.uint8)

                # Use OpenCV face detection to find and crop to face
                h, w = frame_rgb.shape[:2]
                face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(50, 50))

                if len(faces) > 0:
                    # Use the largest face
                    face = max(faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw, fh = face

                    # Create an elliptical mask around just the face (no neck)
                    head_mask = np.zeros_like(mask_binary)
                    center_x = fx + fw // 2
                    # Center on face, shift up to focus on face not neck
                    center_y = fy + int(fh * 0.4)
                    # Ellipse sized to face only - width for ears, height for forehead to chin
                    axes_x = int(fw * 0.75)  # Width (face width)
                    axes_y = int(fh * 0.85)  # Height (forehead to chin)
                    cv2.ellipse(head_mask, (center_x, center_y), (axes_x, axes_y),
                               0, 0, 360, 1, -1)

                    # Intersect with person segmentation to get only head
                    mask_binary = mask_binary & head_mask

                # Apply user mask modifications (additions and removals)
                if self.user_mask_additions is not None:
                    # Ensure user mask matches frame size
                    if self.user_mask_additions.shape == mask_binary.shape:
                        mask_binary = mask_binary | self.user_mask_additions
                if self.user_mask_removals is not None:
                    if self.user_mask_removals.shape == mask_binary.shape:
                        mask_binary = mask_binary & ~self.user_mask_removals

                # Store processed frame size for coordinate mapping
                self._processed_frame_size = (h, w)

                # Crop if face was detected
                if len(faces) > 0:
                    # Crop to the ellipse bounds with padding
                    padding = 20  # Small padding for outline
                    face = max(faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw, fh = face
                    cx = fx + fw // 2
                    cy = fy + int(fh * 0.4)
                    ax = int(fw * 0.75)
                    ay = int(fh * 0.85)
                    crop_x1 = max(0, cx - ax - padding)
                    crop_y1 = max(0, cy - ay - padding)
                    crop_x2 = min(w, cx + ax + padding)
                    crop_y2 = min(h, cy + ay + padding)

                    # Store crop region for coordinate mapping in edit mode
                    self._display_crop = (crop_x1, crop_y1, crop_x2, crop_y2)

                    # Crop the image and mask
                    frame_rgb = frame_rgb[crop_y1:crop_y2, crop_x1:crop_x2]
                    mask_binary = mask_binary[crop_y1:crop_y2, crop_x1:crop_x2]
                    h, w = frame_rgb.shape[:2]
                else:
                    # No face crop - display shows full processed frame
                    self._display_crop = None

                # Smooth the mask edges for a cleaner outline
                mask_float = mask_binary.astype(np.float32)
                mask_float = cv2.GaussianBlur(mask_float, (7, 7), 2)
                mask_binary = (mask_float > 0.3).astype(np.uint8)

                # Create white outline for WhatsApp sticker
                # Dilate the mask to create outline area
                outline_width = 6  # pixels
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                   (outline_width * 2 + 1, outline_width * 2 + 1))
                dilated = cv2.dilate(mask_binary, kernel, iterations=1)

                # Smooth the dilated mask too for cleaner outline
                dilated_float = dilated.astype(np.float32)
                dilated_float = cv2.GaussianBlur(dilated_float, (5, 5), 1.5)
                dilated = (dilated_float > 0.3).astype(np.uint8)

                outline = dilated - mask_binary
                outline = np.clip(outline, 0, 1).astype(np.uint8)  # outline is the difference

                # Create RGBA image with transparent background
                frame_rgba = np.zeros((h, w, 4), dtype=np.uint8)

                # Set white color where outline is
                frame_rgba[:, :, 0] = np.where(outline > 0, 255, frame_rgb[:, :, 0])
                frame_rgba[:, :, 1] = np.where(outline > 0, 255, frame_rgb[:, :, 1])
                frame_rgba[:, :, 2] = np.where(outline > 0, 255, frame_rgb[:, :, 2])

                # Alpha: person + outline are visible
                alpha = (dilated * 255).astype(np.uint8)
                frame_rgba[:, :, 3] = alpha

                # Ensure contiguous array for QImage
                frame_rgba = np.ascontiguousarray(frame_rgba)
                bytes_per_line = 4 * w
                q_image = QImage(frame_rgba.data, w, h, bytes_per_line, QImage.Format_RGBA8888)
            except Exception as e:
                # Fallback to normal rendering if removal fails
                print(f"BG removal error: {e}")
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        else:
            # No background removal - clear crop info
            self._display_crop = None
            self._processed_frame_size = None
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Scale to fit widget while maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(q_image).scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)

    def rerender_frozen_frame(self, zoom: float, brightness: int,
                              bg_removal: bool = False, bg_session=None):
        """Re-render the frozen frame with new zoom/brightness settings."""
        if self.last_raw_frame is not None:
            self._render_frame(self.last_raw_frame.copy(), self.last_mirrored, zoom, brightness,
                             bg_removal, bg_session)


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
        self.bg_removal_enabled = False
        self.selfie_segmentation = None  # Lazy-loaded MediaPipe segmenter

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

        # Common icon button style
        icon_btn_style = """
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:checked {
                background-color: #0066cc;
            }
        """

        # Mirror toggle button
        self.mirror_btn = QPushButton("⇆")
        self.mirror_btn.setToolTip("Mirror (ON)")
        self.mirror_btn.setCheckable(True)
        self.mirror_btn.setChecked(True)
        self.mirror_btn.clicked.connect(self._toggle_mirror)
        self.mirror_btn.setStyleSheet(icon_btn_style)
        controls_layout.addWidget(self.mirror_btn)

        # Sticker mode toggle button
        self.bg_remove_btn = QPushButton("◐")
        self.bg_remove_btn.setToolTip("Sticker Mode (OFF)")
        self.bg_remove_btn.setCheckable(True)
        self.bg_remove_btn.setChecked(False)
        self.bg_remove_btn.clicked.connect(self._toggle_bg_removal)
        self.bg_remove_btn.setStyleSheet(icon_btn_style)
        controls_layout.addWidget(self.bg_remove_btn)

        # Mask edit button (for refining sticker outline)
        self.mask_edit_btn = QPushButton("✎")
        self.mask_edit_btn.setToolTip("Edit Mask")
        self.mask_edit_btn.setCheckable(True)
        self.mask_edit_btn.setChecked(False)
        self.mask_edit_btn.clicked.connect(self._toggle_mask_edit)
        self.mask_edit_btn.setStyleSheet(icon_btn_style.replace("#0066cc", "#cc6600"))
        controls_layout.addWidget(self.mask_edit_btn)

        # Export sticker button
        self.export_btn = QPushButton("↓")
        self.export_btn.setToolTip("Export Sticker as WebP")
        self.export_btn.clicked.connect(self._export_sticker)
        self.export_btn.setStyleSheet(icon_btn_style)
        controls_layout.addWidget(self.export_btn)

        # Fullscreen button
        fullscreen_btn = QPushButton("▢")
        fullscreen_btn.setToolTip("Fullscreen")
        fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        fullscreen_btn.setStyleSheet(icon_btn_style)
        controls_layout.addWidget(fullscreen_btn)

        # About button
        about_btn = QPushButton("?")
        about_btn.setToolTip("About")
        about_btn.clicked.connect(self._show_about)
        about_btn.setStyleSheet(icon_btn_style)
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
            # Reset mask edit button if it was enabled
            if self.mask_edit_btn.isChecked():
                self.mask_edit_btn.setChecked(False)
                self.mask_edit_btn.setToolTip("Edit Mask")
            # Background removal only applies when frozen, not in live preview
            self.camera_widget.update_frame(frame, self.is_mirrored, self.zoom_level,
                                            self.brightness, False, None)

    def _rerender_frozen(self):
        """Re-render the frozen frame (called by CameraWidget for pan updates)."""
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness,
                                                     self.bg_removal_enabled, self.selfie_segmentation)

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
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness,
                                                     self.bg_removal_enabled, self.selfie_segmentation)

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
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness,
                                                     self.bg_removal_enabled, self.selfie_segmentation)

    def _on_brightness_changed(self, value):
        """Handle brightness slider change."""
        self.brightness = value
        self.brightness_label.setText(str(value))
        # Re-render if frozen
        if self.camera_widget.is_frozen:
            self.camera_widget.rerender_frozen_frame(self.zoom_level, self.brightness,
                                                     self.bg_removal_enabled, self.selfie_segmentation)

    def _toggle_mirror(self):
        """Toggle mirror mode."""
        self.is_mirrored = not self.is_mirrored
        self.mirror_btn.setChecked(self.is_mirrored)
        self.mirror_btn.setToolTip(f"Mirror ({'ON' if self.is_mirrored else 'OFF'})")

    def _toggle_bg_removal(self):
        """Toggle sticker mode (background removal)."""
        self.bg_removal_enabled = not self.bg_removal_enabled
        self.bg_remove_btn.setChecked(self.bg_removal_enabled)
        self.bg_remove_btn.setToolTip(f"Sticker Mode ({'ON' if self.bg_removal_enabled else 'OFF'})")
        # Lazy load MediaPipe on first enable
        if self.bg_removal_enabled and self.selfie_segmentation is None:
            try:
                self._init_segmenter()
            except Exception as e:
                QMessageBox.warning(self, "Sticker Mode",
                    f"Failed to load MediaPipe:\n{e}")
                self.bg_removal_enabled = False
                self.bg_remove_btn.setChecked(False)
                self.bg_remove_btn.setToolTip("Sticker Mode (OFF)")

    def _toggle_mask_edit(self):
        """Toggle mask editing mode."""
        if not self.camera_widget.frozen_locked:
            QMessageBox.information(self, "Edit Mask",
                "Double-click to freeze the frame first, then enable Edit Mask.\n\n"
                "Controls:\n"
                "• Click/drag to paint\n"
                "• A = Add mode, E = Erase mode\n"
                "• [ / ] = Brush size\n"
                "• Scroll = Brush size\n"
                "• Double-click = Done")
            self.mask_edit_btn.setChecked(False)
            return

        self.camera_widget.mask_edit_mode = not self.camera_widget.mask_edit_mode
        self.mask_edit_btn.setChecked(self.camera_widget.mask_edit_mode)

        if self.camera_widget.mask_edit_mode:
            self.mask_edit_btn.setToolTip("Edit Mask (ON)")
            # Show instruction overlay
            mode = "ADD" if self.camera_widget.mask_add_mode else "ERASE"
            self.camera_widget._show_frozen_overlay(f"Mode: {mode}  A=Add E=Erase  [/]=Size")
        else:
            self.mask_edit_btn.setToolTip("Edit Mask")
            self.camera_widget._show_frozen_overlay("Double-tap to unfreeze")

    def _init_segmenter(self):
        """Initialize MediaPipe Image Segmenter."""
        import mediapipe as mp
        import os
        import urllib.request

        # Download model if needed
        model_path = os.path.join(os.path.dirname(__file__), "selfie_segmenter.tflite")
        if not os.path.exists(model_path):
            url = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
            urllib.request.urlretrieve(url, model_path)

        base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
        options = mp.tasks.vision.ImageSegmenterOptions(
            base_options=base_options,
            output_category_mask=False,
            output_confidence_masks=True
        )
        self.selfie_segmentation = mp.tasks.vision.ImageSegmenter.create_from_options(options)

    def _export_sticker(self):
        """Export the current sticker as a WebP file for WhatsApp."""
        if not self.camera_widget.frozen_locked:
            QMessageBox.information(self, "Export Sticker",
                "Double-click to freeze the frame first, then export.")
            return

        if not self.bg_removal_enabled:
            QMessageBox.warning(self, "Export Sticker",
                "Enable Sticker mode (◐) first to create a sticker with transparent background.")
            return

        # Get the current displayed pixmap
        pixmap = self.camera_widget.pixmap()
        if pixmap is None:
            QMessageBox.warning(self, "Export Sticker", "No image to export.")
            return

        # Convert to QImage
        image = pixmap.toImage()
        if image.isNull():
            QMessageBox.warning(self, "Export Sticker", "Failed to get image.")
            return

        # WhatsApp sticker requirements: 512x512 pixels, WebP format, <500KB
        # Scale to 512x512 while maintaining aspect ratio
        scaled = image.scaled(512, 512, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Create a 512x512 transparent canvas and center the image
        final = QImage(512, 512, QImage.Format_ARGB32)
        final.fill(Qt.transparent)
        painter = QPainter(final)
        x = (512 - scaled.width()) // 2
        y = (512 - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
        painter.end()

        # Ask user for save location
        from datetime import datetime
        default_name = f"sticker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webp"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Sticker", default_name,
            "WebP Image (*.webp)"
        )

        if not file_path:
            return  # User cancelled

        # Ensure .webp extension
        if not file_path.lower().endswith('.webp'):
            file_path += '.webp'

        # Save as WebP with quality setting to keep under 500KB
        # Start with high quality and reduce if needed
        quality = 90
        while quality >= 10:
            if final.save(file_path, "WEBP", quality):
                import os
                size = os.path.getsize(file_path)
                if size <= 500 * 1024:  # 500KB limit
                    QMessageBox.information(self, "Export Sticker",
                        f"Sticker saved successfully!\n\n"
                        f"File: {file_path}\n"
                        f"Size: {size // 1024}KB")
                    return
                quality -= 10
            else:
                break

        QMessageBox.warning(self, "Export Sticker",
            f"Failed to save sticker to:\n{file_path}")

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
        self.mirror_btn.setToolTip(f"Mirror ({'ON' if self.is_mirrored else 'OFF'})")

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

        # Sticker mode (background removal)
        bg_removal_val = self.settings.value("bg_removal", False)
        self.bg_removal_enabled = bg_removal_val in (True, "true", "True", 1)
        self.bg_remove_btn.setChecked(self.bg_removal_enabled)
        self.bg_remove_btn.setToolTip(f"Sticker Mode ({'ON' if self.bg_removal_enabled else 'OFF'})")
        # Load MediaPipe if enabled
        if self.bg_removal_enabled and self.selfie_segmentation is None:
            try:
                self._init_segmenter()
            except Exception:
                self.bg_removal_enabled = False
                self.bg_remove_btn.setChecked(False)
                self.bg_remove_btn.setToolTip("Sticker Mode (OFF)")

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
        self.settings.setValue("bg_removal", self.bg_removal_enabled)
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
