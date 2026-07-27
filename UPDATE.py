from MQTT.MQTT_connector import *


if __name__ == "__main__":
    HOST = "521fa758f36d406f82650a9a06bdefc2.s1.eu.hivemq.cloud"
    PORT = 8883
    USERNAME = "Merlin"  # <-- replace
    PASSWORD = "Merlin6m"  # <-- replace
    TOPIC = "portal/commands"


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
    mc.send(TOPIC, "git/update123")
    mc.disconnect()