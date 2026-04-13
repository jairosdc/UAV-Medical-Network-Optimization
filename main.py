import argparse

from controllers.simulation_controller import SimulationController
from controllers.gestor_flota_controller import GestorFlotaController
from models.clases_models import MissionRequest, DeliveryCall
from services.grafo_distancias_service import NetworkService
from simulators.generador_pedidos import GeneradorEscenario
from parametros_globales import DEFAULT_SIMULATION_MINUTES
from models.inventario import Inventario
from cola_prioridad import GestorPrioridad

class FabricaPedidosLogistica:
    """Traductor puente entre la generación estocástica de necesidades y el modelo de transporte."""
    def __init__(self):
        self.secuencia_id = 1
        self.pesos = {"organo": 2.5, "sangre": 1.0, "antibiotico": 0.5, "suero": 1.5, "defecto": 1.0}
        
    def _obtener_peso(self, producto: str, cantidad: int) -> float:
        return self.pesos.get(producto, self.pesos["defecto"]) * cantidad

    def crear_emergencia(self, origen, destino, producto, minuto):
        call = DeliveryCall(
            call_id=self.secuencia_id, timestamp_min=minuto,
            origin_hospital=origen.nombre, destination_hospital=destino.nombre,
            payload_kg=self._obtener_peso(producto, 1), priority=1
        )
        self.secuencia_id += 1
        return call

    def crear_reposicion(self, hospital, producto, cantidad, minuto):
        call = DeliveryCall(
            call_id=self.secuencia_id, timestamp_min=minuto,
            origin_hospital="BASE SUR", 
            destination_hospital=hospital.nombre,
            payload_kg=self._obtener_peso(producto, cantidad), priority=3
        )
        self.secuencia_id += 1
        return call


def build_parser():
    parser = argparse.ArgumentParser(description="Simulador de red de drones hospitalarios")
    parser.add_argument("--mode", choices=["single", "fleet"], default="fleet")
    
    # modo single
    parser.add_argument("--origin", help="Hospital origen")
    parser.add_argument("--destination", help="Hospital destino")
    parser.add_argument("--payload", type=float, help="Carga en kg")
    parser.add_argument("--battery", type=float, default=100.0, help="Batería inicial en %")
    parser.add_argument("--date", type=str, default=None, help="Fecha clima YYYY-MM-DD")
    parser.add_argument("--ignore-weather", action="store_true", help="Ignorar validación climática")

    # modo fleet
    parser.add_argument("--minutes", type=int, default=DEFAULT_SIMULATION_MINUTES, help="Duración simulación en minutos")
    parser.add_argument("--stress-factor", type=float, default=1.0, help="Multiplicador escalar para la intensidad de la demanda")
    parser.add_argument("--drones-per-base", type=int, default=5, help="Número de drones por base")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria")
    parser.add_argument("--verbose", action="store_true", help="Mostrar eventos minuto a minuto")
    parser.add_argument("--list-hospitals", action="store_true", help="Mostrar hospitales disponibles")
    return parser


def run_single_mode(args):
    controller = SimulationController()
    request = MissionRequest(
        origin_hospital=args.origin, destination_hospital=args.destination,
        payload_kg=args.payload, battery_start_percent=args.battery,
        weather_date=args.date, ignore_weather=args.ignore_weather,
    )
    result = controller.simulate_mission(request)

    print("\n========== RESULTADO MISIÓN ==========")
    print(f"Viable: {'SÍ' if result.feasible else 'NO'}")
    print(f"Base seleccionada: {result.selected_base}")
    print(f"Distancia total: {result.distance_total_km:.2f} km" if result.distance_total_km is not None else "Distancia total: N/D")
    print(f"Tiempo estimado: {result.estimated_flight_minutes:.2f} min" if result.estimated_flight_minutes is not None else "Tiempo estimado: N/D")
    print(f"Batería final estimada: {result.battery_after_percent:.2f}%" if result.battery_after_percent is not None else "Batería final estimada: N/D")
    print(f"Clima OK: {result.weather_ok}")
    
    if result.route_plan:
        print("\n--- Ruta ---")
        print(f"Base -> Origen: {result.route_plan.distance_base_to_origin_km:.2f} km")
        print(f"Origen -> Destino: {result.route_plan.distance_origin_to_destination_km:.2f} km")
    if result.reasons:
        print("\n--- Motivos / observaciones ---")
        for r in result.reasons: print(f" - {r}")
    print("=====================================\n")


def run_fleet_mode(args):
    network = NetworkService()
    hospitales_nodos = [network.get_hospital(h) for h in network.list_hospitals()]
    
    # 1. Configuración del estado inicial de inventarios y colas
    inventarios_red = {nodo.nombre: Inventario(es_almacen_central=False) for nodo in hospitales_nodos}
    for base in network.list_bases():
        inventarios_red[base] = Inventario(es_almacen_central=True)

    cola_prioridad = GestorPrioridad()
    fabrica = FabricaPedidosLogistica()

    # 2. Inicialización de la Flota
    fleet = GestorFlotaController(network)
    fleet.inicializar_flota_por_defecto(drones_por_base=args.drones_per_base)

    # 3. Generador de Procesos de Poisson
    simulator = GeneradorEscenario(hospitales=hospitales_nodos, semilla=args.seed)

    print("\n========== INICIO SIMULACIÓN FLOTILLA ==========")
    print(f"Duración: {args.minutes} min | Estrés: {args.stress_factor}x | Drones/base: {args.drones_per_base}")
    print("================================================\n")

    # 4. Motor de Eventos Discretos
    for minute in range(args.minutes):
        
        fleet.actualizar_estado_temporal(minute)

        simulator.actualizar_minuto(
            minuto_actual=minute, 
            inventarios=inventarios_red, 
            cola=cola_prioridad, 
            fabrica_pedidos=fabrica
        )

        pedidos_rechazados_temporalmente = []
        
        while cola_prioridad.size() > 0:
            pedido = cola_prioridad.obtener_siguiente_pedido()
            decision = fleet.procesar_nuevo_pedido(pedido, minuto_actual=minute)

            if args.verbose:
                if decision is None:
                    print(
                        f"[t={minute:04d}] CALL {pedido.call_id} | P{pedido.priority} | "
                        f"{pedido.origin_hospital} -> {pedido.destination_hospital} | "
                        f"{pedido.payload_kg}kg | EN ESPERA (Falta de recursos)"
                    )
                else:
                    print(
                        f"[t={minute:04d}] CALL {pedido.call_id} | P{pedido.priority} | "
                        f"{pedido.origin_hospital} -> {pedido.destination_hospital} | "
                        f"{pedido.payload_kg}kg | "
                        f"Drone {decision.drone_id} | dist={decision.distance_total_km:.2f}km | "
                        f"bat {decision.battery_before_percent:.1f}%->{decision.battery_after_percent:.1f}% | "
                        f"dur={decision.estimated_duration_min}min"
                    )
            
            if decision is None:
                pedidos_rechazados_temporalmente.append(pedido)

        # Devolver a la cola los pedidos que experimentaron inanición ("starvation")
        for p in pedidos_rechazados_temporalmente:
            cola_prioridad.añadir_pedido(p)

        if args.verbose and minute > 0 and minute % 60 == 0:
            snapshot = fleet.obtener_resumen_estado()
            print(
                f"[t={minute:04d}] STATUS | "
                f"available={snapshot.get('available', 0)} | "
                f"mission={snapshot.get('mission', 0)} | "
                f"charging={snapshot.get('charging', 0)} | "
                f"en_cola={cola_prioridad.size()}"
            )

    # 5. Volcado de Estadísticas
    snapshot = fleet.obtener_resumen_estado()
    stats = fleet.estadisticas

    print("\n========== FIN SIMULACIÓN ==========")
    print(f"Total llamadas generadas: {stats.total_calls}")
    print(f"Asignadas: {stats.assigned_calls}")
    print(f"Rechazadas/Fallidas: {stats.rejected_calls}")
    print(f"Completadas: {stats.completed_calls}")
    print(f"En cola (Backlog final): {cola_prioridad.size()}")
    print(f"\nPrioridad alta (Emergencias): {stats.high_priority_calls}")
    print(f"Prioridad media (Urgentes): {stats.medium_priority_calls}")
    print(f"Prioridad baja (Reposición): {stats.low_priority_calls}")
    
    print("\n--- Estado final drones ---")
    print(f"Disponibles: {snapshot.get('available', 0)}")
    print(f"En misión: {snapshot.get('mission', 0)}")
    print(f"Cargando: {snapshot.get('charging', 0)}")

    print("\n--- Batería final de drones ---")
    for dron_id, drone in fleet.drones.items():
        print(f"{drone.drone_id} | {drone.base_name} | status={drone.status} | battery={drone.battery_percent:.1f}%")
    print("===================================\n")


def main():
    parser = build_parser()
    args = parser.parse_args()

    network = NetworkService()

    if args.list_hospitals:
        print("Hospitales disponibles:")
        for h in network.list_hospitals():
            print(f" - {h}")
        return

    if args.mode == "single":
        if not args.origin or not args.destination or args.payload is None:
            raise ValueError("En modo single debes indicar --origin --destination --payload")
        run_single_mode(args)
    else:
        run_fleet_mode(args)

if __name__ == "__main__":
    main()