from parametros_globales import BATERIA_MINIMA_VUELO, VELOCIDAD_DRON_M_S
from models.clases_models import DispatchDecision
from services.funcionamiento_bateria_service import calcular_bateria_restante


class ServicioDespacho:
    """
    Selecciona qué dron debe atender cada pedido.

    Para elegir un dron se tiene en cuenta:
    - que esté disponible,
    - que pueda cargar el peso del pedido,
    - que tenga batería suficiente para ir y volver,
    - el clima, que reduce la velocidad,
    - la prioridad del pedido,
    - el deadline, si el pedido lo tiene.
    """

    def __init__(self, servicio_red):
        self.red = servicio_red

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float, factor_velocidad: float = 1.0):
        """
        Calcula cuántos minutos tarda el dron en recorrer una distancia.

        El factor de velocidad viene del simulador de clima:
        - 1.00 significa velocidad normal.
        - 0.70 significa que el dron vuela al 70% de su velocidad normal.
        """
        velocidad_real_m_s = VELOCIDAD_DRON_M_S * factor_velocidad
        velocidad_km_h = velocidad_real_m_s * 3.6

        minutos = (distancia_km / velocidad_km_h) * 60.0

        return max(1, int(round(minutos)))

    def elegir_mejor_dron(
        self,
        drones,
        pedido,
        factor_velocidad: float = 1.0,
        tiempo_actual: float = 0,
    ):
        """
        Busca el mejor dron disponible para un pedido.

        Devuelve:
        - DispatchDecision si encuentra un dron viable.
        - None si ningún dron puede hacer el pedido.
        """
        origen = self.red.obtener_nodo(pedido.origin_hospital)
        destino = self.red.obtener_nodo(pedido.destination_hospital)

        candidatos = []

        for dron in drones:
            if dron.status != "available":
                continue

            base = self.red.obtener_base(dron.base_name)

            distancia_base_origen = self.red.distancia_entre_nodos_km(base, origen)
            distancia_origen_destino = self.red.distancia_entre_nodos_km(origen, destino)
            distancia_destino_base = self.red.distancia_entre_nodos_km(destino, base)

            distancia_ida = distancia_base_origen + distancia_origen_destino
            distancia_vuelta = distancia_destino_base
            distancia_total = distancia_ida + distancia_vuelta

            tiempo_ida = self.estimar_duracion_minutos(
                distancia_ida,
                factor_velocidad
            )

            tiempo_vuelta = self.estimar_duracion_minutos(
                distancia_vuelta,
                factor_velocidad
            )

            tiempo_total = tiempo_ida + tiempo_vuelta

            # Si el pedido tiene deadline, descartamos drones que llegarían tarde.
            # Esto es especialmente importante para órganos.
            eta_entrega = tiempo_actual + tiempo_ida

            if eta_entrega > pedido.deadline_min:
                continue

            try:
                bateria_despues_ida = calcular_bateria_restante(
                    carga_kg=pedido.payload_kg,
                    distancia_km=distancia_ida,
                    bateria_inicial_pct=dron.battery_percent,
                )

                bateria_final = calcular_bateria_restante(
                    carga_kg=0.0,
                    distancia_km=distancia_vuelta,
                    bateria_inicial_pct=bateria_despues_ida,
                )

            except ValueError:
                # Por ejemplo: carga superior a la capacidad del dron.
                continue

            if bateria_final < BATERIA_MINIMA_VUELO:
                continue

            decision = DispatchDecision(
                drone_id=dron.drone_id,
                call_id=pedido.call_id,
                priority=pedido.priority,
                distance_to_origin_km=distancia_base_origen,
                distance_total_km=distancia_total,
                battery_before_percent=dron.battery_percent,
                battery_after_percent=bateria_final,
                estimated_duration_min=tiempo_total,
                estimated_flight_ida_min=tiempo_ida,
                estimated_flight_vuelta_min=tiempo_vuelta,
                score=0.0,
            )

            candidatos.append(decision)

        if not candidatos:
            return None

        return self._ordenar_candidatos(candidatos, pedido)[0]

    def _ordenar_candidatos(self, candidatos, pedido):
        """
        Ordena los drones candidatos según el tipo de pedido.

        Prioridades:
        0 -> órganos o emergencias máximas: llegar lo antes posible.
        1 -> pedidos críticos: estar cerca del origen.
        2 -> pedidos urgentes: minimizar distancia total.
        3 o más -> pedidos rutinarios: conservar la mayor batería posible.
        """
        if pedido.priority == 0:
            candidatos.sort(
                key=lambda c: (
                    c.estimated_flight_ida_min,
                    c.distance_to_origin_km,
                    -c.battery_after_percent,
                )
            )

        elif pedido.priority == 1:
            candidatos.sort(
                key=lambda c: (
                    c.distance_to_origin_km,
                    c.estimated_flight_ida_min,
                    -c.battery_after_percent,
                )
            )

        elif pedido.priority == 2:
            candidatos.sort(
                key=lambda c: (
                    c.distance_total_km,
                    c.estimated_duration_min,
                    -c.battery_after_percent,
                )
            )

        else:
            candidatos.sort(
                key=lambda c: (
                    -c.battery_after_percent,
                    c.distance_total_km,
                    c.estimated_duration_min,
                )
            )

        return candidatos