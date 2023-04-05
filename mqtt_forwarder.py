#!/usr/bin/env python3
#
#  Copyright 2016 Sébastien Lucas <sebastien@slucas.fr>
#  Copyright 2023 Roman Morawek
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

import os
import time
import json
import argparse
import signal
import paho.mqtt.client as mqtt  # pip install paho-mqtt
import urllib.parse

verbose = False

CONNECTION_RETURN_CODE = [
    "connection successful",
    "incorrect protocol version",
    "invalid client identifier",
    "server unavailable",
    "bad username or password",
    "not authorised",
]


def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    client.disconnect()


def environ_or_required(key):
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def debug(msg):
    if verbose:
        print(msg + "\n")


def on_connect(client, userdata, flags, rc):
    debug("Connected with result: " + CONNECTION_RETURN_CODE[rc]
          if rc < len(CONNECTION_RETURN_CODE) else rc)

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(args.topic)


def on_message(client, userdata, msg):
    sensor_name = msg.topic.split('/')[-1]
    if msg.topic in hash_map.keys() or sensor_name in hash_map.keys():
        # determine target topic
        hash_value = hash_map[sensor_name] if sensor_name in hash_map.keys() \
            else hash_map[msg.topic]
        target_path = hash_value.split(":")[0]
        mqttPath = urllib.parse.urljoin(
            args.destination + '/', target_path) if args.destination else target_path
        debug("Received message from {0} with payload {1} to be published to {2}".format(
            msg.topic, str(msg.payload), mqttPath))
        # determine target value
        node_data = msg.payload
        if ":" in hash_value:
            scaling = hash_value.split(":")[1]
            factor = float(scaling.split(",")[0])
            offset = float(scaling.split(",")[1]) if "," in scaling else 0
            node_data = float(node_data) * factor + offset
        if args.addDate:
            newObject = json.loads(node_data.decode('utf-8'))
            newObject['time'] = int(time.time())
            node_data = json.dumps(newObject)
        if not args.dryRun:
            client.publish(mqttPath, node_data)
        else:
            debug("Dry run")
    else:
        debug("Received message from {0} with payload {1}. Hash not found in hashMap".format(
            msg.topic, str(msg.payload)))


parser = argparse.ArgumentParser(description='Send MQTT payload received from a topic to firebase.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-m', '--mqtt-host', dest='host', action="store", default="127.0.0.1",
                    help='Specify the MQTT host to connect to.')
parser.add_argument('-u', '--username', dest='username', action="store", metavar="USERNAME",
                    help='MQTT broker login username.')
parser.add_argument('-p', '--password', dest='password', action="store", metavar="$ECRET",
                    help='MQTT broker login password.')
parser.add_argument('-P', '--port', dest='port', action="store", type=int, default=1883, metavar=1883,
                    help='MQTT boroker port')
parser.add_argument('-t', '--topic', dest='topic', action="store", default="#",
                    help='The listening MQTT topic.')
parser.add_argument('-d', '--destination', dest='destination', action="store", default="",
                    help='The destination MQTT topic base.')
parser.add_argument('-a', '--hash-map', dest='hashMap', action="store",
                    help='Specify the map of MQTT topics to forward.')
parser.add_argument('-c', '--hash-map-file', dest='hashMapFile', action="store",
                    help='Specify the map file of MQTT topics to forward.')
parser.add_argument('-D', '--add-date', dest='addDate', action="store_true", default=False,
                    help='Interpret MQTT payload as JSON and add timestamp.')
parser.add_argument('-n', '--dry-run', dest='dryRun', action="store_true", default=False,
                    help='No data will be sent to the MQTT broker.')
parser.add_argument('-v', '--verbose', dest='verbose', action="store_true", default=False,
                    help='Enable debug messages.')


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
args = parser.parse_args()
verbose = args.verbose

if args.hashMap is None and args.hashMapFile is None:
    raise Exception('You must specify either a hash map or a hash map file.')
if args.hashMap:
    hash_map = json.loads(args.hashMap)
else:
    with open(args.hashMapFile, "r") as hashmapfile:
        hash_map = json.load(hashmapfile)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

if args.username is not None:
    client.username_pw_set(args.username, password=args.password)
elif args.password is not None:
    raise Exception('Login with password requires username.')
client.connect(host=args.host, port=args.port, keepalive=60)

client.loop_forever()
