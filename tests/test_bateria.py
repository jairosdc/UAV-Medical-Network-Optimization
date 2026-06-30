from red import (
    calcular_autonomia_km,
    calcular_bateria_restante,
    tiene_bateria_suficiente,
)

def test_autonomia_decrece_con_carga():
    # Sin carga vs Carga máxima
    autonomia_vacio = calcular_autonomia_km(0.0)
    autonomia_cargado = calcular_autonomia_km(4.7)
    
    assert autonomia_vacio > autonomia_cargado
    assert autonomia_vacio == 94.0
    assert autonomia_cargado == 72.0  # 94.0 - 22.0 * 4.7 / 4.7

def test_bateria_restante_decrece_con_distancia():
    # Misma carga (0.0 kg), distintas distancias
    bat_corta = calcular_bateria_restante(0.0, 10.0, 100.0)
    bat_larga = calcular_bateria_restante(0.0, 30.0, 100.0)
    
    assert bat_corta > bat_larga
    assert bat_corta < 100.0

def test_tiene_bateria_suficiente():
    # Caso viable: distancia corta, batería llena, reserva 5%
    assert tiene_bateria_suficiente(0.0, 10.0, 100.0, 5.0) is True
    
    # Caso no viable: distancia extremadamente larga (supera autonomía)
    assert tiene_bateria_suficiente(0.0, 100.0, 100.0, 5.0) is False
    
    # Caso no viable por reserva mínima al límite
    # Autonomía con 0kg = 94km. Consumo para 90km = 90/94 * 100 = 95.74%
    # Batería restante = 100 - 95.74 = 4.26%. Si reserva es 5%, no es suficiente.
    assert tiene_bateria_suficiente(0.0, 90.0, 100.0, 5.0) is False
