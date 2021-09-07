#!/usr/bin/env python3
import datetime
import os
import time
import random
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

from common.cached_params import CachedParams
from pyextra.paho.mqtt import client as mqtt_client
from pyextra.paho.mqtt.client import MQTT_ERR_SUCCESS
from pyextra.paho.mqtt.subscribeoptions import SubscribeOptions

from selfdrive.mqttd import mqttd

import json

def publish_ha_discovery(pm, count, config_prefix):
  client_id = mqttd.client_id()
  content = {"name": "car","state_topic": f"home/binary_sensor/car/{client_id}", "device_class": "motion", "unique_id": client_id, "count": count}
  topic = f"{config_prefix}/binary_sensor/car/{client_id}/config"
  mqttd.publish(pm, topic, content)

def status_thread():
  cached_params = CachedParams()
  broker = cached_params.get("moneyPlane.settings.mqtt.broker", 5000)
  while broker == "":
    time.sleep(30)
    broker = cached_params.get("moneyPlane.settings.mqtt.broker", 5000)

  config_prefix = cached_params.get("moneyPlane.settings.mqtt.haConfig", 5000)
  status_prefix = cached_params.get("moneyPlane.settings.mqtt.haStatus", 5000)

  time.sleep(30)
  pm = messaging.PubMaster(['mqttPubQueue'])
  sm = messaging.SubMaster(['mqttRecvQueue'])

  panda_state_timeout = int(1000 * 2.5 * DT_TRML)  # 2.5x the expected pandaState frequency
  panda_state_sock = messaging.sub_sock('pandaState', timeout=panda_state_timeout)
  location_sock = messaging.sub_sock('gpsLocationExternal')
  device_sock = messaging.sub_sock('deviceState')

  publish_ha_discovery(pm, "FIRST", config_prefix)

  count = 0
  total_count = 0
  panda_prev = None
  location_prev = None
  device_prev = None

  while True:
    mqttd.subscribe(pm, "openpilot/boom")
    total_count = total_count + 1
    topic = "openpilot/helloworld"
    content = {"hello": "world", "random": random.random(), "date": time.time(), "count": total_count}
    mqttd.publish(pm, topic, content)
    sm.update(1)
    if count == 10:
      count = 0
      publish_ha_discovery(pm, total_count, config_prefix)
    count = count + 1
    if sm.updated["mqttRecvQueue"]:
      print("I got a message")
      message = sm["mqttRecvQueue"]
      print(f"I RECEVIED A MESSAGE {message.payload}")

    panda = messaging.recv_sock(panda_state_sock)
    location = messaging.recv_sock(location_sock)
    device = messaging.recv_sock(device_sock)

    panda_prev = panda if panda else panda_prev
    device_prev = device if device else device_prev
    location_prev = location if location else location_prev

    topic = f"{status_prefix}/openpilot/status"
    content = {"panda_state": (strip_deprecated_keys(panda_prev.to_dict()) if panda_prev else None),
               "location": (strip_deprecated_keys(location_prev.gpsLocationExternal.to_dict()) if location_prev else None),
               "device_state": (strip_deprecated_keys(device_prev.to_dict()) if device_prev else None),
               "count": count,
               "date": time.time()
               }
    mqttd.publish(pm, topic, content)

    time.sleep(30)

def main():
  status_thread()

if __name__ == "__main__":
  main()
