from typing import List, Optional

from parametros_globales import BATERIA_MINIMA_VUELO, VELOCIDAD_DRON_M_S
from models.clases_models import DispatchDecision, Drone, DeliveryCall
from services.funcionamiento_bateria_service import calcular_bateria_restante


class ServicioDespacho:
    """Selecciona el dron más adecuado para atender un pedido."""

    def __init__(self, servicio_red):
        self.red = servicio_red

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float) -> int:
        """Estima el tiempo de vuelo en minutos para una distancia dada."""
        velocidad_km_h = VELOCIDAD_DRON_M_S * 3.6
        minutos = (distancia_km / velocidad_km_h) * 60.0
        return max(1, int(round(minutos)))

    def elegir_mejor_dron(self, drones: List[Drone], pedido: DeliveryCall) -> Optional[DispatchDecision]:
        
        hospital_origen  = self.red.obtener_nodo(pedido.origin_hospital)
        hospital_destino = self.red.obtener_nodo(pedido.destination_hospital)

        candidatos = []

        for dron in drones:
            if dron.status != "available":
                continue

            # El dron disponible siempre está en su base
            nodo_actual = self.red.obtener_base(dron.base_name)

            distancia_base_a_origen  = self.red.distancia_entre_nodos_km(nodo_actual, hospital_origen)
            distancia_origen_destino = self.red.distancia_entre_nodos_km(hospital_origen, hospital_destino)
            distancia_total          = distancia_base_a_origen + distancia_origen_destino

            try:
                bateria_final = calcular_bateria_restante(
                    carga_kg            = pedido.payload_kg,
                    distancia_km        = distancia_total,
                    bateria_inicial_pct = dron.battery_percent,
                )
            except ValueError:
                continue  # Carga inválida → descartar este dron

            if bateria_final < BATERIA_MINIMA_VUELO:
                continue

            candidatos.append(DispatchDecision(
                drone_id               = dron.drone_id,
                call_id                = pedido.call_id,
                priority               = pedido.priority,
                distance_to_origin_km  = distancia_base_a_origen,
                distance_total_km      = distancia_total,
                battery_before_percent = dron.battery_percent,
                battery_after_percent  = bateria_final,
                estimated_duration_min = self.estimar_duracion_minutos(distancia_total),
                score                  = 0.0,
            ))

        if not candidatos:
            return None

        if pedido.priority == 1:
            candidatos.sort(key=lambda c: c.distance_to_origin_km)
        elif pedido.priority == 2:
            candidatos.sort(key=lambda c: c.distance_total_km)
        else:
            candidatos.sort(key=lambda c: c.battery_after_percent, reverse=True)

        return candidatos[0]