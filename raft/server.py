import socket
import threading
import queue
import time
import logging

message_queue = queue.Queue()
connections = []
lock = threading.Lock()

def handle_client(client_socket, address):
    logging.info(f"Conexión establecida con {address}")
    try:
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            message_queue.put((address, message))
            logging.info(f"<recv> {message}")
    finally:
        client_socket.close()

def start_server(host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    logging.info(f"Servidor escuchando en {host}:{port}")
    while True:
        client_socket, addr = server.accept()
        threading.Thread(target=handle_client, args=(client_socket, addr), daemon=True).start()

def connect_to_peer(addr, port):
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((addr, port))
            with lock:
                connections.append(s)
            logging.info(f"Conectado a {addr}:{port}")
            return
        except Exception:
            time.sleep(2)

