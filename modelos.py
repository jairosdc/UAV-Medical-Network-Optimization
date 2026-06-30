"""
modelos.py
==========

Todas las estructuras de datos del sistema:

  - Node              : nodo de la red (hospital o base)
  - RoutePlan         : ruta planificada para una misión
  - Drone             : estado de un dron en cada instante
  - DeliveryCall      : pedido de entrega (inventario u órgano)
  - DispatchDecision  : decisión de asignación de un dron a un pedido
  - SimulationStats   : contadores acumulados al final de la simulación

  - Producto          : un producto de inventario con su stock
  - Inventario        : inventario de un hospital o almacén central
  - GestorPrioridad   : cola de pedidos ordenada por prioridad
"""

from dataclasses import dataclass, field
import math


# ===========================================================================
# NODOS Y RUTAS
# ===========================================================================

@dataclass
class Node:
    nombre: str
    lat: float
    lon: float
    tipo: str


@dataclass
class RoutePlan:
    start_base: str
    origin_hospital: str
    destination_hospital: str
    distance_base_to_origin_km: float
    distance_origin_to_destination_km: float
    distance_total_km: float


# ===========================================================================
# DRONES Y PEDIDOS
# ===========================================================================

@dataclass
class Drone:
    drone_id: str
    base_name: str
    battery_percent: float = 100.0
    status: str = "available"   # available, mission, returning, charging
    busy_until_min: int = 0
    current_node: str | None = None
    current_call_id: int | None = None
    flight_minutes: int = 0
    charging_minutes: int = 0
    deliveries_made: int = 0
    role: str = "base"  # "base" o "hospital"


@dataclass
class DeliveryCall:
    call_id: int
    timestamp_min: int
    origin_hospital: str
    destination_hospital: str
    payload_kg: float
    priority: int   # 0=Organo, 1=alta, 2=media, 3=baja

    status: str = "pending"  # pending, assigned, completed, infeasible
    assigned_drone_id: str | None = None
    rejection_reason: str | None = None

    producto: str | None = None
    unidades: int = 0
    deadline_min: float = math.inf

    tipo_pedido: str = "inventario"  # "inventario" u "organo"

    # Tiempos reales de la simulación
    assigned_time_min: float | None = None
    completed_time_min: float | None = None

    # Métrica de cumplimiento
    is_late: bool = False


@dataclass
class DispatchDecision:
    drone_id: str
    call_id: int
    priority: int
    distance_to_origin_km: float
    distance_total_km: float
    battery_before_percent: float
    battery_after_percent: float
    estimated_duration_min: int
    estimated_flight_ida_min: int = 0
    estimated_flight_vuelta_min: int = 0
    score: float = 0.0


@dataclass
class SimulationStats:
    # Estadísticas generales
    total_calls: int = 0
    assigned_calls: int = 0
    completed_calls: int = 0

    # Solo pedidos físicamente imposibles (no "no había dron ahora")
    rejected_calls: int = 0
    infeasible_calls: int = 0

    # Pedidos por puntualidad
    late_calls: int = 0
    on_time_calls: int = 0

    # Por prioridad
    high_priority_calls: int = 0
    medium_priority_calls: int = 0
    low_priority_calls: int = 0

    # Inventario
    inventory_calls: int = 0
    inventory_completed: int = 0
    inventory_on_time: int = 0
    inventory_late: int = 0

    # Órganos
    organ_calls: int = 0
    organ_assigned: int = 0
    organ_completed: int = 0
    organ_rejected: int = 0
    organ_on_time: int = 0
    organ_late: int = 0


# ===========================================================================
# INVENTARIO
# ===========================================================================

# Productos inventariables con sus parámetros de política (s, Q)
CONFIG_INVENTARIO = {
    "sangre":              {"inicial": 20,   "s": 8,   "Q": 15},
    "farmaco_uci":         {"inicial": 12,   "s": 5,   "Q": 10},
    "antibiotico":         {"inicial": 60,   "s": 25,  "Q": 40},
    "suero":               {"inicial": 80,   "s": 30,  "Q": 50},
    "plasma":              {"inicial": 25,   "s": 10,  "Q": 15},
    "analgesico":          {"inicial": 100,  "s": 40,  "Q": 60},
    "material_sanitario":  {"inicial": 150,  "s": 60,  "Q": 80},
    "medicamento_general": {"inicial": 90,   "s": 35,  "Q": 55},
}

# Productos que NUNCA deben entrar al inventario (se gestionan como pedidos especiales)
ORGANOS_NO_INVENTARIABLES = {"corazon", "pulmon", "rinon", "pancreas", "higado"}

# Los almacenes centrales escalan su stock por este factor respecto a los hospitales
FACTOR_ESCALA_ALMACEN = 50


@dataclass
class Producto:
    stock_fisico: int
    umbral_s: int
    cantidad_a_pedir_Q: int
    stock_en_camino: int = 0

    @property
    def stock_total_estimado(self):
        return self.stock_fisico + self.stock_en_camino


class Inventario:
    """
    Inventario de un hospital o de un almacén central.

    En hospitales:
    - se consume stock,
    - se activa reposición al caer bajo el umbral s (política s, Q).

    En almacenes centrales:
    - no se activa reposición,
    - solo se descuenta stock cuando sale un dron.

    Los órganos NO pertenecen al inventario.
    Se gestionan como pedidos especiales hospital → hospital.
    """

    def __init__(self, es_almacen_central: bool = False):
        self.es_almacen = es_almacen_central
        self.productos = {}
        self.stockout_activo = {}
        self._inicializar_stocks()

    def _inicializar_stocks(self):
        multiplicador = FACTOR_ESCALA_ALMACEN if self.es_almacen else 1
        for nombre, datos in CONFIG_INVENTARIO.items():
            self.productos[nombre] = Producto(
                stock_fisico=datos["inicial"] * multiplicador,
                umbral_s=0 if self.es_almacen else datos["s"],
                cantidad_a_pedir_Q=datos["Q"],
            )
            self.stockout_activo[nombre] = False

    def _validar_no_es_organo(self, nombre_producto: str):
        if nombre_producto in ORGANOS_NO_INVENTARIABLES:
            raise ValueError(
                f"ERROR DE MODELO: '{nombre_producto}' es un órgano y no debe "
                f"gestionarse como inventario."
            )

    def registrar_consumo(self, nombre_producto: str, cantidad_consumida: int):
        """
        Registra consumo interno. Devuelve Q si hay que reponer, 0 si no.
        """
        self._validar_no_es_organo(nombre_producto)
        if self.es_almacen or nombre_producto not in self.productos:
            return 0

        producto = self.productos[nombre_producto]
        producto.stock_fisico = max(0, producto.stock_fisico - cantidad_consumida)

        if producto.stock_fisico == 0:
            self.stockout_activo[nombre_producto] = True

        if producto.stock_total_estimado <= producto.umbral_s:
            producto.stock_en_camino += producto.cantidad_a_pedir_Q
            return producto.cantidad_a_pedir_Q

        return 0

    def enviar_dron(self, nombre_producto: str, cantidad: int):
        """Descuenta stock cuando un dron sale con producto."""
        self._validar_no_es_organo(nombre_producto)
        if nombre_producto not in self.productos:
            return False

        producto = self.productos[nombre_producto]
        producto.stock_fisico = max(0, producto.stock_fisico - cantidad)

        if producto.stock_fisico == 0:
            self.stockout_activo[nombre_producto] = True
        return True

    def recibir_dron(self, nombre_producto: str, cantidad: int):
        """Aumenta stock cuando llega un dron con reposición."""
        self._validar_no_es_organo(nombre_producto)
        if nombre_producto not in self.productos:
            return False

        producto = self.productos[nombre_producto]
        producto.stock_fisico += cantidad
        producto.stock_en_camino = max(0, producto.stock_en_camino - cantidad)
        self.limpiar_stockout(nombre_producto)
        return True

    def hay_stockout_activo(self, nombre_producto: str) -> bool:
        self._validar_no_es_organo(nombre_producto)
        return self.stockout_activo.get(nombre_producto, False)

    def limpiar_stockout(self, nombre_producto: str):
        self._validar_no_es_organo(nombre_producto)
        if nombre_producto in self.stockout_activo:
            self.stockout_activo[nombre_producto] = False

    def obtener_stock_fisico(self, nombre_producto: str) -> int:
        self._validar_no_es_organo(nombre_producto)
        return self.productos[nombre_producto].stock_fisico if nombre_producto in self.productos else 0

    def obtener_stock_en_camino(self, nombre_producto: str) -> int:
        self._validar_no_es_organo(nombre_producto)
        return self.productos[nombre_producto].stock_en_camino if nombre_producto in self.productos else 0

    def obtener_stock_total_estimado(self, nombre_producto: str) -> int:
        self._validar_no_es_organo(nombre_producto)
        return self.productos[nombre_producto].stock_total_estimado if nombre_producto in self.productos else 0


# ===========================================================================
# COLA DE PRIORIDAD
# ===========================================================================

class GestorPrioridad:
    """
    Cola de pedidos ordenada por (prioridad, deadline, timestamp, call_id).

    Prioridad 0 = órgano (máxima urgencia).
    Prioridad 3 = rutinario.
    """

    def __init__(self):
        self.pedidos_pendientes = []

    def añadir_pedido(self, pedido):
        self.pedidos_pendientes.append(pedido)

    def obtener_siguiente_pedido(self):
        if not self.pedidos_pendientes:
            return None
        self.pedidos_pendientes.sort(
            key=lambda p: (p.priority, p.deadline_min, p.timestamp_min, p.call_id)
        )
        return self.pedidos_pendientes.pop(0)

    def extraer_ronda_ordenada(self):
        """Extrae todos los pedidos pendientes ordenados, vaciando la cola."""
        if not self.pedidos_pendientes:
            return []
        pedidos = self.pedidos_pendientes
        self.pedidos_pendientes = []
        pedidos.sort(
            key=lambda p: (p.priority, p.deadline_min, p.timestamp_min, p.call_id)
        )
        return pedidos

    def size(self):
        return len(self.pedidos_pendientes)
