# mqtt_handler.py
import json
import time
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

import stream_manager as sm

# MQTT Settings
MQTT_BROKER        = 'localhost'
MQTT_PORT          = 1883
MQTT_CONTROL_TOPIC = 'yolo/control/#'
MQTT_EVENT_BASE    = 'yolo/events'

mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1)

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected (rc={rc}), subscribing to {MQTT_CONTROL_TOPIC}")
    client.subscribe(MQTT_CONTROL_TOPIC)

def on_message(client, userdata, msg):
    parts = msg.topic.split('/')
    if len(parts) == 4:
        _, _, src, cmd = parts
        try:
            payload = json.loads(msg.payload.decode()) if msg.payload else {}
        except json.JSONDecodeError:
            payload = {}

        ok = False
        if src in sm.flags_stream:
            if cmd == 'start':
                ok = sm.start_stream(
                    src,
                    payload.get('resolution', sm.params[src]['resolution']),
                    payload.get('fps',        sm.params[src]['fps']),
                    payload.get('bitrate',    sm.params[src]['bitrate'])
                )
            elif cmd == 'stop':
                ok = sm.stop_stream(src)
            elif cmd == 'detect_on':
                sm.flags_detect[src] = True; ok = True
            elif cmd == 'detect_off':
                sm.flags_detect[src] = False; ok = True
            elif cmd == 'heat_on':
                sm.flags_heatmap[src] = True; ok = True
            elif cmd == 'heat_off':
                sm.flags_heatmap[src] = False; ok = True

        client.publish(
            f"{MQTT_EVENT_BASE}/{src}/control_ack",
            json.dumps({'cmd': cmd, 'status': 'ok' if ok else 'error', 'ts': time.time()})
        )

def setup_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except ConnectionRefusedError:
        print("[MQTT] Connection refused – is your broker running?")
