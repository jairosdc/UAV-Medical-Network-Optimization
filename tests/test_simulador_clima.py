import pytest
from simulators.simulador_clima import SimuladorClima, ESTADOS_CLIMA

def test_probabilidades_suman_uno():
    """Verifica que la suma de todas las probabilidades sea exactamente 1.0 (o muy cercana)"""
    suma = sum(e.probabilidad for e in ESTADOS_CLIMA)
    assert abs(suma - 1.0) < 0.01, f"Las probabilidades suman {suma}, se esperaba 1.0"

def test_inicializacion_simulador():
    """Verifica que el simulador se inicializa correctamente con los pesos configurados"""
    clima = SimuladorClima()
    assert clima.estado_actual is not None
    assert clima.estado_actual.probabilidad > 0

def test_sorteo_clima():
    """Verifica que el método de actualización retorna un estado válido"""
    clima = SimuladorClima(intervalo_cambio_min=10)
    estado_1 = clima.actualizar(0)
    estado_2 = clima.actualizar(15)  # Debería forzar un sorteo nuevo
    
    assert estado_1 in ESTADOS_CLIMA
    assert estado_2 in ESTADOS_CLIMA
