#!/usr/bin/env python3
import argparse
import glob
import platform
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from serial.tools import list_ports
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, RichLog, Input, Button, Static
from textual.containers import Vertical, Horizontal
from textual import work

VERSION = "1.2.0"

USB_SERIAL_CHIPS = ["CP210", "CH340", "CH341", "FTDI", "SILABS", "PROLIFIC", "MESHTASTIC"]

def find_port() -> str:
    # Busca por chip USB-serial conocido
    for port in list_ports.comports():
        desc = (port.description or "").upper()
        if any(chip in desc for chip in USB_SERIAL_CHIPS):
            return port.device

    # Fallback por sistema operativo
    system = platform.system()
    if system == "Linux":
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        return candidates[0] if candidates else "/dev/ttyUSB0"
    elif system == "Darwin":
        candidates = glob.glob("/dev/tty.usbserial*") + glob.glob("/dev/tty.SLAB_USBtoUART*")
        return candidates[0] if candidates else "/dev/tty.usbserial-0001"
    elif system == "Windows":
        ports = [p.device for p in list_ports.comports()]
        return ports[0] if ports else "COM3"
    return "/dev/ttyUSB0"

MATE_LOGO = """\
[bold green]     )  )  )[/bold green]
[bold green]    (  (  ( [/bold green]
[bold yellow]   ╔═══════╗[/bold yellow]
[bold yellow]   ║ [white]🧉 MESH[/white] ║[/bold yellow]
[bold yellow]   ║ [white]CHAT  [/white] ║[/bold yellow]
[bold yellow]   ╚═══════╝[/bold yellow]
[bold yellow]     ║   ║  [/bold yellow]
[bold yellow]    ═╩═══╩═ [/bold yellow]"""

AYUDA = f"""\
{MATE_LOGO}

[bold white]  MeshChat v{VERSION}[/bold white]
[dim]  Cliente TUI para Meshtastic[/dim]

[bold]  ─── Atajos ──────────────────────[/bold]
  [cyan]1[/cyan]          Tab Logs
  [cyan]2[/cyan]          Tab Chat
  [cyan]3[/cyan]          Tab Ayuda
  [cyan]Enter[/cyan]      Enviar mensaje
  [cyan]Ctrl+C[/cyan]     Salir

[bold]  ─── Inicio ──────────────────────[/bold]
  [dim]# Broadcast en canal 0[/dim]
  python meshchat_tui.py

  [dim]# A un nodo específico[/dim]
  python meshchat_tui.py -d "!a1b2c3d4"

  [dim]# Canal y puerto manual (si auto-detección falla)[/dim]
  python meshchat_tui.py -c 1 -p /dev/ttyUSB1  [dim]# Linux[/dim]
  python meshchat_tui.py -p /dev/tty.usbserial-0001  [dim]# Mac[/dim]
  python meshchat_tui.py -p COM3  [dim]# Windows[/dim]

[bold]  ─── Chat ────────────────────────[/bold]
  Los mensajes en [yellow bold]amarillo ★[/yellow bold] son dirigidos a tu nodo.
  Los mensajes en [cyan]cyan[/cyan] son broadcasts.
  El tab [bold]Logs[/bold] muestra todos los paquetes recibidos.

[bold]  ─── Comandos del bot ────────────[/bold]
  [green]#vecinos[/green]   Nodos cercanos con distancia
  [green]#help[/green]      Lista de comandos disponibles
  [green]#info[/green]      Información del bot
"""


class MeshChatTUI(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #ayuda_panel {
        height: 1fr;
        content-align: center top;
        padding: 2 4;
    }

    #log_viewer {
        border: solid $primary;
        height: 1fr;
        padding: 0 1;
    }

    #chat_viewer {
        border: solid $primary;
        height: 1fr;
        padding: 0 1;
    }

    #input_bar {
        height: 3;
        padding: 0 1;
        dock: bottom;
    }

    #msg_input {
        width: 1fr;
    }

    #send_btn {
        width: 10;
        margin-left: 1;
    }

    TabPane {
        padding: 0;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Salir"),
        ("1", "show_tab('logs')", "Logs"),
        ("2", "show_tab('chat')", "Chat"),
        ("3", "show_tab('ayuda')", "Ayuda"),
    ]

    def __init__(self, port: str, dest: str | None, channel: int):
        super().__init__()
        self.port = port
        self.dest = dest
        self.channel = channel
        self.iface = None
        self.my_id = "?"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="logs"):
            with TabPane("📋 Logs", id="logs"):
                yield RichLog(id="log_viewer", highlight=True, markup=True, wrap=True)
            with TabPane("💬 Chat", id="chat"):
                with Vertical():
                    yield RichLog(id="chat_viewer", highlight=True, markup=True, wrap=True)
                    with Horizontal(id="input_bar"):
                        yield Input(placeholder="Escribí tu mensaje y Enter para enviar...", id="msg_input")
                        yield Button("Enviar ▶", id="send_btn", variant="primary")
            with TabPane("ℹ️ Ayuda", id="ayuda"):
                yield Static(AYUDA, id="ayuda_panel", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "MeshChat 🧉"
        self.sub_title = f"Puerto: {self.port}"
        self._connect()

    @work(thread=True)
    def _connect(self) -> None:
        log = self.query_one("#log_viewer", RichLog)
        self.call_from_thread(log.write, f"[yellow]⏳ Conectando a {self.port}...[/yellow]")
        try:
            self.iface = meshtastic.serial_interface.SerialInterface(self.port)
            pub.subscribe(self._on_receive, "meshtastic.receive")
            node = self.iface.getMyNodeInfo() or {}
            self.my_id = node.get("user", {}).get("id", "?")
            target = self.dest if self.dest else "broadcast"
            self.call_from_thread(log.write, f"[green]✓ Conectado como [bold]{self.my_id}[/bold] | Canal: {self.channel} | Destino: {target}[/green]")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]✗ Error de conexión: {e}[/red]")

    def _on_receive(self, packet, **kwargs) -> None:
        try:
            decoded = packet.get("decoded", {})
            portnum = decoded.get("portnum", "")
            from_id = packet.get("fromId", "???")
            ts = datetime.now().strftime("%H:%M:%S")

            log = self.query_one("#log_viewer", RichLog)

            if portnum == "TEXT_MESSAGE_APP":
                text = decoded.get("text", "")
                to_id = packet.get("toId", "^all")
                is_direct = to_id == self.my_id
                to_label = "broadcast" if to_id == "^all" else to_id
                chat = self.query_one("#chat_viewer", RichLog)
                self.call_from_thread(log.write, f"[dim]{ts}[/dim] [cyan]{from_id}[/cyan] → [magenta]{to_label}[/magenta]: {text}")
                if is_direct:
                    self.call_from_thread(chat.write, f"[dim]{ts}[/dim] [yellow bold]★ {from_id} → vos:[/yellow bold] {text}")
                else:
                    self.call_from_thread(chat.write, f"[dim]{ts}[/dim] [cyan bold]{from_id}[/cyan bold]: {text}")
            else:
                self.call_from_thread(log.write, f"[dim]{ts} {from_id} [{portnum}][/dim]")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send_btn":
            self._send_message()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "msg_input":
            self._send_message()

    def _send_message(self) -> None:
        if not self.iface:
            return
        msg_input = self.query_one("#msg_input", Input)
        text = msg_input.value.strip()
        if not text:
            return
        try:
            if self.dest:
                self.iface.sendText(text, destinationId=self.dest, channelIndex=self.channel)
            else:
                self.iface.sendText(text, channelIndex=self.channel)
            ts = datetime.now().strftime("%H:%M:%S")
            to_label = self.dest if self.dest else "broadcast"
            chat = self.query_one("#chat_viewer", RichLog)
            log = self.query_one("#log_viewer", RichLog)
            chat.write(f"[dim]{ts}[/dim] [green bold]{self.my_id}[/green bold]: {text}")
            log.write(f"[dim]{ts}[/dim] [green bold]{self.my_id}[/green bold] → {to_label}: {text}")
            msg_input.value = ""
        except Exception as e:
            self.query_one("#chat_viewer", RichLog).write(f"[red]✗ Error al enviar: {e}[/red]")

    def action_show_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def on_unmount(self) -> None:
        if self.iface:
            self.iface.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MeshChat TUI - Interfaz interactiva Meshtastic")
    parser.add_argument("-p", "--port", default=None, help="Puerto serial (auto-detectado si no se especifica)")
    parser.add_argument("-d", "--dest", default=None, help="Nodo destino (ej: !a1b2c3d4)")
    parser.add_argument("-c", "--channel", type=int, default=0, help="Canal (default: 0)")
    args = parser.parse_args()

    port = args.port or find_port()
    MeshChatTUI(port=port, dest=args.dest, channel=args.channel).run()
