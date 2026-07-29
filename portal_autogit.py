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
    USERNAME = "Merlin"
    PASSWORD = "Merlin6m"
    TOPIC = "portal/commands"

    main_file = Path("~/Projects/Portal").expanduser() / "main.py"
    current_process = subprocess.Popen(['python3', main_file])
    print("[main] Started main process.")


    def command(topic, payload):
        global current_process
        print(f"[command] topic={topic}  payload={payload}")
        if payload.lower() == "git/update":
            try:
                if current_process and current_process.poll() is None:
                    current_process.kill()
                    current_process.wait(timeout=5)
            except Exception as e:
                print(f"Error killing process: {e}")

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

            try:
                current_process = subprocess.Popen(['python3', main_file])
                print("Restarted main process successfully.")
            except Exception as e:
                print(f"Failed to start process: {e}")



    mqcmd = MQTTClient(
        host=HOST,
        port=PORT,
        username=USERNAME,
        password=PASSWORD,
        subscription=TOPIC,
        on_message=command,
    )

    mqcmd.connect()



    while True:
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            print("Stopping...")
            if current_process:
                current_process.kill()
            break
        except Exception as e:
            print(f"[main loop] Error: {e}")
            time.sleep(5)
