from typing import Dict, List, Optional
from models.clases_models import Drone, DeliveryCall, SimulationStats
from services.cargar_drone_service import procesar_recarga_dron
from services.optimizador_asignacion_service import ServicioDespacho


class GestorFlotaController:
    """
    Controlador principal de la flota de drones.
    Gestiona el ciclo de vida completo de los drones y los pedidos durante la simulación,
    cumpliendo con la simulación de eventos discretos estipulada en la arquitectura del proyecto.
    """
    def __init__(self, servicio_red):
        self.red = servicio_red
        # El optimizador decide qué dron es el más eficiente para cada pedido
        self.optimizador = DispatcherService(servicio_red)
        
        # Diccionario para buscar drones rápidamente por su identificador (ej: "D01")
        self.drones: Dict[str, Drone] = {}
        
        # Listas para rastrear la trazabilidad de los pedidos (la "cola" del sistema)
        self.pedidos_activos: List[DeliveryCall] = []
        self.pedidos_completados: List[DeliveryCall] = []
        self.pedidos_rechazados: List[DeliveryCall] = []
        
        # Objeto de registro para generar los KPIs de la simulación al final del día
        self.estadisticas = SimulationStats()

    def agregar_dron(self, dron: Drone) -> None:
        """Registra un nuevo dron en el sistema logístico."""
        # Si el dron acaba de crearse y no tiene ubicación, lo situamos físicamente en su base
        if dron.current_node is None:
            dron.current_node = dron.base_name
        
        self.drones[dron.drone_id] = dron

    def inicializar_flota_por_defecto(self, drones_por_base: int = 2) -> None:
        """
        Despliega los drones iniciales repartiéndolos equitativamente en los almacenes (Norte y Sur).
        Todos los equipos inician con la batería al 100% y en estado de alerta.
        """
        contador = 1
        # Extrae los nodos que actúan como almacén desde el grafo de la red logística
        for nombre_base in self.red.list_bases():
            for _ in range(drones_por_base):
                id_dron = f"D{contador:02d}"
                dron = Drone(
                    drone_id=id_dron,
                    base_name=nombre_base,
                    battery_percent=100.0,
                    status="available",
                    current_node=nombre_base
                )
                self.agregar_dron(dron)
                contador += 1

    def actualizar_estado_temporal(self, minuto_actual: int) -> None:
        """
        Motor temporal del simulador: avanza el reloj 1 minuto por ejecución.
        Verifica si los drones han finalizado sus vuelos y gestiona las curvas de recarga.
        """
        # 1. Evaluar la situación de la flota de drones
        for dron in self.drones.values():
            # Si estaba volando y el reloj general supera su tiempo de llegada
            if dron.status == "mission" and minuto_actual >= dron.busy_until_min:
                # El dron aterriza, finaliza la misión y pasa automáticamente a recargar
                dron.status = "charging"
                dron.current_call_id = None
                dron.busy_until_min = 0

            # Si está recargando
            elif dron.status == "charging":
                # Se incrementa su batería según la capacidad técnica del cargador en 1 minuto
                ChargingService.update_drone_charging(dron, elapsed_minutes=1)

        # 2. Actualizar la situación de los paquetes en tránsito
        pedidos_aun_activos = []
        for pedido in self.pedidos_activos:
            dron_asignado = self.obtener_dron_por_id(pedido.assigned_drone_id)
            
            # Si el dron que lo transportaba ya no marca estado "mission", 
            # se confirma la entrega en destino.
            if dron_asignado and dron_asignado.status != "mission":
                pedido.status = "completed"
                self.pedidos_completados.append(pedido)
                self.estadisticas.completed_calls += 1
            else:
                # Si sigue volando, se mantiene en la lista de seguimiento
                pedidos_aun_activos.append(pedido)

        # Se purga la lista dejando únicamente los vuelos activos
        self.pedidos_activos = pedidos_aun_activos

    def obtener_dron_por_id(self, id_dron: str) -> Optional[Drone]:
        """Consulta directa y eficiente de la instancia de un dron específico."""
        return self.drones.get(id_dron)

    def procesar_nuevo_pedido(self, pedido: DeliveryCall, minuto_actual: int):
        """
        Recibe una solicitud del hospital e intenta ejecutar el despacho.
        El optimizador evaluará las rutas en el grafo, la meteorología y la autonomía restante.
        """
        self.estadisticas.total_calls += 1

        # Segregación estadística según la prioridad clínica o logística del envío
        if pedido.priority == 1:
            self.estadisticas.high_priority_calls += 1
        elif pedido.priority == 2:
            self.estadisticas.medium_priority_calls += 1
        else:
            self.estadisticas.low_priority_calls += 1

        # Delegamos en el módulo de optimización la selección del mejor vector de transporte
        decision = self.optimizador.choose_best_drone(list(self.drones.values()), pedido)

        # Si no hay solución viable (flota ocupada, clima extremo o distancia inalcanzable)
        if decision is None:
            pedido.status = "rejected"
            pedido.rejection_reason = "Imposibilidad operativa: Sin flota o sin alcance/batería."
            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1
            return None

        # Si la misión es factible, bloqueamos los recursos
        dron = self.obtener_dron_por_id(decision.drone_id)

        dron.status = "mission"
        dron.current_call_id = pedido.call_id
        
        # Descontamos anticipadamente la batería consumida en el trayecto planificado
        dron.battery_percent = decision.battery_after_percent
        # Bloqueamos el dron hasta el minuto futuro de llegada calculada
        dron.busy_until_min = minuto_actual + decision.estimated_duration_min
        # Proyectamos su ubicación futura para posteriores decisiones lógicas
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id

        self.pedidos_activos.append(pedido)
        self.estadisticas.assigned_calls += 1

        return decision

    def obtener_resumen_estado(self) -> Dict[str, int]:
        """
        Genera una radiografía instantánea de la ocupación del sistema.
        Fundamental para calcular la utilización media de la flota.
        """
        resumen = {
            "available": 0,
            "mission": 0,
            "charging": 0,
        }
        
        for dron in self.drones.values():
            resumen[dron.status] += 1

        return resumen