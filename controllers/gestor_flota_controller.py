from models.clases_models import Drone, DeliveryCall, SimulationStats
from services.cargar_drone_service import calcular_tiempo_recarga_completa
from services.optimizador_asignacion_service import ServicioDespacho
from parametros_globales import BATERIA_MINIMA_VUELO


class GestorFlotaController:
    """
    Gestiona la flota de drones durante la simulación.

    Esta clase no decide cómo se calcula la mejor ruta.
    Para eso usa ServicioDespacho.

    Se encarga de:
    - crear los drones iniciales,
    - guardar el estado de cada dron,
    - asignar pedidos a drones,
    - procesar llegadas a hospitales,
    - procesar regresos a base,
    - procesar recargas,
    - guardar estadísticas básicas.
    """

    def __init__(self, grafo):
        self.grafo = grafo
        self.optimizador = ServicioDespacho(grafo)

        # Drones guardados por identificador.
        self.drones = {}

        # Pedidos que ya han salido y todavía no han terminado.
        self.pedidos_activos = {}

        # Historial de pedidos para analizar resultados al final.
        self.pedidos_completados = []
        self.pedidos_rechazados = []

        self.estadisticas = SimulationStats()

        # Estadísticas específicas de órganos.
        # Las inicializamos aquí para no depender de que ya estén añadidas
        # en la dataclass SimulationStats.
        self._inicializar_estadisticas_organos()

    # -----------------------------------------------------------------------
    # Utilidades internas
    # -----------------------------------------------------------------------

    def _inicializar_estadisticas_organos(self):
        """
        Añade contadores específicos de órganos si no existen todavía.

        Esto evita errores aunque SimulationStats aún no tenga estos campos
        definidos explícitamente.
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

        Se comprueba por tipo_pedido, que es lo correcto.
        Además, se deja una comprobación auxiliar por producto para evitar
        problemas si algún pedido antiguo no tiene todavía tipo_pedido.
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
        - (eta_ida, decision) si se ha podido asignar un dron.
        - None si ningún dron puede realizar el pedido.
        """

        # Todo pedido que llega aquí cuenta como pedido procesado.
        self.estadisticas.total_calls += 1

        # Si es órgano, aumenta el contador específico de órganos recibidos.
        if self._es_pedido_organo(pedido):
            self.estadisticas.organ_calls += 1

        decision = self.optimizador.elegir_mejor_dron(
            list(self.drones.values()),
            pedido,
            factor_velocidad,
            tiempo_actual,
        )

        # -------------------------------------------------------------------
        # Caso 1: ningún dron puede realizar el pedido
        # -------------------------------------------------------------------

        if decision is None:
            pedido.status = "rejected"
            pedido.rejection_reason = "No hay ningún dron viable para este pedido."

            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1

            # Estadística específica de órganos rechazados.
            if self._es_pedido_organo(pedido):
                self.estadisticas.organ_rejected += 1

            return None

        # -------------------------------------------------------------------
        # Caso 2: se encuentra un dron viable
        # -------------------------------------------------------------------

        dron = self.drones[decision.drone_id]

        dron.status = "mission"
        dron.current_call_id = pedido.call_id

        # Reservamos desde ahora la batería estimada para todo el viaje.
        dron.battery_percent = decision.battery_after_percent

        # Mientras está en misión, consideramos que su destino operativo
        # es el hospital final.
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id

        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        # Estadística específica de órganos asignados.
        if self._es_pedido_organo(pedido):
            self.estadisticas.organ_assigned += 1

        # Estadísticas generales por nivel de prioridad.
        # Prioridad 0 = órganos / máxima prioridad.
        # Prioridad 1 = crítica.
        # Prioridad 2 = urgente/media.
        # Prioridad 3 = rutinaria/baja.
        if pedido.priority == 0:
            self.estadisticas.high_priority_calls += 1
        elif pedido.priority == 1:
            self.estadisticas.high_priority_calls += 1
        elif pedido.priority == 2:
            self.estadisticas.medium_priority_calls += 1
        else:
            self.estadisticas.low_priority_calls += 1

        eta_ida = tiempo_actual + decision.estimated_flight_ida_min
        dron.flight_minutes += decision.estimated_flight_ida_min

        return eta_ida, decision

    def procesar_evento_llegada_hospital(
        self,
        id_dron: str,
        tiempo_actual: float,
        decision
    ):
        """
        Procesa la llegada de un dron al hospital de destino.

        En este punto:
        - el pedido se marca como completado,
        - el dron pasa a estado de regreso,
        - se calcula cuándo llegará de vuelta a su base.
        """
        dron = self.drones[id_dron]

        id_pedido = dron.current_call_id
        pedido_completado = None

        if id_pedido in self.pedidos_activos:
            pedido = self.pedidos_activos.pop(id_pedido)

            pedido.status = "completed"
            self.pedidos_completados.append(pedido)
            self.estadisticas.completed_calls += 1

            # Estadísticas específicas de órganos completados.
            if self._es_pedido_organo(pedido):
                self.estadisticas.organ_completed += 1

                # Comprobamos si llegó dentro del límite de isquemia.
                if tiempo_actual <= pedido.deadline_min:
                    self.estadisticas.organ_on_time += 1
                else:
                    self.estadisticas.organ_late += 1

            pedido_completado = pedido

        dron.status = "returning"
        dron.deliveries_made += 1
        dron.current_call_id = None

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

        Si la batería está por debajo del umbral mínimo, entra en recarga.
        Si no, queda disponible directamente.
        """
        dron = self.drones[id_dron]
        dron.current_node = dron.base_name

        # Se suma un margen del 15% a BATERIA_MINIMA_VUELO.
        # Ejemplo:
        # BATERIA_MINIMA_VUELO = 20%
        # Margen extra = 15%
        # Umbral operativo = 35%
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