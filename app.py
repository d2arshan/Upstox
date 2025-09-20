from flask import Flask, render_template
from flask_socketio import SocketIO
from threading import Thread
import logging

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

@app.route('/')
def index():
    """Serve the index page."""
    return render_template('index.html')

def data_broadcaster(data_queue, stop_event):
    """A daemon thread that reads from the queue and broadcasts to clients."""
    while not stop_event.is_set():
        try:
            data = data_queue.get(timeout=1)
            socketio.emit('market_data_update', data)
        except Exception:
            continue

def start_web_server(data_queue, stop_event):
    """Starts the Flask-SocketIO server and the broadcaster thread."""
    broadcaster_thread = Thread(target=data_broadcaster, args=(data_queue, stop_event), daemon=True)
    broadcaster_thread.start()
    
    logging.info("Starting web server on http://127.0.0.1:5000")
    print("🚀 Dashboard is running at http://127.0.0.1:5000")
    
    # Use eventlet as the production server for WebSocket support
    socketio.run(app, host='127.0.0.1', port=5000)