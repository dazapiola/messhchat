#!/usr/bin/env python3
import argparse
import glob
import platform
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from rich.markup import escape
from serial.tools import list_ports
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, RichLog, Input, Button, Static, ListView, ListItem, Label
from textual.containers import Vertical, Horizontal
from textual import work

VERSION = "2.0.0"

USB_SERIAL_CHIPS = ["CP210", "CH340", "CH341", "FTDI", "SILABS", "PROLIFIC", "MESHTASTIC"]

def find_port() -> str:
    for port in list_ports.comports():
        desc = (port.description or "").upper()
        if any(chip in desc for chip in USB_SERIAL_CHIPS):
            return port.device
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
  [cyan]Alt+↑/↓[/cyan]   Cambiar canal
  [cyan]Ctrl+C[/cyan]     Salir

[bold]  ─── Inicio ──────────────────────[/bold]
  [dim]# Broadcast en canal 0[/dim]
  python meshchat_tui.py

  [dim]# A un nodo específico[/dim]
  python meshchat_tui.py -d "!a1b2c3d4"

  [dim]# Puerto manual (si auto-detección falla)[/dim]
  python meshchat_tui.py -c 1 -p /dev/ttyUSB1  [dim]# Linux[/dim]
  python meshchat_tui.py -p /dev/tty.usbserial-0001  [dim]# Mac[/dim]
  python meshchat_tui.py -p COM3  [dim]# Windows[/dim]

[bold]  ─── Canales IRC ─────────────────[/bold]
  Los mensajes usan prefijo [green]#canal[/green] al estilo IRC.
  Sin prefijo van a [green]#general[/green] automáticamente.

  [dim]Enviar al canal emergencia:[/dim]
  [green]#emergencia[/green] hay humo en sector norte

  [dim]Entrar a un canal (sin escribir mensaje):[/dim]
  [green]#vecinos[/green]   ← solo Enter, no envía

  El panel izquierdo lista los canales activos.
  Los números [red]rojos[/red] indican mensajes no leídos.
  Click o Enter sobre un canal para entrar.

[bold]  ─── Chat ────────────────────────[/bold]
  Los mensajes en [yellow bold]amarillo ★[/yellow bold] son dirigidos a tu nodo.
  El tab [bold]Logs[/bold] muestra todos los paquetes sin filtro.

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

    #chat_area {
        height: 1fr;
    }

    #sidebar {
        width: 22;
        border-right: solid $primary;
        padding: 0 1;
    }

    #sidebar_title {
        height: 1;
        color: $accent;
        text-style: bold;
    }

    #channel_list {
        height: 1fr;
        border: none;
    }

    #chat_main {
        width: 1fr;
    }

    #chat_viewer {
        border: solid $primary;
        height: 1fr;
        padding: 0 1;
    }

    #input_bar {
        height: 3;
        padding: 0 1;
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
        ("alt+up", "prev_channel", "Canal ↑"),
        ("alt+down", "next_channel", "Canal ↓"),
    ]

    def __init__(self, port: str, dest: str | None, channel: int):
        super().__init__()
        self.port = port
        self.dest = dest
        self.channel = channel
        self.iface = None
        self.my_id = "?"
        self.channels: dict[str, list[dict]] = {"#general": []}
        self.active_channel: str = "#general"
        self.unread: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="logs"):
            with TabPane("📋 Logs", id="logs"):
                yield RichLog(id="log_viewer", highlight=True, markup=True, wrap=True)
            with TabPane("💬 Chat", id="chat"):
                with Horizontal(id="chat_area"):
                    with Vertical(id="sidebar"):
                        yield Static("─ CANALES ─", id="sidebar_title")
                        yield ListView(id="channel_list")
                    with Vertical(id="chat_main"):
                        yield RichLog(id="chat_viewer", highlight=True, markup=True, wrap=True)
                        with Horizontal(id="input_bar"):
                            yield Input(placeholder="[#general] Escribe tu mensaje...", id="msg_input")
                            yield Button("Enviar ▶", id="send_btn", variant="primary")
            with TabPane("ℹ️ Ayuda", id="ayuda"):
                yield Static(AYUDA, id="ayuda_panel", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "MeshChat 🧉"
        self.sub_title = f"Puerto: {self.port} | #general"
        self._refresh_sidebar()
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
            self.call_from_thread(
                log.write,
                f"[green]✓ Conectado como [bold]{self.my_id}[/bold] | Canal HW: {self.channel} | Destino: {target}[/green]"
            )
        except Exception as e:
            self.call_from_thread(log.write, f"[red]✗ Error de conexión: {e}[/red]")

    @staticmethod
    def _parse_channel(text: str) -> tuple[str, str]:
        """Extract (channel_name, message) from text. Returns (#general, text) if no prefix."""
        if text.startswith("#"):
            parts = text.split(" ", 1)
            ch = parts[0].lower()
            msg = parts[1].strip() if len(parts) > 1 else ""
            if msg:
                return ch, msg
        return "#general", text

    def _on_receive(self, packet, **kwargs) -> None:
        try:
            decoded = packet.get("decoded", {})
            portnum = decoded.get("portnum", "")
            from_id = packet.get("fromId") or "???"
            ts = datetime.now().strftime("%H:%M:%S")
            log = self.query_one("#log_viewer", RichLog)

            if portnum == "TEXT_MESSAGE_APP":
                text = decoded.get("text") or ""
                to_id = packet.get("toId") or "^all"
                is_direct = to_id == self.my_id
                to_label = "broadcast" if to_id == "^all" else to_id

                self.call_from_thread(
                    log.write,
                    f"[dim]{ts}[/dim] [cyan]{from_id}[/cyan] → [magenta]{to_label}[/magenta]: {escape(text)}"
                )

                ch_name, ch_msg = self._parse_channel(text)
                msg_data = {
                    "ts": ts,
                    "from_id": from_id,
                    "text": ch_msg,
                    "is_direct": is_direct,
                    "is_mine": False,
                }

                is_new_channel = ch_name not in self.channels
                if is_new_channel:
                    self.channels[ch_name] = []
                self.channels[ch_name].append(msg_data)

                if ch_name != self.active_channel:
                    self.unread[ch_name] = self.unread.get(ch_name, 0) + 1
                    self.call_from_thread(self._refresh_sidebar)
                else:
                    self.call_from_thread(self._append_message, msg_data)
                    if is_new_channel:
                        self.call_from_thread(self._refresh_sidebar)
            else:
                self.call_from_thread(log.write, f"[dim]{ts} {from_id} [{portnum}][/dim]")
        except Exception:
            pass

    def _append_message(self, msg: dict) -> None:
        chat = self.query_one("#chat_viewer", RichLog)
        self._render_message(chat, msg)

    def _render_message(self, chat: RichLog, msg: dict) -> None:
        ts = msg["ts"]
        from_id = escape(msg.get("from_id") or "?")
        text = escape(msg.get("text") or "")
        if msg.get("is_mine"):
            chat.write(f"[dim]{ts}[/dim] [green bold]{from_id}[/green bold]: {text}")
        elif msg.get("is_direct"):
            chat.write(f"[dim]{ts}[/dim] [yellow bold]★ {from_id} → vos:[/yellow bold] {text}")
        else:
            chat.write(f"[dim]{ts}[/dim] [cyan bold]{from_id}[/cyan bold]: {text}")

    def _refresh_sidebar(self) -> None:
        list_view = self.query_one("#channel_list", ListView)
        list_view.clear()
        for ch_name in self.channels:
            unread = self.unread.get(ch_name, 0)
            is_active = ch_name == self.active_channel
            ch_escaped = escape(ch_name)
            prefix = "[green]▶[/green] " if is_active else "  "
            badge = f" [red bold]{unread}[/red bold]" if unread > 0 else ""
            name_markup = f"[bold]{ch_escaped}[/bold]" if is_active else ch_escaped
            list_view.append(ListItem(Label(f"{prefix}{name_markup}{badge}", markup=True)))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "channel_list":
            return
        channels = list(self.channels.keys())
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(channels):
            self._switch_channel(channels[idx])

    def _switch_channel(self, channel_name: str) -> None:
        self.active_channel = channel_name
        self.unread[channel_name] = 0

        chat = self.query_one("#chat_viewer", RichLog)
        chat.clear()
        for msg in self.channels.get(channel_name, []):
            self._render_message(chat, msg)

        self.query_one("#msg_input", Input).placeholder = f"[{channel_name}] Escribe tu mensaje..."
        self.sub_title = f"Puerto: {self.port} | {channel_name}"
        self._refresh_sidebar()

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

        # Typing just "#channelname" (no message) switches channel without sending
        if text.startswith("#") and " " not in text:
            ch_name = text.lower()
            if ch_name not in self.channels:
                self.channels[ch_name] = []
            self._switch_channel(ch_name)
            msg_input.value = ""
            return

        if text.startswith("#"):
            ch_name, ch_text = self._parse_channel(text)
            full_text = text
        else:
            ch_name = self.active_channel
            ch_text = text
            full_text = f"{self.active_channel} {text}"

        try:
            if self.dest:
                self.iface.sendText(full_text, destinationId=self.dest, channelIndex=self.channel)
            else:
                self.iface.sendText(full_text, channelIndex=self.channel)

            ts = datetime.now().strftime("%H:%M:%S")
            msg_data = {"ts": ts, "from_id": self.my_id, "text": ch_text, "is_mine": True, "is_direct": False}

            if ch_name not in self.channels:
                self.channels[ch_name] = []
            self.channels[ch_name].append(msg_data)

            if ch_name == self.active_channel:
                self._render_message(self.query_one("#chat_viewer", RichLog), msg_data)
            else:
                # Sent to a different channel — switch to it so the user sees confirmation
                self._switch_channel(ch_name)

            to_label = self.dest if self.dest else "broadcast"
            self.query_one("#log_viewer", RichLog).write(
                f"[dim]{ts}[/dim] [green bold]{escape(self.my_id)}[/green bold] → {to_label}: {escape(full_text)}"
            )
            msg_input.value = ""
            self._refresh_sidebar()
        except Exception as e:
            self.query_one("#chat_viewer", RichLog).write(f"[red]✗ Error al enviar: {e}[/red]")

    def action_show_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def action_prev_channel(self) -> None:
        channels = list(self.channels.keys())
        idx = channels.index(self.active_channel)
        if idx > 0:
            self._switch_channel(channels[idx - 1])

    def action_next_channel(self) -> None:
        channels = list(self.channels.keys())
        idx = channels.index(self.active_channel)
        if idx < len(channels) - 1:
            self._switch_channel(channels[idx + 1])

    def on_unmount(self) -> None:
        if self.iface:
            self.iface.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MeshChat TUI - Interfaz interactiva Meshtastic")
    parser.add_argument("-p", "--port", default=None, help="Puerto serial (auto-detectado si no se especifica)")
    parser.add_argument("-d", "--dest", default=None, help="Nodo destino (ej: !a1b2c3d4)")
    parser.add_argument("-c", "--channel", type=int, default=0, help="Canal hardware Meshtastic (default: 0)")
    args = parser.parse_args()

    port = args.port or find_port()
    MeshChatTUI(port=port, dest=args.dest, channel=args.channel).run()
