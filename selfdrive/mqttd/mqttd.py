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

from common.cached_params import CachedParams
from pyextra.paho.mqtt import client as mqtt_client
from pyextra.paho.mqtt.client import MQTT_ERR_SUCCESS
from pyextra.paho.mqtt.subscribeoptions import SubscribeOptions
import json
import sys

def client_id():
  device_type = HARDWARE.get_device_type()
  serial = HARDWARE.get_serial()
  client_id = f"{device_type}-{serial}"
  return client_id

def publish(pm, topic, message):
  dat = messaging.new_message("mqttPubQueue")
  dat.mqttPubQueue.publish = True
  dat.mqttPubQueue.topic = topic
  dat.mqttPubQueue.content = json.dumps(message)
  pm.send("mqttPubQueue", dat)

def subscribe(pm, topic):
  dat = messaging.new_message("mqttPubQueue")
  dat.mqttPubQueue.subscribe = True
  dat.mqttPubQueue.topic = topic
  pm.send("mqttPubQueue", dat)

def unsubscribe(pm, topic):
  dat = messaging.new_message("mqttPubQueue")
  dat.mqttPubQueue.subscribe = False
  dat.mqttPubQueue.publish = False
  dat.mqttPubQueue.topic = topic
  pm.send("mqttPubQueue", dat)

def connect_mqtt(client, broker, port, username, password, pm):
    def on_connect(client, userdata, flags, rc):
      if rc != 0:
        client.connected_flag = False
        print("Failed to connect, return code %d\n", rc)
      else:
        client.connected_flag = True
        client.sub_dict = update_subs(client, True)

    def on_message(client, userdata, msg):
      dat = messaging.new_message("mqttRecvQueue")
      dat.mqttRecvQueue.topic = msg.topic
      dat.mqttRecvQueue.payload = msg.payload
      pm.send("mqttRecvQueue", dat)
      print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

    def on_publish(client, userdata, mid):
      print(f"SENT {mid} with SUCCESS")
      mid_filter = lambda message: message["mid"] != mid
      client.pub_list = list(filter(mid_filter, client.pub_list))

    def on_disconnect(client, userdata, rc):
      if rc != 0:
        print("Unexpected disconnection.")
      client.connected_flag = False
      for key in client.sub_dict.keys():
        client.sub_dict[key]["server_state"] = False

    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    if port == 8883:
      client.tls_set()

    client.connect(broker, port)
    return client

def update_subs(client, connect_flag):
  sub_dict = client.sub_dict
  print(f"\n{sub_dict}\n")
  for key in sub_dict.keys():
    #UNSUB
    if not sub_dict[key]["subscribe"] and sub_dict[key]["server_state"] == True:
      if coonect_flag:
        sub_dict.pop(key)
      else:
        res, mid = client.unsubscribe(key)
        if res == MQTT_ERR_SUCCESS:
          sub_dict.pop(key)
        else:
          print("COULDNT UNSUB")
    #SUB
    if sub_dict[key]["subscribe"] and (not sub_dict[key]["server_state"] or connect_flag):
      res, mid = client.subscribe(key)
      if res == MQTT_ERR_SUCCESS:
        print(f"SUBBED {key}")
        sub_dict[key]["server_state"] = True
      else:
        print("COULDNT SUB")
  return sub_dict

def setup_connection(client, pm):
  cached_params = client.cached_params
  broker = cached_params.get("moneyPlane.settings.mqtt.broker", 5000)
  if broker != "":
    port = int(cached_params.get("moneyPlane.settings.mqtt.port", 5000))
    user = cached_params.get("moneyPlane.settings.mqtt.user", 5000)
    password = cached_params.get("moneyPlane.settings.mqtt.pass", 5000)
    print("Hello MQTT is going to attempt to connect now")
    client = connect_mqtt(client, broker, port, user, password, pm)
    client.loop_start()
    return False
  return True

def send_pubs(client):
  updated_pub_list = []
  for message in client.pub_list:
    if message["attempts"] > 4:
      continue
    if message["attempts"] != 0 and time.time() - message["last_sent"] < 0.2:
      updated_pub_list.append(message)
      continue

    result, mid = client.publish(message["topic"], message["content"])
    message["mid"] = mid
    message["attempts"] = message["attempts"] + 1
    message["last_sent"] = time.time()
    updated_pub_list.append(message)

  return updated_pub_list

def mqtt_thread():
  pm = messaging.PubMaster(['mqttRecvQueue'])
  sm = messaging.SubMaster(['mqttPubQueue'])

  # Set Connecting Client ID
  client = mqtt_client.Client(client_id())
  client.connected_flag = False
  client.sub_dict = {}
  client.pub_list = []
  client.cached_params = CachedParams()

  first_connect = True

  count = 100
  while True:
    if first_connect:
      first_connect = setup_connection(client, pm)

    sm.update()
    if not sm.updated["mqttPubQueue"]:
      continue

    message = sm["mqttPubQueue"]
    if not message.subscribe and not message.publish and message.topic in client.sub_dict:
      client.sub_dict[message.topic]["subscribe"] = False
    if message.subscribe:
      if message.topic not in client.sub_dict:
        client.sub_dict[message.topic] = {"server_state": False}
      client.sub_dict[message.topic]["subscribe"] = True
    if message.publish:
      msg = {"topic": message.topic, "content": message.content, "attempts": 0, "last_sent": time.time(), "mid": -1}
      client.pub_list.append(msg)
      client.pub_list = client.pub_list[-100:]
    if client.connected_flag:
      if count == 100:
        print("CONNECTED")
        count = 0
      client.sub_dict = update_subs(client, False)
      client.pub_list = send_pubs(client)
    elif not first_connect:
      if count == 100:
        print("I AM RECONNECTING MANUALLY")
        try:
          client.reconnect()
        except:
          e = sys.exec.info()[0]
          print(f"error reconnecting {e}")
        count = 0
    count = count + 1

def main():
  mqtt_thread()

if __name__ == "__main__":
  main()
