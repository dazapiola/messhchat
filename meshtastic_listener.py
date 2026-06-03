#!/usr/bin/env python3
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from datetime import datetime
import signal
import sys
import time

PORT = "/dev/ttyUSB0"

iface = None


def get_node_name(from_id):
    if iface and iface.nodes:
        node = iface.nodes.get(from_id, {})
        return node.get("user", {}).get("longName", from_id)
    return from_id


def on_message(packet, interface):
    decoded = packet.get("decoded", {})
    if decoded.get("portnum") != "TEXT_MESSAGE_APP":
        return

    text = decoded.get("text", "").strip()
    if not text:
        return

    from_id = packet.get("fromId", "?")
    to_id = packet.get("toId", "^all")
    name = get_node_name(from_id)
    ts = datetime.now().strftime("%H:%M:%S")

    dest = "broadcast" if to_id == "^all" else f"→ {get_node_name(to_id)}"
    print(f"[{ts}] {name} ({dest}): {text}", flush=True)


def on_connection(interface, topic=pub.AUTO_TOPIC):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectado al dispositivo.", flush=True)


def shutdown(sig, frame):
    print("\nCerrando listener...", flush=True)
    if iface:
        iface.close()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

pub.subscribe(on_message, "meshtastic.receive")
pub.subscribe(on_connection, "meshtastic.connection.established")

print(f"Conectando a {PORT}...")
iface = meshtastic.serial_interface.SerialInterface(PORT)
print("Escuchando mensajes. Ctrl+C para salir.\n")

while True:
    time.sleep(1)
