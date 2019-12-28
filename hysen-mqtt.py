#!/usr/bin/env python3

import json
import os
import re
import time

import broadlink
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe


# polling the devices is a blocking operation, so just set
# the interval a bit shorter than 60 s to ensure we get at least
# one sample a minute
POLL_INTERVAL = 50.0


class DevicesNotFoundError(Exception):
    pass


def get_config():
    host = os.environ['MQTT_HOST']
    port = int(os.environ['MQTT_PORT'])
    user = os.environ['MQTT_USER']
    password = os.environ['MQTT_PASSWORD']

    return host, port, user, password


def get_device_id(device):
    dev_type = device.type
    dev_mac_str = ''.join('{:02x}'.format(x) for x in device.mac)
    return '{}_{}'.format(dev_type.lower().replace(' ', '_'), dev_mac_str)


def get_devices(timeout=10):
    all_devices = broadlink.discover(timeout=timeout)
    hysen_devices = [dev for dev in all_devices 
                     if isinstance(dev, broadlink.hysen)]

    dev_dict = {get_device_id(device): device for device in hysen_devices}
    
    return dev_dict


def publish_configuration(devices, mqtt_client):
    for dev_id, device in devices.items():
        config_topic = 'homeassistant/climate/{}/config'.format(dev_id)
        device_mac = dev_id.rsplit('_', 1)[-1]
        device_name = '{} {}'.format(device.type, device_mac)
        base = 'homeassistant/climate/{}'.format(dev_id)
        device_payload = {
            "identifiers": [ device_mac ],
            "name": device_name,
            "model": device.type,
            "manufacturer": "Broadlink"
        }
        config_payload = {
            "name": device_name,
            "unique_id": device_mac,
            "mode_cmd_t": base + "/thermostatModeCmd",
            "mode_stat_t": base + "/state",
            "mode_stat_tpl": "{{ value_json.mode }}",
            "avty_t": base + "/available",
            "pl_avail": "online",
            "pl_not_avail": "offline",
            "temp_cmd_t": base + "/targetTempCmd",
            "temp_stat_t": base + "/state",
            "temp_stat_tpl": "{{ value_json.target_temp }}",
            "curr_temp_t": base + "/state",
            "curr_temp_tpl": "{{ value_json.current_temp }}",
            "min_temp": "5",
            "max_temp": "35",
            "temp_step": "0.5",
            "modes": ["off", "heat"],
            "device": device_payload
        }

        print('Publishing config: ', config_payload)

        mqtt_client.publish(config_topic, 
                            json.dumps(config_payload), 
                            retain=True)


def publish_state(dev_id, device, mqtt_client):
    state_topic = 'homeassistant/climate/{}/state'.format(dev_id)
    status = device.get_full_status()
    mode = "heat" if status["power"] else "off"
    target_temp = str(status["thermostat_temp"])
    current_temp = str(status["external_temp"])
    state_payload = {
        "mode": mode,
        "target_temp": target_temp,
        "current_temp": current_temp
    }

    mqtt_client.publish(state_topic, json.dumps(state_payload))


def publish_available(devices, mqtt_client):
    for dev_id in devices:
        availability_topic = 'homeassistant/climate/{}/available'.format(dev_id)
        availability_payload = 'online'
        mqtt_client.publish(
            availability_topic, availability_payload, retain=True)


def set_device_wills(devices, mqtt_client):
    for dev_id in devices:
        will_topic = 'homeassistant/climate/{}/available'.format(dev_id)
        will_payload = 'offline'
        mqtt_client.will_set(will_topic, will_payload, retain=True)


def subscribe_topics(devices, mqtt_client):
    topics = ["targetTempCmd", "thermostatModeCmd"]
    for dev_id in devices:
        base = "homeassistant/climate/{}/".format(dev_id)
        for topic in topics:
            full_topic = base + topic
            print("Subscribing to {}".format(full_topic))
            mqtt_client.subscribe(full_topic, 0)


def start_loop(devices, mqtt_client):
    mqtt_client.loop_start()

    while True:
        for dev_id, device in devices.items():
            publish_state(dev_id, device, mqtt_client)

            sleep_time = POLL_INTERVAL / len(devices)
            time.sleep(sleep_time)


def set_target_temperature(device, payload):
    temperature = float(payload)
    device.set_temp(temperature)


def set_thermostat_mode(device, payload):
    power = {
        "off": 0,
        "heat": 1
    }
    device.set_power(power[payload])


def main():
    mqtt_host, mqtt_port, mqtt_user, mqtt_password = get_config()

    devices = get_devices()

    for device in devices.values():
        device.auth()

    mqtt_client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        print("Connected with result code {}".format(rc))
        subscribe_topics(devices, mqtt_client)
        publish_configuration(devices, mqtt_client)        
        publish_available(devices, mqtt_client)

    mqtt_client.on_connect = on_connect

    def on_message(client, userdata, message):
        payload = message.payload.decode('utf-8')
        topic = message.topic

        match = re.match(r"^homeassistant/climate/(\w*?)/(.*?)$", topic)
        dev_id = match.group(1)
        command = match.group(2)
        
        handlers = {
            "targetTempCmd": set_target_temperature,
            "thermostatModeCmd": set_thermostat_mode
        }

        print("Calling handler for {}({}, {})".format(command, dev_id, payload))
        handlers[command](devices[dev_id], payload)
        publish_state(dev_id, devices[dev_id], mqtt_client)

    mqtt_client.on_message = on_message

    set_device_wills(devices, mqtt_client)

    mqtt_client.username_pw_set(mqtt_user, mqtt_password)

    mqtt_client.connect(mqtt_host, mqtt_port)

    start_loop(devices, mqtt_client)


if __name__ == '__main__':
    main()
