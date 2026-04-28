from parametros_globales import CARGA_MAXIMA_KG, AUTONOMIA_MAX_EN_VACIO

def calcular_autonomia_km(carga_kg):
    return AUTONOMIA_MAX_EN_VACIO - (22.0 * carga_kg) / CARGA_MAXIMA_KG

def calcular_consumo_porcentaje(carga_kg, distancia_km):
    autonomia = calcular_autonomia_km(carga_kg)
    return (distancia_km / autonomia) * 100.0

def calcular_bateria_restante(carga_kg, distancia_km, bateria_inicial_pct):
    consumo = calcular_consumo_porcentaje(carga_kg, distancia_km)
    return bateria_inicial_pct - consumo

def tiene_bateria_suficiente(carga_kg, distancia_km, bateria_inicial_pct, reserva_minima_pct):
    bateria_final = calcular_bateria_restante(carga_kg, distancia_km, bateria_inicial_pct)
    return bateria_final >= reserva_minima_pct