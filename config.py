"""
Project configuration.

Edit these values to configure the robot without
modifying the main source files.
"""

# -------------------------
# Flask
# -------------------------

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000

# -------------------------
# Camera
# -------------------------

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
JPEG_QUALITY = 75

# -------------------------
# YOLO
# -------------------------

YOLO_MODEL = "yolo11n.pt"
YOLO_IMAGE_SIZE = 320
YOLO_CONFIDENCE = 0.45

# -------------------------
# Robot Following
# -------------------------

CENTER_DEADBAND = 0.05
FOLLOW_SPEED = 25
TURN_GAIN = 0.8
STOP_BOX_WIDTH = 260

# -------------------------
# Obstacle Avoidance
# -------------------------

STOP_DISTANCE_CM = 25
TURN_SPEED = 20
