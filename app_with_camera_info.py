from flask import Flask, Response, jsonify
from picamera2 import Picamera2
import cv2
import time
import threading
import json
import numbers

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
#     "FrameDurationLimits": (2000, 2000),  # Targeting 500 fps (if supported)
# })

picam2.start()

# Global variables to store FPS and configurations
fps = 0.0

# Lock for thread safety
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

@app.route('/stats')
def stats():
    with fps_lock:
        current_fps = fps
    # Get camera controls and configuration
    controls = picam2.controls
    config = picam2.camera_config

    # Function to serialize non-serializable objects
    def serialize(obj):
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        elif isinstance(obj, list):
            return [serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: serialize(value) for key, value in obj.items()}
        elif isinstance(obj, tuple):
            return tuple(serialize(item) for item in obj)
        elif isinstance(obj, numbers.Number):
            return obj
        else:
            return str(obj)

    # Serialize controls and configuration
    controls_serializable = serialize(controls)
    config_serializable = serialize(config)

    # Prepare data to send
    data = {
        'fps': f"{current_fps:.2f}",
        'controls': controls_serializable,
        'configuration': config_serializable
    }
    return jsonify(data)

@app.route('/')
def index():
    return '''
    <html>
        <head>
            <title>Raspberry Pi Camera Stream</title>
            <style>
                body { font-family: Arial, sans-serif; }
                #stats { margin-top: 10px; }
                #fps { font-size: 1.2em; font-weight: bold; }
                pre { background-color: #f4f4f4; padding: 10px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Live Stream</h1>
            <img src="/video_feed">
            <div id="stats">
                <p id="fps">FPS: Calculating...</p>
                <h2>Camera Configuration</h2>
                <pre id="config">Loading...</pre>
            </div>
            <script>
                function fetchStats() {
                    fetch('/stats')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('fps').innerText = 'FPS: ' + data.fps;
                            document.getElementById('config').innerText = JSON.stringify(data.configuration, null, 2);
                        })
                        .catch(error => console.error('Error fetching stats:', error));
                }
                // Fetch stats every second
                setInterval(fetchStats, 1000);
                // Fetch stats on page load
                fetchStats();
            </script>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
