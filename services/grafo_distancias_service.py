import math
from typing import Dict, Tuple
from  models.clases_models import Node, RoutePlan
from  hospitales_almacenes_data import HOSPITALS, BASES


class NetworkService:
    def __init__(self):
        self.hospitals: Dict[str, Node] = HOSPITALS
        self.bases: Dict[str, Node] = BASES

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)

        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def distance_between_nodes(self, a: Node, b: Node) -> float:
        return self.haversine_km(a.lat, a.lon, b.lat, b.lon)

    def get_hospital(self, name: str) -> Node:
        if name not in self.hospitals:
            raise ValueError(f"Hospital no encontrado: {name}")
        return self.hospitals[name]

    def get_base(self, name: str) -> Node:
        if name not in self.bases:
            raise ValueError(f"Base no encontrada: {name}")
        return self.bases[name]

    def choose_best_base_for_origin(self, origin_hospital_name: str) -> Tuple[str, float]:
        origin = self.get_hospital(origin_hospital_name)

        best_base_name = None
        best_distance = float("inf")

        for base_name, base in self.bases.items():
            d = self.distance_between_nodes(base, origin)
            if d < best_distance:
                best_distance = d
                best_base_name = base_name

        return best_base_name, best_distance

    def build_route_plan(self, origin_hospital_name: str, destination_hospital_name: str) -> RoutePlan:
        origin = self.get_hospital(origin_hospital_name)
        destination = self.get_hospital(destination_hospital_name)

        best_base_name, base_to_origin = self.choose_best_base_for_origin(origin_hospital_name)
        origin_to_destination = self.distance_between_nodes(origin, destination)

        return RoutePlan(
            start_base=best_base_name,
            origin_hospital=origin_hospital_name,
            destination_hospital=destination_hospital_name,
            distance_base_to_origin_km=base_to_origin,
            distance_origin_to_destination_km=origin_to_destination,
            distance_total_km=base_to_origin + origin_to_destination,
        )

    def list_hospitals(self):
        return list(self.hospitals.keys())

    def list_bases(self):
        return list(self.bases.keys())