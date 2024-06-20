#!/bin/bash

set -e

cd ../generate-config

echo "Installing Python dependencies..."
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt > /dev/null

echo "Generating config file..."
python app.py --local-app-port=5005 $@ > ../local/core/config.json

echo "Config file saved to ./core/config.json"