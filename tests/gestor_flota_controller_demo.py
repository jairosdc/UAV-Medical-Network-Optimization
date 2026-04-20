from typing import Dict, List, Optional
from dataclasses import dataclass, field

# ---------------------------------------------------------
# 1. Mocks de Modelos y Servicios (Para ejecución de demo)
# ---------------------------------------------------------
@dataclass
class Drone:
    drone_id: str
    base_name: str
    battery_percent: float = 100.0
    status: str = "available"  # available, mission, charging
    current_node: Optional[str] = None
    busy_until_min: int = 0
    current_call_id: Optional[str] = None

@dataclass
class DeliveryCall:
    call_id: str
    destination_hospital: str
    priority: int
    status: str = "pending"
    assigned_drone_id: Optional[str] = None
    rejection_reason: Optional[str] = None

@dataclass
class DispatchDecision:
    drone_id: str
    estimated_duration_min: int
    battery_after_percent: float

@dataclass
class SimulationStats:
    total_calls: int = 0
    assigned_calls: int = 0
    completed_calls: int = 0
    rejected_calls: int = 0
    calls_by_priority: Dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0, 3: 0})

class MockServicioRed:
    def list_bases(self) -> List[str]:
        return ["Base_Norte", "Base_Sur"]

class MockOptimizador:
    def choose_best_drone(self, drones: List[Drone], pedido: DeliveryCall) -> Optional[DispatchDecision]:
        drones_disponibles = [d for d in drones if d.status == "available" and d.battery_percent > 20]
        if not drones_disponibles:
            return None
        # Asignación trivial al primer dron disponible para la demo
        dron_elegido = drones_disponibles[0]
        return DispatchDecision(
            drone_id=dron_elegido.drone_id,
            estimated_duration_min=15, 
            battery_after_percent=dron_elegido.battery_percent - 30.0 # Simula un coste del 30%
        )

def procesar_recarga_dron(dron: Drone, minutos_transcurridos: int):
    # Tasa de recarga teórica: 2% por minuto
    dron.battery_percent = min(100.0, dron.battery_percent + (2.0 * minutos_transcurridos))
    if dron.battery_percent >= 100.0:
        dron.status = "available"

# ---------------------------------------------------------
# 2. Controlador Refactorizado
# ---------------------------------------------------------
class GestorFlotaController:
    def __init__(self, servicio_red, optimizador):
        self.red = servicio_red
        self.optimizador = optimizador
        
        self.drones: Dict[str, Drone] = {}
        self.pedidos_activos: Dict[str, DeliveryCall] = {} 
        self.pedidos_completados: List[DeliveryCall] = []
        self.pedidos_rechazados: List[DeliveryCall] = []
        
        self.estadisticas = SimulationStats()

    def inicializar_flota(self, drones_por_base: int = 2) -> None:
        contador = 1
        for nombre_base in self.red.list_bases():
            for _ in range(drones_por_base):
                id_dron = f"D{contador:02d}"
                self.drones[id_dron] = Drone(
                    drone_id=id_dron,
                    base_name=nombre_base,
                    current_node=nombre_base
                )
                contador += 1

    def actualizar_estado_temporal(self, minuto_actual: int) -> None:
        """Motor temporal revisado con transiciones de estado explícitas."""
        for dron in self.drones.values():
            if dron.status == "mission" and minuto_actual >= dron.busy_until_min:
                # Transición de aterrizaje exitoso
                dron.status = "charging"
                
                # Actualización explícita del estado del pedido
                if dron.current_call_id and dron.current_call_id in self.pedidos_activos:
                    pedido_completado = self.pedidos_activos.pop(dron.current_call_id)
                    pedido_completado.status = "completed"
                    self.pedidos_completados.append(pedido_completado)
                    self.estadisticas.completed_calls += 1
                
                dron.current_call_id = None
                dron.busy_until_min = 0

            elif dron.status == "charging":
                procesar_recarga_dron(dron, minutos_transcurridos=1)

    def procesar_nuevo_pedido(self, pedido: DeliveryCall, minuto_actual: int) -> Optional[DispatchDecision]:
        self.estadisticas.total_calls += 1
        
        # Escalabilidad en métricas mediante asignación dinámica
        prioridad = pedido.priority
        if prioridad not in self.estadisticas.calls_by_priority:
            self.estadisticas.calls_by_priority[prioridad] = 0
        self.estadisticas.calls_by_priority[prioridad] += 1

        decision = self.optimizador.choose_best_drone(list(self.drones.values()), pedido)

        if decision is None:
            pedido.status = "rejected"
            pedido.rejection_reason = "Imposibilidad operativa de flota."
            self.pedidos_rechazados.append(pedido)
            self.estadisticas.rejected_calls += 1
            return None

        dron = self.drones[decision.drone_id]
        dron.status = "mission"
        dron.current_call_id = pedido.call_id
        
        # En una simulación de alta fidelidad el consumo es continuo. 
        # Para mantener la cohesión con la arquitectura actual, se aplica en bloque.
        dron.battery_percent = decision.battery_after_percent
        dron.busy_until_min = minuto_actual + decision.estimated_duration_min
        dron.current_node = pedido.destination_hospital

        pedido.status = "assigned"
        pedido.assigned_drone_id = dron.drone_id
        self.pedidos_activos[pedido.call_id] = pedido
        self.estadisticas.assigned_calls += 1

        return decision

    def obtener_resumen_estado(self) -> Dict[str, int]:
        resumen = {"available": 0, "mission": 0, "charging": 0}
        for dron in self.drones.values():
            if dron.status in resumen:
                resumen[dron.status] += 1
        return resumen

# ---------------------------------------------------------
# 3. Demostración de Ejecución (Bloque Principal)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Iniciando Simulación del Sistema Logístico de UAVs...\n")
    
    # Inyección de dependencias
    red = MockServicioRed()
    optimizador = MockOptimizador()
    gestor = GestorFlotaController(red, optimizador)
    
    # Inicialización
    gestor.inicializar_flota(drones_por_base=1)
    print(f"Estado T=0: {gestor.obtener_resumen_estado()}")
    
    # T=0: Ingresa un pedido urgente (Prioridad 1)
    pedido_1 = DeliveryCall(call_id="REQ-001", destination_hospital="Hosp_Central", priority=1)
    gestor.procesar_nuevo_pedido(pedido_1, minuto_actual=0)
    print(f"Estado T=0 (Tras pedido): {gestor.obtener_resumen_estado()}")
    print(f"Batería del D01 tras asignación: {gestor.drones['D01'].battery_percent}%")
    
    # T=10: Avanzamos el reloj. El dron requiere 15 min de vuelo.
    gestor.actualizar_estado_temporal(minuto_actual=10)
    print(f"\nEstado T=10: {gestor.obtener_resumen_estado()}")
    print(f"Pedidos completados: {len(gestor.pedidos_completados)}")
    
    # T=15: Llegada al destino
    gestor.actualizar_estado_temporal(minuto_actual=15)
    print(f"\nEstado T=15: {gestor.obtener_resumen_estado()}")
    print(f"Pedidos completados: {len(gestor.pedidos_completados)}")
    print(f"Estado de carga de D01: {gestor.drones['D01'].status} (Batería: {gestor.drones['D01'].battery_percent}%)")

    # T=20: Proceso de carga en curso (5 minutos recargando al 2% por minuto = +10%)
    for m in range(16, 21):
        gestor.actualizar_estado_temporal(minuto_actual=m)
    print(f"\nEstado T=20: {gestor.obtener_resumen_estado()}")
    print(f"Batería actual del D01 tras 5 min de recarga: {gestor.drones['D01'].battery_percent}%")