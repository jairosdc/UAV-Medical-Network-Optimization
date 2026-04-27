from datetime import datetime

from models.clases_models import MissionRequest, MissionResult
from parametros_globales import BATERIA_MINIMA_VUELO, CARGA_MAXIMA_KG
from services.funcionamiento_bateria_service import calcular_bateria_restante
from services.grafo_distancias_service import ServicioRed
from services.optimizador_asignacion_service import ServicioDespacho
from simulators.simulador_clima import SimuladorClima


class SimulationController:
    """
    Simula una unica mision hospital-hospital usando los servicios del dominio.

    La ruta evaluada es:
      base mas cercana al origen -> hospital origen -> hospital destino -> base.
    """

    def __init__(self, servicio_red=None):
        self.red = servicio_red or ServicioRed()

    def simulate_mission(self, request: MissionRequest) -> MissionResult:
        reasons = []
        selected_base = None
        distance_base_origin = 0.0
        distance_origin_destination = 0.0
        distance_destination_base = 0.0
        distance_total = 0.0
        estimated_delivery_time = 0
        estimated_total_time = 0
        battery_end = request.battery_start_percent
        weather_ok = True
        weather_description = "Ignorado"
        factor_velocidad = 1.0

        if request.origin_hospital == request.destination_hospital:
            reasons.append("El origen y el destino no pueden ser el mismo hospital.")

        try:
            origin = self.red.obtener_hospital(request.origin_hospital)
        except ValueError as exc:
            origin = None
            reasons.append(str(exc))

        try:
            destination = self.red.obtener_hospital(request.destination_hospital)
        except ValueError as exc:
            destination = None
            reasons.append(str(exc))

        if request.payload_kg < 0:
            reasons.append("La carga no puede ser negativa.")
        elif request.payload_kg > CARGA_MAXIMA_KG:
            reasons.append(
                f"La carga excede el maximo permitido ({CARGA_MAXIMA_KG} kg)."
            )

        if request.battery_start_percent < 0 or request.battery_start_percent > 100:
            reasons.append("La bateria inicial debe estar entre 0 y 100%.")

        if not reasons and origin is not None and destination is not None:
            selected_base, distance_base_origin = self.red.base_mas_cercana_a(
                request.origin_hospital
            )
            base = self.red.obtener_base(selected_base)
            distance_origin_destination = self.red.distancia_entre_nodos_km(
                origin, destination
            )
            distance_destination_base = self.red.distancia_entre_nodos_km(
                destination, base
            )

            delivery_distance = distance_base_origin + distance_origin_destination
            distance_total = delivery_distance + distance_destination_base

            if not request.ignore_weather:
                clima = self._build_weather_simulator(request.date)
                estado = clima.actualizar(0)
                factor_velocidad = estado.factor_velocidad
                weather_description = estado.descripcion
            else:
                weather_description = "Ignorado"

            estimated_delivery_time = ServicioDespacho.estimar_duracion_minutos(
                delivery_distance, factor_velocidad
            )
            estimated_return_time = ServicioDespacho.estimar_duracion_minutos(
                distance_destination_base, factor_velocidad
            )
            estimated_total_time = estimated_delivery_time + estimated_return_time

            try:
                battery_after_delivery = calcular_bateria_restante(
                    carga_kg=request.payload_kg,
                    distancia_km=delivery_distance,
                    bateria_inicial_pct=request.battery_start_percent,
                )
                battery_end = calcular_bateria_restante(
                    carga_kg=0.0,
                    distancia_km=distance_destination_base,
                    bateria_inicial_pct=battery_after_delivery,
                )
            except ValueError as exc:
                reasons.append(str(exc))

            if not reasons and battery_end < BATERIA_MINIMA_VUELO:
                reasons.append(
                    "Batería insuficiente: la mision termina por debajo de la reserva "
                    f"minima de {BATERIA_MINIMA_VUELO:.1f}%."
                )

        return MissionResult(
            feasible=(len(reasons) == 0 and weather_ok),
            selected_base=selected_base,
            distance_base_to_origin_km=distance_base_origin,
            distance_origin_to_destination_km=distance_origin_destination,
            distance_destination_to_base_km=distance_destination_base,
            distance_total_km=distance_total,
            estimated_time_min=estimated_total_time,
            estimated_delivery_time_min=estimated_delivery_time,
            battery_start_percent=request.battery_start_percent,
            battery_end_percent=battery_end,
            weather_ok=weather_ok,
            weather_description=weather_description,
            reasons=reasons,
        )

    @staticmethod
    def _build_weather_simulator(date_text):
        seed = None
        if date_text:
            try:
                parsed = datetime.strptime(date_text, "%Y-%m-%d")
                seed = int(parsed.strftime("%Y%m%d"))
            except ValueError:
                seed = sum(ord(ch) for ch in date_text)

        return SimuladorClima(intervalo_cambio_min=60, semilla=seed)
