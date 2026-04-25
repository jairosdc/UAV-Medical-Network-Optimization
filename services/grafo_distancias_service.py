import math

from models.clases_models import RoutePlan
from hospitales_almacenes_data import HOSPITALS, BASES


class ServicioRed:
    """
    Guarda la red de hospitales y bases.

    Permite:
    - buscar hospitales y bases por nombre,
    - calcular distancias entre nodos,
    - encontrar la base más cercana a un hospital,
    - crear rutas simples para pedidos.
    """

    def __init__(self):
        self.hospitales = HOSPITALS
        self.bases = BASES

    @staticmethod
    def distancia_haversine_km(lat1, lon1, lat2, lon2):
        """
        Calcula la distancia aproximada entre dos coordenadas geográficas.
        """
        radio_tierra_km = 6371.0

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)

        diferencia_lat = math.radians(lat2 - lat1)
        diferencia_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(diferencia_lat / 2) ** 2
            + math.cos(lat1_rad)
            * math.cos(lat2_rad)
            * math.sin(diferencia_lon / 2) ** 2
        )

        return radio_tierra_km * 2 * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )

    def distancia_entre_nodos_km(self, nodo_a, nodo_b):
        """
        Devuelve la distancia en km entre dos nodos de la red.
        """
        return self.distancia_haversine_km(
            nodo_a.lat,
            nodo_a.lon,
            nodo_b.lat,
            nodo_b.lon
        )

    def obtener_hospital(self, nombre):
        """
        Devuelve un hospital por su nombre.
        """
        if nombre not in self.hospitales:
            raise ValueError(f"Hospital no encontrado: {nombre}")

        return self.hospitales[nombre]

    def obtener_base(self, nombre):
        """
        Devuelve una base por su nombre.
        """
        if nombre not in self.bases:
            raise ValueError(f"Base no encontrada: {nombre}")

        return self.bases[nombre]

    def obtener_nodo(self, nombre):
        """
        Devuelve un hospital o una base por su nombre.
        """
        if nombre in self.hospitales:
            return self.hospitales[nombre]

        if nombre in self.bases:
            return self.bases[nombre]

        raise ValueError(f"Nodo no encontrado en la red: {nombre}")

    def listar_hospitales(self):
        """
        Devuelve los nombres de los hospitales.
        """
        return list(self.hospitales.keys())

    def listar_bases(self):
        """
        Devuelve los nombres de las bases.
        """
        return list(self.bases.keys())

    def base_mas_cercana_a(self, nombre_hospital):
        """
        Devuelve la base más cercana a un hospital.

        Devuelve:
        - nombre de la base,
        - distancia desde la base hasta el hospital.
        """
        hospital = self.obtener_hospital(nombre_hospital)

        nombre_base, nodo_base = min(
            self.bases.items(),
            key=lambda item: self.distancia_entre_nodos_km(item[1], hospital)
        )

        distancia = self.distancia_entre_nodos_km(nodo_base, hospital)

        return nombre_base, distancia

    def planificar_reposicion(self, nombre_hospital):
        """
        Crea una ruta de reposición simple:

        base más cercana -> hospital
        """
        nombre_base, distancia = self.base_mas_cercana_a(nombre_hospital)

        return RoutePlan(
            start_base=nombre_base,
            origin_hospital=nombre_base,
            destination_hospital=nombre_hospital,
            distance_base_to_origin_km=0.0,
            distance_origin_to_destination_km=distancia,
            distance_total_km=distancia,
        )

    def planificar_transporte_directo(self, nombre_origen, nombre_destino):
        """
        Crea una ruta para un transporte directo entre dos hospitales.

        Se usa para eventos especiales como órganos:

        base más cercana al origen -> hospital origen -> hospital destino
        """
        origen = self.obtener_hospital(nombre_origen)
        destino = self.obtener_hospital(nombre_destino)

        nombre_base, distancia_base_origen = self.base_mas_cercana_a(nombre_origen)
        distancia_origen_destino = self.distancia_entre_nodos_km(origen, destino)

        distancia_total = distancia_base_origen + distancia_origen_destino

        return RoutePlan(
            start_base=nombre_base,
            origin_hospital=nombre_origen,
            destination_hospital=nombre_destino,
            distance_base_to_origin_km=distancia_base_origen,
            distance_origin_to_destination_km=distancia_origen_destino,
            distance_total_km=distancia_total,
        )