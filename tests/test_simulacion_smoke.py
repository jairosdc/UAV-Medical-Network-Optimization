from simulacion import run_simulation

def test_simulacion_smoke_corta():
    config = {
        "minutos_simulacion": 60,
        "drones_por_base": 1,
        "drones_por_hospital": 1,
        "semilla": 123,
        "factor_demanda_inventario": 0.1,
        "factor_demanda_organos": 0.1,
        "activar_meteorologia": False,
        "generar_graficas": False,
        "verbose": False,
        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    }
    
    resultado = run_simulation(config)
    
    assert isinstance(resultado, dict)
    
    # Comprobar claves requeridas en la salida del motor de simulación
    assert "pedidos_generados" in resultado
    assert "pedidos_completados" in resultado
    assert "tasa_servicio" in resultado
    assert "total_drones" in resultado
    assert "resumen_flota" in resultado
    
    # Validaciones de consistencia básica
    assert resultado["total_drones"] > 0
    assert resultado["pedidos_generados"] >= 0
    assert resultado["pedidos_completados"] <= resultado["pedidos_generados"]
    assert 0.0 <= resultado["tasa_servicio"] <= 1.0
