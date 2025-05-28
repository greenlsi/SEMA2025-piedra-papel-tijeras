import logging
from threading import Thread
import time
import asyncio
import os
import json

from config import get_config, set_config, save_config
from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_page_up, scroll_page_down, scroll_one_line_up, scroll_one_line_down,
)


class UILogHandler(logging.Handler):
    def __init__(self, log_window, max_lines=1000):
        super().__init__()
        self.log_window = log_window
        self.max_lines = max_lines
        self.user_scrolled = False

    def emit(self, record):
        msg = self.format(record)
        if not msg.endswith('\n'):
            msg += '\n'

        async def append():
            buffer = self.log_window.buffer

            if not self.user_scrolled:
                buffer.insert_text(msg)
                lines = buffer.text.splitlines()
                if len(lines) > self.max_lines:
                    trimmed = '\n'.join(lines[-self.max_lines:])
                    buffer.text = trimmed
                    buffer.cursor_position = len(trimmed)
            else:
                # Si el usuario ha hecho scroll, no mover el cursor
                buffer.insert_text(msg)

            get_app().invalidate()

        try:
            app = get_app()
            app.create_background_task(append())
        except Exception as e:
            print("Error en logging UI:", e)
            print(msg)


def bind_scroll_keys(kb, textarea):
    @kb.add("pageup")
    def _(event):
        textarea.buffer.cursor_position -= 80
        scroll_page_up(event)

    @kb.add("pagedown")
    def _(event):
        textarea.buffer.cursor_position += 80
        scroll_page_down(event)

    @kb.add("c-u")
    def _(event):
        textarea.buffer.cursor_position -= 1
        scroll_one_line_up(event)

    @kb.add("c-d")
    def _(event):
        textarea.buffer.cursor_position += 1
        scroll_one_line_down(event)

        # Marcar que el usuario ha hecho scroll (para autoscroll controlado)
        for h in logging.getLogger().handlers:
            if isinstance(h, UILogHandler):
                h.user_scrolled = True

def bind_focus_keys(kb, input_window, output_window, log_window):
    @kb.add('escape', 'i')
    def _(event):
        event.app.layout.focus(input_window)

    @kb.add('escape', 'o')
    def _(event):
        event.app.layout.focus(output_window)

    @kb.add('escape', 'l')
    def _(event):
        event.app.layout.focus(log_window)


def start_shell(raft, done):
    from raft.server import message_queue

    # Comandos disponibles
    available_commands = [
        "raft show", "mq show", "help", "exit",
        "config show", "config set"
    ]
    command_completer = WordCompleter(available_commands, ignore_case=True, sentence=True)
    history_file = os.path.expanduser("~/.piedra_papel_tijeras_history")

    # Widgets
    log_window = TextArea(style='class:log', scrollbar=True, wrap_lines=False, height=D(weight=2))
    output_window = TextArea(style='class:output', scrollbar=True, wrap_lines=True, height=D(weight=1))
    input_window = TextArea(
        style='class:input',
        height=1,
        prompt='> ',
        completer=command_completer,
        multiline=False,
        history=FileHistory(history_file),
        wrap_lines=False
    )

    # Layout completo
    layout = Layout(HSplit([
        log_window,
        output_window,
        input_window,
    ]), focused_element=input_window)

    # Key bindings
    kb = KeyBindings()
    bind_scroll_keys(kb, log_window)
    bind_scroll_keys(kb, output_window)
    bind_focus_keys(kb, input_window, output_window, log_window)

    @kb.add('enter')
    def _(event):
        line = input_window.text.strip()
        input_window.text = ''
        process_command(line)

    # Estilo
    style = Style.from_dict({
        'log': 'bg:#000000 #00ff00',
        'output': 'bg:#1e1e1e #ffffff',
        'input': 'bg:#444444 #ffffff',
    })

    # App
    app = Application(layout=layout, key_bindings=kb, full_screen=True, style=style)

    # Logger (limpiar handlers previos)
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    handler = UILogHandler(log_window)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    def set_output(text):
        output_window.text = text

    def process_command(line):
        if not line:
            return

        if line == "raft show":
            output = ["[Raft STATUS]"]
            output.append(f"  Estado LE:        {raft.fsm.state}")
            output.append(f"  Término actual:   {raft.term}")
            output.append(f"  Votado por:       {raft.voted_for}")
            output.append(f"  Soy líder:        {'sí' if raft.is_leader() else 'no'}")
            if raft.fsm.state in ("follower", "candidate"):
                remaining = max(0, raft.election_timeout - time.time())
                output.append(f"  Timeout en:       {remaining:.2f} segundos")
            if raft.fsm.state == "candidate":
                output.append(f"  Votos recibidos:  {raft.votes_received}")
            set_output("\n".join(output))

        elif line == "mq show":
            output = ["[Message Queue]"]
            if message_queue.empty():
                output.append("  (vacía)")
            else:
                for i, (addr, msg) in enumerate(list(message_queue.queue)):
                    output.append(f"  [{i}] {addr}: {msg}")
            set_output("\n".join(output))

        elif line == "help":
            output = ["Comandos disponibles:"]
            for cmd in available_commands:
                output.append(f"  {cmd}")
            set_output("\n".join(output))

        elif line == "exit":
            app.exit()
            done.set()

        elif line == "config show":
            set_output(json.dumps(get_config(), indent=2))

        elif line.startswith("config set"):
            try:
                new_values = json.loads(cmd[len("show set"):].strip())
                set_config(new_values)
                save_config()
                set_output("Configuration updated.")
            except json.JSONDecodeError:
                set_output("Invalid JSON.")

        else:
            logging.warning("Comando no reconocido. Escribe 'help' para ver los comandos.")
            set_output(f"Comando no reconocido: {line}")

    # Lanzar UI
    Thread(target=app.run, daemon=True).start()

