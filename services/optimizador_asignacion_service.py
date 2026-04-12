from typing import List, Optional
from parametros_globales import BATTERY_RESERVE_PERCENT, CRUISE_SPEED_M_S
from models.clases_models import DispatchDecision, Drone, DeliveryCall
from services.funcionamiento_bateria_service import calcular_bateria_restante

class ServicioDespacho:
    
    def __init__(self, network_service):
        self.red = network_service

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float) -> int:
        # Conversión de m/s a km/h y cálculo del tiempo
        velocidad_km_h = CRUISE_SPEED_M_S * 3.6
        minutos = (distancia_km / velocidad_km_h) * 60.0
        return max(1, int(round(minutos)))

    def choose_best_drone(self, drones: List[Drone], pedido: DeliveryCall) -> Optional[DispatchDecision]:
        """
        Filtra los drones que pueden realizar la misión y elige al mejor candidato 
        basándose en reglas lógicas directas según la prioridad del pedido.
        """
        candidatos = []

        nodo_origen_pedido = self.red.get_hospital(pedido.origin_hospital)
        nodo_destino_pedido = self.red.get_hospital(pedido.destination_hospital)

        # 1. EVALUAR QUÉ DRONES SON CAPACES DE HACER EL VIAJE
        for dron in drones:
            if dron.status != "available":
                continue

            # Ubicación real del dron en este momento
            nodo_actual_dron = self.red.get_node(dron.current_node)

            # Cálculo de las distancias
            distancia_al_origen = self.red.distance_between_nodes(nodo_actual_dron, nodo_origen_pedido)
            distancia_origen_destino = self.red.distance_between_nodes(nodo_origen_pedido, nodo_destino_pedido)
            distancia_total = distancia_al_origen + distancia_origen_destino

            try:
                # Invocación directa a la función importada
                bateria_final = calcular_bateria_restante(
                    carga_kg=pedido.payload_kg,
                    distancia_km=distancia_total,
                    bateria_inicial_pct=dron.battery_percent,
                )
            except ValueError:
                continue

            # Descartar si viola el margen de seguridad
            if bateria_final < BATTERY_RESERVE_PERCENT:
                continue

            tiempo_estimado_min = self.estimar_duracion_minutos(distancia_total)

            candidatos.append(
                DispatchDecision(
                    drone_id=dron.drone_id,
                    call_id=pedido.call_id,
                    priority=pedido.priority,
                    distance_to_origin_km=distancia_al_origen,
                    distance_total_km=distancia_total,
                    battery_before_percent=dron.battery_percent,
                    battery_after_percent=bateria_final,
                    estimated_duration_min=tiempo_estimado_min,
                    score=0.0 
                )
            )

        # Si nadie puede hacer el viaje, se devuelve None
        if not candidatos:
            return None

        if pedido.priority == 1:
            candidatos.sort(key=lambda x: x.distance_to_origin_km)

        elif pedido.priority == 2:
            candidatos.sort(key=lambda x: x.distance_total_km)

        else:
            # RUTINARIO: Ordenar de mayor a menor batería restante (reverse=True).
            # Priorizamos conservar la energía general de la flota de drones.
            candidatos.sort(key=lambda x: x.battery_after_percent, reverse=True)
        
        # El primer elemento de la lista ordenada es nuestro dron ideal
        return candidatos[0]