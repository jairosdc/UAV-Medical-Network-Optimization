"""
escenarios.py
=============

Configuraciones predefinidas para ejecutar simulaciones.

Este archivo NO ejecuta simulaciones.
Solo guarda diccionarios de configuración.

El motor sigue estando en:

    simulators/experimentacion.py

Uso esperado:

    config = ESCENARIOS["normal"].copy()
    resultado = run_simulation(config)
"""


ESCENARIOS = {
    "normal": {
        "minutos_simulacion": 10080,
        "drones_por_base": 2,
        "drones_por_hospital": 1,
        "semilla": 42,

        "factor_demanda_inventario": 1.0,
        "factor_demanda_organos": 1.0,
        "escenario_clima": "normal",

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "generar_graficas": True,
        "verbose": True,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    },

    "alta_demanda": {
        "minutos_simulacion": 10080,
        "drones_por_base": 2,
        "drones_por_hospital": 1,
        "semilla": 42,

        "factor_demanda_inventario": 1.8,
        "factor_demanda_organos": 1.5,
        "escenario_clima": "normal",

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "generar_graficas": True,
        "verbose": True,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    },

    "lluvia_alta_demanda": {
        "minutos_simulacion": 10080,
        "drones_por_base": 2,
        "drones_por_hospital": 1,
        "semilla": 42,

        "factor_demanda_inventario": 1.8,
        "factor_demanda_organos": 1.5,
        "escenario_clima": "lluvioso",

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "generar_graficas": True,
        "verbose": True,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    },

    "baja_demanda_clima_adverso": {
        "minutos_simulacion": 10080,
        "drones_por_base": 1,
        "drones_por_hospital": 1,
        "semilla": 42,

        "factor_demanda_inventario": 0.7,
        "factor_demanda_organos": 1.0,
        "escenario_clima": "adverso",

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "generar_graficas": True,
        "verbose": True,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    },

    "estres_extremo": {
        "minutos_simulacion": 10080,
        "drones_por_base": 1,
        "drones_por_hospital": 1,
        "semilla": 42,

        "factor_demanda_inventario": 2.5,
        "factor_demanda_organos": 2.0,
        "escenario_clima": "adverso",

        "activar_meteorologia": True,
        "intervalo_cambio_clima_min": 300,
        "stock_inicial_cerca_umbral": False,

        "generar_graficas": True,
        "verbose": True,

        "imprimir_eventos_drones": False,
        "imprimir_eventos_hospital": False,
        "imprimir_eventos_clima": False,
    },
}