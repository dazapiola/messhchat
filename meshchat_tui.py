#!/usr/bin/env python3
import argparse
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, RichLog, Input, Button, Static
from textual.containers import Vertical, Horizontal
from textual import work

PORT = "/dev/ttyUSB0"

MATE_LOGO = """\
[bold green]     )  )  )[/bold green]
[bold green]    (  (  ( [/bold green]
[bold yellow]   ╔═══════╗[/bold yellow]
[bold yellow]   ║ [white]🧉 MESH[/white] ║[/bold yellow]
[bold yellow]   ║ [white]CHAT  [/white] ║[/bold yellow]
[bold yellow]   ╚═══════╝[/bold yellow]
[bold yellow]     ║   ║  [/bold yellow]
[bold yellow]    ═╩═══╩═ [/bold yellow]"""


class MeshChatTUI(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #logo {
        height: 9;
        content-align: center middle;
        padding: 1 2;
        color: $text;
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
        yield Static(MATE_LOGO, id="logo")
        with TabbedContent(initial="logs"):
            with TabPane("📋 Logs", id="logs"):
                yield RichLog(id="log_viewer", highlight=True, markup=True, wrap=True)
            with TabPane("💬 Chat", id="chat"):
                with Vertical():
                    yield RichLog(id="chat_viewer", highlight=True, markup=True, wrap=True)
                    with Horizontal(id="input_bar"):
                        yield Input(placeholder="Escribí tu mensaje y Enter para enviar...", id="msg_input")
                        yield Button("Enviar ▶", id="send_btn", variant="primary")
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
                to_label = "broadcast" if to_id == "^all" else to_id
                chat = self.query_one("#chat_viewer", RichLog)
                self.call_from_thread(log.write, f"[dim]{ts}[/dim] [cyan]{from_id}[/cyan] → [magenta]{to_label}[/magenta]: {text}")
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
    parser.add_argument("-p", "--port", default=PORT, help="Puerto serial (default: /dev/ttyUSB0)")
    parser.add_argument("-d", "--dest", default=None, help="Nodo destino (ej: !02eabe70)")
    parser.add_argument("-c", "--channel", type=int, default=0, help="Canal (default: 0)")
    args = parser.parse_args()

    MeshChatTUI(port=args.port, dest=args.dest, channel=args.channel).run()
