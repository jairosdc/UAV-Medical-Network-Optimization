from parametros_globales import BATERIA_MINIMA_VUELO, VELOCIDAD_DRON_M_S
from models.clases_models import DispatchDecision
from services.funcionamiento_bateria_service import calcular_bateria_restante


class ServicioDespacho:
    """
    Selecciona qué dron debe atender cada pedido.

    Se distinguen dos tipos de misión:

    1. Reposición de inventario:
       base -> hospital -> misma base

    2. Transporte de órganos:
       posición actual del dron -> hospital origen -> hospital destino

       El órgano solo viaja en el tramo:
       hospital origen -> hospital destino

       El dron NO vuelve automáticamente a base después de entregar un órgano.
       Eso se gestiona después en GestorFlotaController.
    """

    def __init__(self, servicio_red):
        self.red = servicio_red

    @staticmethod
    def estimar_duracion_minutos(distancia_km: float, factor_velocidad: float = 1.0):
        """
        Calcula cuántos minutos tarda el dron en recorrer una distancia.
        """
        velocidad_real_m_s = VELOCIDAD_DRON_M_S * factor_velocidad
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

        Si current_node no está definido, se asume que está en su base.
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
        - None si ningún dron puede hacer el pedido.
        """

        es_organo = self._es_pedido_organo(pedido)

        origen = self.red.obtener_nodo(pedido.origin_hospital)
        destino = self.red.obtener_nodo(pedido.destination_hospital)

        candidatos = []

        for dron in drones:
            if dron.status != "available":
                continue

            nodo_actual = self._obtener_posicion_actual_dron(dron)

            # ---------------------------------------------------------------
            # CASO 1: ÓRGANOS
            # ---------------------------------------------------------------
            # El dron puede estar en una base o en un hospital.
            # Primero va vacío hasta el hospital origen.
            # Luego transporta el órgano hasta el hospital destino.
            # No se calcula vuelta a base.
            # ---------------------------------------------------------------

            if es_organo:
                distancia_actual_origen = self.red.distancia_entre_nodos_km(
                    nodo_actual,
                    origen
                )

                distancia_origen_destino = self.red.distancia_entre_nodos_km(
                    origen,
                    destino
                )

                distancia_destino_base = 0.0

                distancia_ida = distancia_actual_origen + distancia_origen_destino
                distancia_vuelta = 0.0
                distancia_total = distancia_ida

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
                    # Tramo 1: dron vacío hasta el hospital origen
                    bateria_despues_llegar_origen = calcular_bateria_restante(
                        carga_kg=0.0,
                        distancia_km=distancia_actual_origen,
                        bateria_inicial_pct=dron.battery_percent,
                    )

                    # Tramo 2: dron con órgano hasta el hospital destino
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
            # El dron debe estar físicamente en la base origen del pedido.
            # Ruta:
            # base -> hospital -> misma base
            # ---------------------------------------------------------------

            else:
                nombre_posicion_actual = dron.current_node or dron.base_name

                # En reposición, el producto está en la base origen.
                # Si el dron no está en esa base, no puede hacer este pedido.
                if nombre_posicion_actual != pedido.origin_hospital:
                    continue

                base = self.red.obtener_base(pedido.origin_hospital)

                distancia_base_origen = 0.0

                distancia_origen_destino = self.red.distancia_entre_nodos_km(
                    base,
                    destino
                )

                distancia_destino_base = self.red.distancia_entre_nodos_km(
                    destino,
                    base
                )

                distancia_ida = distancia_origen_destino
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

                try:
                    # Ida con carga desde la base hasta el hospital
                    bateria_despues_ida = calcular_bateria_restante(
                        carga_kg=pedido.payload_kg,
                        distancia_km=distancia_ida,
                        bateria_inicial_pct=dron.battery_percent,
                    )

                    # Vuelta sin carga desde el hospital hasta la misma base
                    bateria_final = calcular_bateria_restante(
                        carga_kg=0.0,
                        distancia_km=distancia_vuelta,
                        bateria_inicial_pct=bateria_despues_ida,
                    )

                except ValueError:
                    continue

                distancia_to_origin = distancia_base_origen

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

        return candidatos[0]