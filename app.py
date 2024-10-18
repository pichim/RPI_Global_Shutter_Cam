import time
import threading

from flask import Flask, Response
from picamera2 import Picamera2
import cv2

app = Flask(__name__)

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
# picam2.configure(picam2.create_video_configuration(main={"size": (1440, 1080)}))

# picam2.set_controls({
#     "ExposureTime": 5000,
#     "AnalogueGain": 10.0,
#     "NoiseReductionMode": 0  # Turn off noise reduction
# })

# Set controls automatically
picam2.set_controls({})

# Force noise rexution off (should increase performance)
picam2.set_controls({
    "NoiseReductionMode": 0  # Turn off noise reduction
})

# picam2.set_controls({
#     "FrameDurationLimits": (55, 65),  # Targeting 500 fps (if supported)
# })
picam2.set_controls({
    "FrameDurationLimits": (2000, 2000),  # Targeting 500 fps (if supported)
})

picam2.start()

# Global variable to store FPS
fps = 0.0
fps_lock = threading.Lock()

def gen_frames():
    global fps
    frame_counter = 0
    start_time = time.time()
    while True:
        frame = picam2.capture_array()
        # Convert from RGB to BGR for OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Calculate FPS
        frame_counter += 1
        elapsed_time = time.time() - start_time
        if elapsed_time >= 1.0:
            with fps_lock:
                fps = frame_counter / elapsed_time
            frame_counter = 0
            start_time = time.time()

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# New route to provide FPS value
@app.route('/fps')
def get_fps():
    with fps_lock:
        current_fps = fps
    return f"{current_fps:.2f}"

@app.route('/')
def index():
    return '''
    <html>
        <head>
            <title>Live Stream</title>
            <style>
                body { font-family: Arial, sans-serif; }
                #fps { font-size: 1.2em; color: black; margin-top: 10px; }
            </style>
        </head>
        <body>
            <h1>Live Stream</h1>
            <img src="/video_feed">
            <div id="fps">FPS: Calculating...</div>
            <script>
                function fetchFPS() {
                    fetch('/fps')
                        .then(response => response.text())
                        .then(data => {
                            document.getElementById('fps').innerText = 'FPS: ' + data;
                        })
                        .catch(error => console.error('Error fetching FPS:', error));
                }
                // Fetch FPS every second
                setInterval(fetchFPS, 1000);
                // Fetch FPS on page load
                fetchFPS();
            </script>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
