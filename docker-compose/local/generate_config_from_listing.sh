#!/bin/bash

set -e

get_python_cmd() {
    # Check if python is defined
    if command -v python &> /dev/null
    then
        echo "python"
    elif command -v python3 &> /dev/null
    then
        echo "python3"
    else
        echo "Error: Neither python nor python3 is installed." >&2
        return 1
    fi
}

cd ../generate-config

PYTHON_CMD=$(get_python_cmd) || exit 1

echo "Installing Python dependencies..."
$PYTHON_CMD -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt > /dev/null

echo "Generating config file..."
mkdir -p ../local/core
$PYTHON_CMD app.py --local-app-port=5005 $@ > ../local/core/config.json

echo "Config file saved to ./core/config.json"