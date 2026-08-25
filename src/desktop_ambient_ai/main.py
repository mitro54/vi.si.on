"""
Main Application Entry Point and Lifecycle Supervisor with IPC Single-Instance Support.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path

# Ensure Qt handles Linux/WSL2 display servers gracefully
if sys.platform.startswith("linux"):
    if "QT_QPA_PLATFORM" not in os.environ:
        # Prefer xcb in WSLg / X11 to avoid wl_display connection failures
        os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"

from PyQt6.QtCore import QByteArray, QDataStream, QIODevice, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from .config import AppConfig, load_config
from .llm.provider_factory import create_llm_worker
from .orchestrator import Orchestrator
from .storage.conversation_store import ConversationStore
from .tools.knowledge_base import KnowledgeBase
from .tools.mcp_bridge import MCPBridge
from .tools.tool_registry import ToolRegistry
from .tools.web_search import SearXNGSearch
from .ui.setup_wizard import SetupWizard
from .ui.tray import SystemTrayManager

IPC_SERVER_NAME = "vi_si_on_ipc_server"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vi.si.on — Ambient Desktop AI Overlay")
    parser.add_argument("--config", type=str, help="Custom configuration JSON path", default=None)
    parser.add_argument("--wizard", "--reset-setup", action="store_true", help="Launch interactive setup wizard")
    parser.add_argument("--quick", action="store_true", help="Trigger quick query modal")
    parser.add_argument("--conversation", action="store_true", help="Trigger active conversation modal")
    parser.add_argument("--new", action="store_true", help="Trigger brand new conversation modal")
    parser.add_argument("--snip", action="store_true", help="Trigger interactive screen region snipping")
    parser.add_argument("--picker", action="store_true", help="Open conversation history picker")
    parser.add_argument("--enable-autostart", action="store_true", help="Configure vi.si.on to launch on system login")
    parser.add_argument("--disable-autostart", action="store_true", help="Remove vi.si.on from system login autostart")
    parser.add_argument("--quit", action="store_true", help="Stop running ambient daemon instance")
    return parser.parse_args()


def send_ipc_command(command: str) -> bool:
    """Sends command to an already running vi.si.on instance via local socket."""
    socket = QLocalSocket()
    socket.connectToServer(IPC_SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(command.encode("utf-8"))
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True
    return False


def main() -> int:
    # Allow Ctrl+C to terminate application gracefully in terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    args = parse_args()

    # Handle Autostart management CLI commands
    if args.enable_autostart:
        from .utils.autostart import setup_autostart
        return 0 if setup_autostart() else 1
    if args.disable_autostart:
        from .utils.autostart import disable_autostart
        return 0 if disable_autostart() else 1

    # Determine command to dispatch
    command = "show"
    if args.quick:
        command = "quick"
    elif args.conversation:
        command = "conversation"
    elif args.new:
        command = "new"
    elif args.snip:
        command = "snip"
    elif args.picker:
        command = "picker"
    elif args.quit:
        command = "quit"

    # Guard against headless Linux/SSH sessions without graphical display server
    if sys.platform.startswith("linux"):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            print("[vi.si.on Error] No active graphical display server (DISPLAY/WAYLAND_DISPLAY) found.", file=sys.stderr)
            print("vi.si.on requires an active desktop graphical environment (X11, Wayland, or WSLg) to render transparent ambient overlays.", file=sys.stderr)
            return 1

    # Initialize Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("vi.si.on")
    app.setOrganizationName("vi.si.on")
    app.setQuitOnLastWindowClosed(False)

    # 1. Check if an instance is already running
    if send_ipc_command(command):
        print(f"[vi.si.on] Dispatched command '{command}' to running instance.")
        return 0

    # If --quit was requested but no instance was running
    if args.quit:
        print("[vi.si.on] No running instance found.")
        return 0

    # 2. Start Primary Instance
    config: AppConfig = load_config(args.config)

    # Launch Setup Wizard on first launch or if requested
    first_launch = not config.setup_complete or args.wizard
    if first_launch:
        wizard = SetupWizard(config)
        wizard.exec()

    # Initialize Storage Subsystem
    conversation_store = ConversationStore()

    # Initialize Tools Subsystems
    web_search = SearXNGSearch(config.web_search)
    knowledge_base = KnowledgeBase(config.knowledge_base)
    mcp_bridge = MCPBridge(config.mcp_servers)

    tool_registry = ToolRegistry(
        config=config,
        web_search=web_search,
        knowledge_base=knowledge_base,
        mcp_bridge=mcp_bridge,
    )

    # Initialize Central Orchestrator Agent
    orchestrator = Orchestrator(
        config=config,
        store=conversation_store,
        tool_registry=tool_registry,
        knowledge_base=knowledge_base,
    )

    # Initialize System Tray
    tray_manager = SystemTrayManager()
    tray_manager.quick_chat_requested.connect(orchestrator.trigger_quick_chat)
    tray_manager.conversation_requested.connect(orchestrator.trigger_conversation)
    tray_manager.new_conversation_requested.connect(orchestrator.trigger_new_conversation)
    tray_manager.snip_requested.connect(orchestrator.trigger_ocr_selection)
    tray_manager.quit_requested.connect(app.quit)

    def _open_settings():
        wiz = SetupWizard(config)
        if wiz.exec():
            orchestrator.llm_worker = create_llm_worker(config.provider, parent=orchestrator)
            tray_manager.show_notification("Settings Updated", "Configuration changes have been applied.")

    tray_manager.settings_requested.connect(_open_settings)

    # 3. Setup IPC Server for receiving commands from external processes / keybinds
    ipc_server = QLocalServer(app)
    # Remove stale server socket if left from previous crash
    QLocalServer.removeServer(IPC_SERVER_NAME)
    if not ipc_server.listen(IPC_SERVER_NAME):
        print(f"[vi.si.on] Warning: Could not start IPC server: {ipc_server.errorString()}")

    def _handle_ipc_connection():
        client_socket = ipc_server.nextPendingConnection()
        if not client_socket:
            return

        def _read_data():
            cmd_bytes = client_socket.readAll().data().decode("utf-8").strip()
            if cmd_bytes == "quick" or cmd_bytes == "show":
                orchestrator.trigger_quick_chat()
            elif cmd_bytes == "conversation":
                orchestrator.trigger_conversation()
            elif cmd_bytes == "new":
                orchestrator.trigger_new_conversation()
            elif cmd_bytes == "snip":
                orchestrator.trigger_ocr_selection()
            elif cmd_bytes == "picker":
                orchestrator.show_conversation_picker()
            elif cmd_bytes == "quit":
                app.quit()

        client_socket.readyRead.connect(_read_data)

    ipc_server.newConnection.connect(_handle_ipc_connection)

    print("=" * 60)
    print("🔮 vi.si.on is active and running in the background!")
    print("Global Hotkeys:")
    print(f"  • Quick Query:             {config.hotkeys.quick_chat}")
    print(f"  • Active Conversation:     {config.hotkeys.conversation}")
    print(f"  • New Conversation:        {config.hotkeys.new_conversation}")
    print(f"  • Region Snip (Vision):    {config.hotkeys.ocr_selection}")
    print(f"  • Dismiss / Close:         {config.hotkeys.dismiss}")
    print("\nCLI Triggers:")
    print("  • uv run vi.si.on --quick")
    print("  • uv run vi.si.on --conversation")
    print("  • uv run vi.si.on --snip")
    print("  • uv run vi.si.on --picker")
    print("  • uv run vi.si.on --wizard")
    print("  • uv run vi.si.on --quit")
    print("=" * 60)

    # 4. Cleanup on Application Exit: Unload Ollama model from GPU/VRAM
    def _cleanup_on_quit():
        if knowledge_base:
            knowledge_base.stop_watcher()

        if config.provider.type == "ollama" and config.provider.model:
            try:
                import ollama
                client = ollama.Client(host=config.provider.ollama_host, timeout=5)
                # Setting keep_alive: 0 immediately evicts the model from VRAM/RAM
                client.generate(model=config.provider.model, keep_alive=0)
                print(f"[vi.si.on] Unloaded model '{config.provider.model}' from memory.")
            except Exception:
                pass

    app.aboutToQuit.connect(_cleanup_on_quit)

    # Open prompt immediately on startup if first launch or requested via CLI
    if args.quick or first_launch:
        QTimer.singleShot(250, orchestrator.trigger_quick_chat)
    elif args.conversation:
        QTimer.singleShot(250, orchestrator.trigger_conversation)
    elif args.picker:
        QTimer.singleShot(250, orchestrator.show_conversation_picker)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
