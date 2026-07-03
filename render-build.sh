#!/usr/bin/env bash
set -e

echo "=== Installing system dependencies ==="
apt-get update && apt-get install -y ffmpeg

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install --pre "yt-dlp[default]"
pip install flask flask-cors gunicorn

echo "=== Build complete ==="
