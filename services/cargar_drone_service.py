from parametros_globales import CHARGE_RATE_PERCENT_PER_MIN

def calcular_tiempo_recarga_completa(bateria_actual: float) -> float:
    """
    Calcula analíticamente los minutos exactos necesarios para alcanzar el 100% de capacidad,
    resolviendo la ecuación lineal de carga para su integración en el motor de Eventos Discretos (DES).
   
    A diferencia de un modelo time-slicing, esta función no muta el estado del dron,
    sino que proyecta el horizonte temporal del evento "FIN_RECARGA".
   
    Args:
        bateria_actual (float): Porcentaje de energía del dron en el instante del aterrizaje.
       
    Returns:
        float: Tiempo (en minutos) requerido para completar la carga. Retorna 0.0 si no requiere carga.
    """
    if bateria_actual >= 100.0:
        return 0.0
   
    bateria_faltante = 100.0 - bateria_actual
   
    # Despeje algebraico del tiempo necesario basado en la constante global
    minutos_necesarios = bateria_faltante / CHARGE_RATE_PERCENT_PER_MIN
   
    return minutos_necesarios