from typing import Optional
from parametros_globales import (
    BATERIA_MINIMA_VUELO,
    VELOCIDAD_DRON_M_S,
)
from models.clases_models import MissionRequest, MissionResult
from services.funcionamiento_bateria_service import (
    calcular_bateria_restante,
    tiene_bateria_suficiente,
)
from services.grafo_distancias_service import NetworkService
from services.meteorologia_service import WeatherService
from models.inventario import Inventario


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
            battery_after = calcular_bateria_restante(
                carga_kg=request.payload_kg,
                distancia_km=route.distance_total_km,
                bateria_inicial_pct=request.battery_start_percent,
            )
        except ValueError as e:
            return MissionResult(feasible=False, reasons=[str(e)])

        enough_battery = tiene_bateria_suficiente(
            carga_kg=request.payload_kg,
            distancia_km=route.distance_total_km,
            bateria_inicial_pct=request.battery_start_percent,
            reserva_minima_pct=BATERIA_MINIMA_VUELO,
        )

        if not enough_battery:
            reasons.append(
                f"Batería insuficiente: quedaría {battery_after:.2f}% y la reserva mínima es {BATERIA_MINIMA_VUELO:.2f}%."
            )

        estimated_minutes = self.km_to_minutes(route.distance_total_km, VELOCIDAD_DRON_M_S)

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

    def verificar_politica_inventario(self, inventario: Inventario, nombre_producto: str) -> Optional[int]:
        """
        Valida la política (s, Q): si el stock total (físico + en camino) cae por debajo
        o igual al umbral 's' (umbral SQ), se debe disparar una reposición de 'Q' elementos.
        Retorna la cantidad Q a reponer si se cumple la condición, o None si no es necesario.
        """
        if nombre_producto not in inventario.productos:
            return None
            
        producto = inventario.productos[nombre_producto]
        
        # Lógica (s, Q): umbral SQ
        if producto.stock_total_estimado <= producto.umbral_s:
            return producto.cantidad_a_pedir_Q
            
        return None