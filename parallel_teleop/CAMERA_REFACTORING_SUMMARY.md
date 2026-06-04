# Camera API Refactoring - Summary

## What Changed

### Before
`record_dual_with_cameras.py` used LeRobot's built-in camera module:
```python
from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig

# Used LeRobot's camera classes directly
cam = OpenCVCamera(OpenCVCameraConfig(...))
```

### After
`record_dual_with_cameras.py` now uses a custom standalone camera API:
```python
from camera_api import Camera, CameraConfig

# Uses custom camera API
cam = Camera(CameraConfig(...))
```

## New Files Created

1. **camera_api.py** (150 lines)
   - Standalone OpenCV camera wrapper
   - Classes: `CameraConfig`, `Camera`
   - Non-blocking background frame capture
   - Compatible with LeRobot dataset format

2. **camera_api_example.py** (250+ lines)
   - Example usage patterns
   - Single and multi-camera examples
   - Dataset integration pattern
   - Run with: `python camera_api_example.py`

3. **CAMERA_API.md** (comprehensive documentation)
   - API reference
   - Integration patterns
   - Debugging guide
   - Device discovery instructions

## Key Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Dependency** | LeRobot (large, multi-purpose) | Standalone module (just camera logic) |
| **Reusability** | Tied to LeRobot ecosystem | Can use with any dataset system |
| **Control** | Limited customization | Full control over frame pipeline |
| **Testing** | Must test through LeRobot | Can test camera independently |
| **Frame Format** | Same (BGR numpy arrays) | Same (BGR numpy arrays) |
| **API Compatibility** | LeRobot-specific methods | Clean, generic async/sync interface |

## API Comparison

### Connection
```python
# Old (LeRobot)
cam = OpenCVCamera(OpenCVCameraConfig(...))
cam.connect()

# New (custom)
cam = Camera(CameraConfig(...))
cam.connect()
```

### Frame Capture (identical interface)
```python
# Both:
frame = cam.async_read(timeout_ms=200)  # Non-blocking
frame = cam.read()                       # Blocking
```

### Cleanup (identical)
```python
# Both:
cam.disconnect()
```

## Record Script Changes

### Imports
```diff
- from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
+ from camera_api import Camera, CameraConfig
```

### Camera Config
```diff
- "top": OpenCVCameraConfig(...)
+ "top": CameraConfig(...)
```

### Camera Instantiation
```diff
- cam = OpenCVCamera(cfg)
+ cam = Camera(cfg)
```

### Everything Else
✓ `make_cameras()` function remains unchanged  
✓ Frame capture loop unchanged (async_read interface identical)  
✓ Dataset attachment unchanged  
✓ BGR→RGB conversion unchanged  
✓ Torch tensor wrapping unchanged  

## Usage Example

### In Your Recording Loop
```python
from camera_api import Camera, CameraConfig
import torch

# Create cameras
cameras = {
    "top": Camera(CameraConfig(index_or_path='/dev/video0', fps=30, width=640, height=480)),
    "wrist": Camera(CameraConfig(index_or_path='/dev/video2', fps=30, width=640, height=480)),
}

# Connect all
for cam in cameras.values():
    cam.connect()

# Record loop
while recording:
    frame_data = {}
    
    # Capture from each camera
    for cam_name, cam in cameras.items():
        frame = cam.async_read(timeout_ms=200)  # Non-blocking
        if frame is not None:
            frame_rgb = frame[..., ::-1].copy()  # BGR → RGB
            frame_data[f"observation.images.{cam_name}"] = torch.from_numpy(frame_rgb)
    
    # Attach to dataset
    dataset.add_frame(frame_data)

# Cleanup
for cam in cameras.values():
    cam.disconnect()
```

## Testing

### Verify Syntax
```bash
python -m py_compile camera_api.py
python -m py_compile record_dual_with_cameras.py
```

### Run Examples
```bash
python camera_api_example.py
```

### List Available Cameras
```bash
ls /dev/video*
v4l2-ctl --list-devices
```

## Next Steps

1. Update camera device paths in `CAMERA_CONFIGS` if needed
2. Test frame capture: `python camera_api_example.py`
3. Run recording script normally: `python record_dual_with_cameras.py --repo-id ... --task ...`
4. Frames are captured and attached to dataset identically to before

## Backward Compatibility

✓ **Recording output unchanged** - same frame format, same dataset structure  
✓ **API interface unchanged** - `async_read()` works exactly the same  
✓ **Dataset attachment unchanged** - frames go into dataset the same way  
✓ **No breaking changes** to record script beyond imports  

## Architecture

```
record_dual_with_cameras.py
    ├── imports Camera & CameraConfig
    ├── defines CAMERA_CONFIGS
    ├── calls make_cameras()
    │   └── instantiates Camera objects
    ├── recording loop
    │   ├── captures frames via camera.async_read()
    │   ├── converts BGR → RGB
    │   ├── wraps in torch.Tensor
    │   └── attaches to dataset
    └── cleanup
        └── camera.disconnect()

camera_api.py (NEW)
    ├── CameraConfig dataclass
    └── Camera class
        ├── OpenCV wrapper
        ├── Background frame thread
        ├── async_read() → non-blocking
        └── read() → blocking
```

## Questions?

Refer to [CAMERA_API.md](CAMERA_API.md) for detailed documentation and debugging guides.
