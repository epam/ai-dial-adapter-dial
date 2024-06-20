#!/bin/bash

set -e

envsubst < ./config_template.json > ./core/config.json
echo "Config file saved to ./core/config.json"