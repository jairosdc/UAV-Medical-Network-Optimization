from models.clases_models import Drone, DeliveryCall, SimulationStats
from services.cargar_drone_service import calcular_tiempo_recarga_completa
from services.optimizador_asignacion_service import ServicioDespacho
from parametros_globales import BATERIA_MINIMA_VUELO


class GestorFlotaController:
    """
    Gestiona la flota de drones durante la simulación.

    Reglas operativas principales:

    1. Pedidos de reposición:
       - El dron sale desde una base.
       - Entrega en el hospital destino.
       - Vuelve a su base.

    2. Pedidos de órganos:
       - El dron puede estar en una base o en un hospital.
       - Se desplaza hasta el hospital origen.
       - Transporta el órgano hasta el hospital destino.
       - Se queda disponible en el hospital destino.
       - No vuelve automáticamente a base.
    """

    def __init__(self, grafo):
        self.grafo = grafo
        self.optimizador = ServicioDespacho(grafo)

        self.drones = {}

        self.pedidos_activos = {}

        self.pedidos_completados = []
        self.pedidos_rechazados = []

        self.estadisticas = SimulationStats()

        self._inicializar_estadisticas_organos()

    # -----------------------------------------------------------------------
    # Utilidades internas
    # -----------------------------------------------------------------------

    def _inicializar_estadisticas_organos(self):
        """
        Añade contadores específicos de órganos si no existen todavía.
        """
        if not hasattr(self.estadisticas, "organ_calls"):
            self.estadisticas.organ_calls = 0

        if not hasattr(self.estadisticas, "organ_assigned"):
            self.estadisticas.organ_assigned = 0

        if not hasattr(self.estadisticas, "organ_rejected"):
            self.estadisticas.organ_rejected = 0

        if not hasattr(self.estadisticas, "organ_completed"):
            self.estadisticas.organ_completed = 0

        if not hasattr(self.estadisticas, "organ_late"):
            self.estadisticas.organ_late = 0

        if not hasattr(self.estadisticas, "organ_on_time"):
            self.estadisticas.organ_on_time = 0

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

        Si el dron no tiene posición actual, se coloca en su base.
        """
        if not dron.base_name:
            raise ValueError(f"El dron {dron.drone_id} no tiene base asignada.")

        if dron.current_node is None:
            dron.current_node = dron.base_name

        self.drones[dron.drone_id] = dron

    def inicializar_flota(self, drones_por_base: int = 2):
        """
        Crea varios drones en cada base disponible.
        """
        contador = 1

        for nombre_base in self.grafo.listar_bases():
            for _ in range(drones_por_base):
                id_dron = f"D{contador:02d}"

                dron = Drone(
                    drone_id=id_dron,
                    base_name=nombre_base,
                    battery_percent=100.0,
                    status="available",
                    current_node=nombre_base,
                )

                self.agregar_dron(dron)
                contador += 1

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
        """

        es_organo = self._es_pedido_organo(pedido)

        # Solo contamos el pedido la primera vez que entra al gestor.
        # Esto evita contar varias veces un órgano que queda esperando en cola.
        if not hasattr(pedido, "_ya_contabilizado"):
            self.estadisticas.total_calls += 1

            if es_organo:
                self.estadisticas.organ_calls += 1

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

            # Los órganos NO se rechazan automáticamente.
            # Si no hay dron viable ahora, deben quedarse pendientes.
            if es_organo:
                pedido.status = "pending"
                pedido.rejection_reason = None
                return None

            # Los pedidos de reposición sí pueden rechazarse si no hay ruta viable.
            pedido.status = "rejected"
            pedido.rejection_reason = "No hay ningún dron viable para este pedido."

            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1

            return None

        # -------------------------------------------------------------------
        # Caso 2: se encuentra un dron viable
        # -------------------------------------------------------------------

        dron = self.drones[decision.drone_id]

        dron.status = "mission"
        dron.current_call_id = pedido.call_id

        # Reservamos desde ahora la batería estimada para toda la misión.
        dron.battery_percent = decision.battery_after_percent

        # Mientras está en misión, consideramos que su destino operativo
        # es el hospital final.
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id
        pedido.assigned_time_min = tiempo_actual

        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        if es_organo:
            self.estadisticas.organ_assigned += 1

        # Estadísticas generales por nivel de prioridad.
        if pedido.priority == 0:
            self.estadisticas.high_priority_calls += 1
        elif pedido.priority == 1:
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
        - el dron se queda en el hospital destino,
        - queda disponible allí,
        - no vuelve a base.

        Si el pedido es de reposición:
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
                else:
                    self.estadisticas.organ_late += 1

            pedido_completado = pedido

        dron.deliveries_made += 1
        dron.current_call_id = None

        # -------------------------------------------------------------------
        # Caso 1: órgano
        # -------------------------------------------------------------------
        # El dron se queda en el hospital destino.
        # No se programa vuelta a base.
        # -------------------------------------------------------------------

        if (
            pedido_completado is not None
            and self._es_pedido_organo(pedido_completado)
        ):
            dron.status = "available"
            dron.current_node = pedido_completado.destination_hospital

            return None, pedido_completado

        # -------------------------------------------------------------------
        # Caso 2: reposición
        # -------------------------------------------------------------------
        # El dron vuelve a su base.
        # -------------------------------------------------------------------

        dron.status = "returning"

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

        Solo debería usarse para pedidos de reposición.
        """
        dron = self.drones[id_dron]
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
        Cuenta cuántos drones hay en cada estado.
        """
        resumen = {
            "available": 0,
            "mission": 0,
            "returning": 0,
            "charging": 0,
        }

        for dron in self.drones.values():
            resumen[dron.status] += 1

        return resumen