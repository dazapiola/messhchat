# MeshChat 🧉

```
     )  )  )
    (  (  (
   ╔═══════╗
   ║ 🧉 MESH ║
   ║  CHAT  ║
   ╚═══════╝
     ║   ║
    ═╩═══╩═
```

Cliente de terminal para interactuar con nodos [Meshtastic](https://meshtastic.org/) desde Linux. Incluye una TUI interactiva con visor de logs en tiempo real, chat y pantalla de ayuda. Compatible con cualquier broker MQTT (MeshChile, Meshtastic público, propio, etc.).

---

## Requisitos

- Python 3.10+
- Dispositivo Meshtastic conectado por USB
- El puerto serial se **auto-detecta** — no necesitás configurar nada en la mayoría de los casos

---

## Instalación

### Linux

```bash
git clone <repo>
cd messhchat
make install
make run
```

> Si el dispositivo no tiene permisos:
> ```bash
> sudo usermod -aG dialout $USER
> # Cerrar sesión y volver a entrar
> ```

### macOS

```bash
git clone <repo>
cd messhchat
make install
make run
```

> En Mac el puerto suele ser `/dev/tty.usbserial-*`. Si falla la auto-detección:
> ```bash
> .venv/bin/python meshchat_tui.py -p /dev/tty.usbserial-0001
> ```

### Windows

```cmd
git clone <repo>
cd messhchat
install.bat
```

Luego para iniciar:
```cmd
.venv\Scripts\python meshchat_tui.py
```

> En Windows el puerto es `COM3`, `COM4`, etc. Si falla la auto-detección:
> ```cmd
> .venv\Scripts\python meshchat_tui.py -p COM3
> ```

---

## Scripts

### `meshchat_tui.py` — Interfaz TUI interactiva

La interfaz principal. Dos tabs:
- **📋 Logs** — todos los paquetes recibidos en tiempo real
- **💬 Chat** — enviá y recibí mensajes de texto

```bash
# Broadcast en canal 0 (default)
.venv/bin/python meshchat_tui.py

# A un nodo específico
.venv/bin/python meshchat_tui.py -d "!a1b2c3d4"

# En otro canal
.venv/bin/python meshchat_tui.py -c 1

# Puerto distinto
.venv/bin/python meshchat_tui.py -p /dev/ttyUSB1
```

**Atajos de teclado:**

| Tecla | Acción |
|-------|--------|
| `1` | Tab Logs |
| `2` | Tab Chat |
| `3` | Tab Ayuda |
| `Enter` | Enviar mensaje |
| `Ctrl+C` | Salir |

---

### `meshtastic_listener.py` — Visor de logs simple

Muestra en tiempo real todos los paquetes que recibe el nodo, sin interfaz gráfica.

```bash
.venv/bin/python meshtastic_listener.py
```

---

## Comandos de bot

Algunos bots de la comunidad Meshtastic responden comandos enviados en broadcast:

| Comando | Descripción |
|---------|-------------|
| `#vecinos` | Nodos cercanos con distancia |
| `#info` | Info del bot |
| `#help` | Lista de comandos disponibles |

---

## MQTT

El cliente funciona con cualquier broker MQTT compatible con Meshtastic:

- [MeshChile](https://meshchile.cl) — `mqtt.meshchile.cl`
- [Meshtastic público](https://meshtastic.org) — `mqtt.meshtastic.org`
- Broker propio

La configuración del broker se realiza directamente en el dispositivo vía `meshtastic --set network.mqtt_*`.

## Hardware probado

- **Heltec WiFi LoRa 32 V3** con firmware Meshtastic 2.7.x
