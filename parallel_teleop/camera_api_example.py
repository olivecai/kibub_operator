"""
Example: Using the Custom Camera API Independently
===================================================

This demonstrates how to use the camera_api module as a standalone
OpenCV wrapper for multi-camera frame acquisition, independent of
LeRobot or any dataset system.

The camera_api provides:
- Non-blocking frame acquisition in a background thread
- Compatible frame format (BGR numpy arrays) for dataset integration
- Simple connect/disconnect lifecycle
"""

import numpy as np
import torch
from camera_api import Camera, CameraConfig


def example_single_camera():
    """Example: Capture from a single camera."""
    print("=" * 60)
    print("Single Camera Example")
    print("=" * 60)

    # Define camera config
    config = CameraConfig(
        index_or_path='/dev/video0',  # or integer index: 0
        fps=30,
        width=640,
        height=480,
    )

    # Create and connect camera
    camera = Camera(config)
    camera.connect()

    # Capture 10 frames
    for i in range(10):
        frame = camera.async_read(timeout_ms=200)  # Non-blocking
        if frame is not None:
            print(f"Frame {i}: shape={frame.shape}, dtype={frame.dtype}, "
                  f"format=BGR")
            # Convert BGR to RGB for dataset
            frame_rgb = frame[..., ::-1].copy()
            # Convert to torch tensor for dataset storage
            frame_tensor = torch.from_numpy(frame_rgb)
            print(f"  → Tensor shape: {frame_tensor.shape}, dtype={frame_tensor.dtype}")
        else:
            print(f"Frame {i}: timeout (no frame available)")

    camera.disconnect()
    print()


def example_multiple_cameras():
    """Example: Capture from multiple cameras simultaneously."""
    print("=" * 60)
    print("Multiple Cameras Example")
    print("=" * 60)

    # Define multiple cameras
    camera_configs = {
        "top_camera": CameraConfig(
            index_or_path=0,
            fps=30,
            width=640,
            height=480,
        ),
        "wrist_camera": CameraConfig(
            index_or_path=2,
            fps=30,
            width=320,
            height=240,
        ),
    }

    # Connect all cameras
    cameras = {}
    for name, cfg in camera_configs.items():
        try:
            print(f"Connecting to {name}...")
            cam = Camera(cfg)
            cam.connect()
            cameras[name] = cam
            print(f"  ✓ {name} connected")
        except RuntimeError as e:
            print(f"  ✗ {name} failed: {e}")

    # Capture one frame from each
    print("\nCapturing frames...")
    frame_data = {}
    for name, cam in cameras.items():
        frame = cam.async_read(timeout_ms=500)
        if frame is not None:
            frame_rgb = frame[..., ::-1].copy()  # BGR → RGB
            frame_tensor = torch.from_numpy(frame_rgb)
            frame_data[f"observation.images.{name}"] = frame_tensor
            print(f"  {name}: {frame_tensor.shape}")

    # Cleanup
    print("\nDisconnecting cameras...")
    for name, cam in cameras.items():
        cam.disconnect()
        print(f"  ✓ {name} disconnected")

    print("\nFrame data keys ready for dataset:")
    for key in frame_data.keys():
        print(f"  - {key}")
    print()


def example_dataset_integration():
    """
    Example: How camera_api integrates with dataset.

    This shows the workflow for attaching custom camera acquisition
    to a LeRobot dataset.
    """
    print("=" * 60)
    print("Dataset Integration Pattern")
    print("=" * 60)

    # 1. Define cameras
    camera_configs = {
        "top": CameraConfig(index_or_path=0, fps=30, width=640, height=480),
        "wrist": CameraConfig(index_or_path=2, fps=30, width=320, height=240),
    }

    # 2. Connect all cameras
    cameras = {}
    for name, cfg in camera_configs.items():
        cam = Camera(cfg)
        cam.connect()
        cameras[name] = cam

    # 3. In your recording loop:
    print("\nSimulating recording loop (3 iterations)...")
    for frame_idx in range(3):
        # Capture from all cameras
        frame_data = {}
        for cam_name, cam in cameras.items():
            frame = cam.async_read(timeout_ms=200)
            if frame is not None:
                frame_rgb = frame[..., ::-1].copy()  # BGR → RGB
                frame_tensor = torch.from_numpy(frame_rgb)
                frame_data[f"observation.images.{cam_name}"] = frame_tensor
                print(f"  Frame {frame_idx}, {cam_name}: captured")

        # 4. Add to dataset
        # dataset.add_frame(frame_data)  # In real usage

    # 5. Cleanup
    print("\nCleaning up...")
    for cam in cameras.values():
        cam.disconnect()
    print("Done.\n")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║  Camera API - Standalone Usage Examples                  ║")
    print("╚" + "=" * 58 + "╝")
    print()

    # NOTE: These examples assume /dev/video0 and /dev/video2 exist.
    # Adjust indices/paths to match your system: ls /dev/video*

    try:
        example_single_camera()
    except RuntimeError as e:
        print(f"Single camera example failed: {e}")
        print("  (Ensure camera device exists)\n")

    try:
        example_multiple_cameras()
    except RuntimeError as e:
        print(f"Multiple cameras example failed: {e}")
        print("  (Ensure camera devices exist)\n")

    example_dataset_integration()

    print("✓ Examples complete")
