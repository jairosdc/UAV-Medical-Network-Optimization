from parametros_globales import BATERIA_MINIMA_VUELO, VELOCIDAD_DRON_M_S
from models.clases_models import DispatchDecision
from services.funcionamiento_bateria_service import calcular_bateria_restante


class ServicioDespacho:
    """
    Selecciona qué dron debe atender cada pedido.

    Tipos de misión:

    1. Reposición de inventario:
       - Solo drones role="base".
       - Ruta: base -> hospital -> misma base.

    2. Transporte de órganos:
       - Solo drones role="hospital".
       - Ruta: posición actual del dron -> hospital origen -> hospital destino.
       - El dron NO vuelve automáticamente a base.
    """

    def __init__(self, servicio_red):
        self.red = servicio_red

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float, factor_velocidad: float = 1.0):
        """
        Calcula cuántos minutos tarda el dron en recorrer una distancia.
        """
        if distancia_km <= 0:
            return 0

        velocidad_real_m_s = VELOCIDAD_DRON_M_S * factor_velocidad

        if velocidad_real_m_s <= 0:
            raise ValueError("La velocidad real del dron debe ser positiva.")

        velocidad_km_h = velocidad_real_m_s * 3.6
        minutos = (distancia_km / velocidad_km_h) * 60.0

        return max(1, int(round(minutos)))

    @staticmethod
    def _es_pedido_organo(pedido):
        """
        Devuelve True si el pedido corresponde a un transporte de órgano.
        """
        return getattr(pedido, "tipo_pedido", "inventario") == "organo"

    def _obtener_posicion_actual_dron(self, dron):
        """
        Devuelve el nodo donde está físicamente el dron.

        Si current_node no está definido, se asume que está en su nodo inicial.
        """
        nombre_nodo_actual = dron.current_node or dron.base_name
        return self.red.obtener_nodo(nombre_nodo_actual)

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
        - None si ningún dron puede hacer el pedido ahora.
        """

        es_organo = self._es_pedido_organo(pedido)

        origen = self.red.obtener_nodo(pedido.origin_hospital)
        destino = self.red.obtener_nodo(pedido.destination_hospital)

        candidatos = []

        for dron in drones:
            if dron.status != "available":
                continue

            # ---------------------------------------------------------------
            # CASO 1: ÓRGANOS
            # ---------------------------------------------------------------
            # Solo pueden atenderlos drones hospitalarios.
            # Ruta:
            # posición actual -> hospital origen -> hospital destino
            # ---------------------------------------------------------------

            if es_organo:
                if getattr(dron, "role", "base") != "hospital":
                    continue

                nodo_actual = self._obtener_posicion_actual_dron(dron)

                distancia_actual_origen = self.red.distancia_entre_nodos_km(
                    nodo_actual,
                    origen
                )

                distancia_origen_destino = self.red.distancia_entre_nodos_km(
                    origen,
                    destino
                )

                distancia_total = distancia_actual_origen + distancia_origen_destino

                tiempo_actual_origen = self.estimar_duracion_minutos(
                    distancia_actual_origen,
                    factor_velocidad
                )

                tiempo_origen_destino = self.estimar_duracion_minutos(
                    distancia_origen_destino,
                    factor_velocidad
                )

                tiempo_ida = tiempo_actual_origen + tiempo_origen_destino
                tiempo_vuelta = 0
                tiempo_total = tiempo_ida

                try:
                    bateria_despues_llegar_origen = calcular_bateria_restante(
                        carga_kg=0.0,
                        distancia_km=distancia_actual_origen,
                        bateria_inicial_pct=dron.battery_percent,
                    )

                    bateria_final = calcular_bateria_restante(
                        carga_kg=pedido.payload_kg,
                        distancia_km=distancia_origen_destino,
                        bateria_inicial_pct=bateria_despues_llegar_origen,
                    )

                except ValueError:
                    continue

                distancia_to_origin = distancia_actual_origen

            # ---------------------------------------------------------------
            # CASO 2: REPOSICIÓN / INVENTARIO
            # ---------------------------------------------------------------
            # Solo pueden atenderlos drones de base.
            # Ruta:
            # base -> hospital -> misma base
            # ---------------------------------------------------------------

            else:
                if getattr(dron, "role", "base") != "base":
                    continue

                nombre_posicion_actual = dron.current_node or dron.base_name

                # En reposición, el pedido sale de una base.
                # El dron debe estar físicamente en esa base.
                if nombre_posicion_actual != pedido.origin_hospital:
                    continue

                base = self.red.obtener_base(pedido.origin_hospital)

                distancia_base_destino = self.red.distancia_entre_nodos_km(
                    base,
                    destino
                )

                distancia_destino_base = self.red.distancia_entre_nodos_km(
                    destino,
                    base
                )

                distancia_total = distancia_base_destino + distancia_destino_base

                tiempo_ida = self.estimar_duracion_minutos(
                    distancia_base_destino,
                    factor_velocidad
                )

                tiempo_vuelta = self.estimar_duracion_minutos(
                    distancia_destino_base,
                    factor_velocidad
                )

                tiempo_total = tiempo_ida + tiempo_vuelta

                try:
                    bateria_despues_ida = calcular_bateria_restante(
                        carga_kg=pedido.payload_kg,
                        distancia_km=distancia_base_destino,
                        bateria_inicial_pct=dron.battery_percent,
                    )

                    bateria_final = calcular_bateria_restante(
                        carga_kg=0.0,
                        distancia_km=distancia_destino_base,
                        bateria_inicial_pct=bateria_despues_ida,
                    )

                except ValueError:
                    continue

                distancia_to_origin = 0.0

            # ---------------------------------------------------------------
            # FILTRO DE BATERÍA
            # ---------------------------------------------------------------

            if bateria_final < BATERIA_MINIMA_VUELO:
                continue

            decision = DispatchDecision(
                drone_id=dron.drone_id,
                call_id=pedido.call_id,
                priority=pedido.priority,
                distance_to_origin_km=distancia_to_origin,
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

        return self._ordenar_candidatos(candidatos, pedido)

    def _ordenar_candidatos(self, candidatos, pedido):
        """
        Ordena los drones candidatos según el tipo de pedido.

        Prioridades:
        0 -> órganos: entregar lo antes posible.
        1 -> pedidos críticos: estar cerca del origen.
        2 -> pedidos urgentes: minimizar distancia total.
        3 o más -> pedidos rutinarios: conservar batería.
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

        return candidatos[0]