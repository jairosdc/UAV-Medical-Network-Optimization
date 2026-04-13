from parametros_globales import CARGA_MAXIMA_KG, AUTONOMIA_MAX_EN_VACIO

def calcular_autonomia_km(carga_kg: float) -> float:
    """
    Calcula la distancia máxima que puede recorrer el dron con una carga específica.
    A mayor peso, menor autonomía.
    """
    if carga_kg < 0:
        raise ValueError("La carga no puede ser negativa.")
    if carga_kg > CARGA_MAXIMA_KG:
        raise ValueError(f"La carga excede el máximo permitido ({CARGA_MAXIMA_KG} kg).")
        
    return AUTONOMIA_MAX_EN_VACIO - (22.0 * carga_kg) / CARGA_MAXIMA_KG

def calcular_consumo_porcentaje(carga_kg: float, distancia_km: float) -> float:
    """
    Calcula el porcentaje de batería que se consumirá para recorrer una distancia dada.
    """
    autonomia = calcular_autonomia_km(carga_kg)
    return (distancia_km / autonomia) * 100.0

def calcular_bateria_restante(carga_kg: float, distancia_km: float, bateria_inicial_pct: float) -> float:
    """
    Devuelve el porcentaje de batería que quedará al finalizar el vuelo.
    """
    consumo = calcular_consumo_porcentaje(carga_kg, distancia_km)
    return bateria_inicial_pct - consumo

def tiene_bateria_suficiente(carga_kg: float, distancia_km: float, bateria_inicial_pct: float, reserva_minima_pct: float) -> bool:
    """
    Evalúa la función indicatriz de viabilidad energética.
    Retorna True si el dron puede completar el vuelo y mantener el umbral de reserva de seguridad.
    """
    bateria_final = calcular_bateria_restante(carga_kg, distancia_km, bateria_inicial_pct)
    return bateria_final >= reserva_minima_pct