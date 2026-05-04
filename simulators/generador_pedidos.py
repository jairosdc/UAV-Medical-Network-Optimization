import random
import math
import numpy as np

from parametros_globales import CARGA_MAXIMA_KG
from models.clases_models import DeliveryCall


# ---------------------------------------------------------------------------
# TASAS DE CONSUMO INTRAHOSPITALARIO
# ---------------------------------------------------------------------------
# Interpretación:
# - Cada tasa está en eventos/hora por hospital.
# - Ejemplo: "suero": 0.60 significa que cada hospital consume suero
#   con media 0.60 veces por hora.
# ---------------------------------------------------------------------------

TASAS_PRODUCTOS = {
    "sangre":              0.30,
    "farmaco_uci":         0.20,
    "antibiotico":         0.80,
    "suero":               0.60,
    "plasma":              0.25,
    "analgesico":          1.20,
    "material_sanitario":  1.00,
    "medicamento_general": 0.90,
}


# ---------------------------------------------------------------------------
# PESO POR UNIDAD
# ---------------------------------------------------------------------------

PESO_UNIDAD_KG = {
    "sangre":              0.50,
    "farmaco_uci":         0.10,
    "antibiotico":         0.05,
    "suero":               0.60,
    "plasma":              0.25,
    "analgesico":          0.02,
    "material_sanitario":  0.10,
    "medicamento_general": 0.05,
}


# ---------------------------------------------------------------------------
# PRIORIDADES
# ---------------------------------------------------------------------------
# 0 = órgano / emergencia máxima
# 1 = crítica
# 2 = urgente
# 3 = rutinaria
# ---------------------------------------------------------------------------

PRIORIDAD_PRODUCTO = {
    "corazon":             0,
    "pulmon":              0,
    "rinon":               0,
    "pancreas":            0,

    "sangre":              1,
    "farmaco_uci":         1,

    "antibiotico":         2,
    "suero":               2,
    "plasma":              2,

    "analgesico":          3,
    "material_sanitario":  3,
    "medicamento_general": 3,
}


# ---------------------------------------------------------------------------
# ÓRGANOS
# ---------------------------------------------------------------------------
# Interpretación:
# - Los órganos NO son inventario.
# - Son eventos raros globales de la red.
# - La tasa_lambda está en eventos/hora para toda la red.
# ---------------------------------------------------------------------------

CONFIGURACION_ORGANOS = {
    "corazon": {
        "isquemia_min": 240,
        "peso_kg": 2.1,
        "tasa_lambda": 0.005,
    },
    "pulmon": {
        "isquemia_min": 360,
        "peso_kg": 2.5,
        "tasa_lambda": 0.008,
    },
    "pancreas": {
        "isquemia_min": 720,
        "peso_kg": 1.9,
        "tasa_lambda": 0.020,
    },
    "rinon": {
        "isquemia_min": 1440,
        "peso_kg": 3.2,
        "tasa_lambda": 0.020,
    },
}


# ---------------------------------------------------------------------------
# FACTORES HORARIOS DEL NHPP
# ---------------------------------------------------------------------------
# factor_lambda multiplica la intensidad de consumo según la franja horaria.
# ---------------------------------------------------------------------------

FACTORES_HORARIOS = [
    (0,   6,  0.48),
    (6,   9,  1.00),
    (9,   14, 1.60),
    (14,  16, 1.13),
    (16,  20, 1.30),
    (20,  24, 0.60),
]


class GeneradorPedidos:
    """
    Genera eventos de simulación:

    1. Consumos intrahospitalarios de productos inventariables.
       - Cada hospital consume según TASAS_PRODUCTOS.
       - Si el inventario baja del umbral, se genera una reposición.

    2. Aparición de órganos.
       - Los órganos se generan como eventos raros globales.
       - No pasan por inventario.
       - Generan pedidos hospital -> hospital.
    """

    def __init__(self, hospitales, bases, semilla=None, duracion_min=1440):
        self.hospitales = hospitales
        self.bases = bases

        self._contador_pedidos = 0
        self._agenda = {}
        self._duracion_min = duracion_min

        if semilla is not None:
            np.random.seed(semilla)
            random.seed(semilla)

        self._pregenerar_periodo()

    # -----------------------------------------------------------------------
    # PREGNERACIÓN DE EVENTOS
    # -----------------------------------------------------------------------

    def _pregenerar_periodo(self):
        """
        Rellena la agenda de eventos para todo el horizonte de simulación.
        """
        minutos_por_dia = 1440

        dias_completos = self._duracion_min // minutos_por_dia
        minutos_extra = self._duracion_min % minutos_por_dia

        for dia in range(dias_completos):
            offset = dia * minutos_por_dia
            self._pregenerar_dia(offset, minutos_por_dia)

        if minutos_extra > 0:
            offset = dias_completos * minutos_por_dia
            self._pregenerar_dia(offset, minutos_extra)

    def _pregenerar_dia(self, offset_min: int, duracion_dia_min: int):
        """
        Genera los eventos de un día completo o parcial.
        """
        fin_periodo = offset_min + duracion_dia_min

        for h_inicio, h_fin, factor in FACTORES_HORARIOS:
            t_inicio = offset_min + h_inicio * 60
            t_fin = min(offset_min + h_fin * 60, fin_periodo)

            if t_inicio >= fin_periodo:
                break

            duracion_h = (t_fin - t_inicio) / 60.0

            self._generar_tramo(
                t_inicio_min=t_inicio,
                t_fin_min=t_fin,
                duracion_h=duracion_h,
                factor=factor,
            )

    def _generar_tramo(
        self,
        t_inicio_min: int,
        t_fin_min: int,
        duracion_h: float,
        factor: float,
    ):
        """
        Genera todos los eventos de una franja horaria.
        """
        self._generar_consumos_inventario(
            t_inicio_min=t_inicio_min,
            t_fin_min=t_fin_min,
            duracion_h=duracion_h,
            factor=factor,
        )

        self._generar_eventos_organos(
            t_inicio_min=t_inicio_min,
            t_fin_min=t_fin_min,
            duracion_h=duracion_h,
        )

    def _generar_consumos_inventario(
        self,
        t_inicio_min: int,
        t_fin_min: int,
        duracion_h: float,
        factor: float,
    ):
        """
        Genera consumos de inventario.

        Cada hospital tiene su propio proceso de consumo.
        Esta es la parte importante: la tasa NO se reparte entre hospitales.
        """
        for hospital in self.hospitales:
            for producto, tasa_base in TASAS_PRODUCTOS.items():

                tasa_efectiva = tasa_base * factor
                n_eventos = np.random.poisson(tasa_efectiva * duracion_h)

                if n_eventos == 0:
                    continue

                minutos = np.random.uniform(
                    t_inicio_min,
                    t_fin_min,
                    size=n_eventos,
                )

                for minuto in minutos:
                    self._agendar_evento(
                        minuto=int(minuto),
                        tipo="inventario",
                        hospital=hospital,
                        producto=producto,
                    )

    def _generar_eventos_organos(
        self,
        t_inicio_min: int,
        t_fin_min: int,
        duracion_h: float,
    ):
        """
        Genera órganos como eventos raros globales de la red.
        """
        for organo, config in CONFIGURACION_ORGANOS.items():

            tasa_lambda = config["tasa_lambda"]
            n_eventos = np.random.poisson(tasa_lambda * duracion_h)

            if n_eventos == 0:
                continue

            minutos = np.random.uniform(
                t_inicio_min,
                t_fin_min,
                size=n_eventos,
            )

            for minuto in minutos:
                self._agendar_evento(
                    minuto=int(minuto),
                    tipo="organo",
                    hospital=random.choice(self.hospitales),
                    producto=organo,
                )

    def _agendar_evento(self, minuto: int, tipo: str, hospital, producto: str):
        """
        Guarda un evento en la agenda interna.
        """
        self._agenda.setdefault(minuto, []).append({
            "tipo": tipo,
            "hospital": hospital,
            "producto": producto,
        })

    # -----------------------------------------------------------------------
    # EJECUCIÓN MINUTO A MINUTO
    # -----------------------------------------------------------------------

    def procesar_minuto(
        self,
        minuto_actual,
        inventarios,
        cola_pedidos,
        verbose=False,
    ):
        """
        Procesa los eventos programados para un minuto concreto.
        """
        eventos = self._agenda.get(minuto_actual, [])

        for evento in eventos:
            tipo_evento = evento["tipo"]

            if tipo_evento == "inventario":
                self._procesar_consumo_inventario(
                    evento=evento,
                    minuto_actual=minuto_actual,
                    inventarios=inventarios,
                    cola_pedidos=cola_pedidos,
                    verbose=verbose,
                )

            elif tipo_evento == "organo":
                self._procesar_evento_organo(
                    evento=evento,
                    minuto_actual=minuto_actual,
                    cola_pedidos=cola_pedidos,
                    verbose=verbose,
                )

    def _procesar_consumo_inventario(
        self,
        evento,
        minuto_actual,
        inventarios,
        cola_pedidos,
        verbose=False,
    ):
        """
        Aplica un consumo intrahospitalario.

        Si el producto cae bajo el umbral, crea uno o varios pedidos
        de reposición desde la base más cercana.
        """
        hospital = evento["hospital"]
        producto = evento["producto"]

        if verbose:
            print(
                f"  [t={minuto_actual:04d}] CONSUMO: "
                f"{hospital.nombre} gasta 1ud {producto}"
            )

        inventario_hospital = inventarios[hospital.nombre]

        unidades_a_reponer = inventario_hospital.registrar_consumo(
            producto,
            1,
        )

        if unidades_a_reponer <= 0:
            return

        if verbose:
            print(
                f"  [!] UMBRAL {producto}: "
                f"{hospital.nombre} solicita {unidades_a_reponer} uds"
            )

        pedidos_reposicion = self._crear_pedidos_reposicion(
            hospital=hospital,
            producto=producto,
            unidades_totales=unidades_a_reponer,
            minuto_actual=minuto_actual,
        )

        for pedido in pedidos_reposicion:
            cola_pedidos.añadir_pedido(pedido)

    def _procesar_evento_organo(
        self,
        evento,
        minuto_actual,
        cola_pedidos,
        verbose=False,
    ):
        """
        Crea un pedido hospital -> hospital para transportar un órgano.
        """
        hospital_origen = evento["hospital"]
        producto = evento["producto"]

        if verbose:
            print(
                f"  [!] CÓDIGO ROJO [t={minuto_actual:04d}]: "
                f"Órgano disponible ({producto}) en {hospital_origen.nombre}"
            )

        pedido = self._crear_pedido_organo(
            hospital_origen=hospital_origen,
            producto=producto,
            minuto_actual=minuto_actual,
        )

        cola_pedidos.añadir_pedido(pedido)

    # -----------------------------------------------------------------------
    # CREACIÓN DE PEDIDOS
    # -----------------------------------------------------------------------

    def _crear_pedidos_reposicion(
        self,
        hospital,
        producto: str,
        unidades_totales: int,
        minuto_actual: int,
    ):
        """
        Trocea una reposición grande en varios vuelos si supera la carga máxima.
        """
        peso_unitario = PESO_UNIDAD_KG[producto]
        max_unidades_por_vuelo = max(1, int(CARGA_MAXIMA_KG / peso_unitario))

        pedidos = []
        unidades_restantes = unidades_totales

        while unidades_restantes > 0:
            unidades_vuelo = min(unidades_restantes, max_unidades_por_vuelo)

            pedido = self._crear_pedido_reposicion(
                hospital=hospital,
                producto=producto,
                unidades=unidades_vuelo,
                minuto_actual=minuto_actual,
            )

            pedidos.append(pedido)
            unidades_restantes -= unidades_vuelo

        return pedidos

    def _crear_pedido_reposicion(
        self,
        hospital,
        producto: str,
        unidades: int,
        minuto_actual: int,
    ) -> DeliveryCall:
        """
        Crea un pedido de reposición:

        base más cercana -> hospital.
        """
        self._contador_pedidos += 1

        base_origen = self._base_mas_cercana(hospital)
        payload_kg = round(unidades * PESO_UNIDAD_KG[producto], 3)

        return DeliveryCall(
            call_id=self._contador_pedidos,
            timestamp_min=minuto_actual,
            origin_hospital=base_origen.nombre,
            destination_hospital=hospital.nombre,
            payload_kg=payload_kg,
            priority=PRIORIDAD_PRODUCTO[producto],
            producto=producto,
            unidades=unidades,
            deadline_min=math.inf,
            tipo_pedido="inventario",
        )

    def _crear_pedido_organo(
        self,
        hospital_origen,
        producto: str,
        minuto_actual: int,
    ) -> DeliveryCall:
        """
        Crea un pedido de órgano:

        hospital origen -> hospital destino.
        """
        posibles_destinos = [
            hospital
            for hospital in self.hospitales
            if hospital.nombre != hospital_origen.nombre
        ]

        hospital_destino = random.choice(posibles_destinos)
        parametros_organo = CONFIGURACION_ORGANOS[producto]

        self._contador_pedidos += 1

        return DeliveryCall(
            call_id=self._contador_pedidos,
            timestamp_min=minuto_actual,
            origin_hospital=hospital_origen.nombre,
            destination_hospital=hospital_destino.nombre,
            payload_kg=parametros_organo["peso_kg"],
            priority=0,
            producto=producto,
            unidades=1,
            deadline_min=minuto_actual + parametros_organo["isquemia_min"],
            tipo_pedido="organo",
        )

    # -----------------------------------------------------------------------
    # UTILIDADES
    # -----------------------------------------------------------------------

    def _base_mas_cercana(self, hospital):
        """
        Devuelve la base más cercana a un hospital.
        """
        return min(
            self.bases,
            key=lambda base: self._distancia_haversine_km(hospital, base),
        )

    @staticmethod
    def _distancia_haversine_km(nodo_a, nodo_b):
        """
        Distancia geográfica aproximada entre dos nodos.
        """
        dlat = math.radians(nodo_b.lat - nodo_a.lat)
        dlon = math.radians(nodo_b.lon - nodo_a.lon)

        lat1 = math.radians(nodo_a.lat)
        lat2 = math.radians(nodo_b.lat)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1)
            * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )

        return 6371 * 2 * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )

    def total_eventos_dia(self) -> int:
        """
        Devuelve el número total de eventos pregenerados.

        Ojo: incluye consumos y órganos, no solo pedidos finales.
        """
        return sum(len(eventos) for eventos in self._agenda.values())