import json
from typing import Tuple, List, Union


def encode_command(line: str) -> bytes:
    """
    Convierte una línea de comando de texto en bytes (formato JSON serializado).
    Ejemplo: "set key1 value1" → b'{"action": "set", "args": ["key1", "value1"]}'
    """
    parts = line.strip().split()
    if not parts:
        raise ValueError("Empty command line")

    return json.dumps({
        "action": parts[0],
        "args": parts[1:]
    }).encode("utf-8")


def encode_no_op() -> bytes:
    """
    Comando especial NO_OP codificado como JSON.
    """
    return json.dumps({"action": "NO_OP"}).encode("utf-8")


def decode_command(data: Union[bytes, str]) -> Tuple[str, List[str]]:
    """
    Decodifica bytes JSON de vuelta a (acción, lista de argumentos).
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    obj = json.loads(data)
    return obj["action"], obj.get("args", [])


# Ejemplos de uso:
if __name__ == "__main__":
    raw = "set temperature 22"
    encoded = encode_command(raw)
    print("Encoded:", encoded)

    action, args = decode_command(encoded)
    print("Decoded:", action, args)

    no_op = encode_no_op()
    print("NO_OP:", decode_command(no_op))

