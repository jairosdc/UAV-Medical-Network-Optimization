from models.clases_models import Drone, DeliveryCall, SimulationStats
from services.cargar_drone_service import calcular_tiempo_recarga_completa
from services.optimizador_asignacion_service import ServicioDespacho
from parametros_globales import BATERIA_MINIMA_VUELO


class GestorFlotaController:
    """
    Gestiona la flota de drones durante la simulación.

    Reglas operativas:

    1. Reposición de inventario:
       - Solo usan drones role="base".
       - Salen de una base.
       - Entregan en un hospital.
       - Vuelven a su base.

    2. Transporte de órganos:
       - Solo usan drones role="hospital".
       - Salen desde el hospital donde estén.
       - Van al hospital origen del órgano.
       - Transportan el órgano al hospital destino.
       - Se quedan en el hospital destino.
       - Si tienen batería baja, recargan en ese hospital.
       - No vuelven automáticamente a base.

    Importante:
    - Ningún pedido se rechaza automáticamente porque no haya dron ahora.
    - Si no se puede asignar, queda pending.
    """

    def __init__(self, grafo):
        self.grafo = grafo
        self.optimizador = ServicioDespacho(grafo)

        self.drones = {}

        self.pedidos_activos = {}

        self.pedidos_completados = []
        self.pedidos_rechazados = []

        self.estadisticas = SimulationStats()

    # -----------------------------------------------------------------------
    # Utilidades internas
    # -----------------------------------------------------------------------

    def _es_pedido_organo(self, pedido: DeliveryCall) -> bool:
        """
        Devuelve True si el pedido es un envío especial de órgano.
        """
        organos = {"corazon", "pulmon", "rinon", "pancreas", "higado"}

        return (
            getattr(pedido, "tipo_pedido", None) == "organo"
            or pedido.producto in organos
        )

    def agregar_dron(self, dron: Drone):
        """
        Añade un dron al sistema.

        Si el dron no tiene posición actual, se coloca en su nodo base.
        En drones hospitalarios, base_name representa su hospital inicial.
        """
        if not dron.base_name:
            raise ValueError(f"El dron {dron.drone_id} no tiene nodo inicial asignado.")

        if dron.role not in {"base", "hospital"}:
            raise ValueError(
                f"El dron {dron.drone_id} tiene un role inválido: {dron.role}"
            )

        if dron.current_node is None:
            dron.current_node = dron.base_name

        self.drones[dron.drone_id] = dron

    def inicializar_flota(
        self,
        drones_por_base: int = 2,
        drones_por_hospital: int = 1,
        drones_por_base_config=None,
        drones_por_hospital_config=None,
    ):
        """
        Crea la flota inicial.

        Si no se pasa configuración concreta, funciona como siempre.

        Ejemplo:
            drones_por_base = 2

            drones_por_base_config = {
                "BASE NORTE CAPITAL": 4,
                "BASE SUR FUENLABRADA": 3,
            }

        En ese caso:
        - las bases indicadas usan su número concreto,
        - las demás usan drones_por_base.

        Igual para hospitales con drones_por_hospital_config.
        """
        if drones_por_base_config is None:
            drones_por_base_config = {}

        if drones_por_hospital_config is None:
            drones_por_hospital_config = {}

        contador_base = 1
        contador_hospital = 1

        # Drones de reposición: viven en bases.
        for nombre_base in self.grafo.listar_bases():
            cantidad_drones = drones_por_base_config.get(
                nombre_base,
                drones_por_base,
            )

            for _ in range(cantidad_drones):
                id_dron = f"B{contador_base:03d}"

                dron = Drone(
                    drone_id=id_dron,
                    base_name=nombre_base,
                    battery_percent=100.0,
                    status="available",
                    current_node=nombre_base,
                    role="base",
                )

                self.agregar_dron(dron)
                contador_base += 1

        # Drones hospitalarios: viven inicialmente en hospitales.
        for nombre_hospital in self.grafo.listar_hospitales():
            cantidad_drones = drones_por_hospital_config.get(
                nombre_hospital,
                drones_por_hospital,
            )

            for _ in range(cantidad_drones):
                id_dron = f"H{contador_hospital:03d}"

                dron = Drone(
                    drone_id=id_dron,
                    base_name=nombre_hospital,
                    battery_percent=100.0,
                    status="available",
                    current_node=nombre_hospital,
                    role="hospital",
                )

                self.agregar_dron(dron)
                contador_hospital += 1

    def procesar_nuevo_pedido(
        self,
        pedido: DeliveryCall,
        tiempo_actual: float,
        factor_velocidad: float = 1.0,
    ):
        """
        Intenta asignar un dron disponible al pedido.

        Devuelve:
        - (eta_entrega, decision) si se ha podido asignar un dron.
        - None si no se ha podido asignar en este instante.

        Importante:
        - No rechaza pedidos automáticamente.
        - Si no hay dron viable ahora, el pedido queda pending.
        """

        es_organo = self._es_pedido_organo(pedido)

        # Solo se contabiliza la primera vez que el pedido entra al gestor.
        if not hasattr(pedido, "_ya_contabilizado"):
            self.estadisticas.total_calls += 1

            if es_organo:
                self.estadisticas.organ_calls += 1
            else:
                self.estadisticas.inventory_calls += 1

            pedido._ya_contabilizado = True

        decision = self.optimizador.elegir_mejor_dron(
            list(self.drones.values()),
            pedido,
            factor_velocidad,
            tiempo_actual,
        )

        # -------------------------------------------------------------------
        # Caso 1: no hay dron viable ahora mismo
        # -------------------------------------------------------------------

        if decision is None:
            pedido.status = "pending"
            pedido.rejection_reason = None
            return None

        # -------------------------------------------------------------------
        # Caso 2: se encuentra un dron viable
        # -------------------------------------------------------------------

        dron = self.drones[decision.drone_id]

        dron.status = "mission"
        dron.current_call_id = pedido.call_id

        # Reservamos desde ahora la batería estimada de toda la misión.
        dron.battery_percent = decision.battery_after_percent

        # Durante la misión, guardamos como nodo operativo previsto el destino.
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id
        pedido.assigned_time_min = tiempo_actual
        pedido.rejection_reason = None

        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        if es_organo:
            self.estadisticas.organ_assigned += 1

        # Estadísticas por prioridad.
        if pedido.priority in (0, 1):
            self.estadisticas.high_priority_calls += 1
        elif pedido.priority == 2:
            self.estadisticas.medium_priority_calls += 1
        else:
            self.estadisticas.low_priority_calls += 1

        eta_entrega = tiempo_actual + decision.estimated_flight_ida_min
        dron.flight_minutes += decision.estimated_flight_ida_min

        return eta_entrega, decision

    def procesar_evento_llegada_hospital(
        self,
        id_dron: str,
        tiempo_actual: float,
        decision
    ):
        """
        Procesa la llegada de un dron al hospital destino.

        Si el pedido es de órgano:
        - el pedido se completa,
        - el dron queda en el hospital destino,
        - si tiene batería suficiente, queda disponible,
        - si tiene batería baja, entra en recarga en ese hospital.

        Si el pedido es de inventario:
        - el pedido se completa,
        - el dron vuelve a su base.
        """

        dron = self.drones[id_dron]

        id_pedido = dron.current_call_id
        pedido_completado = None

        if id_pedido in self.pedidos_activos:
            pedido = self.pedidos_activos.pop(id_pedido)

            pedido.status = "completed"
            pedido.completed_time_min = tiempo_actual

            self.pedidos_completados.append(pedido)
            self.estadisticas.completed_calls += 1

            if self._es_pedido_organo(pedido):
                self.estadisticas.organ_completed += 1

                if tiempo_actual <= pedido.deadline_min:
                    self.estadisticas.organ_on_time += 1
                    self.estadisticas.on_time_calls += 1
                else:
                    self.estadisticas.organ_late += 1
                    self.estadisticas.late_calls += 1
                    pedido.is_late = True

            else:
                self.estadisticas.inventory_completed += 1
                self.estadisticas.on_time_calls += 1

            pedido_completado = pedido

        dron.deliveries_made += 1
        dron.current_call_id = None

        # -------------------------------------------------------------------
        # Caso 1: órgano
        # -------------------------------------------------------------------
        # El dron se queda en el hospital destino.
        # Si tiene batería baja, recarga en ese hospital.
        # No se programa vuelta a base.
        # -------------------------------------------------------------------

        if (
            pedido_completado is not None
            and self._es_pedido_organo(pedido_completado)
        ):
            dron.current_node = pedido_completado.destination_hospital

            if dron.battery_percent < (BATERIA_MINIMA_VUELO + 15.0):
                dron.status = "charging"

                minutos_recarga = calcular_tiempo_recarga_completa(
                    dron.battery_percent
                )

                dron.charging_minutes += int(minutos_recarga)

                tiempo_fin_recarga = tiempo_actual + minutos_recarga

                return ("fin_recarga", tiempo_fin_recarga), pedido_completado

            dron.status = "available"

            return None, pedido_completado

        # -------------------------------------------------------------------
        # Caso 2: reposición de inventario
        # -------------------------------------------------------------------
        # El dron vuelve a su base.
        # -------------------------------------------------------------------

        dron.status = "returning"

        if decision is None:
            raise ValueError(
                f"No hay DispatchDecision para el regreso del dron {id_dron}."
            )

        dron.flight_minutes += decision.estimated_flight_vuelta_min

        eta_base = tiempo_actual + decision.estimated_flight_vuelta_min

        return eta_base, pedido_completado

    def procesar_evento_aterrizaje_base(
        self,
        id_dron: str,
        tiempo_actual: float
    ):
        """
        Procesa la llegada de un dron a su base.

        Solo debe usarse para drones role="base" tras pedidos de reposición.
        """
        dron = self.drones[id_dron]

        if dron.role != "base":
            raise ValueError(
                f"El dron {id_dron} tiene role='{dron.role}' y no debería "
                f"aterrizar en base por lógica de reposición."
            )

        dron.current_node = dron.base_name

        if dron.battery_percent < (BATERIA_MINIMA_VUELO + 15.0):
            dron.status = "charging"

            minutos_recarga = calcular_tiempo_recarga_completa(
                dron.battery_percent
            )

            dron.charging_minutes += int(minutos_recarga)

            return tiempo_actual + minutos_recarga

        dron.status = "available"
        return None

    def procesar_evento_fin_recarga(self, id_dron: str):
        """
        Marca un dron como disponible después de terminar la recarga.
        """
        dron = self.drones[id_dron]

        dron.battery_percent = 100.0
        dron.status = "available"

    def obtener_resumen_estado(self):
        """
        Cuenta cuántos drones hay en cada estado y por rol.
        """
        resumen = {
            "available": 0,
            "mission": 0,
            "returning": 0,
            "charging": 0,

            "base_total": 0,
            "hospital_total": 0,
            "base_available": 0,
            "hospital_available": 0,
        }

        for dron in self.drones.values():
            if dron.status not in resumen:
                resumen[dron.status] = 0

            resumen[dron.status] += 1

            if dron.role == "base":
                resumen["base_total"] += 1
                if dron.status == "available":
                    resumen["base_available"] += 1

            elif dron.role == "hospital":
                resumen["hospital_total"] += 1
                if dron.status == "available":
                    resumen["hospital_available"] += 1

        return resumen