from typing import Dict, List, Optional
from models.clases_models import Drone, DeliveryCall, SimulationStats
from services.cargar_drone_service import calcular_tiempo_recarga_completa
from services.optimizador_asignacion_service import ServicioDespacho

class GestorFlotaController:
    """
    Controlador de flota optimizado para Simulación de Eventos Discretos (DES).
    Abstrae la gestión de estados y delega la progresión temporal al motor de eventos.
    """
    def __init__(self, grafo):
        # Se utiliza la nomenclatura de 'grafo' para representar la topología V, E
        self.grafo = grafo
        self.optimizador = ServicioDespacho(grafo)
       
        # Estructuras de datos eficientes para acceso O(1)
        self.drones: Dict[str, Drone] = {}
        self.pedidos_activos: Dict[str, DeliveryCall] = {}
       
        # Históricos para análisis post-simulación (KPIs)
        self.pedidos_completados: List[DeliveryCall] = []
        self.pedidos_rechazados: List[DeliveryCall] = []
       
        self.estadisticas = SimulationStats()

    def agregar_dron(self, dron: Drone) -> None:
        """Registra e inicializa la ubicación física de un dron en el grafo."""
        if not dron.base_name:
            raise ValueError(f"Invariante violada: El dron {dron.drone_id} carece de base logística.")
           
        if dron.current_node is None:
            dron.current_node = dron.base_name
       
        self.drones[dron.drone_id] = dron

    def inicializar_flota(self, drones_por_base: int = 2) -> None:
        """Puebla el sistema situando recursos en los nodos de almacenamiento."""
        contador = 1
        for nombre_base in self.grafo.list_bases():
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

    def procesar_nuevo_pedido(self, pedido: DeliveryCall, tiempo_actual: float) -> Optional[float]:
        """
        Evento: 'SOLICITUD_PEDIDO'.
        Calcula la viabilidad y, de ser positiva, retorna el tiempo de llegada (ETA).
        """
        self.estadisticas.total_calls += 1
       
        # Selección del vector de transporte mediante el optimizador
        decision = self.optimizador.choose_best_drone(list(self.drones.values()), pedido)

        if decision is None:
            pedido.status = "rejected"
            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1
            return None

        # Transición de estado: Disponibilidad -> Misión
        dron = self.drones[decision.drone_id]
        dron.status = "mission"
        dron.current_call_id = pedido.call_id
       
        # Actualización de variables de estado (consumo proyectado)
        dron.battery_percent = decision.battery_after_percent
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id
        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        # Retorna el instante absoluto del evento 'ATERRIZAJE'
        return tiempo_actual + decision.estimated_duration_min

    def procesar_evento_aterrizaje(self, id_dron: str, tiempo_actual: float) -> float:
        """
        Evento: 'ATERRIZAJE'.
        Cierra el ciclo del pedido y proyecta el tiempo de recarga necesario.
        """
        dron = self.drones[id_dron]
       
        # 1. Finalización del proceso logístico del paquete
        id_pedido = dron.current_call_id
        if id_pedido in self.pedidos_activos:
            pedido = self.pedidos_activos.pop(id_pedido)
            pedido.status = "completed"
            self.pedidos_completados.append(pedido)
            self.estadisticas.completed_calls += 1

        # 2. Transición de estado: Misión -> Recarga
        dron.status = "charging"
        dron.current_call_id = None
       
        # 3. Cálculo del horizonte temporal para el evento 'FIN_RECARGA'
        minutos_recarga = calcular_tiempo_recarga_completa(dron.battery_percent)
        return tiempo_actual + minutos_recarga

    def procesar_evento_fin_recarga(self, id_dron: str) -> None:
        """
        Evento: 'FIN_RECARGA'.
        Restaura la operatividad del dron.
        """
        dron = self.drones[id_dron]
        dron.battery_percent = 100.0
        dron.status = "available"

    def obtener_resumen_estado(self) -> Dict[str, int]:
        """Snapshot de la utilización de la flota."""
        resumen = {"available": 0, "mission": 0, "charging": 0}
        for d in self.drones.values():
            resumen[d.status] += 1
        return resumen