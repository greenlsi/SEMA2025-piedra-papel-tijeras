from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.buffer import Buffer
from threading import Thread
import time

def start_shell(raft):
    # Widgets
    log_window = TextArea(style='class:log', scrollbar=True, wrap_lines=False, read_only=True)
    input_window = TextArea(height=1, prompt='> ', style='class:input')

    # Layout
    root_container = HSplit([
        log_window,
        input_window,
    ])

    layout = Layout(container=root_container, focused_element=input_window)

    # Key bindings
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        line = input_window.text.strip()
        input_window.text = ''
        process_command(line)

    style = Style.from_dict({
        'log': 'bg:#1e1e1e #ffffff',
        'input': 'bg:#444444 #ffffff',
    })

    app = Application(layout=layout, key_bindings=kb, full_screen=True, style=style)

    def log(msg):
        log_window.buffer.insert_text(msg + '\n', move_cursor_to_end=True)

    def process_command(line):
        if not line:
            return

        if line == "raft show":
            log("[Raft STATUS]")
            log(f"  Estado LE:        {raft.fsm_leader.state}")
            log(f"  Término actual:   {raft.term}")
            log(f"  Votado por:       {raft.voted_for}")
            log(f"  Soy líder:        {'sí' if raft.is_leader() else 'no'}")
            if raft.fsm_leader.state in ("follower", "candidate"):
                remaining = max(0, raft.election_timeout - time.time())
                log(f"  Timeout en:       {remaining:.2f} segundos")
            if raft.fsm_leader.state == "candidate":
                log(f"  Votos recibidos:  {raft.votes_received}")
        elif line == "mq show":
            from server import message_queue
            log("[Message Queue]")
            if message_queue.empty():
                log("  (vacía)")
            else:
                for i, (addr, msg) in enumerate(list(message_queue.queue)):
                    log(f"  [{i}] {addr}: {msg}")
        elif line == "help":
            log("Comandos disponibles:")
            for cmd in ["raft show", "mq show", "help", "exit"]:
                log(f"  {cmd}")
        elif line == "exit":
            app.exit()
        else:
            log("Comando no reconocido. Escribe 'help' para ver los comandos.")

    # Lanza en hilo para evitar bloqueo
    Thread(target=app.run, daemon=True).start()

