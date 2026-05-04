"""
telemetria_service.py - Logger de telemetría basado en eventos
==============================================================

Registra cada vuelo (ida y vuelta) del sistema DES sin alterar
la lógica de negocio.  Al finalizar la simulación se exporta
un JSON que la app de radar consume para animar los drones.
"""

import json
import os

from hospitales_almacenes_data import HOSPITALS, BASES


# Diccionario combinado nombre -> (lat, lon) para resolución rápida
_COORDENADAS_NODOS = {}

for nombre, nodo in HOSPITALS.items():
    _COORDENADAS_NODOS[nombre] = (nodo.lat, nodo.lon)

for nombre, nodo in BASES.items():
    _COORDENADAS_NODOS[nombre] = (nodo.lat, nodo.lon)


def _coords(nombre_nodo):
    """Devuelve (lat, lon) de un nodo por su nombre."""
    if nombre_nodo in _COORDENADAS_NODOS:
        return _COORDENADAS_NODOS[nombre_nodo]
    return (0.0, 0.0)


class TelemetriaLogger:
    """
    Acumula registros de vuelo durante la simulación.

    Cada registro contiene la información mínima necesaria para
    interpolar la posición del dron en cualquier instante t:

    - dron_id
    - origen / destino  (nombres de nodo)
    - lat/lon de origen y destino
    - t_salida / t_llegada  (minutos de simulación)
    - tipo_mision  ("inventario", "organo", "vuelta_base")
    - bateria  (% estimado del dron al despacho)
    """

    def __init__(self):
        self.vuelos = []

    def registrar_vuelo(
        self,
        dron_id,
        origen,
        destino,
        t_salida,
        t_llegada,
        tipo_mision,
        bateria,
    ):
        """Registra un segmento de vuelo (ida o vuelta)."""
        lat_o, lon_o = _coords(origen)
        lat_d, lon_d = _coords(destino)

        self.vuelos.append({
            "dron_id": dron_id,
            "origen": origen,
            "destino": destino,
            "lat_origen": lat_o,
            "lon_origen": lon_o,
            "lat_destino": lat_d,
            "lon_destino": lon_d,
            "t_salida": round(t_salida, 2),
            "t_llegada": round(t_llegada, 2),
            "tipo_mision": tipo_mision,
            "bateria": round(bateria, 1),
        })

    def exportar_json(self, ruta_archivo="telemetria_vuelos.json"):
        """
        Sobrescribe el archivo JSON con todos los vuelos registrados.

        Se coloca en la raíz del proyecto por defecto.
        """
        ruta_absoluta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ruta_archivo,
        )

        with open(ruta_absoluta, "w", encoding="utf-8") as archivo:
            json.dump(
                {"vuelos": self.vuelos, "total": len(self.vuelos)},
                archivo,
                ensure_ascii=False,
                indent=2,
            )

        return ruta_absoluta
