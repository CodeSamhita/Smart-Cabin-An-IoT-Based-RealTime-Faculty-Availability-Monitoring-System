# A small web server (Python's built-in http.server, nothing to install).
#   /              -> web page showing the live video
#   /stream.mjpg   -> the live video (MJPEG: a never-ending series of JPEG pictures)
#   /snapshot.jpg  -> one picture (the laptop can use this later for YOLO headcount)

import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import camera
import config

PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Smart Cabin Camera</title>
  <style>
    body { margin: 0; padding: 16px; font-family: sans-serif; background: #f4f4f4; text-align: center; }
    img { max-width: 100%; border-radius: 8px; background: #000; }
  </style>
</head>
<body>
  <h2>Smart Cabin - Live Camera</h2>
  <img src="/stream.mjpg" alt="Live camera">
  <p><a href="/snapshot.jpg">Take one snapshot</a></p>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            send_page(self)
        elif self.path == "/stream.mjpg":
            send_stream(self)
        elif self.path == "/snapshot.jpg":
            send_snapshot(self)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # Don't print a line for every request (the stream makes a lot of them)
        pass


def send_page(handler):
    body = PAGE.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_snapshot(handler):
    jpeg = camera.get_jpeg()
    if jpeg is None:
        handler.send_error(503, "Camera not ready")
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "image/jpeg")
    handler.send_header("Content-Length", str(len(jpeg)))
    handler.end_headers()
    handler.wfile.write(jpeg)


def send_stream(handler):
    # Keep sending the newest picture, each one separated by "--frame"
    handler.send_response(200)
    handler.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    print("Viewer connected:", handler.client_address[0])
    try:
        while True:
            jpeg = camera.get_jpeg()
            if jpeg is not None:
                handler.wfile.write(b"--frame\r\n")
                handler.wfile.write(b"Content-Type: image/jpeg\r\n")
                handler.wfile.write(b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n")
                handler.wfile.write(jpeg)
                handler.wfile.write(b"\r\n")
            time.sleep(1 / config.FPS)
    except (BrokenPipeError, ConnectionResetError):
        print("Viewer left:", handler.client_address[0])


def run_server():
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    print("Stream running. Open http://localhost:" + str(config.PORT) + " (see pi/README.md)")
    server.serve_forever()
