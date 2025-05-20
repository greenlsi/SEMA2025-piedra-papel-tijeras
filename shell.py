import logging
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from threading import Thread
import time


class UILogHandler(logging.Handler):
    """Handler de logging que redirige mensajes a un TextArea de prompt_toolkit."""
    def __init__(self, log_window):
        super().__init__()
        self.log_window = log_window

    def emit(self, record):
        msg = self.format(record)
        buffer = self.log_window.buffer
        was_at_end = buffer.cursor_position == len(buffer.text)
        buffer.insert_text(msg + '\n')
        if was_at_end:
            buffer.cursor_position = len(buffer.text)


def start_shell(raft):
    from server import message_queue  # Import dentro para evitar ciclos

    # Área de logs y entrada
    log_window = TextArea(style='class:log', scrollbar=True, wrap_lines=False)
    input_window = TextArea(height=1, prompt='> ', style='class:input')

    # Layout
    layout = Layout(HSplit([log_window, input_window]), focused_element=input_window)

    # Key bindings
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        line = input_window.text.strip()
        input_window.text = ''
        process_command(line)

    # Estilo básico
    style = Style.from_dict({
        'log': 'bg:#1e1e1e #ffffff',
        'input': 'bg:#444444 #ffffff',
    })

    # Aplicación de prompt_toolkit
    app = Application(layout=layout, key_bindings=kb, full_screen=True, style=style)

    # Configurar logger
    handler = UILogHandler(log_window)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    def process_command(line):
        if not line:
            return

        if line == "raft show":
            logging.info("[Raft STATUS]")
            logging.info(f"  Estado LE:        {raft.fsm_leader.state}")
            logging.info(f"  Término actual:   {raft.term}")
            logging.info(f"  Votado por:       {raft.voted_for}")
            logging.info(f"  Soy líder:        {'sí' if raft.is_leader() else 'no'}")
            if raft.fsm_leader.state in ("follower", "candidate"):
                remaining = max(0, raft.election_timeout - time.time())
                logging.info(f"  Timeout en:       {remaining:.2f} segundos")
            if raft.fsm_leader.state == "candidate":
                logging.info(f"  Votos recibidos:  {raft.votes_received}")
        elif line == "mq show":
            logging.info("[Message Queue]")
            if message_queue.empty():
                logging.info("  (vacía)")
            else:
                for i, (addr, msg) in enumerate(list(message_queue.queue)):
                    logging.info(f"  [{i}] {addr}: {msg}")
        elif line == "help":
            logging.info("Comandos disponibles:")
            for cmd in ["raft show", "mq show", "help", "exit"]:
                logging.info(f"  {cmd}")
        elif line == "exit":
            app.exit()
        else:
            logging.warning("Comando no reconocido. Escribe 'help' para ver los comandos.")

    # Ejecutar aplicación en hilo separado
    Thread(target=app.run, daemon=True).start()

