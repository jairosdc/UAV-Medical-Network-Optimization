import math
from typing import Dict, Tuple

from models.clases_models import Node, RoutePlan
from hospitales_almacenes_data import HOSPITALS, BASES


class ServicioRed:
    """Gestiona la red de hospitales y bases, y calcula rutas entre ellos."""

    def __init__(self):
        self.hospitales: Dict[str, Node] = HOSPITALS
        self.bases: Dict[str, Node] = BASES

    @staticmethod
    def _distancia_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula la distancia en km entre dos coordenadas usando la fórmula de Haversine."""
        RADIO_TIERRA_KM = 6371.0
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        diferencia_lat  = math.radians(lat2 - lat1)
        diferencia_lon  = math.radians(lon2 - lon1)

        a = (math.sin(diferencia_lat / 2) ** 2
             + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(diferencia_lon / 2) ** 2)
        return RADIO_TIERRA_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def distancia_entre_nodos_km(self, nodo_a: Node, nodo_b: Node) -> float:
        # Devuelve la distancia en km entre dos nodos de la red. Es la matriz de adyacencia
        return self._distancia_haversine_km(nodo_a.lat, nodo_a.lon, nodo_b.lat, nodo_b.lon)

    # ------------------------------------------------------------------
    # Acceso a nodos
    # ------------------------------------------------------------------

    def obtener_hospital(self, nombre: str) -> Node:
        """Devuelve el hospital con ese nombre, o lanza error si no existe."""
        if nombre not in self.hospitales:
            raise ValueError(f"Hospital no encontrado: {nombre}")
        return self.hospitales[nombre]

    def obtener_base(self, nombre: str) -> Node:
        """Devuelve la base con ese nombre, o lanza error si no existe."""
        if nombre not in self.bases:
            raise ValueError(f"Base no encontrada: {nombre}")
        return self.bases[nombre]

    def obtener_nodo(self, nombre: str) -> Node:
        """Devuelve cualquier nodo de la red (hospital o base) por su nombre."""
        if nombre in self.hospitales:
            return self.hospitales[nombre]
        if nombre in self.bases:
            return self.bases[nombre]
        raise ValueError(f"Nodo no encontrado en la red: {nombre}")

    def listar_hospitales(self) -> list:
        """Devuelve los nombres de todos los hospitales disponibles."""
        return list(self.hospitales.keys())

    def listar_bases(self) -> list:
        """Devuelve los nombres de todas las bases disponibles."""
        return list(self.bases.keys())

    def list_bases(self) -> list:
        """Alias en ingles para compatibilidad."""
        return self.listar_bases()

    # ------------------------------------------------------------------
    # Lógica de rutas
    # ------------------------------------------------------------------

    def base_mas_cercana_a(self, nombre_hospital: str) -> Tuple[str, float]:
        """Devuelve la base más cercana a un hospital y la distancia en km hasta él."""
        hospital = self.obtener_hospital(nombre_hospital)
        nombre_base, nodo_base = min(
            self.bases.items(),
            key=lambda item: self.distancia_entre_nodos_km(item[1], hospital)
        )
        return nombre_base, self.distancia_entre_nodos_km(nodo_base, hospital)

    def planificar_reposicion(self, nombre_hospital: str) -> RoutePlan:
        """
        Calcula la ruta de reposición:
            base más cercana → hospital que necesita stock
        """
        hospital = self.obtener_hospital(nombre_hospital)
        base, distancia = self.base_mas_cercana_a(nombre_hospital)

        return RoutePlan(
            start_base                        = base,
            origin_hospital                   = base,          # el origen ES la base
            destination_hospital              = nombre_hospital,
            distance_base_to_origin_km        = 0.0,           # no hay tramo previo
            distance_origin_to_destination_km = distancia,
            distance_total_km                 = distancia,
        )

    def build_route_plan(self, origin_hospital: str, destination_hospital: str) -> RoutePlan:
        """Calcula la ruta: base mas cercana -> origen -> destino."""
        base, distancia_base_origen = self.base_mas_cercana_a(origin_hospital)
        nodo_origen = self.obtener_hospital(origin_hospital)
        nodo_destino = self.obtener_hospital(destination_hospital)

        distancia_origen_destino = self.distancia_entre_nodos_km(nodo_origen, nodo_destino)

        return RoutePlan(
            start_base=base,
            origin_hospital=origin_hospital,
            destination_hospital=destination_hospital,
            distance_base_to_origin_km=distancia_base_origen,
            distance_origin_to_destination_km=distancia_origen_destino,
            distance_total_km=distancia_base_origen + distancia_origen_destino,
        )


class NetworkService(ServicioRed):
    """Alias de compatibilidad para el nombre anterior."""
    pass