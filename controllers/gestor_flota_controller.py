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
        self.estadisticas.total_calls += 1

        decision = self.optimizador.elegir_mejor_dron(
            list(self.drones.values()),
            pedido,
            factor_velocidad,
            tiempo_actual,
        )

        if decision is None:
            pedido.status = "rejected"
            pedido.rejection_reason = "No hay ningún dron viable para este pedido."

            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1

            return None

        dron = self.drones[decision.drone_id]

        dron.status = "mission"
        dron.current_call_id = pedido.call_id

        # Reservamos desde ahora la batería estimada para todo el viaje.
        dron.battery_percent = decision.battery_after_percent

        # Mientras está en misión, consideramos que su destino operativo es el hospital final.
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id

        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

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

    def procesar_evento_llegada_hospital(self, id_dron: str, tiempo_actual: float, decision):
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

            pedido_completado = pedido

        dron.status = "returning"
        dron.deliveries_made += 1
        dron.current_call_id = None
        dron.flight_minutes += decision.estimated_flight_vuelta_min

        eta_base = tiempo_actual + decision.estimated_flight_vuelta_min

        return eta_base, pedido_completado

    def procesar_evento_aterrizaje_base(self, id_dron: str, tiempo_actual: float):
        """
        Procesa la llegada de un dron a su base.

        Si la batería está por debajo del umbral mínimo, entra en recarga.
        Si no, queda disponible directamente.
        """
        dron = self.drones[id_dron]
        dron.current_node = dron.base_name

        # Se suma un margen del 15% a BATERIA_MINIMA_VUELO (20% + 15% = 35%).
        # Decidimos dejarlo en 35% porque la gran mayoría de trayectos gastan un 15% de batería.
        # De esta forma, cualquier dron 'available' tiene energía suficiente para completar
        # un viaje típico sin saltarse la norma de  seguridad obligatoria del 20% para poder volar.
        if dron.battery_percent < (BATERIA_MINIMA_VUELO + 15.0):
            dron.status = "charging"

            minutos_recarga = calcular_tiempo_recarga_completa(dron.battery_percent)
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