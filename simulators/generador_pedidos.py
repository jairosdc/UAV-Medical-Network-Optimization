import random
import numpy as np
from collections import defaultdict
import math

from parametros_globales import CARGA_MAXIMA_KG
from models.clases_models import DeliveryCall


# Productos de Inventario (Sujetos a reposición desde almacén)
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

# Peso por unidad de cada producto (kg)
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

# Diccionario Unificado de Prioridades (0=órganos, 1=crítica, 2=urgente, 3=rutinaria)
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
# Eventos Críticos Independientes (Vuelos directos Hospital-Hospital)
# ---------------------------------------------------------------------------
# Parámetros técnicos de carga encapsulados por clave
CONFIGURACION_ORGANOS = {
    "corazon":  {"isquemia_min": 240,  "peso_kg": 2.1, "tasa_lambda": 0.005},
    "pulmon":   {"isquemia_min": 360,  "peso_kg": 2.5, "tasa_lambda": 0.008},
    "pancreas": {"isquemia_min": 720,  "peso_kg": 1.9, "tasa_lambda": 0.020},
    "rinon":    {"isquemia_min": 1440, "peso_kg": 3.2, "tasa_lambda": 0.020}
}

# ---------------------------------------------------------------------------
# Factores horarios del NHPP (hora_inicio, hora_fin, factor_lambda)
# ---------------------------------------------------------------------------
FACTORES_HORARIOS = [
    ( 0,  6, 0.48),
    ( 6,  9, 1.00),
    ( 9, 14, 1.60),
    (14, 16, 1.13),
    (16, 20, 1.30),
    (20, 24, 0.60),
]


class GeneradorPedidos:
    """
    Genera y despacha eventos de la simulación modelados mediante:
      1. NHPP para bienes fungibles (dependiente del estrés horario).
      2. HPP para órganos (eventos discretos independientes de prioridad 0).
    """

    def __init__(self, hospitales, bases, semilla=None, duracion_min=1440, escala_demanda=1.0):
        self.hospitales = hospitales
        self.bases = bases
        self._contador_pedidos = 0
        self._agenda = defaultdict(list)
        self._duracion_min = duracion_min
        self.escala_demanda = max(0.0, float(escala_demanda))

        if semilla is not None:
            np.random.seed(semilla)
            random.seed(semilla)

        self._pregenerar_periodo()

    # -----------------------------------------------------------------------
    # Generación Estocástica de Eventos
    # -----------------------------------------------------------------------

    def _pregenerar_periodo(self):
        """Puebla la agenda ciclando patrones diarios durante el horizonte T."""
        minutos_por_dia = 1440
        dias_completos = self._duracion_min // minutos_por_dia
        minutos_extra  = self._duracion_min % minutos_por_dia

        for dia in range(dias_completos):
            offset = dia * minutos_por_dia
            for h_inicio, h_fin, factor in FACTORES_HORARIOS:
                t_inicio = offset + h_inicio * 60
                t_fin    = offset + h_fin    * 60
                dur_h    = h_fin - h_inicio
                self._generar_tramo(t_inicio, t_fin, dur_h, factor)

        if minutos_extra > 0:
            offset = dias_completos * minutos_por_dia
            for h_inicio, h_fin, factor in FACTORES_HORARIOS:
                t_inicio = offset + h_inicio * 60
                t_fin    = min(offset + h_fin * 60, self._duracion_min)
                if t_inicio >= self._duracion_min:
                    break
                dur_h = (t_fin - t_inicio) / 60.0
                self._generar_tramo(t_inicio, t_fin, dur_h, factor)

    def _generar_tramo(self, t_inicio_min: int, t_fin_min: int, duracion_h: float, factor: float):
        """Inyecta eventos diferenciados (inventario vs órganos) en el espacio temporal."""
        
        # 1. Rutina de Inventario (NHPP condicionado por 'factor')
        for producto, tasa_base in TASAS_PRODUCTOS.items():
            n_eventos = np.random.poisson(tasa_base * self.escala_demanda * factor * duracion_h)
            if n_eventos > 0:
                minutos = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos)
                for m in minutos:
                    self._agenda[int(m)].append({
                        "tipo": "inventario",
                        "hospital": random.choice(self.hospitales),
                        "producto": producto,
                    })

        # 2. Rutina de Órganos (HPP con lambda estático, independiente del factor horario)
        for organo, config in CONFIGURACION_ORGANOS.items():
            tasa_lambda = config["tasa_lambda"] * self.escala_demanda
            n_eventos_org = np.random.poisson(tasa_lambda * duracion_h)
            if n_eventos_org > 0:
                minutos_org = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos_org)
                for m in minutos_org:
                    self._agenda[int(m)].append({
                        "tipo": "organo",
                        "hospital": random.choice(self.hospitales),
                        "producto": organo,
                    })

    # -----------------------------------------------------------------------
    # Ejecución Discreta (Minuto a Minuto)
    # -----------------------------------------------------------------------

    def procesar_minuto(self, minuto_actual, inventarios, cola_pedidos, verbose=False):
        """Bifurca el tratamiento del evento según su naturaleza topológica."""
        
        for evento in self._agenda.get(minuto_actual, []):
            hospital_origen = evento["hospital"]
            producto = evento["producto"]
            tipo_evento = evento["tipo"]

            # ---- LÓGICA 1: Reposición desde Almacén (Umbral s,Q) ----
            if tipo_evento == "inventario":
                if verbose:
                    print(f"  [t={minuto_actual:04d}] CONSUMO: {hospital_origen.nombre} gasta 1ud {producto}")

                inventario_hospital = inventarios[hospital_origen.nombre]
                unidades_a_reponer = inventario_hospital.registrar_consumo(producto, 1)

                if unidades_a_reponer > 0:
                    if verbose:
                        print(f"  [!] UMBRAL {producto}: {hospital_origen.nombre} solicita {unidades_a_reponer}uds")
                    
                    peso_unitario = PESO_UNIDAD_KG[producto]
                    max_unidades_por_vuelo = max(1, int(CARGA_MAXIMA_KG / peso_unitario))
                    
                    unidades_restantes = unidades_a_reponer
                    while unidades_restantes > 0:
                        unidades_vuelo = min(unidades_restantes, max_unidades_por_vuelo)
                        pedido = self._crear_pedido_reposicion(
                            hospital=hospital_origen,
                            producto=producto,
                            unidades=unidades_vuelo,
                            minuto_actual=minuto_actual,
                        )
                        cola_pedidos.añadir_pedido(pedido)
                        unidades_restantes -= unidades_vuelo

            # ---- LÓGICA 2: Vuelo Directo Hospital-Hospital (Prioridad Absoluta) ----
            elif tipo_evento == "organo":
                if verbose:
                    print(f"  [!] CÓDIGO ROJO [t={minuto_actual:04d}]: Órgano disponible ({producto}) en {hospital_origen.nombre}")
                
                # Muestreo uniforme: P(h_j) = 1 / |H_dest| excluyendo el nodo donante
                posibles_destinos = [h for h in self.hospitales if h.nombre != hospital_origen.nombre]
                hospital_destino = random.choice(posibles_destinos)
                
                parametros_org = CONFIGURACION_ORGANOS[producto]
                
                self._contador_pedidos += 1
                pedido_organo = DeliveryCall(
                    call_id=self._contador_pedidos,
                    timestamp_min=minuto_actual,
                    origin_hospital=hospital_origen.nombre,
                    destination_hospital=hospital_destino.nombre,
                    payload_kg=parametros_org["peso_kg"],
                    priority=PRIORIDAD_PRODUCTO[producto],
                    producto=producto,
                    unidades=1,
                    deadline_min=minuto_actual + parametros_org["isquemia_min"]
                )
                cola_pedidos.añadir_pedido(pedido_organo)

    # -----------------------------------------------------------------------
    # Utilidades y Enrutamiento Base
    # -----------------------------------------------------------------------

    def _crear_pedido_reposicion(self, hospital, producto, unidades, minuto_actual) -> DeliveryCall:
        """Instancia DeliveryCall para logística regular (Base -> Hospital)."""
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
            deadline_min=math.inf # Los productos rutinarios no sufren caducidad en vuelo
        )

    def _base_mas_cercana(self, hospital):
        """Resolución geométrica por distancia Haversine mínima."""
        def dist(a, b):
            dlat = math.radians(b.lat - a.lat)
            dlon = math.radians(b.lon - a.lon)
            x = math.sin(dlat/2)**2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlon/2)**2
            return 6371 * 2 * math.atan2(math.sqrt(x), math.sqrt(1-x))
        return min(self.bases, key=lambda b: dist(hospital, b))

    def total_eventos_dia(self) -> int:
        return sum(len(v) for v in self._agenda.values())
