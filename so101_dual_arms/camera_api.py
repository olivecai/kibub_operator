"""
Custom OpenCV Camera API
========================
Standalone camera acquisition module for multi-camera data collection.
Provides non-blocking frame capture compatible with LeRobot dataset format.

Usage
-----
    from camera_api import CameraConfig, Camera

    # Create camera configs
    config = CameraConfig(
        index_or_path='/dev/video0',
        fps=30,
        width=640,
        height=480,
    )

    # Instantiate and connect
    cam = Camera(config)
    cam.connect()

    # Async frame capture (non-blocking)
    frame = cam.async_read(timeout_ms=200)  # Returns np.ndarray (H, W, 3) BGR

    # Cleanup
    cam.disconnect()
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2


@dataclass
class CameraConfig:
    """Configuration for OpenCV camera."""
    index_or_path: str
    """Camera index (int as string or str path like '/dev/video0')"""
    
    fps: int = 30
    """Target frames per second"""
    
    width: int = 640
    """Frame width in pixels"""
    
    height: int = 480
    """Frame height in pixels"""

    fourcc: str = "MJPG"
    """FourCC codec for video capture"""


class Camera:
    """
    Non-blocking OpenCV camera wrapper with background frame acquisition.
    
    Frames are captured in a background thread to avoid blocking the main
    loop. Provides non-blocking read access to the latest captured frame.
    """

    def __init__(self, config: CameraConfig):
        """
        Initialize camera with config.
        
        Parameters
        ----------
        config : CameraConfig
            Camera configuration (device path, resolution, fps)
        """
        self.config = config
        self.cap = None
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()

    def connect(self):
        """
        Open camera and start background frame acquisition thread.
        
        Raises
        ------
        RuntimeError
            If camera cannot be opened or is already connected
        """
        if self.cap is not None:
            raise RuntimeError("Camera already connected")

        # Parse index (handle both int strings and device paths)
        try:
            # Try as integer index first
            index = int(self.config.index_or_path)
        except (ValueError, TypeError):
            # Otherwise treat as device path (string)
            index = self.config.index_or_path

        # Open camera
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            self.cap = None
            raise RuntimeError(
                f"Failed to open camera: {self.config.index_or_path}"
            )

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)

        # Set FPS
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        # Set FourCC codec
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.config.fourcc))

        # Start background capture thread
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def disconnect(self):
        """Stop background thread and release camera."""
        self._running = False
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=2.0)

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self._latest_frame = None

    def _capture_loop(self):
        """Background thread: continuously grab frames from camera."""
        while self._running and not self._stop_event.is_set():
            ret, frame = self.cap.read()
            if ret:
                with self._frame_lock:
                    # Ensure correct shape and type
                    if frame.shape != (self.config.height, self.config.width, 3):
                        frame = cv2.resize(frame, (self.config.width, self.config.height))
                    self._latest_frame = frame.copy()
            else:
                # Camera read failed, try reconnecting or skip
                time.sleep(0.01)

    def async_read(self, timeout_ms: int = 200) -> Optional[np.ndarray]:
        """
        Non-blocking read of the latest captured frame.
        
        Returns the most recent frame captured by the background thread.
        If no frame has been captured yet, waits up to timeout_ms.
        
        Parameters
        ----------
        timeout_ms : int
            Maximum wait time in milliseconds for frame availability
            
        Returns
        -------
        np.ndarray or None
            Frame as (H, W, 3) BGR numpy array, or None if timeout exceeded
        """
        timeout_s = timeout_ms / 1000.0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < timeout_s:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.copy()
            time.sleep(0.001)

        # Return last known frame or None
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

    def read(self) -> Optional[np.ndarray]:
        """
        Blocking read of the next frame.
        
        Waits until a frame is available (up to 5 seconds).
        
        Returns
        -------
        np.ndarray or None
            Frame as (H, W, 3) BGR numpy array, or None if timeout exceeded
        """
        return self.async_read(timeout_ms=5000)
