import logging

class FSM:
    def __init__(self, name, initial_state, transitions):
        """
        Inicializa una máquina de estados finitos.
        transiciones: lista de 4-tuplas (orig_state, condition, dest_state, action)
        """
        self.name = name
        self.state = initial_state
        self.transitions = transitions

    def fire(self):
        """
        Evalúa las condiciones de las transiciones desde el estado actual.
        Ejecuta la primera transición cuya condición se cumple. 
        Esto hace que toda FSM sea determinista.
        """
        for orig, cond, dest, action in self.transitions:
            if self.state == orig and cond():
                logging.debug(f"[{self.name}] {orig} --({cond.__name__})--> {dest}")
                action()
                self.state = dest
                break

