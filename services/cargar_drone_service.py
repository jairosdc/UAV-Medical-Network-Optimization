from parametros_globales import CHARGE_RATE_PERCENT_PER_MIN

def procesar_recarga_dron(dron, minutos_transcurridos: int = 1):

    if dron.status != "charging":
        return

    # Proyección lineal del estado de la batería
    bateria_proyectada = dron.battery_percent + (CHARGE_RATE_PERCENT_PER_MIN * minutos_transcurridos)

    # Evaluación de saturación
    if bateria_proyectada >= 100.0:
        dron.battery_percent = 100.0
        dron.status = "available"
        dron.busy_until_min = 0
        dron.current_call_id = None
    else:
        dron.battery_percent = bateria_proyectada