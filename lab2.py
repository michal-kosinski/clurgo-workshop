from flask import Flask
import socket

app = Flask(__name__)


@app.route('/')
def hello():
    hostname = socket.gethostname()
    return f"Hello, World! Hostname: {hostname}"


@app.route('/health')
def health():
    return "Status: OK", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
