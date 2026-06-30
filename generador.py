"""
generador.py
============

Genera los eventos de la simulación minuto a minuto:

  1. Consumos intrahospitalarios (inventario)
     - Cada hospital consume productos según TASAS_PRODUCTOS (eventos/hora).
     - Si el stock baja del umbral s, se crea un pedido de reposición.

  2. Aparición de órganos
     - Proceso de Poisson raro. El órgano aparece en un hospital origen
       y se transporta a un hospital destino aleatorio.
     - No pasan por inventario.

Los eventos de toda la simulación se pregenera al inicio para ser
eficientes: se usa una agenda interna {minuto: [eventos]}.
"""

import random
import math
import numpy as np

from config import CARGA_MAXIMA_KG
from modelos import DeliveryCall
from red import ServicioRed


# ---------------------------------------------------------------------------
# TASAS DE CONSUMO INTRAHOSPITALARIO (eventos/hora por hospital)
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
# PESO POR UNIDAD (kg)
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

# Factores multiplicadores de las tasas lambda por franja horaria
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
       - Generan pedidos hospital → hospital.
    """

    def __init__(self, hospitales, bases, semilla=None, duracion_min=1440, factor_demanda_inventario=1.0, factor_demanda_organos=1.0):
        self.hospitales = hospitales
        self.bases = bases

        self.factor_demanda_inventario = float(factor_demanda_inventario)
        self.factor_demanda_organos = float(factor_demanda_organos)

        if self.factor_demanda_inventario < 0:
            raise ValueError("factor_demanda_inventario no puede ser negativo")

        if self.factor_demanda_organos < 0:
            raise ValueError("factor_demanda_organos no puede ser negativo")

        self._contador_pedidos = 0
        self._agenda = {}
        self._duracion_min = duracion_min

        if semilla is not None:
            np.random.seed(semilla)
            random.seed(semilla)

        self._pregenerar_periodo()

    # -----------------------------------------------------------------------
    # PREGENERACIÓN DE EVENTOS
    # -----------------------------------------------------------------------

    def _pregenerar_periodo(self):
        """Rellena la agenda de eventos para todo el horizonte de simulación."""
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
        """Genera los eventos de un día completo o parcial."""
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

    def _generar_tramo(self, t_inicio_min, t_fin_min, duracion_h, factor):
        """Genera todos los eventos de una franja horaria."""
        self._generar_consumos_inventario(t_inicio_min, t_fin_min, duracion_h, factor)
        self._generar_eventos_organos(t_inicio_min, t_fin_min, duracion_h)

    def _generar_consumos_inventario(self, t_inicio_min, t_fin_min, duracion_h, factor):
        """Genera consumos de inventario para cada hospital y producto."""
        for hospital in self.hospitales:
            for producto, tasa_base in TASAS_PRODUCTOS.items():

                tasa_efectiva = (
                    tasa_base
                    * factor
                    * self.factor_demanda_inventario
                )

                n_eventos = np.random.poisson(tasa_efectiva * duracion_h)

                if n_eventos == 0:
                    continue

                minutos = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos)

                for minuto in minutos:
                    self._agendar_evento(int(minuto), "inventario", hospital, producto)

    def _generar_eventos_organos(self, t_inicio_min, t_fin_min, duracion_h):
        """Genera órganos como eventos raros globales de la red."""
        for organo, config in CONFIGURACION_ORGANOS.items():

            tasa_lambda = config["tasa_lambda"] * self.factor_demanda_organos
            n_eventos = np.random.poisson(tasa_lambda * duracion_h)

            if n_eventos == 0:
                continue

            minutos = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos)

            for minuto in minutos:
                self._agendar_evento(int(minuto), "organo", random.choice(self.hospitales), organo)

    def _agendar_evento(self, minuto: int, tipo: str, hospital, producto: str):
        """Guarda un evento en la agenda interna."""
        self._agenda.setdefault(minuto, []).append({
            "tipo": tipo,
            "hospital": hospital,
            "producto": producto,
        })

    # -----------------------------------------------------------------------
    # EJECUCIÓN MINUTO A MINUTO
    # -----------------------------------------------------------------------

    def procesar_minuto(self, minuto_actual, inventarios, cola_pedidos, verbose=False):
        """Procesa los eventos programados para un minuto concreto."""
        eventos = self._agenda.get(minuto_actual, [])

        for evento in eventos:
            tipo_evento = evento["tipo"]

            if tipo_evento == "inventario":
                self._procesar_consumo_inventario(evento, minuto_actual, inventarios, cola_pedidos, verbose)

            elif tipo_evento == "organo":
                self._procesar_evento_organo(evento, minuto_actual, cola_pedidos, verbose)

    def _procesar_consumo_inventario(self, evento, minuto_actual, inventarios, cola_pedidos, verbose=False):
        """Aplica un consumo intrahospitalario. Si cae bajo el umbral, crea pedidos de reposición."""
        hospital = evento["hospital"]
        producto = evento["producto"]

        if verbose:
            print(f"  [t={minuto_actual:04d}] CONSUMO: {hospital.nombre} gasta 1ud {producto}")

        inventario_hospital = inventarios[hospital.nombre]
        unidades_a_reponer = inventario_hospital.registrar_consumo(producto, 1)

        if unidades_a_reponer <= 0:
            return

        if verbose:
            print(f"  [!] UMBRAL {producto}: {hospital.nombre} solicita {unidades_a_reponer} uds")

        for pedido in self._crear_pedidos_reposicion(hospital, producto, unidades_a_reponer, minuto_actual):
            cola_pedidos.añadir_pedido(pedido)

    def _procesar_evento_organo(self, evento, minuto_actual, cola_pedidos, verbose=False):
        """Crea un pedido hospital → hospital para transportar un órgano."""
        hospital_origen = evento["hospital"]
        producto = evento["producto"]

        if verbose:
            print(f"  [!] CÓDIGO ROJO [t={minuto_actual:04d}]: Órgano disponible ({producto}) en {hospital_origen.nombre}")

        cola_pedidos.añadir_pedido(self._crear_pedido_organo(hospital_origen, producto, minuto_actual))

    # -----------------------------------------------------------------------
    # CREACIÓN DE PEDIDOS
    # -----------------------------------------------------------------------

    def _crear_pedidos_reposicion(self, hospital, producto, unidades_totales, minuto_actual):
        """Trocea una reposición grande en varios vuelos si supera la carga máxima."""
        peso_unitario = PESO_UNIDAD_KG[producto]
        max_unidades_por_vuelo = max(1, int(CARGA_MAXIMA_KG / peso_unitario))

        pedidos = []
        unidades_restantes = unidades_totales

        while unidades_restantes > 0:
            unidades_vuelo = min(unidades_restantes, max_unidades_por_vuelo)
            pedidos.append(self._crear_pedido_reposicion(hospital, producto, unidades_vuelo, minuto_actual))
            unidades_restantes -= unidades_vuelo

        return pedidos

    def _crear_pedido_reposicion(self, hospital, producto, unidades, minuto_actual) -> DeliveryCall:
        """Crea un pedido de reposición: base más cercana → hospital."""
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

    def _crear_pedido_organo(self, hospital_origen, producto, minuto_actual) -> DeliveryCall:
        """Crea un pedido de órgano: hospital origen → hospital destino."""
        posibles_destinos = [h for h in self.hospitales if h.nombre != hospital_origen.nombre]
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

    # Utilidades
    def _base_mas_cercana(self, hospital):
        """Devuelve el nodo base más cercano al hospital dado."""
        return min(
            self.bases,
            key=lambda base: ServicioRed.distancia_haversine_km(
                hospital.lat, hospital.lon,
                base.lat, base.lon,
            )
        )

    def total_eventos_dia(self) -> int:
        return sum(len(eventos) for eventos in self._agenda.values())
