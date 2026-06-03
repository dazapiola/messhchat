#!/usr/bin/env python3
import argparse
import meshtastic
import meshtastic.serial_interface

PORT = "/dev/ttyUSB0"

def send(text, dest=None, channel=0):
    iface = meshtastic.serial_interface.SerialInterface(PORT)
    if dest:
        iface.sendText(text, destinationId=dest, channelIndex=channel)
        print(f"Enviado a {dest}: {text}")
    else:
        iface.sendText(text, channelIndex=channel)
        print(f"Broadcast: {text}")
    iface.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enviar mensajes por Meshtastic")
    parser.add_argument("mensaje", help="Texto a enviar")
    parser.add_argument("-d", "--dest", help="Nodo destino (ej: !02eabe70)", default=None)
    parser.add_argument("-c", "--channel", help="Canal (default: 0)", type=int, default=0)
    args = parser.parse_args()

    send(args.mensaje, args.dest, args.channel)
