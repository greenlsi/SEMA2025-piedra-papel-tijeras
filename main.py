from fsm import FSM
from server import start_server, message_queue, connect_to_peer, connections, lock
from raft import RaftNode
import threading
import time
import sys
from shell import start_shell

# Dirección propia
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

# Instancia de Raft
raft = RaftNode(my_addr, others)

start_shell(raft)

# Bucle principal
while True:
    raft.fire()
    time.sleep(1)

