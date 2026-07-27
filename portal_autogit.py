import os
import ast
import subprocess
import time
from pathlib import Path

from MQTT.MQTT_connector import *
import base64


def get_cpuinfo():
    cpuinfo = {}

    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if ":" in line:
                    key, value = line.split(":", 1)
                    cpuinfo[key.strip()] = value.strip()
    except Exception as e:
        cpuinfo = {"Serial": "Unknown"}

    return cpuinfo


if __name__ == "__main__":
    HOST = "521fa758f36d406f82650a9a06bdefc2.s1.eu.hivemq.cloud"
    PORT = 8883
    USERNAME = "Merlin"  # <-- replace
    PASSWORD = "Merlin6m"  # <-- replace
    TOPIC = "portal/commands"


    def command(topic, payload):
        print(f"[command] topic={topic}  payload={payload}")
        if payload.lower() == "git/update":
            try:
                # Get the current working directory
                cwd = Path(__file__).parent.resolve()

                # Run git pull command
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Check if the command was successful
                if result.returncode == 0:
                    print("Git update successful.")
                    print(result.stdout)
                else:
                    print("Git update failed.")
                    print(result.stderr)

            except Exception as e:
                print(f"Error during git update: {e}")


    mc = MQTTClient(
        host=HOST,
        port=PORT,
        username=USERNAME,
        password=PASSWORD,
        subscription=TOPIC,
        on_message=command,
    )

    mc.connect()
    while True:
        time.sleep(10)

    mc.disconnect()