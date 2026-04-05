from config import (
    BATTERY_RESERVE_PERCENT,
    CRUISE_SPEED_M_S,
)
from models.models import MissionRequest, MissionResult
from services.battery_service import BatteryService
from services.network_service import NetworkService
from services.weather_service import WeatherService


class SimulationController:
    def __init__(self):
        self.network = NetworkService()
        self.weather = WeatherService()

    @staticmethod
    def km_to_minutes(distance_km: float, speed_m_s: float) -> float:
        speed_km_h = speed_m_s * 3.6
        return (distance_km / speed_km_h) * 60.0

    def simulate_mission(self, request: MissionRequest) -> MissionResult:
        reasons = []

        if request.origin_hospital == request.destination_hospital:
            reasons.append("El origen y el destino no pueden ser el mismo hospital.")
            return MissionResult(feasible=False, reasons=reasons)

        route = self.network.build_route_plan(
            request.origin_hospital,
            request.destination_hospital,
        )

        try:
            battery_after = BatteryService.battery_after(
                payload_kg=request.payload_kg,
                distance_km=route.distance_total_km,
                battery_start_percent=request.battery_start_percent,
            )
        except ValueError as e:
            return MissionResult(feasible=False, reasons=[str(e)])

        enough_battery = BatteryService.has_enough_battery(
            payload_kg=request.payload_kg,
            distance_km=route.distance_total_km,
            battery_start_percent=request.battery_start_percent,
            reserve_percent=BATTERY_RESERVE_PERCENT,
        )

        if not enough_battery:
            reasons.append(
                f"Batería insuficiente: quedaría {battery_after:.2f}% y la reserva mínima es {BATTERY_RESERVE_PERCENT:.2f}%."
            )

        estimated_minutes = self.km_to_minutes(route.distance_total_km, CRUISE_SPEED_M_S)

        weather_ok = None
        if request.ignore_weather:
            weather_ok = True
        elif request.weather_date:
            weather_data = self.weather.get_weather_for_date(
                request.weather_date,
                allow_fetch_if_missing=True,
            )

            if weather_data is None:
                weather_ok = False
                reasons.append(f"No hay datos meteorológicos para la fecha {request.weather_date}.")
            else:
                weather_ok, weather_reasons = self.weather.is_operational_day(weather_data)
                reasons.extend(weather_reasons)
        else:
            weather_ok = True

        feasible = enough_battery and (weather_ok is True)

        return MissionResult(
            feasible=feasible,
            reasons=reasons,
            selected_base=route.start_base,
            distance_total_km=route.distance_total_km,
            estimated_flight_minutes=estimated_minutes,
            battery_after_percent=battery_after,
            weather_ok=weather_ok,
            route_plan=route,
        )