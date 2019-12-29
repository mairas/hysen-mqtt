#!/bin/sh

CONFIG_PATH=/data/options.json

# insert the configuration options into environment
export MQTT_HOST=$(jq --raw-output .mqtt_host $CONFIG_PATH)
export MQTT_PORT=$(jq --raw-output .mqtt_port $CONFIG_PATH)
export MQTT_USER=$(jq --raw-output .mqtt_user $CONFIG_PATH)
export MQTT_PASSWORD=$(jq --raw-output .mqtt_password $CONFIG_PATH)

# run the executable
python3 /hysen-mqtt.py
