"""
MotorGuard — Standalone Local MQTT Broker (No Docker Required)

Runs an authentic MQTT broker on port 1883 using amqtt, enabling
the ESP32 hardware and simulator to communicate with FastAPI and MongoDB.
"""

import asyncio
import logging
from amqtt.broker import Broker

logger = logging.getLogger("motorguard.broker")

config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        }
    },
    "sys_interval": 20,
    "auth": {
        "allow-anonymous": True,
        "plugins": ["auth_anonymous"],
    },
}


async def start_broker():
    broker = Broker(config)
    await broker.start()
    print("=" * 60)
    print("  MotorGuard MQTT Broker ACTIVE on 0.0.0.0:1883")
    print("  Accepting MQTT 3.1.1 telemetry from ESP32 & Simulator")
    print("=" * 60)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(start_broker())
    except KeyboardInterrupt:
        print("MQTT Broker stopped.")
