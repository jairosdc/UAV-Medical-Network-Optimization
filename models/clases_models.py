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
    current_node = None
    current_call_id = None
    flight_minutes: int = 0
    charging_minutes: int = 0
    deliveries_made: int = 0


@dataclass
class DeliveryCall:
    call_id: int
    timestamp_min: int
    origin_hospital: str
    destination_hospital: str
    payload_kg: float
    priority: int   # 0=Organo, 1=alta, 2=media, 3=baja
    status: str = "pending"  # pending, assigned, completed, rejected
    assigned_drone_id = None
    rejection_reason = None
    producto = None
    unidades: int = 0
    deadline_min: float = math.inf


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
class MissionRequest:
    origin_hospital: str
    destination_hospital: str
    payload_kg: float
    battery_start_percent: float = 100.0
    ignore_weather: bool = True
    date: Optional[str] = None


@dataclass
class MissionResult:
    feasible: bool
    selected_base: Optional[str]
    distance_base_to_origin_km: float
    distance_origin_to_destination_km: float
    distance_destination_to_base_km: float
    distance_total_km: float
    estimated_time_min: int
    estimated_delivery_time_min: int
    battery_start_percent: float
    battery_end_percent: float
    weather_ok: bool
    weather_description: str = "Sin meteorologia"
    reasons: List[str] = field(default_factory=list)


@dataclass
class SimulationStats:
    total_calls: int = 0
    assigned_calls: int = 0
    rejected_calls: int = 0
    completed_calls: int = 0
    high_priority_calls: int = 0
    medium_priority_calls: int = 0
    low_priority_calls: int = 0
