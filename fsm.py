
class FSM:
    def __init__(self, nombre, estado_inicial, transiciones):
        """
        Inicializa una máquina de estados finitos.
        transiciones: lista de 4-tuplas (estado_origen, condicion, estado_destino, accion)
        """
        self.nombre = nombre
        self.estado = estado_inicial
        self.transiciones = transiciones

    def fire(self):
        """
        Evalúa las condiciones de las transiciones desde el estado actual.
        Ejecuta la primera transición cuya condición se cumple.
        """
        for origen, condicion, destino, accion in self.transiciones:
            if self.estado == origen and condicion():
                print(f"[{self.nombre}] {origen} --({condicion.__name__})--> {destino}")
                accion()
                self.estado = destino
                break

