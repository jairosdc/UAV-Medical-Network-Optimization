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

    def procesar_nuevo_pedido(self, pedido: DeliveryCall, tiempo_actual: float) -> Optional[tuple[float, object]]:
        """
        Evento: 'SOLICITUD_PEDIDO'.
        Calcula la viabilidad y retorna el tiempo de llegada al hospital y la decisión.
        """
        self.estadisticas.total_calls += 1
       
        decision = self.optimizador.elegir_mejor_dron(list(self.drones.values()), pedido)

        if decision is None:
            pedido.status = "rejected"
            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1
            return None

        dron = self.drones[decision.drone_id]
        dron.status = "mission"
        dron.current_call_id = pedido.call_id
       
        # Asumimos todo el consumo del viaje completo desde este momento
        dron.battery_percent = decision.battery_after_percent
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id
        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        eta_ida = tiempo_actual + decision.estimated_flight_ida_min
        dron.flight_minutes += decision.estimated_flight_ida_min  # Registramos tiempo de vuelo ida
        return eta_ida, decision

    def procesar_evento_llegada_hospital(self, id_dron: str, tiempo_actual: float, decision: object) -> tuple[float, Optional[DeliveryCall]]:
        """
        Evento: 'LLEGADA_HOSPITAL'. Descarga el pedido y programa el viaje de vuelta a base.
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

    def procesar_evento_aterrizaje_base(self, id_dron: str, tiempo_actual: float) -> Optional[float]:
        """
        Evento: 'ATERRIZAJE_BASE'. El dron llega a la base. Si la batería es <= 20% entra en recarga, si no, disponible.
        """
        from parametros_globales import BATERIA_MINIMA_VUELO
        dron = self.drones[id_dron]
        dron.current_node = dron.base_name
        
        # Solo recargamos si baja del umbral indicado (ej. 20%)
        if dron.battery_percent <= BATERIA_MINIMA_VUELO:
            dron.status = "charging"
            minutos_recarga = calcular_tiempo_recarga_completa(dron.battery_percent)
            dron.charging_minutes += int(minutos_recarga)
            return tiempo_actual + minutos_recarga
        else:
            dron.status = "available"
            return None

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
        resumen = {"available": 0, "mission": 0, "returning": 0, "charging": 0}
        for d in self.drones.values():
            resumen[d.status] += 1
        return resumen