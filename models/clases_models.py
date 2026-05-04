from dataclasses import dataclass, field
import math

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

    # Tipo de pedido
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

    # OJO: esto ya no debe significar "no había dron ahora".
    # Solo debería contar pedidos físicamente imposibles.
    rejected_calls: int = 0
    infeasible_calls: int = 0

    # Pedidos pendientes o tardíos
    late_calls: int = 0
    on_time_calls: int = 0

    # Estadísticas por prioridad
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