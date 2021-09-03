#!/usr/bin/env python3
import datetime
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import psutil
from smbus2 import SMBus

import cereal.messaging as messaging
from cereal import log
from common.filter_simple import FirstOrderFilter
from common.numpy_fast import clip, interp
from common.params import Params, ParamKeyType
from common.realtime import DT_TRML, sec_since_boot
from common.dict_helpers import strip_deprecated_keys
from selfdrive.controls.lib.alertmanager import set_offroad_alert
from selfdrive.hardware import EON, TICI, HARDWARE
from selfdrive.loggerd.config import get_available_percent
from selfdrive.pandad import get_expected_signature
from selfdrive.swaglog import cloudlog
from selfdrive.thermald.power_monitoring import PowerMonitoring
from selfdrive.version import get_git_branch, terms_version, training_version

from common.op_params import opParams
from pyextra.paho.mqtt import client as mqtt_client
from pyextra.paho.mqtt.client import MQTT_ERR_SUCCESS
from pyextra.paho.mqtt.subscribeoptions import SubscribeOptions
import json

def publish_ha_discovery(client, client_id):
  config = {"name": "car","state_topic": f"home/binary_sensor/car/{client_id}", "device_class": "motion", "unique_id": client_id}
  client.publish(f"homeassistant/binary_sensor/car/{client_id}/config", json.dumps(config))

def connect_mqtt(broker, port, username, password, client_id, pm):
    def on_connect(client, userdata, flags, rc):
      if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe("openpilot/#", options=SubscribeOptions(noLocal = True))
        publish_ha_discovery(client, client_id)
      else:
        print("Failed to connect, return code %d\n", rc)

    def on_message(client, userdata, msg):
        pm.send("mqttState", bytes(msg.payload.decode(), 'utf-8'))
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

    def on_disconnect(client, userdata, rc):
      if rc != 0:
        print("Unexpected disconnection.")

    # Set Connecting Client ID
    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    if port == 8883:
      client.tls_set()

    client.connect(broker, port)
    return client

def mqtt_thread():
  pm = messaging.PubMaster(['mqttState'])
  panda_state_timeout = int(1000 * 2.5 * DT_TRML)  # 2.5x the expected pandaState frequency
  panda_state_sock = messaging.sub_sock('pandaState', timeout=panda_state_timeout)

  device_type = HARDWARE.get_device_type()
  serial = HARDWARE.get_serial()
  client_id = f"{device_type}-{serial}"

  host = ""
  user = ""
  password = ""
  port = 1883

  while True:
    op_params = opParams()
    broker = op_params.get("mqttBroker")
    port = op_params.get("mqttPort")
    user = op_params.get("mqttUser")
    password = op_params.get("mqttPass")

    if broker != "":
      print("config updated")
      break
    print("Hello MQTT is running, but no connections")
    time.sleep(10)

  print("Hello MQTT is going to attempt to connect now")
  client = connect_mqtt(broker, port, user, password, client_id, pm)
  client.publish("openpilot/device_id", client_id)
  client.loop_start()

  panda_state_prev = None
  while True:
    panda_state = messaging.recv_sock(panda_state_sock, wait=True)
    panda_state = False if panda_state is None else panda_state.pandaState.ignitionLine or panda_state.pandaState.ignitionCan
    car_state = "OFF" if not panda_state else "ON"

    if panda_state == panda_state_prev:
      continue

    print(f"Car is {car_state}")
    result = client.publish(f"home/binary_sensor/car/{client_id}", car_state)
    if not result.is_published():
      print("Failed to send message")
      panda_state_prev = None
    else:
      client.publish("openpilot/state", car_state)
      panda_state_prev = panda_state

def main():
  mqtt_thread()

if __name__ == "__main__":
  main()
