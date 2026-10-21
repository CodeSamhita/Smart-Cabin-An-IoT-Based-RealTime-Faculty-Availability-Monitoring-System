# Settings for the Raspberry Pi camera stream. Change values here, not in the other files.

# "pi" = ribbon-cable Pi Camera (uses picamera2)
# "usb" = USB webcam (uses OpenCV)
CAMERA_TYPE = "pi"

# Picture size and speed. Keep these small: the Pi Zero 2W is slow.
WIDTH = 640
HEIGHT = 480
FPS = 10
JPEG_QUALITY = 80

# Web server. 0.0.0.0 means "accept connections from other computers too", not only the Pi itself.
HOST = "0.0.0.0"
PORT = 8000
