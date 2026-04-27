"""
TelemetriaService - Registro de Eventos de Vuelo para FlyRadar
===============================================================
Captura cada tramo de vuelo (ida y vuelta) con las coordenadas
de origen/destino, tiempos y estado del dron/clima.

Este log se usa para la interpolación de posiciones en la app
de radar (Opción 2: basada en eventos discretos).
"""

import json
from pathlib import Path
from hospitales_almacenes_data import HOSPITALS, BASES


# Diccionario unificado de nodos para buscar coordenadas por nombre
_TODOS_LOS_NODOS = {**HOSPITALS, **BASES}


def _coords_de_nodo(nombre: str) -> dict:
    """Devuelve lat/lon de un nodo por su nombre."""
    nodo = _TODOS_LOS_NODOS.get(nombre)
    if nodo is None:
        return {"nombre": nombre, "lat": 0.0, "lon": 0.0}
    return {"nombre": nodo.nombre, "lat": nodo.lat, "lon": nodo.lon}


class TelemetriaService:
    """
    Acumula registros de tramos de vuelo durante la simulación
    y los exporta a JSON al finalizar.
    """

    def __init__(self):
        self.registros = []

    def registrar_tramo(
        self,
        id_dron: str,
        nombre_origen: str,
        nombre_destino: str,
        t_salida: float,
        t_llegada: float,
        tipo_trayecto: str,
        bateria_inicial: float,
        clima: str,
    ):
        """
        Registra un tramo de vuelo individual.

        Parámetros:
            id_dron:          Identificador del dron (ej. "D01").
            nombre_origen:    Nombre del nodo de salida.
            nombre_destino:   Nombre del nodo de llegada.
            t_salida:         Minuto exacto de despegue.
            t_llegada:        Minuto estimado de llegada (ETA).
            tipo_trayecto:    "ida" (hacia hospital) o "vuelta" (hacia base).
            bateria_inicial:  % de batería al despegar.
            clima:            Nombre del estado climático al despegar.
        """
        registro = {
            "id_dron": id_dron,
            "origen": _coords_de_nodo(nombre_origen),
            "destino": _coords_de_nodo(nombre_destino),
            "t_salida": round(t_salida, 2),
            "t_llegada": round(t_llegada, 2),
            "tipo_trayecto": tipo_trayecto,
            "bateria_inicial": round(bateria_inicial, 2),
            "clima": clima,
        }
        self.registros.append(registro)

    def exportar_json(self, ruta: str = "telemetria_vuelos.json"):
        """Guarda todos los registros en un archivo JSON."""
        ruta_path = Path(ruta)
        with open(ruta_path, "w", encoding="utf-8") as f:
            json.dump(self.registros, f, ensure_ascii=False, indent=2)
        print(f"\n  [TELEMETRIA] {len(self.registros)} tramos guardados en '{ruta_path}'")

    def total_tramos(self) -> int:
        """Devuelve el número de tramos registrados."""
        return len(self.registros)
