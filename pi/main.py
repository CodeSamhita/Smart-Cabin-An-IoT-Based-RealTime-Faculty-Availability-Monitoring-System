# Smart Cabin - Raspberry Pi camera stream.
# Run on the Pi:  python3 main.py   then open the page from the laptop (see README.md).

import camera
import stream_server


def main():
    camera.start_camera()
    try:
        stream_server.run_server()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
