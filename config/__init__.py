"""
Local device config, replaces the Cloud Config Client (CCC).

Reads config/secrets.env (filled in manually, git-ignored), adds the CPU serial
from /proc/cpuinfo and the MQTT certificate content from MQTT_CERT_FILE.

    from config import get_config
    config = get_config()
    config['Serial'], config['MQTT_CERT'], config['AWS_S3_ACCESS_KEY_ID'], ...
"""
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
REPO = CONFIG_DIR.parent
SECRETS_FILE = CONFIG_DIR / "secrets.env"


def load_env(path=SECRETS_FILE):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def cpu_serial():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial") and ":" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "Unknown"


def get_config(path=SECRETS_FILE):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: copy config/secrets.env.example to it and fill in the values")

    config = load_env(path)
    config["Serial"] = cpu_serial()

    cert_file = config.get("MQTT_CERT_FILE")
    if cert_file:
        cert_path = Path(cert_file).expanduser()
        if not cert_path.is_absolute():
            cert_path = REPO / cert_path
        if not cert_path.exists():
            raise FileNotFoundError(f"MQTT certificate not found: {cert_path}")
        config["MQTT_CERT"] = cert_path.read_text()

    return config
