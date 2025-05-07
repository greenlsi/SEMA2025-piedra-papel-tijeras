from fsm import FSM
from server import start_server, message_queue, connect_to_peer, connections, lock
import threading
import time
import sys

# Propia dirección
my_host, my_port = sys.argv[1].split(":")
my_port = int(my_port)
my_addr = sys.argv[1]

# Otras direcciones
others = sys.argv[2:]

# Arranca el servidor
threading.Thread(target=start_server, args=(my_host, my_port), daemon=True).start()

# Conecta con los otros nodos
for peer in others:
    host, port = peer.split(":")
    threading.Thread(target=connect_to_peer, args=(host, int(port)), daemon=True).start()

# FSM
def hay_mensaje():
    return not message_queue.empty()

def tiempo_expirado():
    return time.time() - tiempo_expirado.last_time > 5
tiempo_expirado.last_time = time.time()

def imprimir_mensaje():
    address, msg = message_queue.get()
    print(f"[FSM] Mensaje de {address}: {msg}")

def enviar_ping():
    mensaje = f"Ping de {my_addr}"
    with lock:
        for conn in list(connections):
            try:
                conn.sendall(mensaje.encode('utf-8'))
            except:
                connections.remove(conn)
    tiempo_expirado.last_time = time.time()

fsm = FSM("MainFSM", "activo", [
    ("activo", hay_mensaje, "activo", imprimir_mensaje),
    ("activo", tiempo_expirado, "activo", enviar_ping)
])

while True:
    fsm.fire()
    time.sleep(0.1)

