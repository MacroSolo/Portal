import ssl
import json
import time
import paho.mqtt.client as mqtt


class MQTTClient:
    """
    Unified MQTT client for HiveMQ Cloud (or any TLS broker).

    Usage:
        def on_message(topic, payload):
            print(f"{topic}: {payload}")

        client = MQTTClient(
            host="xxx.hivemq.cloud",
            port=8883,
            username="user",
            password="pass",
            subscription="sensors/#",
            on_message=on_message,
        )
        client.connect()
        client.send("sensors/temp", {"value": 42})
        client.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        subscription: str | None = None,
        on_message=None,
        client_id: str = "mqtt-client",
        qos: int = 1,
        keepalive: int = 60,
    ):
        self.host         = host
        self.port         = port
        self.username     = username
        self.password     = password
        self.subscription = subscription
        self.on_message   = on_message  # callable(topic: str, payload: str | dict)
        self.qos          = qos
        self.keepalive    = keepalive

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        self._client.username_pw_set(username, password)
        self._client.tls_set(
            ca_certs=None,
            certfile=None,
            keyfile=None,
            cert_reqs=ssl.CERT_NONE,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.tls_insecure_set(True)

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._client.on_subscribe  = self._on_subscribe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to the broker and start the background network loop."""
        self._client.connect(self.host, self.port, keepalive=self.keepalive)
        self._client.loop_start()
        time.sleep(1.0)  # allow connection to establish

    def disconnect(self) -> None:
        """Stop the network loop and disconnect cleanly."""
        self._client.loop_stop()
        self._client.disconnect()

    def send(self, topic: str, payload, qos: int | None = None) -> None:
        """
        Publish a message to a topic.
        Payload can be a string, dict, or any JSON-serialisable object.
        """
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False)
        elif not isinstance(payload, str):
            payload = str(payload)

        result = self._client.publish(topic, payload=payload, qos=qos or self.qos)
        result.wait_for_publish()

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[MQTT] Connected → {self.host}:{self.port}")
            if self.subscription:
                client.subscribe(self.subscription, qos=self.qos)
        else:
            print(f"[MQTT] Connection failed (reason_code={reason_code})")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        print(f"[MQTT] Disconnected (reason_code={reason_code})")

    def _on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        print(f"[MQTT] Subscribed → '{self.subscription}'")

    def _on_message(self, client, userdata, msg):
        raw = msg.payload.decode("utf-8", errors="replace")

        # Try to deserialise JSON, fall back to raw string
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw

        if self.on_message:
            self.on_message(msg.topic, payload)


# ------------------------------------------------------------------
# Example usage
# ------------------------------------------------------------------
if __name__ == "__main__":
    HOST     = "521fa758f36d406f82650a9a06bdefc2.s1.eu.hivemq.cloud"
    PORT     = 8883
    USERNAME = "Merlin"   # <-- replace
    PASSWORD = "Merlin6m"   # <-- replace
    TOPIC    = "test"

    def command(topic, payload):
        print(f"[command] topic={topic}  payload={payload}")

    mc = MQTTClient(
        host=HOST,
        port=PORT,
        username=USERNAME,
        password=PASSWORD,
        subscription=TOPIC,
        on_message=command,
    )

    mc.connect()
    mc.send(TOPIC, "hello")
    mc.send(TOPIC, {"value": 42, "status": "ok"})

    time.sleep(60)
    mc.disconnect()