
from fsm import FSM
import time

# Estado global simulado que el FSMJugador usará
estado_global = {
    "config_recibida": False,
    "todos_comprometieron": False,
    "listo_para_revelar": False,
    "resultado_disponible": False
}

# Crear la instancia del FSMJugador
jugador = FSMJugador(estado_global)

# Simulación de cambios de estado global con activaciones periódicas
for ciclo in range(10):
    print(f"--- Ciclo {ciclo} ---")
    if ciclo == 1:
        estado_global["config_recibida"] = True
    if ciclo == 3:
        estado_global["todos_comprometieron"] = True
    if ciclo == 5:
        estado_global["listo_para_revelar"] = True
    if ciclo == 7:
        estado_global["resultado_disponible"] = True

    jugador.fire()
    time.sleep(1)
