import random
import numpy as np
from collections import defaultdict

from models.clases_models import DeliveryCall


# ---------------------------------------------------------------------------
# Tasas base de consumo horario por producto (eventos por hora)
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
# Prioridad clínica de cada producto (1=crítica, 2=urgente, 3=rutinaria)
# ---------------------------------------------------------------------------
PRIORIDAD_PRODUCTO = {
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
# Peso aproximado por unidad de cada producto (kg)
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
    Pregénera todos los eventos de consumo para la duración completa de la
    simulación usando un Proceso de Poisson No Homogéneo (NHPP) con factores
    horarios que se ciclan día a día.

    En cada minuto, procesa los eventos de ese instante: si el inventario
    del hospital cae por debajo del umbral s, genera automáticamente un
    pedido de reposición desde la base al hospital.
    """

    def __init__(self, hospitales, bases, semilla=None, duracion_min=1440):
        self.hospitales = hospitales   # lista de Node tipo hospital
        self.bases = bases             # lista de Node tipo base
        self._contador_pedidos = 0
        self._agenda = defaultdict(list)  # minuto -> lista de eventos
        self._duracion_min = duracion_min

        if semilla is not None:
            np.random.seed(semilla)
            random.seed(semilla)

        self._pregenerar_periodo()

    # -----------------------------------------------------------------------
    # Generación de la agenda para el periodo completo de simulación
    # -----------------------------------------------------------------------

    def _pregenerar_periodo(self):
        """
        Genera todos los eventos de consumo para la duración completa de la
        simulación (multi-día). El patrón NHPP horario se cicla día a día.

        BUG CORREGIDO: la versión anterior solo generaba eventos para el
        primer día (minutos 0-1440), dejando el resto de la simulación vacío.
        """
        minutos_por_dia = 1440   # 24 h × 60 min

        dias_completos = self._duracion_min // minutos_por_dia
        minutos_extra  = self._duracion_min % minutos_por_dia

        # ---- Días completos ------------------------------------------------
        for dia in range(dias_completos):
            offset = dia * minutos_por_dia
            for h_inicio, h_fin, factor in FACTORES_HORARIOS:
                t_inicio = offset + h_inicio * 60
                t_fin    = offset + h_fin    * 60
                dur_h    = h_fin - h_inicio
                self._generar_tramo(t_inicio, t_fin, dur_h, factor)

        # ---- Último tramo parcial (si la duración no es múltiplo de 1440) --
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
        """Genera eventos NHPP dentro de un tramo horario y los inserta en la agenda."""
        for producto, tasa_base in TASAS_PRODUCTOS.items():
            n_eventos = np.random.poisson(tasa_base * factor * duracion_h)
            if n_eventos == 0:
                continue
            minutos = np.random.uniform(t_inicio_min, t_fin_min, size=n_eventos)
            for m in minutos:
                hospital = random.choice(self.hospitales)
                self._agenda[int(m)].append({
                    "hospital": hospital,
                    "producto": producto,
                })

    # -----------------------------------------------------------------------
    # Ejecución minuto a minuto
    # -----------------------------------------------------------------------

    def procesar_minuto(self, minuto_actual, inventarios, cola_pedidos, verbose=False):
        """
        Procesa todos los eventos de consumo del minuto actual.
        Si algún inventario cae por debajo del umbral s, genera un
        pedido de reposición y lo añade a la cola.
        """
        from parametros_globales import CARGA_MAXIMA_KG
        
        for evento in self._agenda.get(minuto_actual, []):
            hospital = evento["hospital"]
            producto = evento["producto"]

            if verbose:
                print(f"  [t={minuto_actual:04d}] CONSUMO: {hospital.nombre} gasta 1 unidad de {producto}")

            inventario_hospital = inventarios[hospital.nombre]
            unidades_a_reponer  = inventario_hospital.registrar_consumo(producto, 1)

            if unidades_a_reponer > 0:
                if verbose:
                    print(f"  [!] UMBRAL ALCANZADO: {hospital.nombre} solicita {unidades_a_reponer} unidades de {producto}")
                
                peso_unitario = PESO_UNIDAD_KG[producto]
                max_unidades_por_vuelo = int(CARGA_MAXIMA_KG / peso_unitario)
                if max_unidades_por_vuelo == 0:
                    max_unidades_por_vuelo = 1
                
                unidades_restantes = unidades_a_reponer
                while unidades_restantes > 0:
                    unidades_vuelo = min(unidades_restantes, max_unidades_por_vuelo)
                    
                    pedido = self._crear_pedido_reposicion(
                        hospital         = hospital,
                        producto         = producto,
                        unidades         = unidades_vuelo,
                        minuto_actual    = minuto_actual,
                    )
                    cola_pedidos.añadir_pedido(pedido)
                    unidades_restantes -= unidades_vuelo

    # -----------------------------------------------------------------------
    # Creación de pedidos
    # -----------------------------------------------------------------------

    def _crear_pedido_reposicion(self, hospital, producto, unidades, minuto_actual) -> DeliveryCall:
        """Construye el DeliveryCall de reposición desde la base más cercana al hospital."""
        self._contador_pedidos += 1

        base_origen = self._base_mas_cercana(hospital)
        payload_kg  = round(unidades * PESO_UNIDAD_KG[producto], 3)

        return DeliveryCall(
            call_id              = self._contador_pedidos,
            timestamp_min        = minuto_actual,
            origin_hospital      = base_origen.nombre,
            destination_hospital = hospital.nombre,
            payload_kg           = payload_kg,
            priority             = PRIORIDAD_PRODUCTO[producto],
            producto             = producto,
            unidades             = unidades
        )

    def _base_mas_cercana(self, hospital):
        """Devuelve la base más cercana al hospital (sin importar ServicioRed)."""
        import math
        def dist(a, b):
            dlat = math.radians(b.lat - a.lat)
            dlon = math.radians(b.lon - a.lon)
            x = math.sin(dlat/2)**2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlon/2)**2
            return 6371 * 2 * math.atan2(math.sqrt(x), math.sqrt(1-x))
        return min(self.bases, key=lambda b: dist(hospital, b))

    # -----------------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------------

    def total_eventos_dia(self) -> int:
        return sum(len(v) for v in self._agenda.values())
