#!/bin/bash
sudo yum update -y
sudo yum install python3 python3-pip -y
pip3 install flask

cat <<EOF > /home/ec2-user/app.py
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

EOF

python3 /home/ec2-user/app.py