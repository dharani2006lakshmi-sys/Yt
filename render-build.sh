#!/usr/bin/env bash
set -e

# Install system dependencies
apt-get update && apt-get install -y ffmpeg python3-pip

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
