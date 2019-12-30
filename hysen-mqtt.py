#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import re
import time
import traceback

import broadlink
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe


POLL_INTERVAL = 30.0

LOGGER = logging.getLogger(__name__)

class DevicesNotFoundError(Exception):
    pass


def get_config():
    host = os.environ['MQTT_HOST']
    port = int(os.environ['MQTT_PORT'])
    user = os.environ['MQTT_USER']
    password = os.environ['MQTT_PASSWORD']

    local_ip_address = os.environ['LOCAL_IP_ADDR'] \
        if 'LOCAL_IP_ADDR' in os.environ and os.environ['LOCAL_IP_ADDR'] \
        else None

    return host, port, user, password, local_ip_address


class HysenMQTTConnector:
    def __init__(self, device, host, port, user, password):
        self._device = device
        self._device_id = self.get_device_id()
        self._mqtt_client = self._build_mqtt_client(host, port, user, password)

    def _build_mqtt_client(self, host, port, user, password):
        client = mqtt.Client()
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        self._set_last_will(client)
        client.username_pw_set(user, password)
        client.connect(host, port)
        client.loop_start()
        return client

    def _on_connect(self, client, userdata, flags, rc):
        LOGGER.debug("Connected with result code %d", rc)
        try:
            self.subscribe_topics()
            self.publish_configuration()
            self.publish_available()
            self.publish_state()
        except Exception as err:
            traceback.print_tb(err.__traceback__)

    def _on_message(self, client, userdata, message):
        payload = message.payload.decode('utf-8')
        topic = message.topic

        match = re.match(r"^homeassistant/climate/{}/(.*?)$".format(
            self._device_id), topic)
        command = match.group(1)
        
        handlers = {
            "targetTempCmd": self.set_target_temperature,
            "thermostatModeCmd": self.set_thermostat_mode
        }

        LOGGER.debug("Calling handler for %s: %s(%s)",
                     self._device_id, command, payload)
        handlers[command](payload)
        try:
            self.publish_state()
        except Exception as err:
            traceback.print_tb(err.__traceback__)

    def set_target_temperature(self, payload):
        temperature = float(payload)
        LOGGER.debug("Setting %s target temperature to %f", 
                     self._device_id, temperature)
        self._device.set_temp(temperature)

    def set_thermostat_mode(self, payload):
        power = {
            "off": 0,
            "heat": 1
        }
        LOGGER.debug("Setting %s power mode to %f", 
                self._device_id, payload)
        self._device.set_power(power[payload])

    def set_time(self):
        cur_time = time.localtime()
        LOGGER.info('Setting %s time', self._device_id)
        self._device.set_time(
            cur_time.tm_hour, 
            cur_time.tm_min, 
            cur_time.tm_sec,
            cur_time.tm_wday+1)

    def set_deadzone(self, deadzone=1):
        LOGGER.info('Setting %s deadzone', self._device_id)
        status = self._device.get_full_status()
        
        loop_mode = status['loop_mode']
        sensor = status['sensor']
        osv = status['osv']
        dif = deadzone
        svh = status['svh']
        svl = status['svl']
        adj = status['room_temp_adj']
        fre = status['fre']
        poweron = status['poweron']

        self._device.set_advanced(loop_mode, sensor, osv, dif, svh, svl,
                                  adj, fre, poweron)

    def get_device_id(self):
        dev_type = self._device.type
        dev_mac_str = ''.join('{:02x}'.format(x) for x in self._device.mac)
        return '{}_{}'.format(dev_type.lower().replace(' ', '_'), dev_mac_str)

    def publish_configuration(self):
        config_topic = 'homeassistant/climate/{}/config'.format(self._device_id)
        device_mac = self._device_id.rsplit('_', 1)[-1]
        device_name = '{} {}'.format(self._device.type, device_mac)
        base = 'homeassistant/climate/{}'.format(self._device_id)
        device_payload = {
            "identifiers": [ device_mac ],
            "name": device_name,
            "model": self._device.type,
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
            "action_topic": base + "/state",
            "action_template": "{{ value_json.action }}",
            "min_temp": "5",
            "max_temp": "35",
            "temp_step": "0.5",
            "modes": ["off", "heat"],
            "device": device_payload
        }

        LOGGER.info('Publishing config for %s', self._device_id)

        self._mqtt_client.publish(config_topic, 
                                  json.dumps(config_payload), 
                                  retain=True)

    def publish_state(self):
        state_topic = 'homeassistant/climate/{}/state'.format(self._device_id)
        status = self._device.get_full_status()
        mode = "heat" if status["power"] else "off"
        if mode == "off":
            action = "off"
        else:
            action = "heating" if status["active"] else "idle"
        target_temp = str(status["thermostat_temp"])
        current_temp = str(status["external_temp"])
        state_payload = {
            "mode": mode,
            "target_temp": target_temp,
            "current_temp": current_temp,
            "action": action,
        }

        LOGGER.info('Publishing state for %s', self._device_id)

        self._mqtt_client.publish(state_topic, json.dumps(state_payload), qos=1)

    def publish_available(self):
        availability_topic = 'homeassistant/climate/{}/available'.format(
            self._device_id)
        availability_payload = 'online'

        LOGGER.info('Publishing availability for %s', self._device_id)

        self._mqtt_client.publish(
            availability_topic, availability_payload, retain=True, qos=1)

    def subscribe_topics(self):
        topics = ["targetTempCmd", "thermostatModeCmd"]
        base = "homeassistant/climate/{}/".format(self._device_id)
        for topic in topics:
            full_topic = base + topic
            LOGGER.debug('Subscribing %s to %s', self._device_id, full_topic)
            self._mqtt_client.subscribe(full_topic, 0)

    async def set_time_coro(self):
        while True:
            sleep_future = asyncio.sleep(30*60)
            try:
                self.set_time()
                self.set_deadzone()
            except Exception as err:
                traceback.print_tb(err.__traceback__)
            await sleep_future

    def _set_last_will(self, client):
        will_topic = 'homeassistant/climate/{}/available'.format(
            self._device_id)
        will_payload = 'offline'
        client.will_set(will_topic, will_payload, retain=True)

    async def publish_config_coro(self):
        while True:
            await asyncio.sleep(10*60)
            try:
                self.publish_configuration()
            except Exception as err:
                traceback.print_tb(err.__traceback__)

    async def publish_available_coro(self):
        while True:
            await asyncio.sleep(10*60)
            try:
                self.publish_available()
            except Exception as err:
                traceback.print_tb(err.__traceback__)

    async def publish_state_coro(self):
        while True:
            sleep_future = asyncio.sleep(POLL_INTERVAL)
            try:
                self.publish_state()
            except Exception as err:
                traceback.print_tb(err.__traceback__)
            await sleep_future

    async def start_tasks(self):
        LOGGER.info("Starting recurring background tasks for %s", 
                    self._device_id)
        tasks = []

        tasks.append(asyncio.create_task(self.publish_available_coro()))
        tasks.append(asyncio.create_task(self.publish_state_coro()))
        tasks.append(asyncio.create_task(self.set_time_coro()))

        for task in tasks:
            await task


async def get_devices(timeout=10, local_ip_address=None):
    LOGGER.info("Discovering broadlink devices")
    all_devices = broadlink.discover(
        timeout=timeout, 
        local_ip_address=local_ip_address)
    hysen_devices = [dev for dev in all_devices 
                     if isinstance(dev, broadlink.hysen)]
    LOGGER.info("Found %d Hysen devices", len(hysen_devices))

    return hysen_devices


async def main():
    LOGGER.setLevel(logging.DEBUG)
    logging.basicConfig(
        level=logging.DEBUG, 
        format="%(asctime)s:%(name)s:%(levelname)s:%(message)s")

    host, port, user, password, local_ip_address = get_config()

    devices = await get_devices(local_ip_address=local_ip_address)

    connectors = []
    tasks = []
    for device in devices:
        device.auth()
        connector = HysenMQTTConnector(device, host, port, user, password)
        connectors.append(connector)
        tasks.append(asyncio.create_task(connector.start_tasks()))

    # these tasks should never finish
    for task in tasks:
        await task

if __name__ == '__main__':
    asyncio.run(main())
