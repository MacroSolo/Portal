import os
import ast
import subprocess
import time
from pathlib import Path

from MQTT.MQTT_connector import *
import requests
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


