# Custom Camera API

## Overview

The **camera_api** module provides a standalone OpenCV wrapper for multi-camera frame acquisition that's independent of LeRobot or any specific dataset system. It provides non-blocking, background-threaded camera access with a clean, minimal API.

### Key Features

- **Non-blocking frame capture** via background thread
- **Compatible format** - frames returned as BGR numpy arrays, ready for RGB conversion and tensor wrapping
- **Simple lifecycle** - `connect()` / `disconnect()`
- **Multi-camera support** - easily manage multiple cameras simultaneously
- **LeRobot compatible** - seamless integration with LeRobotDataset but not dependent on it

## Installation

Just copy `camera_api.py` into your project:

```bash
# Already in /home/kibub/bimanual_teleop/parallel_teleop/camera_api.py
```

### Dependencies

```
opencv-python
numpy
```

## Quick Start

### Single Camera

```python
from camera_api import Camera, CameraConfig

# Create config
config = CameraConfig(
    index_or_path='/dev/video0',  # or integer: 0
    fps=30,
    width=640,
    height=480,
)

# Create and connect
camera = Camera(config)
camera.connect()

# Capture frame (non-blocking)
frame = camera.async_read(timeout_ms=200)  # np.ndarray (H, W, 3) BGR

# Cleanup
camera.disconnect()
```

### Multiple Cameras

```python
from camera_api import Camera, CameraConfig
import torch

# Define configs
configs = {
    "top": CameraConfig(index_or_path=0, fps=30, width=640, height=480),
    "wrist": CameraConfig(index_or_path=2, fps=30, width=640, height=480),
}

# Connect all
cameras = {}
for name, cfg in configs.items():
    cam = Camera(cfg)
    cam.connect()
    cameras[name] = cam

# Capture from all
frames = {}
for name, cam in cameras.items():
    frame = cam.async_read(timeout_ms=200)
    if frame is not None:
        frame_rgb = frame[..., ::-1].copy()  # BGR → RGB
        frames[name] = torch.from_numpy(frame_rgb)

# Cleanup
for cam in cameras.values():
    cam.disconnect()
```

## API Reference

### CameraConfig

Configuration dataclass for a single camera.

```python
@dataclass
class CameraConfig:
    index_or_path: str          # Device index or path ('/dev/video0')
    fps: int = 30               # Target frames per second
    width: int = 640            # Frame width in pixels
    height: int = 480           # Frame height in pixels
```

### Camera

Main camera class for frame acquisition.

#### `Camera(config: CameraConfig)`

Initialize camera with config. Does not connect immediately.

#### `connect()`

Open camera device and start background frame acquisition thread.

**Raises:** `RuntimeError` if device cannot be opened or already connected.

#### `disconnect()`

Stop background thread and release camera resources.

#### `async_read(timeout_ms: int = 200) -> Optional[np.ndarray]`

Non-blocking frame read. Returns the latest frame captured by the background thread.

**Parameters:**
- `timeout_ms` (int): Max wait time in milliseconds for frame availability

**Returns:**
- `np.ndarray` with shape `(height, width, 3)` in BGR format, or `None` on timeout

**Note:** This is the preferred method during recording loops.

#### `read() -> Optional[np.ndarray]`

Blocking frame read. Waits up to 5 seconds for a frame.

**Returns:**
- `np.ndarray` with shape `(height, width, 3)` in BGR format, or `None` on timeout

## Integration with LeRobotDataset

### Pattern: Attach Custom Camera Data to Dataset

```python
from camera_api import Camera, CameraConfig
from lerobot.datasets import LeRobotDataset
import torch

# 1. Create dataset with image features
dataset = LeRobotDataset.create(
    repo_id="your-org/your-dataset",
    fps=30,
    features={
        "observation.images.top": {
            "dtype": "video",
            "shape": (480, 640, 3),
            "names": ["height", "width", "channel"],
        },
        "observation.images.wrist": {
            "dtype": "video",
            "shape": (480, 640, 3),
            "names": ["height", "width", "channel"],
        },
        # ... other features
    },
    use_videos=True,
    image_writer_threads=2,
)

# 2. Setup cameras with custom API
cameras = {
    "top": Camera(CameraConfig(index_or_path=0, fps=30, width=640, height=480)),
    "wrist": Camera(CameraConfig(index_or_path=2, fps=30, width=640, height=480)),
}
for cam in cameras.values():
    cam.connect()

# 3. In recording loop
while recording:
    # Capture frames
    frame_data = {
        "observation.state": state_tensor,
        "action": action_tensor,
    }
    
    for cam_name, cam in cameras.items():
        frame = cam.async_read(timeout_ms=200)
        if frame is not None:
            frame_rgb = frame[..., ::-1].copy()  # BGR → RGB
            frame_data[f"observation.images.{cam_name}"] = torch.from_numpy(frame_rgb)
    
    # Attach to dataset
    dataset.add_frame(frame_data)

# 4. Cleanup
for cam in cameras.values():
    cam.disconnect()
```

## Why Separate from LeRobot?

The custom `camera_api` module provides:

1. **Independence** - Use camera acquisition without LeRobot dependencies
2. **Control** - Full control over frame acquisition pipeline
3. **Reusability** - Compatible format (BGR numpy arrays) works with any dataset system
4. **Testing** - Easier to test camera logic in isolation
5. **Modularity** - Cleanly separates camera concern from robot/dataset concerns

## Current Usage in Record Script

`record_dual_with_cameras.py` uses the custom camera API:

```python
# Old (LeRobot dependency):
# from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig

# New (custom API):
from camera_api import Camera, CameraConfig

# Camera configs use CameraConfig
CAMERA_CONFIGS = {
    "top_realsense_color": CameraConfig(
        index_or_path='/dev/video4',
        fps=30,
        width=640,
        height=480,
    ),
    # ...
}

# make_cameras() uses Camera
cameras = {}
for name, cfg in CAMERA_CONFIGS.items():
    cam = Camera(cfg)
    cam.connect()
    cameras[name] = cam
```

## Debugging

### Finding Camera Devices

```bash
# Linux
ls /dev/video*

# List detailed camera info
v4l2-ctl --list-devices

# Check a specific camera
v4l2-ctl -d /dev/video0 --list-formats-ext
```

### Common Issues

**RuntimeError: Failed to open camera**
- Verify device exists: `ls /dev/video0`
- Check permissions: `ls -la /dev/video0`
- Ensure camera isn't in use by another process

**Timeouts (None returned)**
- Increase `timeout_ms` in `async_read()`
- Check camera fps matches config
- Verify camera is capturing (test with `ffplay /dev/video0`)

**Frame format issues**
- Frames are always BGR from OpenCV
- Convert to RGB before passing to dataset: `frame[..., ::-1].copy()`
- Check tensor shape and dtype match dataset features

## Examples

See [camera_api_example.py](camera_api_example.py) for runnable examples:

```bash
python camera_api_example.py
```

Examples include:
- Single camera capture
- Multiple cameras
- Dataset integration pattern
