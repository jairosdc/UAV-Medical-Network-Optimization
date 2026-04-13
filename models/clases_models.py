from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Hospital:
    nombre: str
    lat: float
    lon: float
    tipo: str

@dataclass
class DroneSpec:
    max_payload_kg: float
    max_range_km_empty: float
    battery_reserve_percent: float
    cruise_speed_m_s: float


@dataclass
class WeatherDay:
    date: str
    tmax: Optional[float] = None
    tmin: Optional[float] = None
    wind_avg: Optional[float] = None
    wind_gust: Optional[float] = None
    precip: Optional[float] = None


@dataclass
class MissionRequest:
    origin_hospital: str
    destination_hospital: str
    payload_kg: float
    battery_start_percent: float = 100.0
    weather_date: Optional[str] = None
    ignore_weather: bool = False


@dataclass
class RoutePlan:
    start_base: str
    origin_hospital: str
    destination_hospital: str
    distance_base_to_origin_km: float
    distance_origin_to_destination_km: float
    distance_total_km: float


@dataclass
class MissionResult:
    feasible: bool
    reasons: List[str] = field(default_factory=list)
    selected_base: Optional[str] = None
    distance_total_km: Optional[float] = None
    estimated_flight_minutes: Optional[float] = None
    battery_after_percent: Optional[float] = None
    weather_ok: Optional[bool] = None
    route_plan: Optional[RoutePlan] = None


# --------------------------
# NUEVO: modelos de flota
# --------------------------

@dataclass
class Drone:
    drone_id: str
    base_name: str
    battery_percent: float = 100.0
    status: str = "available"   # available, mission, charging
    busy_until_min: int = 0
    current_node: Optional[str] = None
    current_call_id: Optional[int] = None


@dataclass
class DeliveryCall:
    call_id: int
    timestamp_min: int
    origin_hospital: str
    destination_hospital: str
    payload_kg: float
    priority: int   # 1=alta, 2=media, 3=baja
    status: str = "pending"  # pending, assigned, completed, rejected
    assigned_drone_id: Optional[str] = None
    rejection_reason: Optional[str] = None


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
    score: float


@dataclass
class SimulationStats:
    total_calls: int = 0
    assigned_calls: int = 0
    rejected_calls: int = 0
    completed_calls: int = 0
    high_priority_calls: int = 0
    medium_priority_calls: int = 0
    low_priority_calls: int = 0