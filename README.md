# Portal
Multispectral camera.

Being brought to the same standard as the main Merlin project (config, secrets, auto-update).

```
Portal/
├── main.py                 # Camera, display, MQTT commands (s3/<label> -> frame series to S3)
├── portal_autogit.py       # Starts main, keeps it running, updates from GitHub
├── git_push.py             # Development only: push with the token from secrets.env
├── config/
│   ├── __init__.py         # get_config() / load_env(): secrets.env + CPU serial
│   ├── secrets.env.example # Template of all keys, passwords and tokens
│   ├── secrets.env         # Real values, filled in on every device (git-ignored)
│   └── certs/              # Certificates (git-ignored)
├── MQTT/MQTT_connector.py  # MQTT client (HiveMQ Cloud)
└── tools/                  # Cameras, encoder, motor driver, S3 recorder
```

## Secrets

Keys, passwords and tokens live only in `config/secrets.env`. It is git-ignored and filled in by hand on every device:

```bash
cp config/secrets.env.example config/secrets.env
nano config/secrets.env
```

| Keys | Used by |
|---|---|
| `AWS_REGION`, `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY`, `S3_BUCKET` | `main.py` -> `tools/AWS_S3_recorder.py` |
| `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`, `MQTT_TOPIC` | `main.py` (commands) |
| `GITHUB_READ_USER`, `GITHUB_READ_TOKEN` | `portal_autogit.py` (read-only token) |
| `GITHUB_PUSH_USER`, `GITHUB_PUSH_TOKEN` | `git_push.py`, development machine only |

## Run

```bash
python3 portal_autogit.py     # normal operation: keeps main running and updates it from GitHub
python3 main.py               # the current local code as is, no updates
```

Exit codes of `main.py`: `0` or a crash = restart (autogit starts it again after 5 s), `10` = stop (`q` on the display).

## Auto-Update

`portal_autogit.py` (same as `merlin_autogit.py`) polls GitHub with `git ls-remote` (only the branch hash):

- every **1 s** for an hour after startup and after every update;
- every **15 s** after an hour without updates.

On a new commit on `main` it fetches it while main keeps running, stops `main.py`, runs `git reset --hard origin/main` and starts it again; if `portal_autogit.py` itself changed, autogit restarts too.

> `git reset --hard` discards local edits of tracked files on the device. Git-ignored files (`config/secrets.env`, `config/certs/`) are kept.

The old update path (GitHub Action -> Lambda -> MQTT `git/update` -> `git pull`) and the Lambda config (`tools/CloudConfigClient.py`) are removed.
