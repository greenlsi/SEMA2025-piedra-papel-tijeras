import logging
from threading import Thread
import time
import asyncio

from prompt_toolkit import Application
from prompt_toolkit.application import run_in_terminal, get_app
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

class UILogHandler(logging.Handler):
    def __init__(self, log_window, max_lines=1000):
        super().__init__()
        self.log_window = log_window
        self.max_lines = max_lines

    def emit(self, record):
        msg = self.format(record)
        if not msg.endswith('\n'):
            msg += '\n'

        async def append():
            buffer = self.log_window.buffer

            buffer.insert_text(msg)

            # Recortar si excede
            lines = buffer.text.splitlines()
            if len(lines) > self.max_lines:
                trimmed = '\n'.join(lines[-self.max_lines:])
                buffer.text = trimmed
                buffer.cursor_position = len(trimmed)

            get_app().invalidate()

        try:
            app = get_app()
            app.create_background_task(append())
        except Exception as e:
            print("Error en logging UI:", e)
            print(msg)

def start_shell(raft, done):
    from server import message_queue  # Import diferido
    from prompt_toolkit.layout.dimension import D

    # Widgets
    log_window = TextArea(style='class:log', scrollbar=True, wrap_lines=False, height=D(weight=2))
    output_window = TextArea(style='class:output', scrollbar=True, wrap_lines=True, height=D(weight=1))
    input_window = TextArea(style='class:input', height=1)

    # Layout con altura proporcional
    layout = Layout(HSplit([
        log_window,
        output_window,
        input_window,
    ]), focused_element=input_window)

    # Key bindings
    kb = KeyBindings()

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

    # Logger
    handler = UILogHandler(log_window)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Eliminar todos los handlers anteriores (como el StreamHandler por defecto)
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    logger.addHandler(handler)

    def set_output(text):
        output_window.text = text

    def process_command(line):
        if not line:
            return

        if line == "raft show":
            output = ["[Raft STATUS]"]
            output.append(f"  Estado LE:        {raft.fsm_leader.state}")
            output.append(f"  Término actual:   {raft.term}")
            output.append(f"  Votado por:       {raft.voted_for}")
            output.append(f"  Soy líder:        {'sí' if raft.is_leader() else 'no'}")
            if raft.fsm_leader.state in ("follower", "candidate"):
                remaining = max(0, raft.election_timeout - time.time())
                output.append(f"  Timeout en:       {remaining:.2f} segundos")
            if raft.fsm_leader.state == "candidate":
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
            for cmd in ["raft show", "mq show", "help", "exit"]:
                output.append(f"  {cmd}")
            set_output("\n".join(output))

        elif line == "exit":
            app.exit()
            done.set()

        else:
            logging.warning("Comando no reconocido. Escribe 'help' para ver los comandos.")

    Thread(target=app.run, daemon=True).start()

