#!/usr/bin/env python3
import argparse
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

PORT = "/dev/ttyUSB0"
iface = None
dest = None
channel = 0

def on_receive(packet, **kwargs):
    try:
        decoded = packet.get("decoded", {})
        if decoded.get("portnum") != "TEXT_MESSAGE_APP":
            return

        text = decoded.get("text", "")
        from_id = packet.get("fromId", "???")
        to_id = packet.get("toId", "^all")
        ts = datetime.now().strftime("%H:%M:%S")

        to_label = "broadcast" if to_id == "^all" else to_id
        print(f"\n[{ts}] {from_id} → {to_label}: {text}")
        print("Mensaje: ", end="", flush=True)
    except Exception:
        pass

def listen():
    pub.subscribe(on_receive, "meshtastic.receive")

def main():
    global iface, dest, channel

    parser = argparse.ArgumentParser(description="Chat interactivo Meshtastic")
    parser.add_argument("-d", "--dest", help="Nodo destino (ej: !02eabe70), default: broadcast", default=None)
    parser.add_argument("-c", "--channel", type=int, default=0, help="Canal (default: 0)")
    args = parser.parse_args()

    dest = args.dest
    channel = args.channel

    print(f"Conectando a {PORT}...")
    iface = meshtastic.serial_interface.SerialInterface(PORT)

    listen()

    node = iface.getMyNodeInfo() or {}
    my_id = node.get("user", {}).get("id", "?")
    target = dest if dest else "broadcast"
    print(f"Conectado como {my_id} | Canal: {channel} | Destino: {target}")
    print("Escribí tu mensaje y Enter para enviar. Ctrl+C para salir.\n")

    try:
        while True:
            print("Mensaje: ", end="", flush=True)
            text = input()
            if not text.strip():
                continue
            if dest:
                iface.sendText(text, destinationId=dest, channelIndex=channel)
            else:
                iface.sendText(text, channelIndex=channel)
    except KeyboardInterrupt:
        print("\nSaliendo...")
    finally:
        iface.close()

if __name__ == "__main__":
    main()
