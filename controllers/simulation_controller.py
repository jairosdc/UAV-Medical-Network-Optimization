"""
Controlador de simulación de misiones UAV.

Comprueba si una misión de transporte médico puede realizarse.

Tiene en cuenta:
- origen y destino,
- distancia de la ruta,
- carga transportada,
- batería disponible,
- clima simulado,
- política de inventario.

En esta versión el clima no cancela vuelos.
El clima solo modifica la velocidad del dron.


from parametros_globales import BATERIA_MINIMA_VUELO, VELOCIDAD_DRON_M_S

from models.clases_models import MissionRequest, MissionResult
from models.inventario import Inventario

from services.funcionamiento_bateria_service import (
    calcular_bateria_restante,
    tiene_bateria_suficiente,
)

from services.grafo_distancias_service import ServicioRed
from simulators.simulador_clima import SimuladorClima


class SimulationController:
    
    Controla la simulación de una misión concreta.
    

    def __init__(self, intervalo_cambio_clima_min: int = 60, semilla_clima=None):
        self.network = ServicioRed()
        self.clima = SimuladorClima(
            intervalo_cambio_min=intervalo_cambio_clima_min,
            semilla=semilla_clima
        )

    @staticmethod
    def km_to_minutes(distance_km: float, speed_m_s: float):
        velocidad_km_h = speed_m_s * 3.6
        return (distance_km / velocidad_km_h) * 60.0

    def simulate_mission(self, request: MissionRequest, minuto_actual: int = 0):
        motivos = []

        if request.origin_hospital == request.destination_hospital:
            motivos.append("El origen y el destino no pueden ser el mismo hospital.")
            return MissionResult(
                feasible=False,
                reasons=motivos
            )

        ruta = self.network.planificar_reposicion(
            request.destination_hospital
        )

        try:
            bateria_final = calcular_bateria_restante(
                carga_kg=request.payload_kg,
                distancia_km=ruta.distance_total_km,
                bateria_inicial_pct=request.battery_start_percent
            )
        except ValueError as error:
            return MissionResult(
                feasible=False,
                reasons=[str(error)]
            )

        bateria_suficiente = tiene_bateria_suficiente(
            carga_kg=request.payload_kg,
            distancia_km=ruta.distance_total_km,
            bateria_inicial_pct=request.battery_start_percent,
            reserva_minima_pct=BATERIA_MINIMA_VUELO
        )

        if not bateria_suficiente:
            motivos.append(
                f"Batería insuficiente: quedaría {bateria_final:.2f}% "
                f"y la reserva mínima es {BATERIA_MINIMA_VUELO:.2f}%."
            )

        estado_clima = self.clima.actualizar(minuto_actual)
        factor_velocidad = estado_clima.factor_velocidad
        velocidad_real_m_s = VELOCIDAD_DRON_M_S * factor_velocidad

        tiempo_estimado_min = self.km_to_minutes(
            ruta.distance_total_km,
            velocidad_real_m_s
        )

        es_viable = bateria_suficiente

        return MissionResult(
            feasible=es_viable,
            reasons=motivos,
            selected_base=ruta.start_base,
            distance_total_km=ruta.distance_total_km,
            estimated_flight_minutes=tiempo_estimado_min,
            battery_after_percent=bateria_final,
            weather_state=estado_clima.nombre,
            weather_speed_factor=factor_velocidad,
            route_plan=ruta
        )

    def verificar_politica_inventario(self, inventario: Inventario, nombre_producto: str):
        if nombre_producto not in inventario.productos:
            return None

        producto = inventario.productos[nombre_producto]

        if producto.stock_total_estimado <= producto.umbral_s:
            return producto.cantidad_a_pedir_Q

        return None
    """