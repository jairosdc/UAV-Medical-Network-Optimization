"""
red.py
======

Todo lo relacionado con la física del dron en la red geográfica:

  Batería
  -------
  - calcular_autonomia_km        : autonomía en km según carga
  - calcular_consumo_porcentaje  : % de batería consumido en un trayecto
  - calcular_bateria_restante    : batería final tras un vuelo
  - tiene_bateria_suficiente     : comprueba si el dron puede hacer el trayecto
  - calcular_tiempo_recarga_completa : minutos para cargar de X% a 100%

  Red geográfica — ServicioRed
  ----------------------------
  - distancia_haversine_km       : distancia real entre dos coordenadas
  - obtener_hospital / base / nodo
  - listar_hospitales / bases
  - base_mas_cercana_a
  - planificar_reposicion
  - planificar_transporte_directo

  Optimizador de asignación — ServicioDespacho
  --------------------------------------------
  - elegir_mejor_dron : devuelve el mejor dron para cada pedido
"""

import math

from uav_medical_network.config import (
    CARGA_MAXIMA_KG,
    AUTONOMIA_MAX_EN_VACIO,
    BATERIA_MINIMA_VUELO,
    VELOCIDAD_DRON_M_S,
    CHARGE_RATE_PERCENT_PER_MIN,
    HOSPITALS,
    BASES,
)
from uav_medical_network.modelos import RoutePlan, DispatchDecision


# ===========================================================================
# BATERÍA
# ===========================================================================

def calcular_autonomia_km(carga_kg: float) -> float:
    """Autonomía en km del dron según la carga transportada."""
    return AUTONOMIA_MAX_EN_VACIO - (22.0 * carga_kg) / CARGA_MAXIMA_KG


def calcular_consumo_porcentaje(carga_kg: float, distancia_km: float) -> float:
    """% de batería consumido al recorrer distancia_km con carga_kg."""
    autonomia = calcular_autonomia_km(carga_kg)
    return (distancia_km / autonomia) * 100.0


def calcular_bateria_restante(carga_kg: float, distancia_km: float, bateria_inicial_pct: float) -> float:
    """Batería final (%) tras recorrer distancia_km con carga_kg."""
    consumo = calcular_consumo_porcentaje(carga_kg, distancia_km)
    return bateria_inicial_pct - consumo


def tiene_bateria_suficiente(carga_kg: float, distancia_km: float, bateria_inicial_pct: float, reserva_minima_pct: float) -> bool:
    """True si la batería final supera la reserva mínima."""
    return calcular_bateria_restante(carga_kg, distancia_km, bateria_inicial_pct) >= reserva_minima_pct


def calcular_tiempo_recarga_completa(bateria_actual: float) -> float:
    """Minutos necesarios para cargar de bateria_actual% a 100%."""
    if bateria_actual >= 100.0:
        return 0.0
    return (100.0 - bateria_actual) / CHARGE_RATE_PERCENT_PER_MIN


# ===========================================================================
# RED GEOGRÁFICA
# ===========================================================================

class ServicioRed:
    """
    Gestiona la red de hospitales y bases.

    Permite:
    - buscar hospitales y bases por nombre,
    - calcular distancias entre nodos (fórmula haversine),
    - encontrar la base más cercana a un hospital,
    - crear rutas simples para pedidos.
    """

    def __init__(self):
        self.hospitales = HOSPITALS
        self.bases = BASES

    @staticmethod
    def distancia_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia aproximada entre dos coordenadas geográficas (fórmula haversine)."""
        radio = 6371.0
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return radio * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def distancia_entre_nodos_km(self, nodo_a, nodo_b) -> float:
        """Distancia en km entre dos nodos de la red."""
        return self.distancia_haversine_km(nodo_a.lat, nodo_a.lon, nodo_b.lat, nodo_b.lon)

    def obtener_hospital(self, nombre: str):
        if nombre not in self.hospitales:
            raise ValueError(f"Hospital no encontrado: {nombre}")
        return self.hospitales[nombre]

    def obtener_base(self, nombre: str):
        if nombre not in self.bases:
            raise ValueError(f"Base no encontrada: {nombre}")
        return self.bases[nombre]

    def obtener_nodo(self, nombre: str):
        """Devuelve un hospital o una base por su nombre."""
        if nombre in self.hospitales:
            return self.hospitales[nombre]
        if nombre in self.bases:
            return self.bases[nombre]
        raise ValueError(f"Nodo no encontrado en la red: {nombre}")

    def listar_hospitales(self):
        return list(self.hospitales.keys())

    def listar_bases(self):
        return list(self.bases.keys())

    def base_mas_cercana_a(self, nombre_hospital: str):
        """Devuelve (nombre_base, distancia_km) de la base más cercana al hospital."""
        hospital = self.obtener_hospital(nombre_hospital)
        nombre_base, nodo_base = min(
            self.bases.items(),
            key=lambda item: self.distancia_entre_nodos_km(item[1], hospital)
        )
        distancia = self.distancia_entre_nodos_km(nodo_base, hospital)
        return nombre_base, distancia

    def planificar_reposicion(self, nombre_hospital: str) -> RoutePlan:
        """Ruta de reposición: base más cercana → hospital."""
        nombre_base, distancia = self.base_mas_cercana_a(nombre_hospital)
        return RoutePlan(
            start_base=nombre_base,
            origin_hospital=nombre_base,
            destination_hospital=nombre_hospital,
            distance_base_to_origin_km=0.0,
            distance_origin_to_destination_km=distancia,
            distance_total_km=distancia,
        )

    def planificar_transporte_directo(self, nombre_origen: str, nombre_destino: str) -> RoutePlan:
        """Ruta para transporte de órgano: base más cercana → hospital origen → hospital destino."""
        origen = self.obtener_hospital(nombre_origen)
        destino = self.obtener_hospital(nombre_destino)
        nombre_base, distancia_base_origen = self.base_mas_cercana_a(nombre_origen)
        distancia_origen_destino = self.distancia_entre_nodos_km(origen, destino)
        return RoutePlan(
            start_base=nombre_base,
            origin_hospital=nombre_origen,
            destination_hospital=nombre_destino,
            distance_base_to_origin_km=distancia_base_origen,
            distance_origin_to_destination_km=distancia_origen_destino,
            distance_total_km=distancia_base_origen + distancia_origen_destino,
        )


# ===========================================================================
# OPTIMIZADOR DE ASIGNACIÓN
# ===========================================================================

class ServicioDespacho:
    """
    Selecciona el mejor dron para cada pedido.

    Tipos de misión:
    1. Reposición de inventario → drones role="base"
       Ruta: base → hospital → misma base
    2. Transporte de órganos → drones role="hospital"
       Ruta: posición actual → hospital origen → hospital destino
       El dron NO vuelve automáticamente a base.

    Criterio de selección según prioridad del pedido:
      0 (órgano) → minimizar tiempo de llegada
      1 (crítico) → minimizar distancia al origen
      2 (urgente) → minimizar distancia total
      3 (rutinario) → maximizar batería restante
    """

    def __init__(self, servicio_red: ServicioRed):
        self.red = servicio_red

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float, factor_velocidad: float = 1.0) -> int:
        """Minutos que tarda el dron en recorrer distancia_km a la velocidad actual."""
        if distancia_km <= 0:
            return 0
        velocidad_real = VELOCIDAD_DRON_M_S * factor_velocidad
        if velocidad_real <= 0:
            raise ValueError("La velocidad real del dron debe ser positiva.")
        velocidad_km_h = velocidad_real * 3.6
        return max(1, int(round((distancia_km / velocidad_km_h) * 60.0)))

    @staticmethod
    def _es_pedido_organo(pedido) -> bool:
        return getattr(pedido, "tipo_pedido", "inventario") == "organo"

    def _obtener_posicion_actual_dron(self, dron):
        nombre = dron.current_node or dron.base_name
        return self.red.obtener_nodo(nombre)

    def elegir_mejor_dron(self, drones, pedido, factor_velocidad: float = 1.0, tiempo_actual: float = 0):
        """
        Busca el mejor dron disponible para un pedido.

        Devuelve DispatchDecision o None si no hay dron viable ahora.
        """
        es_organo = self._es_pedido_organo(pedido)
        origen = self.red.obtener_nodo(pedido.origin_hospital)
        destino = self.red.obtener_nodo(pedido.destination_hospital)
        candidatos = []

        for dron in drones:
            if dron.status != "available":
                continue

            if es_organo:
                # Solo drones hospitalarios
                if getattr(dron, "role", "base") != "hospital":
                    continue

                nodo_actual = self._obtener_posicion_actual_dron(dron)
                d_actual_origen = self.red.distancia_entre_nodos_km(nodo_actual, origen)
                d_origen_destino = self.red.distancia_entre_nodos_km(origen, destino)
                d_total = d_actual_origen + d_origen_destino

                t_ida = (self.estimar_duracion_minutos(d_actual_origen, factor_velocidad)
                         + self.estimar_duracion_minutos(d_origen_destino, factor_velocidad))
                t_vuelta = 0

                try:
                    bat_tras_recoger = calcular_bateria_restante(0.0, d_actual_origen, dron.battery_percent)
                    bat_final = calcular_bateria_restante(pedido.payload_kg, d_origen_destino, bat_tras_recoger)
                except ValueError:
                    continue

                distancia_to_origin = d_actual_origen

            else:
                # Solo drones de base
                if getattr(dron, "role", "base") != "base":
                    continue

                nombre_pos = dron.current_node or dron.base_name
                if nombre_pos != pedido.origin_hospital:
                    continue

                base = self.red.obtener_base(pedido.origin_hospital)
                d_base_destino = self.red.distancia_entre_nodos_km(base, destino)
                d_destino_base = self.red.distancia_entre_nodos_km(destino, base)
                d_total = d_base_destino + d_destino_base

                t_ida = self.estimar_duracion_minutos(d_base_destino, factor_velocidad)
                t_vuelta = self.estimar_duracion_minutos(d_destino_base, factor_velocidad)

                try:
                    bat_tras_ida = calcular_bateria_restante(pedido.payload_kg, d_base_destino, dron.battery_percent)
                    bat_final = calcular_bateria_restante(0.0, d_destino_base, bat_tras_ida)
                except ValueError:
                    continue

                distancia_to_origin = 0.0

            if bat_final < BATERIA_MINIMA_VUELO:
                continue

            candidatos.append(DispatchDecision(
                drone_id=dron.drone_id,
                call_id=pedido.call_id,
                priority=pedido.priority,
                distance_to_origin_km=distancia_to_origin,
                distance_total_km=d_total,
                battery_before_percent=dron.battery_percent,
                battery_after_percent=bat_final,
                estimated_duration_min=t_ida + t_vuelta,
                estimated_flight_ida_min=t_ida,
                estimated_flight_vuelta_min=t_vuelta,
                score=0.0,
            ))

        if not candidatos:
            return None
        return self._ordenar_candidatos(candidatos, pedido)

    def _ordenar_candidatos(self, candidatos, pedido):
        """Ordena según la prioridad del pedido y devuelve el mejor."""
        if pedido.priority == 0:
            candidatos.sort(key=lambda c: (c.estimated_flight_ida_min, c.distance_to_origin_km, -c.battery_after_percent))
        elif pedido.priority == 1:
            candidatos.sort(key=lambda c: (c.distance_to_origin_km, c.estimated_flight_ida_min, -c.battery_after_percent))
        elif pedido.priority == 2:
            candidatos.sort(key=lambda c: (c.distance_total_km, c.estimated_duration_min, -c.battery_after_percent))
        else:
            candidatos.sort(key=lambda c: (-c.battery_after_percent, c.distance_total_km, c.estimated_duration_min))
        return candidatos[0]
