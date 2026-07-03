from camera_api import CameraConfig

CAMERA_CONFIGS = {
    "top_realsense_color": CameraConfig(
        index_or_path='/dev/top_realsense_color',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG",  # Realsense RGB stream is usually YUYV by default, which is slow to capture with OpenCV. MJPG is much faster.
    ),
    "top_realsense_depth": CameraConfig(
        index_or_path='/dev/top_realsense_depth',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "overhead_realsense": CameraConfig(
        index_or_path='/dev/overhead_realsense',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG",  # Realsense RGB stream is usually YUYV by default, which is slow to capture with OpenCV. MJPG is much faster.
    ),
    "top_webcam": CameraConfig(
        index_or_path='/dev/top_webcam',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "wrist_right": CameraConfig(
        index_or_path='/dev/wrist_right',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
    "wrist_left": CameraConfig(
        index_or_path='/dev/wrist_left',
        fps=30,
        width=640,
        height=480,
        fourcc="MJPG"
    ),
}