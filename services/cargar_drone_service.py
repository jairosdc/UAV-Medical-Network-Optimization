from parametros_globales import CHARGE_RATE_PERCENT_PER_MIN

def calcular_tiempo_recarga_completa(bateria_actual: float) -> float:
   
    if bateria_actual >= 100.0:
        return 0.0
   
    bateria_faltante = 100.0 - bateria_actual
   
    # Despeje algebraico del tiempo necesario basado en la constante global
    minutos_necesarios = bateria_faltante / CHARGE_RATE_PERCENT_PER_MIN
   
    return minutos_necesarios